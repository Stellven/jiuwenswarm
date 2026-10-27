"""Durable, request-owned IF016 execution; never a product Run authority."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import math
import sqlite3
import time
import uuid
from types import SimpleNamespace

from .contracts import ResearchError, validate
from .evaluation_projection import EvaluationProjectionAdapter, private_record, require
from .measurement import measure_trial, all_mandatory_pass
from .state import json_bytes, utc_now


def identity(prefix): return prefix+':'+uuid.uuid4().hex
def encoded(value): return json_bytes(value).decode('utf-8')
def narrowed(*limits): return {key:min(value[key] for value in limits) for key in ('time_s','model_calls','memory_mb')}


def strict_original_request_body(request, original_body=None):
    """Validate exact wire bytes without claims, resources or new captures."""
    raw = json_bytes(request) if original_body is None else original_body
    require(type(raw) is bytes, 'Original strict UTF8 JSON bytes required', 'evaluation_request')
    def pairs(items):
        value = {}
        for key, val in items:
            require(key not in value, 'Duplicate original JSON key', 'evaluation_request')
            value[key] = val
        return value
    try:
        parsed = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError) as error:
        raise ResearchError('evaluation_request', 'Invalid original strict JSON body') from error
    require(parsed == request, 'Original and parsed request differ', 'evaluation_request')
    return raw


CAPTURE_KINDS = frozenset('original_request normalized_request runtime source_binding source_contract actual_contract check_plan input declaration implementation output deterministic_result review_context assessment verifier_check observation prompt route model_claim model_start model_call model_refusal tool_claim tool_observation trace workspace evaluation_gate recording_action containment measurement result failure'.split())
START_CAPTURE_KINDS=frozenset({'execution_preparation','execution_preflight','execution_activation'})
CAPTURE_KINDS=CAPTURE_KINDS|START_CAPTURE_KINDS
PRIVATE_EVIDENCE = {'observation':'evaluation-invocation-observation', 'deterministic_result':'evaluation-deterministic-check-result',
    'verifier_check':'evaluation-deterministic-check-result', 'review_context':'evaluation-review-context',
    'assessment':'evaluation-verifier-assessment', 'measurement':'evaluation-trial-measurement'}
NATIVE_KINDS = {'model-call-start':'model_start','model-call':'model_call','route-record':'route',
    'model-call-refused':'model_refusal','model-call-input':'prompt','model-call-output':'output',
    'model-provider-observation':'tool_observation','native-governed-trace':'trace',
    'native-governed-trace-event':'trace'}


def validate_evaluation_executor_binding(store, request, response, *, _prepared=False):
    """Read-only custody check AFTER the live owner authorizes this operation.

    A stored registration is not process liveness. The caller must obtain the
    six-field response from the live protected authorizer on every operation;
    this independent check confirms its immutable and durable ownership joins.
    It neither registers an owner nor claims/renews any execution allowance.
    """
    fields = {'contract_ref', 'invocation_id', 'execution_id'}
    require(type(request) is dict and set(request) == fields
        and type(response) is dict and set(response) == fields | {
            'contract', 'execution_deadline_monotonic_s', 'remaining_time_s'}
        and all(response[k] == request[k] for k in fields), 'Malformed exact private executor response')
    child = private_record(store, request['contract_ref'], 'evaluation-subnode-context')
    require(response['contract'] == child, 'Executor response differs from immutable private context')
    try:
        with store._lock:
            assignment = store.connection.execute('SELECT * FROM evaluation_assignments WHERE execution_id=?',
                (request['execution_id'],)).fetchone()
            row = store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',
                (encoded(child['request_ref']),)).fetchone()
            owner = store.connection.execute('SELECT boot FROM evaluation_owner_boots WHERE runtime=?',
                (row['runtime'],)).fetchone() if row else None
    except sqlite3.Error as error:
        raise ResearchError('evaluation_authority', 'Durable private executor ownership is unavailable') from error
    require(assignment is not None and row is not None and owner is not None,
        'Executor context has no exact durable owner')
    require(owner['boot'] == row['boot'] and row['cancel_id'] is None
        and row['state'] in ({'prepared','executing'} if _prepared else {'executing'}) and row['terminal_ref'] is None
        and assignment['state'] == ('prepared' if _prepared else 'started'), 'Private executor owner is stopped or reconstructed',
        'evaluation_outcome_unknown')
    grant_ref = json.loads(assignment['grant_ref'])
    grant = private_record(store, grant_ref, 'evaluation-assignment-grant')
    source_request = private_record(store, child['request_ref'], 'evaluation-request')
    runtime = private_record(store, source_request['runtime_ref'], 'evaluation-runtime')
    scope_ref = json.loads(row['scope_ref']) if row['scope_ref'] else None
    require(scope_ref is not None, 'Private executor request has no bound scope')
    scope = private_record(store, scope_ref, 'evaluation-scope')
    parent = private_record(store, scope['actual_node_ref'], 'evaluation-node-context')
    basis = private_record(store, grant['check_plan_ref'], 'evaluation-checking-basis')
    require(all(grant[k] == request[k] for k in fields)
        and grant['request_ref'] == scope['request_ref'] == child['request_ref'] == parent['request_ref'] == basis['request_ref']
        and grant['scope_ref'] == scope_ref and child['node_contract_ref'] == scope['actual_node_ref']
        and basis['assignment_context_ref'] == request['contract_ref'] and basis['node_context_ref'] == scope['actual_node_ref']
        and assignment['request_ref'] == encoded(child['request_ref'])
        and assignment['role'] == child['role'] == grant['role']
        and assignment['port'] == (child['output_port'] or '') and child['output_port'] == grant['output_port'],
        'Private executor assignment/context/basis ownership differs')
    require(row['runtime'] == encoded(source_request['runtime_ref'])
        and row['slot'] == source_request['slot_id'] and row['fingerprint'] == source_request['fingerprint']
        and row['started_ns'] == source_request['started_unix_ns'] and row['deadline_ns'] == source_request['deadline_unix_ns']
        and row['identity'] == encoded([runtime[k] for k in ('account_id', 'workspace_id', 'campaign_id',
            'profile_ref', 'configuration_ref')] + [source_request['request_id']]),
        'Private executor request differs from its original durable slot')
    slots = [s for s in runtime['slots'] if s['slot_id'] == source_request['slot_id']]
    require(len(slots) == 1 and all(slots[0][k] == source_request[k] for k in ('request_id', 'entry_point', 'case_id'))
        and slots[0]['request_sha256'] == source_request['fingerprint'] and slots[0]['limits'] == source_request['limits'],
        'Private executor request is outside its approved slot')
    require(scope['private_run_id'] == parent['run_id'] == child['run_id']
        and child['node_id'] == parent['node_id'] and child['attempt_id'] == parent['attempt_id']
        and child['configuration_ref'] == parent['configuration_ref'] == runtime['configuration_ref']
        and child['policy_ref'] == parent['policy_ref'] == runtime['policy_ref']
        and grant['source_contract_ref'] == scope['source_contract_ref'] == child['source_subject_ref']
        and parent['source_contract_ref'] == scope['source_contract_ref'],
        'Private executor source/parent/configuration provenance differs')
    require(store.record_kind(scope['source_contract_ref']) == 'subnode-execution-contract'
        and store.record_kind(scope['source_check_plan_ref']) == 'bound-check-plan',
        'Private executor has no canonical original source provenance')
    source = store.read_record(scope['source_contract_ref'], contract_id='subnode-execution-contract')
    require(source['node_contract_ref'] == parent['source_node_ref']
        and scope['source_check_plan_ref'] == parent['source_check_plan_ref'] == basis['source_check_plan_ref']
        and all(record['started_unix_ns'] == source_request['started_unix_ns']
            and record['deadline_unix_ns'] == source_request['deadline_unix_ns'] for record in (parent, scope))
        and grant['deadline_unix_ns'] == source_request['deadline_unix_ns'],
        'Private executor source/time provenance differs')
    require(len(child['bindings']) == 1 and child['bindings'][0]['limits'] == grant['limits'],
        'Private executor binding/limits differ')
    for key in ('time_s', 'model_calls', 'memory_mb'):
        require(grant['limits'][key] <= child['subnode_limits'][key] <= parent['node_limits'][key]
            and grant['limits'][key] <= source_request['limits'][key], 'Private executor limits were widened')
    deadline, remaining = response['execution_deadline_monotonic_s'], response['remaining_time_s']
    require(type(deadline) in (int, float) and type(remaining) in (int, float)
        and math.isfinite(deadline) and math.isfinite(remaining) and remaining > 0,
        'Private executor response has no finite active time bound', 'budget_exhausted')
    now_mono, now_wall = time.monotonic(), time.time_ns()
    require(deadline > now_mono and source_request['deadline_unix_ns'] > now_wall,
        'Original private executor deadline expired', 'budget_exhausted')
    # Allow only serialization/scheduling time to consume the returned remaining
    # bound. The live response never increases the original absolute deadline.
    require(deadline <= now_mono + grant['limits']['time_s'] + .01
        and deadline <= now_mono + (source_request['deadline_unix_ns'] - now_wall) / 1e9 + .01
        and remaining <= grant['limits']['time_s'] + .01,
        'Private executor response widened original time authority', 'budget_exhausted')
    return child


def capture_evaluation_native(store,kind,record,*,context):
    """Capture-only reconstruction from protected dispatch context.

    This function grants no dispatch and needs no executable resources. Exact
    durable joins allow late failure/containment evidence after expiry/restart.
    The caller supplies the already-authorized private context, never user JSON.
    """
    fields={'execution_id','invocation_id','call_id','call_claim_ref','contract_ref'}
    require(isinstance(context,dict) and set(context) in (fields,fields|{'model_call_start_ref'})
            and kind in NATIVE_KINDS and isinstance(record,dict),'Malformed finite private native capture')
    claim=private_record(store,context['call_claim_ref'],'evaluation-call-claim')
    require(all(claim[k]==context[k] for k in fields-{'call_claim_ref'}),'Native capture differs from protected call claim')
    with store._lock:
        row=store.connection.execute('SELECT * FROM evaluation_calls WHERE execution_id=? AND call_id=?',
            (context['execution_id'],context['call_id'])).fetchone()
        assignment=store.connection.execute('SELECT * FROM evaluation_assignments WHERE execution_id=?',(context['execution_id'],)).fetchone()
        request_row=store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',(encoded(claim['request_ref']),)).fetchone()
    require(row is not None and json.loads(row['claim_ref'])==context['call_claim_ref'] and assignment is not None
            and json.loads(assignment['grant_ref'])==claim['assignment_grant_ref'] and request_row is not None,
            'Native capture has no durable private claim/assignment/request')
    grant=private_record(store,claim['assignment_grant_ref'],'evaluation-assignment-grant')
    scope=private_record(store,grant['scope_ref'],'evaluation-scope')
    request=private_record(store,grant['request_ref'],'evaluation-request')
    runtime=private_record(store,request['runtime_ref'],'evaluation-runtime')
    child=private_record(store,grant['contract_ref'],'evaluation-subnode-context')
    basis=private_record(store,grant['check_plan_ref'],'evaluation-checking-basis')
    parent=private_record(store,scope['actual_node_ref'],'evaluation-node-context')
    require(grant['contract_ref']==context['contract_ref'] and grant['invocation_id']==context['invocation_id']
            and grant['execution_id']==context['execution_id'] and grant['request_ref']==claim['request_ref']==scope['request_ref']==child['request_ref']==basis['request_ref']==parent['request_ref']
            and basis['assignment_context_ref']==grant['contract_ref'] and child['node_contract_ref']==scope['actual_node_ref']
            and request_row['runtime']==encoded(request['runtime_ref']) and json.loads(request_row['scope_ref'])==grant['scope_ref']
            and request_row['fingerprint']==request['fingerprint'] and runtime['configuration_ref']==child['configuration_ref'],
            'Private native context provenance differs')
    for key,expected in {'execution_id':context['execution_id'],'invocation_id':context['invocation_id'],
            'run_id':scope['private_run_id'],'call_id':context['call_id'],'contract_ref':context['contract_ref']}.items():
        if key in record:require(record[key]==expected,'Native packet belongs to another private identity')
    if kind=='model-call':require(record.get('id')==context['call_id'],'Native ModelCall ID differs')
    if kind=='model-call-start':require(record.get('call_claim_ref')==context['call_claim_ref'],'Native start claim differs')
    if kind.startswith('native-governed-trace'):
        expected_scope={**{k:child[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
            **{k:context[k] for k in ('execution_id','invocation_id','call_id','contract_ref')}}
        require(isinstance(record.get('scope'),dict) and all(record['scope'].get(k)==v for k,v in expected_scope.items()),'Native trace scope differs')
        start_ref=record['scope'].get('model_call_start_ref')
        require(start_ref is not None and store.record_kind(start_ref)=='model-call-start','Native trace has no actual start')
        start=store.read_record(start_ref)
        require(start.get('execution_id')==context['execution_id'] and start.get('call_id')==context['call_id']
                and start.get('call_claim_ref')==context['call_claim_ref'],'Native trace start differs')
    if kind in {'model-call','route-record'}:validate(kind,record)
    ref=store.append_record(kind,record)
    with store._lock:
        row=store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',(encoded(grant['request_ref']),)).fetchone()
        event={'schema':'ai4r-evaluation-event:1','id':identity('evaluation-event'),'request_ref':grant['request_ref'],
            'scope_ref':grant['scope_ref'],'sequence':row['sequence']+1,'previous_event_ref':json.loads(row['head_ref']) if row['head_ref'] else None,
            'kind':'captured','assignment_grant_ref':claim['assignment_grant_ref'],'capture_kind':NATIVE_KINDS[kind],
            'capture_ref':ref,'reason':None,'recorded_unix_ns':time.time_ns(),'accepted':False,'invalid_for_product':True}
        validate('urn:ai4r:private:evaluation-event:1',event);event_ref=store.append_record('evaluation-event',event)
        with store.transaction() as db:
            require(db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=? WHERE request_ref=? AND sequence=?',
                (encoded(event_ref),event['sequence'],encoded(grant['request_ref']),row['sequence'])).rowcount==1,
                'Private native journal publication conflicted','audit_unavailable')
    return ref


class EvaluationAuthority:
    def __init__(self, resources, runtime_ref):
        # This is installed construction from actual protected resources, never
        # an object deserialized from a request or a configurable module name.
        from .evaluation_provider import InstalledEvaluationResources
        require(type(resources) is InstalledEvaluationResources, 'Actual installed evaluation resources required')
        self.resources, self.store = resources, resources.store
        self.runner = resources.admitted.runner
        self.runtime_ref = copy.deepcopy(runtime_ref)
        self.runtime = private_record(self.store, runtime_ref, 'evaluation-runtime')
        self.provider = resources.provider
        self._boot = identity('owner-boot'); self._deadlines = {}; self._scope_refs = {}; self._registered = False
        self._failure_cleanups = {}
        with self.store._lock:
            self.store.connection.executescript('''
              CREATE TABLE IF NOT EXISTS evaluation_requests (
                runtime TEXT NOT NULL,slot TEXT NOT NULL,identity TEXT NOT NULL UNIQUE,
                fingerprint TEXT NOT NULL,request_ref TEXT,scope_ref TEXT,terminal_ref TEXT,
                state TEXT NOT NULL,boot TEXT NOT NULL,started_ns INTEGER NOT NULL,deadline_ns INTEGER NOT NULL,
                cancel_id TEXT,head_ref TEXT,sequence INTEGER NOT NULL DEFAULT -1,
                PRIMARY KEY(runtime,slot));
              CREATE TABLE IF NOT EXISTS evaluation_assignments (
                execution_id TEXT PRIMARY KEY,request_ref TEXT NOT NULL,role TEXT NOT NULL,port TEXT NOT NULL,
                grant_ref TEXT NOT NULL,state TEXT NOT NULL,UNIQUE(request_ref,role,port));
              CREATE TABLE IF NOT EXISTS evaluation_calls (
                execution_id TEXT NOT NULL,ordinal INTEGER NOT NULL,call_id TEXT NOT NULL UNIQUE,
                claim_ref TEXT NOT NULL,protected TEXT NOT NULL,PRIMARY KEY(execution_id,ordinal));
              CREATE TABLE IF NOT EXISTS evaluation_tools (
                execution_id TEXT NOT NULL,ordinal INTEGER NOT NULL,claim_ref TEXT NOT NULL,
                PRIMARY KEY(execution_id,ordinal));
              CREATE TABLE IF NOT EXISTS evaluation_owner_boots (
                runtime TEXT PRIMARY KEY,boot TEXT NOT NULL);
            ''')
        self.projection = EvaluationProjectionAdapter(self)
        self._current_runtime()
        self.runner.register_evaluation_owner(self)
        with self.store.transaction() as db:
            db.execute('INSERT INTO evaluation_owner_boots(runtime,boot) VALUES (?,?) '
                'ON CONFLICT(runtime) DO UPDATE SET boot=excluded.boot',(encoded(self.runtime_ref),self._boot))
        self._registered = True

    def _current_runtime(self):
        r = private_record(self.store,self.runtime_ref,'evaluation-runtime')
        require(r == self.runtime, 'Protected evaluation runtime changed')
        if self._registered:
            with self.store._lock:
                owner = self.store.connection.execute('SELECT boot FROM evaluation_owner_boots WHERE runtime=?',
                    (encoded(self.runtime_ref),)).fetchone()
            require(owner is not None and owner['boot'] == self._boot,
                'Private owner was reconstructed; historical inspection only', 'evaluation_outcome_unknown')
        p = self.provider
        require(self.store.read_record(p.assets_ref)==p.assets and self.store.read_record(p.profile_ref,contract_id='evaluation-profile')==p.profile,
                'Current protected profile/assets changed')
        require(self.resources.admitted.resources.operator.snapshot()==p.operator,'Protected operator configuration changed')
        expected = self.resources.admitted.resources.exact_binding_refs
        require(all(r[k] == p.assets[k] for k in ('account_id','workspace_id','campaign_id','configuration_ref'))
                and r['assets_ref'] == p.assets_ref and r['profile_ref'] == p.profile_ref
                and r['library_snapshot_ref'] == self.resources.snapshot_ref
                and all(r[k] == expected[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')),
                'Private runtime differs from actual protected startup')
        require(r['policy_ref'] == p.operator['cc']['plan_policy_ref'], 'Private policy differs from startup')
        selection = self.store.read_record(r['model_selection_profile_ref'],contract_id='model-selection-profile')
        require(selection['policy_mode']=='fixed_baseline' and p.operator['cc']['router']['enabled'] is False,
                'Qualified evaluation routing adapter is unavailable', 'entry_point_unavailable')
        slots = r['slots']
        if r.get('account_model_selection_ref') is not None:
            from .evaluation_model_binding import source_model_selection
            for case in p.assets['cases']:
                source_ref = self.resources._subject(case)[0]
                source = self.store.read_record(source_ref, contract_id='subnode-execution-contract')
                source_model_selection(self.store, r['account_model_selection_ref'],
                    account_id=r['account_id'], source_run_id=source['run_id'])
        require(len({s['slot_id'] for s in slots})==len(slots) and len({s['request_id'] for s in slots})==len(slots),
                'Approved request slots are ambiguous')
        self.store.read_blob(r['schedule_ref'])
        return r

    def _row(self, request_ref):
        with self.store._lock:
            row=self.store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',(encoded(request_ref),)).fetchone()
        require(row is not None, 'Request is not durably registered')
        return row

    def _request(self, ref):
        value=private_record(self.store,ref,'evaluation-request'); row=self._row(ref)
        require(value['runtime_ref']==self.runtime_ref and row['runtime']==encoded(self.runtime_ref)
                and value['slot_id']==row['slot'] and value['fingerprint']==row['fingerprint']
                and value['started_unix_ns']==row['started_ns'] and value['deadline_unix_ns']==row['deadline_ns'],
                'Request differs from its durable first claim')
        return value

    def _active(self,ref):
        request=self._request(ref);row=self._row(ref);self._current_runtime()
        require(row['boot']==self._boot, 'Restarted requests permit inspection/containment only','evaluation_outcome_unknown')
        require(row['state'] in {'claimed','prepared','executing'} and row['cancel_id'] is None,
                'Request is stopped or already consumed','evaluation_outcome_unknown')
        remaining=min((request['deadline_unix_ns']-time.time_ns())/1e9,self._deadlines[encoded(ref)]-time.monotonic())
        require(remaining>0,'Original whole-request deadline expired','budget_exhausted')
        return request,remaining

    def _scope(self,ref):
        scope=private_record(self.store,ref,'evaluation-scope');row=self._row(scope['request_ref'])
        require(row['scope_ref'] is not None and json.loads(row['scope_ref'])==ref,'Scope is not the exact registered request scope')
        node=private_record(self.store,scope['actual_node_ref'],'evaluation-node-context')
        require(node['request_ref']==scope['request_ref'] and node['run_id']==scope['private_run_id'], 'Private parent ownership differs')
        return scope

    def _assignment(self,execution_id):
        with self.store._lock:
            return self.store.connection.execute('SELECT * FROM evaluation_assignments WHERE execution_id=?',(execution_id,)).fetchone()

    def owns_execution(self,execution_id):
        row=self._assignment(execution_id)
        if row is None:return False
        self.projection.load_execution(json.loads(row['grant_ref']))
        return True

    def owns_run(self,run_id):
        # Exact durable scope Refs, never an ID-prefix or a global record scan.
        with self.store._lock:
            rows=self.store.connection.execute('SELECT scope_ref FROM evaluation_requests WHERE runtime=? AND scope_ref IS NOT NULL',(encoded(self.runtime_ref),)).fetchall()
        return any(self._scope(json.loads(row[0]))['private_run_id']==run_id for row in rows)

    def accept_request(self,principal,request,entry_point,*,original_body=None):
        normalized,_,_=self.provider._validate(principal,request,entry_point)
        r=self._current_runtime();fingerprint=hashlib.sha256(json_bytes([entry_point,normalized])).hexdigest()
        matches=[s for s in r['slots'] if s['request_id']==normalized['request_id']]
        require(len(matches)==1 and matches[0]['entry_point']==entry_point and matches[0]['case_id']==normalized['case_id']
                and matches[0]['request_sha256']==fingerprint,'Request is outside the approved finite slots','evaluation_slot')
        slot=matches[0]
        # The API adapter must pass original HTTP bytes. Controlled direct calls
        # use canonical JSON as their actual original body, with no claimed wire provenance.
        raw = strict_original_request_body(request, original_body)
        key=encoded([r[k] for k in ('account_id','workspace_id','campaign_id','profile_ref','configuration_ref')]+[normalized['request_id']])
        now=time.time_ns();deadline=now+int(slot['limits']['time_s']*1e9)
        # First durable claim precedes all captures/preparation. An interrupted
        # claim with no bound Ref remains consumed and cannot acquire a new time.
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM evaluation_requests WHERE identity=? OR (runtime=? AND slot=?)',(key,encoded(self.runtime_ref),slot['slot_id'])).fetchone()
            if row is not None:
                require(row['identity']==key and row['runtime']==encoded(self.runtime_ref) and row['fingerprint']==fingerprint,
                        'Request identity or consumed slot conflict','identity_conflict')
                require(row['request_ref'] is not None,'Initial request claim is uncertain','evaluation_outcome_unknown')
                return json.loads(row['request_ref'])
            db.execute('INSERT INTO evaluation_requests(runtime,slot,identity,fingerprint,state,boot,started_ns,deadline_ns) VALUES (?,?,?,?,?,?,?,?)',
                (encoded(self.runtime_ref),slot['slot_id'],key,fingerprint,'claiming',self._boot,now,deadline))
        original=self.store.put_blob(raw,media_type='application/json');normal=self.store.put_blob(json_bytes(normalized),media_type='application/json')
        record=dict(schema='ai4r-evaluation-request:1',id=identity('evaluation-request'),runtime_ref=self.runtime_ref,slot_id=slot['slot_id'],
            request_id=normalized['request_id'],entry_point=entry_point,case_id=normalized['case_id'],original_request_ref=original,
            normalized_request_ref=normal,fingerprint=fingerprint,started_unix_ns=now,deadline_unix_ns=deadline,limits=slot['limits'],accepted=False,invalid_for_product=True)
        ref=self._put('evaluation-request',record)
        with self.store.transaction() as db:
            changed=db.execute("UPDATE evaluation_requests SET request_ref=?,state='claimed' WHERE identity=? AND state='claiming' AND request_ref IS NULL",(encoded(ref),key)).rowcount
            require(changed==1,'Request claim binding was lost','evaluation_outcome_unknown')
        self._deadlines[encoded(ref)]=time.monotonic()+max(0,(deadline-time.time_ns())/1e9)
        self.event(ref,'claimed')
        for kind,pin in [('original_request',original),('normalized_request',normal),('runtime',self.runtime_ref)]:self.register_capture(None,kind,pin,request_ref=ref)
        return ref

    def _put(self,kind,value):
        version='2' if kind=='evaluation-event' and value.get('schema')=='ai4r-evaluation-event:2' else '1'
        validate('urn:ai4r:private:'+kind+':'+version,value)
        return self.store.append_record(kind,value)

    def event(self,request_ref,kind,*,scope_ref=None,grant_ref=None,capture_kind=None,capture_ref=None,reason=None):
        self._request(request_ref)
        with self.store._lock:
            row=self._row(request_ref)
            record={'schema':'ai4r-evaluation-event:'+('2' if capture_kind in START_CAPTURE_KINDS else '1'),'id':identity('evaluation-event'),'request_ref':request_ref,
                'scope_ref':scope_ref if scope_ref is not None else (json.loads(row['scope_ref']) if row['scope_ref'] else None),
                'sequence':row['sequence']+1,'previous_event_ref':json.loads(row['head_ref']) if row['head_ref'] else None,
                'kind':kind,'assignment_grant_ref':grant_ref,'capture_kind':capture_kind,'capture_ref':capture_ref,'reason':reason,
                'recorded_unix_ns':time.time_ns(),'accepted':False,'invalid_for_product':True}
            ref=self._put('evaluation-event',record)
            with self.store.transaction() as db:
                changed=db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=? WHERE request_ref=? AND sequence=?',
                    (encoded(ref),record['sequence'],encoded(request_ref),row['sequence'])).rowcount
                require(changed==1,'Private journal head changed','audit_unavailable')
        return ref

    def register_capture(self,grant_ref,kind,ref,*,request_ref=None):
        require(kind in CAPTURE_KINDS,'Unknown private capture class')
        self.store.read_blob(ref)
        if grant_ref is not None:
            grant,_,_=self.projection.load_execution(grant_ref)
            require(request_ref is None or request_ref==grant['request_ref'],'Capture request differs')
            request_ref=grant['request_ref']
        require(request_ref is not None,'Explicit durable capture owner required')
        if kind in PRIVATE_EVIDENCE:require(self.store.record_kind(ref)==PRIVATE_EVIDENCE[kind],'Private evidence kind differs')
        return self.event(request_ref,'captured',grant_ref=grant_ref,capture_kind=kind,capture_ref=ref)

    def captures(self,request_ref,kind=None):
        row=self._row(request_ref);ref=json.loads(row['head_ref']) if row['head_ref'] else None;result=[];sequence=row['sequence']
        while ref is not None:
            event=private_record(self.store,ref,'evaluation-event')
            require(event['request_ref']==request_ref and event['sequence']==sequence,'Private journal chain is corrupt')
            if event['kind']=='captured' and (kind is None or event['capture_kind']==kind):result.append(event)
            ref=event['previous_event_ref'];sequence-=1
        require(sequence==-1,'Private journal is incomplete')
        return list(reversed(result))

    def _source(self,request_ref):
        request=self._request(request_ref);normal=self.store.read_record(request['normalized_request_ref'])
        cases=[c for c in self.resources.assets['cases'] if c['case_id']==request['case_id'] and c['entry_point']==request['entry_point']]
        require(len(cases)==1,'No exact approved source binding')
        source_ref,plan_ref,replay=self.resources._subject(cases[0]);store=self.store
        require(store.record_kind(source_ref)=='subnode-execution-contract' and store.record_kind(plan_ref)=='bound-check-plan','Original canonical provenance required')
        source=store.read_record(source_ref,contract_id='subnode-execution-contract');plan=store.read_record(plan_ref,contract_id='bound-check-plan')
        parent=store.read_record(source['node_contract_ref'],contract_id='node-execution-contract');b=source['bindings'][0]
        require(len(source['bindings'])==1 and b['role']=='work' and plan['contract_ref']==source_ref and plan['node_contract_ref']==source['node_contract_ref'], 'Original source/check identity differs')
        decl=store.read_record(b['declaration_ref'],contract_id='capsule-declaration');row=self.resources.admitted.library.get(decl['identity']['name'],decl['identity']['version_label'])
        admission=store.read_record(b['admission_ref'],contract_id='library-admission')
        require(row['declaration_ref']==b['declaration_ref'] and row['admission_ref']==b['admission_ref'] and admission['status']=='admitted'
                and admission['candidate_ref']==b['declaration_ref'] and b['implementation_refs']==[row['body_refs'][p['path']] for p in decl['identity']['body']], 'Original admission/body closure differs')
        require(row['standing'] not in {'revoked','suspended'},'Original admitted subject is no longer eligible')
        self.resources.admitted.library.eligible_association(b['declaration_ref'])
        dependencies=[row['body_refs'][pin['ref']] for dependency in decl['needs']['external'] for key in ('pin','lockfile') if (pin:=dependency.get(key))]
        require(b['dependency_refs']==dependencies,'Original dependency closure changed')
        for pin in [*b['implementation_refs'],*dependencies]:store.read_blob(pin)
        snapshot=store.read_record(self.runtime['library_snapshot_ref'],contract_id='library-snapshot')
        require((decl['identity']['name'],decl['identity']['version_label'],b['declaration_ref']['sha256']) in
                {(p['cc_name'],p['cc_version'],p['declaration_sha256']) for p in snapshot['entries']},'Source subject is outside the frozen snapshot')
        from .contracts import contract_schema
        for direction in ('inputs','outputs'):
            expected={p['name']:p for p in decl['ports'][direction]};actual=source[direction]
            require(len(actual)==len({p['name'] for p in actual}) and {p['name'] for p in actual}==set(expected)
                    and all(p['required']==expected[p['name']]['required'] and contract_schema(p['contract_id'])==contract_schema(expected[p['name']]['schema_ref']) for p in actual),
                    'Original ports differ from admitted declaration')
        per=decl['budget']['per_call'];calls=per['invocations'] if any(i['service_key']=='audited_model_bridge' for i in decl['needs']['injects']) else 0
        ceilings={'time_s':per['wall_s'],'model_calls':calls,'memory_mb':admission['memory_mb']}
        require(all(source['subnode_limits'][k]<=min(parent['node_limits'][k],ceilings[k]) and b['limits'][k]<=min(parent['node_limits'][k],ceilings[k]) for k in ceilings),
                'Source invocation widened declaration/parent limits')
        authority=b['effective_authority'];ceiling=parent['authority_ceiling'];network=decl['needs']['network']
        require(all(value in ceiling[key] for key in ('network_allowlist','resource_reads','write_roots','tools') for value in authority[key])
                and (authority['network']=='none' or ceiling['network']=='allowlist' and network['mode']=='allowlist'
                    and all(value in network['allowlist'] for value in authority['network_allowlist'])),'Original authority widens the admitted source')
        require(source['configuration_ref']==parent['configuration_ref']==self.runtime['configuration_ref']
                and source['policy_ref']==parent['policy_ref']==plan['policy_ref']==self.runtime['policy_ref'], 'Original policy/configuration differs')
        self.runner._require_check_assets(source)
        template=store.read_record(source['template_ref']);bundle=store.read_record(template['check_bundle_ref'],contract_id='check-bundle')
        required={c['check_id'] for c in bundle['checks'] if c['blocking']}|{'host_contract','host_identity','host_limits','host_authority'}
        require(required<=set(plan['mandatory_deterministic']) and len(plan['mandatory_deterministic'])==len(set(plan['mandatory_deterministic']))
                and plan['profile_ref']==source['checking_profile_ref'] and template['check_bundle_ref'] in plan['runner_refs'],'Original mandatory check coverage changed')
        profile=store.read_record(plan['profile_ref'],contract_id='checking-profile')
        require(len(plan['mandatory_semantic'])==len(set(plan['mandatory_semantic']))
                and set(plan['mandatory_semantic'])=={c['criterion_id'] for c in profile['criteria'] if c['blocking']},'Original semantic criteria changed')
        policy=store.read_record(self.runtime['policy_ref'],contract_id='plan-policy')
        require(all(request['limits'][k]<=min(parent['node_limits'][k],policy['aggregate_limits'][k]) for k in request['limits']), 'Request widens approved aggregate ceilings')
        if replay is not None:
            self.resources.admitted._host_records(replay['host_records'])
            observed=store.read_record(replay['original_observation_ref'],contract_id='invocation-observation')
            require(store.record_kind(replay['original_observation_ref'])=='invocation-observation' and observed['contract_ref']==source_ref,'Original replay observation differs')
            from .measurement import ordered_replay_outputs
            replay=copy.deepcopy(replay);replay['output_refs']=ordered_replay_outputs(replay['output_refs'],observed['output_refs'])
            selected=replay.get('selected_output_port') or next(iter(replay['output_refs']))
            supplied_hosts=[{'record_type':h['record_type'],'ref':self.provider._asset({k:h[k] for k in ('path','sha256')},'host_'+h['record_type'])} for h in normal['host_records']]
            require(normal['node_id']==source['node_id'] and normal['verifier_cc_id']==replay['verifier_cc_id']
                and self.provider._asset(normal['declaration'],'declaration')==b['declaration_ref']
                and self.provider._asset(normal['output'],'output')==replay['output_refs'][selected]
                and supplied_hosts==replay['host_records'],'Replay request differs from exact original subject/output/host closure')
        else:
            supplied_inputs=[(p['port'],self.provider._asset({k:p[k] for k in ('path','sha256')},'input')) for p in normal['inputs']]
            require(supplied_inputs==[(p['name'],ref) for p in source['inputs'] for ref in p['artifact_refs']]
                and (normal['capsule_id'],normal['capsule_version'],normal['capsule_declaration_sha256'])
                    ==(decl['identity']['name'],decl['identity']['version_label'],b['declaration_ref']['sha256']),
                'Single request differs from exact named input/declaration binding')
        return source,plan,parent,template,bundle,(source_ref,plan_ref,cases[0],replay,normal)

    def _create_node(self,request_ref):
        request,_=self._active(request_ref);source,_,parent,_,_,extra=self._source(request_ref)
        source_ref,plan_ref,case,_,_=extra
        keys='node_id objective requirement_ids inputs outputs input_refs required_outputs evidence_obligations authority_ceiling subnodes checking_profile_ref policy_ref configuration_ref'.split()
        node={k:copy.deepcopy(parent[k]) for k in keys}
        node.update(schema='ai4r-evaluation-node-context:1',id=identity('evaluation-node'),request_ref=request_ref,
            source_binding_ref=case['binding_ref'],source_contract_ref=source_ref,source_node_ref=source['node_contract_ref'],
            source_template_ref=parent['template_ref'],source_check_plan_ref=plan_ref,run_id=identity('evaluation-run'),
            attempt_id=parent['node_id']+'-a1',revision=1,node_limits=narrowed(parent['node_limits'],request['limits']),
            started_unix_ns=request['started_unix_ns'],deadline_unix_ns=request['deadline_unix_ns'],accepted=False,invalid_for_product=True)
        return self._put('evaluation-node-context',node)

    def prepare(self,request_ref):
        request,_=self._active(request_ref);row=self._row(request_ref)
        if row['scope_ref']:return json.loads(row['scope_ref'])
        source,_,_,_,_,extra=self._source(request_ref);source_ref,plan_ref,case,replay,_=extra
        node_ref=self.projection.create_node_context(request_ref);node=private_record(self.store,node_ref,'evaluation-node-context')
        scope={'schema':'ai4r-evaluation-scope:1','id':identity('evaluation-scope'),'request_ref':request_ref,
            'source_binding_ref':case['binding_ref'],'source_contract_ref':source_ref,'source_check_plan_ref':plan_ref,
            'source_observation_ref':replay['original_observation_ref'] if replay else None,'source_output_refs':list(replay['output_refs'].values()) if replay else [],
            'selected_output_port':(replay.get('selected_output_port') or next(iter(replay['output_refs']))) if replay else None,
            'private_run_id':node['run_id'],'actual_node_ref':node_ref,'limits':request['limits'],
            'started_unix_ns':request['started_unix_ns'],'deadline_unix_ns':request['deadline_unix_ns'],'accepted':False,'invalid_for_product':True}
        ref=self._put('evaluation-scope',scope)
        with self.store.transaction() as db:
            require(db.execute("UPDATE evaluation_requests SET scope_ref=?,state='prepared' WHERE request_ref=? AND scope_ref IS NULL AND state='claimed'",(encoded(ref),encoded(request_ref))).rowcount==1,'Scope preparation already claimed','evaluation_outcome_unknown')
        self.event(request_ref,'prepared',scope_ref=ref)
        for kind,pin in [('source_binding',case['binding_ref']),('source_contract',source_ref),('actual_contract',node_ref)]:self.register_capture(None,kind,pin,request_ref=request_ref)
        for kind,pins in [('declaration',[source['bindings'][0]['declaration_ref']]),
                ('implementation',source['bindings'][0]['implementation_refs']),('input',source['input_refs'])]:
            for pin in pins:self.register_capture(None,kind,pin,request_ref=request_ref)
        return ref

    def _assignment_projection(self,scope,role,port,*,child_id,basis_id,child_ref=None):
        request=self._request(scope['request_ref']);source,plan,_,template,_,_=self._source(scope['request_ref'])
        node=private_record(self.store,scope['actual_node_ref'],'evaluation-node-context')
        if role == 'verifier':
            return self._reviewer_projection(scope, port, child_id=child_id, basis_id=basis_id, child_ref=child_ref)
        require(role=='worker' and port is None and request['entry_point']=='E3','Requested private assignment adapter is unavailable','entry_point_unavailable')
        child={k:copy.deepcopy(source[k]) for k in 'node_id subnode_id objective requirement_ids bindings inputs outputs input_refs required_outputs evidence_obligations checking_profile_ref policy_ref configuration_ref'.split()}
        child.update(schema='ai4r-evaluation-subnode-context:1',id=child_id,request_ref=scope['request_ref'],node_contract_ref=scope['actual_node_ref'],
            source_subject_ref=scope['source_contract_ref'],source_template_ref=source['template_ref'],role=role,output_port=port,
            run_id=node['run_id'],attempt_id=node['attempt_id'],revision=1,subnode_limits=narrowed(source['subnode_limits'],request['limits']),accepted=False,invalid_for_product=True)
        child['bindings'][0]['limits']=narrowed(source['bindings'][0]['limits'],child['subnode_limits'])
        basis={'schema':'ai4r-evaluation-checking-basis:1','id':basis_id,'request_ref':scope['request_ref'],'node_context_ref':scope['actual_node_ref'],
            'assignment_context_ref':child_ref,'source_contract_ref':scope['source_contract_ref'],'source_check_plan_ref':scope['source_check_plan_ref'],
            'source_template_ref':source['template_ref'],'mode':'worker_output','input_refs':child['input_refs'],'profile_ref':plan['profile_ref'],
            'policy_ref':plan['policy_ref'],'mandatory_deterministic':plan['mandatory_deterministic'],'mandatory_semantic':[],
            'runner_refs':plan['runner_refs'],'output_port':None,'accepted':False,'invalid_for_product':True}
        return child,basis

    def _reviewer_projection(self, scope, port, *, child_id, basis_id, child_ref=None):
        request = self._request(scope['request_ref'])
        require((request['entry_point'] == 'E2' and port == scope['selected_output_port']) or request['entry_point'] == 'E3',
            'Only an approved original output may receive a reviewer')
        source, plan, parent, _, _, extra = self._source(scope['request_ref'])
        original = extra[3]
        if request['entry_point'] == 'E3':
            from .evaluation_inspection import captured_worker_outputs
            outputs = captured_worker_outputs(self.store, scope['request_ref'], scope['source_contract_ref'])
        else:
            require(original is not None, 'Selected replay output is unavailable')
            outputs = original['output_refs']
        require(port in outputs, 'Selected measured output is unavailable')
        # The complete original Tier1 population must pass before ANY reviewer
        # context/grant can exist. A selected output cannot waive another output.
        checks = self.captures(scope['request_ref'], 'deterministic_result')
        matches = []
        for event in checks:
            ref = event['capture_ref']
            require(self.store.record_kind(ref) == 'evaluation-deterministic-check-result', 'Replay checks have a foreign kind')
            checked = self.store.read_record(ref, contract_id='deterministic-check-result')
            basis = private_record(self.store, checked['check_plan_ref'], 'evaluation-checking-basis')
            if basis['mode'] == ('replay_subject' if request['entry_point'] == 'E2' else 'worker_output') and basis['request_ref'] == scope['request_ref']:
                require(basis['source_contract_ref'] == scope['source_contract_ref']
                    and basis['mandatory_deterministic'] == plan['mandatory_deterministic'], 'Replay mandatory coverage differs')
                matches.append(checked)
        require(len(matches) == 1 and all_mandatory_pass(plan, matches[0]['results']),
            'Complete original mandatory Tier1 checks must pass before review')
        assignments = []
        for item in parent['subnodes']:
            if item['role'] != 'verifier':
                continue
            template = self.store.read_record(item['template_ref'])
            if template.get('subject_subnode_id') == source['subnode_id'] and template.get('output_port') == port:
                assignments.append((item, template))
        require(len(assignments) == 1, 'No exact source-parent selected reviewer assignment')
        assignment, template = assignments[0]
        pin, _ = self.resources._verifier()
        row = self.resources.admitted.library.get(pin['cc_name'], pin['cc_version'])
        declaration = self.store.read_record(row['declaration_ref'], contract_id='capsule-declaration')
        admission = self.store.read_record(row['admission_ref'], contract_id='library-admission')
        require(assignment['capsule_ref'] == template['capsule_ref'] == row['declaration_ref']
            and template['cc'] == pin and template['admission_ref'] == row['admission_ref']
            and template['body_refs'] == row['body_refs'] and template['ports'] == declaration['ports']
            and admission['status'] == 'admitted' and admission['candidate_ref'] == row['declaration_ref']
            and row['standing'] not in {'suspended', 'revoked'}, 'Selected reviewer differs from eligible admitted pins')
        association = self.resources.admitted.library.eligible_association(row['declaration_ref'])
        require(template['check_bundle_ref'] == association['bundle_ref']
            and template['checking_profile_ref'] == plan['profile_ref'], 'Reviewer check/template pins differ')
        profile = self.store.read_record(plan['profile_ref'], contract_id='checking-profile')
        require(profile['model_call_limit'] == 1, 'Reviewer must retain exactly one model call')
        per = declaration['budget']['per_call']
        node = private_record(self.store, scope['actual_node_ref'], 'evaluation-node-context')
        limits = narrowed({'time_s': min(per['wall_s'], profile['time_s']), 'model_calls': 1,
            'memory_mb': admission['memory_mb']}, node['node_limits'], request['limits'])
        require(limits['model_calls'] == 1, 'Approved request cannot contain its selected reviewer')
        from .compiler import input_port
        from .binding import ContractFactory
        inputs = [input_port('subject_declaration', 'capsule-declaration', source['bindings'][0]['declaration_ref']),
            input_port('subject_output', 'opaque-bytes', outputs[port])]
        outputs = [{'name': p['name'], 'contract_id': p['schema_ref'], 'version': ContractFactory._version(p['schema_ref']),
            'required': p['required']} for p in declaration['ports']['outputs']]
        authority = {'network': 'none', 'network_allowlist': [], 'resource_reads': [r for p in inputs for r in p['artifact_refs']],
            'write_roots': [], 'tools': []}
        binding = {'id': assignment['subnode_id'] + '.binding', 'role': 'verifier', 'declaration_ref': row['declaration_ref'],
            'implementation_refs': [row['body_refs'][b['path']] for b in declaration['identity']['body']],
            'dependency_refs': [row['body_refs'][p['ref']] for d in declaration['needs']['external'] for k in ('pin', 'lockfile') if (p := d.get(k))],
            'admission_ref': row['admission_ref'], 'effective_authority': authority, 'limits': limits}
        child = {k: copy.deepcopy(source[k]) for k in ('node_id', 'objective', 'requirement_ids', 'evidence_obligations', 'policy_ref', 'configuration_ref')}
        child.update(schema='ai4r-evaluation-subnode-context:1', id=child_id, request_ref=scope['request_ref'],
            node_contract_ref=scope['actual_node_ref'], source_subject_ref=scope['source_contract_ref'],
            source_template_ref=assignment['template_ref'], role='verifier', output_port=port,
            run_id=scope['private_run_id'], subnode_id=assignment['subnode_id'], attempt_id=node['attempt_id'],
            revision=1, bindings=[binding], inputs=inputs, outputs=outputs,
            input_refs=authority['resource_reads'], required_outputs=[p['name'] for p in outputs if p['required']],
            subnode_limits=limits, checking_profile_ref=template['checking_profile_ref'], accepted=False, invalid_for_product=True)
        bundle = self.store.read_record(template['check_bundle_ref'], contract_id='check-bundle')
        mandatory = list(dict.fromkeys([*[c['check_id'] for c in bundle['checks'] if c['blocking']],
            'host_contract', 'host_identity', 'host_limits', 'host_authority']))
        runners = list({r['sha256']: r for r in [template['check_bundle_ref'], *[c['runner_ref'] for c in bundle['checks']]]}.values())
        basis = {'schema': 'ai4r-evaluation-checking-basis:1', 'id': basis_id, 'request_ref': scope['request_ref'],
            'node_context_ref': scope['actual_node_ref'], 'assignment_context_ref': child_ref,
            'source_contract_ref': scope['source_contract_ref'], 'source_check_plan_ref': scope['source_check_plan_ref'],
            'source_template_ref': assignment['template_ref'], 'mode': 'verifier_output', 'input_refs': child['input_refs'],
            'profile_ref': plan['profile_ref'], 'policy_ref': plan['policy_ref'], 'mandatory_deterministic': mandatory,
            'mandatory_semantic': [], 'runner_refs': runners, 'output_port': port, 'accepted': False, 'invalid_for_product': True}
        return child, basis

    def _create_assignment_context(self,scope_ref,role,port):
        scope=self._scope(scope_ref);self._active(scope['request_ref'])
        child,_=self._assignment_projection(scope,role,port,child_id=identity('evaluation-context'),basis_id='unused')
        return self._put('evaluation-subnode-context',child)

    def _create_basis(self,scope_ref,child_ref,mode):
        scope=self._scope(scope_ref)
        if child_ref is None:
            request, _ = self._active(scope['request_ref'])
            require(mode == 'replay_subject' and request['entry_point'] == 'E2', 'Only replay host basis may omit an assignment')
            source, plan, _, _, _, _ = self._source(scope['request_ref'])
            profile = self.store.read_record(plan['profile_ref'], contract_id='checking-profile')
            basis = {'schema': 'ai4r-evaluation-checking-basis:1', 'id': identity('evaluation-basis'), 'request_ref': scope['request_ref'],
                'node_context_ref': scope['actual_node_ref'], 'assignment_context_ref': None,
                'source_contract_ref': scope['source_contract_ref'], 'source_check_plan_ref': scope['source_check_plan_ref'],
                'source_template_ref': source['template_ref'], 'mode': mode, 'input_refs': source['input_refs'],
                'profile_ref': plan['profile_ref'], 'policy_ref': plan['policy_ref'],
                'mandatory_deterministic': plan['mandatory_deterministic'],
                'mandatory_semantic': [c['criterion_id'] for c in profile['criteria'] if c['blocking'] and c['target_port'] in (None, scope['selected_output_port'])],
                'runner_refs': plan['runner_refs'], 'output_port': scope['selected_output_port'], 'accepted': False, 'invalid_for_product': True}
            return self._put('evaluation-checking-basis', basis)
        child=private_record(self.store,child_ref,'evaluation-subnode-context')
        _,basis=self._assignment_projection(scope,child['role'],child['output_port'],child_id=child['id'],basis_id=identity('evaluation-basis'),child_ref=child_ref)
        require(basis['mode']==mode,'Private checking mode differs')
        return self._put('evaluation-checking-basis',basis)

    def prepare_assignment(self,scope_ref,role,output_port):
        scope=self._scope(scope_ref);request,_=self._active(scope['request_ref'])
        with self.store._lock:
            prior=self.store.connection.execute('SELECT grant_ref FROM evaluation_assignments WHERE request_ref=? AND role=? AND port=?',(encoded(scope['request_ref']),role,output_port or '')).fetchone()
            if prior:return json.loads(prior[0])
            child=self.projection.create_assignment_context(scope_ref,role,output_port)
            basis=self.projection.create_checking_basis(scope_ref,child,'worker_output' if role=='worker' else 'verifier_output')
            context=private_record(self.store,child,'evaluation-subnode-context')
            grant={'schema':'ai4r-evaluation-assignment-grant:1','id':identity('evaluation-assignment'),'request_ref':scope['request_ref'],'scope_ref':scope_ref,
                'role':role,'output_port':output_port,'source_contract_ref':scope['source_contract_ref'],'contract_ref':child,'check_plan_ref':basis,
                'execution_id':identity('execution'),'invocation_id':identity('invocation'),'limits':context['bindings'][0]['limits'],
                'started_unix_ns':time.time_ns(),'deadline_unix_ns':request['deadline_unix_ns'],'accepted':False,'invalid_for_product':True}
            ref=self._put('evaluation-assignment-grant',grant)
            with self.store.transaction() as db:
                db.execute('INSERT INTO evaluation_assignments VALUES (?,?,?,?,?,?)',(grant['execution_id'],encoded(scope['request_ref']),role,output_port or '',encoded(ref),'prepared'))
            for kind,pin in [('actual_contract',child),('check_plan',basis)]:self.register_capture(ref,kind,pin)
            return ref

    def start_assignment(self,grant_ref,inputs):
        grant,context,basis=self.projection.load_execution(grant_ref);request,remaining=self._active(grant['request_ref'])
        require(self._assignment(grant['execution_id'])['state']=='prepared'
            and grant['execution_id'] not in self.runner._executions,
            'Assignment was already prepared; reconcile without replay','evaluation_outcome_unknown')
        declaration=self.store.read_record(context['bindings'][0]['declaration_ref'],contract_id='capsule-declaration')
        original_remaining=(grant['started_unix_ns']+int(grant['limits']['time_s']*1e9)-time.time_ns())/1e9
        require(original_remaining>0,'Original assignment allowance expired during preparation','budget_exhausted')
        began=time.monotonic();self.runner._executions[grant['execution_id']]={'contract_ref':grant['contract_ref'],'contract':context,'declaration':declaration,
            'invocation_id':grant['invocation_id'],'started':began,'deadline':min(self._deadlines[encoded(grant['request_ref'])],began+original_remaining),
            'calls':[],'closed':False,'call_function':'worker' if grant['role']=='worker' else 'verifier','evaluation_owner':self,'evaluation_grant_ref':grant_ref,
            'evaluation_executor_port': self.runner.executor}
        from .runner import InvocationContext
        from .invocation_start import prepare
        return prepare(self.runner,InvocationContext(self.runner,context,grant['execution_id'],inputs))

    def _commit_prepared_start(self,execution,live_check):
        grant_ref=execution['evaluation_grant_ref'];grant=self.projection.load_execution(grant_ref)[0]
        with self.store.transaction() as db:
            live_check()
            row=self._row(grant['request_ref'])
            require(row['state'] in {'prepared','executing'} and row['cancel_id'] is None and row['terminal_ref'] is None
                and row['boot']==self._boot and row['deadline_ns']>time.time_ns(),
                'Private request stopped before consumed start','evaluation_outcome_unknown')
            require(db.execute("UPDATE evaluation_assignments SET state='started' WHERE execution_id=? AND state='prepared'",(grant['execution_id'],)).rowcount==1,
                'Private assignment start was already consumed','evaluation_outcome_unknown')
            timing={'started_at':utc_now(),'started_monotonic_s':time.monotonic()}
            event={'schema':'ai4r-evaluation-event:1','id':identity('evaluation-event'),'request_ref':grant['request_ref'],
                'scope_ref':grant['scope_ref'],'sequence':row['sequence']+1,
                'previous_event_ref':json.loads(row['head_ref']) if row['head_ref'] else None,
                'kind':'assignment_started','assignment_grant_ref':grant_ref,'capture_kind':None,'capture_ref':None,'reason':None,
                'recorded_unix_ns':time.time_ns(),'accepted':False,'invalid_for_product':True}
            validate('urn:ai4r:private:evaluation-event:1',event)
            digest=self.store.blobs.put(json_bytes(event));ref={'id':event['id'],'sha256':digest}
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'evaluation-event',None,None,None,utc_now()))
            require(db.execute("UPDATE evaluation_requests SET state='executing',head_ref=?,sequence=? WHERE request_ref=? AND sequence=? AND cancel_id IS NULL AND terminal_ref IS NULL",
                (encoded(ref),event['sequence'],encoded(grant['request_ref']),row['sequence'])).rowcount==1,
                'Private journal/start CAS changed','evaluation_outcome_unknown')
        return timing

    def _execution(self,execution_id,*,active=True):
        row=self._assignment(execution_id);require(row is not None,'Unknown private execution')
        grant,context,basis=self.projection.load_execution(json.loads(row['grant_ref']))
        if active:
            self._active(grant['request_ref']);execution=self.runner._executions.get(execution_id)
            require(row['state']=='started' and execution is not None and execution.get('evaluation_owner') is self and not execution['closed'] and execution.get('phase')=='active',
                    'No actual active private invocation','evaluation_outcome_unknown')
            require(execution['contract_ref']==grant['contract_ref'] and execution['contract']==context and execution['invocation_id']==grant['invocation_id'], 'Actual private invocation drifted')
            require(time.monotonic()<execution['deadline'],'Assignment deadline expired','budget_exhausted')
        return grant,context,basis

    def authorize_model_context(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'execution_id','call_ordinal'},'Malformed private invoke claim')
        grant,context,_=self._execution(payload['execution_id']);ordinal=payload['call_ordinal']
        require(type(ordinal) is int and ordinal>0,'Invalid call ordinal')
        execution=self.runner._executions[payload['execution_id']];runtime=self._current_runtime();request,remaining=self._active(grant['request_ref'])
        selection=self.store.read_record(runtime['model_selection_profile_ref'],contract_id='model-selection-profile')
        remaining=min(remaining,execution['deadline']-time.monotonic())
        protected={**{k:context[k] for k in ('run_id','node_id','subnode_id','attempt_id')},'execution_id':grant['execution_id'],'invocation_id':grant['invocation_id'],
            'call_ordinal':ordinal,'call_function':execution['call_function'],'cc_name':execution['declaration']['identity']['name'],'cc_version':execution['declaration']['identity']['version_label'],
            'declaration':copy.deepcopy(execution['declaration']),
            'contract_ref':grant['contract_ref'],'input_refs':context['input_refs'],'limits':dict(grant['limits'],time_s=remaining),
            'execution_deadline_monotonic_s':execution['deadline'],**{k:runtime[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')},
            'router':copy.deepcopy(self.provider.operator['cc']['router']),'model_selection_profile':selection,'approved_model_ids':selection['approved_model_ids']}
        if runtime.get('account_model_selection_ref') is not None:
            protected.update(evaluation_runtime_ref=copy.deepcopy(self.runtime_ref),
                             account_model_selection_ref=copy.deepcopy(runtime['account_model_selection_ref']))
        call_id=identity('call')
        claim={'schema':'ai4r-evaluation-call-claim:1','id':identity('evaluation-call-claim'),'request_ref':grant['request_ref'],'scope_ref':grant['scope_ref'],
            'assignment_grant_ref':execution['evaluation_grant_ref'],'execution_id':grant['execution_id'],'invocation_id':grant['invocation_id'],'call_ordinal':ordinal,'call_id':call_id,
            'contract_ref':grant['contract_ref'],'expected_prompt_sha256':None,'claimed_unix_ns':time.time_ns(),'accepted':False,'invalid_for_product':True}
        if grant['role'] == 'verifier':
            claim['expected_prompt_sha256'] = self._review_prompt_hash(grant['scope_ref'], grant['output_port'])
            protected['expected_prompt_sha256'] = claim['expected_prompt_sha256']
        with self.store._lock:
            with self.store.transaction() as db:
                used=db.execute('SELECT COUNT(*) FROM evaluation_calls WHERE execution_id=?',(grant['execution_id'],)).fetchone()[0]
                total=db.execute('SELECT COUNT(*) FROM evaluation_calls JOIN evaluation_assignments USING(execution_id) WHERE request_ref=?',(encoded(grant['request_ref']),)).fetchone()[0]
                require(ordinal==used+1 and used<grant['limits']['model_calls'] and total<request['limits']['model_calls'],'Private call budget or ordinal exhausted','budget_exhausted')
            ref=self._put('evaluation-call-claim',claim)
            protected.update(call_id=call_id,call_claim_ref=ref)
            with self.store.transaction() as db:
                db.execute('INSERT INTO evaluation_calls VALUES (?,?,?,?,?)',(grant['execution_id'],ordinal,call_id,encoded(ref),encoded(protected)))
        self.register_capture(execution['evaluation_grant_ref'],'model_claim',ref)
        return protected

    def authorize_model_dispatch(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'execution_id','invocation_id','call_id','call_claim_ref','contract_ref'},'Malformed private dispatch')
        grant,_,_=self._execution(payload['execution_id'])
        with self.store._lock:row=self.store.connection.execute('SELECT * FROM evaluation_calls WHERE execution_id=? AND call_id=?',(payload['execution_id'],payload['call_id'])).fetchone()
        require(row is not None and json.loads(row['claim_ref'])==payload['call_claim_ref'],'Unknown exact private call claim')
        claim=private_record(self.store,payload['call_claim_ref'],'evaluation-call-claim')
        require(all(claim[k]==payload[k] for k in payload if k!='call_claim_ref') and claim['assignment_grant_ref']==json.loads(self._assignment(payload['execution_id'])['grant_ref']), 'Private call identity differs')
        result=json.loads(row['protected']);remaining=min(self._active(grant['request_ref'])[1],result['execution_deadline_monotonic_s']-time.monotonic())
        require(remaining>0,'Private dispatch expired','budget_exhausted');result['limits']['time_s']=remaining
        return result

    def authorize_executor_binding(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'contract_ref','invocation_id','execution_id'},'Malformed private executor binding')
        grant,context,_=self._execution(payload['execution_id'])
        require(all(payload[k]==grant[k] for k in payload),'Private executor binding identity differs')
        deadline=self.runner._executions[payload['execution_id']]['deadline'];remaining=min(self._active(grant['request_ref'])[1],deadline-time.monotonic())
        return {**copy.deepcopy(payload),'contract':context,'execution_deadline_monotonic_s':deadline,'remaining_time_s':remaining}

    def authorize_tool_call(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'execution_id','tool_ordinal','operation'},'Malformed private tool claim')
        grant,context,_=self._execution(payload['execution_id']);ordinal=payload['tool_ordinal']
        require(type(ordinal) is int and ordinal>0 and payload['operation'] in context['bindings'][0]['effective_authority']['tools'],'Tool outside private authority')
        with self.store._lock:
            used=self.store.connection.execute('SELECT COUNT(*) FROM evaluation_tools WHERE execution_id=?',(payload['execution_id'],)).fetchone()[0]
            declaration=self.runner._executions[payload['execution_id']]['declaration']
            require(ordinal==used+1 and used<declaration['budget']['per_call']['tool_calls'],'Tool ordinal/ceiling exhausted')
            record={'schema':'ai4r-evaluation-tool-claim:1','id':identity('evaluation-tool-claim'),'request_ref':grant['request_ref'],'scope_ref':grant['scope_ref'],
                'assignment_grant_ref':json.loads(self._assignment(payload['execution_id'])['grant_ref']),**payload,'invocation_id':grant['invocation_id'],
                'contract_ref':grant['contract_ref'],'claimed_unix_ns':time.time_ns(),'accepted':False,'invalid_for_product':True}
            ref=self._put('evaluation-tool-claim',record)
            with self.store.transaction() as db:db.execute('INSERT INTO evaluation_tools VALUES (?,?,?)',(payload['execution_id'],ordinal,encoded(ref)))
        self.register_capture(record['assignment_grant_ref'],'tool_claim',ref)
        return ref

    def capture_native(self,kind,record,*,execution_id=None):
        """Finite sink: persist unchanged native bytes, then bind exact claim.

        Native consumer calls this for a known private execution only. No global
        scan or matching merely by contract can supply attribution.
        """
        execution_id=execution_id or record.get('execution_id');row=self._assignment(execution_id)
        require(row is not None,'Native capture has no exact private assignment')
        grant,_,_=self.projection.load_execution(json.loads(row['grant_ref']))
        require(record.get('invocation_id')==grant['invocation_id'],'Native capture invocation differs')
        call_id=record.get('call_id') or (record.get('id') if kind=='model-call' else None)
        if call_id:
            with self.store._lock:claim=self.store.connection.execute('SELECT claim_ref,protected FROM evaluation_calls WHERE execution_id=? AND call_id=?',(execution_id,call_id)).fetchone()
            require(claim is not None,'Native capture has no durable private call claim')
        else:
            with self.store._lock:claims=self.store.connection.execute('SELECT claim_ref,protected FROM evaluation_calls WHERE execution_id=?',(execution_id,)).fetchall()
            require(len(claims)==1,'Native route has ambiguous private call attribution');claim=claims[0]
        require(kind in NATIVE_KINDS,'Unsupported private native capture kind')
        protected=json.loads(claim['protected']);context={key:protected[key] for key in ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')}
        return capture_evaluation_native(self.store,kind,record,context=context)

    def _published_terminal(self, request_ref, row=None):
        """Only the bounded durable journal can publish a terminal object."""
        self._request(request_ref)
        row = self._row(request_ref) if row is None else row
        from .evaluation_history import EvaluationReader
        reader = EvaluationReader(self.store, runtime_ref=self.runtime_ref)
        scope_ref = json.loads(row['scope_ref']) if row['scope_ref'] else None
        _, events = reader._journal(request_ref, row, scope_ref)
        return reader._terminal(request_ref, row, scope_ref, events)

    def inspect(self, request_ref):
        self._request(request_ref)
        with self.store._lock:
            row = self._row(request_ref)
            terminal = self._published_terminal(request_ref, row)
        return terminal if terminal is not None else {
            'state': 'outcome_unknown' if row['boot'] != self._boot else row['state'],
            'request_ref': request_ref}

    def _reconcile_terminal(self, request_ref, row, result, measurement_refs):
        terminal = self._published_terminal(request_ref, row)
        require(terminal is not None, 'Terminal publication is incomplete', 'audit_unavailable')
        if result is not None:
            require(terminal['state'] in {'completed', 'failed', 'outcome_unknown'} and terminal['result_ref'] is not None
                and self.store.read_record(terminal['result_ref'])['result'] == result
                and terminal['measurement_refs'] == list(measurement_refs),
                'Stopped request cannot publish a different response', 'evaluation_outcome_unknown')
        return json.loads(row['terminal_ref'])

    def _cleanup_response_window(self, request_ref, row, marker):
        request = self._request(request_ref)
        self._current_runtime()
        require(self in self.runner._evaluation_owners and row['boot'] == self._boot
            and row['terminal_ref'] is None and row['state'] == 'cancelling'
            and row['cancel_id'] == marker['cancel_id']
            and row['scope_ref'] == encoded(marker['scope_ref']),
            'No original live failed-measurement cleanup', 'evaluation_outcome_unknown')
        require(time.time_ns() < request['deadline_unix_ns']
            and time.monotonic() < self._deadlines[encoded(request_ref)],
            'Original whole-request deadline expired during failure cleanup', 'budget_exhausted')

    def _cleanup_response(self, request_ref, row, result, measurement_refs):
        marker = self._failure_cleanups.get(encoded(request_ref))
        if result is None or marker is None:
            return None
        self._cleanup_response_window(request_ref, row, marker)
        state = 'failed' if marker['containment_ref'] is not None else 'outcome_unknown'
        failure = marker['reason'] if state == 'failed' else 'containment_uncertain'
        from .evaluation_history import validate_cleanup_response
        events = self.captures(request_ref)
        captures = {(entry['capture_kind'], encoded(entry['capture_ref'])) for entry in events}
        measured = validate_cleanup_response(self.store, request_ref, marker['scope_ref'], result, measurement_refs,
            state=state, failure=failure, containment_ref=marker['containment_ref'], cancel_id=marker['cancel_id'],
            captures=captures, events=events)
        require(measured['contract_ref'] == marker['contract_ref'], 'Cleanup measurement targets another context')
        return marker, state, failure

    def terminal(self, request_ref, *, result=None, failure=None, measurement_refs=(), state=None,
                 containment_ref=None):
        self._request(request_ref)
        row = self._row(request_ref)
        if row['terminal_ref']:
            return self._reconcile_terminal(request_ref, row, result, measurement_refs)
        cleanup = self._cleanup_response(request_ref, row, result, measurement_refs)
        if cleanup is not None:
            marker, state, failure = cleanup
            containment_ref = marker['containment_ref']
        # Completion means producing an immutable response, including a source
        # failed/blocked response. Every such response uses the original deadline.
        if result is not None and cleanup is None:
            self._active(request_ref)
        result_ref = self.store.append_record('evaluation-result', {
            'id': identity('evaluation-result'), 'result': result,
            'accepted': False, 'invalid_for_product': True}) if result is not None else None
        failure_ref = self.store.append_record('evaluation-failure', {
            'id': identity('evaluation-failure'), 'reason': failure,
            'accepted': False, 'invalid_for_product': True}) if failure else None
        for kind, pin in [('result', result_ref), ('failure', failure_ref)]:
            if pin:
                self.register_capture(None, kind, pin, request_ref=request_ref)
        row = self._row(request_ref)
        if row['terminal_ref']:
            return self._reconcile_terminal(request_ref, row, result, measurement_refs)
        terminal_state = state or ('completed' if result_ref is not None else 'failed')
        require(result_ref is None or terminal_state == 'completed' or cleanup is not None,
            'A result cannot bypass completed-response deadline checks')
        require(row['cancel_id'] is None or terminal_state in {'cancelled', 'outcome_unknown'} or cleanup is not None,
            'Cancellation revoked terminal response publication', 'evaluation_outcome_unknown')
        if terminal_state == 'cancelled':
            require(row['cancel_id'] is not None and containment_ref is not None,
                'Cancelled terminal requires the original cancellation and containment', 'containment_uncertain')
        if containment_ref is not None:
            require(self.store.record_kind(containment_ref) == 'evaluation-containment',
                'Containment evidence kind differs')
            receipt = self.store.read_record(containment_ref)
            require(receipt.get('request_ref') == request_ref and receipt.get('cancel_id') == row['cancel_id'],
                'Containment evidence belongs to another cancellation')
        captures = {(entry['capture_kind'], encoded(entry['capture_ref'])) for entry in self.captures(request_ref)}
        require(all(('measurement', encoded(ref)) in captures
            and self.store.record_kind(ref) == 'evaluation-trial-measurement' for ref in measurement_refs),
            'Terminal measurements are not original request captures')
        require(terminal_state != 'completed' or result_ref is not None and measurement_refs,
            'Completed response needs actual original measurements')
        terminal = {'schema': 'ai4r-evaluation-terminal:1', 'id': identity('evaluation-terminal'),
            'request_ref': request_ref, 'scope_ref': json.loads(row['scope_ref']) if row['scope_ref'] else None,
            'state': terminal_state, 'measurement_refs': list(measurement_refs), 'result_ref': result_ref,
            'failure_ref': failure_ref, 'through_event_ref': json.loads(row['head_ref']),
            'containment_ref': containment_ref, 'recorded_unix_ns': time.time_ns(),
            'accepted': False, 'invalid_for_product': True}
        ref = self._put('evaluation-terminal', terminal)
        event = {'schema': 'ai4r-evaluation-event:1', 'id': identity('evaluation-event'),
            'request_ref': request_ref, 'scope_ref': terminal['scope_ref'], 'sequence': row['sequence'] + 1,
            'previous_event_ref': terminal['through_event_ref'], 'kind': 'terminal',
            'assignment_grant_ref': None, 'capture_kind': None, 'capture_ref': ref, 'reason': None,
            'recorded_unix_ns': time.time_ns(), 'accepted': False, 'invalid_for_product': True}
        event_ref = self._put('evaluation-event', event)
        # Immutable captures may orphan on failure; neither they nor a terminal
        # object grant completion. Publish terminal+state+exact journal head in
        # one recoverable CAS after all capture/preparation time has elapsed.
        with self.store._lock:
            current = self._row(request_ref)
            if current['terminal_ref']:
                return self._reconcile_terminal(request_ref, current, result, measurement_refs)
            if result is not None:
                if cleanup is None:self._active(request_ref)
                else:self._cleanup_response_window(request_ref, current, marker)
            with self.store.transaction() as db:
                current = db.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',
                    (encoded(request_ref),)).fetchone()
                require(current is not None and current['cancel_id'] == row['cancel_id']
                    and current['state'] == row['state'] and current['boot'] == row['boot'],
                    'Request changed before terminal publication', 'evaluation_outcome_unknown')
                if result is not None:
                    request = self._request(request_ref)
                    boot = db.execute('SELECT boot FROM evaluation_owner_boots WHERE runtime=?',
                        (encoded(self.runtime_ref),)).fetchone()
                    require(current['boot'] == self._boot and boot is not None and boot['boot'] == self._boot
                        and ((current['state'] in {'claimed', 'prepared', 'executing'} and current['cancel_id'] is None)
                            if cleanup is None else (current['state'] == 'cancelling' and current['cancel_id'] == marker['cancel_id'])),
                        'No live original request for response publication', 'evaluation_outcome_unknown')
                    require(time.time_ns() < request['deadline_unix_ns']
                        and time.monotonic() < self._deadlines[encoded(request_ref)],
                        'Original whole-request deadline expired during terminal capture', 'budget_exhausted')
                changed = db.execute('UPDATE evaluation_requests SET terminal_ref=?,state=?,head_ref=?,sequence=? '
                    'WHERE request_ref=? AND terminal_ref IS NULL AND sequence=? AND head_ref IS ? '
                    'AND state=? AND cancel_id IS ? AND boot=?',
                    (encoded(ref), terminal_state, encoded(event_ref), event['sequence'], encoded(request_ref),
                     row['sequence'], row['head_ref'], row['state'], row['cancel_id'], row['boot'])).rowcount
                require(changed == 1, 'Terminal journal publication conflict', 'audit_unavailable')
        return ref

    def authorize_containment(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'run_id','request_id'},'Malformed private containment')
        with self.store._lock:rows=self.store.connection.execute('SELECT * FROM evaluation_requests WHERE runtime=? AND cancel_id=?',(encoded(self.runtime_ref),payload['request_id'])).fetchall()
        matches=[r for r in rows if r['scope_ref'] and self._scope(json.loads(r['scope_ref']))['private_run_id']==payload['run_id']]
        require(len(matches)==1,'No durable private containment request')
        with self.store._lock:grants=self.store.connection.execute('SELECT grant_ref FROM evaluation_assignments WHERE request_ref=?',(matches[0]['request_ref'],)).fetchall()
        return {'authorized':True,**payload,'invocation_ids':[private_record(self.store,json.loads(r[0]),'evaluation-assignment-grant')['invocation_id'] for r in grants]}

    async def contain_failure(self, context, reason):
        require(type(context) is EvaluationMeasurementContext and context.owner is self
            and isinstance(reason, str) and bool(reason), 'Actual failed measurement context required')
        request_ref = context.scope['request_ref']; row = self._row(request_ref)
        marker = self._failure_cleanups.get(encoded(request_ref))
        if reason == 'cancelled' or row['cancel_id'] is not None and marker is None:
            return await self.cancel(request_ref, row['cancel_id'] or identity('evaluation-cancel'))
        if marker is not None:
            require(marker['scope_ref'] == context.scope_ref and marker['contract_ref'] == context.contract_ref
                and marker['cancel_id'] == row['cancel_id'], 'Failure cleanup identity changed')
            require(marker['containment_ref'] is not None, 'Original failure containment remains uncertain', 'containment_uncertain')
            return {'contained': True, 'request_ref': request_ref, 'containment_ref': marker['containment_ref']}
        self._request(request_ref); self._current_runtime()
        require(self in self.runner._evaluation_owners and row['boot'] == self._boot
            and row['scope_ref'] == encoded(context.scope_ref) and row['terminal_ref'] is None,
            'Failure cleanup requires the original installed live context', 'evaluation_outcome_unknown')
        if context.grant is not None:
            execution = self.runner._executions.get(context.grant['execution_id'])
            require(execution is not None and execution.get('evaluation_owner') is self
                and execution.get('evaluation_grant_ref') == context.grant_ref
                and execution.get('contract_ref') == context.contract_ref, 'Failure context was not actually started')
        marker = {'scope_ref': context.scope_ref, 'contract_ref': context.contract_ref,
            'assignment_grant_ref': context.grant_ref, 'source_failure_ref': None,
            'cancel_id': identity('evaluation-cleanup'), 'reason': reason, 'containment_ref': None}
        # The registered marker survives an uncertain containment exception;
        # later original failed evidence can form only non-success inspection.
        receipt = await self._contain_request(request_ref, marker['cancel_id'], finalize=False, cleanup_marker=marker)
        marker['containment_ref'] = receipt['containment_ref']
        return receipt

    async def cancel(self, request_ref, cancel_id):
        return await self._contain_request(request_ref, cancel_id, finalize=True)

    async def _contain_request(self, request_ref, cancel_id, *, finalize, cleanup_marker=None):
        self._request(request_ref)
        require(isinstance(cancel_id, str) and cancel_id, 'Explicit private cancel identity required')
        # Compare against the CURRENT durable row under its writer transaction;
        # an earlier snapshot cannot replace a cancellation or completed result.
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',
                (encoded(request_ref),)).fetchone()
            require(row is not None and row['cancel_id'] in (None, cancel_id),
                'Private cancel identity conflict', 'identity_conflict')
            if row['terminal_ref']:
                terminal = self._published_terminal(request_ref, row)
                require(row['cancel_id'] == cancel_id and terminal['state'] == 'cancelled'
                    and terminal['containment_ref'] is not None,
                    'Completed terminal cannot acquire a new cancellation', 'evaluation_outcome_unknown')
                return {'contained': True, 'request_ref': request_ref,
                    'containment_ref': terminal['containment_ref']}
            fresh = row['cancel_id'] is None
            if fresh:
                require(db.execute("UPDATE evaluation_requests SET cancel_id=?,state='cancelling' "
                    'WHERE request_ref=? AND terminal_ref IS NULL AND cancel_id IS NULL',
                    (cancel_id, encoded(request_ref))).rowcount == 1,
                    'Cancellation claim changed', 'evaluation_outcome_unknown')
            if cleanup_marker is not None:
                require(fresh and row['boot'] == self._boot,
                    'An explicit or reconstructed cancellation cannot become automatic cleanup', 'evaluation_outcome_unknown')
                self._failure_cleanups[encoded(request_ref)] = cleanup_marker
        if fresh:
            self.event(request_ref, 'cancellation_requested', reason='Original cancel identity: ' + cancel_id)
        if cleanup_marker is not None:
            # Effects are already durably revoked. Preserve the original cause
            # before containment can independently fail or become uncertain.
            source_failure = self.store.append_record('evaluation-failure', {
                'id': identity('evaluation-failure'), 'reason': cleanup_marker['reason'],
                'accepted': False, 'invalid_for_product': True})
            self.register_capture(cleanup_marker['assignment_grant_ref'], 'failure', source_failure,
                request_ref=request_ref)
            cleanup_marker['source_failure_ref'] = source_failure
        row = self._row(request_ref)
        scope = self._scope(json.loads(row['scope_ref'])) if row['scope_ref'] else None
        with self.store._lock:
            assignments = self.store.connection.execute('SELECT * FROM evaluation_assignments WHERE request_ref=?',
                (encoded(request_ref),)).fetchall()
        started = [item for item in assignments if item['state'] == 'started']
        receipts = []
        if scope is not None:
            grant = self.authorize_containment({'run_id': scope['private_run_id'], 'request_id': cancel_id})
            for name, port in [('model', self.runner.model), ('executor', self.runner.executor)]:
                if port is None:
                    # An absent current port never proves historical cessation.
                    # Only the same live owner's exact start context can show
                    # that no executor capability existed for this assignment.
                    no_executor_capability = name == 'executor' and all(
                        (execution := self.runner._executions.get(item['execution_id'])) is not None
                        and execution.get('evaluation_owner') is self
                        and execution.get('evaluation_grant_ref') == json.loads(item['grant_ref'])
                        and 'evaluation_executor_port' in execution
                        and execution['evaluation_executor_port'] is None for item in started)
                    require(not started or no_executor_capability,
                        'Containment owner unavailable', 'containment_uncertain')
                    continue
                from .bridge import GovernedBridge
                method = getattr(port, 'contain_run', None)
                require(method is not None, 'Actual managed containment unavailable', 'containment_uncertain')
                result = method(grant) if isinstance(port, GovernedBridge) else method(scope['private_run_id'], cancel_id)
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, 35)
                require(isinstance(result, dict) and result.get('contained') is True
                    and result.get('run_id') == scope['private_run_id'] and result.get('request_id') == cancel_id,
                    'Exact private containment acknowledgement missing', 'containment_uncertain')
                receipts.append(result)
        else:
            require(not assignments, 'Unprepared request has assignment evidence', 'containment_uncertain')
        ref = self.store.append_record('evaluation-containment', {
            'id': identity('evaluation-containment'), 'request_ref': request_ref, 'cancel_id': cancel_id,
            'scope_ref': json.loads(row['scope_ref']) if row['scope_ref'] else None,
            'no_started_assignments': not started, 'receipts': receipts,
            'accepted': False, 'invalid_for_product': True})
        self.register_capture(None, 'containment', ref, request_ref=request_ref)
        self.event(request_ref, 'contained')
        if finalize:self.terminal(request_ref, failure='cancelled', state='cancelled', containment_ref=ref)
        return {'contained': True, 'request_ref': request_ref, 'containment_ref': ref}

    async def execute(self,scope_ref):
        scope=self._scope(scope_ref);request,_=self._active(scope['request_ref'])
        if request['entry_point'] == 'E2':
            ctx = EvaluationMeasurementContext(self, None, scope_ref=scope_ref)
            _, _, _, _, bundle, _ = self._source(scope['request_ref'])
            return ctx, await measure_trial(ctx, None, ctx.inputs, ctx.contract['outputs'], ctx.check_plan_ref,
                bundle['bundle_id'], ctx.review)
        grant_ref=self.prepare_assignment(scope_ref,'worker',None);ctx=EvaluationMeasurementContext(self,grant_ref)
        source,_,_,_,bundle,_=self._source(scope['request_ref']);decl=self.store.read_record(source['bindings'][0]['declaration_ref'],contract_id='capsule-declaration')
        handler,pinned=self.runner.registry.resolve(decl['identity']['name'],decl['identity']['version_label'],source['bindings'][0]['declaration_ref']['sha256'])
        require(not pinned or tuple(source['bindings'][0]['implementation_refs'])==pinned,'Installed carrier bytes differ')
        await self.runner._await_start(ctx.worker_context)
        measured=await measure_trial(ctx,handler,ctx.inputs,ctx.contract['outputs'],ctx.check_plan_ref,bundle['bundle_id'],ctx.review)
        for port in measured.output_refs:
            decision=ctx.recording_decision(measured,port)
            gate=self.store.append_record('evaluation-gate-record',{'id':identity('evaluation-gate'),'decision':decision,
                'persisted_at':utc_now(),'invalid_for_product':True})
            self.register_capture(None,'evaluation_gate',gate,request_ref=scope['request_ref'])
        return ctx,measured

    def _review_prompt_hash(self, scope_ref, port):
        scope = self._scope(scope_ref)
        source, plan, _, _, _, extra = self._source(scope['request_ref'])
        if self._request(scope['request_ref'])['entry_point'] == 'E3':
            from .evaluation_inspection import captured_worker_outputs
            outputs = captured_worker_outputs(self.store, scope['request_ref'], scope['source_contract_ref'])
        else:
            require(port == scope['selected_output_port'], 'Verifier prompt targets another output')
            outputs = extra[3]['output_refs']
        require(port in outputs, 'Verifier prompt targets an uncaptured output')
        output = self.store.read_blob(outputs[port])
        from .gate import zip_projection
        from .contracts import contract_schema
        if contract_schema(next(p['contract_id'] for p in source['outputs'] if p['name'] == port)) == contract_schema('poc-artifact-bundle'):
            output = zip_projection(output)
        profile = self.store.read_record(plan['profile_ref'], contract_id='checking-profile')
        criteria = [c for c in profile['criteria'] if c['target_port'] in (None, port)]
        instructions = self.store.read_blob(profile['instruction_ref']).decode('utf-8')
        instructions += '\nCriteria for this output:\n' + json.dumps(criteria, ensure_ascii=False)
        payload = json.dumps({'subject_declaration': self.store.read_blob(source['bindings'][0]['declaration_ref']).decode('utf-8'),
            'subject_output': output.decode('utf-8')}, ensure_ascii=False)
        return hashlib.sha256((instructions + '\n\n<subject_payload>\n' + payload + '\n</subject_payload>').encode('utf-8')).hexdigest()


class EvaluationMeasurementContext:
    def __init__(self,owner,grant_ref,*,scope_ref=None):
        self.owner,self.store,self.runner=owner,owner.store,owner.runner
        self.review_observation_refs=[]
        if grant_ref is None:
            self.grant_ref,self.grant=None,None
            self.scope_ref=scope_ref;self.scope=owner._scope(scope_ref)
            request,remaining=owner._active(self.scope['request_ref'])
            self.contract,_,_,_,_,extra=owner._source(self.scope['request_ref'])
            require(request['entry_point']=='E2' and extra[3] is not None,'Only protected E2 may replay original bytes')
            self.contract_ref=self.scope['source_contract_ref'];self.check_registry=self.runner.check_registry
            self.check_plan_ref=owner.projection.create_checking_basis(scope_ref,None,'replay_subject')
            self.basis=private_record(self.store,self.check_plan_ref,'evaluation-checking-basis')
            owner.register_capture(None,'check_plan',self.check_plan_ref,request_ref=self.scope['request_ref'])
            self.inputs=self.runner._decode_inputs(self.contract);self.worker_context=None
            self.replay_output_refs=extra[3]['output_refs'];self.original_observation_ref=extra[3]['original_observation_ref']
            self.replay_output_order=self.store.read_record(self.original_observation_ref)['output_refs']
            self.replay_output_port=self.scope['selected_output_port'];self.review_ports=[self.replay_output_port]
            self.host_records=extra[3]['host_records']
            self.deadline_monotonic_s=owner._deadlines[encoded(self.scope['request_ref'])]
            for kind,pin in [('observation',self.original_observation_ref),*[('output',r) for r in self.replay_output_refs.values()]]:
                # The original producer observation retains its original kind;
                # its scope record is the typed ownership edge, not a fresh
                # private-producing observation journal alias.
                if kind=='output':owner.register_capture(None,kind,pin,request_ref=self.scope['request_ref'])
            return
        self.grant_ref=grant_ref;self.grant,self.contract,self.basis=owner.projection.load_execution(grant_ref)
        self.scope_ref=self.grant['scope_ref'];self.scope=owner._scope(self.scope_ref)
        self.contract_ref=self.grant['contract_ref'];self.check_plan_ref=self.grant['check_plan_ref'];self.check_registry=self.runner.check_registry
        self.inputs=self.runner._decode_inputs(self.contract)
        self.store.append_record('evaluation-context-origin',{'id':identity('evaluation-origin'),'contract_ref':self.contract_ref,
            'request_ref':self.grant['request_ref'],'profile_ref':owner.runtime['profile_ref'],'invalid_for_product':True})
        self.worker_context=owner.start_assignment(grant_ref,self.inputs)
        self.deadline_monotonic_s=self.runner._executions[self.grant['execution_id']]['deadline']

    def private_plan(self,ref):
        if self.grant is None:
            require(ref==self.check_plan_ref,'Replay checking basis differs')
            basis=private_record(self.store,ref,'evaluation-checking-basis')
            require(basis==self.basis and basis['request_ref']==self.scope['request_ref'],'Replay basis changed')
            return dict(basis,contract_ref=self.contract_ref)
        grant,_,basis=self.owner.projection.load_execution(self.grant_ref)
        require(ref==grant['check_plan_ref'],'Private checking basis differs')
        return dict(basis,contract_ref=self.contract_ref)

    def require_checks(self):
        self.owner._active(self.scope['request_ref'])
        if self.grant is not None:self.owner.projection.load_execution(self.grant_ref)
        else:self.owner._source(self.scope['request_ref'])
        template=self.store.read_record(self.contract['source_template_ref'] if self.grant else self.contract['template_ref'])
        self.runner.check_assets.require(template['check_bundle_ref'],self.contract['checking_profile_ref'])

    def capture_output(self,ref):
        self.owner.register_capture(self.grant_ref,'output',ref,request_ref=self.scope['request_ref'])
        if self.grant is not None:
            self.store.append_record('evaluation-output-origin',{'id':identity('evaluation-origin'),'contract_ref':self.contract_ref,'output_refs':{'captured':ref},'invalid_for_product':True})

    def capture_record(self,kind,value):
        mapping={'deterministic-check-result':'deterministic_result','trial-measurement':'measurement'}
        capture=mapping[kind];ref=self.store.append_record(PRIVATE_EVIDENCE[capture],value)
        self.owner.register_capture(self.grant_ref,capture,ref,request_ref=self.scope['request_ref']);return ref

    def capture_observation(self,*,output_refs,started_at,elapsed_s,outcome,failure):
        if self.grant is None:return self.original_observation_ref
        execution=self.runner._executions[self.grant['execution_id']]
        execution['closed']=True
        record=self.runner._observation(execution,self.contract_ref,started_at,output_refs,outcome,failure)
        ref=self.store.append_record('evaluation-invocation-observation',record)
        execution['observation_ref']=ref
        self.owner.register_capture(self.grant_ref,'observation',ref)
        return ref

    def host_results(self,*,observation_ref,output_refs,outputs):
        observation=self.store.read_record(observation_ref)
        if self.grant is None:
            rows=self.runner._host_checks(self.contract_ref,self.contract,observation,observation_ref)
            require(observation['contract_ref']==self.contract_ref and observation['output_refs']==list(output_refs.values()),'Replay output/observation inventory differs')
            projections={'runtime_observation':{r['check_id'] for r in rows},'identity_record':{'host_identity'},
                'budget_record':{'host_limits'},'tool_observation':{'host_authority'}}
            for item in self.owner.resources.admitted._host_records(self.host_records):
                supplied=self.store.read_record(item['ref'],contract_id='invocation-observation')
                measured=self.runner._host_checks(self.contract_ref,self.contract,supplied,item['ref'])
                joined=supplied['contract_ref']==self.contract_ref and supplied['id']==observation['id'] and supplied['output_refs']==list(output_refs.values())
                for result in measured:
                    if result['check_id'] not in projections[item['record_type']]:continue
                    base=next(r for r in rows if r['check_id']==result['check_id'])
                    if not joined or result['outcome']!='PASS':base['outcome']='FAIL'
                    if result['check_id']=='host_authority' and any(e not in self.contract['bindings'][0]['effective_authority']['tools'] for e in supplied['effects']):base['outcome']='FAIL'
                    base['evidence_refs'].append(item['ref'])
                    base['reason']+='; recomputed original '+item['record_type']+' projection'
            return rows
        parent=private_record(self.store,self.contract['node_contract_ref'],'evaluation-node-context')
        return self.runner._host_checks(self.contract_ref,self.contract,observation,observation_ref,validated_parent=parent)

    async def contain(self,reason):
        return await self.owner.contain_failure(self,reason)

    async def review(self,port,output_ref,deterministic_ref,observation_ref):
        profile=self.store.read_record(self.basis['profile_ref'],contract_id='checking-profile')
        from .evidence_review import MODE
        require(profile.get('review_mode') != MODE,
            'Evidence-aware v2 review is not wired into evaluation replay', 'entry_point_unavailable')
        if self.grant is None:
            require(port==self.replay_output_port and self.replay_output_refs[port]==output_ref,
                'Only the exact selected original output may be reviewed')
        else:
            from .evaluation_inspection import captured_worker_outputs
            require(captured_worker_outputs(self.store,self.scope['request_ref'],self.scope['source_contract_ref']).get(port)==output_ref,
                'Reviewer subject differs from this request producing worker')
        grant_ref=self.owner.prepare_assignment(self.scope_ref,'verifier',port)
        grant,contract,basis=self.owner.projection.load_execution(grant_ref)
        context=self.owner.start_assignment(grant_ref,{})
        await self.runner._await_start(context)
        started=utc_now();assessment=None;failure=None
        try:
            review={'schema_version':'2.0.0','id':identity('evaluation-review'),'subject_ref':output_ref,
                'contract_ref':self.contract_ref,'check_plan_ref':self.check_plan_ref,'input_refs':self.contract['input_refs'],
                'deterministic_result_ref':deterministic_ref,'criteria':[c['criterion_id'] for c in profile['criteria'] if c['blocking']],
                'observations':[observation_ref],'evidence_classes':['captured_input_and_output','invocation_observation'],
                'node_contract_ref':self.contract['node_contract_ref'],'subnode_id':self.contract['subnode_id']}
            validate('review-context',review)
            review_ref=self.store.append_record('evaluation-review-context',review)
            self.owner.register_capture(grant_ref,'review_context',review_ref)
            from .gate import SemanticVerifier,assemble_assessment,zip_projection
            from .evidence_review import EvidenceAwareSemanticVerifier
            require(type(self.runner.verifier) in (SemanticVerifier, EvidenceAwareSemanticVerifier)
                and self.runner.verifier.store is self.store,
                'Actual installed verifier mechanics unavailable','entry_point_unavailable')
            require(profile['model_call_limit']==1,'One selected semantic call required')
            criteria=[c for c in profile['criteria'] if c['target_port'] in (None,port)]
            instructions=self.store.read_blob(profile['instruction_ref']).decode('utf-8')
            instructions+='\nCriteria for this output:\n'+json.dumps(criteria,ensure_ascii=False)
            raw_output=self.store.read_blob(output_ref);subject_ref=output_ref
            from .contracts import contract_schema
            if contract_schema(next(p['contract_id'] for p in self.contract['outputs'] if p['name']==port))==contract_schema('poc-artifact-bundle'):
                raw_output=zip_projection(raw_output)
                subject_ref=self.store.put_blob(raw_output,media_type='text/plain;charset=utf-8')
                self.owner.register_capture(grant_ref,'output',subject_ref)
            payload=json.dumps({'subject_declaration':self.store.read_blob(self.contract['bindings'][0]['declaration_ref']).decode('utf-8'),
                'subject_output':raw_output.decode('utf-8')},ensure_ascii=False)
            raw=await context.model(payload,system=instructions)
            try:reply=json.loads(raw)
            except (ValueError,TypeError) as error:raise ResearchError('assessment_invalid','Verifier returned malformed JSON') from error
            value=assemble_assessment(reply,criteria,self.contract['bindings'][0]['declaration_ref'],subject_ref,review_ref)
            assessment=self.store.append_record('evaluation-verifier-assessment',value)
            self.owner.register_capture(grant_ref,'assessment',assessment)
        except BaseException as error:
            failure=getattr(error,'code',type(error).__name__);raise
        finally:
            execution=self.runner._executions[grant['execution_id']];execution['closed']=True
            observed=self.runner._observation(execution,grant['contract_ref'],started,
                {'verifier_assessment':assessment} if assessment else {},'failed' if failure else 'success',failure)
            observed_ref=self.store.append_record('evaluation-invocation-observation',observed)
            execution['observation_ref']=observed_ref
            self.owner.register_capture(grant_ref,'observation',observed_ref)
            self.review_observation_refs.append(observed_ref)
        from .checks.verifier import verifier_predicates
        profile=self.store.read_record(self.basis['profile_ref'],contract_id='checking-profile')
        criteria=[c for c in profile['criteria'] if c['target_port'] in (None,port)]
        predicates=verifier_predicates(self.store,contract,assessment,criteria,self.contract['bindings'][0]['declaration_ref'],output_ref)
        parent=private_record(self.store,self.scope['actual_node_ref'],'evaluation-node-context')
        rows=self.runner._host_checks(grant['contract_ref'],contract,observed,observed_ref,validated_parent=parent)
        known={r['check_id']:r for r in rows}
        for key in basis['mandatory_deterministic']:
            if key not in known:known[key]={'check_id':key,'outcome':'PASS' if predicates.get(key) is True else 'FAIL',
                'reason':'Independent selected reviewer mechanical predicate '+key,'evidence_refs':[observed_ref,assessment]}
        checked={'schema_version':'1.0.0','subject_ref':assessment,'check_plan_ref':grant['check_plan_ref'],
            'results':[known[k] for k in basis['mandatory_deterministic']]}
        validate('deterministic-check-result',checked)
        checked_ref=self.store.append_record('evaluation-deterministic-check-result',checked)
        self.owner.register_capture(grant_ref,'verifier_check',checked_ref)
        return {'assessment_ref':assessment,'verifier_check_ref':checked_ref,'observation_refs':[observed_ref],'trace_refs':observed['trace_refs']}

    def validate_review(self,reply,*,port,output_ref,deterministic_ref,observation_ref):
        require(type(reply) is dict and set(reply)=={'assessment_ref','verifier_check_ref','observation_refs','trace_refs'},'Malformed private review evidence')
        def owned(kind,ref):
            require(any(e['capture_ref']==ref for e in self.owner.captures(self.scope['request_ref'],kind)),
                'Private review evidence was not captured by this request')
            require(self.store.record_kind(ref)==PRIVATE_EVIDENCE[kind],'Private review evidence kind differs')
        assessment_ref,checked_ref=reply['assessment_ref'],reply['verifier_check_ref']
        owned('assessment',assessment_ref);owned('verifier_check',checked_ref)
        assessment=self.store.read_record(assessment_ref,contract_id='verifier-assessment')
        owned('review_context',assessment['review_context_ref'])
        review=self.store.read_record(assessment['review_context_ref'],contract_id='review-context')
        require(review['contract_ref']==self.contract_ref and review['check_plan_ref']==self.check_plan_ref
            and review['subject_ref']==output_ref and review['deterministic_result_ref']==deterministic_ref
            and review['observations']==[observation_ref],'Private review context targets another original subject')
        profile=self.store.read_record(self.basis['profile_ref'],contract_id='checking-profile')
        criteria=[c for c in profile['criteria'] if c['target_port'] in (None,port)]
        body={k:assessment[k] for k in ('uncertainties','limitations','required_correction')}
        body['findings']=[{k:f[k] for k in ('criterion_id','outcome','reason')} for f in assessment['findings']]
        from .gate import assemble_assessment,zip_projection
        if assessment['subject_ref']!=output_ref:
            require(self.store.read_blob(assessment['subject_ref'])==zip_projection(self.store.read_blob(output_ref)), 'Private assessment reviews different bytes')
        require(assemble_assessment(body,criteria,self.contract['bindings'][0]['declaration_ref'],assessment['subject_ref'],assessment['review_context_ref'])==assessment,'Private assessment does not follow pinned criteria')
        checked=self.store.read_record(checked_ref,contract_id='deterministic-check-result')
        basis=private_record(self.store,checked['check_plan_ref'],'evaluation-checking-basis')
        require(basis['mode']=='verifier_output' and basis['request_ref']==self.scope['request_ref']
            and basis['output_port']==port and checked['subject_ref']==assessment_ref and all_mandatory_pass(basis,checked['results']), 'Private reviewer mechanics failed')
        require(reply['observation_refs'],'Private reviewer observation missing')
        for ref in reply['observation_refs']:
            owned('observation',ref)
            observed=self.store.read_record(ref,contract_id='invocation-observation')
            require(observed['contract_ref']==basis['assignment_context_ref'] and assessment_ref in observed['output_refs'],'Private reviewer observation differs')
        for ref in reply['trace_refs']:self.store.read_blob(ref)
        return assessment_ref,checked_ref,tuple(reply['observation_refs']),tuple(reply['trace_refs'])

    def recording_decision(self,measured,port):
        plan=self.private_plan(self.check_plan_ref)
        checks=self.store.read_record(measured.deterministic_ref,contract_id='deterministic-check-result')
        eligible=all_mandatory_pass(plan,checks['results'])
        assessment=measured.assessment_refs[0] if measured.assessment_refs else None
        selected_index=0
        if self.grant is not None:
            assessment=None
            for index,pin in enumerate(measured.assessment_refs):
                reviewed=self.store.read_record(pin,contract_id='verifier-assessment')['subject_ref']
                if reviewed==measured.output_refs[port]:assessment=pin;selected_index=index;break
                from .gate import zip_projection
                try:matches=self.store.read_blob(reviewed)==zip_projection(self.store.read_blob(measured.output_refs[port]))
                except ResearchError:matches=False
                if matches:assessment=pin;selected_index=index;break
        verdict='FAIL'
        if eligible and assessment and not measured.failure:
            verdict=self.store.read_record(assessment,contract_id='verifier-assessment')['verdict']
        action='advance' if verdict in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'} and not measured.failure else 'halt'
        return {'contract_ref':self.contract_ref,'check_plan_ref':self.check_plan_ref,'output_port':port,
            'output_refs':[measured.output_refs[port]],'deterministic_result_ref':measured.deterministic_ref,
            'assessment_ref':assessment,'verifier_check_ref':measured.verifier_check_refs[selected_index] if assessment and measured.verifier_check_refs else None,
            'verdict':verdict,'action':action,'reasons':[measured.failure or ('Semantic review did not pass: '+verdict if self.grant is not None and action=='halt' else 'All mandatory checks and selected semantic criteria passed')],
            'accepted':False,'invalid_for_product':True}


def inspect_evaluation_executor_binding(store, request, *, live_owner=None):
    """Finite IF016r2 original proof; never an execution authorization."""
    from .evaluation_inspection import inspect_executor_binding
    return inspect_executor_binding(store, request, live_owner=live_owner)
