"""Contract -> planner -> scheduler + node checks -> lab manager, offline.

Node contracts come from the contract, the plan from a planner (the stand-in, a task
file or FACTORY_PLANNER), the scheduler says what can run, every output is checked,
and only the deliver node hands the engine to the lab manager.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from jiuwenswarm.factory import lab_build, node_contract, scheduler
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.contract_v2 import problems as contract_problems
from jiuwenswarm.factory.lab_agent import CommandAdapter, LabAgent, serve
from jiuwenswarm.factory.lab_manager import LabManager
from jiuwenswarm.factory.node_check import NodeChecks
from jiuwenswarm.factory.planner import PlanError, contract_plan
from jiuwenswarm.factory.taskgraph import plan_get, plan_patch, seed_plan

from test_lab_build import RECIPES, git
from test_lab_manager import good_report, lab_task
from test_node_check import CC_YAML, PASS, Reviewer

REPO = Path(__file__).resolve().parents[2]
STAR = REPO / 'jiuwenswarm/factory/contracts/star-deepseek-v2.json'
# The fake capsule verifier reads the working change when no patch file is given.
VERIFY = '''import json, subprocess, sys
packet = json.load(sys.stdin)
inputs = packet["inputs"]
diff = open(inputs["diff_path"]).read() if inputs.get("diff_path") else subprocess.run(
    ["git", "-C", inputs["checkout"], "diff", "HEAD"], capture_output=True, text=True).stdout
ok = "BAD" not in diff
checks = [dict(name="no_bad_marker", status="pass" if ok else "fail", stage="native CC execution", detail="")]
print(json.dumps(dict(outcome="ok", outputs=dict(done=ok, checks=checks))))
'''


def tiny_nodes():
    return dict(format='factory.node-contracts/1', nodes=[
        dict(node_id='integrate', kind='integrate', objective='Add the thing to the checkout, off by default.',
             requirement_ids=['C3', 'gate_unset_parity'], inputs=[{'name': 'source', 'from': 'task:source'}],
             outputs=[dict(name='change', kind='diff', criteria=['Off by default.'])],
             work=dict(helpful_ccs=['test.build_thing']),
             verifiers=[dict(output='change', verifier='test.build_thing.verify', stage='native CC execution', review=True)],
             hands_to='build'),
        dict(node_id='build', kind='build', objective='Bundle the change for the lab.', predecessors=['integrate'],
             inputs=[{'name': 'change', 'from': 'integrate.change'}],
             outputs=[dict(name='sources', kind='source_bundle')], node_limits=dict(build_attempts=1),
             verifiers=[dict(output='sources')], hands_to='deliver'),
        dict(node_id='deliver', kind='deliver', objective='Send the build and the lab task to the lab manager.',
             requirement_ids=['A', 'C3', 'gate_unset_parity', 'client_ttft_ms'], predecessors=['build'],
             inputs=[{'name': 'sources', 'from': 'build.sources'}],
             outputs=[dict(name='lab_request', kind='lab_request')], verifiers=[dict(output='lab_request')],
             hands_to='lab_manager')])


def write_contract(tmp_path, nodes):
    document = json.loads(STAR.read_text())
    document['extensions']['factory.node-contracts'] = nodes
    path = tmp_path / 'contract.json'
    path.write_text(json.dumps(document))
    return str(path)


def test_the_spark_contract_carries_valid_node_contracts():
    document = json.loads(STAR.read_text())
    assert contract_problems(document) == []
    nodes = node_contract.from_contract(document)['nodes']
    assert [n['node_id'] for n in nodes][0] == 'inspect_engine' and nodes[-1]['kind'] == 'deliver'
    assert node_contract.order(nodes)[-1] == 'deliver_to_lab' and len(nodes) == 9


@pytest.mark.parametrize('change,message', [
    (lambda d: d['nodes'][0]['verifiers'].clear() or d['nodes'][0]['verifiers'].append({'output': 'other'}), 'no output other'),
    (lambda d: d['nodes'][1].update(predecessors=[]), 'must be a predecessor'),
    (lambda d: d['nodes'][0].update(predecessors=['deliver']), 'cycle'),
    (lambda d: d['nodes'][2].update(kind='build'), 'exactly one leaf, the deliver node'),
    (lambda d: d['nodes'][2]['requirement_ids'].append('Z9'), 'no arm, check or metric Z9'),
    (lambda d: d['nodes'][1]['verifiers'][0].update(review=True), 'checked by the host'),
    (lambda d: d['nodes'][1]['verifiers'][0].update(verifier='a.b.verify'), 'capsule verifiers check diff and evidence outputs'),
    (lambda d: d['nodes'][1].update(hands_to='integrate'), 'must be a node that lists build'),
])
def test_node_contract_problems(change, message):
    document = tiny_nodes()
    change(document)
    contract = json.loads(STAR.read_text())
    found = node_contract.problems(document, contract)
    assert any(message in problem for problem in found), found


def test_stand_in_planner_seeds_the_graph_and_the_scheduler_orders_it(store):
    store.create_task(dict(task_id='s', objective='Speed up DeepSeek on the Spark', contract_id='star-deepseek-v2'))
    graph = seed_plan(store, store.get_task('s'))
    assert graph['history'][0]['planner'] == 'factory.planner.contract_plan'
    nodes = {n['node_id']: n for n in graph['nodes']}
    assert nodes['integrate_cache']['check']['outputs'][0]['verifier'] == 'engine.build_expert_weight_cache.verify'
    assert nodes['deliver_to_lab']['kind'] == 'deliver' and nodes['build_candidate']['resources'] == {'class': 'build'}
    work = scheduler.next_work(store, 's')
    assert [n['node_id'] for n in work['runnable']] == ['inspect_engine']
    assert work['waiting']['combine'].startswith('waiting for integrate_')
    first = work['runnable'][0]
    assert first['helpful_ccs'] == ['factory.engine_inspector', 'factory.source_workbench'] and first['hands_to'] == 'integrate_recorder'
    assert 'needs a passing node check' in first['done_blocked_by']


def reverse_planner(task, contract, node_contracts):
    """A stand-in for another team's planner (FACTORY_PLANNER points here)."""
    plan = contract_plan(task, contract, node_contracts)
    plan['planner'] = 'test.reverse_planner'
    plan['nodes'][-1]['title'] = 'Hand over to the lab'
    return plan


def test_external_plans_are_checked_against_the_node_contracts(store, tmp_path, monkeypatch):
    path = write_contract(tmp_path, tiny_nodes())
    task = store.create_task(dict(task_id='p', objective='o', contract_id=path))
    good = dict(format='factory.plan/1', planner='someone', nodes=[
        dict(node_id='integrate'), dict(node_id='build', depends_on=['integrate']),
        dict(node_id='deliver', depends_on=['build', 'integrate'])])  # an extra ordering edge is fine
    missing = copy.deepcopy(good)
    missing['nodes'].pop(1)
    invented = copy.deepcopy(good)
    invented['nodes'].append(dict(node_id='tune_more', depends_on=['build']))
    unordered = copy.deepcopy(good)
    unordered['nodes'][1]['depends_on'] = []
    for plan, message in ((missing, 'build is not in the plan'), (invented, 'no node contract tune_more'),
                          (unordered, 'missing contract predecessors')):
        with pytest.raises(PlanError, match=message):
            seed_plan(store, task, plan)
    graph = seed_plan(store, task, good)
    assert graph['history'][0]['planner'] == 'someone'

    store.create_task(dict(task_id='q', objective='o', contract_id=path))
    monkeypatch.setenv('FACTORY_PLANNER', 'test_node_contracts:reverse_planner')
    graph = seed_plan(store, store.get_task('q'))
    assert graph['history'][0]['planner'] == 'test.reverse_planner'
    assert next(n for n in graph['nodes'] if n['node_id'] == 'deliver')['title'] == 'Hand over to the lab'


def test_a_task_file_can_carry_the_planners_plan(tmp_path):
    from jiuwenswarm.factory.controller import Controller
    path = write_contract(tmp_path, tiny_nodes())
    plan = dict(format='factory.plan/1', planner='planner-team', nodes=[
        dict(node_id='integrate'), dict(node_id='build', depends_on=['integrate']), dict(node_id='deliver', depends_on=['build'])])
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    task = dict(task_id='tf', objective='o', constraints={}, allowed_effects=['process.exec'], target='spark-gb10',
                budget={'max_turns': 3, 'wall_clock_s': 100}, contract_id=path, initial_run_config={},
                component_cc='engine.build_expert_weight_cache', source={'subpath': 'llama.cpp', 'pre_integration_commit': 'abc'},
                plan='plan.json')
    (tmp_path / 'task.json').write_text(json.dumps(task))
    controller = Controller(tmp_path / 'home')
    try:
        assert controller.init_task(tmp_path / 'task.json') == 'tf'
        graph = plan_get(controller.store, 'tf')
        assert graph['history'][0]['planner'] == 'planner-team' and len(graph['nodes']) == 3
        bad = dict(task, task_id='tf2', plan=dict(plan, nodes=plan['nodes'][:2]))
        (tmp_path / 'bad.json').write_text(json.dumps(bad))
        with pytest.raises(PlanError):
            controller.init_task(tmp_path / 'bad.json')
        with pytest.raises(Exception):
            controller.store.get_task('tf2')  # a refused plan creates no task
    finally:
        controller.store.close()


@pytest.fixture
def pipeline(store, tmp_path, monkeypatch):
    """A tiny contract planned by the stand-in, a fake capsule, a checkout and a lab mailbox."""
    ccs = tmp_path / 'ccs'
    (ccs / 'thing').mkdir(parents=True)
    (ccs / 'thing/cc.yaml').write_text(CC_YAML)
    (ccs / 'thing/run.py').write_text(VERIFY)
    (ccs / 'thing/METHOD.md').write_text('# Method\nKeep the feature off by default.\n')
    root = tmp_path / 'engine'
    root.mkdir()
    git(tmp_path, 'init', '-q', str(root))
    (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.10)\nproject(hello C)\nadd_executable(hello main.c)\n')
    (root / 'main.c').write_text('#include <stdio.h>\nint main(void){printf("stock\\n");return 0;}\n')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'base')
    base = git(root, 'rev-parse', 'HEAD')
    monkeypatch.setattr(lab_build, 'RECIPES', RECIPES)
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    monkeypatch.setenv('FACTORY_LAB_ROUTE', 'mailbox')
    store.create_task(dict(task_id='lt', objective='Make the thing faster', contract_id=write_contract(tmp_path, tiny_nodes()),
                           constraints={}))
    seed_plan(store, store.get_task('lt'))
    store.advance_decision('lt', 0, {'hypothesis': 'work the planned nodes'})
    return store, ccs, root, base


def mark_done(store, node_id, evidence):
    rev = plan_get(store, 'lt')['rev']
    return plan_patch(store, 'lt', {'update': [dict(node_id=node_id, state='done', evidence_ids=evidence)]}, rev, 1)


def test_contract_to_lab_manager_end_to_end(pipeline, tmp_path):
    store, ccs, root, base = pipeline
    checks = NodeChecks(store, reviewer=Reviewer(PASS), ccs_roots=[ccs])

    # integrate: the capsule verifier and the independent reviewer check the diff.
    (root / 'main.c').write_text('#include <stdio.h>\nint main(void){printf("cache\\n");return 0;}\n')
    with pytest.raises(ValueError, match='output change needs a passing node check'):
        mark_done(store, 'integrate', ['lt'])
    change = checks.start('lt', 'integrate', checkout=root, background=False)
    assert change['passed'] and change['review']['passed'], change
    assert 'Off by default.' in checks.reviewer.prompts[0]
    mark_done(store, 'integrate', [change['obs_id']])

    # build: the scheduler resolves its input to the passing check; the source bundle is checked by the host.
    work = scheduler.next_work(store, 'lt')
    build = work['runnable'][0]
    assert build['node_id'] == 'build' and build['inputs']['change']['value']['check'] == change['obs_id']
    assert build['limits_left'] == {'build_attempts': 1}
    shipped = LabManager(store, route='mailbox').source_bundle('lt', root, base, 'hello', include_base=True)
    bad = checks.start('lt', 'build', refs={'artifact_ids': ['nope']})
    assert not bad['passed'] and 'no artifact nope' in bad['reason']
    sources = checks.start('lt', 'build', refs={'artifact_ids': [shipped['artifact_id']]})
    assert sources['passed'] and sources['found']['bundles'][0]['head_tree'] == shipped['subject']['identity']['head_tree']
    mark_done(store, 'build', [sources['obs_id']])

    # deliver: only the deliver node may compose; the lab request must cover the node's requirements.
    subjects = dict(stock=dict(kind='stock', identity=dict(name='stock llama.cpp')), cache=shipped['subject'])
    packet = {'inputs': {'lab_task': lab_task(subjects)}}
    with pytest.raises(ValueError, match='deliver node'):
        dispatch(store, 'lt', 'lab_manager.compose', packet)
    with pytest.raises(ValueError, match='not the contracted deliver node'):
        dispatch(store, 'lt', 'lab_manager.compose', {'inputs': dict(packet['inputs'], node_id='build')})
    # Subject names never stand in for checks or metrics: a lab task without the parity test fails the deliver check.
    thin = lab_task(subjects)
    thin['tests'] = [test for test in thin['tests'] if test['id'] != 'parity']
    thin['subjects']['gate_unset_parity'] = thin['subjects']['stock']
    thin_pkg = dispatch(store, 'lt', 'lab_manager.compose', {'inputs': dict(lab_task=thin, node_id='deliver')})
    thin_req = dispatch(store, 'lt', 'lab_manager.send', {'inputs': dict(package_id=thin_pkg['package_id'], idem_key='thin')})['request_id']
    thin_check = checks.start('lt', 'deliver', refs={'request_id': thin_req})
    assert not thin_check['passed'] and 'does not test gate_unset_parity' in thin_check['reason']
    composed = dispatch(store, 'lt', 'lab_manager.compose', {'inputs': dict(packet['inputs'], node_id='deliver')})
    request = dispatch(store, 'lt', 'lab_manager.send', {'inputs': dict(package_id=composed['package_id'], idem_key='go')})['request_id']
    request_check = checks.start('lt', 'deliver', refs={'request_id': request})
    assert request_check['passed'] and request_check['found']['tests'] == ['parity', 'ttft'], request_check

    # The lab side: a command lab agent answers; the factory records the checked report.
    (tmp_path / 'report.json').write_text(json.dumps(good_report()))
    script = tmp_path / 'lab.py'
    script.write_text('import shutil, sys\nfrom pathlib import Path\nout = Path(sys.argv[2])\n'
                      '(out / "files" / "samples").write_text("[]")\n'
                      f'shutil.copy({str(tmp_path / "report.json")!r}, out / "report.json")\n')
    agent = LabAgent(LabManager(store, route='mailbox').mailbox, 'test-lab', 'command')
    adapter = CommandAdapter(f'{sys.executable} {script} {{package}} {{output}}', tmp_path / 'work')
    serve(agent, adapter, once=True, log=lambda line: None)
    serve(agent, adapter, once=True, log=lambda line: None)
    recorded = LabManager(store, route='mailbox').report('lt', request)
    assert recorded['valid'], recorded['problems']
    graph = mark_done(store, 'deliver', [request_check['obs_id'], recorded['evidence_id']])
    assert all(n['state'] == 'done' for n in graph['nodes']) and scheduler.next_work(store, 'lt')['delivered']


def test_node_limits_are_charged(pipeline):
    store, ccs, root, base = pipeline
    checks = NodeChecks(store, reviewer=Reviewer(PASS), ccs_roots=[ccs])
    (root / 'main.c').write_text('int main(void){return 0;}\n')
    mark_done(store, 'integrate', [checks.start('lt', 'integrate', checkout=root, background=False)['obs_id']])
    store.create_attempt('lt', dict(kind='build', idem_key='b1', fingerprint='f', request={'node_id': 'build'}))
    with pytest.raises(ValueError, match='used its build_attempts'):
        scheduler.charge(store, 'lt', 'build', 'build')
    scheduler.charge(store, 'lt', 'build', 'lab')  # other kinds have no limit here


# ---- review findings: the done rule and the hand-off cannot be bypassed --------------------------
def test_agents_cannot_drop_or_fake_contracted_work(pipeline):
    store, ccs, root, base = pipeline
    rev = plan_get(store, 'lt')['rev']
    attempts = [
        ({'cancel': [dict(node_id='build', reason='skip it')]}, 'stays covered'),
        ({'add': [dict(node_id='fake', kind='deliver', title='Fake delivery')]}, 'only the contracted deliver node'),
        ({'add': [dict(node_id='fake', kind='inspect', title='x', node_contract='does_not_exist')]}, 'no node contract'),
        ({'add': [dict(node_id='b2', kind='build', title='x', node_contract='build', depends_on=['integrate'])]},
         'keep the kind and checks'),
    ]
    for patch, message in attempts:
        with pytest.raises(ValueError, match=message):
            plan_patch(store, 'lt', patch, rev, 1)
    # A replacement that keeps the contract, its checks and its predecessors is fine.
    build = next(n for n in plan_get(store, 'lt')['nodes'] if n['node_id'] == 'build')
    replacement = dict(node_id='build_again', kind='build', title='Retry the bundle', node_contract='build',
                       check=build['check'], depends_on=['integrate'])
    graph = plan_patch(store, 'lt', {'add': [replacement],
                                     'supersede': [dict(node_id='build', by='build_again', reason='retry')]}, rev, 1)
    assert {n['node_id']: n['state'] for n in graph['nodes']}['build'] == 'superseded'


def test_check_inputs_scope_and_timing(pipeline, monkeypatch):
    store, ccs, root, base = pipeline
    (root / 'main.c').write_text('int main(void){return 0;} /* BAD */\n')
    (root.parent / 'innocent.diff').write_text('')
    checks = NodeChecks(store, reviewer=Reviewer(PASS), ccs_roots=[ccs])
    with pytest.raises(ValueError, match='set by the host'):
        checks.start('lt', 'integrate', checkout=root, verifier_inputs={'diff_path': str(root.parent / 'innocent.diff')},
                     background=False)

    # A pass does not count while a newer check of other work is still running.
    (root / 'main.c').write_text('int main(void){return 1;}\n')
    first = checks.start('lt', 'integrate', checkout=root, background=False)
    assert first['passed']
    (root / 'main.c').write_text('int main(void){return 2;} /* BAD */\n')
    import jiuwenswarm.factory.node_check as node_check_module
    monkeypatch.setattr(node_check_module, '_spawn', lambda *a, **k: None)  # the worker never finishes
    assert checks.start('lt', 'integrate', checkout=root)['state'] == 'running'
    with pytest.raises(ValueError, match='has not finished'):
        mark_done(store, 'integrate', [first['obs_id']])


def test_the_checkout_must_still_hold_the_reviewed_work(pipeline):
    store, ccs, root, base = pipeline
    (root / 'main.c').write_text('int main(void){return 3;}\n')

    class Changing(Reviewer):
        def __call__(self, prompt):
            (root / 'main.c').write_text('int main(void){return 4;} /* BAD */\n')
            return super().__call__(prompt)
    result = NodeChecks(store, reviewer=Changing(PASS), ccs_roots=[ccs]).start('lt', 'integrate', checkout=root,
                                                                                background=False)
    assert not result['passed'] and 'changed after the check was requested' in result['reason']


def test_a_diff_needs_a_real_check():
    from jiuwenswarm.factory.node_check import validate_spec
    document = tiny_nodes()
    document['nodes'][0]['verifiers'] = [{'output': 'change'}]
    assert any('needs a capsule verifier, a review or both' in p for p in node_contract.problems(document))
    with pytest.raises(ValueError, match='needs a capsule verifier'):
        validate_spec({'outputs': [{'name': 'change', 'kind': 'diff'}]})


def test_authority_ceiling_and_idempotent_limits(pipeline):
    store, ccs, root, base = pipeline
    with pytest.raises(ValueError, match='beyond node n'):
        scheduler.check_ceiling(dict(node_id='n', authority_ceiling=dict(effects=[])), 'builder', 'submit')
    with pytest.raises(ValueError, match='allows workspace none'):
        scheduler.check_ceiling(dict(node_id='n', authority_ceiling=dict(workspace='none')), 'source_workbench', 'write')
    scheduler.check_ceiling(dict(node_id='n', authority_ceiling=dict(effects=['process.exec'])), 'builder', 'submit')
    checks = NodeChecks(store, reviewer=Reviewer(PASS), ccs_roots=[ccs])
    (root / 'main.c').write_text('int main(void){return 5;}\n')
    mark_done(store, 'integrate', [checks.start('lt', 'integrate', checkout=root, background=False)['obs_id']])
    store.create_attempt('lt', dict(kind='build', idem_key='b1', fingerprint='f', request={'node_id': 'build'}))
    scheduler.charge(store, 'lt', 'build', 'build', 'b1')  # a retry of the admitted job is not charged again
    with pytest.raises(ValueError, match='used its build_attempts'):
        scheduler.charge(store, 'lt', 'build', 'build', 'b2')


def test_renamed_plan_nodes_still_receive_their_inputs(pipeline):
    store, ccs, root, base = pipeline
    path = store.get_task('lt')['contract_id']
    store.create_task(dict(task_id='rn', objective='o', contract_id=path))
    seed_plan(store, store.get_task('rn'), dict(format='factory.plan/1', planner='renamer', nodes=[
        dict(node_id='p_integrate', node_contract='integrate'),
        dict(node_id='p_build', node_contract='build', depends_on=['p_integrate']),
        dict(node_id='p_deliver', node_contract='deliver', depends_on=['p_build'])]))
    store.advance_decision('rn', 0, {'hypothesis': 'renamed plan'})
    (root / 'main.c').write_text('int main(void){return 6;}\n')
    passed = NodeChecks(store, reviewer=Reviewer(PASS), ccs_roots=[ccs]).start('rn', 'p_integrate', checkout=root,
                                                                                background=False)
    plan_patch(store, 'rn', {'update': [dict(node_id='p_integrate', state='done', evidence_ids=[passed['obs_id']])]}, 1, 1)
    build = scheduler.next_work(store, 'rn')['runnable'][0]
    assert build['node_id'] == 'p_build' and build['inputs']['change']['value']['check'] == passed['obs_id']
