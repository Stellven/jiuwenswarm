"""Finite transform and real CC bridge qualification; no GPU execution."""
import copy
import json
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import throughput_workbench as w
from jiuwenswarm.factory.store import Store
from test_strata_prefill import base


def profile():
    p=base()
    p['environment'].update(DS4_AHEAD='0',DS4_ENGRAM_THREADS='2',DS4_ENGRAM_CACHE_MB='64')
    return p


@pytest.mark.parametrize('setting,value', [('cpu_threads',4),('cpu_threads',6),
    ('engram_threads',1),('engram_threads',4),('engram_cache_mb',0),
    ('engram_cache_mb',256),('ahead',1),('prefill_chunk',512),('drafting',1)])
def test_finite_transform_is_immutable_single_field_and_verified(setting,value):
    p=profile(); original=copy.deepcopy(p)
    result=w.apply(p,setting,value)
    assert p==original
    assert len(result['change']['changed_paths'])==1
    assert result['change']['runtime_engagement']=='not_measured'
    assert result['change']['execution_authorized'] is False
    again=w.apply(result['profile'],setting,value)
    assert again['change']['changed'] is False
    inputs=dict(base_profile=p,candidate_profile=result['profile'],setting=setting,value=value)
    assert w.dispatch(None,None,'verify_profile',inputs)['result']['configuration_verified']
    inputs['candidate_profile']=copy.deepcopy(result['profile'])
    inputs['candidate_profile']['environment']['DS4_ENGRAM_CACHE_MB']='128'
    with pytest.raises(ValueError):w.dispatch(None,None,'verify_profile',inputs)


@pytest.mark.parametrize('setting,value',[('ahead',2),('engram_threads',64),
    ('cpu_threads',True),('cpu_threads','4'),('prefill_chunk',128),('store',1)])
def test_invalid_unbounded_or_wrongly_typed_treatments_rejected(setting,value):
    with pytest.raises(ValueError):w.apply(profile(),setting,value)


@pytest.mark.parametrize('mutation',['reserve','override','skip','draft_auto','async','implicit'])
def test_fixed_envelope_rejects_unsafe_or_implicit_treatments(mutation):
    p=profile()
    if mutation=='reserve':p['args'][p['args'].index('--reserve-mib')+1]='8192'
    elif mutation=='override':p['environment']['DS4_CHUNK']='512'
    elif mutation=='skip':p['args']+=['--skip-experts','1']
    elif mutation=='draft_auto':p['args'][p['args'].index('--dspark')+1]='auto'
    elif mutation=='async':p['environment']['DS4_ASYNC_T']='8'
    else:del p['environment']['DS4_ENGRAM_THREADS']
    with pytest.raises(ValueError):w.apply(p,'engram_threads',4)


def test_actual_host_package_inspection_transform_evidence_and_gpu_grant(tmp_path,monkeypatch):
    home=tmp_path/'factory'
    with Store(home) as store:
        store.create_task(dict(task_id='throughput',objective='Bounded config investigation',allowed_effects=['process.exec']))
    monkeypatch.setenv('FACTORY_HOME',str(home));monkeypatch.setenv('FACTORY_TASK_ID','throughput')
    monkeypatch.setenv('PYTHONPATH',str(Path.cwd()));monkeypatch.delenv('FACTORY_BRIDGE_DIR',raising=False)
    host=Host(home/'ccstore',session_grants=['process.exec'],python=sys.executable)
    package=Path(w.__file__).parent/'ccs/strata_throughput_workbench'
    release=host.prepare(package)
    desc=host.describe(release)
    assert desc['capabilities']['execute']['changes']==['process.exec','gpu.use']
    def call(name,**inputs):
        receipt=host.call(release,name,inputs)
        assert receipt['state']=='succeeded',receipt
        return receipt['outputs']
    assert call('inspect')['result']['execution_performed'] is False
    p=profile()
    changed=call('apply',base_profile=p,setting='engram_threads',value=4)['result']['profile']
    assert call('verify_profile',base_profile=p,candidate_profile=changed,setting='engram_threads',value=4)['result']['configuration_verified']
    assert call('publish',type='observation',record=dict(obs_id='throughput-seed',kind='report',values={'measurement':'not_performed'}))['record']['obs_id']=='throughput-seed'
    assert call('read',id='throughput-seed')['record']['values']['measurement']=='not_performed'
    assert any(row['id']=='throughput-seed' for row in call('query')['items'])
    assert host.call(release,'execute',dict(cycle_id='unadmitted'))['state']=='blocked'
    assert host.call(release,'design',dict(template_id='unadmitted'))['state']=='failed'
    with Store(home) as store:
        assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0]==0


def test_design_checks_installed_identity_before_contract_validation(tmp_path,monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from jiuwenswarm.factory import benchmark as broad_benchmark
    path=tmp_path/'template.json';path.write_text(json.dumps({'test':'explicit simulated contract validator'}))
    entry=dict(id='screen',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    store=SimpleNamespace(get_task=lambda task_id:dict(constraints={'factory_loop':{'templates':[entry]}}))
    validations=[]
    monkeypatch.setattr(broad_benchmark,'validate_contract',lambda c:validations.append(c) or c)
    result=w.design(store,'task','screen')
    assert result['contract_sha256']==entry['sha256']
    assert result['execution_performed'] is False and len(validations)==1
    path.write_text('{}')
    with pytest.raises(ValueError,match='identity changed'):w.design(store,'task','screen')
    assert len(validations)==1
    with pytest.raises(ValueError,match='operator-installed'):w.design(store,'task','unknown')
