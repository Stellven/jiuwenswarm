"""Real admitted consumer must guard before granting or claiming work."""
import copy

import pytest

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.contracts import ResearchError
from tests.unit_tests.research.test_evaluation_authority import source_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize('phase', ['prepare', 'execute'])
async def test_admitted_consumer_rejects_sibling_tool_before_grant_or_start_claim(tmp_path, phase):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        admitted = provider.resources.admitted
        source_ref = provider.assets['cases'][0]['binding_ref']
        source = store.read_record(source_ref)
        parent = store.read_record(source['node_contract_ref'])
        composition = admitted.resources.composition
        factory = ContractFactory(store, admitted.library, verifier_pin=composition.installed['verifier']['pin'],
            finalization_profile_ref=parent['checking_profile_ref'])
        ceiling = copy.deepcopy(parent['authority_ceiling']); ceiling['tools'] = ['deepsearch']
        pin = store.read_record(source['template_ref'])['cc']
        parent_ref = factory.prepare_parent(source['run_id'], 'admitted_union',
            [{'subnode_id': source['subnode_id'], 'cc': pin, 'depends_on': []}],
            inputs=source['inputs'], outputs=source['outputs'], objective=source['objective'],
            requirement_ids=source['requirement_ids'], limits=parent['node_limits'], policy_ref=parent['policy_ref'],
            configuration_ref=parent['configuration_ref'], template_ref=parent['template_ref'], authority_ceiling=ceiling)
        good_ref, good_plan_ref, _ = factory.bind_subnode(parent_ref, source['subnode_id'], source['inputs'])
        child = store.read_record(good_ref)
        assert child['bindings'][0]['effective_authority']['tools'] == []
        child['id'] += ':forged-tool'; child['bindings'][0]['effective_authority']['tools'] = ['deepsearch']
        forged_ref = store.put_record('subnode-execution-contract', child)
        plan = store.read_record(good_plan_ref); plan['id'] += ':forged-tool'; plan['contract_ref'] = forged_ref
        forged_plan_ref = store.put_record('bound-check-plan', plan)
        grant_ref = None
        if phase == 'execute':
            # A captured corrupt grant is a negative fault. It must never grant
            # execution merely because the private kind/body is parseable.
            original_grant = admitted.prepare(good_ref, good_plan_ref, semantic_review=False)
            grant = store.read_record(original_grant); grant['id'] += ':forged-tool'
            grant['contract_ref'] = forged_ref; grant['check_plan_ref'] = forged_plan_ref
            grant_ref = store.append_record('admitted-measurement-grant', grant)
        names = ('metadata', 'attempts', 'model_calls', 'tool_calls')
        before = {name: [tuple(row) for row in store.connection.execute('SELECT * FROM ' + name)] for name in names}
        grants_before = [row['ref'] for row in store.iter_records(kinds=('admitted-measurement-grant',))]
        starts_before = [row['ref'] for row in store.iter_records(kinds=('invocation-budget-reservation', 'invocation-observation'))]
        error = None
        try:
            if phase == 'prepare': admitted.prepare(forged_ref, forged_plan_ref, semantic_review=False)
            else: await admitted.execute(grant_ref)
        except BaseException as caught:
            error = caught
        assert isinstance(error, ResearchError), error
        assert {name: [tuple(row) for row in store.connection.execute('SELECT * FROM ' + name)] for name in names} == before
        assert [row['ref'] for row in store.iter_records(kinds=('admitted-measurement-grant',))] == grants_before
        assert [row['ref'] for row in store.iter_records(kinds=('invocation-budget-reservation', 'invocation-observation'))] == starts_before
        assert not prompts
    finally:
        store.close()
