import copy
import json
from contextlib import closing
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import plan_checks
from jiuwenswarm.research.capability_planning import capability_plan_policy, is_capability_policy, layout_issues
from jiuwenswarm.research.capsule_extensions.catalog import candidates, register_active
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
        {'selector': 'all_deliverables', 'node_ids': ['work_1']}]
    library['entries'] = library['entries'][:2]
    for node, entry in zip(nodes, library['entries']):
        entry.update(**node['cc'], selectable_by_planner=True, input_ports=[],
            output_ports=[{'name': 'result', 'artifact_type': 'work_packet', 'schema_ref': 'urn:ai4r:work-packet:1.0.0', 'required': True}],
            resource_needs=[], max_limits=node['limits'])
    return source, brief, library, resources


def test_open_dag_preserves_old_policy_and_rejects_cycles_and_incomplete_coverage():
    values = graph()
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    assert all(r['outcome'] == 'PASS' for r in results), results
    from jiuwenswarm.research.unified_planning import integrated_plan_policy
    _, results = plan_checks(*values, integrated_plan_policy(), plan_source='static')
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
        assert 'workflow.capability_planner' in assets
        for name, (asset, _) in assets.items():
            declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
            results = declaration_checks(declaration, {k: store.read_blob(v) for k, v in asset['body_refs'].items()})
            assert all(r['outcome'] == 'PASS' for r in results), (name, results)
            validate('check-bundle', store.read_record(asset['bundle_ref']))
            validate('checking-profile', store.read_record(asset['profile_ref']))
        library = LibraryService(store)
        assert register_active(Registry(), CheckRegistry(), library, store) == {}
        assert library.entries() == []
        receipt = prepare_requests(store, 'workflow.capability_planner')
        assert receipt['status'] == 'candidate_only'
        assert library.entries() == []


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
