"""Custodian-only IF011 transport and signed projections of the existing ledger.

No operation is installed on the ordinary jobs socket. Hidden labels, oracle
paths and signing material are never part of a trial binding or result.
"""
from __future__ import annotations
import asyncio,base64,hashlib,json,uuid
from importlib.resources import files
from jsonschema import Draft202012Validator
from .records import encoded
from .signing import verify


def external_inputs(binding):
    """Version2 explicitly freezes only the two external research ports."""
    version=binding.get('schema')
    if version in {'ai4r-isolated-evaluation-binding:2','ai4r-admitted-measurement-binding:2'}:
        if not isinstance(binding.get('inputs'),list) or any(not isinstance(p,dict) for p in binding['inputs']) or [p.get('name') for p in binding['inputs']]!=['brief','candidate_set']:
            raise ValueError('Current binding requires canonical external brief/candidate_set only')
        for port in binding['inputs']:
            if set(port)!={'name','contract_id','artifact_refs'} or not port['artifact_refs']:
                raise ValueError('Invalid exact external input binding')
            # Canonical source aliases are resolved independently by core. Do
            # not maintain a second contract-identity allowlist here.
    elif version not in {'ai4r-isolated-evaluation-binding:1','ai4r-admitted-measurement-binding:1'}:
        raise ValueError('Unknown explicit private binding version')
    return binding['inputs']


def validate_private(name,value):
    suffix='.v2' if name=='binding' and value.get('schema')=='ai4r-isolated-evaluation-binding:2' else ''
    schema=json.loads((files('jiuwenswarm.research_contracts')/'schemas'/('isolated-evaluation-'+name+suffix+'.schema.json')).read_bytes())
    if next(Draft202012Validator(schema).iter_errors(value),None) is not None:
        raise ValueError('Invalid owning IF011 '+name)


def validate_parent(name,value):
    if name not in {'binding','grant','result'}:raise ValueError('Unknown private parent record')
    suffix='.v2' if name=='binding' and value.get('schema')=='ai4r-admitted-measurement-binding:2' else ''
    schema=json.loads((files('jiuwenswarm.research_contracts')/'schemas'/('admitted-measurement-'+name+suffix+'.schema.json')).read_bytes())
    if next(Draft202012Validator(schema).iter_errors(value),None) is not None:
        raise ValueError('Invalid owning IF012 '+name)


def verify_reservation(record,binding,public_key,key_id,*,target=None,session=None):
    keys={'schema','id','session_ref','target_ref','child_declaration_ref','phase','repeat_index','inputs_sha256','configuration_ref',
        'action_id','charge_kind','queries_used','queries_left','signer_key_id','signature'}
    version=2 if binding.get('schema')=='ai4r-isolated-evaluation-binding:2' else 1
    if not isinstance(record,dict) or set(record)!=keys or record['schema'] not in {'ai4r-rsi-trial-reservation:'+str(version),*({'ai4r-rsi-trial-reservation:3'} if version==2 else set())}:raise ValueError('Unknown trial reservation version')
    external_inputs(binding)
    verify(record,public_key,key_id)
    if record['schema'].endswith(':3'):
        from jiuwenswarm.research.measurement_slots import parse_slot
        if target is None or session is None:raise ValueError('Frozen slot target/session unavailable')
        parse_slot(record,binding,target,session)
    for key in ('session_ref','target_ref','child_declaration_ref','phase','repeat_index','configuration_ref'):
        if record[key]!=binding[key]:raise ValueError('Reservation differs from the exact trial')
    if record['inputs_sha256']!=hashlib.sha256(encoded(binding['inputs'])).hexdigest():raise ValueError('Reserved legitimate inputs changed')
    expected={'development':'development','hidden_loop':'loop','hidden_final':'final','platform':'final'}[binding['phase']]
    if record['charge_kind']!=expected or type(record['queries_used']) is not int or type(record['queries_left']) is not int or not 0<=record['queries_used']<=30 or not 0<=record['queries_left']<=30:
        raise ValueError('Invalid charged evaluation state')


class TrialReservationIssuer:
    """Runs only inside custody after the existing action is charged/sealed."""
    def __init__(self,ledger,store,signer,*,approved_sessions,development_input_hashes=()):
        self.ledger,self.store,self.signer=ledger,store,signer
        self.sessions=frozenset(encoded(p) for p in approved_sessions)
        self.development_inputs=frozenset(development_input_hashes)
    def issue(self,binding,*,action_id,charge_kind,candidate_ref=None,comparison=None,slot=None):
        external_inputs(binding)
        version=2 if binding.get('schema')=='ai4r-isolated-evaluation-binding:2' else 1
        if slot is not None:
            if version!=2:raise ValueError('Finite timing slots require explicit binding2')
            version=3
        return self._issue(binding,slot=slot,action_id=action_id,charge_kind=charge_kind,candidate_ref=candidate_ref,
            comparison=comparison,subject='child_declaration_ref',schema='ai4r-rsi-trial-reservation:'+str(version))
    def issue_parent(self,binding,*,action_id,charge_kind,candidate_ref=None,comparison=None,slot=None):
        external_inputs(binding)
        version=2 if binding.get('schema')=='ai4r-admitted-measurement-binding:2' else 1
        if slot is not None:
            if version!=2:raise ValueError('Finite timing slots require explicit binding2')
            version=3
        return self._issue(binding,slot=slot,action_id=action_id,charge_kind=charge_kind,candidate_ref=candidate_ref,
            comparison=comparison,subject='parent_declaration_ref',schema='ai4r-rsi-parent-reservation:'+str(version))
    def _issue(self,binding,*,action_id,charge_kind,candidate_ref,comparison,subject,schema,slot):
        if encoded(binding['session_ref']) not in self.sessions:raise ValueError('Session is outside custody grant')
        session=self.store.get(binding['session_ref']);sid=session['session_id']
        if (binding['target_ref']!=session['target_profile_ref'] or binding['configuration_ref']!=session['configuration_ref']
                or type(binding['repeat_index']) is not int or not 0<=binding['repeat_index']<session['pass_count_repeats']):
            raise ValueError('Trial differs from the frozen session repeat/configuration')
        digest=hashlib.sha256(encoded(binding['inputs'])).hexdigest()
        expected={'development':'development','hidden_loop':'loop','hidden_final':'final','platform':'final'}.get(binding['phase'])
        if charge_kind!=expected:raise ValueError('Reservation phase differs')
        state=self.ledger.state(sid)
        if state['halted']:raise ValueError('Custody session is halted')
        if charge_kind=='development':
            if digest not in self.development_inputs:raise ValueError('Development input is not a declared visible parent test')
        else:
            row=self.ledger.db.execute('SELECT kind,state,fingerprint FROM actions WHERE session=? AND id=?',(sid,action_id)).fetchone()
            if row is None or row['kind']!=charge_kind or row['state'] not in {'reserved','evaluating'} or charge_kind=='final' and not state['final_sealed']:
                raise ValueError('The original custody action has not been charged/sealed')
            if charge_kind=='loop':
                if candidate_ref is None:raise ValueError('The actual charged candidate identity is required')
                fingerprint=hashlib.sha256(encoded(candidate_ref)).hexdigest()
            else:
                fields={'attempt_ref','target_ref','parent_ref','child_ref','configuration_ref','repeats','qualification'}
                if not isinstance(comparison,dict) or set(comparison)!=fields:raise ValueError('The exact sealed parent/child comparison is required')
                if (comparison['target_ref']!=binding['target_ref'] or comparison['configuration_ref']!=binding['configuration_ref']
                        or comparison['repeats']!=session['pass_count_repeats'] or comparison['qualification']!=session['qualification']):
                    raise ValueError('Final comparison differs from the frozen session')
                fingerprint=hashlib.sha256(encoded(comparison)).hexdigest()
            if row['fingerprint']!=fingerprint:raise ValueError('The charged custody action names another candidate/comparison')
        record={'schema':schema,
            **{k:binding[k] for k in ('session_ref','target_ref',subject,'phase','repeat_index','configuration_ref')},
            'inputs_sha256':digest,'action_id':action_id,'charge_kind':charge_kind,'queries_used':state['used'],
            'queries_left':min(state['cap']-state['used'],state['lifetime_cap']-state['lifetime'])}
        if slot is not None:
            from jiuwenswarm.research.measurement_slots import reservation_id,parse_slot
            from jiuwenswarm.research.contracts import ResearchError
            try:
                record['id']=reservation_id(record,slot)
                parse_slot(record,binding,self.store.get(binding['target_ref']),session)
            except ResearchError:raise ValueError('Invalid finite frozen measurement slot') from None
        else:record['id']='trial-reservation:'+uuid.uuid4().hex
        return self.store.put(self.signer.sign(record))


class TrialPort:
    """Protected local adapter. Only a distinct UID12002 peer may reach it."""
    def __init__(self,service,core_store,*,public_reader,allowed_session_refs,native_lease=None,qualification=None):
        self.service,self.store,self.read_public=service,core_store,public_reader
        self.sessions=frozenset(encoded(pin) for pin in allowed_session_refs)
        self.native_lease=native_lease
        self.qualification=qualification
        self.active_tasks={}
    async def contain_session(self,session_id,*,recheck=True):
        tasks=tuple(self.active_tasks.get(session_id,()))
        for task in tasks:task.cancel()
        if tasks:await asyncio.wait_for(asyncio.gather(*tasks,return_exceptions=True),40)
        if self.native_lease is None:raise ValueError('Durable native containment authority is unavailable')
        if recheck:self.native_lease.assert_available()
        return {'contained':True,'session_id':session_id}
    def _import(self,pin):
        try:return self.store.read_blob(pin)
        except Exception:pass
        raw=self.read_public(pin)
        if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Trial transfer hash differs')
        if self.store.put_blob(raw,record_id=pin['id'])!=pin:raise ValueError('Trial transfer identity differs')
        return raw
    def _binding(self,pin):
        binding=json.loads(self._import(pin));validate_private('binding',binding)
        if encoded(binding['session_ref']) not in self.sessions:raise ValueError('Trial is outside approved session')
        refs=[binding[k] for k in ('session_ref','target_ref','parent_admission_ref','parent_declaration_ref','parent_contract_ref','child_declaration_ref',
            'configuration_ref','model_selection_profile_ref','deployment_ref','check_bundle_ref','checking_profile_ref','reservation_ref')]
        refs.extend(binding['child_body_refs'].values());refs.extend(binding['dependency_refs'])
        refs.extend(pin for port in binding['inputs'] for pin in port['artifact_refs'])
        for ref in refs:self._import(ref)
        return binding
    @staticmethod
    def _key(pin):return 'rsi-trial-port:'+hashlib.sha256(encoded(pin)).hexdigest()
    async def prepare(self,pin):
        binding=self._binding(pin)
        from .qualification import require_qualification
        require_qualification(self.qualification,'trial',session_ref=binding['session_ref'],candidate_ref=binding['child_declaration_ref'])
        if self.native_lease is not None:self.native_lease.assert_available()
        trial=self.service.prepare_isolated_evaluation(pin)
        with self.store.transaction() as db:
            key=self._key(trial);prior=db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
            value=encoded(pin).decode()
            if prior is not None and prior[0]!=value:raise ValueError('Trial identity changed binding')
            db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',(key,value))
        return {'trial_ref':trial}
    def _authorized(self,trial):
        row=self.store.connection.execute('SELECT value FROM metadata WHERE key=?',(self._key(trial),)).fetchone()
        if row is None:raise ValueError('Unknown trial grant')
        pin=json.loads(row[0]);self._binding(pin);return pin
    def _result(self,pin):
        result=self.store.read_record(pin);validate_private('result',result)
        queue=[(pin,'record')]
        queue.extend((row['artifact_ref'],'output') for row in result['outputs'])
        queue.extend((ref,'record') for ref in [*result['assessment_refs'],*result['observation_refs'],*result['trace_refs'],
            *([result['deterministic_result_ref']] if result['deterministic_result_ref'] else []),
            *(result['failure']['evidence_refs'] if result['failure'] else [])])
        return self._capture_closure(pin,queue)
    def _capture_closure(self,pin,queue):
        allowed={'isolated-evaluation-result','isolated-evaluation-failure','isolated-reservation-claim','isolated-required-test','trial-measurement',
            'deterministic-check-result','verifier-assessment','invocation-observation','model-call','route-record',
            'model-call-input','model-call-output','model-provider-observation','execution-receipt','builder-execution',
            'admitted-parent-result','bound-check-plan','isolated-evaluation-check-plan'}
        captures=[];seen=set()
        while queue:
            ref,role=queue.pop(0)
            if encoded(ref) in seen:continue
            raw=self.store.read_blob(ref);seen.add(encoded(ref))
            kind='declared-output' if role=='output' else self.store.record_kind(ref)
            if kind!='declared-output' and kind not in allowed:raise ValueError('Unknown/private trial evidence kind')
            captures.append({'kind':kind,'ref':ref,'bytes_base64':base64.b64encode(raw).decode('ascii')})
            if role=='output':continue
            value=json.loads(raw)
            nested=[]
            if kind=='model-call':
                from jiuwenswarm.research.isolated_resources import owned_model_evidence
                for owned in owned_model_evidence(self.store,ref):
                    if encoded(owned['ref']) not in seen:
                        captures.append({'kind':owned['kind'],'ref':owned['ref'],'bytes_base64':base64.b64encode(owned['bytes']).decode('ascii')})
                        seen.add(encoded(owned['ref']))
            elif kind=='deterministic-check-result':nested=[value['check_plan_ref']]
            elif kind=='invocation-observation':nested=value['trace_refs']
            elif kind=='isolated-required-test':nested=[value[k] for k in ('deterministic_result_ref','execution_receipt_ref') if value.get(k)]
            elif kind=='trial-measurement':
                nested=[value[k] for k in ('deterministic_ref','observation_ref')]+value['assessment_refs']+value['verifier_check_refs']+value['observation_refs']+value['trace_refs']
                queue.extend((ref,'output') for ref in value['output_refs'].values())
            for child in nested:queue.append((child,'record'))
        return {'result_ref':pin,'captures':captures}
    async def execute(self,trial):
        binding_ref=self._authorized(trial);binding=self.store.read_record(binding_ref)
        from .qualification import require_qualification
        require_qualification(self.qualification,'trial',session_ref=binding['session_ref'],candidate_ref=binding['child_declaration_ref'])
        if self.native_lease is None:raise ValueError('Durable native ownership is unavailable')
        session=self.store.read_record(binding['session_ref'])
        lease=self.native_lease.start(session['session_id'],trial)
        task=asyncio.current_task();self.active_tasks.setdefault(session['session_id'],set()).add(task)
        before={encoded(e['ref']) for e in self.store.iter_records(kinds=('model-call-start',))}
        try:
            result=await self.service.execute_isolated_evaluation(trial)
            return self._result(result)
        finally:
            self.active_tasks[session['session_id']].discard(task)
            starts=[e for e in self.store.iter_records(kinds=('model-call-start',)) if encoded(e['ref']) not in before]
            from .native_lease import native_completion_proof
            known,proof=native_completion_proof(self.store,starts)
            if known:self.native_lease.complete(lease,proof)
            else:
                self.native_lease.uncertain(lease,proof)
                from .native_lease import ProfileInUse
                raise ProfileInUse('PROFILE_IN_USE: isolated trial native effect remains uncertain')
    async def inspect(self,trial):
        self._authorized(trial)
        matches=[e['ref'] for e in self.store.iter_records(kinds=('isolated-evaluation-result',)) if e['record'].get('trial_ref')==trial]
        if len(matches)>1:raise ValueError('Ambiguous trial result')
        return self._result(matches[0]) if matches else {'status':'outcome_unknown','trial_ref':trial}
    def handlers(self):return {'trial_prepare':self.prepare,'trial_execute':self.execute,'trial_inspect':self.inspect}


class ParentTrialPort(TrialPort):
    """IF012 custodian operations, constrained to captured parent contracts."""
    def __init__(self,*args,parent_bindings,**kwargs):
        super().__init__(*args,**kwargs)
        self.parents={}
        for item in parent_bindings:
            if set(item)!={'session_ref','parent_contract_ref','parent_check_plan_ref'}:raise ValueError('Unknown protected parent binding')
            key=encoded(item['session_ref'])
            if key in self.parents or key not in self.sessions:raise ValueError('Ambiguous or unauthorized parent binding')
            self.parents[key]=item
    @staticmethod
    def _key(pin):return 'rsi-parent-port:'+hashlib.sha256(encoded(pin)).hexdigest()
    def _binding(self,pin):
        binding=json.loads(self._import(pin));validate_parent('binding',binding)
        parent=self.parents.get(encoded(binding['session_ref']))
        if parent is None or any(binding[k]!=parent[k] for k in ('parent_contract_ref','parent_check_plan_ref')):
            raise ValueError('Parent measurement is outside exact protected context')
        for key in ('session_ref','target_ref','parent_admission_ref','parent_declaration_ref','parent_contract_ref','parent_check_plan_ref',
                'configuration_ref','model_selection_profile_ref','deployment_ref','reservation_ref'):self._import(binding[key])
        for port in binding['inputs']:
            for ref in port['artifact_refs']:self._import(ref)
        return binding
    async def prepare(self,pin):
        binding=self._binding(pin)
        from .qualification import require_qualification
        require_qualification(self.qualification,'trial',session_ref=binding['session_ref'],candidate_ref=binding['parent_declaration_ref'])
        if self.native_lease is not None:self.native_lease.assert_available()
        grant=self.service.prepare_admitted_measurement(pin)
        with self.store.transaction() as db:
            key=self._key(grant);prior=db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
            value=encoded(pin).decode()
            if prior is not None and prior[0]!=value:raise ValueError('Parent grant identity changed binding')
            db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',(key,value))
        return {'grant_ref':grant}
    def _result(self,pin):
        result=self.store.read_record(pin);validate_parent('result',result)
        return self._capture_closure(pin,[(pin,'record'),(result['measurement_ref'],'record')])
    async def execute(self,grant):
        self._authorized(grant)
        # Reuse the same native effect lease/actual-start reconciliation as the
        # child path, with a finite method alias local to this installed owner.
        return await self._execute_parent(grant)
    async def _execute_parent(self,grant):
        binding=self.store.read_record(self._authorized(grant));session=self.store.read_record(binding['session_ref'])
        from .qualification import require_qualification
        require_qualification(self.qualification,'trial',session_ref=binding['session_ref'],candidate_ref=binding['parent_declaration_ref'])
        if self.native_lease is None:raise ValueError('Durable native ownership is unavailable')
        lease=self.native_lease.start(session['session_id'],grant)
        task=asyncio.current_task();self.active_tasks.setdefault(session['session_id'],set()).add(task)
        before={encoded(e['ref']) for e in self.store.iter_records(kinds=('model-call-start',))}
        try:return self._result(await self.service.execute_admitted_measurement(grant))
        finally:
            self.active_tasks[session['session_id']].discard(task)
            starts=[e for e in self.store.iter_records(kinds=('model-call-start',)) if encoded(e['ref']) not in before]
            from .native_lease import native_completion_proof
            known,proof=native_completion_proof(self.store,starts)
            if known:self.native_lease.complete(lease,proof)
            else:
                self.native_lease.uncertain(lease,proof)
                from .native_lease import ProfileInUse
                raise ProfileInUse('PROFILE_IN_USE: original-parent native effect remains uncertain')
    async def inspect(self,grant):
        self._authorized(grant)
        matches=[e['ref'] for e in self.store.iter_records(kinds=('admitted-parent-result',)) if e['record'].get('grant_ref')==grant]
        if len(matches)>1:raise ValueError('Ambiguous parent measurement result')
        return self._result(matches[0]) if matches else {'status':'outcome_unknown','grant_ref':grant}
    def handlers(self):return {'parent_prepare':self.prepare,'parent_execute':self.execute,'parent_inspect':self.inspect}
