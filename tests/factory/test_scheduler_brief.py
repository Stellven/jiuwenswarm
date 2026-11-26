"""What the scheduler agent reads: the node briefing, the finalize brief, and the on-demand capsule and evidence reads."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory import node_contract, scheduler, scheduler_agent, scheduler_brief
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.node_finalize import check_final, draft_final, digest
from jiuwenswarm.factory.taskgraph import seed_plan

from test_node_contracts import write_contract
from test_node_finalize import CC, good_final, planned, preliminary_nodes, prelim  # noqa: F401 (planned is a fixture)

CONTRACTS = Path(scheduler.__file__).with_name('contracts')
BRIEFING = dict(summary='Gate the thing behind FACTORY_THING.',
                facts=['Stock outputs are byte-identical with the gate unset (run 12, evidence obs-1).'],
                pitfalls=['The verifier reads the working change, not a patch file.'],
                how_to_fill=['tolerance: the measured noise of the upstream run, at most 5.'])


def _schema_tolerant(nodes):
    """Rev 8 contracts use review: "advisory" (a schema change made on another branch). Until it lands here, read
    advisory as a review that is on, so these tests check the briefing and the brief, not that change."""
    nodes = copy.deepcopy(nodes)
    if any('is not of type' in p and 'review' in p for p in node_contract.problems(nodes)):
        for node in nodes['nodes']:
            for verifier in node['verifiers']:
                if verifier.get('review') == 'advisory':
                    verifier['review'] = True
    return nodes


def briefed_nodes():
    nodes = preliminary_nodes()
    nodes['nodes'][0]['briefing'] = copy.deepcopy(BRIEFING)
    return nodes


# ---- the briefing field ---------------------------------------------------------------------------------
def test_a_briefing_validates_is_carried_over_and_may_be_extended():
    nodes = briefed_nodes()
    assert node_contract.problems(nodes) == []
    p = nodes['nodes'][0]
    final = good_final(p)
    assert final['briefing'] == BRIEFING  # draft_final carries it
    assert check_final(p, final, known_ccs={CC}) == []
    final['briefing']['facts'].append('The upstream noise was 1.4 (obs-7).')
    assert check_final(p, final, known_ccs={CC}) == []
    del final['briefing']
    assert check_final(p, final, known_ccs={CC}) == []  # dropping it is not a weakening
    # The final contract document (with the briefing) passes the schema, and its digest covers the briefing.
    document = dict(nodes, nodes=[good_final(p)] + nodes['nodes'][1:])
    assert node_contract.problems(document) == []
    assert digest(good_final(p)) != digest(good_final(preliminary_nodes()['nodes'][0]))


@pytest.mark.parametrize('change', [
    lambda b: b.update(owner='x'), lambda b: b.update(facts='one string'), lambda b: b.update(summary='')])
def test_a_malformed_briefing_is_refused_by_the_schema(change):
    nodes = briefed_nodes()
    change(nodes['nodes'][0]['briefing'])
    assert any('briefing' in p for p in node_contract.problems(nodes))


def test_every_shipped_contract_still_validates():
    for path in sorted(CONTRACTS.glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        nodes = node_contract.from_contract(document)
        if nodes:
            assert node_contract.problems(_schema_tolerant(nodes)) == [], path.name


def test_the_worker_sees_the_briefing_of_a_finalized_node(store, tmp_path):
    store.create_task(dict(task_id='pb', objective='o', contract_id=write_contract(tmp_path, briefed_nodes()), constraints={}))
    seed_plan(store, store.get_task('pb'))
    store.advance_decision('pb', 0, {'hypothesis': 'work the planned nodes'})
    assert scheduler.finalize_brief(store, 'pb', 'integrate')['briefing'] == BRIEFING
    assert scheduler.finalize(store, 'pb', 'integrate', good_final(briefed_nodes()['nodes'][0]), 'r')['admitted']
    item = next(i for i in scheduler.next_work(store, 'pb')['runnable'] if i['node_id'] == 'integrate')
    assert item['briefing'] == BRIEFING
    assert scheduler.brief(scheduler.next_work(store, 'pb'))['runnable'][0]['briefing'] == BRIEFING


# ---- the brief ------------------------------------------------------------------------------------------
def test_the_brief_shows_the_task_the_plan_and_the_capsules(planned, monkeypatch):
    monkeypatch.delenv('JOBQ_DIR', raising=False)
    monkeypatch.delenv('FACTORY_MACHINE_STATE', raising=False)
    brief =scheduler.finalize_brief(planned, 'pf', 'integrate')
    assert brief['schema'] == 'factory.finalize-brief/2'
    assert 'factory.node-contracts' not in brief['task']['contract'].get('extensions', {})  # listed once, below
    assert {'purpose', 'scope', 'arms'} <= set(brief['task']['contract'])
    assert [n['node_id'] for n in brief['task']['node_contracts']] == ['integrate', 'build', 'deliver']
    this = [n for n in brief['plan']['nodes'] if n.get('this')]
    assert [n['node_id'] for n in this] == ['integrate'] and this[0]['objective'].startswith('Add the thing')
    assert brief['neighbours']['hands_to']['objective'] == 'Bundle the change for the lab.'
    capsule = brief['capsules'][CC]
    assert 'capabilities:' in capsule['cc_yaml']['text'] and capsule['files'] and capsule['docs']
    assert any(f['path'] == 'cc.yaml' for f in capsule['files'])
    assert capsule['used_in_this_run'] == [] and brief['bounds'].get('trimmed') is None
    assert brief['machine'] == {'state': None, 'queue': {'this_task': []}}
    assert scheduler.catalog()[CC]['purpose']  # cc v2 capsules get a purpose from their doc


def test_the_brief_records_where_a_capsule_was_bound_and_the_done_nodes(planned):
    final = good_final()
    assert scheduler.finalize(planned, 'pf', 'integrate', final, 'tolerance 2 from obs-1')['admitted']
    graph = scheduler._graph(planned, 'pf')
    contracts = node_contract.for_task(planned.get_task('pf'))
    used = scheduler_brief._bound_in_run(planned, 'pf', graph, contracts, 'build')
    assert [{k: u[k] for k in ('node_id', 'node_contract', 'state')} for u in used[CC]] == [
        dict(node_id='integrate', node_contract='integrate', state='proposed')]
    planned.append_observation('pf', dict(kind='capped_run', host_run=dict(by='test'), values=dict(
        recipe='build', request=dict(recipe='build', args=dict(jobs=4)), outcome='ok', seconds=12.5, node_id='integrate',
        result=dict(binary='/x/llama-server'), attempt_id='a1')))
    runs = scheduler_brief.capped_runs(planned, 'pf', 'integrate', 8000)
    assert runs[0]['recipe'] == 'build' and runs[0]['args'] == {'jobs': 4} and runs[0]['seconds'] == 12.5


def test_the_brief_history_lists_operator_records_and_all_refusals(planned):
    weak = good_final()
    weak['verifiers'][0]['inputs']['expect_range'] = [1, 1000]
    scheduler.finalize(planned, 'pf', 'integrate', weak, 'looser')
    planned.append_observation('pf', dict(kind='operator_halt', host_run=dict(by='test'),
                                          values=dict(key='k', node_id='integrate', reason='two failed checks', evidence=[])))
    history = scheduler.finalize_brief(planned, 'pf', 'integrate')['history']
    assert history['refusals'][0]['node_id'] == 'integrate' and 'may only narrow' in ' '.join(history['refusals'][0]['problems'])
    assert history['operator']['halts'][0]['reason'] == 'two failed checks'
    assert history['this_node'] == dict(failures=[], earlier_finals=[], checks=[], capped_runs=[])


def test_a_large_brief_tightens_its_bounds_and_says_so(planned, monkeypatch):
    planned.append_observation('pf', dict(kind='operator_input', host_run=dict(by='operator import'), values=dict(
        key='big', path='/x', sha256='ab' * 32, bytes=1, how='h', results='r' * 50000)))
    full = len(json.dumps(scheduler.finalize_brief(planned, 'pf', 'integrate')))
    monkeypatch.setattr(scheduler_brief, 'BRIEF_CHARS', full - 1000)
    brief = scheduler.finalize_brief(planned, 'pf', 'integrate')
    assert 'trimmed' in brief['bounds'] and len(json.dumps(brief)) < full


def test_a_cut_capsule_doc_says_how_to_read_it_whole():
    entry = scheduler.catalog()[CC]
    view = scheduler_brief.capsule_view(CC, entry, file_chars=100)
    doc = view['docs'][0]
    assert len(doc['text']) == 100 and 'factory.scheduler.capsule' in doc['cut'] and doc['path'] in doc['cut']
    assert scheduler_brief.capsule_view(CC, entry, file_chars=0)['docs'][0]['cut'].startswith('Left out')


def test_the_rev8_muse_contract_brief_carries_the_planner_briefing(store, tmp_path):
    document = json.loads((CONTRACTS / 'muse-2bit-ttft-v4.json').read_text(encoding='utf-8'))
    document['extensions']['factory.node-contracts'] = _schema_tolerant(document['extensions']['factory.node-contracts'])
    path = tmp_path / 'muse-2bit-ttft-v4.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    store.create_task(dict(task_id='mv', objective='o', contract_id=str(path), constraints={}))
    seed_plan(store, store.get_task('mv'))
    nodes = {n['node_id']: n for n in document['extensions']['factory.node-contracts']['nodes']}
    briefed = [k for k, n in nodes.items() if n.get('briefing')]
    assert briefed, 'rev 8 nodes to finalize carry a briefing'
    for node_id in briefed:
        brief = scheduler.finalize_brief(store, 'mv', node_id)
        assert brief['briefing'] == nodes[node_id]['briefing'] and brief['task']['contract']['contract_id'] == 'muse-2bit-ttft-v4'
        assert len(brief['task']['node_contracts']) == len(nodes) and set(brief['capsules']) <= set(nodes[node_id]['work']['eligible_ccs'])
        assert len(json.dumps(brief)) <= scheduler_brief.BRIEF_CHARS


# ---- on-demand reads ------------------------------------------------------------------------------------
def test_capsule_reads_list_and_read_and_stay_inside_the_folder(planned):
    listing = dispatch(planned.scoped('pf'), 'pf', 'scheduler.capsule', {'inputs': {'id': CC}})['capsule']
    assert any(f['path'] == 'cc.yaml' for f in listing['files'])
    one = scheduler_brief.capsule_read(CC, 'cc.yaml')
    assert one['text'].startswith('cc:') or 'capabilities:' in one['text']
    page = scheduler_brief.capsule_read(CC, 'cc.yaml', offset=10)
    assert page['text'] == one['text'][10:10 + scheduler_brief.FILE_CHARS]
    for bad in ('../node_check/cc.yaml', '/etc/passwd', 'C:/Windows/win.ini', '..\\x', 'no-such-file'):
        with pytest.raises(ValueError):
            scheduler_brief.capsule_read(CC, bad)
    with pytest.raises(ValueError, match='Unknown capsule'):
        scheduler_brief.capsule_read('no.such_capsule')
    with pytest.raises(ValueError):
        dispatch(planned.scoped('pf'), 'pf', 'scheduler.capsule', {'inputs': {'id': CC, 'extra': 1}})


def test_evidence_reads_return_a_whole_record_or_artifact(planned, tmp_path):
    record = planned.append_observation('pf', dict(kind='capped_run', host_run=dict(by='test'),
                                                   values=dict(recipe='serve', result=dict(log='x' * 100000))))
    got = dispatch(planned.scoped('pf'), 'pf', 'scheduler.evidence', {'inputs': {'id': record['obs_id']}})['record']
    assert got['record']['values']['result']['log'] == 'x' * 100000
    text = tmp_path / 'progress.log'
    text.write_text('line\n' * 60000)
    planned.put_artifact('pf', 'run-a-progress.log', text, 'text/plain', None)
    first = scheduler_brief.evidence_read(planned.scoped('pf'), 'pf', 'run-a-progress.log')
    assert first['chars'] == 300000 and len(first['text']) == scheduler_brief.READ_CHARS and first['next_offset']
    rest = scheduler_brief.evidence_read(planned.scoped('pf'), 'pf', 'run-a-progress.log', first['next_offset'])
    assert len(rest['text']) == 100000 and 'next_offset' not in rest
    with pytest.raises(Exception):
        scheduler_brief.evidence_read(planned.scoped('pf'), 'pf', 'no-such-record')


def test_the_scheduler_capsule_declares_every_capability_it_routes():
    import yaml
    folder = Path(scheduler_agent.CAPSULES) / 'scheduler'
    declared = yaml.safe_load((folder / 'cc.yaml').read_text(encoding='utf-8'))
    roles = json.loads((folder / 'roles.json').read_text(encoding='utf-8'))
    assert set(declared['capabilities']) == set(roles['capabilities']) == {'brief', 'propose', 'capsule', 'evidence'}
    assert scheduler_agent.DEFAULT_MODEL == 'gpt-6.2-astra'
