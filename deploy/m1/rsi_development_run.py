"""Finite development composition of existing RSI components, never qualification.

Root reviews ``plan`` and supplies that exact digest to ``run``.  A run consumes
the Root claim before dropping authority; interrupted claims are never replayed.
Work contracts must already exist in the ordinary isolated Core store.  This
helper does not install/admit Capsules, change checking assets, or read fixtures.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import inspect
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import select
import re
import stat
import sys
import time
from types import SimpleNamespace

AUTH_SCHEMA = 'ai4r-rsi-development-authorization:1'
RESULT_SCHEMA = 'ai4r-rsi-development-result:1'
SUCCESS_FIELDS = frozenset(('schema id status security security_campaigns hidden_evaluation final_evaluation '
    'qualification_ref package_ref admission_ref activation_ref diagnosis_ref diagnosis_capture_ref proposal_start_ref '
    'proposal_prompt_ref proposal_response_ref generation_evidence_refs model_calls parent_body_ref parent_declaration_ref '
    'target_profile_ref visible_context_ref rationale generating_model parent_visible candidate_visible candidate limitations '
    'evaluator_exit_code').split())
ERROR_FIELDS = frozenset(('schema id status security security_campaigns hidden_evaluation final_evaluation '
    'exception_type diagnostic_sha256 model_calls qualification_ref package_ref admission_ref activation_ref limitations evaluator_exit_code').split())
MAX_BYTES = 4 * 1024 * 1024
V18_EXECUTOR_SHA256 = '25c77a8c6830e32e83a6b77334d82e12350912fe33b312df8d5b1aad26bc4715'
FIELDS = ('schema id expires_at isolation_root core_root account_root record_root work_root '
          'parent_directory input_root cgroup_root forbidden_roots principal exact_binding_refs native_lease_root '
          'run_contexts diagnosis_contract_ref proposal_contract_ref native_scope_ref '
          'parent_declaration_ref target_profile_ref visible_context_ref preparation_ref '
          'target_kind limits observed_symptom authorized_component work_capsule_refs worker public_original_refs '
          'seed_receipt launch_guard_receipt evaluator_root host_binding_ref host_id').split()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def closed_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'DUPLICATE_JSON_FIELD')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def pin(value):
    need(isinstance(value, dict) and set(value) == {'id', 'sha256'}
         and isinstance(value['id'], str) and bool(value['id'])
         and isinstance(value['sha256'], str) and len(value['sha256']) == 64
         and all(c in '0123456789abcdef' for c in value['sha256']), 'INVALID_REF')


def validate_public_preparation(preparation, authorization, required_test_refs):
    need(isinstance(preparation, dict) and set(preparation) == {
        'schema', 'parent_declaration_ref', 'target_profile_ref', 'visible_context_ref',
        'required_test_refs', 'development_export_ref', 'security_campaigns', 'qualification'},
        'CLOSED_PUBLIC_DEVELOPMENT_PREPARATION_REQUIRED')
    need(preparation['schema'] == 'ai4r-rsi-development-public-preparation:1'
         and preparation['security_campaigns'] == 'DEFERRED' and preparation['qualification'] is False,
         'PUBLIC_PREPARATION_IS_NOT_QUALIFICATION')
    need(all(preparation[key] == authorization[key] for key in
             ('parent_declaration_ref', 'target_profile_ref', 'visible_context_ref'))
         and preparation['required_test_refs'] == required_test_refs, 'PUBLIC_PREPARATION_BINDINGS_DIFFER')
    pin(preparation['development_export_ref'])
    return preparation


def validate_result(value):
    need(isinstance(value, dict) and set(value) in (SUCCESS_FIELDS, ERROR_FIELDS)
         and value['schema'] == RESULT_SCHEMA, 'CLOSED_DEVELOPMENT_RESULT_REQUIRED')
    need(value['security'] == 'UNQUALIFIED' and value['security_campaigns'] == 'DEFERRED'
         and value['hidden_evaluation'] == value['final_evaluation'] == 'NOT_RUN', 'DEFERRED_RESULT_CANNOT_CLAIM_QUALIFICATION')
    need(all(value[key] is None for key in ('qualification_ref', 'package_ref', 'admission_ref', 'activation_ref')),
         'DEVELOPMENT_RESULT_GRANTS_NO_LIBRARY_AUTHORITY')
    if set(value) == SUCCESS_FIELDS:
        need(value['status'] in {'VISIBLE_EVALUATED_UNQUALIFIED', 'ERROR_NO_REPLAY'}
             and type(value['model_calls']) is int and value['model_calls'] == 2, 'EXACT_ACTUAL_TWO_CALL_RESULT_REQUIRED')
        for name in ('parent_visible', 'candidate_visible'):
            row = value[name]
            need(set(row) == {'passed', 'passed_count', 'executions', 'evidence_refs', 'visible_selection_time_s'}
                 and row['executions'] == 12 and type(row['passed_count']) is int and 0 <= row['passed_count'] <= 12
                 and row['passed'] is (row['passed_count'] == 12), 'ACTUAL_PUBLIC_EVALUATION_RESULT_REQUIRED')
    else:
        need(value['status'] == 'ERROR_NO_REPLAY' and value['model_calls'] is None, 'ERROR_RESULT_MUST_NOT_GUESS_CALL_COUNT')
    return value


def protected(path, *, owner=0, directory=False, maximum=MAX_BYTES):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_PROTECTED_PATH_REQUIRED')
    for parent in (path, *path.parents):
        info = parent.lstat()
        need(not stat.S_ISLNK(info.st_mode), 'SYMLINK_PATH_DENIED')
        if parent != path:
            need(info.st_uid in {0, owner} and not info.st_mode & 0o022,
                 'WRITABLE_PATH_ANCESTRY')
    info = path.lstat()
    need(info.st_uid == owner and not info.st_mode & 0o022, 'PATH_CUSTODY_DIFFERS')
    need(stat.S_ISDIR(info.st_mode) if directory else
         stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= maximum,
         'PROTECTED_PATH_KIND_DIFFERS')
    return path


def validate_authorization(value):
    from datetime import datetime, timezone
    need(isinstance(value, dict) and set(value) == set(FIELDS)
         and value['schema'] == AUTH_SCHEMA, 'CLOSED_DEVELOPMENT_AUTHORIZATION_REQUIRED')
    need(isinstance(value['id'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value['id']), 'INVALID_RUN_ID')
    expiry = datetime.fromisoformat(value['expires_at'].replace('Z', '+00:00'))
    need(expiry.tzinfo is not None and 0 < (expiry-datetime.now(timezone.utc)).total_seconds() <= 86400,
         'DEVELOPMENT_AUTHORIZATION_EXPIRED')
    expected = {'max_attempts': 1, 'max_no_progress': 1, 'wall_s': 3600,
                'per_call_s': 120, 'session_query_limit': 2, 'lifetime_query_limit': 2}
    need(value['limits'] == expected and all(type(n) is int for n in value['limits'].values()),
         'DEVELOPMENT_BUDGET_MUST_BE_ONE_CANDIDATE_TWO_CALLS')
    need(value['target_kind'] in {'ranking-v1', 'normalize-labels-v1'}, 'UNREGISTERED_HELPER')
    need(set(value['work_capsule_refs']) == {'intent', 'verifier'}, 'LITERAL_INTENT_VERIFIER_SUBSET_REQUIRED')
    for ref in value['work_capsule_refs'].values(): pin(ref)
    need(set(value['worker']) == {'contract_ref', 'environment_ref', 'hardware_ref', 'memory_mb', 'pids_max', 'timeout_s'},
         'CLOSED_WORKER_LIMITS_REQUIRED')
    for key in ('contract_ref', 'environment_ref', 'hardware_ref'): pin(value['worker'][key])
    for key, maximum in (('memory_mb', 256), ('pids_max', 16), ('timeout_s', 5)):
        need(type(value['worker'][key]) is int and 0 < value['worker'][key] <= maximum, 'WORKER_LIMIT_EXCEEDS_DEVELOPMENT_CEILING')
    for key in ('diagnosis_contract_ref', 'proposal_contract_ref', 'native_scope_ref',
                'parent_declaration_ref', 'target_profile_ref', 'visible_context_ref', 'preparation_ref', 'host_binding_ref'):
        pin(value[key])
    need(value['diagnosis_contract_ref'] != value['proposal_contract_ref'], 'DISTINCT_WORK_CONTEXTS_REQUIRED')
    for key in ('seed_receipt', 'launch_guard_receipt'):
        record = value[key]
        need(isinstance(record, dict) and set(record) == {'path', 'sha256'}, 'ROOT_RECEIPT_PIN_REQUIRED')
        need(isinstance(record['path'], str) and PurePosixPath(record['path']).is_absolute()
             and '..' not in PurePosixPath(record['path']).parts, 'ROOT_RECEIPT_PATH_REQUIRED')
        pin({'id': record['path'], 'sha256': record['sha256']})
    need(isinstance(value['public_original_refs'], list) and 1 <= len(value['public_original_refs']) <= 96,
         'FINITE_ROOT_APPROVED_PUBLIC_CLOSURE_REQUIRED')
    for ref in value['public_original_refs']: pin(ref)
    need(len({encoded(ref) for ref in value['public_original_refs']}) == len(value['public_original_refs']),
         'DUPLICATE_PUBLIC_ORIGINAL')
    exact = value['exact_binding_refs']
    need(set(exact) == {'configuration_ref', 'model_selection_profile_ref', 'deployment_ref',
                        'workspace_id', 'protected_options'}, 'EXACT_BINDINGS_REQUIRED')
    need(isinstance(value['host_id'],str) and 0<len(value['host_id'])<=256,'PINNED_HOST_ID_REQUIRED')
    for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref'):
        pin(exact[key])
    need(exact['protected_options'].get('development_builtin_catalog') is False,
         'NO_BUILTIN_ADMISSION_BYPASS')
    need(set(value['principal']) == {'account_id', 'workspace_ids', 'operations', 'audiences'}
         and exact['workspace_id'] in value['principal']['workspace_ids'], 'WORKSPACE_PRINCIPAL_DIFFERS')
    need(isinstance(value['run_contexts'], dict) and len(value['run_contexts']) == 2,
         'EXACTLY_TWO_GOVERNED_WORK_CONTEXTS_REQUIRED')
    need(isinstance(value['forbidden_roots'], list) and bool(value['forbidden_roots']), 'FORBIDDEN_ROOTS_REQUIRED')
    need(all(isinstance(p, str) and PurePosixPath(p).is_absolute() and '..' not in PurePosixPath(p).parts
             for p in value['forbidden_roots']), 'ABSOLUTE_FORBIDDEN_ROOTS_REQUIRED')
    for key in ('observed_symptom', 'authorized_component'):
        need(isinstance(value[key], str) and 0 < len(value[key]) <= 4096, 'BOUNDED_CONTEXT_REQUIRED')
    return value


class Originals:
    """Checkpointed original Core + finite capture bytes; no recovery/writes."""
    def __init__(self, value):
        self.value = value
        path = Path(value['core_root'])/'state/research.sqlite3'
        for suffix in ('-wal', '-journal'):
            side = Path(str(path)+suffix)
            need(not side.exists() or side.stat().st_size == 0, 'CHECKPOINTED_STOPPED_CORE_REQUIRED')
        self.db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)
        self.db.execute('PRAGMA query_only=ON'); self.db.execute('PRAGMA trusted_schema=OFF')
        self.hashes = {}

    def read(self, ref):
        pin(ref)
        row = self.db.execute('SELECT sha256 FROM artifacts WHERE id=?', (ref['id'],)).fetchone()
        if row is not None:
            need(row[0] == ref['sha256'], 'CORE_ORIGINAL_REF_DIFFERS')
            path = Path(self.value['core_root'])/'artifacts/sha256'/ref['sha256'][:2]/ref['sha256']
        else:
            need(ref['id'] == ref['sha256']+'.json', 'UNINDEXED_OPAQUE_ORIGINAL')
            candidates = [Path(self.value[key])/(ref['sha256']+'.json') for key in ('record_root', 'native_lease_root')]
            matches = [p for p in candidates if p.exists()]
            need(bool(matches), 'FINITE_ORIGINAL_ABSENT'); path = matches[0]
        raw = protected(path, owner=12001).read_bytes()
        need(digest(raw) == ref['sha256'], 'ORIGINAL_BYTES_CHANGED')
        self.hashes[str(path)] = digest(raw)
        return raw

    def get(self, ref): return closed_json(self.read(ref))

    def close(self): self.db.close()


def original_preflight(value, reader):
    """Validate identities before Root claim; canonical runner rechecks later."""
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.fixed_subscription import deployment_model, require_profile_model
    from jiuwenswarm.research_rsi.profiles import freeze_profile
    exact = value['exact_binding_refs']
    raw_binding=reader.get(value['host_binding_ref'])
    need(raw_binding==dict(exact,host_id=value['host_id']),'ORIGINAL_HOST_BINDING_PROJECTION_DIFFERS')
    public = {encoded(ref) for ref in value['public_original_refs']}
    def public_ref(ref):
        need(encoded(ref) in public, 'NONPUBLIC_WORK_CONTEXT_REF')
        reader.read(ref)
    deployment = reader.get(exact['deployment_ref'])
    need(deployment_model(deployment) == 'gpt-6.1-sol', 'EXACT_SOL_REQUIRED')
    profile = reader.get(exact['protected_options']['profile_ref'])
    from jiuwenswarm.research.fixed_subscription import HOST_CODEX_BACKEND
    require_profile_model(profile, 'gpt-6.1-sol', backend=HOST_CODEX_BACKEND)
    selection = reader.get(exact['model_selection_profile_ref'])
    need(selection['policy_mode'] == 'fixed_baseline' and selection['approved_model_ids'] == ['codex-cli-default'],
         'FIXED_NATIVE_MODEL_SELECTION_REQUIRED')
    target = reader.get(value['target_profile_ref']); parent = reader.get(value['parent_declaration_ref'])
    validate('capsule-declaration', parent); freeze_profile(target, parent, validate)
    need(target['configuration_ref'] == exact['configuration_ref'], 'TARGET_CONFIGURATION_DIFFERS')
    need(target['parent_declaration_ref'] == value['parent_declaration_ref'], 'TARGET_PARENT_DIFFERS')
    public_ref(target['parent_ref']); public_ref(value['visible_context_ref'])
    visible = reader.get(value['visible_context_ref'])
    public_ref(value['preparation_ref'])
    validate_public_preparation(reader.get(value['preparation_ref']), value, target['required_test_refs'])
    need(set(visible) == {'context', 'mandatory_fixtures', 'required_test_refs'}, 'CLOSED_PUBLIC_CONTEXT_REQUIRED')
    need(len(visible['mandatory_fixtures']) == 12 and visible['required_test_refs'] == target['required_test_refs']
         and len({encoded(t['test_ref']) for t in visible['mandatory_fixtures']}) == 12, 'TWELVE_PUBLIC_TESTS_REQUIRED')
    from jiuwenswarm.research_rsi.targets import registered_helper
    helper = registered_helper(value['target_kind'])
    for row in visible['mandatory_fixtures']:
        need(set(row) == {'input_ref', 'test_ref'}, 'CLOSED_PUBLIC_FIXTURE_REQUIRED')
        need(row['test_ref'] in target['required_test_refs'], 'FOREIGN_PUBLIC_TEST')
        public_ref(row['input_ref']); public_ref(row['test_ref'])
        helper.validate_visible_inputs(reader.get(row['input_ref']))
    parent_root = Path(value['parent_directory'])
    expected = {row['path']: row['sha256'] for row in parent['identity']['body']}
    for dependency in parent['needs']['external']:
        ref = dependency.get('pin')
        if isinstance(ref, dict) and set(ref) == {'ref', 'sha256'}: expected[ref['ref']] = ref['sha256']
    actual = {p.relative_to(parent_root).as_posix(): p for p in parent_root.rglob('*') if p.is_file() or p.is_symlink()}
    need(set(actual) == set(expected), 'EXACT_PARENT_FILE_CLOSURE_REQUIRED')
    for name, path in actual.items():
        need(digest(protected(path, owner=12001).read_bytes()) == expected[name], 'PARENT_FILE_BYTES_DIFFER')
    scope = reader.get(value['native_scope_ref'])
    validate_native_scope(value, scope)
    for stage, ref in value['work_capsule_refs'].items():
        declaration = reader.get(ref); validate('capsule-declaration', declaration)
        need(declaration['identity']['name'] == ('research.verifier' if stage == 'verifier' else 'intent.compiler'),
             'INTENDED_WORK_CAPSULE_REQUIRED')
    contracts = []
    for key in ('diagnosis_contract_ref', 'proposal_contract_ref'):
        contract_ref = value[key]; contract = reader.get(contract_ref); validate('subnode-execution-contract', contract)
        need(len(contract['bindings']) == 1, 'SINGLE_GOVERNED_WORK_BINDING_REQUIRED')
        binding = contract['bindings'][0]
        authority = binding['effective_authority']
        need(binding['role'] == 'work' and binding['declaration_ref'] == value['work_capsule_refs']['intent'], 'NO_VERIFIER_IMPERSONATION')
        need(authority['network'] == 'none' and not authority['tools'] and not authority['write_roots'], 'NO_TOOLS_WORK_REQUIRED')
        for resource_ref in authority['resource_reads']: public_ref(resource_ref)
        for port in contract['inputs']:
            need(port['contract_id'] == 'qualified-intake:field-contract:2', 'ONLY_APPROVED_INTAKE_INPUT_SUPPORTED')
            for input_ref in port['artifact_refs']:
                public_ref(input_ref)
                intake = reader.get(input_ref); validate('qualified-intake', intake)
                public_ref(intake['request_ref'])
                for source_ref in intake['source_refs']: public_ref(source_ref)
        need(contract['subnode_limits'] == {'time_s': 120, 'model_calls': 1, 'memory_mb': 256}, 'EXACT_WORK_LIMITS_REQUIRED')
        need(contract['run_id'] in value['run_contexts'], 'MISSING_FROZEN_RUN_CONTEXT')
        run = reader.db.execute('SELECT account_id,workspace_id,state FROM runs WHERE id=?', (contract['run_id'],)).fetchone()
        need(run is not None and run[:2] == (value['principal']['account_id'], exact['workspace_id'])
             and run[2] in {'pending', 'running'}, 'ORIGINAL_WORK_RUN_IDENTITY_DIFFERS')
        context = value['run_contexts'][contract['run_id']]
        need(all(context[k] == exact[k] for k in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')),
             'WORK_CONTEXT_BINDINGS_DIFFER')
        need(context['router']['enabled'] is False and context['run_limits']['model_calls'] <= 2, 'NO_UNUSED_STAGE_ROUTING')
        attempt = reader.db.execute('SELECT state,contract_ref FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',
                                    tuple(contract[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id'))).fetchone()
        require_unissued_attempt(attempt)
        for nested in (contract['node_contract_ref'], contract['template_ref'], binding['admission_ref'], *binding['implementation_refs'], *binding['dependency_refs']): reader.read(nested)
        admission = reader.get(binding['admission_ref']); validate('library-admission', admission)
        need(admission['status'] == 'admitted' and admission['candidate_ref'] == binding['declaration_ref'], 'REAL_INTENT_ADMISSION_REQUIRED')
        contracts.append(contract['run_id'])
    need(len(set(contracts)) == 2 and set(contracts) == set(value['run_contexts']), 'EXACT_TWO_FRESH_RUNS_REQUIRED')
    need(reader.db.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0] == 0
         and reader.db.execute('SELECT COUNT(*) FROM tool_calls').fetchone()[0] == 0,
         'FRESH_DEVELOPMENT_CORE_MUST_HAVE_NO_DISPATCH_CHARGES')
    for key in ('contract_ref', 'environment_ref', 'hardware_ref'):
        reader.read(value['worker'][key])
    return {'original_refs': reader.hashes, 'work_runs': contracts}


def require_unissued_attempt(row):
    # Frozen V18 claim_attempt inserts prepared at the first actual invocation.
    # A metadata-only Factory binding has no row. Every existing row is issued.
    need(row is None,'WORK_ATTEMPT_ALREADY_ISSUED_NO_REPLAY')


def validate_native_scope(value, scope, *, allow_bootstrap=False):
    if allow_bootstrap and scope.get('schema') == 'ai4r-rsi-bootstrap-native-scope:1':
        core = PurePosixPath(value['core_root'])
        need(core.name == 'core' and PurePosixPath(value['native_lease_root']) == core.parent/'native-leases',
             'ORIGINAL_BOOTSTRAP_LEASE_PATH_REQUIRED')
        expected = {'schema': 'ai4r-rsi-bootstrap-native-scope:1',
                    'root': str(core.parent), 'account_root': value['account_root']}
    else:
        expected = {'schema': 'ai4r-rsi-native-profile-scope:1', 'isolation_root': value['isolation_root'],
                    'account_root': value['account_root']}
    need(scope == expected, 'ORIGINAL_NATIVE_SCOPE_REQUIRED')


def seed_module():
    path = Path(__file__).with_name('rsi_development_seed.py')
    spec = importlib.util.spec_from_file_location('_fixed_development_seed', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def seed_facts(value):
    """B boundary: source observations belong to the external Root launcher.

    The fresh worker receives only immutable Root receipts. No old Core,
    private fixture or credential mount is required by this consumer.
    """
    module = seed_module()
    seed = module.read_completed_seed(value['seed_receipt'])
    guard = module.read_launch_guard(value['launch_guard_receipt'], value['seed_receipt'])
    need(seed['id'] == guard['id'] == value['id'], 'ROOT_SEED_RUN_ID_DIFFERS')
    expected = {key: value[key] for key in ('isolation_root', 'core_root', 'input_root', 'account_root',
                'record_root', 'native_lease_root', 'work_root', 'parent_directory', 'native_scope_ref')}
    need(seed['destination'] == expected and seed['zero_dispatch'] is True, 'EXACT_FRESH_SEED_DESTINATION_REQUIRED')
    need(guard['seed_receipt_sha256'] == value['seed_receipt']['sha256']
         and guard['bootstrap_operations_frozen'] is True and guard['relay_idle'] is True,
         'ROOT_ORIGINAL_SCOPE_AND_LAUNCH_GUARD_REQUIRED')
    return {'seed_sha256': value['seed_receipt']['sha256'], 'guard_sha256': value['launch_guard_receipt']['sha256'],
            'source_guards_sha256': guard['source_guards_sha256'],
            'seed_helper_sha256': digest(Path(inspect.getsourcefile(module)).read_bytes())}


def empty_native_scope(value):
    """A fresh canonical scope has no completion; never manufacture one."""
    index = Path(value['native_lease_root'])/'index.sqlite'
    if not index.exists(): return {'state': 'EMPTY', 'index_sha256': None}
    protected(index, owner=12001)
    wal = Path(str(index)+'-wal')
    need(not wal.exists() or wal.stat().st_size == 0, 'CHECKPOINTED_NATIVE_LEASE_INDEX_REQUIRED')
    connection = sqlite3.connect(index.as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='native_effect_leases'").fetchone()
        need(table is None or connection.execute('SELECT COUNT(*) FROM native_effect_leases').fetchone()[0] == 0,
             'FRESH_NATIVE_SCOPE_MUST_HAVE_NO_EFFECT_HISTORY')
    finally: connection.close()
    return {'state': 'EMPTY', 'index_sha256': digest(index.read_bytes())}


async def relay_idle_fact(account_root):
    """Read-only fixed status RPC; no Core, credential cache or native call."""
    if os.name=='posix' and os.geteuid()==0:
        # The canonical session is private to12001, even from a Root planner.
        # Inspect under its real caller identity, never copy/re-own the session.
        script = '''import asyncio,json,os,sys
from jiuwenswarm.research_rsi.host_codex_backend import HostCodexSubscriptionService
import hashlib
async def main():
 assert os.getuid()==os.geteuid()==12001 and os.getgid()==os.getegid()==12001 and os.getgroups()==[13000]
 owner=HostCodexSubscriptionService(sys.argv[1])
 try:
  binding,status=await owner.relay_status()
  assert not owner.active and status['active'] is False and status['unresolved'] is False
  raw=json.dumps(status,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
  print(json.dumps({'binding_sha256':status['binding_sha256'],'policy_sha256':status['policy_sha256'],'active':False,'unresolved':False,'status_sha256':hashlib.sha256(raw).hexdigest()},sort_keys=True))
 finally:await owner.transport.close()
asyncio.run(main())
'''
        def controller_identity():os.setgroups([13000]);os.setgid(12001);os.setuid(12001)
        process=await asyncio.create_subprocess_exec(sys.executable,'-I','-B','-c',script,str(account_root),
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,preexec_fn=controller_identity,
            env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8'})
        try:stdout,stderr=await asyncio.wait_for(process.communicate(),15)
        except BaseException:
            if process.returncode is None:process.kill();await process.wait()
            raise
        need(process.returncode==0 and len(stdout)<=16384,'CONTROLLER_READONLY_RELAY_STATUS_UNAVAILABLE')
        result=closed_json(stdout)
        need(set(result)=={'binding_sha256','policy_sha256','active','unresolved','status_sha256'}
             and result['active'] is False and result['unresolved'] is False,'CLOSED_CONTROLLER_RELAY_FACT_REQUIRED')
        return result
    from jiuwenswarm.research_rsi.host_codex_backend import HostCodexSubscriptionService
    owner = HostCodexSubscriptionService(Path(account_root))
    try:
        binding, status = await owner.relay_status()
        need(not owner.active and status['active'] is False and status['unresolved'] is False, 'GLOBAL_NATIVE_RELAY_NOT_IDLE')
        return {'binding_sha256': status['binding_sha256'], 'policy_sha256': status['policy_sha256'],
                'active': False, 'unresolved': False, 'status_sha256': digest(encoded(status))}
    finally: await owner.transport.close()


def public_evaluator_inputs(value):
    reader = Originals(value)
    try:
        target = reader.get(value['target_profile_ref'])
        visible = reader.get(value['visible_context_ref'])
        return {'parent': reader.read(target['parent_ref']), 'parent_ref': target['parent_ref'],
                'tests': [{'test_ref': row['test_ref'], 'input_ref': row['input_ref'],
                           'input_raw': reader.read(row['input_ref']), 'inputs': reader.get(row['input_ref'])}
                          for row in visible['mandatory_fixtures']]}
    finally: reader.close()


def source_pins():
    """Literal imported implementation closure; no configuration-selected code."""
    from jiuwenswarm.research import isolated_resources, runner, bridge, executor, library, binding, compiler, state, invocation_start, fixed_subscription
    from jiuwenswarm.research.checks import assets
    from jiuwenswarm.research_rsi import diagnosis, proposer, assessment, mutation, worker, native_lease, process_policy, host_codex_backend, session_policy
    from jiuwenswarm.research_records import contracts as record_contracts
    modules = (isolated_resources, runner, bridge, executor, library, binding, compiler, state,
               invocation_start, fixed_subscription, assets, diagnosis, proposer,
               assessment, mutation, worker, native_lease, process_policy, host_codex_backend, session_policy, record_contracts)
    pins = {str(Path(__file__).resolve()): digest(Path(__file__).read_bytes()),
            **{module.__name__: digest(Path(inspect.getsourcefile(module)).read_bytes()) for module in modules}}
    package = Path(inspect.getsourcefile(record_contracts)).parents[1]
    schemas = sorted((package/'research_contracts').rglob('*.json'))
    need(len(schemas) <= 1024, 'FINITE_CONTRACT_SOURCE_INVENTORY_EXCEEDED')
    pins.update({str(path.relative_to(package)): digest(path.read_bytes()) for path in schemas})
    return pins


def executor_abi():
    """Actual installed V18 ABI, checked before the administrative claim."""
    from jiuwenswarm.research.executor import ExecutionJob,ReadonlyMount,RestrictedExecutor
    from jiuwenswarm.research_rsi.records import RecordStore
    module_file=Path(inspect.getsourcefile(RestrictedExecutor))
    need(digest(module_file.read_bytes())==V18_EXECUTOR_SHA256,'EXACT_V18_EXECUTOR_SOURCE_REQUIRED')
    expected=set(('job_id invocation_id contract_ref run_id node_id attempt_id sequence role repeat_index seed argv cwd timeout_s '
                  'memory_mb pids_max baseline_ref validation_ref environment_ref subject_ref hardware_ref readonly_mounts environment').split())
    need(set(inspect.signature(ExecutionJob).parameters)==expected,'V18_EXECUTION_JOB_ABI_DIFFERS')
    need(set(inspect.signature(ReadonlyMount).parameters)=={'source','target','ref'},'V18_READONLY_MOUNT_ABI_DIFFERS')
    need(set(inspect.signature(RestrictedExecutor._run_kernel).parameters)=={
        'self','job','command','output_parent','stdin_bytes','stdout_line_observer','stdout_line_limit'},'V18_KERNEL_CAPTURE_ABI_DIFFERS')
    need(set(inspect.signature(RecordStore.put_ref).parameters)=={'self','ref','raw'},'V18_CAPTURE_REF_ABI_DIFFERS')
    return {'executor_source_sha256':V18_EXECUTOR_SHA256,'admin_adapter_sha256':digest(Path(__file__).read_bytes()),
            'combined_stdout_stderr_limit_bytes':8192,'separate_probe_limit_bytes':4096}


def cgroup_capacity(path):
    """Every finite ancestor limit must accommodate the complete 24-job plan."""
    result = []
    for group in (Path(path), *Path(path).parents):
        control = group/'cgroup.max.descendants'
        if not control.exists(): break
        text = control.read_text().strip()
        counts = dict(line.split() for line in (group/'cgroup.stat').read_text().splitlines())
        visible = int(counts['nr_descendants']); dying = int(counts['nr_dying_descendants'])
        if text != 'max': need(visible+dying+24 <= int(text), 'ANCESTOR_GROUP_BUDGET_CANNOT_FIT_DEVELOPMENT_RUN')
        result.append({'path': str(group), 'max_descendants': text, 'visible': visible, 'dying': dying})
    need(bool(result), 'OBSERVED_CGROUP_CAPACITY_REQUIRED')
    return result


def persistent_evaluator_mount(path):
    """Root evidence must survive --rm; require an explicit durable RW mount."""
    path = Path(path)
    matches = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        before, after = line.split(' - ', 1)
        fields = before.split(); kind = after.split()[0]
        mount = Path(fields[4].replace('\\040', ' ').replace('\\134', '\\'))
        if path == mount or path.is_relative_to(mount):
            if mount != Path('/') and kind not in {'overlay', 'tmpfs', 'proc', 'sysfs', 'cgroup2'} and 'rw' in fields[5].split(','):
                metadata = path.stat()
                matches.append({'mountpoint': str(mount), 'filesystem': kind,
                    'device': fields[2], 'root': fields[3],
                    'bound_device': metadata.st_dev, 'bound_inode': metadata.st_ino})
    need(bool(matches), 'PERSISTENT_ROOT_EVALUATOR_RW_BIND_REQUIRED')
    return max(matches, key=lambda row: len(row['mountpoint']))


def transport_metadata():
    """Fixed host transport metadata only, with the normal controller group."""
    from jiuwenswarm.research_rsi.host_codex_backend import CATALOG, SESSION, SOCKET
    result = {}
    for path in (CATALOG, SESSION, SOCKET):
        info = path.lstat()
        need(info.st_uid == (12001 if path==SESSION else 0) and not stat.S_ISLNK(info.st_mode), 'FIXED_HOST_TRANSPORT_OWNER_REQUIRED')
        if path == SOCKET:
            need(stat.S_ISSOCK(info.st_mode) and info.st_gid == 13000
                 and stat.S_IMODE(info.st_mode) == 0o660, 'HOST_TRANSPORT_SOCKET_CUSTODY_DIFFERS')
        else:
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o022,
                 'HOST_TRANSPORT_FILE_CUSTODY_DIFFERS')
            if path==SESSION:need(stat.S_IMODE(info.st_mode)==0o400,'PRIVATE_CONTROLLER_SESSION_MODE_DIFFERS')
            need(bool(info.st_uid==12001 and info.st_mode & stat.S_IRUSR or info.st_mode & stat.S_IROTH or info.st_gid in {12001, 13000} and info.st_mode & stat.S_IRGRP),
                 'CONTROLLER_CANNOT_READ_FIXED_HOST_TRANSPORT')
        for parent in path.parents:
            meta = parent.lstat()
            need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o022,
                 'HOST_TRANSPORT_ANCESTRY_DIFFERS')
            need(bool(meta.st_mode & stat.S_IXOTH or meta.st_gid in {12001, 13000} and meta.st_mode & stat.S_IXGRP),
                 'CONTROLLER_CANNOT_TRAVERSE_HOST_TRANSPORT')
        result[str(path)] = {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode), 'inode': info.st_ino}
    return result


def plan(authorization_path):
    """Pure original-byte plan. No writable store or model service is opened."""
    path = protected(authorization_path)
    raw = path.read_bytes()
    value = validate_authorization(closed_json(raw))
    root = protected(value['isolation_root'], owner=12001, directory=True)
    evidence_root = protected(value['evaluator_root'], directory=True)
    need(stat.S_IMODE(evidence_root.stat().st_mode) == 0o711,
         'ROOT_EVALUATOR_MUST_PERMIT_ONLY_UNPRIVILEGED_TRAVERSAL')
    need(all(parent.stat().st_mode & stat.S_IXOTH for parent in evidence_root.parents),
         'EXECUTOR_CANNOT_TRAVERSE_EVALUATOR_MOUNT')
    need(not any(evidence_root.iterdir()), 'FRESH_ROOT_EVALUATOR_EVIDENCE_REQUIRED')
    evidence_mount = persistent_evaluator_mount(evidence_root)
    paths = {}
    for key in ('core_root', 'input_root', 'account_root', 'record_root', 'work_root', 'parent_directory', 'native_lease_root'):
        current = protected(value[key], owner=12001, directory=True)
        need(current.is_relative_to(root), 'PATH_ESCAPES_DEVELOPMENT_NAMESPACE')
        need(all(not (current == Path(p) or current.is_relative_to(Path(p)) or Path(p).is_relative_to(current))
                 for p in value['forbidden_roots']), 'LIVE_NAMESPACE_OVERLAP')
        paths[key] = {'path': str(current), 'inode': current.stat().st_ino}
    need(len({paths[k]['path'] for k in paths}) == len(paths), 'DEVELOPMENT_ROOTS_MUST_BE_DISTINCT')
    need(not any(Path(value['work_root']).iterdir()), 'FRESH_EMPTY_DEVELOPMENT_WORK_ROOT_REQUIRED')
    historical = seed_facts(value)
    core = Path(value['core_root'])
    database = core/'state/research.sqlite3'
    database_facts = {}
    for file in (database, Path(str(database)+'-wal')):
        if file.exists():
            # The stopped owner must keep these byte-exact through Root claim.
            protected(file, owner=12001, maximum=256*1024*1024)
            database_facts[str(file)] = digest(file.read_bytes())
    need(str(database) in database_facts, 'EXISTING_CORE_REQUIRED')
    reader = Originals(value)
    try: original_facts = original_preflight(value, reader)
    finally: reader.close()
    lease_facts = empty_native_scope(value)
    cgroup = protected(value['cgroup_root'], directory=True)
    groups = [cgroup, *sorted(p for p in cgroup.rglob('*') if p.is_dir())]
    need(len(groups) <= 4096-24, 'FINITE_CGROUP_CAPACITY_UNAVAILABLE')
    group_facts = []
    for group in groups:
        events = dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
        need(events.get('populated') == '0' and not (group/'cgroup.procs').read_text().strip(), 'OWNED_JOB_NOT_EMPTY')
        group_facts.append({'path': str(group), 'inode': group.stat().st_ino})
    need(not path.with_name('development-claim.json').exists(), 'DEVELOPMENT_ALREADY_CLAIMED_NO_REPLAY')
    result = {'schema': 'ai4r-rsi-development-plan:1', 'authorization_sha256': digest(raw),
              'paths': paths, 'core_originals': database_facts, 'source_pins': source_pins(), 'originals': original_facts,
              'native_lease': lease_facts, 'empty_owned_groups': group_facts, 'cgroup_capacity': cgroup_capacity(cgroup),
              'historical_seed': historical, 'global_relay': asyncio.run(relay_idle_fact(value['account_root'])),
              'root_evaluator': {'path': str(evidence_root), 'inode': evidence_root.stat().st_ino, 'mount': evidence_mount},
              'fixed_host_transport': transport_metadata(), 'controller_supplementary_groups': [13000],
              'bounded_executor':executor_abi(),
              'maximum_model_calls': 2, 'maximum_candidates': 1, 'visible_cases': 12,
              'security': 'UNQUALIFIED', 'security_campaigns': 'DEFERRED',
              'hidden_evaluation': 'NOT_AUTHORIZED', 'package_admission_activation': 'NOT_AUTHORIZED'}
    return value, result


def exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    finally:
        os.close(fd)
    if os.name == 'posix':
        directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)


def development_job_id(run_id, side, index):
    need(side in {'parent', 'candidate'} and type(index) is int and 0 <= index < 12, 'FINITE_JOB_ID_INPUT_REQUIRED')
    return 'development-' + digest(encoded([run_id, side, index]))[:40]


class DevelopmentModel:
    """Lease/evidence wrapper around the SAME normal governed work entrypoint."""
    def __init__(self, resources, lease, contract_ref, run_id):
        self.resources, self.lease, self.contract_ref, self.run_id = resources, lease, contract_ref, run_id
        self.used = False
        self.last_evidence = []; self.last_model_calls = None; self.last_generating_model = None
        self.last_unavailable_reasons = []

    async def __call__(self, prompt):
        need(not self.used, 'DEVELOPMENT_WORK_CONTEXT_ALREADY_USED')
        self.used = True
        store = self.resources.store
        before = {encoded(e['ref']) for e in store.iter_records(kinds={'model-call-start', 'model-call', 'route-record', 'invocation-observation'})}
        lease_ref = self.lease.start(self.run_id, self.contract_ref)
        succeeded = False
        refusal_ref = None
        try:
            response = await self.resources.propose_once(self.contract_ref, prompt)
            succeeded = True
            return response
        except BaseException as error:
            code = str(getattr(error, 'code', type(error).__name__))[:128]
            refusal_ref = store.append_record('rsi-governed-work-refusal', {
                'schema': 'ai4r-rsi-governed-work-refusal:1', 'contract_ref': self.contract_ref,
                'run_id': self.run_id, 'exception_type': type(error).__name__, 'reason_code': code})
            self.last_unavailable_reasons.append('Governed work refused: ' + code)
            raise
        finally:
            entries = [e for e in store.iter_records(kinds={'model-call-start', 'model-call', 'route-record', 'invocation-observation'})
                       if encoded(e['ref']) not in before]
            starts = [e for e in entries if e['kind'] == 'model-call-start']
            need(all(e['record']['contract_ref'] == self.contract_ref for e in starts), 'FOREIGN_MODEL_EFFECT')
            self.last_evidence = [e['ref'] for e in entries]
            if refusal_ref is not None: self.last_evidence.append(refusal_ref)
            self.last_model_calls = len(starts)
            calls = [e['record'] for e in entries if e['kind'] == 'model-call' and e['record'].get('outcome') == 'completed']
            if len(calls) == 1:
                self.last_generating_model = calls[0].get('identity', {}).get('effective')
                usage = calls[0].get('usage')
                if not isinstance(usage, dict) or any(usage.get(key) is None for key in ('input_tokens', 'output_tokens', 'cost')):
                    self.last_unavailable_reasons.append('Model usage is unavailable or partial; inspect governed call evidence.')
            need(not succeeded or len(starts) == len(calls) == 1, 'NO_UNCLAIMED_MODEL_RESPONSE')
            from jiuwenswarm.research_rsi.native_lease import native_completion_proof
            known, proof = native_completion_proof(store, starts)
            if known:
                self.lease.complete(lease_ref, proof)
            else:
                self.lease.uncertain(lease_ref, proof)
                raise ValueError('NATIVE_CONTAINMENT_UNCERTAIN_NO_FURTHER_EFFECT')


def validate_calibration_binding(core, exact, operator):
    """Resolve the current protected runtime through its calibration owner.

    This validates captured startup/policy identity without measuring cases,
    publishing eligibility or making a model call. Published checking guards
    remain independently enforced by LibraryService/CheckAssetAdmissions.
    """
    from jiuwenswarm.research.calibration_authority import CalibrationAuthority
    return CalibrationAuthority(core, exact['protected_options']['calibration_runtime_ref'],
        **{key: exact[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
        policy_ref=operator.snapshot()['cc']['plan_policy_ref'], model=None)



async def compose(value, evaluate):
    """Canonical classes, explicitly limited to Intent and its shared Verifier.

    compose_core also constructs Compiler/Planning/Scheduler and therefore
    demands the entire catalog. FiniteE1 only supports Screening/Hypothesis.
    Here only those graph-building conveniences are omitted; Library, checking
    admission, runner authorization, bridge claims and native lease are reused.
    """
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.runner import Registry, CapsuleRunner
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.run_evidence import RunEvidence
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.isolated_resources import IsolatedResources
    from jiuwenswarm.research_rsi.fixed_resources import CombinedRecords, require_native_profile_ready
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.native_lease import NativeEffectLease
    from jiuwenswarm.research_rsi.spark_backend import subscription_for_deployment
    core = SQLiteRunStore(value['core_root'], recover=False, input_root=value['input_root'])
    records = RecordStore(value['record_root'])
    lease_records = RecordStore(value['native_lease_root'])
    store = CombinedRecords(records, core)
    lease = NativeEffectLease(lease_records, value['native_scope_ref'])
    lease.assert_available()
    exact = value['exact_binding_refs']
    configuration = core.read_record(exact['configuration_ref'])
    operator = OperatorConfiguration.from_mapping(configuration.get('operator', configuration), resolve_profile=core.read_record)
    need(operator.snapshot()['cc']['router']['enabled'] is False, 'DEVELOPMENT_ROUTING_FORBIDDEN')
    actor = value['principal']
    principal = Principal(actor['account_id'], frozenset(actor['workspace_ids']), frozenset(actor['operations']), frozenset(actor['audiences']))
    principal.require('status', exact['workspace_id'])
    # This object cannot execute jobs; actual public evaluation is Root-owned.
    class NoWorkExecutor:
        workspace_root = Path(value['work_root'])
        async def run(self, *args, **kwargs): raise ValueError('ONLY_FINITE_PUBLIC_EVALUATOR_MAY_EXECUTE')
    executor = NoWorkExecutor()
    library = LibraryService(core, executor=executor)
    validate_calibration_binding(core, exact, operator)

    for stage, declaration_ref in value['work_capsule_refs'].items():
        declaration = core.read_record(declaration_ref, contract_id='capsule-declaration')
        identity = declaration['identity']
        entry = library.get(identity['name'], identity['version_label'])
        need(entry['declaration_ref'] == declaration_ref and entry['standing'] == 'active'
             and entry['effect_scope'] == 'live_plans', 'EXACT_ACTIVE_ADMITTED_CAPSULE_REQUIRED')
        admission = core.read_record(entry['admission_ref'], contract_id='library-admission')
        need(admission['status'] == 'admitted' and admission['candidate_ref'] == declaration_ref, 'CAPSULE_ADMISSION_DIFFERS')
        association = library.association(declaration_ref)
        library.check_assets.require(association['bundle_ref'], association['profile_ref'])
        if stage == 'verifier': library.configure_verifier(admission['cc'])
    subscription = subscription_for_deployment(Path(value['account_root']), core.read_record(exact['deployment_ref']))
    subscription.set_account_observer(core.append_record)
    subscription.set_governed_trace_writer(core.append_record, core.put_blob)
    async def unavailable(_): raise ValueError('NO_UNCOMPOSED_MODEL_AUTHORITY')
    from jiuwenswarm.research.contracts import validate
    bridge = GovernedBridge(persist=core.append_record, authorize=unavailable,
        subscription_service=subscription, fixed_route_id=operator.codex_route_id,
        validate_record=validate, read_evidence=core.read_blob)
    registry, checks = Registry(), CheckRegistry()
    runner = CapsuleRunner(core, registry, checks, model=bridge, executor=executor,
                           check_assets=library.check_assets, evidence=RunEvidence(core, library))
    bridge.authorize = runner.authorize_model_context
    bridge.revalidate = runner.authorize_model_dispatch
    for run_id, context in value['run_contexts'].items(): runner.configure_run(run_id, **context)
    for key in ('diagnosis_contract_ref', 'proposal_contract_ref'):
        contract = core.read_record(value[key], contract_id='subnode-execution-contract')
        runner._require_child_authority(value[key], contract)
        runner._require_check_assets(contract)
        row=core.connection.execute('SELECT state,contract_ref FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',
            tuple(contract[k] for k in ('run_id','node_id','subnode_id','attempt_id'))).fetchone()
        require_unissued_attempt(row)
    await require_native_profile_ready(subscription, lease)
    async def before_model():
        await require_native_profile_ready(subscription, lease)
    resources = IsolatedResources(core, operator, SimpleNamespace(runner=runner, registry=registry, checks=checks),
                                  bridge, executor, principal, exact)
    return SimpleNamespace(store=store, resources=resources, lease=lease, evaluate=evaluate,
                           subscription=subscription, before_model=before_model,
                           core=core, records=records, lease_records=lease_records)


def prepare_work_contexts(*, core, library, runner, operator, exact, intake_ref, action_id, work_capsule_refs, account_id):
    """Metadata-only normal ContractFactory entrypoint; caller owns Root claim.

    The already-admitted Intent Capsule is the same genuine work binding used
    by rsi_controller_setup. No verifier role is repurposed as a model worker.
    """
    from jiuwenswarm.research.binding import ContractFactory
    from jiuwenswarm.research.compiler import input_port
    entries = {}
    for stage in ('intent', 'verifier'):
        declaration = core.read_record(work_capsule_refs[stage], contract_id='capsule-declaration')
        entry = library.get(declaration['identity']['name'], declaration['identity']['version_label'])
        need(entry['standing'] == 'active' and entry['declaration_ref'] == work_capsule_refs[stage], 'EXACT_INSTALLED_CAPSULE_REQUIRED')
        admission = core.read_record(entry['admission_ref'], contract_id='library-admission')
        need(admission['status'] == 'admitted', 'REAL_ADMISSION_REQUIRED')
        entries[stage] = dict(entry, pin=admission['cc'])
    intent, verifier = entries['intent'], entries['verifier']
    factory = ContractFactory(core, library, verifier_pin=verifier['pin'],
                              finalization_profile_ref=exact['protected_options']['finalization_profile_ref'])
    declaration = core.read_record(intent['declaration_ref'], contract_id='capsule-declaration')
    intake = core.read_record(intake_ref, contract_id='qualified-intake')
    ports = [input_port('request', 'qualified-intake:field-contract:2', intake_ref)]
    outputs = [{'name': row['name'], 'contract_id': row['schema_ref'],
                'version': ContractFactory._version(row['schema_ref']), 'required': row['required']}
               for row in declaration['ports']['outputs']]
    contracts, contexts = {}, {}
    for role in ('diagnosis', 'proposal'):
        run_id = 'rsi-development:' + action_id + ':' + role
        core.create_run(run_id, account_id=account_id, workspace_id=exact['workspace_id'], submission={'intake_ref': intake_ref})
        parent_ref = factory.prepare_parent(run_id, role,
            [{'subnode_id': role, 'cc': intent['pin'], 'depends_on': []}], inputs=ports, outputs=outputs,
            objective='Unqualified development ' + role, requirement_ids=['rsi_'+role],
            limits={'time_s': 240, 'model_calls': 2, 'memory_mb': 256},
            policy_ref=operator.snapshot()['cc']['plan_policy_ref'], configuration_ref=exact['configuration_ref'],
            template_ref=exact['protected_options']['compiler_template_ref'], authority_ceiling={
                'network': 'none', 'network_allowlist': [], 'tools': [], 'write_roots': [],
                'resource_reads': [intake_ref, intake['request_ref'], *intake['source_refs']]})
        contract, _, _ = factory.bind_subnode(parent_ref, role, ports, role='work')
        contexts[run_id] = {**{k: exact[k] for k in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
                            'router': operator.snapshot()['cc']['router'],
                            'run_limits': {'time_s': 240, 'model_calls': 2, 'memory_mb': 256}}
        runner.configure_run(run_id, **contexts[run_id])
        contracts[role+'_contract_ref'] = contract
    return dict(contracts, run_contexts=contexts)


def write_frame(stream, value):
    raw = encoded(value)
    need(len(raw) <= MAX_BYTES, 'PIPE_FRAME_TOO_LARGE')
    stream.write(raw+b'\n'); stream.flush()


def read_frame(stream):
    raw = stream.readline(MAX_BYTES+2)
    if not raw: return None
    need(raw.endswith(b'\n') and len(raw) <= MAX_BYTES+1, 'PIPE_FRAME_TOO_LARGE')
    return closed_json(raw)


def read_frame_deadline(stream, deadline):
    """No indefinitely blocked read thread can outlive the Root deadline."""
    raw = bytearray()
    while True:
        remaining = deadline-time.monotonic()
        need(remaining > 0, 'FINITE_PIPE_DEADLINE_EXPIRED')
        ready, _, _ = select.select([stream.fileno()], [], [], remaining)
        need(bool(ready), 'FINITE_PIPE_DEADLINE_EXPIRED')
        part = os.read(stream.fileno(), min(65536, MAX_BYTES+2-len(raw)))
        if not part:
            need(not raw, 'TRUNCATED_PIPE_FRAME')
            return None
        raw.extend(part)
        need(len(raw) <= MAX_BYTES+1, 'PIPE_FRAME_TOO_LARGE')
        if b'\n' in part:
            need(raw.endswith(b'\n') and raw.count(b'\n') == 1, 'MULTIPLE_PIPE_FRAMES_NOT_AUTHORIZED')
            return closed_json(raw)


class BoundedCapture:
    """Bound both pipes before the canonical V18 kernel writes capture files."""
    LIMIT = 8192
    PREFIX = b'AI4R_EXECUTOR_PROBE_V1 '

    def __init__(self, kill):
        self.kill, self.used, self.overflow = kill, 0, False

    async def take(self, reader, chunk):
        remaining = self.LIMIT-self.used
        kept = chunk[:remaining]
        self.used += len(kept)
        if len(chunk)>remaining:
            if not self.overflow:
                self.overflow=True
                self.kill()
            # The exact owned group has been killed. Drain discarded bytes so
            # asyncio's finite transport buffers cannot keep wait() blocked.
            while await reader.read(65536): pass
        return kept

    def pipe(self, reader, *, probe=False):
        fence=self
        class Pipe:
            async def readline(self):
                frame=await reader.readline()
                if probe and frame.startswith(fence.PREFIX) and len(frame)<=4096+len(fence.PREFIX)+1:
                    return frame
                return await fence.take(reader,frame)
            async def read(self, size=65536):
                need(type(size) is int and 0<size<=65536,'FINITE_KERNEL_PIPE_READ_REQUIRED')
                return await fence.take(reader,await reader.read(size))
        return Pipe()


def bounded_executor(base):
    """Reuse the original compiled kernel and every lifecycle/security check.

    A private globals dictionary replaces only its asyncio subprocess factory.
    Neither the installed module, shared asyncio, nor its source is modified.
    This supplies the V18 missing output bound without inventing a job field.
    """
    import types
    class Executor(base):
        async def _run_kernel(self,job,command,**kwargs):
            canonical=base._run_kernel
            original_asyncio=canonical.__globals__['asyncio']
            def kill():
                active=self.active.get(job.job_id)
                need(active is not None,'OWNED_OUTPUT_LIMIT_GROUP_UNAVAILABLE')
                (active[1]/'cgroup.kill').write_text('1')
            fence=BoundedCapture(kill)
            class Process:
                def __init__(self,process):
                    self.process=process
                    self.stdout=fence.pipe(process.stdout,probe=True)
                    self.stderr=fence.pipe(process.stderr)
                def __getattr__(self,name):return getattr(self.process,name)
            class Asyncio:
                def __getattr__(self,name):return getattr(original_asyncio,name)
                async def create_subprocess_exec(self,*args,**kw):
                    return Process(await original_asyncio.create_subprocess_exec(*args,**kw))
            scoped=types.FunctionType(canonical.__code__,dict(canonical.__globals__,asyncio=Asyncio()),
                                      canonical.__name__,canonical.__defaults__,canonical.__closure__)
            scoped.__kwdefaults__=canonical.__kwdefaults__
            receipt=await scoped(self,job,command,**kwargs)
            receipt['observed_limits']={**receipt.get('observed_limits',{}),
                'admin_output_limit_bytes':fence.LIMIT,'admin_output_captured_bytes':fence.used,
                'admin_output_truncated':fence.overflow,
                'admin_kernel_source_sha256':digest(Path(inspect.getsourcefile(base)).read_bytes()),
                'admin_output_adapter_sha256':digest(Path(__file__).read_bytes())}
            if fence.overflow and receipt['termination_reason']=='completed':
                receipt['termination_reason']='output_limit_exceeded'
            return receipt
    return Executor


async def evaluator(value, public, request_stream, response_stream, root):
    """Root broker: exactly parent then candidate; no external fixture selectors."""
    from jiuwenswarm.research.executor import RestrictedExecutor, ExecutionJob, ReadonlyMount
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.worker import worker_program
    from jiuwenswarm.research_rsi.process_policy import POLICY
    from jiuwenswarm.research_rsi.targets import registered_helper
    captures = RecordStore(root/'captures')
    for name in ('assets', 'work'):
        (root/name).mkdir(mode=0o711)
        (root/name).chmod(0o711)
    helper = registered_helper(value['target_kind'])
    issued = {}
    def authorize(job):
        need(issued.get(job.job_id) == job, 'UNISSUED_DEVELOPMENT_JOB'); return job
    def verify(mount): need(digest(mount.source.read_bytes()) == mount.ref['sha256'], 'PUBLIC_EXECUTION_ASSET_CHANGED')
    executor = bounded_executor(RestrictedExecutor)(workspace_root=root/'work', cgroup_root=value['cgroup_root'],
        authorize_job=authorize, capture=lambda data, **_: captures.put_bytes(data),
        executor_uid=12003, executor_gid=12003, allowed_asset_roots=[root/'assets'], verify_mount=verify)
    need(not executor.prerequisites(), 'ACTUAL_EXECUTOR_CONFINEMENT_UNAVAILABLE')
    program = worker_program(value['target_kind'], POLICY)
    write_frame(response_stream, {'ready': True, 'maximum_executions': 24, 'program_sha256': digest(program)})
    deadline = time.monotonic()+value['limits']['wall_s']
    for sequence, role in enumerate(('parent', 'candidate')):
        request = await asyncio.to_thread(read_frame_deadline, request_stream, deadline)
        if request is None:
            captures.close(); return
        need(set(request) == {'role', 'candidate_ref', 'body_base64'} and request['role'] == role, 'FINITE_EVALUATION_ORDER_DIFFERS')
        body = base64.b64decode(request['body_base64'], validate=True)
        need(0 < len(body) <= MAX_BYTES//2, 'INVALID_CANDIDATE_BODY_BOUND')
        pin(request['candidate_ref'])
        need(digest(body) == request['candidate_ref']['sha256'], 'EXACT_CANDIDATE_BYTES_REQUIRED')
        if role == 'parent': need(body == public['parent'] and request['candidate_ref'] == public['parent_ref'], 'PARENT_CONTROL_BYTES_DIFFER')
        else: need(body != public['parent'], 'UNCHANGED_CANDIDATE')
        child_ref = captures.put_ref(request['candidate_ref'], body)
        receipts = []; elapsed = 0; passed = True; passed_count = 0
        for index, row in enumerate(public['tests']):
            need(time.monotonic() < deadline, 'DEVELOPMENT_DEADLINE_EXPIRED')
            ident = development_job_id(value['id'], role, index)
            assets = root/'assets'/ident; assets.mkdir(mode=0o755)
            assets.chmod(0o755)
            work = root/'work'/ident; work.mkdir(mode=0o700); os.chown(work, 12003, 12003)
            mounts = []
            input_ref = captures.put_ref(row['input_ref'], row['input_raw'])
            program_ref = captures.put_bytes(program)
            for name, raw in (('worker.py', program), ('body.py', body), ('input.json', row['input_raw'])):
                path = assets/name; path.write_bytes(raw); path.chmod(0o444)
                mounts.append(ReadonlyMount(path, '/resources/'+name, {'id': name, 'sha256': digest(raw)}))
            worker = value['worker']
            job = ExecutionJob(job_id=ident, invocation_id=ident, contract_ref=worker['contract_ref'],
                run_id=value['id'], node_id='unqualified-development', attempt_id=role, sequence=1, role='treatment',
                repeat_index=index, seed=0, argv=('/usr/local/bin/python3', '-I', '/resources/worker.py'),
                cwd=work, timeout_s=worker['timeout_s'], memory_mb=worker['memory_mb'], pids_max=worker['pids_max'],
                baseline_ref=public['parent_ref'], validation_ref=row['test_ref'], environment_ref=worker['environment_ref'],
                subject_ref=child_ref, hardware_ref=worker['hardware_ref'], readonly_mounts=tuple(mounts))
            # Persistent Root receipt BEFORE the kernel effect, including failures.
            start_ref = captures.put({'schema': 'ai4r-rsi-development-execution-start:1',
                'id': ident, 'run_id': value['id'], 'case_index': index,
                'candidate_ref': child_ref, 'test_ref': row['test_ref'], 'role': role,
                'input_ref': input_ref, 'program_ref': program_ref,
                'recorded_unix_ns': time.time_ns()})
            issued[ident] = job
            receipt = await executor.run(job)
            group = Path(value['cgroup_root'])/ident
            events = dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
            need(events.get('populated') == '0' and not (group/'cgroup.procs').read_text().strip(), 'EXECUTION_GROUP_NOT_EMPTY')
            ok = receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0 and receipt['observed_runtime'] is True
            if ok:
                stdout = captures.read(receipt['stdout_ref'])  # integrity errors remain fatal
                try: actual = closed_json(stdout)
                except (ValueError, UnicodeError): ok = False
                else: ok = actual == helper.reference(row['inputs'])
            elapsed += receipt['wall_time_s']; passed = passed and ok; passed_count += int(ok)
            proof = {'schema': 'ai4r-rsi-development-visible-check:1', 'start_ref': start_ref,
                     'test_ref': row['test_ref'], 'candidate_ref': child_ref, 'receipt': receipt,
                     'input_ref': input_ref, 'program_ref': program_ref,
                     'passed': ok, 'group_empty': True}
            proof_ref = captures.put(proof)
            raw_refs = [receipt['stdout_ref'], receipt['stderr_ref'], receipt['observed_limits']['isolation_probe_ref'], input_ref, program_ref]
            receipts.append({'ref': proof_ref, 'bytes_base64': base64.b64encode(captures.read(proof_ref)).decode('ascii'),
                             'captures': [{'ref': p, 'bytes_base64': base64.b64encode(captures.read(p)).decode('ascii')} for p in raw_refs]})
        write_frame(response_stream, {'passed': passed, 'passed_count': passed_count, 'evidence': receipts,
            'visible_selection_time_s': elapsed, 'executions': len(receipts)})
    captures.close()


async def run_controller(value, request_stream, response_stream):
    runtime = None
    async def evaluate(candidate_ref, tests, role):
        need(len(tests) == 12, 'EXACT_PUBLIC_EVALUATION_REQUIRED')
        from jiuwenswarm.research_rsi.worker import worker_program
        from jiuwenswarm.research_rsi.process_policy import POLICY
        expected_program = digest(worker_program(value['target_kind'], POLICY))
        expected_inputs = {encoded(row['test_ref']): row['input_ref'] for row in tests}
        raw = runtime.store.read(candidate_ref)
        write_frame(request_stream, {'role': role, 'candidate_ref': candidate_ref, 'body_base64': base64.b64encode(raw).decode('ascii')})
        response = await asyncio.to_thread(read_frame_deadline, response_stream, time.monotonic()+180)
        need(isinstance(response, dict) and set(response) == {'passed', 'passed_count', 'evidence', 'visible_selection_time_s', 'executions'}
             and response['executions'] == 12 and type(response['passed']) is bool
             and type(response['passed_count']) is int, 'ROOT_EVALUATOR_RESPONSE_DIFFERS')
        refs = []; test_refs = []; actual_passed = 0; actual_time = 0
        for capture in response['evidence']:
            need(set(capture) == {'ref', 'bytes_base64', 'captures'}, 'UNKNOWN_EVALUATION_CAPTURE')
            raw = base64.b64decode(capture['bytes_base64'], validate=True)
            need(runtime.store.put_bytes(raw) == capture['ref'], 'EVALUATION_CAPTURE_HASH_DIFFERS')
            record = closed_json(raw)
            need(record['schema'] == 'ai4r-rsi-development-visible-check:1'
                 and record['candidate_ref'] == candidate_ref and record['group_empty'] is True,
                 'ROOT_EVALUATION_SCOPE_DIFFERS')
            need(record['input_ref'] == expected_inputs.get(encoded(record['test_ref']))
                 and record['program_ref']['sha256'] == expected_program, 'ROOT_PUBLIC_CASE_OR_PROGRAM_DIFFERS')
            receipt = record['receipt']
            need(receipt['subject_ref'] == candidate_ref and type(record['passed']) is bool,
                 'RECEIPT_CANDIDATE_DIFFERS')
            test_refs.append(record['test_ref'])
            actual_passed += int(record['passed']); actual_time += receipt['wall_time_s']
            expected_raw = [receipt['stdout_ref'], receipt['stderr_ref'], receipt['observed_limits']['isolation_probe_ref'], record['input_ref'], record['program_ref']]
            need([c['ref'] for c in capture['captures']] == expected_raw, 'EXACT_RECEIPT_BYTE_CLOSURE_REQUIRED')
            for original in capture['captures']:
                need(set(original) == {'ref', 'bytes_base64'}, 'UNKNOWN_RAW_CAPTURE')
                raw = base64.b64decode(original['bytes_base64'], validate=True)
                need(digest(raw) == original['ref']['sha256'], 'RECEIPT_ORIGINAL_BYTES_DIFFER')
                runtime.store.records.put_ref(original['ref'], raw)
            refs.append(capture['ref'])
        need(len(refs) == 12 and len({encoded(p) for p in refs}) == 12, 'TWELVE_DISTINCT_ACTUAL_RECEIPTS_REQUIRED')
        need({encoded(p) for p in test_refs} == {encoded(row['test_ref']) for row in tests}, 'EVALUATOR_TEST_SET_DIFFERS')
        need(actual_passed == response['passed_count'] and response['passed'] == (actual_passed == 12)
             and actual_time == response['visible_selection_time_s'], 'ACTUAL_VISIBLE_METRICS_DIFFER')
        return {'passed': response['passed'], 'evidence_refs': refs,
                'passed_count': actual_passed, 'visible_selection_time_s': actual_time, 'executions': len(refs)}
    try:
        runtime = await compose(value, evaluate)
        return await asyncio.wait_for(execute(value, runtime), value['limits']['wall_s'])
    finally:
        if runtime is not None:
            close = getattr(runtime.subscription.transport, 'close', None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result): await result
            runtime.records.close(); runtime.lease_records.close(); runtime.core.close()


def launch(value, facts, authorization_path):
    """Root claim then fork BEFORE writable Core/account/model composition."""
    public = public_evaluator_inputs(value)  # all read-only DB handles close here
    current, repeated = plan(authorization_path)
    need(current == value and repeated == facts, 'REVIEW_PLAN_CHANGED_BEFORE_CLAIM')
    claim_path = Path(authorization_path).with_name('development-claim.json')
    exclusive(claim_path, {'schema': 'ai4r-rsi-development-claim:1', 'plan_sha256': digest(encoded(facts)),
                           'authorization_sha256': facts['authorization_sha256'], 'id': value['id']})
    worker_root = protected(value['evaluator_root'], directory=True)
    controller_state = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    controller_argv = Path('/proc/self/cmdline').read_bytes()
    exclusive(worker_root/'controller-owner.json', {
        'schema': 'ai4r-rsi-development-controller-owner:1', 'id': value['id'],
        'pid': os.getpid(), 'start_ticks': int(controller_state[19]),
        'argv_sha256': digest(controller_argv),
        'argv': controller_argv.decode('utf8').rstrip('\0').split('\0'),
        'pid_namespace': os.readlink('/proc/self/ns/pid'),
        'mount_namespace': os.readlink('/proc/self/ns/mnt'),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'deadline_unix_ns': time.time_ns()+int((value['limits']['wall_s']+30)*1e9),
        'initial_uid': os.geteuid(), 'initial_gid': os.getegid(),
        'controller_uid': 12001, 'controller_gid': 12001, 'controller_groups': [13000],
        'plan_sha256': digest(encoded(facts)), 'bounded_executor':facts['bounded_executor']})
    request_read, request_write = os.pipe()
    response_read, response_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        # Nothing related to account/model services has been instantiated.
        try:
            keep = {0, 1, 2, request_read, response_write}
            for name in os.listdir('/proc/self/fd'):
                fd = int(name)
                if fd not in keep:
                    try: os.close(fd)
                    except OSError: pass
            import signal
            def expired(signum, frame): raise TimeoutError('FINITE_EVALUATOR_LIFETIME_EXPIRED')
            signal.signal(signal.SIGALRM, expired)
            signal.alarm(value['limits']['wall_s']+30)
            os.setgroups([])
            state = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
            argv = Path('/proc/self/cmdline').read_bytes()
            exclusive(worker_root/'owner.json', {'schema': 'ai4r-rsi-development-evaluator-owner:1',
                'id': value['id'], 'pid': os.getpid(), 'start_ticks': int(state[19]),
                'argv_sha256': digest(argv), 'argv': argv.decode('utf8').rstrip('\0').split('\0'),
                'pid_namespace': os.readlink('/proc/self/ns/pid'), 'mount_namespace': os.readlink('/proc/self/ns/mnt'),
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'deadline_unix_ns': time.time_ns()+int((value['limits']['wall_s']+30)*1e9),
                'uid': os.geteuid(), 'gid': os.getegid(), 'groups': os.getgroups(),
                'plan_sha256': digest(encoded(facts)), 'bounded_executor':facts['bounded_executor']})
            with os.fdopen(request_read, 'rb') as incoming, os.fdopen(response_write, 'wb') as outgoing:
                asyncio.run(evaluator(value, public, incoming, outgoing, worker_root))
            exclusive(worker_root/'complete.json', {'schema': 'ai4r-rsi-development-evaluator-completion:1',
                'id': value['id'], 'plan_sha256': digest(encoded(facts)), 'status': 'STOPPED',
                'owner_sha256': digest((worker_root/'owner.json').read_bytes())})
            os._exit(0)
        except BaseException as error:
            try:
                import traceback
                exclusive(worker_root/'failure.json', {'schema': 'ai4r-rsi-development-evaluator-failure:1',
                    'id': value['id'], 'exception_type': type(error).__name__,
                    'private_diagnostic': str(error)[:4096], 'private_traceback': traceback.format_exc()[-65536:],
                    'plan_sha256': digest(encoded(facts)), 'status': 'ERROR_NO_REPLAY'})
            except BaseException: pass
            os._exit(2)
    os.close(request_read); os.close(response_write)
    incoming = os.fdopen(response_read, 'rb'); outgoing = os.fdopen(request_write, 'wb')
    # Parent permanently drops Root before touching account/bridge/Core owners.
    os.setgroups([13000]); os.setgid(12001); os.setuid(12001)
    need(os.getuid() == os.geteuid() == 12001 and os.getgid() == os.getegid() == 12001, 'CONTROLLER_IDENTITY_DROP_FAILED')
    need(os.getgroups() == [13000], 'CONTROLLER_TRANSPORT_GROUP_DIFFERS')
    result = None
    try:
        ready = read_frame_deadline(incoming, time.monotonic()+15)
        from jiuwenswarm.research_rsi.worker import worker_program
        from jiuwenswarm.research_rsi.process_policy import POLICY
        need(isinstance(ready, dict) and set(ready) == {'ready', 'maximum_executions', 'program_sha256'}
             and ready['ready'] is True and ready['maximum_executions'] == 24
             and ready['program_sha256'] == digest(worker_program(value['target_kind'], POLICY)),
             'ROOT_EVALUATOR_NOT_READY')
        result = asyncio.run(run_controller(value, outgoing, incoming))
    except BaseException as error:
        import traceback
        diagnostic = {'schema': 'ai4r-rsi-development-controller-failure:1', 'id': value['id'],
                      'exception_type': type(error).__name__, 'private_diagnostic': str(error)[:4096],
                      'private_traceback': traceback.format_exc()[-65536:]}
        exclusive(Path(value['record_root'])/'controller-failure.json', diagnostic)
        result = {'schema': RESULT_SCHEMA, 'id': value['id'], 'security': 'UNQUALIFIED',
                  'security_campaigns': 'DEFERRED', 'status': 'ERROR_NO_REPLAY',
                  'hidden_evaluation': 'NOT_RUN', 'final_evaluation': 'NOT_RUN',
                  'exception_type': type(error).__name__, 'diagnostic_sha256': digest(encoded(diagnostic)), 'model_calls': None,
                  'qualification_ref': None, 'package_ref': None, 'admission_ref': None, 'activation_ref': None,
                  'limitations': ['Inspect retained governed starts, native lease and evaluation starts before any new effect.']}
    finally:
        outgoing.close(); incoming.close()
        _, status = os.waitpid(pid, 0)
    result['evaluator_exit_code'] = os.waitstatus_to_exitcode(status)
    if result['evaluator_exit_code'] != 0: result['status'] = 'ERROR_NO_REPLAY'
    validate_result(result)
    output = Path(value['record_root'])/'development-result.json'
    exclusive(output, result)
    # Safe references/status only; bodies and model/raw native evidence stay private.
    print(json.dumps({'id': value['id'], 'result_sha256': digest(encoded(result)),
                      'security': result['security'], 'status': result.get('status', 'EVALUATED_UNQUALIFIED')}, sort_keys=True))
    return result


async def execute(value, runtime):
    """Finite orchestration; injected runtime is the fixed compose() below."""
    from jiuwenswarm.research_rsi.diagnosis import BoundedDiagnosis
    from jiuwenswarm.research_rsi.proposer import GuardedProposer, proposal_context
    from jiuwenswarm.research_rsi.assessment import GuardedAssessment
    from jiuwenswarm.research_rsi.profiles import Limits
    from jiuwenswarm.research_rsi.mutation import child_declaration
    store = runtime.store
    limits = Limits.from_mapping(value['limits'])
    target = store.get(value['target_profile_ref'])
    visible = store.get(value['visible_context_ref'])
    need(set(visible) == {'context', 'mandatory_fixtures', 'required_test_refs'}, 'CLOSED_VISIBLE_CONTEXT_REQUIRED')
    tests = visible['mandatory_fixtures']
    need(len(tests) == 12 and len({encoded(t['test_ref']) for t in tests}) == 12
         and {encoded(t['test_ref']) for t in tests} == {encoded(p) for p in target['required_test_refs']}
         and visible['required_test_refs'] == target['required_test_refs'], 'EXACT_TWELVE_PUBLIC_CHECKS_REQUIRED')
    need(len(target['mutable_paths']) == 1, 'ONE_MUTABLE_BODY_REQUIRED')
    parent = store.get(value['parent_declaration_ref'])
    parent_body = store.read(target['parent_ref'])
    need(digest(parent_body) == target['parent_ref']['sha256'], 'PARENT_BYTES_DIFFER')
    parent_checks = await runtime.evaluate(target['parent_ref'], tests, 'parent')
    need(parent_checks['passed'] is True, 'PARENT_PUBLIC_CONTROL_FAILED_NO_MODEL_CALL')
    baseline_ref = store.put({'schema': 'ai4r-rsi-development-baseline:1', 'candidate_ref': target['parent_ref'], **parent_checks})
    evidence = [{'ref': value['visible_context_ref'], 'content': visible['context']},
                {'ref': baseline_ref, 'content': parent_checks}]
    models = [DevelopmentModel(runtime.resources, runtime.lease, value[key], value['id'])
              for key in ('diagnosis_contract_ref', 'proposal_contract_ref')]
    diagnosis = BoundedDiagnosis(models[0], store=store, limits=limits)
    parent_pin = {'cc_name': parent['identity']['name'], 'cc_version': parent['identity']['version_label'],
                  'declaration_sha256': value['parent_declaration_ref']['sha256']}
    await runtime.before_model()
    diagnosed, diagnosis_ref = await diagnosis.diagnose(parent=parent_pin,
        profile_ref=value['target_profile_ref'], preparation_ref=value['preparation_ref'],
        configuration_ref=value['exact_binding_refs']['configuration_ref'],
        authorized_component=value['authorized_component'], observed_symptom=value['observed_symptom'], evidence=evidence)
    proposer = GuardedProposer(models[1], configuration_ref=value['exact_binding_refs']['configuration_ref'],
                              improver_ref=target['improver_ref'], limits=limits, store=store)
    proposal_start_ref = store.put({'schema': 'ai4r-rsi-development-proposer-start:1', 'id': value['id'],
        'contract_ref': value['proposal_contract_ref'], 'target_profile_ref': value['target_profile_ref'],
        'parent_ref': target['parent_ref'], 'visible_context_ref': value['visible_context_ref'], 'diagnosis_ref': diagnosis_ref})
    context = proposal_context({'visible': visible['context'], 'diagnosis': diagnosed},
                               body=parent_body, history=[], mutable_path=target['mutable_paths'][0])
    await runtime.before_model()
    proposal = await proposer.propose(context, None)
    need(len(proposal['body'].encode('utf8')) <= MAX_BYTES//2, 'DEVELOPMENT_CANDIDATE_TOO_LARGE')

    async def declaration(snapshot, child_ref, diff_ref):
        hashes = {row['path']: row['sha256'] for row in parent['identity']['body']}
        hashes[target['mutable_paths'][0]] = child_ref['sha256']
        label = parent['identity']['version_label'] + '.development.' + child_ref['sha256'][:12]
        from jiuwenswarm.research.contracts import validate
        result = child_declaration(parent, body_hashes=hashes, version_label=label,
            carrier=parent['identity']['carrier'], lineage={'parent': value['parent_declaration_ref'], 'co_parents': [],
            'relation': 'supersedes', 'builder': 'rsi_workbench', 'build_trigger': value['id'],
            'context_capsules': [], 'diagnosis_inputs': [diagnosis_ref], 'builder_ref': proposal_start_ref,
            'provenance': {'generating_model': proposer.last_generating_model,
                           'prompt_ref': proposer.last_prompt_ref, 'trajectory_ref': proposer.last_response_ref}}, validate=validate)
        pin_value = store.put(result)
        return result, {'cc_name': result['identity']['name'], 'cc_version': label, 'declaration_sha256': pin_value['sha256']}

    candidate_checks = {}
    async def mandatory(snapshot, declaration_value):
        child_ref = store.put_bytes((Path(snapshot['path'])/target['mutable_paths'][0]).read_bytes())
        checked = await runtime.evaluate(child_ref, tests, 'candidate')
        candidate_checks.update(checked)
        return checked

    assessment = GuardedAssessment(parent_directory=value['parent_directory'], target=target,
        store=store, work_root=value['work_root'], run_mandatory=mandatory, make_declaration=declaration)
    assessed = await assessment(proposal)
    return {'schema': RESULT_SCHEMA, 'id': value['id'], 'status': 'VISIBLE_EVALUATED_UNQUALIFIED', 'security': 'UNQUALIFIED',
            'security_campaigns': 'DEFERRED', 'hidden_evaluation': 'NOT_RUN', 'final_evaluation': 'NOT_RUN',
            'qualification_ref': None, 'package_ref': None, 'admission_ref': None, 'activation_ref': None,
            'diagnosis_ref': diagnosis_ref, 'diagnosis_capture_ref': diagnosis.last_capture_ref,
            'proposal_start_ref': proposal_start_ref,
            'proposal_prompt_ref': proposer.last_prompt_ref, 'proposal_response_ref': proposer.last_response_ref,
            'generation_evidence_refs': [p for model in models for p in model.last_evidence],
            'model_calls': sum(model.last_model_calls or 0 for model in models),
            'parent_body_ref': target['parent_ref'], 'parent_declaration_ref': value['parent_declaration_ref'],
            'target_profile_ref': value['target_profile_ref'], 'visible_context_ref': value['visible_context_ref'],
            'rationale': proposal['rationale'], 'generating_model': proposer.last_generating_model,
            'parent_visible': parent_checks, 'candidate_visible': candidate_checks, 'candidate': assessed,
            'limitations': ['Only the twelve approved public cases were evaluated.',
                            'Security campaigns, hidden evaluation and final qualification are deferred.',
                            'This development result grants no package, admission or activation authority.',
                            *proposer.last_unavailable_reasons]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('plan', 'run'))
    parser.add_argument('--authorization', required=True)
    parser.add_argument('--approved-plan-sha256')
    args = parser.parse_args(argv)
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_ADMIN_REQUIRED')
    value, facts = plan(args.authorization)
    if args.operation == 'plan':
        print(json.dumps({'plan': facts, 'plan_sha256': digest(encoded(facts))}, sort_keys=True))
        return
    need(args.approved_plan_sha256 == digest(encoded(facts)), 'REVIEW_PLAN_CHANGED')
    os.umask(0o077)
    launch(value, facts, args.authorization)


if __name__ == '__main__':
    main()
