"""Real compiler/runner/gates/freeze with controlled transport and model content."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import Binder, expand_selectors
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.planning import PlanningCoordinator
from jiuwenswarm.research.state import json_bytes
from jiuwenswarm.research.unified_planning import integrated_plan_policy
from tests.unit_tests.research.test_compiler import controlled_compiler
from tests.unit_tests.research.test_typed_planner import FIXTURES


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['valid', 'repair', 'graph_repair', 'exhausted', 'verifier_reject'])
async def test_planner_through_independent_gate_and_freeze(tmp_path, monkeypatch, mode):
    generated = []
    def model(prompt):
        payload = json.loads(prompt.split('<subject_payload>\n', 1)[1].split('\n</subject_payload>', 1)[0])['fixture_planner_payload']
        generated.append(copy.deepcopy(payload))
        if mode == 'exhausted' or mode == 'repair' and len(generated) == 1:
            return '{invalid'
        source = expand_selectors(json.loads(Path('jiuwenswarm/research_assets/planner/static-template.json').read_text()), payload['brief'])
        source.pop('template_name')
        source.update(schema_version='3.0.0', plan_source='planned', topic_hints=[], notes='', **{
            key: payload[key] for key in ('brief_ref', 'library_snapshot_ref', 'resource_inventory_ref', 'policy_ref')})
        entries = {e['cc_name']: e for e in payload['library_snapshot']['entries']}
        for node in source['nodes']:
            entry = entries[node['cc']['cc_name']]
            node['cc'] = {key: entry[key] for key in ('cc_name', 'cc_version', 'declaration_sha256')}
            node['limits'] = {key: min(node['limits'][key], entry['max_limits'][key]) for key in node['limits']}
        source['limits'] = {'time_s': sum(n['limits']['time_s'] for n in source['nodes']),
                            'model_calls': sum(n['limits']['model_calls'] for n in source['nodes']),
                            'memory_mb': max(n['limits']['memory_mb'] for n in source['nodes'])}
        if mode == 'graph_repair' and len(generated) == 1:
            source['nodes'][0]['predecessors'] = ['delivery']
        return json.dumps(source)

    async def native(self, payload, *, invoke, instructions):
        # Use the real scoped audited model port, not a direct worker shortcut.
        return await invoke(json.dumps({'fixture_planner_payload': payload}), system=instructions)
    monkeypatch.setattr('jiuwenswarm.research.native.NativePlanner.propose', native)
    app = await controlled_compiler(tmp_path, planner_model=model, run_model_calls=12, review_reject_node='planner' if mode == 'verifier_reject' else None)
    store, library, actor = app['store'], app['library'], app['actor']
    try:
        library.configure_verifier(app['installed']['verifier']['pin'])
        for asset in build_research_assets(store).values():
            library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
            admission_ref = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=16384)
            admission = store.read_record(admission_ref)
            assert admission['status'] == 'admitted', admission['reasons']
            pin = admission['cc']
            library.set_standing(pin['cc_name'], pin['cc_version'], 'active', actor, reason='Controlled integration fixture')
        snapshot_ref = library.snapshot()
        resources = json.loads((FIXTURES / 'resource_inventory.json').read_text())
        for row in resources['resources']:
            if row['ref'] is not None:
                row['ref'] = store.put_blob(('Controlled qualified source bytes: ' + row['resource_key']).encode())
        resources_ref = store.put_record('resource-inventory', resources)
        policy_ref = store.put_record('plan-policy', integrated_plan_policy())
        protected = app['protected']
        authority = {'network': 'none', 'network_allowlist': [], 'resource_reads': [], 'write_roots': [], 'tools': ['deepsearch']}
        coordinator = PlanningCoordinator(store, app['runner'], app['factory'],
            planner_pin=app['installed']['planner']['pin'], template_ref=store.put_blob(b'controlled template'),
            node_limits={'time_s': 600, 'model_calls': 3, 'memory_mb': 256}, authority_ceiling=authority)
        outcome = await coordinator.run('run:compiler', app['brief_ref'], snapshot_ref, resources_ref, policy_ref, protected)
        assert len(generated) == (2 if mode in ('repair', 'graph_repair', 'exhausted') else 1), (outcome, [r['record'] for r in store.iter_records(kinds=('invocation-observation',)) if r['record']['node_id'] == 'planner'])
        assert len(list(store.iter_records(kinds=('planner_attempt',)))) == len(generated)
        if mode in ('exhausted', 'verifier_reject'):
            assert not outcome['accepted']
            assert not store.accepted_outputs('run:compiler', 'planner')
            assert not list(store.iter_records(kinds=('run-plan',)))
            return
        assert outcome['accepted'], outcome
        assert app['calls'].count('verifier') == 3  # compiler two; planner one
        bounds = store.put_blob(json_bytes({'schema': 'ai4r-search-bounds:1', 'id': 'bounds',
            'connectors': ['local_documents'], 'max_queries': 2, 'max_hits_per_query': 3}))
        binder = Binder(store, library, app['checks'], search_bounds_ref=bounds)
        run_inputs = {row['resource_key']: row['ref'] for row in resources['resources'] if row['ref']}
        authority['resource_reads'] = list(run_inputs.values())
        plan_ref = binder.freeze(outcome['proposal_ref'], app['brief_ref'], snapshot_ref, resources_ref,
            policy_ref, protected['configuration_ref'], plan_source='planned', acceptance_ref=outcome['decision_ref'],
            run_inputs=run_inputs, authority_ceiling=authority)
        plan = store.read_record(plan_ref, contract_id='run-plan')
        assert len(plan['nodes']) == 7
        binder.validate_acceptance(plan)
        # Status must distinguish the Planner's extra catalog input from the
        # four resources independently rechecked by Binder after acceptance.
        from jiuwenswarm.research.status_stage import observed_stage
        run = store.get_run('run:compiler')
        assert observed_stage(store, run, store.node_states(run['id']),
                              list(store.iter_records(run_id=run['id']))) == 'planner'
        # Source tampering after acceptance cannot borrow the accepted gate.
        source = store.read_record(outcome['proposal_ref'])
        source['nodes'][0]['cc']['declaration_sha256'] = 'f' * 64
        changed = store.put_blob(json_bytes(source))
        with pytest.raises(ResearchError):
            binder.freeze(changed, app['brief_ref'], snapshot_ref, resources_ref, policy_ref,
                protected['configuration_ref'], plan_source='planned', acceptance_ref=outcome['decision_ref'])
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('planner_kind', ['core', 'paper'])
async def test_each_admitted_planner_binds_its_declared_catalog_before_dispatch(tmp_path, monkeypatch, planner_kind):
    from jiuwenswarm.research.capsules.paper_assets import build_paper_assets
    from jiuwenswarm.research.planner_catalog import SCHEMA

    app = await controlled_compiler(tmp_path)
    store, library, actor = app['store'], app['library'], app['actor']
    try:
        library.configure_verifier(app['installed']['verifier']['pin'])
        pin = app['installed']['planner']['pin']
        if planner_kind == 'paper':
            asset = build_paper_assets(store)['paper_planner']
            library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
            admission = store.read_record(await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=256))
            assert admission['status'] == 'admitted', admission['reasons']
            pin = admission['cc']
            library.set_standing(pin['cc_name'], pin['cc_version'], 'active', actor, reason='Controlled legacy Planner compatibility')
        snapshot_ref = library.snapshot()
        resources_ref = store.put_record('resource-inventory', {'schema_version': '1.0.0', 'id': 'empty', 'resources': []})
        policy_ref = store.put_record('plan-policy', integrated_plan_policy())

        def stop_after_real_binding(parent_ref):
            parent = store.read_record(parent_ref)
            ports = {port['name']: port for port in parent['inputs']}
            assert ports['capsule_contracts']['contract_id'] == SCHEMA
            catalog = store.read_record(ports['capsule_contracts']['artifact_refs'][0])
            assert catalog['library_snapshot_ref'] == snapshot_ref
            raise ResearchError('bound_before_dispatch', 'Intentional test boundary after real Factory binding')

        monkeypatch.setattr(app['runner'], 'prepare_node_check_plan', stop_after_real_binding)
        coordinator = PlanningCoordinator(store, app['runner'], app['factory'], planner_pin=pin,
            template_ref=store.put_blob(b'controlled template'),
            node_limits={'time_s': 600, 'model_calls': 3, 'memory_mb': 256},
            authority_ceiling={'network': 'none', 'network_allowlist': [], 'resource_reads': [], 'write_roots': [], 'tools': []})
        with pytest.raises(ResearchError, match='bound_before_dispatch'):
            await coordinator.run('run:compiler', app['brief_ref'], snapshot_ref, resources_ref, policy_ref, app['protected'])
        assert not list(store.iter_records(kinds=('planner_attempt',)))
        assert app['calls'] == ['worker', 'verifier', 'worker', 'verifier']
    finally:
        store.close()
