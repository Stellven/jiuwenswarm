"""Actual candidate measurements without an acceptance or dispatch authority.

Only installed protected resource adapters construct a context. The worker
receives its capability object; private store/observations remain host-owned.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
import inspect
import json
import math
import time
import uuid

from .checks import CheckContext
from .contracts import ResearchError, contract_schema, validate
from .gate import assemble_assessment, zip_projection
from .runner import ProducedArtifact
from .state import json_bytes, utc_now


def require(condition, message, code='measurement_binding'):
    if not condition:
        raise ResearchError(code, message)


def _same_contract(produced, expected):
    if produced in (None, expected):
        return True
    try:
        return contract_schema(produced) == contract_schema(expected)
    except ResearchError:
        return False


def _replay_media(store,ref,contract_id):
    # Blob metadata is first-write and cannot identify the media of a later
    # captured output with identical bytes. The closed output type owns this
    # projection; actual ZIP/report structure remains independently checked.
    for known,media in [('poc-artifact-bundle','application/zip'),('research-report','text/markdown')]:
        if _same_contract(known,contract_id):return media
    return store.artifact_metadata(ref)['media_type']


def ordered_replay_outputs(refs,original_order):
    """JSON object key order cannot replace an original observation's array."""
    require(isinstance(refs,dict) and isinstance(original_order,list),'Invalid original replay inventory')
    remaining=list(refs.items());ordered={}
    for ref in original_order:
        matches=[(i,name) for i,(name,value) in enumerate(remaining) if value==ref]
        require(bool(matches),'Replay changed its original captured output inventory')
        index,name=matches[0];ordered[name]=remaining.pop(index)[1]
    require(not remaining,'Replay added an uncaptured output')
    return ordered


@dataclass(frozen=True)
class TrialMeasurement:
    accepted: bool
    status: str
    output_refs: dict
    deterministic_ref: dict
    observation_ref: dict
    assessment_refs: tuple
    verifier_check_refs: tuple
    observation_refs: tuple
    trace_refs: tuple
    failure: str | None
    measurement_ref: dict


def _plan(store, ref, contract_ref):
    kind = store.record_kind(ref)
    require(kind in {'bound-check-plan', 'isolated-evaluation-check-plan'}, 'No protected checking-plan capture')
    plan = store.read_record(ref, contract_id='bound-check-plan' if kind == 'bound-check-plan' else None)
    require(plan.get('contract_ref') == contract_ref, 'Checks belong to a different subject')
    mandatory = plan.get('mandatory_deterministic')
    require(isinstance(mandatory, list) and bool(mandatory) and all(isinstance(k, str) and k for k in mandatory)
            and len(mandatory) == len(set(mandatory)), 'Mandatory check coverage must be explicit and unique')
    require(isinstance(plan.get('mandatory_semantic'), list) and isinstance(plan.get('runner_refs'), list)
            and isinstance(plan.get('profile_ref'), dict), 'Incomplete protected checking plan')
    for source in [plan['profile_ref'], *plan['runner_refs']]:
        store.read_blob(source)
    return plan


def all_mandatory_pass(plan, results):
    ids = [row.get('check_id') for row in results]
    return (len(ids) == len(set(ids)) and set(plan['mandatory_deterministic']).issubset(ids)
            and all(row['outcome'] == 'PASS' for row in results if row['check_id'] in plan['mandatory_deterministic']))


async def _within(value, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        if inspect.iscoroutine(value):
            value.close()
        raise ResearchError('budget_exhausted', 'Actual measurement deadline exhausted')
    if inspect.isawaitable(value):
        try:
            value = await asyncio.wait_for(value, timeout=remaining)
        except TimeoutError as error:
            raise ResearchError('budget_exhausted', 'Actual measurement deadline exhausted') from error
    require(time.monotonic() < deadline, 'Actual measurement deadline exhausted', 'budget_exhausted')
    return value


def _decode(store, specs, produced, outputs, refs, *, contract_ref, replay=False,private_capture=None):
    require(isinstance(produced, dict), 'Carrier must return captured named artifacts', 'output_invalid')
    require(not (set(produced) - set(specs)) and all(not s['required'] or name in produced for name, s in specs.items()),
            'Output ports differ from the fixed subject', 'output_invalid')
    for port, item in produced.items():
        require(isinstance(item, ProducedArtifact), 'Uncaptured carrier output', 'output_invalid')
        require(_same_contract(item.contract_id, specs[port]['contract_id']), 'Carrier changed the output contract', 'output_invalid')
        raw = item.data if isinstance(item.data, bytes) else item.data.encode('utf-8') if isinstance(item.data, str) else json_bytes(item.data)
        ref = store.put_blob(raw, media_type=item.media_type)
        if item.ref is not None:
            require(store.read_blob(item.ref) == raw and (replay or item.ref == ref), 'Output Ref differs from captured bytes', 'integrity_fault')
            ref = copy.deepcopy(item.ref)
        # Publish capture before parsing so a malformed/partial output remains
        # attributable evidence rather than disappearing with the exception.
        store.append_record('measurement-captured-output', {'id': 'measurement-output:' + uuid.uuid4().hex,
            'contract_ref': contract_ref, 'output_port': port, 'artifact_ref': ref,
            'contract_id': specs[port]['contract_id'], 'media_type': item.media_type})
        refs[port] = ref
        if private_capture is not None:private_capture(ref)
        if item.media_type in {'application/zip', 'text/markdown'}:
            outputs[port] = raw
        else:
            try:
                outputs[port] = json.loads(raw.decode('utf-8'))
            except (UnicodeError, ValueError) as error:
                raise ResearchError('output_invalid', 'Captured output is not declared JSON') from error
            validate(specs[port]['contract_id'], outputs[port])
    return outputs, refs


def _review_refs(store, reply, *, output_ref, port, check_plan_ref, contract_ref, plan, zip_output,
                 declaration_ref, deterministic_ref, observation_ref):
    expected = {'assessment_ref', 'verifier_check_ref', 'observation_refs', 'trace_refs'}
    require(isinstance(reply, dict) and set(reply) == expected, 'Reviewer must return actual captured evidence')
    assessment_ref, checked_ref = reply['assessment_ref'], reply['verifier_check_ref']
    require(store.record_kind(assessment_ref) == 'verifier-assessment', 'No independently captured assessment')
    assessment = store.read_record(assessment_ref, contract_id='verifier-assessment')
    manifest = store.read_record(assessment['review_context_ref'], contract_id='review-context')
    require(manifest['contract_ref'] == contract_ref and manifest['check_plan_ref'] == check_plan_ref
            and manifest['subject_ref'] == output_ref and manifest['deterministic_result_ref'] == deterministic_ref
            and observation_ref in manifest['observations'], 'Review context differs from actual subject')
    if assessment['subject_ref'] != output_ref:
        projected = zip_projection(store.read_blob(output_ref)) if zip_output else None
        require(projected is not None and store.read_blob(assessment['subject_ref']) == projected,
                'Review assessed other bytes')
    profile = store.read_record(plan['profile_ref'], contract_id='checking-profile')
    criteria = [c for c in profile['criteria'] if c['target_port'] in (None, port)]
    body = {key: assessment[key] for key in ('uncertainties', 'limitations', 'required_correction')}
    body['findings'] = [{key: finding[key] for key in ('criterion_id', 'outcome', 'reason')} for finding in assessment['findings']]
    require(declaration_ref is not None and assemble_assessment(body, criteria, declaration_ref,
            assessment['subject_ref'], assessment['review_context_ref']) == assessment,
            'Assessment does not follow the exact pinned profile')
    require(store.record_kind(checked_ref) == 'deterministic-check-result', 'No independent reviewer mechanical checks')
    checked = store.read_record(checked_ref, contract_id='deterministic-check-result')
    checked_plan = store.read_record(checked['check_plan_ref'])
    mandatory = checked_plan.get('mandatory_deterministic')
    require(isinstance(mandatory, list) and bool(mandatory) and len(mandatory) == len(set(mandatory))
            and checked['subject_ref'] == assessment_ref and all_mandatory_pass(checked_plan, checked['results']),
            'Reviewer mechanical checks failed or cover another assessment')
    require(isinstance(reply['observation_refs'], (list, tuple)) and bool(reply['observation_refs'])
            and isinstance(reply['trace_refs'], (list, tuple)), 'Actual independent reviewer observation is missing')
    for ref in [*reply['observation_refs'], *reply['trace_refs']]:
        store.read_blob(ref)
    require(any(store.read_record(ref).get('contract_ref') == checked_plan['contract_ref']
                and assessment_ref in store.read_record(ref).get('output_refs', [])
                for ref in reply['observation_refs']), 'Reviewer observation does not join the checked assessment')
    return assessment_ref, checked_ref, tuple(reply['observation_refs']), tuple(reply['trace_refs'])


async def measure_trial(private_context, handler, inputs, output_specs, check_plan_ref, bundle_id, review_callback=None):
    """Measure one installed carrier or frozen replay, always accepted:false.

    A handler of None is permitted only for a protected frozen replay context.
    The resource owner must independently authorize and contain actual effects.
    """
    ctx = private_context
    from .evaluation_authority import EvaluationMeasurementContext
    private=type(ctx) is EvaluationMeasurementContext
    if private:
        actual=(ctx.runner.resolve_evaluation_owner(execution_id=ctx.grant['execution_id']) if ctx.grant is not None
            else ctx.runner.resolve_evaluation_owner(run_id=ctx.scope['private_run_id']))
        require(actual is ctx.owner,
                'Unregistered private measurement context')
    store, contract, contract_ref, deadline = ctx.store, ctx.contract, ctx.contract_ref, ctx.deadline_monotonic_s
    require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline > time.monotonic(),
            'An unexpired actual owner deadline is required', 'budget_exhausted')
    store.read_blob(contract_ref)
    plan = ctx.private_plan(check_plan_ref) if private else _plan(store, check_plan_ref, contract_ref)
    specs = {s['name']: copy.deepcopy(s) for s in output_specs}
    require(len(specs) == len(output_specs) and bool(specs) and all(type(s.get('required')) is bool
            and isinstance(s.get('contract_id'), str) for s in specs.values()), 'Invalid fixed output ports')
    await _within(ctx.require_checks(), deadline)
    began, started = time.monotonic(), utc_now()
    outputs, output_refs, failure, cancelled = {}, {}, None, False
    outcome, status = 'success', 'completed'
    assessments, verifier_checks, reviewer_observations, traces = [], [], [], []
    try:
        if handler is None:
            frozen = ctx.replay_output_refs
            require(isinstance(frozen, dict) and bool(frozen), 'Replay has no frozen original output')
            original_order=getattr(ctx,'replay_output_order',None)
            if original_order is not None:frozen=ordered_replay_outputs(frozen,original_order)
            produced = {name: ProducedArtifact(store.read_blob(ref), contract_id=specs[name]['contract_id'],
                        media_type=_replay_media(store,ref,specs[name]['contract_id']), ref=ref) for name, ref in frozen.items()}
        else:
            call = handler.execute if hasattr(handler, 'execute') else handler
            produced = await _within(call(ctx.worker_context, inputs), deadline)
        _decode(store, specs, produced, outputs, output_refs, contract_ref=contract_ref, replay=handler is None,
                private_capture=ctx.capture_output if private else None)
        await _within(ctx.require_checks(), deadline)
    except asyncio.CancelledError:
        failure, cancelled, outcome, status = 'cancelled', True, 'interrupted', 'interrupted'
    except Exception as error:
        failure = getattr(error, 'code', type(error).__name__)
        outcome = 'budget_exhausted' if failure == 'budget_exhausted' else 'failed'
        status = 'blocked' if failure in {'budget_exhausted', 'model_unavailable', 'entry_point_unavailable'} else 'failed'
    if failure:
        try:
            contained = ctx.contain(failure)
            if inspect.isawaitable(contained):
                await contained
        except BaseException:
            failure = 'containment_uncertain'
            status = 'interrupted' if cancelled else 'blocked'
    try:
        observation_ref = ctx.capture_observation(output_refs=output_refs, started_at=started,
            elapsed_s=time.monotonic() - began, outcome=outcome, failure=failure)
        if inspect.isawaitable(observation_ref):
            observation_ref = await observation_ref
    except Exception as error:
        try:
            store.append_record('measurement-audit-failure', {'id': 'measurement-audit:' + uuid.uuid4().hex,
                'contract_ref': contract_ref, 'output_refs': output_refs, 'reason': type(error).__name__,
                'status': status, 'accepted': False, 'recorded_at': utc_now()})
        finally:
            if cancelled:
                raise asyncio.CancelledError from error
        raise ResearchError('audit_unavailable', 'Actual owner observation could not be captured') from error
    observation = store.read_record(observation_ref)
    require(observation.get('contract_ref') == contract_ref and observation.get('output_refs') == list(output_refs.values()),
            'Owner observation does not name actual captured subject bytes', 'integrity_fault')
    if failure:
        results = [{'check_id': key, 'outcome': 'FAIL', 'reason': failure, 'evidence_refs': [observation_ref]}
                   for key in plan['mandatory_deterministic']]
    else:
        try:
            host = await _within(ctx.host_results(observation_ref=observation_ref, output_refs=output_refs, outputs=outputs), deadline)
            check_context = CheckContext(contract, store, inputs, outputs, output_refs, observation, tuple(host))
            results = await _within(ctx.check_registry.run(plan, check_context, bundle_id=bundle_id), deadline)
        except asyncio.CancelledError:
            failure, cancelled, status = 'cancelled', True, 'interrupted'
            results = [{'check_id': key, 'outcome': 'FAIL', 'reason': failure, 'evidence_refs': [observation_ref]}
                       for key in plan['mandatory_deterministic']]
        except Exception as error:
            failure = getattr(error, 'code', type(error).__name__)
            status = 'blocked' if failure == 'budget_exhausted' else 'failed'
            results = [{'check_id': key, 'outcome': 'FAIL', 'reason': failure, 'evidence_refs': [observation_ref]}
                       for key in plan['mandatory_deterministic']]
    subjects = list(output_refs.values()) or [observation_ref]
    deterministic = {'schema_version': '1.0.0', 'subject_ref': subjects[0], 'check_plan_ref': check_plan_ref, 'results': results}
    if len(subjects) > 1:
        deterministic['subject_refs'] = subjects
    deterministic_ref = (ctx.capture_record('deterministic-check-result',deterministic) if private else
        store.put_record('deterministic-check-result', deterministic,record_id='measurement-checks:' + uuid.uuid4().hex, scope=contract))
    if not failure and not all_mandatory_pass(plan, results):
        failure, status = 'deterministic_check_failed', 'failed'
    if not failure:
        # Match the ordinary producing runner: an explicit blocking uncertainty
        # is a halt, not permission for a consistent-but-unusable artifact to advance.
        for value in outputs.values():
            if isinstance(value,dict) and (value.get('readiness',{}).get('status')=='needs_clarification'
                    or any(item.get('blocking') for item in value.get('uncertainties',[]))
                    or any(item.get('blocking') for item in value.get('unresolved_items',[]))):
                failure,status='blocking_uncertainty','blocked'
                break
    if not failure and review_callback is not None:
        try:
            selected=getattr(ctx,'review_ports',None)
            if selected is not None:
                require(isinstance(selected,(list,tuple)) and bool(selected) and len(selected)==len(set(selected))
                        and set(selected)<=set(output_refs),'Protected replay selected unknown or duplicate review ports')
            for port, ref in output_refs.items():
                if selected is not None and port not in selected:continue
                reply = await _within(review_callback(port, ref, deterministic_ref, observation_ref), deadline)
                if private:
                    assessment,checked,observations,trace=ctx.validate_review(reply,output_ref=ref,port=port,
                        deterministic_ref=deterministic_ref,observation_ref=observation_ref)
                else:
                    assessment, checked, observations, trace = _review_refs(store, reply, output_ref=ref, port=port,
                        check_plan_ref=check_plan_ref, contract_ref=contract_ref, plan=plan,
                        zip_output=specs[port]['contract_id'] == 'poc-artifact-bundle',
                        declaration_ref=contract.get('declaration_ref') or next(iter(contract.get('bindings', [])), {}).get('declaration_ref'),
                        deterministic_ref=deterministic_ref, observation_ref=observation_ref)
                assessments.append(assessment);verifier_checks.append(checked)
                reviewer_observations.extend(observations);traces.extend(trace)
        except asyncio.CancelledError:
            failure, cancelled, status = 'cancelled', True, 'interrupted'
        except Exception as error:
            failure, status = getattr(error, 'code', type(error).__name__), 'failed'
    # An actual reviewer may fail after its governed call was captured. The
    # installed owner retains that observation even when review() cannot return
    # an assessment; losing it would hide real failed model usage.
    for ref in getattr(ctx,'review_observation_refs',()):
        if private:
            require(store.record_kind(ref)=='evaluation-invocation-observation'
                and any(e['capture_ref']==ref for e in ctx.owner.captures(ctx.scope['request_ref'],'observation')),
                'Private reviewer failure observation is not request-owned')
            observed=store.read_record(ref,contract_id='invocation-observation')
            reviewer=store.read_record(observed['contract_ref'])
            require(store.record_kind(observed['contract_ref'])=='evaluation-subnode-context'
                and reviewer['request_ref']==ctx.scope['request_ref'] and reviewer['role']=='verifier',
                'Private failure observation has another reviewer')
            if ref not in reviewer_observations:reviewer_observations.append(ref)
            for trace in observed['trace_refs']:
                store.read_blob(trace)
                if trace not in traces:traces.append(trace)
            continue
        require(store.record_kind(ref)=='invocation-observation','Reviewer failure evidence is not an actual observation')
        observed=store.read_record(ref,contract_id='invocation-observation')
        reviewer=store.read_record(observed['contract_ref'],contract_id='subnode-execution-contract')
        template=store.read_record(reviewer['template_ref'])
        require(reviewer['node_contract_ref']==contract['node_contract_ref'] and reviewer['bindings'][0]['role']=='verifier'
                and template.get('subject_subnode_id')==contract['subnode_id'], 'Reviewer failure observation belongs to another subject')
        if ref not in reviewer_observations:reviewer_observations.append(ref)
        for trace in observed['trace_refs']:
            store.read_blob(trace)
            if trace not in traces:traces.append(trace)
    if cancelled or failure == 'budget_exhausted':
        # This also covers cancellation while host checks or independent review
        # were active, after the initial worker observation was captured.
        if not ctx.store.read_record(observation_ref).get('failure_reason_code'):
            try:
                contained = ctx.contain('cancelled' if cancelled else failure)
                if inspect.isawaitable(contained):await contained
            except BaseException:
                failure = 'containment_uncertain'
    record = {'id': 'measurement:' + uuid.uuid4().hex, 'contract_ref': contract_ref, 'accepted': False,
        'status': status, 'output_refs': output_refs, 'deterministic_ref': deterministic_ref, 'observation_ref': observation_ref,
        'assessment_refs': assessments, 'verifier_check_refs': verifier_checks, 'observation_refs': reviewer_observations,
        'trace_refs': traces, 'failure': failure, 'elapsed_s': time.monotonic() - began, 'recorded_at': utc_now()}
    measurement_ref = ctx.capture_record('trial-measurement',record) if private else store.append_record('trial-measurement', record)
    if cancelled:
        raise asyncio.CancelledError
    return TrialMeasurement(False, status, copy.deepcopy(output_refs), deterministic_ref, observation_ref,
        tuple(assessments), tuple(verifier_checks), tuple(reviewer_observations), tuple(traces), failure, measurement_ref)
