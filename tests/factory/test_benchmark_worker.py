"""The campaign driver is tested without Docker, a model or a GPU."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import benchmark_worker as worker


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    quality = [dict(id=f'q{i}', ids=[2, 3], max_new_tokens=8) for i in range(64)]
    speed = [dict(id=f's{i}', ids=[2]*512, max_new_tokens=128) for i in range(4)]
    dataset = tmp_path/'dataset.json'
    dataset.write_text(json.dumps(dict(quality=quality, pilot=quality[:2], speed=speed)))
    contract = dict(stage='main', image=dict(id='sha256:fixed'),
        dataset_path=str(dataset), dataset_sha256=worker.sha(dataset),
        workload=dict(pack=str(tmp_path/'assets'/'pack'), model_root=str(tmp_path/'assets'/'model')),
        arms={arm:dict(args=['--eos','1'],environment={'FIXED':'1'}) for arm in 'AB'},
        order=list('ABBAABBA'), limits=dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,
            quality_timeout_s=900,speed_timeout_s=300))
    path = tmp_path/'contract.json'
    launches=[]
    def protocol(cases,arm):
        return json.dumps(dict(cases=cases,arm=arm)).encode()
    def record(argv,**kwargs):
        launches.append(dict(argv=argv,**kwargs))
        out=kwargs['output'];out.mkdir()
        (out/'stdout.log').write_text('native transcript')
        (out/'stderr.log').write_text('six experts')
        report=dict(reason='completed',container_exit_code=0,quiescent=True,container_removed=True,
            evidence_completeness='complete',container_oom_killed=False)
        (out/'report.json').write_text(json.dumps(report))
        return report
    def parse(stdout,stderr,cases):
        assert stdout=='native transcript' and stderr=='six experts'
        return dict(requests=[dict(ids=[42]*case['max_new_tokens'],generated_tokens=case['max_new_tokens'])
            for case in cases],effective_experts=6)
    tools=SimpleNamespace(validate_contract=lambda c:None,validate_assets=lambda c:{'model':'frozen'},
        protocol=protocol,phase_args=lambda c,a,p:['engine',a,p],parse_native=parse)
    monkeypatch.setattr(worker,'_benchmark_tools',lambda:tools)
    monkeypatch.setattr(worker,'check_source_pins',lambda c:{'frozen':'source'})
    monkeypatch.setattr(worker,'admission',lambda image:{'available_bytes':110*2**30})
    monkeypatch.setattr(worker.lab_recorder,'run_container',record)
    monkeypatch.setenv('FACTORY_HOME',str(tmp_path/'factory'))
    def run(**kwargs):
        path.write_text(json.dumps(contract))
        return worker.run(path,tmp_path/'output','task','attempt',contract_sha256=worker.sha(path),**kwargs)
    return SimpleNamespace(contract=contract,path=path,dataset=dataset,output=tmp_path/'output',
        tools=tools,launches=launches,run=run)


def read(path):
    return json.loads(path.read_text())


def test_frozen_abba_runs_separate_phases_and_seals(campaign):
    assert campaign.run()==0
    calls=campaign.launches
    assert [call['argv'][1] for call in calls[::2]]==list('ABBAABBA')
    assert [call['argv'][2] for call in calls]==['quality','speed']*8
    assert [len(json.loads(call['protocol'])['cases']) for call in calls]==[64,4]*8
    assert all(call['gpu'] and call['cpus']==8 and call['memory_bytes']==104*2**30 for call in calls)
    assert all(call['environment']=={'FIXED':'1'} and call['guard_gib']==8 for call in calls)
    assert all(call['lease_root']==campaign.output.parent/'lab-lease' for call in calls)
    result=read(campaign.output/'campaign.json')
    assert result['execution_outcome']=='ok' and result['evidence_completeness']=='complete'
    assert all(cell['status']=='completed' for cell in result['cells'])
    manifest=read(campaign.output/'manifest.json')
    assert manifest['state']=='complete'
    assert manifest['files']['campaign.json']==worker.sha(campaign.output/'campaign.json')
    assert all(worker.sha(campaign.output/name)==digest for name,digest in manifest['files'].items())


def test_pilot_uses_two_train_cases_and_two_speed_requests(campaign):
    campaign.contract.update(stage='pilot',order=list('AB'))
    assert campaign.run()==0
    assert len(campaign.launches)==4
    assert all(len(json.loads(call['protocol'])['cases'])==2 for call in campaign.launches)


def test_unpinned_contract_stops_before_admission(campaign):
    campaign.path.write_text(json.dumps(campaign.contract))
    assert worker.run(campaign.path,campaign.output,'t','a',contract_sha256='0'*64)==1
    assert not campaign.launches
    assert 'contract changed' in read(campaign.output/'campaign.json')['error']['message']


def test_dataset_mutation_rejected(campaign):
    campaign.dataset.write_text('{}')
    assert campaign.run()==1
    assert not campaign.launches


@pytest.mark.parametrize('report',[
    dict(reason='timeout'),dict(reason='completed',container_exit_code=0,quiescent=True,container_removed=True),
    dict(reason='completed',container_exit_code=0,quiescent=True,container_removed=True,
         evidence_completeness='complete',container_oom_killed=True)])
def test_incomplete_recorder_never_counts_as_success(campaign,monkeypatch,report):
    def fail(argv,**kwargs):
        campaign.launches.append(kwargs)
        return report
    monkeypatch.setattr(worker.lab_recorder,'run_container',fail)
    assert campaign.run()==1
    assert len(campaign.launches)==1
    result=read(campaign.output/'campaign.json')
    assert result['evidence_completeness']=='partial' and result['cells'][0]['status']=='partial'
    assert read(campaign.output/'manifest.json')['state']=='partial'


@pytest.mark.parametrize('corruption',['eos','short','count','parse'])
def test_native_output_failure_stops_campaign(campaign,corruption):
    original=campaign.tools.parse_native
    def parse(stdout,stderr,cases):
        result=original(stdout,stderr,cases)
        if cases[0]['max_new_tokens']==128:
            if corruption=='eos':result['requests'][0]['ids'][0]=1
            if corruption=='short':result['requests'][0]['generated_tokens']=127
            if corruption=='count':result['requests'].pop()
            if corruption=='parse':raise ValueError('malformed transcript')
        return result
    campaign.tools.parse_native=parse
    assert campaign.run()==1
    assert len(campaign.launches)==2
    assert read(campaign.output/'campaign.json')['evidence_completeness']=='partial'


def test_changed_asset_metadata_stops_after_first_engine(campaign):
    state={'n':0}
    def assets(c):
        state['n']+=1
        return {'identity':'before' if state['n']<3 else 'after'}
    campaign.tools.validate_assets=assets
    assert campaign.run()==1
    assert len(campaign.launches)==1
    assert 'asset identity changed' in read(campaign.output/'campaign.json')['error']['message']


def test_interrupt_recovers_owned_partial_and_seals(campaign,monkeypatch):
    recovered=[]
    def interrupted(argv,**kwargs):
        kwargs['output'].mkdir()
        (kwargs['output']/'intent.json').write_text('{}')
        raise SystemExit(143)
    monkeypatch.setattr(worker.lab_recorder,'run_container',interrupted)
    monkeypatch.setattr(worker,'recover_run',lambda output,**kwargs:recovered.append(output))
    assert campaign.run()==143
    assert recovered==[campaign.output/'cell-001-A'/'quality']
    result=read(campaign.output/'campaign.json')
    assert result['execution_outcome']=='cancelled' and result['evidence_completeness']=='partial'
    assert (campaign.output/'manifest.json').is_file()


def test_recovery_error_is_durable(campaign,monkeypatch):
    def interrupted(argv,**kwargs):
        kwargs['output'].mkdir();(kwargs['output']/'intent.json').write_text('{}')
        raise RuntimeError('recorder crashed')
    monkeypatch.setattr(worker.lab_recorder,'run_container',interrupted)
    def recover(*args,**kwargs):raise RuntimeError('ownership mismatch')
    monkeypatch.setattr(worker,'recover_run',recover)
    assert campaign.run()==1
    assert 'ownership mismatch' in read(campaign.output/'campaign.json')['recovery_errors'][0]['error']


def test_deadline_clips_phase_timeout(campaign):
    campaign.contract['campaign_timeout_s']=20
    assert campaign.run()==0
    assert all(0<call['timeout_s']<=20 for call in campaign.launches)


def test_cannot_override_frozen_phases(campaign):
    assert campaign.run(phase_names=('speed',))==1
    assert not campaign.launches


def test_cannot_overwrite_attempt(campaign):
    campaign.output.mkdir()
    (campaign.output/'evidence').write_text('retain')
    with pytest.raises(ValueError,match='already exists'):campaign.run()
    assert (campaign.output/'evidence').read_text()=='retain'


def test_output_cannot_overlap_read_only_model(campaign):
    campaign.contract['workload']['model_root']=str(campaign.output)
    assert campaign.run()==1
    assert not campaign.launches


def test_source_identity_requires_all_worker_dependencies(tmp_path):
    pins={}
    for name in worker._REQUIRED_SOURCES:
        (tmp_path/name).write_text(name);pins[name]=worker.sha(tmp_path/name)
    assert worker.check_source_pins({'execution_sha256':pins},tmp_path)==pins
    (tmp_path/'lab_recorder.py').write_text('mutation')
    with pytest.raises(ValueError,match='execution source changed'):
        worker.check_source_pins({'execution_sha256':pins},tmp_path)
    with pytest.raises(ValueError,match='source identities'):
        worker.check_source_pins({'execution_sha256':{}},tmp_path)


def test_explicit_shared_lease_works_without_factory_home(campaign,monkeypatch):
    monkeypatch.delenv('FACTORY_HOME')
    monkeypatch.setenv('FACTORY_LAB_LEASE',str(campaign.output.parent/'explicit-lease'))
    assert campaign.run()==0
    assert all(call['lease_root']==campaign.output.parent/'explicit-lease' for call in campaign.launches)


def test_source_mutation_during_campaign_stops_before_next_launch(campaign,monkeypatch):
    count={'n':0}
    def pins(contract):
        count['n']+=1
        if count['n']==3:raise ValueError('Admitted benchmark execution source changed')
        return {'frozen':'source'}
    monkeypatch.setattr(worker,'check_source_pins',pins)
    assert campaign.run()==1
    assert len(campaign.launches)==1
    assert 'source changed' in read(campaign.output/'campaign.json')['error']['message']
