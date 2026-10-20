"""Literal production bindings for finite RSI targets.

All roots, grants and immutable input records come from protected host capture.
Nothing in a job selects a Python module, factory, command, oracle path or actor.
Unavailable installation, calibration or confinement is an explicit blocker.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
from fractions import Fraction
from .records import RecordStore,encoded
from .worker import PublicBytes,WorkerClient,ref


class CombinedRecords:
    def __init__(self,records,core=None,public=None,publisher=None):self.records,self.core,self.public,self.publisher=records,core,public,publisher
    def read(self,pin):
        if pin['id']==pin['sha256']+'.json':
            try:return self.records.read(pin)
            except FileNotFoundError:pass
        if self.core is not None:
            try:return self.core.read_blob(pin)
            except Exception:pass
        if self.public is not None:return self.public.read(pin)
        raise ValueError('Exact captured resource bytes unavailable')
    def get(self,pin):return json.loads(self.read(pin))
    def put_bytes(self,data):
        pin=self.records.put_bytes(data)
        if self.publisher is not None and self.publisher.put_bytes(data)!=pin:raise ValueError('Public bytes publication changed identity')
        return pin
    def put(self,value):return self.put_bytes(encoded(value))
    def append_attempt(self,session,value):
        pin=self.records.append_attempt(session,value)
        if self.publisher is not None:self.publisher.put(value)
        return pin
    def record_proposer_start(self,session,value):
        pin=self.records.record_proposer_start(session,value)
        if self.publisher is not None:self.publisher.put_ref(pin,self.records.read(pin))
        return pin
    def __getattr__(self,name):return getattr(self.records,name)


def closed(value,fields,schema):
    if not isinstance(value,dict) or set(value)!=set(fields)|{'schema'} or value['schema']!=schema:raise ValueError('Unknown protected resource binding')
    return value


def owned_directory(value,uid):
    path=Path(value)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Unsafe protected resource root')
    meta=path.stat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=uid or meta.st_mode&0o077:raise ValueError('Resource root is not privately owned')
    return path


def shared_directory(value,uid):
    path=Path(value)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Unsafe shared capture root')
    meta=path.stat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=uid or meta.st_gid!=13000 or stat.S_IMODE(meta.st_mode)!=0o2750:raise ValueError('Shared captured bytes require the private controller/custodian read group')
    return path


async def native_profile_ready(subscription,native_lease):
    """Uncertain restart exposes reconciliation without spawning another owner."""
    from .native_lease import ProfileInUse
    try:native_lease.assert_available()
    except ProfileInUse:return False
    if (await subscription.status()).get('state')!='ready':raise ValueError('Separately owned native subscription is not ready')
    return True


class CoreProposer:
    """Actual normal runner model contexts over an immutable per-attempt list."""
    def __init__(self,resources,contract_refs,store,*,native_lease=None,session_id=None,qualification=None,session_ref=None):
        self.resources,self.refs,self.store=resources,list(contract_refs),store
        self.position=0;self.last_evidence=[];self.last_model_calls=None;self.native_lease=native_lease;self.session_id=session_id
        self.qualification,self.session_ref=qualification,session_ref
    async def __call__(self,prompt):
        self.last_evidence=[];self.last_model_calls=None
        from .qualification import require_qualification
        require_qualification(self.qualification,'proposal',session_ref=self.session_ref)
        if self.position>=len(self.refs):raise ValueError('No further captured proposer invocation is authorized')
        pin=self.refs[self.position];self.position+=1
        lease_ref=self.native_lease.start(self.session_id,pin) if self.native_lease is not None else None
        before={encoded(e['ref']) for e in self.resources.store.iter_records(kinds={'model-call','route-record','invocation-observation'})}
        prior_starts={encoded(e['ref']) for e in self.resources.store.iter_records(kinds={'model-call-start'})}
        try:return await self.resources.propose_once(pin,prompt)
        finally:
            entries=[e for e in self.resources.store.iter_records(kinds={'model-call','route-record','invocation-observation'}) if encoded(e['ref']) not in before]
            observations=[e for e in entries if e['kind']=='invocation-observation' and e['record']['contract_ref']==pin]
            starts=[e for e in self.resources.store.iter_records(kinds={'model-call-start'}) if encoded(e['ref']) not in prior_starts and e['record']['contract_ref']==pin]
            invocations={e['record']['invocation_id'] for e in starts}
            entries=[e for e in entries if e in observations or e['record'].get('invocation_id') in invocations]
            self.last_evidence=[e['ref'] for e in entries]
            observations=[e['record'] for e in entries if e['kind']=='invocation-observation']
            self.last_model_calls=observations[-1]['model_calls'] if observations else None
            if lease_ref is not None:
                from .native_lease import native_completion_proof
                known,proof=native_completion_proof(self.resources.store,starts)
                if known:self.native_lease.complete(lease_ref,proof)
                else:
                    self.native_lease.uncertain(lease_ref,proof)
                    from .native_lease import ProfileInUse
                    raise ProfileInUse('PROFILE_IN_USE: native effect outcome/containment is uncertain; further work is blocked')
            publication=getattr(self.store,'publisher',None)
            if publication is not None:
                # A proposer uses the normal worker model port. Export its
                # exact typed input/output captures, never the native account
                # trajectory journal or login/event-store frames.
                from jiuwenswarm.research.isolated_resources import owned_model_evidence
                for entry in entries:
                    publication.put_ref(entry['ref'],self.resources.store.read_blob(entry['ref']))
                    record=entry['record']
                    if entry['kind']=='model-call':
                        for nested in owned_model_evidence(self.resources.store,entry['ref']):
                            publication.put_ref(nested['ref'],nested['bytes'])
                    elif entry['kind']=='invocation-observation':
                        for pin in record['output_refs']:publication.put_ref(pin,self.resources.store.read_blob(pin))



class FixtureEvaluator:
    """Custodian-owned expected outputs; only function inputs reach the worker."""
    def __init__(self,*,manifest,store,worker,session_ref,target,repeats):
        closed(manifest,{'fixture_identity','target_ref','partitions','independent','independence_evidence_ref','calibration_ref'},'ai4r-rsi-fixtures:1')
        if type(manifest['independent']) is not bool:raise ValueError('Frozen fixture independence is required')
        self.manifest,self.store,self.worker,self.session_ref,self.target,self.repeats=manifest,store,worker,session_ref,target,repeats
        self.last_evidence=[]
        store.read(manifest['independence_evidence_ref'])
        ids=[]
        if set(manifest['partitions'])!={'development','hidden_loop','hidden_final','platform'}:raise ValueError('Four exact partitions required')
        for split,rows in manifest['partitions'].items():
            if not isinstance(rows,list) or not rows or split.startswith('hidden_') and len(rows)<20:raise ValueError('Required fixture population absent')
            for row in rows:
                if not isinstance(row,dict) or set(row)!={'id','input_ref','expected_ref'} or not isinstance(row['id'],str):raise ValueError('Unknown fixture field')
                ids.append(row['id']);store.read(row['input_ref']);store.read(row['expected_ref'])
        if len(ids)!=len(set(ids)):raise ValueError('Fixture partitions overlap')
    async def one(self,candidate,row,phase,operation,repeat,*,timing=False):
        reservation=self.worker.requests.put({'schema':'ai4r-rsi-worker-reservation:1','session_ref':self.session_ref,
            'candidate_ref':candidate,'phase':phase,'operation':operation,'fixture_id':row['id']})
        response=await self.worker.run(candidate,self.store.get(row['input_ref']),phase=phase,reservation_ref=reservation,repeat_index=repeat,timing=timing)
        receipt=response['receipt'];self.last_evidence.append(self.store.put({'schema':'ai4r-rsi-fixture-capture:1',
            'session_ref':self.session_ref,'candidate_ref':candidate,'fixture_id':row['id'],'phase':phase,'receipt':receipt}))
        for item in response.get('captures',[]):
            if self.store.put_bytes(self.worker.requests.read(item['ref']))!=item['ref']:raise ValueError('Private fixture capture identity differs')
        if receipt['termination_reason']!='completed' or receipt['exit_code']!=0:raise ValueError('Worker evaluation did not complete under confinement')
        value=json.loads(self.store.read(receipt['stdout_ref']))
        return int(value==self.store.get(row['expected_ref'])),receipt['wall_time_s']
    async def scores(self,candidate,phase,operation):
        self.last_evidence=[];scores=[]
        for row in self.manifest['partitions'][phase]:
            values=[]
            for repeat in range(self.repeats):
                value,_=await self.one(candidate,row,phase,operation,repeat);values.append(value)
            scores.append(values)
        return scores
    async def loop(self,candidate,split):
        # LoopOracle has durably charged before entering this callback.
        scores=await self.scores(candidate,split,'loop:'+uuid.uuid4().hex)
        total=sum((Fraction(sum(row),self.repeats) for row in scores),Fraction())
        return {'passed':float(total) if total.denominator!=1 else total.numerator,'total':len(scores)}
    async def mandatory(self,candidate):
        scores=await self.scores(candidate,'platform','mandatory:'+uuid.uuid4().hex)
        return bool(scores) and all(all(value==1 for value in row) for row in scores)
    async def paired(self,parent,child,split,repeats,configuration_ref):
        if repeats!=self.repeats or configuration_ref!=self.target['configuration_ref']:raise ValueError('Final context differs from frozen target')
        p=await self.scores(parent,split,'final-parent');c=await self.scores(child,split,'final-child')
        capture={'parent':p,'child':c,'independent':self.manifest['independent'],'violations':[]}
        # Timing remains actual and profile-bound. No timing success can be
        # inferred from correctness; equal means need the complete procedure.
        expected={'parent':[Fraction(sum(row),repeats) for row in p],
                  'child':[Fraction(sum(row),repeats) for row in c]}
        # Every final referee pair requires seven actual times, including a
        # correctness gain. Timing can qualify only an equal-quality child.
        times={'parent':[],'child':[]};stable=True
        for round_index in range(12):
            order=(('parent',parent),('child',child)) if round_index%2==0 else (('child',child),('parent',parent))
            for name,candidate in order:
                elapsed=0
                for index,row in enumerate(self.manifest['partitions'][split]):
                    observed=[]
                    for repeat in range(repeats):
                        passed,duration=await self.one(candidate,row,split,'timing:'+str(round_index)+':'+name,repeat,timing=True)
                        observed.append(passed);elapsed+=duration
                    if Fraction(sum(observed),repeats)!=expected[name][index]:stable=False
                if round_index>=5:times[name].append(elapsed)
        if stable:capture.update(parent_times=times['parent'],child_times=times['child'],warmups=5,calibrated_noise=self.target['scoring']['calibrated_relative_noise'])
        else:capture['timing_unavailable_reason']='Observed timed fixture means changed; comparable fixed-quality timing was not established'

        return capture


async def assemble_jobs(config,records):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.contracts import Principal,validate
    from jiuwenswarm.research.isolated_resources import build_isolated_resources
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    from .controller import Controller
    from .custodian_client import CustodianClient
    from .assessment import GuardedAssessment
    from .proposer import GuardedProposer
    from .profiles import freeze_profile,Limits
    from .mutation import child_declaration
    from .opportunity import decide
    binding=records.get(config['resource_binding_ref'])
    fields={'isolation_root','core_root','account_root','forbidden_roots','principal','exact_binding_refs','run_contexts','custodian','worker','parent_directory','work_root','approved_session_refs','public_root','public_record_refs','native_containment_ref'}
    qualified_binding=binding.get('schema')=='ai4r-rsi-workbench-resources:2'
    closed(binding,fields|({'security_qualification_ref'} if qualified_binding else set()),'ai4r-rsi-workbench-resources:2' if qualified_binding else 'ai4r-rsi-workbench-resources:1')
    root=owned_directory(binding['isolation_root'],12001)
    for key in ('core_root','account_root','work_root'):
        path=owned_directory(binding[key],12001)
        if not path.is_relative_to(root):raise ValueError('Workbench resource escapes isolated root')
    core=SQLiteRunStore(binding['core_root'],recover=False)
    from .qualification import captured_qualification
    qualification=captured_qualification(core,binding.get('security_qualification_ref'))
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    publication=OriginalBytes(shared_directory(binding['public_root'],12001),writable=True)
    store=CombinedRecords(records,core,publisher=publication)
    for pin in binding['public_record_refs']:publication.put_ref(pin,store.read(pin))
    from .native_lease import NativeEffectLease
    scope_ref=records.put({'schema':'ai4r-rsi-native-profile-scope:1','isolation_root':str(root),'account_root':binding['account_root']})
    native_lease=NativeEffectLease(records,scope_ref)
    if binding['native_containment_ref'] is not None:native_lease.release_from_receipt(binding['native_containment_ref'],store.read)
    exact=binding['exact_binding_refs'];configuration=core.read_record(exact['configuration_ref'])
    operator=OperatorConfiguration.from_mapping(configuration.get('operator',configuration),resolve_profile=core.read_record)
    actor=binding['principal']
    if set(actor)!={'account_id','workspace_ids','operations','audiences'}:raise ValueError('Unknown captured actor field')
    principal=Principal(actor['account_id'],frozenset(actor['workspace_ids']),frozenset(actor['operations']),frozenset(actor['audiences']))
    worker_binding=binding['worker']
    closed(worker_binding,{'socket_path','session_id','capability','requests_root','profile_ref'},'ai4r-rsi-worker-client:1')
    requests=RecordStore(owned_directory(worker_binding['requests_root'],12001))
    if not binding['approved_session_refs']:raise ValueError('No captured isolated session is authorized')
    worker_probe=WorkerClient(socket_path=worker_binding['socket_path'],session_id=worker_binding['session_id'],capability=worker_binding['capability'],
        requests=requests,profile_ref=worker_binding['profile_ref'],session_ref=binding['approved_session_refs'][0])
    # The isolated core receives its own finite executor capability. Pure helper
    # execution is exposed separately; no main-account executor is referenced.
    class OwnExecutor:
        workspace_root=Path(binding['work_root'])
        async def prerequisites(self):
            value=await worker_probe.prerequisites()
            if not isinstance(value,dict) or value.get('ready') is not True or value.get('worker_uid')!=12003 or worker_binding['profile_ref'] not in value.get('profile_refs',[]):return ['RSI_WORKER_BROKER_UNQUALIFIED']
            return []
    async def unavailable_readiness(_):raise ValueError('Use the separately qualified finite job readiness')
    executor=OwnExecutor()
    if await executor.prerequisites():raise ValueError('Actual isolated worker peer/profile/confinement is unavailable')
    subscription=SubscriptionService(Path(binding['account_root']))
    subscription.set_account_observer(core.append_record)
    # An uncertain native owner cannot be replaced even by a status bootstrap.
    # Keep the finite port available for history closure/inspection only; the
    # factory's durable lease guard blocks every new session/model effect.
    resources=await build_isolated_resources(store=core,operator=operator,own_subscription_service=subscription,
        own_executor=executor,principal=principal,exact_binding_refs=exact,isolation_root=root,forbidden_roots=binding['forbidden_roots'],readiness=unavailable_readiness)
    if not resources.ready:raise ValueError('Exact isolated core admissions and bindings are unavailable')
    resources.composition.library.rsi_security_guard=qualification
    for run_id,context in binding['run_contexts'].items():resources.runner.configure_run(run_id,**context)
    custody=binding['custodian'];closed(custody,{'socket_path','peer_uid','requests_root','public_roots'},'ai4r-rsi-custodian-client:1')
    custody_requests=RecordStore(shared_directory(custody['requests_root'],12001),file_mode=0o640)
    public=PublicBytes(custody['public_roots']);store.public=public
    async def factory(job,*,recovery=False):
        closed(job,{'session_ref','opportunity_ref','visible_context_ref','proposer_contract_refs','worker_profile_ref','fixture_identity','target_kind'},'ai4r-rsi-session-job:1')
        if not recovery:native_lease.assert_available()
        if job['session_ref'] not in binding['approved_session_refs'] or job['target_kind'] not in {'ranking-v1','screening-text-v1'}:raise ValueError('Job is outside the frozen target registry')
        if not recovery:
            from .qualification import require_qualification
            require_qualification(qualification,'session_start',session_ref=job['session_ref'],worker_profile_ref=job['worker_profile_ref'])
            await native_profile_ready(subscription,native_lease)
        if job['target_kind']=='screening-text-v1':
            from .text_resources import assemble_text_job
            return await assemble_text_job(job,resources=resources,store=store,binding=binding,custody=custody,
                custody_requests=custody_requests,native_lease=native_lease,publication=publication,
                trial_runtime=factory.trial_port,principal=principal,recovery=recovery,qualification=qualification)
        if job['worker_profile_ref']!=worker_binding['profile_ref']:raise ValueError('Ranking worker profile differs')
        session=store.get(job['session_ref']);validate('rsi-session',session)
        if session['started_by']!=principal.account_id:raise ValueError('Session actor differs from captured authorization')
        limits=Limits.from_mapping(session['limits'])
        if len(job['proposer_contract_refs'])!=limits.max_attempts:raise ValueError('Bounded per-attempt proposer contracts are missing')
        target=store.get(session['target_profile_ref']);parent=store.get(session['parent_declaration_ref']);freeze_profile(target,parent,validate)
        from .worker import validate_profile
        worker_profile=validate_profile(store.get(job['worker_profile_ref']))
        if worker_profile['session_ref']!=job['session_ref'] or worker_profile['target_ref']!=session['target_profile_ref'] or worker_profile['parent_ref']!=target['parent_ref']:raise ValueError('Worker profile differs from the frozen session target')
        if session['pass_count_repeats']!=1 or worker_profile['memory_mb']>target['limits']['memory_mb'] or worker_profile['timeout_s']>min(target['limits']['time_s'],limits.per_call_s):raise ValueError('Deterministic target repetition or resource scope was widened')
        for pin in (job['session_ref'],session['target_profile_ref'],session['parent_declaration_ref'],session['chain_root_ref'],session['hash_profile_ref'],target['parent_ref']):
            publication.put_ref(pin,store.read(pin))
        parent_hashes={row['sha256'] for row in parent['identity']['body']}
        for ident,entry in core.ref_index().items():
            if entry['sha256'] in parent_hashes:publication.put_ref({'id':ident,'sha256':entry['sha256']},core.read_blob({'id':ident,'sha256':entry['sha256']}))
        entry=resources.composition.library.get(session['parent']['cc_name'],session['parent']['cc_version'])
        admission=core.read_record(entry['admission_ref'],contract_id='library-admission')
        if entry['declaration_ref']!=session['parent_declaration_ref'] or admission['status']!='admitted':raise ValueError('Selected immutable admitted parent is unavailable')
        if worker_profile['memory_mb']>admission['memory_mb']:raise ValueError('Worker memory exceeds the frozen parent admission')
        opportunity=store.get(job['opportunity_ref']);closed(opportunity,{'attribution','symptom_reproduced','mandatory_passed','headroom','headroom_minimum','diagnosis','resource_ready','evidence_refs','parent_visible_time_s'},'ai4r-rsi-opportunity:1')
        if not opportunity['evidence_refs']:raise ValueError('Measured opportunity has no actual evidence')
        for pin in opportunity['evidence_refs']:store.read(pin)
        decision=decide(**{k:opportunity[k] for k in ('attribution','symptom_reproduced','mandatory_passed','headroom','headroom_minimum','diagnosis','resource_ready')})
        if decision.get('decision')!='START':raise ValueError('Target lacks an eligible measured implementation opportunity')
        decision['parent_visible_time_s']=opportunity['parent_visible_time_s']
        worker=WorkerClient(socket_path=worker_binding['socket_path'],session_id=worker_binding['session_id'],capability=worker_binding['capability'],
            requests=requests,profile_ref=job['worker_profile_ref'],session_ref=job['session_ref'])
        visible=store.get(job['visible_context_ref'])
        if set(visible)!={'context','mandatory_fixtures','required_test_refs'} or visible['required_test_refs']!=target['required_test_refs'] or not visible['mandatory_fixtures']:raise ValueError('Visible required tests are incomplete')
        parent_directory=owned_directory(binding['parent_directory'],12001)
        if not parent_directory.is_relative_to(root):raise ValueError('Parent sandbox is outside isolated state')
        expected_files={row['path']:row['sha256'] for row in parent['identity']['body']}
        for dependency in parent['needs']['external']:
            pin=dependency.get('pin')
            if isinstance(pin,dict) and set(pin)=={'ref','sha256'}:expected_files[pin['ref']]=pin['sha256']
        actual_files={p.relative_to(parent_directory).as_posix():p for p in parent_directory.rglob('*') if p.is_file() or p.is_symlink()}
        if set(actual_files)!=set(expected_files):raise ValueError('Parent sandbox contains missing or undeclared files')
        for name,p in actual_files.items():
            if p.is_symlink() or p.stat().st_nlink!=1 or hashlib.sha256(p.read_bytes()).hexdigest()!=expected_files[name]:raise ValueError('Parent snapshot differs from the frozen implementation closure')
        async def mandatory(snapshot,declaration):
            child=store.put_bytes((Path(snapshot['path'])/target['mutable_paths'][0]).read_bytes());pins=[];durations=[];passed=True
            from .targets.ranking import rank_opportunities
            for index,fixture in enumerate(visible['mandatory_fixtures']):
                if set(fixture)!={'input_ref','test_ref'} or fixture['test_ref'] not in target['required_test_refs']:raise ValueError('Unknown mandatory test binding')
                inputs=store.get(fixture['input_ref']);expected=rank_opportunities(inputs['scores'])
                reserve=requests.put({'session_ref':job['session_ref'],'candidate_ref':child,'phase':'development','operation':'mandatory:'+uuid.uuid4().hex})
                # Candidate bytes are copied to the explicitly shared public
                # controller request store; no hidden fixture enters it.
                requests.put_bytes(store.read(child))
                result=await worker.run(child,inputs,phase='development',reservation_ref=reserve)
                for item in result.get('captures',[]):
                    if store.put_bytes(requests.read(item['ref']))!=item['ref']:raise ValueError('Visible worker capture identity differs')
                receipt=result['receipt'];ok=receipt['termination_reason']=='completed' and receipt['exit_code']==0
                if ok:ok=json.loads(requests.read(receipt['stdout_ref']))==expected
                passed=passed and ok;durations.append(receipt['wall_time_s']);pins.append(store.put({'schema':'ai4r-rsi-visible-check:1','test_ref':fixture['test_ref'],'candidate_ref':child,'receipt':receipt,'passed':ok}))
            if set(encoded(f['test_ref']) for f in visible['mandatory_fixtures'])!=set(encoded(p) for p in target['required_test_refs']):raise ValueError('Some required parent tests were not executed')
            return {'passed':passed,'evidence_refs':pins,'visible_selection_time_s':sum(durations)}
        async def declaration(snapshot,child,diff):
            hashes={row['path']:row['sha256'] for row in parent['identity']['body']};hashes[target['mutable_paths'][0]]=child['sha256']
            label=parent['identity']['version_label']+'.'+uuid.uuid4().hex[:8]
            value=child_declaration(parent,body_hashes=hashes,version_label=label,carrier=parent['identity']['carrier'],
                lineage={'parent':session['parent_declaration_ref'],'co_parents':[],'relation':'supersedes','builder':'rsi_workbench',
                    'build_trigger':session['session_id'],'context_capsules':[],'diagnosis_inputs':opportunity['evidence_refs'],
                    'builder_ref':store.proposer_starts(session['session_id'])[-1],
                    'provenance':{'generating_model':None,'prompt_ref':session['improver_ref'],'trajectory_ref':store.proposer_starts(session['session_id'])[-1]}},validate=validate)
            pin=store.put(value)
            return value,{'cc_name':value['identity']['name'],'cc_version':label,'declaration_sha256':pin['sha256']}
        client=CustodianClient(custody_requests,socket_path=custody['socket_path'],peer_uid=custody['peer_uid'],session_id=session['session_id'],timeout=limits.wall_s)
        proposer=GuardedProposer(CoreProposer(resources,job['proposer_contract_refs'],store,native_lease=native_lease,session_id=session['session_id'],qualification=qualification,session_ref=job['session_ref']),configuration_ref=session['configuration_ref'],improver_ref=session['improver_ref'],limits=limits,store=store)
        assess=GuardedAssessment(parent_directory=binding['parent_directory'],target=target,store=store,work_root=binding['work_root'],run_mandatory=mandatory,make_declaration=declaration)
        async def recovery_containment(sid):
            if sid!=session['session_id']:raise ValueError('Recovery containment session differs')
            try:await client.halt(sid)
            finally:await worker.cancel()
            # A new in-memory owner cannot prove an old native process stopped;
            # durable uncertain leases still require the exact host receipt.
            native_lease.assert_available()
            return {'contained':True,'session_id':sid}
        controller=Controller(store=store,ledger=client,oracle=client,proposer=proposer,assess=assess,signer=client,validate=validate,
            recovery_containment=recovery_containment,qualification=qualification)
        async def final(best):
            value=store.get(best['child_declaration_ref'])
            value['identity']['lineage']['builder_ref']=best['attempt_ref']
            value['identity']['lineage']['provenance']['trajectory_ref']=best['attempt_ref']
            validate('capsule-declaration',value)
            best['child_declaration_ref']=store.put(value)
            best['child']={**best['child'],'declaration_sha256':best['child_declaration_ref']['sha256']}
            decision,pin=await client.final(dict(attempt_ref=best['attempt_ref'],target_ref=session['target_profile_ref'],parent_ref=target['parent_ref'],child_ref=best['child_ref'],
                configuration_ref=session['configuration_ref'],repeats=session['pass_count_repeats'],qualification=session['qualification'],mandatory_passed=True,integrity_passed=True))
            if store.put(custody_requests.get(pin))!=pin:raise ValueError('Transferred public final record changed')
            return decision,pin
        return controller,dict(session=session,session_ref=job['session_ref'],opportunity=decision,fixture_identity=job['fixture_identity'],visible_context=visible['context'],parent_body_ref=target['parent_ref'],finalize=final)
    # Optional fixed Target2 port: a separate input publication and UID grant,
    # never the public proposer OriginalBytes root or ordinary jobs socket.
    factory.trial_port=None
    trial_file=os.environ.get('AI4R_RSI_TRIAL_BINDING_FILE')
    if trial_file is not None:
        try:
            factory.trial_port=assemble_trial_runtime(trial_file,records,resources,native_lease,qualification=qualification)
        except (OSError,ValueError,KeyError):
            factory.trial_unavailable='Exact optional text-trial binding, custody input grant or parent tests are unavailable'
    return factory,store.read,resources.trace_reader,resources


async def assemble_custodian(config,records):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from jiuwenswarm.research_records.contracts import ContractData
    from .custody import ExposureLedger,require_custody
    from .signing import Signer,verify
    from .oracle import LoopOracle
    from .referee import Referee
    from .custodian_service import CustodianService
    require_custody(config['custody_root'],12002)
    binding=records.get(config['resource_binding_ref'])
    qualified_binding=binding.get('schema')=='ai4r-rsi-custodian-resources:3'
    text_mode=binding.get('schema') in {'ai4r-rsi-custodian-resources:2','ai4r-rsi-custodian-resources:3'}
    closed(binding,{'public_roots','worker','session_refs','fixture_root','candidate_inbox','public_record_refs'}|
        ({'text_profile_refs','trial_input_root'} if text_mode else set())|({'security_qualification_ref'} if qualified_binding else set()),
        'ai4r-rsi-custodian-resources:3' if qualified_binding else 'ai4r-rsi-custodian-resources:2' if text_mode else 'ai4r-rsi-custodian-resources:1')
    private=owned_directory(binding['fixture_root'],12002);public=PublicBytes(binding['public_roots'])
    store=CombinedRecords(records,public=public)
    from .qualification import captured_qualification
    qualification=captured_qualification(store,binding.get('security_qualification_ref'))
    manifest=store.get(config['fixture_manifest_ref'])
    key_path=Path(config['signing_key_file'])
    if key_path.is_symlink() or key_path.stat().st_uid!=12002 or stat.S_IMODE(key_path.stat().st_mode)!=0o600:raise ValueError('Independent signing key is not private')
    signer=Signer(Ed25519PrivateKey.from_private_bytes(key_path.read_bytes()),config['signer_key_id'])
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    inbox=shared_directory(binding['candidate_inbox'],12002)
    publication=OriginalBytes(inbox,writable=True)
    for pin in binding['public_record_refs']:publication.put_ref(pin,store.read(pin))
    validate=ContractData().validate;ledger=ExposureLedger(Path(config['custody_root'])/'exposure.sqlite')
    requests=PublicBytes([config['request_root']]);worker_binding=binding['worker']
    if worker_binding is not None:
        closed(worker_binding,{'socket_path','session_id','capability','requests_root','profile_ref'},'ai4r-rsi-worker-client:1')
        worker_records=RecordStore(owned_directory(worker_binding['requests_root'],12002))
    elif not text_mode:raise ValueError('Frozen ranking worker binding is missing')
    grant_map={};runtimes={};sessions={}
    for session_ref in binding['session_refs']:
        session=store.get(session_ref);validate('rsi-session',session);sid=session['session_id']
        if sid not in config['authorized_sessions']:raise ValueError('Custodian session is not explicitly granted')
        target=store.get(session['target_profile_ref'])
        if manifest['target_ref']!=session['target_profile_ref']:raise ValueError('Private fixtures name another frozen target')
        text_profiles=[ref for ref in binding.get('text_profile_refs',[]) if store.get(ref).get('session_ref')==session_ref]
        if len(text_profiles)>1:raise ValueError('Ambiguous exact text profile')
        if text_profiles:
            from .text_resources import assemble_text_custody
            evaluator=assemble_text_custody(profile_ref=text_profiles[0],session_ref=session_ref,session=session,target=target,
                manifest=manifest,store=store,public=public,ledger=ledger,signer=signer,
                input_root=binding['trial_input_root'],custody_root=config['custody_root'])
        else:
            if worker_binding is None:raise ValueError('No actual frozen target execution owner')
            from .worker import validate_profile
            worker_profile=validate_profile(public.get(worker_binding['profile_ref']))
            if (worker_profile['session_ref']!=session_ref or worker_profile['target_ref']!=session['target_profile_ref']
                or worker_profile['parent_ref']!=target['parent_ref'] or worker_profile['memory_mb']>target['limits']['memory_mb']
                or worker_profile['timeout_s']>min(target['limits']['time_s'],session['limits']['per_call_s'])):
                raise ValueError('Hidden worker profile differs from the exact frozen evaluation scope')
            worker=WorkerClient(socket_path=worker_binding['socket_path'],session_id=worker_binding['session_id'],capability=worker_binding['capability'],requests=worker_records,
                profile_ref=worker_binding['profile_ref'],session_ref=session_ref,hidden=True)
            evaluator=FixtureEvaluator(manifest=manifest,store=store,worker=worker,session_ref=session_ref,target=target,repeats=session['pass_count_repeats'])
        calibration=store.get(manifest['calibration_ref']);verify(calibration,signer.public_bytes(),config['signer_key_id'])
        # Excluding only the calibration link avoids an impossible circular
        # content hash while binding every other frozen target/fixture field.
        target_context=hashlib.sha256(encoded({key:value for key,value in target.items() if key!='calibration_ref'})).hexdigest()
        fixture_context=hashlib.sha256(encoded({key:value for key,value in manifest.items() if key!='calibration_ref'})).hexdigest()
        calibration_fields={'target_context_sha256','fixture_context_sha256','known_bad_rejected','known_good_qualified','measurable_headroom','evidence_refs','signer_key_id','signature'}
        if set(calibration)!=calibration_fields or calibration.get('target_context_sha256')!=target_context or calibration.get('fixture_context_sha256')!=fixture_context or calibration.get('known_bad_rejected',0)<10 or calibration.get('known_good_qualified',0)<3 or not calibration.get('measurable_headroom') or not calibration.get('evidence_refs'):raise ValueError('Actual frozen planted-child calibration/headroom unavailable')
        if target['calibration_ref']!=manifest['calibration_ref']:raise ValueError('Target calibration differs from the custody aggregate')
        for pin in calibration['evidence_refs']:store.read(pin)
        identity=ledger.register(manifest['fixture_identity'],{name:[row['id'] for row in rows] for name,rows in manifest['partitions'].items()},known_bad=calibration['known_bad_rejected'],known_good=calibration['known_good_qualified'])
        if identity!=manifest['fixture_identity']:raise ValueError('Fixture lifetime identity differs from registered lineage')
        grant_map[sid]={'fixture_identity':identity,'session_cap':session['limits']['session_query_limit'],'lifetime_cap':session['limits']['lifetime_query_limit'],'session_ref':session_ref}
        runtimes[sid]=evaluator;sessions[sid]=session
    class SessionOracle:
        async def score(self,sid,action,candidate):
            evaluator=runtimes[sid]
            if not await evaluator.mandatory(candidate):raise ValueError('Independent mandatory parent checks rejected candidate before hidden query')
            # The complete loop candidate operation is charged exactly once by
            # the shared durable ledger before any hidden inputs are released.
            return await LoopOracle(ledger,evaluator.loop,repeats=sessions[sid]['pass_count_repeats']).score(sid,action,candidate)
    class SessionReferee:
        def __init__(self):self.store=store
        async def final(self,sid,**comparison):
            session=sessions[sid];target=store.get(session['target_profile_ref'])
            expected={'target_ref':session['target_profile_ref'],'parent_ref':target['parent_ref'],'configuration_ref':session['configuration_ref'],
                'repeats':session['pass_count_repeats'],'qualification':session['qualification']}
            if any(comparison.get(k)!=v for k,v in expected.items()):raise ValueError('Final comparison differs from custody grant')
            if hasattr(runtimes[sid],'comparison'):
                runtimes[sid].comparison={k:comparison[k] for k in ('attempt_ref','target_ref','parent_ref','child_ref','configuration_ref','repeats','qualification')}
            passed=await runtimes[sid].mandatory(comparison['parent_ref']) and await runtimes[sid].mandatory(comparison['child_ref'])
            if not passed:raise ValueError('Independent mandatory parent tests failed before final comparison')
            comparison=dict(comparison,mandatory_passed=True,integrity_passed=True)
            return await Referee(ledger,store,signer,runtimes[sid].paired,validate).final(sid,**comparison)
    def package_publisher(result_ref):
        from .package import build_candidate,publish_candidate,write_candidate
        public_reader=PublicBytes([*binding['public_roots'],inbox])
        # Only these two newly signed aggregate records become public here;
        # FixtureEvaluator's private captures remain in the custody store.
        result=store.get(result_ref);publication.put_ref(result_ref,store.read(result_ref))
        evidence_ref=result['referee_evidence_ref'];publication.put_ref(evidence_ref,store.read(evidence_ref))
        def resolve_body(digest):
            for root in public_reader.roots:
                index=OriginalBytes(root).index() if (root/'original-byte-index.json').exists() else {}
                for ident,value in index.items():
                    if value==digest:return {'id':ident,'sha256':digest}
            raise ValueError('Public original child body unavailable')
        def put_public(value):
            pin=store.put(value);publication.put_ref(pin,store.read(pin));return pin
        package=build_candidate(result_ref,read_ref=public_reader.read,put_record=put_public,resolve_body_ref=resolve_body,
            public_key=signer.public_bytes(),key_id=config['signer_key_id'],validate=validate,qualification=qualification)
        publish_candidate(package,read_public=public_reader.read,publication=publication,qualification=qualification)
        return write_candidate(package,session_result=result,referee_evidence=store.get(evidence_ref),public_key=signer.public_bytes(),
            key_id=config['signer_key_id'],read_ref=public_reader.read,validate=validate,inbox=inbox,custodian_uid=12002,qualification=qualification)
    async def contain_session(sid):
        worker=getattr(runtimes[sid],'worker',None)
        if worker is not None:await worker.cancel()
        # Text effects run in the controller's exact private owner. The
        # controller containment callback cancels those owned tasks after this
        # custody ledger has been halted; no hidden worker proof substitutes.
    service=CustodianService(requests,ledger,SessionOracle(),SessionReferee(),signer,validate,config['authorized_sessions'],session_grants=grant_map,public_store=store,package_publisher=package_publisher,contain_session=contain_session,qualification=qualification)
    return service,ledger


def assemble_trial_runtime(path,records,resources,native_lease,*,qualification=None):
    """Fixed optional assembly, no module/factory or caller actor selection."""
    from .trial_port import TrialPort,ParentTrialPort
    from .text_trial import TRIAL_SOCKET
    from .text_checks import TextParentTests
    from jiuwenswarm.research.isolated_evaluation import IsolatedEvaluation
    if path!='/run/ai4r-rsi/trial-binding.json':raise ValueError('Unknown text-trial bootstrap path')
    supplied=Path(path)
    if any(p.is_symlink() for p in (supplied,*supplied.parents)):raise ValueError('Unsafe text-trial bootstrap custody')
    meta=supplied.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or meta.st_uid!=0 or meta.st_mode&0o022 or meta.st_size>4096:
        raise ValueError('Text-trial bootstrap is not protected')
    pointer=json.loads(supplied.read_bytes())
    if set(pointer)!={'binding_ref'}:raise ValueError('Unknown text-trial bootstrap fields')
    binding=records.get(pointer['binding_ref'])
    current=binding.get('schema')=='ai4r-rsi-text-trial-runtime:2'
    closed(binding,{'binding_id','allowed_session_refs','socket_path','custodian_input_root'}|({'parent_bindings'} if current else set()),
        'ai4r-rsi-text-trial-runtime:2' if current else 'ai4r-rsi-text-trial-runtime:1')
    if binding['binding_id']!='screening-text-v1' or binding['socket_path']!=TRIAL_SOCKET or binding['custodian_input_root']!='/var/lib/ai4r-rsi-trial-inputs' or not binding['allowed_session_refs']:
        raise ValueError('Unknown finite text-trial runtime')
    socket_root=Path(TRIAL_SOCKET).parent
    if any(p.is_symlink() for p in (socket_root,*socket_root.parents)):raise ValueError('Unsafe private trial socket ancestry')
    socket_owner=socket_root.stat()
    if (not stat.S_ISDIR(socket_owner.st_mode) or socket_owner.st_uid!=12001 or socket_owner.st_gid!=12002
            or stat.S_IMODE(socket_owner.st_mode)!=0o2750):raise ValueError('Exact controller/custodian socket custody is unavailable')
    root=shared_directory(binding['custodian_input_root'],12002)
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    legitimate=OriginalBytes(root)
    service=IsolatedEvaluation(resources,required_tests=TextParentTests(resources.store))
    child=TrialPort(service,resources.store,public_reader=legitimate.read,allowed_session_refs=binding['allowed_session_refs'],native_lease=native_lease,qualification=qualification)
    if not current:return child
    from jiuwenswarm.research.parent_measurement import ParentMeasurement
    parent=ParentTrialPort(ParentMeasurement(resources),resources.store,public_reader=legitimate.read,
        allowed_session_refs=binding['allowed_session_refs'],parent_bindings=binding['parent_bindings'],native_lease=native_lease,qualification=qualification)
    class TrialRuntime:
        parent_bindings=binding['parent_bindings']
        def handlers(self):return child.handlers()|parent.handlers()
        async def contain_session(self,session_id):
            import asyncio
            await asyncio.gather(child.contain_session(session_id,recheck=False),parent.contain_session(session_id,recheck=False))
            native_lease.assert_available()
            return {'contained':True,'session_id':session_id}
    return TrialRuntime()
