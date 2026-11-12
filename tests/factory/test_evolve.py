"""F12 offline checks. Captured ingestion fixtures are not live A/B results."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest
import jsonschema
import yaml

from jiuwenswarm.ccv2.ccv2 import load
from jiuwenswarm.ccv2.agent_mcp import Catalog
from jiuwenswarm.factory import ab, components, contract, story, telemetry
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.controller import Controller, configure_agent, validate_action
from jiuwenswarm.factory.manager import Manager, AdmissionError, UploadConflict
from jiuwenswarm.factory.monitor import engine_stack
from jiuwenswarm.factory.jobs import KeyConflict

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT / 'jiuwenswarm/factory/ccs'
FIXTURE = Path(__file__).parent / 'fixtures/ab'
NAMES = ['mmap_advice', 'router_prefetch', 'expert_fill', 'expert_pregate', 'thread_names']
IMAGE = 'sha256:' + 'a' * 64


def test_component_materials_and_discovery(tmp_path):
    for name in NAMES:
        folder = CCS / 'expert_streaming/components' / name
        load(folder / 'cc.yaml')
        declaration = yaml.safe_load((folder / 'cc.yaml').read_text())
        assert declaration['cc'] == '2' and 'bindings' not in declaration and 'capabilities' not in declaration
        assert set(declaration) == {'cc', 'id', 'version', 'materials'}
        for material in declaration['materials'].values():
            path = (folder / material['path']).resolve()
            assert path.is_relative_to(folder) and path.is_file()
        c = components.load(name)
        jsonschema.validate(c, json.loads((ROOT/'jiuwenswarm/factory/schemas/evolve-component.schema.json').read_text()))
        assert c['base']['commit'].startswith('cf34d3113')
        assert c['correctness_obligation'] == 'identical greedy stdout'
        assert c['measure'] in {'perf', 'none'} and c['hypothesis'] and c['rollback']
        assert set(c['depends_on']) <= set(NAMES[:NAMES.index(name)])
        for patch in c['patches']:
            assert hashlib.sha256((folder / patch['file']).read_bytes()).hexdigest() == patch['sha256']
    catalog = Catalog([CCS, CCS / 'expert_streaming/components'], tmp_path / 'ccstore')
    entries = catalog.scan()
    assert all(e['usable'] for e in entries)
    assert {e['cc'] for e in entries} >= {'factory.components.' + n for n in NAMES} | {'factory.methodology_ab'}
    assert len((CCS / 'methodology_ab/AB.md').read_text().splitlines()) <= 120


def checkout():
    candidates = [Path.home() / 'projects/siminfeng/ref/llama.cpp',
                  Path.home() / '.jiuwenswarm-factory/agent-workspace/llama.cpp']
    for path in candidates:
        if path.is_dir() and subprocess.run(['git', '-C', str(path), 'cat-file', '-e', 'cf34d3113^{commit}'], capture_output=True).returncode == 0:
            return path
    pytest.skip('No read-only llama.cpp checkout containing cf34d3113 is available')


def test_dependency_order_series_applies(tmp_path):
    # Export from the read-only checkout; no worktree metadata or ref writes there.
    archive = subprocess.run(['git', '-C', str(checkout()), 'archive', 'cf34d3113'], capture_output=True, check=True).stdout
    tree = tmp_path / 'tree'; tree.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(tree, filter='data')
    for name in NAMES:
        for patch in components.load(name)['patches']:
            path = CCS / 'expert_streaming/components' / name / patch['file']
            subprocess.run(['git', 'apply', '--check', str(path)], cwd=tree, capture_output=True, check=True)
            subprocess.run(['git', 'apply', str(path)], cwd=tree, capture_output=True, check=True)


@pytest.fixture
def experiment(store, tmp_path, monkeypatch):
    c = dict(contract.load('qwen36-bare-greedy-v1'))
    sha = hashlib.sha256((FIXTURE / '001-base/stdout.txt').read_bytes()).hexdigest()
    c['reference'] = dict(image_tag='fixture:engine', image_id=IMAGE, stdout_sha256=sha)
    directory = tmp_path / 'contracts'; directory.mkdir()
    contract.atomic_json(directory / 'fixture.json', dict(c, contract_id='fixture'))
    monkeypatch.setattr(contract, 'CONTRACTS', directory)
    manager = Manager(store, tmp_path / 'spool')
    builds=[]
    for key in ['base', 'candidate']:
        b = store.create_attempt('t',dict(kind='build',idem_key=key,fingerprint=key,request={}))
        store.put_artifact('t',b['attempt_id']+':receipt',json.dumps({'image_id':IMAGE}).encode(),'application/json',b['attempt_id'])
        store.transition_attempt('t',b['attempt_id'],'running')
        store.transition_attempt('t',b['attempt_id'],'succeeded')
        builds.append(dict(tag='fixture:'+key,id=IMAGE,build_attempt_id=b['attempt_id']))
    row=dict(Id=IMAGE,Architecture='arm64',Config={'Labels':{'campaign.target.profile':'jetson-orin'}})
    monkeypatch.setattr('jiuwenswarm.factory.manager.inspect_image',lambda tag:row)
    # Fake the queue invocation, preserving real durable Jobs identity and replay logic.
    calls=[]
    def queue(*args,**kwargs):
        calls.append((args,kwargs))
        if args[0] == 'show':
            return subprocess.CompletedProcess([],0,json.dumps(dict(state='queued')),'')
        return subprocess.CompletedProcess([],0,'job-fixture','')
    monkeypatch.setattr(manager.jobs,'_call',queue)
    monkeypatch.setattr(manager.jobs,'_recover',lambda attempt:attempt)
    inputs=dict(base_image=builds[0],candidate_image=builds[1],base_env={},
                candidate_env={'LLAMA_EXPERT_PREGATE':'1'},rounds=1,idem_key='ab',
                component='factory.components.expert_pregate',contract_id='fixture')
    return manager,inputs,calls,row


def test_ab_submission_admission_spec_and_replay(experiment):
    m,inputs,calls,row=experiment
    h=m.ab_submit('t',**inputs)
    request=h['request'];spec=request['spec']
    assert spec['order']=='ABBA' and spec['metric']=='eval_ms_per_token' and spec['direction']=='lower'
    assert spec['argv']==request['contract']['workload']['argv']
    assert spec['arms']['candidate']['expect_switch']
    assert spec['arms']['candidate']['switch_regex']==[c['regex'] for c in components.load(inputs['component'])['engagement_checks']]
    assert spec['arms']['base']['image']==spec['arms']['candidate']['image']==IMAGE
    assert h['resources']['job_class']=='gpu' and '--submit' not in h['resources']['argv']
    assert m.ab_submit('t',**inputs)['attempt_id']==h['attempt_id']
    assert len(calls)==1
    with pytest.raises(KeyConflict): m.ab_submit('t',**dict(inputs,rounds=2))
    row['Architecture']='amd64'
    with pytest.raises(AdmissionError): m.ab_submit('t',**dict(inputs,idem_key='bad'))


def bundle(experiment):
    manager,inputs,_,_=experiment
    h=manager.ab_submit('t',**inputs)
    root=manager.spool_root/h['attempt_id'];root.mkdir()
    shutil.copytree(FIXTURE,root/'ab')
    contract.atomic_json(root/'config.json',dict(h['request'],lab_run_id=h['attempt_id']))
    contract.atomic_json(root/'worker.json',dict(execution_outcome='ok'))
    manifest(root,'t',h['attempt_id'])
    return h,root


def manifest(root,task,run):
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in root.rglob('*') if p.is_file() and p.name not in {'ack.json','manifest.json'}}
    contract.atomic_json(root/'manifest.json',dict(task_id=task,lab_run_id=run,files=files))


def test_ab_ingest_verdict_and_artifacts(experiment):
    h,root=bundle(experiment);m=experiment[0]
    assert m.ingest_upload('t',h['attempt_id'],root)['ack_state']=='durable'
    result=m.ab_result(h['attempt_id'])
    assert result['evaluation']['correctness']=='pass'
    assert result['execution_outcome']=='ok'
    values=result['ab_result']
    assert values['gate']=='improved' and values['ratio']>1 and values['output_class']=='identical'
    assert set(values['per_arm_ms'])=={'base','candidate'}
    assert any(ref.endswith('verdict.json') for ref in result['evidence_refs'])
    assert any(ref.endswith('REPORT.md') for ref in result['evidence_refs'])
    assert m.ingest_upload('t',h['attempt_id'],root)['ack_state']=='durable'
    assert len(m.store.dump('t')['observations'])==1
    assert any(e['event']=='ab.result' for e in telemetry.read_events(m.store.home))
    (root/'ab/001-base/stdout.txt').write_text('changed after upload')
    with pytest.raises(UploadConflict): m.ingest_upload('t',h['attempt_id'],root)


@pytest.mark.parametrize('failure',['reference','output','engagement','metric','worker','missing'])
def test_ab_never_scores_bad_evidence(experiment,failure):
    m,inputs,_,_=experiment
    if failure=='reference':
        path=contract.CONTRACTS/'fixture.json';c=json.loads(path.read_text());c['reference']['stdout_sha256']='0'*64;contract.atomic_json(path,c)
    h,root=bundle(experiment)
    if failure=='output':(root/'ab/002-candidate/stdout.txt').write_text('different')
    elif failure in {'engagement','metric'}:
        path=root/'ab/002-candidate/stderr.txt'
        text=path.read_text().replace('expert_pregate: active','removed') if failure=='engagement' else ''
        path.write_text(text)
    elif failure=='worker':contract.atomic_json(root/'worker.json',{'execution_outcome':'measurement_failed'})
    elif failure=='missing':(root/'ab/verdict.json').unlink()
    manifest(root,'t',h['attempt_id'])
    m.ingest_upload('t',h['attempt_id'],root)
    result=m.ab_result(h['attempt_id'])
    assert result['execution_outcome']==('candidate_failed' if failure in {'reference','output'} else 'measurement_failed')
    assert result['ab_result']['gate'] in {'invalid','improved'}


@pytest.mark.parametrize('action',[dict(type='keep_component',component='mmap_advice',image='sha256:a',ratio=1.2),
                                  dict(type='revert_component',component='mmap_advice',reason='null gate'),
                                  dict(type='integrate'),dict(type='build'),dict(type='measure')])
def test_evolve_decisions(action):
    validate_action(action)


@pytest.mark.parametrize('action',[dict(type='keep_component',component='unknown',image='x',ratio=2),
    dict(type='keep_component',component='mmap_advice',image='x',ratio=float('nan')),
    dict(type='keep_component',component='mmap_advice',ratio=2),
    dict(type='revert_component',component='mmap_advice',reason=''),dict(type='invent')])
def test_invalid_evolve_decisions(action):
    with pytest.raises(ValueError):validate_action(action)


def test_evolve_publication_and_story(store):
    def publish(action):
        return dispatch(store.scoped('t'),'t','evidence.publish',{'inputs':dict(type='decision',
            expected_rev=store.get_task('t')['current_decision_rev'],record=dict(action=action,evidence_ids=['t', 'accepted-ab']))})
    store.append_observation('t', dict(obs_id='accepted-ab', kind='ab_result', values=dict(component='mmap_advice', acceptance=dict(type='performance', verdict='accept', reasons=[]))))
    publish(dict(type='keep_component',component='mmap_advice',image=IMAGE,ratio=1.2))
    publish(dict(type='revert_component',component='mmap_advice',reason='output mismatch'))
    with pytest.raises(ValueError):publish(dict(type='revert_component',component='mmap_advice'))
    data=store.dump('t');data['_meta']=dict(outcome=None,budget_used=dict(turns=2,wall_clock_s=1))
    text=story.render_story(data,True)
    assert 'keep mmap_advice' in text and 'revert mmap_advice' in text and 'output mismatch' in text
    assert 'engine stack: bare' in text
    assert 'mmap_advice' not in story.decision_stack(data)
    assert next(r for r in engine_stack(data) if r['name']=='mmap_advice')['state']=='reverted'


def test_bare_contract_and_null_reference_freeze(tmp_path):
    c=contract.load('qwen36-bare-greedy-v1')
    assert c['workload']['env']=={} and c['engagement_checks']==[]
    assert c['reference_image']['image_tag']=='factory/llamacpp:bare-cf34d311'
    c['reference']=None  # exercise the unfrozen path on a copy; the checked-in contract may be frozen
    c['reference_image']['image_id']=IMAGE
    path=tmp_path/'bare.json';contract.atomic_json(path,c)
    contract.freeze(path,dict(execution_outcome='ok',evidence_completeness='complete',
        image_id=IMAGE,stdout_sha256='a'*64,run_ref='fixture'))
    assert contract.load(path)['reference']['stdout_sha256']=='a'*64


def test_controller_only_creates_evolve_ref(tmp_path,monkeypatch):
    checkout=tmp_path/'factory/agent-workspace/llama.cpp';checkout.mkdir(parents=True)
    controller=Controller(home=tmp_path/'factory')
    calls=[]
    def git(argv,**kwargs):
        calls.append(argv[3:])
        if '--show-toplevel' in argv:return subprocess.CompletedProcess(argv,0,str(checkout)+'\n','')
        if 'show-ref' in argv:return subprocess.CompletedProcess(argv,1,'','')
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr('jiuwenswarm.factory.controller.subprocess.run',git)
    task_id=controller.init_task(ROOT/'jiuwenswarm/factory/tasks/evolve-qwen36.json')
    assert calls==[['rev-parse','--show-toplevel'],['show-ref','--verify','--quiet','refs/heads/evolve'],['branch','evolve','cf34d3113']]
    assert controller.store.get_task(task_id)['budget']['max_turns']==40
    controller.store.close()


def test_ab_worker_runs_one_direct_experiment(experiment,tmp_path,monkeypatch):
    from jiuwenswarm.factory import ab_runner
    m,inputs,_,row=experiment
    model=tmp_path/'models/model.gguf';model.parent.mkdir();model.write_bytes(b'fixture')
    path=contract.CONTRACTS/'fixture.json';c=contract.load(path)
    c['model']=dict(path=str(model),size=model.stat().st_size,sha256=None);contract.atomic_json(path,c)
    h=m.ab_submit('t',**inputs)
    config=next((m.spool_root/'configs').glob('*.json'))
    fake=tmp_path/'abrun.py'
    fake.write_text('import sys,json,os,shutil\nfrom pathlib import Path\n'
        'assert len(sys.argv)==2\ns=json.loads(Path(sys.argv[1]).read_text())\n'
        'assert s["order"]=="ABBA" and s["metric"]=="eval_ms_per_token"\n'
        'assert os.environ["OM_MODELDIR"]=='+repr(str(model.parent))+'\n'
        'shutil.copytree('+repr(str(FIXTURE.resolve()))+',Path(s["outdir_base"])/s["id"])\n')
    monkeypatch.setenv('FACTORY_ABRUN',str(fake))
    monkeypatch.setattr(ab_runner,'inspect_image',lambda ref:row)
    monkeypatch.setattr(ab_runner,'upload',lambda task,run,root,spool:bool(m.ingest_upload(task,run,root)))
    assert ab_runner.run('t',h['attempt_id'],config,m.spool_root)==0
    assert m.ab_result(h['attempt_id'])['evaluation']['correctness']=='pass'


def test_ab_both_images_and_unfrozen_admission(experiment,monkeypatch):
    m,inputs,calls,row=experiment
    monkeypatch.setattr('jiuwenswarm.factory.manager.inspect_image',
        lambda tag:dict(row,Id='sha256:'+'b'*64) if tag.endswith('candidate') else row)
    with pytest.raises(AdmissionError):m.ab_submit('t',**inputs)
    assert calls==[]
    path=contract.CONTRACTS/'fixture.json';c=contract.load(path);c['reference']=None;contract.atomic_json(path,c)
    with pytest.raises(ValueError,match='freeze'):m.ab_submit('t',**inputs)


def test_ab_api_rejects_agent_regex_and_foreign_attempt(experiment,monkeypatch):
    from jiuwenswarm.factory.store import ScopeDenied
    m,inputs,_,_=experiment
    # Use the prepared fake job adapter, while exercising API field/scope checks.
    monkeypatch.setattr('jiuwenswarm.factory.manager.Manager',lambda *args:m)
    with pytest.raises(ValueError):
        dispatch(m.store.scoped('t'),'t','lab.ab_submit',{'inputs':dict(inputs,switch_regex=['.*'])})
    h=dispatch(m.store.scoped('t'),'t','lab.ab_submit',{'inputs':inputs})
    m.store.create_task(dict(task_id='other',objective='scope'))
    with pytest.raises(ScopeDenied):
        dispatch(m.store.scoped('other',{'t'}),'other','lab.ab_result',{'inputs':{'attempt_id':h['attempt_id']}})


def test_keep_dormant_only_for_real_prerequisites():
    import pytest
    from jiuwenswarm.factory.controller import validate_action
    from jiuwenswarm.factory.components import dependents
    assert dependents('mmap_advice') == {'router_prefetch', 'expert_fill', 'expert_pregate', 'thread_names', 'expert_readiness', 'inflight_join', 'phase_stats'}
    assert dependents('thread_names') == set()
    validate_action({'type': 'keep_dormant', 'component': 'mmap_advice', 'reason': 'source prerequisite',
                     'needed_by': ['expert_fill']})
    for bad in ({'needed_by': []}, {'needed_by': ['expert_fill'], 'reason': ''},
                {'needed_by': ['mmap_advice']}, {'component': 'thread_names', 'needed_by': ['expert_fill']}):
        action = dict({'type': 'keep_dormant', 'component': 'mmap_advice', 'reason': 'r'}, **bad)
        with pytest.raises(ValueError):
            validate_action(action)
