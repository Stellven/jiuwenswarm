"""Controlled candidates exercise assembly/repair; they do not prove model quality."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.binding import expand_selectors, plan_checks
from jiuwenswarm.research.capsules import planner
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.planner_catalog import capture_catalog, verify_captured_catalog
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.runner import CapsuleArtifacts
from jiuwenswarm.research.run_input_types import typed_resource
from jiuwenswarm.research.unified_planning import integrated_plan_policy, legacy_integrated_plan_policy
from tests.unit_tests.research.test_budget_ceiling import installed_library
from tests.unit_tests.research.test_capability_extensions import graph

FIXTURES = Path('tests/fixtures/research/planning')


def assembled():
    source, brief, library, resources = graph()
    source = expand_selectors(source, brief)
    source.pop('template_name')
    refs = {key: {'id': key, 'sha256': '0' * 64} for key in
            ('brief_ref', 'library_snapshot_ref', 'resource_inventory_ref', 'policy_ref')}
    source.update(schema_version='3.0.0', plan_source='planned', topic_hints=[], notes='', **refs)
    return source, brief, library, resources


def test_core_policy_assembles_generic_nodes_and_keeps_legacy_placement():
    source, brief, library, resources = assembled()
    # Input order is deliberately unrelated to execution order.
    source['nodes'].reverse()
    _, results = plan_checks(source, brief, library, resources, integrated_plan_policy(), plan_source='planned')
    assert all(row['outcome'] == 'PASS' for row in results), results
    _, results = plan_checks(source, brief, library, resources, legacy_integrated_plan_policy(), plan_source='planned')
    assert any(row['outcome'] == 'FAIL' for row in results)


def test_scientific_graph_can_include_an_additional_admitted_capsule():
    source = json.loads((FIXTURES / 'static_template.json').read_text())
    brief = json.loads((FIXTURES / 'lifecycle_research_brief.json').read_text())
    library = json.loads((FIXTURES / 'library_snapshot.json').read_text())
    resources = json.loads((FIXTURES / 'resource_inventory.json').read_text())
    resources['resources'] = [typed_resource(row) for row in resources['resources']]
    extra = copy.deepcopy(source['nodes'][0])
    extra.update(node_id='support', cc=dict(extra['cc'], cc_name='utility.support'),
        objective='Supporting artifact for the research deliverable')
    entry = copy.deepcopy(next(e for e in library['entries'] if e['cc_name'] == 'research.search'))
    entry.update(cc_name='utility.support')
    library['entries'].append(entry)
    source['nodes'].append(extra)
    source['nodes'][-2]['predecessors'].append('support')
    source['coverage'][0]['node_ids'].append('support')
    _, results = plan_checks(source, brief, library, resources, integrated_plan_policy(), plan_source='static')
    assert all(row['outcome'] == 'PASS' for row in results), results


def test_planner_events_cannot_read_or_export_foreign_artifacts(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        own = store.put_blob(b'candidate')
        foreign = store.put_blob(b'private other task')
        scope = {'run_id': 'run:test', 'node_id': 'planner', 'subnode_id': 'planner', 'attempt_id': 'a1'}
        events = CapsuleArtifacts(store, [own], scope=scope)
        record = {'ordinal': 1, 'candidate_ref': own, 'diagnostics_ref': foreign, 'advisory': True, 'repair_requested': True}
        with pytest.raises(ResearchError): events.append_record('planner_attempt', record)
        record['diagnostics_ref'] = own
        captured = store.read_record(events.append_record('planner_attempt', record))
        assert captured['run_id'] == 'run:test'
        for change in ({'ordinal': 3}, {'advisory': False}, {'run_id': 'other'}):
            with pytest.raises(ResearchError): events.append_record('planner_attempt', dict(record, **change))
        worker = CapsuleArtifacts(store, [own], scope=dict(scope, node_id='other'))
        with pytest.raises(ResearchError): worker.append_record('planner_attempt', record)
    finally:
        store.close()


@pytest.mark.parametrize('fault,check', [
    ('cycle', 'acyclicity'), ('pin', 'library_membership'), ('ports', 'port_type_compatibility'),
    ('coverage', 'brief_coverage'), ('checks', 'mandatory_check_bundle_present'),
    ('effect', 'effects_within_policy'), ('budget', 'budget_ceilings'), ('resource', 'resource_feasibility'),
    ('evidence', 'brief_coverage'), ('science', 'delivery_leaf_coverage')])
def test_core_policy_blocks_bad_assembled_graphs(fault, check):
    source, brief, library, resources = assembled()
    if fault == 'cycle': source['nodes'][0]['predecessors'] = ['work_1']
    if fault == 'pin': source['nodes'][0]['cc']['declaration_sha256'] = 'f' * 64
    if fault == 'ports': source['nodes'][0]['outputs'][0]['artifact_type'] = 'invented'
    if fault == 'coverage': source['coverage'] = []
    if fault == 'checks': library['entries'][0]['check_pins'] = None
    if fault == 'effect': library['entries'][0]['effect_class'] = 'irreversible'
    if fault == 'budget': source['nodes'][0]['limits']['model_calls'] = 999
    if fault == 'resource': library['entries'][0]['resource_needs'] = [{'resource_key': 'missing', 'mode': 'read', 'min_quantity': None}]
    if fault == 'evidence': source['coverage'] = [c for c in source['coverage'] if c['item_kind'] != 'evidence_obligation']
    if fault == 'science':
        source['nodes'][0]['cc']['cc_name'] = library['entries'][0]['cc_name'] = 'research.benchmark'
    _, results = plan_checks(source, brief, library, resources, integrated_plan_policy(), plan_source='planned')
    assert any(row['check_id'] == check and row['outcome'] == 'FAIL' for row in results), results


@pytest.mark.asyncio
async def test_catalog_includes_exact_complete_contracts_and_detects_tampering(tmp_path):
    store, _, _, library, installed, _ = await installed_library(tmp_path, scientific=True)
    try:
        snapshot_ref = library.snapshot()
        snapshot = store.read_record(snapshot_ref)
        catalog = store.read_record(capture_catalog(store, library, snapshot_ref))
        verify_captured_catalog(store, catalog, snapshot, snapshot_ref)
        assert len(catalog['capsules']) == 7
        assert all(item['declaration']['identity']['summary'] for item in catalog['capsules'])
        assert all(item['cc']['cc_name'] != 'research.planner' for item in catalog['capsules'])
        assert installed['planner']['pin']['cc_name'] == 'research.planner'
        for kind in ('text', 'port', 'omission', 'duplicate', 'snapshot'):
            modified = copy.deepcopy(catalog)
            if kind == 'text': modified['capsules'][0]['declaration']['identity']['summary'] = 'Forged capability'
            if kind == 'port': modified['capsules'][0]['declaration']['ports']['inputs'][0]['artifact_type'] = 'forged'
            if kind == 'omission': modified['capsules'].pop()
            if kind == 'duplicate': modified['capsules'].append(modified['capsules'][0])
            if kind == 'snapshot': modified['library_snapshot_ref']['sha256'] = 'f' * 64
            with pytest.raises(ResearchError): verify_captured_catalog(store, modified, snapshot, snapshot_ref)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,expected_calls', [('good', 1), ('repair', 2), ('exhausted', 2), ('runtime', 1), ('infeasible', 1)])
async def test_worker_repair_is_bounded_recorded_and_not_an_acceptance(tmp_path, monkeypatch, mode, expected_calls):
    source, brief, library, resources = assembled()
    store = SQLiteRunStore(tmp_path)
    refs = {}
    # A controlled model/worker fixture; actual catalog source integrity has its
    # separate host test above. This fixture isolates the retry boundary.
    monkeypatch.setattr('jiuwenswarm.research.planner_catalog.verify_catalog', lambda *args: None)
    inputs = {'brief': brief, 'library_snapshot': library, 'resource_inventory': resources,
              'plan_policy': integrated_plan_policy(), 'capsule_contracts': {'fixture': True}}
    for key, value in inputs.items(): refs[key] = store.put_blob(json.dumps(value).encode())
    source.update(**{field: refs[port] for field, port in
        [('brief_ref', 'brief'), ('library_snapshot_ref', 'library_snapshot'), ('resource_inventory_ref', 'resource_inventory'), ('policy_ref', 'plan_policy')]})
    calls = []
    class ControlledNative:
        async def propose(self, payload, **kwargs):
            calls.append(copy.deepcopy(payload))
            assert payload['capsule_contracts'] == inputs['capsule_contracts']
            if mode == 'runtime': raise ResearchError('model_access_unavailable', 'Controlled authentication failure')
            if mode == 'infeasible': return 'INFEASIBLE: no available implementation'
            if mode == 'exhausted' or mode == 'repair' and len(calls) == 1: return '{broken'
            return json.dumps(source)
    monkeypatch.setattr(planner, 'NativePlanner', ControlledNative)
    ctx = SimpleNamespace(store=store, input_ref=refs.__getitem__, model=None, record_host=lambda *args: None)
    try:
        if mode in ('runtime', 'infeasible'):
            with pytest.raises(ResearchError): await planner.execute(ctx, inputs)
        else:
            result = await planner.execute(ctx, inputs)
            assert set(result) == {'plan_proposal'}
        assert len(calls) == expected_calls
        attempts = list(store.iter_records(kinds=('planner_attempt',)))
        assert len(attempts) == (0 if mode == 'runtime' else expected_calls)
        assert all(a['record']['advisory'] for a in attempts)
        if expected_calls == 2:
            assert calls[1]['repair']['validation_errors']
            assert calls[1]['brief'] == calls[0]['brief']
            assert store.read_blob(attempts[0]['record']['candidate_ref']) == b'{broken'
    finally:
        store.close()
