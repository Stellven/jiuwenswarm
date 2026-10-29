"""Core fault mechanics using explicit controlled assets/transport, not QA PASS."""
import json
from pathlib import Path
import pytest
from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.compiler import input_port
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.intake import qualify_intake
from jiuwenswarm.research.runner import CapsuleRunner
from tests.unit_tests.research.test_budget_ceiling import installed_library


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['foreign_output','run_id','node_id','subnode_id','attempt_id','contract_ref','node_contract_ref','binding_id','cc_name','cc_version','declaration_sha256','body_files_sha256','input_refs'])
async def test_real_foreign_ref_swap_keeps_original_observation_and_fails_tier1_without_review(tmp_path,monkeypatch,fault):
    store,registry,checks,library,installed,_=await installed_library(tmp_path)
    opaque=store.put_blob(b'controlled approved binding')
    actor=Principal('alice',frozenset({'project'}),frozenset({'ingest'}))
    request=Path('tests/fixtures/research/compiler/request.txt').read_text('utf-8')
    intake_ref=qualify_intake(store,actor,request,[],workspace_id='project',profile_ref=opaque,workspace_ref=opaque,input_directory_ref=opaque)
    intake=store.read_record(intake_ref)
    store.create_run('run:fault',account_id='alice',workspace_id='project',submission={})
    foreign=store.put_blob(b'{"foreign":"valid immutable bytes from another captured invocation"}')
    store.append_record('captured-output',{'id':'capture:foreign','run_id':'run:other','invocation_id':'invocation:other','output_port':'intent','artifact_ref':foreign})
    class Fault:
        async def after_capture(self,context):return {'output_refs':{'intent':foreign} if fault=='foreign_output' else context['output_refs']}
    original_observation=CapsuleRunner._observation
    def stale_observation(self,*args,**kwargs):
        value=original_observation(self,*args,**kwargs)
        if fault not in {'foreign_output'}:
            value[fault]=[foreign] if fault=='input_refs' else foreign if fault in {'contract_ref','node_contract_ref'} else '0'*64 if fault in {'declaration_sha256','body_files_sha256'} else 'foreign.cc' if fault=='cc_name' else 'foreign'
        return value
    monkeypatch.setattr(CapsuleRunner,'_observation',stale_observation)
    calls=[]
    class Transport:
        async def call(self,context,prompt):
            protected=runner.authorize_model_context(context);calls.append(protected['call_function'])
            store.append_record('model-call-start',dict(protected,id=protected['call_id']+':start'))
            value=json.loads(Path('tests/fixtures/research/compiler/intent_ir.json').read_bytes())
            def rewrite(v):
                if isinstance(v,dict):return intake['request_ref'] if set(v)=={'id','sha256'} else {k:rewrite(x) for k,x in v.items()}
                if isinstance(v,list):return [rewrite(x) for x in v]
                return v
            return {'text':json.dumps(rewrite(value)),'observed_runtime':True}
    runner=CapsuleRunner(store,registry,checks,model=Transport(),check_assets=library.check_assets,faults=Fault())
    final=store.put_record('node-finalization-profile',{'schema_version':'2.0.0','id':'final','mandatory_deterministic':['internal_acceptance','external_output','aggregate_limits'],'semantic_assessment_reuse':'accepted_requirements','additional_model_calls':0})
    factory=ContractFactory(store,library,verifier_pin=installed['verifier']['pin'],finalization_profile_ref=final)
    inputs=[input_port('request','qualified-intake:field-contract:2',intake_ref)]
    parent=factory.prepare_parent('run:fault','intent',[{'subnode_id':'intent','cc':installed['intent']['pin'],'depends_on':[]}],inputs=inputs,
        outputs=[{'name':'intent','contract_id':'intent-ir','version':'1.0.0','required':True}],objective='Controlled swap negative',requirement_ids=['intent'],
        limits={'time_s':120,'model_calls':2,'memory_mb':256},policy_ref=opaque,configuration_ref=opaque,template_ref=opaque,
        authority_ceiling={'network':'none','network_allowlist':[],'resource_reads':[intake_ref,intake['request_ref']],'write_roots':[],'tools':[]})
    contract,checkplan,bundle=factory.bind_subnode(parent,'intent',inputs)
    selection=store.put_record('model-selection-profile',{'schema_version':'1.0.0','id':'fixed','policy_mode':'fixed_baseline','approved_model_ids':['codex-cli-default'],'extra_requirements':{},'selection_allowance':{'enabled':False,'deployment_ref':None,'model_calls':0,'time_s':0,'output_tokens':0,'disclosure_scope':[]},'alternate_model_id':None,'policy_ref':opaque})
    runner.configure_run('run:fault',model_selection_profile_ref=selection,deployment_ref=opaque,router={'enabled':False,'deadline_s':30,'profile_ref':None},configuration_ref=opaque,run_limits={'time_s':120,'model_calls':2,'memory_mb':256})
    result=await runner.run(contract,checkplan,bundle_id=bundle)
    assert not result.accepted and calls==['worker'] and result.assessment_refs==()
    observed=store.read_record(result.observation_ref)
    assert foreign not in observed['output_refs']
    if fault=='foreign_output':assert result.output_refs=={'intent':foreign}
    assert any(row['check_id']=='host_identity' and row['outcome']=='FAIL' for row in store.read_record(result.deterministic_ref)['results'])
    assert not store.accepted_outputs('run:fault','intent')


def test_evaluation_material_cannot_reenter_product_intake_or_admission(tmp_path):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.contracts import ResearchError
    from tests.unit_tests.research.controlled_assets import ControlledLibraryService
    store=SQLiteRunStore(tmp_path);store.create_run('eval-run',account_id='alice',workspace_id='project',submission={})
    store.append_record('evaluation-run-binding',{'id':'evaluation:binding','run_id':'eval-run','invalid_for_product':True})
    ref=store.put_blob(b'evaluation only output');store.mark_evaluation_material('eval-run',ref)
    with pytest.raises(ResearchError,match='evaluation_only'):store.require_product_material([ref])
    actor=Principal('alice',frozenset({'project'}),frozenset({'ingest'}))
    with pytest.raises(ResearchError,match='evaluation_only'):
        qualify_intake(store,actor,'evaluation only output',[],workspace_id='project',profile_ref=ref,workspace_ref=ref,input_directory_ref=ref)


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel',[False,True])
async def test_node_advance_is_not_durable_until_awaited_hold_returns(tmp_path,monkeypatch,cancel):
    import asyncio
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.contracts import ResearchError
    from tests.unit_tests.research.test_compiler import test_compiler_requires_internal_acceptance_and_commits_one_external_brief
    entered=asyncio.Event();release=asyncio.Event();original=CapsuleRunner.__init__
    class Hold:
        async def after_capture(self,context):return {'output_refs':context['output_refs']}
        async def before_advance(self,context):
            assert set(context)=={'run_id','node_id','contract_ref','decision_id','deadline_monotonic_s'}
            assert context['node_id']=='intention_compiler'
            entered.set();await release.wait()
    def init(self,*args,**kwargs):original(self,*args,**kwargs);self.faults=Hold()
    monkeypatch.setattr(CapsuleRunner,'__init__',init)
    task=asyncio.create_task(test_compiler_requires_internal_acceptance_and_commits_one_external_brief(tmp_path,None,'fixed_baseline'))
    await asyncio.wait_for(entered.wait(),30)
    store=SQLiteRunStore(tmp_path,recover=False)
    assert store.accepted_outputs('run:compiler','intention_compiler')=={}
    assert not [r for r in store.iter_records(kinds=('gate-decision',)) if r['record']['scope_kind']=='node']
    assert list(store.iter_records(kinds=('gate-decision',)))
    if cancel:store.request_cancellation('run:compiler','alice','cancel-during-hold')
    release.set()
    if cancel:
        with pytest.raises(ResearchError,match='cancelled'):await task
        await asyncio.sleep(0)
        assert store.accepted_outputs('run:compiler','intention_compiler')=={}
        assert not [r for r in store.iter_records(kinds=('gate-decision',)) if r['record']['scope_kind']=='node']
    else:
        await task
        assert store.accepted_outputs('run:compiler','intention_compiler')


def test_public_evaluation_measurement_origins_reject_failed_partial_material(tmp_path):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.contracts import ResearchError
    store=SQLiteRunStore(tmp_path);contract=store.put_blob(b'actual isolated evaluation contract')
    store.append_record('evaluation-context-origin',{'id':'evaluation:context','contract_ref':contract,'invalid_for_product':True})
    partial=store.put_blob(b'actual partial failed evaluation output')
    store.append_record('measurement-captured-output',{'id':'measurement:partial','contract_ref':contract,'artifact_ref':partial})
    with pytest.raises(ResearchError,match='evaluation_only'):store.require_product_material([partial])
    baseline=store.put_blob(b'legitimate separately owned RSI baseline output')
    store.require_product_material([baseline])
