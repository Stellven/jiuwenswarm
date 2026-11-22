"""Native configuration component transformations; no model or GPU execution."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory.strata_components import apply, dispatch


def profile():
    return dict(args=['--pack','/pack','--experts','6','--mmap-experts','on','--cpu-threads','8',
        '--reserve-mib','16384','--vram-experts','1.0','--dspark','none','--dspark-conf','0.65',
        '--no-expert-cache'],environment={'STRATA_DS4_REUSE':'0','DS4_UMA_HEADROOM_GIB':'16',
        'DS4_COPY_ALL':'0','DS4_STORE_GB':'0','DS4_ASYNC_T':'4'},
        image='sha256:'+'a'*64,limits={'cpus':8,'memory_bytes':104*2**30})


def test_apply_is_single_setting_and_never_mutates_base():
    baseline=profile();before=copy.deepcopy(baseline)
    result=dispatch({'base_profile':baseline,'enabled':True})
    assert baseline==before
    assert result['profile']['environment']==baseline['environment']
    assert result['profile']['image']==baseline['image']
    assert result['profile']['limits']==baseline['limits']
    differences=[i for i,(a,b) in enumerate(zip(baseline['args'],result['profile']['args'])) if a!=b]
    assert differences==[baseline['args'].index('--dspark')+1]
    assert result['profile']['args'][differences[0]]=='on'
    assert result['change']['changed_paths']==[f'args[{differences[0]}]']
    assert result['change']['performance_benefit']=='unknown'
    assert result['change']['status']=='candidate_profile_only'
    assert result['change']['before_sha256']!=result['change']['after_sha256']


def test_apply_idempotent_and_reversible_to_identical_baseline():
    baseline=profile()
    first=apply(baseline,True)
    repeated=apply(first['profile'],True)
    assert repeated['profile']==first['profile']
    assert repeated['change']['changed'] is False
    assert repeated['change']['changed_paths']==[]
    restored=apply(first['profile'],False)
    assert restored['profile']==baseline
    unchanged=apply(baseline,False)
    assert unchanged['profile']==baseline
    assert unchanged['change']['before_sha256']==unchanged['change']['after_sha256']
    assert unchanged['change']['changed'] is False


def test_env_alias_preserved_without_adding_another_mapping():
    baseline=profile();baseline['env']=baseline.pop('environment')
    result=apply(baseline,True)['profile']
    assert result['env']==baseline['env']
    assert 'environment' not in result


@pytest.mark.parametrize('enabled',[None,1,0,'true',{},[]])
def test_enabled_is_boolean_only(enabled):
    with pytest.raises(ValueError,match='boolean'):apply(profile(),enabled)


@pytest.mark.parametrize('flag,value',[
    ('--experts','5'),('--mmap-experts','off'),('--cpu-threads','4'),
    ('--reserve-mib','8192'),('--vram-experts','0.5'),('--dspark','auto'),
    ('--dspark','off'),('--dspark-conf','0.8')])
def test_unsafe_or_confounding_baseline_rejected(flag,value):
    base=profile();base['args'][base['args'].index(flag)+1]=value
    with pytest.raises(ValueError):apply(base,True)


@pytest.mark.parametrize('mutation',[
    lambda p:p['args'].extend(['--dspark','none']),
    lambda p:p['args'].extend(['--skip-layers','2']),
    lambda p:p['args'].remove('--no-expert-cache'),
    lambda p:p['environment'].update(DS4_SKIP_EXPERTS='1'),
    lambda p:p['environment'].update(STRATA_DS4_REUSE='1'),
    lambda p:p['environment'].update(DS4_UMA_HEADROOM_GIB='8'),
    lambda p:p['environment'].update(DS4_STORE_GB='16'),
    lambda p:p.update(env={}),
    lambda p:p.update(unknown_number=float('nan')),
])
def test_invalid_profiles_fail_without_mutation(mutation):
    base=profile();mutation(base);before=copy.deepcopy(base)
    with pytest.raises(ValueError):apply(base,True)
    # NaN is deliberately not equal to itself; compare serialized data for this
    # negative input instead of treating it as an accepted candidate.
    assert json.dumps(base,sort_keys=True)==json.dumps(before,sort_keys=True)


def test_dispatch_rejects_extra_or_missing_fields():
    for inputs in [{},{'base_profile':profile()},{'base_profile':profile(),'enabled':True,'run':True}]:
        with pytest.raises(ValueError):dispatch(inputs)


def test_cc_seals_with_boolean_input_schema(tmp_path):
    from jiuwenswarm.ccv2.ccv2 import Host
    folder=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/strata_verified_drafting'
    host=Host(tmp_path/'ccstore',session_grants=['process.exec'])
    release=host.prepare(folder)
    assert release
    assert host.material(release,'methodology')
    assert host.material(release,'component')
