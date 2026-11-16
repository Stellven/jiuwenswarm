"""Real native CC composition plus explicitly injected lifecycle faults."""
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.software_factory.cc_catalog import describe_capabilities
from jiuwenswarm.software_factory.cc_workflow import CCWorkflow, WorkflowConflict
from jiuwenswarm.software_factory.contracts import StageFailure
from jiuwenswarm.software_factory.workflow_definitions import (
    Binding, StageRef, SubworkflowDefinition, SubworkflowRef, WorkflowDefinition, WorkflowRegistry,
)


@pytest.fixture
def setup(tmp_path):
    bundle = tmp_path / 'cc'
    bundle.mkdir()
    (bundle / 'run.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'outcome':'ok','outputs':{'value':p['inputs']['value']*2}}))\n")
    (bundle / 'cc.yaml').write_text(yaml.safe_dump(dict(cc='2', id='test.double', version='1.0.0',
        bindings={'default': {'kind': 'native', 'command': ['{python}', '{bundle}/run.py']}},
        capabilities={'double': {'does': 'Double a number', 'takes': {'value': 'json'}, 'gives': {'value': 'json'}}})))
    host = Host(tmp_path / 'host', session_grants=[])
    caps = describe_capabilities(host, [host.seal(bundle)])
    sub = SubworkflowDefinition('double', 'Double', {'value': 'json'}, (
        StageRef('call', 'test.double:double', {'value': Binding('$input', 'value')}),), {'value': Binding('call', 'value')})
    workflow = WorkflowDefinition('calculate', 'Calculate', {'value': 'json'}, (
        SubworkflowRef('first', 'double', {'value': Binding('$input', 'value')}),
        SubworkflowRef('second', 'double', {'value': Binding('first', 'value')})), {'value': Binding('second', 'value')})
    registry = WorkflowRegistry(caps, [sub], [workflow])
    runtime = CCWorkflow(tmp_path / 'runs', host, caps, task_id='cpu-test')
    return runtime, registry, host, caps


def finish(runtime, run_id, limit=20):
    for _ in range(limit):
        run = runtime.tick(run_id)
        if run['status'] in {'completed', 'failed', 'cancelled'}:
            return run
    raise AssertionError('Workflow did not settle')


def test_real_ccs_nested_selection_and_replay(setup):
    runtime, registry, host, caps = setup
    graph = registry.expand('calculate')
    run = runtime.create(graph, {'value': 7}, objective='Exercise real CC composition', run_id='cpu')
    done = finish(runtime, run['id'])
    assert done['nodes'][-1]['outputs']['value'] == 28
    assert done['acceptance'] == 'not_assessed'
    assert all(n['receipts'][0]['release'] == caps[0].release for n in done['nodes'])
    assert runtime.create(graph, {'value': 7}, objective='Exercise real CC composition', run_id='cpu') == done
    with pytest.raises(WorkflowConflict):
        runtime.create(graph, {'value': 8}, objective='Exercise real CC composition', run_id='cpu')
    assert [e['sequence'] for e in runtime.events('cpu')] == list(range(1, done['sequence'] + 1))
    selected = runtime.create(registry.expand('calculate/second'), {'value': 3}, objective='Independent selection')
    assert len(finish(runtime, selected['id'])['nodes']) == 1


def test_lost_ack_restart_reuses_same_real_call(setup):
    runtime, registry, host, caps = setup
    run = runtime.create(registry.expand('calculate'), {'value': 5}, objective='Lost acknowledgement')
    original = host.call
    def lose_ack(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('Injected lost acknowledgement after real execution')
    with patch.object(host, 'call', lose_ack):
        runtime.tick(run['id'])
    restarted = CCWorkflow(runtime.root, host, caps, task_id='cpu-test')
    done = finish(restarted, run['id'])
    assert done['nodes'][-1]['outputs']['value'] == 20
    with host.db() as db:
        assert db.execute('SELECT count(*) FROM calls').fetchone()[0] == 2


def test_adaptation_is_append_only_and_evidence_scoped(setup):
    runtime, registry, host, caps = setup
    run = finish(runtime, runtime.create(registry.expand('calculate'), {'value': 2}, objective='Adaptive experiment')['id'])
    graph = registry.expand('calculate/second', instance_id='revision2')
    decision = {'reason': 'Observed output warrants a follow-up', 'evidence': [{'task_id': 'cpu-test', 'node_id': run['nodes'][-1]['id']}]}
    revised = runtime.append(run['id'], graph, {'value': 9}, expected_revision=1, decision=decision)
    assert revised['nodes'][:2] == run['nodes']
    assert finish(runtime, run['id'])['nodes'][-1]['outputs']['value'] == 18
    with pytest.raises(WorkflowConflict):
        runtime.append(run['id'], graph, {'value': 9}, expected_revision=1, decision=decision)
    with pytest.raises(ValueError):
        runtime.append(run['id'], graph, {'value': 9}, expected_revision=2,
            decision={'reason': 'bad evidence', 'evidence': [{'task_id': 'other', 'node_id': run['nodes'][0]['id']}]})


def test_stop_and_grants_do_not_expand_authority(setup):
    runtime, registry, host, caps = setup
    run = runtime.create(registry.expand('calculate'), {'value': 2}, objective='Stop before effects')
    runtime.stop(run['id'])
    assert finish(runtime, run['id'])['status'] == 'cancelled'
    with host.db() as db:
        assert db.execute('SELECT count(*) FROM calls').fetchone()[0] == 0
    runtime.capabilities[caps[0].id] = replace(caps[0], changes=('process.exec',))
    with pytest.raises(ValueError, match='grants'):
        runtime.create(registry.expand('calculate'), {'value': 2}, objective='Denied')


def test_uncertain_call_blocks_descendants_without_retry(setup):
    runtime, registry, host, caps = setup
    run = runtime.create(registry.expand('calculate'), {'value': 2}, objective='Unknown execution')
    keys = []
    def uncertain(*args, **kwargs):
        keys.append(kwargs['key'])
        return dict(state='unknown', completeness='none', outputs={}, reason='INJECTED', call='injected')
    with patch.object(host, 'call', uncertain):
        for _ in range(3):
            state = runtime.tick(run['id'])
    assert len(set(keys)) == 1
    assert state['nodes'][1]['state'] == 'pending'


def test_bound_context_cannot_change_on_restart(setup):
    runtime, registry, host, caps = setup
    run = runtime.create(registry.expand('calculate'), {'value': 2}, objective='Scope')
    other = CCWorkflow(runtime.root, host, caps, task_id='other-task')
    with pytest.raises(WorkflowConflict):
        other.get(run['id'])


def test_recursive_subworkflows_and_cycle_rejection(setup):
    runtime, registry, host, caps = setup
    leaf = registry.subworkflows['double']
    nested = SubworkflowDefinition('nested', 'Nested', {'value': 'json'}, (
        SubworkflowRef('child', 'double', {'value': Binding('$input', 'value')}),), {'value': Binding('child', 'value')})
    top = WorkflowDefinition('recursive', 'Recursive', {'value': 'json'}, (
        SubworkflowRef('nested', 'nested', {'value': Binding('$input', 'value')}),), {'value': Binding('nested', 'value')})
    registry = WorkflowRegistry(caps, [leaf, nested], [top])
    graph = registry.expand('recursive')
    assert graph.nodes[0].id == 'main/recursive/nested/child/call'
    assert finish(runtime, runtime.create(graph, {'value': 4}, objective='Recursive composition')['id'])['nodes'][0]['outputs']['value'] == 8
    assert len(registry.expand('recursive/nested/child/call').nodes) == 1
    recursive = replace(nested, stages=(SubworkflowRef('self', 'nested', {'value': Binding('$input', 'value')}),))
    with pytest.raises(StageFailure):
        WorkflowRegistry(caps, [recursive], [top])


def test_lab_lifecycle_collects_rejection_and_cancellation_continues(setup):
    """Injected lab replies exercise ownership; no hardware execution claimed."""
    runtime, registry, host, caps = setup
    cap = replace(caps[0], lifecycle={'status': 'status', 'result': 'result', 'cancel': 'cancel'})
    runtime.capabilities[cap.id] = cap
    calls = []
    def describe(_):
        return {'capabilities': {name: {'changes': []} for name in ('double', 'status', 'cancel', 'result')}}
    def call(release, operation, inputs, **kwargs):
        calls.append((operation, inputs))
        if operation == 'double':
            outputs = {'value': inputs['value'] * 2, 'attempt_id': 'job-' + str(inputs['value'])}
        elif operation == 'result':
            outputs = {'execution_outcome': 'succeeded', 'evaluation': {'acceptance': 'reject'}, 'evidence_refs': []}
        else:
            outputs = dict(task_id='cpu-test', attempt_id=inputs['attempt_id'], state='succeeded', cleanup_state='reaped')
        return dict(state='succeeded', completeness='complete', outputs=outputs, call=kwargs['key'])
    with patch.object(host, 'describe', describe), patch.object(host, 'call', call):
        run = runtime.create(registry.expand('calculate'), {'value': 2}, objective='Rejected candidate')
        done = finish(runtime, run['id'])
    assert done['status'] == 'completed'
    assert done['acceptance'] == 'not_assessed'
    assert all(n['lab']['collected'] for n in done['nodes'])
    assert done['nodes'][0]['lab']['result']['evaluation']['acceptance'] == 'reject'
    assert [op for op, _ in calls] == ['double', 'status', 'result', 'double', 'status', 'result']

    # Independent siblings, with one cancel transport failure.
    graph = registry.expand('calculate')
    second = replace(graph.nodes[1], input_bindings=graph.nodes[0].input_bindings)
    graph = replace(graph, nodes=(graph.nodes[0], second))
    cancelled = []
    def cancel_fault(release, operation, inputs, **kwargs):
        if operation == 'cancel':
            cancelled.append(kwargs['key'])
            if len(cancelled) == 1:
                raise OSError('Injected cancellation failure')
        return call(release, operation, inputs, **kwargs)
    with patch.object(host, 'describe', describe), patch.object(host, 'call', cancel_fault):
        run = runtime.create(graph, {'value': 3}, objective='Cancel siblings')
        runtime.tick(run['id'])
        runtime.tick(run['id'])
        runtime.stop(run['id'], 'deadline')
        runtime.tick(run['id'])
        state = runtime.tick(run['id'])
    assert len(cancelled) == 2 and cancelled[0] != cancelled[1]
    assert state['stop_reason'] == 'deadline'
    assert state['status'] == 'stopping'


def test_native_service_http_scope_and_replay(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jiuwenswarm.software_factory.cc_api import create_cc_router
    from jiuwenswarm.software_factory.cc_service import CCService
    runtime, registry, host, caps = setup
    app = FastAPI()
    app.include_router(create_cc_router(CCService(runtime, registry)))
    client = TestClient(app)
    assert client.get('/api/v1/cc-workflows/catalog', headers={'Origin': 'https://untrusted.example'}).status_code == 403
    response = client.post('/api/v1/cc-workflows/runs', json={
        'workflow': 'calculate', 'inputs': {'value': 6}, 'objective': 'HTTP execution'})
    assert response.status_code == 202
    run_id = response.json()['id']
    for _ in range(3):
        response = client.post(f'/api/v1/cc-workflows/runs/{run_id}/tick', json={})
        assert response.status_code == 200
    assert response.json()['status'] == 'completed'
    events = client.get(f'/api/v1/cc-workflows/runs/{run_id}/events').json()
    assert events[0]['nodes'][0]['state'] == 'pending'
    assert [e for e in events if e['type'] == 'cc.receipt'][-1]['outputs']['value'] == 24
    assert client.post('/api/v1/cc-workflows/runs', json={
        'workflow': 'calculate', 'inputs': {'value': 1}, 'objective': 'Bad authority', 'grants': ['process.exec']}).status_code == 422


def test_prepare_existing_packages_and_reload_without_resealing(setup, tmp_path):
    from jiuwenswarm.software_factory.cc_prepare import prepare
    from jiuwenswarm.software_factory.cc_service import CCService
    config = tmp_path / 'prepared' / 'config.json'
    prepare(config, 'prepared-task', [tmp_path / 'cc'])
    service = CCService.from_config(config)
    run = service.create({'workflow': 'test-double-double', 'inputs': {'value': 11}, 'objective': 'Prepared native CC'})
    assert finish(service.runtime, run['id'])['nodes'][0]['outputs']['value'] == 22
    (tmp_path / 'cc' / 'run.py').write_text('raise RuntimeError("changed after sealing")')
    resumed = CCService.from_config(config)
    new = resumed.create({'workflow': 'test-double-double', 'inputs': {'value': 12}, 'objective': 'Pinned native CC'})
    assert finish(resumed.runtime, new['id'])['nodes'][0]['outputs']['value'] == 24
