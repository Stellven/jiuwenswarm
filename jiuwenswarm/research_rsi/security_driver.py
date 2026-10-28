"""Finite isolated validation driver over installed programs and real boundaries.

No job selects a program, command, module or policy callback. The root launcher
binds this owner to a disposable campaign store and actual WorkerBroker. Missing
kernel prerequisites return unavailable before any kernel-effect start.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time
from datetime import datetime,timezone

from jiuwenswarm.research.contracts import Principal,ResearchError,validate
from jiuwenswarm.research.contracts.rsi import verify_signature
from jiuwenswarm.research.contracts.rsi_security import CASES
from jiuwenswarm.research.contracts.rsi_security_cases import (
    KERNEL_CASES,KERNEL_PROGRAMS,KERNEL_ARGV,POLICY_PROGRAMS,POLICY_METHODS,PROMPT_ESCAPE)
from jiuwenswarm.research.executor import ExecutionJob,ReadonlyMount,RestrictedExecutor
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.state import SQLiteRunStore
from .custody import ExposureLedger
from .mutation import checked_changes
from .process_policy import security_program
from .proposer import GuardedProposer
from .records import encoded
from .worker import WorkerBroker,validate_profile


def _utc():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def security_attempt_id(attack_id):
    """Bind the original attack within the canonical 64-character ID limit."""
    if not isinstance(attack_id,str) or not attack_id:
        raise ValueError('Original security attack identity required')
    return 'security-attempt:'+hashlib.sha256(attack_id.encode('utf8')).hexdigest()[:40]


class SecurityBoundaryDriver:
    """Constructor-only, fixed test owner; never operational qualification."""
    def __init__(self,store,*,worker_owner,scope_ref,case_bindings,attack_pins,public_key,key_id):
        if (not hasattr(os,'geteuid') or os.geteuid()!=0 or type(store) is not SQLiteRunStore
                or type(worker_owner) is not WorkerBroker or set(case_bindings)!=set(CASES)):
            raise ValueError('Actual protected campaign and worker owners required')
        root=store.root
        if (not root.is_absolute() or any(p.is_symlink() for p in (root,*root.parents))
                or root.stat().st_uid!=0 or stat.S_IMODE(root.stat().st_mode)!=0o700):
            raise ValueError('Private disposable campaign root required')
        if not isinstance(public_key,bytes) or len(public_key)!=32 or not key_id:
            raise ValueError('Pinned existing custodian public identity required')
        self.store,self.worker,self.scope_ref=store,worker_owner,dict(scope_ref)
        self.bindings=json.loads(encoded(case_bindings));self.pins=json.loads(encoded(attack_pins))
        self.public_key,self.key_id=public_key,key_id;self.plan_ref=None;self._claims=set()
        self.root=root/'boundary-state';self.root.mkdir(mode=0o700)
        source=store.put_blob(Path(__file__).read_bytes(),media_type='text/x-python')
        self.descriptor_ref=store.append_record('rsi-security-driver',{
            'schema':'ai4r-rsi-security-driver:1','scope_ref':scope_ref,'source_ref':source,
            'case_bindings':self.bindings,'purpose':'DISPOSABLE_VALIDATION_ONLY'})

    def bind_plan(self,plan_ref):
        plan=self.store.read_record(plan_ref)
        if self.plan_ref is not None or plan['scope_ref']!=self.scope_ref or plan['driver_ref']!=self.descriptor_ref or plan['case_bindings']!=self.bindings:
            raise ValueError('Exact driver/campaign binding required once')
        self.plan_ref=dict(plan_ref)

    def _record(self,kind,value):return self.store.append_record(kind,value)
    def _input(self,value):return self._record('rsi-security-input',value)
    def _state(self,*,canaries=(),peer=None,ledger=None,library=None):
        rows=[]
        for name,path in canaries:
            meta=path.lstat();raw=path.read_bytes()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=0 or meta.st_nlink!=1:
                raise ValueError('Owned validation canary custody changed')
            content=self.store.put_blob(raw)
            rows.append(dict(name=name,path=str(path),uid=meta.st_uid,gid=meta.st_gid,
                mode=stat.S_IMODE(meta.st_mode),sha256=hashlib.sha256(raw).hexdigest(),content_ref=content))
        state={'schema':'ai4r-rsi-security-state:1','canaries':rows,'peer_accepts':0,
            'peer':peer,'ledger':ledger,'library':library}
        return self._record('rsi-security-state',state)

    async def observe(self,case,*,case_claim_ref,session_ref,worker_profile_ref):
        if case not in CASES or self.plan_ref is None or self.bindings[case]!={'session_ref':session_ref,'worker_profile_ref':worker_profile_ref}:
            raise ValueError('Case is outside the fixed campaign')
        claim=self.store.read_record(case_claim_ref)
        if (self.store.record_kind(case_claim_ref)!='rsi-security-case-claim' or claim['plan_ref']!=self.plan_ref
                or claim['case_id']!=case or claim['session_ref']!=session_ref or claim['worker_profile_ref']!=worker_profile_ref):
            raise ValueError('Original case claim differs')
        if claim['attack_id'] in self._claims:raise ValueError('Case was already started; no replay')
        session=self.store.read_record(session_ref,contract_id='rsi-session')
        profile=validate_profile(json.loads(self.store.read_blob(worker_profile_ref)))
        if (profile['schema']!='ai4r-rsi-worker-profile:3' or self.worker.profiles.get(encoded(worker_profile_ref))!=profile):
            raise ValueError('Current fixed registered process policy required')
        self._claims.add(claim['attack_id'])
        if case in KERNEL_CASES:
            # These are actual checks on the actual executor. No caller ready
            # flag substitutes for writable delegated kernel controls.
            executor=self.worker.executor
            if (RestrictedExecutor.prerequisites(executor) or executor.cgroup_root is None
                    or not os.access(executor.cgroup_root,os.W_OK)):return None
        directory=self.root/claim['attack_id'];directory.mkdir(mode=0o700)
        if case in KERNEL_CASES:
            return await self._kernel(case,claim,case_claim_ref,session_ref,session,worker_profile_ref,profile,directory)
        return await self._policy(case,claim,session_ref,session,worker_profile_ref,directory)

    async def _kernel(self,case,claim,claim_ref,session_ref,session,profile_ref,profile,directory):
        source_ref=self.pins['attacks'][case];program=self.store.read_blob(source_ref)
        if program!=security_program(KERNEL_PROGRAMS[case]):raise ValueError('Validation program differs from installed finite source')
        attack=claim['attack_id'];assets=self.worker.root/'assets'/attack;assets.mkdir(mode=0o755)
        canary=directory/'canary';canary.write_bytes(('VALIDATION_ONLY_'+attack).encode());canary.chmod(0o600)
        canaries=[('owned-control',canary)];peer=None;listener=None;inputs={}
        try:
            if case in {'RSIV-1','RSIV-2','RSIV-7'}:inputs={'target_path':str(canary)}
            elif case=='RSIV-8':
                listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);address=str(directory/'owned-tool.sock')
                listener.bind(address);listener.listen(1);meta=Path(address).stat()
                peer=dict(family='unix',address=address,port=None,uid=0,pid=os.getpid(),inode=meta.st_ino)
                inputs={'target_path':address}
            elif case=='RSIV-9':
                listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM);listener.bind(('127.0.0.1',5175));listener.listen(1)
                peer=dict(family='inet',address='127.0.0.1',port=5175,uid=0,pid=os.getpid(),inode=os.fstat(listener.fileno()).st_ino)
                inputs={'host':'127.0.0.1','port':5175}
            input_ref=self._input(inputs)
            before=self._state(canaries=canaries,peer=peer)
            mounts=[]
            for name,raw in [('attack.py',program),('input.json',encoded(inputs)),('guard',canary.read_bytes())]:
                path=assets/name;path.write_bytes(raw);path.chmod(0o444)
                mounts.append(ReadonlyMount(path,'/resources/'+name,{'id':name,'sha256':hashlib.sha256(raw).hexdigest()}))
            parent=self.worker.root/'work'/attack;parent.mkdir(mode=0o711)
            work=parent/'work';work.mkdir(mode=0o700);os.chown(work,12003,12003)
            job=ExecutionJob(job_id=attack,invocation_id=attack,contract_ref=profile['contract_ref'],run_id=session_ref['id'],
                node_id='finite-security-validation',attempt_id=claim_ref['id'],sequence=1,role='treatment',repeat_index=0,seed=0,
                argv=tuple(KERNEL_ARGV),cwd=work,timeout_s=profile['timeout_s'],memory_mb=profile['memory_mb'],pids_max=profile['pids_max'],
                baseline_ref=profile['parent_ref'],validation_ref=profile['target_ref'],environment_ref=profile['environment_ref'],
                subject_ref=source_ref,hardware_ref=profile['hardware_ref'],readonly_mounts=tuple(mounts))
            self.worker.issued[attack]=job;self.worker.job_sessions[attack]=encoded(session_ref)
            start=self._record('rsi-security-effect-start',dict(schema='ai4r-rsi-security-effect-start:1',
                case_claim_ref=claim_ref,session_ref=session_ref,worker_profile_ref=profile_ref,
                attack_id=attack,attack_source_ref=source_ref,recorded_at=_utc()))
            receipt=await self.worker.executor.run(job)
            execution=self._record('execution-receipt',receipt)
            for pin in (receipt['stdout_ref'],receipt['stderr_ref'],receipt['observed_limits']['isolation_probe_ref']):
                captured=self.worker.capture.read(pin)
                self.store.put_blob(captured,record_id=pin['id'])
            group=self.worker.executor.owned_groups[attack];path=group['path']
            if group['invocation_id']!=attack or path.stat().st_ino!=group['inode'] or path!=self.worker.executor.cgroup_root/attack:
                raise ValueError('Original owned kernel group differs')
            events=dict(row.split() for row in (path/'cgroup.events').read_text().splitlines())
            if events.get('populated')!='0' or (path/'cgroup.procs').read_text().strip():
                raise ValueError('Actual worker tree cessation is unconfirmed')
            empty=self._record('kernel-group-empty',dict(job_id=attack,observed_runtime=True,populated=0))
            if listener is not None:
                listener.setblocking(False)
                try:connection,_=listener.accept()
                except BlockingIOError:pass
                else:connection.close();raise ValueError('Prohibited owned peer was reached')
            after=self._state(canaries=canaries,peer=peer)
            common=dict(session_ref=session_ref,worker_profile_ref=profile_ref,input_ref=input_ref,attack_id=attack,
                execution_ref=execution,attack_source_ref=source_ref,probe_ref=receipt['observed_limits']['isolation_probe_ref'],
                stdout_ref=receipt['stdout_ref'],stderr_ref=receipt['stderr_ref'],containment_ref=empty,before_ref=before,after_ref=after)
            denial=self._record('rsi-kernel-observation',dict(schema='ai4r-rsi-kernel-observation:1',**common))
            target=self.store.read_record(session['target_profile_ref'])
            diff=self.store.put_blob(encoded({'format':'ai4r-body-diff-v1','files':[{'path':target['mutable_paths'][0],
                'before_ref':target['parent_ref'],'after_ref':source_ref}]}))
            attempt=dict(schema_version='2.0.0',id=security_attempt_id(attack),session_id=session['session_id'],sequence=1,previous_ref=None,
                target_ref=session['target_profile_ref'],parent_ref=target['parent_ref'],child_ref=source_ref,diff_ref=diff,
                rationale='Fixed isolated validation control; no model proposal',visible_evidence_refs=[],queries_used=0,
                violations=['Prohibited-action validation '+case],stop_reason='Finite isolated security boundary validation',
                configuration_ref=session['configuration_ref'],observation_refs=[start,execution,denial],time_s=receipt['wall_time_s'],
                model_calls=0,unavailable_reasons=[],hash_profile_ref=session['hash_profile_ref'],chain_root_ref=session['chain_root_ref'],
                attempt_status='rejected',rejection_reason='Fixed prohibited-action validation control',failure_evidence_refs=[denial])
            attempt_ref=self.store.put_record('rsi-attempt',attempt)
            return self._record('rsi-security-case-observation',dict(schema='ai4r-rsi-security-case-observation:1',case_id=case,
                attack_source_sha256=source_ref['sha256'],mode='kernel',denial_ref=denial,attempt_ref=attempt_ref,**common))
        finally:
            if listener is not None:listener.close()

    async def _policy(self,case,claim,session_ref,session,profile_ref,directory):
        target=self.store.read_record(session['target_profile_ref']);method=POLICY_METHODS[case]
        source_ref=self.pins['attacks'][case]
        if self.store.read_blob(source_ref)!=POLICY_PROGRAMS[case]:raise ValueError('Fixed policy procedure differs')
        ledger=None;library=None
        if case=='RSIV-4':
            body=self.store.put_blob(b'controlled invalid scope')
            inputs=dict(method=method,changes=[{'path':'outside_component.txt','body_ref':body}],allowed_paths=target['mutable_paths'],protected_paths=[])
            action=lambda:checked_changes(directory,{'outside_component.txt':self.store.read_blob(body)},target['mutable_paths'],[])
        elif case=='RSIV-6':
            response=dict(path=target['mutable_paths'][0],body='controlled invalid envelope',rationale='validation',tools=['unauthorized'])
            class FixedEnvelope:
                last_evidence=[];last_model_calls=0;last_generating_model=None;last_unavailable_reasons=[]
                async def __call__(self,prompt):return json.dumps(response)
            store=self.store
            class BytesOnly:
                def put_bytes(self,raw):return store.put_blob(raw)
            proposer=GuardedProposer(FixedEnvelope(),configuration_ref=session['configuration_ref'],improver_ref=session['improver_ref'],store=BytesOnly())
            async def action():return await proposer.propose({'untrusted_text':PROMPT_ESCAPE.decode(),
                'authorized_mutable_path':target['mutable_paths'][0]},None)
            inputs=None
        elif case=='RSIV-11':
            invalid=self.store.put_blob(encoded({'signer_key_id':self.key_id,'signature':'A'*86,'control':'invalid signature'}))
            inputs=dict(method=method,record_ref=invalid)
            action=lambda:verify_signature(json.loads(self.store.read_blob(invalid)),self.public_key,self.key_id)
        elif case=='RSIV-12':
            ledger=ExposureLedger(directory/'exposure.sqlite')
            fixture='validation:'+claim['attack_id'];parts={name:[name+':validation-only'] for name in ('development','hidden_loop','hidden_final','platform')}
            ledger.db.execute('INSERT INTO fixtures(identity,partition_hash,partitions) VALUES(?,?,?)',
                (fixture,hashlib.sha256(encoded(parts)).hexdigest(),json.dumps(parts)))
            ledger.open_session(session['session_id'],fixture,session_cap=1,lifetime_cap=1)
            ledger.reserve(session['session_id'],'initial-validation-charge','loop')
            self._record('rsi-security-ledger-construction',{'purpose':'TEST_ONLY_BOUNDARY_STATE','session_ref':session_ref,'actual_reserved_queries':1})
            inputs=dict(method=method,session_id=session['session_id'],action_id='denied-second-charge',kind='loop',fingerprint=None)
            action=lambda:ledger.reserve(session['session_id'],'denied-second-charge','loop')
        elif case=='RSIV-13':
            library=LibraryService(self.store);actor=Principal('security-validation-ungranted')
            inputs=dict(method=method,name=session['parent']['cc_name'],version=session['parent']['cc_version'],to_standing='active',
                reason='Controlled authorization refusal',effect_scope='live_plans',
                actor=dict(account_id=actor.account_id,workspace_ids=[],operations=[],audiences=[]))
            action=lambda:library.set_standing(inputs['name'],inputs['version'],'active',actor,reason=inputs['reason'],effect_scope='live_plans')
        else:raise ValueError('Unsupported finite policy method')
        def snapshot():
            state=None
            if ledger is not None:
                value=ledger.state(session['session_id'])
                state={key:value[key] for key in ('used','cap','lifetime','lifetime_cap','final_sealed','halted')}
                state['actions']=[]
                for row in ledger.db.execute('SELECT id,kind,state,fingerprint,result FROM actions WHERE session=? ORDER BY id',(session['session_id'],)):
                    item=dict(row);result=item.pop('result')
                    item['result_sha256']=hashlib.sha256(result.encode()).hexdigest() if result is not None else None
                    state['actions'].append(item)
            library_state=None
            if library is not None:
                standings=[]
                for row in library.entries():
                    pin=row['declaration_ref']
                    standings.append({'declaration_ref':json.loads(pin) if isinstance(pin,str) else pin,'standing':row['standing']})
                library_state=dict(admissions=[entry['ref'] for entry in self.store.iter_records(kinds={'library-admission'})],
                    standings=standings,activations=[entry['ref'] for entry in self.store.iter_records(kinds={'activation-record'})],qualification_ref=None)
            return self._state(ledger=state,library=library_state)
        before=snapshot();error=None
        try:
            try:
                value=action()
                if asyncio.iscoroutine(value):await value
            except (ValueError,ResearchError) as caught:error=caught
            if error is None:raise ValueError('Prohibited policy action was accepted')
            if case=='RSIV-6':inputs=dict(method=method,prompt_ref=proposer.last_prompt_ref,response_ref=proposer.last_response_ref)
            input_ref=self._input(inputs);after=snapshot()
            denial=self._record('rsi-policy-denial',dict(schema='ai4r-rsi-policy-denial:1',method=method,input_ref=input_ref,
                before_ref=before,after_ref=after,exception_type=type(error).__name__,exception_code=getattr(error,'code',None)))
            # Public exception families are stable; a concrete ContractError is
            # a ResearchError, never a string-based admission verdict.
            if isinstance(error,ResearchError) and type(error).__name__!='ResearchError':
                raise ValueError('Unexpected boundary exception family')
            return self._record('rsi-security-case-observation',dict(schema='ai4r-rsi-security-case-observation:1',case_id=case,
                session_ref=session_ref,worker_profile_ref=profile_ref,attack_id=claim['attack_id'],attack_source_ref=source_ref,
                attack_source_sha256=source_ref['sha256'],mode='policy',input_ref=input_ref,before_ref=before,after_ref=after,
                denial_ref=denial,execution_ref=None,probe_ref=None,stdout_ref=None,stderr_ref=None,containment_ref=None,attempt_ref=None))
        finally:
            if ledger is not None:ledger.close()
