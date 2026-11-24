import copy
import json
from pathlib import Path
import pytest
from jiuwenswarm.factory import benchmark as b

@pytest.fixture
def contract():
    args=['--pack','/pack','--max-context','8192','--eos','1','--vision','off',
        '--dspark','none','--prefill-chunk','256','--cpu-threads','8',
        '--vram-experts','1.0','--reserve-mib','16384','--ssd-cache','0',
        '--mmap-experts','on','--experts','6','--verbose','--dspark-conf','0.65','--no-expert-cache']
    a=dict(args=args,environment={'STRATA_DS4_REUSE':'0'});other=copy.deepcopy(a)
    other['args'][other['args'].index('--dspark')+1]='on'
    return dict(adapter=b.ADAPTER,version=1,stage='pilot',tolerance='arc-exact-answer-regression-v1',
        target='spark-gb10',image={'id':'sha256:'+'a'*64},arms={'A':a,'B':other},order=['A','B'],
        workload={'pack':'/pack','model_root':'/models'},
        limits=dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,extra_swap_bytes=0,quality_timeout_s=900,speed_timeout_s=300),
        gates=dict(minimum_accuracy=0.5,minimum_speedup=1.05,confidence=0.95,bootstrap_resamples=20000,
            seed=42,correctness='no_per_question_regression'),campaign_timeout_s=5280,
        dataset_sha256='a'*64,execution_sha256={v:'a'*64 for v in b.EXECUTION_FILES})

def test_valid_frozen_policy(contract):
    assert b.validate_contract(contract) is contract

@pytest.mark.parametrize('mutation', ['second_knob','order','gate','memory','environment'])
def test_rejects_confounding_or_changed_policy(contract,mutation):
    if mutation=='second_knob':contract['arms']['B']['args'][3]='4096'
    if mutation=='order':contract['order']=['B','A']
    if mutation=='gate':contract['gates']['minimum_speedup']=1
    if mutation=='memory':contract['limits']['memory_bytes']+=1
    if mutation=='environment':contract['arms']['B']['environment']['DS4_AHEAD']='1'
    with pytest.raises(ValueError):b.validate_contract(contract)

CASES=[dict(id='one',ids=[0,2],max_new_tokens=2)]
STDOUT='READY\nT 42\nT 43\nDONE 2 2 10 100 length 0 0 0 0 0\n'

def test_native_rates_come_from_verified_counts():
    row=b.parse_native(STDOUT,'experts per word: 6',CASES)['requests'][0]
    assert row['decode_tps']==20
    assert row['ids']==[42,43]

@pytest.mark.parametrize('stdout,stderr',[
    (STDOUT.replace('DONE 2','DONE 3'),'experts per word: 6'),
    (STDOUT.replace(' 100 ',' nan '),'experts per word: 6'),
    (STDOUT,'experts per word: 2'),
    (STDOUT+'T 1\n','experts per word: 6'),
    (STDOUT.replace(' 0 0 0 0 0',' 2 1 0 0 0'),'experts per word: 6'),
    (STDOUT,'experts per word: 6\nterminate called'),
])
def test_corrupt_native_evidence_cannot_score(stdout,stderr):
    with pytest.raises(ValueError):b.parse_native(stdout,stderr,CASES)

def test_stage_wire_matches_frozen_inputs(contract):
    d={'speed':[{'id':str(i),'ids':[0,2],'max_new_tokens':128} for i in range(4)]};cases=b.phase_cases(contract,d,'speed')
    assert len(cases)==2
    assert b.protocol(cases,'A').count(b'spec=0')==2
    assert b.protocol(cases,'B').count(b'spec=1')==2
    args=b.phase_args(contract,'A','speed')
    assert args[args.index('--eos')+1]=='-1'
    assert b.phase_args(contract,'A','quality')[args.index('--eos')+1]=='1'


def test_scope_checked_before_queue_or_host_delegation(tmp_path,monkeypatch):
    from jiuwenswarm.factory.store import Store
    with Store(tmp_path/'store') as store:
        for task in ('mine','other'):store.create_task(dict(task_id=task,objective='scope test'))
        attempt=store.create_attempt('other',dict(kind='lab',request={'adapter':b.ADAPTER},idem_key='one',fingerprint='f'))
        manager=b.Benchmark(store)
        with pytest.raises(ValueError,match='another task'):manager.status('mine',attempt['attempt_id'])
        monkeypatch.setenv('FACTORY_BRIDGE_DIR',str(tmp_path/'inbox'))
        with pytest.raises(ValueError,match='another task'):manager.result('mine',attempt['attempt_id'])


def test_submit_requires_frozen_task_identity(tmp_path,contract,monkeypatch):
    from jiuwenswarm.factory.store import Store
    path=tmp_path/'contract.json';path.write_text(json.dumps(contract))
    with Store(tmp_path/'store') as store:
        store.create_task(dict(task_id='task',objective='fixed contract',contract_id=str(path),constraints={'benchmark_contract_sha256':'wrong'}))
        with pytest.raises(ValueError,match='identity changed'):b.Benchmark(store).submit('task',str(path),'one')
        with pytest.raises(ValueError,match='operator task contract'):b.Benchmark(store).submit('task','another','one')


def test_container_submission_uses_host_source_and_interpreter(tmp_path,contract,monkeypatch):
    from jiuwenswarm.factory.store import Store
    path=tmp_path/'contract.json';contract['workspace_root']=str(tmp_path);path.write_text(json.dumps(contract))
    monkeypatch.setenv('FACTORY_BRIDGE_DIR',str(tmp_path/'inbox'))
    monkeypatch.setenv('FACTORY_HOST_PYTHON','/usr/bin/python3')
    monkeypatch.setattr(b,'load_dataset',lambda c:{})
    monkeypatch.setattr(b,'validate_assets',lambda c:pytest.fail('Model access must stay on host worker'))
    with Store(tmp_path/'store') as store:
        store.create_task(dict(task_id='task',objective='container to host',contract_id=str(path),constraints={'benchmark_contract_sha256':b.sha(path)}))
        manager=b.Benchmark(store);calls=[]
        monkeypatch.setattr(manager.jobs,'submit',lambda *args:calls.append(args) or {})
        manager.submit('task',str(path),'one')
        call=calls[0]
        assert call[5][0]=='/usr/bin/python3'
        assert call[-1]['PYTHONPATH']==str(tmp_path/'sources/cc-dgx-spark')
        assert call[-2]<=5400


@pytest.mark.parametrize('mutation',['coverage','identity','hash'])
def test_independent_analysis_rejects_incomplete_or_changed_manifest(tmp_path,contract,monkeypatch,mutation):
    monkeypatch.setattr(b,'load_dataset',lambda c:{})
    values={'config.json':dict(contract=contract,task_id='t',attempt_id='a'),
        'campaign.json':dict(execution_outcome='ok',evidence_completeness='complete')}
    for name,value in values.items():(tmp_path/name).write_text(json.dumps(value))
    manifest=dict(state='complete',task_id='t',attempt_id='a',files={name:b.sha(tmp_path/name) for name in values})
    if mutation=='coverage':manifest['files'].pop('config.json')
    if mutation=='identity':manifest['task_id']='other'
    if mutation=='hash':manifest['files']['config.json']='0'*64
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):b.analyze_files(contract,tmp_path)


def test_standard_capsule_is_sealable(tmp_path):
    from jiuwenswarm.ccv2.ccv2 import Host
    path=Path(b.__file__).parent/'ccs/standard_benchmark'
    assert Host(tmp_path/'host',session_grants=[]).prepare(path)
