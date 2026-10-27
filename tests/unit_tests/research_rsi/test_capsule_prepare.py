"""Real upload/intake/ContractFactory metadata, with controlled Library admission only."""
import asyncio
from pathlib import Path
import pytest
from types import SimpleNamespace

from deploy.m1.rsi_capsule_prepare import prepare_session
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule, public_fixtures
from jiuwenswarm.research.runner import CapsuleRunner
from tests.unit_tests.research.controlled_assets import ControlledLibraryService
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.compiler import register_compiler_capsules
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.checks import CheckRegistry

async def installed_library(path):
    store = SQLiteRunStore(path)
    registry, checks = Registry(), CheckRegistry()
    library = ControlledLibraryService(store)
    actor = Principal('operator', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
    installed = await register_compiler_capsules(registry, checks, library, store, actor, activate=True)
    library.configure_verifier(installed['verifier']['pin'])
    return store, registry, checks, library, installed, actor

from tests.unit_tests.research.test_operator_config import valid_config
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime
from tests.unit_tests.research_rsi.test_capsule_executor import grant_for


try:
    import jiuwenswarm.research_rsi.capsule_loop  # noqa: F401  (W2 loop owner)
    loop_available = True
except ImportError:
    loop_available = False


def test_prepare_appends_real_work_contexts_and_preserves_prior_records(installed_runtime, tmp_path, monkeypatch):
    # Windows lacks the production Linux O_NOFOLLOW/directory-fsync API.
    # Replace only the claim writer, preserving its exclusive no-replay action.
    import deploy.m1.rsi_capsule_prepare as preparation
    from jiuwenswarm.research_rsi.records import encoded
    def local_exclusive(path, value):
        with Path(path).open('xb') as stream:
            stream.write(encoded(value))
    monkeypatch.setattr(preparation, 'exclusive', local_exclusive)
    async def exercise():
        core, registry, checks, library, installed, _ = await installed_library(tmp_path / 'core')
        records, leases = RecordStore(tmp_path / 'records'), RecordStore(tmp_path / 'leases')
        try:
            prior = core.append_record('prior-session-marker', {'retained': True})
            opaque = core.put_blob(b'controlled binding')
            final = core.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': 'final',
                'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
                'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
            selection = core.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': 'fixed',
                'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
                'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0,
                    'output_tokens': 0, 'disclosure_scope': []}, 'alternate_model_id': None, 'policy_ref': opaque})
            configuration = valid_config()
            configuration['cc']['plan_policy_ref'] = opaque
            configuration_ref = core.append_record('approved-configuration', {'operator': configuration})
            from jiuwenswarm.research.operator_config import OperatorConfiguration
            operator = OperatorConfiguration.from_mapping(configuration, resolve_profile=core.read_record)
            exact = {'configuration_ref': configuration_ref, 'model_selection_profile_ref': selection,
                'deployment_ref': opaque, 'workspace_id': 'project', 'protected_options': {
                    'profile_ref': opaque, 'workspace_ref': opaque, 'input_directory_ref': opaque,
                    'finalization_profile_ref': final, 'compiler_template_ref': opaque}}
            runner = CapsuleRunner(core, registry, checks, model=None, check_assets=library.check_assets)
            runtime, manifest = installed_runtime
            name = 'utility.calculate'; target = registered_capsule(name)
            grant = grant_for(manifest, name)
            body = (runtime / 'source/jiuwenswarm' / target.carrier_path).read_bytes()
            declaration = {'identity': {'name': name, 'version_label': '1.0.0',
                'carrier': {'ref': target.carrier_path.removeprefix('research/')},
                'body': [{'path': target.carrier_path.removeprefix('research/'), 'sha256': grant['parent_sha256']}]}}
            visible = {'schema': 'ai4r-rsi-whole-capsule-public-context:1', 'capsule_name': name,
                'mutable_path': target.carrier_path, 'fixtures': public_fixtures(name),
                'metrics': list(target.metrics), 'labels': 'PUBLIC'}
            value = {'grant': grant, 'runtime_manifest': manifest, 'preparation_claim': str(tmp_path / 'claim.json'),
                'exact_binding_refs': exact, 'account_id': 'alice', 'input_root': str(core.input_root),
                'request_text': 'Improve the public calculate carrier only.',
                'work_capsule_refs': {key: installed[key]['declaration_ref'] for key in ('intent', 'verifier')},
                'account_root': str(tmp_path / 'accounts'), 'observed_symptom': 'Public time only'}
            result = await prepare_session(core=core, library=library, runner=runner, operator=operator,
                records=records, lease_records=leases, value=value, parent_body=body,
                parent_declaration=declaration, visible_context=visible)
            assert result['model_calls'] == 0
            assert len(result['run_contexts']) == 2
            assert core.read_record(prior) == {'retained': True}
            assert not list(core.iter_records(kinds=('model-call-start',)))
            assert records.get(result['session']['grant_ref']) == grant
            # A second target/session shares this actual Core/workspace. Its
            # uploads must not collide with the first target's public originals.
            second_name = 'utility.table_normalize'
            second_target = registered_capsule(second_name)
            second_grant = grant_for(manifest, second_name)
            second_grant['run_id'] = 'public-normalize-r2'
            second_body = (runtime / 'source/jiuwenswarm' / second_target.carrier_path).read_bytes()
            second_declaration = {'identity': {'name': second_name, 'version_label': '1.0.0',
                'carrier': {'ref': second_target.carrier_path.removeprefix('research/')},
                'body': [{'path': second_target.carrier_path.removeprefix('research/'),
                          'sha256': second_grant['parent_sha256']}]}}
            second_visible = {'schema': 'ai4r-rsi-whole-capsule-public-context:1', 'capsule_name': second_name,
                'mutable_path': second_target.carrier_path, 'fixtures': public_fixtures(second_name),
                'metrics': list(second_target.metrics), 'labels': 'PUBLIC'}
            second_value = dict(value, grant=second_grant,
                preparation_claim=str(tmp_path / 'second-claim.json'))
            second = await prepare_session(core=core, library=library, runner=runner, operator=operator,
                records=records, lease_records=leases, value=second_value, parent_body=second_body,
                parent_declaration=second_declaration, visible_context=second_visible)
            assert second['model_calls'] == 0 and len(second['run_contexts']) == 2
            assert not set(result['uploaded_ids']) & set(second['uploaded_ids'])
            assert not list(core.iter_records(kinds=('model-call-start',)))
            assert core.read_record(prior) == {'retained': True}
            for key in ('diagnosis_contract_ref', 'proposal_contract_ref'):
                contract = core.read_record(result['session'][key])
                assert contract['bindings'][0]['role'] == 'work'
                assert contract['subnode_limits']['model_calls'] == 1
            with pytest.raises(FileExistsError):
                await prepare_session(core=core, library=library, runner=runner, operator=operator,
                    records=records, lease_records=leases, value=value, parent_body=body,
                    parent_declaration=declaration, visible_context=visible)
            if loop_available:
                # Iterative loop session: one genuine work pair per iteration and
                # a grant budget derived from the loop configuration.
                from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import loop_grant
                from jiuwenswarm.research_rsi.capsule_loop import loop_run_context_ids
                from jiuwenswarm.research_rsi.targets.capsule_executor import loop_execution_budget
                loop = {'model_backend': {'kind': 'fake'}, 'max_iterations': 3, 'trials': 2}
                small = loop_grant(manifest, name, budget_pairs=1); small['run_id'] = 'public-calculate-loop'
                with pytest.raises(ValueError, match='LOOP_GRANT_EXECUTION_BUDGET_TOO_SMALL'):
                    await prepare_session(core=core, library=library, runner=runner, operator=operator,
                        records=records, lease_records=leases, value=dict(value, grant=small, loop=loop,
                        preparation_claim=str(tmp_path / 'small-claim.json')), parent_body=body,
                        parent_declaration=declaration, visible_context=visible)
                from jiuwenswarm.research_rsi.targets.capsule_executor import grant_fixtures
                cases = len(grant_fixtures(small))  # public + public_extended + held_out
                assert cases > len(public_fixtures(name))
                needed = loop_execution_budget(cases, max_iterations=3, trials=2)
                assert needed == cases * (3 + 2 * 3)
                grant3 = dict(small, max_executions=needed, run_id='public-calculate-loop-2')
                looped = await prepare_session(core=core, library=library, runner=runner, operator=operator,
                    records=records, lease_records=leases, value=dict(value, grant=grant3, loop=loop,
                    preparation_claim=str(tmp_path / 'loop-claim.json')), parent_body=body,
                    parent_declaration=declaration, visible_context=visible)
                session = looped['session']
                assert len(session['loop']['contracts']) == 2 and len(looped['run_contexts']) == 6
                assert set(looped['run_contexts']) == loop_run_context_ids(session)
                for pair in session['loop']['contracts']:
                    for ref in pair.values():
                        contract = core.read_record(ref)
                        assert contract['bindings'][0]['role'] == 'work' and contract['subnode_limits']['model_calls'] == 1
                assert not list(core.iter_records(kinds=('model-call-start',)))
        finally:
            records.close(); leases.close(); core.close()
    asyncio.run(exercise())
