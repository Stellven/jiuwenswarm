"""Custodian-only service: hidden callbacks and key never cross the process boundary."""
from .signing import Signer
from .records import encoded


class CustodianService:
    def __init__(self,requests,ledger,oracle,referee,signer,validate,authorized_sessions,*,session_grants=None,public_store=None,package_publisher=None,contain_session=None,qualification=None):
        self.requests,self.ledger,self.oracle,self.referee,self.signer,self.validate=requests,ledger,oracle,referee,signer,validate
        self.authorized_sessions=frozenset(authorized_sessions)
        self.grants=dict(session_grants or {});self.public=public_store;self.package_publisher=package_publisher;self.contain_session=contain_session
        self.qualification=qualification
    def _security(self,sid,operation,candidate_ref=None):
        from .qualification import require_qualification
        session_ref=self.grants.get(sid,{}).get('session_ref')
        return require_qualification(self.qualification,operation,session_ref=session_ref,candidate_ref=candidate_ref)
    def _resolve(self,ref):
        value=self.requests.get(ref)
        if value['session_id'] not in self.authorized_sessions:raise PermissionError('session outside custodian grant')
        return value
    async def open(self,ref):
        value=self._resolve(ref);grant=self.grants.get(value['session_id'])
        self._security(value['session_id'],'session_start')
        if grant is None or any(value.get(k)!=grant[k] for k in ('fixture_identity','session_cap','lifetime_cap')):raise ValueError('Captured session grant differs')
        self.ledger.open_session(value['session_id'],value['fixture_identity'],session_cap=value['session_cap'],lifetime_cap=value['lifetime_cap'])
        return {'opened':True}
    async def state(self,ref):
        value=self._resolve(ref);state=self.ledger.state(value['session_id'])
        return {key:state[key] for key in ('used','cap','lifetime','lifetime_cap','final_sealed','halted')}
    async def halt(self,ref):
        value=self._resolve(ref);self.ledger.halt(value['session_id'])
        if self.contain_session is not None:await self.contain_session(value['session_id'])
        return {'halted':True}
    async def evaluate(self,ref):
        value=self._resolve(ref)
        self._security(value['session_id'],'oracle',value['candidate_ref'])
        return await self.oracle.score(value['session_id'],value['action_id'],value['candidate_ref'])
    async def final(self,ref):
        value=self._resolve(ref)
        self._security(value['session_id'],'oracle',value['comparison'].get('child_ref'))
        decision,pin=await self.referee.final(value['session_id'],**value['comparison'])
        return {'decision':decision,'evidence_ref':pin,'evidence':self.referee.store.get(pin)}
    async def sign_terminal(self,ref):
        value=self._resolve(ref);record=value['record'];state=self.ledger.state(value['session_id'])
        if record.get('schema_version')!='2.0.0':raise ValueError('Only current terminal records may be newly signed')
        if self.public is not None:
            session=self.public.get(record['session_ref']);previous=None
            if session['session_id']!=value['session_id']:raise ValueError('Terminal session binding differs')
            grant=self.grants.get(value['session_id'],{})
            if grant.get('session_ref',record['session_ref'])!=record['session_ref']:raise ValueError('Terminal substituted a captured session')
            if record['parent']!=session['parent'] or len(record['attempt_refs'])>session['limits']['max_attempts']:raise ValueError('Terminal parent or attempt budget differs')
            target=self.public.get(session['target_profile_ref']);last_queries=0
            for sequence,pin in enumerate(record['attempt_refs'],1):
                attempt=self.public.get(pin);self.validate('rsi-attempt',attempt)
                if attempt['schema_version']!='2.0.0' or attempt['session_id']!=session['session_id'] or attempt['sequence']!=sequence or attempt['previous_ref']!=previous:raise ValueError('Terminal chain is incomplete')
                expected={'target_ref':session['target_profile_ref'],'parent_ref':target['parent_ref'],'configuration_ref':session['configuration_ref'],
                    'hash_profile_ref':session['hash_profile_ref'],'chain_root_ref':session['chain_root_ref']}
                if any(attempt[k]!=v for k,v in expected.items()) or not last_queries<=attempt['queries_used']<=state['used']:raise ValueError('Attempt scope/exposure differs from custody')
                last_queries=attempt['queries_used']
                if pin==record['final_attempt_ref'] and attempt['attempt_status']!='proposed':raise ValueError('Rejected attempt cannot be finalist')
                previous=pin
            if record['attempts_used']!=len(record['attempt_refs']) or record['final_attempt_ref'] is not None and record['final_attempt_ref'] not in record['attempt_refs']:raise ValueError('Terminal attempt count/final mismatch')
        if record['queries_used']!=state['used'] or record['outcome']=='QUALIFIED' and not state['final_sealed']:raise ValueError('terminal exposure or final mismatch')
        if record['outcome']=='QUALIFIED':
            self._security(value['session_id'],'package',record['child_declaration_ref'])
            evidence=self.referee.store.get(record['referee_evidence_ref'])
            if evidence['violations'] or not evidence['integrity_passed'] or not evidence['mandatory_parent_tests_passed']:raise ValueError('referee prerequisites failed')
            # Authorize qualification only from the independent stored comparison,
            # never the controller-supplied statistics or outcome text.
            import json
            row=self.ledger.db.execute('SELECT state,result FROM actions WHERE session=? AND id=?',(value['session_id'],'original-parent-final')).fetchone()
            if row is None or row['state']!='complete':raise ValueError('independent final receipt absent')
            receipt=json.loads(row['result']);comparison=receipt['decision']
            if receipt['evidence_ref']!=record['referee_evidence_ref'] or evidence['attempt_ref']!=record['final_attempt_ref']:raise ValueError('Terminal final evidence differs from the sealed comparison')
            if comparison['outcome']!='QUALIFIED' or comparison['statistics']!=record['statistics'] or comparison['qualified_by']!=record['qualified_by']:raise ValueError('qualification differs from independent referee')
        signed=self.signer.sign(record);self.validate('rsi-session-result',signed)
        if self.public is not None:
            pin=self.public.put(signed)
            if signed['outcome']=='QUALIFIED' and self.package_publisher is not None:
                try:self.package_publisher(pin)
                except (ValueError,KeyError,OSError) as exc:
                    # Qualification evidence remains immutable even if the
                    # separate inactive-package publication is unavailable.
                    self.public.put({'record_kind':'rsi-package-publication-failure:1','session_result_ref':pin,'reason':type(exc).__name__})
        return signed
    def handlers(self):return {'custodian_open':self.open,'custodian_state':self.state,'custodian_halt':self.halt,
        'custodian_evaluate':self.evaluate,'custodian_final':self.final,'custodian_sign_terminal':self.sign_terminal}
