"""Literal calibration adapter controls; labels are explicit unit fixtures."""
import json
from pathlib import Path
import pytest
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_check_asset_admission import prepared,fixed_unit_profile


@pytest.mark.asyncio
async def test_literal_adapter_runs_actual_registered_predicate_but_missing_model_never_qualifies(tmp_path):
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.checks.calibration import CalibrationMeasurements
    store,library,actor,asset=prepared(tmp_path);profile,_=fixed_unit_profile(store,asset)
    implementation=store.put_blob(Path(__import__('inspect').getfile(CalibrationMeasurements)).read_bytes())
    profile['measurement_runner_ref']=implementation
    bundle=store.read_record(asset['bundle_ref']);registry=CheckRegistry();called=[]
    def actual_predicate(ctx,inputs,outputs):
        called.append(dict(outputs));observed=outputs['screening_result']
        return [{'check_id':row['check_id'],'outcome':'PASS' if isinstance(observed,dict) and 'scores' in observed else 'FAIL',
            'reason':'Explicit unit predicate evaluated actual captured subject bytes; no scientific-check qualification claim',
            'evidence_refs':[ctx.output_refs['screening_result']]} for row in bundle['checks']]
    registry.register_bundle(bundle['bundle_id'],[c['check_id'] for c in bundle['checks']],actual_predicate,
        implementation_ref=bundle['checks'][0]['runner_ref'],profile_ref=asset['profile_ref'])
    producer=CalibrationMeasurements(library.check_assets,registry)
    profile_ref=store.put_blob(json_bytes(profile));producer.install(profile_ref,actor)
    producer._context(profile['cases'][0],library.check_assets.closure(asset['bundle_ref'],asset['profile_ref']),profile_ref)
    refs=await library.check_assets.measure(profile_ref,actor)
    assert len(called)==5 and len(refs)==10
    reports=[store.read_record(ref) for ref in refs]
    assert all(r['status']=='matched' for r in reports if r['asset_kind']=='bundle')
    assert all(r['status']=='blocked' and r['reason_code']=='calibration_model_unavailable' for r in reports if r['asset_kind']=='criteria')
    admissions=library.check_assets.admit(profile_ref,actor)
    assert store.read_record(admissions['bundle'])['status']=='admitted'
    assert store.read_record(admissions['criteria'])['status']=='blocked'
    with pytest.raises(ResearchError,match='check_asset_unqualified'):library.eligible_association(asset['declaration_ref'])
    assert not list(store.iter_records(kinds=('model-call','activation-record','library-admission')))


def test_literal_adapter_rejects_a_different_installed_body_before_registration(tmp_path):
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.checks.calibration import CalibrationMeasurements
    store,library,actor,asset=prepared(tmp_path);profile,_=fixed_unit_profile(store,asset)
    ref=store.put_blob(json_bytes(profile))
    with pytest.raises(ResearchError,match='calibration_runner'):CalibrationMeasurements(library.check_assets,CheckRegistry()).install(ref,actor)
    assert not list(store.iter_records(kinds=('calibration-profile-registration',)))


@pytest.mark.asyncio
@pytest.mark.parametrize('zip_subject',[False,True])
async def test_semantic_calibration_uses_actual_bridge_claim_payload_and_independent_recomputation(tmp_path,zip_subject):
    import inspect
    import time
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.checks.calibration import CalibrationMeasurements
    from jiuwenswarm.research.contracts import validate
    from tests.unit_tests.research.test_bridge import authorized_context
    store,library,actor,asset=prepared(tmp_path);profile,_=fixed_unit_profile(store,asset)
    if zip_subject:
        import io,zipfile
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as output:output.writestr('run_benchmark.py','print("unit projection")\n')
        original=store.put_blob(archive.getvalue(),media_type='application/zip')
        declaration=store.read_record(asset['declaration_ref'])
        for output in declaration['ports']['outputs']:output['schema_ref']='poc-artifact-bundle'
        declaration_ref=store.put_blob(json_bytes(declaration))
        for case in profile['cases']:case.update(subject_ref=original,declaration_ref=declaration_ref)
    profile['measurement_runner_ref']=store.put_blob(Path(inspect.getfile(CalibrationMeasurements)).read_bytes())
    checking=store.read_record(asset['profile_ref']);bundle=store.read_record(asset['bundle_ref']);registry=CheckRegistry()
    for case in profile['cases']:
        if case['asset_kind']=='criteria':case['expected_ref']=store.put_blob(json_bytes({c['criterion_id']:'FAIL' for c in checking['criteria'] if c['target_port'] in (None,case['output_port'])}))
    other=dict(next(c for c in profile['cases'] if c['asset_kind']=='criteria'),case_id='criteria:other-port',output_port='opportunity_card')
    other['expected_ref']=store.put_blob(json_bytes({c['criterion_id']:'FAIL' for c in checking['criteria'] if c['target_port'] in (None,'opportunity_card')}))
    profile['cases'].append(other);profile_ref=store.put_blob(json_bytes(profile))
    def measured(ctx,inputs,outputs):return [{'check_id':c['check_id'],'outcome':'FAIL','reason':'Explicit unit absence predicate on captured fixture output','evidence_refs':list(ctx.output_refs.values())} for c in bundle['checks']]
    registry.register_bundle(bundle['bundle_id'],[c['check_id'] for c in bundle['checks']],measured,implementation_ref=bundle['checks'][0]['runner_ref'],profile_ref=asset['profile_ref'])
    store.create_run('calibration-unit',account_id='independent-test-owner',workspace_id='unit',submission={})
    class ControlledProvider:
        async def invoke_governed(self,prompt,**kwargs):
            payload=json.loads(prompt.split('<subject_payload>\n')[1].split('\n</subject_payload>')[0])
            assert set(payload)=={'subject_declaration','subject_output'} and 'expected_ref' not in payload
            if zip_subject:
                assert payload['subject_output'].startswith('path: run_benchmark.py\nsha256: ')
                assert 'print("unit projection")' in payload['subject_output']
            criteria=json.loads(prompt.split('Criteria for this output:\n')[1].split('\n\n<subject_payload>')[0])
            return {'text':json.dumps({'findings':[{'criterion_id':c['criterion_id'],'outcome':'FAIL','reason':'Controlled unit challenge reply, no model quality claim'} for c in criteria],
                'uncertainties':[],'limitations':[],'required_correction':'Controlled fixture is incomplete'}),'observed_runtime':True,'usage':{},'identity':{'effective':None,'basis':'Controlled unit provider'}}
    class BoundPort:
        def __init__(self,case):self.case=case;self.protected=None
        async def invoke(self,prompt,*,system):
            source=next(r for r in store.iter_records(kinds=('calibration-subject',)) if r['record']['id'].endswith(':'+self.case['case_id']))
            context=authorized_context();context.update(run_id='calibration-unit',node_id='calibration',subnode_id='reviewer',call_function='verifier',
                invocation_id='invocation:'+self.case['case_id'],execution_id='execution:'+self.case['case_id'],contract_ref=source['ref'],
                model_selection_profile_ref=asset['profile_ref'],deployment_ref=asset['profile_ref'],execution_deadline_monotonic_s=time.monotonic()+30)
            context['limits']['time_s']=30
            def authorize(_):
                call,claim=store.claim_model_call(context,invocation_limit=1,node_limit=20,run_limit=20)
                self.protected=dict(context,call_id=call,call_claim_ref=claim);return self.protected
            bridge=GovernedBridge(persist=store.append_record,authorize=authorize,revalidate=lambda _:self.protected,
                subscription_service=ControlledProvider(),validate_record=validate)
            return await bridge.call({},system+'\n\n<subject_payload>\n'+prompt+'\n</subject_payload>')
        async def contain(self):return {'contained':True}
    models={(profile_ref['sha256'],case['case_id']):BoundPort(case) for case in profile['cases'] if case['asset_kind']=='criteria'}
    producer=CalibrationMeasurements(library.check_assets,registry,model_ports=models);producer.install(profile_ref,actor)
    receipts=await library.check_assets.measure(profile_ref,actor)
    assert all(store.read_record(ref)['status']=='matched' for ref in receipts),[store.read_record(ref) for ref in receipts]
    assert len(list(store.iter_records(kinds=('model-call',))))==6
    admissions=library.check_assets.admit(profile_ref,actor)
    assert all(store.read_record(ref)['status']=='admitted' for ref in admissions.values())
    assert not library.entries() and not list(store.iter_records(kinds=('activation-record','gate-decision')))
