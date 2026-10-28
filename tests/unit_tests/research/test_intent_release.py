"""Offline immutable release/selection/deadline checks; no model dispatch."""
import copy
import hashlib
import json
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.compiler import input_port, prepare_compiler_assets, register_compiler_capsules
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.intake import qualify_intake
from jiuwenswarm.research.local_profile import capture_local_profile
from jiuwenswarm.research.runner import CapsuleRunner, Registry
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from tests.unit_tests.research.controlled_assets import ControlledLibraryService

OLD_SHA = '6fd9f35c4d20b3e5224e6bf6d2a5d195cf8537d547dc25c0f6382752da79f06a'
NEW_SHA = 'f3eb92f0173d8d6ea71fe12fa3421bb1181367c67ff09d5cb832e0e0c75e792b'


@pytest.mark.asyncio
async def test_exact_additive_release_and_historical_bytes(tmp_path):
    raw = Path('jiuwenswarm/research_assets/compiler/intent.declaration.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == OLD_SHA
    with closing(SQLiteRunStore(tmp_path)) as store:
        old = await prepare_compiler_assets(store)
        new = await prepare_compiler_assets(store, intent_version='m1-7')
        base, selected = old['intent'], new['intent']
        assert store.read_blob(base['declaration_ref']) == raw
        assert base['declaration_ref']['sha256'] == OLD_SHA
        assert selected['declaration_ref']['sha256'] == NEW_SHA
        expected = copy.deepcopy(base['declaration'])
        # A new immutable release must also have a distinct version identity.
        expected['identity']['version_label'] = 'm1-7'
        expected['budget']['per_call']['wall_s'] = 420
        assert selected['declaration'] == expected
        for key in ('body_refs', 'runner_ref'):
            assert selected[key] == base[key]
        assert selected['bundle']['checks'] == base['bundle']['checks']
        for stage in ('requirements', 'planner', 'verifier'):
            assert new[stage] == old[stage]
        ControlledLibraryService(store)._validate_association(selected['declaration_ref'], selected['bundle_ref'], selected['profile_ref'])
        pinned = json.loads(Path('jiuwenswarm/research_assets/compiler/intent_m1_7_catalog.json').read_text())
        assert json.loads(json_bytes(selected)) == pinned
        assert await prepare_compiler_assets(store) == old


@pytest.mark.asyncio
async def test_prepared_release_validation_rejects_drift_and_implicit_selection(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        selected = await prepare_compiler_assets(store, intent_version='m1-7')
        args = (None, None, None, store, None)
        checked = await register_compiler_capsules(*args, prepare_only=True, prepared_assets=selected, intent_version='m1-7')
        assert checked['intent'] == selected['intent']
        for stage in selected:
            for key in ('declaration_ref', 'body_refs', 'runner_ref', 'bundle_ref', 'profile_ref'):
                assert checked[stage][key] == selected[stage][key]
        with pytest.raises(ResearchError):
            await register_compiler_capsules(*args, prepare_only=True, prepared_assets=selected)
        drift = copy.deepcopy(selected)
        drift['intent']['runner_ref'] = drift['intent']['declaration_ref']
        with pytest.raises(ResearchError, match='differs from exact explicit release'):
            await register_compiler_capsules(*args, prepare_only=True, prepared_assets=drift, intent_version='m1-7')


def capture(store, root, **options):
    inputs = root / 'input'
    inputs.mkdir(exist_ok=True)
    with patch('jiuwenswarm.research.local_profile.os.geteuid', return_value=inputs.stat().st_uid, create=True), \
         patch('jiuwenswarm.research.local_profile.stat.S_IMODE', return_value=0o700), \
         patch('jiuwenswarm.research.bootstrap_gateway._protected_file', side_effect=lambda p: Path(p).read_bytes()):
        return capture_local_profile(store, root / 'operator', input_root=inputs, **{'allow_missing_science': True, **options})


def test_profile_freezes_selection_and_default_is_unchanged(tmp_path):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        selected = capture(store, tmp_path, intent_version='m1-7')
        options = store.read_record(selected['binding_ref'])['protected_options']
        assert options['intent_version'] == 'm1-7'
        assert options['compiler_limits'] == {'time_s': 900, 'model_calls': 4, 'memory_mb': 16384}
        assert capture(store, tmp_path, intent_version='m1-7') == selected
        with pytest.raises(ResearchError, match='Frozen Intent release changed'):
            capture(store, tmp_path, intent_version='m1-6')
        # An unnamed Intent release adopts what the existing profile froze.
        assert capture(store, tmp_path) == selected
        other = tmp_path / 'default'
        other.mkdir()
        default = capture(store, other, intent_version='m1-6')
        default_options = store.read_record(default['binding_ref'])['protected_options']
        assert 'intent_version' not in default_options
        assert default_options['compiler_limits']['time_s'] == 600
        for key in ('compiler_limits', 'intent_version'):
            options.pop(key, None)
            default_options.pop(key, None)
        # Input-directory Refs differ between these captures.
        options.pop('input_directory_ref'); default_options.pop('input_directory_ref')
        options.pop('workspace_ref'); default_options.pop('workspace_ref')
        assert options == default_options


def test_new_profile_defaults_to_the_m1_8_intent_release(tmp_path):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        options = store.read_record(capture(store, tmp_path)['binding_ref'])['protected_options']
        assert options['intent_version'] == 'm1-8'
        assert options['compiler_limits']['time_s'] == 900


@pytest.mark.asyncio
@pytest.mark.parametrize('intent_version', ['m1-6', 'm1-7'])
async def test_core_composes_exact_profile_selection_without_dispatch(tmp_path, monkeypatch, intent_version):
    from jiuwenswarm.research.bootstrap_core import compose_core
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    monkeypatch.setenv('JIUWENSWARM_M1_LOCAL_RESEARCH', '1')
    with closing(SQLiteRunStore(tmp_path)) as store:
        profile = capture(store, tmp_path, intent_version=intent_version)
        binding = store.read_record(profile['binding_ref'])
        operator = OperatorConfiguration.from_mapping(store.read_record(binding['configuration_ref']))
        binding.pop('host_id')
        actor = Principal('operator', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
        core = await compose_core(store=store, operator=operator, model=None, executor=None, readiness=None,
            upload_manager=None, principal=actor, initialize=True, **binding)
        assert core.diagnostics == []
        assert core.installed['intent']['pin']['cc_version'] == intent_version
        assert core.compiler.intent_pin == core.installed['intent']['pin']
        assert core.compiler.node_limits['time_s'] == (900 if intent_version == 'm1-7' else 600)


@pytest.mark.parametrize('version', ['latest', 'm1-9', None, []])
@pytest.mark.asyncio
async def test_unknown_or_checking_only_selection_rejected(tmp_path, version):
    with pytest.raises(ResearchError, match='Unsupported explicit Intent'):
        capture_local_profile(None, 'unused', intent_version=version)
    with pytest.raises(ResearchError, match='Checking-only refresh'):
        capture_local_profile(None, 'unused', intent_version='m1-7', legacy_checking_refresh=True)
    with closing(SQLiteRunStore(tmp_path)) as store:
        with pytest.raises(ResearchError, match='Unknown explicit Intent'):
            await prepare_compiler_assets(store, intent_version=version)


@pytest.mark.parametrize('requirements_version', ['m1-8', 'm1-9'])
@pytest.mark.asyncio
async def test_opt_in_profile_binds_full_compiler_and_runner_deadline(tmp_path, requirements_version):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        profile = capture(store, tmp_path, intent_version='m1-7', requirements_version=requirements_version)
        binding = store.read_record(profile['binding_ref'])
        options = binding['protected_options']
        registry, checks = Registry(), CheckRegistry()
        library = ControlledLibraryService(store)
        actor = Principal('operator', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
        installed = await register_compiler_capsules(registry, checks, library, store, actor, activate=True,
            intent_version=options['intent_version'], requirements_version=options['requirements_version'])
        assert installed['intent']['pin']['cc_version'] == 'm1-7'
        assert installed['intent']['pin']['declaration_sha256'] == NEW_SHA
        snapshot = store.read_record(library.snapshot())
        intent_entry = next(e for e in snapshot['entries'] if e['cc_name'] == 'intent.compiler')
        assert intent_entry['max_limits']['time_s'] == 480  # 420 work + independent 60 review
        factory = ContractFactory(store, library, verifier_pin=installed['verifier']['pin'],
                                  finalization_profile_ref=options['finalization_profile_ref'])
        user = Principal('alice', frozenset({'local'}), frozenset({'ingest'}))
        intake = qualify_intake(store, user, 'Compare two feasible implementations.', [], workspace_id='local',
            profile_ref=options['profile_ref'], workspace_ref=options['workspace_ref'], input_directory_ref=options['input_directory_ref'])
        store.create_run('intent-release', account_id='alice', workspace_id='local', submission={'intake_ref': intake})
        ports = [input_port('request', 'qualified-intake:field-contract:2', intake),
                 input_port('defaults', 'default-policy:field-contract:1', options['default_policy_ref'])]
        authority = dict(options['authority_ceiling'], resource_reads=[intake, store.read_record(intake)['request_ref'], options['default_policy_ref']])
        parent = factory.prepare_parent('intent-release', 'intention_compiler', [
            {'subnode_id': 'intent', 'cc': installed['intent']['pin'], 'depends_on': []},
            {'subnode_id': 'requirements', 'cc': installed['requirements']['pin'], 'depends_on': ['intent', 'intent.verifier']}],
            inputs=ports, outputs=[{'name': 'brief', 'contract_id': 'research-brief', 'version': '3.0.0', 'required': True}],
            objective='Compile qualified meaning', requirement_ids=['intent', 'brief'], limits=options['compiler_limits'],
            policy_ref=options['default_policy_ref'], configuration_ref=binding['configuration_ref'],
            template_ref=options['compiler_template_ref'], authority_ceiling=authority)
        child, _, _ = factory.bind_subnode(parent, 'intent', [ports[0]])
        contract = store.read_record(child)
        assert contract['bindings'][0]['limits']['time_s'] == contract['subnode_limits']['time_s'] == 420
        runner = CapsuleRunner(store, registry, checks, model=None, check_assets=library.check_assets)
        configuration = store.read_record(binding['configuration_ref'])
        policy = store.read_record(configuration['cc']['plan_policy_ref'])
        assert policy['aggregate_limits']['time_s'] == 10800
        runner.configure_run('intent-release', model_selection_profile_ref=binding['model_selection_profile_ref'],
            deployment_ref=binding['deployment_ref'], router=configuration['cc']['router'],
            configuration_ref=binding['configuration_ref'], run_limits=policy['aggregate_limits'])
        # Freeze the clock only: real binding, authority, reservations and start code execute.
        with patch('jiuwenswarm.research.runner.time.monotonic', return_value=1000):
            runner._run_started['intent-release'] = 1000
            budget = runner._budget_state(contract)
            assert budget['verifier_reserved']['time_s'] == 120
            assert budget['other_work_reserved']['time_s'] == 180
            assert budget['spendable']['time_s'] == 420
            ctx = runner._start_context(child, contract, {})
            await runner._await_start(ctx)
            execution = runner._executions[ctx.execution_id]
            assert execution['deadline'] - execution['started'] == 420
            protected = runner.authorize_model_context({'execution_id': ctx.execution_id, 'call_ordinal': 1})
            assert protected['limits']['time_s'] == 420
            assert protected['execution_deadline_monotonic_s'] == 1420
            # A second model call remains prohibited despite the longer wall.
            with pytest.raises(ResearchError, match='budget_exhausted'):
                runner.authorize_model_context({'execution_id': ctx.execution_id, 'call_ordinal': 2})
