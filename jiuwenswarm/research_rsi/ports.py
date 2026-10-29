"""Finite private Unix ports for approved jobs and separated custodian operations."""
import asyncio
import json
import os
from pathlib import Path
import socket
import stat
import struct
import base64
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
        self._authorize(ref)
        task=self.active.get(ref['id'])
        if task and not task.done():return {'state':'running'}
        return self.store.job_state(ref)
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
        records=[]
        for kind,pin in refs:
            raw=self.public_reader(pin)
            if not isinstance(raw,bytes) or __import__('hashlib').sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('public workbench evidence bytes unavailable')
            records.append({'kind':kind,'ref':pin,'bytes_base64':base64.b64encode(raw).decode('ascii')})
        missing=[];seen={encoded(r['ref']) for r in records}
        for attempt_ref in result['attempt_refs']:
            attempt=json.loads(self.public_reader(attempt_ref))
            for pin in attempt.get('observation_refs',[]):
                if encoded(pin) in seen:continue
                # Type comes from the protected host capture index, never from
                # a worker-authored payload which merely resembles a call.
                entry=self.trace_reader(pin) if self.trace_reader else None
                if entry is None or entry.get('kind') not in {'model-call','route-record','invocation-observation'}:
                    missing.append(pin);continue
                raw=entry['bytes']
                if not isinstance(raw,bytes) or __import__('hashlib').sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('protected trace bytes mismatch')
                records.append({'kind':entry['kind'],'ref':pin,'bytes_base64':base64.b64encode(raw).decode('ascii')});seen.add(encoded(pin))
                if entry['kind']=='model-call':
                    for nested in json.loads(raw)['evidence_refs']:
                        owned=self.trace_reader(nested)
                        if owned is None:raise ValueError('Required exact call evidence is unavailable')
                        queue=[(nested,owned)]
                        while queue:
                            ref,value=queue.pop(0)
                            if encoded(ref) in seen:continue
                            if value['kind'] not in {'model-call-input','model-call-output','model-provider-observation','native-governed-trace','native-governed-trace-event','native-governed-packet'}:
                                raise ValueError('Private or unknown call evidence')
                            if __import__('hashlib').sha256(value['bytes']).hexdigest()!=ref['sha256']:raise ValueError('Call evidence digest differs')
                            records.append({'kind':value['kind'],'ref':ref,'bytes_base64':base64.b64encode(value['bytes']).decode('ascii')});seen.add(encoded(ref))
                            children=[]
                            if value['kind']=='native-governed-trace':children=json.loads(value['bytes'])['event_refs']
                            elif value['kind']=='native-governed-trace-event':children=[json.loads(value['bytes'])['raw_ref']]
                            for child in children:
                                captured=self.trace_reader(child)
                                if captured is None:raise ValueError('Exact owned trace packet is unavailable')
                                queue.append((child,captured))

        return {**state,'records':records,'unavailable_trace_refs':missing}
    def handlers(self):return {'session_start':self.start,'session_inspect':self.inspect,'session_stop':self.stop,'session_export':self.export}
