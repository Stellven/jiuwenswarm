"""Offline lab protocol tests: fake image inspection and fake guarded execution."""
import builtins
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from jiuwenswarm.factory import contract, lab_runner
from jiuwenswarm.factory.api import dispatch, input_reason
from jiuwenswarm.factory.manager import Manager, AdmissionError, UploadConflict
from jiuwenswarm.factory.store import PersistenceFailed, ScopeDenied
from conftest import until

FIXTURES = Path(__file__).parent / 'fixtures' / 'lab'
IMAGE = 'sha256:' + 'a' * 64


@pytest.fixture
def lab(store, tmp_path, monkeypatch):
    model = tmp_path / 'model.gguf'
    model.write_bytes(b'fixture model')
    c = dict(contract.load('qwen36-greedy-v1'))
    c['model'] = dict(path=str(model), size=model.stat().st_size, sha256=None)
    c['reference']['image_id'] = IMAGE
    c['reference']['stdout_sha256'] = hashlib.sha256((FIXTURES / 'stdout.txt').read_bytes()).hexdigest()
    c['reference']['frozen_at'] = 'fixture'
    c['reference']['run_ref'] = 'fixture'
    contracts = tmp_path / 'contracts'
    contracts.mkdir()
    contract.atomic_json(contracts / 'fixture-v1.json', dict(c, contract_id='fixture-v1'))
    monkeypatch.setattr(contract, 'CONTRACTS', contracts)
    fake = tmp_path / 'docker'
    image = tmp_path / 'image.json'
    image.write_text(json.dumps([dict(Id=IMAGE, Architecture='arm64', Config=dict(Labels={'campaign.target.profile':'jetson-orin'}))]))
    fake.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\nif sys.argv[1:3] == ["image","inspect"]: print(Path(' + repr(str(image)) + ').read_text())\n')
    fake.chmod(0o755)
    om = tmp_path / 'om_run'
    om.write_text('#!' + sys.executable + '\nimport sys,shutil,os,time\nfrom pathlib import Path\nroot=Path(sys.argv[1]);root.mkdir(exist_ok=True)\nassert os.environ["OM_THREADS"] == "1"\nassert os.environ["OM_MIN_AVAIL_MIB"] == "600"\nassert Path(os.environ["OM_MODELDIR"]).is_dir()\nfor name in '+repr(sorted(lab_runner.REQUIRED))+': shutil.copyfile(Path('+repr(str(FIXTURES.resolve()))+')/name,root/name)\n(root/"container.id").write_text("a"*64)\n')
    om.chmod(0o755)
    monkeypatch.setenv('FACTORY_DOCKER', str(fake))
    monkeypatch.setenv('FACTORY_OM_RUN', str(om))
    build = store.create_attempt('t', dict(kind='build', idem_key='built', fingerprint='fixture', request={}))
    store.put_artifact('t', build['attempt_id'] + ':receipt', json.dumps({'image_id':IMAGE}).encode(), 'application/json', build['attempt_id'])
    store.transition_attempt('t', build['attempt_id'], 'running')
    store.transition_attempt('t', build['attempt_id'], 'succeeded')
    return Manager(store, tmp_path / 'spool'), build, image


def admit(lab):
    manager, build, _ = lab
    return manager.admit('t', dict(tag='fixture:engine', id=IMAGE), build['attempt_id'])


def bundle(lab):
    manager, _, _ = lab
    a = admit(lab)
    handle = manager.submit_run('t', a['admission_id'], 'fixture-v1', {'env':{}}, 'run')
    root = manager.spool_root / handle['attempt_id']
    root.mkdir()
    for name in lab_runner.REQUIRED:
        shutil.copyfile(FIXTURES / name, root / name)
    config = dict(handle['request'], lab_run_id=handle['attempt_id'])
    contract.atomic_json(root / 'config.json', config)
    contract.atomic_json(root / 'worker.json', {'execution_outcome':'ok'})
    lab_runner.write_bundle(root, 't', handle['attempt_id'], a['admission_id'], 'fixture-v1')
    return handle, root


def test_admit_bad_digest(lab):
    manager, build, path = lab
    data=json.loads(path.read_text()); data[0]['Id']='sha256:'+'b'*64; path.write_text(json.dumps(data))
    with pytest.raises(AdmissionError) as exc:
        admit(lab)
    assert exc.value.code == 'BAD_DIGEST'


@pytest.mark.parametrize('arch,labels', [('amd64', {'campaign.target.profile':'jetson-orin'}), ('arm64', {})])
def test_admit_wrong_target(lab, arch, labels):
    data=json.loads(lab[2].read_text());data[0].update(Architecture=arch,Config={'Labels':labels});lab[2].write_text(json.dumps(data))
    with pytest.raises(AdmissionError) as exc:
        admit(lab)
    assert exc.value.code == 'WRONG_TARGET'


def test_admit_ok_labeled_same_host(lab):
    a = admit(lab)
    assert a['delivery'] == 'same_host_local_image'
    assert json.loads(lab[0].store.artifact_bytes('t',a['admission_id'])) == a
    assert admit(lab) == a


def test_contract_freeze_once(tmp_path):
    c = dict(contract.load('qwen36-greedy-v1'))
    p = tmp_path / 'contract.json';contract.atomic_json(p,c)
    loaded = contract.load(p)
    run = dict(execution_outcome='ok',evidence_completeness='complete',image_id=c['reference']['image_id'],stdout_sha256='a'*64,run_ref='fixture')
    contract.freeze(loaded, run)
    assert contract.load(p)['reference']['stdout_sha256'] == 'a'*64
    with pytest.raises(contract.ContractFrozen):
        contract.freeze(loaded, run)
    with pytest.raises(contract.ContractFrozen):
        contract.freeze(contract.load(p), run)


def test_eval_identical_pass(lab):
    handle, root = bundle(lab)
    config = json.loads((root/'config.json').read_text())
    run = lab_runner.collect(root, config)
    evaluation = contract.evaluate(config['contract'],run)
    assert evaluation['correctness'] == 'pass'
    assert evaluation['execution_outcome'] == 'ok'
    assert run['details']['effective_line_count'] == 2
    assert all(run['details']['engagement_checks'].values())
    assert run['details']['eval_ms_per_token'] == 747.88


def test_eval_mismatch_candidate_failed(lab):
    handle, root = bundle(lab)
    (root/'stdout.txt').write_text('different')
    config = json.loads((root/'config.json').read_text())
    result=contract.evaluate(config['contract'],lab_runner.collect(root,config))
    assert result['correctness'] == 'fail' and result['execution_outcome'] == 'candidate_failed'


def test_measurement_failed_not_evaluated(lab):
    handle, root = bundle(lab)
    for name in ('watchdog.jsonl','result.json'):
        shutil.copyfile(FIXTURES / ('tripped-'+name), root/name)
    config=json.loads((root/'config.json').read_text())
    result=contract.evaluate(config['contract'],lab_runner.collect(root,config))
    assert result['execution_outcome'] == 'measurement_failed'
    assert result['correctness'] == 'not_evaluated'


def test_config_rejected_message_captured(lab):
    handle, root = bundle(lab)
    shutil.copyfile(FIXTURES/'invalid-stderr.txt', root/'stderr.txt')
    result=json.loads((root/'result.json').read_text());result['exit_code']=133
    contract.atomic_json(root/'result.json',result)
    config=json.loads((root/'config.json').read_text())
    result=contract.evaluate(config['contract'],lab_runner.collect(root,config))
    assert result['execution_outcome'] == 'config_rejected'
    assert result['correctness'] == 'not_evaluated'
    assert result['details']['invalid_message'] == 'expert_config: invalid LLAMA_EXPERT_PREGATE_K=48 (range 1..32)'
    assert result['details']['aborted']


def test_upload_idempotent(lab):
    handle, root=bundle(lab);manager=lab[0]
    first=manager.ingest_upload('t',handle['attempt_id'],root)
    count=len(manager.store.dump('t')['observations'])
    assert first == manager.ingest_upload('t',handle['attempt_id'],root)
    assert json.loads((root/'ack.json').read_text()) == first
    assert len(manager.store.dump('t')['observations']) == count == 1
    result=manager.result(handle['attempt_id'])
    assert result['evaluation']['correctness'] == 'pass'
    assert result['evidence_refs']


def test_upload_conflict(lab):
    handle,root=bundle(lab);manager=lab[0]
    manager.ingest_upload('t',handle['attempt_id'],root)
    (root/'stdout.txt').write_text('changed')
    m=json.loads((root/'manifest.json').read_text());m['files']['stdout.txt']=hashlib.sha256(b'changed').hexdigest();contract.atomic_json(root/'manifest.json',m)
    with pytest.raises(UploadConflict):
        manager.ingest_upload('t',handle['attempt_id'],root)


def test_upload_failure_no_ack_then_retry(lab):
    handle,root=bundle(lab);manager=lab[0]
    def fault(stage):
        # Fail the final semantic transaction, after all artifact commits.
        if stage=='before_commit' and manager.store._db.execute('SELECT 1 FROM uploads').fetchone():
            raise OSError('fixture fault')
    manager.store.fault=fault
    with pytest.raises(PersistenceFailed):
        manager.ingest_upload('t',handle['attempt_id'],root)
    assert not (root/'ack.json').exists()
    assert manager.store.dump('t')['uploads'] == []
    assert manager.store.dump('t')['observations'] == []
    assert manager.store.dump('t')['evaluations'] == []
    manager.store.fault=None
    assert manager.retry_spool()[0]['ack_state'] == 'durable'


@pytest.mark.parametrize('change', ['task', 'run', 'sha', 'path', 'config'])
def test_upload_rejects_invalid_bundle(lab, change):
    handle,root=bundle(lab);m=json.loads((root/'manifest.json').read_text())
    if change=='task':m['task_id']='other'
    elif change=='run':m['lab_run_id']='other'
    elif change=='sha':m['files']['stdout.txt']='0'*64
    elif change=='path':m['files']['../outside']='0'*64
    else:
        config=json.loads((root/'config.json').read_text());config['env']={}
        contract.atomic_json(root/'config.json',config)
        m['files']['config.json']=hashlib.sha256((root/'config.json').read_bytes()).hexdigest()
    contract.atomic_json(root/'manifest.json',m)
    with pytest.raises(ValueError):lab[0].ingest_upload('t',handle['attempt_id'],root)
    assert not (root/'ack.json').exists()


def test_lab_never_writes_store_directly(lab, monkeypatch):
    manager,_,_=lab;a=admit(lab)
    handle=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'guard')
    config=next((manager.spool_root/'configs').glob('*.json'))
    real_import=builtins.__import__
    def guarded(name,*args,**kwargs):
        assert not (name.endswith('.store') or name=='store'), 'Lab must not import Store'
        return real_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    monkeypatch.delenv('FACTORY_HOME',raising=False)
    monkeypatch.setattr(lab_runner,'upload',lambda *args: True)
    assert lab_runner.run('t',handle['attempt_id'],a['admission_id'],'fixture-v1',config,manager.spool_root)==0
    assert not manager.store.dump('t')['uploads']


def test_lab_job_external_runner_and_ingest(lab, worker):
    manager,_,_=lab;a=admit(lab)
    h=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'external')
    assert h['resources']['job_class']=='gpu'
    assert manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'external')['attempt_id']==h['attempt_id']
    worker()
    assert until(manager.jobs,h['attempt_id'])['state']=='succeeded'
    result=manager.result(h['attempt_id'])
    assert result['evaluation']['correctness']=='pass'
    assert (manager.spool_root/h['attempt_id']/'ack.json').exists()


def test_cancel_lab_job(lab, worker):
    manager,_,_=lab;a=admit(lab)
    # Queued cancellation must be confirmed by jobq; no container was created.
    h=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'cancel')
    assert manager.cancel(h['attempt_id'])['state']=='cancelled'
    assert manager.result(h['attempt_id'])['execution_outcome']=='cancelled'


@pytest.mark.parametrize('status',[133,134])
def test_inspector_aborted_signal_status(lab, monkeypatch,status):
    from jiuwenswarm.factory.inspector import Inspector
    probe=Inspector()
    monkeypatch.setattr(probe,'image',lambda image:{'id':IMAGE})
    monkeypatch.setattr(probe,'container',lambda *a,**k:subprocess.CompletedProcess([],status,'',(FIXTURES/'invalid-stderr.txt').read_text()))
    output,error=probe.verify({'image':{'id':IMAGE},'env':{'LLAMA_EXPERT_PREGATE_K':'48'}})
    assert output['aborted'] and error[0]=='CONFIG_REJECTED'


def test_api_invalid_input_reason(store, monkeypatch, capsys):
    from jiuwenswarm.factory import api
    import io
    monkeypatch.setenv('FACTORY_HOME',str(store.home));monkeypatch.setenv('FACTORY_TASK_ID','t')
    monkeypatch.setattr(sys,'argv',['api','evidence.read'])
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'inputs':{'id':[]}})))
    api.main()
    result=json.loads(capsys.readouterr().out)
    assert result['error']['message']=='id must be a nonempty string'
    monkeypatch.setenv('LAB_API_KEY','super-secret-value')
    assert 'super-secret-value' not in input_reason(ValueError('super-secret-value'))
    assert len(input_reason(ValueError('x'*500)))==300


def test_lab_api_scope(lab):
    manager,build,_=lab
    manager.store.create_task(dict(task_id='other',objective='scope fixture'))
    a=admit(lab);h=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'scope')
    with pytest.raises(ScopeDenied):
        dispatch(manager.store.scoped('other',{'t'}),'other','lab.cancel',{'inputs':{'attempt_id':h['attempt_id']}})


def test_upload_bytes_changed_with_same_manifest_conflicts(lab):
    handle,root=bundle(lab);manager=lab[0]
    manager.ingest_upload('t',handle['attempt_id'],root)
    (root/'stdout.txt').write_bytes(b'changed without updating manifest')
    with pytest.raises(UploadConflict):
        manager.ingest_upload('t',handle['attempt_id'],root)


@pytest.mark.parametrize('failure',['missing','disagree','mismatch','no_xfill'])
def test_engagement_missing_is_measurement_failure(lab,failure):
    _,root=bundle(lab)
    text=(root/'stderr.txt').read_text()
    if failure=='missing':
        text='\n'.join(line for line in text.splitlines() if not line.startswith('expert_config: effective'))
    elif failure=='disagree':
        text=text.replace('k=8 ', 'k=9 ',1)
    elif failure=='mismatch':
        text=text.replace('k=8 ', 'k=9 ')
    else:
        contract.atomic_json(root/'threads.summary.json',{'threads':{},'groups':{}})
    (root/'stderr.txt').write_text(text)
    config=json.loads((root/'config.json').read_text())
    evaluation=contract.evaluate(config['contract'],lab_runner.collect(root,config))
    assert evaluation['execution_outcome']=='measurement_failed'
    assert evaluation['correctness']=='not_evaluated'


def test_lab_api_submit_and_result(lab):
    manager,build,_=lab
    response=dispatch(manager.store.scoped('t'),'t','lab.submit',{'inputs':dict(
        image=dict(tag='fixture:engine',id=IMAGE),build_attempt_id=build['attempt_id'],
        contract_id='fixture-v1',run_config={'env':{}},idem_key='api-lab')})
    assert response['admission']['delivery']=='same_host_local_image'
    assert response['state']=='queued' and response['jobq_id']
    result=dispatch(manager.store.scoped('t'),'t','lab.result',{'inputs':{'attempt_id':response['attempt_id']}})
    assert result['evaluation'] is None


def test_cancel_running_lab_reaps_only_owned_container(lab,worker):
    manager,_,_=lab;a=admit(lab)
    om=Path(os.environ['FACTORY_OM_RUN'])
    om.write_text(om.read_text()+'\ntime.sleep(300)\n')
    fake=Path(os.environ['FACTORY_DOCKER'])
    removed=manager.spool_root/'removed.txt'
    fake.write_text(fake.read_text()+'\nif sys.argv[1:3]==["rm","-f"]: Path('+repr(str(removed))+').write_text(sys.argv[3])\n')
    h=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'cancel-running')
    worker()
    root=manager.spool_root/h['attempt_id']
    until(manager.jobs,h['attempt_id'],lambda a:(root/'container.id').exists())
    assert manager.cancel(h['attempt_id'])['state']=='cancelled'
    assert removed.read_text()=='a'*64


@pytest.mark.parametrize('failure',['bad_digest','wrong_target','model_size'])
def test_lab_preflight_failure_bundles_and_reaps(lab,monkeypatch,failure):
    manager,_,path=lab;a=admit(lab)
    h=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'preflight')
    config=next((manager.spool_root/'configs').glob('*.json'))
    if failure=='model_size':
        model=Path(h['request']['contract']['model']['path']);model.write_bytes(b'wrong')
    else:
        data=json.loads(path.read_text())
        if failure=='bad_digest': data[0]['Id']='sha256:'+'b'*64
        else:data[0]['Architecture']='amd64'
        path.write_text(json.dumps(data))
    monkeypatch.setattr(lab_runner,'upload',lambda *args:True)
    lab_runner.run('t',h['attempt_id'],a['admission_id'],'fixture-v1',config,manager.spool_root)
    root=manager.spool_root/h['attempt_id']
    assert (root/'manifest.json').exists()
    outcome=json.loads((root/'worker.json').read_text())['execution_outcome']
    assert outcome==('measurement_failed' if failure=='model_size' else failure)


def test_lab_upload_pending_retains_bundle(lab,monkeypatch,capsys):
    manager,_,_=lab;a=admit(lab)
    h=manager.submit_run('t',a['admission_id'],'fixture-v1',{'env':{}},'pending')
    config=next((manager.spool_root/'configs').glob('*.json'))
    monkeypatch.setattr(lab_runner,'upload',lambda *args:False)
    assert lab_runner.run('t',h['attempt_id'],a['admission_id'],'fixture-v1',config,manager.spool_root)==1
    root=manager.spool_root/h['attempt_id']
    assert json.loads(capsys.readouterr().out)['execution_outcome']=='upload_pending'
    assert (root/'manifest.json').exists() and not (root/'ack.json').exists()
    assert manager.retry_spool()[0]['ack_state']=='durable'


def test_reference_helper_uses_lab_and_freezes(lab,monkeypatch,capsys):
    from jiuwenswarm.factory import manager as module
    manager,_,_=lab
    path=contract.CONTRACTS/'fixture-v1.json'
    c=contract.load(path);c['reference'].update(stdout_sha256=None,frozen_at=None,run_ref=None)
    contract.atomic_json(path,c)
    record=path.parent/'baseline.json'
    contract.atomic_json(record,{'image':{'Id':IMAGE}})
    monkeypatch.setattr(module,'BASELINE_RECORD',record)
    original=manager.submit_run
    def submit(task,a,contract_id,config,key):
        h=original(task,a,contract_id,config,key)
        root=manager.spool_root/h['attempt_id'];root.mkdir()
        for name in lab_runner.REQUIRED:shutil.copyfile(FIXTURES/name,root/name)
        contract.atomic_json(root/'config.json',dict(h['request'],lab_run_id=h['attempt_id']))
        contract.atomic_json(root/'worker.json',{'execution_outcome':'ok'})
        lab_runner.write_bundle(root,task,h['attempt_id'],a,contract_id)
        manager.ingest_upload(task,h['attempt_id'],root)
        return h
    monkeypatch.setattr(manager,'submit_run',submit)
    module.freeze_reference(manager,'fixture-v1',c['reference']['image_tag'])
    assert capsys.readouterr().out.strip()==hashlib.sha256((FIXTURES/'stdout.txt').read_bytes()).hexdigest()
    assert contract.load(path)['reference']['frozen_at']


def test_native_lab_capsule_submission(lab, tmp_path, monkeypatch):
    from jiuwenswarm.ccv2.ccv2 import Host
    manager,build,_=lab
    monkeypatch.setenv('FACTORY_HOME',str(manager.store.home))
    monkeypatch.setenv('FACTORY_TASK_ID','t')
    root=Path(__file__).resolve().parents[2]
    monkeypatch.setenv('PYTHONPATH',str(root))
    host=Host(tmp_path/'cc-host',session_grants=['process.exec'])
    release=host.prepare(root/'jiuwenswarm/factory/ccs/lab_client')
    result=host.call(release,'submit',dict(image=dict(tag='fixture:engine',id=IMAGE),
        build_attempt_id=build['attempt_id'],contract_id=str(contract.CONTRACTS/'fixture-v1.json'),
        run_config={'env':{}},idem_key='native-lab'))
    assert result['state']=='succeeded',result
    assert result['outputs']['admission']['delivery']=='same_host_local_image'
    assert result['outputs']['jobq_id']
    bad=host.call(release,'submit',dict(image={},build_attempt_id=build['attempt_id'],
        contract_id='fixture',run_config={},idem_key='bad'))
    assert bad['reason']=='INVALID_INPUT',bad
