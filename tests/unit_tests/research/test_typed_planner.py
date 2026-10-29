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
              'plan_policy': integrated_plan_policy(), 'capsule_contracts': {'schema_version': '1.0.0', 'library_snapshot_ref': None, 'capsules': []}}
    for key, value in inputs.items(): refs[key] = store.put_blob(json.dumps(value).encode())
    source.update(**{field: refs[port] for field, port in
        [('brief_ref', 'brief'), ('library_snapshot_ref', 'library_snapshot'), ('resource_inventory_ref', 'resource_inventory'), ('policy_ref', 'plan_policy')]})
    calls = []
    class ControlledNative:
        async def propose(self, payload, **kwargs):
            calls.append(copy.deepcopy(payload))
            assert payload['capsule_contracts']['capsules'] == [] and payload['capsule_contracts']['view'] == 'planner-reduced'
            assert payload['library_snapshot']['view'] == 'planner-reduced' and inputs['library_snapshot'].get('view') is None
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


def _schema_refs(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '$ref':
                found.add(item.split('/')[2])
            else:
                _schema_refs(item, found)
    elif isinstance(value, list):
        for item in value:
            _schema_refs(item, found)
    return found


def test_reduced_schema_keeps_exactly_the_reachable_definitions():
    from jiuwenswarm.research.contracts import contract_schema
    full = contract_schema('plan-proposal')
    reduced = planner.reachable_schema(full)
    body = {key: value for key, value in reduced.items() if key != '$defs'}
    assert body == {key: value for key, value in full.items() if key != '$defs'}
    assert 0 < len(reduced['$defs']) < len(full['$defs'])
    assert all(reduced['$defs'][name] == full['$defs'][name] for name in reduced['$defs'])
    reached, pending = set(), _schema_refs(body, set())
    while pending:
        name = pending.pop()
        if name not in reached:
            reached.add(name)
            pending |= _schema_refs(full['$defs'][name], set())
    assert reached == set(reduced['$defs'])


@pytest.mark.asyncio
async def test_planner_view_keeps_every_field_the_plan_checks_read(tmp_path):
    store, _, _, library, installed, _ = await installed_library(tmp_path, scientific=True)
    try:
        snapshot_ref = library.snapshot()
        snapshot = store.read_record(snapshot_ref)
        catalog = store.read_record(capture_catalog(store, library, snapshot_ref))
        before = (copy.deepcopy(snapshot), copy.deepcopy(catalog))
        contracts, reduced = planner.planner_views(catalog, snapshot, integrated_plan_policy())
        assert (snapshot, catalog) == before
        assert len(json.dumps(contracts)) < len(json.dumps(catalog)) / 2
        selectable = [e for e in snapshot['entries'] if e['selectable_by_planner']]
        assert len(selectable) == len(contracts['capsules']) == len(reduced['entries'])
        fields = ('input_ports', 'output_ports', 'effect_class', 'network_mode', 'resource_needs', 'max_limits')
        by_pin = {tuple(c['cc'].values()): c['declaration'] for c in catalog['capsules']}
        for entry, row, item in zip(selectable, reduced['entries'], contracts['capsules']):
            pin = {key: entry[key] for key in ('cc_name', 'cc_version', 'declaration_sha256')}
            assert item['cc'] == pin and {key: row[key] for key in pin} == pin
            declaration = by_pin[tuple(pin.values())]
            # Everything binding.plan_checks reads from a snapshot entry is still on the planner's surface,
            # apart from check_pins, which only the host checks for existence.
            port_keys = ('name', 'artifact_type', 'schema_ref', 'required')
            rebuilt = dict(row, check_pins=entry['check_pins'],
                input_ports=[{k: p[k] for k in port_keys} for p in item['ports']['inputs']],
                output_ports=[{k: p[k] for k in port_keys} for p in item['ports']['outputs']])
            for key in fields:
                assert rebuilt[key] == entry[key], (pin['cc_name'], key)
            assert 'check_pins' not in row and 'input_ports' not in row
            assert item['purpose'] == declaration['identity']['summary']
            assert item['needs'] == declaration['needs'] and item['limits'] == declaration['budget']['per_call']
            assert item['guarantees']['check_ids'] == [c['id'] for c in declaration['guarantees']['checks']]
            for side in ('inputs', 'outputs'):
                assert [p.get('check_ids', []) for p in item['ports'][side]] == [p['check_ids'] for p in declaration['ports'][side]]
        # Host-side checking still reads the full records.
        verify_captured_catalog(store, catalog, snapshot, snapshot_ref)
    finally:
        store.close()


def test_policy_hides_only_paper_releases_it_cannot_select():
    pins = [{'cc_name': name, 'cc_version': version, 'declaration_sha256': 'a' * 64} for name, version in
            (('research.paper_summary', 'paper-m1-5'), ('research.paper_summary', 'paper-m1-5-evidence-1'),
             ('research.paper_summary_delivery', 'paper-m1-5-evidence-1'), ('research.evaluation', 'm1-5-evidence-1'))]
    snapshot = {'schema_version': '1.0.0', 'id': 'x', 'entries': [dict(pin, selectable_by_planner=True) for pin in pins]
                + [dict(pins[0], cc_name='research.verifier', selectable_by_planner=False)]}
    catalog = {'schema_version': '1.0.0', 'library_snapshot_ref': None, 'capsules': []}
    _, reduced = planner.planner_views(catalog, snapshot, integrated_plan_policy())
    assert [(e['cc_name'], e['cc_version']) for e in reduced['entries']] == [
        ('research.paper_summary', 'paper-m1-5'), ('research.evaluation', 'm1-5-evidence-1')]


@pytest.mark.asyncio
async def test_instructions_travel_once_and_other_messages_are_untouched():
    seen = []

    async def invoke(prompt, system=None):
        seen.append((prompt, system))
        return 'ok'
    messages = [{'role': 'system', 'content': 'RULES'}, {'role': 'user', 'content': '{"brief_ref": 1}'}]
    assert await planner._instructions_once(invoke)(json.dumps(messages), system='RULES') == 'ok'
    assert json.loads(seen[0][0]) == messages[1:] and seen[0][1] == 'RULES'
    await planner._instructions_once(invoke)('not a conversation', system='RULES')
    assert seen[1] == ('not a conversation', 'RULES')
    await planner._instructions_once(invoke)(json.dumps(messages))
    assert json.loads(seen[2][0]) == messages and seen[2][1] is None
