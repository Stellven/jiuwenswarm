"""Synthetic one-token prefill evidence; no GPU/model or live timing claims."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import benchmark, prefill_workbench as workbench, prefill_worker as worker
from jiuwenswarm.factory.contract import atomic_json
from jiuwenswarm.factory.lab_recorder import GATE
from test_strata_prefill import v2


@pytest.fixture
def scoped(tmp_path):
    base=v2();base.update(workspace_root=str(tmp_path),assets={})
    files={f'tokenizer/{name}':'a'*64 for name in ('vocab.json','token_type.json','tokenizer.json')}
    return workbench.design(base,[42]*512,files,stage='confirm')


def transcript(c,arm,pp=100,token=42):
    stdout='READY 8192 stop\n'+''.join(f'T {token}\nDONE 1 512 {pp} 0.0 length 0 0 0 0 0\n' for _ in range(7))
    chunk=benchmark.flag(c['arms'][arm]['args'],'--prefill-chunk')
    return stdout,f'ds4: experts per word: 6\nread ahead; prompts in chunks of {chunk})\n'


def cell(c,arm,pp=100,token=42):
    stdout,stderr=transcript(c,arm,pp,token)
    return dict(arm=arm,**workbench.parse_native(stdout,stderr,c,arm))


def retain(c,arm,path,pp=100):
    path.mkdir()
    stdout,stderr=transcript(c,arm,pp)
    (path/'stdout.log').write_text(stdout);(path/'stderr.log').write_text(stderr)
    report=dict(reason='completed',quiescent=True,container_removed=True,container_exit_code=0,
        evidence_completeness='complete',container_oom_killed=False)
    intent=dict(image=c['image']['id'],nonce='b'*32,container_name='factory-lab-'+'c'*32)
    created=dict(Id='d'*64,Image=c['image']['id'],Name='/'+intent['container_name'],
        Config=dict(User=f'{os.getuid()}:{os.getgid()}',Env=[k+'='+v for k,v in c['arms'][arm]['environment'].items()],
            Volumes=None,Tty=False,Entrypoint=['/usr/bin/python3'],
            Labels={'factory.lab.owner':'spark-lab-v1','factory.lab.nonce':intent['nonce']},
            Cmd=['-c',GATE,*benchmark.phase_args(c,arm,'speed')]),
        HostConfig=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='none',IpcMode='private',
            CgroupnsMode='private',Memory=104*2**30,MemorySwap=104*2**30,NanoCpus=8000000000,
            PidsLimit=256,PidMode='',UTSMode='',UsernsMode='',CapDrop=['ALL'],CapAdd=None,
            SecurityOpt=['no-new-privileges:true'],LogConfig={'Type':'none'},
            DeviceRequests=[{'Driver':'cdi','DeviceIDs':['nvidia.com/gpu=0']}]),
        Mounts=[dict(Type='bind',RW=False,Source=str(Path(v).resolve()),Destination=v) for v in c['workload'].values()],
        State=dict(Running=False,Pid=0,ExitCode=0,OOMKilled=False))
    for name,data in [('report.json',report),('intent.json',intent),('inspect-created.json',created),('inspect-final.json',created)]:
        atomic_json(path/name,data)
    wire=b'FACTORY_EXEC\n'+benchmark.protocol(workbench.cases(c),arm,c)
    (path/'stdin-wire.log').write_bytes(wire)
    events=[dict(sequence=i,stream=name,offset=0,retained_bytes=len(data),truncated=False)
        for i,(name,data) in enumerate([('stdin',wire),('stdout',stdout.encode()),('stderr',stderr.encode())])]
    (path/'pipe-events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in events))
    (path/'samples.jsonl').write_text(json.dumps(dict(available_bytes=32*2**30,memory_events={'oom':0,'oom_kill':0}))+'\n')
    return report


def test_design_is_new_scope_and_changes_only_native_chunk(scoped):
    assert scoped['adapter']==workbench.ADAPTER
    assert scoped['order']==list('ABBA')
    assert scoped['arms']['B']==workbench.apply(scoped['arms']['A'],512)['profile']
    assert len(workbench.cases(scoped))==7
    assert set(scoped['execution_sha256'])==set(workbench.EXECUTION_FILES)


@pytest.mark.parametrize('change',['samechunk','twoknobs','draft','order','prompt','maxnew','warmup','pins','tables','timeout'])
def test_contract_changes_fail_closed(scoped,change):
    c=copy.deepcopy(scoped)
    if change=='samechunk':c['arms']['B']=copy.deepcopy(c['arms']['A'])
    elif change=='twoknobs':c['arms']['B']['args'][c['arms']['B']['args'].index('--cpu-threads')+1]='4'
    elif change=='draft':c['arms']['A']['args'][c['arms']['A']['args'].index('--dspark')+1]='on'
    elif change=='order':c['order']=list('AABB')
    elif change=='prompt':c['prompt']['ids'][0]=99
    elif change=='maxnew':c['max_new_tokens']=True
    elif change=='warmup':c['warmup_requests']=1
    elif change=='pins':c['execution_sha256'].pop('prefill_worker.py')
    elif change=='tables':c['prompt']['tokenizer_files'].pop('tokenizer/vocab.json')
    elif change=='timeout':c['limits']['timeout_s']=301
    with pytest.raises(ValueError):workbench.validate_contract(c)


def test_parser_retains_zero_decode_without_inventing_decode_rate(scoped):
    result=cell(scoped,'A')
    assert result['effective_experts']==6 and result['effective_prefill_chunk']==256
    assert result['requests'][0]['decode_ms']==0
    assert 'decode_tps' not in result['requests'][0]


@pytest.mark.parametrize('change',['chunk','fullsix','draft','reused','negative','missing','extra','eos'])
def test_raw_protocol_rejects_missing_or_incorrect_engagement(scoped,change):
    stdout,stderr=transcript(scoped,'A')
    if change=='chunk':stderr=stderr.replace('256','512')
    elif change=='fullsix':stderr=stderr.replace('word: 6','word: 5')
    elif change=='draft':stdout=stdout.replace('length 0 0','length 0 1')
    elif change=='reused':stdout=stdout.replace('0 0 0 0 0','0 0 1 0 0')
    elif change=='negative':stdout=stdout.replace('100 0.0','-1 0.0')
    elif change=='missing':stdout='\n'.join(stdout.splitlines()[:-1])
    elif change=='extra':stdout+='T 42\n'
    elif change=='eos':stdout=stdout.replace('T 42','T 1')
    with pytest.raises(ValueError):workbench.parse_native(stdout,stderr,scoped,'A')


def test_confirm_scope_signal_excludes_warmups_and_requires_cell_separation(scoped):
    cells=[cell(scoped,arm,100 if arm=='A' else 80) for arm in scoped['order']]
    for item in cells:
        for row in item['requests'][:4]:row['prefill_ms']=100000
    result=workbench.analyze(scoped,cells)
    assert result['verdict']=='scoped_improvement'
    assert result['prefill']['speedup_A_over_B']==1.25
    assert result['promotion_authorized'] is False and result['full_quality_claim'] is False
    cells[-1]=cell(scoped,'A',70)
    assert workbench.analyze(scoped,cells)['verdict']=='no_scoped_improvement'


def test_cross_arm_single_token_disagreement_rejects_scoped_signal(scoped):
    cells=[cell(scoped,arm,100 if arm=='A' else 80,42 if arm=='A' else 43) for arm in scoped['order']]
    result=workbench.analyze(scoped,cells)
    assert result['verdict']=='scoped_correctness_failed'
    assert result['prefill']['scope_performance_signal'] is False


def test_screen_has_no_performance_acceptance(scoped):
    scoped.update(stage='screen',order=list('AB'))
    result=workbench.analyze(scoped,[cell(scoped,'A',100),cell(scoped,'B',50)])
    assert result['verdict']=='screen_complete'
    assert result['prefill']['screen_trend'] is True
    assert result['prefill']['scope_performance_signal'] is False


@pytest.mark.parametrize('change',['argv','observer','oom','wire','truncated','cleanup'])
def test_independent_boundary_rejects_forged_or_incomplete_cell(scoped,tmp_path,change):
    path=tmp_path/'cell';retain(scoped,'A',path)
    if change in ('argv','observer'):
        p=path/'inspect-created.json';value=json.loads(p.read_text())
        if change=='argv':value['Config']['Cmd'].append('--skip-layer')
        else:value['Config']['Env'].append('DS4_PROF=1')
        atomic_json(p,value)
    elif change=='oom':atomic_json(path/'samples.jsonl',dict(available_bytes=32*2**30,memory_events={'oom':1}))
    elif change=='wire':(path/'stdin-wire.log').write_bytes(b'FACTORY_EXEC\nQUIT\n')
    elif change=='truncated':
        p=path/'pipe-events.jsonl';p.write_text(p.read_text().replace('false','true'))
    elif change=='cleanup':
        p=path/'report.json';value=json.loads(p.read_text());value['container_removed']=False;atomic_json(p,value)
    with pytest.raises((ValueError,RuntimeError)):workbench.verify_cell(scoped,'A',path)


@pytest.fixture
def campaign(scoped,tmp_path,monkeypatch):
    scoped.update(stage='screen',order=list('AB'))
    path=tmp_path/'contract.json';atomic_json(path,scoped)
    launches=[]
    def record(argv,**kwargs):
        launches.append(kwargs)
        arm='A' if benchmark.flag(argv,'--prefill-chunk')=='256' else 'B'
        return retain(scoped,arm,kwargs['output'],100 if arm=='A' else 80)
    monkeypatch.setattr(worker.lab_recorder,'run_container',record)
    monkeypatch.setattr(worker,'admission',lambda image:dict(available_bytes=110*2**30))
    monkeypatch.setattr(workbench,'verify_inputs',lambda c:{'assets':'synthetic'})
    monkeypatch.delenv('FACTORY_PREFILL_QUIET_ROOT',raising=False)
    monkeypatch.setenv('FACTORY_HOME',str(tmp_path/'factory'))
    return SimpleNamespace(c=scoped,path=path,output=tmp_path/'output',launches=launches)


def test_fresh_process_worker_uses_shared_guards_and_revalidates_raw_output(campaign):
    c=campaign
    assert worker.run(c.path,c.output,'task','attempt',workbench.sha(c.path))==0
    assert len(c.launches)==2
    assert all(v['gpu'] and v['cpus']==8 and v['guard_gib']==8 and v['memory_bytes']==104*2**30 for v in c.launches)
    assert all(v['protocol'].count(b'GEN 1 ')==7 and b'spec=0' in v['protocol'] for v in c.launches)
    result=workbench.analyze_files(c.c,c.output,task_id='task',attempt_id='attempt')
    assert result['verification']['raw_files_verified'] is True
    assert result['verdict']=='screen_complete'
    with pytest.raises(ValueError,match='identity/coverage'):
        workbench.analyze_files(c.c,c.output,task_id='copied-task',attempt_id='attempt')
    (c.output/'cell-001-A/prefill/stdout.log').write_text('forged')
    with pytest.raises(ValueError,match='Changed'):
        workbench.analyze_files(c.c,c.output,task_id='task',attempt_id='attempt')


def test_worker_preserves_partial_evidence_and_stops_after_failure(campaign,monkeypatch):
    def failed(argv,**kwargs):
        kwargs['output'].mkdir()
        return dict(reason='guard_low_memory',quiescent=True,container_removed=True)
    monkeypatch.setattr(worker.lab_recorder,'run_container',failed)
    assert worker.run(campaign.path,campaign.output,'task','attempt',workbench.sha(campaign.path))==1
    result=json.loads((campaign.output/'campaign.json').read_text())
    assert result['evidence_completeness']=='partial' and len(result['cells'])==1


def test_preoccupied_observation_cannot_substitute_for_raw_result(store,scoped,monkeypatch):
    manager=workbench.Workbench(store)
    attempt=dict(attempt_id='owned',state='succeeded',request={'contract':scoped})
    monkeypatch.setattr(manager,'status',lambda *args:attempt)
    monkeypatch.setattr(workbench,'analyze_files',lambda *args,**kwargs:dict(verdict='no_scoped_improvement'))
    store.append_observation('t',dict(obs_id='owned:observation',kind='untrusted',values={'verdict':'scoped_improvement'}))
    with pytest.raises(ValueError,match='occupied'):
        manager.result('t','owned')
