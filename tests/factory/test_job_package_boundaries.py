"""Composed job packages retain host scope and report semantics."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory import methodology
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.store import ScopeDenied


def test_builder_cannot_operate_on_same_task_lab_attempt(store, monkeypatch):
    from jiuwenswarm.factory.builder import Builder
    attempt=store.create_attempt('t',dict(kind='lab',idem_key='lab',fingerprint='fixture',request={}))
    called=[]
    for operation in ('status','result','cancel'):
        monkeypatch.setattr(Builder,operation,lambda *a:called.append(a))
        with pytest.raises(ScopeDenied,match='not a build'):
            dispatch(store.scoped('t'),'t','builder.'+operation,{'inputs':{'attempt_id':attempt['attempt_id']}})
    assert not called


def test_scoped_report_normalizes_without_inventing_decode_speed_or_repeatability():
    report=dict(scope='prefill_microbenchmark',verdict='scoped_correctness_failed',cells=[
        dict(arm=arm,requests=[dict(prefill_ms=ms,decode_ms=.1,generated_tokens=1,ids=[token],finish='length')]*7)
        for arm,ms,token in [('A',4400,9544),('B',3200,5)]])
    before=copy.deepcopy(report)
    result=methodology.diagnose([{'report':report}],['screen'])
    assert result['request_count']==14
    assert result['prefill_ms']['count']==14
    assert result['failure_count']==1
    assert result['failures'][0]['status']=='correctness_failed'
    assert result['recommended_inspection']=='diagnose_failure'
    assert result['decode_tps']['count']==0  # not a spurious 10000 tokens/s
    assert result['repeatability']['status']=='not_established'  # no invented prompt/config identity
    assert report==before
    followup=methodology.followup(result,{'task_id':'t','target':'spark-gb10'})
    assert followup['proposed_input']['hypothesis_id']=='diagnose_failure'
    assert followup['status']=='proposal_only'


def test_nested_report_bound_and_existing_measurement_rates():
    doc={'measurements':[{'requests':[{'generated_tokens':12,'decode_ms':2000}]}]}
    assert methodology.diagnose([doc],['a'])['decode_tps']['median']==6
    for _ in range(6):doc={'report':doc}
    with pytest.raises(ValueError,match='nesting'):
        methodology.diagnose([doc],['a'])


def test_job_router_matches_declared_surface_and_does_not_union_effects():
    import yaml
    from jiuwenswarm.factory.job_packages import ROUTES
    root=Path('jiuwenswarm/factory/ccs')
    names={'factory.integration_skill':'integration_skill','engine.expert_streaming':'expert_streaming',
           'factory.inference_lab':'inference_lab','engine.strata_prefill_workbench':'strata_prefill_workbench'}
    for package_id,folder in names.items():
        manifest=yaml.safe_load((root/folder/'cc.yaml').read_text())
        assert set(manifest['capabilities'])==set(ROUTES[package_id])
        for name,route in ROUTES[package_id].items():
            effects=manifest['capabilities'][name]['changes']
            if route in {'factory_loop.execute','lab.submit','lab.ab_submit','prefill_workbench.submit'}:
                assert 'gpu.use' in effects
            if route.startswith(('evidence.','inference_methods.')):
                assert 'gpu.use' not in effects
