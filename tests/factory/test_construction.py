"""Construction regression: actual hosts/files/processes; no GPU claims."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.ccv2.roles import read_roles
from jiuwenswarm.factory import execution_binding as binding
from jiuwenswarm.factory.experiment_jobs import bounded_run

ROOT=Path(__file__).resolve().parents[2]
CCS=ROOT/'jiuwenswarm/factory/ccs'


def baseline():
    sys.path.insert(0,str(CCS/'performance_baseline'))
    spec=importlib.util.spec_from_file_location('baseline_components',CCS/'performance_baseline/components.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_canonical_roles_and_sealed_component(tmp_path):
    from jiuwenswarm.factory.components import load
    host=Host(tmp_path/'ccstore')
    release=host.seal(CCS/'expert_streaming/components/expert_fill')
    declaration,bundle=host.release(release)
    assert read_roles(declaration,bundle)['materials']['component']=='component'
    assert load('expert_fill',host=host,release=release)
    assert all('kind' not in value for value in declaration['materials'].values())
    (bundle/'component.yaml').write_text('{}')
    with pytest.raises(Exception,match='differ|DIGEST'):
        load('expert_fill',host=host,release=release)


def test_binding_rejects_backend_dependency_and_manifest_drift(tmp_path):
    host=Host(tmp_path/'ccstore'); release=host.seal(CCS/'performance_baseline')
    source=tmp_path/'source';source.mkdir();(source/'backend.py').write_text('value=1\n')
    frozen=binding.freeze(source,tmp_path/'frozen')
    lock=tmp_path/'dependencies.lock';lock.write_text('stdlib')
    runtime=dict(python=sys.executable,sha256=binding.file_digest(sys.executable),dependencies={str(lock):binding.file_digest(lock)})
    record=binding.create(host,release,frozen,runtime)
    assert binding.verify(host,record,backend_root=tmp_path/'frozen')==record['binding_id']
    (source/'backend.py').write_text('value=2\n')
    assert binding.verify(host,record) # mutable original does not affect frozen backend
    lock.write_text('tampered')
    with pytest.raises(ValueError,match='Dependency'): binding.verify(host,record)
    lock.write_text('stdlib');(tmp_path/'frozen/backend.py').write_text('value=3\n')
    with pytest.raises(ValueError,match='snapshot'): binding.verify(host,record)


def test_output_overrun_and_timeout_retain_partial_logs(tmp_path):
    result=bounded_run([sys.executable,'-c','import sys;print("x"*10000);sys.stderr.write("failure")'],tmp_path,2,512)
    assert result['stop_reason']=='output_limit'
    assert sum((tmp_path/name).stat().st_size for name in ('stdout','stderr'))==512
    result=bounded_run([sys.executable,'-c','import time;print("partial",flush=True);time.sleep(10)'],tmp_path,.1,512)
    assert result['stop_reason']=='timeout'
    assert b'partial' in (tmp_path/'stdout').read_bytes()


def test_replay_capacity_compulsory_work_and_readiness():
    module=baseline()
    result=module.replay([[0,1],[1,2],[0,1]],4,8,4,[1,1,1])
    assert result['page_reads']==4 and result['elapsed_s']==7
    assert result['schedule'][0]['ready_s']==2
    assert all(len(step['resident_pages'])<=2 for step in result['schedule'])
    assert result['globally_optimal'] is False
    with pytest.raises(ValueError,match='Compulsory'): module.replay([[0,1]],4,4,4,[0])


def test_ceiling_precision_and_missing_evidence():
    module=baseline();work=dict(flops=100,memory_bytes=200,dependency_s=1,precision='fp32',sparsity='dense')
    calibration=dict(flops_per_s=50,memory_bytes_per_s=50,precision='fp32',sparsity='dense',kind='measured')
    result=module.ceilings(work,calibration)
    assert result['ideal_expert_availability_reference']['minimum_seconds']==4
    assert result['measured_strata_baseline'] is None
    assert result['gaps']
    del calibration['flops_per_s']
    assert module.ceilings(work,calibration)['ideal_expert_availability_reference']['minimum_seconds'] is None
    calibration['precision']='fp16'
    with pytest.raises(ValueError,match='path differs'): module.ceilings(work,calibration)


def test_model_preserves_experts_and_packed_bytes():
    module=baseline()
    model=dict(identity='pinned',demanded_experts=6,layers=2,kv_heads=2,head_dimension=4,kv_element_bytes=2,
               tensors=[dict(shape=[4,8],block_elements=8,block_bytes=4,bytes=16,numerical_path='iq2')])
    hardware=dict(usable_memory_bytes=1024,supported_paths=['iq2'])
    workload=dict(demanded_experts=6,context=8,batch=1)
    result=module.inspect(model,hardware,workload)
    assert result['kv_bytes']==512 and result['weight_bytes']==16
    workload['demanded_experts']=5
    with pytest.raises(ValueError,match='Every demanded'): module.inspect(model,hardware,workload)


def test_baseline_native_runner(tmp_path):
    host=Host(tmp_path/'store',session_grants=['process.exec'])
    release=host.prepare(CCS/'performance_baseline')
    if isinstance(release,dict): release=release['release']
    receipt=host.call(release,'replay',dict(trace=[[0],[1],[0]],page_bytes=4,capacity_bytes=4,storage_bytes_per_s=4,compute_seconds=[0,0,0]))
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['result']['page_reads']==3


def prepared_loop(tmp_path):
    from jiuwenswarm.factory.store import Store
    from jiuwenswarm.factory.loop import FactoryLoop
    from tests.factory.test_loop import FakeBenchmark
    store=Store(tmp_path/'factory')
    host=Host(store.home/'ccstore');release=host.seal(CCS/'engine_factory_loop')
    root=ROOT/'jiuwenswarm/factory';files=binding.inventory(root)
    backend=dict(root=str(root),files=files,sha256=binding.digest(files))
    record=binding.create(host,release,backend,{'image':'sha256:'+'a'*64})
    limits=dict(timeout_s=10,cpus=1,memory_bytes=104857600,output_bytes=1024,pids=32)
    policy=dict(max_cycles=2,max_experiments=2,wall_clock_s=1000,templates=[],experiment_authority=dict(
        images=['sha256:'+'a'*64],purposes=['cpu_analysis','gpu_probe'],permitted_changes=['probe'],limits=limits,
        acceptance_policy_sha256='b'*64,max_build_attempts=0,max_gpu_launches=1))
    store.create_task(dict(task_id='authored',objective='Probe',allowed_effects=['process.exec','gpu.use'],
        constraints=dict(factory_loop=policy,execution_binding=record)))
    store.append_observation('authored',dict(obs_id='seed',kind='report',values={'status':'success'}))
    spec=dict(hypothesis='A discriminating probe',evidence_ids=['seed'],purpose='cpu_analysis',
        changed_variables=['probe'],artifacts={'probe.py':'print(1)'},recipe=['python3','/probe/probe.py'],
        measurements=['value'],interpretation='One proves the probe ran; no promotion',budget=limits)
    return store,FactoryLoop(store,'authored',benchmark=FakeBenchmark(store)),spec


def test_authored_prepare_freezes_then_recovers_one_attempt(tmp_path):
    store,loop,spec=prepared_loop(tmp_path)
    prepared=loop.prepare_experiment('one',spec,'sha256:'+'a'*64)
    assert prepared['execution_authorized'] is False
    assert not loop.status()['cycles']
    assert loop.prepare_experiment('one',spec,'sha256:'+'a'*64)==prepared
    spec['artifacts']['probe.py']='print(2)'
    with pytest.raises(ValueError,match='conflicts'):loop.prepare_experiment('one',spec,'sha256:'+'a'*64)
    cycle=loop.select('one',['seed'],spec['hypothesis'],expected_rev=0,experiment_id='one')
    assert cycle['contract']['specification']['artifacts']['probe.py']=='print(1)'
    loop.benchmark.crash=True
    with pytest.raises(RuntimeError):loop.execute('one')
    loop.execute('one');result=loop.collect('one')
    assert result['state']=='collected' and result['followup']['promotion_authorized'] is False
    assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0]==1
    store.close()


def test_authored_rejects_resource_and_judge_changes(tmp_path):
    store,loop,spec=prepared_loop(tmp_path)
    spec['budget']=dict(spec['budget'],cpus=2)
    with pytest.raises(Exception,match='resource envelope'):loop.prepare_experiment('over',spec,'sha256:'+'a'*64)
    spec['budget']['cpus']=1;spec['judge']='my tolerant judge'
    with pytest.raises(ValueError,match='acceptance rules'):loop.prepare_experiment('judge',spec,'sha256:'+'a'*64)
    store.close()


def test_build_admission_uses_host_bridge_without_local_docker(monkeypatch):
    from types import SimpleNamespace
    from jiuwenswarm.factory.experiment_build import ensure_build
    from jiuwenswarm.factory import bridge
    import subprocess
    monkeypatch.setenv('FACTORY_BRIDGE_DIR','operator-bridge')
    calls=[]
    def call(operation,**values):
        calls.append((operation,values))
        return subprocess.CompletedProcess([],0,json.dumps({'cycle':{'cycle_id':'c','build_admission_id':'admitted'},'ready':True}),'')
    monkeypatch.setattr(bridge,'call',call)
    cycle,ready=ensure_build(SimpleNamespace(task_id='t'),{'cycle_id':'c'})
    assert ready and cycle['build_admission_id']=='admitted'
    assert calls==[('experiment_build_admit',{'task_id':'t','cycle_id':'c'})]


def test_collector_exposes_verified_raw_artifacts_in_parent_scope(tmp_path):
    store,loop,spec=prepared_loop(tmp_path)
    loop.prepare_experiment('one',spec,'sha256:'+'a'*64)
    loop.select('one',['seed'],spec['hypothesis'],expected_rev=0,experiment_id='one')
    cycle=loop.execute('one')
    child=cycle['child_task_id'];attempt=store.read(child,cycle['attempt_id'])
    artifact=store.put_artifact(child,attempt['attempt_id']+':stdout',b'negative result retained','text/plain',attempt['attempt_id'])
    from jiuwenswarm.factory.jobs import metadata
    metadata(store,attempt,result_refs=[artifact['artifact_id']])
    collected=loop.collect('one')
    report=store.read(loop.task_id,collected['evidence_id'])['values']
    retained=report['raw_artifacts'][0]
    assert retained['sha256']==artifact['sha256']
    assert store.artifact_bytes(loop.task_id,retained['artifact_id'])==b'negative result retained'
    store.close()


def test_ack_loss_exercise_is_durable_and_only_gpu_submit(tmp_path):
    from jiuwenswarm.factory.bridge import withheld_ack
    packet=dict(operation='queue',args=['submit','--class','gpu'])
    value=dict(returncode=0,stdout='job-identity\n')
    path=tmp_path/'one.request.json'
    assert withheld_ack(tmp_path,path,packet,value,enabled=False,now=1) is None
    assert withheld_ack(tmp_path,path,packet,value,enabled=True,now=1)=={'pending':True}
    assert withheld_ack(tmp_path,path,now=50)=={'pending':True}
    assert withheld_ack(tmp_path,path,now=76)=={'value':value}
    assert withheld_ack(tmp_path,tmp_path/'two.request.json',packet,value,enabled=True,now=80) is None


def test_build_preparation_uses_host_environment_binding(tmp_path,monkeypatch):
    from jiuwenswarm.factory import bridge, builder
    from jiuwenswarm.factory.store import Store
    home=tmp_path/'factory';source=tmp_path/'owned';source.mkdir()
    with Store(home) as store:
        store.create_task(dict(task_id='t',objective='x',constraints={'factory_loop':{'experiment_authority':{'owned_worktrees':[str(source)]}}}))
    monkeypatch.setenv('FACTORY_BRIDGE_HOME',str(home));monkeypatch.setenv('FACTORY_BRIDGE_DIR','client-inbox')
    observed=[]
    def normalize(self,request):
        import os
        assert 'FACTORY_BRIDGE_DIR' not in os.environ
        observed.append(request)
        return {'host_environment':'frozen'}
    monkeypatch.setattr(builder.Builder,'_request',normalize)
    request={'source':{'path':str(source)}}
    result=bridge.handle(dict(operation='experiment_build_prepare',task_id='t',request=request),tmp_path,tmp_path,tmp_path/'jobq')
    assert json.loads(result['stdout'])=={'host_environment':'frozen'} and observed==[request]


def test_bound_worker_cannot_import_queue_checkout(tmp_path):
    import os, subprocess
    from jiuwenswarm.factory.execution_binding import worker_environment
    frozen=tmp_path/'frozen';checkout=tmp_path/'editable';checkout.mkdir()
    backend=frozen/'jiuwenswarm/factory';backend.mkdir(parents=True)
    (frozen/'identity_probe.py').write_text('print("frozen")')
    (checkout/'identity_probe.py').write_text('raise RuntimeError("editable checkout imported")')
    env=dict(os.environ,**worker_environment({'backend':{'root':str(backend)}}))
    assert subprocess.check_output([sys.executable,'-m','identity_probe'],cwd=checkout,env=env,text=True).strip()=='frozen'


def test_failed_build_closes_cycle_atomically(tmp_path,monkeypatch):
    from jiuwenswarm.factory.experiment_build import ensure_build
    from jiuwenswarm.factory.builder import Builder
    store,loop,spec=prepared_loop(tmp_path)
    loop.prepare_experiment('one',spec,'sha256:'+'a'*64)
    cycle=loop.select('one',['seed'],spec['hypothesis'],expected_rev=0,experiment_id='one')
    cycle['contract']['specification']['build']={}
    cycle['contract']['build_binding']={}
    monkeypatch.setattr(Builder,'_request',lambda self,request:{})
    monkeypatch.setattr(Builder,'submit',lambda *args,**kw:dict(state='failed',attempt_id='failed-build'))
    result,ready=ensure_build(loop,cycle)
    assert not ready and result['state']=='collected'
    assert store.read(loop.task_id,result['evidence_id'])['values']['build_attempt_id']=='failed-build'
    assert loop.status()['cycles'][0]['state']=='collected'
    store.close()


def test_recommendation_cannot_renew_shared_turn_budget(tmp_path):
    from jiuwenswarm.factory.store import Store
    from jiuwenswarm.factory.recommendations import remaining_resources
    with Store(tmp_path/'factory') as store:
        store.create_task(dict(task_id='campaign',objective='x',budget={'max_turns':3,'wall_clock_s':100}))
        store.create_task(dict(task_id='prior',objective='x',constraints={'campaign_budget_owner':'campaign'}))
        store.create_task(dict(task_id='current',objective='x',budget={'max_turns':10,'wall_clock_s':1000},constraints={'campaign_budget_owner':'campaign'}))
        sessions=store.home/'sessions';sessions.mkdir()
        (sessions/'prior.state.json').write_text(json.dumps({'turns':3}))
        result=remaining_resources(store,store.get_task('current'))
        assert result['max_turns']==0 and result['wall_clock_s']<=100


def test_gpu_experiment_uses_guarded_lab_lease(tmp_path):
    from jiuwenswarm.factory.lab_lifecycle import OwnedContainerGuard
    from jiuwenswarm.factory.experiment_jobs import container_argv
    from types import SimpleNamespace
    guard=OwnedContainerGuard(tmp_path/'owner','sha256:'+'a'*64,kind='lab',timeout_s=60)
    assert guard.kind=='lab'
    contract=dict(limits=dict(cpus=1,memory_bytes=1024**3,pids=64,output_bytes=1024),model=None,
        specification=dict(purpose='gpu_probe',recipe=['/opt/probe']),image=guard.image)
    argv=container_argv(contract,tmp_path,SimpleNamespace(name='owned',labels={}))
    assert argv[argv.index('--gpus')+1]=='all'


def test_export_retains_missing_operator_contract_as_gap(tmp_path):
    from jiuwenswarm.factory.store import Store
    from jiuwenswarm.factory.export import export_task, verify
    with Store(tmp_path/'factory') as store:
        store.create_task(dict(task_id='diagnostic',objective='x',contract_id='missing-construction-contract'))
    destination=tmp_path/'export'
    export_task('diagnostic',destination,tmp_path/'factory')
    assert verify(destination)>0
    origins=json.loads((destination/'contract-origins.json').read_text())
    assert origins==[{'contract_id':'missing-construction-contract','source':'unavailable','path':None}]


def test_authored_child_contract_exports_without_engine_judge(tmp_path):
    from jiuwenswarm.factory.export import export_task,verify
    store,loop,spec=prepared_loop(tmp_path)
    loop.prepare_experiment('one',spec,'sha256:'+'a'*64)
    loop.select('one',['seed'],spec['hypothesis'],expected_rev=0,experiment_id='one')
    cycle=loop.execute('one')
    destination=tmp_path/'child-export'
    export_task(cycle['child_task_id'],destination,store.home)
    assert verify(destination)>0
    origins=json.loads((destination/'contract-origins.json').read_text())
    assert origins and origins[0]['source']=='export_time_operator_input'
    store.close()
