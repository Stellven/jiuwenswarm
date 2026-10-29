"""Finite private Unix ports for approved jobs and separated custodian operations."""
import asyncio
import json
import os
from pathlib import Path
import socket
import stat
import struct
import base64
import hashlib
from .records import encoded


PROTOCOL='ai4r-rsi-ipc:1'
MAX_FRAME=4*1024*1024


def peer_uid(sock):
    if not hasattr(socket,'SO_PEERCRED'):raise PermissionError('Linux peer credentials required')
    return struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]


async def request(path,peer,operation,ref,*,timeout=30):
    info=os.stat(path,follow_symlinks=False)
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=peer or stat.S_IMODE(info.st_mode) not in {0o600,0o660}:raise PermissionError('untrusted RSI socket')
    async def exchange():
        reader,writer=await asyncio.open_unix_connection(path)
        try:
            if peer_uid(writer.get_extra_info('socket'))!=peer:raise PermissionError('untrusted RSI process')
            raw=encoded({'protocol':PROTOCOL,'operation':operation,'ref':ref})
            if len(raw)>MAX_FRAME:raise ValueError('RSI frame limit')
            writer.write(struct.pack('!I',len(raw))+raw);await writer.drain()
            size=struct.unpack('!I',await reader.readexactly(4))[0]
            if not 0<size<=MAX_FRAME:raise ValueError('RSI frame limit')
            value=json.loads(await reader.readexactly(size))
            if value.get('protocol')!=PROTOCOL or value.get('status') not in {'ok','blocked','error'}:raise ValueError('invalid RSI reply')
            return value
        finally:writer.close();await writer.wait_closed()
    return await asyncio.wait_for(exchange(),timeout)


class PrivatePort:
    def __init__(self,handlers,allowed_uids):
        self.handlers=dict(handlers);self.allowed_uids=frozenset(allowed_uids)
        if not self.allowed_uids:raise ValueError('empty RSI UID authority')
    async def handle(self,reader,writer):
        try:
            if peer_uid(writer.get_extra_info('socket')) not in self.allowed_uids:return
            size=struct.unpack('!I',await asyncio.wait_for(reader.readexactly(4),30))[0]
            if not 0<size<=MAX_FRAME:return
            body=json.loads(await asyncio.wait_for(reader.readexactly(size),30))
            if set(body)!={'protocol','operation','ref'} or body['protocol']!=PROTOCOL or body['operation'] not in self.handlers:return
            result=await self.handlers[body['operation']](body['ref'])
            reply=encoded({'protocol':PROTOCOL,'status':'ok','result':result})
            if len(reply)>MAX_FRAME:raise ValueError('oversized RSI reply')
        except Exception:
            reply=encoded({'protocol':PROTOCOL,'status':'blocked','reason':'Protected job operation unavailable; inspect custody evidence.'})
        finally:
            if 'reply' in locals():
                writer.write(struct.pack('!I',len(reply))+reply)
                try:await writer.drain()
                except (ConnectionError,OSError):pass
            writer.close()
            try:await writer.wait_closed()
            except (ConnectionError,OSError):pass
    async def serve(self,path):
        p=Path(path)
        if p.exists() or p.is_symlink():raise ValueError('RSI socket path already exists')
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o750)
        server=await asyncio.start_unix_server(self.handle,path=p);p.chmod(0o660);inode=p.stat().st_ino
        try:
            async with server:await server.serve_forever()
        finally:
            if p.exists() and p.stat().st_ino==inode:p.unlink()


class JobPort:
    """Only preapproved job identity operations; no direct final oracle operation."""
    def __init__(self,jobs,store,*,allowed_refs=(),public_reader=None,trace_reader=None):
        self.jobs,self.store=jobs,store;self.active={};self.results={}
        self.allowed_refs=frozenset(encoded(ref) for ref in allowed_refs)
        self.public_reader=public_reader or store.read
        self.trace_reader=trace_reader
    def _authorize(self,ref):
        if encoded(ref) not in self.allowed_refs:raise PermissionError('job reference outside launcher grant')
        return self.jobs.resolve(ref)
    async def readiness(self,ref):
        job=self._authorize(ref)
        task=self.active.get(ref['id'])
        if task is not None and not task.done():raise ValueError('Running job cannot become a fresh session')
        owner=getattr(getattr(self.jobs,'factory',None),'readiness',None)
        if not callable(owner):raise ValueError('Installed current runtime inspection unavailable')
        result=await owner(job,job_ref=ref)
        from .runtime_readiness import validate_report
        validate_report(result)
        if result['session_ref']!=job['session_ref']:raise ValueError('Runtime inspection changed the approved session')
        return result
    def _public(self,pin):
        from .worker import ref as validate_ref
        validate_ref(pin)
        raw=self.public_reader(pin)
        if not isinstance(raw,bytes) or len(raw)>MAX_FRAME or hashlib.sha256(raw).hexdigest()!=pin['sha256']:
            raise ValueError('Exact public workbench evidence bytes unavailable')
        return raw
    def _opportunity(self,job):
        # Only durable typed indexes nominate the canonical decision/capture.
        # Never probe generic evidence_refs, preparations or store directories.
        session_ref=job.get('session_ref')
        if session_ref is None:return None
        indexed=self.store.opportunity_for_session_ref(session_ref)
        if indexed is None:return None
        # Historical phase inspection does not require original session bytes
        # merely to prove that no canonical opportunity was ever indexed.
        session=json.loads(self._public(session_ref));sid=indexed['session_id']
        if session['session_id']!=sid:raise ValueError('Indexed opportunity session differs')
        opportunity_ref=self.store.opportunity_ref(sid,session_ref)
        if opportunity_ref!=indexed['ref']:raise ValueError('Opportunity index changed during inspection')
        from .session_policy import _contracts
        opportunity=json.loads(self._public(opportunity_ref));_contracts().validate('rsi-opportunity',opportunity)
        if opportunity['target_profile_ref']!=session['target_profile_ref'] or opportunity['parent']!=session['parent']:
            raise ValueError('Indexed opportunity differs from the exact session')
        capture_ref=self.store.opportunity_capture_ref(sid,session_ref)
        if capture_ref!=indexed['diagnosis_capture_ref']:raise ValueError('Diagnosis index changed during inspection')
        capture=None
        if capture_ref is not None:
            capture=json.loads(self._public(capture_ref))
            _contracts().validate('urn:ai4r:private:rsi-diagnosis-capture:1',capture)
            if (capture_ref not in opportunity['evidence_refs'] or capture['target_profile_ref']!=session['target_profile_ref']
                    or capture['parent']!=session['parent'] or capture['configuration_ref']!=session['configuration_ref']
                    or capture['diagnosis_ref']!=opportunity['diagnosis_ref']):
                raise ValueError('Indexed diagnosis capture differs from the exact opportunity/session')
        return dict(record=opportunity,ref=opportunity_ref,capture=capture,capture_ref=capture_ref)
    @staticmethod
    def _append_export(records,seen,kind,pin,raw):
        from .worker import ref as validate_ref
        validate_ref(pin)
        if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=pin['sha256']:
            raise ValueError('Exact exported evidence bytes differ')
        identity=encoded(pin)
        if identity in seen and any(row['kind']==kind and row['ref']==pin for row in records):return
        row={'kind':kind,'ref':pin,'bytes_base64':base64.b64encode(raw).decode('ascii')}
        # Keep work and response finite even before the port frame guard. Do
        # not truncate required captures into a misleading complete export.
        if len(records)>=512 or sum(len(encoded(item)) for item in records)+len(encoded(row))>MAX_FRAME-65536:
            raise ValueError('Bounded workbench evidence export exceeds the private frame')
        records.append(row);seen.add(identity)
    def _export_traces(self,pins,records,seen,missing):
        for pin in pins:
            # The protected host type index supplies these kinds. A JSON
            # payload resembling a model call cannot nominate its own type.
            entry=self.trace_reader(pin) if self.trace_reader else None
            if entry is None or entry.get('kind') not in {'model-call','route-record','invocation-observation'}:
                missing.append(pin);continue
            if encoded(pin) in seen and any(row['kind']==entry['kind'] and row['ref']==pin for row in records):continue
            raw=entry['bytes'];self._append_export(records,seen,entry['kind'],pin,raw)
            if entry['kind']!='model-call':continue
            for nested in json.loads(raw)['evidence_refs']:
                owned=self.trace_reader(nested)
                if owned is None:raise ValueError('Required exact call evidence is unavailable')
                queue=[(nested,owned)]
                while queue:
                    nested_ref,value=queue.pop(0)
                    if encoded(nested_ref) in seen and any(row['kind']==value['kind'] and row['ref']==nested_ref for row in records):continue
                    if value['kind'] not in {'model-call-input','model-call-output','model-provider-observation','native-governed-trace','native-governed-trace-event','native-governed-packet'}:
                        raise ValueError('Private or unknown call evidence')
                    self._append_export(records,seen,value['kind'],nested_ref,value['bytes'])
                    children=[]
                    if value['kind']=='native-governed-trace':children=json.loads(value['bytes'])['event_refs']
                    elif value['kind']=='native-governed-trace-event':children=[json.loads(value['bytes'])['raw_ref']]
                    for child in children:
                        captured=self.trace_reader(child)
                        if captured is None:raise ValueError('Exact owned trace packet is unavailable')
                        queue.append((child,captured))
    async def start(self,ref):
        self._authorize(ref);ident=ref['id']
        if ident in self.active or not self.store.claim_job(ref):return await self.inspect(ref)
        async def execute():
            try:
                result=await self.jobs.start(ref);self.results[ident]={'state':'terminal','result':result}
            except BaseException as exc:
                from .native_lease import ProfileInUse
                from .qualification import QualificationUnavailable
                retained=self.store.retained_job_terminal(ref)
                unknown={'state':'outcome_unknown','reason':'Protected execution interrupted; retain actual starts/receipts; no automatic replay.'}
                if retained:self.results[ident]=retained
                elif self.store.job_history_started(ref):self.results[ident]=unknown
                elif isinstance(exc,ProfileInUse):self.results[ident]={'state':'blocked','reason':'PROFILE_IN_USE: prior native model effect has no exact containment proof; session start was refused.'}
                elif isinstance(exc,QualificationUnavailable):self.results[ident]={'state':'blocked','reason':'RSI_SECURITY_QUALIFICATION_UNAVAILABLE: protected execution cannot proceed; retain actual starts/receipts and do not replay.'}
                else:self.results[ident]=unknown
            if self.results[ident]['state']=='outcome_unknown':
                # Preserve diagnostics without freezing an absent terminal into
                # the job index. Restart can close the same tracked history.
                self.store.put({'record_kind':'rsi-job-interruption:1','job_ref':ref,**self.results[ident]})
                return
            self.store.finish_job(ref,self.results[ident])
        # A durable start receipt precedes task scheduling.
        self.store.put({'job_ref':ref,'state':'started','operation':'session_start'})
        self.active[ident]=asyncio.create_task(execute());return {'state':'started'}
    async def inspect(self,ref):
        job=self._authorize(ref)
        task=self.active.get(ref['id'])
        state={'state':'running'} if task and not task.done() else self.store.job_state(ref)
        current=self.store.job_phase(ref)
        if current is not None:
            record=current['record']
            state={**state,'progress':{key:record[key] for key in ('phase','revision','incumbent_ref','attempts_used','queries_used')}}
        if job.get('session_ref') is not None:
            opportunity=self._opportunity(job)
            if opportunity is None:state={**state,'opportunity':{'status':'unavailable'}}
            else:
                capture=opportunity['capture']
                state={**state,'opportunity':{'status':'captured','opportunity_ref':opportunity['ref'],
                    'decision':opportunity['record']['decision'],'diagnosis_ref':opportunity['record']['diagnosis_ref'],
                    'diagnosis_capture_ref':opportunity['capture_ref'],
                    'diagnosis_status':capture['status'] if capture is not None else 'unavailable'}}
        return state
    async def stop(self,ref):
        self._authorize(ref);task=self.active.get(ref['id'])
        if task and not task.done():
            task.cancel()
            try:await asyncio.wait_for(asyncio.shield(task),30)
            except asyncio.TimeoutError:return {'state':'outcome_unknown','reason':'Cancellation containment has not completed; no successful stop acknowledgement'}
        state=await self.inspect(ref)
        if state.get('state')=='terminal' and self.store.job_containment_uncertain(ref):
            return {'state':'outcome_unknown','reason':'Original terminal history is retained for inspect/export; actual containment remains uncertain and no successful stop is acknowledged'}
        return state
    async def export(self,ref):
        state=await self.inspect(ref)
        if state.get('state')!='terminal':return state
        result,result_ref=state['result']
        if self.store.get(result_ref)!=result:raise ValueError('terminal job result differs from exact stored bytes')
        # This finite explicit closure never follows arbitrary evidence refs,
        # target profiles or fixture directories. A trusted bootstrap reader can
        # resolve the independent custodian's already-public aggregate record.
        refs=[('rsi-session-result',result_ref),('rsi-session',result['session_ref']),
            *[('rsi-attempt',r) for r in result['attempt_refs']]]
        if result['referee_evidence_ref']:refs.append(('rsi-referee-evidence',result['referee_evidence_ref']))
        records=[];seen=set()
        for kind,pin in refs:
            self._append_export(records,seen,kind,pin,self._public(pin))
        missing=[];unavailable=[]
        opportunity=self._opportunity(self._authorize(ref))
        if opportunity is None:unavailable.append('canonical_opportunity')
        else:
            self._append_export(records,seen,'rsi-opportunity',opportunity['ref'],self._public(opportunity['ref']))
            diagnosis_ref=opportunity['record']['diagnosis_ref']
            if diagnosis_ref is not None:
                from .session_policy import _contracts
                raw=self._public(diagnosis_ref)
                if len(raw)>64*1024:raise ValueError('Diagnosis evidence exceeds its fixed disclosure bound')
                _contracts().validate('urn:ai4r:private:rsi-diagnosis:1',json.loads(raw))
                self._append_export(records,seen,'rsi-diagnosis',diagnosis_ref,raw)
            capture=opportunity['capture']
            if capture is None:unavailable.append('diagnosis_capture')
            else:
                self._append_export(records,seen,'rsi-diagnosis-capture',opportunity['capture_ref'],self._public(opportunity['capture_ref']))
                for field,kind,maximum in (('prompt_ref','rsi-diagnosis-prompt',256*1024),
                        ('response_ref','rsi-diagnosis-response',64*1024),('diagnosis_ref','rsi-diagnosis',64*1024)):
                    pin=capture[field]
                    if pin is None:continue
                    raw=self._public(pin)
                    if len(raw)>maximum:raise ValueError('Diagnosis evidence exceeds its fixed disclosure bound')
                    if field=='diagnosis_ref':
                        from .session_policy import _contracts
                        _contracts().validate('urn:ai4r:private:rsi-diagnosis:1',json.loads(raw))
                    self._append_export(records,seen,kind,pin,raw)
                self._export_traces(capture['generation_evidence_refs'],records,seen,missing)
        for attempt_ref in result['attempt_refs']:
            attempt=json.loads(self._public(attempt_ref))
            self._export_traces(attempt.get('observation_refs',[]),records,seen,missing)
        return {**state,'records':records,'unavailable_trace_refs':missing,'unavailable_opportunity_evidence':unavailable}
    def handlers(self):return {'session_start':self.start,'session_inspect':self.inspect,'session_stop':self.stop,'session_export':self.export,'session_readiness':self.readiness}
