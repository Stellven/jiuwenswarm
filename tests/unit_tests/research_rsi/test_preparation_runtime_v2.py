"""Complete offline facade vectors; no runtime, model or admission authority."""
import asyncio
import base64
import copy
import json
import os
from pathlib import Path
import sys

import pytest

from jiuwenswarm.research_rsi import preparation_runtime as runtime
from jiuwenswarm.research_rsi import session_preparation as compiler
from jiuwenswarm.research_rsi.records import RecordStore,encoded


def fixture(tmp_path,monkeypatch,*,projection=False):
    from tests.unit_tests.research_rsi.test_session_preparation import fixture as session_fixture
    store,values,manifest,target=session_fixture(tmp_path,monkeypatch)
    hidden=None;private_preparation=None
    if projection:
        calibration=store.put({'schema':'unit:private-calibration','secret':'NEVER_EXPORT_CALIBRATION_SENTINEL'})
        review=store.put({'schema':'unit:private-review','secret':'NEVER_EXPORT_REVIEW_SENTINEL'})
        hidden=store.put({'secret':'NEVER_EXPORT_HIDDEN_SENTINEL'})
        private_preparation=store.put({'schema':'unit:private-preparation','secret':'NEVER_EXPORT_PREPARATION_SENTINEL'})
        target['calibration_ref']=calibration
        target['improver_ref']=store.put({'public_improver':'separately approved original required'})
        target['protected_refs'].append(hidden)
        values['target_ref']=store.put(target)
        manifest.update(target_ref=values['target_ref'],calibration_ref=calibration,independence_evidence_ref=review)
        manifest['partitions']['hidden_final'][0]['expected_ref']=hidden
        values['fixture_manifest_ref']=store.put(manifest)
    private=store.root;inputs=tmp_path/'inputs';inputs.mkdir(mode=0o700)
    native=sys.platform=='linux' and hasattr(os,'geteuid') and os.geteuid()==12002
    private_value=str(private) if os.name=='posix' else '/custodian/private'
    input_value=str(inputs) if os.name=='posix' else '/custodian/inputs'
    key_value=str(tmp_path/'no-key') if os.name=='posix' else '/custodian/no-key'
    if not native:
        monkeypatch.setattr(runtime,'_identity',lambda:None)
        monkeypatch.setattr(runtime,'_private_root',lambda value:private if value==private_value else inputs)
        monkeypatch.setattr(runtime,'require_custodian_store',lambda value:value)
        original=runtime._path
        monkeypatch.setattr(runtime,'_path',lambda value:{private_value:private,input_value:inputs,key_value:tmp_path/'no-key'}.get(str(value),Path(value)))
    config={'schema':'ai4r-rsi-preparation-service:1','record_root':private_value,'approved_request_refs':[],
        'approved_plan_refs':[],'approved_preparation_refs':[],'public_roots':[],'public_original_refs':[],
        'worker':{'socket_path':'/run/ai4r-rsi-worker/hidden/helper.sock','session_id':'unit:worker',
            'capability':'C'*64,'requests_root':input_value,'profile_refs':[]},
        'signing_key_file':key_value,'signer_key_id':'unit:custodian'}
    monkeypatch.setattr(runtime,'_qualification',lambda *a:pytest.fail('Offline compilation requested qualification'))
    monkeypatch.setattr(runtime,'WorkerClient',lambda **k:pytest.fail('Offline compilation constructed a worker client'))
    monkeypatch.setattr(runtime,'_signer',lambda *a:pytest.fail('Offline compilation opened a signing key'))
    return dict(store=store,values=values,manifest=manifest,target=target,config=config,
                hidden=hidden,preparation=private_preparation,inputs=inputs,key=tmp_path/'no-key')


def capture_request(f,operation,parameters,version=2):
    request={'schema':'ai4r-rsi-preparation-request:'+str(version),'operation':operation,'parameters':parameters}
    pin=f['store'].put(request)
    f['config']['approved_request_refs'].append(pin)
    return pin


def dispatch(f,operation,parameters,version=2):
    pin=capture_request(f,operation,parameters,version)
    return asyncio.run(runtime.execute(f['config'],operation,pin))


def parent_bodies(store,target):
    parent=store.get(target['parent_declaration_ref']);bodies={}
    for row in parent['identity']['body']:
        if row['path']==target['mutable_paths'][0]:bodies[row['path']]=target['parent_ref'];continue
        alias=store.db.execute('SELECT id FROM original_aliases WHERE sha256=? ORDER BY id LIMIT 1',(row['sha256'],)).fetchone()
        bodies[row['path']]={'id':alias[0] if alias else row['sha256']+'.json','sha256':row['sha256']}
    return bodies


def test_v2_facade_compiles_real_offline_records_and_keeps_v1_distinct(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    try:
        parameters={'schema':'ai4r-rsi-helper-session-request:1',**f['values']}
        result=dispatch(f,'compile-helper-session',parameters)
        assert result['status']=='COMPILED_NOT_STARTED'
        assert f['store'].get(result['worker_profile_ref'])['session_ref']==result['session_ref']
        assert f['config']['worker']['profile_refs']==[]
        assert f['store'].db.execute('SELECT count(*) FROM session_history').fetchone()[0]==0
        with pytest.raises(ValueError):dispatch(f,'compile-helper-session',parameters,version=1)
        assert list(f['inputs'].iterdir())==[] and not f['key'].exists()
    finally:f['store'].close()


def test_session_projection_excludes_private_sentinels_even_if_context_approval_is_wrong(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch,projection=True)
    try:
        compiled=dispatch(f,'compile-helper-session',{'schema':'ai4r-rsi-helper-session-request:1',**f['values']})
        f['config']['worker']['profile_refs']=[compiled['worker_profile_ref']]
        # Deliberately overbroad publication approval cannot disclose a known
        # hidden original through protected_refs or a differently named alias.
        f['config']['public_original_refs']=[f['hidden']]
        parameters={'session_ref':compiled['session_ref'],'worker_profile_ref':compiled['worker_profile_ref'],
            'parent_body_refs':parent_bodies(f['store'],f['target']),'visible_context_ref':None,'job_ref':None}
        result=dispatch(f,'prepare-session-materials',parameters)
        bundle=f['store'].get(result['materials_ref']);refs=[row['ref'] for row in bundle['materials']]
        assert f['hidden'] not in refs and f['preparation'] not in refs
        raw=b'\n'.join(base64.b64decode(row['bytes_base64'],validate=True) for row in bundle['materials'])
        for sentinel in ('CALIBRATION','REVIEW','HIDDEN','PREPARATION'):
            assert ('NEVER_EXPORT_'+sentinel+'_SENTINEL').encode() not in raw
        assert all(compiled[key] in refs for key in ('session_ref','worker_profile_ref','genesis_ref','final_budget_ref'))
        assert f['target']['improver_ref'] in result['required_original_refs']
        assert result['private_runtime_refs']==[]
        assert result['status']=='MATERIALS_PREPARED_PRIVATE' and not f['key'].exists()
    finally:f['store'].close()


def test_alleged_visible_hidden_input_is_rejected_before_its_body_is_read(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch,projection=True)
    try:
        compiled=compiler.compile_helper_session(f['store'],**f['values'])
        hidden=f['manifest']['partitions']['hidden_final'][0]['input_ref']
        visible=f['store'].put({'context':{},'required_test_refs':f['target']['required_test_refs'],
            'mandatory_fixtures':[{'input_ref':hidden,'test_ref':f['target']['required_test_refs'][0]}]})
        original=f['store'].read
        def guarded(pin):
            if pin==hidden:pytest.fail('Projection opened a hidden input body')
            return original(pin)
        monkeypatch.setattr(f['store'],'read',guarded)
        with pytest.raises(ValueError):compiler.session_public_materials(f['store'],session_ref=compiled['session_ref'],
            worker_profile_ref=compiled['worker_profile_ref'],parent_body_refs=parent_bodies(f['store'],f['target']),
            visible_context_ref=visible)
    finally:f['store'].close()


def test_v2_job_facade_uses_only_config_approval_and_preserves_private_preparation_pointer(tmp_path,monkeypatch):
    from tests.unit_tests.research_rsi.test_session_preparation import contract
    from jiuwenswarm.research_rsi import opportunity
    f=fixture(tmp_path,monkeypatch,projection=True)
    try:
        compiled=dispatch(f,'compile-helper-session',{'schema':'ai4r-rsi-helper-session-request:1',**f['values']})
        f['config']['worker']['profile_refs']=[compiled['worker_profile_ref']]
        f['config']['approved_preparation_refs']=[f['preparation']]
        def prepared(*args,**kwargs):
            assert kwargs['approved_preparation_refs']==f['config']['approved_preparation_refs']
            return {'preparation':{'worker_profile_ref':compiled['worker_profile_ref']}}
        monkeypatch.setattr(opportunity,'validated_preparation',prepared)
        visible=f['store'].put({'context':{'public':'visible only'},'required_test_refs':f['target']['required_test_refs'],
            'mandatory_fixtures':[{'input_ref':f['manifest']['partitions']['development'][0]['input_ref'],
                'test_ref':f['target']['required_test_refs'][0]}]})
        calls=[contract(f['store'],f['values']['hash_profile_ref'],f['target']['configuration_ref'],i) for i in range(3)]
        job={'schema':'ai4r-rsi-session-job:2','session_ref':compiled['session_ref'],'preparation_ref':f['preparation'],
            'diagnosis_contract_ref':calls[0],'visible_context_ref':visible,'proposer_contract_refs':calls[1:],
            'worker_profile_ref':compiled['worker_profile_ref'],'fixture_identity':f['manifest']['fixture_identity'],'target_kind':'ranking-v1'}
        result=dispatch(f,'assemble-job2',job)
        assert result['status']=='JOB_COMPILED_NOT_STARTED'
        assert f['store'].get(result['job_ref'])==job
        with pytest.raises(ValueError):dispatch(f,'assemble-job2',dict(job,approved_preparation_refs=[f['preparation']]))
        f['config']['public_original_refs']=calls
        projection=dispatch(f,'prepare-session-materials',{'session_ref':compiled['session_ref'],
            'worker_profile_ref':compiled['worker_profile_ref'],'parent_body_refs':parent_bodies(f['store'],f['target']),
            'visible_context_ref':visible,'job_ref':result['job_ref']})
        bundle=f['store'].get(projection['materials_ref']);refs=[row['ref'] for row in bundle['materials']]
        assert result['job_ref'] in refs and visible in refs and all(pin in refs for pin in calls)
        assert f['preparation'] not in refs and projection['private_runtime_refs']==[f['preparation']]
        raw=b''.join(base64.b64decode(row['bytes_base64']) for row in bundle['materials'])
        assert b'NEVER_EXPORT_PREPARATION_SENTINEL' not in raw
        assert list(f['inputs'].iterdir())==[] and not f['key'].exists()
    finally:f['store'].close()


def test_opt_in_preparation_config_mount_is_custodian_only():
    import yaml
    root=Path(__file__).resolve().parents[3]
    services=yaml.safe_load((root/'deploy/m1/compose.rsi.preparation.yaml').read_text())['services']
    assert set(services)=={'rsi-custodian'}
    mount=services['rsi-custodian']['volumes'][0]
    assert mount['target']=='/run/ai4r-rsi/preparation-service.json'
    assert mount['read_only'] is True and mount['bind']['create_host_path'] is False


def test_generic_helper_facade_uses_finite_normalization_adapter_without_approval(tmp_path,monkeypatch):
    from jiuwenswarm.research_rsi.targets import ranking_preparation
    from jiuwenswarm.research_rsi.targets.unrelated_helper import NORMALIZE_LABELS_PARENT
    f=fixture(tmp_path,monkeypatch)
    try:
        if sys.platform!='linux' or not hasattr(os,'geteuid') or os.geteuid()!=12002:
            monkeypatch.setattr(ranking_preparation,'require_custodian_store',lambda value:value)
        body=f['store'].put_bytes(NORMALIZE_LABELS_PARENT)
        declaration=f['store'].get(f['target']['parent_declaration_ref'])
        declaration['identity']['body']=[{'path':'labels.py','sha256':body['sha256']}]
        declaration['evolution']['may_change']=['files:labels.py']
        declaration_ref=f['store'].put(declaration)
        generator=f['store'].put_bytes(Path(ranking_preparation.__file__).read_bytes())
        parameters={'target_kind':'normalize-labels-v1','parent_ref':body,'parent_declaration_ref':declaration_ref,
            'author':'unit:fixture-author','origin_ref':f['values']['hash_profile_ref'],'generator_ref':generator,
            'prior_preparation_refs':[],'populations':{'development':12,'hidden_loop':20,'hidden_final':20,'platform':12},
            'max_rows':7,'seed':'private-normalization-unit-seed'}
        result=dispatch(f,'prepare-helper',parameters)
        assert result['status']=='PREPARED_REVIEW_REQUIRED'
        preparation=f['store'].get(result['preparation_ref'])
        assert preparation['schema']=='ai4r-rsi-helper-preparation:2' and preparation['max_rows']==7
        assert preparation['status']=='PENDING_REVIEW_AND_CALIBRATION'
        assert f['config']['approved_preparation_refs']==[]
        with pytest.raises(ValueError):dispatch(f,'prepare-helper',dict(parameters,max_rows=3))
    finally:f['store'].close()
