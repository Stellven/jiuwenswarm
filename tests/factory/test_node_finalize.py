"""Preliminary node contracts, finalized by the scheduler just before the node runs.

The planner writes a rough contract with slots; the scheduler agent proposes the final one; control
code admits it only when it is more concrete or stricter, never weaker.
"""
import copy
import json

import pytest

from jiuwenswarm.factory import node_contract, scheduler
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.node_finalize import check_final, diff, draft_final, preliminary_problems
from jiuwenswarm.factory.store import ScopeDenied
from jiuwenswarm.factory.taskgraph import operator_patch, plan_get, plan_patch, seed_plan

from test_node_contracts import tiny_nodes, write_contract

CC = 'factory.evidence'  # a real catalog capsule; the scheduler binds from the factory catalog


def preliminary_nodes():
    nodes = tiny_nodes()
    integrate = nodes['nodes'][0]
    integrate.update(
        stage='preliminary',
        node_limits=dict(turns=20, build_attempts=3),
        authority_ceiling=dict(effects=['workspace.read', 'process.exec'], workspace='read'),
        evidence_obligations=['mandatory_checks'],
        work=dict(helpful_ccs=['test.build_thing'], eligible_ccs=[CC, 'factory.node_check']),
        slots=[dict(id='bind', at='work.bound_ccs', kind='ccs', from_='catalog'),
               dict(id='tolerance', at='verifiers.change.inputs.tolerance', kind='number', within=[0, 5],
                    from_='the measured noise of the upstream run'),
               dict(id='concrete', at='outputs.change.criteria', kind='criteria', from_='the accepted inputs')],
        bounds={'verifiers.change.inputs.expect_range': 'inside'})
    for slot in integrate['slots']:
        slot['from'] = slot.pop('from_')
    integrate['verifiers'][0]['inputs'] = dict(expect_range=[10, 100])
    return nodes


def prelim():
    return preliminary_nodes()['nodes'][0]


def good_final(p=None):
    final = draft_final(p or prelim())
    final['work']['bound_ccs'] = [CC]
    final['verifiers'][0]['inputs']['tolerance'] = 2
    final['outputs'][0]['criteria'].append('The gate reads FACTORY_THING; unset keeps stock outputs byte for byte.')
    return final


def test_a_preliminary_contract_is_valid_and_a_filled_draft_is_admitted():
    p = prelim()
    assert preliminary_problems(p) == []
    assert node_contract.problems(preliminary_nodes()) == []
    assert check_final(p, good_final(p), known_ccs={CC, 'factory.node_check'}) == []


def test_stricter_is_admitted():
    final = good_final()
    final['verifiers'][0]['inputs']['expect_range'] = [20, 80]        # narrower
    final['node_limits']['turns'] = 10                                 # lower
    final['node_limits']['gpu_launches'] = 1                           # a new limit
    final['authority_ceiling'] = dict(effects=['workspace.read'], workspace='none')
    final['evidence_obligations'].append('semantic_assessment')
    final['requirement_ids'].append('client_ttft_ms')
    assert check_final(prelim(), final, known_ccs={CC}) == []


def _set(path, value):
    def change(final):
        target = final
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
    return change


@pytest.mark.parametrize('change,message', [
    (_set(['objective'], 'Something easier.'), 'objective must stay'),
    (_set(['predecessors'], ['deliver']), 'predecessors must stay'),
    (lambda f: f['outputs'][0]['criteria'].remove('Off by default.'), 'word for word'),
    (lambda f: f['outputs'][0]['criteria'].__setitem__(0, 'Off by default, mostly.'), 'word for word'),
    (_set(['verifiers', 0, 'inputs', 'expect_range'], [5, 100]), 'may only narrow'),
    (_set(['verifiers', 0, 'inputs', 'tolerance'], 9), 'outside the allowed'),
    (lambda f: f['verifiers'][0]['inputs'].pop('tolerance'), 'tolerance is not filled'),
    (_set(['verifiers', 0, 'inputs', 'skip_slow_checks'], True), 'only through a slot'),
    (_set(['verifiers', 0, 'review'], False), 'review stays on'),
    (_set(['verifiers', 0, 'stage'], 'fixture'), 'stage must stay'),
    (_set(['node_limits', 'turns'], 40), 'exceeds the ceiling'),
    (lambda f: f['node_limits'].pop('build_attempts'), 'a ceiling stays'),
    (_set(['authority_ceiling', 'effects'], ['workspace.read', 'process.exec', 'network']), 'adds network'),
    (_set(['authority_ceiling', 'workspace'], 'write'), 'wider than read'),
    (lambda f: f['requirement_ids'].remove('C3'), 'requirement ids dropped'),
    (lambda f: f['evidence_obligations'].clear(), 'evidence obligations dropped'),
    (_set(['work', 'bound_ccs'], ['factory.lab_manager']), 'outside work.eligible_ccs'),
    (_set(['work', 'bound_ccs'], []), 'binds at least one capsule'),
    (lambda f: f['outputs'][0]['criteria'].pop(), 'add at least one concrete criterion'),
    (_set(['stage'], 'preliminary'), 'stage: final'),
    (_set(['slots'], [{'id': 'x', 'at': 'work.bound_ccs', 'kind': 'ccs', 'from': 'y'}]), 'no slots or bounds'),
])
def test_weaker_is_refused(change, message):
    final = good_final()
    change(final)
    found = check_final(prelim(), final, known_ccs={CC, 'factory.node_check', 'factory.lab_manager'})
    assert any(message in f for f in found), found


def test_an_advisory_review_may_only_become_blocking():
    blocking = prelim()  # review: true
    final = good_final(blocking)
    final['verifiers'][0]['review'] = 'advisory'
    assert any('stays blocking' in f for f in check_final(blocking, final, known_ccs={CC}))
    advisory = prelim()
    advisory['verifiers'][0]['review'] = 'advisory'
    assert preliminary_problems(advisory) == []
    final = good_final(advisory)
    assert check_final(advisory, final, known_ccs={CC}) == []          # stays advisory
    final['verifiers'][0]['review'] = True
    assert check_final(advisory, final, known_ccs={CC}) == []          # stricter: blocking
    final['verifiers'][0]['review'] = False
    assert any('review stays on' in f for f in check_final(advisory, final, known_ccs={CC}))
    unreviewed = prelim()
    unreviewed['verifiers'][0].pop('review')
    final = good_final(unreviewed)
    final['verifiers'][0]['review'] = 'advisory'
    assert check_final(unreviewed, final, known_ccs={CC}) == []        # adding a review is stricter


def test_unknown_capsules_are_refused():
    p = prelim()
    p['work'].pop('eligible_ccs')
    final = good_final(p)
    final['work']['bound_ccs'] = ['made.up_capsule']
    assert any('unknown capsules' in f for f in check_final(p, final, known_ccs={CC}))


def test_bad_slot_and_bound_declarations():
    p = prelim()
    p['slots'].append(dict(id='bad', at='verifiers.nothing.inputs.x', kind='number', **{'from': 'z'}))
    p['bounds']['node_limits.turns'] = 'lower'
    found = preliminary_problems(p)
    assert any('no verifier for output nothing' in f for f in found)
    assert any('bounds direct pinned verifier inputs only' in f for f in found)


def test_diff_names_what_changed():
    changes = {c['path'] for c in diff(prelim(), good_final())}
    assert {'stage', 'slots', 'bounds', 'work.bound_ccs', 'verifiers.change.inputs.tolerance',
            'outputs.change.criteria'} <= changes


# ---- the store: next_work, admission, finalize, reopen, repeat -----------------------------------
@pytest.fixture
def planned(store, tmp_path):
    store.create_task(dict(task_id='pf', objective='o', contract_id=write_contract(tmp_path, preliminary_nodes()),
                           constraints={}))
    seed_plan(store, store.get_task('pf'))
    store.advance_decision('pf', 0, {'hypothesis': 'work the planned nodes'})
    return store


def test_a_preliminary_node_waits_for_the_scheduler(planned):
    work = scheduler.next_work(planned, 'pf')
    assert [i['node_id'] for i in work['to_finalize']] == ['integrate'] and not work['runnable']
    assert 'scheduler to finalize' in work['waiting']['integrate']
    with pytest.raises(ValueError, match='preliminary node contract'):
        with scheduler.admitted(planned, 'pf', 'builder.submit', {'node_id': 'integrate'}):
            pass
    brief = scheduler.finalize_brief(planned, 'pf', 'integrate')
    assert brief['preliminary']['stage'] == 'preliminary' and brief['draft_final']['stage'] == 'final'
    assert set(brief['capsules']) <= {CC, 'factory.node_check'} and CC in brief['capsules']


def test_refused_then_admitted(planned):
    weak = good_final()
    weak['verifiers'][0]['inputs']['expect_range'] = [1, 1000]
    result = scheduler.finalize(planned, 'pf', 'integrate', weak, 'try a looser range')
    assert not result['admitted'] and any('may only narrow' in p for p in result['problems'])
    brief = scheduler.finalize_brief(planned, 'pf', 'integrate')
    assert brief['refusals'][0]['problems'] == result['problems'] and brief['refusals'][0]['by'] == 'scheduler-agent'
    assert brief['resources'] == {} and brief['constraints'] == {}
    assert scheduler.next_work(planned, 'pf')['to_finalize']  # nothing changed

    final = good_final()
    result = scheduler.finalize(planned, 'pf', 'integrate', final, 'tolerance 2 from the upstream noise')
    assert result['admitted'] and any(c['path'] == 'work.bound_ccs' for c in result['diff'])
    work = scheduler.next_work(planned, 'pf')
    item = next(i for i in work['runnable'] if i['node_id'] == 'integrate')
    assert item['bound_ccs'] == [CC] and item['final_contract'] == result['digest'] and not work['to_finalize']
    node = next(n for n in plan_get(planned, 'pf')['nodes'] if n['node_id'] == 'integrate')
    assert node['check'] == node_contract.check_spec(final)
    assert scheduler.effective_contract(planned, 'pf', node, node_contract.for_task(planned.get_task('pf')))[0] == final
    with pytest.raises(ValueError, match='already has a final'):
        scheduler.finalize(planned, 'pf', 'integrate', good_final(), 'again')


def test_agents_cannot_set_a_final_contract(planned):
    rev = plan_get(planned, 'pf')['rev']
    with pytest.raises(ValueError):
        plan_patch(planned, 'pf', {'update': [dict(node_id='integrate', final_contract='x')]}, rev, 1)
    node = next(n for n in plan_get(planned, 'pf')['nodes'] if n['node_id'] == 'integrate')
    with pytest.raises(ValueError, match='Only the scheduler'):
        plan_patch(planned, 'pf', {'add': [dict(node_id='i2', kind='integrate', title='x', node_contract='integrate',
                                                check=node['check'], final_contract='x')]}, rev, 1)
    with pytest.raises(ScopeDenied, match='reserved for the host'):
        planned.scoped('pf').append_observation('pf', dict(kind='node_contract_final', values={}))
    with pytest.raises(ScopeDenied, match='reserved for the host'):  # only the operator imports prior artifacts
        planned.scoped('pf').append_observation('pf', dict(kind='prior_artifact', values={'key': 'q2_pack'}))


def test_a_reopened_node_needs_a_new_and_different_final(planned):
    scheduler.finalize(planned, 'pf', 'integrate', good_final(), 'first')
    rev = plan_get(planned, 'pf')['rev']
    plan_patch(planned, 'pf', {'update': [dict(node_id='integrate', state='failed', reason='verifier failed')]}, rev, 1)
    operator_patch(planned, 'pf', 'reopen', 'integrate', 'try again')
    assert [i['node_id'] for i in scheduler.next_work(planned, 'pf')['to_finalize']] == ['integrate']
    again = scheduler.finalize(planned, 'pf', 'integrate', good_final(), 'same again')
    assert not again['admitted'] and 'something must change' in again['problems'][0]
    changed = good_final()
    changed['verifiers'][0]['inputs']['tolerance'] = 1
    assert scheduler.finalize(planned, 'pf', 'integrate', changed, 'tighter tolerance after the failure')['admitted']


def test_only_the_scheduler_role_proposes(planned, monkeypatch):
    packet = {'inputs': {'node_id': 'integrate', 'final': good_final(), 'rationale': 'r'}}
    monkeypatch.delenv('FACTORY_AGENT_ROLE', raising=False)
    with pytest.raises(ScopeDenied):
        dispatch(planned.scoped('pf'), 'pf', 'scheduler.propose', packet)
    monkeypatch.setenv('FACTORY_AGENT_ROLE', 'scheduler')
    assert dispatch(planned.scoped('pf'), 'pf', 'scheduler.propose', packet)['result']['admitted']


def test_the_controller_runs_the_scheduler_before_the_worker(planned, tmp_path):
    calls = []

    def runner(home, task_id, node_id, attempt=1):
        calls.append((node_id, attempt))
        if attempt == 2:
            scheduler.finalize(planned, task_id, node_id, good_final(), 'second try')

    controller = Controller(store=planned, facade=object(), scheduler=runner)
    state = {}
    assert controller._finalize_pending('pf', state) == []
    assert calls == [('integrate', 1), ('integrate', 2)]
    assert not scheduler.next_work(planned, 'pf')['to_finalize']


def test_the_controller_pauses_when_the_scheduler_cannot_finalize(planned):
    controller = Controller(store=planned, facade=object(), scheduler=lambda *a, **k: None)
    assert controller._finalize_pending('pf', {}) == ['integrate']


def test_the_muse_v3_contract_refuses_a_looser_accuracy_margin():
    """The operator test of the demo run (scripts/factory/muse_v3_controller.py) on the real contract."""
    from pathlib import Path
    path = Path(scheduler.__file__).with_name('contracts') / 'muse-q2-ttft-v3.json'
    nodes = json.loads(path.read_text(encoding='utf-8'))['extensions']['factory.node-contracts']
    assert node_contract.problems(nodes) == []
    prelim = next(n for n in nodes['nodes'] if n['node_id'] == 'measure_accuracy')
    final = draft_final(prelim)
    final['work']['bound_ccs'] = ['eval.paired_accuracy']
    final['outputs'][0]['criteria'].append('Checkpoints at 50, 100, 160, 250 and 430 questions.')
    assert check_final(prelim, final) == []
    final['verifiers'][0]['inputs']['margin_pts'] = 8
    found = check_final(prelim, final)
    assert found and all('margin_pts' in f for f in found), found


def test_the_brief_carries_what_accepted_upstream_checks_measured(planned):
    def check(output, passed, detail):
        planned.append_observation('pf', dict(kind='node_check', host_run=dict(by='test'), values=dict(
            node_id='integrate', output=output, state='finished', passed=passed,
            verifier=dict(cc='weights.x', capability='verify_pack', stage_reached='native CC execution',
                          checks=[dict(name='total_bytes', status='pass' if passed else 'fail', detail=detail)]))))
    check('pack', False, 'too small')
    check('pack', True, '528942162176 bytes' + ' x' * 400)
    found = scheduler.accepted_checks(planned, 'pf', 'integrate')
    assert list(found) == ['pack'] and found['pack']['verifier'] == 'weights.x.verify_pack'
    assert found['pack']['checks'][0]['detail'].startswith('528942162176 bytes') and len(found['pack']['checks'][0]['detail']) == 300
    assert scheduler.accepted_checks(planned, 'pf', 'other') == {}


def test_the_brief_lists_operator_inputs_recorded_on_the_run(planned):
    planned.append_observation('pf', dict(kind='operator_input', host_run=dict(by='operator import'), values=dict(
        key='earlier_accuracy_timing', path='/x/run.log', sha256='ab' * 32, bytes=10, how='an earlier run',
        results='about 6.3 s per question' + ' x' * 500)))
    brief = scheduler.finalize_brief(planned, 'pf', 'integrate')
    item = brief['operator_inputs']['earlier_accuracy_timing']
    # The scheduler sees the whole result (up to the brief's record bound), not a 600-character summary.
    assert item['how'] == 'an earlier run' and item['results'] == 'about 6.3 s per question' + ' x' * 500


def test_retire_needs_a_contract_revision_and_unlinks_the_node(planned):
    from jiuwenswarm.factory.taskgraph import operator_patch, _apply_operator
    with pytest.raises(ValueError, match='still in the task contract'):
        operator_patch(planned, 'pf', 'retire', 'integrate', 'moved to the lab')
    nodes = {'a': dict(node_id='a', state='proposed', depends_on=[]), 'b': dict(node_id='b', state='proposed', depends_on=['a'], hold='step')}
    from jiuwenswarm.factory import taskgraph
    original = taskgraph._validate
    taskgraph._validate = lambda *a, **k: None
    try:
        _apply_operator(nodes, {'retire': [dict(node_id='b', reason='moved to the lab')]})
        _apply_operator(nodes, {'retire': [dict(node_id='a', reason='moved to the lab')]})
    finally:
        taskgraph._validate = original
    assert nodes['b']['state'] == 'cancelled' and 'hold' not in nodes['b'] and nodes['b']['reason'].startswith('retired by operator')
    assert nodes['b']['depends_on'] == [] and nodes['a']['state'] == 'cancelled'
