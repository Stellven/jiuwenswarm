"""Revision 10 dispatch admission, with no engine or GPU operations."""

import json
from pathlib import Path

import pytest

from jiuwenswarm.factory import api, scheduler, taskgraph
from jiuwenswarm.factory.contract import load
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.node_contract import from_contract
from jiuwenswarm.factory.node_finalize import draft_final


TASK = 'muse-2bit-demo-r10'


@pytest.fixture
def factory(tmp_path):
    controller = Controller(tmp_path)
    task = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/tasks' / f'{TASK}.json'
    controller.init_task(task)
    return controller.store


def by_id(store, key):
    return next(n for n in taskgraph.plan_get(store, TASK)['nodes'] if n['node_id'] == key)


def publish(store, action, evidence=(), close=None):
    record = {'action': action, 'evidence_ids': list(evidence)}
    if close:
        node_id, check = close
        record.update(expected_graph_rev=taskgraph.plan_get(store, TASK)['rev'],
                      plan_patch={'update': [{'node_id': node_id, 'state': 'done', 'evidence_ids': [check]}]})
    return api.dispatch(store, TASK, 'evidence.publish', {'inputs': {
        'type': 'decision', 'expected_rev': store.get_task(TASK)['current_decision_rev'], 'record': record,
    }})


def finish(store, node_id, output, payload=None):
    """Simulate the native output's reserved records inside the isolated test store."""
    entry = next(item for item in by_id(store, node_id)['check']['outputs'] if item['name'] == output)
    values = dict(node_id=node_id, output=output, passed=True, state='finished', entry=entry, reason='passed')
    artifacts = []
    if payload is not None:
        item = store.put_artifact(TASK, 'sealed-test-trace', json.dumps(payload).encode(), 'application/json', None)
        artifacts = [item['artifact_id']]
        values['verifier'] = dict(sealed_artifact=artifacts[0])
    check = store.append_observation(TASK, dict(kind='node_check', values=values, source_artifacts=artifacts))
    publish(store, {'type': 'investigate'}, [check['obs_id']], close=(node_id, check['obs_id']))
    return check['obs_id']


def test_eager_scheduler_still_requires_never_weaker_proposals(factory):
    nodes = from_contract(load(TASK))['nodes']
    assert [n['node_id'] for n in scheduler.next_work(factory, TASK)['to_finalize']] == [n['node_id'] for n in nodes]
    draft = draft_final(nodes[2])
    draft['work']['bound_ccs'] = draft['work']['helpful_ccs']
    draft['node_limits']['gpu_launches'] = 1
    assert scheduler.finalize(factory, TASK, 'verify_fixtures', draft, 'Fixture-only simulated proposal')['admitted'] is False
    assert not scheduler.next_work(factory, TASK)['runnable']


@pytest.mark.parametrize('eligibility', ['already_batched', 'no_eligible_shapes', 'unresolved'])
def test_missing_or_negative_trace_blocks_submissions_and_supports_a_sourced_stop(factory, eligibility):
    for draft in from_contract(load(TASK))['nodes']:
        final = draft_final(draft)
        final['work']['bound_ccs'] = list(final['work']['helpful_ccs'])
        assert scheduler.finalize(factory, TASK, draft['node_id'], final, 'Test-only bound capsules')['admitted']
    assert [n['node_id'] for n in scheduler.next_work(factory, TASK)['runnable']] == ['pin_inputs']

    blocked = [('builder.submit', {'node_id': 'build_image'}), ('builder.submit', {}),
               ('lab_manager.compose', {'node_id': 'deliver_to_lab'}),
               ('capped_runner.start', {'node_id': 'trace_dispatch', 'recipe': 'serve'})]
    for capability, args in blocked:
        with pytest.raises(ValueError):
            with scheduler.admitted(factory, TASK, capability, args):
                pytest.fail(f'Admitted {capability} without a positive trace')
    stop = dict(type='stop_missing_prerequisite', eligibility=eligibility, reason='Fixture eligibility stopped candidate work.')
    with pytest.raises(ValueError):
        publish(factory, stop)

    finish(factory, 'pin_inputs', 'pinned_inputs')
    checked = finish(factory, 'trace_dispatch', 'dispatch_trace', dict(eligibility=eligibility, may_build=False))
    assert not scheduler.next_work(factory, TASK)['runnable']
    with pytest.raises(ValueError, match='Dispatch checkpoint refused candidate work'):
        taskgraph.dispatch_precondition(factory, TASK, 'verify_fixtures')
    for capability, args in blocked:
        with pytest.raises(ValueError):
            with scheduler.admitted(factory, TASK, capability, args):
                pytest.fail(f'Admitted {capability} with a sealed negative trace')

    with pytest.raises(ValueError, match='cite its accepted node check'):
        publish(factory, stop)
    with pytest.raises(ValueError, match='cite its accepted node check'):
        publish(factory, dict(stop, eligibility='eligible'), [checked])
    decision = publish(factory, stop, [checked])
    assert decision['action'] == stop
    assert decision['evidence_ids'] == [checked]


def test_candidate_verifier_only_accepts_current_host_bound_trace_diff_and_receipt(factory, monkeypatch):
    from jiuwenswarm.factory.node_check import NodeChecks

    for draft in from_contract(load(TASK))['nodes']:
        final = draft_final(draft)
        final['work']['bound_ccs'] = list(final['work']['helpful_ccs'])
        assert scheduler.finalize(factory, TASK, draft['node_id'], final, 'Test-only bound capsules')['admitted']
    finish(factory, 'pin_inputs', 'pinned_inputs')
    trace = dict(eligibility='eligible', may_build=True)
    trace_check = finish(factory, 'trace_dispatch', 'dispatch_trace', trace)
    node_id = 'verify_fixtures'
    checks = NodeChecks(factory)
    node = by_id(factory, node_id)
    patch_entry = next(entry for entry in node['check']['outputs'] if entry['name'] == 'candidate_patch')
    patch_file = factory.put_artifact(TASK, 'test-diff', b'--- before\n+++ after\n', 'text/x-diff', None)

    def patch_check(passed):
        return factory.append_observation(TASK, dict(kind='node_check', source_artifacts=[patch_file['artifact_id']],
            values=dict(node_id=node_id, output='candidate_patch', state='finished', passed=passed,
                        entry=patch_entry, diff_sha256=patch_file['sha256'])))['obs_id']

    with pytest.raises(ValueError, match='candidate_patch output check'):
        checks.start(TASK, node_id, 'fixture_evidence', refs={'evidence_ids': [trace_check]})
    patch_id = patch_check(True)
    fixture_file = factory.put_artifact(TASK, 'test-fixture', b'{"format":"fixture-test"}', 'application/json', None)
    fixture_fields = dict(key='candidate_fixture_receipt', artifact_id=fixture_file['artifact_id'],
                          sha256=fixture_file['sha256'])
    bogus = factory.append_observation(TASK, dict(kind='measurement', values=fixture_fields,
                                                 source_artifacts=[fixture_file['artifact_id']]))
    trusted = factory.append_observation(TASK, dict(kind='operator_input', values=fixture_fields,
                                                   source_artifacts=[fixture_file['artifact_id']]))
    refs = {'evidence_ids': [trace_check, patch_id, trusted['obs_id']]}
    for port in ('dispatch_trace', 'fixture_receipt', 'candidate_patch'):
        with pytest.raises(ValueError, match='only host-bound inputs'):
            checks.start(TASK, node_id, 'fixture_evidence', refs=refs, verifier_inputs={port: {}})
    with pytest.raises(ValueError, match='host-imported candidate_fixture_receipt'):
        checks.start(TASK, node_id, 'fixture_evidence',
                     refs={'evidence_ids': [trace_check, patch_id, bogus['obs_id']]})
    with pytest.raises(ValueError, match='current candidate_patch check'):
        checks.start(TASK, node_id, 'fixture_evidence',
                     refs={'evidence_ids': [trace_check, trusted['obs_id']]})
    wrong = factory.append_observation(TASK, dict(kind='operator_input',
        values=dict(fixture_fields, sha256='0' * 64), source_artifacts=[fixture_file['artifact_id']]))
    with pytest.raises(ValueError, match='host-pinned JSON digest'):
        checks.start(TASK, node_id, 'fixture_evidence', refs={'evidence_ids': [trace_check, patch_id, wrong['obs_id']]})
    monkeypatch.setattr(checks, '_start_records', lambda _task, _node, _entry, _refs, _background, inputs: inputs)
    inputs = checks.start(TASK, node_id, 'fixture_evidence', refs=refs)

    def pin(file):
        return dict(uri=(factory.home / file['location']).as_uri(), sha256=file['sha256'])

    assert inputs == dict(dispatch_trace=trace, fixture_receipt=pin(fixture_file), candidate_patch=pin(patch_file))
    request = dict(task_id=TASK, node_id=node_id, refs=refs, verifier_inputs=inputs,
                   verifier={'cc': 'engine.gpu_kernel_lab', 'capability': 'verify_candidate'})
    patch_check(False)
    with pytest.raises(ValueError, match='candidate_patch output check'):
        checks._call_verifier(request, factory.home)
