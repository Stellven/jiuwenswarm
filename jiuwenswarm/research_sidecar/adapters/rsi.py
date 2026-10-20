"""Preapproved custodian session reference only; no evaluation power or hidden path."""
import asyncio
import base64
import hashlib
import json
import os
import socket
import stat
import struct
import math
import statistics
from fractions import Fraction
from pathlib import Path
from ..evidence import canonical,write_once
from ..frozen_records import ref_key,strict_json

PUBLIC_KINDS=frozenset({'rsi-session-result','rsi-session','rsi-attempt','rsi-referee-evidence','rsi-evidence-export',
    'model-call','route-record','invocation-observation'})
TRACE_KINDS=frozenset({'model-call-input','model-call-output','model-provider-observation',
    'native-governed-trace','native-governed-trace-event','native-governed-packet'})
PUBLIC_KINDS=PUBLIC_KINDS|TRACE_KINDS


def validate_transport_record(kind,value,validate):
    if kind not in TRACE_KINDS:
        validate(kind,value);return
    if not isinstance(value,dict):raise ValueError('Typed call evidence must be an object')
    if kind in {'model-call-input','model-call-output','model-provider-observation'}:
        payload={'model-call-input':'prompt','model-call-output':'text','model-provider-observation':'observation'}[kind]
        if set(value)!={'id','run_id','invocation_id','call_id',payload} or any(not isinstance(value[k],str) or not value[k] for k in ('id','run_id','invocation_id','call_id')):raise ValueError('Unknown/private model evidence fields')
        if payload!='observation' and not isinstance(value[payload],str):raise ValueError('Model evidence text unavailable')
        if payload=='observation' and (not isinstance(value[payload],dict) or set(value[payload])!={'identity','usage','provider_request_id','observed_runtime'}):raise ValueError('Unknown private provider observation')
    elif kind=='native-governed-packet':
        if str(value.get('method','')).startswith(('account/','login/','auth/')):raise ValueError('Private account packet is not call evidence')
    elif kind=='native-governed-trace':
        if set(value)!={'schema','scope','status','event_refs'} or value['schema']!='ai4r-native-governed-trace:1' or value['status'] not in {'completed','failed','interrupted'} or not isinstance(value['event_refs'],list):raise ValueError('Invalid native summary')
    else:
        if set(value)!={'schema','scope','sequence','direction','method','raw_ref'} or value['schema']!='ai4r-native-governed-trace-event:1' or type(value['sequence']) is not int or value['sequence']<0 or value['direction'] not in {'in','out'} or not isinstance(value['method'],str) or value['method'].startswith(('account/','login/','auth/')):raise ValueError('Invalid/private native event')


def validate_transport_closure(records):
    # Independent finite joins; no client or hidden store.
    by_ref={ref_key(row['ref']):row for row in records};extras={ref_key(row['ref']) for row in records if row['kind'] in TRACE_KINDS}
    if not extras:return # Explicit historical top-level-only export decoding.
    used=set()
    def get(ref,kind=None):
        key=ref_key(ref);row=by_ref.get(key)
        if row is None or kind is not None and row['kind']!=kind:raise ValueError('Original typed call evidence is missing or swapped')
        used.add(key);return row
    for row in records:
        if row['kind']!='model-call':continue
        call=row['record'];observed=[o['record'] for o in records if o['kind']=='invocation-observation' and row['ref'] in o['record']['trace_refs']]
        if len(observed)!=1:raise ValueError('Native evidence needs an exact protected observation')
        observation=observed[0]
        for ref in call['evidence_refs']:
            item=get(ref);kind=item['kind'];value=item['record']
            if kind in {'model-call-input','model-call-output','model-provider-observation'}:
                if value['call_id']!=call['id'] or value['invocation_id']!=call['invocation_id'] or value['run_id']!=observation['run_id']:raise ValueError('Foreign typed model evidence')
                continue
            if kind!='native-governed-trace':raise ValueError('Unexpected/private model evidence')
            scope=value['scope'];required={'run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id','call_id','contract_ref','model_call_start_ref'}
            if (not isinstance(scope,dict) or set(scope)!=required or scope['call_id']!=call['id']
                or any(scope[k]!=call[k] for k in ('execution_id','invocation_id'))
                or any(scope[k]!=observation[k] for k in ('run_id','node_id','subnode_id','attempt_id','contract_ref'))):raise ValueError('Native scope differs from actual call/observation')
            ref_key(scope['model_call_start_ref']);ref_key(scope['contract_ref'])
            for index,event_ref in enumerate(value['event_refs']):
                event=get(event_ref,'native-governed-trace-event')['record']
                if event['scope']!=scope or event['sequence']!=index:raise ValueError('Native event order/scope differs')
                packet=get(event['raw_ref'],'native-governed-packet')['record']
                if 'method' in packet and packet['method']!=event['method']:raise ValueError('Native packet/event method differs')
    if extras-used:raise ValueError('Unbound/private extra trace evidence')



def validate_evidence(result,*,verify_signature,session,attempts,packages=(),activation_claim=False):
    verify_signature(result)
    if activation_claim:raise ValueError('benchmark session cannot grant activation')
    if not attempts or result['attempts_used']!=len(attempts):raise ValueError('actual bounded proposer/child attempts required')
    if result['queries_used']<1:raise ValueError('actual baseline exposure missing')
    if not result['referee_evidence_ref']:
        if result['statistics'] is not None or result['qualified_by']!='none' or packages:raise ValueError('no-final session cannot fabricate statistics or package')
    if packages and result['outcome']!='QUALIFIED':raise ValueError('nonqualified session cannot produce package')
    if result['parent']!=session['parent']:raise ValueError('original parent identity changed')
    return True


async def execute_preapproved(session_ref,host_port):
    if not isinstance(session_ref,dict) or set(session_ref)!={'id','sha256'}:raise ValueError('preapproved immutable custodian session reference required')
    # host_port exposes only start/status/export for this grant, not a command,
    # hidden fixture path, key path or final-query operation.
    return await host_port.start(session_ref)


class JobClient:
    """Route only a granted job identity to its UID-authenticated finite port."""
    def __init__(self,path,peer_uid,job_ref):
        ref_key(job_ref)
        self.path,self.peer_uid,self.job_ref=path,peer_uid,dict(job_ref)
    async def operation(self,operation,*,timeout=30):
        if operation not in {'session_start','session_inspect','session_stop','session_export'}:raise ValueError('finite job operation required')
        info=os.stat(self.path,follow_symlinks=False)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=self.peer_uid or stat.S_IMODE(info.st_mode) not in {0o600,0o660}:raise PermissionError('untrusted workbench port')
        async def exchange():
            reader,writer=await asyncio.open_unix_connection(self.path)
            try:
                sock=writer.get_extra_info('socket')
                if not hasattr(socket,'SO_PEERCRED') or struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]!=self.peer_uid:raise PermissionError('untrusted workbench process')
                raw=canonical({'protocol':'ai4r-rsi-ipc:1','operation':operation,'ref':self.job_ref})
                writer.write(struct.pack('!I',len(raw))+raw);await writer.drain()
                size=struct.unpack('!I',await reader.readexactly(4))[0]
                if not 0<size<=4*1024*1024:raise ValueError('workbench frame policy exceeded')
                reply=strict_json(await reader.readexactly(size))
                if reply.get('protocol')!='ai4r-rsi-ipc:1' or reply.get('status')!='ok':raise ValueError('protected workbench operation unavailable')
                return reply['result']
            finally:
                writer.close();await writer.wait_closed()
        return await asyncio.wait_for(exchange(),timeout)
    async def start(self,ref):
        if ref!=self.job_ref:raise PermissionError('job differs from launcher grant')
        return await self.operation('session_start')


def freeze_public_export(root,value,*,validate):
    """Only public RSI contract records; no recursive fixture/ref traversal."""
    allowed=PUBLIC_KINDS
    if value.get('state')!='terminal' or not isinstance(value.get('records'),list):raise ValueError('actual terminal workbench export required')
    root=Path(root);rows=[];seen=set();decoded=[]
    for entry in value['records']:
        if set(entry)!={'kind','ref','bytes_base64'} or entry['kind'] not in allowed:raise ValueError('unapproved workbench export kind')
        key=ref_key(entry['ref'])
        if key in seen:raise ValueError('duplicate workbench record')
        seen.add(key)
        raw=base64.b64decode(entry['bytes_base64'],validate=True)
        if len(raw)>4*1024*1024 or hashlib.sha256(raw).hexdigest()!=key[1]:raise ValueError('workbench original-byte hash mismatch')
        record=strict_json(raw);validate_transport_record(entry['kind'],record,validate)
        decoded.append({'kind':entry['kind'],'ref':entry['ref'],'record':record})
        name=f"{len(rows):04d}-{entry['kind']}.json"
        rows.append({'kind':entry['kind'],'ref':entry['ref'],'path':name,'sha256':key[1]})
        write_once(root/name,raw)
    validate_transport_closure(decoded)
    write_once(root/'manifest.json',{'schema':'ai4r-rsi-public-export:1','records':rows})
    return rows


def read_public_export(root,*,validate=None):
    from jiuwenswarm.research_records.contracts import ContractData
    from ..evidence import read_verified
    root=Path(root);validate=validate or ContractData().validate
    manifest=strict_json((root/'manifest.json').read_bytes())
    if manifest.get('schema')!='ai4r-rsi-public-export:1':raise ValueError('unsupported workbench export')
    records=[];seen=set()
    for row in manifest['records']:
        if row['kind'] not in PUBLIC_KINDS or ref_key(row['ref']) in seen:raise ValueError('unapproved or duplicate public record')
        seen.add(ref_key(row['ref']))
        if row['sha256']!=row['ref']['sha256']:raise ValueError('public record Ref/hash disagreement')
        value=strict_json(read_verified(root,row));validate_transport_record(row['kind'],value,validate)
        records.append({**row,'record':value})
    validate_transport_closure(records)
    return records


def validate_public_session(records,*,public_key,key_id):
    by_ref={ref_key(e['ref']):e for e in records}
    results=[e for e in records if e['kind']=='rsi-session-result']
    if len(results)!=1:raise ValueError('one exact terminal signed session result required')
    result=results[0]['record'];verify=lambda r:verify_signature(r,public_key,key_id)
    if result['schema_version']!='2.0.0':raise ValueError('Current evidence requires current r2 terminal records')
    session_row=by_ref.get(ref_key(result['session_ref']))
    if not session_row or session_row['kind']!='rsi-session':raise ValueError('exact signed-result session binding unavailable')
    session=session_row['record'];attempts=[]
    for number,pin in enumerate(result['attempt_refs'],1):
        row=by_ref.get(ref_key(pin))
        if not row or row['kind']!='rsi-attempt':raise ValueError('full original attempt chain required')
        attempt=row['record']
        if attempt.get('schema_version')!='2.0.0' or attempt.get('attempt_status') not in {'proposed','rejected'}:raise ValueError('Current attempt status/version is absent')
        if attempt['session_id']!=session['session_id'] or attempt['sequence']!=number or attempt['previous_ref']!=(result['attempt_refs'][number-2] if number>1 else None):raise ValueError('attempt chain is not gapless and exact')
        if attempt['target_ref']!=session['target_profile_ref'] or attempt['configuration_ref']!=session['configuration_ref'] or attempt['hash_profile_ref']!=session['hash_profile_ref'] or attempt['chain_root_ref']!=session['chain_root_ref']:raise ValueError('attempt changed frozen session context')
        if attempts and attempt['parent_ref']!=attempts[0]['parent_ref']:raise ValueError('attempt changed original parent')
        if attempt['queries_used']>result['queries_used']:raise ValueError('fabricated exposure count')
        if attempt['attempt_status']=='proposed':
            if not attempt['child_ref'] or not attempt['diff_ref'] or attempt['child_ref']['sha256']==attempt['parent_ref']['sha256'] or attempt['rejection_reason'] is not None:raise ValueError('Proposed attempt lacks real distinct child/diff')
        elif not attempt['rejection_reason'] or not attempt['failure_evidence_refs']:raise ValueError('Rejected attempt lacks captured failure reason/evidence')
        attempts.append(attempt)
    validate_evidence(result,verify_signature=verify,session=session,attempts=attempts)
    limits=session['limits']
    if result['attempts_used']>limits['max_attempts'] or result['queries_used']>limits['session_query_limit']:raise ValueError('frozen session cap exceeded')
    if result['final_attempt_ref'] and result['final_attempt_ref'] not in result['attempt_refs']:raise ValueError('final candidate is outside the exact chain')
    if result['referee_evidence_ref']:
        row=by_ref.get(ref_key(result['referee_evidence_ref']))
        if not row or row['kind']!='rsi-referee-evidence':raise ValueError('independent final aggregate unavailable')
        referee=row['record'];verify(referee)
        if referee['attempt_ref']!=result['final_attempt_ref'] or referee['final_evaluations']!=1:raise ValueError('final comparison binding/count mismatch')
        attempt=by_ref[ref_key(result['final_attempt_ref'])]['record']
        if attempt['attempt_status']!='proposed' or referee['schema_version']!='2.0.0':raise ValueError('Rejected/historical attempt cannot support a current final comparison')
        if referee['target_ref']!=session['target_profile_ref'] or referee['parent_ref']!=attempt['parent_ref'] or referee['child_ref']!=attempt['child_ref'] or referee['configuration_ref']!=session['configuration_ref']:raise ValueError('final comparison did not use exact original parent/candidate context')
        if result['outcome']=='QUALIFIED' and (referee['violations'] or not referee['mandatory_parent_tests_passed'] or not referee['integrity_passed']):raise ValueError('qualification prerequisites did not pass')
        validate_final_statistics(result,session,referee)
    elif result['final_attempt_ref'] is not None:raise ValueError('no-final session cannot claim final attempt evaluation')
    return True


def validate_final_statistics(result,session,referee):
    """Independent arithmetic from public signed aggregates; no hidden labels."""
    stats=result['statistics'];policy=session['qualification'];repeats=session['pass_count_repeats']
    if stats is None or len(referee['pairs'])!=1 or type(repeats) is not int or repeats not in (1,3):raise ValueError('One exact final aggregate/repetition profile is required')
    pair=referee['pairs'][0];n=pair['total'];g=pair['gain_units'];loss=pair['loss_units']
    times=[*pair['parent_time_s'],*pair['child_time_s']]
    if len(pair['parent_time_s'])!=7 or len(pair['child_time_s'])!=7 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in times):raise ValueError('Every signed final pair requires seven actual positive timing captures')
    if type(n) is not int or n<20 or any(type(v) is not int or v<0 for v in (g,loss)) or g+loss>n:raise ValueError('Invalid independent fixture directions')
    def total(value):
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=n:raise ValueError('Invalid fractional mean total')
        exact=Fraction(round(value*repeats),repeats)
        if float(exact)!=value:raise ValueError('Mean total is outside the frozen repeat grid')
        return exact
    parent,child=total(pair['parent_passed']),total(pair['child_passed'])
    gain=float((child-parent)/n)
    probability=float(Fraction(sum(math.comb(g+loss,k) for k in range(g,g+loss+1)),2**(g+loss))) if g+loss else None
    expected={'fixture_units':n,'parent_passed':pair['parent_passed'],'child_passed':pair['child_passed'],
        'gain_units':g,'loss_units':loss,'pass_rate_gain':gain,'p_value':probability}
    if any(stats[key]!=value for key,value in expected.items()):raise ValueError('Signed statistics differ from the independent aggregate arithmetic')
    if not 0<policy['alpha']<=.05 or policy['min_pass_rate_gain']<.05 or policy['min_timing_gain']<.1 or policy['noise_multiplier']<3 or policy['warmup_batches']!=5 or policy['paired_rounds']!=7:raise ValueError('Frozen qualification policy was widened')
    if result['outcome']=='QUALIFIED':
        if loss or result['qualified_by']=='none':raise ValueError('Regression/unqualified result cannot qualify')
        if result['qualified_by']=='pass_gain':
            if child<=parent or g==0 or gain<policy['min_pass_rate_gain'] or probability is None or probability>policy['alpha']:raise ValueError('Paired mean gain does not qualify')
        elif result['qualified_by']=='timing_tiebreak':
            timing=stats['timing'];p=pair['parent_time_s'];c=pair['child_time_s']
            if timing is None or g or child!=parent or len(p)!=7 or len(c)!=7 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in p+c):raise ValueError('Complete equal-mean timing comparison required')
            pm,cm=statistics.median(p),statistics.median(c);relative=float(1-Fraction(str(cm))/Fraction(str(pm)))
            if timing['parent_median_s']!=pm or timing['child_median_s']!=cm or timing['relative_gain']!=relative or timing['warmup_batches']!=5 or timing['paired_rounds']!=7:raise ValueError('Timing medians/procedure do not recompute')
            if timing['noise_multiplier']!=policy['noise_multiplier'] or timing['min_relative_gain']<policy['min_timing_gain'] or relative<timing['min_relative_gain'] or relative<=policy['noise_multiplier']*timing['calibrated_relative_noise']:raise ValueError('Measured timing gain does not exceed the fixed qualification/noise rule')
        else:raise ValueError('Unknown qualification mode')


def validate_actual_proposer(records):
    """Integration proof requires actual protected calls joined to attempts."""
    by_ref={ref_key(e['ref']):e for e in records};completed=False;owned_calls=set()
    for envelope in [e for e in records if e['kind']=='rsi-attempt']:
        attempt=envelope['record'];trace=[]
        for pin in attempt['observation_refs']:
            row=by_ref.get(ref_key(pin))
            if row is None or row['kind'] not in {'model-call','route-record','invocation-observation'}:raise ValueError('Actual attempted-call trace is missing')
            trace.append(row)
        calls=[e for e in trace if e['kind']=='model-call'];observations=[e for e in trace if e['kind']=='invocation-observation']
        routes=[e['record'] for e in trace if e['kind']=='route-record']
        if attempt['model_calls'] is not None and attempt['model_calls']!=len(calls):raise ValueError('Attempt call count differs from its actual trace')
        for call in calls:
            value=call['record'];owned_calls.add(ref_key(call['ref']))
            if value['observed_runtime'] is not True or value['purpose']!='task_execution':raise ValueError('A declared call is not an observed execution')
            joined=[o['record'] for o in observations if call['ref'] in o['record']['trace_refs']]
            if len(joined)!=1:raise ValueError('Call has no unique protected observation join')
            route=[r for r in routes if r['invocation_id']==value['invocation_id'] and r['route_id']==joined[0]['route_id']]
            if len(route)!=1 or route[0]['route_decision_ref']!=value['route_decision_ref'] or route[0]['model_id']!=value['identity']['requested']:raise ValueError('Call has no exact governed route join')
            completed=completed or value['outcome']=='completed'
    all_calls={ref_key(e['ref']) for e in records if e['kind']=='model-call'}
    if not completed or owned_calls!=all_calls:raise ValueError('A real completed proposer call with full attempted provenance is required')
    return True


def verify_signature(record,public_key,key_id):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if record.get('signer_key_id')!=key_id:raise ValueError('untrusted custodian signer')
    text=record.get('signature')
    if not isinstance(text,str) or len(text)!=86 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for c in text):raise ValueError('invalid custodian signature encoding')
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(base64.urlsafe_b64decode(text+'=='),canonical({k:v for k,v in record.items() if k!='signature'}))
    except Exception:raise ValueError('invalid custodian signature') from None
