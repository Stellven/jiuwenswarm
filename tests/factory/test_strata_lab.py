"""Strata admission/submission and evidence ingestion; no GPU or model launch."""
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from jiuwenswarm.factory import contract, engine_adapters, strata_lab
from jiuwenswarm.factory.contract import atomic_json
from jiuwenswarm.factory.manager import Manager, UploadConflict
from jiuwenswarm.factory.store import NotFound
from jiuwenswarm.factory.targets import labels

IMAGE = 'sha256:'+'a'*64


@pytest.fixture
def spark_lab(store, tmp_path, monkeypatch, request):
    model = tmp_path/'model.gguf'; model.write_bytes(b'tiny synthetic asset')
    pack = tmp_path/'pack'; pack.mkdir()
    asset = tmp_path/'assets.json'
    stat = model.stat()
    atomic_json(asset, dict(files=[dict(path=str(model), sha256=engine_adapters.sha(model),
        st_size=stat.st_size, st_mtime_ns=stat.st_mtime_ns, st_ctime_ns=stat.st_ctime_ns)], pack_files={}))
    c = dict(contract_id='spark-fixture-v1', version=1, adapter='strata-v1', target='spark-gb10',
        tolerance='canonical-token-ids-and-finish', scope='Synthetic protocol and lifecycle checks, not accuracy',
        workload=dict(pack=str(pack), model_root=str(tmp_path),
            argv=['--pack',str(pack),'--experts','6','--mmap-experts','on','--dspark','none'],
            environment={'STRATA_DS4_REUSE':'0'},
            requests=[dict(ids=list(range(1471)), max_new_tokens=128)]*2),
        limits=dict(cpus=8,memory_bytes=104*2**30,extra_swap_bytes=0,guard_gib=8,timeout_s=900),
        assets=dict(identity_path=str(asset),identity_sha256=engine_adapters.sha(asset)))
    if getattr(request, 'param', None) == 'missing-scope':
        c.pop('scope')
    contracts = tmp_path/'contracts'; contracts.mkdir()
    path = contracts/'spark-fixture-v1.json'; atomic_json(path,c)
    monkeypatch.setattr(contract,'CONTRACTS',contracts)
    store.create_task(dict(task_id='spark',objective='Synthetic repeatability',target={'profile':'spark-gb10'},
        contract_id=c['contract_id'],constraints={'contract_sha256':engine_adapters.sha(path),'quiet_required':True}))
    build = store.create_attempt('spark',dict(kind='build',idem_key='built-spark',fingerprint='spark',request={'target':'spark-gb10'}))
    store.put_artifact('spark',build['attempt_id']+':receipt',json.dumps(dict(image_id=IMAGE)).encode(),'application/json',build['attempt_id'])
    store.transition_attempt('spark',build['attempt_id'],'running')
    store.transition_attempt('spark',build['attempt_id'],'succeeded')
    monkeypatch.setattr('jiuwenswarm.factory.manager.inspect_image',lambda image:dict(Id=IMAGE,Architecture='arm64',Config={'Labels':labels('spark-gb10')}))
    manager = Manager(store,tmp_path/'spool')
    admission = manager.admit('spark',dict(tag='factory/strata:fixture',id=IMAGE),build['attempt_id'])
    return manager, admission, contract.load(c['contract_id']), path


def bundle(spark_lab, run_config=None):
    manager, admission, c, _ = spark_lab
    handle = manager.submit_run('spark',admission['admission_id'],c['contract_id'],run_config or {},'cell-1')
    root = manager.spool_root/handle['attempt_id']; root.mkdir()
    cell = root/'cell'; cell.mkdir()
    stdout = 'READY 8192 stop\n'+''.join('T 42\nDONE 1 1471 10.0 20.0 stop 0 0 0 0 0\n' for _ in range(2))
    stderr = 'ds4: experts per word: 6 (full quality)\n'
    (cell/'stdout.log').write_text(stdout); (cell/'stderr.log').write_text(stderr)
    collected = dict(reason='completed',quiescent=True,container_removed=True,container_exit_code=0,
        container_oom_killed=False,image=IMAGE,memory_bytes=104*2**30,swap_extra_bytes=0,cpus=8,
        evidence_completeness='complete',guard_gib=8)
    atomic_json(cell/'report.json',collected)
    from jiuwenswarm.factory.lab_recorder import GATE
    nonce='b'*32; cid='c'*64
    atomic_json(cell/'intent.json',dict(image=IMAGE,nonce=nonce,container_name='factory-lab-'+'d'*32))
    created=dict(Id=cid,Image=IMAGE,Name='/factory-lab-'+'d'*32,
        Config=dict(User=f'{os.getuid()}:{os.getgid()}',Env=[k+'='+v for k,v in strata_lab.execution_environment(handle['request']).items()],Volumes=None,Tty=False,
            Entrypoint=['/usr/bin/python3'],Labels={'factory.lab.owner':'spark-lab-v1','factory.lab.nonce':nonce},
            Cmd=['-c',GATE,'/opt/strata/strata-dsv41',*c['workload']['argv'],'--profile-readonly','--serve']),
        HostConfig=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='none',IpcMode='private',
            CgroupnsMode='private',Memory=104*2**30,MemorySwap=104*2**30,NanoCpus=8_000_000_000,
            PidsLimit=256,PidMode='',UTSMode='',UsernsMode='',CapDrop=['ALL'],CapAdd=None,
            SecurityOpt=['no-new-privileges:true'],LogConfig={'Type':'none'},
            DeviceRequests=[{'Driver':'cdi','DeviceIDs':['nvidia.com/gpu=0']}]),
        Mounts=[dict(Type='bind',RW=False,Source=c['workload'][key],Destination=c['workload'][key]) for key in ('pack','model_root')],
        State=dict(Running=False,Pid=0,ExitCode=0,OOMKilled=False))
    atomic_json(cell/'inspect-created.json',created);atomic_json(cell/'inspect-final.json',created)
    wire=b'FACTORY_EXEC\n'+engine_adapters.protocol(c)
    (cell/'stdin-wire.log').write_bytes(wire)
    events=[]
    for i,(stream,data) in enumerate([('stdin',wire),('stdout',stdout.encode()),('stderr',stderr.encode())]):
        events.append(dict(sequence=i,stream=stream,offset=0,retained_bytes=len(data),observed_bytes=len(data),truncated=False))
    (cell/'pipe-events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in events))
    (cell/'samples.jsonl').write_text(json.dumps(dict(available_bytes=32*2**30,memory_events={'oom':0,'oom_kill':0}))+'\n')
    atomic_json(root/'config.json',dict(handle['request'],lab_run_id=handle['attempt_id']))
    parsed=engine_adapters.parse_protocol(stdout,stderr,c)
    atomic_json(root/'worker.json',dict(execution_outcome='ok',evidence_completeness='complete',collector=collected,
        assets_before=engine_adapters.inspect_assets(c),assets_after=engine_adapters.inspect_assets(c),**parsed))
    strata_lab.seal(root,'spark',handle['attempt_id'],handle['request'])
    return handle,root


def reseal(handle,root):
    strata_lab.seal(root,'spark',handle['attempt_id'],handle['request'])


def test_native_profile_retains_guarded_host_path_and_excludes_reference(spark_lab):
    manager, _, c, _ = spark_lab
    handle, root = bundle(spark_lab, {'profile': 'strata-native'})
    assert handle['request']['profile'] == 'strata-native'
    assert strata_lab.execution_environment(handle['request']) == {'STRATA_DS4_REUSE':'0', 'DS4_PROF':'1'}
    manager.ingest_upload('spark', handle['attempt_id'], root)
    records = manager.store.dump('spark')
    observation = next(r for r in records['observations'] if r['obs_id'] == handle['attempt_id']+':observation')
    assert observation['kind'] == 'profile_result'
    assert observation['values']['scoring_eligible'] is False
    assert observation['values']['traced'] is True
    assert observation['values']['native_profile']['status'] == 'not_measured'
    from jiuwenswarm.factory.acceptance import validate
    with pytest.raises(ValueError, match='found 0'):
        validate(manager.store, 'spark')


@pytest.mark.parametrize('spark_lab', ['missing-scope'], indirect=True)
def test_profile_import_accepts_valid_contract_without_optional_scope(spark_lab):
    manager, _, c, _ = spark_lab
    assert 'scope' not in c
    handle, root = bundle(spark_lab, {'profile': 'strata-native'})
    manager.ingest_upload('spark', handle['attempt_id'], root)
    obs = manager.store.read('spark', handle['attempt_id']+':observation')
    assert obs['kind'] == 'profile_result'
    assert 'Native Strata evidence' in obs['limitations']


def test_native_profile_import_requires_actual_observer_environment(spark_lab):
    manager, _, _, _ = spark_lab
    handle, root = bundle(spark_lab, {'profile': 'strata-native'})
    for name in ('inspect-created.json', 'inspect-final.json'):
        path = root/'cell'/name
        data = json.loads(path.read_text())
        data['Config']['Env'] = ['STRATA_DS4_REUSE=0']
        atomic_json(path, data)
    reseal(handle, root)
    with pytest.raises(RuntimeError, match='environment differs'):
        manager.ingest_upload('spark', handle['attempt_id'], root)


def test_unprofiled_run_rejects_inherited_observer(spark_lab):
    manager, _, _, _ = spark_lab
    handle, root = bundle(spark_lab)
    for name in ('inspect-created.json', 'inspect-final.json'):
        path = root/'cell'/name
        data = json.loads(path.read_text())
        data['Config']['Env'].append('DS4_PROF=1')
        atomic_json(path, data)
    reseal(handle, root)
    with pytest.raises(RuntimeError, match='uncontrolled profiler'):
        manager.ingest_upload('spark', handle['attempt_id'], root)


def test_submit_routes_generic_manager_and_replays(spark_lab):
    manager,admission,c,_=spark_lab
    first=manager.submit_run('spark',admission['admission_id'],c['contract_id'],{},'one')
    second=manager.submit_run('spark',admission['admission_id'],c['contract_id'],{},'one')
    assert first['attempt_id']==second['attempt_id']
    assert first['request']['adapter']=='strata-v1'
    assert first['request']['quiet_required'] is True
    assert first['resources']['job_class']=='gpu'
    assert first['resources']['argv'][2]=='jiuwenswarm.factory.strata_lab'


@pytest.mark.parametrize('config',[{'env':{'DS4_AHEAD':'1'}},{'argv_overrides':['--experts','5']},{'profile':'nsys'}])
def test_fixed_contract_rejects_run_config_changes(spark_lab,config):
    manager,admission,c,_=spark_lab
    with pytest.raises(ValueError,match='fixed'):
        manager.submit_run('spark',admission['admission_id'],c['contract_id'],config,'bad')


def test_operator_contract_mutation_rejected(spark_lab):
    manager,admission,c,path=spark_lab
    mutated=json.loads(path.read_text());mutated['workload']['argv']+=['--cpu-threads','4'];atomic_json(path,mutated)
    with pytest.raises(ValueError,match='identity'):
        manager.submit_run('spark',admission['admission_id'],c['contract_id'],{},'changed')


def test_native_protocol_contains_all_1471_input_ids_and_128_cap(spark_lab):
    _,_,c,_=spark_lab
    wire=engine_adapters.protocol(c)
    assert wire.count(b'GEN 128 ')==2 and wire.endswith(b'QUIT\n')
    lines=wire.splitlines()
    for line in lines[:-1]:
        assert b'spec=0 ' in line
        ids=[int(v) for v in line.rsplit(b' ',1)[1].split(b',')]
        assert ids==list(range(1471))
    assert len(wire)<1024*1024


def test_ingest_derives_metrics_and_is_idempotent(spark_lab):
    manager,*_=spark_lab
    handle,root=bundle(spark_lab)
    first=manager.ingest_upload('spark',handle['attempt_id'],root)
    second=manager.ingest_upload('spark',handle['attempt_id'],root)
    assert first==second
    obs=manager.store.read('spark',handle['attempt_id']+':observation')
    assert obs['values']['requests'][0]['decode_tps']==50.0
    assert obs['values']['repeat_equal'] is True
    assert len(manager.store._db.execute('SELECT * FROM uploads WHERE task_id=?',('spark',)).fetchall())==1
    evaluation=manager.store.read('spark',handle['attempt_id']+':evaluation')
    assert evaluation['correctness']=='not_evaluated'
    assert evaluation['execution_outcome']=='ok'


def test_altered_artifact_hash_rejected(spark_lab):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    (root/'cell/stdout.log').write_text('forged')
    with pytest.raises(ValueError,match='hash mismatch'):
        manager.ingest_upload('spark',handle['attempt_id'],root)


def test_worker_metric_cannot_override_raw_records(spark_lab):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    worker=json.loads((root/'worker.json').read_text());worker['requests'][0]['decode_tps']=999
    atomic_json(root/'worker.json',worker);reseal(handle,root)
    with pytest.raises(ValueError,match='metrics differ'):
        manager.ingest_upload('spark',handle['attempt_id'],root)


def test_resealed_configuration_change_rejected(spark_lab):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    config=json.loads((root/'config.json').read_text());config['quiet_required']=False
    atomic_json(root/'config.json',config);reseal(handle,root)
    with pytest.raises(ValueError,match='configuration differs'):
        manager.ingest_upload('spark',handle['attempt_id'],root)


def test_changed_sealed_upload_conflicts_after_ingest(spark_lab):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    manager.ingest_upload('spark',handle['attempt_id'],root)
    (root/'extra-note.txt').write_text('new bytes after upload');reseal(handle,root)
    with pytest.raises(UploadConflict):manager.ingest_upload('spark',handle['attempt_id'],root)


def test_partial_worker_loss_is_recoverable_without_final_manifest(spark_lab):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    (root/'manifest.json').unlink();(root/'worker.json').unlink()
    shutil.rmtree(root/'cell')
    # This models a worker dying before its collector was created. A collector
    # intent would exercise exact-container recovery in lifecycle tests.
    strata_lab.recover_upload(manager,'spark',handle['attempt_id'],root)
    manager.ingest_upload('spark',handle['attempt_id'],root)
    evaluation=manager.store.read('spark',handle['attempt_id']+':evaluation')
    assert evaluation['execution_outcome']=='measurement_failed'
    assert evaluation['evidence_completeness']=='partial'


def test_attempt_owner_scope_is_enforced(spark_lab):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    manager.store.create_task(dict(task_id='other',objective='Separate task'))
    with pytest.raises(NotFound):manager.ingest_upload('other',handle['attempt_id'],root)


def test_bundle_escape_rejected(spark_lab,tmp_path):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    outside=tmp_path/'outside.txt';outside.write_text('outside')
    manifest=json.loads((root/'manifest.json').read_text())
    manifest['files']['../../outside.txt']=engine_adapters.sha(outside)
    atomic_json(root/'manifest.json',manifest)
    with pytest.raises(ValueError,match='escapes'):manager.ingest_upload('spark',handle['attempt_id'],root)


@pytest.mark.parametrize('mode', ['swap','wrong_gpu','wrong_env','final_oom','guard','pipe_gap','replay','assets'])
def test_resealed_boundary_or_telemetry_corruption_is_rejected(spark_lab,mode):
    manager,*_=spark_lab;handle,root=bundle(spark_lab)
    if mode in {'swap','wrong_gpu','wrong_env'}:
        path=root/'cell/inspect-created.json';value=json.loads(path.read_text())
        if mode=='swap':value['HostConfig']['MemorySwap']+=1024
        elif mode=='wrong_gpu':value['HostConfig']['DeviceRequests']=[]
        else:value['Config']['Env']=['STRATA_DS4_REUSE=1']
        atomic_json(path,value)
    elif mode=='final_oom':
        path=root/'cell/inspect-final.json';value=json.loads(path.read_text());value['State']['OOMKilled']=True;atomic_json(path,value)
    elif mode=='guard':
        (root/'cell/samples.jsonl').write_text(json.dumps(dict(available_bytes=1,memory_events={}))+'\n')
    elif mode=='pipe_gap':
        path=root/'cell/pipe-events.jsonl';values=[json.loads(l) for l in path.read_text().splitlines()]
        values[1]['sequence']=99;path.write_text(''.join(json.dumps(v)+'\n' for v in values))
    elif mode=='replay':
        path=root/'cell/stdin-wire.log';path.write_bytes(path.read_bytes().replace(b'seed=42',b'seed=43'))
    else:
        path=root/'worker.json';value=json.loads(path.read_text());value['assets_after']['identity_sha256']='0'*64;atomic_json(path,value)
    reseal(handle,root)
    with pytest.raises((ValueError, RuntimeError)):manager.ingest_upload('spark',handle['attempt_id'],root)
