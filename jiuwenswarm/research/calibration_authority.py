"""IF014 private calibration authority. It grants no product invocation or standing."""
from __future__ import annotations
import copy
import hashlib
import inspect
import json
import math
import threading
import time
import weakref
from datetime import datetime,timezone
from .contracts import ResearchError,validate
from .state import json_bytes,utc_now


def require(value,reason,code='calibration_authority'):
    if not value:raise ResearchError(code,reason)


def epoch(value):
    try:return datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()
    except (ValueError,TypeError):raise ResearchError('calibration_authority','Whole-second UTC time is required') from None


def timestamp(value):return datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


_CAPTURE_KINDS = ('model-call','model-call-start','model-call-input','model-call-output',
    'model-provider-observation','route-record','native-governed-trace','native-governed-trace-event')
_AUDIT_CACHES = weakref.WeakKeyDictionary()
_AUDIT_CACHES_LOCK = threading.RLock()


class _CaptureAuditIndex:
    """Process-local index of exact captures in one append-only Store.

    Neither a cursor nor a cached marker supplies acceptance. They only avoid
    rereading immutable bytes already verified in this exact Store instance.
    Every new record is read through its original Ref before indexing, and
    every newly attributed Ref still receives its original durable marker.
    """
    def __init__(self, store):
        self.connection = store.connection
        self.lock = threading.RLock()
        self.frontier = 0
        self.by_run, self.by_execution, self.by_call = {}, {}, {}
        self.marked = set()

    def refresh(self, store):
        require(self.connection is store.connection, 'Calibration audit Store connection changed')
        # Fence the append-only population first. A packet appended after this
        # fence is inspected on the next joined audit, never skipped by a
        # cursor advanced beyond a record which has not been read.
        with store._lock:
            fence = store.connection.execute('SELECT COALESCE(MAX(rowid),0) FROM records').fetchone()[0]
            require(fence >= self.frontier, 'Calibration audit capture history regressed')
            rows = store.connection.execute(
                'SELECT r.rowid AS ordinal,r.kind,r.id,a.sha256 FROM records r '
                'JOIN artifacts a ON a.id=r.id WHERE r.rowid>? AND r.rowid<=? AND r.kind IN (' +
                ','.join('?' for _ in _CAPTURE_KINDS) + ') ORDER BY r.rowid',
                (self.frontier, fence, *_CAPTURE_KINDS)).fetchall()
        for row in rows:
            ref = {'id':row['id'], 'sha256':row['sha256']}
            value = store.read_record(ref)
            scope = value.get('scope', {})
            extras = []
            if row['kind'] == 'model-call':extras.extend(value['evidence_refs'])
            if row['kind'] == 'native-governed-trace':extras.extend(value['event_refs'])
            if row['kind'] == 'native-governed-trace-event':extras.append(value['raw_ref'])
            entry = (row['ordinal'], ref, extras)
            key = json_bytes(ref)
            for index, identity in ((self.by_run,value.get('run_id')),
                    (self.by_execution,value.get('execution_id')),
                    (self.by_execution,scope.get('execution_id')),
                    (self.by_call,value.get('call_id',value.get('id')))):
                if identity is not None:index.setdefault(identity,{})[key] = entry
        self.frontier = fence


def _audit_cache(store):
    with _AUDIT_CACHES_LOCK:
        cached = _AUDIT_CACHES.get(store)
        if cached is None:
            cached = _CaptureAuditIndex(store)
            _AUDIT_CACHES[store] = cached
        require(cached.connection is store.connection, 'Calibration audit Store connection changed')
        return cached


def semantic_prompt(store,case,profile):
    """The existing one-text verifier encoding, with no labels or host context."""
    from .gate import zip_projection
    from .checks.verifier import contract_is
    declaration=store.read_record(case['declaration_ref'],contract_id='capsule-declaration')
    port=next(p for p in declaration['ports']['outputs'] if p['name']==case['output_port'])
    raw=store.read_blob(case['subject_ref'])
    if contract_is(port['schema_ref'],'poc-artifact-bundle'):raw=zip_projection(raw)
    criteria=[c for c in profile['criteria'] if c['target_port'] in (None,case['output_port'])]
    instructions=store.read_blob(profile['instruction_ref']).decode('utf-8')
    instructions+='\nCriteria for this output:\n'+json.dumps(criteria,ensure_ascii=False)
    payload=json.dumps({'subject_declaration':store.read_blob(case['declaration_ref']).decode('utf-8'),
        'subject_output':raw.decode('utf-8')},ensure_ascii=False)
    return instructions+'\n\n<subject_payload>\n'+payload+'\n</subject_payload>'


class CalibrationAuthority:
    def __init__(self,store,runtime_ref,*,configuration_ref,model_selection_profile_ref,deployment_ref,policy_ref,model=None):
        from .checks.assets import CheckAssetAdmissions
        self.store=store;self.runtime_ref=copy.deepcopy(runtime_ref);self.model=model
        self.admissions=CheckAssetAdmissions(store)
        self.runtime=store.read_record(runtime_ref);validate('urn:ai4r:private:calibration-runtime:1',self.runtime)
        require(store.record_kind(runtime_ref)=='calibration-runtime','Runtime must be a protected indexed capture')
        for key,ref in [('configuration_ref',configuration_ref),('model_selection_profile_ref',model_selection_profile_ref),('deployment_ref',deployment_ref)]:
            require(self.runtime[key]==ref,'Runtime differs from actual protected startup');store.read_blob(ref)
        self.policy_ref=copy.deepcopy(policy_ref);policy=store.read_record(policy_ref,contract_id='plan-policy')
        require(all(self.runtime['limits'][key]<=policy['aggregate_limits'][key] for key in ('time_s','model_calls','memory_mb')),'Runtime exceeds approved aggregate policy')
        selection=store.read_record(model_selection_profile_ref,contract_id='model-selection-profile')
        require(selection['policy_mode']=='fixed_baseline' and selection['approved_model_ids']==['codex-cli-default'],'Calibration requires the protected fixed subscription baseline')
        require(selection['policy_ref']==policy_ref,'Selection profile names another approved policy')
        self.selection=selection
        try:deployment=store.read_record(deployment_ref)
        except (ResearchError,ValueError,UnicodeError):deployment={}
        self.requested_model=(deployment.get('requested_model')
            if isinstance(deployment,dict) and deployment.get('schema')=='ai4r-fixed-subscription:1' else None)
        if self.requested_model is not None:
            require(self.requested_model in {'gpt-6.1-sol','gpt-6-luna'},'Local fixed deployment requires an exact supported model')
        from importlib.resources import files
        catalog=json.loads(files('jiuwenswarm.research_assets').joinpath('catalog.json').read_text('utf-8'))
        entry=catalog['capsules']['verifier'];raw=store.read_blob(self.runtime['verifier_declaration_ref'])
        require(hashlib.sha256(raw).hexdigest()==entry['declaration_sha256'],'Runtime verifier is not the exact installed declaration')
        self.verifier=store.read_record(self.runtime['verifier_declaration_ref'],contract_id='capsule-declaration')
        for body in entry['body']:
            require(hashlib.sha256(files('jiuwenswarm').joinpath(body['path']).read_bytes()).hexdigest()==body['sha256'],'Installed verifier implementation changed')
        approved=self.runtime['approved_profile_refs'];require(len({json_bytes(r) for r in approved})==len(approved),'Duplicate approved profiles')
        require(set(self.runtime['case_context_refs'])=={r['sha256'] for r in approved},'Context mapping differs from exact approved profiles')
        with store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS private_calibration_requests (
                id TEXT PRIMARY KEY,request_ref TEXT NOT NULL,state TEXT NOT NULL,started_epoch REAL NOT NULL,
                deadline_epoch REAL NOT NULL,calls INTEGER NOT NULL,receipt_ref TEXT,cancel_id TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS private_calibration_grants (
                execution_id TEXT PRIMARY KEY,request_id TEXT NOT NULL,case_id TEXT NOT NULL,grant_ref TEXT NOT NULL,
                started_epoch REAL NOT NULL,deadline_epoch REAL NOT NULL,UNIQUE(request_id,case_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS private_calibration_calls (
                request_id TEXT NOT NULL,case_id TEXT NOT NULL,ordinal INTEGER NOT NULL,call_id TEXT NOT NULL UNIQUE,
                claim_ref TEXT NOT NULL,execution_id TEXT NOT NULL UNIQUE,PRIMARY KEY(request_id,case_id,ordinal))''')

    def _profile(self,ref):
        require(ref in self.runtime['approved_profile_refs'],'Profile is not explicitly runtime-approved')
        profile,closure=self.admissions._profile(ref)
        require(set(self.runtime['case_context_refs'][ref['sha256']])=={c['case_id'] for c in profile['cases']},'Every exact case needs a protected context capture')
        for case in profile['cases']:self.context(ref,case)
        return profile,closure

    def context(self,profile_ref,case):
        ref=self.runtime['case_context_refs'][profile_ref['sha256']][case['case_id']]
        value=self.store.read_record(ref)
        require(isinstance(value,dict) and set(value)=={'contract_ref','observation_ref','output_refs'},'Unknown protected case context fields')
        contract=self.store.read_record(value['contract_ref']);fixture=contract.get('schema')=='ai4r-calibration-fixture:2'
        private=contract.get('schema')=='ai4r-calibration-subject:1' or fixture
        if fixture:
            require(value['observation_ref'] is None,'A static development fixture must not claim a product invocation observation')
            require(set(contract)=={'schema','id','declaration_ref','bindings','run_id','node_id','subnode_id','attempt_id',
                'inputs','input_refs','outputs','accepted','invalid_for_product'},'Static fixture fields are closed')
            require(contract['bindings']==[{'declaration_ref':case['declaration_ref']}]
                and contract['run_id']=='calibration-fixture','Static fixture cannot carry runtime authority or a product Run identity')
        if private:
            require(contract.get('declaration_ref')==case['declaration_ref'],'Private subject declaration differs from case')
        else:
            validate('subnode-execution-contract',contract)
            require(contract['bindings'][0]['declaration_ref']==case['declaration_ref'],'Original context declaration differs from case')
        require(isinstance(value['output_refs'],dict) and value['output_refs'].get(case['output_port'])==case['subject_ref'],'Case subject differs from exact output capture')
        for output in value['output_refs'].values():validate('Ref',output);self.store.read_blob(output)
        if value['observation_ref'] is None:
            # Static development cases exercise the real installed predicates
            # over captured inputs. They are not product invocations and must
            # never invent an invocation-observation to stand in for one.
            require(private and (fixture or not contract.get('inputs') and not contract.get('input_refs')),
                'Only protected static fixtures or output-only private subjects may omit actual host observation')
            if fixture:
                require(self.store.record_kind(value['contract_ref'])=='calibration-fixture'
                    and contract.get('invalid_for_product') is True and contract.get('accepted') is False,
                    'Static fixture has no product execution or acceptance authority')
                require(contract.get('input_refs')==[r for p in contract['inputs'] for r in p['artifact_refs']],
                    'Static fixture input inventory differs from its captured bindings')
                for ref in contract['input_refs']:self.store.read_blob(ref)
        else:
            observation=self.store.read_record(value['observation_ref'],contract_id='invocation-observation')
            require(observation['contract_ref']==value['contract_ref'] and observation['output_refs']==list(value['output_refs'].values()),'Original host observation/context/output differs')
        return copy.deepcopy(value)

    def register(self,profile_ref,actor):
        from .checks.calibration import CalibrationMeasurements
        from pathlib import Path
        profile,_=self._profile(profile_ref)
        require(self.store.read_blob(profile['measurement_runner_ref'])==Path(inspect.getfile(CalibrationMeasurements)).read_bytes(),'Profile does not pin the installed measurement adapter')
        return self.admissions.register_profile(profile_ref,actor)

    def start(self,profile_ref,actor,action_id):
        actor.require('verifier_assets');require(isinstance(action_id,str) and action_id,'Exact immutable action identity is required')
        require(profile_ref in self.runtime['approved_profile_refs'],'Profile is not explicitly runtime-approved')
        request_id='calibration-request:'+hashlib.sha256(json_bytes([actor.account_id,action_id])).hexdigest()
        with self.store.transaction() as db:
            prior=db.execute('SELECT * FROM private_calibration_requests WHERE id=?',(request_id,)).fetchone()
            if prior:
                ref=json.loads(prior['request_ref']);old=self.store.read_record(ref)
                require(old['calibration_profile_ref']==profile_ref and old['runtime_ref']==self.runtime_ref,'Human action identity names different calibration bytes')
                return ref
            began=time.time();expires=math.floor(began+self.runtime['limits']['time_s'])
            require(expires>math.floor(began),'Whole request has no positive wall allowance')
            record={'schema':'ai4r-check-calibration-request:1','id':request_id,'actor_id':actor.account_id,'operation':'verifier_assets',
                'calibration_profile_ref':profile_ref,'runtime_ref':self.runtime_ref,'created_at':timestamp(began),'expires_at':timestamp(expires)}
            validate('urn:ai4r:private:check-calibration-request:1',record)
            ref={'id':request_id,'sha256':hashlib.sha256(json_bytes(record)).hexdigest()}
            db.execute('INSERT INTO private_calibration_requests VALUES(?,?,?,?,?,0,NULL,NULL)',
                (request_id,json_bytes(ref).decode(),'running',began,min(began+self.runtime['limits']['time_s'],expires)))
        actual=self.store.append_record('check-calibration-request',record);require(actual==ref,'Durable request identity changed')
        self.store.append_record('calibration-request-start',{'id':request_id+':start','request_ref':ref,'started_epoch':began,'deadline_epoch':min(began+self.runtime['limits']['time_s'],expires)})
        return actual

    def _request(self,ref,*,active=True):
        request=self.store.read_record(ref);validate('urn:ai4r:private:check-calibration-request:1',request)
        require(self.store.record_kind(ref)=='check-calibration-request' and request['runtime_ref']==self.runtime_ref,'Request is not this registered private runtime')
        with self.store._lock:row=self.store.connection.execute('SELECT * FROM private_calibration_requests WHERE id=?',(request['id'],)).fetchone()
        require(row is not None and json.loads(row['request_ref'])==ref,'No exact durable request-start claim')
        require(epoch(request['expires_at'])>epoch(request['created_at']),'Request time ordering is invalid')
        if active:
            require(row['state']=='running','Calibration request is closed or uncertain')
            require(time.time()<min(row['deadline_epoch'],epoch(request['expires_at'])),'Absolute request deadline expired','calibration_deadline')
        return request,row

    def prepare_calibration_case(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'request_ref','case_id'},'Finite case request only accepts exact identity')
        request,row=self._request(payload['request_ref']);profile,_=self.admissions._registered(request['calibration_profile_ref'])[:2]
        # _registered returns profile, closure, registration; no unregistered path.
        case=next((c for c in profile['cases'] if c['case_id']==payload['case_id']),None)
        require(case is not None and case['asset_kind']=='criteria','Only preregistered semantic cases receive model authority')
        self.context(request['calibration_profile_ref'],case)
        checked=self.store.read_record(profile['profile_ref'],contract_id='checking-profile')
        remaining=min(row['deadline_epoch'],epoch(request['expires_at']))-time.time()
        wall=min(remaining,checked['time_s'],self.verifier['budget']['per_call']['wall_s'])
        require(wall>0 and checked['model_call_limit']>=1 and self.verifier['budget']['per_call']['invocations']>=1,'Pinned verifier has no semantic allowance')
        execution='calibration-execution:'+hashlib.sha256(json_bytes([payload['request_ref'],case['case_id']])).hexdigest()
        with self.store._lock:prior=self.store.connection.execute('SELECT grant_ref FROM private_calibration_grants WHERE execution_id=?',(execution,)).fetchone()
        if prior:return {'grant_ref':json.loads(prior['grant_ref'])}
        now=time.time();record={'schema':'ai4r-calibration-case-grant:1','id':'calibration-grant:'+execution.split(':',1)[1],
            'request_ref':payload['request_ref'],'calibration_profile_ref':request['calibration_profile_ref'],'case_id':case['case_id'],
            'subject_declaration_ref':case['declaration_ref'],'subject_ref':case['subject_ref'],'checking_profile_ref':profile['profile_ref'],
            'instruction_ref':checked['instruction_ref'],'context_ref':self.runtime['case_context_refs'][request['calibration_profile_ref']['sha256']][case['case_id']],
            **{k:self.runtime[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')},
            'limits':{'time_s':wall,'model_calls':1,'memory_mb':self.runtime['limits']['memory_mb']},'execution_id':execution,
            'invocation_id':'calibration-invocation:'+execution.split(':',1)[1],
            'expected_prompt_sha256':hashlib.sha256(semantic_prompt(self.store,case,checked).encode()).hexdigest(),
            'created_at':timestamp(now),'expires_at':request['expires_at']}
        validate('urn:ai4r:private:calibration-case-grant:1',record)
        grant=self.store.append_record('calibration-case-grant',record)
        with self.store.transaction() as db:db.execute('INSERT INTO private_calibration_grants VALUES(?,?,?,?,?,?)',(execution,request['id'],case['case_id'],json_bytes(grant).decode(),now,min(row['deadline_epoch'],now+wall)))
        self.mark([grant]);return {'grant_ref':grant}

    def _grant(self,execution):
        with self.store._lock:row=self.store.connection.execute('SELECT * FROM private_calibration_grants WHERE execution_id=?',(execution,)).fetchone()
        require(row is not None,'No registered private calibration execution')
        ref=json.loads(row['grant_ref']);grant=self.store.read_record(ref);validate('urn:ai4r:private:calibration-case-grant:1',grant)
        request,request_row=self._request(grant['request_ref'])
        profile,closure,_=self.admissions._registered(grant['calibration_profile_ref'])
        case=next((c for c in profile['cases'] if c['case_id']==grant['case_id']),None)
        require(case is not None and case['asset_kind']=='criteria','Private grant is not a semantic case')
        checked=self.store.read_record(profile['profile_ref'],contract_id='checking-profile');context=self.context(grant['calibration_profile_ref'],case)
        expected={'request_ref':json.loads(request_row['request_ref']),'calibration_profile_ref':request['calibration_profile_ref'],
            'subject_declaration_ref':case['declaration_ref'],'subject_ref':case['subject_ref'],'checking_profile_ref':profile['profile_ref'],
            'instruction_ref':checked['instruction_ref'],'context_ref':self.runtime['case_context_refs'][grant['calibration_profile_ref']['sha256']][case['case_id']],
            **{k:self.runtime[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')},
            'expected_prompt_sha256':hashlib.sha256(semantic_prompt(self.store,case,checked).encode()).hexdigest()}
        require(all(grant[key]==value for key,value in expected.items()),'Grant no longer matches preregistered exact closure/payload')
        require(grant['execution_id']==execution and grant['case_id']==row['case_id'] and request['id']==row['request_id'],'Grant identity differs from durable execution')
        require(epoch(grant['expires_at'])>epoch(grant['created_at']),'Grant time ordering is invalid')
        require(grant['limits']['model_calls']==1 and grant['limits']['memory_mb']<=self.runtime['limits']['memory_mb']
            and grant['limits']['time_s']<=min(checked['time_s'],self.verifier['budget']['per_call']['wall_s'],self.runtime['limits']['time_s']),
            'Case limits exceed the independent pinned verifier/profile/runtime')
        require(time.time()<row['deadline_epoch'],'Original case deadline expired','calibration_deadline')
        return ref,grant,request,dict(request_row,case_deadline_epoch=row['deadline_epoch'])

    def prompt(self,grant_ref):
        grant=self.store.read_record(grant_ref);_,actual,_,_=self._grant(grant['execution_id']);require(grant==actual,'Foreign grant')
        profile,_,_=self.admissions._registered(grant['calibration_profile_ref'])
        case=next(c for c in profile['cases'] if c['case_id']==grant['case_id'])
        return semantic_prompt(self.store,case,self.store.read_record(profile['profile_ref']))

    def owns_execution(self,execution):return isinstance(execution,str) and execution.startswith('calibration-execution:')
    def owns_run(self,run_id):return isinstance(run_id,str) and run_id.startswith('calibration-run:')

    def authorize_model_context(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'execution_id','call_ordinal'} and type(payload['call_ordinal']) is int and payload['call_ordinal']==1,'One exact private semantic call ordinal is required')
        ref,grant,request,row=self._grant(payload['execution_id']);now=time.time()
        remaining=min(row['deadline_epoch']-now,row['case_deadline_epoch']-now,epoch(grant['expires_at'])-now)
        require(remaining>0,'Calibration case expired','calibration_deadline')
        # Source ModelCall IDs are at most 64 lower-case identifier characters.
        call_id='calibration-call:'+hashlib.sha256(json_bytes([ref,1])).hexdigest()[:40]
        protected={'run_id':'calibration-run:'+request['id'].split(':',1)[1],'node_id':'calibration','subnode_id':grant['case_id'],
            'attempt_id':'calibration-attempt:'+request['id'].split(':',1)[1],'execution_id':grant['execution_id'],'invocation_id':grant['invocation_id'],
            'call_ordinal':1,'call_id':call_id,'call_function':'verifier','cc_name':self.verifier['identity']['name'],
            'cc_version':self.verifier['identity']['version_label'],'contract_ref':ref,'input_refs':[],
            **{k:self.runtime[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')},
            'model_selection_profile':copy.deepcopy(self.selection),'approved_model_ids':copy.deepcopy(self.selection['approved_model_ids']),
            'router':{'enabled':False,'deadline_s':30,'profile_ref':None},'limits':dict(grant['limits'],time_s=remaining),
            'execution_deadline_monotonic_s':time.monotonic()+remaining,'expected_prompt_sha256':grant['expected_prompt_sha256']}
        if self.requested_model is not None:protected['requested_model']=self.requested_model
        claim_record=dict(protected,id=call_id+':claim',request_ref=grant['request_ref'],grant_ref=ref,
            case_id=grant['case_id'],ordinal=1,claimed_at=utc_now(),claimed_epoch=time.time())
        claim={'id':claim_record['id'],'sha256':hashlib.sha256(json_bytes(claim_record)).hexdigest()}
        with self.store.transaction() as db:
            fresh=db.execute('SELECT * FROM private_calibration_requests WHERE id=?',(request['id'],)).fetchone()
            require(fresh['state']=='running' and time.time()<fresh['deadline_epoch'],'Request stopped before durable call claim')
            require(fresh['calls']<self.runtime['limits']['model_calls'],'Private request aggregate call allowance exhausted')
            require(db.execute('SELECT 1 FROM private_calibration_calls WHERE execution_id=?',(grant['execution_id'],)).fetchone() is None,'Private semantic call already claimed; reconcile without replay')
            db.execute('INSERT INTO private_calibration_calls VALUES(?,?,?,?,?,?)',(request['id'],grant['case_id'],1,call_id,json_bytes(claim).decode(),grant['execution_id']))
            db.execute('UPDATE private_calibration_requests SET calls=calls+1 WHERE id=?',(request['id'],))
        require(self.store.append_record('calibration-call-claim',claim_record)==claim,'Durable private claim publication changed')
        self.mark([claim]);return dict(protected,call_claim_ref=claim)

    def authorize_model_dispatch(self,payload):
        fields={'execution_id','invocation_id','call_id','call_claim_ref','contract_ref'}
        require(isinstance(payload,dict) and set(payload)==fields,'Exact existing private call claim required')
        ref,grant,request,row=self._grant(payload['execution_id'])
        with self.store._lock:claimed=self.store.connection.execute('SELECT * FROM private_calibration_calls WHERE execution_id=?',(payload['execution_id'],)).fetchone()
        require(claimed is not None and json.loads(claimed['claim_ref'])==payload['call_claim_ref'],'No exact durable private call claim')
        claim=self.store.read_record(payload['call_claim_ref'])
        require(all(claim.get(k)==payload[k] for k in fields-{'call_claim_ref'}) and ref==payload['contract_ref'],'Private dispatch claim/context mismatch')
        remaining=min(row['deadline_epoch']-time.time(),row['case_deadline_epoch']-time.time(),claim['execution_deadline_monotonic_s']-time.monotonic())
        require(remaining>0,'Private call deadline expired','calibration_deadline')
        require(claim['expected_prompt_sha256']==grant['expected_prompt_sha256'],'Private prompt authority changed')
        return dict(copy.deepcopy(claim),call_claim_ref=copy.deepcopy(payload['call_claim_ref']),limits=dict(claim['limits'],time_s=remaining),execution_deadline_monotonic_s=time.monotonic()+remaining)

    def inspect_calibration(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'request_ref'},'Inspection accepts only exact request identity')
        _,row=self._request(payload['request_ref'],active=False)
        return {'state':row['state'],'receipt_ref':json.loads(row['receipt_ref']) if row['receipt_ref'] else None}

    def authorize_containment(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'run_id','request_id'},'Exact private containment identity required')
        request_id='calibration-request:'+payload['run_id'].removeprefix('calibration-run:')
        with self.store._lock:row=self.store.connection.execute('SELECT * FROM private_calibration_requests WHERE id=?',(request_id,)).fetchone()
        require(row is not None and row['cancel_id']==payload['request_id'] and row['state'] in {'cancelling','containment_unknown','cancelled'},'No durable private cancellation request')
        with self.store._lock:grants=self.store.connection.execute('SELECT grant_ref FROM private_calibration_grants WHERE request_id=?',(request_id,)).fetchall()
        return {'authorized':True,**payload,'invocation_ids':[self.store.read_record(json.loads(g['grant_ref']))['invocation_id'] for g in grants]}

    async def cancel_calibration(self,payload):
        require(isinstance(payload,dict) and set(payload)=={'request_ref'},'Cancellation accepts only exact request identity')
        request,row=self._request(payload['request_ref'],active=False);cancel='calibration-cancel:'+request['id'].split(':',1)[1]
        run_id='calibration-run:'+request['id'].split(':',1)[1]
        if row['state']=='cancelled' and row['cancel_id']==cancel:
            prior=self.store.read_record(self.store.record_ref(cancel))
            require(prior.get('request_ref')==payload['request_ref'] and prior.get('contained') is True
                and prior.get('owner_ack')=={'contained':True,'run_id':run_id,'request_id':cancel},
                'Prior cancellation lacks its original scoped owner acknowledgement','calibration_containment_uncertain')
            return {'contained':True,'request_ref':payload['request_ref']}
        with self.store.transaction() as db:db.execute("UPDATE private_calibration_requests SET state='cancelling',cancel_id=? WHERE id=?",(cancel,request['id']))
        try:
            require(self.model is not None,'Managed model owner is unavailable')
            ack=self.model.contain_run(run_id,cancel)
            if inspect.isawaitable(ack):ack=await ack
            require(isinstance(ack,dict) and ack.get('contained') is True and ack.get('run_id')==run_id and ack.get('request_id')==cancel,
                'Actual model owner containment scope is unconfirmed','calibration_containment_uncertain')
        except BaseException:
            with self.store.transaction() as db:db.execute("UPDATE private_calibration_requests SET state='containment_unknown' WHERE id=?",(request['id'],))
            raise ResearchError('calibration_containment_uncertain','Actual calibration model containment is unconfirmed') from None
        receipt=self.store.append_record('calibration-containment',{'id':cancel,'request_ref':payload['request_ref'],'contained':True,
            'owner_ack':{'contained':True,'run_id':run_id,'request_id':cancel},'recorded_at':utc_now()})
        with self.store.transaction() as db:db.execute("UPDATE private_calibration_requests SET state='cancelled' WHERE id=?",(request['id'],))
        self.mark([receipt]);return {'contained':True,'request_ref':payload['request_ref']}

    def mark(self,refs):
        cached = _audit_cache(self.store)
        with cached.lock:
            for ref in refs:
                key = json_bytes(ref)
                if key in cached.marked:continue
                self.store.read_blob(ref);identity=hashlib.sha256(key).hexdigest()
                marker={'id':'calibration-material:'+identity,'artifact_ref':ref,'calibration_only':True}
                with self.store._lock:
                    present=self.store.connection.execute('SELECT 1 FROM records WHERE id=? AND kind=?',
                        (marker['id'],'calibration-material')).fetchone()
                if present:
                    require(self.store.read_record(self.store.record_ref(marker['id']))==marker,
                        'Existing calibration origin marker differs from its exact source')
                else:self.store.append_record('calibration-material',marker)
                # Cache only a successfully checked/persisted exact marker.
                cached.marked.add(key)

    def capture_produced(self,request_ref):
        """Taint only new captures; original subject/context/instruction refs stay original."""
        request,_=self._request(request_ref,active=False)
        with self.store._lock:rows=self.store.connection.execute('SELECT * FROM private_calibration_calls WHERE request_id=?',(request['id'],)).fetchall()
        executions={r['execution_id'] for r in rows};calls={r['call_id'] for r in rows}
        cached = _audit_cache(self.store)
        with cached.lock:
            cached.refresh(self.store)
            matched = dict(cached.by_run.get('calibration-run:'+request['id'].split(':',1)[1], {}))
            for identity in executions:matched.update(cached.by_execution.get(identity, {}))
            for identity in calls:matched.update(cached.by_call.get(identity, {}))
            refs = []
            for _, ref, extras in sorted(matched.values(), key=lambda entry:entry[0]):
                refs.extend((ref,*extras))
            if refs:self.mark(list({json_bytes(r):r for r in refs}.values()))

    async def capture_produced_async(self,request_ref):
        """Join audit-only work without blocking other owned IPC returns."""
        import asyncio
        audit=asyncio.create_task(asyncio.to_thread(self.capture_produced,request_ref))
        try:await asyncio.shield(audit)
        except asyncio.CancelledError:
            # Request expiry/cancellation still forbids acceptance. Join the
            # finite capture worker before propagating it; no orphan task may
            # keep writing after this operation reports containment.
            try:await audit
            except Exception:pass
            raise

    def _mark_measurements(self,refs):
        self.mark(refs)
        for measured in refs:
            actual=self.store.read_record(measured).get('result')
            if actual:
                produced=[actual['result_ref'],*actual['model_call_refs']];record=self.store.read_record(actual['result_ref'])
                for field in ('check_plan_ref','review_context_ref'):
                    if field in record:produced.append(record[field])
                self.mark(produced)

    async def execute(self,profile_ref,actor,action_id):
        """Explicit OS operation. Startup construction and inspection make no calls."""
        request=self.start(profile_ref,actor,action_id);state=self.inspect_calibration({'request_ref':request})
        if state['receipt_ref'] is not None:return self.store.read_record(state['receipt_ref'])
        request_record,row=self._request(request)
        execution_key='calibration-execute:'+request_record['id']
        with self.store.transaction() as db:
            require(db.execute('SELECT 1 FROM metadata WHERE key=?',(execution_key,)).fetchone() is None,'Issued request has uncertain completion; reconcile without replay')
            db.execute('INSERT INTO metadata VALUES(?,?)',(execution_key,json_bytes({'request_ref':request}).decode()))
        result={'id':request_record['id']+':result','request_ref':request,'status':'blocked','measurement_refs':[],
            'bundle_admission_ref':None,'criteria_admission_ref':None,'reason_code':None,'recorded_at':utc_now()}
        import asyncio
        admitted=None
        try:
            from .checks import CheckRegistry
            from .checks.calibration import CalibrationMeasurements
            from .checks.calibration_runtime import prepare_calibration_checks,CalibrationModelPort
            deadline=time.monotonic()+max(0,row['deadline_epoch']-time.time())
            async with asyncio.timeout_at(deadline):
                self._request(request)
                checks=CheckRegistry();await prepare_calibration_checks(self.store,checks)
                await asyncio.sleep(0);self._request(request)
                profile,_=self._profile(profile_ref)
                contexts={(profile_ref['sha256'],case['case_id']):self.context(profile_ref,case) for case in profile['cases']}
                ports={(profile_ref['sha256'],case['case_id']):CalibrationModelPort(self,request,case['case_id']) for case in profile['cases'] if case['asset_kind']=='criteria'}
                producer=CalibrationMeasurements(self.admissions,checks,case_contexts=contexts,model_ports=ports,private_request_ref=request)
                producer.install(profile_ref,actor);self._request(request)
                result['measurement_refs']=await self.admissions.measure(profile_ref,actor,stop_on_failure=True)
                await asyncio.sleep(0);self._request(request)
                admitted=self.admissions.admit(profile_ref,actor,publish=False,guard=lambda:self._request(request))
                result.update(bundle_admission_ref=admitted['bundle'],criteria_admission_ref=admitted['criteria'])
                result['status']='completed' if all(self.store.read_record(ref)['status']=='admitted' for ref in admitted.values()) else 'blocked'
                await self.capture_produced_async(request);self._mark_measurements(result['measurement_refs'])
                await asyncio.sleep(0);self._request(request)
                receipt=self.store.append_record('calibration-request-result',result);self.mark([receipt])
                self._request(request)
                def commit(db):
                    db.execute('UPDATE private_calibration_requests SET state=?,receipt_ref=? WHERE id=?',
                        (result['status'],json_bytes(receipt).decode(),request_record['id']))
                self.admissions.publish_admissions(admitted,guard=lambda:self._request(request),commit=commit)
                return result
        except BaseException as error:
            result['status']='blocked';result['id']+=':failed';result['reason_code']=getattr(error,'code',type(error).__name__)
            if isinstance(error,(asyncio.CancelledError,TimeoutError)) or getattr(error,'code',None)=='calibration_deadline':
                try:await self.cancel_calibration({'request_ref':request})
                except ResearchError as containment:result['containment_reason_code']=containment.code
        # measure() can be interrupted after publishing earlier case receipts.
        # Recover those original captures rather than treating its unreturned
        # aggregate list as proof that no measurement happened.
        with self.store._lock:
            registered=self.store.connection.execute('SELECT registration_ref FROM calibration_profiles WHERE profile_sha=?',(profile_ref['sha256'],)).fetchone()
        registration=json.loads(registered['registration_ref']) if registered else None
        result['measurement_refs']=[row['ref'] for row in self.store.iter_records(kinds=('calibration-measurement',))
            if registration is not None and row['record'].get('profile_ref')==profile_ref and row['record'].get('registration_ref')==registration]
        await self.capture_produced_async(request);self._mark_measurements(result['measurement_refs'])
        receipt=self.store.append_record('calibration-request-result',result);self.mark([receipt])
        current=self.inspect_calibration({'request_ref':request})['state']
        final_state=current if current in {'cancelled','containment_unknown','cancelling'} else result['status']
        with self.store.transaction() as db:
            db.execute('UPDATE private_calibration_requests SET state=?,receipt_ref=? WHERE id=?',
                (final_state,json_bytes(receipt).decode(),request_record['id']))
        return result

