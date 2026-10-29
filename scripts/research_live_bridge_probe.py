"""Frozen stdlib-only I027 probe and independent original-byte predicates.

The executable entry uses only fixed native paths. It neither issues context
authority nor imports product code, installed packages or provider credentials.
Public capture predicates are also replayed by the external pytest controller.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import struct
import subprocess
import sys

PROTOCOL='ai4r-model-ipc:1'
PROMPT='Return the single word OK.'
MAX_FRAME=4*1024**2
PROFILE=Path('/run/ai4r/live-bridge-profile.json')
SESSION=Path('/run/ai4r/session.json')
STORE=Path('/var/lib/ai4r')
SOCKET=Path('/run/ai4r/model.sock')
MANIFEST=Path('/usr/local/share/ai4r-build-identity.json')
CLI=Path('/usr/local/bin/codex')
CLI_RECEIPT=Path('/usr/local/share/ai4r-codex-runtime.json')
REF_FIELDS={'id','sha256'}
TELEMETRY={'run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id',
           'call_id','route_ref','contract_ref','model_call_start_ref'}


class EvidenceError(ValueError):
    pass


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition,code):
    if not condition:raise EvidenceError(code)


def ref_key(ref):
    require(isinstance(ref,dict) and set(ref)==REF_FIELDS and isinstance(ref['id'],str) and ref['id']
        and isinstance(ref['sha256'],str) and re.fullmatch('[a-f0-9]{64}',ref['sha256']), 'EXACT_REF_REQUIRED')
    return ref['id'],ref['sha256']


def check_capture(value,target):
    """Recompute original bytes/kinds/joins; reported booleans are never proof."""
    require(isinstance(value,dict) and value.get('schema')=='ai4r-live-bridge-capture:1'
        and value.get('outcome')=='CAPTURED','LIVE_CAPTURE_INCOMPLETE')
    require(value.get('identity')=={key:target[key] for key in
        ('job_id','instance_id','build_id','candidate_id','profile_sha256')},'CAPTURE_IDENTITY_MISMATCH')
    status=value.get('subscription_status')
    require(isinstance(status,dict) and set(status)=={'state','enabled','builder_qualified','capture_healthy'}
        and status['state']=='ready' and status['enabled'] is True and status['capture_healthy'] is True,
        'ACTUAL_APP_ACCOUNT_OR_CAPTURE_UNAVAILABLE')
    require(set(value.get('roles',{}))=={'worker','verifier'},'BOTH_ROLE_CAPTURES_REQUIRED')
    records={};record_sequences=set()
    for item in value.get('records',[]):
        require(isinstance(item,dict) and set(item)=={'ref','kind','record_sequence','raw_b64'},'CLOSED_CAPTURE_ROW_REQUIRED')
        key=ref_key(item['ref']);require(key not in records,'DUPLICATE_CAPTURE_REF')
        try:raw=base64.b64decode(item['raw_b64'],validate=True)
        except (ValueError,TypeError):raise EvidenceError('CAPTURE_ENCODING') from None
        require(len(raw)<=16*1024**2 and sha(raw)==key[1],'ORIGINAL_CAPTURE_HASH_MISMATCH')
        require(item['kind'] is None or isinstance(item['kind'],str),'CAPTURE_KIND_INVALID')
        require(item['record_sequence'] is None if item['kind'] is None else type(item['record_sequence']) is int and item['record_sequence']>0,
            'PROTECTED_RECORD_SEQUENCE_REQUIRED')
        if item['record_sequence'] is not None:
            require(item['record_sequence'] not in record_sequences,'DUPLICATE_PROTECTED_SEQUENCE')
            record_sequences.add(item['record_sequence'])
        records[key]=(item['kind'],raw,item['record_sequence'])
    def read(ref,kind=None):
        key=ref_key(ref);require(key in records,'ORIGINAL_CAPTURE_MISSING')
        actual,raw,_=records[key]
        require(kind is None or actual==kind,'PROTECTED_KIND_MISMATCH')
        try:return json.loads(raw)
        except (ValueError,UnicodeError):raise EvidenceError('CAPTURE_JSON_INVALID') from None
    result={}
    thread_ids=[]
    for role,row in value['roles'].items():
        context=read(row['context_ref']);reservation=read(row['reservation_ref'],'invocation-budget-reservation')
        require(set(context)=={'execution_id','call_ordinal'} and context['call_ordinal']==1,'UNCLAIMED_CONTEXT_REQUIRED')
        contract=read(row['contract_ref']);configuration=read(row['configuration_ref'])
        require(reservation['execution_id']==context['execution_id'] and reservation['contract_ref']==row['contract_ref']
            and contract['configuration_ref']==row['configuration_ref'],'CONTEXT_CONTRACT_JOIN')
        binding=contract['bindings'][0]
        require(binding['role']==role and binding['limits']['model_calls']==1
            and 0<binding['limits']['time_s']<=120 and configuration['cc']['router']['enabled'] is False,'FIXED_BOUNDED_ROLE_REQUIRED')
        require(row['before_start_refs']==row['wrong_token_start_refs']==[]
            and len(row['after_start_refs'])==1 and row['duplicate_start_refs']==row['after_start_refs'], 'NEGATIVE_START_COUNT_MISMATCH')
        require(set(row['wrong_token_reply'])=={'error'} and row['wrong_token_reply']['error'] in
            {'DELIVERY_UNKNOWN','PLATFORM_INTEGRITY_FAULT'} and set(row['duplicate_reply'])=={'error'}
            and row['duplicate_reply']['error'] in {'DELIVERY_UNKNOWN','PLATFORM_INTEGRITY_FAULT','invalid_request'},'NEGATIVE_REFUSAL_REQUIRED')
        reply=row['reply'];require(reply.get('protocol')==PROTOCOL and 'error' not in reply,'LIVE_REPLY_FAILED')
        call=read(reply['result']['call_ref'],'model-call');route=read(reply['result']['route_ref'],'route-record')
        start_ref=row['after_start_refs'][0];start=read(start_ref,'model-call-start')
        require(start['execution_id']==context['execution_id']==call['execution_id']
            and start['invocation_id']==reservation['invocation_id']==call['invocation_id']==route['invocation_id']
            and start['contract_ref']==row['contract_ref'] and start['route_ref']==reply['result']['route_ref']
            and start['call_id']==call['id'], 'CALL_START_ROUTE_JOIN')
        claim=read(start['call_claim_ref'],'model-call-claim')
        require(claim.get('execution_id')==context['execution_id'] and claim.get('invocation_id')==reservation['invocation_id']
            and claim.get('contract_ref')==row['contract_ref'] and claim.get('call_id')==call['id']
            and claim.get('call_ordinal')==1,'ORIGINAL_DURABLE_CALL_CLAIM_JOIN')
        prompt=read(start['input_ref'],'model-call-input')
        require(prompt.get('prompt')==PROMPT and prompt.get('call_id')==call['id'],'FIXED_PROMPT_JOIN')
        start_order=records[ref_key(start_ref)][2];call_order=records[ref_key(reply['result']['call_ref'])][2]
        require(records[ref_key(reply['result']['route_ref'])][2]<start_order<call_order
            and records[ref_key(start['input_ref'])][2]<start_order
            and records[ref_key(start['call_claim_ref'])][2]<start_order,'DURABLE_ROUTE_INPUT_START_ORDER')
        require(call['outcome']=='completed' and call['call_function']==role and route['router_enabled'] is False
            and route['model_id']==call['identity']['requested']=='codex-cli-default' and isinstance(call.get('usage'),dict), 'FIXED_NATIVE_CALL_REQUIRED')
        traces=[]
        for ref in call['evidence_refs']:
            record=read(ref)
            if record.get('schema')=='ai4r-native-governed-trace:1':
                read(ref,'native-governed-trace');traces.append(record)
        require(len(traces)==1 and traces[0]['status']=='completed' and traces[0]['event_refs'],'ORIGINAL_NATIVE_TRACE_REQUIRED')
        scope={key:contract[key] for key in ('run_id','node_id','subnode_id','attempt_id')}
        scope.update(execution_id=context['execution_id'],invocation_id=reservation['invocation_id'],
            call_id=call['id'],contract_ref=row['contract_ref'],model_call_start_ref=start_ref)
        trace=traces[0];require(trace['scope']==scope,'TRACE_SCOPE_JOIN')
        methods=[]
        for index,ref in enumerate(trace['event_refs']):
            event=read(ref,'native-governed-trace-event')
            require(event.get('schema')=='ai4r-native-governed-trace-event:1' and event.get('scope')==scope
                and event.get('sequence')==index and event.get('direction') in {'in','out'},'TRACE_EVENT_JOIN')
            require(start_order<records[ref_key(ref)][2]<call_order,'NATIVE_PACKET_AFTER_DURABLE_START')
            packet=read(event['raw_ref']);methods.append(event['method'])
            require(not event['method'].startswith(('account/','login/')),'ACCOUNT_PAYLOAD_EXCLUDED')
            if event['direction']=='out':
                def clean(obj):
                    if isinstance(obj,dict):return not TELEMETRY.intersection(obj) and all(clean(v) for v in obj.values())
                    if isinstance(obj,list):return all(clean(v) for v in obj)
                    return True
                require(clean(packet.get('params',{})),'TELEMETRY_PROVIDER_NONINTERFERENCE')
                require(packet.get('method')==event['method'],'OUTGOING_METHOD_JOIN')
            if event['method']=='thread/start' and event['direction']=='in':
                identifier=((packet.get('result') or {}).get('thread') or {}).get('id')
                require(isinstance(identifier,str) and identifier,'FRESH_NATIVE_THREAD_REQUIRED');thread_ids.append(identifier)
        require('thread/start' in methods and 'turn/start' in methods,'NATIVE_THREAD_TURN_REQUIRED')
        result[role]={name:True for name in ('original_bytes','protected_kinds','identity','fixed_role','bounded_context',
            'wrong_token_zero_start','single_start','route_input_join','native_trace','telemetry_excluded','duplicate_zero_start')}
    require(len(thread_ids)==2 and len(set(thread_ids))==2, 'TWO_FRESH_GOVERNED_THREADS_REQUIRED')
    return result


def regular(path,*,uid=None,mode=None,maximum=16*1024**2):
    path=Path(path)
    require(not any(item.is_symlink() for item in (path,*path.parents)),'NATIVE_PATH_ALIAS')
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=maximum,'NATIVE_REGULAR_FILE_REQUIRED')
    require(uid is None or info.st_uid==uid,'NATIVE_FILE_OWNER')
    require(mode is None or stat.S_IMODE(info.st_mode)==mode,'NATIVE_FILE_MODE')
    raw=path.read_bytes();after=path.lstat()
    require((info.st_ino,info.st_size,info.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'NATIVE_FILE_CHANGED')
    return raw


class ReadOnlyEvidence:
    def __init__(self):
        path=STORE/'state/research.sqlite3'
        require(not any(item.is_symlink() for item in (path,*path.parents)),'STORE_PATH_ALIAS')
        self.db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        self.rows={};self.total=0
    def read(self,ref):
        key=ref_key(ref)
        require(self.db.execute('SELECT sha256 FROM artifacts WHERE id=?',(key[0],)).fetchone()==(key[1],),'ORIGINAL_REF_NOT_REGISTERED')
        raw=regular(STORE/'artifacts/sha256'/key[1][:2]/key[1]);require(sha(raw)==key[1],'ORIGINAL_STORED_HASH')
        kind=self.db.execute('SELECT kind,rowid FROM records WHERE id=?',(key[0],)).fetchone()
        if key not in self.rows:
            self.total+=len(raw);require(self.total<=64*1024**2,'PUBLIC_CAPTURE_BOUND')
            self.rows[key]={'ref':ref,'kind':kind[0] if kind else None,'record_sequence':kind[1] if kind else None,
                'raw_b64':base64.b64encode(raw).decode()}
        return json.loads(raw)
    def selected(self,kind,execution_id):
        found=[]
        for identifier,digest in self.db.execute('SELECT r.id,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id WHERE r.kind=? ORDER BY r.rowid',(kind,)):
            ref={'id':identifier,'sha256':digest}
            # Read only matching records into the exported run-local closure.
            raw=regular(STORE/'artifacts/sha256'/digest[:2]/digest)
            require(sha(raw)==digest,'ORIGINAL_STORED_HASH')
            if json.loads(raw).get('execution_id')==execution_id:
                self.read(ref);found.append(ref)
        return found


def exchange(context,session,*,wrong=False):
    metadata=SOCKET.lstat()
    require(stat.S_ISSOCK(metadata.st_mode) and metadata.st_uid==10001 and stat.S_IMODE(metadata.st_mode)==0o600,'MODEL_SOCKET_CUSTODY')
    envelope={'protocol':PROTOCOL,'op':'invoke',**session,'context':context,'prompt':PROMPT}
    if wrong:envelope['capability']='deliberately-invalid'
    raw=encoded(envelope);require(len(raw)<=MAX_FRAME,'FRAME_BOUND')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(130);client.connect(str(SOCKET))
        _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        require(uid==10001,'MODEL_PEER_UID');client.sendall(struct.pack('!I',len(raw))+raw)
        def receive(count):
            data=b''
            while len(data)<count:
                part=client.recv(count-len(data))
                if not part:raise EOFError
                data+=part
            return data
        try:
            size=struct.unpack('!I',receive(4))[0];require(0<size<=MAX_FRAME,'REPLY_FRAME_BOUND')
            value=json.loads(receive(size));require(value.get('protocol')==PROTOCOL,'MODEL_REPLY_PROTOCOL')
            if 'error' in value and not value.get('call_ref') and not value.get('route_ref'):
                return {'error':value['error']}
            return value
        except (EOFError,ConnectionError):return {'error':'DELIVERY_UNKNOWN'}


def subscription_status(session):
    """Existing finite read-only IPC; never login/logout or credentials."""
    path=Path('/run/ai4r/agent-status.sock');metadata=path.lstat()
    require(stat.S_ISSOCK(metadata.st_mode) and metadata.st_uid==10001 and stat.S_IMODE(metadata.st_mode)==0o600,'AGENT_STATUS_CUSTODY')
    raw=encoded({'protocol':'ai4r-agent-status-v1',**session,'operation':'subscription_status','payload':{}})
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(30);client.connect(str(path))
        _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12));require(uid==10001,'AGENT_STATUS_PEER')
        client.sendall(struct.pack('!I',len(raw))+raw)
        def receive(count):
            data=b''
            while len(data)<count:
                part=client.recv(count-len(data))
                if not part:raise EvidenceError('AGENT_STATUS_UNAVAILABLE')
                data+=part
            return data
        size=struct.unpack('!I',receive(4))[0];require(0<size<=MAX_FRAME,'AGENT_STATUS_BOUND')
        value=json.loads(receive(size))
        require(value.get('protocol')=='ai4r-agent-status-v1' and 'error' not in value,'AGENT_STATUS_UNAVAILABLE')
        result=value.get('result')
        require(isinstance(result,dict) and set(result)=={'state','enabled','builder_qualified','capture_healthy'}
            and result['state']=='ready' and result['enabled'] is True and result['capture_healthy'] is True,'ACTUAL_APP_ACCOUNT_OR_CAPTURE_UNAVAILABLE')
        return result


def preflight(target):
    require(os.geteuid()==os.getegid()==10001,'APP_IDENTITY_REQUIRED')
    raw=regular(PROFILE,uid=10001,mode=0o400,maximum=65536)
    require(sha(raw)==target['profile_sha256'],'PRIVATE_PROFILE_HASH')
    profile=json.loads(raw)
    require(set(profile)=={'schema','job_id','instance_id','build_id','candidate_id','store_root','model_socket','session_file','context_refs'}
        and profile['schema']=='ai4r-live-codex-target:1','PRIVATE_PROFILE_SCHEMA')
    require(all(profile[key]==target[key] for key in ('job_id','instance_id','build_id','candidate_id'))
        and profile['store_root']==str(STORE) and profile['model_socket']==str(SOCKET)
        and profile['session_file']==str(SESSION) and set(profile['context_refs'])=={'worker','verifier'},'PRIVATE_PROFILE_IDENTITY')
    session=json.loads(regular(SESSION,uid=10001,mode=0o600,maximum=4096))
    require(set(session)=={'session_id','capability'} and all(isinstance(v,str) and v for v in session.values())
        and session['session_id']==target['instance_id'],'BOOT_SESSION_IDENTITY')
    boot=json.loads(regular('/run/ai4r/instance.json',uid=10001,mode=0o600,maximum=65536))
    require(boot.get('schema')=='ai4r-native-instance:1' and boot.get('boot_id')==target['instance_id'],'ACTUAL_NATIVE_BOOT_IDENTITY')
    raw=regular(MANIFEST,uid=0,maximum=32*1024**2);manifest=json.loads(raw)
    require(manifest.get('schema')=='ai4r-installed-build:2' and manifest.get('build_id')==target['build_id']
        and sha(encoded({k:v for k,v in manifest.items() if k!='build_id'}))==manifest['build_id'],'INSTALLED_BUILD_IDENTITY')
    receipt=json.loads(regular(CLI_RECEIPT,uid=0,maximum=65536));info=CLI.lstat()
    require(not CLI.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o555,'CLI_CUSTODY')
    digest=hashlib.sha256()
    with CLI.open('rb') as stream:
        while chunk:=stream.read(1024**2):digest.update(chunk)
    require(receipt.get('schema')=='ai4r-packaged-codex:1' and receipt.get('package_version')=='0.144.4'
        and digest.hexdigest()==receipt.get('sha256'),'CLI_BYTES_IDENTITY')
    call=subprocess.run([str(CLI),'--version'],stdin=subprocess.DEVNULL,capture_output=True,timeout=10,check=False)
    require(call.returncode==0 and call.stdout.strip()==b'codex-cli 0.144.4','CLI_VERSION_IDENTITY')
    return profile,session


def main():
    # A first fixed public frame permits PID/start-time/code-scoped cleanup if
    # the host times out. It contains no session, account or provider payload.
    args=Path('/proc/self/cmdline').read_bytes().split(b'\0')
    program=args[args.index(b'-c')+1]
    started={'pid':os.getpid(),'start_time':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
        'uid':os.geteuid(),'program_sha256':sha(program)}
    print('AI4R_LIVE_PROBE_START:'+json.dumps(started,sort_keys=True,separators=(',',':')),flush=True)
    capture={'schema':'ai4r-live-bridge-capture:1','outcome':'BLOCKED','effect_attempted':False,'roles':{},'records':[]}
    evidence=None
    try:
        raw=sys.stdin.buffer.read(65537);require(len(raw)<=65536,'PUBLIC_DESCRIPTOR_BOUND')
        target=json.loads(raw);profile,session=preflight(target)
        capture['subscription_status']=subscription_status(session)
        capture['identity']={key:target[key] for key in ('job_id','instance_id','build_id','candidate_id','profile_sha256')}
        evidence=ReadOnlyEvidence();prepared={}
        for role in ('worker','verifier'):
            context=evidence.read(profile['context_refs'][role]);require(set(context)=={'execution_id','call_ordinal'} and context['call_ordinal']==1,'UNCLAIMED_CONTEXT_REQUIRED')
            reservations=evidence.selected('invocation-budget-reservation',context['execution_id']);require(len(reservations)==1,'ACTUAL_RESERVATION_REQUIRED')
            reservation=evidence.read(reservations[0]);contract=evidence.read(reservation['contract_ref']);configuration=evidence.read(contract['configuration_ref'])
            binding=contract['bindings'][0]
            require(binding['role']==role and binding['limits']['model_calls']==1 and 0<binding['limits']['time_s']<=120
                and configuration['cc']['router']['enabled'] is False,'FIXED_BOUNDED_CONTEXT_REQUIRED')
            require(not evidence.selected('model-call-start',context['execution_id']),'UNUSED_LIVE_CONTEXT_REQUIRED')
            prepared[role]=(context,reservations[0],reservation,contract)
        for role,(context,reservation_ref,reservation,contract) in prepared.items():
            row={'context_ref':profile['context_refs'][role],'reservation_ref':reservation_ref,'contract_ref':reservation['contract_ref'],
                'configuration_ref':contract['configuration_ref'],'before_start_refs':[]}
            capture['roles'][role]=row
            row['wrong_token_reply']=exchange(context,session,wrong=True)
            row['wrong_token_start_refs']=evidence.selected('model-call-start',context['execution_id'])
            require(not row['wrong_token_start_refs'] and 'error' in row['wrong_token_reply'],'WRONG_TOKEN_EFFECT')
            capture['effect_attempted']=True;capture['outcome']='OUTCOME_UNKNOWN'
            row['reply']=exchange(context,session)
            row['after_start_refs']=evidence.selected('model-call-start',context['execution_id'])
            if 'result' not in row['reply']:
                # Preserve any actual failed call/route/trace before reporting
                # non-success; a failed model effect is never retried.
                if row['reply'].get('route_ref'):evidence.read(row['reply']['route_ref'])
                if row['reply'].get('call_ref'):
                    failed=evidence.read(row['reply']['call_ref'])
                    for ref in failed.get('evidence_refs',[]):
                        obj=evidence.read(ref)
                        if obj.get('schema')=='ai4r-native-governed-trace:1':
                            for event_ref in obj['event_refs']:evidence.read(evidence.read(event_ref)['raw_ref'])
                for start in row['after_start_refs']:
                    obj=evidence.read(start);evidence.read(obj['input_ref']);evidence.read(obj['call_claim_ref'])
                raise EvidenceError('ACTUAL_MODEL_CALL_NON_SUCCESS')
            result=row['reply']['result'];call=evidence.read(result['call_ref']);evidence.read(result['route_ref'])
            for start in row['after_start_refs']:
                obj=evidence.read(start);evidence.read(obj['input_ref']);evidence.read(obj['call_claim_ref'])
            for ref in call.get('evidence_refs',[]):
                obj=evidence.read(ref)
                if obj.get('schema')=='ai4r-native-governed-trace:1':
                    for event_ref in obj['event_refs']:evidence.read(evidence.read(event_ref)['raw_ref'])
            row['duplicate_reply']=exchange(context,session)
            row['duplicate_start_refs']=evidence.selected('model-call-start',context['execution_id'])
        capture['outcome']='CAPTURED'
    except Exception as error:
        # Stable error class/code only: no profile/session/account values.
        capture['error']=str(error) if isinstance(error,EvidenceError) else type(error).__name__
    finally:
        if evidence is not None:
            capture['records']=list(evidence.rows.values());evidence.db.close()
        print(json.dumps(capture,sort_keys=True,separators=(',',':')),flush=True)
    return 0 if capture['outcome']=='CAPTURED' else 2


if __name__=='__main__':raise SystemExit(main())
