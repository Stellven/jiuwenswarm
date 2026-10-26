"""E2 uses actual admitted Intent captures; controlled transport is not calibration.

The original capsule executes once to create the frozen fixture. Replay then
uses the installed measurement owner, host checks and recording-only gate.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit_tests.research.evaluation_runtime_fixture import bind_request_runtime

from jiuwenswarm.research.admitted_measurement import AdmittedMeasurementResources, AdmittedResourceContext
from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.bridge import GovernedBridge
from jiuwenswarm.research.compiler import input_port, register_compiler_capsules
from jiuwenswarm.research.contracts import Principal, ResearchError, validate
from jiuwenswarm.research.evaluation_provider import EvaluationProvider, InstalledEvaluationResources
from jiuwenswarm.research.intake import qualify_intake
from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.runner import CapsuleRunner, Registry
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.controlled_assets import ControlledLibraryService


async def replay_fixture(root, *, bad_span=True, record_gate=False, host_duration=None,
                         verifier_mismatch=False, review_failure=False, verifier_reject=False):
    store = SQLiteRunStore(root)
    registry, checks = Registry(), CheckRegistry()
    # Explicit test checking authority, never a production calibrated admission.
    library = ControlledLibraryService(store)
    owner = Principal('operator', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
    installed = await register_compiler_capsules(registry, checks, library, store, owner, activate=True)
    library.configure_verifier(installed['verifier']['pin'])
    snapshot = library.snapshot()
    opaque = store.put_blob(b'controlled immutable evaluation deployment')
    policy = store.put_record('plan-policy', {
        'schema_version': '1.0.0', 'id': 'replay-policy', 'max_nodes': 12,
        'allowed_effect_classes': ['pure', 'read'], 'allow_network': False,
        'required_stages': [], 'aggregate_limits': {'time_s': 120, 'model_calls': 2, 'memory_mb': 256},
        'max_attempts_per_node': 1,
    })
    verifier = installed['intent']['declaration_ref'] if verifier_mismatch else installed['verifier']['declaration_ref']
    profile = {
        'schema_version': '1.0.0', 'id': 'profile:replay', 'profile_id': 'controlled:replay',
        'plan_source': 'static', 'router_enabled': False, 'router_version': None,
        'model_route': 'codex-cli-default', 'library_snapshot_sha256': snapshot['sha256'],
        'candidate_pins': [], 'verifier_cc_ref': verifier, 'invalid_for_product': True,
        'allowed_entry_points': ['E2'],
    }
    profile_ref = store.put_record('evaluation-profile', profile)
    settings = {
        'schema_version': '1.0.0',
        'cc': {'plan_source': 'static', 'plan_policy_ref': policy, 'static_template_ref': opaque,
               'evaluation_profile_ref': profile_ref,
               'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
        'codex': {'route_id': 'codex-cli-default'},
        'rsi': {'custodian_key_id': None, 'custodian_public_key': None}, 'role_aliases': {},
    }
    operator = SimpleNamespace(snapshot=lambda: copy.deepcopy(settings))
    configuration = store.append_record('approved-configuration', {'operator': settings})
    actor = Principal('operator', frozenset({'isolated'}), frozenset({'ingest', 'evaluation_profile'}))
    fixtures = Path('tests/fixtures/research/compiler')
    intake_ref = qualify_intake(store, actor, (fixtures / 'request.txt').read_text('utf-8'), [],
        workspace_id='isolated', profile_ref=opaque, workspace_ref=opaque, input_directory_ref=opaque)
    intake = store.read_record(intake_ref)
    store.create_run('run:replay', account_id='operator', workspace_id='isolated', submission={'intake_ref': intake_ref})
    final = store.put_record('node-finalization-profile', {
        'schema_version': '2.0.0', 'id': 'replay-final',
        'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
        'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0,
    })
    factory = ContractFactory(store, library, verifier_pin=installed['verifier']['pin'], finalization_profile_ref=final)
    ports = [input_port('request', 'qualified-intake:field-contract:2', intake_ref)]
    parent_ref = factory.prepare_parent('run:replay', 'intent', [
        {'subnode_id': 'intent', 'cc': installed['intent']['pin'], 'depends_on': []}], inputs=ports,
        outputs=[{'name': 'intent', 'contract_id': 'intent-ir', 'version': '1.0.0', 'required': True}],
        objective='Frozen source-span replay fixture', requirement_ids=['intent'],
        limits={'time_s': 120, 'model_calls': 2, 'memory_mb': 256}, policy_ref=policy,
        configuration_ref=configuration, template_ref=opaque,
        authority_ceiling={'network': 'none', 'network_allowlist': [], 'resource_reads': [intake_ref, intake['request_ref']],
                           'write_roots': [], 'tools': []})
    contract_ref, plan_ref, _ = factory.bind_subnode(parent_ref, 'intent', ports)
    selection = store.put_record('model-selection-profile', {
        'schema_version': '1.0.0', 'id': 'replay-fixed', 'policy_mode': 'fixed_baseline',
        'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
        'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0,
                                'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []},
        'alternate_model_id': None, 'policy_ref': policy,
    })
    prompts, transport_errors, private_host_pins = [], [], []
    class ControlledSubscription:
        async def invoke_governed(self, prompt, *, model, timeout_s):
            try:
                return await self.reply(prompt, model=model, timeout_s=timeout_s)
            except Exception as error:
                transport_errors.append(repr(error))
                raise
        async def reply(self, prompt, *, model, timeout_s):
            prompts.append(prompt)
            payload = json.loads(prompt.split('<subject_payload>\n', 1)[1].split('\n</subject_payload>', 1)[0])
            if set(payload) == {'subject_declaration', 'subject_output'}:
                assert 'HOST_RECORD_SENTINEL' not in prompt
                assert all(pin not in prompt for pin in private_host_pins)
                if review_failure:
                    raise RuntimeError('Controlled independent-review provider failure')
                criteria = json.loads(prompt.split('Criteria for this output:\n', 1)[1].split('\n\n<subject_payload>', 1)[0])
                value = {'findings': [{'criterion_id': c['criterion_id'], 'outcome': 'FAIL' if verifier_reject else 'PASS',
                    'reason': 'Controlled structural reply, not semantic quality evidence'} for c in criteria],
                    'uncertainties': [], 'limitations': [], 'required_correction': 'Controlled rejection' if verifier_reject else None}
            else:
                value = json.loads((fixtures / 'intent_ir.json').read_bytes())
                def rewrite(v):
                    if isinstance(v, dict):
                        return intake['request_ref'] if set(v) == {'id', 'sha256'} else {k: rewrite(x) for k, x in v.items()}
                    if isinstance(v, list): return [rewrite(x) for x in v]
                    return v
                value = rewrite(value)
                if bad_span: value['interpretation']['problem']['source_spans'][0]['end'] = 100000
            return {'text': json.dumps(value), 'identity': {'effective': None, 'basis': 'Controlled in-process provider'},
                    'usage': {}, 'provider_request_id': None, 'observed_runtime': True}
    runner = CapsuleRunner(store, registry, checks, model=None, check_assets=library.check_assets)
    runner.model = GovernedBridge(persist=store.append_record, authorize=runner.authorize_model_context,
        revalidate=runner.authorize_model_dispatch, subscription_service=ControlledSubscription(), validate_record=validate)
    resources = AdmittedResourceContext(store, operator,
        SimpleNamespace(library=library, registry=registry, checks=checks, installed=installed, runner=runner), actor,
        {'configuration_ref': configuration, 'workspace_id': 'isolated', 'model_selection_profile_ref': selection,
         'deployment_ref': opaque}, None)
    admitted = AdmittedMeasurementResources(resources)
    original = await admitted.execute(admitted.prepare(contract_ref, plan_ref, semantic_review=False))
    assert original.output_refs and len(prompts) == 1, (original.failure, transport_errors)
    assert original.failure == ('deterministic_check_failed' if bad_span else None)
    host_records, entries = [], []
    if host_duration is not None:
        host = store.read_record(original.observation_ref)
        host['duration_s'] = host_duration
        marker = store.put_blob(b'HOST_RECORD_SENTINEL: deterministic-only captured fixture')
        host['trace_refs'] = [*host['trace_refs'], marker]
        host_ref = store.put_record('invocation-observation', host, record_id='replay-host-duration')
        private_host_pins.extend([host_ref['sha256'], marker['sha256']])
        host_records.append({'record_type': 'runtime_observation', 'ref': host_ref})
        entries.append({'path': 'host.json', 'sha256': host_ref['sha256'], 'artifact_ref': host_ref,
                        'role': 'host_runtime_observation'})
    output_ref = original.output_refs['intent']
    declaration_ref = installed['intent']['declaration_ref']
    verifier_id = 'research.verifier@' + installed['verifier']['pin']['cc_version']
    binding_ref = store.append_record('evaluation-case-binding', {
        'id': 'replay:case', 'contract_ref': contract_ref, 'check_plan_ref': plan_ref,
        'output_refs': original.output_refs, 'original_observation_ref': original.observation_ref,
        'verifier_cc_id': verifier_id, 'host_records': host_records,
    })
    entries += [{'path': name, 'sha256': ref['sha256'], 'artifact_ref': ref, 'role': role}
        for name, ref, role in [('capsule.json', declaration_ref, 'declaration'), ('output.json', output_ref, 'output')]]
    assets_ref = store.append_record('evaluation-assets', {
        'schema': 'ai4r-evaluation-assets:1', 'id': 'assets:replay', 'profile_ref': profile_ref,
        'configuration_ref': configuration, 'account_id': 'operator', 'workspace_id': 'isolated',
        'campaign_id': 'campaign', 'entries': entries,
        'cases': [{'case_id': 'span', 'entry_point': 'E2', 'binding_ref': binding_ref, 'record_gate': record_gate}],
    })
    try:
        installed_resources = InstalledEvaluationResources(admitted, profile_ref=profile_ref, assets_ref=assets_ref,
                                                         library_snapshot_ref=snapshot)
    except BaseException:
        store.close()
        raise
    provider = EvaluationProvider(store, operator, assets_ref=assets_ref, resources=installed_resources, library=library)
    request = {'request_id': 'replay:request', 'campaign_id': 'campaign', 'case_id': 'span',
        'evaluation_profile_id': profile['profile_id'], 'verifier_cc_id': verifier_id, 'node_id': 'intent',
        'declaration': {'path': 'capsule.json', 'sha256': declaration_ref['sha256']},
        'output': {'path': 'output.json', 'sha256': output_ref['sha256']},
        'host_records': [{'record_type': row['record_type'], 'path': 'host.json', 'sha256': row['ref']['sha256']}
                         for row in host_records]}
    return store, provider, actor, request, prompts, original


def authority_state(store):
    return {
        'tables': {name: store.connection.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                   for name in ('library_versions', 'acceptance', 'model_calls')},
        'records': [row['ref'] for row in store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'activation-record'))],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('record_gate', [False, True])
async def test_replay_actual_tier1_failure_never_calls_worker_or_reviewer_or_product_gate(tmp_path, record_gate):
    store, provider, actor, request, prompts, original = await replay_fixture(tmp_path, record_gate=record_gate)
    owner=bind_request_runtime(store,provider,request,'E2')
    try:
        before = authority_state(store)
        observed_before = [r['ref'] for r in store.iter_records(kinds=('invocation-observation',))]
        original_outputs = copy.deepcopy(original.output_refs)
        original_bytes = [(ref,store.read_blob(ref)) for ref in
            [*original_outputs.values(),original.observation_ref]]
        original_kind = store.record_kind(original.observation_ref)
        assert original_kind == 'invocation-observation'
        assert store.require_product_material(list(original_outputs.values())) is None
        assert provider.available_entry_points == ('E2',)
        result = await provider.node_replay(actor, request)
        assert result['tier1_verdict'] == 'FAIL' and result['tier2_verdict'] == 'NOT_RUN'
        assert result['advanced'] is False and result['invalid_for_product'] is True
        assert result['downstream_action'] == ('halted' if record_gate else 'locked')
        assert result['reason'] == 'deterministic_check_failed'
        assert result['model_calls'] == [] and len(prompts) == 1
        assert before == authority_state(store)
        assert observed_before == [r['ref'] for r in store.iter_records(kinds=('invocation-observation',))]
        measured = store.read_record(result['evidence_refs'][0])
        checks = store.read_record(measured['deterministic_ref'])
        assert store.record_kind(result['evidence_refs'][0]) == 'evaluation-trial-measurement'
        assert store.record_kind(measured['deterministic_ref']) == 'evaluation-deterministic-check-result'
        assert measured['accepted'] is False and measured['output_refs'] == original.output_refs
        assert any(r['check_id'] == 'source_spans' and r['outcome'] == 'FAIL' for r in checks['results'])
        # IF016 preserves the canonical source. Evaluation-produced private
        # evidence must be excluded without retroactively tainting originals.
        assert measured['output_refs'] == original_outputs
        assert all(store.read_blob(ref) == raw for ref,raw in original_bytes)
        assert store.record_kind(original.observation_ref) == original_kind
        assert store.require_product_material(list(original_outputs.values())) is None
        derived = [('measurement',result['evidence_refs'][0]),
                   ('deterministic_result',measured['deterministic_ref'])]
        actions = list(store.iter_records(kinds=('evaluation-recording-downstream-action',)))
        assert len(actions) == int(record_gate)
        if actions:
            gate = store.read_record(actions[0]['record']['gate_ref'])
            assert gate['invalid_for_product'] is True and actions[0]['record']['scheduler_kind'] == 'recording'
            assert gate['persisted_at'] <= actions[0]['record']['at']
            derived += [('evaluation_gate',actions[0]['record']['gate_ref']),
                        ('recording_action',actions[0]['ref'])]
        from jiuwenswarm.research.evaluation_history import EvaluationReader
        import io
        import zipfile
        exported = EvaluationReader(store,runtime_ref=owner.runtime_ref).export_bytes(
            actor,request['request_id'],audience='researcher')
        with zipfile.ZipFile(io.BytesIO(exported)) as archive:
            exported_manifest = archive.read('evaluation_export.json')
        # Re-import actual delivered bytes, with no fabricated record kind or
        # evaluation-origin alias that could make the denial vacuously pass.
        derived += [('export_manifest',store.put_blob(exported_manifest,media_type='application/json')),
                    ('export_zip',store.put_blob(exported,media_type='application/zip'))]
        leaked = []
        for label,ref in derived:
            try:
                store.require_product_material([ref])
            except ResearchError as error:
                assert error.code == 'evaluation_only'
            else:
                leaked.append(label)
        assert not leaked, 'Evaluation-produced material remained eligible: ' + repr(leaked)
        provider.resources = None
        assert await provider.node_replay(actor, request) == result
        assert provider.get(actor, request['request_id'])['result'] == result
        assert len(prompts) == 1 and before == authority_state(store)
        with pytest.raises(ResearchError) as error:
            await provider.node_replay(actor, request | {'node_id': 'foreign'})
        assert error.value.code == 'identity_conflict'
    finally:
        store.close()


@pytest.mark.asyncio
async def test_replay_claim_survives_owner_failure_without_reissuing(tmp_path, monkeypatch):
    store, provider, actor, request, prompts, _ = await replay_fixture(tmp_path)
    owner=bind_request_runtime(store,provider,request,'E2')
    calls = []
    def fail_prepare(request_ref):
        calls.append('prepare')
        raise ResearchError('controlled_owner_failure', 'Actual owner preparation failure')
    monkeypatch.setattr(owner, 'prepare', fail_prepare)
    try:
        before = authority_state(store)
        with pytest.raises(ResearchError) as error: await provider.node_replay(actor, request)
        assert error.value.code == 'controlled_owner_failure'
        state = provider.get(actor, request['request_id'])
        assert state['status'] == 'failed' and state['result'] is None
        assert store.record_kind(state['failure_ref']) == 'evaluation-failure'
        assert store.read_record(state['failure_ref'])['reason'] == 'controlled_owner_failure'
        with pytest.raises(ResearchError) as error: await provider.node_replay(actor, request)
        assert error.value.code == 'evaluation_outcome_unknown'
        assert calls == ['prepare'] and len(prompts) == 1 and before == authority_state(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_replay_cannot_advertise_a_different_installed_verifier(tmp_path):
    with pytest.raises(ResearchError, match='actual installed independent reviewer'):
        await replay_fixture(tmp_path, verifier_mismatch=True)


@pytest.mark.asyncio
async def test_replay_supplied_runtime_budget_evidence_is_not_silently_ignored(tmp_path):
    store, provider, actor, request, prompts, _ = await replay_fixture(tmp_path, bad_span=False, host_duration=999)
    bind_request_runtime(store,provider,request,'E2')
    try:
        assert provider.available_entry_points == ('E2',)
        result = await provider.node_replay(actor, request)
        assert result['tier1_verdict'] == 'FAIL' and result['tier2_verdict'] == 'NOT_RUN'
        assert result['advanced'] is False and len(prompts) == 1
        assert result['reason'] == 'deterministic_check_failed'
        measured = store.read_record(result['evidence_refs'][0])
        checked = store.read_record(measured['deterministic_ref'])
        budget = next(row for row in checked['results'] if row['check_id'] == 'host_limits')
        host_ref = provider.entries['host.json']['artifact_ref']
        assert budget['outcome'] == 'FAIL' and host_ref in budget['evidence_refs']
        assert all(row['outcome'] == 'PASS' for row in checked['results'] if row['check_id'] != 'host_limits')
    finally:
        store.close()


@pytest.mark.asyncio
async def test_failed_independent_review_retains_actual_model_call_and_once_state(tmp_path):
    store, provider, actor, request, prompts, _ = await replay_fixture(tmp_path, bad_span=False, review_failure=True)
    bind_request_runtime(store,provider,request,'E2')
    try:
        result = await provider.node_replay(actor, request)
        assert result['tier1_verdict'] == 'PASS' and result['advanced'] is False
        assert result['reason'] == 'provider_error' and result['tier2_verdict'] == 'NOT_RUN'
        assert len(prompts) == 2
        assert len(result['model_calls']) == 1
        call = result['model_calls'][0]
        assert call['role'] == 'verifier' and call['outcome'] == 'failed'
        captured = store.read_record(call['call_ref'], contract_id='model-call')
        assert captured['provider_error_code'] == 'provider_error'
        assert captured['identity']['effective'] is None and captured['usage']['input_tokens'] is None
        assert await provider.node_replay(actor, request) == result and len(prompts) == 2
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit')))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_actual_verifier_rejection_halts_valid_replay_with_call_evidence(tmp_path):
    store, provider, actor, request, prompts, _ = await replay_fixture(
        tmp_path, bad_span=False, record_gate=True, verifier_reject=True)
    bind_request_runtime(store, provider, request, 'E2')
    try:
        before = authority_state(store)
        result = await provider.node_replay(actor, request)
        assert result['tier1_verdict'] == 'PASS'
        assert result['tier2_verdict'] == 'FAIL'
        assert result['advanced'] is False and result['downstream_action'] == 'halted'
        assert result['invalid_for_product'] is True and result['reason'] is None
        assert len(prompts) == 2 and len(result['model_calls']) == 1
        call = result['model_calls'][0]
        assert call['role'] == 'verifier' and call['outcome'] == 'completed'
        captured = store.read_record(call['call_ref'], contract_id='model-call')
        assert captured['call_function'] == 'verifier' and captured['outcome'] == 'completed'
        measured = store.read_record(result['evidence_refs'][0])
        assert measured['accepted'] is False
        actions = list(store.iter_records(kinds=('evaluation-recording-downstream-action',)))
        assert len(actions) == 1 and actions[0]['record']['action'] == 'halted'
        assert actions[0]['record']['scheduler_kind'] == 'recording'
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit')))
        # Fixture setup already activated the reviewed capsule. Replay must
        # preserve that authority exactly, rather than assert it never existed.
        assert before == authority_state(store)
        assert await provider.node_replay(actor, request) == result and len(prompts) == 2
    finally:
        store.close()

@pytest.mark.asyncio
async def test_eligible_replay_sends_only_declaration_and_output_to_actual_reviewer(tmp_path):
    store, provider, actor, request, prompts, _ = await replay_fixture(tmp_path, bad_span=False, host_duration=0)
    bind_request_runtime(store,provider,request,'E2')
    try:
        before = [r['ref'] for r in store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'activation-record'))]
        result = await provider.node_replay(actor, request)
        assert result['tier1_verdict'] == 'PASS' and result['tier2_verdict'] == 'PASS', result['reason']
        assert len(prompts) == 2 and len(result['model_calls']) == 1
        assert result['model_calls'][0]['role'] == 'verifier'
        assert result['advanced'] is False and result['downstream_action'] == 'locked'
        assert result['invalid_for_product'] is True
        measured = store.read_record(result['evidence_refs'][0])
        checked = store.read_record(measured['deterministic_ref'])
        host_ref = provider.entries['host.json']['artifact_ref']
        assert all(host_ref in row['evidence_refs'] for row in checked['results'] if row['check_id'].startswith('host_'))
        assert before == [r['ref'] for r in store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'activation-record'))]
        assert await provider.node_replay(actor, request) == result and len(prompts) == 2
    finally:
        store.close()


@pytest.mark.asyncio
async def test_evaluation_replay_rejects_evidence_aware_profile_before_review_call(tmp_path):
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research.checks.assets import prepare_evidence_aware_release
    from jiuwenswarm.research.evaluation_authority import EvaluationMeasurementContext

    store = SQLiteRunStore(tmp_path)
    asset = build_research_assets(store)['screening']
    base = store.read_record(asset['profile_ref'], contract_id='checking-profile')
    selected = next(row['criterion_id'] for row in base['criteria']
                    if row['criterion_id'] not in {
                        'declared_output_conformance', 'internal_consistency', 'limitations_consistency'})
    evidence_release = prepare_evidence_aware_release(store, asset, version_label='replay-v2-test',
        evidence_criterion_ids=[selected], evidence_input_names=['brief'],
        reviewer_instructions='Use only the selected task evidence for the named criterion.')

    context = object.__new__(EvaluationMeasurementContext)
    context.store = store
    context.basis = {'profile_ref': evidence_release['profile_ref']}
    with pytest.raises(ResearchError, match='not wired into evaluation replay') as caught:
        await context.review('intent', {'id': 'output', 'sha256': '0' * 64},
            {'id': 'deterministic', 'sha256': '0' * 64}, {'id': 'observation', 'sha256': '0' * 64})
    assert caught.value.code == 'entry_point_unavailable'
    assert not list(store.iter_records(kinds=('model-call',)))
    store.close()
