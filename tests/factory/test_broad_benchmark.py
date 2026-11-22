"""CPU-only additive broad protocol and actual-cell analysis tests."""
import copy
import hashlib
import json
import pytest
from jiuwenswarm.factory import benchmark as b
from jiuwenswarm.factory import broad_benchmark as broad
from jiuwenswarm.factory.loop import FactoryLoop
from jiuwenswarm.factory.store import ScopeDenied, Store

@pytest.fixture
def contract():
    args=['--pack','/pack','--max-context','8192','--eos','1','--vision','off','--dspark','none',
        '--prefill-chunk','256','--cpu-threads','8','--vram-experts','1.0','--reserve-mib','16384',
        '--ssd-cache','0','--mmap-experts','on','--experts','6','--verbose','--dspark-conf','0.65','--no-expert-cache']
    env=dict(DS4_AHEAD='0',DS4_ASYNC_T='4',DS4_COPY_ALL='0',DS4_ENGRAM_CACHE_MB='64',DS4_ENGRAM_THREADS='2',DS4_STORE_GB='0',DS4_UMA_HEADROOM_GIB='16',STRATA_DS4_REUSE='0')
    a=dict(args=args,environment=env)
    return dict(adapter=broad.ADAPTER,version=3,stage='main',campaign_stage='aa',configuration_change='aa',
        primary_metric='prefill_plus_decode_output_tokens_per_second',quality_case_indices=list(range(8)),speed_case_indices=list(range(4)),
        target='spark-gb10',tolerance='arc-exact-answer-regression-v1',image={'id':'sha256:'+'a'*64},
        arms={'A':a,'B':copy.deepcopy(a)},order=list('AB'),
        runtime_bounds=dict(fresh_process_cells=2,phase_containers=4,observer_interval_ms=1000),
        workload={'pack':'/pack','model_root':'/models'},limits=dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,extra_swap_bytes=0,quality_timeout_s=900,speed_timeout_s=300),
        gates=dict(minimum_accuracy=.5,minimum_speedup=1.05,confidence=.95,bootstrap_resamples=20000,seed=42,correctness='no_per_question_regression'),
        campaign_timeout_s=1200,dataset_sha256='a'*64,execution_sha256={n:'a'*64 for n in (*b.EXECUTION_FILES,'broad_benchmark.py')})

@pytest.mark.parametrize('name',list(broad.CHANGES))
def test_only_finite_single_changes_admit(contract,name):
    c=contract;c['configuration_change']=name;c['campaign_stage']='aa' if name=='aa' else 'screen'
    change=broad.CHANGES[name]
    if change:
        section,key,value=change
        if section=='args':c['arms']['B']['args'][c['arms']['B']['args'].index(key)+1]=value
        else:c['arms']['B'][section][key]=value
    assert b.validate_contract(c) is c
    c['arms']['B']['environment']['DS4_STORE_GB']='1'
    with pytest.raises(ValueError):b.validate_contract(c)

@pytest.mark.parametrize('key,value',[('quality_case_indices',list(range(2))),('campaign_timeout_s',1201),('order',list('BA')),('phases',['speed']),('runtime_bounds',{})])
def test_reject_changed_protocol(contract,key,value):
    contract[key]=value
    with pytest.raises(ValueError):b.validate_contract(contract)

def test_aa_spec_is_disabled_for_both_arms(contract):
    cases=[dict(ids=[2,3],max_new_tokens=128)]
    assert b.protocol(cases,'A',contract)==b.protocol(cases,'B',contract)
    assert b'spec=0 ' in b.protocol(cases,'B',contract)

def dataset():
    return dict(quality=[dict(id=str(i),ids=[2],allowed_letters=['A','B'],expected_letter='A',max_new_tokens=8) for i in range(64)],speed=[dict(id=str(i),ids=[2]*512,max_new_tokens=128) for i in range(4)])

def cells(c,d):
    result=[]
    for i,arm in enumerate(c['order'],1):
        qs=b.phase_cases(c,d,'quality');ss=b.phase_cases(c,d,'speed')
        result.append(dict(index=i,arm=arm,
            quality=dict(cases=qs,requests=[dict(ids=[65],finish='length') for _ in qs]),
            speed=dict(cases=ss,requests=[dict(ids=[2]*128,finish='length',generated_tokens=128,prefill_ms=100.,decode_ms=1000. if arm=='A' else 800.,accepted_drafts=0,offered_drafts=0) for _ in ss])))
    return result

def decode(ids,letters):return dict(answer=chr(ids[0]),text=chr(ids[0]))

def test_aa_and_screen_cannot_accept(contract):
    d=dataset();r=broad.analyze(contract,d,cells(contract,d),decode)
    assert r['verdict']=='aa_valid' and not r['performance_acceptance_evaluated']
    contract['configuration_change']='cpu4';contract['campaign_stage']='screen';contract['arms']['B']['args'][contract['arms']['B']['args'].index('--cpu-threads')+1]='4'
    r=broad.analyze(contract,d,cells(contract,d),decode)
    assert r['verdict']=='screen_candidate' and not r['performance_acceptance_evaluated']

def test_aa_mismatch_fails_and_confirm_uses_actual_two_pairs(contract):
    d=dataset();rows=cells(contract,d);rows[1]['speed']['requests'][0]['ids'][0]=3
    assert broad.analyze(contract,d,rows,decode)['verdict']=='aa_invalid'
    contract.update(campaign_stage='confirm',configuration_change='cpu4',quality_case_indices=list(range(64)),order=list('ABBA'),campaign_timeout_s=2700,runtime_bounds=dict(fresh_process_cells=4,phase_containers=8,observer_interval_ms=1000))
    contract['arms']['B']['args'][contract['arms']['B']['args'].index('--cpu-threads')+1]='4'
    rows=cells(contract,d);r=broad.analyze(contract,d,rows,decode)
    assert r['verdict']=='accept' and r['speed']['bootstrap']['independent_pairs']==2
    rows[1]['quality']['requests'][0]['ids']=[66]
    assert broad.analyze(contract,d,rows,decode)['verdict']=='rejectQuality'

def test_loop_requires_aa_before_broad_screen(contract,tmp_path):
    contract['campaign_stage']='screen';contract['configuration_change']='cpu4';contract['arms']['B']['args'][contract['arms']['B']['args'].index('--cpu-threads')+1]='4'
    path=tmp_path/'screen.json';path.write_text(json.dumps(contract))
    template=dict(id='cpu4-screen',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),allowed_hypothesis_ids=['measure_cpu_scheduling'])
    with Store(tmp_path/'store') as store:
        store.create_task(dict(task_id='parent',objective='Broad experiment',contract_id=str(path),allowed_effects=['process.exec','gpu.use'],constraints={'factory_loop':dict(max_cycles=10,max_experiments=10,wall_clock_s=100,templates=[template])}))
        store.append_observation('parent',dict(obs_id='seed',kind='research',values={}))
        with pytest.raises(ScopeDenied,match='A/A first'):
            FactoryLoop(store,'parent').select('first',['seed'],'measure_cpu_scheduling','cpu4-screen',0)

def test_aa_selection_replay_is_durable(contract,tmp_path):
    path=tmp_path/'aa.json';path.write_text(json.dumps(contract))
    template=dict(id='aa-aa',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),allowed_hypothesis_ids=['establish_repeatability'])
    with Store(tmp_path/'store') as store:
        store.create_task(dict(task_id='parent',objective='Broad experiment',contract_id=str(path),allowed_effects=['process.exec','gpu.use'],constraints={'factory_loop':dict(max_cycles=10,max_experiments=10,wall_clock_s=100,templates=[template])}))
        store.append_observation('parent',dict(obs_id='seed',kind='research',values={}))
        loop=FactoryLoop(store,'parent')
        first=loop.select('aa',['seed'],'establish_repeatability','aa-aa',0)
        replay=loop.select('aa',['seed'],'establish_repeatability','aa-aa',0)
        assert first==replay and loop.status()['remaining_experiments']==9

def test_aa_timing_gate_separate_from_token_repeatability(contract):
    d=dataset();rows=cells(contract,d)
    report=broad.analyze(contract,d,rows,decode)
    assert report['verdict']=='aa_valid'
    assert report['gates']['aa_timing_stable'] is False
    for row in rows[1]['speed']['requests']:row['decode_ms']=1000.
    report=broad.analyze(contract,d,rows,decode)
    assert report['gates']['aa_timing_stable'] is True

@pytest.mark.parametrize('rates',[(100.,105.1,210.2,200.),(100.,101.,150.,100.)])
def test_confirm_requires_both_pairs_and_process_separation(contract,rates):
    contract.update(campaign_stage='confirm',configuration_change='cpu4',quality_case_indices=list(range(64)),order=list('ABBA'),campaign_timeout_s=2700,runtime_bounds=dict(fresh_process_cells=4,phase_containers=8,observer_interval_ms=1000))
    contract['arms']['B']['args'][contract['arms']['B']['args'].index('--cpu-threads')+1]='4'
    d=dataset();rows=cells(contract,d)
    for cell,rate in zip(rows,rates):
        for row in cell['speed']['requests']:row['decode_ms']=128000/rate-100
    report=broad.analyze(contract,d,rows,decode)
    assert report['verdict']=='speedNoImprovement'
    assert report['speed']['bootstrap']['interpretation']=='descriptive_exploratory_not_reliable_95_percent_confidence'

@pytest.fixture
def diagnostic_loop(contract,tmp_path,monkeypatch):
    store=Store(tmp_path/'store')
    origin=copy.deepcopy(contract);raw=json.dumps(origin).encode();path=tmp_path/'origin.json';path.write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
    template=dict(id='aa-aa',path=str(path),sha256=digest,allowed_hypothesis_ids=['establish_repeatability'])
    policy=dict(max_cycles=9,max_experiments=9,wall_clock_s=100,templates=[template])
    for taskid in ('origin','origin-child'):
        store.create_task(dict(task_id=taskid,objective='test',contract_id=str(path),constraints={'factory_loop':policy}))
    FactoryLoop(store,'origin')
    attempt=store.create_attempt('origin-child',dict(kind='lab',idem_key='aa',fingerprint='test',request=dict(contract=origin,contract_sha256=digest)))
    store.transition_attempt('origin-child',attempt['attempt_id'],'running');store.transition_attempt('origin-child',attempt['attempt_id'],'succeeded')
    cycle=dict(cycle_id='aa',state='collected',attempt_id=attempt['attempt_id'],contract_sha256=digest,contract_path=str(path),contract=origin,child_task_id='origin-child')
    store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('origin','aa',1,json.dumps(cycle)))
    rawroot=store.home/'benchmark-spool'/attempt['attempt_id'];rawroot.mkdir(parents=True);(rawroot/'manifest.json').write_text('{}')
    mode=dict(origin_task_id='origin',origin_cycle_id='aa',origin_attempt_id=attempt['attempt_id'],origin_contract_sha256=digest,origin_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),aggregate_max_experiments=10)
    store.create_task(dict(task_id='diagnostic',objective='diagnostic',contract_id=str(path),constraints=dict(factory_loop=policy,nonpromoting_diagnostics=mode)))
    calls=[]
    def analyze_files(c,p):
        calls.append((c,p));return dict(verdict='aa_invalid',verification=dict(raw_files_verified=True),gates=dict(sampled_no_per_question_regression=True,aa_timing_stable=True))
    monkeypatch.setattr(b,'analyze_files',analyze_files)
    candidate=copy.deepcopy(origin);candidate.update(campaign_stage='screen',configuration_change='cpu4');candidate['arms']['B']['args'][candidate['arms']['B']['args'].index('--cpu-threads')+1]='4'
    yield FactoryLoop(store,'diagnostic'),candidate,rawroot,calls
    store.close()

def test_diagnostic_independently_rechecks_original_failed_aa(diagnostic_loop):
    loop,candidate,root,calls=diagnostic_loop
    assert loop._diagnostic_admission(candidate,reserving=True)
    assert len(calls)==1
    candidate['arms']['A']['environment']['DS4_ENGRAM_THREADS']='4'
    with pytest.raises(ScopeDenied,match='baseline profile'):loop._diagnostic_admission(candidate,reserving=True)

def test_diagnostic_never_admits_confirm_or_changed_raw_manifest(diagnostic_loop):
    loop,candidate,root,calls=diagnostic_loop
    candidate['campaign_stage']='confirm'
    with pytest.raises(ScopeDenied,match='screen experiments only'):loop._diagnostic_admission(candidate,reserving=True)
    candidate['campaign_stage']='screen';(root/'manifest.json').write_text('{"changed":true}')
    with pytest.raises(ScopeDenied,match='raw manifest changed'):loop._diagnostic_admission(candidate,reserving=True)

def test_diagnostic_budget_counts_other_continuations(diagnostic_loop):
    loop,candidate,root,calls=diagnostic_loop
    constraints=copy.deepcopy(loop.task['constraints'])
    loop.store.create_task(dict(task_id='other-continuation',objective='other',constraints=constraints))
    for i in range(9):loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('other-continuation',str(i),i+1,'{}'))
    with pytest.raises(ScopeDenied,match='Aggregate'):loop._diagnostic_admission(candidate,reserving=True)

def test_diagnostic_rejects_repeated_setting(diagnostic_loop):
    loop,candidate,root,calls=diagnostic_loop
    loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('diagnostic','prior',1,json.dumps({'contract':candidate})))
    with pytest.raises(ScopeDenied,match='may not be repeated'):loop._diagnostic_admission(candidate,reserving=True)

def test_diagnostic_requires_stable_original_aa_timing(diagnostic_loop,monkeypatch):
    loop,candidate,root,calls=diagnostic_loop
    monkeypatch.setattr(b,'analyze_files',lambda c,p:dict(verdict='aa_invalid',verification=dict(raw_files_verified=True),gates=dict(sampled_no_per_question_regression=True,aa_timing_stable=False)))
    with pytest.raises(ScopeDenied,match='independently verified failed A/A'):loop._diagnostic_admission(candidate,reserving=True)
