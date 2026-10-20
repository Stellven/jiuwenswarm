"""Independent public evidence controls; fixtures authorize no live effect."""
import base64
import json
from pathlib import Path

import pytest

from scripts.research_live_bridge import LiveBlocked, run_probe, validate_target
from scripts.research_live_bridge_probe import EvidenceError, check_capture, encoded, sha


def target():
    return {'schema':'ai4r-live-bridge-host-target:1','job_id':'ai4r-live-codex-test',
        'project':'ai4r-live-test','container_id':'a'*64,'image_id':'sha256:'+'b'*64,
        'build_id':'c'*64,'instance_id':'boot-test','candidate_id':'d'*64,'platform':'linux/amd64',
        'source_build_pin':{'path':'/public/receipt.json','sha256':'e'*64},'profile_sha256':'f'*64}


def capture_fixture(*,bad_role=False,telemetry=False,reused_thread=False,foreign_scope=False):
    records=[]
    def add(value,kind=None):
        raw=encoded(value);ref={'id':'blob:'+sha(raw),'sha256':sha(raw)}
        if not any(row['ref']==ref for row in records):
            records.append({'ref':ref,'kind':kind,'record_sequence':len(records)+1 if kind else None,
                'raw_b64':base64.b64encode(raw).decode()})
        return ref
    roles={}
    for role in ('worker','verifier'):
        context={'execution_id':'execution-'+role,'call_ordinal':1};context_ref=add(context)
        config_ref=add({'cc':{'router':{'enabled':False}}})
        contract_ref=add({'run_id':'run','node_id':'node','subnode_id':role,'attempt_id':'attempt',
            'configuration_ref':config_ref,'bindings':[{'role':'verifier' if bad_role else role,'limits':{'time_s':30,'model_calls':1}}]})
        reservation_ref=add({'execution_id':context['execution_id'],'invocation_id':'invocation-'+role,
            'contract_ref':contract_ref},'invocation-budget-reservation')
        route_ref=add({'schema_version':'1.0.0','model_id':'codex-cli-default','invocation_id':'invocation-'+role,
            'run_id':'run','node_id':'node','subnode_id':role,'router_enabled':False,'route_id':'route-'+role,
            'decision_source':'codex_router_disabled','router_failure':None,'route_decision_ref':None,
            'recorded_at':'2026-10-17T00:00:00Z'},'route-record')
        input_ref=add({'prompt':'Return the single word OK.','call_id':'call-'+role},'model-call-input')
        claim_ref=add({'execution_id':context['execution_id'],'invocation_id':'invocation-'+role,
            'contract_ref':contract_ref,'call_id':'call-'+role,'call_ordinal':1},'model-call-claim')
        start_ref=add({'execution_id':context['execution_id'],'invocation_id':'invocation-'+role,
            'call_id':'call-'+role,'contract_ref':contract_ref,'route_ref':route_ref,'input_ref':input_ref,
            'call_claim_ref':claim_ref},'model-call-start')
        scope={'run_id':'run','node_id':'node','subnode_id':role,'attempt_id':'attempt',
            'execution_id':context['execution_id'],'invocation_id':'invocation-'+role,'call_id':'call-'+role,
            'contract_ref':contract_ref,'model_call_start_ref':start_ref}
        if foreign_scope:scope['run_id']='foreign'
        events=[]
        for index,method in enumerate(('thread/start','turn/start')):
            params={'input':'Return the single word OK.'}
            if telemetry:params['execution_id']='private-telemetry'
            raw_ref=add({'id':index,'method':method,'params':params})
            events.append(add({'schema':'ai4r-native-governed-trace-event:1','scope':scope,
                'sequence':index,'direction':'out','method':method,'raw_ref':raw_ref},'native-governed-trace-event'))
        response_ref=add({'id':0,'result':{'thread':{'id':'same-thread' if reused_thread else 'fresh-thread-'+role}}})
        events.append(add({'schema':'ai4r-native-governed-trace-event:1','scope':scope,
            'sequence':2,'direction':'in','method':'thread/start','raw_ref':response_ref},'native-governed-trace-event'))
        trace_ref=add({'schema':'ai4r-native-governed-trace:1','scope':scope,'status':'completed',
            'event_refs':events},'native-governed-trace')
        call_ref=add({'schema_version':'1.0.0','id':'call-'+role,'route_attempt_id':'attempt-'+role,
            'route_decision_ref':None,'purpose':'task_execution','deployment_ref':config_ref,'model_selection_profile_ref':config_ref,
            'provider_request_id':None,'started_at':'2026-10-17T00:00:00Z','ended_at':'2026-10-17T00:00:01Z',
            'provider_error_code':None,'observed_runtime':True,'execution_id':context['execution_id'],'invocation_id':'invocation-'+role,
            'call_function':role,'outcome':'completed','identity':{'requested':'codex-cli-default','effective':None,'basis':'unavailable'},
            'usage':{'input_tokens':None,'output_tokens':None,'cost_amount':None,'currency':None,
                'unavailable_reasons':['input_tokens: controlled unavailable','output_tokens: controlled unavailable',
                    'cost_amount: controlled unavailable','currency: controlled unavailable']},'evidence_refs':[input_ref,trace_ref]},'model-call')
        roles[role]={'context_ref':context_ref,'reservation_ref':reservation_ref,'contract_ref':contract_ref,
            'configuration_ref':config_ref,'before_start_refs':[],'wrong_token_start_refs':[],
            'after_start_refs':[start_ref],'duplicate_start_refs':[start_ref],
            'wrong_token_reply':{'error':'DELIVERY_UNKNOWN'},'duplicate_reply':{'error':'PLATFORM_INTEGRITY_FAULT'},
            'reply':{'protocol':'ai4r-model-ipc:1','result':{'call_ref':call_ref,'route_ref':route_ref}}}
    return {'schema':'ai4r-live-bridge-capture:1','outcome':'CAPTURED',
        'subscription_status':{'state':'ready','enabled':True,'builder_qualified':False,'capture_healthy':True},
        'identity':{key:target()[key] for key in
        ('job_id','instance_id','build_id','candidate_id','profile_sha256')},'roles':roles,'records':records}


def replace_record(capture,ref,mutator):
    row=next(row for row in capture['records'] if row['ref']==ref)
    value=json.loads(base64.b64decode(row['raw_b64']));mutator(value)
    # Deliberately retain the original Ref, proving independent byte validation.
    row['raw_b64']=base64.b64encode(encoded(value)).decode()


def test_closed_descriptor_accepts_only_public_finite_identity():
    assert validate_target(target())==target()
    for key,value in [('command',['sh']),('model_socket','/other'),('profile_path','/other')]:
        with pytest.raises(LiveBlocked):validate_target(target()|{key:value})


@pytest.mark.parametrize('field,value',[('container_id','foreign'),('image_id','latest'),('platform','windows/amd64'),
    ('job_id','unowned'),('profile_sha256','0'),('source_build_pin',{'path':'/public/private.json','sha256':'e'*64})])
def test_invalid_descriptor_cannot_reach_docker(field,value):
    with pytest.raises(LiveBlocked):validate_target(target()|{field:value})


def test_absent_target_is_explicit_blocked_and_never_constructs_host(tmp_path):
    class NoDocker:
        def __getattr__(self,name):raise AssertionError('No Docker or model effect is permitted')
    result=run_probe(tmp_path,None,tmp_path/'evidence',host=NoDocker())
    assert result['outcome']=='BLOCKED' and result['effect_attempted'] is False
    assert result['error']=='OWNED_LIVE_TARGET_REQUIRED'


def test_capture_recomputes_original_bytes_joins_both_roles_and_negative_counts():
    result=check_capture(capture_fixture(),target())
    assert set(result)=={'worker','verifier'} and all(all(row.values()) for row in result.values())


@pytest.mark.parametrize('option,reason',[('bad_role','FIXED_BOUNDED_ROLE_REQUIRED'),
    ('telemetry','TELEMETRY_PROVIDER_NONINTERFERENCE'),('reused_thread','TWO_FRESH_GOVERNED_THREADS_REQUIRED'),
    ('foreign_scope','TRACE_SCOPE_JOIN')])
def test_validly_hashed_bytes_still_require_source_semantic_joins(option,reason):
    with pytest.raises(EvidenceError,match=reason):check_capture(capture_fixture(**{option:True}),target())


def test_frozen_program_executes_without_site_or_product_import_and_blocks_wrong_uid():
    import os,subprocess,sys
    if os.geteuid()==10001:pytest.fail('This controlled no-profile population requires its verification UID')
    program=Path('scripts/research_live_bridge_probe.py').read_bytes()
    run=subprocess.run([sys.executable,'-I','-S','-c',program.decode()],input=encoded(target()),capture_output=True,timeout=10)
    assert run.returncode==2 and not run.stderr
    header,body=run.stdout.splitlines();capture=json.loads(body)
    assert header.startswith(b'AI4R_LIVE_PROBE_START:')
    assert capture['outcome']=='BLOCKED' and not capture['effect_attempted'] and capture['records']==[]
    assert capture['error']=='APP_IDENTITY_REQUIRED'


def host_fixture(tmp_path,monkeypatch):
    from scripts import research_live_bridge as module
    from scripts.research_candidate import capture_candidate
    root=tmp_path/'source';root.mkdir();(root/'LICENSE').write_text('controlled public source\n')
    (root/'scripts').mkdir()
    for name in ('research_live_bridge.py','research_live_bridge_probe.py','research_image_closure_probe.py'):
        (root/'scripts'/name).write_bytes(Path('scripts',name).read_bytes())
    candidate=capture_candidate(root);frozen=root/'.test_logs/m1/controlled/app-production';frozen.mkdir(parents=True)
    (frozen/'candidate.json').write_bytes(encoded(candidate))
    build_raw=encoded({'schema':'ai4r-source-build:1','outcome':'BUILT','target':'app-production','platform':'linux/amd64',
        'image':{'image_id':target()['image_id']},'candidate_id':candidate['candidate_id']});(frozen/'receipt.json').write_bytes(build_raw)
    value=target()|{'candidate_id':candidate['candidate_id'],
        'source_build_pin':{'path':str(frozen/'receipt.json'),'sha256':sha(build_raw)}}
    path=tmp_path/'target.json';path.write_bytes(encoded(value))
    class Host:
        prefix=['docker','--context','default']
        def json(self,args):
            if args[0]=='image':return [{'Id':value['image_id'],'Os':'linux','Architecture':'amd64','Config':{'Entrypoint':['native'],'Cmd':[]}}]
            return [{'Id':value['container_id'],'Image':value['image_id'],'State':{'Running':True,'StartedAt':'original'},
                'HostConfig':{'Privileged':False,'ReadonlyRootfs':True},'Mounts':[],
                'Config':{'Entrypoint':['native'],'Cmd':[],'Labels':{'ai4r.owner':value['job_id'],
                    'com.docker.compose.project':value['project'],'com.docker.compose.service':'app'}}}]
    monkeypatch.setattr(module,'inspect_closure',lambda *args,**kwargs:{'qualified':True,'image_id':value['image_id'],'candidate_id':value['candidate_id']})
    return module,root,path,value,Host()


def test_host_dispatch_control_failure_is_unknown_and_never_retried(tmp_path,monkeypatch):
    module,root,path,value,host=host_fixture(tmp_path,monkeypatch);calls=[]
    def launch(command,**kwargs):calls.append(command);raise OSError('controlled host dispatch failure')
    monkeypatch.setattr(module,'_execute',launch)
    result=module.run_probe(root,path,tmp_path/'evidence',host=host)
    assert result['outcome']=='OUTCOME_UNKNOWN' and result['effect_attempted'] is True
    assert len(calls)==1 and calls[0][3:7]==['exec','-i','--user','10001:10001']
    assert calls[0][-4:-1]==['-I','-S','-c']


def test_host_timeout_cleans_only_exact_probe_identity_and_retains_model_unknown(tmp_path,monkeypatch):
    import subprocess
    module,root,path,value,host=host_fixture(tmp_path,monkeypatch);calls=[]
    program=Path('scripts/research_live_bridge_probe.py').read_bytes()
    start={'pid':123,'start_time':'456','uid':10001,'program_sha256':sha(program)}
    def launch(command,**kwargs):
        calls.append((command,kwargs['input']))
        if len(calls)==1:raise subprocess.TimeoutExpired(command,300,output=b'AI4R_LIVE_PROBE_START:'+encoded(start)+b'\n')
        return subprocess.CompletedProcess(command,0,encoded({'attempted':True,'confirmed':True}),b'')
    monkeypatch.setattr(module,'_execute',launch)
    result=module.run_probe(root,path,tmp_path/'evidence',host=host)
    assert result['outcome']=='OUTCOME_UNKNOWN' and result['cleanup']=={'attempted':True,'confirmed':True}
    assert result['model_containment']=='UNRESOLVED_DISCONNECT_IS_NOT_CANCELLATION'
    assert len(calls)==2 and calls[1][0][-1]==module.PROBE_CLEANUP and json.loads(calls[1][1])==start


def test_host_success_keeps_full_v10_incomplete_and_records_exact_fixed_command(tmp_path,monkeypatch):
    import subprocess
    module,root,path,value,host=host_fixture(tmp_path,monkeypatch)
    capture=capture_fixture();capture['identity']={key:value[key] for key in capture['identity']}
    program=Path('scripts/research_live_bridge_probe.py').read_bytes()
    start={'pid':123,'start_time':'456','uid':10001,'program_sha256':sha(program)}
    def launch(command,**options):
        assert options['input']==encoded(value)
        return subprocess.CompletedProcess(command,0,b'AI4R_LIVE_PROBE_START:'+encoded(start)+b'\n'+encoded(capture)+b'\n',b'')
    monkeypatch.setattr(module,'_execute',launch)
    result=module.run_probe(root,path,tmp_path/'evidence',host=host)
    assert result['outcome']=='CAPTURED' and result['complete_v10'] is False
    assert result['checkout_current_before'] and result['checkout_current_after'] and result['target_unchanged']
    assert result['program_sha256']==sha(program)


def receipt_fixture(tmp_path):
    """Synthetic public formats exercise replay predicates, not image truth."""
    from scripts.research_candidate import capture_candidate
    from scripts.research_image_closure_probe import CHECKS
    source=tmp_path/'source';source.mkdir();(source/'LICENSE').write_bytes(b'controlled license')
    (source/'scripts').mkdir()
    for name in ('research_live_bridge.py','research_live_bridge_probe.py','research_image_closure_probe.py'):
        (source/'scripts'/name).write_bytes(Path('scripts',name).read_bytes())
    candidate=capture_candidate(source,snapshot=tmp_path/'source.zip')
    value=target()|{'candidate_id':candidate['candidate_id']}
    build={'schema':'ai4r-source-build:1','outcome':'BUILT','target':'app-production','candidate_id':value['candidate_id'],
        'context':{'sha256':'1'*64},'snapshot_sha256':candidate['snapshot']['sha256'],'image':{'image_id':value['image_id']}}
    build_raw=encoded(build);value['source_build_pin']={'path':'/public/receipt.json','sha256':sha(build_raw)}
    directory=tmp_path/'receipt';directory.mkdir();closure_dir=directory/'closure';closure_dir.mkdir()
    (directory/'source-build-receipt.json').write_bytes(build_raw);(directory/'target.json').write_bytes(encoded(value))
    joins={key:value[key] for key in ('candidate_id','image_id','build_id','platform')}
    joins['source_build_receipt_sha256']=value['source_build_pin']['sha256']
    observation={'schema':'ai4r-installed-closure-observation:1','mode':'installed','joins':joins,
        'installed_build_id':value['build_id'],'assertions':{key:True for key in CHECKS}}
    observation_raw=encoded(observation);input_raw=encoded({'candidate':candidate})
    (closure_dir/'image-closure.stdout.json').write_bytes(observation_raw)
    (closure_dir/'image-closure-input.json').write_bytes(input_raw)
    closure={'image_id':value['image_id'],'candidate_id':value['candidate_id'],'context_sha256':'1'*64,
        'snapshot_sha256':candidate['snapshot']['sha256'],'input_sha256':sha(input_raw),'stdout_sha256':sha(observation_raw),
        'program_sha256':sha(Path('scripts/research_image_closure_probe.py').read_bytes()),'returncode':0,
        'cleanup':{'confirmed':True},'observation':observation}
    (closure_dir/'result.json').write_bytes(encoded(closure))
    capture=capture_fixture();capture['identity']={key:value[key] for key in capture['identity']}
    program=Path('scripts/research_live_bridge_probe.py').read_bytes()
    start={'pid':123,'start_time':'456','uid':10001,'program_sha256':sha(program)}
    raw=b'AI4R_LIVE_PROBE_START:'+encoded(start)+b'\n'+encoded(capture)+b'\n'
    (directory/'probe.stdout.jsonl').write_bytes(raw);(directory/'probe.stderr.log').write_bytes(b'')
    command=['docker','--context','default','exec','-i','--user','10001:10001',value['container_id'],
        '/usr/local/bin/python3','-I','-S','-c',program.decode()]
    (directory/'command.json').write_bytes(encoded(command))
    receipt={'schema':'ai4r-live-bridge-host-receipt:1','outcome':'CAPTURED','program_sha256':sha(program),
        'input_sha256':sha(encoded(value)),'stdout_sha256':sha(raw),'stderr_sha256':sha(b''),'target_sha256':sha(encoded(value)),
        'command_sha256':sha(encoded(command)),'returncode':0,'checkout_current_before':True,'checkout_current_after':True,
        'target_unchanged':True,'cleanup':{'attempted':False,'confirmed':True},'closure_sha256':sha(encoded(closure))}
    path=directory/'receipt.json';path.write_bytes(encoded(receipt));return path


def test_outside_consumer_recomputes_original_public_formats_without_dispatch_or_acceptance(tmp_path,monkeypatch):
    from scripts import research_live_bridge as module
    path=receipt_fixture(tmp_path)
    monkeypatch.setattr(module,'_execute',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('Read-only consumer')))
    result=module.validate_receipt(path)
    assert set(result['roles'])=={'worker','verifier'} and result['complete_v10'] is False


@pytest.mark.parametrize('name',['command.json','probe.stdout.jsonl','source-build-receipt.json','closure/image-closure-input.json',
    'closure/image-closure.stdout.json','closure/result.json'])
def test_outside_consumer_rejects_each_changed_original_input(tmp_path,name):
    from scripts import research_live_bridge as module
    path=receipt_fixture(tmp_path);artifact=path.parent/name;artifact.write_bytes(artifact.read_bytes()+b' ')
    with pytest.raises((LiveBlocked,ValueError)):module.validate_receipt(path)


@pytest.mark.parametrize('change',['owner','entrypoint','source_overlay','docker_socket','writable_root'])
def test_actual_target_inspection_denies_nonfrozen_or_foreign_boundary(tmp_path,monkeypatch,change):
    module,root,path,value,host=host_fixture(tmp_path,monkeypatch)
    original=host.json
    def inspect(args):
        rows=original(args)
        if args[0]=='container':
            item=rows[0]
            if change=='owner':item['Config']['Labels']['ai4r.owner']='foreign'
            elif change=='entrypoint':item['Config']['Entrypoint']=['sh']
            elif change=='source_overlay':item['Mounts']=[{'Destination':'/opt/ai4r','Source':'/public/source'}]
            elif change=='docker_socket':item['Mounts']=[{'Destination':'/var/run/docker.sock','Source':'/var/run/docker.sock'}]
            else:item['HostConfig']['ReadonlyRootfs']=False
        return rows
    host.json=inspect
    monkeypatch.setattr(module,'_execute',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('No effect before inspection')))
    result=module.run_probe(root,path,tmp_path/'evidence',host=host)
    assert result['outcome']=='BLOCKED' and result['effect_attempted'] is False


@pytest.mark.parametrize('mutation',['bytes','kind','missing_trace','second_start','telemetry','foreign_scope','prompt','role'])
def test_forged_or_incomplete_public_evidence_never_becomes_live_pass(mutation):
    value=capture_fixture();role=value['roles']['worker']
    if mutation=='bytes':value['records'][0]['raw_b64']=base64.b64encode(b'{}').decode()
    elif mutation=='kind':next(row for row in value['records'] if row['ref']==role['after_start_refs'][0])['kind']='raw-blob'
    elif mutation=='missing_trace':value['records']=[row for row in value['records'] if row['kind']!='native-governed-trace']
    elif mutation=='second_start':role['duplicate_start_refs']=[]
    else:
        call_ref=role['reply']['result']['call_ref'];call=json.loads(base64.b64decode(next(row for row in value['records'] if row['ref']==call_ref)['raw_b64']))
        trace=next(row for row in value['records'] if row['kind']=='native-governed-trace')
        if mutation=='foreign_scope':replace_record(value,trace['ref'],lambda obj:obj['scope'].update(execution_id='foreign'))
        elif mutation=='role':replace_record(value,call_ref,lambda obj:obj.update(call_function='verifier'))
        elif mutation=='prompt':replace_record(value,role['after_start_refs'][0],lambda obj:obj.update(input_ref={'id':'missing','sha256':'0'*64}))
        else:
            event=next(row for row in value['records'] if row['kind']=='native-governed-trace-event')
            packet_ref=json.loads(base64.b64decode(event['raw_b64']))['raw_ref']
            replace_record(value,packet_ref,lambda obj:obj['params'].update(run_id='telemetry'))
    with pytest.raises(EvidenceError):check_capture(value,target())
