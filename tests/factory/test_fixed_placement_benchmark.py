"""CPU-only v4 tests use synthetic source/build receipts, never Docker or GPU."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_broad_benchmark import contract as broad_contract, dataset, cells, decode
from jiuwenswarm.factory import benchmark, fixed_placement_benchmark as fixed
from jiuwenswarm.factory.benchmark_worker import check_source_pins
from jiuwenswarm.factory.contract import load
from jiuwenswarm.factory.loop import FactoryLoop
from jiuwenswarm.factory.store import Store


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path,value):path.write_text(json.dumps(value));return sha(path)

@pytest.fixture
def contract(broad_contract,tmp_path,monkeypatch):
    """Explicit synthetic files stand in for the exact four committed files."""
    source_root=tmp_path/'source';source_files={}
    for name in fixed.SOURCE_FILES:
        path=source_root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
        source_files[name]=sha(path)
    monkeypatch.setattr(fixed,'SOURCE_FILES',source_files)
    patch=tmp_path/'patch';patch.write_text('synthetic fixed-placement source patch')
    monkeypatch.setattr(fixed,'PATCH',sha(patch))
    source_record=dict(source=str(source_root),candidate_commit=fixed.COMMIT,candidate_tree=fixed.TREE,
        base_commit='ffa80d73133ea5c548aefe57889a16e8085a938f',clean=True,patch_sha256=sha(patch),files=source_files)
    source_path=tmp_path/'SOURCE.json';write_json(source_path,source_record)
    receipt=dict(status='success',target='spark-gb10',host_architecture='aarch64',
        source=dict(commit=fixed.COMMIT,tree=fixed.TREE),dependency=dict(commit='3cf03257f219afbe7334045ff7c6a06ac68c627d'),
        image=dict(Id='sha256:'+'b'*64,Architecture='arm64',Config=dict(Labels={'factory.source':fixed.COMMIT})),executable_sha256='e'*64)
    receipt_path=tmp_path/'build-record.json';write_json(receipt_path,receipt)
    c=copy.deepcopy(broad_contract);c.update(adapter=fixed.ADAPTER,version=4,promotion_authorized=False,
        expected_placement_layers=40,expected_experts_per_layer=384,image={'id':receipt['image']['Id']},
        candidate_build=dict(receipt_path=str(receipt_path),receipt_sha256=sha(receipt_path),
            source_record_path=str(source_path),source_record_sha256=sha(source_path),patch_path=str(patch)))
    for a in c['arms'].values():a['environment']['DS4_EXPERT_BUDGET_BYTES']=fixed.BUDGET
    c['execution_sha256'].update({'fixed_placement_benchmark.py':'a'*64,'engine_adapters.py':'a'*64})
    return c


def test_general_dispatch_fixed_contract_is_additive_and_nonmutating(contract,tmp_path):
    original=copy.deepcopy(contract)
    assert benchmark.validate_contract(contract) is contract
    assert contract==original
    path=tmp_path/'contract.json';write_json(path,contract)
    assert load(str(path))==contract
    cases=benchmark.phase_cases(contract,dataset(),'speed')
    assert len(cases)==4 and len(benchmark.phase_cases(contract,dataset(),'quality'))==8
    assert benchmark.protocol(cases,'A',contract)==benchmark.protocol(cases,'B',contract)
    assert b'spec=0 ' in benchmark.protocol(cases,'B',contract)

@pytest.mark.parametrize('field,value',[('status','failed'),('target','other'),('host_architecture','x86_64'),('executable_sha256','missing')])
def test_reject_incomplete_native_build_receipt_even_with_refrozen_digest(contract,field,value):
    build=contract['candidate_build'];path=Path(build['receipt_path']);receipt=json.loads(path.read_text());receipt[field]=value
    build['receipt_sha256']=write_json(path,receipt)
    with pytest.raises(ValueError):fixed.validate_contract(contract)

@pytest.mark.parametrize('field,value',[('commit','wrong'),('tree','wrong')])
def test_reject_wrong_source_identity_in_build(contract,field,value):
    build=contract['candidate_build'];path=Path(build['receipt_path']);receipt=json.loads(path.read_text());receipt['source'][field]=value
    build['receipt_sha256']=write_json(path,receipt)
    with pytest.raises(ValueError,match='source/dependency/image'):fixed.validate_contract(contract)

@pytest.mark.parametrize('mutation',['image','arch','label','dependency'])
def test_reject_unmatched_image_or_dependency(contract,mutation):
    build=contract['candidate_build'];path=Path(build['receipt_path']);r=json.loads(path.read_text())
    if mutation=='image':r['image']['Id']='sha256:'+'c'*64
    if mutation=='arch':r['image']['Architecture']='amd64'
    if mutation=='label':r['image']['Config']['Labels']['factory.source']='wrong'
    if mutation=='dependency':r['dependency']['commit']='wrong'
    build['receipt_sha256']=write_json(path,r)
    with pytest.raises(ValueError):fixed.validate_contract(contract)

@pytest.mark.parametrize('mutation',['receipt','source-record','source-file','patch','empty-files','omit-file','base','dirty'])
def test_independent_source_and_patch_hash_checks(contract,mutation):
    build=contract['candidate_build'];sp=Path(build['source_record_path']);source=json.loads(sp.read_text())
    if mutation=='receipt':Path(build['receipt_path']).write_text('{}')
    if mutation=='source-record':sp.write_text('{}')
    if mutation=='source-file':(Path(source['source'])/'src/dsv41/ds4_model.cu').write_text('changed')
    if mutation=='patch':Path(build['patch_path']).write_text('changed')
    if mutation=='empty-files':source['files']={}
    if mutation=='omit-file':source['files'].pop('src/dsv41/ds4_model.cu')
    if mutation=='base':source['base_commit']='wrong'
    if mutation=='dirty':source['clean']=False
    if mutation in ('empty-files','omit-file','base','dirty'):build['source_record_sha256']=write_json(sp,source)
    with pytest.raises(ValueError):fixed.validate_contract(contract)

@pytest.mark.parametrize('mutation',['budget','one-arm','baseline','confirm','missing-pin','bad-pin','layers'])
def test_reject_other_controls_or_legacy_policy_changes(contract,mutation):
    if mutation=='budget':
        for a in contract['arms'].values():a['environment']['DS4_EXPERT_BUDGET_BYTES']='1'
    if mutation=='one-arm':contract['arms']['B']['environment'].pop('DS4_EXPERT_BUDGET_BYTES')
    if mutation=='baseline':
        for a in contract['arms'].values():a['args'][a['args'].index('--cpu-threads')+1]='4'
    if mutation=='confirm':contract['campaign_stage']='confirm'
    if mutation=='missing-pin':contract['execution_sha256'].pop('engine_adapters.py')
    if mutation=='bad-pin':contract['execution_sha256']['engine_adapters.py']='bad'
    if mutation=='layers':contract['expected_placement_layers']=39
    with pytest.raises(ValueError):fixed.validate_contract(contract)


def placement_log(*,changed_layer=None,omit=None,duplicate=None,budget=None,aggregate_bad=False):
    rows=[];total=14695981039346656037
    for i in range(40):
        value=i+1000+(1 if changed_layer==i else 0)
        rows.append(f'ds4: fixed placement layer={i} experts=384 resident=220 fnv1a64={value:016x}')
        for byte in value.to_bytes(8,'little'):total=((total^byte)*1099511628211)&((1<<64)-1)
    if omit is not None:rows.pop(omit)
    if duplicate is not None:rows.insert(duplicate,rows[duplicate])
    return ('ds4: Engram rows read on 2 threads, issued with the tokens, collected before their layer; row cache 64 MB (1024 rows)\n'
        +'ds4: prompts in chunks of 256)\n'
        +(budget or f'ds4: fixed expert budget requested={fixed.BUDGET} effective={fixed.BUDGET} safe=80000000000 bytes')+'\n'
        +'\n'.join(rows)+f'\nds4: fixed placement layers=40 fnv1a64={(total+int(aggregate_bad))%(1<<64):016x}\n')


def parsed():return dict(requests=[dict(accepted_drafts=0,offered_drafts=0)])

def test_effective_budget_and_complete_placement_hash_recomputed(contract):
    report=parsed();benchmark.verify_prefill_engagement(contract,'A',report,placement_log())
    assert len(report['fixed_placement_identity']['layers'])==40
    assert report['fixed_placement_identity']['effective_budget']==fixed.BUDGET

@pytest.mark.parametrize('change',[
    {'omit':5},{'duplicate':5},{'aggregate_bad':True},
    {'budget':'ds4: fixed expert budget requested=76000000000 effective=75999999999 safe=80000000000 bytes'},
    {'budget':'ds4: fixed expert budget requested=76000000000 effective=76000000000 safe=75999999999 bytes'},
    {'budget':'no budget startup marker'},
])
def test_missing_duplicate_or_inconsistent_placement_cannot_pass(contract,change):
    with pytest.raises(ValueError):fixed.engagement(contract,'A',parsed(),placement_log(**change))

@pytest.mark.parametrize('change',['reorder','malformed','wrong-experts','missing-aggregate','duplicate-budget','duplicate-aggregate','drafts','overlong-layer-hash','overlong-total-hash','extra-malformed-layer'])
def test_other_malformed_effective_evidence_fails_closed(contract,change):
    log=placement_log();report=parsed()
    if change=='reorder':log=log.replace('layer=0 experts','layer=99 experts')
    if change=='malformed':log=log.replace('fnv1a64=00000000000003e8','fnv1a64=invalid')
    if change=='wrong-experts':log=log.replace('layer=0 experts=384','layer=0 experts=383')
    if change=='missing-aggregate':log='\n'.join(log.splitlines()[:-1])
    if change=='duplicate-budget':log+='ds4: fixed expert budget requested=76000000000 effective=76000000000 safe=80000000000 bytes\n'
    if change=='duplicate-aggregate':log+='\n'+log.splitlines()[-1]
    if change=='overlong-layer-hash':log=log.replace('fnv1a64=00000000000003e8','fnv1a64=00000000000003e80')
    if change=='overlong-total-hash':log=log.rstrip()+'0\n'
    if change=='extra-malformed-layer':log+='ds4: fixed placement layer=malformed\n'
    if change=='drafts':report['requests'][0]['offered_drafts']=1
    with pytest.raises(ValueError):fixed.engagement(contract,'A',report,log)


def scored_cells(c):
    d=dataset();rows=cells(c,d)
    for cell in rows:
        for phase in ('quality','speed'):
            report=parsed();fixed.engagement(c,cell['arm'],report,placement_log())
            cell[phase]['fixed_placement_identity']=report['fixed_placement_identity']
    return d,rows


def test_aa_never_performance_accepts_and_requires_all_four_equal_placements(contract):
    d,rows=scored_cells(contract);r=fixed.analyze(contract,d,rows,decode)
    assert r['verdict']=='fixed_placement_aa_observed_repeatable'
    assert not r['promotion_authorized'] and not r['performance_acceptance_evaluated']
    other=parsed();fixed.engagement(contract,'B',other,placement_log(changed_layer=5))
    rows[1]['speed']['fixed_placement_identity']=other['fixed_placement_identity']
    r=fixed.analyze(contract,d,rows,decode)
    assert r['verdict']=='fixed_placement_aa_inconclusive'
    assert not r['gates']['complete_fixed_placement_equal_across_all_processes']


def test_missing_process_identity_or_repeated_token_mismatch_stays_inconclusive(contract):
    d,rows=scored_cells(contract);rows[0]['quality'].pop('fixed_placement_identity')
    assert fixed.analyze(contract,d,rows,decode)['verdict']=='fixed_placement_aa_inconclusive'
    d,rows=scored_cells(contract);rows[1]['speed']['requests'][0]['ids'][0]=3
    assert fixed.analyze(contract,d,rows,decode)['verdict']=='fixed_placement_aa_inconclusive'


def test_legacy_adapter_rejects_fixed_budget_even_identical_arms(contract):
    old=fixed.shaped(contract)
    for a in old['arms'].values():a['environment']['DS4_EXPERT_BUDGET_BYTES']=fixed.BUDGET
    with pytest.raises(ValueError):benchmark.validate_contract(old)

@pytest.fixture
def final_loop(contract,tmp_path):
    store=Store(tmp_path/'store');path=tmp_path/'fixed.json';write_json(path,contract)
    template=dict(id='fixed-aa',path=str(path),sha256=sha(path),allowed_hypothesis_ids=['establish_repeatability'])
    origin='spark-broad-throughput-004'
    policy=dict(max_cycles=1,max_experiments=1,wall_clock_s=100,templates=[template])
    store.create_task(dict(task_id=origin,objective='origin',constraints={'factory_loop':policy}))
    FactoryLoop(store,origin)
    store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',(origin,'original-aa',1,'{}'))
    store.create_task(dict(task_id='diag',objective='prior diagnostics',constraints={'nonpromoting_diagnostics':{'origin_task_id':origin}}))
    task=dict(task_id='final',objective='One final diagnostic',target='spark-gb10',contract_id=str(path),
        allowed_effects=['process.exec','gpu.use'],constraints=dict(factory_loop=policy,
            fixed_placement_final_slot=dict(origin_task_id=origin,aggregate_max_experiments=10)))
    store.create_task(task);store.append_observation('final',dict(obs_id='seed',kind='research',values={}))
    class FakeBenchmark:
        def __init__(self):self.calls=0
        def submit(self,task,path,key):
            self.calls+=1
            return store.create_attempt(task,dict(kind='lab',idem_key=key,fingerprint='offline',request={}))
    benchmark_fake=FakeBenchmark()
    yield FactoryLoop(store,'final',benchmark=benchmark_fake),contract,benchmark_fake
    store.close()


def add_diag_cycles(loop,count):
    for i in range(count):loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('diag',str(i),i+1,'{}'))


def test_final_slot_counts_origin_and_all_diagnostics_before_reserving(final_loop):
    loop,contract,fake=final_loop;add_diag_cycles(loop,8)
    assert fixed.admit_final_slot(loop,contract,reserving=True)['aggregate_used_before_reservation']==9
    add=loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    assert add['number']==1
    assert fixed.admit_final_slot(loop,contract,reserving=False)['aggregate_used_before_reservation']==10
    with pytest.raises(ValueError,match='aggregate cap'):fixed.admit_final_slot(loop,contract,reserving=True)


def test_same_key_replay_does_not_consume_second_slot_or_dispatch(final_loop):
    loop,contract,fake=final_loop;add_diag_cycles(loop,8)
    first=loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    assert loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)==first
    sent=loop.execute('fixed');assert sent['state']=='submitted' and fake.calls==1
    assert loop.execute('fixed')==sent and fake.calls==1
    replay=loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    assert replay['attempt_id']==sent['attempt_id'] and len(loop.status()['cycles'])==1


def test_exhausted_final_slot_never_selects_or_submits(final_loop):
    loop,contract,fake=final_loop;add_diag_cycles(loop,9)
    with pytest.raises(ValueError,match='aggregate cap'):loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    assert loop.status()['cycles']==[] and fake.calls==0


def test_dispatch_rechecks_aggregate_count_since_selection(final_loop):
    loop,contract,fake=final_loop;add_diag_cycles(loop,7)
    loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('diag','concurrent',8,'{}'))
    loop.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',('diag','concurrent-2',9,'{}'))
    with pytest.raises(ValueError,match='aggregate cap'):loop.execute('fixed')
    assert fake.calls==0


def test_dispatch_rechecks_build_receipt_integrity(final_loop):
    loop,contract,fake=final_loop
    loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    Path(contract['candidate_build']['receipt_path']).write_text('{}')
    with pytest.raises(ValueError,match='build receipt changed'):loop.execute('fixed')
    assert fake.calls==0


def test_final_slot_never_authorizes_acceptance(final_loop):
    from jiuwenswarm.factory.acceptance import validate
    loop,contract,fake=final_loop
    with pytest.raises(ValueError,match='acceptance and promotion prohibited'):validate(loop.store,'final')


def test_final_slot_uses_original_campaign_lock(final_loop,monkeypatch):
    import os
    from jiuwenswarm.factory import loop as loop_module
    loop,contract,fake=final_loop;locks=[]
    monkeypatch.setattr(loop_module.fcntl,'flock',lambda fd,kind:locks.append(Path(fd.name).name))
    loop.select('fixed',['seed'],'establish_repeatability','fixed-aa',0)
    assert [name for name in locks if name.endswith('.lock')]==[hashlib.sha256(b'spark-broad-throughput-004').hexdigest()+'.lock']

@pytest.mark.parametrize('missing_layer',[False,True])
def test_real_worker_dispatch_uses_v4_cases_protocol_and_effective_placement(contract,tmp_path,monkeypatch,missing_layer):
    """Only physical container launch/assets are mocked; real validator/parser/worker execute."""
    from jiuwenswarm.factory import benchmark_worker as worker
    data=dataset();data['pilot']=data['quality'][:2]
    data_path=tmp_path/'dataset.json';write_json(data_path,data)
    contract.update(dataset_path=str(data_path),dataset_sha256=sha(data_path))
    source_root=Path(benchmark.__file__).parent
    contract['execution_sha256']={name:sha(source_root/name) for name in contract['execution_sha256']}
    path=tmp_path/'contract.json';write_json(path,contract);launches=[]
    monkeypatch.setattr(worker,'admission',lambda image:{'available_bytes':110*2**30})
    monkeypatch.setattr(benchmark,'validate_assets',lambda c:{'assets':'synthetic frozen identity'})
    monkeypatch.setenv('FACTORY_HOME',str(tmp_path/'factory'))
    def record(argv,**kwargs):
        launches.append(kwargs);out=kwargs['output'];out.mkdir()
        stdout='READY\n'
        for line in kwargs['protocol'].decode().splitlines():
            if not line.startswith('GEN '):continue
            cap=int(line.split()[1]);prompt=len(line.split()[-1].split(','))
            stdout+=('T 65\n'*cap)+f'DONE {cap} {prompt} 100 1000 length 0 0 0 0 0\n'
        (out/'stdout.log').write_text(stdout)
        (out/'stderr.log').write_text('experts per word: 6\n'+placement_log(omit=3 if missing_layer else None))
        report=dict(reason='completed',container_exit_code=0,quiescent=True,container_removed=True,evidence_completeness='complete',container_oom_killed=False)
        (out/'report.json').write_text(json.dumps(report));return report
    monkeypatch.setattr(worker.lab_recorder,'run_container',record)
    output=tmp_path/'output'
    rc=worker.run(path,output,'offline','offline-attempt',contract_sha256=sha(path))
    result=json.loads((output/'campaign.json').read_text())
    if missing_layer:
        assert rc==1 and result['evidence_completeness']=='partial'
        assert len(launches)==1 and 'fixed-placement startup evidence' in result['error']['message']
    else:
        assert rc==0 and result['evidence_completeness']=='complete' and len(launches)==4
        assert [call['protocol'].count(b'GEN ') for call in launches]==[8,4,8,4]
        assert all(b'spec=1 ' not in call['protocol'] and b'spec=0 ' in call['protocol'] for call in launches)
        assert all(call['environment']['DS4_EXPERT_BUDGET_BYTES']==fixed.BUDGET for call in launches)
        assert all(cell['phases'][phase]['fixed_placement_identity']['effective_budget']==fixed.BUDGET for cell in result['cells'] for phase in ('quality','speed'))
