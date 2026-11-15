"""Scope advice cannot silently upgrade evidence or bypass delegated scoping."""
import pytest

from jiuwenswarm.factory import experiment_methods as methods
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.store import NotFound


@pytest.mark.parametrize('claim,scope', [
    ('configuration_invariant','component'), ('prediction_quality','offline_replay'),
    ('subsystem_performance','subsystem'), ('end_to_end_performance','integration'),
    ('recovery_reliability','fault_recovery')])
def test_scope_keeps_claim_boundaries(claim, scope):
    result = methods.test_scope(claim, 'prefill')
    assert result['smallest_useful_scope'] == scope
    assert result['limitations'] and result['verification_obligations']
    assert result['execution_authorized'] is False
    assert result['promotion_authorized'] is False


def test_scope_rejects_unknown_claim_and_fields(store):
    for inputs in ({'claim':'automatic_promotion','layer':'prefill'},
                   {'claim':'subsystem_performance','layer':'everything'},
                   {'claim':'subsystem_performance','layer':'prefill','execute':True}):
        with pytest.raises(ValueError):
            dispatch(store.scoped('t'), 't', 'inference_methods.test_scope', {'inputs':inputs})


def test_bundled_method_retains_evidence_scope(store):
    store.create_task(dict(task_id='private', objective='Other task'))
    store.append_observation('private', dict(obs_id='private-report',kind='report',values={'status':'success'}))
    with pytest.raises(NotFound):
        dispatch(store.scoped('t'), 't', 'inference_methods.diagnose',
                 {'inputs':{'evidence_ids':['private-report']}})
    store.append_observation('t', dict(obs_id='local-report',kind='report',values={'status':'success'}))
    result = dispatch(store.scoped('t'), 't', 'inference_methods.diagnose',
                      {'inputs':{'evidence_ids':['local-report']}})
    assert result['analysis']['evidence_sources'] == [{'task_id':'t','evidence_id':'local-report'}]


def test_scope_is_callable_through_native_package(tmp_path, monkeypatch):
    import os
    import sys
    from pathlib import Path
    from jiuwenswarm.ccv2.ccv2 import Host
    from jiuwenswarm.factory.store import Store
    home = tmp_path/'native-store'
    with Store(home) as store:
        store.create_task(dict(task_id='native', objective='Scoped method'))
    monkeypatch.setenv('FACTORY_HOME',str(home))
    monkeypatch.setenv('FACTORY_TASK_ID','native')
    monkeypatch.setenv('PYTHONPATH',str(Path.cwd()))
    monkeypatch.delenv('FACTORY_BRIDGE_DIR',raising=False)
    host=Host(tmp_path/'ccstore',session_grants=['process.exec'],python=sys.executable)
    release=host.prepare(Path('jiuwenswarm/factory/ccs/inference_lab'))
    receipt=host.call(release,'test_scope',{'claim':'subsystem_performance','layer':'prefill'},key='scope-test')
    assert receipt['state']=='succeeded', receipt
    assert receipt['outputs']['analysis']['smallest_useful_scope']=='subsystem'
    assert receipt['outputs']['analysis']['promotion_authorized'] is False


def test_caller_cannot_publish_scoped_host_result(store):
    from jiuwenswarm.factory.store import ScopeDenied
    with pytest.raises(ScopeDenied):
        dispatch(store.scoped('t'),'t','evidence.publish',{'inputs':{'type':'observation',
            'record':{'kind':'scoped_prefill_result','values':{'verdict':'scoped_improvement'}}}})
