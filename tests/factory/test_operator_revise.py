"""Operator revise: apply a task contract revision to the live graph in one recorded graph revision.

Offline unit tests over a scratch store and contract file; no live agent, image or lab result.
"""
import copy
import json

import pytest

from jiuwenswarm.factory import node_contract, scheduler, taskgraph
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.node_finalize import draft_final
from jiuwenswarm.factory.taskgraph import (format_revise, operator_patch, operator_revise, plan_get, plan_patch,
                                           replay, seed_plan)

from test_node_contracts import tiny_nodes, write_contract

CC = 'factory.evidence'


def v1():
    """integrate -> port -> build -> deliver (the live shape: a port node a revision will remove)."""
    integrate, build, deliver = copy.deepcopy(tiny_nodes()['nodes'])
    integrate['hands_to'] = 'port'
    port = dict(node_id='port', kind='integrate', objective='Port the cache.', predecessors=['integrate'],
                outputs=[dict(name='change', kind='diff')],
                verifiers=[dict(output='change', verifier='test.build_thing.verify', review=True)], hands_to='build')
    build.update(predecessors=['port'], inputs=[])
    return dict(format='factory.node-contracts/1', nodes=[integrate, port, build, deliver])


def v2():
    """port removed; a new preliminary image node after integrate; build now after image; text changes on integrate."""
    integrate, _, build, deliver = v1()['nodes']
    integrate.update(hands_to='image', requirement_ids=['C3'], objective='Add the thing, off by default (rev 2 wording).')
    image = dict(node_id='image', kind='build', objective='Build the engine image.', predecessors=['integrate'],
                 stage='preliminary', outputs=[dict(name='image', kind='image')], verifiers=[dict(output='image')],
                 hands_to='build')
    build.update(predecessors=['image'], objective='Bundle the image for the lab.')
    return dict(format='factory.node-contracts/1', nodes=[integrate, image, build, deliver])


def write(path, nodes):
    document = json.loads(open(path).read())
    document['extensions']['factory.node-contracts'] = nodes
    document['version'] = document.get('version', 1) + 1
    with open(path, 'w') as out:
        json.dump(document, out)


@pytest.fixture
def live(store, tmp_path):
    path = write_contract(tmp_path, v1())
    store.create_task(dict(task_id='rv', objective='o', contract_id=path, constraints={}))
    seed_plan(store, store.get_task('rv'))
    store.advance_decision('rv', 0, {'hypothesis': 'work the planned nodes'})
    return store, path


def nodes_of(store):
    return {n['node_id']: n for n in plan_get(store, 'rv')['nodes']}


def finish(store, key):
    """Mark a node done with host node checks for its outputs (what node_check would have recorded)."""
    node = nodes_of(store)[key]
    ids = []
    for entry in node['check']['outputs']:
        row = store.append_observation('rv', dict(obs_id=f'nc-{key}-{entry["name"]}', kind='node_check', host_run={},
                                                  values=dict(node_id=key, output=entry['name'], state='finished',
                                                              passed=True, entry=entry, key='k')))
        ids.append(row['obs_id'])
    plan_patch(store, 'rv', {'update': [dict(node_id=key, state='done', evidence_ids=ids)]}, plan_get(store, 'rv')['rev'], 1)


def test_revise_cancels_adds_and_rewires_in_one_revision(live):
    store, path = live
    finish(store, 'integrate')
    # A capped job of an unchanged node keeps running through the revise.
    store.create_attempt('rv', dict(attempt_id='busy', kind='lab', idem_key='i', fingerprint='f', request={'node_id': 'deliver'}))
    write(path, v2())
    before = plan_get(store, 'rv')

    dry = operator_revise(store, 'rv', 'rev 2 moves the port to the lab', dry_run=True)
    assert dry['dry_run'] and not dry['applied'] and plan_get(store, 'rv')['rev'] == before['rev']
    actions = {(c['action'], c['node_id']) for c in dry['changes']}
    assert actions == {('cancel', 'port'), ('add', 'image'), ('update', 'build')}
    assert 'dry run, nothing written' in format_revise(dry) and 'add    image' in format_revise(dry)

    result = operator_revise(store, 'rv', 'rev 2 moves the port to the lab')
    assert result['applied'] and result['graph_rev'] == before['rev'] + 1 and result['changes'] == dry['changes']
    graph = plan_get(store, 'rv')
    entry = graph['history'][-1]
    assert entry['origin'] == 'operator' and list(entry['patch']) == ['revise'] and len(graph['history']) == len(before['history']) + 1
    nodes = {n['node_id']: n for n in graph['nodes']}
    assert nodes['port']['state'] == 'cancelled' and nodes['port']['reason'].startswith('retired by operator revise')
    assert nodes['image']['state'] == 'proposed' and nodes['image']['depends_on'] == ['integrate']
    assert nodes['image']['node_contract'] == 'image' and 'final_contract' not in nodes['image']
    assert nodes['image']['check'] == node_contract.check_spec(v2()['nodes'][1]) and nodes['image']['resources'] == {'class': 'build'}
    assert nodes['build']['depends_on'] == ['image'] and nodes['deliver']['depends_on'] == ['build']
    assert nodes['build']['title'] == 'Bundle the image for the lab.'
    update = next(c for c in result['changes'] if c['node_id'] == 'build')
    assert update['was']['depends_on'] == ['port']
    assert nodes['integrate']['state'] == 'done'  # text changes leave a done node as it is
    assert 'version' in entry['patch']['revise'][0]['reason']
    # The history replays to the same graph.
    assert replay('rv', graph['history'])['nodes'] == graph['nodes']

    # The added preliminary node goes through the scheduler's finalize flow like a planned one.
    work = scheduler.next_work(store, 'rv')
    assert [i['node_id'] for i in work['to_finalize']] == ['image']
    contracts = node_contract.for_task(store.get_task('rv'))
    contract, needs = scheduler.effective_contract(store, 'rv', nodes['image'], contracts)
    assert needs and contract['stage'] == 'preliminary'
    final = draft_final(contract)
    final['work'] = dict(bound_ccs=[CC])
    admitted = scheduler.finalize(store, 'rv', 'image', final, 'bind the evidence capsule')
    assert admitted['admitted'], admitted
    work = scheduler.next_work(store, 'rv')
    assert [i['node_id'] for i in work['runnable']] == ['image'] and not work['to_finalize']

    # Idempotent: a second revise has nothing to change and records nothing.
    again = operator_revise(store, 'rv', 'again')
    assert not again['applied'] and again['changes'] == [] and plan_get(store, 'rv')['rev'] == admitted['graph_rev']
    assert 'nothing to change' in format_revise(again)


def test_revise_refuses_and_changes_nothing(live):
    store, path = live
    finish(store, 'integrate')
    rev = plan_get(store, 'rv')['rev']

    # A done node's contract removed.
    nodes = v1()
    nodes['nodes'] = nodes['nodes'][1:]
    nodes['nodes'][0]['predecessors'] = []
    write(path, nodes)
    with pytest.raises(ValueError, match='integrate is done but the revision removed'):
        operator_revise(store, 'rv', 'x')
    with pytest.raises(ValueError, match='integrate is done but the revision removed'):
        operator_revise(store, 'rv', 'x', dry_run=True)

    assert plan_get(store, 'rv')['rev'] == rev

    # A done node's predecessors changed.
    write(path, v1())
    finish(store, 'port')
    rev = plan_get(store, 'rv')['rev']
    nodes = v1()
    nodes['nodes'][1]['predecessors'] = []
    nodes['nodes'][0]['hands_to'] = 'deliver'
    nodes['nodes'][3]['predecessors'] = ['build', 'integrate']
    write(path, nodes)
    with pytest.raises(ValueError, match='port is done and the revision changed its predecessors'):
        operator_revise(store, 'rv', 'x')
    assert plan_get(store, 'rv')['rev'] == rev


def test_revise_refuses_a_change_to_a_running_node(live):
    store, path = live
    finish(store, 'integrate')
    plan_patch(store, 'rv', {'update': [dict(node_id='port', state='running')]}, plan_get(store, 'rv')['rev'], 1)
    write(path, v2())
    rev = plan_get(store, 'rv')['rev']
    with pytest.raises(ValueError, match='port is running'):
        operator_revise(store, 'rv', 'x')
    assert plan_get(store, 'rv')['rev'] == rev


def test_a_queued_attempt_counts_as_running(live):
    store, path = live
    finish(store, 'integrate')
    store.create_attempt('rv', dict(attempt_id='q', kind='build', idem_key='i', fingerprint='f', request={'node_id': 'port'}))
    write(path, v2())
    with pytest.raises(ValueError, match='port is running'):
        operator_revise(store, 'rv', 'x')


def test_revise_refuses_a_cycle_or_a_missing_dependency(live, monkeypatch):
    store, path = live
    rev = plan_get(store, 'rv')['rev']
    for depends, message in ((['deliver'], 'cycle'), (['nowhere'], 'does not exist')):
        monkeypatch.setattr(taskgraph, 'revise_changes', lambda *a, d=depends, **k: (
            [dict(node_id='integrate', reason='r', action='update', depends_on=d, was=dict(depends_on=[]))], []))
        with pytest.raises(ValueError, match=message):
            operator_revise(store, 'rv', 'x')
        with pytest.raises(ValueError, match=message):
            operator_revise(store, 'rv', 'x', dry_run=True)
    assert plan_get(store, 'rv')['rev'] == rev


def test_a_finalized_node_whose_preliminary_changed_is_finalized_again(store, tmp_path):
    from test_node_finalize import good_final, preliminary_nodes
    path = write_contract(tmp_path, preliminary_nodes())
    store.create_task(dict(task_id='rv', objective='o', contract_id=path, constraints={}))
    seed_plan(store, store.get_task('rv'))
    store.advance_decision('rv', 0, {'hypothesis': 'h'})
    first = scheduler.finalize(store, 'rv', 'integrate', good_final(), 'first')
    assert first['admitted']
    assert operator_revise(store, 'rv', 'nothing changed yet')['changes'] == []
    changed = preliminary_nodes()
    changed['nodes'][0]['outputs'][0]['criteria'].append('Logs one line when on.')
    write(path, changed)
    result = operator_revise(store, 'rv', 'rev adds a criterion')
    update = next(c for c in result['changes'] if c['node_id'] == 'integrate')
    assert update['unfinalize'] and update['was']['final_contract'] == first['digest']
    node = nodes_of(store)['integrate']
    assert 'final_contract' not in node and node['check'] == node_contract.check_spec(changed['nodes'][0])
    assert [i['node_id'] for i in scheduler.next_work(store, 'rv')['to_finalize']] == ['integrate']
    final = good_final(changed['nodes'][0])
    assert scheduler.finalize(store, 'rv', 'integrate', final, 'under the new preliminary contract')['admitted']


def test_revise_needs_a_reason_and_is_not_a_node_op(live):
    store, _ = live
    with pytest.raises(ValueError, match='reason'):
        operator_revise(store, 'rv', ' ')
    with pytest.raises(ValueError, match='operator_revise'):
        operator_patch(store, 'rv', 'revise', 'port', 'x')


def test_controller_revise_notes_the_agent_and_forgets_step_checkpoints(live):
    store, path = live
    finish(store, 'integrate')
    controller = Controller(store=store, facade=object())
    state = controller._load('rv')
    state.update(stepped=['port', 'integrate'], finalize_tries={'port': 1})
    controller._save('rv', state)
    write(path, v2())
    assert controller.revise('rv', 'apply rev 2', dry_run=True)['applied'] is False
    result = controller.revise('rv', 'apply rev 2')
    assert result['applied']
    state = controller._load('rv')
    assert state['stepped'] == ['integrate'] and state['finalize_tries'] == {}
    from jiuwenswarm.factory.operator_notes import pending
    notes = pending(controller.home, 'rv', state)
    assert any('cancelled port' in n['text'] and 'added image' in n['text'] and 'rewired build' in n['text'] for n in notes)


def test_cli_revise_dry_run(live, capsys, monkeypatch):
    from jiuwenswarm.factory import cli
    store, path = live
    finish(store, 'integrate')
    write(path, v2())
    monkeypatch.setattr('jiuwenswarm.factory.cli.check_legacy_config_or_exit', lambda: None)
    cli.main(['--home', str(store.home), 'revise', 'rv', 'apply rev 2', '--dry-run'])
    out = capsys.readouterr().out
    assert 'dry run, nothing written' in out and 'cancel port' in out and 'update build: depends_on [port] -> [image]' in out
    assert plan_get(store, 'rv')['history'][-1]['origin'] != 'operator'
