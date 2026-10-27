"""Supplied (accepted_ref) inputs carry a captured artifact type that the consumer port must equal."""
import copy
from contextlib import closing

import pytest

from jiuwenswarm.research.binding import plan_checks
from jiuwenswarm.research.capability_planning import capability_plan_policy
from jiuwenswarm.research.capsule_extensions.catalog import candidates
from jiuwenswarm.research.capsule_extensions.packet import PACKET
from jiuwenswarm.research.capsules import planner
from jiuwenswarm.research.run_input_types import typed_resource
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.test_capability_extensions import graph

SUMMARY = 'urn:ai4r:paper-summary:1.0.0'


def supplied_graph(*, held, wanted, held_schema=PACKET, wanted_schema=PACKET, key='data_source', typed=True):
    """One node consuming a host-supplied input: `held` is what was captured, `wanted` what the port declares."""
    source, brief, library, resources = graph()
    node = source['nodes'][0]
    node['inputs'] = [{'name': 'packet', 'artifact_type': wanted, 'required': True, 'source_kind': 'accepted_ref',
        'run_input_key': key, 'accepted_ref': None, 'future': None}]
    library['entries'][0]['input_ports'] = [{'name': 'packet', 'artifact_type': wanted,
        'schema_ref': wanted_schema, 'required': True}]
    item = {'resource_key': key, 'kind': 'file', 'available': True, 'quantity': None,
            'ref': {'id': 'blob:' + '1' * 64, 'sha256': '1' * 64}}
    if typed:
        item.update(artifact_type=held, schema_ref=held_schema)
    resources['resources'] = [item]
    return source, brief, library, resources


def failed(values):
    _, results = plan_checks(*values, capability_plan_policy(), plan_source='static')
    return {row['check_id'] for row in results if row['outcome'] == 'FAIL'}


def test_matching_captured_type_is_accepted():
    assert failed(supplied_graph(held='work_packet', wanted='work_packet')) == set()


def test_paper_summary_cannot_feed_a_work_packet_port():
    values = supplied_graph(held='paper_summary', held_schema=SUMMARY, wanted='work_packet')
    assert failed(values) == {'port_type_compatibility'}


def test_same_type_with_another_schema_is_refused():
    values = supplied_graph(held='work_packet', held_schema='urn:ai4r:other:1.0.0', wanted='work_packet')
    assert failed(values) == {'port_type_compatibility'}


def test_untyped_supplied_data_fails_closed():
    assert failed(supplied_graph(held=None, wanted='work_packet', typed=False)) == {'port_type_compatibility'}


def test_planner_label_cannot_rename_the_supplied_bytes():
    # The proposal copies the consumer's type onto its own port; only the capture counts.
    values = supplied_graph(held='paper_summary', held_schema=SUMMARY, wanted='work_packet')
    assert values[0]['nodes'][0]['inputs'][0]['artifact_type'] == 'work_packet'
    assert 'port_type_compatibility' in failed(values)


def test_host_typing_covers_science_and_request_keys_and_keeps_unknown_keys_untyped():
    row = typed_resource({'resource_key': 'baseline_resource', 'kind': 'file', 'available': True, 'quantity': 1, 'ref': None})
    assert (row['artifact_type'], row['schema_ref']) == ('resource_snapshot', 'resource-snapshot:field-contract:1')
    other = {'resource_key': 'mystery', 'kind': 'file', 'available': True, 'quantity': 1, 'ref': None}
    assert typed_resource(other) == other


def test_planner_prompt_shows_the_captured_type_per_input():
    resources = {'resources': [typed_resource({'resource_key': 'local_document_buffer', 'kind': 'dataset', 'available': True,
        'quantity': 1, 'ref': {'id': 'x', 'sha256': '2' * 64}}),
        {'resource_key': 'mystery', 'kind': 'file', 'available': True, 'quantity': None, 'ref': None}]}
    records = {r['run_input_key']: r for r in planner._protected_run_inputs(resources)['records']}
    assert records['local_document_buffer']['artifact_type'] == 'local_document_buffer'
    assert records['mystery']['artifact_type'] is None
    assert records['brief']['artifact_type'] == 'research_brief'


@pytest.fixture
def releases(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        found = candidates(store)
        yield {name: store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
               for name, (asset, _) in found.items()}


def ports(declaration):
    return {direction: {p['name']: (p['artifact_type'], p['schema_ref']) for p in declaration['ports'][direction]}
            for direction in ('inputs', 'outputs')}


def chain(releases, *, first_output, calculate_input_source):
    """normalize -> calculate with the real declared ports; the second consumes `calculate_input_source`."""
    source, brief, library, resources = graph()
    normalize, calculate = releases['utility.table_normalize'], releases['utility.calculate']
    for entry, declaration in zip(library['entries'], (normalize, calculate)):
        entry.update(cc_name=declaration['identity']['name'], cc_version=declaration['identity']['version_label'],
            selectable_by_planner=True,
            input_ports=copy.deepcopy([{k: p[k] for k in ('name', 'artifact_type', 'schema_ref', 'required')}
                                       for p in declaration['ports']['inputs']]),
            output_ports=copy.deepcopy([{k: p[k] for k in ('name', 'artifact_type', 'schema_ref', 'required')}
                                        for p in declaration['ports']['outputs']]))
    first, second = source['nodes']
    for node, entry, digest in zip((first, second), library['entries'], ('a' * 64, 'b' * 64)):
        entry['declaration_sha256'] = digest
        node['cc'] = {key: entry[key] for key in ('cc_name', 'cc_version', 'declaration_sha256')}
    first['inputs'] = [{'name': 'packet', 'artifact_type': 'work_packet', 'required': True, 'source_kind': 'accepted_ref',
        'run_input_key': 'raw_file', 'accepted_ref': None, 'future': None}]
    first['outputs'] = [{'name': 'result', 'artifact_type': first_output, 'required': True}]
    if calculate_input_source == 'producer':
        second['inputs'] = [{'name': 'packet', 'artifact_type': first_output, 'required': True, 'source_kind': 'future_output',
            'run_input_key': None, 'accepted_ref': None,
            'future': {'producer_node': first['node_id'], 'port': 'result', 'artifact_type': first_output}}]
    else:  # the unparsed file itself, skipping the parse step
        second['inputs'] = [{'name': 'packet', 'artifact_type': 'work_packet', 'required': True, 'source_kind': 'accepted_ref',
        'run_input_key': 'raw_file', 'accepted_ref': None, 'future': None}]
    resources['resources'] = [{'resource_key': 'raw_file', 'kind': 'file', 'available': True, 'quantity': None,
        'ref': {'id': 'blob:' + '3' * 64, 'sha256': '3' * 64}, 'artifact_type': 'work_packet', 'schema_ref': PACKET}]
    return source, brief, library, resources


def test_release_ports_split_unparsed_and_parsed_packets(releases):
    normalize, calculate = ports(releases['utility.table_normalize']), ports(releases['utility.calculate'])
    assert normalize['inputs']['packet'][0] == 'work_packet' and normalize['outputs']['result'][0] == 'table_packet'
    assert calculate['inputs']['packet'][0] == 'table_packet' and calculate['outputs']['result'][0] == 'work_packet'
    assert releases['utility.table_normalize']['identity']['version_label'] == 'm1-3'
    assert releases['utility.calculate']['identity']['version_label'] == 'm1-4'


def test_parse_then_calculate_is_accepted(releases):
    assert failed(chain(releases, first_output='table_packet', calculate_input_source='producer')) == set()


def test_calculate_fed_by_an_unparsed_file_is_refused(releases):
    values = chain(releases, first_output='table_packet', calculate_input_source='file')
    assert failed(values) == {'port_type_compatibility'}


def test_calculate_fed_by_a_producer_that_never_parsed_is_refused(releases):
    values = chain(releases, first_output='work_packet', calculate_input_source='producer')
    assert failed(values) == {'port_type_compatibility'}
