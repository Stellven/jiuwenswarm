import copy
import json
from pathlib import Path
import pytest
from jiuwenswarm.factory.engine_adapters import parse_protocol, protocol, validate_contract
from jiuwenswarm.factory.jobs import Jobs


def contract():
    return dict(adapter='strata-v1',contract_id='spark-test-v1',version=1,target='spark-gb10',
        tolerance='canonical-token-ids-and-finish',scope='Synthetic protocol fixture',
        assets=dict(identity_path='/assets.json',identity_sha256='a'*64),
        limits=dict(cpus=8,memory_bytes=104*2**30,extra_swap_bytes=0,guard_gib=8,timeout_s=900),
        workload=dict(argv=['--pack','/pack','--experts','6','--mmap-experts','on','--dspark','none'],
            environment={'STRATA_DS4_REUSE':'0'},requests=[dict(ids=[1,2,3],max_new_tokens=2)]*2))


def stdout():
    return 'READY 8192 stop\nT 42\nT 43\nDONE 2 3 100 20 length 0 0 0 0 0\nT 42\nT 43\nDONE 2 3 50 10 length 0 0 0 0 0\n'


def test_rates_and_raw_integrity_are_separate_from_canonical_output():
    result=parse_protocol(stdout(),'ds4: experts per word: 6 (full quality)',contract())
    assert result['repeat_equal'] is True
    assert [v['decode_tps'] for v in result['requests']]==[100,200]
    changed=parse_protocol(stdout().replace('100 20','100 40'),'ds4: experts per word: 6',contract())
    assert changed['raw_stdout_sha256']!=result['raw_stdout_sha256']
    assert changed['requests'][0]['canonical_sha256']==result['requests'][0]['canonical_sha256']
    assert b'spec=0' in protocol(contract())


@pytest.mark.parametrize('bad',[
    lambda s:s.replace('DONE 2 3','DONE 1 3',1),
    lambda s:s.replace(' 20 length',' nan length'),
    lambda s:s.replace('DONE 2 3','DONE 2 4',1),
    lambda s:s.replace('length 0 0','length 1 1',1),
    lambda s:s.replace(' 0 0 0\n',' 0 0 1\n',1),
    lambda s:s.replace('T 43\n','T 43\nT 44\n',1),
    lambda s:s.rsplit('DONE',1)[0],
])
def test_malformed_or_misrepresented_native_protocol_rejected(bad):
    with pytest.raises(ValueError):parse_protocol(bad(stdout()),'experts per word: 6',contract())


def test_effective_reduced_expert_count_rejected():
    with pytest.raises(ValueError,match='Full-six'):parse_protocol(stdout(),'experts per word: 5',contract())


def test_contract_boundary_and_env_rejected():
    c=contract();c['limits']['extra_swap_bytes']=1024
    with pytest.raises(ValueError):validate_contract(c)
    c=contract();c['workload']['environment']['DS4_SKIP_EXPERTS']='1'
    with pytest.raises(ValueError):validate_contract(c)


def test_attempt_limits_are_host_enforced_and_replay_safe(store,monkeypatch):
    store._db.execute("UPDATE tasks SET constraints=? WHERE task_id='t'",(json.dumps({'attempt_limits':{'build':1}}),))
    jobs=Jobs(store)
    monkeypatch.setattr(jobs,'_call',lambda *a,**k:type('R',(),{'stdout':'job-abc'})())
    first=jobs.submit('t','build',{},'one','build',['true'],10,{})
    assert jobs.submit('t','build',{},'one','build',['true'],10,{})['attempt_id']==first['attempt_id']
    with pytest.raises(ValueError,match='budget exhausted'):
        jobs.submit('t','build',{},'two','build',['true'],10,{})


def test_operator_contract_path_and_internal_id_are_same_binding(tmp_path):
    from jiuwenswarm.factory.contract import load_for_task
    path=tmp_path/'operator-contract.json';path.write_text(json.dumps(contract()))
    task={'contract_id':str(path)}
    assert load_for_task(task,str(path))['contract_id']=='spark-test-v1'
    assert load_for_task(task,'spark-test-v1').path==path
    with pytest.raises(ValueError,match='must match'):
        load_for_task(task,'other-contract')


def test_host_docker_without_group_prefix_is_real_argv(monkeypatch):
    from jiuwenswarm.factory import lab_runner
    monkeypatch.setattr(lab_runner,'DOCKER_PREFIX','')
    monkeypatch.delenv('FACTORY_DOCKER',raising=False)
    calls=[]
    monkeypatch.setattr(lab_runner.subprocess,'run',lambda argv,**kw:calls.append(argv))
    lab_runner.docker(['image','inspect','sha256:'+'a'*64])
    assert calls==[['docker','image','inspect','sha256:'+'a'*64]]


def test_reference_accept_requires_verified_matching_cells(store,tmp_path):
    from jiuwenswarm.factory.acceptance import validate
    c=contract();path=tmp_path/'contract.json';path.write_text(json.dumps(c))
    store._db.execute("UPDATE tasks SET target=?,contract_id=? WHERE task_id='t'",(json.dumps({'profile':'spark-gb10'}),str(path)))
    with pytest.raises(ValueError,match='3 complete verified'):
        validate(store,'t')
    for i in range(3):
        store.append_observation('t',dict(obs_id='cell-'+str(i),kind='lab_result',values=dict(
            execution_outcome='ok',evidence_completeness='complete',comparison_group='a'*64,
            verification={'boundary_verified':True,'replay_verified':True},requests=[{'canonical_sha256':'b'*64}]*2)))
    validate(store,'t')
    store.append_observation('t',dict(obs_id='different',kind='lab_result',values=dict(
        execution_outcome='ok',evidence_completeness='complete',comparison_group='a'*64,
        verification={'boundary_verified':True,'replay_verified':True},requests=[{'canonical_sha256':'c'*64}])))
    with pytest.raises(ValueError,match='outputs/configurations differ'):
        validate(store,'t')
