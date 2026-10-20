"""Fixed pure-helper broker. Candidate Python runs only in RestrictedExecutor.

The root broker has no fixture/key mounts. Its two ports have different peer
UIDs, capabilities and input stores; hidden-input results return only to the
custodian. Requests contain exact refs, never commands, paths or import names.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import uuid
from .records import RecordStore,encoded

PROTOCOL='ai4r-rsi-worker:1'
DENIED_PATHS=('/var/lib/ai4r','/var/lib/ai4r-accounts','/run/ai4r','/var/run/docker.sock',
    '/hidden-fixtures','/var/lib/ai4r-rsi/custodian','/run/ai4r-rsi/custodian-service.json',
    '/var/lib/ai4r-rsi/accounts','/var/lib/ai4r-rsi/controller','/var/lib/ai4r-rsi-inputs/hidden',
    '/run/ai4r-rsi-worker/hidden','/run/ai4r-rsi/jobs-service.json')

# This installed program is mounted read-only by the broker. runpy executes
# candidate code inside the worker namespace, never in either authority owner.
WORKER_PROGRAM=b'''import json,runpy,sys\nmodule=runpy.run_path('/resources/body.py')\nvalue=json.load(open('/resources/input.json'))\nresult=module['rank_opportunities'](value['scores'])\nsys.stdout.write(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))\n'''


def timing_program(iterations):
    if type(iterations) is not int or iterations<=0:raise ValueError('Frozen positive batch iteration count required')
    # Host receipt wall time measures the whole identical batch externally.
    # No child-authored clock or reported duration is trusted by the referee.
    return ("import json,runpy,sys\nmodule=runpy.run_path('/resources/body.py')\n"
        "value=json.load(open('/resources/input.json'))\n"
        f"for _ in range({iterations}):\n result=module['rank_opportunities'](value['scores'])\n"
        "sys.stdout.write(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))\n").encode()


def ref(value):
    if not isinstance(value,dict) or set(value)!={'id','sha256'} or not isinstance(value['id'],str) or not value['id'] or not isinstance(value['sha256'],str) or len(value['sha256'])!=64 or any(c not in '0123456789abcdef' for c in value['sha256']):raise ValueError('Exact Ref required')


def validate_request(value):
    if not isinstance(value,dict) or set(value)!={'profile_ref','session_ref','candidate_ref','input_ref','reservation_ref','phase','repeat_index'}:raise ValueError('Unknown worker request field')
    for name in ('profile_ref','session_ref','candidate_ref','input_ref','reservation_ref'):ref(value[name])
    if value['phase'] not in {'development','platform','hidden_loop','hidden_final'} or type(value['repeat_index']) is not int or not 0<=value['repeat_index']<=2:raise ValueError('Unknown worker phase/repetition')
    return value


def validate_profile(value):
    fields={'schema','target_kind','session_ref','target_ref','parent_ref','contract_ref','environment_ref','hardware_ref','memory_mb','pids_max','timeout_s'}
    if not isinstance(value,dict) or set(value)!=fields or value['schema']!='ai4r-rsi-worker-profile:1' or value['target_kind']!='ranking-v1':raise ValueError('Unknown finite worker profile')
    for name in ('session_ref','target_ref','parent_ref','contract_ref','environment_ref','hardware_ref'):ref(value[name])
    if type(value['memory_mb']) is not int or not 0<value['memory_mb']<=65536 or type(value['pids_max']) is not int or not 0<value['pids_max']<=256 or type(value['timeout_s']) not in (int,float) or not math.isfinite(value['timeout_s']) or not 0<value['timeout_s']<=300:raise ValueError('Worker limits widened')
    return value


class PublicBytes:
    """Exact immutable record reader; no shared writable SQLite connection."""
    def __init__(self,roots):self.roots=tuple(Path(p).resolve(strict=True) for p in roots)
    def read(self,pin):
        ref(pin)
        for root in self.roots:
            if (root/'original-byte-index.json').exists():
                from jiuwenswarm.research_records.original_bytes import OriginalBytes
                publication=OriginalBytes(root)
                if pin['id'] not in publication.index():continue
                return publication.read(pin)
            if pin['id']!=pin['sha256']+'.json':continue
            path=root/pin['id']
            if not path.exists():continue
            meta=path.lstat()
            if not stat.S_ISREG(meta.st_mode) or path.is_symlink() or meta.st_nlink!=1 or meta.st_size>4*1024*1024:raise ValueError('Unsafe public bytes')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=pin['sha256']:raise ValueError('Public bytes changed')
            return data
        raise ValueError('Exact public bytes absent')
    def get(self,pin):return json.loads(self.read(pin))


class WorkerClient:
    def __init__(self,*,socket_path,session_id,capability,requests,profile_ref,session_ref,hidden=False):
        from jiuwenswarm.research.private_rpc import PrivateRPCClient
        self.rpc=PrivateRPCClient(socket_path,protocol=PROTOCOL,session_id=session_id,capability=capability,peer_uid=0,socket_mode=0o660)
        self.requests,self.profile_ref,self.session_ref,self.hidden=requests,profile_ref,session_ref,hidden
    async def run(self,candidate_ref,inputs,*,phase,reservation_ref,repeat_index=0,timing=False):
        if phase not in ({'hidden_loop','hidden_final','platform'} if self.hidden else {'development'}):raise ValueError('Worker phase is outside the caller role')
        pin=self.requests.put(inputs)
        value=dict(profile_ref=self.profile_ref,session_ref=self.session_ref,candidate_ref=candidate_ref,input_ref=pin,
            reservation_ref=reservation_ref,phase=phase,repeat_index=repeat_index)
        if timing and (not self.hidden or phase not in {'hidden_final','platform'}):raise ValueError('Timing batches are custodian final-only')
        try:response=await self.rpc.call('run_timing_batch' if timing else 'run_helper',validate_request(value),timeout_s=300)
        except asyncio.CancelledError:
            await asyncio.shield(self.rpc.call('cancel_session',{'session_ref':self.session_ref},timeout_s=30))
            raise
        # Keep original raw protected captures with independently verified hashes.
        for item in response.get('captures',[]):
            raw=base64.b64decode(item['bytes_base64'],validate=True)
            if hashlib.sha256(raw).hexdigest()!=item['ref']['sha256']:raise ValueError('Worker capture transfer changed')
            captured=self.requests.put_bytes(raw)
            if captured!=item['ref']:raise ValueError('Worker capture identity differs')
        return response
    async def prerequisites(self):return await self.rpc.call('prerequisites',{},timeout_s=30)
    async def cancel(self):
        value=await self.rpc.call('cancel_session',{'session_ref':self.session_ref},timeout_s=30)
        if value!={'contained':True,'session_ref':self.session_ref}:raise ValueError('Worker session containment is not established')
        return value


class WorkerBroker:
    def __init__(self,*,root,cgroup_root,profiles,public_reader,input_reader,capture_store,hidden,qualification=None):
        from jiuwenswarm.research.executor import RestrictedExecutor
        self.qualification=qualification
        self.root=Path(root);self.root.mkdir(mode=0o711,parents=True,exist_ok=True)
        self.profiles={encoded(pin):validate_profile(public_reader.get(pin)) for pin in profiles}
        self.public,self.inputs,self.capture,self.hidden=public_reader,input_reader,capture_store,hidden
        self.issued={};self.claims=set();self.lock=asyncio.Lock();self.tasks={};self.job_sessions={};self.cancelled=set()
        owner=self
        class RSIExecutor(RestrictedExecutor):
            def _sandbox(self,job):
                command=super()._sandbox(job)
                # Extend the existing observed kernel probe, without changing
                # the core executor or its main application policy.
                index=command.index('/executor-probe.py',command.index('--'))+1
                expected=json.loads(command[index]);expected['denied_paths']=list(DENIED_PATHS)
                command[index]=json.dumps(expected,separators=(',',':'))
                return command
        def authorize(job):
            if owner.issued.get(job.job_id)!=job or owner.job_sessions.get(job.job_id) in owner.cancelled:raise ValueError('Unissued or cancelled worker job')
            return job
        def verify_mount(mount):
            if hashlib.sha256(mount.source.read_bytes()).hexdigest()!=mount.ref['sha256']:raise ValueError('Worker asset changed')
        self.executor=RSIExecutor(workspace_root=self.root/'work',cgroup_root=cgroup_root,authorize_job=authorize,
            capture=lambda data,**_:capture_store.put_bytes(data),executor_uid=12003,executor_gid=12003,
            allowed_asset_roots=[self.root/'assets'],verify_mount=verify_mount)
        for name in ('work','assets'):(self.root/name).mkdir(mode=0o711,exist_ok=True)
    async def run(self,value,*,timing=False):
        from jiuwenswarm.research.executor import ExecutionJob,ReadonlyMount
        validate_request(value)
        profile=self.profiles.get(encoded(value['profile_ref']))
        if profile is None or profile['session_ref']!=value['session_ref'] or value['phase'] not in ({'hidden_loop','hidden_final','platform'} if self.hidden else {'development'}):raise ValueError('Unapproved worker scope')
        session_key=encoded(value['session_ref']);cancel_path=self.root/('cancelled-'+hashlib.sha256(session_key).hexdigest())
        if session_key in self.cancelled or cancel_path.exists():raise ValueError('Session is permanently cancelled')
        # Custodian/controller charge or authorize the exact operation before
        # issuing this immutable reservation. It contains no hidden labels.
        reservation=self.inputs.get(value['reservation_ref'])
        if any(reservation.get(k)!=value[k] for k in ('session_ref','candidate_ref','phase')):raise ValueError('Worker reservation differs')
        from .qualification import require_qualification
        require_qualification(getattr(self,'qualification',None),'trial',session_ref=value['session_ref'],
                              worker_profile_ref=value['profile_ref'],candidate_ref=value['candidate_ref'])
        program=WORKER_PROGRAM
        if timing:
            if not self.hidden or value['phase'] not in {'hidden_final','platform'} or not str(reservation.get('operation','')).startswith('timing:'):
                raise ValueError('Timing batch is outside custodian final reservation')
            target=self.public.get(profile['target_ref'])
            program=timing_program(target['scoring']['batch_iterations'])
        claim=(encoded(value['reservation_ref']),value['repeat_index'],encoded(value['input_ref']))
        async with self.lock:
            if claim in self.claims:raise ValueError('Worker operation already issued; reconcile without replay')
            self.claims.add(claim)
        # Durable receipt precedes spawning. A restarted broker also refuses it.
        claim_id=hashlib.sha256(encoded([value['reservation_ref'],value['repeat_index'],value['input_ref']])).hexdigest()
        claim_path=self.root/('claim-'+claim_id)
        with claim_path.open('xb') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        raw=self.public.read(value['candidate_ref']);inputs=self.inputs.read(value['input_ref'])
        data=json.loads(inputs)
        if not isinstance(data,dict) or set(data)!={'scores'} or not isinstance(data['scores'],list):raise ValueError('Unknown legitimate helper input')
        ident='rsi-'+uuid.uuid4().hex;assets=self.root/'assets'/ident;assets.mkdir(mode=0o755)
        mounts=[]
        for name,body in [('worker.py',program),('body.py',raw),('input.json',inputs)]:
            path=assets/name;path.write_bytes(body);path.chmod(0o444)
            mounts.append(ReadonlyMount(path,'/resources/'+name,{'id':name,'sha256':hashlib.sha256(body).hexdigest()}))
        parent=self.root/'work'/ident;parent.mkdir(mode=0o711);work=parent/'work';work.mkdir(mode=0o700);os.chown(work,12003,12003)
        job=ExecutionJob(job_id=ident,invocation_id=claim_id,contract_ref=profile['contract_ref'],run_id=value['session_ref']['id'],
            node_id='isolated-helper',attempt_id=value['reservation_ref']['id'],sequence=1,role='treatment',repeat_index=value['repeat_index'],seed=0,
            argv=('/usr/local/bin/python3','-I','/resources/worker.py'),cwd=work,timeout_s=profile['timeout_s'],memory_mb=profile['memory_mb'],pids_max=profile['pids_max'],
            baseline_ref=profile['parent_ref'],validation_ref=profile['target_ref'],environment_ref=profile['environment_ref'],subject_ref=value['candidate_ref'],
            hardware_ref=profile['hardware_ref'],readonly_mounts=tuple(mounts))
        self.issued[ident]=job;self.job_sessions[ident]=session_key;self.tasks[ident]=asyncio.current_task()
        try:receipt=await self.executor.run(job)
        finally:self.tasks.pop(ident,None)
        self.capture.put({'schema':'ai4r-rsi-worker-receipt:1','request':value,'receipt':receipt})
        captures=[]
        for pin in [receipt['stdout_ref'],receipt['stderr_ref'],receipt['observed_limits']['isolation_probe_ref']]:
            captures.append({'ref':pin,'bytes_base64':base64.b64encode(self.capture.read(pin)).decode('ascii')})
        return {'receipt':receipt,'captures':captures}
    async def cancel(self,value):
        if not isinstance(value,dict) or set(value)!={'session_ref'}:raise ValueError('Unknown containment field')
        ref(value['session_ref']);key=encoded(value['session_ref'])
        if not any(profile['session_ref']==value['session_ref'] for profile in self.profiles.values()):raise ValueError('Containment session is outside the grant')
        self.cancelled.add(key)
        path=self.root/('cancelled-'+hashlib.sha256(key).hexdigest())
        try:
            with path.open('xb') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes()!=encoded(value):raise ValueError('Containment identity changed')
        tasks=[task for ident,task in self.tasks.items() if self.job_sessions.get(ident)==key]
        for task in tasks:task.cancel()
        if tasks:await asyncio.wait_for(asyncio.gather(*tasks,return_exceptions=True),30)
        if any(self.job_sessions.get(ident)==key for ident in self.executor.active):raise ValueError('Worker process tree containment is not established')
        return {'contained':True,'session_ref':value['session_ref']}
