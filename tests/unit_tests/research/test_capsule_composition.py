"""Optional combined-branch checks; these are evaluator trials, not admission."""
import copy
import hashlib
import json
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.catalog import candidates
from jiuwenswarm.research.capsule_extensions.assets_v2 import prepare as prepare_asset_v2
from jiuwenswarm.research.capsule_extensions.summary_to_packet import worker as summary_adapter
from jiuwenswarm.research.capsule_extensions.summary_to_packet.checks import check as check_summary_adapter
from jiuwenswarm.research.capability_planning import capability_plan_policy
from jiuwenswarm.research.binding import Binder, expand_selectors
from jiuwenswarm.research.capsule_extensions.catalog import register_active
from jiuwenswarm.research.scheduler import Scheduler
from jiuwenswarm.research.state import json_bytes
from jiuwenswarm.research.checks import CheckContext, CheckRegistry
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.test_compiler import controlled_compiler


def paper_summary():
    ref = lambda name: {'id': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}
    sections = {name: {'status': 'supported' if name == 'results' else 'not_stated',
        'text': 'A bounded source statement.', 'citation_ids': ['C1'] if name == 'results' else []}
        for name in ('problem', 'method', 'results', 'contributions', 'limitations')}
    return {'schema_version': '1.0.0', 'id': 'paper_summary', 'brief_ref': ref('brief'),
        'documents_ref': ref('documents'), 'title': 'Example study',
        'documents': [{'document_id': 'P1', 'source_ref': ref('pdf'), 'page_count': 1}],
        'sections': sections, 'citations': [{'citation_id': 'C1', 'document_id': 'P1', 'page': 1,
            'start': 0, 'end': 8, 'quote': 'Evidence.'}]}


@pytest.mark.asyncio
async def test_actual_utility_pipeline_checked_artifacts_and_retained_input(tmp_path):
    text = 'item,value\na,2\nb,4\n'
    packet = {'schema_version': '1.0.0', 'data': {
        'table_request': {'file': 'input.csv', 'format': 'csv', 'columns': ['item', 'value'], 'delimiter': ','},
        'calculation': {'columns': ['value'], 'operations': ['count', 'sum', 'mean'], 'numeric_mode': 'decimal_strings'},
        'report': {'path': 'report.md', 'title': 'Trial', 'sections': [], 'data_keys': ['calculation_result']}},
        'files': [{'path': 'input.csv', 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}],
        'trust': 'low', 'provenance': [], 'limitations': ['Synthetic test input, not a research conclusion']}
    original = copy.deepcopy(packet)
    with closing(SQLiteRunStore(tmp_path)) as store:
        assets = candidates(store)
        registry = CheckRegistry()
        for name in ['utility.table_normalize', 'utility.calculate', 'utility.markdown_report']:
            asset, module = assets[name]
            output = (await module.execute(None, {'packet': packet}))['result']
            result = json.loads(output.data)
            ref = store.put_blob(output.data, media_type=output.media_type)
            bundle = store.read_record(asset['bundle_ref'])
            ids = [c['check_id'] for c in bundle['checks']]
            registry.register_bundle(bundle['bundle_id'], ids, module.check,
                implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
            plan = {'runner_refs': [asset['runner_ref']], 'profile_ref': asset['profile_ref'], 'mandatory_deterministic': ids}
            context = CheckContext({}, store, {'packet': packet}, {'result': result}, {'result': ref}, {})
            checked = await registry.run(plan, context, bundle_id=bundle['bundle_id'])
            assert all(r['outcome'] == 'PASS' for r in checked)
            packet = result
        assert original['files'][0]['text'] == text
        assert packet['files'][0] == original['files'][0]
        assert packet['data']['calculation_result']['columns']['value'] == {'count': 2, 'sum': '6', 'mean': '3'}
        assert packet['files'][-1]['path'] == 'report.md'
        assert 'Trust: low' in packet['files'][-1]['text']
        assert packet['data']['report_manifest']['input_files'][0]['sha256'] == original['files'][0]['sha256']
        assert packet['trust'] == 'low'


def test_summary_adapter_preserves_exact_source_references_as_low_trust_packet():
    summary = paper_summary()
    result = summary_adapter.convert(summary)
    assert result['trust'] == 'low'
    assert result['data']['paper_summary'] == summary
    assert result['data']['brief_ref'] == summary['brief_ref']
    assert result['data']['documents_ref'] == summary['documents_ref']
    assert result['data']['source_refs'] == [summary['documents'][0]['source_ref']]
    assert {(row['id'], row['sha256']) for row in result['provenance']} == {
        (summary['brief_ref']['id'], summary['brief_ref']['sha256']),
        (summary['documents_ref']['id'], summary['documents_ref']['sha256']),
        (summary['documents'][0]['source_ref']['id'], summary['documents'][0]['source_ref']['sha256'])}
    context = SimpleNamespace(output_refs={'result': {'id': 'output', 'sha256': 'f' * 64}})
    assert all(row['outcome'] == 'PASS' for row in check_summary_adapter(context, {'summary': summary}, {'result': result}))
    tampered = dict(result, trust='provisional')
    assert any(row['outcome'] == 'FAIL' for row in check_summary_adapter(context, {'summary': summary}, {'result': tampered}))
    dropped_provenance = copy.deepcopy(result)
    dropped_provenance['provenance'] = dropped_provenance['provenance'][:-1]
    assert any(row['outcome'] == 'FAIL' for row in check_summary_adapter(
        context, {'summary': summary}, {'result': dropped_provenance}))
    malformed = copy.deepcopy(summary)
    malformed['documents'][0]['source_ref'].pop('sha256')
    failed = check_summary_adapter(context, {'summary': malformed}, {'result': result})
    assert {row['outcome'] for row in failed} == {'FAIL'}


def test_v2_utility_releases_preserve_historical_v1_byte_pins():
    root = Path(__file__).parents[3] / 'jiuwenswarm/research/capsule_extensions'
    modules = {'table_normalize': 'table_normalize_v2', 'calculate': 'calculate_v2',
        'markdown_report': 'markdown_report_v2', 'generalist': 'generalist_v2'}
    for old_module, new_module in modules.items():
        historical = json.loads((root / 'history/v1' / old_module / 'release.json').read_text('utf-8'))
        current = json.loads((root / new_module / 'release.json').read_text('utf-8'))
        deps = {item['path']: item['sha256'] for item in current['shared_dependencies']}
        for path, digest in historical['files'].items():
            # Historical pins are still exact source bytes; the new release
            # declares the executable old worker/check implementation as an
            # independently hashed dependency.
            source_path = root / path
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == digest
            if path.endswith(('/worker.py', '/checks.py', '/expression.py')):
                assert deps[path] == digest


def test_packet_v1_runtime_pin_is_independent_of_capsule_release_version(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        first = prepare_asset_v2(store, Path(__file__).parents[3] /
            'jiuwenswarm/research/capsule_extensions/summary_to_packet', name='utility.summary_to_packet',
            summary='adapter', input_name='summary', input_type='paper_summary',
            input_schema='urn:ai4r:paper-summary:1.0.0', version='m1-1')
        second = prepare_asset_v2(store, Path(__file__).parents[3] /
            'jiuwenswarm/research/capsule_extensions/summary_to_packet', name='utility.summary_to_packet',
            summary='adapter', input_name='summary', input_type='paper_summary',
            input_schema='urn:ai4r:paper-summary:1.0.0', version='m1-2')
        a = store.read_record(first['declaration_ref'])
        b = store.read_record(second['declaration_ref'])
        assert a['identity']['version_label'] != b['identity']['version_label']
        assert a['needs']['external'] == b['needs']['external']
        assert a['ports']['outputs'] == b['ports']['outputs']
        assert a['needs']['external'][0]['pin']['sha256'] == first['body_refs']['capsule_extensions/packet.py']['sha256']
        assert 'assets.py' not in first['body_refs']


@pytest.mark.asyncio
async def test_admitted_adapter_and_report_capsules_compose_through_frozen_gated_dag(tmp_path, monkeypatch):
    app = await controlled_compiler(tmp_path, run_model_calls=80)
    store, library, actor = app['store'], app['library'], app['actor']
    try:
        library.configure_verifier(app['installed']['verifier']['pin'])
        installed_candidates = candidates(store)
        names = ('utility.summary_to_packet', 'utility.packet_report', 'utility.table_normalize',
            'utility.calculate', 'utility.markdown_report', 'research.generalist')
        for name in names:
            asset, _ = installed_candidates[name]
            library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
            admission_ref = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=16384)
            admission = store.read_record(admission_ref)
            assert admission['status'] == 'admitted', admission['reasons']
            pin = admission['cc']
            library.set_standing(pin['cc_name'], pin['cc_version'], 'active', actor, reason='Controlled composition fixture')
        register_active(app['registry'], app['checks'], library, store)

        summary_ref = store.put_blob(json_bytes(paper_summary()), media_type='application/json')
        resources = json.loads(Path('tests/fixtures/research/planning/resource_inventory.json').read_text('utf-8'))
        resources['resources'] = [{'resource_key': 'paper_summary_source', 'kind': 'file', 'available': True,
            'quantity': None, 'ref': summary_ref}]
        resources_ref = store.put_record('resource-inventory', resources)
        snapshot_ref = library.snapshot()
        policy_ref = store.put_record('plan-policy', capability_plan_policy())
        brief = store.read_record(app['brief_ref'])
        entries = {entry['cc_name']: entry for entry in store.read_record(snapshot_ref)['entries']}

        static = json.loads(Path('tests/fixtures/research/planning/static_template.json').read_text('utf-8'))
        source = expand_selectors(static, brief)
        packet_pin = {key: entries['utility.summary_to_packet'][key] for key in
            ('cc_name', 'cc_version', 'declaration_sha256')}
        report_pin = {key: entries['utility.packet_report'][key] for key in
            ('cc_name', 'cc_version', 'declaration_sha256')}
        base = copy.deepcopy(static['nodes'][0])
        nodes = []
        for nid, cc, predecessor, deliverables in (
            ('adapt', packet_pin, [], []), ('report', report_pin, ['adapt'],
                [item['id'] for item in brief['deliverables']])):
            node = copy.deepcopy(base)
            node.update(node_id=nid, cc=cc, objective='Convert and render the accepted paper summary',
                requirement_ids=[item['id'] for item in brief['mandatory_requirements']],
                deliverable_ids=deliverables, predecessors=predecessor,
                outputs=[{'name': 'result', 'artifact_type': 'work_packet', 'required': True}],
                    # Admission ceiling reserves 30 s for the pure worker and
                    # up to 60 s for its one independent output review.
                    limits={'time_s': 90, 'model_calls': 1, 'memory_mb': 256}, suggested_checks=[])
            if nid == 'adapt':
                node['inputs'] = [{'name': 'summary', 'artifact_type': 'paper_summary', 'required': True,
                    'source_kind': 'accepted_ref', 'run_input_key': 'paper_summary_source', 'accepted_ref': None, 'future': None}]
            else:
                node['inputs'] = [{'name': 'packet', 'artifact_type': 'work_packet', 'required': True,
                    'source_kind': 'future_output', 'run_input_key': None, 'accepted_ref': None,
                    'future': {'producer_node': 'adapt', 'port': 'result', 'artifact_type': 'work_packet'}}]
            nodes.append(node)
        source['nodes'] = nodes
        source['coverage'] = []
        for kind, rows, field in (('requirement', brief['mandatory_requirements'], 'requirement_ids'),
                                  ('deliverable', brief['deliverables'], 'deliverable_ids'),
                                  ('evidence_obligation', brief['evidence_obligations'], None)):
            for item in rows:
                assigned = [node['node_id'] for node in nodes if field is None or item['id'] in node[field]]
                source['coverage'].append({'item_kind': kind, 'item_id': item['id'], 'node_ids': assigned})
        source['nodes'].reverse()  # Freeze order must come from typed dependencies, not proposal list order.
        source_ref = store.put_blob(json_bytes(source), media_type='application/json')
        bounds = store.put_blob(json_bytes({'schema': 'ai4r-search-bounds:1', 'id': 'bounds',
            'connectors': ['local_documents'], 'max_queries': 2, 'max_hits_per_query': 3}))
        binder = Binder(store, library, app['checks'], search_bounds_ref=bounds)
        authority = {'network': 'none', 'network_allowlist': [], 'resource_reads': [summary_ref],
            'write_roots': [], 'tools': []}
        try:
            plan_ref = binder.freeze(source_ref, app['brief_ref'], snapshot_ref, resources_ref, policy_ref,
                app['protected']['configuration_ref'], plan_source='static', run_inputs={'paper_summary_source': summary_ref},
                authority_ceiling=authority)
        except Exception as error:
            pytest.fail(f'Frozen graph rejected: {getattr(error, "details", error)}')
        plan = store.read_record(plan_ref, contract_id='run-plan')
        assert plan['frozen'] and plan['topological_order'] == ['adapt', 'report']
        scheduler = Scheduler(store, app['runner'], app['factory'], binder, library=library)
        async def serial(order, dispatch, **kwargs):
            return [await dispatch(node_id) for node_id in order]
        monkeypatch.setattr('jiuwenswarm.research.scheduler.run_native_workflow', serial)

        low_source = copy.deepcopy(source)
        rename = {node['node_id']: 'low_' + node['node_id'] for node in low_source['nodes']}
        for node in low_source['nodes']:
            node['node_id'] = rename[node['node_id']]
            node['predecessors'] = [rename[item] for item in node['predecessors']]
            # The review reservation consumes this whole ceiling, so dispatch
            # must fail closed before creating an accepted node output.
            node['limits']['time_s'] = 60
            for port in node['inputs']:
                if port['future']:
                    port['future']['producer_node'] = rename[port['future']['producer_node']]
        for item in low_source['coverage']:
            item['node_ids'] = [rename[node_id] for node_id in item['node_ids']]
        low_plan_ref = binder.freeze(store.put_blob(json_bytes(low_source), media_type='application/json'),
            app['brief_ref'], snapshot_ref, resources_ref, policy_ref,
            app['protected']['configuration_ref'], plan_source='static',
            run_inputs={'paper_summary_source': summary_ref}, authority_ceiling=authority)
        original_run = store.get_run('run:compiler')
        low_submission = copy.deepcopy(original_run['submission'])
        low_submission.update(id='submission:compiler-low', client_request_id='compiler-low-budget')
        store.create_run('run:compiler-low', account_id=original_run['account_id'],
            workspace_id=original_run['workspace_id'], submission=low_submission)
        app['runner'].configure_run('run:compiler-low', **{key: app['protected'][key] for key in
            ('model_selection_profile_ref', 'deployment_ref', 'router', 'configuration_ref', 'run_limits', 'routing_context')})
        low_result = await scheduler.execute_plan('run:compiler-low', low_plan_ref, {
            **app['protected'], 'resource_inventory_ref': resources_ref,
            'library_snapshot_ref': snapshot_ref, 'authority_ceiling': authority})
        assert low_result['node_states']['low_adapt'] == 'failed', low_result
        assert not store.accepted_outputs('run:compiler-low', 'low_adapt')
        assert not [row for row in store.iter_records(run_id='run:compiler-low', kinds=('gate-decision',))
            if row['record'].get('node_id') == 'low_adapt' and row['record']['action'] == 'advance']

        result = await scheduler.execute_plan('run:compiler', plan_ref, {
            **app['protected'], 'resource_inventory_ref': resources_ref,
            'library_snapshot_ref': snapshot_ref, 'authority_ceiling': authority})
        assert result['status'] == 'completed', result
        assert store.accepted_outputs('run:compiler', 'adapt')
        assert store.accepted_outputs('run:compiler', 'report')
        packet = store.read_record(store.accepted_outputs('run:compiler', 'adapt')['result'])
        assert packet['trust'] == 'low'
        assert packet['data']['paper_summary'] == paper_summary()
        assert any(row['record']['node_id'] == 'adapt' and row['record']['action'] == 'advance'
            for row in store.iter_records(run_id='run:compiler', kinds=('gate-decision',)))

        table_text = 'item,value\na,2\nb,4\n'
        work_packet = {'schema_version': '1.0.0', 'data': {
            'table_request': {'file': 'input.csv', 'format': 'csv', 'columns': ['item', 'value'], 'delimiter': ','},
            'calculation': {'columns': ['value'], 'operations': ['count', 'sum', 'mean'], 'numeric_mode': 'decimal_strings'},
            'report': {'path': 'report.md', 'title': 'Trial', 'sections': [], 'data_keys': ['calculation_result']}},
            'files': [{'path': 'input.csv', 'text': table_text,
                'sha256': hashlib.sha256(table_text.encode()).hexdigest()}],
            'trust': 'low', 'provenance': [], 'limitations': ['Controlled utility composition fixture']}
        packet_ref = store.put_blob(json_bytes(work_packet), media_type='application/json')
        utility_resources = json.loads(Path('tests/fixtures/research/planning/resource_inventory.json').read_text('utf-8'))
        utility_resources['resources'] = [{'resource_key': 'packet_source', 'kind': 'file', 'available': True,
            'quantity': None, 'ref': packet_ref}]
        utility_resources_ref = store.put_record('resource-inventory', utility_resources)
        utility_entries = {entry['cc_name']: entry for entry in store.read_record(snapshot_ref)['entries']}
        utility_names = ['utility.table_normalize', 'utility.calculate', 'utility.markdown_report']
        utility_nodes = []
        for index, name in enumerate(utility_names):
            node_id = ['normalize', 'calculate', 'markdown'][index]
            entry = utility_entries[name]
            pin = {key: entry[key] for key in ('cc_name', 'cc_version', 'declaration_sha256')}
            template_node = copy.deepcopy(static['nodes'][0])
            template_node.update(node_id=node_id, cc=pin, objective='Normalize, calculate, and report the checked work packet',
                requirement_ids=[item['id'] for item in brief['mandatory_requirements']],
                deliverable_ids=[item['id'] for item in brief['deliverables']] if index == 2 else [],
                predecessors=[] if index == 0 else [['normalize'], ['calculate']][index - 1],
                inputs=[{'name': 'packet', 'artifact_type': 'work_packet', 'required': True,
                    'source_kind': 'accepted_ref' if index == 0 else 'future_output',
                    'run_input_key': 'packet_source' if index == 0 else None, 'accepted_ref': None,
                    'future': None if index == 0 else {'producer_node': ['normalize', 'calculate'][index - 1],
                        'port': 'result', 'artifact_type': 'work_packet'}}],
                outputs=[{'name': 'result', 'artifact_type': 'work_packet', 'required': True}],
                limits={'time_s': 90, 'model_calls': 1, 'memory_mb': 256}, suggested_checks=[])
            utility_nodes.append(template_node)
        utility_source = expand_selectors(static, brief)
        utility_source['nodes'] = list(reversed(utility_nodes))
        utility_source['coverage'] = []
        for kind, rows, field in (('requirement', brief['mandatory_requirements'], 'requirement_ids'),
                                  ('deliverable', brief['deliverables'], 'deliverable_ids'),
                                  ('evidence_obligation', brief['evidence_obligations'], None)):
            for item in rows:
                assigned = [node['node_id'] for node in utility_nodes if field is None or item['id'] in node[field]]
                utility_source['coverage'].append({'item_kind': kind, 'item_id': item['id'], 'node_ids': assigned})
        utility_plan_ref = binder.freeze(store.put_blob(json_bytes(utility_source), media_type='application/json'),
            app['brief_ref'], snapshot_ref, utility_resources_ref, policy_ref,
            app['protected']['configuration_ref'], plan_source='static', run_inputs={'packet_source': packet_ref},
            authority_ceiling={'network': 'none', 'network_allowlist': [], 'resource_reads': [packet_ref],
                'write_roots': [], 'tools': []})
        utility_run = 'run:compiler-utilities'
        store.create_run(utility_run, account_id=original_run['account_id'], workspace_id=original_run['workspace_id'],
            submission=dict(low_submission, id='submission:compiler-utilities', client_request_id='compiler-utilities'))
        app['runner'].configure_run(utility_run, **{key: app['protected'][key] for key in
            ('model_selection_profile_ref', 'deployment_ref', 'router', 'configuration_ref', 'run_limits', 'routing_context')})
        utility_authority = {'network': 'none', 'network_allowlist': [], 'resource_reads': [packet_ref],
            'write_roots': [], 'tools': []}
        utility_result = await scheduler.execute_plan(utility_run, utility_plan_ref, {
            **app['protected'], 'resource_inventory_ref': utility_resources_ref,
            'library_snapshot_ref': snapshot_ref, 'authority_ceiling': utility_authority})
        assert utility_result['status'] == 'completed', utility_result
        assert utility_result['node_states'] == {'normalize': 'accepted', 'calculate': 'accepted', 'markdown': 'accepted'}
        accepted_packet = store.read_record(store.accepted_outputs(utility_run, 'calculate')['result'])
        assert accepted_packet['data']['calculation_result']['columns']['value'] == {'count': 2, 'sum': '6', 'mean': '3'}
        assert all(store.accepted_outputs(utility_run, node) for node in ('normalize', 'calculate', 'markdown'))
        for node in ('normalize', 'calculate', 'markdown'):
            assert any(row['record']['node_id'] == node and row['record']['action'] == 'advance'
                for row in store.iter_records(run_id=utility_run, kinds=('gate-decision',)))
    finally:
        store.close()
