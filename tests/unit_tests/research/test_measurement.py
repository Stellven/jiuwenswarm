"""Independent controls for actual, unaccepted trial measurements."""
import asyncio
import json
from pathlib import Path
import time

import pytest

from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.gate import SemanticVerifier
from jiuwenswarm.research.runner import ProducedArtifact
from jiuwenswarm.research.state import SQLiteRunStore


class WorkerCapability:
    __slots__=()


class ControlledMeasurementContext:
    """Controlled authorizer double; no live model/confinement qualification."""
    def __init__(self,store,*,check_pass=True,timeout=5):
        self.store=store;self.worker_context=WorkerCapability();self.deadline_monotonic_s=time.monotonic()+timeout
        self.contract={'id':'trial:controlled','inputs':[],'outputs':[{'name':'result','contract_id':'Ref','required':True}]}
        self.contract_ref=store.append_record('isolated-evaluation-trial',self.contract)
        self.profile_ref=store.put_blob(b'controlled independent checking profile')
        runner=store.put_blob(b'controlled installed check implementation')
        self.check_registry=CheckRegistry();self.check_pass=check_pass;self.contained=[];self.observed=[]
        def check(ctx,inputs,outputs):
            assert ctx.outputs is outputs and ctx.observation['contract_ref']==self.contract_ref
            return [{'check_id':'body','outcome':'PASS' if self.check_pass else 'FAIL','reason':'Independently compare captured output',
                     'evidence_refs':list(ctx.output_refs.values())}]
        self.check_registry.register_bundle('controlled',['body'],check,implementation_ref=runner,profile_ref=self.profile_ref)
        self.plan_ref=store.append_record('isolated-evaluation-check-plan',{'id':'checks:controlled',
            'contract_ref':self.contract_ref,'profile_ref':self.profile_ref,'runner_refs':[runner],
            'mandatory_deterministic':['body','host'],'mandatory_semantic':[]})
    def require_checks(self):return None
    def capture_observation(self,*,output_refs,started_at,elapsed_s,outcome,failure):
        record={'contract_ref':self.contract_ref,'output_refs':list(output_refs.values()),'started_at':started_at,
                'wall_time_s':elapsed_s,'exit_status':outcome,'failure_reason_code':failure}
        self.observed.append(record)
        return self.store.append_record('isolated-invocation-observation',record)
    def host_results(self,*,observation_ref,output_refs,outputs):
        observed=self.store.read_record(observation_ref)
        return [{'check_id':'host','outcome':'PASS' if observed['output_refs']==list(output_refs.values()) else 'FAIL',
                 'reason':'Compare actual owner capture with selected refs','evidence_refs':[observation_ref]}]
    async def contain(self,reason):self.contained.append(reason)


@pytest.fixture
def context(tmp_path):
    store=SQLiteRunStore(tmp_path)
    try:yield ControlledMeasurementContext(store)
    finally:store.close()


async def good_worker(ctx,inputs):
    assert type(ctx) is WorkerCapability and not hasattr(ctx,'store')
    return {'result':ProducedArtifact({'id':'actual-value','sha256':'1'*64},contract_id='Ref')}


@pytest.mark.asyncio
async def test_actual_worker_bytes_and_checks_confer_no_acceptance(context):
    from jiuwenswarm.research.measurement import measure_trial
    result=await measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert result.accepted is False and result.status=='completed' and result.failure is None
    assert context.store.read_record(result.output_refs['result'])=={'id':'actual-value','sha256':'1'*64}
    checks=context.store.read_record(result.deterministic_ref)
    assert {r['check_id']:r['outcome'] for r in checks['results']}=={'body':'PASS','host':'PASS'}
    assert context.store.read_record(result.measurement_ref)['accepted'] is False
    assert context.observed[0]['wall_time_s']>=0
    assert not list(context.store.iter_records(kinds=('gate-decision','acceptance-commit','library-admission','activation-record')))


@pytest.mark.asyncio
@pytest.mark.parametrize('contract_id,raw',[
    ('poc-artifact-bundle:field-contract:1',b'PK\x03\x04frozen binary archive bytes'),
    ('research-report:field-contract:1',b'# Frozen report\nExact original markdown.\n'),
])
async def test_replay_media_comes_from_the_declared_output_not_first_blob_metadata(context,contract_id,raw):
    from jiuwenswarm.research.measurement import measure_trial
    context.contract['outputs'][0]['contract_id']=contract_id
    ref=context.store.put_blob(raw)  # Deliberately captured first as generic bytes.
    assert context.store.artifact_metadata(ref)['media_type']=='application/octet-stream'
    context.replay_output_refs={'result':ref}
    measured=await measure_trial(context,None,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert measured.status=='completed' and measured.failure is None
    assert measured.output_refs=={'result':ref} and context.store.read_blob(ref)==raw


@pytest.mark.asyncio
@pytest.mark.parametrize('produced',[
    {},{'extra':ProducedArtifact({'id':'extra','sha256':'1'*64})},
    {'result':ProducedArtifact({'id':'missing-sha'})},
    {'result':ProducedArtifact({'id':'x','sha256':'1'*64},contract_id='other')},
    {'result':{'id':'uncaptured','sha256':'1'*64}},
])
async def test_invalid_output_never_becomes_success_or_triggers_review(context,produced):
    from jiuwenswarm.research.measurement import measure_trial
    async def worker(ctx,inputs):return produced
    async def forbidden(*args):pytest.fail('Invalid output cannot invoke reviewer')
    result=await measure_trial(context,worker,{},context.contract['outputs'],context.plan_ref,'controlled',forbidden)
    assert result.status=='failed' and result.accepted is False and result.failure
    assert all(row['outcome']!='PASS' for row in context.store.read_record(result.deterministic_ref)['results'])
    assert not result.assessment_refs


@pytest.mark.asyncio
async def test_mandatory_check_failure_suppresses_every_review(context):
    from jiuwenswarm.research.measurement import measure_trial
    context.check_pass=False
    async def forbidden(*args):pytest.fail('Tier1 failure must suppress all reviews')
    result=await measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled',forbidden)
    assert result.status=='failed' and result.assessment_refs==()
    assert any(row['outcome']=='FAIL' for row in context.store.read_record(result.deterministic_ref)['results'])


@pytest.mark.asyncio
async def test_missing_qualified_checks_blocks_before_worker(context):
    from jiuwenswarm.research.measurement import measure_trial
    def deny():raise ResearchError('check_assets_unqualified')
    context.require_checks=deny
    async def forbidden(*args):pytest.fail('No worker dispatch without independently qualified checks')
    with pytest.raises(ResearchError,match='check_assets_unqualified'):
        await measure_trial(context,forbidden,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert not context.observed


@pytest.mark.asyncio
async def test_timeout_contains_owner_and_retains_actual_failure(context):
    from jiuwenswarm.research.measurement import measure_trial
    context.deadline_monotonic_s=time.monotonic()+1
    entered=asyncio.Event()
    async def slow(ctx,inputs):
        entered.set()
        await asyncio.sleep(30)
    result=await measure_trial(context,slow,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert entered.is_set()
    assert result.status=='blocked' and result.failure=='budget_exhausted' and context.contained==['budget_exhausted']
    assert context.observed[0]['exit_status']=='budget_exhausted'


@pytest.mark.asyncio
async def test_cancel_waits_for_owner_and_preserves_interrupted_capture(context):
    from jiuwenswarm.research.measurement import measure_trial
    entered=asyncio.Event()
    async def slow(ctx,inputs):
        entered.set()
        await asyncio.sleep(30)
    task=asyncio.create_task(measure_trial(context,slow,{},context.contract['outputs'],context.plan_ref,'controlled'))
    await asyncio.wait_for(entered.wait(),5);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert context.contained==['cancelled'] and context.observed[0]['exit_status']=='interrupted'
    rows=list(context.store.iter_records(kinds=('trial-measurement',)))
    assert len(rows)==1 and rows[0]['record']['accepted'] is False and rows[0]['record']['status']=='interrupted'


@pytest.mark.asyncio
async def test_private_trial_is_not_fabricated_as_canonical_subnode(context):
    from jiuwenswarm.research.measurement import measure_trial
    result=await measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert context.store.record_kind(context.contract_ref)=='isolated-evaluation-trial'
    assert context.store.read_record(result.measurement_ref)['contract_ref']==context.contract_ref
    assert not list(context.store.iter_records(kinds=('subnode-execution-contract','library-admission','accepted-output')))


def independent_review(context):
    store=context.store
    profile=json.loads(Path('tests/fixtures/research/router/protected-capture/intent_checking_profile.json').read_bytes())
    profile['instruction_ref']=store.put_blob(b'Independently assess the declaration and output only.')
    profile_ref=store.put_record('checking-profile',profile)
    declaration=store.put_blob(b'{"identity":{"name":"controlled.cc","version_label":"1"}}')
    context.contract=dict(context.contract,id='trial:review',declaration_ref=declaration)
    context.contract_ref=store.append_record('isolated-evaluation-trial',context.contract)
    old=context.check_registry._bundles['controlled']
    registry=CheckRegistry();registry.register_bundle('controlled',['body'],old['handler'],
        implementation_ref=old['implementation_ref'],profile_ref=profile_ref)
    context.check_registry=registry
    plan=store.read_record(context.plan_ref);plan.update(id='checks:review',contract_ref=context.contract_ref,
        profile_ref=profile_ref,mandatory_semantic=[c['criterion_id'] for c in profile['criteria'] if c['target_port'] in (None,'result')])
    context.plan_ref=store.append_record('isolated-evaluation-check-plan',plan)
    calls=[]
    async def review(port,output_ref,deterministic_ref,observation_ref):
        manifest=store.put_record('review-context',{'schema_version':'2.0.0','id':'review:controlled',
            'subject_ref':output_ref,'contract_ref':context.contract_ref,'check_plan_ref':context.plan_ref,
            'input_refs':[],'deterministic_result_ref':deterministic_ref,'criteria':plan['mandatory_semantic'],
            'observations':[observation_ref],'evidence_classes':['captured_input_and_output','invocation_observation'],
            'node_contract_ref':context.contract_ref,'subnode_id':'controlled'})
        async def invoke(payload,*,system):
            decoded=json.loads(payload);calls.append(decoded)
            assert set(decoded)=={'subject_declaration','subject_output'}
            assert 'NEVER_SEND_TO_SEMANTIC_REVIEW' not in payload+system
            return json.dumps({'findings':[{'criterion_id':criterion,'outcome':'PASS',
                'reason':'The captured declared Ref has exactly id and sha256.'} for criterion in plan['mandatory_semantic']],
                'uncertainties':[],'limitations':[],'required_correction':None})
        assessment=await SemanticVerifier(store).review(declaration,output_ref,profile_ref,manifest,port,invoke)
        reviewer=store.append_record('isolated-review-trial',{'id':'reviewer:controlled'})
        checked_plan=store.append_record('isolated-evaluation-check-plan',{'id':'reviewer-checks:controlled',
            'contract_ref':reviewer,'mandatory_deterministic':['assessment-schema']})
        checked=store.put_record('deterministic-check-result',{'schema_version':'1.0.0','subject_ref':assessment,
            'check_plan_ref':checked_plan,'results':[{'check_id':'assessment-schema','outcome':'PASS',
            'reason':'The actual SemanticVerifier stored a schema-validated assessment.','evidence_refs':[assessment]}]})
        observed=store.append_record('isolated-invocation-observation',{'contract_ref':reviewer,'output_refs':[assessment]})
        return {'assessment_ref':assessment,'verifier_check_ref':checked,'observation_refs':[observed],'trace_refs':[]}
    return review,calls


@pytest.mark.asyncio
async def test_actual_semantic_path_receives_only_declaration_and_output(context):
    from jiuwenswarm.research.measurement import measure_trial
    context.contract['host_only']='NEVER_SEND_TO_SEMANTIC_REVIEW'
    review,calls=independent_review(context)
    result=await measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled',review)
    assert result.status=='completed' and len(calls)==1 and len(result.assessment_refs)==1
    assert context.store.read_record(result.assessment_refs[0])['verdict']=='PASS'
    assert result.accepted is False and not list(context.store.iter_records(kinds=('gate-decision','acceptance-commit')))


@pytest.mark.asyncio
async def test_reviewer_boolean_or_missing_measurement_cannot_replace_evidence(context):
    from jiuwenswarm.research.measurement import measure_trial
    async def fake(*args):return {'accepted':True}
    result=await measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled',fake)
    assert result.status=='failed' and not result.assessment_refs and result.accepted is False


@pytest.mark.asyncio
async def test_cancel_during_review_contains_the_actual_owner(context):
    from jiuwenswarm.research.measurement import measure_trial
    active=asyncio.Event()
    async def pending(*args):active.set();await asyncio.sleep(30)
    task=asyncio.create_task(measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled',pending))
    await active.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert context.contained==['cancelled']
    result=list(context.store.iter_records(kinds=('trial-measurement',)))[0]['record']
    assert result['status']=='interrupted' and result['failure']=='cancelled' and result['accepted'] is False


@pytest.mark.asyncio
async def test_malformed_partial_bytes_remain_in_the_failure_observation(context):
    from jiuwenswarm.research.measurement import measure_trial
    async def malformed(*args):return {'result':ProducedArtifact(b'not-json')}
    result=await measure_trial(context,malformed,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert result.status=='failed' and context.store.read_blob(result.output_refs['result'])==b'not-json'
    assert context.store.read_record(result.observation_ref)['output_refs']==[result.output_refs['result']]


@pytest.mark.asyncio
async def test_owner_observation_failure_cannot_be_reported_completed(context):
    from jiuwenswarm.research.measurement import measure_trial
    def fail(**kwargs):raise OSError('controlled owner audit failure')
    context.capture_observation=fail
    with pytest.raises(ResearchError) as observed:
        await measure_trial(context,good_worker,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert observed.value.code=='audit_unavailable'
    failures=list(context.store.iter_records(kinds=('measurement-audit-failure',)))
    assert len(failures)==1 and failures[0]['record']['accepted'] is False
    assert not list(context.store.iter_records(kinds=('trial-measurement','acceptance-commit')))


@pytest.mark.asyncio
@pytest.mark.parametrize('produced_contract,accepted',[
    ('intent-ir',True),('qualified-intake',False),('unknown-client-schema',False),
])
async def test_only_exact_frozen_schema_aliases_are_accepted(context,produced_contract,accepted):
    from jiuwenswarm.research.measurement import measure_trial
    context.contract=dict(context.contract,id='trial:alias',outputs=[{'name':'result',
        'contract_id':'urn:jiuwenswarm:m1-design:intent-ir:1.0.0','required':True}])
    context.contract_ref=context.store.append_record('isolated-evaluation-trial',context.contract)
    plan=context.store.read_record(context.plan_ref);plan.update(id='checks:alias',contract_ref=context.contract_ref)
    context.plan_ref=context.store.append_record('isolated-evaluation-check-plan',plan)
    output=json.loads(Path('tests/fixtures/research/compiler/intent_ir.json').read_bytes())
    async def worker(*args):return {'result':ProducedArtifact(output,contract_id=produced_contract)}
    result=await measure_trial(context,worker,{},context.contract['outputs'],context.plan_ref,'controlled')
    assert (result.status=='completed') is accepted
    assert result.accepted is False
    if not accepted:assert result.failure=='output_invalid'
