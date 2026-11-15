"""Sealed-package/domain-check tests never execute package code or launch jobs."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import cc_qualification as q
from jiuwenswarm.factory.store import NotFound, Store
from test_strata_components import profile


def pair():
    base=profile();base['args'].extend(['--prefill-chunk','256'])
    candidate=copy.deepcopy(base)
    candidate['args'][candidate['args'].index('--prefill-chunk')+1]='512'
    return {'baseline_profile':base,'candidate_profile':candidate}


@pytest.fixture
def setup(tmp_path):
    with Store(tmp_path/'home') as store:
        package=tmp_path/'package';package.mkdir()
        (package/'danger.py').write_text("raise RuntimeError('Package code must never execute during qualification')\n")
        material=dict(format='factory-verification-units/1',implementation_modules=list(q.MODULES),units=[
            dict(id='profile-single-change',capabilities=['apply','verify_profile'],checker=q.CHECKER,claim='Configuration only')])
        (package/'UNITS.json').write_text(json.dumps(material))
        caps={name:dict(does='Synthetic declaration; not invoked',needs=['python'],changes=['process.exec'])
              for name in ('apply','verify_profile','submit')}
        (package/'cc.yaml').write_text(json.dumps(dict(cc='2',id='engine.strata_prefill_workbench',version='1.0.0',
            materials={'verification_units':{'path':'UNITS.json'}},capabilities=caps,
            bindings={'default':{'kind':'native','command':['{python}','{bundle}/danger.py']}})))
        release=Host(store.home/'ccstore').prepare(package)
        policy=dict(id='config',release=release,capabilities=['apply','verify_profile'],
            required_units=['profile-single-change'],allowed_effects=['process.exec'])
        store.create_task(dict(task_id='mine',objective='Explicit domain intake',constraints={'cc_qualification':{'policies':[policy]}}))
        store.create_task(dict(task_id='other',objective='Other scope',constraints={'cc_qualification':{'policies':[policy]}}))
        store.append_observation('mine',dict(obs_id='profile-pair',values=pair(),kind='profile_pair'))
        yield store,release,package,material


def verify(store,release,evidence_id='profile-pair'):
    return q.verify_unit(store.scoped('mine'),'mine',release,'profile-single-change',evidence_id)


def test_identity_many_capabilities_and_independent_domain_check(setup):
    store,release,_,_=setup
    inspected=q.dispatch(store.scoped('mine'),'mine','inspect_package',{'release':release})['package']
    assert set(inspected['capabilities'])=={'apply','verify_profile','submit'}
    assert inspected['release']==release
    assert set(inspected['implementation_module_sha256'])==set(q.MODULES)
    first=verify(store,release);second=verify(store,release)
    assert first==second
    assert first['verification']['verdict']=='passed'
    assert first['verification']['runtime_qualified'] is False
    assert first['verification']['execution_authorized'] is False
    assert first['verification']['identity']['checker_module_sha256']==q._file(q.__file__)
    assert first['verification']['identity']['api_dispatch_sha256']==q._file(Path(q.__file__).with_name('api.py'))
    eligible=q.assess_admission(store.scoped('mine'),'mine','config',[first['observation_id']])['eligibility']
    assert eligible['verdict']=='eligible'
    assert eligible['capabilities']==['apply','verify_profile']
    assert eligible['execution_authorized'] is eligible['promotion_authorized'] is False
    assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0]==0


@pytest.mark.parametrize('mutation',[
    lambda v:v['candidate_profile']['args'].extend(['--skip-experts','1']),
    lambda v:v['candidate_profile']['args'].__setitem__(v['candidate_profile']['args'].index('--experts')+1,'5'),
    lambda v:v['baseline_profile']['environment'].update(DS4_CHUNK='512'),
    lambda v:v['baseline_profile']['environment'].update(STRATA_DS4_REUSE='1'),
    lambda v:v['candidate_profile']['args'].remove('--no-expert-cache'),
    lambda v:v['candidate_profile'].update(image='different-image'),
    lambda v:v['candidate_profile']['args'].__setitem__(v['candidate_profile']['args'].index('--dspark')+1,'on'),
])
def test_negative_profile_checks_retain_failure_and_block_intake(setup,mutation):
    store,release,_,_=setup;value=pair();mutation(value)
    store.append_observation('mine',dict(obs_id='bad-pair',values=value))
    result=verify(store,release,'bad-pair')
    assert result['verification']['verdict']=='failed'
    assert result['verification']['reasons']
    assert q.assess_admission(store.scoped('mine'),'mine','config',[result['observation_id']])['eligibility']['verdict']=='blocked'


def test_unsupported_checker_and_missing_unit_fail_without_execution(setup):
    store,release,package,material=setup
    with pytest.raises(ValueError,match='Missing unit'):q.verify_unit(store.scoped('mine'),'mine',release,'unknown','profile-pair')
    material['units'][0]['checker']='package.code.execute'
    (package/'UNITS.json').write_text(json.dumps(material))
    other=Host(store.home/'ccstore').prepare(package)
    with pytest.raises(ValueError,match='unsupported'):verify(store,other)


@pytest.mark.parametrize('changed_file',['strata_prefill.py','cc_qualification.py','api.py'])
def test_external_implementation_and_checker_hash_changes_invalidate_certificate(setup,monkeypatch,changed_file):
    store,release,_,_=setup;result=verify(store,release)
    original=q._file
    monkeypatch.setattr(q,'_file',lambda path: '0'*64 if Path(path).name==changed_file else original(path))
    with pytest.raises(ValueError,match='stale'):q.assess_admission(store.scoped('mine'),'mine','config',[result['observation_id']])


def test_wrong_task_or_missing_certificate_rejected_even_with_read_grant(setup):
    store,release,_,_=setup;result=verify(store,release)
    with pytest.raises(NotFound):q.assess_admission(store.scoped('other',{'mine'}),'other','config',[result['observation_id']])
    with pytest.raises(NotFound):q.assess_admission(store.scoped('mine'),'mine','config',['missing-certificate'])
    store.append_observation('other',dict(obs_id='other-pair',values=pair()))
    with pytest.raises(NotFound):verify(store,release,'other-pair')


def test_sibling_capability_not_admitted_by_profile_unit(setup):
    store,release,_,_=setup;result=verify(store,release)
    policy=copy.deepcopy(store.get_task('mine')['constraints']['cc_qualification']['policies'][0])
    policy['capabilities']=['submit']
    store.create_task(dict(task_id='sibling',objective='Cannot inherit sibling verification',
        constraints={'cc_qualification':{'policies':[policy]}}))
    store.append_observation('sibling',dict(obs_id='pair',values=pair()))
    verified=q.verify_unit(store.scoped('sibling'),'sibling',release,'profile-single-change','pair')
    assessed=q.assess_admission(store.scoped('sibling'),'sibling','config',[verified['observation_id']])['eligibility']
    assert assessed['verdict']=='blocked'
    assert any('lacks' in reason for reason in assessed['reasons'])


def test_tampered_sealed_material_rejected_by_existing_host(setup):
    store,release,_,_=setup
    path=store.home/'ccstore/releases'/release/'bundle/UNITS.json'
    path.write_text('{}')
    from jiuwenswarm.ccv2.ccv2 import CCError
    with pytest.raises(CCError):q.inspect_package(store.scoped('mine'),release)


def test_no_arbitrary_module_identity_or_extra_inputs(setup):
    store,release,package,material=setup
    material['implementation_modules']=['untrusted_package.evil']
    (package/'UNITS.json').write_text(json.dumps(material));other=Host(store.home/'ccstore').prepare(package)
    with pytest.raises(ValueError,match='unsupported implementation'):q.inspect_package(store.scoped('mine'),other)
    with pytest.raises(ValueError):q.dispatch(store.scoped('mine'),'mine','inspect_package',{'release':release,'command':'echo evil'})


def test_qualification_package_seals_three_capabilities(tmp_path):
    folder=Path(q.__file__).parent/'ccs/cc_qualification'
    host=Host(tmp_path/'store',session_grants=['process.exec'])
    release=host.prepare(folder)
    assert set(host.describe(release)['capabilities'])=={'inspect_package','verify_unit','assess_admission'}
