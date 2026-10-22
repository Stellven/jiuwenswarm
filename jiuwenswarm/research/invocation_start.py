"""Protected inert invocation preparation and the once-consumed start boundary.

Preparation records are audit evidence. Only the actual registered live owner,
original native exchanges when required, and a current local CAS can start work.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
import math
import time
import uuid

from .contracts import ResearchError, validate


def require(value, message, code='executor_preparation_authorization'):
    if not value:
        raise ResearchError(code, message)


def binding(execution, execution_id):
    return {'contract_ref': copy.deepcopy(execution['contract_ref']),
        'invocation_id': execution['invocation_id'], 'execution_id': execution_id}


def prepare(runner, context):
    execution = runner._executions[context.execution_id]
    now = time.monotonic()
    remaining = execution['deadline'] - now
    require(type(remaining) in (int, float) and math.isfinite(remaining) and remaining > 0,
        'Original invocation deadline expired during preparation', 'budget_exhausted')
    recorded = time.time_ns()
    deadline = recorded + int(remaining * 1_000_000_000)
    owner = execution.get('evaluation_owner')
    grant_ref = execution.get('evaluation_grant_ref')
    if owner is not None:
        grant = owner.projection.load_execution(grant_ref)[0]
        deadline = min(deadline, grant['deadline_unix_ns'])
    require(deadline > recorded, 'Preparation has no remaining original allowance', 'budget_exhausted')
    record = {'schema': 'ai4r-invocation-preparation:1',
        'id': 'invocation-preparation:' + uuid.uuid4().hex,
        **binding(execution, context.execution_id), 'assignment_grant_ref': grant_ref,
        'recorded_unix_ns': recorded, 'deadline_unix_ns': deadline}
    validate('urn:ai4r:private:invocation-preparation:1', record)
    ref = runner.store.append_record('invocation-preparation', record)
    execution.update(phase='prepared', preparation_ref=ref, preparation=record,
        start_pending=False, actual_started_at=None, actual_started_monotonic_s=None)
    runner._preparations[context.execution_id] = {'context': context, 'execution': execution}
    return context


def current(runner, payload):
    require(type(payload) is dict and set(payload) == {'contract_ref', 'invocation_id', 'execution_id'},
        'Prepared binding must contain exactly its original three identities')
    validate('Ref', payload['contract_ref'])
    require(all(type(payload[key]) is str and payload[key] for key in ('execution_id', 'invocation_id')),
        'Prepared execution identities must be immutable nonempty strings')
    registration = runner._preparations.get(payload['execution_id'])
    execution = runner._executions.get(payload['execution_id'])
    require(registration is not None and registration['execution'] is execution
        and registration['context']._runner is runner and not execution['closed']
        and execution.get('phase') == 'prepared'
        and binding(execution, payload['execution_id']) == payload,
        'No matching actual live prepared invocation')
    record = execution['preparation']
    require(runner.store.record_kind(execution['preparation_ref']) == 'invocation-preparation'
        and runner.store.read_record(execution['preparation_ref']) == record,
        'Original indexed preparation differs')
    validate('urn:ai4r:private:invocation-preparation:1', record)
    require(all(record[key] == payload[key] for key in payload)
        and record['deadline_unix_ns'] > time.time_ns(), 'Original preparation expired', 'budget_exhausted')
    deadline = execution['deadline']
    require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline > time.monotonic(),
        'Original prepared invocation deadline expired', 'budget_exhausted')
    owner = execution.get('evaluation_owner')
    if owner is not None:
        require(owner in runner._evaluation_owners and owner.runner is runner and owner.store is runner.store
            and runner.resolve_evaluation_owner(execution_id=payload['execution_id']) is owner,
            'Actual private prepared owner is unavailable')
        grant, contract, _ = owner.projection.load_execution(execution['evaluation_grant_ref'])
        owner._active(grant['request_ref'])
        require(owner._assignment(payload['execution_id'])['state'] == 'prepared'
            and record['assignment_grant_ref'] == execution['evaluation_grant_ref']
            and grant['contract_ref'] == payload['contract_ref']
            and grant['invocation_id'] == payload['invocation_id']
            and contract == execution['contract'], 'Private prepared assignment differs')
    else:
        contract = runner.store.read_record(payload['contract_ref'], contract_id='subnode-execution-contract')
        require(contract == execution['contract'], 'Prepared canonical child changed')
        runner._require_child_authority(payload['contract_ref'], contract)
        runner._require_check_assets(contract)
        attempt = runner.store.get_attempt(*(contract[key] for key in
            ('run_id', 'node_id', 'subnode_id', 'attempt_id')))
        require(attempt['state'] == 'prepared' and attempt['contract_ref'] == payload['contract_ref'],
            'Original once reservation is no longer prepared')
        budget = runner._budget_state(contract, execution)
    remaining = min(deadline - time.monotonic(), (record['deadline_unix_ns'] - time.time_ns()) / 1e9,
        budget['spendable']['time_s'] if owner is None else float('inf'))
    require(math.isfinite(remaining) and remaining > 0, 'Original prepared allowance expired', 'budget_exhausted')
    return execution, {'contract_ref': copy.deepcopy(payload['contract_ref']),
        'invocation_id': payload['invocation_id'], 'execution_id': payload['execution_id'],
        'contract': copy.deepcopy(execution['contract']),
        'preparation_ref': copy.deepcopy(execution['preparation_ref']),
        'execution_deadline_monotonic_s': deadline, 'remaining_time_s': remaining}


def authorize(runner, payload):
    return current(runner, payload)[1]


def validate_invocation_preparation(store, preparation_ref, response):
    """Independent immutable custody validation after a fresh live callback.

    This function has no live-owner registry and supplies no liveness or start
    authority. The authenticated caller must separately bind the actual live
    callback and same Store/runtime session on every exchange.
    """
    fields={'contract_ref','invocation_id','execution_id'}
    require(type(response) is dict and set(response)==fields|{'contract','preparation_ref',
        'execution_deadline_monotonic_s','remaining_time_s'}, 'Malformed exact prepared response')
    validate('Ref',preparation_ref)
    require(response['preparation_ref']==preparation_ref
        and store.record_kind(preparation_ref)=='invocation-preparation', 'Prepared response names another indexed original')
    record=store.read_record(preparation_ref)
    validate('urn:ai4r:private:invocation-preparation:1',record)
    require(all(record[key]==response[key] for key in fields)
        and record['deadline_unix_ns']>record['recorded_unix_ns']
        and record['deadline_unix_ns']>time.time_ns(), 'Prepared original identities/deadline differ')
    request={key:copy.deepcopy(response[key]) for key in fields}
    validate('Ref',request['contract_ref'])
    kind=store.record_kind(request['contract_ref'])
    if record['assignment_grant_ref'] is not None:
        require(kind=='evaluation-subnode-context', 'Private preparation must name its exact private child')
        from .evaluation_authority import validate_evaluation_executor_binding
        six={key:value for key,value in response.items() if key!='preparation_ref'}
        child=validate_evaluation_executor_binding(store,request,six,_prepared=True)
        grant_ref=record['assignment_grant_ref']
        require(store.record_kind(grant_ref)=='evaluation-assignment-grant', 'Original prepared grant kind differs')
        grant=store.read_record(grant_ref)
        validate('urn:ai4r:private:evaluation-assignment-grant:1',grant)
        require(all(grant[key]==request[key] for key in fields)
            and record['deadline_unix_ns']<=grant['deadline_unix_ns'], 'Original private preparation/grant differs')
    else:
        require(kind=='subnode-execution-contract', 'Ordinary preparation must name its exact canonical child')
        child=store.read_record(request['contract_ref'],contract_id='subnode-execution-contract')
        require(response['contract']==child,'Original canonical prepared child differs')
        attempt=store.get_attempt(*(child[key] for key in ('run_id','node_id','subnode_id','attempt_id')))
        run=store.get_run(child['run_id'])
        require(attempt['state']=='prepared' and attempt['contract_ref']==request['contract_ref']
            and run['state'] in {'pending','running'} and not store.cancellation_requested(child['run_id']),
            'Original canonical preparation is stopped or already consumed')
        from .binding import validate_child_authority
        validate_child_authority(store,child['node_contract_ref'],child['subnode_id'],child['inputs'],
            effective_authority=child['bindings'][0]['effective_authority'])
    from .attempt_resources import attempt_resource_disposition
    attempt_resource_disposition(store,child['node_contract_ref'])
    deadline,remaining=response['execution_deadline_monotonic_s'],response['remaining_time_s']
    now=time.monotonic()
    # The live callback captured remaining before this custody roundtrip and
    # the original-source checks above. It is a duration snapshot, not a new
    # allowance: compare it to the immutable prepared duration while requiring
    # both absolute expiries to remain live. Start recomputes spendable time.
    prepared_duration=(record['deadline_unix_ns']-record['recorded_unix_ns'])/1e9
    require(type(deadline) in (int,float) and math.isfinite(deadline)
        and type(remaining) in (int,float) and math.isfinite(remaining)
        and deadline>now and record['deadline_unix_ns']>time.time_ns()
        and 0<remaining<=prepared_duration,
        'Prepared response exceeds its finite original allowance','budget_exhausted')
    return copy.deepcopy(child)


def _receipt(store, ref, kind):
    validate('Ref', ref)
    require(store.record_kind(ref) == kind, 'Native start receipt has another original indexed kind')
    value = store.read_record(ref)
    validate('urn:ai4r:private:' + kind + ':1', value)
    return value


async def _exchange(runner, context, method, payload):
    execution = runner._executions[context.execution_id]
    _, protected = current(runner, binding(execution, context.execution_id))
    carrier = runner._require_native_start_port()
    operation = getattr(carrier, method, None)
    require(callable(operation), 'Protected native start service is unavailable', 'SCIENCE_RUNTIME_BINDINGS_UNAVAILABLE')
    response = operation(payload)
    require(inspect.isawaitable(response), 'Native start must use an explicitly awaited protected carrier')
    response = await asyncio.wait_for(response, timeout=protected['remaining_time_s'])
    current(runner, binding(execution, context.execution_id))
    return response


async def start(runner, context, *, dispatch=None):
    execution, _ = current(runner, {'contract_ref': context.contract_ref,
        'invocation_id': context.invocation_id, 'execution_id': context.execution_id})
    require(not execution['start_pending'], 'Start is already consumed; reconcile without replay')
    execution['start_pending'] = True
    try:
        from .attempt_resources import AttemptResourceDisposition, attempt_resource_disposition
        disposition = attempt_resource_disposition(runner.store, execution['contract']['node_contract_ref'])
        require(type(disposition) is AttemptResourceDisposition, 'Protected whole-parent disposition is unavailable')
        if disposition.requires_broker:
            owner = execution.get('evaluation_owner')
            if owner is not None:
                owner.register_capture(execution['evaluation_grant_ref'], 'execution_preparation', execution['preparation_ref'])
            response = await _exchange(runner, context, 'prepare_attempt_resources',
                {'preparation_ref': copy.deepcopy(execution['preparation_ref'])})
            require(type(response) is dict and set(response) == {'preflight_ref'}, 'Malformed exact native preflight response')
            preflight_ref = response['preflight_ref']
            preflight = _receipt(runner.store, preflight_ref, 'scientific-attempt-preflight')
            require(preflight['preparation_ref'] == execution['preparation_ref'], 'Native preflight belongs to another preparation')
            require(runner.store.record_kind(preflight['science_runtime_ref']) == 'science-runtime',
                'Original scientific runtime kind differs')
            runtime = runner.store.read_record(preflight['science_runtime_ref'])
            from .science_runtime import decode_science_runtime_record
            decode_science_runtime_record(runtime)
            execution['preflight_ref'] = copy.deepcopy(preflight_ref)
            owner = execution.get('evaluation_owner')
            if owner is not None:
                owner.register_capture(execution['evaluation_grant_ref'], 'execution_preflight', preflight_ref)
            response = await _exchange(runner, context, 'activate_attempt_resources',
                {'preparation_ref': copy.deepcopy(execution['preparation_ref']), 'preflight_ref': copy.deepcopy(preflight_ref)})
            require(type(response) is dict and set(response) == {'activation_ref'}, 'Malformed exact native activation response')
            activation_ref = response['activation_ref']
            activation = _receipt(runner.store, activation_ref, 'scientific-attempt-activation')
            require(activation['preflight_ref'] == preflight_ref
                and activation['broker_instance_id'] == preflight['broker_instance_id']
                and activation['recorded_unix_ns'] >= preflight['recorded_unix_ns'],
                'Native activation does not join the exact original preflight/broker')
            execution['activation_ref'] = copy.deepcopy(activation_ref)
            if owner is not None:
                owner.register_capture(execution['evaluation_grant_ref'], 'execution_activation', activation_ref)
        payload = binding(execution, context.execution_id)
        owner = execution.get('evaluation_owner')
        check = lambda: current(runner, payload)
        context._bind_active_capabilities()
        if owner is not None:
            timing = owner._commit_prepared_start(execution, check)
        else:
            timing = runner.store.start_prepared_attempt(execution['contract_ref'], execution['contract'],
                execution['preparation_ref'], check, dispatch=dispatch)
        execution.update(phase='active', actual_started_at=timing['started_at'],
            actual_started_monotonic_s=timing['started_monotonic_s'])
        if runner.evidence is not None and owner is None:
            try:
                runner.evidence.capture_invocation_start(execution['contract_ref'], execution['contract'])
            except Exception as error:
                runner.evidence.missing(execution['contract']['run_id'], 'invocation-start:' + context.execution_id,
                    'Optional original-byte file copy failed: ' + type(error).__name__)
        return context
    except BaseException:
        # No late packet or record-only lookup may reopen this invocation.
        execution.update(phase='start_failed', closed=True)
        if execution.get('evaluation_owner') is None:
            runner.store.finish_attempt(execution['contract'], 'interrupted')
        raise
