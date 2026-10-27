"""Builder tool authority comes from the admitted declaration, not from prose or defaults."""
import pytest

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.compiler import input_port
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.runner import BoundExecutorAccess, CapsuleRunner
from tests.unit_tests.research.test_budget_ceiling import installed_library


async def builder_contract(tmp_path, *, ceiling_tools):
    store, registry, checks, library, installed, _ = await installed_library(tmp_path, scientific=True)
    opaque = store.put_blob(b'controlled protected binding')
    profile = store.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': 'final',
        'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
        'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
    factory = ContractFactory(store, library, verifier_pin=installed['verifier']['pin'], finalization_profile_ref=profile)
    declaration = store.read_record(installed['builder']['declaration_ref'])
    assert declaration['identity']['version_label'] == 'm1-18'
    ports = [input_port(p['name'], p['schema_ref'], store.put_blob(b'input ' + p['name'].encode()))
             for p in declaration['ports']['inputs'] if p['required']]
    store.create_run('builder-run', account_id='alice', workspace_id='project', submission={})
    limits = {'time_s': 1200, 'model_calls': 40, 'memory_mb': 4096}
    parent = factory.prepare_parent('builder-run', 'builder', [{'subnode_id': 'builder', 'cc': installed['builder']['pin'], 'depends_on': []}],
        inputs=ports, outputs=[{'name': p['name'], 'contract_id': p['schema_ref'], 'version': ContractFactory._version(p['schema_ref']), 'required': p['required']}
                               for p in declaration['ports']['outputs']],
        objective='Builder authority', requirement_ids=['builder'], limits=limits, policy_ref=opaque, configuration_ref=opaque,
        template_ref=opaque, authority_ceiling={'network': 'allowlist', 'network_allowlist': ['approved_package_index'],
            'resource_reads': [r for p in ports for r in p['artifact_refs']], 'write_roots': ['/workspace/poc'], 'tools': ceiling_tools})
    contract_ref, _, _ = factory.bind_subnode(parent, 'builder', ports)
    contract = store.read_record(contract_ref)
    selection = store.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': 'fixed', 'policy_mode': 'fixed_baseline',
        'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {}, 'selection_allowance': {'enabled': False, 'deployment_ref': None,
        'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []}, 'alternate_model_id': None, 'policy_ref': opaque})
    runner = CapsuleRunner(store, registry, checks, model=None, check_assets=library.check_assets)
    runner.configure_run('builder-run', model_selection_profile_ref=selection, deployment_ref=opaque,
        router={'enabled': False, 'profile_ref': None, 'deadline_s': 30}, configuration_ref=opaque, run_limits=limits)
    return store, runner, contract_ref, contract


def activate(runner, ctx):
    # The native broker start needs the root executor; the authorization under test
    # starts after it, so only the phase transition is stood in for here.
    runner._executions[ctx.execution_id]['phase'] = 'active'


class Facade:
    def __init__(self): self.calls = []
    async def builder_action(self, *args, **kwargs):
        self.calls.append(kwargs)
        return {'ok': True}


@pytest.mark.asyncio
async def test_real_builder_contract_authorizes_builder_action_and_refuses_undeclared_tool(tmp_path):
    store, runner, ref, contract = await builder_contract(tmp_path, ceiling_tools=['deepsearch', 'codesearch', 'builder_action'])
    assert contract['bindings'][0]['effective_authority']['tools'] == ['builder_action']
    ctx = runner._start_context(ref, contract, {})
    activate(runner, ctx)
    facade, seen = Facade(), []
    class Artifacts:
        def _grant(self, value): seen.append(value)
    access = BoundExecutorAccess(facade, Artifacts(), ctx._before_tool)
    assert await access.builder_action(contract, action='list_files', arguments={}, ordinal=1, model_ordinal=1) == {'ok': True}
    assert facade.calls, 'authorized action must reach the executor'
    for undeclared in ('deepsearch', 'codesearch', 'arxiv'):
        with pytest.raises(ResearchError, match='tool_authorization'):
            runner.authorize_tool_call({'execution_id': ctx.execution_id, 'tool_ordinal': 9, 'operation': undeclared})
    store.close()


@pytest.mark.asyncio
async def test_builder_action_is_not_granted_when_the_parent_ceiling_withholds_it(tmp_path):
    store, runner, ref, contract = await builder_contract(tmp_path, ceiling_tools=[])
    assert contract['bindings'][0]['effective_authority']['tools'] == []
    ctx = runner._start_context(ref, contract, {})
    activate(runner, ctx)
    with pytest.raises(ResearchError, match='tool_authorization'):
        ctx._before_tool('builder_action')
    store.close()


def test_non_builder_declarations_never_gain_builder_action():
    import copy
    from jiuwenswarm.research.binding import declaration_authority_ceiling
    from jiuwenswarm.research.capsules.assets import source_metadata
    parent = {'network': 'none', 'network_allowlist': [], 'resource_reads': [], 'write_roots': [], 'tools': ['builder_action', 'deepsearch', 'codesearch']}
    for stage in ('search', 'hypothesis', 'screening'):
        declaration = copy.deepcopy(source_metadata()[stage]['declaration'])
        declaration['budget']['per_call']['tool_calls'] = 5
        assert 'builder_action' not in declaration_authority_ceiling(declaration, parent, role='work')['tools']
