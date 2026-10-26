"""Read-only IF016 custody, independent of executable evaluation resources.

Only the immutable request ledger and its typed journal provide ownership.
References found in arbitrary JSON, a time window or the complete asset/store
inventory never extend disclosure authority.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import sqlite3
import stat
import zipfile

from .contracts import ResearchError, validate
from .evaluation_projection import private_record, require
from .inspection import safe_named_path
from .state import json_bytes


def validate_cleanup_response(store, request_ref, scope_ref, result, measurement_refs, *,
                              state, failure, containment_ref, cancel_id, captures, events):
    """Validate non-authorizing failed data against its original owned capture."""
    require(cancel_id is not None and state in {'failed', 'outcome_unknown'}
        and isinstance(result, dict) and result.get('invalid_for_product') is True
        and len(measurement_refs) == 1, 'Invalid failed-response terminal', 'integrity_fault')
    pin = measurement_refs[0]
    require(('measurement', encoded(pin)) in captures
        and store.record_kind(pin) == 'evaluation-trial-measurement',
        'Failed response has no original owned measurement', 'integrity_fault')
    measured = store.read_record(pin)
    fields = {'id','contract_ref','accepted','status','output_refs','deterministic_ref','observation_ref',
        'assessment_refs','verifier_check_refs','observation_refs','trace_refs','failure','elapsed_s','recorded_at'}
    require(set(measured) == fields and measured['accepted'] is False
        and measured['status'] in {'failed', 'blocked'} and isinstance(measured['failure'], str)
        and bool(measured['failure']) and failure == measured['failure'] == result.get('reason'),
        'Response reason/status differs from actual failed measurement', 'integrity_fault')
    scope = private_record(store, scope_ref, 'evaluation-scope')
    request = private_record(store, request_ref, 'evaluation-request')
    require(scope['request_ref'] == request_ref, 'Failed measurement scope differs', 'integrity_fault')
    require(store.record_kind(scope['source_contract_ref']) == 'subnode-execution-contract'
        and store.record_kind(scope['source_check_plan_ref']) == 'bound-check-plan',
        'Failed measurement original source kinds differ', 'integrity_fault')
    source = store.read_record(scope['source_contract_ref'], contract_id='subnode-execution-contract')
    plan = store.read_record(scope['source_check_plan_ref'], contract_id='bound-check-plan')
    require(plan['contract_ref'] == scope['source_contract_ref']
        and plan['node_contract_ref'] == source['node_contract_ref'],
        'Failed measurement original plan targets another source', 'integrity_fault')
    observation_ref = measured['observation_ref']
    if request['entry_point'] == 'E3':
        require(('observation', encoded(observation_ref)) in captures
            and store.record_kind(observation_ref) == 'evaluation-invocation-observation',
            'Failed response has no owned private observation', 'integrity_fault')
    else:
        require(observation_ref == scope['source_observation_ref']
            and store.record_kind(observation_ref) == 'invocation-observation',
            'Failed replay changed original observation', 'integrity_fault')
    observed = store.read_record(observation_ref, contract_id='invocation-observation')
    require(observed['contract_ref'] == measured['contract_ref'],
        'Failed measurement changed original observation contract', 'integrity_fault')
    if request['entry_point'] == 'E3':
        require(sorted(encoded(ref) for ref in observed['output_refs'])
                == sorted(encoded(ref) for ref in measured['output_refs'].values())
            and observed['failure_reason_code'] == measured['failure'],
            'Failed worker changed original output/failure observation', 'integrity_fault')
    else:
        from .measurement import ordered_replay_outputs
        binding_ref = scope['source_binding_ref']
        require(('source_binding', encoded(binding_ref)) in captures
            and store.record_kind(binding_ref) == 'evaluation-case-binding',
            'Failed replay has no original owned source binding', 'integrity_fault')
        binding = store.read_record(binding_ref)
        fields = {'id', 'contract_ref', 'check_plan_ref', 'output_refs',
            'original_observation_ref', 'verifier_cc_id', 'host_records'}
        require(isinstance(binding, dict) and isinstance(binding.get('output_refs'), dict)
            and isinstance(measured['output_refs'], dict) and 0 < len(binding['output_refs']) <= 64
            and all(isinstance(port, str) and bool(port) for port in binding['output_refs']),
            'Failed replay original port inventory differs', 'integrity_fault')
        if binding.get('schema') == 'ai4r-node-replay-binding:2':
            require(set(binding) == fields | {'schema', 'selected_output_port'}
                and isinstance(binding['selected_output_port'], str) and bool(binding['selected_output_port'])
                and binding['selected_output_port'] in binding['output_refs'],
                'Failed replay selected-port binding differs', 'integrity_fault')
            selected = binding['selected_output_port']
        else:
            require(set(binding) == fields and len(binding['output_refs']) == 1,
                'Failed replay legacy source binding differs', 'integrity_fault')
            selected = next(iter(binding['output_refs']))
        require(binding['contract_ref'] == scope['source_contract_ref']
            and binding['check_plan_ref'] == scope['source_check_plan_ref']
            and binding['original_observation_ref'] == observation_ref
            and selected == scope['selected_output_port']
            and set(binding['output_refs']) <= {port['name'] for port in source['outputs']},
            'Failed replay binding changed its original source joins', 'integrity_fault')
        try:
            original_outputs = ordered_replay_outputs(binding['output_refs'], observed['output_refs'])
        except ResearchError as error:
            raise ResearchError('integrity_fault', 'Failed replay changed original output mapping') from error
        require(list(original_outputs.values()) == scope['source_output_refs'] == observed['output_refs']
            and all(original_outputs.get(port) == ref for port, ref in measured['output_refs'].items()),
            'Failed replay changed complete original output closure', 'integrity_fault')
    checked_ref = measured['deterministic_ref']
    require(('deterministic_result', encoded(checked_ref)) in captures
        and store.record_kind(checked_ref) == 'evaluation-deterministic-check-result',
        'Failed response lacks original private checks', 'integrity_fault')
    checked = store.read_record(checked_ref, contract_id='deterministic-check-result')
    basis = private_record(store, checked['check_plan_ref'], 'evaluation-checking-basis')
    worker = request['entry_point'] == 'E3'
    subject_refs = [ref for ref in observed['output_refs'] if ref in measured['output_refs'].values()]
    subject_refs = subject_refs or [observation_ref]
    require(checked['subject_ref'] == subject_refs[0]
        and checked.get('subject_refs', [checked['subject_ref']]) == subject_refs,
        'Failed checks target another original subject', 'integrity_fault')
    profile = store.read_record(plan['profile_ref'], contract_id='checking-profile')
    semantic = [] if worker else [row['criterion_id'] for row in profile['criteria']
        if row['blocking'] and row['target_port'] in (None, scope['selected_output_port'])]
    require(basis['request_ref'] == request_ref and basis['node_context_ref'] == scope['actual_node_ref']
        and basis['assignment_context_ref'] == (measured['contract_ref'] if worker else None)
        and basis['mode'] == ('worker_output' if worker else 'replay_subject')
        and basis['output_port'] == (None if worker else scope['selected_output_port'])
        and basis['source_contract_ref'] == scope['source_contract_ref']
        and basis['source_check_plan_ref'] == scope['source_check_plan_ref']
        and basis['source_template_ref'] == source['template_ref']
        and basis['input_refs'] == source['input_refs']
        and all(basis[key] == plan[key] for key in ('profile_ref', 'policy_ref', 'mandatory_deterministic', 'runner_refs'))
        and basis['mandatory_semantic'] == semantic,
        'Failed checks differ from the exact original assignment/checking basis', 'integrity_fault')
    measured_events = [event for event in events if event['kind'] == 'captured'
        and event['capture_kind'] == 'measurement' and event['capture_ref'] == pin]
    require(len(measured_events) == 1, 'Failed measurement has ambiguous publication', 'integrity_fault')
    causes = []
    for event in events:
        if (event['kind'] != 'captured' or event['capture_kind'] != 'failure'
            or event['sequence'] >= measured_events[0]['sequence']):
            continue
        cause_ref = event['capture_ref']
        require(store.record_kind(cause_ref) == 'evaluation-failure',
            'Failed measurement cause kind differs', 'integrity_fault')
        cause = store.read_record(cause_ref)
        require(set(cause) == {'id', 'reason', 'accepted', 'invalid_for_product'}
            and cause['accepted'] is False and cause['invalid_for_product'] is True
            and isinstance(cause['reason'], str) and bool(cause['reason']),
            'Failed measurement original cause differs', 'integrity_fault')
        grant_ref = event['assignment_grant_ref']
        if worker:
            if grant_ref is None:
                continue
            grant = private_record(store, grant_ref, 'evaluation-assignment-grant')
            if not (grant['request_ref'] == request_ref and grant['scope_ref'] == scope_ref
                and grant['contract_ref'] == measured['contract_ref'] and grant['role'] == 'worker'):
                continue
        elif grant_ref is not None:
            continue
        causes.append(cause)
    require(len(causes) == 1 and (state == 'outcome_unknown' or causes[0]['reason'] == failure),
        'Failed response lacks its exact original pre-containment cause', 'integrity_fault')
    require(type(result.get('duration_s')) in (int, float) and math.isfinite(result['duration_s'])
        and result['duration_s'] >= 0, 'Failed response has no actual finite duration', 'integrity_fault')
    if request['entry_point'] == 'E3':
        child = private_record(store, measured['contract_ref'], 'evaluation-subnode-context')
        require(child['request_ref'] == request_ref and child['role'] == 'worker'
            and child['node_contract_ref'] == scope['actual_node_ref']
            and child['source_subject_ref'] == scope['source_contract_ref']
            and child['source_template_ref'] == source['template_ref']
            and ('actual_contract', encoded(measured['contract_ref'])) in captures
            and result.get('status') == measured['status'] and result.get('output_refs') == measured['output_refs']
            and result.get('invocation_id') == observed['id']
            and result.get('check_results') == [{'check_id': row['check_id'], 'status': row['outcome']} for row in checked['results']]
            and result.get('tool_effects_observed') == (observed['effects'] or None),
            'Failed response differs from original worker evidence', 'integrity_fault')
    else:
        require(measured['contract_ref'] == scope['source_contract_ref']
            and result.get('advanced') is False and result.get('downstream_action') != 'started'
            and result.get('gate_decision', {}).get('action') == 'halt'
            and pin in result.get('evidence_refs', []),
            'Failed replay claims advancement or another measurement', 'integrity_fault')
    if state == 'outcome_unknown':
        require(failure == 'containment_uncertain' and containment_ref is None,
            'Unknown cleanup cannot claim actual containment', 'integrity_fault')
    else:
        require(containment_ref is not None and ('containment', encoded(containment_ref)) in captures
            and store.record_kind(containment_ref) == 'evaluation-containment',
            'Failed cleanup lacks actual containment', 'integrity_fault')
        receipt = store.read_record(containment_ref)
        require(receipt.get('request_ref') == request_ref and receipt.get('scope_ref') == scope_ref
            and receipt.get('cancel_id') == cancel_id and type(receipt.get('no_started_assignments')) is bool
            and isinstance(receipt.get('receipts'), list)
            and (receipt['no_started_assignments'] or receipt['receipts'])
            and all(isinstance(item, dict) and item.get('contained') is True
                and item.get('run_id') == scope['private_run_id'] and item.get('request_id') == cancel_id
                for item in receipt['receipts']), 'Failed cleanup containment joins differ', 'integrity_fault')
    return measured


# Transport safety ceilings, not quality/acceptance thresholds. Exceeding a
# ceiling refuses this export; it never silently truncates an original capture.
MAX_EXPORT_BYTES = 128 * 1024 * 1024
MAX_EXPORT_FILES = 4096
MAX_JOURNAL_EVENTS = 16384
PRIVATE_EVIDENCE = {
    'observation': ('evaluation-invocation-observation', 'invocation-observation'),
    'deterministic_result': ('evaluation-deterministic-check-result', 'deterministic-check-result'),
    'verifier_check': ('evaluation-deterministic-check-result', 'deterministic-check-result'),
    'review_context': ('evaluation-review-context', 'review-context'),
    'assessment': ('evaluation-verifier-assessment', 'verifier-assessment'),
    'measurement': ('evaluation-trial-measurement', None),
}
NATIVE_KINDS = {
    'prompt': {'model-call-input'}, 'route': {'route-record'},
    'model_claim': {'evaluation-call-claim'}, 'model_start': {'model-call-start'},
    'model_call': {'model-call'}, 'model_refusal': {'model-call-refused'},
    'tool_claim': {'evaluation-tool-claim'},
    'tool_observation': {'model-provider-observation', 'tool-observation'},
    'trace': {'native-governed-trace', 'native-governed-trace-event'},
}
START_CAPTURES = {
    'execution_preparation': ('invocation-preparation', 'urn:ai4r:private:invocation-preparation:1'),
    'execution_preflight': ('scientific-attempt-preflight', 'urn:ai4r:private:scientific-attempt-preflight:1'),
    'execution_activation': ('scientific-attempt-activation', 'urn:ai4r:private:scientific-attempt-activation:1'),
}


def encoded(value):
    return json_bytes(value).decode('utf-8')


def _model_endpoint_shape(endpoint):
    """Bound non-secret original endpoint metadata to the native finite shapes."""
    from urllib.parse import urlsplit
    require(isinstance(endpoint, dict), 'Original model endpoint is not metadata', 'integrity_fault')
    if endpoint.get('provider_id') == 'operator-local':
        require(set(endpoint) == {'provider_id','transport','gateway_id','binding_sha256','backend','model'}
            and endpoint['transport'] == 'authenticated-unix-rpc', 'Original local endpoint shape differs', 'integrity_fault')
        backend = endpoint['backend']; model = endpoint['model']
        codex = backend.get('kind') == 'host-codex-app-server'
        fields = {'kind','codex_sha256','account_fingerprint'} if codex else {'kind','target','base_url'}
        model_fields = {'id','name','model_name','revision','enabled','context_window','max_prompt_bytes','timeout_s'}
        model_fields |= {'reasoning_effort'} if codex else {'max_output_tokens','temperature','enable_thinking'}
        require(set(backend) == fields and set(model) == model_fields,
            'Original local endpoint contains unsupported private fields', 'integrity_fault')
        if not codex:
            parsed = urlsplit(backend['base_url'])
            require(backend['kind'] == 'ssh-loopback-openai' and parsed.scheme == 'http'
                and parsed.hostname in {'127.0.0.1','::1'} and parsed.path == '/v1'
                and not (parsed.username or parsed.password or parsed.query or parsed.fragment),
                'Original local endpoint contains private address credentials', 'integrity_fault')
    elif endpoint.get('provider_id') == 'chatgpt':
        require(set(endpoint) == {'provider_id','transport'}
            and endpoint['transport'] == 'packaged-app-server-subscription', 'Original subscription endpoint shape differs', 'integrity_fault')
    else:
        require(set(endpoint) == {'provider_id','base_url','models','credential_env_var','timeout_s','enabled'}
            and endpoint['credential_env_var'] == 'AI4R_SELECTED_API_KEY'
            and isinstance(endpoint['models'], list) and all(set(m) == {'model_id','provider_model_name'} for m in endpoint['models']),
            'Original API endpoint contains unsupported private fields', 'integrity_fault')
        parsed = urlsplit(endpoint['base_url'])
        require(parsed.scheme in {'http','https'} and parsed.hostname
            and not (parsed.username or parsed.password or parsed.query or parsed.fragment),
            'Original API endpoint contains private address credentials', 'integrity_fault')


def validate_preparation_binding(store, value, grant_ref, grant):
    """Original Binding3 and remaining child allowance, without a live claim."""
    child = private_record(store, grant['contract_ref'], 'evaluation-subnode-context')
    require(child['request_ref'] == grant['request_ref'] and len(child['bindings']) == 1,
        'Scientific preparation has another private child', 'integrity_fault')
    allowance = min(grant['limits']['time_s'], child['subnode_limits']['time_s'],
        child['bindings'][0]['limits']['time_s'])
    require(value['assignment_grant_ref'] == grant_ref
        and all(value[key] == grant[key] for key in ('contract_ref', 'execution_id', 'invocation_id'))
        and grant['started_unix_ns'] <= value['recorded_unix_ns'] < value['deadline_unix_ns'] <= grant['deadline_unix_ns']
        and value['deadline_unix_ns'] - value['recorded_unix_ns'] <= int(allowance * 1_000_000_000),
        'Scientific preparation differs from original binding/remaining child allowance', 'integrity_fault')


def validate_start_capture_order(store, events):
    """Original event2 ordering only; no current live owner/lease inference."""
    captured, started = {}, set()
    for _, event in events:
        grant_ref = event['assignment_grant_ref']
        if grant_ref is None:
            require(not (event['kind'] == 'captured' and event['capture_kind'] in START_CAPTURES),
                'Scientific start capture has no original assignment', 'integrity_fault')
            continue
        key = encoded(grant_ref)
        slots = captured.setdefault(key, {})
        if event['kind'] == 'captured' and event['capture_kind'] in START_CAPTURES:
            kind = event['capture_kind']
            require(key not in started and kind not in slots,
                'Scientific start receipt is duplicate or captured after start', 'integrity_fault')
            indexed, schema = START_CAPTURES[kind]
            require(store.record_kind(event['capture_ref']) == indexed,
                'Scientific start receipt indexed kind differs', 'integrity_fault')
            value = store.read_record(event['capture_ref'])
            validate(schema, value)
            slots[kind] = (event['capture_ref'], value)
        if event['kind'] != 'assignment_started':
            continue
        require(key not in started, 'Duplicate private assignment start', 'integrity_fault')
        if event['schema'] == 'ai4r-evaluation-event:2' or slots:
            require(set(slots) == set(START_CAPTURES),
                'Scientific assignment starts before all original receipts', 'integrity_fault')
            preparation_ref, preparation = slots['execution_preparation']
            preflight_ref, preflight = slots['execution_preflight']
            _, activation = slots['execution_activation']
            grant = private_record(store, grant_ref, 'evaluation-assignment-grant')
            validate_preparation_binding(store, preparation, grant_ref, grant)
            require(preflight['preparation_ref'] == preparation_ref and activation['preflight_ref'] == preflight_ref
                and activation['broker_instance_id'] == preflight['broker_instance_id']
                and preparation['recorded_unix_ns'] <= preflight['recorded_unix_ns']
                <= activation['recorded_unix_ns'] <= event['recorded_unix_ns'] < preparation['deadline_unix_ns'],
                'Scientific start differs from its exact original receipt sequence', 'integrity_fault')
        started.add(key)


def _strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'Duplicate captured JSON key', 'integrity_fault')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    except (ValueError, UnicodeError) as error:
        raise ResearchError('integrity_fault', 'Captured strict JSON is unavailable') from error


class EvaluationReader:
    """Finite authenticated request history; construction starts no effects."""

    def __init__(self, store, *, runtime_ref, operator=None):
        self.store = store
        self.runtime_ref = copy.deepcopy(runtime_ref)
        self.runtime = private_record(store, runtime_ref, 'evaluation-runtime')
        self.operator = operator

    def _owned(self, principal, request_id):
        runtime = private_record(self.store, self.runtime_ref, 'evaluation-runtime')
        require(runtime == self.runtime, 'Historical runtime changed', 'integrity_fault')
        principal.require('evaluation_profile', runtime['workspace_id'])
        require(principal.account_id == runtime['account_id'], 'Request is unavailable', 'not_found')
        require(isinstance(request_id, str) and request_id, 'Request is unavailable', 'not_found')
        identity = encoded([runtime[k] for k in ('account_id', 'workspace_id', 'campaign_id',
            'profile_ref', 'configuration_ref')] + [request_id])
        try:
            with self.store._lock:
                row = self.store.connection.execute(
                    'SELECT * FROM evaluation_requests WHERE identity=? AND runtime=?',
                    (identity, encoded(self.runtime_ref))).fetchone()
                row = dict(row) if row else None
        except sqlite3.Error as error:
            raise ResearchError('not_found', 'Request is unavailable') from error
        require(row is not None and row['request_ref'] is not None,
            'Request is unavailable', 'not_found')
        return self._owned_row(row, request_id)


    def _owned_row(self, row, request_id):
        """Pure original ledger validation; callers separately own access."""
        runtime = private_record(self.store, self.runtime_ref, 'evaluation-runtime')
        require(runtime == self.runtime and isinstance(request_id, str) and bool(request_id),
            'Historical runtime/request identity changed', 'integrity_fault')
        identity = encoded([runtime[k] for k in ('account_id', 'workspace_id', 'campaign_id',
            'profile_ref', 'configuration_ref')] + [request_id])
        require(row is not None and row['request_ref'] is not None
            and row['runtime'] == encoded(self.runtime_ref) and row['identity'] == identity,
            'Historical row belongs to another original runtime/request', 'integrity_fault')
        request_ref = _strict_json(row['request_ref'].encode('utf-8'))
        request = private_record(self.store, request_ref, 'evaluation-request')
        require(request['runtime_ref'] == self.runtime_ref and request['request_id'] == request_id
            and request['slot_id'] == row['slot'] and request['fingerprint'] == row['fingerprint']
            and request['started_unix_ns'] == row['started_ns']
            and request['deadline_unix_ns'] == row['deadline_ns'],
            'Historical request differs from its durable claim', 'integrity_fault')
        slots = [s for s in runtime['slots'] if s['slot_id'] == request['slot_id']]
        require(len(slots) == 1 and slots[0]['request_id'] == request_id
            and slots[0]['entry_point'] == request['entry_point']
            and slots[0]['case_id'] == request['case_id']
            and slots[0]['request_sha256'] == request['fingerprint']
            and slots[0]['limits'] == request['limits'],
            'Historical request is outside its approved original slot', 'integrity_fault')
        original = _strict_json(self.store.read_blob(request['original_request_ref']))
        normalized = _strict_json(self.store.read_blob(request['normalized_request_ref']))
        expected = copy.deepcopy(original)
        if request['entry_point'] == 'E2':
            expected.setdefault('host_records', [])
        require(expected == normalized and hashlib.sha256(
            json_bytes([request['entry_point'], normalized])).hexdigest() == request['fingerprint'],
            'Historical original/normalized request differs', 'integrity_fault')
        require(normalized.get('request_id') == request_id and normalized.get('case_id') == request['case_id']
            and normalized.get('campaign_id') == runtime['campaign_id'],
            'Historical request source scope differs', 'integrity_fault')
        require(self.store.record_kind(runtime['profile_ref']) == 'evaluation-profile',
            'Historical profile kind differs', 'integrity_fault')
        profile = self.store.read_record(runtime['profile_ref'], contract_id='evaluation-profile')
        require(normalized.get('evaluation_profile_id') == profile['profile_id'],
            'Historical profile identity differs', 'integrity_fault')
        require(self.store.record_kind(runtime['assets_ref']) == 'evaluation-assets',
            'Historical asset kind differs', 'integrity_fault')
        assets = self.store.read_record(runtime['assets_ref'])
        require(all(assets[k] == runtime[k] for k in ('account_id', 'workspace_id', 'campaign_id',
            'profile_ref', 'configuration_ref')), 'Historical asset scope differs', 'integrity_fault')
        scope = None
        scope_ref = _strict_json(row['scope_ref'].encode('utf-8')) if row['scope_ref'] else None
        if scope_ref:
            scope = private_record(self.store, scope_ref, 'evaluation-scope')
            require(scope['request_ref'] == request_ref
                and scope['started_unix_ns'] == request['started_unix_ns']
                and scope['deadline_unix_ns'] == request['deadline_unix_ns'],
                'Historical scope belongs to another request', 'integrity_fault')
        return runtime, profile, request_ref, request, row, scope_ref, scope

    def request_scope(self, principal, request_id):
        runtime, profile, *_ = self._owned(principal, request_id)
        return {**{k: copy.deepcopy(runtime[k]) for k in ('account_id', 'workspace_id', 'campaign_id',
            'profile_ref', 'configuration_ref', 'assets_ref')},
            'profile_id': profile['profile_id'], 'runtime_ref': copy.deepcopy(self.runtime_ref)}

    def _journal(self, request_ref, row, scope_ref):
        require(row['head_ref'] is not None, 'Historical journal is incomplete', 'integrity_fault')
        cursor = _strict_json(row['head_ref'].encode('utf-8'))
        ref, sequence, result, seen = cursor, row['sequence'], [], set()
        while ref is not None:
            key = encoded(ref)
            require(key not in seen and len(result) < MAX_JOURNAL_EVENTS,
                'Historical journal cycle or transfer bound', 'integrity_fault')
            seen.add(key)
            event = private_record(self.store, ref, 'evaluation-event')
            require(event['request_ref'] == request_ref and event['sequence'] == sequence
                and event['scope_ref'] in (None, scope_ref),
                'Historical journal ownership differs', 'integrity_fault')
            if event['assignment_grant_ref'] is not None:
                grant = private_record(self.store, event['assignment_grant_ref'], 'evaluation-assignment-grant')
                require(grant['request_ref'] == request_ref and grant['scope_ref'] == scope_ref,
                    'Historical assignment belongs to another request', 'integrity_fault')
            result.append((ref, event))
            ref, sequence = event['previous_event_ref'], sequence - 1
        require(sequence == -1 and result[-1][1]['kind'] == 'claimed',
            'Historical journal is incomplete', 'integrity_fault')
        ordered = list(reversed(result))
        validate_start_capture_order(self.store, ordered)
        return cursor, ordered

    def _terminal(self, request_ref, row, scope_ref, events):
        if not row['terminal_ref']:
            require(not any(e['kind'] == 'terminal' for _, e in events),
                'Unbound historical terminal', 'integrity_fault')
            return None
        terminal_ref = _strict_json(row['terminal_ref'].encode('utf-8'))
        terminal = private_record(self.store, terminal_ref, 'evaluation-terminal')
        matches = [e for _, e in events if e['kind'] == 'terminal' and e['capture_ref'] == terminal_ref]
        require(terminal['request_ref'] == request_ref and terminal['scope_ref'] == scope_ref
            and terminal['state'] == row['state'] and len(matches) == 1
            and matches[0]['previous_event_ref'] == terminal['through_event_ref'],
            'Historical terminal lacks its exact durable journal link', 'integrity_fault')
        captures = {(e['capture_kind'], encoded(e['capture_ref'])) for _, e in events
            if e['kind'] == 'captured'}
        for kind, ref in [('result', terminal['result_ref']), ('failure', terminal['failure_ref'])]:
            require(ref is None or (kind, encoded(ref)) in captures
                and self.store.record_kind(ref) == 'evaluation-' + kind,
                'Historical terminal promised unowned evidence', 'integrity_fault')
            if ref is not None:
                body = self.store.read_record(ref)
                require(body.get('accepted') is False and body.get('invalid_for_product') is True,
                    'Historical terminal evidence origin differs', 'integrity_fault')
        require(all(('measurement', encoded(ref)) in captures
            and self.store.record_kind(ref) == 'evaluation-trial-measurement'
            for ref in terminal['measurement_refs']),
            'Historical terminal measurement was not captured', 'integrity_fault')
        for ref in terminal['measurement_refs']:
            self.store.read_blob(ref)
        if terminal['containment_ref'] is not None:
            ref = terminal['containment_ref']
            require(('containment', encoded(ref)) in captures
                and self.store.record_kind(ref) == 'evaluation-containment',
                'Historical terminal containment was not captured', 'integrity_fault')
            receipt = self.store.read_record(ref)
            require(receipt.get('request_ref') == request_ref
                and receipt.get('cancel_id') == row['cancel_id'] and row['cancel_id'] is not None
                and receipt.get('scope_ref') == scope_ref,
                'Historical terminal containment identity differs', 'integrity_fault')
        if terminal['state'] == 'cancelled':
            require(row['cancel_id'] is not None and terminal['containment_ref'] is not None
                and terminal['result_ref'] is None,
                'Cancelled history lacks original containment', 'integrity_fault')
        cleanup_result = terminal['result_ref'] is not None and terminal['state'] in {'failed', 'outcome_unknown'}
        require(row['cancel_id'] is None or terminal['state'] in {'cancelled', 'outcome_unknown'} or cleanup_result,
            'Historical completion contradicts cancellation', 'integrity_fault')
        if cleanup_result:
            require(terminal['failure_ref'] is not None, 'Cleanup response lacks original failure', 'integrity_fault')
            validate_cleanup_response(self.store, request_ref, scope_ref,
                self.store.read_record(terminal['result_ref'])['result'], terminal['measurement_refs'],
                state=terminal['state'], failure=self.store.read_record(terminal['failure_ref'])['reason'],
                containment_ref=terminal['containment_ref'], cancel_id=row['cancel_id'], captures=captures,
                events=[event for _, event in events])
        if terminal['state'] == 'completed':
            require(terminal['result_ref'] is not None and terminal['measurement_refs'],
                'Completed history has no actual result/measurement', 'integrity_fault')
        return terminal

    def get(self, principal, request_id):
        _, _, ref, _, row, scope_ref, _ = self._owned(principal, request_id)
        _, events = self._journal(ref, row, scope_ref)
        terminal = self._terminal(ref, row, scope_ref, events)
        result, failure = None, None
        state = 'started'
        if terminal:
            state = {'cancelled': 'interrupted', 'outcome_unknown': 'interrupted'}.get(
                terminal['state'], terminal['state'])
            failure = terminal['failure_ref']
            if terminal['result_ref']:
                require(self.store.record_kind(terminal['result_ref']) == 'evaluation-result',
                    'Historical result kind differs', 'integrity_fault')
                result = self.store.read_record(terminal['result_ref'])['result']
        return {'request_id': request_id, 'status': state, 'result': result,
            'failure_ref': failure, 'invalid_for_product': True}

    def _kind(self, ref):
        try:
            return self.store.record_kind(ref)
        except ResearchError as error:
            if error.code != 'evidence_unavailable':
                raise
            return None

    def _capture(self, capture_kind, ref, request_ref, scope_ref, scope, grant_ref):
        raw = self.store.read_blob(ref)
        kind = self._kind(ref)
        # A protected journal link does not permit cross-authority private data.
        require(kind is None or not any(x in kind for x in ('calibration', 'isolated-', 'rsi-', 'credential')),
            'Foreign private evidence cannot enter evaluation history', 'integrity_fault')
        if capture_kind in PRIVATE_EVIDENCE:
            expected, contract_id = PRIVATE_EVIDENCE[capture_kind]
            require(kind == expected, 'Private evidence indexed kind differs', 'integrity_fault')
            value = self.store.read_record(ref, **({'contract_id': contract_id} if contract_id else {}))
            if capture_kind == 'measurement':
                require(value.get('accepted') is False, 'Measurement claimed acceptance', 'integrity_fault')
        elif capture_kind == 'actual_contract':
            require(kind in {'evaluation-node-context', 'evaluation-subnode-context'},
                'Canonical source cannot masquerade as a private context', 'integrity_fault')
            value = private_record(self.store, ref, kind)
            require(value['request_ref'] == request_ref, 'Private context is foreign', 'integrity_fault')
            require(scope is not None, 'Private context has no bound scope', 'integrity_fault')
            if kind == 'evaluation-node-context':
                require(ref == scope['actual_node_ref'] and grant_ref is None,
                    'Private parent is not the exact scope target', 'integrity_fault')
                source = self.store.read_record(scope['source_contract_ref'], contract_id='subnode-execution-contract')
                require(self.store.record_kind(source['node_contract_ref']) == 'node-execution-contract',
                    'Original source parent kind differs', 'integrity_fault')
                parent = self.store.read_record(source['node_contract_ref'], contract_id='node-execution-contract')
                require(value['source_contract_ref'] == scope['source_contract_ref']
                    and value['source_node_ref'] == source['node_contract_ref']
                    and value['source_template_ref'] == parent['template_ref']
                    and value['source_check_plan_ref'] == scope['source_check_plan_ref']
                    and value['source_binding_ref'] == scope['source_binding_ref']
                    and value['run_id'] == scope['private_run_id']
                    and all(value[k] == parent[k] for k in ('node_id', 'objective', 'requirement_ids', 'inputs',
                        'outputs', 'input_refs', 'required_outputs', 'evidence_obligations', 'subnodes',
                        'checking_profile_ref', 'policy_ref', 'configuration_ref')),
                    'Private parent differs from original source projection', 'integrity_fault')
            else:
                require(grant_ref is not None, 'Private child has no durable assignment', 'integrity_fault')
                grant = private_record(self.store, grant_ref, 'evaluation-assignment-grant')
                require(grant['contract_ref'] == ref and value['node_contract_ref'] == scope['actual_node_ref']
                    and value['source_subject_ref'] == scope['source_contract_ref']
                    and value['role'] == grant['role'] and value['output_port'] == grant['output_port'],
                    'Private child differs from its exact grant/parent', 'integrity_fault')
        elif capture_kind == 'check_plan':
            value = private_record(self.store, ref, 'evaluation-checking-basis')
            require(value['request_ref'] == request_ref and value['node_context_ref'] == scope['actual_node_ref'],
                'Private checking basis is foreign', 'integrity_fault')
            if grant_ref:
                grant = private_record(self.store, grant_ref, 'evaluation-assignment-grant')
                require(grant['check_plan_ref'] == ref and value['assignment_context_ref'] == grant['contract_ref'],
                    'Private checking basis differs from its grant', 'integrity_fault')
            else:
                require(value['assignment_context_ref'] is None and value['mode'] == 'replay_subject',
                    'Unassigned basis is not a replay host basis', 'integrity_fault')
        elif capture_kind in {'source_contract', 'source_binding'}:
            if capture_kind == 'source_contract':
                require(scope is not None and ref == scope['source_contract_ref']
                    and kind == 'subnode-execution-contract', 'Original source contract differs', 'integrity_fault')
                value = self.store.read_record(ref, contract_id='subnode-execution-contract')
            elif kind == 'subnode-execution-contract':
                value = self.store.read_record(ref, contract_id='subnode-execution-contract')
            else:
                require(kind == 'evaluation-case-binding', 'Original replay binding kind differs', 'integrity_fault')
                value = self.store.read_record(ref)
        elif capture_kind in START_CAPTURES:
            indexed_kind, schema_id = START_CAPTURES[capture_kind]
            require(kind == indexed_kind and grant_ref is not None,
                'Scientific start receipt lacks its exact private kind/assignment', 'integrity_fault')
            value = self.store.read_record(ref)
            validate(schema_id, value)
            grant = private_record(self.store, grant_ref, 'evaluation-assignment-grant')
            require(grant['request_ref'] == request_ref and grant['scope_ref'] == scope_ref,
                'Scientific start receipt belongs to another request', 'integrity_fault')
            if capture_kind == 'execution_preparation':
                validate_preparation_binding(self.store, value, grant_ref, grant)
        elif capture_kind in NATIVE_KINDS:
            require(kind in NATIVE_KINDS[capture_kind], 'Native evidence indexed kind differs', 'integrity_fault')
            value = self.store.read_record(ref)
        else:
            value = None
        if grant_ref and value is not None:
            grant = private_record(self.store, grant_ref, 'evaluation-assignment-grant')
            for field, expected in [('execution_id', grant['execution_id']), ('invocation_id', grant['invocation_id'])]:
                if field in value:
                    require(value[field] == expected, 'Captured native identity differs', 'integrity_fault')
            if capture_kind in PRIVATE_EVIDENCE and 'contract_ref' in value:
                expected_contract=scope['source_contract_ref'] if capture_kind=='review_context' else grant['contract_ref']
                require(value['contract_ref'] == expected_contract,
                    'Captured private evidence targets another assignment', 'integrity_fault')
        if capture_kind in {'workspace', 'output'} and (raw.startswith(b'PK\x03\x04')
                or self.store.artifact_metadata(ref)['media_type'] == 'application/zip'):
            self._archive(raw)
        return raw

    @staticmethod
    def _archive(raw):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries, paths, total = archive.infolist(), set(), 0
                require(len(entries) <= MAX_EXPORT_FILES, 'Captured ZIP member bound exceeded', 'validation')
                for info in entries:
                    path = info.filename[:-1] if info.is_dir() else info.filename
                    require(safe_named_path(path) and path.casefold() not in paths,
                        'Unsafe or case-colliding captured ZIP member', 'validation')
                    paths.add(path.casefold())
                    mode = info.external_attr >> 16
                    require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)
                        and not info.flag_bits & 1, 'Special/encrypted captured ZIP member', 'validation')
                    total += info.file_size
                    require(total <= MAX_EXPORT_BYTES, 'Captured ZIP transfer bound exceeded', 'validation')
                    if not info.is_dir():
                        require(len(archive.read(info)) == info.file_size,
                            'Captured ZIP promised length differs', 'integrity_fault')
        except (zipfile.BadZipFile, RuntimeError, ValueError, OSError) as error:
            raise ResearchError('integrity_fault', 'Captured ZIP is unavailable') from error

    def _trace_packets(self, ref, request_ref, grant_ref, captures):
        """Follow only the native summary→event→raw-packet typed edges."""
        require(grant_ref is not None, 'Native trace has no exact private assignment', 'integrity_fault')
        grant = private_record(self.store, grant_ref, 'evaluation-assignment-grant')
        child = private_record(self.store, grant['contract_ref'], 'evaluation-subnode-context')
        require(grant['request_ref'] == request_ref == child['request_ref'],
            'Native trace belongs to another request', 'integrity_fault')
        kind = self.store.record_kind(ref)
        require(kind in {'native-governed-trace', 'native-governed-trace-event'},
            'Native trace indexed kind differs', 'integrity_fault')
        value = self.store.read_record(ref)
        scope = value.get('scope')
        scope_fields = {'run_id', 'node_id', 'subnode_id', 'attempt_id', 'execution_id',
            'invocation_id', 'call_id', 'contract_ref', 'model_call_start_ref'}
        require(type(scope) is dict and set(scope) == scope_fields
            and all(scope[k] == child[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id'))
            and all(scope[k] == grant[k] for k in ('execution_id', 'invocation_id', 'contract_ref')),
            'Native trace has another private execution scope', 'integrity_fault')
        owned_starts = [e for e in captures if e['capture_kind'] == 'model_start'
            and e['capture_ref'] == scope['model_call_start_ref'] and e['assignment_grant_ref'] == grant_ref]
        require(owned_starts and self.store.record_kind(scope['model_call_start_ref']) == 'model-call-start',
            'Native trace has no captured exact start', 'integrity_fault')
        start = self.store.read_record(scope['model_call_start_ref'])
        require(all(start[k] == scope[k] for k in ('run_id', 'execution_id', 'invocation_id', 'call_id', 'contract_ref')),
            'Native trace differs from original start', 'integrity_fault')
        claim = private_record(self.store, start['call_claim_ref'], 'evaluation-call-claim')
        require(claim['request_ref'] == request_ref and claim['assignment_grant_ref'] == grant_ref
            and all(claim[k] == scope[k] for k in ('execution_id', 'invocation_id', 'call_id', 'contract_ref'))
            and any(e['capture_kind'] == 'model_claim' and e['capture_ref'] == start['call_claim_ref']
                and e['assignment_grant_ref'] == grant_ref for e in captures),
            'Native trace has no captured private claim', 'integrity_fault')
        if kind == 'native-governed-trace':
            require(set(value) == {'schema', 'scope', 'status', 'event_refs'}
                and value['schema'] == 'ai4r-native-governed-trace:1'
                and value['status'] in {'completed', 'failed', 'interrupted'}
                and type(value['event_refs']) is list and len(value['event_refs']) <= MAX_JOURNAL_EVENTS
                and len({encoded(r) for r in value['event_refs']}) == len(value['event_refs']),
                'Malformed native trace summary', 'integrity_fault')
            refs = value['event_refs']
        else:
            refs = [ref]
        found = []
        for index, event_ref in enumerate(refs):
            require(any(e['capture_kind'] == 'trace' and e['capture_ref'] == event_ref
                and e['assignment_grant_ref'] == grant_ref for e in captures)
                and self.store.record_kind(event_ref) == 'native-governed-trace-event',
                'Native event is not privately captured', 'integrity_fault')
            event = self.store.read_record(event_ref)
            require(set(event) == {'schema', 'scope', 'sequence', 'direction', 'method', 'raw_ref'}
                and event['schema'] == 'ai4r-native-governed-trace-event:1' and event['scope'] == scope
                and type(event['sequence']) is int and event['sequence'] >= 0
                and (kind != 'native-governed-trace' or event['sequence'] == index)
                and event['direction'] in {'in', 'out'} and isinstance(event['method'], str)
                and not event['method'].startswith(('account/', 'login/', 'auth/')),
                'Native event is malformed or private', 'integrity_fault')
            raw = self.store.read_blob(event['raw_ref'])
            packet = _strict_json(raw)
            require(type(packet) is dict and not str(packet.get('method', '')).startswith(('account/', 'login/', 'auth/'))
                and ('method' not in packet or packet['method'] == event['method']),
                'Native raw packet has a private or different method', 'integrity_fault')
            found.append(('native_packet', event['raw_ref'], raw))
        return found

    def export_bytes(self, principal, request_id, *, audience):
        require(audience in {'researcher', 'reviewer'} and audience in principal.audiences,
            'Audience is outside the authenticated grant', 'auth')
        _, _, request_ref, request, row, scope_ref, scope = self._owned(principal, request_id)
        cursor, events = self._journal(request_ref, row, scope_ref)
        terminal = self._terminal(request_ref, row, scope_ref, events)
        files, contents, required, seen, total = [], {}, [], set(), 0
        def add(kind, ref, *, evidence_id, raw=None):
            nonlocal total
            key = (kind, encoded(ref))
            if key in seen:
                return
            raw = self.store.read_blob(ref) if raw is None else raw
            seen.add(key)
            total += len(raw)
            require(len(files) < MAX_EXPORT_FILES and total <= MAX_EXPORT_BYTES,
                'Evaluation export transfer bound exceeded', 'evidence_unavailable')
            path = 'evidence/' + str(len(files)).zfill(5) + '-' + kind + '-' + ref['sha256']
            require(safe_named_path(path) and path.casefold() not in {p.casefold() for p in contents},
                'Unsafe evaluation export path', 'integrity_fault')
            files.append({'path': path, 'artifact_ref': ref, 'kind': kind,
                'media_type': self.store.artifact_metadata(ref)['media_type'], 'audience': audience, 'byte_length': len(raw)})
            contents[path] = raw
            required.append({'evidence_id': evidence_id, 'kind': kind, 'status': 'present',
                'artifact_ref': ref, 'path': path, 'reason': None})
        # Closed control edges are indispensable original custody, not invented
        # captures or an all-store inventory. They let an offline reader verify
        # the request/slot/journal/assignment/terminal joins independently.
        add('request', request_ref, evidence_id='control:request')
        if scope_ref:
            add('scope', scope_ref, evidence_id='control:scope')
        if row['terminal_ref']:
            add('terminal', _strict_json(row['terminal_ref'].encode('utf-8')), evidence_id='control:terminal')
        grants = set()
        for event_ref, event in events:
            add('event', event_ref, evidence_id='journal:' + event['id'])
            if event['assignment_grant_ref'] is not None and encoded(event['assignment_grant_ref']) not in grants:
                grant_ref = event['assignment_grant_ref'];grants.add(encoded(grant_ref))
                grant = private_record(self.store, grant_ref, 'evaluation-assignment-grant')
                require(grant['request_ref'] == request_ref and grant['scope_ref'] == scope_ref,
                    'Private assignment custody differs', 'integrity_fault')
                add('assignment_grant', grant_ref, evidence_id='control:' + grant['id'])
        binding_ref = scope['source_binding_ref'] if scope else None
        for event_ref, event in events:
            if event['kind'] in {'gap', 'audit_failure', 'outcome_unknown'}:
                required.append({'evidence_id': event['id'], 'kind': event['capture_kind'] or event['kind'],
                    'status': 'unavailable', 'artifact_ref': None, 'path': None, 'reason': event['reason']})
            if event['kind'] != 'captured':
                continue
            capture_kind, ref = event['capture_kind'], event['capture_ref']
            if capture_kind == 'source_binding':
                require(binding_ref is None or binding_ref == ref, 'Source binding capture differs', 'integrity_fault')
                binding_ref = ref
            raw = self._capture(capture_kind, ref, request_ref, scope_ref, scope, event['assignment_grant_ref'])
            add(capture_kind, ref, evidence_id=event['id'], raw=raw)
        captures = [event for _, event in events if event['kind'] == 'captured']
        for event in captures:
            if event['capture_kind'] != 'trace':
                continue
            for kind, ref, raw in self._trace_packets(event['capture_ref'], request_ref,
                    event['assignment_grant_ref'], captures):
                add(kind, ref, evidence_id='typed-native:' + ref['sha256'], raw=raw)
        missing_sources=set()
        def source_add(kind, ref, *, evidence_id):
            # Missing permitted provenance stays an explicit incomplete row.
            # Other integrity/authorization failures still refuse the export.
            key=(kind,encoded(ref))
            if key in missing_sources:return False
            try:
                raw = self.store.read_blob(ref)
            except ResearchError as error:
                if error.code != 'evidence_unavailable':
                    raise
                missing_sources.add(key)
                required.append({'evidence_id':evidence_id,'kind':kind,'status':'unavailable',
                    'artifact_ref':None,'path':None,'reason':'Original selected source bytes unavailable.'})
                return False
            add(kind, ref, evidence_id=evidence_id, raw=raw)
            return True
        selection_ref = self.runtime.get('account_model_selection_ref')
        if selection_ref is not None:
            from .evaluation_model_binding import source_model_selection
            selection = self.store.read_record(selection_ref)
            source_run_id = (self.store.read_record(scope['source_contract_ref'])['run_id']
                             if scope else selection.get('run_id'))
            selection = source_model_selection(self.store, selection_ref,
                account_id=self.runtime['account_id'], source_run_id=source_run_id)
            add('source_model_selection', selection_ref, evidence_id='source:account-model-selection')
            if selection.get('deployment_ref') is not None:
                deployment = self.store.read_record(selection['deployment_ref'])
                endpoint = self.store.read_record(deployment['endpoint_ref'])
                # These are original public routing metadata, never the private
                # catalog transport/session or credential contents.
                _model_endpoint_shape(endpoint)
                add('source_model_deployment', selection['deployment_ref'], evidence_id='source:account-model-deployment')
                add('source_model_endpoint', deployment['endpoint_ref'], evidence_id='source:account-model-endpoint')
        if scope:
            # Source provenance is typed and finite. Original E2 observations,
            # complete outputs and permitted host records stay separate from
            # the actual private reviewer evidence and measured usage.
            source=self.store.read_record(scope['source_contract_ref'],contract_id='subnode-execution-contract')
            # Capture the two exact immutable eligibility records selected by
            # this runtime, never an inventory of the current live Library.
            profile_ref=self.runtime['profile_ref'];snapshot_ref=self.runtime['library_snapshot_ref']
            for kind,ref in [('evaluation-profile',profile_ref),('library-snapshot',snapshot_ref)]:
                require(self.store.record_kind(ref)==kind,
                    'Original frozen eligibility kind differs','integrity_fault')
                if source_add(kind,ref,evidence_id='source:'+kind+':'+ref['sha256']):
                    self.store.read_record(ref,contract_id=kind)
            if ('library-snapshot',encoded(snapshot_ref)) not in missing_sources:
                profile=self.store.read_record(profile_ref,contract_id='evaluation-profile')
                snapshot=self.store.read_record(snapshot_ref,contract_id='library-snapshot')
                declaration_ref=source['bindings'][0]['declaration_ref']
                declaration=self.store.read_record(declaration_ref,contract_id='capsule-declaration')
                pin={'cc_name':declaration['identity']['name'],'cc_version':declaration['identity']['version_label'],
                    'declaration_sha256':declaration_ref['sha256']}
                require(snapshot_ref['sha256']==profile['library_snapshot_sha256']
                    and sum(all(entry.get(k)==v for k,v in pin.items()) for entry in snapshot['entries'])==1,
                    'Original frozen snapshot/profile subject differs','integrity_fault')
            require(self.store.record_kind(scope['source_check_plan_ref'])=='bound-check-plan'
                and self.store.record_kind(source['node_contract_ref'])=='node-execution-contract',
                'Original checking/parent provenance kind differs','integrity_fault')
            plan=self.store.read_record(scope['source_check_plan_ref'],contract_id='bound-check-plan')
            parent=self.store.read_record(source['node_contract_ref'],contract_id='node-execution-contract')
            require(plan['contract_ref']==scope['source_contract_ref'] and plan['node_contract_ref']==source['node_contract_ref'],
                'Original checking provenance targets another subject','integrity_fault')
            for kind,ref in [('source_check_plan',scope['source_check_plan_ref']),('source_node',source['node_contract_ref']),
                    ('source_template',source['template_ref']),('source_template',parent['template_ref'])]:
                source_add(kind,ref,evidence_id='source:'+kind+':'+ref['sha256'])
            # This is the finite immutable source edge closure needed by an
            # offline consumer. Do not follow calibration/eligibility fixtures,
            # account/key records, arbitrary nested Refs or whole snapshots.
            template_refs = [source['template_ref']]
            for grant_text in grants:
                grant=private_record(self.store,_strict_json(grant_text.encode('utf-8')),'evaluation-assignment-grant')
                child=private_record(self.store,grant['contract_ref'],'evaluation-subnode-context')
                source_add('source_template',child['source_template_ref'],evidence_id='source:assignment-template:'+child['source_template_ref']['sha256'])
                template_refs.append(child['source_template_ref'])
            for template_ref in {encoded(pin):pin for pin in template_refs}.values():
                if ('source_template',encoded(template_ref)) not in seen:
                    continue
                require(self.store.record_kind(template_ref) == 'subnode-template',
                    'Selected source template kind differs', 'integrity_fault')
                template = self.store.read_record(template_ref)
                available={}
                for kind, pin in [('source_declaration', template['capsule_ref']),
                        ('source_admission', template['admission_ref']),
                        ('source_check_profile', template['checking_profile_ref']),
                        ('source_check_bundle', template['check_bundle_ref'])]:
                    available[kind]=source_add(kind, pin, evidence_id='source:'+kind+':'+pin['sha256'])
                if available['source_admission']:
                    admission=self.store.read_record(template['admission_ref'],contract_id='library-admission')
                    require(admission['candidate_ref']==template['capsule_ref'],
                        'Original source admission targets another declaration','integrity_fault')
                if available['source_check_profile']:
                    profile=self.store.read_record(template['checking_profile_ref'],contract_id='checking-profile')
                    source_add('source_instructions', profile['instruction_ref'],
                        evidence_id='source:instructions:'+profile['instruction_ref']['sha256'])
                if available['source_declaration']:
                    declaration=self.store.read_record(template['capsule_ref'],contract_id='capsule-declaration')
                    paths=[body['path'] for body in declaration['identity']['body']]
                    paths += [pin['ref'] for dependency in declaration['needs']['external']
                        for name in ('pin','lockfile') if (pin:=dependency.get(name))]
                    for path in paths:
                        pin=template['body_refs'][path]
                        source_add('source_body',pin,evidence_id='source:body:'+pin['sha256'])
                if available['source_check_bundle']:
                    bundle=self.store.read_record(template['check_bundle_ref'],contract_id='check-bundle')
                    for check in bundle['checks']:
                        pin=check['runner_ref']
                        source_add('source_runner',pin,evidence_id='source:runner:'+pin['sha256'])
            for pin in source['input_refs']:
                source_add('source_input', pin, evidence_id='source:input:'+pin['sha256'])
            if request['entry_point']=='E2':
                require(scope['source_observation_ref'] is not None
                    and self.store.record_kind(scope['source_observation_ref'])=='invocation-observation',
                    'Original E2 observation provenance kind differs','integrity_fault')
                original=self.store.read_record(scope['source_observation_ref'],contract_id='invocation-observation')
                require(original['contract_ref']==scope['source_contract_ref']
                    and original['output_refs']==scope['source_output_refs'],
                    'Original E2 observation/output inventory differs','integrity_fault')
                add('source_observation',scope['source_observation_ref'],evidence_id='source:observation')
                binding=self.store.read_record(scope['source_binding_ref'])
                require(binding['contract_ref']==scope['source_contract_ref']
                    and binding['check_plan_ref']==scope['source_check_plan_ref']
                    and binding['original_observation_ref']==scope['source_observation_ref']
                    and sorted(encoded(r) for r in binding['output_refs'].values())==sorted(encoded(r) for r in scope['source_output_refs']),
                    'Original E2 binding/observation closure differs','integrity_fault')
                for item in binding['host_records']:
                    require(type(item) is dict and set(item)=={'record_type','ref'}
                        and item['record_type'] in {'runtime_observation','identity_record','budget_record','tool_observation'}
                        and self.store.record_kind(item['ref'])=='invocation-observation',
                        'Original E2 host record kind differs','integrity_fault')
                    host=self.store.read_record(item['ref'],contract_id='invocation-observation')
                    require(host['contract_ref']==scope['source_contract_ref'],
                        'Original E2 host record belongs to another subject','integrity_fault')
                    add('source_host_record',item['ref'],evidence_id='source:host:'+item['record_type']+':'+item['ref']['sha256'])
            # Every already-promised measurement edge must be delivered through
            # a captured private edge or the explicit original E2 provenance.
            delivered_refs={encoded(item['artifact_ref']) for item in files}
            for item in list(files):
                if item['kind']!='measurement':continue
                value=self.store.read_record(item['artifact_ref'])
                fields={'id','contract_ref','accepted','status','output_refs','deterministic_ref','observation_ref',
                    'assessment_refs','verifier_check_refs','observation_refs','trace_refs','failure','elapsed_s','recorded_at'}
                require(set(value)==fields and value['accepted'] is False and value['status'] in {'completed','failed','blocked','interrupted'},
                    'Private measurement body differs from its original shape','integrity_fault')
                promised=[value['contract_ref'],value['deterministic_ref'],value['observation_ref'],
                    *value['output_refs'].values(),*value['assessment_refs'],*value['verifier_check_refs'],
                    *value['observation_refs'],*value['trace_refs']]
                require(all(encoded(ref) in delivered_refs for ref in promised),
                    'Measurement promised uncaptured original bytes','integrity_fault')
        require(binding_ref is not None, 'No captured original source binding for export', 'evidence_unavailable')
        delivered = {(f['kind'], encoded(f['artifact_ref'])) for f in files}
        require(('original_request', encoded(request['original_request_ref'])) in delivered
            and ('normalized_request', encoded(request['normalized_request_ref'])) in delivered,
            'Original request captures are incomplete', 'integrity_fault')
        for kind in ('workspace', 'trace'):
            if not any(e['kind'] == kind for e in required):
                required.append({'evidence_id': 'not-produced:' + kind, 'kind': kind,
                    'status': 'not_produced', 'artifact_ref': None, 'path': None,
                    'reason': 'No ' + kind + ' capture was produced for this request snapshot.'})
        manifest = {'schema': 'ai4r-evaluation-export:1', 'request_ref': request_ref, 'scope_ref': scope_ref,
            'request_state': terminal['state'] if terminal else 'outcome_unknown' if row['state'] in {'claiming', 'cancelling'} else 'started',
            'through_event_ref': cursor, 'source_binding_ref': binding_ref,
            'original_request_ref': request['original_request_ref'], 'normalized_request_ref': request['normalized_request_ref'],
            'result_ref': terminal['result_ref'] if terminal else None,
            'failure_ref': terminal['failure_ref'] if terminal else None,
            'measurement_refs': terminal['measurement_refs'] if terminal else [],
            'audience': audience, 'files': files, 'required_evidence': required, 'redactions': [],
            'accepted': False, 'invalid_for_product': True}
        manifest['id'] = 'evaluation-export:' + hashlib.sha256(json_bytes(manifest)).hexdigest()
        validate('urn:ai4r:private:evaluation-export:1', manifest)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path, raw in [('evaluation_export.json', json_bytes(manifest)), *sorted(contents.items())]:
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
        require(len(output.getvalue()) <= MAX_EXPORT_BYTES,
            'Evaluation export transfer bound exceeded', 'evidence_unavailable')
        return output.getvalue()
