"""One-candidate bounded controller. Hidden data never enters proposal context."""
import asyncio
from datetime import datetime,timezone
import time
import uuid
import inspect
import math
from .mutation import SecurityViolation
from .profiles import Limits
from .custody import ExposureError


def utc():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


async def resolved(value):return await value if inspect.isawaitable(value) else value


class Controller:
    def __init__(self,*,store,ledger,oracle,proposer,assess,signer,validate,clock=time.monotonic,recovery_containment=None,qualification=None):
        self.store,self.ledger,self.oracle,self.proposer,self.assess,self.signer,self.validate=store,ledger,oracle,proposer,assess,signer,validate
        self.clock=clock;self.cancelled=False;self.recovery_containment=recovery_containment;self.containment_uncertain=False
        self.qualification=qualification
    def cancel(self):self.cancelled=True
    def _history_context(self,session,session_ref,parent_body_ref):
        session_bytes_ref=self.store.put_bytes(self.store.read(session_ref))
        return self.store.put({'record_kind':'rsi-session-history-context:1','session_ref':session_ref,
            'session_bytes_ref':session_bytes_ref,'parent_ref':parent_body_ref,**{key:session[key] for key in ('parent_declaration_ref','target_profile_ref',
                'hash_profile_ref','chain_root_ref','configuration_ref','improver_ref','scoring_adapter_ref')}})
    def _population(self,session_ref,context_ref,starts,attempts,queries_used):
        return {'record_kind':'rsi-terminal-population:1','session_ref':session_ref,'context_ref':context_ref,
            'proposer_start_refs':starts,'attempt_refs':attempts,'queries_used':queries_used}
    async def _sign_staged(self,session,session_ref,context_ref,result):
        signed=await resolved(self.signer.sign(result));self.validate('rsi-session-result',signed)
        # Retain the exact received signature before a publication/job-index
        # failure can lose it. Re-publication of these same bytes has no effects.
        pin=self.store.complete_terminal(session['session_id'],session_ref,context_ref,signed)
        if self.store.put(signed)!=pin:raise ValueError('Terminal publication changed exact bytes')
        return signed,pin
    async def _terminal(self,session,session_ref,context_ref,result):
        population=self._population(session_ref,context_ref,self.store.proposer_starts(session['session_id']),
            self.store.attempts(session['session_id']),result['queries_used'])
        if (result['attempt_refs']!=population['attempt_refs'] or result['attempts_used']!=len(population['attempt_refs'])
                or len(population['attempt_refs'])!=len(population['proposer_start_refs'])):raise ValueError('Terminal attempt population is incomplete or differs')
        self.store.stage_terminal(session['session_id'],session_ref,context_ref,population,result,
            containment_uncertain=self.containment_uncertain)
        return await self._sign_staged(session,session_ref,context_ref,result)
    async def recover_terminal(self,session,*,parent_body_ref,session_ref=None):
        """Close durable unmatched starts without replaying any effect."""
        self.validate('rsi-session',session);sid=session['session_id'];limits=Limits.from_mapping(session['limits'])
        session_ref=session_ref or self.store.put(session)
        if self.store.get(session_ref)!=session:raise ValueError('Recovery session bytes differ')
        # Resolve original immutable scope before halting custody or mutating
        # indexes. Current eligibility/qualification cannot authorize history.
        from .profiles import freeze_profile
        target=self.store.get(session['target_profile_ref']);parent=self.store.get(session['parent_declaration_ref'])
        freeze_profile(target,parent,self.validate)
        if target['parent_ref']!=parent_body_ref or target['parent_declaration_ref']!=session['parent_declaration_ref']:raise ValueError('Recovery parent scope differs')
        if limits.session_query_limit>target['session_query_limit'] or limits.lifetime_query_limit>target['lifetime_query_limit']:raise ValueError('Recovery query limits exceed the frozen target')
        identity=parent['identity']
        if session['parent']!={'cc_name':identity['name'],'cc_version':identity['version_label'],'declaration_sha256':session['parent_declaration_ref']['sha256']}:raise ValueError('Recovery parent identity differs')
        if any(target[key]!=session[key] for key in ('configuration_ref','improver_ref','scoring_adapter_ref')):raise ValueError('Recovery target bindings differ')
        genesis=self.store.get(session['chain_root_ref'])
        if any(genesis.get(k)!=v for k,v in {'session_id':sid,'target_ref':session['target_profile_ref'],
                'hash_profile_ref':session['hash_profile_ref'],'interface_revision':'M1-IF-009@r2'}.items()):raise ValueError('Recovery genesis differs')
        for pin in (parent_body_ref,session['hash_profile_ref'],session['configuration_ref'],session['improver_ref'],session['scoring_adapter_ref']):self.store.read(pin)
        context_ref=self._history_context(session,session_ref,parent_body_ref)
        history=self.store.session_history(sid,session_ref,context_ref)
        if history is None:raise ExposureError('Original terminal tracking is absent; retained originals remain unresolved and automatic replacement/replay is forbidden')
        state=await resolved(self.ledger.state(sid));starts=self.store.proposer_starts(sid);attempts=self.store.attempts(sid)
        if type(state['used']) is not int or not 0<=state['used']<=limits.session_query_limit or state['cap']!=limits.session_query_limit or state['lifetime_cap']!=limits.lifetime_query_limit:raise ValueError('Recovery custody grant/accounting differs')
        before_used=state['used']
        if len(starts)>limits.max_attempts or len(attempts)>len(starts):raise ValueError('Recovery start/attempt accounting is invalid')
        last_queries=0
        # Validate the entire existing population before cleanup/closure. A
        # second unmatched start cannot have a genuine previous attempt link.
        for sequence,pin in enumerate(starts,1):
            if sequence>len(attempts)+1:raise ValueError('Recovery has multiple unmatched proposer starts')
            started=self.store.get(pin)
            previous=attempts[sequence-2] if sequence>1 else None
            if any(started.get(k)!=v for k,v in {'record_kind':'rsi-proposer-start:1','session_id':sid,'sequence':sequence,'previous_ref':previous,
                    'configuration_ref':session['configuration_ref'],'improver_ref':session['improver_ref']}.items()):raise ValueError('Recovery start chain differs')
            if sequence<=len(attempts):
                existing=self.store.get(attempts[sequence-1]);self.validate('rsi-attempt',existing)
                expected={'schema_version':'2.0.0','sequence':sequence,'previous_ref':previous,'session_id':sid,
                    'target_ref':session['target_profile_ref'],'parent_ref':parent_body_ref,'configuration_ref':session['configuration_ref'],
                    'hash_profile_ref':session['hash_profile_ref'],'chain_root_ref':session['chain_root_ref']}
                if any(existing[k]!=v for k,v in expected.items()) or not last_queries<=existing['queries_used']<=state['used']:raise ValueError('Recovery completed chain differs')
                last_queries=existing['queries_used']
        original=None;signed=None
        if history['unsigned_ref'] is not None:
            original=self.store.get(history['unsigned_ref'])
            population=self._population(session_ref,context_ref,starts,attempts,state['used'])
            expected={'session_ref':session_ref,'parent':session['parent'],'attempt_refs':attempts,
                'attempts_used':len(attempts),'queries_used':state['used']}
            if len(starts)!=len(attempts) or self.store.get(history['population_ref'])!=population or any(original[k]!=v for k,v in expected.items()):raise ValueError('Original terminal population differs from retained history')
            if history['signed_ref'] is not None:
                signed=self.store.get(history['signed_ref']);self.validate('rsi-session-result',signed)
                if {k:v for k,v in signed.items() if k not in {'signature','signer_key_id'}}!=original:raise ValueError('Original signed terminal payload differs')
        failures=[];contained=False;halt_request_completed=False
        try:
            await resolved(self.ledger.halt(sid));halt_request_completed=True
        except Exception as exc:failures.append({'phase':'custody_halt','exception_type':type(exc).__name__})
        try:
            if self.recovery_containment is None:raise ValueError('Owned containment callback is unavailable')
            proof=await resolved(self.recovery_containment(sid))
            contained=isinstance(proof,dict) and proof.get('contained') is True and proof.get('session_id')==sid
            if not contained:failures.append({'phase':'owned_cleanup','reason':'Exact session containment acknowledgement is absent'})
        except Exception as exc:failures.append({'phase':'owned_cleanup','exception_type':type(exc).__name__})
        cleanup_ref=self.store.put({'record_kind':'rsi-recovery-cleanup-attempt:1','session_id':sid,'session_ref':session_ref,
            'context_ref':context_ref,'recorded_at':utc(),'halt_request_completed':halt_request_completed,
            'containment_status':'confirmed' if contained else 'uncertain','failures':failures,
            'previously_observed_queries_used':before_used,'automatic_replay':False,'native_lease_released':False})
        # A failed RPC may follow a durable halt. Confirm the original ledger;
        # missing halt/query evidence is uncertainty, never fabricated zeroes.
        try:state=await resolved(self.ledger.state(sid))
        except Exception as exc:
            self.store.put({'record_kind':'rsi-recovery-custody-unavailable:1','session_id':sid,'session_ref':session_ref,
                'cleanup_attempt_ref':cleanup_ref,'recorded_at':utc(),'exception_type':type(exc).__name__,
                'reason':'Actual post-cleanup custody state is unavailable; no query count or terminal is fabricated'})
            raise
        if type(state['used']) is not int or not before_used<=state['used']<=limits.session_query_limit:raise ValueError('Recovery custody count changed inconsistently')
        if state.get('halted') is not True and state.get('halted')!=1:raise ExposureError('Custody halt is unconfirmed; no attempt/history closure is authorized')
        self.containment_uncertain=not contained
        if self.containment_uncertain:self.store.mark_history_uncertain(sid,session_ref,context_ref)
        if original is not None:
            if original['queries_used']!=state['used']:raise ValueError('Custody count changed after the original terminal was staged')
            if signed is not None:
                if self.store.put(signed)!=history['signed_ref']:raise ValueError('Original terminal publication changed bytes')
                return signed,history['signed_ref']
            if original['outcome']=='QUALIFIED':raise ExposureError('Original qualified terminal signing/publication response is unresolved; recovery cannot replay package effects')
            return await self._sign_staged(session,session_ref,context_ref,original)
        containment_ref=self.store.put({'record_kind':'rsi-recovery-containment:1','session_id':sid,'session_ref':session_ref,
            'context_ref':context_ref,'cleanup_attempt_ref':cleanup_ref,'recorded_at':utc(),'custody_halted':True,
            'containment_status':'confirmed' if contained else 'uncertain','contained':contained,'failures':failures,
            'queries_used':state['used'],'automatic_replay':False,'native_lease_released':False})
        for sequence in range(len(attempts)+1,len(starts)+1):
            pin=starts[sequence-1];previous=attempts[-1] if attempts else None
            reason='Process loss after durable proposer start; no authoritative proposal/assessment completion is available'
            failure=self.store.put({'record_kind':'rsi-attempt-recovery:1','session_id':sid,'sequence':sequence,
                'proposer_start_ref':pin,'containment_evidence_ref':containment_ref,'recorded_at':utc(),'reason':reason,'automatic_replay':False})
            attempt={'schema_version':'2.0.0','id':'attempt:'+uuid.uuid4().hex,'session_id':sid,'sequence':sequence,
                'attempt_status':'rejected','rejection_reason':reason,'failure_evidence_refs':[failure,containment_ref],
                'previous_ref':previous,'target_ref':session['target_profile_ref'],'parent_ref':parent_body_ref,
                'child_ref':None,'diff_ref':None,'rationale':None,'visible_evidence_refs':[],
                'queries_used':state['used'],'violations':[],'stop_reason':reason,'configuration_ref':session['configuration_ref'],
                'observation_refs':[],'time_s':None,'model_calls':None,
                'unavailable_reasons':['Process loss left no attributable completion duration/model-call count; inspect retained protected starts and native receipts'],
                'hash_profile_ref':session['hash_profile_ref'],'chain_root_ref':session['chain_root_ref']}
            self.validate('rsi-attempt',attempt);attempts.append(self.store.append_attempt(sid,attempt))
        result={'schema_version':'2.0.0','id':'result:'+uuid.uuid4().hex,'session_ref':session_ref,'outcome':'ERROR',
            'parent':session['parent'],'child':None,'child_declaration_ref':None,'attempt_refs':attempts,
            'final_attempt_ref':None,'referee_evidence_ref':None,'qualified_by':'none','statistics':None,
            'attempts_used':len(attempts),'queries_used':state['used'],'stop_reason':'Recovered interrupted session evidence without replay',
            'limitations':['no_evidence_no_hidden_query: recovery performs no model, loop or final evaluation and permits no package; existing exposure and private final receipts remain retained',
                'Recovery cleanup evidence '+containment_ref['sha256']+' is retained; terminal history does not release the native lease or authorize execution'],
            'recorded_at':utc()}
        if self.containment_uncertain:result['limitations'].append('Actual native/effect containment remains uncertain; no successful stop is acknowledged')
        return await self._terminal(session,session_ref,context_ref,result)

    async def run(self,session,*,opportunity,fixture_identity,visible_context,parent_body_ref,finalize=None,session_ref=None):
        self.validate('rsi-session',session)
        if opportunity.get('decision')!='START':raise ValueError('qualified opportunity required before START')
        limits=Limits.from_mapping(session['limits']);sid=session['session_id']
        genesis=self.store.get(session['chain_root_ref'])
        if genesis.get('session_id')!=sid or genesis.get('target_ref')!=session['target_profile_ref'] or genesis.get('hash_profile_ref')!=session['hash_profile_ref'] or genesis.get('interface_revision')!='M1-IF-009@r2':
            raise ValueError('session genesis does not match frozen target/hash profile')
        self.store.read(session['hash_profile_ref'])
        session_ref=session_ref or self.store.put(session)
        if self.store.get(session_ref)!=session:raise ValueError('Session bytes differ from the protected grant')
        from .qualification import require_qualification
        require_qualification(self.qualification,'session_start',session_ref=session_ref)
        # A protected session ID is single execution. Re-entering it never repeats an unknown query.
        await resolved(self.ledger.open_session(sid,fixture_identity,session_cap=limits.session_query_limit,lifetime_cap=limits.lifetime_query_limit))
        state=await resolved(self.ledger.state(sid))
        if state['used'] or state.get('halted') or self.store.attempts(sid) or self.store.proposer_starts(sid):raise ExposureError('session already started; inspect protected receipts instead of replay')
        context_ref=self._history_context(session,session_ref,parent_body_ref)
        self.store.begin_session_history(sid,session_ref,context_ref)
        deadline=self.clock()+limits.wall_s;no_progress=0;best=None;best_score=None;feedback=None;reason='attempt cap reached';outcome=None
        best_time=opportunity.get('parent_visible_time_s')
        try:
            feedback=await asyncio.wait_for(self.oracle.score(sid,'baseline',parent_body_ref),max(.001,deadline-self.clock()))
            baseline=feedback['passed'];best_score=baseline
            for sequence in range(1,limits.max_attempts+1):
                if self.cancelled:outcome='CANCELLED';reason='operator cancellation';break
                if self.clock()>=deadline:reason='session wall limit reached';break
                if no_progress>=limits.max_no_progress:reason='consecutive no-progress cap reached';break
                if feedback['queries_left']<=0:reason='hidden-loop query budget exhausted';break
                require_qualification(self.qualification,'proposal',session_ref=session_ref)
                prior=self.store.attempts(sid);start=self.clock();child=None;violations=[];rationale=None;diff=None;visible=[];stop=None;selected_this_attempt=False;attempt_status='rejected';assessment_started=False
                # This raw protected receipt survives a hard process loss even
                # if no response/child body exists. It is not a canonical
                # attempt itself; C007 closes it with a counted v2 chain record.
                start_ref=self.store.record_proposer_start(sid,{'record_kind':'rsi-proposer-start:1','session_id':sid,'sequence':sequence,
                    'previous_ref':prior[-1] if prior else None,'recorded_at':utc(),
                    'configuration_ref':session['configuration_ref'],'improver_ref':session['improver_ref']})
                try:
                    proposal=await asyncio.wait_for(self.proposer.propose(visible_context,feedback),min(limits.per_call_s,max(0,deadline-self.clock())))
                    rationale=proposal['rationale'];assessment_started=True
                    assessed=await asyncio.wait_for(self.assess(proposal),max(0,deadline-self.clock()))
                    child=assessed.get('child_ref');diff=assessed.get('diff_ref');visible=assessed.get('evidence_refs',[])
                    if not assessed.get('mandatory_passed'):
                        stop='mandatory parent tests rejected candidate';no_progress+=1
                    else:
                        if child is None or diff is None or child['sha256']==parent_body_ref['sha256']:
                            raise ValueError('eligible proposal lacks actual differing child/diff')
                        self.store.read(child);self.store.read(diff)
                        attempt_status='proposed'
                        next_feedback=await asyncio.wait_for(self.oracle.score(sid,'attempt:'+str(sequence),child),max(.001,deadline-self.clock()))
                        child_time=assessed.get('visible_selection_time_s')
                        timing_improves=next_feedback['passed']==best_score and all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in (child_time,best_time)) and child_time<best_time
                        if next_feedback['passed']>best_score or timing_improves:
                            best_score=next_feedback['passed'];best_time=child_time;best=assessed;no_progress=0;selected_this_attempt=True
                        else:no_progress+=1
                        feedback=next_feedback
                except SecurityViolation as exc:
                    violations=[str(exc)];stop='security violation';outcome='SECURITY_HALTED';await resolved(self.ledger.halt(sid))
                except ExposureError:
                    stop='candidate evaluation interrupted, exhausted or unknown';outcome='ERROR';no_progress+=1
                except (ValueError,asyncio.TimeoutError) as exc:
                    stop=type(exc).__name__+': proposal or visible assessment failed';no_progress+=1
                except asyncio.CancelledError:
                    stop='controller cancelled during the started attempt';outcome='CANCELLED'
                finally:
                    # Each started proposal counts, including malformed/visible rejects.
                    capture=getattr(self.assess,'last_capture',{}) if assessment_started else getattr(self.proposer,'last_capture',{})
                    child=child or capture.get('child_ref');diff=diff or capture.get('diff_ref')
                    if rationale is None:rationale=capture.get('rationale')
                    failure=[]
                    if stop is not None or attempt_status=='rejected':
                        failure.append(self.store.put({'record_kind':'rsi-attempt-failure:1','session_id':sid,'sequence':sequence,
                            'proposer_start_ref':start_ref,'phase':'candidate_evaluation' if attempt_status=='proposed' else 'proposal_or_visible_assessment',
                            'reason':stop or 'No eligible proposal was produced','recorded_at':utc(),
                            'captured_refs':list(getattr(self.proposer,'last_evidence',[]))+visible+([self.proposer.last_response_ref] if getattr(self.proposer,'last_response_ref',None) else [])}))
                    record={'schema_version':'2.0.0','id':'attempt:'+uuid.uuid4().hex,'session_id':sid,'sequence':sequence,
                        'attempt_status':attempt_status,'rejection_reason':(stop or 'No eligible proposal was produced') if attempt_status=='rejected' else None,
                        'failure_evidence_refs':failure,
                        'previous_ref':prior[-1] if prior else None,'target_ref':session['target_profile_ref'],'parent_ref':parent_body_ref,
                        'child_ref':child,'diff_ref':diff,'rationale':rationale,'visible_evidence_refs':visible,
                        'queries_used':(await resolved(self.ledger.state(sid)))['used'],'violations':violations,'stop_reason':stop,
                        'configuration_ref':session['configuration_ref'],'observation_refs':list(getattr(self.proposer,'last_evidence',[])),
                        'time_s':self.clock()-start,'model_calls':getattr(self.proposer,'last_model_calls',None),'unavailable_reasons':[] if getattr(self.proposer,'last_model_calls',None) is not None else ['model_calls unavailable until protected bridge receipt capture'],
                        'hash_profile_ref':session['hash_profile_ref'],'chain_root_ref':session['chain_root_ref']}
                    self.validate('rsi-attempt',record)
                    ref=self.store.append_attempt(sid,record)
                    if selected_this_attempt:best={**best,'attempt_ref':ref}
                if outcome is not None:reason=stop or 'session stopped';break
        except ExposureError:
            outcome='ERROR';reason='evaluation interrupted, exhausted or unknown; no automatic replay'
        except (ValueError,asyncio.TimeoutError):
            outcome='ERROR';reason='bounded evaluation failed or exceeded the session wall limit; counted exposure is retained'
        except asyncio.CancelledError:
            outcome='CANCELLED';reason='controller cancelled after durable exposure capture'
        decision={'qualified_by':'none','statistics':None};referee_ref=None;final_attempt=None
        if outcome is None and best is not None and finalize is not None:
            final_attempt=best['attempt_ref']
            try:
                decision,referee_ref=await asyncio.wait_for(finalize(best),max(.001,deadline-self.clock()))
                outcome=decision['outcome'];reason=decision['reason']
            except (ExposureError,ValueError,asyncio.TimeoutError):
                outcome='ERROR';reason='final comparison failed, expired or has unknown effects; no automatic replay';final_attempt=None
            except asyncio.CancelledError:
                outcome='CANCELLED';reason='cancelled during independent final comparison; existing exposure retained';final_attempt=None
        elif outcome is None:outcome='UNEVALUATED_CANDIDATE' if best else 'NO_IMPROVEMENT'
        if outcome=='CANCELLED':
            try:
                if self.recovery_containment is None:raise ValueError('Actual owned effect containment is unavailable')
                proof=await resolved(self.recovery_containment(sid))
                if not isinstance(proof,dict) or proof.get('contained') is not True or proof.get('session_id')!=sid:
                    raise ValueError('Actual owned effect containment is not acknowledged')
            except Exception:
                self.containment_uncertain=True;outcome='ERROR';reason='Cancellation containment remains uncertain; no successful stop or new effect is authorized'
        # An infrastructure/evaluator ERROR supplies no actual cessation proof.
        # A later stop must not turn that history into a containment receipt.
        if outcome=='ERROR':
            self.containment_uncertain=True
            try:await resolved(self.ledger.halt(sid))
            except Exception as exc:
                self.store.put({'record_kind':'rsi-terminal-halt-failure:1','session_id':sid,'session_ref':session_ref,
                    'context_ref':context_ref,'recorded_at':utc(),'exception_type':type(exc).__name__,
                    'reason':'Halt request failed; actual custody state must confirm halt before terminal staging'})
            state=await resolved(self.ledger.state(sid))
            if state.get('halted') is not True and state.get('halted')!=1:raise ExposureError('Custody halt is unconfirmed; terminal count cannot be frozen')
        attempts=self.store.attempts(sid)
        result={'schema_version':'2.0.0','id':'result:'+uuid.uuid4().hex,'session_ref':session_ref,'outcome':outcome,
            'parent':session['parent'],'child':best.get('child') if best else None,'child_declaration_ref':best.get('child_declaration_ref') if best else None,
            'attempt_refs':attempts,'final_attempt_ref':final_attempt,'referee_evidence_ref':referee_ref,
            'qualified_by':decision['qualified_by'],'statistics':decision['statistics'],'attempts_used':len(attempts),
            'queries_used':(await resolved(self.ledger.state(sid)))['used'],'stop_reason':reason,
            'limitations':[] if referee_ref else ['no_evidence_no_hidden_query: final comparison absent; no package permitted; actual loop exposure retained'],
            'recorded_at':utc()}
        if self.containment_uncertain:result['limitations'].append('Actual native/effect containment remains uncertain; terminal ERROR history grants no successful stop or new execution')
        return await self._terminal(session,session_ref,context_ref,result)
