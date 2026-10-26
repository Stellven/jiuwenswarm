import copy
import json
from contextlib import closing
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import plan_checks
from jiuwenswarm.research.capability_planning import capability_plan_policy, is_capability_policy, layout_issues
from jiuwenswarm.research.capsule_extensions.catalog import candidates, historical_candidates, register_active
from jiuwenswarm.research.capsule_extensions.operator import prepare_requests
from jiuwenswarm.research.capsule_extensions.packet import inherited, output_packet, validate_packet
from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.checks.admission import declaration_checks
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore

FIXTURES = Path(__file__).parents[2] / 'fixtures/research/planning'


def packet():
    return {'schema_version': '1.0.0', 'data': {}, 'files': [], 'trust': 'provisional', 'provenance': [], 'limitations': []}


def graph():
    source = json.loads((FIXTURES / 'static_template.json').read_text())
    library = json.loads((FIXTURES / 'library_snapshot.json').read_text())
    brief = json.loads((FIXTURES / 'lifecycle_research_brief.json').read_text())
    resources = json.loads((FIXTURES / 'resource_inventory.json').read_text())
    # Two unrelated compatible capabilities, no scientific stages or fixed order.
    nodes = source['nodes'][:2]
    source['nodes'] = nodes
    for i, node in enumerate(nodes):
        node['node_id'] = 'work_' + str(i)
        node['cc']['cc_name'] = 'utility.work_' + str(i)
        node['predecessors'] = [] if i == 0 else ['work_0']
        node['inputs'] = []
        node['outputs'] = [{'name': 'result', 'artifact_type': 'work_packet', 'required': True}]
        node['requirement_ids'] = ['all_mandatory_requirements']
        node['deliverable_ids'] = ['all_deliverables'] if i == 1 else []
    source['coverage'] = [
        {'selector': 'all_mandatory_requirements', 'node_ids': ['work_0', 'work_1']},
        {'selector': 'all_deliverables', 'node_ids': ['work_1']},
        {'selector': 'all_evidence_obligations', 'node_ids': ['work_0', 'work_1']}]
    library['entries'] = library['entries'][:2]
    for node, entry in zip(nodes, library['entries']):
        entry.update(**node['cc'], selectable_by_planner=True, input_ports=[],
            output_ports=[{'name': 'result', 'artifact_type': 'work_packet', 'schema_ref': 'urn:ai4r:work-packet:1.0.0', 'required': True}],
            resource_needs=[], max_limits=node['limits'])
    return source, brief, library, resources


def test_open_dag_preserves_legacy_policy_and_rejects_cycles_and_incomplete_coverage():
    values = graph()
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    assert all(r['outcome'] == 'PASS' for r in results), results
    from jiuwenswarm.research.unified_planning import legacy_integrated_plan_policy
    _, results = plan_checks(*values, legacy_integrated_plan_policy(), plan_source='static')
    assert any(r['check_id'] == 'delivery_leaf_coverage' and r['outcome'] == 'FAIL' for r in results)
    values[0]['nodes'][0]['predecessors'] = ['work_1']
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    assert any(r['check_id'] == 'acyclicity' and r['outcome'] == 'FAIL' for r in results)


def test_policy_is_exact_and_science_cannot_bypass_evaluation():
    value = capability_plan_policy()
    validate('plan-policy', value)
    value['max_nodes'] = 11
    with pytest.raises(ResearchError):
        is_capability_policy(value)
    source, *_ = graph()
    source['nodes'][0]['cc']['cc_name'] = 'research.benchmark'
    assert layout_issues(source)
    source['nodes'] = [dict(source['nodes'][0], cc={'cc_name': 'research.generalist'}) for _ in range(3)]
    assert layout_issues(source)


def test_candidates_are_pinned_valid_and_never_auto_admitted(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        assets = candidates(store)
        assert 'workflow.capability_planner' not in assets
        for name, (asset, _) in assets.items():
            declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
            results = declaration_checks(declaration, {k: store.read_blob(v) for k, v in asset['body_refs'].items()})
            assert all(r['outcome'] == 'PASS' for r in results), (name, results)
            validate('check-bundle', store.read_record(asset['bundle_ref']))
            validate('checking-profile', store.read_record(asset['profile_ref']))
        library = LibraryService(store)
        assert register_active(Registry(), CheckRegistry(), library, store) == {}
        assert library.entries() == []
        with pytest.raises(ResearchError):
            prepare_requests(store, 'workflow.capability_planner')
        assert library.entries() == []


def test_historical_manifests_are_hash_checked_without_bypassing_current_admission(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        historical = historical_candidates(store)
        assert set(historical) == {(name, 'm1-1') for name in ('utility.table_normalize',
            'utility.calculate', 'utility.markdown_report', 'research.generalist')}
        active = candidates(store)
        for name, version in historical:
            old_asset, _ = historical[(name, version)]
            declaration = store.read_record(old_asset['declaration_ref'], contract_id='capsule-declaration')
            assert declaration['identity']['version_label'] == version
            assert name in active
        # The archived v1 worker/check bytes remain readable, but their legacy
        # packet_schema identifier does not pass the current independent output
        # schema admission rule. Startup must not grandfather that mismatch.
        legacy_asset, _ = historical[('utility.calculate', 'm1-1')]
        with pytest.raises(ResearchError, match='Every output needs its independent blocking schema check'):
            LibraryService(store)._validate_association(legacy_asset['declaration_ref'],
                legacy_asset['bundle_ref'], legacy_asset['profile_ref'])


def test_packet_paths_hashes_limits_and_low_trust_propagation():
    original = packet()
    ref = {'id': 'task', 'sha256': 'a' * 64}
    result = output_packet(original, files=[{'path': 'notes/result.txt', 'text': 'hello'}], low_trust=True, provenance=ref)
    assert inherited(original, result)
    assert output_packet(result, data={'answer': 2})['trust'] == 'low'
    modified = copy.deepcopy(result)
    modified['trust'] = 'provisional'
    assert not inherited(result, modified)
    for path in ['../x', '/x', 'C:/x', 'a\\x', 'a//x', './x']:
        with pytest.raises(ResearchError):
            output_packet(original, files=[{'path': path, 'text': 'x'}])
    result['files'][0]['text'] = 'tampered'
    with pytest.raises(ResearchError):
        validate_packet(result)


@pytest.mark.asyncio
async def test_optional_checks_are_available_to_existing_protected_calibration(tmp_path):
    from jiuwenswarm.research.checks.calibration_runtime import prepare_calibration_checks
    with closing(SQLiteRunStore(tmp_path)) as store:
        registry = CheckRegistry()
        fixed = await prepare_calibration_checks(store, registry)
        assert 'workflow.capability_planner' not in fixed  # not a fixed POC corpus stage
        asset = fixed['planner']
        bundle = store.read_record(asset['bundle_ref'])
        assert bundle['bundle_id'] in registry._bundles
        assert LibraryService(store).entries() == []


def test_new_policy_requires_evidence_assignments_and_exact_future_port_schemas():
    values = graph()
    values[0]['coverage'] = [r for r in values[0]['coverage'] if r.get('selector') != 'all_evidence_obligations']
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    assert any(r['check_id'] == 'brief_coverage' and r['outcome'] == 'FAIL' for r in results)
    values = graph()
    values[0]['nodes'][1]['inputs'] = [{'name': 'packet', 'artifact_type': 'work_packet', 'required': True,
        'source_kind': 'future_output', 'run_input_key': None, 'accepted_ref': None,
        'future': {'producer_node': 'work_0', 'port': 'result', 'artifact_type': 'work_packet'}}]
    values[2]['entries'][1]['input_ports'] = [{'name': 'packet', 'artifact_type': 'work_packet',
        'required': True, 'schema_ref': 'urn:ai4r:work-packet:1.0.0'}]
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    assert all(r['outcome'] == 'PASS' for r in results), results
    values[2]['entries'][1]['input_ports'][0]['schema_ref'] = 'incompatible-schema'
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    assert any(r['check_id'] == 'port_type_compatibility' and r['outcome'] == 'FAIL' for r in results)
