"""Explicit catalog bootstrap in the isolated controller; never starts RSI.

capture/plan make no model call or eligibility claim. Each calibrate/admit
operation needs an exact root-owned grant naming the actual new local account,
immutable final pins, selected stage, budget and human action identity. Issued
calibrations retain their existing no-replay/containment rules. This tool never
admits an RSI child, activates a child, signs fixtures or starts a session.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

ROOT = Path('/var/lib/ai4r-rsi/controller/operational-bootstrap')
BASE_ROOT = ROOT
ACTIVE_GENERATION = None
GENERATION_CONFIG = Path('/run/ai4r-rsi/bootstrap-generation.json')
OPERATOR = Path('/run/ai4r-rsi/operator.json')
APPROVAL = Path('/run/ai4r-rsi/bootstrap-authorization.json')
ACCOUNT_ROOT = Path('/var/lib/ai4r-rsi/controller/accounts')
PUBLIC_ROOT = Path('/var/lib/ai4r-rsi-source-public')
LEGACY_MODEL = 'gpt-6-luna'
SCHEMA = 'ai4r-rsi-operational-bootstrap:1'
GENERATION_SCHEMA = 'ai4r-rsi-operational-bootstrap:2'
HOST_GENERATION_SCHEMA = 'ai4r-rsi-operational-bootstrap:3'
ACTIVE_SELECTION = None
SELECTION_DIRECTORY = Path('/run/ai4r-rsi/bootstrap-supersession')
OPERATIONS = frozenset(('verifier_assets', 'library_admit', 'library_standing'))


def need(value):
    if not value:
        raise ValueError('Protected isolated operational bootstrap prerequisite unavailable')


def select_generation(name):
    """A bounded sibling namespace, never an arbitrary filesystem path."""
    global ROOT, ACTIVE_GENERATION
    need(isinstance(name, str) and re.fullmatch('[a-z0-9][a-z0-9_-]{0,47}', name))
    ACTIVE_GENERATION = name
    ROOT = BASE_ROOT.with_name(BASE_ROOT.name + '.' + name)


def generation_settings(stages=None):
    if ACTIVE_GENERATION is None:
        return None
    value = protected_json(GENERATION_CONFIG, root_owned=True)
    fields = {'schema', 'generation', 'profile_generations', 'prior_namespaces'}
    if value.get('schema') in ('ai4r-rsi-bootstrap-generation:2', 'ai4r-rsi-bootstrap-generation:3', 'ai4r-rsi-bootstrap-generation:4'):
        fields.add('requested_model')
    if value.get('schema') in ('ai4r-rsi-bootstrap-generation:3','ai4r-rsi-bootstrap-generation:4'):
        fields |= {'model_backend', 'reasoning_effort'}
        need(value.get('model_backend') == 'host-codex-app-server'
             and value.get('requested_model') == 'gpt-6.1-sol' and value.get('reasoning_effort') == 'medium')
    if value.get('schema') == 'ai4r-rsi-bootstrap-generation:4':
        fields.add('selection_required')
        expected=value['selection_required']
        need(set(expected)=={'supersession_id','claim_sha256'} and re.fullmatch('[a-z][a-z0-9-]{0,47}',expected['supersession_id']) and re.fullmatch('[a-f0-9]{64}',expected['claim_sha256']))
    need(set(value) == fields
         and value['schema'] in ('ai4r-rsi-bootstrap-generation:1', 'ai4r-rsi-bootstrap-generation:2', 'ai4r-rsi-bootstrap-generation:3', 'ai4r-rsi-bootstrap-generation:4')
         and value['generation'] == ACTIVE_GENERATION and isinstance(value['profile_generations'], dict)
         and (stages is None or set(value['profile_generations']) == set(stages))
         and all(isinstance(item, str) and re.fullmatch('[a-z0-9][a-z0-9_.-]{0,63}', item)
                 for item in value['profile_generations'].values())
         and isinstance(value['prior_namespaces'], list) and len(value['prior_namespaces']) <= 32
         and len(set(value['prior_namespaces'])) == len(value['prior_namespaces'])
         and all(isinstance(item, str) and (item == 'legacy' or re.fullmatch('[a-z0-9][a-z0-9_-]{0,47}', item))
                 and item != ACTIVE_GENERATION for item in value['prior_namespaces']))
    if 'requested_model' in value:
        from jiuwenswarm.research.fixed_subscription import require_requested_model
        require_requested_model(value['requested_model'])
    return value


def selected_model():
    """Only protected finite generation metadata selects the native backend."""
    value = generation_settings()
    return LEGACY_MODEL if value is None else value.get('requested_model', LEGACY_MODEL)


def selected_backend():
    value = generation_settings()
    return None if value is None else value.get('model_backend')


def profile_generations(stages):
    value = generation_settings(stages)
    if value is None:
        return {}, []
    return value['profile_generations'], value['prior_namespaces']


def prior_namespaces_available(value):
    """A new generation cannot bypass an old active/uncertain model lease."""
    from jiuwenswarm.research_rsi.native_lease import ProfileInUse
    sealed = [BASE_ROOT if name == 'legacy' else BASE_ROOT.with_name(BASE_ROOT.name + '.' + name)
              for name in value.get('prior_namespaces', [])]
    for namespace in sealed:
        need((namespace / 'bootstrap.json').is_file() and (namespace / 'native-leases/index.sqlite').is_file())
    siblings = [ROOT, *sealed]
    for namespace in siblings:
        database = namespace / 'native-leases/index.sqlite'
        if not database.exists():
            continue
        need(not any(path.is_symlink() for path in (database, *database.parents)))
        meta = database.stat()
        need(meta.st_uid == os.geteuid() and stat.S_ISREG(meta.st_mode) and not meta.st_mode & 0o077)
        wal = database.with_name(database.name + '-wal')
        if wal.exists() and wal.stat().st_size:
            raise ProfileInUse('PROFILE_IN_USE: prior native lease history needs consistent inspection')
        db = sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_effect_leases'").fetchone()
            need(exists is not None)
            if db.execute("SELECT 1 FROM native_effect_leases WHERE state IN ('active','uncertain') LIMIT 1").fetchone():
                raise ProfileInUse('PROFILE_IN_USE: prior bootstrap generation remains active or uncertain')
        finally:
            db.close()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def protected_json(path, *, root_owned=False):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)))
    meta = path.stat()
    need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and 0 < meta.st_size <= 1024 * 1024)
    need(meta.st_uid == (0 if root_owned else 12001) and not meta.st_mode & (0o022 if root_owned else 0o077))
    for parent in path.parents:
        meta = parent.stat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid in ((0,) if root_owned else (0, 12001)) and not meta.st_mode & 0o022)
    return json.loads(path.read_bytes())


def custody():
    need(os.name == 'posix' and os.geteuid() == os.getegid() == 12001)
    need(ROOT.is_absolute() and not any(p.is_symlink() for p in (ROOT, *ROOT.parents)))
    from jiuwenswarm.research_rsi.preparation_runtime import _native_fs
    _native_fs(ROOT.parent)
    if ROOT.exists():
        meta = ROOT.stat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == meta.st_gid == 12001 and stat.S_IMODE(meta.st_mode) == 0o700)


def source_digest():
    import jiuwenswarm.research as research
    package = Path(research.__file__).resolve().parent.parent
    rows = []
    for name in ('research', 'research_assets', 'research_contracts'):
        for path in sorted((package / name).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.json', '.txt', '.md'}:
                need(not path.is_symlink())
                rows.append([path.relative_to(package).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    need(rows)
    return hashlib.sha256(encoded(rows)).hexdigest()


@contextmanager
def private_creation():
    old = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old)


def write_new(path, value):
    with Path(path).open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(encoded(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def final_operator(source, approved):
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    source = OperatorConfiguration.from_mapping(source).snapshot()
    approved = OperatorConfiguration.from_mapping(approved).snapshot()
    need({key: value for key, value in source.items() if key != 'rsi'} ==
         {key: value for key, value in approved.items() if key != 'rsi'})
    key = approved['rsi']
    need(isinstance(key.get('custodian_key_id'), str) and re.fullmatch('[a-z][a-z0-9_.:-]{0,63}', key['custodian_key_id'])
         and isinstance(key.get('custodian_public_key'), str))
    raw = base64.urlsafe_b64decode(key['custodian_public_key'] + '=' * (-len(key['custodian_public_key']) % 4))
    need(len(raw) == 32)
    return approved


def calibration_plan(store, profiles):
    rows = []
    for pin in profiles:
        profile = store.read_record(pin)
        parts = profile['id'].split(':')
        need(len(parts) >= 3 and parts[0] == 'authored-local-catalog')
        declarations = {encoded(case['declaration_ref']) for case in profile['cases']}
        need(len(declarations) == 1)
        declaration_ref = profile['cases'][0]['declaration_ref']
        declaration = store.read_record(declaration_ref, contract_id='capsule-declaration')
        semantic = sum(case['asset_kind'] == 'criteria' for case in profile['cases'])
        need(semantic <= 12)
        rows.append({'stage': parts[1], 'profile_ref': pin, 'declaration_ref': declaration_ref,
                     'model_calls_ceiling': semantic, 'case_count': len(profile['cases']),
                     'request_time_s_ceiling': 1800,
                     'self_test_count': len(declaration['guarantees'].get('self_tests', []))})
    need(len({row['stage'] for row in rows}) == len(rows))
    return rows


def capture():
    custody()
    model = selected_model()
    need(not os.environ.get('JIUWENSWARM_M1_EXTERNAL_DATASET') and not os.environ.get('JIUWENSWARM_M1_EXTERNAL_SCORING_PINS'))
    approved = protected_json(OPERATOR, root_owned=True)
    # A root-prepared empty exact submount is allowed for a named generation;
    # existing capture bytes, claims and partial work are never adopted.
    need(not ROOT.exists() or ACTIVE_GENERATION is not None and not any(ROOT.iterdir()))
    from jiuwenswarm.research.accounts import AccountStore
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.local_profile import capture_local_profile
    from jiuwenswarm.research.catalog_calibration import capture_catalog_calibration
    with private_creation():
        if not ROOT.exists():
            ROOT.mkdir(mode=0o700)
        (ROOT / 'input').mkdir(mode=0o700)
        accounts = AccountStore(ROOT / 'identity')
        store = SQLiteRunStore(ROOT / 'core', recover=False, input_root=ROOT / 'input')
        try:
            account = accounts.primary()['account_id']
            original = capture_local_profile(store, ROOT / 'source-profile', input_root=ROOT / 'input',
                                             development_builtin_catalog=False, requested_model=model,
                                             model_backend=selected_backend())
            initial = store.read_record(original['binding_ref'])
            operator = final_operator(store.read_record(initial['configuration_ref']), approved)
            configuration_ref = store.put_blob(encoded(operator), media_type='application/json')
            initial_stages = calibration_plan(store, initial['protected_options']['calibration_profile_refs'])
            generations, prior_namespaces = profile_generations([row['stage'] for row in initial_stages])
            calibrated = asyncio.run(capture_catalog_calibration(store, configuration_ref=configuration_ref,
                model_selection_profile_ref=initial['model_selection_profile_ref'], deployment_ref=initial['deployment_ref'],
                profile_generations=generations))
            binding = dict(initial, configuration_ref=configuration_ref)
            binding['protected_options'] = dict(initial['protected_options'], development_builtin_catalog=False,
                integrated_workflows=False, paper_summary_workflow=False, isolated_helper_scope='rsi-screening-helper:1',
                calibration_runtime_ref=calibrated['runtime_ref'], calibration_profile_refs=calibrated['profile_refs'],
                calibration_limitations=calibrated['limitations'])
            binding_ref = store.put_blob(encoded(binding), media_type='application/json')
            manifest = {'schema': SCHEMA, 'account_id': account, 'root': str(ROOT), 'model': model,
                'installed_source_sha256': source_digest(), 'binding_ref': binding_ref,
                'configuration_ref': configuration_ref, 'model_selection_profile_ref': initial['model_selection_profile_ref'],
                'deployment_ref': initial['deployment_ref'], 'calibration_runtime_ref': calibrated['runtime_ref'],
                'stages': calibration_plan(store, calibrated['profile_refs'])}
            if ACTIVE_GENERATION is not None:
                manifest.update(schema=GENERATION_SCHEMA, generation=ACTIVE_GENERATION,
                                profile_generations=generations, prior_namespaces=prior_namespaces)
                if selected_backend() is not None:
                    manifest.update(schema=HOST_GENERATION_SCHEMA, model_backend=selected_backend(), reasoning_effort='medium')
            write_new(ROOT / 'operator.json', operator)
            write_new(ROOT / 'bootstrap.json', manifest)
            return {'status': 'CAPTURED_NOT_ADMITTED', **manifest}
        finally:
            store.close()
            accounts.close()


def load_original():
    custody()
    value = protected_json(ROOT / 'bootstrap.json')
    fields = {'schema', 'account_id', 'root', 'model', 'installed_source_sha256', 'binding_ref', 'configuration_ref',
              'model_selection_profile_ref', 'deployment_ref', 'calibration_runtime_ref', 'stages'}
    if ACTIVE_GENERATION is not None:
        fields |= {'generation', 'profile_generations', 'prior_namespaces'}
        if selected_backend() is not None:
            fields |= {'model_backend', 'reasoning_effort'}
            need(value.get('schema') == HOST_GENERATION_SCHEMA and value.get('model_backend') == selected_backend()
                 and value.get('reasoning_effort') == 'medium')
        else:
            need(value.get('schema') == GENERATION_SCHEMA)
        need(value.get('generation') == ACTIVE_GENERATION)
        generations, prior_namespaces = profile_generations([row['stage'] for row in value['stages']])
        need(value.get('profile_generations') == generations and value.get('prior_namespaces') == prior_namespaces)
    else:
        need(value.get('schema') == SCHEMA)
    need(set(value) == fields and value['root'] == str(ROOT)
         and value['model'] == selected_model() and value['installed_source_sha256'] == source_digest())
    return value


def load():
    """Original Root generation first; optional completed Root selection second."""
    global ACTIVE_SELECTION
    original=load_original()
    spec=importlib.util.spec_from_file_location('selected_bootstrap_owner',Path(__file__).with_name('rsi_bootstrap_supersession.py'))
    owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
    selected,ACTIVE_SELECTION=owner.selected_bootstrap(original,(ROOT/'bootstrap.json').read_bytes(),path=SELECTION_DIRECTORY,expected=(generation_settings() or {}).get('selection_required'))
    return selected


def selected_call_budget(store,value,row,grant):
    if ACTIVE_SELECTION is None:return
    request=ACTIVE_SELECTION['request'];caps=request['budget_caps']
    need(grant['max_model_calls']==row['model_calls_ceiling'])
    calls=list(store.iter_records(kinds=('model-call-start',)))
    maximum=caps['setup'] if row['stage']=='delivery' else caps['pre_delivery']
    need(len(calls)+row['model_calls_ceiling']<=maximum)
    need(caps['including_rsi']==caps['setup']+2)


def plan():
    value = load()
    return {'status': 'CAPTURED_NOT_ADMITTED', 'account_id': value['account_id'],
            'configuration_ref': value['configuration_ref'], 'stages': value['stages'],
            'total_model_calls_ceiling': sum(row['model_calls_ceiling'] for row in value['stages']),
            'total_request_time_s_ceiling': sum(row['request_time_s_ceiling'] for row in value['stages']),
            'required_root_approval': str(APPROVAL),
            'remaining_session_gates': ['independent_fixture_review', 'draft_security_qualification',
                'real_helper_calibration_and_headroom', 'final_security_qualification', 'exact_live_doctor']}


def approval(value, stage, operation):
    grant = protected_json(APPROVAL, root_owned=True)
    fields = {'schema', 'account_id', 'configuration_ref', 'model_selection_profile_ref', 'deployment_ref',
              'operations', 'stage', 'action_id', 'max_model_calls', 'max_time_s', 'expires_at'}
    need(set(grant) == fields and grant['schema'] == 'ai4r-rsi-bootstrap-authorization:1'
         and all(grant[key] == value[key] for key in ('account_id', 'configuration_ref', 'model_selection_profile_ref', 'deployment_ref'))
         and grant['stage'] == stage and isinstance(grant['action_id'], str)
         and re.fullmatch('[a-z0-9][a-z0-9_.:-]{0,95}', grant['action_id'])
         and isinstance(grant['operations'], list) and set(grant['operations']) <= OPERATIONS
         and operation in grant['operations'])
    expires = datetime.fromisoformat(grant['expires_at'].replace('Z', '+00:00'))
    need(expires.tzinfo is not None and 0 < (expires - datetime.now(timezone.utc)).total_seconds() <= 86400)
    need(type(grant['max_model_calls']) is int and 0 <= grant['max_model_calls'] <= 12
         and type(grant['max_time_s']) is int and 0 < grant['max_time_s'] <= 1800)
    return grant


def actor_for(accounts, value, grant):
    from jiuwenswarm.research.contracts import Principal
    need(accounts.primary()['account_id'] == value['account_id'] == grant['account_id'])
    return Principal(value['account_id'], frozenset({'local'}), frozenset(grant['operations']), frozenset({'researcher', 'reviewer'}))


def validate_capture(store, value):
    """Rejoin every effect to originals, not editable manifest counters."""
    from jiuwenswarm.research.fixed_subscription import deployment_model, deployment_backend, require_profile_model
    binding = store.read_record(value['binding_ref'])
    need(all(binding.get(key) == value[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')))
    need(binding['protected_options']['development_builtin_catalog'] is False
         and binding['protected_options'].get('integrated_workflows') is False
         and binding['protected_options'].get('paper_summary_workflow') is False
         and binding['protected_options'].get('isolated_helper_scope') == 'rsi-screening-helper:1'
         and binding['protected_options']['calibration_runtime_ref'] == value['calibration_runtime_ref']
         and deployment_model(store.read_record(value['deployment_ref'])) == value['model'] == selected_model())
    expected_backend = selected_backend() or ('spark' if selected_model() == 'Qwen3.8-27B-NVFP4' else 'codex')
    need(deployment_backend(store.read_record(value['deployment_ref'])) == expected_backend)
    profile = store.read_record(binding['protected_options']['profile_ref'])
    require_profile_model(profile, value['model'], backend=expected_backend)
    selection = store.read_record(value['model_selection_profile_ref'], contract_id='model-selection-profile')
    deployment = store.read_record(value['deployment_ref'])
    need(selection['id'] == profile['id'] + '.selection'
         and deployment['id'] == profile['id'] + '.deployment'
         and selection['approved_model_ids'] == ['codex-cli-default'] and selection['policy_mode'] == 'fixed_baseline')
    runtime = store.read_record(value['calibration_runtime_ref'])
    need(all(runtime[key] == value[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref'))
         and calibration_plan(store, runtime['approved_profile_refs']) == value['stages'])
    return binding


async def calibrate(stage):
    value = load()
    row = next((row for row in value['stages'] if row['stage'] == stage), None)
    need(row is not None)
    grant = approval(value, stage, 'verifier_assets')
    need(grant['max_model_calls'] >= row['model_calls_ceiling'])
    prior_namespaces_available(value)
    from jiuwenswarm.research.accounts import AccountStore
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.calibration_authority import CalibrationAuthority
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.native_ports import capture_native_record, capture_governed_trace_record
    from jiuwenswarm.research_rsi.spark_backend import subscription_for_deployment
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.native_lease import NativeEffectLease, native_completion_proof
    with private_creation():
        accounts = AccountStore(ROOT / 'identity')
        store = SQLiteRunStore(ROOT / 'core', recover=False, input_root=ROOT / 'input')
        leases = RecordStore(ROOT / 'native-leases')
        scope = leases.put({'schema': 'ai4r-rsi-bootstrap-native-scope:1', 'account_root': str(ACCOUNT_ROOT), 'root': str(ROOT)})
        lease = NativeEffectLease(leases, scope)
        lease.assert_available()  # no native owner can start before this guard
        owner = None
        lease_ref = None
        starts = set()
        try:
            actor = actor_for(accounts, value, grant)
            binding = validate_capture(store, value)
            selected_call_budget(store,value,row,grant)
            owner = subscription_for_deployment(ACCOUNT_ROOT, store.read_record(value['deployment_ref']))
            owner.set_account_observer(store.append_record)
            operator = store.read_record(value['configuration_ref'])
            authority = CalibrationAuthority(store, value['calibration_runtime_ref'],
                configuration_ref=value['configuration_ref'], model_selection_profile_ref=value['model_selection_profile_ref'],
                deployment_ref=value['deployment_ref'], policy_ref=operator['cc']['plan_policy_ref'])
            owner.set_governed_trace_writer(lambda kind, record: capture_governed_trace_record(store, kind, record), store.put_blob)
            bridge = GovernedBridge(persist=store.append_record, authorize=authority.authorize_model_context,
                revalidate=authority.authorize_model_dispatch, subscription_service=owner, read_evidence=store.read_blob,
                capture_native=lambda kind, record, *, context: capture_native_record(store, kind, record, context=context))
            authority.model = bridge
            authority.register(row['profile_ref'], actor)
            starts = {encoded(item['ref']) for item in store.iter_records(kinds=('model-call-start',))}
            lease_ref = lease.start('catalog-calibration:' + grant['action_id'], row['profile_ref'])
            remaining = min(grant['max_time_s'], (datetime.fromisoformat(grant['expires_at'].replace('Z', '+00:00')) - datetime.now(timezone.utc)).total_seconds())
            need(remaining > 0)
            result = await asyncio.wait_for(authority.execute(row['profile_ref'], actor, grant['action_id']), remaining)
            return {'status': result['status'], 'stage': stage, 'result': result,
                    'session_started': False, 'candidate_admitted': False}
        finally:
            try:
                if owner is not None:
                    await owner.transport.close()
                if lease_ref is not None:
                    observed = [item for item in store.iter_records(kinds=('model-call-start',)) if encoded(item['ref']) not in starts]
                    known, proof = native_completion_proof(store, observed)
                    (lease.complete if known else lease.uncertain)(lease_ref, proof)
            finally:
                leases.close()
                store.close()
                accounts.close()


async def admit(stage):
    value = load()
    row = next((row for row in value['stages'] if row['stage'] == stage), None)
    need(row is not None)
    grant = approval(value, stage, 'library_admit')
    need({'library_admit', 'library_standing', 'verifier_assets'} <= set(grant['operations']))
    # Admission self-tests remain a genuine confined-executor obligation. No
    # metadata-only substitute or callback selected by the grant is accepted.
    need(row['self_test_count'] == 0)
    from jiuwenswarm.research.accounts import AccountStore
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.checks.calibration_runtime import prepare_calibration_checks
    with private_creation():
        accounts = AccountStore(ROOT / 'identity')
        store = SQLiteRunStore(ROOT / 'core', recover=False, input_root=ROOT / 'input')
        try:
            actor = actor_for(accounts, value, grant)
            validate_capture(store, value)
            assets = await prepare_calibration_checks(store, CheckRegistry())
            need(stage in assets and assets[stage]['declaration_ref'] == row['declaration_ref'])
            asset = assets[stage]
            declaration = store.read_record(asset['declaration_ref'])
            need(not declaration['identity'].get('lineage') and not declaration['guarantees'].get('self_tests'))
            library = LibraryService(store)
            library.check_assets.bind_calibration_runtime(value['calibration_runtime_ref'],
                configuration_ref=value['configuration_ref'], model_selection_profile_ref=value['model_selection_profile_ref'],
                deployment_ref=value['deployment_ref'])
            library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
            policy = store.read_record(store.read_record(value['configuration_ref'])['cc']['plan_policy_ref'])
            from jiuwenswarm.research.contracts import ResearchError
            identity = declaration['identity']
            try:
                prior = library.get(identity['name'], identity['version_label'])
            except ResearchError as error:
                if error.code != 'library_membership':
                    raise
                prior = None
            if prior is not None:
                need(prior['declaration_ref'] == asset['declaration_ref'] and prior['body_refs'] == asset['body_refs']
                     and prior['effect_scope'] == 'live_plans' and prior['standing'] in {'inactive', 'active'})
                admission = prior['admission_ref']
            else:
                admission = await library.admit(asset['declaration_ref'], asset['body_refs'], actor,
                                                memory_mb=policy['aggregate_limits']['memory_mb'])
            actual = store.read_record(admission, contract_id='library-admission')
            if actual['status'] != 'admitted':
                return {'status': 'BLOCKED', 'admission_ref': admission, 'reasons': actual['reasons']}
            if prior is not None and prior['standing'] == 'active':
                return {'status': 'PARENT_ALREADY_ADMITTED_ACTIVE', 'stage': stage, 'admission_ref': admission,
                        'session_started': False, 'rsi_child_activated': False}
            standing = library.set_standing(identity['name'], identity['version_label'], 'active', actor,
                reason='Explicit root-approved admission of the exact installed bootstrap catalog parent')
            return {'status': 'PARENT_ADMITTED_ACTIVE', 'stage': stage, 'admission_ref': admission,
                    'standing_ref': standing, 'session_started': False, 'rsi_child_activated': False}
        finally:
            store.close()
            accounts.close()


class CapturedSourceReader:
    """Read-only captured originals plus a verifying installed-factory adapter.

    The factory may calculate pins, but cannot capture anything into Core.
    Every calculated blob must already exist with identical captured bytes.
    """
    def __init__(self, root):
        self.root = Path(root)
        self.database = self.root / 'state/research.sqlite3'
        # WAL-mode databases without an SHM file can still try to create one
        # under mode=ro. Immutable reads are safe only for quiescent originals:
        # never ignore committed WAL frames or continue across a writer.
        self.original_metadata = self._metadata()
        self.connection = sqlite3.connect(self.database.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            self.connection.execute('PRAGMA query_only=ON')
            self._unchanged()
        except BaseException:
            self.connection.close()
            raise

    def _metadata(self):
        need(not any(path.is_symlink() for path in (self.database, *self.database.parents)))
        result = []
        for path in (self.database, self.database.with_name(self.database.name + '-wal'),
                     self.database.with_name(self.database.name + '-shm')):
            if not os.path.lexists(path):
                need(path != self.database)
                result.append(None)
                continue
            meta = path.lstat()
            need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1)
            if path.name.endswith('-wal'):
                need(meta.st_size == 0)
            result.append((meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns, meta.st_ctime_ns))
        return tuple(result)

    def _unchanged(self):
        need(self._metadata() == self.original_metadata)

    def close(self):
        self.connection.close()

    def read_blob(self, ref):
        from jiuwenswarm.research.contracts import validate
        self._unchanged()
        validate('Ref', ref)
        row = self.connection.execute('SELECT sha256 FROM artifacts WHERE id=?', (ref['id'],)).fetchone()
        need(row is not None and row[0] == ref['sha256'])
        path = self.root / 'artifacts/sha256' / ref['sha256'][:2] / ref['sha256']
        need(not any(p.is_symlink() for p in (path, *path.parents)))
        raw = path.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == ref['sha256'])
        self._unchanged()
        return raw

    def read_record(self, ref, *, contract_id=None):
        from jiuwenswarm.research.contracts import validate
        value = json.loads(self.read_blob(ref))
        if contract_id:
            validate(contract_id, value)
        return value

    def put_blob(self, raw, **kwargs):
        digest = hashlib.sha256(raw).hexdigest()
        ref = {'id': 'blob:' + digest, 'sha256': digest}
        need(self.read_blob(ref) == raw)
        return ref

    def put_record(self, contract_id, value, **kwargs):
        from jiuwenswarm.research.contracts import validate
        from jiuwenswarm.research.state import json_bytes
        validate(contract_id, value)
        return self.put_blob(json_bytes(value))


def parent_public_closure(store, value, asset):
    """Finite authored source positions, never a recursive Ref traversal."""
    validate_capture(store, value)
    row = next(row for row in value['stages'] if row['stage'] == 'screening')
    need(row['declaration_ref'] == asset['declaration_ref'])
    declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
    need(not declaration['identity'].get('lineage'))
    body = {}
    for item in declaration['identity']['body']:
        ref = asset['body_refs'][item['path']]
        need(ref['sha256'] == item['sha256'])
        body[item['path']] = ref
    carrier = declaration['identity']['carrier']
    need(carrier['ref'] in body and body[carrier['ref']]['sha256'] == carrier['sha256'])
    external = {}
    for item in declaration['needs']['external']:
        pin = item.get('pin')
        need(isinstance(pin, dict) and set(pin) == {'ref', 'sha256'})
        ref = asset['body_refs'][pin['ref']]
        need(ref['sha256'] == pin['sha256'] and pin['ref'] not in body)
        external[pin['ref']] = ref
    need(set(body) | set(external) == set(asset['body_refs']))
    bundle = store.read_record(asset['bundle_ref'], contract_id='check-bundle')
    profile = store.read_record(asset['profile_ref'], contract_id='checking-profile')
    need(all(check['runner_ref'] == asset['runner_ref'] for check in bundle['checks']))
    runner = store.read_record(asset['runner_ref'])
    need(set(runner) == {'implementation', 'files'} and runner['implementation'] == 'research.checks.stages'
         and set(runner['files']) == {'checks/stages.py', 'checks/research.py', 'science.py', 'environment.py', 'target_comparisons.py'})
    sources = {'instruction_ref': profile['instruction_ref'], 'runner_ref': asset['runner_ref'],
               'runner_source_refs': runner['files']}
    refs = [value['configuration_ref'], asset['declaration_ref'], *body.values(), *external.values(),
            asset['bundle_ref'], asset['profile_ref'], sources['instruction_ref'], sources['runner_ref'],
            *sources['runner_source_refs'].values()]
    refs = list({encoded(ref): ref for ref in refs}.values())
    # Verify the complete finite set before the first publication.
    originals = [(ref, store.read_blob(ref)) for ref in refs]
    result = {'schema': 'ai4r-rsi-parent-source-export:1', 'status': 'NOT_ADMISSION', 'stage': 'screening',
              'installed_source_sha256': value['installed_source_sha256'],
              'configuration_ref': value['configuration_ref'], 'parent_declaration_ref': asset['declaration_ref'],
              'parent_body_refs': body, 'external_refs': external, 'bundle_ref': asset['bundle_ref'],
              'checking_profile_ref': asset['profile_ref'], 'required_test_refs': [asset['bundle_ref'], asset['profile_ref']],
              'guard_source_refs': sources, 'public_original_refs': refs}
    return result, originals


def export_parent(stage):
    need(stage == 'screening')
    value = load()
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    store = CapturedSourceReader(ROOT / 'core')
    try:
        # Normal release-pin verification stays enabled. All put operations in
        # this adapter only verify an already captured exact source original.
        result, originals = parent_public_closure(store, value, build_research_assets(store)['screening'])
        meta = PUBLIC_ROOT.lstat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 12001 and meta.st_gid == 13000
             and stat.S_IMODE(meta.st_mode) == 0o2750)
        public = OriginalBytes(PUBLIC_ROOT, writable=True)
        for ref, raw in originals:
            public.put_ref(ref, raw)
        manifest_ref = public.put(result)
        return {**result, 'export_manifest_ref': manifest_ref}
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('capture', 'plan', 'calibrate', 'admit', 'export-parent'))
    parser.add_argument('--stage')
    parser.add_argument('--generation', help='Explicit fresh sibling namespace; Root must approve its complete profile-generation map')
    args = parser.parse_args(argv)
    if args.generation is not None:
        select_generation(args.generation)
    if args.operation == 'capture' and args.generation is None:
        parser.error('fresh capture requires an explicit --generation; existing captures are never migrated')
    if args.operation in {'calibrate', 'admit', 'export-parent'} and not args.stage:
        parser.error('an exact captured --stage is required')
    if args.operation in {'capture', 'plan'} and args.stage:
        parser.error('stage applies only to separately approved effectful operations')
    result = capture() if args.operation == 'capture' else plan() if args.operation == 'plan' else export_parent(args.stage) if args.operation == 'export-parent' else asyncio.run(
        calibrate(args.stage) if args.operation == 'calibrate' else admit(args.stage))
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] not in {'BLOCKED', 'blocked'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
