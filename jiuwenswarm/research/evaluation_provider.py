"""Finite source E2/E3 operations over installed protected measurement owners.

Public requests select frozen assets and identities. Resource construction,
model calls, grants and filesystem custody stay with installed host adapters.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import inspect
import json
from pathlib import PurePosixPath
import re
import time
import uuid

from .contracts import ResearchError
from .gate import ProtectedGate
from .measurement import TrialMeasurement, all_mandatory_pass,ordered_replay_outputs
from .state import json_bytes, utc_now


def require(condition, message, code='evaluation_request'):
    if not condition:
        raise ResearchError(code, message)


def closed(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields), 'Unexpected evaluation request or capture fields')


def text(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def logical_path(value):
    require(text(value) and '\\' not in value and ':' not in value and not any(ord(c) < 32 for c in value),
            'Only a captured logical relative asset path is allowed')
    path = PurePosixPath(value)
    require(not path.is_absolute() and not any(p in {'.', '..', ''} for p in value.split('/'))
            and path.as_posix() == value, 'Only a canonical captured relative asset path is allowed')
    return value


def single_cc_check_results(store, measured):
    """Expose original deterministic, semantic and reviewer-mechanical findings."""
    field=lambda key:getattr(measured,key) if hasattr(measured,key) else measured[key]
    checked=store.read_record(field('deterministic_ref'))
    rows=[{'check_id':r['check_id'],'status':r['outcome']} for r in checked['results']]
    for index,ref in enumerate(field('assessment_refs')):
        assessment=store.read_record(ref,contract_id='verifier-assessment')
        rows.extend({'check_id':'semantic:'+str(index)+':'+r['criterion_id'],'status':r['outcome']} for r in assessment['findings'])
    for index,ref in enumerate(field('verifier_check_refs')):
        checked=store.read_record(ref,contract_id='deterministic-check-result')
        rows.extend({'check_id':'reviewer:'+str(index)+':'+r['check_id'],'status':r['outcome']} for r in checked['results'])
    return rows


@dataclass(frozen=True)
class PreparedEvaluation:
    """Installed owner result, never deserialized from a client request.

    context retains actual store/contract/evaluation_binding; execute owns the
    durable measurement grant, actual governed effects and containment.
    """
    context: object
    check_plan_ref: dict
    execute: object


class EvaluationProvider:
    def __init__(self, store, operator, *, assets_ref, resources, library):
        self.store, self.resources, self.library = store, resources, library
        self._history_runtime_ref = None
        self.operator = operator.snapshot()
        self.profile_ref = self.operator['cc']['evaluation_profile_ref']
        require(self.profile_ref is not None, 'Product mode has no evaluation operations', 'entry_point_unavailable')
        require(store.record_kind(self.profile_ref) == 'evaluation-profile', 'No approved evaluation-profile capture')
        self.profile = store.read_record(self.profile_ref, contract_id='evaluation-profile')
        require(self.profile['invalid_for_product'] and self.profile['router_enabled'] == self.operator['cc']['router']['enabled']
                and self.profile['plan_source'] == self.operator['cc']['plan_source'], 'Evaluation-only profile/settings differ')
        require((self.profile['router_version'] is None) == (self.profile['router_enabled'] is False)
                and (self.profile['router_enabled'] or self.profile['model_route'] == self.operator['codex']['route_id']),
                'Evaluation route pins differ')
        self.assets_ref = copy.deepcopy(assets_ref)
        require(store.record_kind(assets_ref) == 'evaluation-assets', 'No protected evaluation-asset capture')
        assets = store.read_record(assets_ref)
        closed(assets, {'schema', 'id', 'profile_ref', 'configuration_ref', 'account_id', 'workspace_id', 'campaign_id', 'entries', 'cases'})
        require(assets['schema'] == 'ai4r-evaluation-assets:1' and assets['profile_ref'] == self.profile_ref
                and all(text(assets[k]) for k in ('id', 'account_id', 'workspace_id', 'campaign_id')), 'Invalid protected asset scope')
        configuration = store.read_record(assets['configuration_ref'])
        require(configuration.get('operator', configuration) == self.operator, 'Asset configuration differs from approved bytes')
        self.assets, self.entries, self.cases = assets, {}, {}
        if isinstance(resources,InstalledEvaluationResources):resources.provider=self
        roles = {'declaration', 'output', 'binding', 'input', 'host_runtime_observation', 'host_identity_record',
                 'host_budget_record', 'host_tool_observation'}
        require(isinstance(assets['entries'], list) and isinstance(assets['cases'], list), 'Invalid protected asset inventory')
        for entry in assets['entries']:
            closed(entry, {'path', 'sha256', 'artifact_ref', 'role'})
            name = logical_path(entry['path'])
            require(name.casefold() not in {p.casefold() for p in self.entries} and entry['role'] in roles
                    and entry['sha256'] == entry['artifact_ref']['sha256'], 'Ambiguous asset identity or role')
            store.read_blob(entry['artifact_ref']);self.entries[name] = copy.deepcopy(entry)
        for case in assets['cases']:
            closed(case, {'case_id', 'entry_point', 'binding_ref', 'record_gate'})
            key = (case['case_id'], case['entry_point'])
            require(text(case['case_id']) and case['entry_point'] in {'E2', 'E3'} and key not in self.cases
                    and type(case['record_gate']) is bool and (case['entry_point'] == 'E2' or not case['record_gate']),
                    'Invalid or duplicate protected evaluation case')
            store.read_blob(case['binding_ref']);self.cases[key] = copy.deepcopy(case)

    @property
    def available_entry_points(self):
        from .evaluation_authority import EvaluationAuthority
        authority=getattr(self.resources,'authority',None)
        if (type(authority) is not EvaluationAuthority or authority.resources is not self.resources
                or authority.store is not self.store or authority not in authority.runner._evaluation_owners):return ()
        try:authority._current_runtime()
        except (ResearchError,KeyError):return ()
        installed = tuple(getattr(self.resources, 'available_entry_points', ())) if self.resources is not None else ()
        return tuple(p for p in ('E2', 'E3') if p in installed and p in self.profile['allowed_entry_points'])

    def _actor(self, principal):
        principal.require('evaluation_profile', self.assets['workspace_id'])
        require(principal.account_id == self.assets['account_id'], 'Evaluation account is outside the protected scope', 'auth')
        require(self.store.read_record(self.profile_ref, contract_id='evaluation-profile') == self.profile
                and self.store.read_record(self.assets_ref) == self.assets, 'Frozen evaluation inputs changed')
        configuration = self.store.read_record(self.assets['configuration_ref'])
        require(configuration.get('operator', configuration) == self.operator, 'Frozen evaluation configuration changed')

    def _asset(self, value, role):
        closed(value, {'path', 'sha256'})
        name = logical_path(value['path']);entry = self.entries.get(name)
        require(entry is not None and entry['role'] == role and value['sha256'] == entry['sha256'],
                'Asset is outside the exact frozen inventory')
        self.store.read_blob(entry['artifact_ref'])
        return copy.deepcopy(entry['artifact_ref'])

    def _normalized_request(self, request, entry_point):
        require(entry_point in {'E2', 'E3'}, 'Unknown evaluation entry point')
        common = {'request_id', 'campaign_id', 'case_id', 'evaluation_profile_id'}
        fields = {'verifier_cc_id', 'declaration', 'output', 'node_id', 'host_records'} if entry_point == 'E2' else {
            'capsule_id', 'capsule_version', 'capsule_declaration_sha256', 'binding', 'inputs', 'model_route'}
        require(isinstance(request, dict), 'Evaluation request must be an object')
        normalized = copy.deepcopy(request)
        if entry_point == 'E2':
            normalized.setdefault('host_records', [])
        closed(normalized, common | fields)
        return normalized

    def _bind_history_runtime(self, resources, runtime_ref):
        require(type(resources) is InstalledEvaluationResources and resources is self.resources
            and resources.provider is self and resources.authority is not None
            and resources.authority.provider is self and resources.authority.runtime_ref == runtime_ref,
            'Historical runtime requires the actual installed evaluation owner')
        require(self._history_runtime_ref in (None, runtime_ref), 'Historical runtime cannot be replaced')
        self._history_runtime_ref = copy.deepcopy(runtime_ref)
        self._history_reader()  # Independently bind exact captured provider scope.

    def _history_reader(self):
        if self._history_runtime_ref is None:
            return None
        from .evaluation_history import EvaluationReader
        reader = EvaluationReader(self.store, runtime_ref=self._history_runtime_ref)
        runtime = reader.runtime
        require(runtime['assets_ref'] == self.assets_ref and runtime['profile_ref'] == self.profile_ref
            and all(runtime[key] == self.assets[key] for key in
                ('account_id', 'workspace_id', 'campaign_id', 'configuration_ref')),
            'Historical runtime belongs to another protected provider', 'integrity_fault')
        return reader

    def _historical_result(self, principal, request, entry_point, original_body):
        reader = self._history_reader()
        if reader is None:
            return None
        normalized = self._normalized_request(request, entry_point)
        require(text(normalized['request_id']), 'Request identity is required')
        from .evaluation_authority import strict_original_request_body
        strict_original_request_body(request, original_body)
        try:
            _, _, _, original, *_ = reader._owned(principal, normalized['request_id'])
        except ResearchError as error:
            if error.code == 'not_found':
                return None
            raise
        fingerprint = hashlib.sha256(json_bytes([entry_point, normalized])).hexdigest()
        require(original['entry_point'] == entry_point and original['fingerprint'] == fingerprint,
            'Request identity already names different content', 'identity_conflict')
        historical = reader.get(principal, normalized['request_id'])
        require(historical['result'] is not None,
            'Reconcile the original claimed request; it cannot start again', 'evaluation_outcome_unknown')
        require(isinstance(historical['result'], dict), 'Historical response is not an original object', 'integrity_fault')
        return copy.deepcopy(historical['result'])

    def _validate(self, principal, request, entry_point):
        self._actor(principal)
        normalized = self._normalized_request(request, entry_point)
        common = {'request_id', 'campaign_id', 'case_id', 'evaluation_profile_id'}
        require(all(text(normalized[k]) for k in common) and normalized['campaign_id'] == self.assets['campaign_id']
                and normalized['evaluation_profile_id'] == self.profile['profile_id'], 'Request differs from the frozen campaign/profile')
        case = self.cases.get((normalized['case_id'], entry_point))
        require(entry_point in self.profile['allowed_entry_points'] and case is not None, 'Case/entry point is outside the approved profile')
        resolved = {'case_binding_ref': copy.deepcopy(case['binding_ref'])}
        if entry_point == 'E2':
            require(text(normalized['node_id']) and text(normalized['verifier_cc_id']), 'Replay subject identity is incomplete')
            resolved['declaration_ref'] = self._asset(normalized['declaration'], 'declaration')
            resolved['output_ref'] = self._asset(normalized['output'], 'output')
            require(isinstance(normalized['host_records'], list), 'Replay host-record inventory must be an array')
            resolved['host_records'] = []
            allowed = {'runtime_observation', 'identity_record', 'budget_record', 'tool_observation'}
            for record in normalized['host_records']:
                closed(record, {'record_type', 'path', 'sha256'})
                require(record['record_type'] in allowed, 'Unsupported host-only evidence class')
                ref = self._asset({key: record[key] for key in ('path', 'sha256')}, 'host_' + record['record_type'])
                resolved['host_records'].append({'record_type': record['record_type'], 'ref': ref})
        else:
            require(text(normalized['capsule_id']) and text(normalized['capsule_version'])
                    and isinstance(normalized['capsule_declaration_sha256'], str)
                    and re.fullmatch('[a-f0-9]{64}', normalized['capsule_declaration_sha256']) is not None
                    and normalized['model_route'] == self.profile['model_route'], 'Single-CC identity/route differs')
            resolved['binding_ref'] = self._asset(normalized['binding'], 'binding')
            require(resolved['binding_ref'] == case['binding_ref'], 'Binding differs from the frozen case')
            require(isinstance(normalized['inputs'], list), 'Single-CC inputs must be an array')
            resolved['inputs'] = []
            for item in normalized['inputs']:
                closed(item, {'port', 'path', 'sha256'});require(text(item['port']), 'Invalid input port')
                resolved['inputs'].append({'port': item['port'], 'ref': self._asset({k:item[k] for k in ('path','sha256')}, 'input')})
            row = self.library.get(normalized['capsule_id'], normalized['capsule_version'])
            admission = self.library.store.read_record(row['admission_ref'], contract_id='library-admission')
            pin = {'cc_name': normalized['capsule_id'], 'cc_version': normalized['capsule_version'],
                   'declaration_sha256': normalized['capsule_declaration_sha256']}
            require(admission['status'] == 'admitted' and admission['cc'] == pin and row['declaration_ref']['sha256'] == pin['declaration_sha256']
                    and row['standing'] not in {'revoked', 'suspended'}, 'Single-CC subject is not the exact admitted version')
            self.library.eligible_association(row['declaration_ref'])
            resolved['library_entry'] = row
        return normalized, resolved, case

    def _key(self, request_id):
        return 'evaluation-request:' + hashlib.sha256(json_bytes([self.profile_ref, self.assets['account_id'], request_id])).hexdigest()

    def _claim(self, request, entry_point):
        key = self._key(request['request_id']);fingerprint = hashlib.sha256(json_bytes([entry_point, request])).hexdigest()
        with self.store.transaction() as db:
            prior = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            if prior:
                record = json.loads(prior[0])
                require(record['fingerprint'] == fingerprint, 'Request identity already names different content', 'identity_conflict')
                return key, record, False
            record = {'fingerprint': fingerprint, 'status': 'started', 'result_ref': None, 'failure_ref': None}
            db.execute('INSERT INTO metadata(key,value) VALUES(?,?)', (key, json_bytes(record).decode()))
        self.store.append_record('evaluation-request', {'id': key, 'request_id': request['request_id'], 'entry_point': entry_point,
            'account_id': self.assets['account_id'], 'workspace_id': self.assets['workspace_id'], 'campaign_id': self.assets['campaign_id'],
            'profile_ref': self.profile_ref, 'assets_ref': self.assets_ref, 'request': request, 'invalid_for_product': True})
        return key, record, True

    def _save(self, key, state, *, result=None, failure=None):
        record = copy.deepcopy(state)
        if result is not None:
            ref = self.store.append_record('evaluation-result', {'id': key + ':result', 'result': result, 'invalid_for_product': True})
            record.update(status='completed', result_ref=ref)
        else:
            ref = self.store.append_record('evaluation-request-failure', {'id': key + ':failure', 'code': failure,
                'invalid_for_product': True, 'recorded_at': utc_now()})
            record.update(status='interrupted' if failure == 'cancelled' else 'failed', failure_ref=ref)
        with self.store.transaction() as db:
            current = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            require(current is not None and json.loads(current[0]) == state, 'Request state changed during measurement')
            db.execute('UPDATE metadata SET value=? WHERE key=?', (json_bytes(record).decode(), key))

    def get(self, principal, request_id):
        self._actor(principal);require(text(request_id), 'Request identity is required')
        reader = self._history_reader()
        if reader is not None:
            return reader.get(principal, request_id)
        # Only an unbound historical provider reads retired metadata. A bound
        # runtime owns its complete history namespace, including unknown IDs.
        with self.store._lock:
            row = self.store.connection.execute('SELECT value FROM metadata WHERE key=?', (self._key(request_id),)).fetchone()
        require(row is not None, 'Evaluation request is unavailable', 'not_found')
        record = json.loads(row[0])
        return {'request_id': request_id, 'status': record['status'], 'result':
            self.store.read_record(record['result_ref'])['result'] if record['result_ref'] else None,
            'failure_ref': record['failure_ref'], 'invalid_for_product': True}

    def _prepared(self, prepared, request, resolved, entry_point):
        require(isinstance(prepared, PreparedEvaluation) and callable(prepared.execute), 'No installed finite measurement owner')
        ctx = prepared.context;binding = ctx.evaluation_binding
        expected = {'profile_ref': self.profile_ref, 'configuration_ref': self.assets['configuration_ref'],
            'account_id': self.assets['account_id'], 'workspace_id': self.assets['workspace_id'], 'campaign_id': self.assets['campaign_id'],
            'verifier_cc_ref': self.profile['verifier_cc_ref'], 'candidate_pins': self.profile['candidate_pins'], 'model_route': self.profile['model_route']}
        require(all(binding.get(k) == v for k,v in expected.items()), 'Actual measurement context differs from the approved evaluation scope')
        snapshot_ref = binding.get('library_snapshot_ref')
        snapshot = ctx.store.read_record(snapshot_ref, contract_id='library-snapshot')
        require(snapshot_ref['sha256'] == self.profile['library_snapshot_sha256'], 'Measurement library snapshot drifted')
        require(ctx.store.record_kind(ctx.contract_ref) == 'subnode-execution-contract', 'E2/E3 requires an actual canonical admitted subject')
        contract = ctx.store.read_record(ctx.contract_ref, contract_id='subnode-execution-contract')
        require(contract == ctx.contract and contract['configuration_ref'] == self.assets['configuration_ref'], 'Frozen canonical subject/configuration differs')
        require(prepared.check_plan_ref == ctx.check_plan_ref, 'Owner checking plan differs from its metadata')
        if entry_point == 'E2':
            require(contract['node_id'] == request['node_id'] and contract['bindings'][0]['declaration_ref'] == resolved['declaration_ref']
                    and ctx.replay_output_refs.get(ctx.replay_output_port) == resolved['output_ref'], 'Replay differs from the exact frozen subject/output')
            source = self.store.read_record(resolved['case_binding_ref'])
            require(ctx.replay_output_refs==source['output_refs'],'Replay changed its complete original output inventory')
            require(source.get('verifier_cc_id') == request['verifier_cc_id'], 'Replay verifier differs from its fixed case binding')
            require(ctx.replay_host_records == resolved['host_records'], 'Replay host-record closure differs from the supplied frozen bundle')
        else:
            subject = contract['bindings'][0]['declaration_ref']
            require(subject == resolved['library_entry']['declaration_ref'], 'Measurement substituted a different capsule')
            expected_inputs = [(item['port'],item['ref']) for item in resolved['inputs']]
            actual_inputs = [(port['name'],ref) for port in contract['inputs'] for ref in port['artifact_refs']]
            require(actual_inputs == expected_inputs, 'Canonical measurement inputs differ from supplied binding')
            identity = (request['capsule_id'], request['capsule_version'], request['capsule_declaration_sha256'])
            require(identity in {(e['cc_name'],e['cc_version'],e['declaration_sha256']) for e in snapshot['entries']}, 'Subject is outside the frozen snapshot')
        return ctx

    async def node_replay(self, principal, request, *, original_body=None):
        return await self._run(principal, request, 'E2', original_body=original_body)

    async def single_cc(self, principal, request, *, original_body=None):
        return await self._run(principal, request, 'E3', original_body=original_body)

    async def _run(self, principal, request, entry_point, *, original_body=None):
        # Fresh public evaluations are owned only by IF016's registered finite
        # runtime. Internal admitted/RSI measurement grants are never a fallback.
        self._actor(principal)
        historical = self._historical_result(principal, request, entry_point, original_body)
        if historical is not None:
            return historical
        normalized,resolved,case=self._validate(principal,request,entry_point)
        authority=getattr(self.resources,'authority',None)
        require(authority is not None,'Fresh evaluation runtime is unavailable','entry_point_unavailable')
        request_ref=authority.accept_request(principal,request,entry_point,original_body=original_body)
        historical=authority.inspect(request_ref)
        if historical.get('result_ref') is not None:return self.store.read_record(historical['result_ref'])['result']
        require(historical.get('state') in {'claimed','prepared'},'Claimed evaluation cannot be replayed','evaluation_outcome_unknown')
        began=time.monotonic()
        try:
            scope=authority.prepare(request_ref)
            ctx,measurement=await authority.execute(scope)
            starts=[{'ref':e['capture_ref'],'record':self.store.read_record(e['capture_ref'])} for e in authority.captures(request_ref,'model_start')]
            calls=self._model_calls(ctx,measurement,starts,replay=entry_point=='E2')
            prepared=PreparedEvaluation(ctx,ctx.check_plan_ref,None)
            result=self._single_result(prepared,measurement,calls) if entry_point=='E3' else self._replay_result(normalized,case,prepared,measurement,calls)
            result.update(duration_s=time.monotonic()-began,invalid_for_product=True)
            authority.terminal(request_ref,result=result,measurement_refs=[measurement.measurement_ref])
            return result
        except BaseException as error:
            code='cancelled' if isinstance(error,asyncio.CancelledError) else getattr(error,'code',type(error).__name__)
            try:
                if code == 'cancelled':
                    row = authority._row(request_ref)
                    await authority.cancel(request_ref, row['cancel_id'] or 'evaluation-cancel:' + uuid.uuid4().hex)
                else:
                    stopped = authority._row(request_ref)['cancel_id'] is not None
                    authority.terminal(request_ref, failure=code,
                        state='outcome_unknown' if stopped or code in {'audit_unavailable', 'containment_uncertain'} else 'failed')
            except Exception as capture_error:raise ResearchError('evaluation_audit_unavailable','Reconcile original request; terminal proof unavailable') from capture_error
            raise

    async def _legacy_run(self, principal, request, entry_point):
        # Reconciliation of an identical already-claimed request is historical:
        # later standing/resource changes must not dispatch it or erase its result.
        self._actor(principal)
        require(isinstance(request,dict) and text(request.get('request_id')), 'Request identity is required')
        historical=copy.deepcopy(request)
        if entry_point=='E2':historical.setdefault('host_records',[])
        with self.store._lock:
            prior=self.store.connection.execute('SELECT value FROM metadata WHERE key=?',(self._key(historical['request_id']),)).fetchone()
        if prior:
            state=json.loads(prior[0])
            fingerprint=hashlib.sha256(json_bytes([entry_point,historical])).hexdigest()
            require(state['fingerprint']==fingerprint,'Request identity already names different content','identity_conflict')
            if state['result_ref'] is not None:return self.store.read_record(state['result_ref'])['result']
            raise ResearchError('evaluation_outcome_unknown','Reconcile the existing claimed request; it cannot start again')
        request, resolved, case = self._validate(principal, request, entry_point)
        require(entry_point in self.available_entry_points, 'Actual qualified evaluation resources are unavailable', 'entry_point_unavailable')
        key, state, fresh = self._claim(request, entry_point)
        if not fresh:
            if state['result_ref'] is not None:return self.store.read_record(state['result_ref'])['result']
            raise ResearchError('evaluation_outcome_unknown', 'Reconcile the existing claimed request; it cannot start again')
        began = time.monotonic()
        try:
            prepare = self.resources.prepare_replay if entry_point == 'E2' else self.resources.prepare_single_cc
            prepared = prepare(request=copy.deepcopy(request), resolved=resolved, profile_ref=copy.deepcopy(self.profile_ref), profile=copy.deepcopy(self.profile))
            if inspect.isawaitable(prepared):prepared = await prepared
            ctx = self._prepared(prepared, request, resolved, entry_point)
            starts_before = {row['ref']['id'] for row in ctx.store.iter_records(kinds=('model-call-start',))}
            ctx.store.append_record('evaluation-context-origin', {'id':'evaluation-origin:'+uuid.uuid4().hex,
                'contract_ref':ctx.contract_ref,'profile_ref':self.profile_ref,'request_id':request['request_id'],
                'campaign_id':request['campaign_id'],'entry_point':entry_point,'invalid_for_product':True})
            measurement = prepared.execute()
            if inspect.isawaitable(measurement):measurement = await measurement
            require(isinstance(measurement, TrialMeasurement) and measurement.accepted is False, 'Owner did not return actual unaccepted measurements')
            require(ctx.store.record_kind(measurement.measurement_ref) == 'trial-measurement', 'No original protected measurement capture')
            recorded = ctx.store.read_record(measurement.measurement_ref)
            require(recorded['contract_ref'] == ctx.contract_ref and recorded['accepted'] is False
                    and recorded['output_refs'] == measurement.output_refs and recorded['deterministic_ref'] == measurement.deterministic_ref
                    and recorded['observation_ref'] == measurement.observation_ref and recorded['status'] == measurement.status
                    and recorded['failure'] == measurement.failure
                    and recorded['assessment_refs'] == list(measurement.assessment_refs)
                    and recorded['verifier_check_refs'] == list(measurement.verifier_check_refs)
                    and recorded['observation_refs'] == list(measurement.observation_refs)
                    and recorded['trace_refs'] == list(measurement.trace_refs),
                    'Returned measurement differs from original captured evidence')
            ctx.store.append_record('evaluation-output-origin', {'id':'evaluation-output:'+uuid.uuid4().hex,
                'contract_ref':ctx.contract_ref,'profile_ref':self.profile_ref,'request_id':request['request_id'],
                'measurement_ref':measurement.measurement_ref,'output_refs':measurement.output_refs,'invalid_for_product':True})
            new_starts = [row for row in ctx.store.iter_records(kinds=('model-call-start',)) if row['ref']['id'] not in starts_before]
            if entry_point == 'E2':
                require(not any(row['record'].get('contract_ref') == ctx.contract_ref for row in new_starts),
                        'Replay invoked its producing worker', 'evaluation_authority')
            calls = self._model_calls(ctx, measurement, new_starts, replay=entry_point == 'E2')
            result = self._replay_result(request, case, prepared, measurement, calls) if entry_point == 'E2' else self._single_result(prepared, measurement, calls)
            result.update(duration_s=time.monotonic()-began, invalid_for_product=True)
            self._save(key, state, result=result)
            return result
        except BaseException as error:
            code = 'cancelled' if isinstance(error, asyncio.CancelledError) else getattr(error,'code',type(error).__name__)
            try:self._save(key, state, failure=code)
            except Exception as audit_error:
                if isinstance(error,asyncio.CancelledError):raise asyncio.CancelledError from audit_error
                raise ResearchError('evaluation_audit_unavailable','Request outcome could not be captured; reconcile without resending') from audit_error
            raise

    def _single_result(self, prepared, measured, calls):
        store = prepared.context.store;checks = store.read_record(measured.deterministic_ref)
        observation = store.read_record(measured.observation_ref)
        effects = observation.get('effects')
        return {'invocation_id': observation.get('id', measured.observation_ref['id']), 'status': measured.status if measured.status in {'completed','failed','blocked'} else 'failed',
            'output_refs': copy.deepcopy(measured.output_refs), 'check_results': single_cc_check_results(store, measured),
            'tool_effects_observed': effects if effects else None, 'model_calls': calls,
            'reason': measured.failure or ('Complete tool-effect observation unavailable' if not effects else None)}

    def _replay_result(self, request, case, prepared, measured, calls):
        ctx = prepared.context;store = ctx.store;plan = store.read_record(prepared.check_plan_ref)
        checks = store.read_record(measured.deterministic_ref);eligible = all_mandatory_pass(plan, checks['results'])
        assessment = measured.assessment_refs[0] if measured.assessment_refs else None
        require(not eligible or assessment is not None or measured.failure is not None,
                'Eligible replay has no actual independent verifier measurement', 'verifier_unavailable')
        port=ctx.replay_output_port;outputs=[measured.output_refs[port]]
        from .evaluation_authority import EvaluationMeasurementContext
        if type(ctx) is EvaluationMeasurementContext:
            decision=ctx.recording_decision(measured,port)
        else:
            decision = ProtectedGate(store).decide(ctx.contract_ref, prepared.check_plan_ref, measured.deterministic_ref,
                assessment, outputs, [measured.observation_ref,*measured.observation_refs], output_port=port,
                halt_reason=measured.failure, verifier_check_ref=measured.verifier_check_refs[0] if measured.verifier_check_refs else None,persist=False)
        persisted, advanced = None, False
        evidence = [measured.measurement_ref]
        if case['record_gate']:
            persisted = utc_now()
            ref = store.append_record('evaluation-gate-record', {'id':'evaluation-gate:'+uuid.uuid4().hex,
                'decision':decision,'persisted_at':persisted,'invalid_for_product':True})
            if type(ctx) is EvaluationMeasurementContext:ctx.owner.register_capture(None,'evaluation_gate',ref,request_ref=ctx.scope['request_ref'])
            advanced = decision['action'] == 'advance';evidence.append(ref)
            action_ref=store.append_record('evaluation-recording-downstream-action', {'id':'evaluation-action:'+uuid.uuid4().hex,
                'gate_ref':ref,'at':utc_now(),'action':'started' if advanced else 'halted','scheduler_kind':'recording','invalid_for_product':True})
            if type(ctx) is EvaluationMeasurementContext:ctx.owner.register_capture(None,'recording_action',action_ref,request_ref=ctx.scope['request_ref'])
        return {'replay_id':'replay:'+uuid.uuid4().hex,'tier1_verdict':'PASS' if eligible else 'FAIL',
            'tier2_verdict':store.read_record(assessment)['verdict'] if assessment else 'NOT_RUN','gate_decision':decision,
            'advanced':advanced,'persisted_at':persisted,'downstream_action':'started' if advanced else 'halted' if case['record_gate'] else 'locked',
            'reason':measured.failure,'evidence_refs':evidence,'model_calls':calls}

    @staticmethod
    def _model_calls(ctx, measured, starts, *, replay):
        calls=[]
        contracts=[ctx.store.read_record(ref)['contract_ref'] for ref in measured.observation_refs]
        if not replay:contracts.append(ctx.contract_ref)
        for row in starts:
            start=row['record']
            if start.get('contract_ref') not in contracts:continue
            ref=ctx.store.record_ref(start['call_id']);call=ctx.store.read_record(ref,contract_id='model-call')
            require(call['invocation_id']==start['invocation_id'] and call['execution_id']==start['execution_id'], 'Call does not join its actual protected start')
            usage,identity=call['usage'],call['identity']
            unknown=call['outcome']=='outcome_unknown'
            require((call['ended_at'] is None)==unknown, 'ModelCall completion does not match its actual outcome')
            duration=None
            if not unknown:
                try:
                    duration=(datetime.fromisoformat(call['ended_at'].replace('Z','+00:00'))-datetime.fromisoformat(call['started_at'].replace('Z','+00:00'))).total_seconds()
                except (TypeError,ValueError,AttributeError):
                    raise ResearchError('evaluation_request','ModelCall completion chronology is unavailable') from None
                require(duration>=0,'ModelCall completion chronology is inconsistent')
            calls.append({'call_ref':ref,'role':call['call_function'] if call['call_function'] in {'compiler','planner','worker','verifier','router','delivery'} else 'other',
                'requested_model':identity['requested'],'effective_model':identity['effective'],'identity_basis':identity['basis'],
                'duration_s':duration,'outcome':call['outcome'],'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],
                'cost':{'amount':usage['cost_amount'],'currency':usage['currency']} if usage['cost_amount'] is not None else None})
        return calls


class InstalledEvaluationResources:
    """Literal admitted-measurement adapter for pre-captured campaign cases.

    Construction takes real protected resources and Refs, never configuration
    module names or caller callbacks. Readiness performs only validation reads.
    """
    def __init__(self, admitted, *, profile_ref, assets_ref, library_snapshot_ref):
        self.admitted, self.store = admitted, admitted.store
        self.profile_ref, self.assets_ref = copy.deepcopy(profile_ref), copy.deepcopy(assets_ref)
        self.profile = self.store.read_record(profile_ref, contract_id='evaluation-profile')
        self.assets = self.store.read_record(assets_ref)
        self.snapshot_ref = copy.deepcopy(library_snapshot_ref)
        self.store.read_record(library_snapshot_ref, contract_id='library-snapshot')
        require(library_snapshot_ref['sha256'] == self.profile['library_snapshot_sha256']
                and self.assets['profile_ref'] == profile_ref, 'Installed resources differ from the fixed profile snapshot')
        self._verifier()
        self.unavailable_reasons = {}
        self.provider=None;self.authority=None

    def bind_runtime(self,runtime_ref):
        from .evaluation_authority import EvaluationAuthority
        require(self.provider is not None,'Installed provider must be bound before private runtime')
        require(self.provider._history_runtime_ref in (None,runtime_ref),'Historical runtime cannot be replaced')
        require(self.authority is None or self.authority.runtime_ref==runtime_ref,'Runtime cannot be replaced')
        if self.authority is None:self.authority=EvaluationAuthority(self,runtime_ref)
        self.provider._bind_history_runtime(self, runtime_ref)
        return self.authority

    def _verifier(self):
        installed=self.admitted.resources.composition.installed['verifier']
        require(self.profile['verifier_cc_ref']==installed['declaration_ref'],
                'Profile verifier is not the actual installed independent reviewer')
        declaration=self.store.read_record(installed['declaration_ref'],contract_id='capsule-declaration')
        identity=declaration['identity'];pin=installed['pin']
        row=self.admitted.library.get(identity['name'],identity['version_label'])
        admitted=self.store.read_record(row['admission_ref'],contract_id='library-admission')
        require(row['declaration_ref']==installed['declaration_ref'] and admitted['status']=='admitted'
                and admitted['candidate_ref']==installed['declaration_ref'] and admitted['cc']==pin,
                'Installed reviewer is not the exact admitted version')
        return pin,identity['name']+'@'+identity['version_label']

    def _subject(self, case):
        if case['entry_point'] == 'E3':
            contract_ref = case['binding_ref']
            plans = [r['ref'] for r in self.store.iter_records(kinds=('bound-check-plan',))
                     if r['record']['contract_ref'] == contract_ref]
            require(len(plans) == 1, 'Single-CC binding has no unique exact checking plan')
            return contract_ref, plans[0], None
        capture = self.store.read_record(case['binding_ref'])
        require(isinstance(capture.get('output_refs'),dict) and 0<len(capture['output_refs'])<=64
                and all(text(name) for name in capture['output_refs']),'Invalid frozen replay output inventory')
        for ref in capture['output_refs'].values():self.store.read_blob(ref)
        fields={'id','contract_ref','check_plan_ref','output_refs','original_observation_ref','verifier_cc_id','host_records'}
        if capture.get('schema')=='ai4r-node-replay-binding:2':
            closed(capture,fields|{'schema','selected_output_port'})
            require(text(capture['selected_output_port']) and capture['selected_output_port'] in capture['output_refs'],
                    'Replay selected output is absent from its original capture')
        else:
            closed(capture,fields)
            require(len(capture['output_refs'])==1,'Legacy replay binding requires one original output')
        pin,version=self._verifier()
        require(capture['verifier_cc_id']==version,'Replay case names a different installed reviewer')
        subject=self.store.read_record(capture['contract_ref'],contract_id='subnode-execution-contract')
        parent=self.store.read_record(subject['node_contract_ref'],contract_id='node-execution-contract')
        reviewers=[]
        for assignment in parent['subnodes']:
            if assignment['role']!='verifier':continue
            template=self.store.read_record(assignment['template_ref'])
            if template.get('subject_subnode_id')==subject['subnode_id']:
                reviewers.append((assignment,template))
        require(bool(reviewers) and all(a['capsule_ref']==self.profile['verifier_cc_ref'] and t['cc']==pin for a,t in reviewers),
                'Frozen replay reviewer assignments differ from the approved installed version')
        return capture['contract_ref'], capture['check_plan_ref'], capture

    @property
    def available_entry_points(self):
        available = set();self.unavailable_reasons = {}
        for case in self.assets['cases']:
            if case['entry_point'] not in self.profile['allowed_entry_points']:continue
            try:
                self._verifier()
                contract, checks, replay = self._subject(case)
                self.admitted._validate(contract, checks, replay=replay is not None)
                if replay is not None:
                    check_plan = self.store.read_record(checks, contract_id='bound-check-plan')
                    review_profile = self.store.read_record(check_plan['profile_ref'], contract_id='checking-profile')
                    from .evidence_review import MODE
                    require(review_profile.get('review_mode') != MODE,
                        'Evidence-aware v2 review is not wired into evaluation replay', 'entry_point_unavailable')
                    self.admitted._host_records(replay['host_records'])
                    observed = self.store.read_record(replay['original_observation_ref'],contract_id='invocation-observation')
                    require(observed['contract_ref']==contract,'Replay has no exact original observation identity')
                    ordered_replay_outputs(replay['output_refs'],observed['output_refs'])
                available.add(case['entry_point'])
            except (ResearchError,KeyError) as error:
                self.unavailable_reasons[case['case_id']] = getattr(error,'code','protected_binding_unavailable')
        return tuple(p for p in ('E2','E3') if p in available)

    def _prepare(self, *, request, resolved, profile_ref, profile, entry_point):
        require(profile_ref == self.profile_ref and profile == self.profile, 'Installed measurement profile differs')
        cases=[c for c in self.assets['cases'] if c['case_id']==request['case_id'] and c['entry_point']==entry_point]
        require(len(cases)==1 and cases[0]['binding_ref']==resolved['case_binding_ref'], 'Installed case binding differs')
        contract, checks, replay = self._subject(cases[0])
        if replay is None:
            require(resolved['binding_ref']==contract, 'Externally supplied binding is not the exact canonical subject')
            grant=self.admitted.prepare(contract,checks,semantic_review=False)
        else:
            check_plan = self.store.read_record(checks, contract_id='bound-check-plan')
            review_profile = self.store.read_record(check_plan['profile_ref'], contract_id='checking-profile')
            from .evidence_review import MODE
            require(review_profile.get('review_mode') != MODE,
                'Evidence-aware v2 review is not wired into evaluation replay', 'entry_point_unavailable')
            port=replay.get('selected_output_port') or next(iter(replay['output_refs']))
            require(replay['output_refs'][port]==resolved['output_ref']
                    and replay['host_records']==resolved['host_records'], 'Request changed the frozen replay closure')
            grant=self.admitted.prepare_replay(contract,checks,replay['output_refs'],observation_ref=replay['original_observation_ref'],
                host_records=replay['host_records'],review_ports=[port])
        metadata=self.admitted.metadata(grant)
        metadata.replay_output_port=port if replay else None
        metadata.replay_host_records=copy.deepcopy(replay['host_records']) if replay else []
        metadata.evaluation_binding={'profile_ref':self.profile_ref,'configuration_ref':self.assets['configuration_ref'],
            'account_id':self.assets['account_id'],'workspace_id':self.assets['workspace_id'],'campaign_id':self.assets['campaign_id'],
            'verifier_cc_ref':self.profile['verifier_cc_ref'],'candidate_pins':self.profile['candidate_pins'],
            'model_route':self.profile['model_route'],'library_snapshot_ref':self.snapshot_ref}
        async def execute():return await self.admitted.execute(grant)
        return PreparedEvaluation(metadata,checks,execute)

    def prepare_single_cc(self, **kwargs):return self._prepare(**kwargs,entry_point='E3')
    def prepare_replay(self, **kwargs):return self._prepare(**kwargs,entry_point='E2')
