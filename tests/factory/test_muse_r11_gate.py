"""Native Run 4 authority gates, without a graph session, engine build or model."""
from pathlib import Path
import json
import subprocess

import pytest

from jiuwenswarm.factory import api, muse_r11_gate as gate, scheduler, taskgraph
from jiuwenswarm.factory.contract import load, load_for_task
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.lab_manager import LabManager, task_problems
from jiuwenswarm.factory.node_check import NodeChecks
from jiuwenswarm.factory.node_contract import from_contract
from jiuwenswarm.factory.node_finalize import draft_final


TASK = 'muse-2bit-demo-r11'
TASKS = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/tasks'


@pytest.fixture
def store(tmp_path):
    root = tmp_path / 'home'
    checkout = root / 'agent-workspace/work'
    checkout.mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
    subprocess.run(['git', '-C', str(checkout), '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                    'commit', '-qm', 'fixture base', '--allow-empty'], check=True)
    task = json.loads((TASKS / f'{TASK}.json').read_text())
    task['source']['pre_integration_commit'] = gate.git(checkout, 'rev-parse', 'HEAD').decode().strip()
    task['plan'] = str(TASKS / f'{TASK}.plan.json')
    path = tmp_path / 'task.json'
    path.write_text(json.dumps(task))
    controller = Controller(root)
    controller.init_task(path)
    yield controller.store
    controller.store.close()


def close_output(store, node_id, output, sealed=None):
    """Only this isolated test store stands in for completed capsule evidence."""
    node = gate.graph(store, TASK)[node_id]
    entry = next(item for item in node['check']['outputs'] if item['name'] == output)
    values = dict(node_id=node_id, output=output, entry=entry, passed=True, state='finished', reason='passed')
    artifacts = []
    if sealed is not None:
        artifact = store.put_artifact(TASK, f'test-sealed-{output}', gate.profile_bytes(sealed), 'application/json', None)
        artifacts = [artifact['artifact_id']]
        values['verifier'] = dict(sealed_artifact=artifacts[0])
    check = store.append_observation(TASK, dict(kind='node_check', values=values, source_artifacts=artifacts))
    evidence = [check['obs_id']]
    publish(store, dict(type='investigate'), evidence, expected_graph_rev=taskgraph.plan_get(store, TASK)['rev'],
            plan_patch=dict(update=[dict(node_id=node_id, state='done', evidence_ids=evidence)]))
    return check['obs_id']


def publish(store, action, evidence=(), **extra):
    return api.dispatch(store, TASK, 'evidence.publish', dict(inputs=dict(type='decision',
        expected_rev=store.get_task(TASK)['current_decision_rev'],
        record=dict(action=action, evidence_ids=list(evidence), **extra))))


def finalize(store):
    for node in from_contract(load(TASK))['nodes']:
        final = draft_final(node)
        final['work']['bound_ccs'] = node['work']['eligible_ccs']
        assert scheduler.finalize(store, TASK, node['node_id'], final, 'Unit test only')['admitted']


def test_run4_admits_without_profile_and_blocks_every_candidate_path(store):
    finalize(store)
    assert [item['node_id'] for item in scheduler.next_work(store, TASK)['runnable']] == ['pin_inputs']
    for name, args in [('builder.submit', {'request': {}, 'idem_key': 'build', 'node_id': 'build_image'}),
                       ('lab_manager.compose', {'node_id': 'deliver_to_lab'}),
                       ('capped_runner.start', {'recipe': 'r11_cache_lab', 'node_id': 'check_seeding_premise'}),
                       ('lab.submit', {'node_id': 'check_seeding_premise'}),
                       ('source_workbench.write', {'path': 'candidate.txt', 'text': 'source', 'expected_sha256': None})]:
        with pytest.raises(ValueError):
            api.dispatch(store, TASK, name, dict(inputs=args))
    pin = close_output(store, 'pin_inputs', 'pinned_inputs')
    task = store.get_task(TASK)
    checkpoint = task['constraints']['seeding_checkpoint']
    assert gate.external_wait(store, task, checkpoint)[0].startswith('Awaiting operator')
    checks = NodeChecks(store)
    with pytest.raises(ValueError, match='only host-imported'):
        checks.start(TASK, 'check_seeding_premise', verifier_inputs={'request': {}})
    with pytest.raises(ValueError, match='operator-imported seeding_trace'):
        checks.start(TASK, 'check_seeding_premise', refs={'evidence_ids': [pin]})


def test_sealed_negative_premise_keeps_build_and_unlinked_stop_closed(store):
    finalize(store)
    pin = close_output(store, 'pin_inputs', 'pinned_inputs')
    premise = close_output(store, 'check_seeding_premise', 'premise',
        dict(format=gate.PREMISE_SCHEMA, may_build=False, reason='No held-out cache benefit'))
    with pytest.raises(ValueError, match='refused candidate work'):
        taskgraph.dispatch_precondition(store, TASK, 'implement_seeding')
    stop = dict(type='stop_missing_prerequisite', reason='The sealed premise found no headroom.')
    with pytest.raises(ValueError, match='cited sealed result'):
        publish(store, stop, [pin])
    assert publish(store, stop, [premise])['action'] == stop


def test_lab_draft_has_same_image_scopes_exact_container_mount_and_receipts(store):
    task = store.get_task(TASK)
    contract = load_for_task(task, TASK)
    manager = LabManager(store, route='mailbox')
    draft = manager.draft_task(TASK, dict(AQBC='engine', AQBCE='engine'),
        dict(engine=dict(kind='container_image', identity=dict(id='candidate')), seeding_profile=dict(
            kind='artifact', identity=dict(artifact_id='test-profile'), transfer='attach')))
    assert not draft['problems']
    spec = draft['lab_task']
    assert {item['name'] for item in spec['deliverables']['files']} == set(gate.EVIDENCE_FILES)
    coverage = {(metric, arm, req) for test in spec['tests'] for metric in test.get('measure', [])
                for arm in test['arms'] for req in test.get('requests', [None])}
    assert coverage == gate.required_measurements(contract)
    spec['arms']['AQBCE']['env'] = dict(gate.policy(task)['profile_env'])
    verified = task_problems(spec, contract, task['constraints']['contract_sha256'])
    assert not verified
    spec['arms']['AQBCE']['env']['LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH'] = '/opt/unsafe-other-path'
    assert any('absolute host path' in text for text in task_problems(spec, contract, task['constraints']['contract_sha256']))


def test_pinned_calibration_rejects_short_profile():
    contract = load(TASK)
    with pytest.raises(ValueError, match='specifies 16 requests, trace contains 2'):
        gate.verify_calibration_binding(contract, {'requests': [{'cohort': 'calibration'}] * 2})


def test_rendered_calibration_compares_each_request(tmp_path, monkeypatch):
    import shutil

    folder = Path('ops/spark/prompts/muse')
    target = tmp_path / folder
    target.mkdir(parents=True)
    for filename in ('chat_template.jinja', 'MANIFEST.json'):
        shutil.copy(TASKS.parents[2] / folder / filename, target / filename)
    monkeypatch.setattr(gate, '__file__', str(tmp_path / 'jiuwenswarm/factory/muse_r11_gate.py'))
    source = target / 'fixture.jsonl'
    prompt = 'Rendered fixture with a trailing newline.\n'
    record = {'id': 'fixture', 'rendered_prompt': prompt, 'n_predict': 32, 'token_ids_sha256': 'a' * 64}
    source.write_text(json.dumps(record) + '\n')
    sha = gate.digest(source.read_bytes())
    spec = dict(repo_path=str(source.relative_to(tmp_path)), size=source.stat().st_size, sha256=sha)
    contract = {'inputs': {'calibration_prompts': spec}}
    row = dict(id='fixture', cohort='calibration', prompt_sha256=gate.digest(prompt.encode()),
               generated_n=32, cache_prompt=False, token_ids_sha256=record['token_ids_sha256'])
    assert gate.verify_calibration_binding(contract, {'requests': [row]}) == sha
    for field, other in [('id', 'other'), ('prompt_sha256', '0' * 64), ('generated_n', 31),
                         ('cache_prompt', True), ('token_ids_sha256', 'b' * 64)]:
        with pytest.raises(ValueError, match='differs|differ'):
            gate.verify_calibration_binding(contract, {'requests': [{**row, field: other}]})
