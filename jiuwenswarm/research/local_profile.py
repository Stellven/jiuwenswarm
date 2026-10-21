"""Explicit local operator capture, separate from admission and readiness.

The launcher opt-in captures an immutable policy, fixed subscription deployment
and workspace bindings. It does not invent scientific resources, calibrated
guard eligibility, library admissions, credentials or observed hardware.
"""
from __future__ import annotations

import json
import os
import stat
from importlib.resources import files
from pathlib import Path

from .contracts import ResearchError, validate
from .operator_config import OperatorConfiguration
from .state import SQLiteRunStore, json_bytes

PROFILE_NAME = 'local-research-v1'


def _write_once(path, value):
    raw = json_bytes(value)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise ResearchError('local_profile_conflict', 'Existing local operator capture differs; no implicit policy replacement')
    else:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def capture_local_profile(store, directory, *, input_root=Path('/workspace/input')):
    directory = Path(directory)
    if not directory.is_absolute() or directory.is_symlink() or input_root.is_symlink() or not input_root.is_dir():
        raise ResearchError('local_profile_custody', 'Local operator and input directories must be real absolute directories')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = directory.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o700 or metadata.st_uid != os.geteuid():
        raise ResearchError('local_profile_custody', 'Local operator directory has another owner or unsafe permissions')
    config_path, binding_path = directory / 'config.json', directory / 'bootstrap.json'
    if config_path.exists() or binding_path.exists():
        # Ordinary recreation retains the captured policy and immutable refs.
        from .bootstrap_gateway import _protected_file
        envelope = json.loads(_protected_file(str(binding_path)))
        if set(envelope) != {'binding_ref'}:
            raise ResearchError('local_profile_conflict', 'Local bootstrap locator is invalid')
        validate('Ref', envelope['binding_ref'])
        binding = store.read_record(envelope['binding_ref'])
        operator = OperatorConfiguration.load(config_path, resolve_profile=store.read_record)
        if store.read_record(binding['configuration_ref']) != operator.snapshot():
            raise ResearchError('local_profile_conflict', 'Local configuration differs from its captured identity')
        return {'configuration_path': str(config_path), 'binding_path': str(binding_path), 'binding_ref': envelope['binding_ref']}

    static_ref = store.put_blob(files('jiuwenswarm.research_assets').joinpath('planner/static-template.json').read_bytes(), media_type='application/json')
    required = ['research.' + stage for stage in ('search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')]
    policy_ref = store.put_record('plan-policy', {'schema_version': '1.0.0', 'id': PROFILE_NAME + '.plan-policy',
        'max_nodes': 12, 'allowed_effect_classes': ['pure', 'read_only', 'idempotent', 'compensable'],
        'allow_network': True, 'required_stages': required,
        'aggregate_limits': {'time_s': 10800, 'model_calls': 80, 'memory_mb': 16384}, 'max_attempts_per_node': 1})
    operator = OperatorConfiguration.from_mapping({'schema_version': '1.0.0',
        'cc': {'plan_source': 'planned', 'plan_policy_ref': policy_ref, 'static_template_ref': static_ref,
               'evaluation_profile_ref': None, 'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
        'codex': {'route_id': 'codex-cli-default'},
        'role_aliases': {role: 'codex-cli-default' for role in ('worker', 'planner', 'verifier')},
        'rsi': {'custodian_key_id': None, 'custodian_public_key': None}}).snapshot()
    configuration = store.put_blob(json_bytes(operator), media_type='application/json')
    selection = store.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': PROFILE_NAME + '.selection',
        'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
        'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []},
        'alternate_model_id': None, 'policy_ref': policy_ref})
    deployment = store.put_blob(json_bytes({'schema': 'ai4r-fixed-subscription:1', 'id': PROFILE_NAME + '.deployment',
        'route_id': 'codex-cli-default', 'requested_model': 'gpt-6.1-sol', 'endpoint': 'local-protected-IPC'}), media_type='application/json')
    defaults = store.put_record('default-policy', {'schema_version': '1.0.0', 'id': PROFILE_NAME + '.defaults',
        'hardware_profile': 'single_gpu', 'automatic_retries': 0})
    finalization = store.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': PROFILE_NAME + '.finalization',
        'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
        'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
    capture = lambda name, value: store.put_blob(json_bytes({'schema': 'ai4r-local-' + name + ':1', **value}), media_type='application/json')
    profile = capture('profile', {'id': PROFILE_NAME, 'model': 'gpt-6.1-sol', 'hardware_ceiling': 'single_gpu'})
    workspace = capture('workspace', {'id': 'local', 'input_root': str(input_root), 'poc_root': '/workspace/poc'})
    inputs = capture('input-directory', {'id': PROFILE_NAME + '.inputs', 'path': str(input_root), 'readable': os.access(input_root, os.R_OK)})
    inventory = store.put_record('resource-inventory', {'schema_version': '1.0.0', 'id': PROFILE_NAME + '.resources', 'resources': []})
    bounds = capture('search-bounds', {'id': PROFILE_NAME + '.search', 'connectors': ['local_documents'], 'max_queries': 3, 'max_hits_per_query': 3})
    # The source-owned Search bound has its own closed shape.
    bounds_value = store.read_record(bounds)
    bounds_value['schema'] = 'ai4r-search-bounds:1'
    bounds = store.put_blob(json_bytes(bounds_value), media_type='application/json')
    options = {'profile_ref': profile, 'workspace_ref': workspace, 'input_directory_ref': inputs,
        'default_policy_ref': defaults, 'finalization_profile_ref': finalization,
        'compiler_template_ref': capture('compiler-template', {'id': PROFILE_NAME + '.compiler', 'subnodes': ['intent', 'requirements']}),
        'planner_template_ref': capture('planner-template', {'id': PROFILE_NAME + '.planner', 'required_stages': required}),
        'compiler_limits': {'time_s': 600, 'model_calls': 4, 'memory_mb': 16384},
        'planner_limits': {'time_s': 600, 'model_calls': 2, 'memory_mb': 16384},
        'resource_inventory_ref': inventory, 'search_bounds_ref': bounds,
        'authority_ceiling': {'network': 'allowlist', 'network_allowlist': ['approved_package_index'],
                              'resource_reads': [], 'write_roots': ['/workspace/poc'], 'tools': ['deepsearch', 'codesearch']},
        'document_extraction_timeout_s': 30, 'max_upload_bytes': 20 * 1024 * 1024,
        'run_inputs': {}, 'host_records': {}}
    binding = store.put_blob(json_bytes({'workspace_id': 'local', 'host_id': 'local', 'configuration_ref': configuration,
        'model_selection_profile_ref': selection, 'deployment_ref': deployment, 'protected_options': options}), media_type='application/json')
    _write_once(config_path, operator)
    _write_once(binding_path, {'binding_ref': binding})
    return {'configuration_path': str(config_path), 'binding_path': str(binding_path), 'binding_ref': binding}


def main():
    if os.name != 'posix' or os.geteuid() != 10001 or os.environ.get('JIUWENSWARM_M1_LOCAL_RESEARCH') != '1':
        raise ResearchError('local_profile_identity', 'Local research capture requires explicit launcher opt-in and the product OS identity')
    root = Path(os.environ['JIUWENSWARM_M1_STATE'])
    store = SQLiteRunStore(root, input_root='/workspace/input', recover=False)
    try:
        capture_local_profile(store, root / 'operator' / PROFILE_NAME)
    finally:
        store.close()


if __name__ == '__main__':
    main()
