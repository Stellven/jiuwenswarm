"""Admitted-source adapter controls; explicit controlled assets are not qualification."""
import copy
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.runner import CapsuleRunner,Registry
from tests.unit_tests.research.test_isolated_evaluation import trial_fixture


async def adapter_fixture(root):
    from jiuwenswarm.research.admitted_measurement import AdmittedMeasurementResources
    store,private,fixture,binding=await trial_fixture(root)
    resources=private.resources;registry=Registry();contract=store.read_record(binding['parent_contract_ref']);b=contract['bindings'][0]
    declaration=store.read_record(b['declaration_ref'])
    class UnavailableCarrier:
        async def execute(self,*_):raise ResearchError('model_unavailable','Explicit controlled unavailable carrier')
    registry.register(declaration['identity']['name'],declaration['identity']['version_label'],UnavailableCarrier(),declaration_sha256=b['declaration_ref']['sha256'],implementation_refs=b['implementation_refs'])
    resources.registry=registry
    resources.runner=CapsuleRunner(store,registry,resources.composition.checks,model=None,check_assets=resources.composition.library.check_assets)
    original=store.read_record(binding['parent_contract_ref']);node=store.read_record(original['node_contract_ref'])
    policy=store.put_record('plan-policy',{'schema_version':'1.0.0','id':'admitted-test-policy','max_nodes':12,
        'allowed_effect_classes':['pure','read'],'allow_network':False,'required_stages':[],
        'aggregate_limits':copy.deepcopy(node['node_limits']),'max_attempts_per_node':1})
    node['policy_ref']=policy;node_ref=store.put_record('node-execution-contract',node,record_id='admitted-test-node')
    original['node_contract_ref']=node_ref;original['policy_ref']=policy
    contract_ref=store.put_record('subnode-execution-contract',original,record_id='admitted-test-subnode')
    source_plan=next(r['record'] for r in store.iter_records(kinds=('bound-check-plan',)) if r['record']['contract_ref']==binding['parent_contract_ref'])
    source_plan.update(contract_ref=contract_ref,node_contract_ref=node_ref,policy_ref=policy)
    source_plan_ref=store.put_record('bound-check-plan',source_plan,record_id='admitted-test-checks')
    settings={'schema_version':'1.0.0','cc':{'plan_source':'static','plan_policy_ref':policy,'static_template_ref':binding['target_ref'],
        'evaluation_profile_ref':None,'router':{'enabled':False,'deadline_s':30,'profile_ref':None}},
        'codex':{'route_id':'codex-cli-default'},'rsi':{'custodian_key_id':None,'custodian_public_key':None},'role_aliases':{}}
    resources.operator=SimpleNamespace(snapshot=lambda:copy.deepcopy(settings))
    return store,AdmittedMeasurementResources(resources),contract_ref,source_plan_ref,fixture


@pytest.mark.asyncio
async def test_prepare_pins_actual_admitted_identity_without_child_gate_or_live_rows(tmp_path):
    store,adapter,contract,checks,fixture=await adapter_fixture(tmp_path)
    tables=['library_versions','acceptance','model_calls'];before={t:store.connection.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables}
    grant=adapter.prepare(contract,checks)
    assert adapter.prepare(contract,checks)==grant
    record=store.read_record(grant)
    assert record['contract_ref']==contract and record['accepted'] is False
    assert 'child_declaration_ref' not in record
    assert before=={t:store.connection.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables}
    forged=store.read_record(contract);forged['bindings'][0]['admission_ref']=contract
    with pytest.raises(ResearchError):adapter.prepare(fixture['put'](forged),checks)
    store.close()


@pytest.mark.asyncio
async def test_measured_failure_captures_actual_observation_without_gate_acceptance_or_retry(tmp_path):
    store,adapter,contract,checks,_=await adapter_fixture(tmp_path)
    grant=adapter.prepare(contract,checks)
    result=await adapter.execute(grant)
    assert result.accepted is False and result.status in {'failed','blocked'}
    assert store.read_record(result.observation_ref)['contract_ref']==contract
    assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit')))
    assert store.connection.execute('SELECT COUNT(*) FROM acceptance').fetchone()[0]==0
    replay=await adapter.execute(grant)
    assert replay.measurement_ref==result.measurement_ref
    assert len(list(store.iter_records(kinds=('invocation-observation',))))==1
    store.close()


@pytest.mark.asyncio
async def test_e3_protected_review_mode_differs_from_rsi_baseline_and_no_worker_replay(tmp_path):
    store,adapter,contract,checks,_=await adapter_fixture(tmp_path)
    ordinary=adapter.prepare(contract,checks)
    e3=adapter.prepare(contract,checks,semantic_review=False)
    assert ordinary!=e3
    assert adapter.metadata(ordinary).semantic_review is True
    assert adapter.metadata(e3).semantic_review is False
    assert not list(store.iter_records(kinds=('model-call','gate-decision')))
    with pytest.raises(ResearchError):adapter.prepare_replay(contract,checks,{})
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['authority','declaration_limit','port_type','account'])
async def test_captured_canonical_shape_cannot_widen_admitted_authority(tmp_path,fault):
    store,adapter,contract_ref,checks_ref,_=await adapter_fixture(tmp_path)
    contract=store.read_record(contract_ref);plan=store.read_record(checks_ref)
    if fault=='authority':contract['bindings'][0]['effective_authority']['write_roots']=['/unapproved']
    elif fault=='declaration_limit':contract['bindings'][0]['limits']['model_calls']+=1
    elif fault=='port_type':contract['outputs'][0]['contract_id']='Ref'
    else:adapter.resources.principal=SimpleNamespace(account_id='foreign')
    changed=store.put_record('subnode-execution-contract',contract,record_id='fault:'+fault)
    plan['contract_ref']=changed;changed_checks=store.put_record('bound-check-plan',plan,record_id='checks:'+fault)
    with pytest.raises(ResearchError):adapter.prepare(changed,changed_checks)
    assert not list(store.iter_records(kinds=('model-call-start','gate-decision','admitted-measurement-grant')))
    store.close()


@pytest.mark.asyncio
async def test_immutable_policy_and_existing_run_reservation_cannot_be_enlarged(tmp_path):
    store,adapter,contract_ref,checks_ref,_=await adapter_fixture(tmp_path)
    policy_ref=adapter.resources.operator.snapshot()['cc']['plan_policy_ref']
    policy=store.read_record(policy_ref);policy['aggregate_limits']['model_calls']=1
    lower=store.put_record('plan-policy',policy,record_id='lower-policy')
    settings=adapter.resources.operator.snapshot();settings['cc']['plan_policy_ref']=lower
    adapter.resources.operator=SimpleNamespace(snapshot=lambda:copy.deepcopy(settings))
    with pytest.raises(ResearchError):adapter.prepare(contract_ref,checks_ref)
    assert not list(store.iter_records(kinds=('model-call-start',)))
    store.close()


@pytest.mark.asyncio
async def test_matching_captured_policy_refs_do_not_authorize_node_above_global_ceiling(tmp_path):
    store,adapter,contract_ref,checks_ref,_=await adapter_fixture(tmp_path)
    settings=adapter.resources.operator.snapshot();policy=store.read_record(settings['cc']['plan_policy_ref'])
    policy['aggregate_limits']['model_calls']=1
    policy_ref=store.put_record('plan-policy',policy,record_id='bounded-global-policy')
    contract=store.read_record(contract_ref);node=store.read_record(contract['node_contract_ref']);node['policy_ref']=policy_ref
    node_ref=store.put_record('node-execution-contract',node,record_id='over-global-node')
    contract.update(policy_ref=policy_ref,node_contract_ref=node_ref)
    changed=store.put_record('subnode-execution-contract',contract,record_id='over-global-work')
    plan=store.read_record(checks_ref);plan.update(policy_ref=policy_ref,node_contract_ref=node_ref,contract_ref=changed)
    checks=store.put_record('bound-check-plan',plan,record_id='over-global-checks')
    settings['cc']['plan_policy_ref']=policy_ref;adapter.resources.operator=SimpleNamespace(snapshot=lambda:copy.deepcopy(settings))
    with pytest.raises(ResearchError,match='global policy ceiling'):adapter.prepare(changed,checks)
    assert not list(store.iter_records(kinds=('model-call-start','admitted-measurement-grant')))
    store.close()
