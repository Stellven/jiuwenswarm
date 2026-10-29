"""Finite protected job registry. No caller supplied module, graph or hidden path."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from .records import encoded


class RuntimeJobs:
    def __init__(self,approved_root,controller_factory,*,record_store=None):
        self.root=Path(approved_root).resolve(strict=True);self.factory=controller_factory;self.records=record_store
    def resolve(self,ref):
        if set(ref)!={'id','sha256'} or not ref['id'].startswith('job_') or any(x not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for x in ref['id']):raise ValueError('invalid approved job identity')
        path=self.root/(ref['id']+'.json')
        if path.is_symlink() or not path.is_file() or path.stat().st_size>4*1024*1024 or os.name!='nt' and path.stat().st_mode&0o022:raise ValueError('runtime job is not protected')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('runtime job bytes changed')
        return json.loads(raw)
    async def start(self,ref):
        job=self.resolve(ref);prior_sessions=[]
        if self.records is not None:
            # A different job cannot revive the same original session, including
            # legacy zero-query histories. Unresolvable older jobs remain a
            # limitation, not evidence that their terminal/session is absent.
            for prior in self.records.job_refs():
                if prior==ref:continue
                pin=self.resolve(prior)['session_ref'];prior_sessions.append(pin)
                if pin==job['session_ref']:raise ValueError('Session was already claimed by another exact job; no automatic replay')
            self.records.bind_job_session(ref,job['session_ref'])
        controller,arguments=await self.factory(job)
        if arguments.get('session_ref')!=job['session_ref'] or controller.store.get(job['session_ref'])!=arguments['session']:raise ValueError('Factory session differs from the exact approved job')
        for pin in prior_sessions:
            if controller.store.get(pin)['session_id']==arguments['session']['session_id']:raise ValueError('Original session identity cannot be reused with changed bytes')
        # Factory is configured by the trusted host, never selected/imported by
        # a client job. It binds existing core bridge and isolated eval target.
        result=await controller.run(**arguments)
        # A signed terminal can coexist with uncertain containment. Preserve
        # that original history; it is neither a pre-effect refusal nor a stop
        # acknowledgement. The protected lease continues to block new effects.
        return result
    async def recover(self,ref):
        job=self.resolve(ref)
        if self.records is not None and self.records.job_session(ref)!=job['session_ref']:raise ValueError('Original job/session tracking is absent or differs; no historical replacement/replay')
        if self.records is not None:
            from jiuwenswarm.research.contracts import validate
            retained=self.records.restore_job_terminal(ref,validate=validate)
            if retained is not None:return retained['result']
        controller,arguments=await self.factory(job,recovery=True)
        if arguments.get('session_ref')!=job['session_ref'] or controller.store.get(job['session_ref'])!=arguments['session']:raise ValueError('Recovery factory session differs from the exact approved job')
        return await controller.recover_terminal(arguments['session'],parent_body_ref=arguments['parent_body_ref'],session_ref=arguments.get('session_ref'))
