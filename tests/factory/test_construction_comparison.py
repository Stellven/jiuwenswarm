"""CPU-only: actual Git/CC/artifact/loop lineage, fixture native execution and scoring.

No fixture timing is hardware evidence. Docker/queue boundaries are substituted;
policy, manifests, parsing and durable identities are not replaced by success labels.
"""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import construction_comparison as cc, benchmark
from jiuwenswarm.factory.execution_binding import digest
from jiuwenswarm.factory.jobs import Jobs, metadata
from jiuwenswarm.factory.loop import FactoryLoop
from jiuwenswarm.factory.store import Store
from tests.factory.test_construction import prepared_loop
from tests.factory.test_broad_benchmark import contract as reference_contract, dataset, cells, decode


def comparison(reference, stage='aa'):
    c=copy.deepcopy(reference)
    c.update(adapter=cc.ADAPTER,version=1,reference_contract=copy.deepcopy(reference),
        hypothesis='Queue batching preserves the computation',configuration_change='source',campaign_stage=stage,
        phases=['quality','speed'],correctness_policy='exact_tokens_and_finish_all_requests',promotion_authorized=False,
        baseline_executable_sha256='b'*64,engagement_regex=r'batch_rows=64 actual_batches=[1-9][0-9]*',template_sha256='c'*64)
    c['execution_sha256'].update({n:'a'*64 for n in ('construction_comparison.py','engine_adapters.py','targets.py')})
    if stage=='confirm':c.update(order=list('ABBA'),quality_case_indices=list(range(8,64)),campaign_timeout_s=2700,
        runtime_bounds=dict(fresh_process_cells=4,phase_containers=8,observer_interval_ms=1000))
    c['lineage']={'image_id':'sha256:'+'b'*64,'executable_sha256':'e'*64}
    c['lineage']['identity']=digest(c['lineage'])
    return c


@pytest.mark.parametrize('stage',['aa','screen','confirm'])
def test_independent_exactness_and_disjoint_holdout(reference_contract,stage):
    c=comparison(reference_contract,stage);d=dataset();rows=cells(c,d)
    assert cc.validate_contract(c) is c
    result=cc.analyze(c,d,rows,decode)
    assert result['verdict']=={'aa':'aa_valid','screen':'screen_candidate','confirm':'accept'}[stage]
    if stage=='confirm':assert set(c['quality_case_indices']).isdisjoint(range(8))
    rows[1]['speed']['requests'][-1]['ids'][-1]=3
    result=cc.analyze(c,d,rows,decode)
    assert result['verdict']=='reject_correctness' and result['promotion_authorized'] is False


@pytest.mark.parametrize('field',['limits','gates','arms','correctness_policy','quality_case_indices'])
def test_candidate_cannot_redefine_judge_or_second_variable(reference_contract,field):
    c=comparison(reference_contract,'confirm')
    if field=='limits':c[field]['cpus']=4
    elif field=='gates':c[field]['minimum_speedup']=1
    elif field=='arms':c[field]['B']['environment']['DS4_AHEAD']='1'
    elif field=='correctness_policy':c[field]='tolerant'
    else:c[field]=list(range(64))
    with pytest.raises(ValueError):cc.validate_contract(c)


def test_actual_engagement_required(reference_contract):
    c=comparison(reference_contract,'screen')
    c['engagement_regex']=r'^batch_rows=64 actual_batches=[1-9][0-9]*$'
    stderr='Engram rows read on 2 threads, row cache 64 MB\nprompts in chunks of 256)\n'
    parsed={'requests':[{'offered_drafts':0,'accepted_drafts':0}]}
    with pytest.raises(ValueError,match='did not engage'):cc.engagement(c,'B',parsed,stderr)
    cc.engagement(c,'B',parsed,stderr+'batch_rows=64 actual_batches=12')
    cc.engagement(c,'A',parsed,stderr)


@pytest.fixture
def built(tmp_path,monkeypatch,reference_contract):
    reference_contract['image']['id']='sha256:'+'d'*64
    data=dataset();data['pilot']=[dict(data['quality'][i],id='pilot'+str(i)) for i in range(2)]
    data['provenance']={'tokenizer':{'files':{}}}
    dataset_path=tmp_path/'dataset.json';dataset_path.write_text(json.dumps(data))
    reference_contract.update(dataset_path=str(dataset_path),dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),workspace_root=str(tmp_path),assets={})
    store,loop,spec=prepared_loop(tmp_path)
    monkeypatch.setattr(Jobs,'status',lambda self,aid:self._get(aid))
    source=tmp_path/'source';source.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(source),*args],text=True).strip()
    git('init','-q');git('config','user.email','fixture@localhost');git('config','user.name','CPU fixture')
    (source/'engine.txt').write_text('source candidate');git('add','.');git('commit','-qm','fixture source')
    pin=dict(commit=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'))
    package=tmp_path/'cc';package.mkdir()
    (package/'cc.yaml').write_text("cc: '2'\nid: fixture.source\nversion: 1.0.0\nmaterials:\n  component: {path: source.json}\n  roles: {path: roles.json}\n")
    (package/'source.json').write_text(json.dumps(dict(id='fixture.source',source=pin)))
    (package/'roles.json').write_text(json.dumps(dict(format='factory-roles/1',capabilities={},materials={'component':'component'})))
    release=Host(store.home/'ccstore').seal(package)
    expected=dict(pin,component=dict(release=release,material='component'))
    loop.prepare_experiment('probe',spec,'sha256:'+'a'*64)
    loop.select('probe',['seed'],spec['hypothesis'],expected_rev=0,experiment_id='probe');cycle=loop.execute('probe')
    aid=cycle['attempt_id'];child=cycle['child_task_id']
    report=dict(status='succeeded',execution_outcome='ok',evidence_completeness='complete',artifact_copy_returncode=0,cleanup={'container_removed':True})
    ref=store.put_artifact(child,aid+':result.json',json.dumps(report).encode(),'application/json',aid)
    metadata(store,store.read(child,aid),result_refs=[ref['artifact_id']])
    store.transition_attempt(child,aid,'running');store.transition_attempt(child,aid,'succeeded')
    from jiuwenswarm.factory.experiment_jobs import ExperimentJobs
    loop.benchmark=ExperimentJobs(store);cycle=loop.collect('probe')
    binding=store.get_task(loop.task_id)['constraints']['execution_binding']
    # This is a durable fixture build, not a native build or GPU result.
    from jiuwenswarm.factory.builder import Builder
    builder=Builder(store)
    request=dict(source=dict(pin,path=str(source)),env={},deadline_s=1,build_target='strata-dsv41',tag='factory/strata:fixture')
    monkeypatch.setattr(builder,'_request',lambda r:copy.deepcopy(request))
    monkeypatch.setattr(builder.jobs,'_call',lambda *a,**kw:SimpleNamespace(stdout='job-fixture'))
    # Fixture task's build cap initially zero; separate CPU test setup admits one.
    policy=copy.deepcopy(loop.policy);policy['experiment_authority']['max_build_attempts']=1
    policy['experiment_authority']['max_gpu_launches']=17
    policy.update(max_cycles=5,max_experiments=5)
    templates=[]
    for stage in ('aa','screen','confirm'):
        c=comparison(reference_contract,stage);c.pop('lineage');c.pop('template_sha256');c['candidate_source']=expected
        factory=Path(benchmark.__file__).parent
        c['execution_sha256']={name:hashlib.sha256((factory/name).read_bytes()).hexdigest() for name in c['execution_sha256']}
        path=tmp_path/(stage+'.json');path.write_text(json.dumps(c))
        templates.append(dict(id=stage,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    policy['comparison_templates']=templates
    with store._transaction():
        task=store.get_task(loop.task_id);constraints=dict(task['constraints'],factory_loop=policy)
        store._db.execute('UPDATE tasks SET constraints=?,budget=? WHERE task_id=?',(json.dumps(constraints),json.dumps({'wall_clock_s':600,'max_turns':8}),loop.task_id))
        store._db.execute('UPDATE factory_loop_policy SET policy=? WHERE task_id=?',(json.dumps(policy,sort_keys=True),loop.task_id))
    loop=FactoryLoop(store,loop.task_id)
    attempt=builder.submit(loop.task_id,{},'fixture-build')
    store.transition_attempt(loop.task_id,attempt['attempt_id'],'running');store.transition_attempt(loop.task_id,attempt['attempt_id'],'succeeded')
    build=dict(status='success',source=pin,image={'Id':'sha256:'+'a'*64},executable_sha256='e'*64)
    build_id=attempt['attempt_id']+':build-record'
    store.put_artifact(loop.task_id,build_id,json.dumps(build).encode(),'application/json',attempt['attempt_id'])
    receipt=dict(image_id='sha256:'+'a'*64,build_record={'artifact_id':build_id})
    artifact=store.put_artifact(loop.task_id,attempt['attempt_id']+':receipt',json.dumps(receipt).encode(),'application/json',attempt['attempt_id'])
    admission_id='admission:fixture'
    store.put_artifact(loop.task_id,admission_id,json.dumps(dict(image={'id':receipt['image_id']},build_attempt_id=attempt['attempt_id'])).encode(),'application/json',attempt['attempt_id'])
    with store._transaction():
        cycle.update(build_attempt_id=attempt['attempt_id'],build_receipt_sha256=artifact['sha256'],build_admission_id=admission_id)
        loop._write(cycle,'fixture_build_attached')
    yield SimpleNamespace(store=store,loop=loop,expected=expected,source=source,cycle=cycle,templates=templates)
    store.close()


def test_source_tree_build_image_and_sealed_release_bound_without_execution(built):
    b=built
    result=b.loop.prepare_comparison('comparison','probe','aa')
    c,_=cc.resolve(b.loop,'comparison')
    assert not result['execution_authorized']
    assert c['lineage']['source']['tree']==b.expected['tree']
    assert c['lineage']['component']['release']==b.expected['component']['release']
    assert c['lineage']['build_attempt_id']==b.cycle['build_attempt_id']
    selected=b.loop.select('eval',['loop-result:1'],c['hypothesis'],expected_rev=1,comparison_id='comparison')
    assert selected['contract']['lineage']==c['lineage']
    assert b.store._db.execute("SELECT COUNT(*) FROM attempts WHERE kind='lab'").fetchone()[0]==1


def test_component_or_judge_mutation_rejected(built):
    b=built;b.loop.prepare_comparison('comparison','probe','aa')
    host=Host(b.store.home/'ccstore');_,bundle=host.release(b.expected['component']['release'])
    (bundle/'source.json').write_text('{}')
    with pytest.raises(Exception):cc.resolve(b.loop,'comparison')


def test_incomplete_diagnostic_cannot_feed_engine_comparison(built):
    b=built;child=b.cycle['child_task_id'];aid=b.cycle['attempt_id']
    art=b.store.read(child,aid+':result.json');(b.store.home/art['location']).write_text('{}')
    with pytest.raises(ValueError,match='incomplete'):b.loop.prepare_comparison('comparison','probe','aa')


def test_independent_comparison_counts_phase_launches_and_deadline(tmp_path,monkeypatch):
    with Store(tmp_path/'factory') as store:
        authority=dict(max_build_attempts=0,max_gpu_launches=4)
        store.create_task(dict(task_id='p',objective='CPU budget fixture',budget={'wall_clock_s':100},constraints={'factory_loop':{'experiment_authority':authority}}))
        jobs=Jobs(store);monkeypatch.setattr(jobs,'_call',lambda *a,**kw:SimpleNamespace(stdout='job-fixture'))
        req=dict(adapter=cc.ADAPTER,contract={'runtime_bounds':{'phase_containers':4}})
        for invalid in (-1, 0, True):
            bad=dict(adapter=cc.ADAPTER,contract={'runtime_bounds':{'phase_containers':invalid}})
            with pytest.raises(ValueError,match='Positive integer'):
                jobs.submit('p','lab',bad,'bad-'+str(invalid),'gpu',['fixture'],1,{})
        a=jobs.submit('p','lab',req,'same','gpu',['fixture'],1,{})
        assert jobs.submit('p','lab',req,'same','gpu',['fixture'],1,{})['attempt_id']==a['attempt_id']
        with pytest.raises(ValueError,match='max_gpu_launches'):jobs.submit('p','lab',req,'new','gpu',['fixture'],1,{})
        monkeypatch.setattr('jiuwenswarm.factory.jobs.time.time',lambda:store.get_task('p')['created']+101)
        with pytest.raises(ValueError,match='expired'):jobs.submit('p','lab',req,'late','gpu',['fixture'],1,{})


def native_fixture(c,root,task_id,attempt_id,diverge=False):
    """Synthetic native protocol plus full boundary/raw manifests, not GPU evidence."""
    import os
    from jiuwenswarm.factory.lab_recorder import GATE
    root.mkdir(parents=True)
    def put(path,value):path.write_text(json.dumps(value))
    put(root/'config.json',dict(contract=c,task_id=task_id,attempt_id=attempt_id))
    put(root/'campaign.json',dict(execution_outcome='ok',evidence_completeness='complete'))
    data=benchmark.load_dataset(c)
    for index,arm in enumerate(c['order'],1):
        for phase in ('quality','speed'):
            path=root/f'cell-{index:03d}-{arm}'/phase;path.mkdir(parents=True)
            image=cc.image_for(c,arm)
            intent={'image':image};put(path/'intent.json',intent)
            configuration=dict(Image=image,Id='fixture-'+str(index)+phase,Config=dict(User=f'{os.getuid()}:{os.getgid()}',
                Env=[k+'='+v for k,v in c['arms'][arm]['environment'].items()],Entrypoint=['/usr/bin/python3'],
                Cmd=['-c',GATE,*benchmark.phase_args(c,arm,phase)]),
                Mounts=[dict(Type='bind',RW=False,Source=v,Destination=v) for v in c['workload'].values()],
                HostConfig=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='none',IpcMode='private',CgroupnsMode='private',
                    Memory=c['limits']['memory_bytes'],MemorySwap=c['limits']['memory_bytes'],NanoCpus=8*10**9,PidsLimit=256,
                    CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],LogConfig={'Type':'none'},
                    DeviceRequests=[dict(Driver='cdi',DeviceIDs=['nvidia.com/gpu=0'])]))
            put(path/'inspect-created.json',configuration)
            put(path/'inspect-final.json',dict(configuration,State=dict(Running=False,Pid=0,ExitCode=0,OOMKilled=False)))
            put(path/'report.json',dict(reason='completed',quiescent=True,container_removed=True,container_exit_code=0,evidence_completeness='complete'))
            cases=benchmark.phase_cases(c,data,phase)
            (path/'stdin-wire.log').write_bytes(b'FACTORY_EXEC\n'+benchmark.protocol(cases,arm,c))
            stdout='READY\n'
            for case in cases:
                tokens=[65] if phase=='quality' else [2]*128
                if diverge and arm=='B' and phase=='speed':tokens[-1]=3
                elapsed=800 if arm=='B' and c['campaign_stage']!='aa' else 1000
                stdout+=''.join('T '+str(token)+'\n' for token in tokens)
                stdout+=f'DONE {len(tokens)} {len(case["ids"])} 100 {elapsed} length 0 0 0 0 0\n'
            (path/'stdout.log').write_text(stdout)
            (path/'stderr.log').write_text('experts per word: 6\nEngram rows read on 2 threads, row cache 64 MB\nprompts in chunks of 256)\nbatch_rows=64 actual_batches=12\n')
            events=[]
            for i,(stream,name) in enumerate([('stdin','stdin-wire.log'),('stdout','stdout.log'),('stderr','stderr.log')]):
                events.append(dict(sequence=i,stream=stream,offset=0,truncated=False,retained_bytes=(path/name).stat().st_size))
            (path/'pipe-events.jsonl').write_text('\n'.join(json.dumps(v) for v in events)+'\n')
            (path/'samples.jsonl').write_text(json.dumps(dict(available_bytes=10*2**30,memory_events={}))+'\n')
            executable=c['baseline_executable_sha256'] if arm=='A' or c['campaign_stage']=='aa' else c['lineage']['executable_sha256']
            put(path.parent/(phase+'-result.json'),dict(executable_sha256=executable))
    put(root/'manifest.json',dict(state='complete',task_id=task_id,attempt_id=attempt_id,
        files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}))


@pytest.mark.parametrize('diverge',[False,True])
def test_full_loop_independent_raw_evaluation_keep_or_reject_lineage(built,monkeypatch,diverge):
    b=built
    from jiuwenswarm.factory import benchmark_data
    monkeypatch.setattr(benchmark_data,'load_decoder',lambda *a:SimpleNamespace(special_ids={},decode=lambda ids:''.join(chr(x) for x in ids)))
    monkeypatch.setattr(benchmark,'validate_assets',lambda c:{'fixture':True})
    monkeypatch.setattr(Jobs,'_call',lambda *a,**kw:SimpleNamespace(stdout='job-fixture'))
    evidence='loop-result:1'
    for stage in ('aa','screen','confirm'):
        b.loop.prepare_comparison(stage,'probe',stage)
        c,_=cc.resolve(b.loop,stage)
        b.loop.select(stage,[evidence],c['hypothesis'],expected_rev=b.store.get_task(b.loop.task_id)['current_decision_rev'],comparison_id=stage)
        cycle=b.loop.execute(stage)
        attempt=b.store.read(cycle['child_task_id'],cycle['attempt_id'])
        assert attempt['request']['adapter']==cc.ADAPTER
        root=b.store.home/'benchmark-spool'/attempt['attempt_id']
        native_fixture(c,root,cycle['child_task_id'],attempt['attempt_id'],diverge=diverge and stage=='confirm')
        b.store.transition_attempt(cycle['child_task_id'],attempt['attempt_id'],'running')
        b.store.transition_attempt(cycle['child_task_id'],attempt['attempt_id'],'succeeded')
        cycle=b.loop.collect(stage);evidence=cycle['evidence_id']
        evaluation=b.store.read(b.loop.task_id,'engine-evaluation:'+str(cycle['number']))
        assert evaluation['inputs']['lineage']['component']['release']==b.expected['component']['release']
        assert evaluation['inputs']['lineage']['source']['tree']==b.expected['tree']
        assert evaluation['evidence_completeness']=='complete'
    if diverge:
        assert cycle['result']['analysis']['verdict']=='reject_correctness'
        with pytest.raises(ValueError,match='Keep/accept'):cc.validate_acceptance(b.store,b.loop.task_id,[evidence])
    else:
        accepted=cc.validate_acceptance(b.store,b.loop.task_id,[evidence])
        assert accepted['lineage']['build_attempt_id']==b.cycle['build_attempt_id']
        from jiuwenswarm.factory.controller import validate_action, validate_keep_evidence
        action=dict(type='keep_component',component='fixture.source',image=accepted['lineage']['image_id'],ratio=accepted['ratio'])
        validate_action(action,sealed_component=True)
        validate_keep_evidence(b.store,b.loop.task_id,dict(action=action,evidence_ids=[evidence]))
        with pytest.raises(ValueError,match='ratio differs'):
            validate_keep_evidence(b.store,b.loop.task_id,dict(action=dict(action,ratio=999),evidence_ids=[evidence]))
        with pytest.raises(ValueError,match='Keep/accept'):cc.validate_acceptance(b.store,b.loop.task_id,['seed'])
        # A cached accept cannot hide later raw-evidence mutation.
        (root/'cell-002-B/speed/stdout.log').write_text('changed')
        # Rewriting the spool manifest cannot replace host-retained evidence either.
        manifest=json.loads((root/'manifest.json').read_text())
        manifest['files']['cell-002-B/speed/stdout.log']=hashlib.sha256(b'changed').hexdigest()
        (root/'manifest.json').write_text(json.dumps(manifest))
        with pytest.raises(ValueError,match='Changed/escaping'):cc.validate_acceptance(b.store,b.loop.task_id,[evidence])


def test_actual_worker_routes_images_and_holdout_before_independent_parsing(built,monkeypatch,tmp_path):
    import shutil
    from jiuwenswarm.factory import benchmark_worker as worker, benchmark_data, strata_lab
    b=built
    monkeypatch.setattr(benchmark,'validate_assets',lambda c:{'fixture':True})
    monkeypatch.setattr(benchmark_data,'load_decoder',lambda *a:SimpleNamespace(special_ids={},decode=lambda ids:''.join(chr(x) for x in ids)))
    monkeypatch.setattr(Jobs,'_call',lambda *a,**kw:SimpleNamespace(stdout='job-fixture'))
    monkeypatch.setattr(worker,'admission',lambda image:{'fixture':True})
    monkeypatch.setattr(strata_lab,'wait_quiet',lambda *a,**kw:{'fixture_control_stopped':True})
    monkeypatch.setenv('FACTORY_HOME',str(b.store.home))
    # The loop must pass real A/A and screen parsing before confirming. Reuse the
    # fixture native transcripts as the external recorder boundary, not the evaluator.
    evidence='loop-result:1';launches=[]
    for stage in ('aa','screen','confirm'):
        b.loop.prepare_comparison(stage,'probe',stage);c,_=cc.resolve(b.loop,stage)
        b.loop.select(stage,[evidence],c['hypothesis'],expected_rev=b.store.get_task(b.loop.task_id)['current_decision_rev'],comparison_id=stage)
        cycle=b.loop.execute(stage);task=cycle['child_task_id'];aid=cycle['attempt_id']
        attempt=b.store.read(task,aid);monkeypatch.setenv('FACTORY_BENCHMARK_QUIET_ROOT',attempt['request']['quiet_root'])
        fixture=tmp_path/('native-'+stage);native_fixture(c,fixture,task,aid)
        def recorder(argv,**kw):
            destination=kw['output'];relative=Path(destination.parent.name)/destination.name
            shutil.copytree(fixture/relative,destination)
            launches.append((stage,kw['image'],kw['protocol'].count(b'GEN ')))
            return json.loads((destination/'report.json').read_text())
        monkeypatch.setattr(worker.lab_recorder,'run_container',recorder)
        # Real executable checker exercised against a controlled Docker response.
        def checksum(argv,**kw):
            image=argv[-2]
            return (c['baseline_executable_sha256'] if image==c['image']['id'] else c['lineage']['executable_sha256'])+'  /opt/strata/strata-dsv41\n'
        monkeypatch.setattr(cc.subprocess,'check_output',checksum)
        root=b.store.home/'benchmark-spool'/aid
        assert worker.run(cycle['contract_path'],root,task,aid,contract_sha256=cycle['contract_sha256'])==0
        b.store.transition_attempt(task,aid,'running');b.store.transition_attempt(task,aid,'succeeded')
        collected=b.loop.collect(stage);evidence=collected['evidence_id']
    confirm=[v for v in launches if v[0]=='confirm']
    assert [v[1] for v in confirm]==[c['image']['id']]*2+[c['lineage']['image_id']]*4+[c['image']['id']]*2
    assert [v[2] for v in confirm]==[56,4]*4
    assert cc.validate_acceptance(b.store,b.loop.task_id,[evidence])['verdict']=='accept'
