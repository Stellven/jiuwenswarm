"""Focused closed cache protocol and protected scorer negatives."""
import copy
import json
import os
import subprocess
import sys
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.cache_protocol import PROTOCOL, parse_cache_dataset, parse_cache_output, recompute_cache_results
from jiuwenswarm.research.cache_science import BASELINE, capture_cache_science_resources
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.metric_contract import metric_protocol, validate_metric_declarations, protocol_for_resource
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from jiuwenswarm.research.trusted_cache import RootCacheScorer, scored_empirical_row


def public():
    return {'capacity_entries':1,'replacement':'LRU','traces':{'arbitrary':['x','y','x'],'repeated':['q','q']},'units':{'hits':'requests','misses':'requests','miss_ratio':'fraction'},'source_id':'test-independent-cache'}


def output(data):
    return {'source_id':data['source_id'],'unit':'requests','results':recompute_cache_results(data)}


def test_actual_baseline_execution_and_closed_counts(tmp_path):
    data=public();path=tmp_path/'input.json';path.write_bytes(json_bytes(data))
    source=BASELINE.decode().replace('/resources/validation/data.json',path.as_posix())
    run=subprocess.run([sys.executable,'-c',source],capture_output=True,check=True)
    observed=parse_cache_output(run.stdout,parse_cache_dataset(path.read_bytes()))
    assert observed['results']['arbitrary']=={'hits':0,'misses':3,'unbounded_misses':2}
    assert observed['results']['repeated']=={'hits':1,'misses':1,'unbounded_misses':1}


@pytest.mark.parametrize('mutate',[lambda v:v.update(unit='seconds'),lambda v:v['results']['arbitrary'].update(hits=True),lambda v:v['results']['arbitrary'].update(misses=2),lambda v:v['results'].pop('repeated'),lambda v:v.update(metrics={'miss_ratio':0})])
def test_forged_count_units_coverage_or_metric_rejected(mutate):
    data=public();value=output(data);mutate(value)
    with pytest.raises(ResearchError):parse_cache_output(json_bytes(value),data)


def test_duplicate_json_and_unknown_protocol_rejected():
    with pytest.raises(ResearchError):parse_cache_dataset(b'{"capacity_entries":1,"capacity_entries":2}')
    with pytest.raises(ResearchError):metric_protocol('arbitrary-model-protocol')
    metric=metric_protocol(PROTOCOL)['metrics'][0]
    validate_metric_declarations([metric],PROTOCOL)
    with pytest.raises(ResearchError):validate_metric_declarations([dict(metric,unit='requests')],PROTOCOL)
    assert metric_protocol()['metrics'][0]['metric_id']=='accuracy'
    assert protocol_for_resource({},lambda _:b'') is None


def test_capture_pins_exact_public_bytes(tmp_path):
    path=tmp_path/'data.json';path.write_bytes(json_bytes(public()))
    store=SQLiteRunStore(tmp_path/'store')
    try:
        captured=capture_cache_science_resources(store,public_path=path)
        profile=captured['scoring_profile'];resource=store.read_record(profile['public_dataset_ref'])
        assert resource['files'][0]['artifact_ref']['sha256']==profile['public_data_sha256']
        assert protocol_for_resource(resource,store.read_blob)==PROTOCOL
        assert store.read_blob(resource['files'][0]['artifact_ref'])==path.read_bytes()
    finally:store.close()


@pytest.mark.skipif(os.name!='posix',reason='root broker scoring requires Linux')
def test_root_scoring_roles_and_original_stdout_binding(tmp_path):
    path=tmp_path/'data.json';path.write_bytes(json_bytes(public()))
    store=SQLiteRunStore(tmp_path/'store')
    try:
        captured=capture_cache_science_resources(store,public_path=path);p=captured['scoring_profile']
        scorer=RootCacheScorer(store,p);resource=store.read_record(p['public_dataset_ref'])
        for role,expected in [('baseline',3/5),('treatment',4/5)]:
            ref=store.put_blob(b'test identity')
            job=SimpleNamespace(run_id='test-run',node_id='test-node',attempt_id='test-attempt',invocation_id='test-inv',job_id='test-'+role,sequence=1,role=role,repeat_index=0,seed=42,contract_ref=ref,subject_ref=ref,validation_ref=p['public_dataset_ref'])
            raw={k:getattr(job,k) for k in ('job_id','contract_ref','invocation_id','sequence','role','repeat_index','seed','subject_ref')}
            raw.update(observed_runtime=True,exit_code=0,termination_reason='completed',stdout_ref=store.put_blob(json_bytes(output(public()))))
            scored=scorer.score(job,raw,resource);score=store.read_record(scored['trusted_scoring_ref'])
            assert scored_empirical_row(scored,score)['metrics']=={'miss_ratio':expected}
            with pytest.raises(ResearchError):scored_empirical_row(dict(scored,sequence=999),score)
            with pytest.raises(ResearchError):scorer.score(job,scored,resource)
            bad=dict(raw,stdout_ref=store.put_blob(b'{}'))
            failed=scorer.score(job,bad,resource);failure=store.read_record(failed['trusted_scoring_ref'])
            assert scored_empirical_row(failed,failure)['status']=='unmeasured'
    finally:store.close()

@pytest.mark.skipif(os.name!='posix',reason='captured execution roots are Linux absolute paths')
def test_cache_runtime_has_new_closed_version_and_rejects_extra_authority(tmp_path):
    from jiuwenswarm.research.science_runtime import decode_science_runtime_record
    from jiuwenswarm.research.executor import ExecutorBlocked
    path=tmp_path/'data.json';path.write_bytes(json_bytes(public()))
    store=SQLiteRunStore(tmp_path/'store')
    try:
        scoring=capture_cache_science_resources(store,public_path=path)['scoring_profile']
        profile={'asset_root':'/var/lib/ai4r-executor/assets','environment_root':'/var/lib/ai4r-executor/environments','memory_mb':1024,'pids_max':64,'run_timeout_s':60,'provision_timeout_s':60,'baseline_arguments':[],'treatment_arguments':[],'uv_path':'/usr/local/bin/uv','python_path':sys._base_executable}
        value={'schema':'ai4r-science-runtime:6','id':'test-runtime','build_id':'test-build','profile':profile,'gpu_required':False,'approved_environments':[],'execution_bindings':[],'scoring_profile':scoring,'execution_mode':'restricted'}
        assert decode_science_runtime_record(value).record==value
        assert decode_science_runtime_record(dict(value,execution_mode='m1_app_process')).record['schema']=='ai4r-science-runtime:6'
        with pytest.raises(ExecutorBlocked):decode_science_runtime_record(dict(value,schema='ai4r-science-runtime:5'))
        bad=copy.deepcopy(value);bad['scoring_profile']['model_authorized']=True
        with pytest.raises(ExecutorBlocked):decode_science_runtime_record(bad)
    finally:store.close()
