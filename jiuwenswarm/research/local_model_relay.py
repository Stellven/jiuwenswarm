"""Explicitly started, authenticated private model relay with durable effect claims."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import secrets
import shlex
import signal
import sqlite3
import stat
import subprocess

from contextlib import contextmanager
from time import monotonic
from pathlib import Path

from .contracts.types import ResearchError
from .private_rpc import PrivateRPCServer

PROTOCOL = 'ai4r-local-model:1'
REQUEST_KEYS = {'request_id', 'endpoint_id', 'binding_sha256', 'model', 'prompt', 'timeout_s'}
RESULT_KEYS = {'outcome', 'http_status', 'response_text', 'provider_request_id'}
MAX_BACKEND_RECEIPT_BYTES = 4 * 1024 * 1024
MAX_BACKEND_STDERR_BYTES = 256 * 1024



def exception_category(error):
    """Closed categories only: exception messages and arbitrary class names may contain secrets."""
    for kind in (BrokenPipeError, ConnectionResetError, FileNotFoundError, PermissionError,
                 TimeoutError, OSError, UnicodeError, ValueError, TypeError, KeyError, ResearchError):
        if isinstance(error, kind):return kind.__name__
    return 'other'


class BackendStageFailure(Exception):
    def __init__(self,stage,error):
        allowed={'helper_source','helper_spawn','helper_stdin','helper_stdout','helper_stderr',
                 'helper_output_bound','helper_exit','helper_decode'}
        self.diagnostic={'stage':stage if stage in allowed else 'backend_error',
                         'exception_class':exception_category(error)}
        super().__init__('BACKEND_STAGE_FAILED')


@contextmanager
def backend_stage(stage):
    try:yield
    except BackendStageFailure:raise
    except Exception as error:raise BackendStageFailure(stage,error) from error


class CapturedBackendReceipt(dict):
    """Internal only: original stdout never becomes another RPC envelope field."""
    def __init__(self,value,raw,transport_error=None,*,stderr=b'',observation=None):
        super().__init__(value)
        self.original_bytes=raw
        self.transport_error=transport_error
        self.stderr_bytes=stderr
        self.transport_observation=observation


def backend_receipt(value,raw):
    return CapturedBackendReceipt(value,raw) if isinstance(value,dict) else value


def backend_output(raw,returncode,decoder):
    if returncode:
        return CapturedBackendReceipt(LocalModelRelay._unknown(),raw,'nonzero_exit')
    try:
        value=decoder(raw)
        if not isinstance(value,dict):raise ValueError()
    except (ValueError,UnicodeError,TypeError,RecursionError):
        return CapturedBackendReceipt(LocalModelRelay._unknown(),raw,'invalid_json')
    return backend_receipt(value,raw)


def host_backend_output(raw):
    """Private evidence stays in original stdout custody, outside public RPC."""
    from .router_client import decode_frame
    from .local_model_codex import unpack_bundle
    value=decode_frame(raw)
    if not isinstance(value,dict):raise ValueError()
    if '_private_evidence' in value:
        if set(value)!=RESULT_KEYS|{'_private_evidence'}:raise ValueError()
        evidence=value['_private_evidence']
        if (not isinstance(evidence,dict) or set(evidence)!={'schema','full_original_trace','wire_frames','observed_frames','observed_bytes'}
                or evidence['schema']!='ai4r-host-codex-private-evidence:1'):
            raise ValueError()
        # Reuse bounded byte/count/encoding validation without authorizing any
        # terminal from the private carrier. Public evidence is validated later.
        public=decode_frame(value['response_text'].encode()) if isinstance(value.get('response_text'),str) else None
        if not isinstance(public,dict) or public.get('schema')!='ai4r-host-codex-response:2':raise ValueError()
        check={**public,'thread_start':None,'turn_start':None,'turn_completed':None,
            'wire_frames':evidence['wire_frames'],
            'evidence':{'full_original_trace':evidence['full_original_trace'],
                'unavailable_reason':None if evidence['full_original_trace'] else 'wire_budget',
                'observed_frames':evidence['observed_frames'],'observed_bytes':evidence['observed_bytes']}}
        unpack_bundle(check)
        value={key:value[key] for key in RESULT_KEYS}
    return value


def private_path(path, *, directory=False):
    path = Path(path)
    info = path.lstat()
    if (not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents))
            or info.st_uid != os.geteuid() or (not directory and info.st_nlink != 1)
            or (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)):
        raise ResearchError('ENVIRONMENT_BLOCKED')


class SSHBackend:
    def __init__(self, executable='ssh'):
        self.executable = str(executable)

    async def __call__(self, binding, payload):
        backend = binding['backend']
        target = backend['target']
        if (backend['kind'] != 'ssh-loopback-openai'
                or not re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9_.-]*@)?[A-Za-z0-9][A-Za-z0-9.-]*', target)):
            raise ResearchError('invalid_request')
        source = Path(__file__).with_name('local_model_remote.py').read_text(encoding='utf-8')
        remote = 'python3 -c ' + shlex.quote(source)
        spawning = asyncio.create_task(asyncio.create_subprocess_exec(self.executable, '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes', target, remote,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True, limit=65536))
        try:
            process = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            process = await asyncio.shield(spawning)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.communicate()
            raise
        wire = json.dumps({'base_url': backend['base_url'], 'model': binding['model'],
            'prompt': payload['prompt'], 'timeout_s': payload['timeout_s']}, allow_nan=False).encode()
        async def observe():
            process.stdin.write(wire)
            await process.stdin.drain()
            process.stdin.close()
            chunks, size = [], 0
            while True:
                chunk = await process.stdout.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > 4 * 1024 * 1024:
                    raise ResearchError('DELIVERY_UNKNOWN')
                chunks.append(chunk)
            await process.wait()
            return b''.join(chunks)
        observer = asyncio.create_task(observe())
        try:
            output = await asyncio.shield(observer)
            return backend_output(output,process.returncode,json.loads)
        finally:
            if process.returncode is None:
                # Terminate and join local observers only; remote GPU work may continue.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
            await asyncio.gather(observer, return_exceptions=True)


class HostCodexBackend:
    """Observe a fixed native helper using the operator's existing host login."""
    async def __call__(self,binding,payload):
        from .local_models import native_absolute_path
        backend=binding['backend']
        if backend.get('kind')!='host-codex-app-server' or not native_absolute_path(backend.get('host_python'),posix_only=True):
            raise ResearchError('invalid_request')
        with backend_stage('helper_source'):
            source=Path(__file__).with_name('local_model_codex.py').read_text(encoding='utf-8')
        # Fixed public Source metadata, never an RPC-selected file or override.
        from .local_model_codex import packaged_model_catalog
        catalog=packaged_model_catalog()
        argv=[backend['host_python'],'-X','utf8','-B','-c',source]
        if len(subprocess.list2cmdline(argv))>=32767:
            raise ResearchError('invalid_request')
        wire=json.dumps({'model':binding['model'],'prompt':payload['prompt'],
            'native_model_catalog':catalog,
            'timeout_s':max(.001,payload['timeout_s']-2),
            **{key:backend[key] for key in ('codex_executable','codex_sha256','account_fingerprint','working_directory')}},
            allow_nan=False).encode()
        return await self._observe(argv,wire,relay_timeout_s=payload['timeout_s'],
            helper_timeout_s=max(.001,payload['timeout_s']-2))

    @staticmethod
    async def _observe(argv,wire,*,relay_timeout_s=None,helper_timeout_s=None):
        """Retain bounded original pipe bytes even when the carrier fails.

        Killing this observer does not establish native/provider containment.
        Diagnostics never contain exception messages or credential material.
        Raw stderr stays exclusively in the private Root receipt directory.
        """
        process=None;spawning=None;readers=[];failure=None
        streams={'stdout':bytearray(),'stderr':bytearray()}
        stderr_digest=hashlib.sha256()
        facts={'phase':'spawn','exception_class':None,'errno':None,'returncode':None,
            'stdin_complete':False,'stdout_complete':False,'stderr_complete':False,
            'stdout_bytes_observed':0,'stderr_bytes_observed':0,
            'stdout_overflow':False,'stderr_overflow':False,'observer_joined':False,
            'relay_timeout_s':relay_timeout_s,'helper_timeout_s':helper_timeout_s,
            'stdin_bytes':len(wire)}
        async def read(name,limit):
            while True:
                with backend_stage('helper_stdout' if name=='stdout' else 'helper_stderr'):
                    chunk=await getattr(process,name).read(65536)
                if not chunk:
                    facts[name+'_complete']=True;return
                facts[name+'_bytes_observed']+=len(chunk)
                if name=='stderr':stderr_digest.update(chunk)
                room=max(0,limit-len(streams[name]))
                streams[name].extend(chunk[:room])
                if len(chunk)>room:
                    first_overflow=not facts[name+'_overflow']
                    facts[name+'_overflow']=True
                    if name=='stdout' and first_overflow and process.returncode is None:
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                    # Continue draining after termination. asyncio Process.wait
                    # can otherwise remain blocked by a full pipe transport.
        def diagnostic():
            raw=bytes(streams['stderr']);prefix=raw[:65536]
            category='empty' if not facts['stderr_bytes_observed'] else 'unclassified'
            if b'WSL' in prefix and any(token in prefix for token in
                    (b'UtilAcceptVsock',b'CreateProcessEntryCommon',b'UtilConnectToInteropServer')):
                category='wsl_interop_error'
            elif b'Traceback (most recent call last):' in prefix:category='python_traceback'
            return {'exit_code':facts['returncode'],'stderr_bytes':facts['stderr_bytes_observed'],
                    'stderr_sha256':stderr_digest.hexdigest(),'stderr_class':category,
                    'stderr_classification_prefix_bytes':len(prefix),
                    'stderr_classification_truncated':facts['stderr_bytes_observed']>len(prefix)}
        try:
            spawning=asyncio.create_task(asyncio.create_subprocess_exec(*argv,
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
                start_new_session=True,limit=65536))
            with backend_stage('helper_spawn'):process=await asyncio.shield(spawning)
            readers=[asyncio.create_task(read('stdout',MAX_BACKEND_RECEIPT_BYTES)),
                     asyncio.create_task(read('stderr',MAX_BACKEND_STDERR_BYTES))]
            facts['phase']='stdin_write'
            with backend_stage('helper_stdin'):
                process.stdin.write(wire);await process.stdin.drain();process.stdin.close()
            facts['stdin_complete']=True;facts['phase']='stdout_read'
            await asyncio.shield(readers[0])
            if facts['stdout_overflow']:
                with backend_stage('helper_output_bound'):raise ResearchError('DELIVERY_UNKNOWN')
            facts['phase']='process_wait'
            with backend_stage('helper_exit'):await process.wait()
            await asyncio.shield(readers[1])
            facts['phase']='decode'
            with backend_stage('helper_decode'):
                result=backend_output(bytes(streams['stdout']),process.returncode,host_backend_output)
        except BaseException as error:
            failure=error
            # Closed class names and numeric errno only, never str(error).
            observed = (error.__cause__ if isinstance(error, BackendStageFailure)
                        and error.__cause__ is not None else error)
            facts['exception_class']=type(observed).__name__ if type(observed).__name__ in {
                'CancelledError','TimeoutError','BrokenPipeError','ConnectionResetError',
                'OSError','FileNotFoundError','PermissionError','ResearchError',
                'UnicodeDecodeError','ValueError','RuntimeError'} else 'OtherError'
            number=getattr(observed,'errno',None)
            facts['errno']=number if type(number) is int else None
        finally:
            if process is None and spawning is not None:
                try:process=await asyncio.shield(spawning)
                except BaseException:pass
            if process is not None:
                if process.returncode is None:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                try:
                    await asyncio.wait_for(process.wait(),1)
                    facts['observer_joined']=True
                except (TimeoutError,OSError):pass
                facts['returncode']=process.returncode
            # Native Windows descendants can retain inherited pipe handles.
            # Never wait forever for EOF after the local observer has exited.
            if readers:
                done,pending=await asyncio.wait(readers,timeout=1)
                for task in pending:task.cancel()
                await asyncio.gather(*readers,return_exceptions=True)
        if failure is not None:
            failure.backend_receipt=CapturedBackendReceipt(LocalModelRelay._unknown(),bytes(streams['stdout']),
                'carrier_error',stderr=bytes(streams['stderr']),observation=facts)
            failure.backend_receipt.transport_diagnostic=diagnostic()
            raise failure
        result.stderr_bytes=bytes(streams['stderr']);result.transport_observation=facts
        if facts['stderr_overflow']:
            result=CapturedBackendReceipt(LocalModelRelay._unknown(),result.original_bytes,'stderr_overflow',
                stderr=bytes(streams['stderr']),observation=facts)
        result.transport_diagnostic=diagnostic()
        return result


class BackendRouter:
    def __init__(self,ssh_executable='ssh'):
        self.ssh=SSHBackend(ssh_executable)
        self.codex=HostCodexBackend()

    async def __call__(self,binding,payload):
        kind=binding['backend']['kind']
        if kind=='ssh-loopback-openai':return await self.ssh(binding,payload)
        if kind=='host-codex-app-server':return await self.codex(binding,payload)
        raise ResearchError('invalid_request')


class LocalModelRelay:
    def __init__(self, catalog, runtime, *, backend=None, recovery_policy_sha256=None):
        self.catalog, self.runtime = catalog, Path(runtime)
        private_path(self.runtime, directory=True)
        if recovery_policy_sha256 is not None:
            if (not isinstance(recovery_policy_sha256,str) or not re.fullmatch('[0-9a-f]{64}',recovery_policy_sha256)
                    or os.name!='posix' or os.geteuid()!=0):raise ResearchError('ENVIRONMENT_BLOCKED')
        self.recovery_policy_sha256=recovery_policy_sha256
        from .local_model_recovery import RuntimeLock
        self.runtime_lock = RuntimeLock(self.runtime)
        self.db = None
        self.backend = backend if backend is not None else BackendRouter()
        self.lock = asyncio.Lock()
        try:
            self._open_ledger()
        except Exception:
            self.close()
            raise

    def _open_ledger(self):
        ledger = self.runtime / 'requests.sqlite3'
        if not ledger.exists():
            fd = os.open(ledger, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        private_path(ledger)
        self.db = sqlite3.connect(ledger)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT)')
        self.db.commit()

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        self.runtime_lock.close()

    def unresolved(self):
        """Only an exact Root disposition can authorize a DIFFERENT host policy.

        The original unknown response and charged claim are never changed. This
        is not retry permission, native terminal evidence or provider recovery.
        Generic relays retain their separate explicit operator acknowledgement;
        that broader protocol cannot satisfy an RSI recovery policy.
        """
        for ident,digest,result in self.db.execute("SELECT id,digest,result FROM requests WHERE result IS NULL OR json_extract(result,'$.outcome')='outcome_unknown'"):
            if result is None:return True
            if self.recovery_policy_sha256 is None:
                from .local_model_recovery import acknowledged_unknown
                if not acknowledged_unknown(self.runtime,(ident,digest,result)):return True
                continue
            try:
                self._validate_disposition(ident,digest,result)
            except (OSError,ValueError,TypeError,KeyError,RecursionError,ResearchError):return True
        return False

    def _validate_disposition(self,ident,digest,result):
        def need(value):
            if not value:raise ResearchError('DELIVERY_UNKNOWN')
        def read(path,limit):
            private_path(path)
            with path.open('rb') as stream:raw=stream.read(limit+1)
            need(len(raw)<=limit)
            return raw
        directory=self.runtime/'reconciliations';private_path(directory,directory=True)
        stem=hashlib.sha256(ident.encode()).hexdigest()
        value=json.loads(read(directory/(stem+'.json'),65536))
        fields={'schema','request_id','payload_sha256','result_sha256','diagnostic_sha256',
            'prior_policy_sha256','successor_policy_sha256','prior_qualification_sha256',
            'successor_qualification_sha256','actor','authorization','purpose','provider_termination',
            'original_outcome','automatic_replay','prior_budget_preserved','recorded_at','evidence_refs'}
        need(isinstance(value,dict) and set(value)==fields
            and value['schema']=='ai4r-host-codex-abandonment:1'
            and value['request_id']==ident and value['payload_sha256']==digest
            and value['result_sha256']==hashlib.sha256(result.encode()).hexdigest()
            and value['successor_policy_sha256']==self.recovery_policy_sha256
            and value['prior_policy_sha256']!=value['successor_policy_sha256']
            and value['actor']=='os:0:root' and value['purpose']=='exact_new_bounded_screening_run'
            and value['provider_termination']=='UNPROVEN' and value['original_outcome']=='outcome_unknown'
            and value['automatic_replay'] is False and value['prior_budget_preserved'] is True
            and isinstance(value['authorization'],str) and 0<len(value['authorization'])<=4096
            and isinstance(value['recorded_at'],str))
        from datetime import datetime
        need(datetime.fromisoformat(value['recorded_at'].replace('Z','+00:00')).tzinfo is not None)
        for field in ('payload_sha256','result_sha256','diagnostic_sha256','prior_policy_sha256',
                      'successor_policy_sha256','prior_qualification_sha256','successor_qualification_sha256'):
            need(isinstance(value[field],str) and re.fullmatch('[0-9a-f]{64}',value[field]))
        receipts=self.runtime/'backend-receipts';private_path(receipts,directory=True)
        diagnostic=read(receipts/(stem+'.json'),16384)
        need(hashlib.sha256(diagnostic).hexdigest()==value['diagnostic_sha256'])
        diagnosis=json.loads(diagnostic)
        need(diagnosis.get('request_id')==ident and diagnosis.get('payload_sha256')==digest
            and diagnosis.get('backend_kind')=='host-codex-app-server')
        kinds={'old_qualification','new_qualification','old_profile','local_cessation','windows_cessation',
               'old_no_tools_proof','new_no_tools_proof','authorization'}
        refs=value['evidence_refs'];need(isinstance(refs,list) and len(refs)==len(kinds))
        evidence={};root=self.runtime/'recovery-evidence';private_path(root,directory=True)
        for pin in refs:
            need(isinstance(pin,dict) and set(pin)=={'kind','sha256'} and pin['kind'] in kinds
                and pin['kind'] not in evidence and isinstance(pin['sha256'],str)
                and re.fullmatch('[0-9a-f]{64}',pin['sha256']))
            raw=read(root/(pin['sha256']+'.json'),2*1024*1024)
            need(hashlib.sha256(raw).hexdigest()==pin['sha256'])
            evidence[pin['kind']]=json.loads(raw)
        need(set(evidence)==kinds)
        for prefix in ('old','new'):
            qualified=evidence[prefix+'_qualification'];proof=evidence[prefix+'_no_tools_proof']
            pin=next(pin for pin in refs if pin['kind']==prefix+'_qualification')
            need(pin['sha256']==value['prior_qualification_sha256' if prefix=='old' else 'successor_qualification_sha256']
                and qualified.get('schema')=='ai4r-rsi-host-codex-no-tools:1'
                and qualified.get('model')=='gpt-6.1-sol' and qualified.get('reasoning_effort')=='medium'
                and qualified.get('tool_names')==[]
                and all(type(qualified.get(key)) is int and qualified[key]==0
                        for key in ('tools_count','functions_count','additional_tools_count'))
                and proof.get('schema')=='ai4r-offline-native-tools-wire-proof:1'
                and proof.get('helper_source_sha256')==qualified.get('helper_sha256')
                and proof.get('native_binary_sha256')==qualified.get('binary_sha256')
                and proof.get('real_auth_or_account_files_used') is False
                and proof.get('real_generation_performed') is False)
            proofpin=next(pin for pin in refs if pin['kind']==prefix+'_no_tools_proof')
            need(qualified.get('proof_sha256')==proofpin['sha256'])
            cases=proof.get('cases');need(isinstance(cases,list) and bool(cases))
            for case in cases:
                requests=case.get('http_requests');need(isinstance(requests,list) and bool(requests))
                need(case.get('real_provider_called') is False and case.get('account_rpc_sent') is False)
                for request in requests:
                    need(request.get('model')=='gpt-6.1-sol' and request.get('reasoning_effort')=='medium'
                        and request.get('tools_count')==0 and request.get('functions_count')==0
                        and request.get('additional_tools')==[] and request.get('recursive_tool_locations')==[]
                        and request.get('actual_system_guard_present') is True)
        old=evidence['old_profile']
        need(old.get('schema')=='ai4r-rsi-host-codex:1' and old.get('policy_sha256')==value['prior_policy_sha256']
            and old.get('qualification')==evidence['old_qualification'])
        auth=evidence['authorization']
        need(isinstance(auth,dict) and set(auth)=={'schema','actor','request_id','prior_policy_sha256',
            'successor_policy_sha256','purpose','authorization','recorded_at'}
            and auth['schema']=='ai4r-host-codex-recovery-authorization:1'
            and all(auth[key]==value[key] for key in ('actor','request_id','prior_policy_sha256',
                'successor_policy_sha256','purpose','authorization','recorded_at')))
        local=evidence['local_cessation'];windows=evidence['windows_cessation']
        need(local.get('schema')=='ai4r-rsi-cloud-native-host-cessation-observation:1'
            and local.get('matching_processes')==[] and local.get('matching_native_container_ids')==[]
            and local.get('process_scan_errors')==[] and isinstance(local.get('owned_container_id'),str)
            and any(event.get('Action')=='die' and event.get('Actor',{}).get('ID')==local['owned_container_id']
                    for event in local.get('lifecycle_events',[]))
            and windows.get('schema')=='ai4r-rsi-host-windows-scoped-process-observation:1'
            and windows.get('status')=='OBSERVED' and type(windows.get('owned_process_count')) is int
            and windows['owned_process_count']==0 and windows.get('processes')==[]
            and windows.get('remote_termination_inferred') is False)

    def _receipt_directory(self):
        directory=self.runtime/'backend-receipts'
        directory.mkdir(mode=0o700,exist_ok=True)
        private_path(directory,directory=True)
        return directory

    @staticmethod
    def _write_once(path,raw):
        """Publish complete private bytes exclusively; never adopt/replace evidence."""
        temporary=path.parent/('.capture-'+secrets.token_hex(16))
        fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.link(temporary,path)
            if os.name=='posix':
                directory=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
                try:os.fsync(directory)
                finally:os.close(directory)
        finally:temporary.unlink(missing_ok=True)
        private_path(path)

    def _capture_receipt(self,payload,digest,result):
        original=getattr(result,'original_bytes',None)
        source='backend-stdout' if isinstance(original,bytes) else 'serialized-backend-result'
        raw=original if isinstance(original,bytes) else json.dumps(result,ensure_ascii=False,
            separators=(',',':'),allow_nan=False).encode('utf-8')
        if len(raw)>MAX_BACKEND_RECEIPT_BYTES:raise ResearchError('AUDIT_UNAVAILABLE')
        name=hashlib.sha256(payload['request_id'].encode()).hexdigest()+'.receipt'
        self._write_once(self._receipt_directory()/name,raw)
        return {'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw),'encoding':source}

    def _capture_stderr(self,payload,original):
        raw=getattr(original,'stderr_bytes',None)
        if not isinstance(raw,bytes) or not raw:return None
        if len(raw)>MAX_BACKEND_STDERR_BYTES:raise ResearchError('AUDIT_UNAVAILABLE')
        name=hashlib.sha256(payload['request_id'].encode()).hexdigest()+'.stderr'
        self._write_once(self._receipt_directory()/name,raw)
        return {'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}

    def _capture_error(self,payload,digest,error,original,receipt):
        # asyncio.timeout translates cancellation, preserving it as __cause__.
        current=error
        for _ in range(3):
            captured=getattr(current,'backend_receipt',None)
            if captured is not None:
                if original is None:original=captured
                if receipt is None:receipt=self._capture_receipt(payload,digest,original)
                break
            current=getattr(current,'__cause__',None)
            if current is None:break
        return original,receipt

    @staticmethod
    def _receipt_counts(result):
        """Only bounded counters/closed statuses enter diagnostics, never error text."""
        counts={'response_text_bytes':None,'wire_frames':None,'wire_bytes':None,
                'native_outcome':None,'native_error_code':None,'terminal_status':None,
                'full_original_trace':None,'evidence_unavailable':None,'observed_wire_frames':None,'observed_wire_bytes':None}
        if not isinstance(result,dict) or not isinstance(result.get('response_text'),str):return counts
        raw=result['response_text']
        try:counts['response_text_bytes']=len(raw.encode())
        except UnicodeError:return counts
        if counts['response_text_bytes']>1024*1024:return counts
        try:
            bundle=json.loads(raw)
            from .local_model_codex import unpack_bundle
            packed=bundle
            bundle=unpack_bundle(bundle)
            if packed.get('schema')=='ai4r-host-codex-response:2':
                evidence=packed['evidence']
                counts.update(full_original_trace=evidence['full_original_trace'],
                    evidence_unavailable=evidence['unavailable_reason'],
                    observed_wire_frames=evidence['observed_frames'],observed_wire_bytes=evidence['observed_bytes'])
        except (ValueError,TypeError,KeyError,UnicodeError,RecursionError):return counts
        if not isinstance(bundle,dict):return counts
        if bundle.get('outcome') in ('completed','failed','outcome_unknown'):counts['native_outcome']=bundle['outcome']
        code=bundle.get('error_code')
        if code in ('auth_failed','invalid_request','provider_error','timeout','network_error','invalid_output','CONTAINMENT_UNCERTAIN'):
            counts['native_error_code']=code
        terminal=bundle.get('turn_completed')
        if isinstance(terminal,dict) and isinstance(terminal.get('turn'),dict):
            status=terminal['turn'].get('status')
            if status in ('completed','failed','interrupted','inProgress'):counts['terminal_status']=status
        frames=bundle.get('wire_frames')
        if isinstance(frames,list):
            counts['wire_frames']=len(frames)
            try:
                counts['wire_bytes']=sum(len(frame['raw'].encode()) for frame in frames
                    if isinstance(frame,dict) and isinstance(frame.get('raw'),str))
            except UnicodeError:pass
        return counts

    def _receipt_diagnostic(self,payload,digest,binding,receipt,reason,received_at,original,failure=None):
        directory=self._receipt_directory()
        name=hashlib.sha256(payload['request_id'].encode()).hexdigest()+'.json'
        value={'schema':'ai4r-backend-receipt:1','request_id':payload['request_id'],
            'payload_sha256':digest,'binding_sha256':payload['binding_sha256'],
            'backend_kind':binding.get('backend',{}).get('kind'),'receipt':receipt,'reason':reason,
            'transport_error':getattr(original,'transport_error',None),
            'transport_diagnostic':getattr(original,'transport_diagnostic',None),
            'transport_observation':getattr(original,'transport_observation',None),
            'stderr_receipt':self._capture_stderr(payload,original),
            'requested_timeout_s':payload['timeout_s'],
            'elapsed_ms':max(0,int((monotonic()-received_at)*1000)),
            'bounds':{'backend_receipt_bytes':MAX_BACKEND_RECEIPT_BYTES,'backend_stderr_bytes':MAX_BACKEND_STDERR_BYTES,
                      'native_response_bytes':1024*1024,'native_wire_frames':None},
            'counts':self._receipt_counts(original),'failure':failure}
        raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>16384:raise ResearchError('AUDIT_UNAVAILABLE')
        self._write_once(directory/name,raw)

    async def probe(self, payload):
        """Private no-inference helper readiness; never acquires a ledger claim."""
        if (not isinstance(payload,dict) or set(payload)!={'endpoint_id','binding_sha256'}
                or not isinstance(payload['endpoint_id'],str) or not payload['endpoint_id']
                or not isinstance(payload['binding_sha256'],str)
                or not re.fullmatch('[0-9a-f]{64}',payload['binding_sha256'])):
            raise ResearchError('invalid_request')
        binding=self.catalog.resolve(payload['endpoint_id'],binding_sha256=payload['binding_sha256'])
        backend=binding.get('backend',{})
        if (backend.get('kind')!='host-codex-app-server'
                or not isinstance(backend.get('codex_sha256'),str)
                or not re.fullmatch('[0-9a-f]{64}',backend['codex_sha256'])
                or backend['codex_sha256']=='0'*64):
            raise ResearchError('invalid_request')
        # Explicitly corrupt the verified binary pin, so the fixed helper exits
        # validation before native profile/account access or App Server launch.
        binding={**binding,'backend':{**backend,'codex_sha256':'0'*64},'model':dict(binding['model'])}
        if self.lock.locked():
            raise ResearchError('ENVIRONMENT_BLOCKED')
        observation={'schema':'ai4r-local-model-probe:1','ready':False,
                     'inference_requested':False,'decision':'backend_failure',
                     'transport_diagnostic':None,'failure':None}
        async with self.lock:
            try:
                timeout=min(20,binding['model']['timeout_s'])
                async with asyncio.timeout(timeout):
                    result=await self.backend(binding,{'prompt':'AI4R transport readiness probe.', 'timeout_s':timeout})
                observation['transport_diagnostic']=getattr(result,'transport_diagnostic',None)
                if getattr(result,'transport_error',None):
                    observation['decision']='transport_rejected'
                    return observation
                observation['decision']='invalid_helper_receipt'
                from .local_model_codex import unpack_bundle
                if not isinstance(result,dict) or set(result)!=RESULT_KEYS:
                    return observation
                native=unpack_bundle(json.loads(result['response_text']))
                if (result['outcome']=='failed' and result['http_status'] is None
                        and result['provider_request_id'] is None
                        and native.get('outcome')=='failed' and native.get('error_code')=='invalid_request'
                        and native.get('schema')=='ai4r-host-codex-response:1'
                        and native.get('requested_model')==binding['model']['model_name']
                        and native.get('reasoning_effort')==binding['model'].get('reasoning_effort')
                        and native.get('binary_sha256') is None and native.get('account_fingerprint') is None
                        and all(native.get(key) is None for key in ('thread_start','turn_start','turn_completed'))
                        and native.get('wire_frames')==[]):
                    observation.update(ready=True,decision='expected_predispatch_rejection')
                return observation
            except asyncio.CancelledError:
                raise
            except Exception as error:
                observation['failure']=(error.diagnostic if isinstance(error,BackendStageFailure) else
                    {'stage':'probe_observer','exception_class':exception_category(error)})
                return observation

    async def invoke(self, payload):
        received_at=monotonic()
        if (not isinstance(payload, dict) or set(payload) != REQUEST_KEYS
                or any(not isinstance(payload[k], str) or not payload[k] for k in ('request_id', 'endpoint_id', 'binding_sha256', 'model'))
                or len(payload['request_id']) > 128 or not re.fullmatch(r'[0-9a-f]{64}', payload['binding_sha256'])
                or not isinstance(payload['prompt'], str)):
            raise ResearchError('invalid_request')
        # Freeze caller-owned objects before the first scheduling boundary.
        payload = dict(payload)
        binding = self.catalog.resolve(payload['endpoint_id'], binding_sha256=payload['binding_sha256'])
        policy = binding['model']
        timeout = payload['timeout_s']
        if (payload['model'] != policy['model_name'] or type(timeout) not in {int, float}
                or not math.isfinite(timeout) or not 0 < timeout <= min(600, policy['timeout_s'])
                or len(payload['prompt'].encode('utf-8')) > policy['max_prompt_bytes']):
            raise ResearchError('invalid_request')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        row = self.db.execute('SELECT digest,result FROM requests WHERE id=?', (payload['request_id'],)).fetchone()
        if row:
            if row[0] != digest:
                raise ResearchError('invalid_request')
            if row[1] is not None:
                return json.loads(row[1])
            return self._envelope(payload, self._unknown())
        # Never queue model effects behind another call: its caller may expire
        # while waiting. Save the rejection so the same ID cannot dispatch later.
        # No scheduling boundary occurs between checking and acquiring this lock.
        if self.lock.locked():
            self.db.execute('INSERT INTO requests VALUES (?,?,NULL)', (payload['request_id'], digest))
            self.db.commit()
            return self._save(payload, dict(outcome='failed', http_status=429,
                                           response_text=None, provider_request_id=None))
        async with self.lock:
            # Every unresolved durable claim blocks all further effects, including after restart.
            if self.unresolved():
                raise ResearchError('DELIVERY_UNKNOWN')
            self.db.execute('INSERT INTO requests VALUES (?,?,NULL)', (payload['request_id'], digest))
            self.db.commit()
            remaining=received_at+timeout-monotonic()
            if remaining<=0:
                return self._save(payload,dict(outcome='failed',http_status=408,
                                               response_text=None,provider_request_id=None))
            receipt=None;original=None;reason='backend_error';failure=None
            try:
                async with asyncio.timeout(remaining):
                    result = await self.backend(binding, {**payload,'timeout_s':remaining})
                original=result;reason='receipt_capture_failed'
                receipt=self._capture_receipt(payload,digest,result)
                if getattr(original,'transport_error',None):
                    reason='backend_transport_rejected'
                    raise ResearchError('DELIVERY_UNKNOWN')
                reason='backend_envelope_rejected'
                if (not isinstance(result, dict) or set(result) != RESULT_KEYS
                        or result['outcome'] not in {'completed', 'failed', 'outcome_unknown'}
                        or (result['http_status'] is not None and (type(result['http_status']) is not int or not 100 <= result['http_status'] <= 599))
                        or any(result[k] is not None and not isinstance(result[k], str) for k in ('response_text', 'provider_request_id'))
                        or (result['response_text'] is not None and len(result['response_text'].encode()) > 1024 * 1024)):
                    result = self._unknown()
                if binding.get('backend',{}).get('kind')=='host-codex-app-server':
                    if isinstance(result['response_text'],str):
                        reason='native_validation_rejected'
                        from .local_models import native_codex_response
                        bundle,observation,_=native_codex_response(result['response_text'],binding,prompt=payload['prompt'])
                        if (result['http_status'] is not None or result['outcome']!=bundle['outcome']
                                or result['provider_request_id']!=observation['provider_request_id']):
                            reason='native_envelope_rejected'
                            result=self._unknown()
                        else:reason='accepted'
                    else:
                        reason='native_bundle_absent';result=self._unknown()
                elif result['outcome'] == 'completed':
                    provider_receipt = result['provider_request_id']
                    if (type(result['http_status']) is not int or not 200 <= result['http_status'] < 300
                            or not isinstance(result['response_text'], str)
                            or (provider_receipt is not None and (len(provider_receipt) > 256 or not all(32 <= ord(c) < 127 for c in provider_receipt)))
                            or len(json.dumps(result, ensure_ascii=False).encode()) > 3 * 1024 * 1024):
                        result = self._unknown()
                    else:reason='accepted'
                elif result['outcome'] == 'failed':
                    status = result['http_status']
                    result = (dict(outcome='failed', http_status=status, response_text=None, provider_request_id=None)
                              if type(status) is int and 300 <= status <= 599 else self._unknown())
                    if result['outcome']=='failed':reason='accepted'
                else:
                    result = self._unknown()
                if reason=='backend_envelope_rejected' and original is result:reason='accepted'
            except asyncio.CancelledError as error:
                try:original,receipt=self._capture_error(payload,digest,error,original,receipt)
                except Exception:pass
                try:self._receipt_diagnostic(payload,digest,binding,receipt,'backend_cancelled',received_at,original)
                except Exception:pass
                self._save(payload, self._unknown())
                raise
            except Exception as error:
                try:original,receipt=self._capture_error(payload,digest,error,original,receipt)
                except Exception:pass
                failure=(error.diagnostic if isinstance(error,BackendStageFailure) else
                         {'stage':reason,'exception_class':exception_category(error)})
                result = self._unknown()
            try:self._receipt_diagnostic(payload,digest,binding,receipt,reason,received_at,original,failure)
            except Exception:result=self._unknown()
            return self._save(payload, result)

    @staticmethod
    def _unknown():
        return dict(outcome='outcome_unknown', http_status=None, response_text=None, provider_request_id=None)

    @staticmethod
    def _envelope(payload, result):
        return {'request_id': payload['request_id'], 'binding_sha256': payload['binding_sha256'], **result}

    def _save(self, payload, result):
        envelope = self._envelope(payload, result)
        self.db.execute('UPDATE requests SET result=? WHERE id=?',
                        (json.dumps(envelope, allow_nan=False), payload['request_id']))
        self.db.commit()
        return envelope


async def serve(args):
    from .local_models import LocalModelCatalog
    if not args.allowed_uid:
        raise ResearchError('ENVIRONMENT_BLOCKED')
    runtime = Path(args.runtime)
    # Existing runtime is supported only under strict custody; never replace session/socket.
    if runtime.exists():
        private_path(runtime, directory=True)
    else:
        runtime.mkdir(mode=0o700)
    session_path = runtime / 'session.json'
    if session_path.exists():
        private_path(session_path)
        session = json.loads(session_path.read_text())
        if set(session) != {'session_id', 'capability'} or any(not isinstance(v, str) or len(v) < 32 for v in session.values()):
            raise ResearchError('ENVIRONMENT_BLOCKED')
    else:
        session = {'session_id': secrets.token_urlsafe(32), 'capability': secrets.token_urlsafe(48)}
        fd = os.open(session_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(session, output)
            output.flush()
            os.fsync(output.fileno())
    catalog = LocalModelCatalog(args.catalog,owner_uid=args.catalog_owner_uid)
    document = catalog.snapshot()
    transport = document['transport']
    if transport['peer_uid'] != os.geteuid():
        raise ResearchError('ENVIRONMENT_BLOCKED')
    # Catalog checks are repeated on every invoke, including the server UID pin.
    class ProcessCatalog:
        def resolve(self, endpoint_id, binding_sha256=None):
            binding = catalog.resolve(endpoint_id, binding_sha256=binding_sha256)
            if binding['transport']['peer_uid'] != os.geteuid():
                raise ResearchError('ENVIRONMENT_BLOCKED')
            return binding
    relay = LocalModelRelay(ProcessCatalog(), runtime, backend=BackendRouter(args.ssh_executable))
    socket_directory = runtime
    if args.socket_directory:
        socket_directory = Path(args.socket_directory)
        info = socket_directory.lstat()
        if (not socket_directory.is_absolute() or any(p.is_symlink() for p in (socket_directory, *socket_directory.parents))
                or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_gid != 10001 or stat.S_IMODE(info.st_mode) != 0o2710
                or transport['socket_mode'] != 0o660 or socket_directory == runtime
                or any(p.name != 'model.sock' for p in socket_directory.iterdir())):
            raise ResearchError('ENVIRONMENT_BLOCKED')
    server = PrivateRPCServer(socket_directory / 'model.sock', protocol=PROTOCOL,
        session_id=session['session_id'], capability=session['capability'],
        handlers={'invoke': relay.invoke,'probe': relay.probe}, allowed_uids=args.allowed_uid,
        socket_mode=transport['socket_mode'], directory_mode=0o2710 if args.socket_directory else 0o700)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await server.start()
        await stop.wait()
    finally:
        await server.close()
        relay.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--catalog-owner-uid',type=int,default=0)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--socket-directory', help='Dedicated owner:10001 directory, mode 02710; exports only model.sock')
    parser.add_argument('--ssh-executable', default='ssh')
    parser.add_argument('--allowed-uid', type=int, action='append', required=True)
    asyncio.run(serve(parser.parse_args()))


if __name__ == '__main__':
    main()
