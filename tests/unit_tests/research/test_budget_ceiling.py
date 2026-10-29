"""C008 protected budget invariants; controlled mechanics, not live model proof."""
import copy

import pytest

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.compiler import input_port, register_compiler_capsules
from jiuwenswarm.research.contracts import Principal, ResearchError
from tests.unit_tests.research.controlled_assets import ControlledLibraryService as LibraryService
from jiuwenswarm.research.runner import CapsuleRunner, Registry
from jiuwenswarm.research.state import SQLiteRunStore


async def installed_library(tmp_path, *, scientific=False, scientific_memory=512):
    store = SQLiteRunStore(tmp_path)
    registry, checks = Registry(), CheckRegistry()
    library = LibraryService(store)
    actor = Principal('operator', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
    installed = await register_compiler_capsules(registry, checks, library, store, actor, activate=True)
    library.configure_verifier(installed['verifier']['pin'])
    if scientific:
        for stage, asset in build_research_assets(store).items():
            library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
            admission = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=scientific_memory)
            record = store.read_record(admission)
            assert record['status'] == 'admitted', record['reasons']
            pin = record['cc']
            library.set_standing(pin['cc_name'], pin['cc_version'], 'active', actor, reason='Controlled C008 fixture')
            installed[stage] = dict(asset, pin=pin)
    return store, registry, checks, library, installed, actor


@pytest.mark.asyncio
async def test_library_ceiling_adds_exact_per_output_review_without_changing_workers(tmp_path):
    store, _, _, library, installed, _ = await installed_library(tmp_path, scientific=True)
    declarations = {stage: store.read_blob(value['declaration_ref']) for stage, value in installed.items()}
    snapshot_ref = library.snapshot()
    snapshot = store.read_record(snapshot_ref, contract_id='library-snapshot')
    entries = {entry['cc_name']: entry for entry in snapshot['entries']}
    verifier = store.read_record(installed['verifier']['declaration_ref'])
    for stage, value in installed.items():
        declaration = store.read_record(value['declaration_ref'])
        worker = declaration['budget']['per_call']
        profile = store.read_record(value['profile_ref'])
        count = 0 if stage == 'verifier' else len(declaration['ports']['outputs'])
        calls = worker['invocations'] if any(x['service_key'] == 'audited_model_bridge' for x in declaration['needs']['injects']) else 0
        entry = entries[declaration['identity']['name']]
        assert entry['max_limits']['time_s'] == worker['wall_s'] + count * min(verifier['budget']['per_call']['wall_s'], profile['time_s'])
        assert entry['max_limits']['model_calls'] == calls + count
        assert entry['max_limits']['memory_mb'] == (256 if count == 0 else max(512 if stage not in {'intent', 'requirements', 'planner'} else 256, 256))
        assert store.read_blob(value['declaration_ref']) == declarations[stage]
    benchmark = entries['research.benchmark']
    assert benchmark['max_limits']['model_calls'] == 3
    binding = store.read_record(library.snapshot_budget_binding(snapshot_ref))
    assert binding['interface_revision'] == 'M1-IF-002@r2'
    assert binding['library_snapshot_ref'] == snapshot_ref
    assert binding['verifier']['cc'] == installed['verifier']['pin']
    assert library.snapshot() == snapshot_ref


@pytest.mark.asyncio
async def test_verifier_pin_is_explicit_and_later_standing_cannot_rewrite_frozen_snapshot(tmp_path):
    store, _, _, library, installed, actor = await installed_library(tmp_path)
    frozen = library.snapshot()
    exact = store.read_blob(frozen)
    missing = dict(installed['verifier']['pin'], cc_version='unadmitted')
    with pytest.raises(ResearchError):
        library.configure_verifier(missing)
    library.set_standing('research.verifier', installed['verifier']['pin']['cc_version'], 'suspended', actor, reason='Controlled unavailable verifier')
    with pytest.raises(ResearchError, match='verifier_binding'):
        library.snapshot()
    assert store.read_blob(frozen) == exact


async def work_contract(tmp_path, *, calls=2):
    store, registry, checks, library, installed, _ = await installed_library(tmp_path)
    opaque = store.put_blob(b'controlled protected binding')
    profile = store.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': 'final', 'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'], 'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
    factory = ContractFactory(store, library, verifier_pin=installed['verifier']['pin'], finalization_profile_ref=profile)
    from jiuwenswarm.research.intake import qualify_intake
    user = Principal('alice', frozenset({'project'}), frozenset({'ingest'}))
    intake_ref = qualify_intake(store, user, 'Compare an exact index with repeated lookup.', [],
        workspace_id='project', profile_ref=opaque, workspace_ref=opaque, input_directory_ref=opaque)
    store.create_run('budget-run', account_id='alice', workspace_id='project', submission={'intake_ref': intake_ref})
    ports = [input_port('request', 'qualified-intake:field-contract:2', intake_ref)]
    parent = factory.prepare_parent('budget-run', 'intent', [{'subnode_id': 'intent', 'cc': installed['intent']['pin'], 'depends_on': []}], inputs=ports,
        outputs=[{'name': 'intent', 'contract_id': 'intent-ir', 'version': '1.0.0', 'required': True}], objective='Controlled budget binding', requirement_ids=['intent'],
        limits={'time_s': 120, 'model_calls': calls, 'memory_mb': 256}, policy_ref=opaque, configuration_ref=opaque, template_ref=opaque,
        authority_ceiling={'network': 'none', 'network_allowlist': [], 'resource_reads': [intake_ref, store.read_record(intake_ref)['request_ref']], 'write_roots': [], 'tools': []})
    contract_ref, _, _ = factory.bind_subnode(parent, 'intent', ports)
    contract = store.read_record(contract_ref)
    selection = store.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': 'fixed', 'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {}, 'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []}, 'alternate_model_id': None, 'policy_ref': opaque})
    runner = CapsuleRunner(store, registry, checks, model=None,check_assets=library.check_assets)
    runner.configure_run('budget-run', model_selection_profile_ref=selection, deployment_ref=opaque, router={'enabled': False, 'profile_ref': None, 'deadline_s': 30}, configuration_ref=opaque, run_limits={'time_s': 120, 'model_calls': calls, 'memory_mb': 256})
    return store, runner, contract_ref, contract


@pytest.mark.asyncio
async def test_worker_cannot_start_by_borrowing_the_required_review_call(tmp_path):
    store, runner, ref, contract = await work_contract(tmp_path, calls=1)
    with pytest.raises(ResearchError, match='budget_exhausted'):
        runner._start_context(ref, contract, {})
    assert list(store.iter_records(kinds=('model-call-claim',))) == []


@pytest.mark.asyncio
async def test_reserved_review_survives_worker_authorization_and_executor_has_absolute_deadline(tmp_path):
    store, runner, ref, contract = await work_contract(tmp_path)
    original = copy.deepcopy(contract)
    ctx = runner._start_context(ref, contract, {})
    await runner._await_start(ctx)
    protected = runner.authorize_model_context({'execution_id': ctx.execution_id, 'call_ordinal': 1})
    assert protected['limits']['model_calls'] == 1
    with pytest.raises(ResearchError, match='budget_exhausted'):
        runner.authorize_model_context({'execution_id': ctx.execution_id, 'call_ordinal': 2})
    executor = runner.authorize_executor_binding({'contract_ref': ref, 'invocation_id': ctx.invocation_id, 'execution_id': ctx.execution_id})
    assert 0 < executor['remaining_time_s'] <= 60
    assert executor['execution_deadline_monotonic_s'] > runner._executions[ctx.execution_id]['started']
    assert store.read_record(ref) == original


@pytest.mark.asyncio
async def test_model_dispatch_recheck_joins_claim_without_consuming_a_second_ordinal(tmp_path):
    store,runner,ref,contract=await work_contract(tmp_path)
    ctx=runner._start_context(ref,contract,{})
    await runner._await_start(ctx)
    claimed=runner.authorize_model_context({'execution_id':ctx.execution_id,'call_ordinal':1})
    request={key:claimed[key] for key in ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')}
    before=list(store.iter_records(kinds=('model-call-claim',)))
    live=runner.authorize_model_dispatch(request)
    assert live['model_selection_profile_ref']==claimed['model_selection_profile_ref']
    assert live['execution_deadline_monotonic_s']<=claimed['execution_deadline_monotonic_s']
    assert list(store.iter_records(kinds=('model-call-claim',)))==before
    with pytest.raises(ResearchError):runner.authorize_model_dispatch(dict(request,call_id='forged'))
    runner._executions[ctx.execution_id]['closed']=True
    with pytest.raises(ResearchError):runner.authorize_model_dispatch(request)


def test_atomic_model_claim_preserves_independent_node_and_run_reservations(tmp_path):
    store = SQLiteRunStore(tmp_path)
    store.create_run('r', account_id='alice', workspace_id='project', submission={})
    context = {'run_id': 'r', 'node_id': 'n', 'attempt_id': 'n-a1', 'invocation_id': 'worker', 'call_ordinal': 1}
    store.claim_model_call(context, invocation_limit=2, node_limit=2, run_limit=2, reserved_node_calls=1, reserved_run_calls=1)
    with pytest.raises(ResearchError, match='budget_exhausted'):
        store.claim_model_call(context | {'call_ordinal': 2}, invocation_limit=2, node_limit=2, run_limit=2, reserved_node_calls=1, reserved_run_calls=1)
    store.claim_model_call(context | {'invocation_id': 'verifier'}, invocation_limit=1, node_limit=2, run_limit=2)


@pytest.mark.asyncio
async def test_configuration_delay_does_not_spend_work_time_and_started_clock_never_resets(tmp_path,monkeypatch):
    import jiuwenswarm.research.runner as module
    clock=[100.0]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    store,runner,ref,contract=await work_contract(tmp_path)
    frozen=copy.deepcopy(runner._run_contexts['budget-run'])
    clock[0]+=1000  # Parent correctness and benchmark preparation are not this work run.
    assert runner._run_started=={} and runner._node_started=={}
    preview=runner._budget_state(contract,reserve=False)
    assert preview['run_remaining']['time_s']==120
    assert runner._run_started=={} and list(store.iter_records(kinds=('node-budget-start',)))==[]
    context=runner._start_context(ref,contract,{})
    first=runner._run_started['budget-run']
    clock[0]+=10
    assert runner._budget_state(contract)['run_remaining']['time_s']==110
    runner.configure_run('budget-run',**frozen)
    assert runner._run_started['budget-run']==first
    clock[0]+=120
    with pytest.raises(ResearchError,match='budget_exhausted'):
        runner._budget_state(contract,reserve=False)
    assert runner._run_started['budget-run']==first
    assert list(store.iter_records(kinds=('model-call-start',)))==[]


@pytest.mark.asyncio
async def test_schema2_host_work_reaches_dispatch_fence_without_inference(tmp_path):
    from types import SimpleNamespace
    from jiuwenswarm.research.isolated_resources import IsolatedResources
    store,old,ref,contract=await work_contract(tmp_path)
    deployment=store.put_blob(__import__('json').dumps({'schema':'ai4r-fixed-subscription:2','id':'host-test',
        'route_id':'codex-cli-default','requested_model':'gpt-6.1-sol','endpoint':'local-protected-IPC',
        'backend':'host-codex-app-server','reasoning_effort':'medium'}).encode())
    runner=CapsuleRunner(store,old.registry,old.check_registry,model=None,check_assets=old.check_assets)
    frozen=dict(old._run_contexts['budget-run'],deployment_ref=deployment)
    runner.configure_run('budget-run',**frozen)
    resources=IsolatedResources(store,None,SimpleNamespace(runner=runner),None,None,None,{})
    preview=resources.validate_proposal_once(ref)
    assert preview['requested_model']=='gpt-6.1-sol' and preview['requires_broker'] is False
    assert runner._run_started=={} and runner._node_started=={}
    assert store.connection.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==0
    context=runner._start_context(ref,contract,runner._decode_inputs(contract))
    await runner._await_start(context)
    claimed=runner.authorize_model_context({'execution_id':context.execution_id,'call_ordinal':1})
    request={k:claimed[k] for k in ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')}
    protected=runner.authorize_model_dispatch(request)
    assert protected['requested_model']=='gpt-6.1-sol' and protected['limits']['model_calls']==1
    assert list(store.iter_records(kinds=('model-call-start','model-call-output')))==[]