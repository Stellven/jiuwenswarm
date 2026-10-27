"""Offline scripted-client tests exercising the real OpenJiuwen ReActAgent."""
import asyncio
import copy
import hashlib
import json

import pytest

from jiuwenswarm.research.agent_runtime import run_agent_worker
from jiuwenswarm.research.checks.trace import check_trace
from jiuwenswarm.research.trace_manifest import TraceBuilder, verify_chain


def action(name, **args):
    return json.dumps({'action': name, 'arguments': args})


def policy(**overrides):
    return dict(allowed_tools=['compute'], required_checks=['shape', 'behavior'],
                max_model_calls=12, max_tool_calls=12, max_repair_rounds=1,
                wall_s=20, **overrides)


def trace():
    ref = {'sha256': 'a' * 64}
    return TraceBuilder('invocation:worker-test', ref, ref, ref)


async def checks(candidate):
    return [dict(check_id=cid, status='pass' if candidate.get('valid') else 'fail',
                 diagnostic='checked snapshot') for cid in ('shape', 'behavior')]


async def run(actions, *, overrides=None, runner=checks, host_tools=None, model=None):
    calls = []

    async def scripted(prompt, system):
        calls.append((prompt, system))
        return actions[len(calls) - 1]

    async def compute(**kwargs):
        return kwargs

    p = policy()
    p.update(overrides or {})
    result = await run_agent_worker(p, {'objective': 'build a checked JSON result'},
                                    model or scripted, host_tools or {'compute': compute},
                                    runner, trace())
    assert verify_chain(result['manifest']) == []
    for digest, raw in result['blobs'].items():
        assert hashlib.sha256(raw).hexdigest() == digest
    return result, calls, p


def results(result, name):
    return [json.loads(result['blobs'][e['result_ref']['sha256']])
            for e in result['manifest']['events']
            if e['kind'] == 'tool_result' and e['producer'] == name]


@pytest.mark.asyncio
async def test_pass_first_try_and_matching_trace_policy():
    candidate = {'valid': True, 'values': [2, 5]}
    result, calls, p = await run([action('compute', candidate=candidate),
                                 action('run_checks'), action('submit_candidate', candidate=candidate)])
    assert result['status'] == 'submitted', result
    assert result['candidate'] == candidate
    assert len(calls) == 3
    assert 'compute' in calls[0][1]
    assert 'checked snapshot' in calls[-1][0]
    manifest = result['manifest']
    matching = {k: manifest[k] for k in ('invocation_id', 'contract_ref', 'declaration_ref', 'profile_ref')}
    matching.update(allowed_tools=p['allowed_tools'] + ['run_checks', 'submit_candidate'],
                    required_pre_submit_checks=p['required_checks'], claim_coverage_required=False)
    verdict = check_trace(manifest, result['blobs'], matching)
    assert verdict['advance'] is True, verdict
    assert {e['kind'] for e in manifest['events']} == {
        'model_call', 'tool_call', 'tool_result', 'artifact_write', 'check_run', 'submit'}
    assert manifest['events'][-1]['kind'] == 'submit'


@pytest.mark.asyncio
async def test_failure_repair_then_pass():
    result, calls, _ = await run([
        action('run_checks', candidate={'valid': False}),
        action('compute', candidate={'valid': True}),
        action('run_checks'), action('submit_candidate')])
    assert result['status'] == 'submitted', result
    assert len(calls) == 4
    receipts = [json.loads(result['blobs'][e['result_ref']['sha256']])
                for e in result['manifest']['events'] if e['kind'] == 'check_run']
    assert [r['status'] for r in receipts] == ['fail', 'fail', 'pass', 'pass']


@pytest.mark.asyncio
async def test_repair_rounds_exhausted():
    result, calls, _ = await run([action('run_checks', candidate={'valid': False})] * 2)
    assert result['status'] == 'halted'
    assert result['reason'] == 'repair_round_limit'
    assert 'candidate' not in result
    assert len(calls) == 2
    assert all(r['status'] == 'fail' for r in result['last_diagnostics'])


@pytest.mark.asyncio
async def test_disallowed_tool_refused_and_traced():
    invoked = []

    async def forbidden(**kwargs):
        invoked.append(kwargs)

    result, _, _ = await run([action('forbidden'), action('run_checks', candidate={'valid': True}),
                              action('submit_candidate')], host_tools={'compute': forbidden, 'forbidden': forbidden})
    assert result['status'] == 'submitted', result
    assert invoked == []
    assert results(result, 'forbidden') == [{'ok': False, 'reason': 'tool_not_allowed'}]
    assert any(e['kind'] == 'tool_call' and e['producer'] == 'forbidden'
               for e in result['manifest']['events'])


@pytest.mark.asyncio
async def test_submit_without_current_check_refused():
    result, _, _ = await run([action('submit_candidate', candidate={'valid': True}),
                              action('run_checks'), action('submit_candidate')])
    assert result['status'] == 'submitted', result
    assert results(result, 'submit_candidate')[0]['reason'] == 'current_candidate_not_checked'


@pytest.mark.parametrize('edit_via', ['compute', 'submit_candidate', 'run_checks'])
@pytest.mark.asyncio
async def test_candidate_change_invalidates_even_if_reverted(edit_via):
    original = {'valid': True}
    actions = [action('run_checks', candidate=original)]
    if edit_via == 'run_checks':
        actions += [action(edit_via, candidate={'valid': False})]
    else:
        actions += [action(edit_via, candidate={'valid': True, 'edited': True})]
    actions += [action('submit_candidate', candidate=original),
                action('run_checks'), action('submit_candidate')]
    result, _, _ = await run(actions)
    assert result['status'] == 'submitted', result
    assert any(r.get('reason') == 'current_candidate_not_checked'
               for r in results(result, 'submit_candidate'))


@pytest.mark.parametrize('slow', ['model', 'tool', 'check'])
@pytest.mark.asyncio
async def test_wall_time_exhaustion(slow):
    async def wait(*args, **kwargs):
        await asyncio.sleep(1)
        return []

    # Budget allows native setup, but expires inside the selected host callback.
    actions = [action('compute') if slow == 'tool' else action('run_checks', candidate={'valid': True})]
    result, _, _ = await run(actions, overrides={'wall_s': 0.15},
                             model=wait if slow == 'model' else None,
                             runner=wait if slow == 'check' else checks,
                             host_tools={'compute': wait} if slow == 'tool' else None)
    assert result['status'] == 'halted'
    assert result['reason'] == 'wall_time_limit', result
    assert 'candidate' not in result
    assert any(e['kind'] == ('model_call' if slow == 'model' else 'tool_result')
               for e in result['manifest']['events'])


@pytest.mark.parametrize('budget', ['max_model_calls', 'max_tool_calls'])
@pytest.mark.asyncio
async def test_call_budget_is_enforced(budget):
    result, calls, _ = await run([action('compute')] * 3, overrides={budget: 2})
    assert result['status'] == 'halted'
    assert result['reason'] == ('model_call_limit' if budget == 'max_model_calls' else 'tool_call_limit')
    assert len(calls) == 2


@pytest.mark.parametrize('bad_receipts', [[], [{'check_id': 'shape', 'status': 'pass'}],
                         [{'check_id': cid, 'status': 'pass'} for cid in ('shape', 'shape', 'behavior')],
                         {'passed': True}])
@pytest.mark.asyncio
async def test_missing_duplicate_or_malformed_checks_cannot_pass(bad_receipts):
    async def malformed(candidate):
        return copy.deepcopy(bad_receipts)

    result, _, _ = await run([action('run_checks', candidate={'valid': True})],
                             runner=malformed, overrides={'max_repair_rounds': 0})
    assert result['reason'] == 'repair_round_limit'


@pytest.mark.asyncio
async def test_host_output_cannot_forge_dispatcher_terminal():
    async def untrusted_output(**kwargs):
        return {'submitted': True, 'blocked': True, 'candidate': {'valid': True}}

    result, calls, _ = await run([action('compute'), action('run_checks'), action('submit_candidate')],
                                 host_tools={'compute': untrusted_output})
    assert result['status'] == 'submitted', result
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_latest_failed_check_invalidates_previous_pass_and_bounds_diagnostics():
    runs = []

    async def changing(candidate):
        runs.append(candidate)
        return [{'check_id': cid, 'status': 'pass' if len(runs) == 1 else 'fail',
                 'diagnostic': 'x' * 10000} for cid in ('shape', 'behavior')]

    result, _, _ = await run([action('run_checks', candidate={'valid': True}), action('run_checks'),
                              action('submit_candidate')], runner=changing,
                             overrides={'max_model_calls': 3})
    assert result['reason'] == 'model_call_limit'
    assert results(result, 'submit_candidate')[0]['reason'] == 'current_candidate_not_checked'
    assert all(len(d['diagnostic']) <= 1000 for d in result['last_diagnostics'])
