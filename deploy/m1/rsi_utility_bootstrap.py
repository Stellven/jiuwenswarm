"""Explicit utility-only RSI bootstrap; no product profile or child activation.

Uses current calibration/admission owners. Every effect uses a pinned Root
configuration and the existing per-stage Root grant. Source scope is fixed.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from deploy.m1 import rsi_operational_bootstrap as owner

TARGETS = ['utility.calculate', 'utility.table_normalize']
STAGES = ['intent', 'verifier']
CONFIG = {}
SCOPE = {'schema': 'ai4r-utility-rsi-scope:1', 'targets': TARGETS,
         'work_stages': STAGES, 'setup_model_calls': 12,
         'rsi_model_calls_per_target': 10, 'product_eligible': False}


def configure(args):
    global CONFIG
    raw = owner.protected_json(args.configuration, root_owned=True)
    owner.need(hashlib.sha256(Path(args.configuration).read_bytes()).hexdigest() == args.configuration_sha256)
    fields = {'schema', 'authorization', 'base_root', 'generation', 'account_root',
              'generation_configuration', 'selection_directory', 'source_sha256', 'helper_sha256'}
    continuation = raw.get('schema') == 'ai4r-utility-rsi-bootstrap-configuration:2'
    if continuation:
        fields |= {'budget_authorization', 'setup_model_calls_ceiling', 'prior_setup'}
        owner.need(raw['budget_authorization'] == 'Approve 13 setup calls'
                   and raw['setup_model_calls_ceiling'] == 13
                   and isinstance(raw['prior_setup'], list) and raw['prior_setup'])
    owner.need(set(raw) == fields and raw['schema'] in (
                   'ai4r-utility-rsi-bootstrap-configuration:1', 'ai4r-utility-rsi-bootstrap-configuration:2')
               and raw['authorization'] == 'Approve utility-only bootstrap'
               and raw['source_sha256'] == owner.source_digest()
               and raw['helper_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for key in ('base_root', 'account_root', 'generation_configuration', 'selection_directory'):
        path = Path(raw[key])
        owner.need(path.is_absolute() and '..' not in path.parts and not path.is_symlink())
    owner.BASE_ROOT = Path(raw['base_root'])
    owner.ROOT = owner.BASE_ROOT
    owner.ACCOUNT_ROOT = Path(raw['account_root'])
    owner.GENERATION_CONFIG = Path(raw['generation_configuration'])
    owner.SELECTION_DIRECTORY = Path(raw['selection_directory'])
    owner.select_generation(raw['generation'])
    generation = owner.generation_settings(STAGES)
    owner.need(generation['schema'] == 'ai4r-rsi-bootstrap-generation:3')
    CONFIG = raw
    prior_calls = historical_setup_calls()
    owner.need((continuation and prior_calls == 1) or (not continuation and prior_calls == 0))
    if args.approval:
        owner.APPROVAL = Path(args.approval)
    owner.need(os.geteuid() == os.getegid() == 12001)
    return raw



def historical_setup_calls():
    """Count pinned prior generations read-only after actual native release."""
    from deploy.m1.rsi_development_seed import database
    prior = CONFIG.get('prior_setup', [])
    names = owner.generation_settings(STAGES)['prior_namespaces']
    owner.need(set(names) == {row['generation'] for row in prior} and len(names) == len(prior))
    owner.prior_namespaces_available({'prior_namespaces': names})
    total = 0
    for item in prior:
        owner.need(set(item) == {'generation', 'bootstrap_sha256', 'model_calls'}
                   and type(item['model_calls']) is int and item['model_calls'] >= 0)
        root = owner.BASE_ROOT.with_name(owner.BASE_ROOT.name + '.' + item['generation'])
        original = root / 'bootstrap.json'
        owner.protected_json(original)
        owner.need(hashlib.sha256(original.read_bytes()).hexdigest() == item['bootstrap_sha256'])
        db = database(root / 'core/state/research.sqlite3')
        try:
            actual = db.execute("SELECT COUNT(*) FROM records WHERE kind='model-call-start'").fetchone()[0]
            owner.need(actual == item['model_calls'])
            total += actual
        finally:
            db.close()
    return total



def capture():
    owner.custody()
    owner.need(not owner.ROOT.exists() or not any(owner.ROOT.iterdir()))
    from jiuwenswarm.research.accounts import AccountStore
    from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.unified_planning import integrated_plan_policy
    from jiuwenswarm.research.catalog_calibration import capture_catalog_calibration
    with owner.private_creation():
        owner.ROOT.mkdir(mode=0o700, exist_ok=True)
        (owner.ROOT / 'input').mkdir(mode=0o700)
        accounts = AccountStore(owner.ROOT / 'identity')
        store = SQLiteRunStore(owner.ROOT / 'core', recover=False, input_root=owner.ROOT / 'input')
        try:
            policy = integrated_plan_policy()
            policy.update(id='utility_rsi_work_policy_v1', max_nodes=2,
                          allowed_effect_classes=['read_only'], allow_network=False,
                          aggregate_limits={'time_s': 1800, 'model_calls': 12, 'memory_mb': 16384})
            policy_ref = store.put_record('plan-policy', policy)
            blob = lambda value: store.put_blob(json_bytes(value), media_type='application/json')
            # Operator syntax requires a template Ref; this explicit denial
            # artifact is not a static DAG and product composition rejects it.
            denied_template = blob({'schema': 'ai4r-utility-rsi-no-product-template:1',
                                    'scope': SCOPE, 'product_execution': 'forbidden'})
            operator = OperatorConfiguration.from_mapping({'schema_version': '1.0.0',
                'cc': {'plan_source': 'static', 'plan_policy_ref': policy_ref,
                       'static_template_ref': denied_template, 'evaluation_profile_ref': None,
                       'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
                'codex': {'route_id': 'codex-cli-default'},
                'role_aliases': {role: 'codex-cli-default' for role in ('worker', 'planner', 'verifier')},
                'rsi': {'custodian_key_id': None, 'custodian_public_key': None}}).snapshot()
            configuration_ref = blob(operator)
            profile_id = 'utility-rsi:' + owner.ACTIVE_GENERATION
            selection = store.put_record('model-selection-profile', {
                'schema_version': '1.0.0', 'id': profile_id + '.selection',
                'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'],
                'extra_requirements': {}, 'selection_allowance': {'enabled': False,
                'deployment_ref': None, 'model_calls': 0, 'time_s': 0, 'output_tokens': 0,
                'disclosure_scope': []}, 'alternate_model_id': None, 'policy_ref': policy_ref})
            deployment = blob({'schema': 'ai4r-fixed-subscription:2', 'id': profile_id + '.deployment',
                'route_id': 'codex-cli-default', 'requested_model': 'gpt-6.1-sol',
                'endpoint': 'local-protected-IPC', 'backend': 'host-codex-app-server',
                'reasoning_effort': 'medium'})
            generations, prior = owner.profile_generations(STAGES)
            calibrated = asyncio.run(capture_catalog_calibration(store,
                configuration_ref=configuration_ref, model_selection_profile_ref=selection,
                deployment_ref=deployment, profile_generations=generations, stages=STAGES))
            scope_options = {'profile_ref': blob({'schema': 'ai4r-local-profile:2', 'id': profile_id,
                'model': 'gpt-6.1-sol', 'hardware_ceiling': 'unobserved-development-only',
                'backend': 'host-codex-app-server', 'reasoning_effort': 'medium'}),
                'workspace_ref': blob({'schema': 'ai4r-local-workspace:1', 'id': 'local',
                    'input_root': str(owner.ROOT / 'input'), 'poc_root': None}),
                'input_directory_ref': blob({'schema': 'ai4r-local-input-directory:1',
                    'id': profile_id + '.inputs', 'path': str(owner.ROOT / 'input'), 'readable': True}),
                'compiler_template_ref': blob({'schema': 'ai4r-utility-rsi-work-template:1',
                    'id': profile_id + '.work', 'subnodes': ['diagnosis', 'proposal']}),
                'finalization_profile_ref': store.put_record('node-finalization-profile', {
                    'schema_version': '2.0.0', 'id': profile_id + '.finalization',
                    'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
                    'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0}),
                'development_builtin_catalog': False, 'integrated_workflows': False,
                'paper_summary_workflow': False, 'isolated_helper_scope': 'utility-rsi:1',
                'utility_rsi_scope': SCOPE, 'calibration_runtime_ref': calibrated['runtime_ref'],
                'calibration_profile_refs': calibrated['profile_refs'], 'calibration_limitations': calibrated['limitations']}
            binding = {'workspace_id': 'local', 'host_id': 'local', 'configuration_ref': configuration_ref,
                       'model_selection_profile_ref': selection, 'deployment_ref': deployment,
                       'protected_options': scope_options}
            binding_ref = blob(binding)
            manifest = {'schema': owner.HOST_GENERATION_SCHEMA, 'account_id': accounts.primary()['account_id'],
                'root': str(owner.ROOT), 'model': 'gpt-6.1-sol',
                'installed_source_sha256': owner.source_digest(), 'binding_ref': binding_ref,
                'configuration_ref': configuration_ref, 'model_selection_profile_ref': selection,
                'deployment_ref': deployment, 'calibration_runtime_ref': calibrated['runtime_ref'],
                'stages': owner.calibration_plan(store, calibrated['profile_refs']),
                'generation': owner.ACTIVE_GENERATION, 'profile_generations': generations,
                'prior_namespaces': prior, 'model_backend': 'host-codex-app-server', 'reasoning_effort': 'medium'}
            owner.need(sum(row['model_calls_ceiling'] for row in manifest['stages']) == 12)
            owner.write_new(owner.ROOT / 'operator.json', operator)
            owner.write_new(owner.ROOT / 'bootstrap.json', manifest)
            return {'status': 'CAPTURED_NOT_ADMITTED', 'scope': SCOPE, **manifest}
        finally:
            store.close()
            accounts.close()


def inspect_scope(*, bindings=False):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.calibration_authority import CalibrationAuthority
    from jiuwenswarm.research.library import LibraryService
    value = owner.load()
    store = SQLiteRunStore(owner.ROOT / 'core', recover=False, input_root=owner.ROOT / 'input')
    try:
        binding = owner.validate_capture(store, value)
        operator = store.read_record(value['configuration_ref'])
        authority = CalibrationAuthority(store, value['calibration_runtime_ref'],
            **{key: value[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
            policy_ref=operator['cc']['plan_policy_ref'], model=None)
        for row in value['stages']:
            authority._profile(row['profile_ref'])
        starts = list(store.iter_records(kinds=('model-call-start',)))
        owner.need(len(starts) <= 12)
        if not bindings:
            return {'status': 'UTILITY_SCOPE_VALIDATED_NOT_ELIGIBILITY', 'scope': SCOPE,
                    'setup_model_calls': len(starts), 'prior_setup_model_calls': historical_setup_calls(),
                    'total_setup_model_calls': len(starts) + historical_setup_calls(),
                    'setup_model_calls_ceiling': CONFIG.get('setup_model_calls_ceiling', 12), 'stages': value['stages'],
                    'requested_model': authority.requested_model, 'backend': authority.model_backend}
        library = LibraryService(store)
        refs = {}
        for row in value['stages']:
            declaration = store.read_record(row['declaration_ref'])
            entry = library.get(declaration['identity']['name'], declaration['identity']['version_label'])
            owner.need(entry['standing'] == 'active' and entry['declaration_ref'] == row['declaration_ref'])
            association = library.association(row['declaration_ref'])
            library.check_assets.require(association['bundle_ref'], association['profile_ref'])
            admission = store.read_record(entry['admission_ref'])
            owner.need(admission['status'] == 'admitted')
            refs[row['stage']] = row['declaration_ref']
        return {'schema': 'ai4r-utility-rsi-preparation-bindings:1', 'scope': SCOPE,
            'account_id': value['account_id'], 'composition': {
                'core_root': str(owner.ROOT / 'core'), 'input_root': str(owner.ROOT / 'input'),
                'native_lease_root': str(owner.ROOT / 'native-leases'), 'account_root': str(owner.ACCOUNT_ROOT),
                'principal': {'account_id': value['account_id'], 'workspace_ids': ['local'],
                              'operations': ['upload', 'ingest', 'status'], 'audiences': ['researcher']},
                'exact_binding_refs': binding, 'work_capsule_refs': refs},
            'setup_model_calls': len(starts), 'prior_setup_model_calls': historical_setup_calls(),
            'total_setup_model_calls': len(starts) + historical_setup_calls()}
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('capture', 'diagnose', 'plan', 'calibrate', 'admit', 'bindings'))
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--configuration-sha256', required=True)
    parser.add_argument('--stage', choices=STAGES)
    parser.add_argument('--approval')
    args = parser.parse_args(argv)
    configure(args)
    if args.operation == 'capture':
        result = capture()
    elif args.operation in ('diagnose', 'bindings'):
        result = inspect_scope(bindings=args.operation == 'bindings')
    elif args.operation == 'plan':
        result = owner.plan()
    else:
        owner.need(args.stage in STAGES and args.approval is not None)
        value = owner.load()
        # Validate scope/current sources before any durable calibration request.
        inspect_scope()
        if args.operation == 'calibrate':
            from jiuwenswarm.research.state import SQLiteRunStore
            store = SQLiteRunStore(owner.ROOT / 'core', recover=False, input_root=owner.ROOT / 'input')
            try:
                used = len(list(store.iter_records(kinds=('model-call-start',))))
                row = next(r for r in value['stages'] if r['stage'] == args.stage)
                grant = owner.approval(value, args.stage, 'verifier_assets')
                owner.need(grant['max_model_calls'] == row['model_calls_ceiling'] == 6
                           and used + row['model_calls_ceiling'] <= 12
                           and historical_setup_calls() + used + row['model_calls_ceiling']
                               <= CONFIG.get('setup_model_calls_ceiling', 12))
            finally:
                store.close()
            result = asyncio.run(owner.calibrate(args.stage))
        else:
            result = asyncio.run(owner.admit(args.stage))
    print(json.dumps(result, sort_keys=True))
    return 2 if result.get('status') in ('blocked', 'BLOCKED') else 0


if __name__ == '__main__':
    raise SystemExit(main())
