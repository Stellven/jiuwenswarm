"""Explicit test setup for current IF016 slots; no operational qualification.

Shared source fixtures remain unbound. Each positive test opts into one exact
approved request after its source carrier/inputs/profile have been installed.
"""
import copy
import hashlib

from jiuwenswarm.research.bridge import GovernedBridge
from jiuwenswarm.research.evaluation_authority import EvaluationAuthority
from jiuwenswarm.research.state import json_bytes


def bind_request_runtime(store, provider, request, entry_point):
    resources = provider.resources
    case = provider.cases[(request['case_id'], entry_point)]
    source_ref, _, _ = resources._subject(case)
    source = store.read_record(source_ref)
    parent = store.read_record(source['node_contract_ref'])
    normalized = copy.deepcopy(request)
    if entry_point == 'E2':
        normalized.setdefault('host_records', [])
    slots = [{'slot_id': 'explicit-request-slot', 'request_id': request['request_id'],
        'entry_point': entry_point, 'case_id': request['case_id'],
        'config_id': 'controlled', 'repeat_index': 0,
        'request_sha256': hashlib.sha256(json_bytes([entry_point, normalized])).hexdigest(),
        'limits': copy.deepcopy(parent['node_limits'])}]
    refs = resources.admitted.resources.exact_binding_refs
    runtime = store.append_record('evaluation-runtime', {
        'schema': 'ai4r-evaluation-runtime:1', 'id': 'runtime:explicit-request',
        **{key: provider.assets[key] for key in
           ('account_id', 'workspace_id', 'campaign_id', 'configuration_ref')},
        **{key: refs[key] for key in ('model_selection_profile_ref', 'deployment_ref')},
        'profile_ref': provider.profile_ref, 'assets_ref': provider.assets_ref,
        'policy_ref': source['policy_ref'], 'library_snapshot_ref': resources.snapshot_ref,
        'schedule_ref': store.put_blob(json_bytes(slots), media_type='application/json'),
        'slots': slots, 'accepted': False, 'invalid_for_product': True})
    owner = resources.bind_runtime(runtime)
    assert type(owner) is EvaluationAuthority and owner in owner.runner._evaluation_owners
    if type(owner.runner.model) is GovernedBridge:
        owner.runner.model.persist = owner.runner.capture_record
    return owner


def assert_private_measurement_origin(store, owner):
    """Replace retired marker assertions with exact private journal joins."""
    grants = list(store.iter_records(kinds=('evaluation-assignment-grant',)))
    measured = list(store.iter_records(kinds=('evaluation-trial-measurement',)))
    assert len(grants) == len(measured) == 1
    grant = grants[0]['record']
    assert store.record_kind(grant['contract_ref']) == 'evaluation-subnode-context'
    child = store.read_record(grant['contract_ref'])
    scope = store.read_record(grant['scope_ref'])
    assert child['source_subject_ref'] == scope['source_contract_ref']
    assert measured[0]['record']['contract_ref'] == grant['contract_ref']
    assert measured[0]['record']['accepted'] is False
    captures = owner.captures(grant['request_ref'])
    assert any(row['capture_kind'] == 'actual_contract'
        and row['capture_ref'] == grant['contract_ref'] for row in captures)
    assert any(row['capture_kind'] == 'measurement'
        and row['capture_ref'] == measured[0]['ref'] for row in captures)
