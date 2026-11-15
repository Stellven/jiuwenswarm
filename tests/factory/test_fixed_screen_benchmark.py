"""CPU-only fixed-screen validation and conditional host admission tests."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_fixed_placement_benchmark import contract as fixed_contract, parsed, placement_log, scored_cells
from test_broad_benchmark import contract as broad_contract,dataset,cells,decode
from jiuwenswarm.factory import benchmark,fixed_screen_benchmark as screens
from jiuwenswarm.factory.loop import FactoryLoop
from jiuwenswarm.factory.store import Store


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value));return sha(path)

@pytest.fixture
def contract(fixed_contract):
    c=copy.deepcopy(fixed_contract);c.update(adapter=screens.ADAPTER,version=5,campaign_stage='screen',configuration_change='ahead1')
    c['arms']['B']['environment']['DS4_AHEAD']='1';c['execution_sha256']['fixed_screen_benchmark.py']='a'*64
    return c

@pytest.mark.parametrize('setting',['ahead1','cpu6'])
def test_two_strict_finite_single_changes_validate_without_mutation(contract,setting):
    if setting=='cpu6':
        contract['configuration_change']='cpu6';contract['arms']['B']['environment']['DS4_AHEAD']='0'
        args=contract['arms']['B']['args'];args[args.index('--cpu-threads')+1]='6'
    before=copy.deepcopy(contract)
    assert benchmark.validate_contract(contract) is contract and contract==before
    assert benchmark.protocol(benchmark.phase_cases(contract,dataset(),'speed'),'A',contract).count(b'spec=0 ')==4
    assert len(benchmark.phase_cases(contract,dataset(),'quality'))==8

@pytest.mark.parametrize('change',['other-setting','extra-knob','baseline-cpu','budget','one-arm-budget','confirm','missing-pin','bad-pin','quality-subset'])
def test_unadmitted_change_is_rejected(contract,change):
    if change=='other-setting':contract['configuration_change']='cpu4'
    if change=='extra-knob':contract['arms']['B']['environment']['DS4_ENGRAM_THREADS']='4'
    if change=='baseline-cpu':
        for a in contract['arms'].values():a['args'][a['args'].index('--cpu-threads')+1]='6'
    if change=='budget':
        for a in contract['arms'].values():a['environment']['DS4_EXPERT_BUDGET_BYTES']='75999999999'
    if change=='one-arm-budget':contract['arms']['B']['environment'].pop('DS4_EXPERT_BUDGET_BYTES')
    if change=='confirm':contract['campaign_stage']='confirm'
    if change=='missing-pin':contract['execution_sha256'].pop('fixed_placement_benchmark.py')
    if change=='bad-pin':contract['execution_sha256']['fixed_screen_benchmark.py']='bad'
    if change=='quality-subset':contract['quality_case_indices']=list(range(2))
    with pytest.raises(ValueError):screens.validate_contract(contract)


def screen_rows(c):
    d=dataset();rows=cells(c,d)
    for row in rows:
        for phase in ('quality','speed'):
            value=parsed();screens.engagement(c,row['arm'],value,placement_log())
            row[phase]['fixed_placement_identity']=value['fixed_placement_identity']
    return d,rows


def test_diagnostic_positive_requires_quality_tokens_placement_and_point_gain(contract):
    d,rows=screen_rows(contract);r=screens.analyze(contract,d,rows,decode)
    assert r['verdict']=='fixed_screen_diagnostic_positive'
    assert r['scope']=='fixed_screen_diagnostic' and not r['promotion_authorized'] and not r['performance_acceptance_evaluated']
    assert r['gates']['exact_cross_arm_tokens_and_finish'] and r['gates']['complete_fixed_placement_equal_across_all_processes']

@pytest.mark.parametrize('failure',['token','finish','quality','placement','missing-placement','no-speed-gain'])
def test_failed_screen_is_retained_as_nonpositive(contract,failure):
    d,rows=screen_rows(contract)
    if failure=='token':rows[1]['speed']['requests'][0]['ids'][0]=3
    if failure=='finish':rows[1]['speed']['requests'][0]['finish']='stop'
    if failure=='quality':rows[1]['quality']['requests'][0]['ids']=[66]
    if failure=='placement':
        value=parsed();screens.engagement(contract,'B',value,placement_log(changed_layer=3))
        rows[1]['speed']['fixed_placement_identity']=value['fixed_placement_identity']
    if failure=='missing-placement':rows[0]['quality'].pop('fixed_placement_identity')
    if failure=='no-speed-gain':
        for row in rows[1]['speed']['requests']:row['decode_ms']=1000.
    r=screens.analyze(contract,d,rows,decode)
    assert r['verdict']=='fixed_screen_diagnostic_inconclusive' and not r['performance_acceptance_evaluated']

@pytest.fixture
def campaign(contract,fixed_contract,tmp_path,monkeypatch):
    store=Store(tmp_path/'store');aa=fixed_contract;aa_path=tmp_path/'aa.json';write(aa_path,aa)
    aa_template=dict(id='aa',path=str(aa_path),sha256=sha(aa_path),allowed_hypothesis_ids=['establish_repeatability'])
    aa_policy=dict(max_cycles=1,max_experiments=1,wall_clock_s=100,templates=[aa_template])
    store.create_task(dict(task_id=screens.ORIGIN,objective='original',constraints={'factory_loop':aa_policy}))
    FactoryLoop(store,screens.ORIGIN)
    store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',(screens.ORIGIN,'original-aa',1,'{}'))
    store.create_task(dict(task_id='old-diag',objective='old',constraints={'nonpromoting_diagnostics':{'origin_task_id':screens.ORIGIN}}))
    for i in range(6):store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('old-diag',str(i),i+1,'{}'))
    store.create_task(dict(task_id=screens.AA_TASK,objective='fixed aa',constraints={'factory_loop':aa_policy,'fixed_placement_final_slot':{'origin_task_id':screens.ORIGIN}}))
    store.create_task(dict(task_id='fixed-child',objective='fixed child',constraints={}))
    attempt=store.create_attempt('fixed-child',dict(kind='lab',idem_key='aa',fingerprint='offline',request=dict(contract=aa,contract_sha256=sha(aa_path))))
    store.transition_attempt('fixed-child',attempt['attempt_id'],'running');store.transition_attempt('fixed-child',attempt['attempt_id'],'succeeded')
    baseline=dict(cycle_id='fixed-aa',state='collected',attempt_id=attempt['attempt_id'],contract_sha256=sha(aa_path),contract_path=str(aa_path),child_task_id='fixed-child',contract=aa)
    store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',(screens.AA_TASK,'fixed-aa',1,json.dumps(baseline)))
    root=store.home/'benchmark-spool'/attempt['attempt_id'];root.mkdir(parents=True);(root/'manifest.json').write_text('{}')
    d,aa_rows=scored_cells(aa)
    from jiuwenswarm.factory.fixed_placement_benchmark import analyze as analyze_aa
    report=analyze_aa(aa,d,aa_rows,decode);report['verification']=dict(raw_files_verified=True,independent_native_parse=True,complete_cells=2)
    calls=[]
    def reader(c,p):calls.append((c,p));return copy.deepcopy(report)
    monkeypatch.setattr(benchmark,'analyze_files',reader)
    mode=dict(origin_task_id=screens.ORIGIN,baseline_task_id=screens.AA_TASK,baseline_cycle_id='fixed-aa',baseline_attempt_id=attempt['attempt_id'],baseline_contract_sha256=sha(aa_path),baseline_manifest_sha256=sha(root/'manifest.json'),aggregate_max_experiments=10)
    templates=[]
    for name in ('ahead1','cpu6'):
        c=copy.deepcopy(contract)
        if name=='cpu6':
            c['configuration_change']='cpu6';c['arms']['B']['environment']['DS4_AHEAD']='0';a=c['arms']['B']['args'];a[a.index('--cpu-threads')+1]='6'
        path=tmp_path/(name+'.json');write(path,c)
        templates.append(dict(id=name,path=str(path),sha256=sha(path),allowed_hypothesis_ids=['measure_cpu_scheduling']))
    policy=dict(max_cycles=2,max_experiments=2,wall_clock_s=100,templates=templates)
    store.create_task(dict(task_id='screens',objective='two screens',target='spark-gb10',contract_id=templates[0]['path'],allowed_effects=['process.exec','gpu.use'],constraints=dict(factory_loop=policy,fixed_placement_screens=mode)))
    store.append_observation('screens',dict(obs_id='seed',kind='research',values={}))
    class Fake:
        def __init__(self):self.calls=0
        def submit(self,task,path,key):
            self.calls+=1;return store.create_attempt(task,dict(kind='lab',idem_key=key,fingerprint='offline',request={}))
        def result(self,task,attempt):return dict(state='succeeded',analysis=dict(verdict='fixed_screen_diagnostic_positive'))
    fake=Fake();loop=FactoryLoop(store,'screens',benchmark=fake)
    yield dict(loop=loop,contract=contract,baseline=baseline,report=report,root=root,calls=calls,fake=fake)
    store.close()


def test_host_reparses_qualified_baseline_independently(campaign):
    c=campaign;result=screens.admit_fixed_screens(c['loop'],c['contract'],reserving=True)
    assert result['aggregate_used_before_reservation']==8 and len(c['calls'])==1

@pytest.mark.parametrize('failure',['verdict','tokens','placement','raw','parse','cells'])
def test_failed_aa_qualification_blocks_both_screens(campaign,failure):
    c=campaign;report=c['report']
    if failure=='verdict':report['verdict']='fixed_placement_aa_inconclusive'
    if failure=='tokens':report['raw_token_equal']=False
    if failure=='placement':report['gates']['complete_fixed_placement_equal_across_all_processes']=False
    if failure=='raw':report['verification']['raw_files_verified']=False
    if failure=='parse':report['verification']['independent_native_parse']=False
    if failure=='cells':report['verification']['complete_cells']=1
    with pytest.raises(ValueError,match='qualification failed'):screens.admit_fixed_screens(c['loop'],c['contract'],reserving=True)
    assert c['fake'].calls==0

@pytest.mark.parametrize('failure',['manifest','contract','pending','failed-attempt','profile','image','build','dataset'])
def test_changed_baseline_or_provenance_fails_closed(campaign,failure):
    c=campaign;loop=c['loop'];base=c['baseline'];candidate=copy.deepcopy(c['contract'])
    if failure=='manifest':(c['root']/'manifest.json').write_text('{"changed":1}')
    if failure=='contract':Path(base['contract_path']).write_text('{}')
    if failure=='pending':
        base['state']='submitted';loop.store._db.execute('UPDATE factory_loop_cycles SET record=? WHERE task_id=?',(json.dumps(base),screens.AA_TASK))
    if failure=='failed-attempt':loop.store._db.execute("UPDATE attempts SET state='failed' WHERE attempt_id=?",(base['attempt_id'],))
    if failure=='profile':candidate['arms']['A']['environment']['DS4_AHEAD']='1'
    if failure=='image':candidate['image']['id']='sha256:'+'c'*64
    if failure=='build':Path(candidate['candidate_build']['receipt_path']).write_text('{}')
    if failure=='dataset':candidate['dataset_sha256']='b'*64
    with pytest.raises(ValueError):screens.admit_fixed_screens(loop,candidate,reserving=True)


def test_two_unique_cycles_count_old_scopes_and_replay_durably(campaign):
    c=campaign;loop=c['loop'];first=loop.select('one',['seed'],'measure_cpu_scheduling','ahead1',0)
    assert loop.select('one',['seed'],'measure_cpu_scheduling','ahead1',0)==first
    sent=loop.execute('one');assert loop.execute('one')==sent and c['fake'].calls==1
    loop.collect('one')
    with pytest.raises(ValueError,match='may not be repeated'):loop.select('duplicate',['seed'],'measure_cpu_scheduling','ahead1',1)
    loop.select('two',['seed'],'measure_cpu_scheduling','cpu6',1);loop.execute('two');loop.collect('two')
    assert c['fake'].calls==2 and loop.status()['remaining_experiments']==0
    assert screens.admit_fixed_screens(loop,c['contract'],reserving=False)['aggregate_used_before_reservation']==10


def test_total_budget_exhaustion_blocks_new_screen(campaign):
    c=campaign;loop=c['loop']
    for i in range(2):loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('old-diag','more'+str(i),7+i,'{}'))
    with pytest.raises(ValueError,match='aggregate cap'):loop.select('one',['seed'],'measure_cpu_scheduling','ahead1',0)
    assert c['fake'].calls==0


def test_dispatch_rechecks_conditional_gate_after_selection(campaign):
    c=campaign;loop=c['loop'];loop.select('one',['seed'],'measure_cpu_scheduling','ahead1',0)
    c['report']['raw_token_equal']=False
    with pytest.raises(ValueError,match='qualification failed'):loop.execute('one')
    assert c['fake'].calls==0


def test_acceptance_is_prohibited_and_lock_is_shared(campaign,monkeypatch):
    from jiuwenswarm.factory.acceptance import validate
    from jiuwenswarm.factory import loop as loop_module
    c=campaign;loop=c['loop'];locks=[]
    with pytest.raises(ValueError,match='acceptance and promotion prohibited'):validate(loop.store,'screens')
    monkeypatch.setattr(loop_module.fcntl,'flock',lambda handle,kind:locks.append(Path(handle.name).name))
    loop.select('one',['seed'],'measure_cpu_scheduling','ahead1',0)
    assert [name for name in locks if name.endswith('.lock')]==[hashlib.sha256(screens.ORIGIN.encode()).hexdigest()+'.lock']

@pytest.mark.parametrize('missing_layer',[False,True])
def test_actual_worker_dispatch_with_v5_protocol_and_partial_failure(contract,tmp_path,monkeypatch,missing_layer):
    from test_fixed_placement_benchmark import test_real_worker_dispatch_uses_v4_cases_protocol_and_effective_placement as run_physical_boundary_case
    run_physical_boundary_case(contract,tmp_path,monkeypatch,missing_layer)


def test_old_fixed_aa_guard_counts_new_fixed_screen_reservations(campaign):
    from types import SimpleNamespace
    from jiuwenswarm.factory.fixed_placement_benchmark import admit_final_slot
    c=campaign;loop=c['loop']
    for i in range(2):loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('screens','reserved'+str(i),i+1,'{}'))
    old_guard=SimpleNamespace(task={'constraints':{'fixed_placement_final_slot':{'origin_task_id':screens.ORIGIN,'aggregate_max_experiments':10}}},policy={'max_cycles':1,'max_experiments':1},store=loop.store)
    with pytest.raises(ValueError,match='aggregate cap'):admit_final_slot(old_guard,c['baseline']['contract'],reserving=True)


def test_last_cpu6_task_can_admit_only_cpu6_with_one_aggregate_slot(campaign):
    c=campaign;parent=c['loop'];store=parent.store
    store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('screens','old-ahead',1,json.dumps({'contract':c['contract']})))
    task=copy.deepcopy(parent.task)
    # Build a new task record from immutable admitted inputs, preserving the v5 policy shape.
    constraints=copy.deepcopy(task['constraints'])
    constraints['factory_loop']['templates']=[t for t in constraints['factory_loop']['templates'] if t['id']=='cpu6']
    store.create_task(dict(task_id='last-cpu6',objective='one remaining cpu6',target='spark-gb10',allowed_effects=['process.exec','gpu.use'],constraints=constraints))
    store.append_observation('last-cpu6',dict(obs_id='seed',kind='research',values={}))
    loop=FactoryLoop(store,'last-cpu6')
    from jiuwenswarm.factory.store import ScopeDenied
    with pytest.raises(ScopeDenied):loop.select('wrong',['seed'],'measure_cpu_scheduling','ahead1',0)
    result=loop.select('last',['seed'],'measure_cpu_scheduling','cpu6',0)
    assert result['contract']['configuration_change']=='cpu6' and len(loop.status()['cycles'])==1
    with pytest.raises(ValueError):screens.admit_fixed_screens(loop,result['contract'],reserving=True)
