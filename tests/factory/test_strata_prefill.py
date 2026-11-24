"""Synthetic profile, policy, wire and metric tests; no GPU execution."""
import copy
from pathlib import Path

import pytest

from jiuwenswarm.factory import benchmark as b
from jiuwenswarm.factory.strata_prefill import apply, dispatch
from test_strata_components import profile
from test_benchmark import contract as v1_contract
from test_benchmark_analysis import fixture, decode
from jiuwenswarm.factory.benchmark_analysis import analyze


def base():
    value = profile()
    value['args'].extend(['--prefill-chunk', '256'])
    return value


def v2():
    value = v1_contract.__wrapped__()
    value.update(adapter=b.PREFILL_ADAPTER, version=2, component='strata.prefill_chunk',
                 primary_metric='prefill_plus_decode_output_tokens_per_second')
    value['execution_sha256'] = {name:'a'*64 for name in b.V2_EXECUTION_FILES}
    for arm in ('A','B'):
        value['arms'][arm]['environment'].update(DS4_UMA_HEADROOM_GIB='16', DS4_COPY_ALL='0', DS4_STORE_GB='0')
        args = value['arms'][arm]['args']
        args[args.index('--dspark')+1] = 'none'
    value['arms']['B'] = apply(value['arms']['A'],512)['profile']
    return value


def test_single_setting_reversible_and_sealable(tmp_path):
    baseline = base(); before = copy.deepcopy(baseline)
    result = dispatch(dict(base_profile=baseline,chunk_tokens=512))
    assert baseline == before
    assert result['change']['changed_paths'] == [f"args[{baseline['args'].index('--prefill-chunk')+1}]"]
    assert apply(result['profile'],256)['profile'] == baseline
    assert apply(result['profile'],512)['change']['changed'] is False
    from jiuwenswarm.ccv2.ccv2 import Host
    folder=Path(b.__file__).parent/'ccs/strata_prefill_chunk'
    assert Host(tmp_path/'store',session_grants=['process.exec']).prepare(folder)


@pytest.mark.parametrize('value',[128,0,-1,8192,True,'512',512.0])
def test_only_effective_bounded_integer_chunks(value):
    with pytest.raises(ValueError):apply(base(),value)


@pytest.mark.parametrize('key',['DS4_CHUNK','DS4_WINDOWS','DS4_CHUNK_MIN'])
def test_effective_setting_cannot_be_overridden(key):
    value=base();value['environment'][key]='1'
    with pytest.raises(ValueError):apply(value,512)


def test_v2_policy_and_profile_driven_wire():
    contract=v2();before=copy.deepcopy(contract)
    assert b.validate_contract(contract) is contract
    assert contract==before
    cases=[dict(ids=[42],max_new_tokens=8)]
    for arm in ('A','B'):
        assert b'spec=0' in b.protocol(cases,arm,contract)
    contract['arms']['B']['args'][contract['arms']['B']['args'].index('--dspark')+1]='on'
    assert b'spec=1' in b.protocol(cases,'B',contract)
    with pytest.raises(ValueError):b.validate_contract(contract)


@pytest.mark.parametrize('mutation',['metric','second_knob','environment','pins','baseline_chunk','candidate_chunk'])
def test_v2_rejects_changed_policy(mutation):
    contract=v2()
    if mutation=='metric':contract['primary_metric']='decode'
    if mutation=='second_knob':contract['arms']['B']['args'][contract['arms']['B']['args'].index('--cpu-threads')+1]='4'
    if mutation=='environment':contract['arms']['B']['environment']['DS4_AHEAD']='1'
    if mutation=='pins':contract['execution_sha256'].pop('strata_prefill.py')
    if mutation=='baseline_chunk':contract['arms']['A']['args'][contract['arms']['A']['args'].index('--prefill-chunk')+1]='512'
    if mutation=='candidate_chunk':contract['arms']['B']['args'][contract['arms']['B']['args'].index('--prefill-chunk')+1]='1024'
    with pytest.raises(ValueError):b.validate_contract(contract)


def trial(stage='main'):
    contract,dataset,cells=fixture(stage=stage,ratio=1)
    contract.update(adapter=b.PREFILL_ADAPTER,version=2,primary_metric='prefill_plus_decode_output_tokens_per_second')
    for cell in cells:
        for request in cell['speed']['requests']:
            request.update(offered_drafts=0,accepted_drafts=0,decode_ms=1000,prefill_ms=1000 if cell['arm']=='A' else 500)
    return contract,dataset,cells


def test_prefill_improvement_scores_without_drafts_and_decode_gain_not_required():
    result=analyze(*trial(),decode)
    assert result['verdict']=='accept'
    assert result['speed']['geometric_mean_ratio_B_over_A']==pytest.approx(4/3)
    assert result['speed']['acceptance_scope']=='warm_native_prefill_plus_decode'
    assert 'candidate_drafting_engaged' not in result['gates']
    assert result['gates']['drafting_disabled_in_both_arms'] is True


def test_decode_improvement_cannot_hide_prefill_regression():
    args=trial()
    for cell in args[2]:
        if cell['arm']=='B':
            for request in cell['speed']['requests']:request.update(decode_ms=100,prefill_ms=3000)
    assert analyze(*args,decode)['verdict']=='speedNoImprovement'


def test_drafts_rejected_and_pilot_has_no_speed_acceptance():
    result=analyze(*trial('pilot'),decode)
    assert result['verdict']=='pilot_ok'
    assert result['performance_acceptance_evaluated'] is False
    args=trial();args[2][1]['speed']['requests'][1].update(offered_drafts=1)
    assert analyze(*args,decode)['verdict']=='inconclusive'


def test_effective_chunk_fallback_and_draft_counts_fail_closed():
    contract=v2();parsed=dict(requests=[dict(accepted_drafts=0,offered_drafts=0)])
    b.verify_prefill_engagement(contract,'B',parsed,'read ahead; prompts in chunks of 512)')
    assert parsed['effective_prefill_chunk']==512
    for stderr in ('', 'read ahead; prompts in chunks of 256)'):
        with pytest.raises(ValueError):b.verify_prefill_engagement(contract,'B',parsed,stderr)
    parsed['requests'][0]['offered_drafts']=1
    with pytest.raises(ValueError):b.verify_prefill_engagement(contract,'B',parsed,'prompts in chunks of 512)')


def test_loop_child_request_waits_under_parent_mission(tmp_path,monkeypatch):
    import json
    from jiuwenswarm.factory.store import Store
    from jiuwenswarm.factory.mission_supervisor import mission_root
    contract=v2();contract['workspace_root']=str(tmp_path)
    path=tmp_path/'contract.json';path.write_text(json.dumps(contract))
    monkeypatch.setenv('FACTORY_BRIDGE_DIR',str(tmp_path/'bridge'))
    monkeypatch.setattr(b,'load_dataset',lambda c:{})
    with Store(tmp_path/'home') as store:
        store.create_task(dict(task_id='parent',objective='bounded loop'))
        store.create_task(dict(task_id='child',objective='frozen benchmark',contract_id=str(path),
            constraints={'benchmark_contract_sha256':b.sha(path),'factory_loop_parent':'parent'}))
        manager=b.Benchmark(store);calls=[]
        monkeypatch.setattr(manager.jobs,'submit',lambda *args:calls.append(args) or {})
        manager.submit('child',str(path),'one')
        request=calls[0][2];environment=calls[0][-1]
        assert request['adapter']==b.PREFILL_ADAPTER
        assert request['quiet_required'] is True
        assert request['quiet_root']==str(mission_root(store.home,'parent'))
        assert environment['FACTORY_BENCHMARK_QUIET_ROOT']==request['quiet_root']


def test_fixed_budget_is_preserved_without_widening_other_overrides():
    import copy
    from jiuwenswarm.factory.strata_prefill import apply
    import pytest
    base={'args':['--pack','/models/deepseek-v4.1-flash','--max-context','8192','--eos','1','--vision','off',
                  '--dspark','none','--prefill-chunk','256','--cpu-threads','8','--vram-experts','1.0',
                  '--reserve-mib','16384','--ssd-cache','0','--mmap-experts','on','--experts','6','--verbose',
                  '--dspark-conf','0.65','--no-expert-cache'],
          'environment':{'DS4_AHEAD':'0','DS4_ASYNC_T':'4','DS4_COPY_ALL':'0','DS4_ENGRAM_CACHE_MB':'64',
                         'DS4_ENGRAM_THREADS':'2','DS4_EXPERT_BUDGET_BYTES':'76000000000','DS4_STORE_GB':'0',
                         'DS4_UMA_HEADROOM_GIB':'16','STRATA_DS4_REUSE':'0'}}
    before=copy.deepcopy(base)
    result=apply(base,1024)
    assert base==before
    expected=copy.deepcopy(base);expected['args'][expected['args'].index('--prefill-chunk')+1]='1024'
    assert result['profile']==expected
    assert result['change']['fixed_budget_engine_required'] is True
    for value in ['0','-1','1e10',True,'76000000000\n','9'*1000]:
        changed=copy.deepcopy(base);changed['environment']['DS4_EXPERT_BUDGET_BYTES']=value
        with pytest.raises(ValueError):apply(changed,1024)
    changed=copy.deepcopy(base);changed['environment']['DS4_CHUNK']='512'
    with pytest.raises(ValueError):apply(changed,1024)


def test_coverage_exposes_vacuous_short_prompt_quality_checks(tmp_path, monkeypatch):
    from jiuwenswarm.factory.strata_prefill import coverage
    from jiuwenswarm.ccv2.ccv2 import Host
    import sys
    short=coverage([109,118,129],256,1024)
    assert short['predicted_changed_chunk_count_cases']==0
    assert not short['runtime_engagement_verified']
    long=coverage([256,257,1024,4096],256,1024)
    assert long['predicted_changed_chunk_count_cases']==3
    assert long['cases'][-1]['baseline_chunks']==16
    assert long['cases'][-1]['candidate_chunks']==4
    for bad in [[],[True],[0],[8193],[1.5]]:
        with pytest.raises(ValueError):coverage(bad,256,1024)
    # Match the Controller's admitted factory module path for this core-bound CC.
    monkeypatch.setenv('PYTHONPATH', str(Path(__file__).resolve().parents[2]))
    host=Host(tmp_path/'coverage-host',session_grants=['process.exec'],python=sys.executable)
    release=host.prepare(Path(b.__file__).parent/'ccs/strata_prefill_chunk')
    receipt=host.call(release,'coverage',dict(prompt_lengths=[109,4096],baseline_chunk=256,candidate_chunk=1024))
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['analysis']['predicted_changed_chunk_count_cases']==1
