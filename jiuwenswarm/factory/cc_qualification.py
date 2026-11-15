"""Explicit, bounded domain qualification of existing sealed CC packages.

Reuses the host's release validator. Never executes, imports or installs code
supplied by an intake package. Eligibility is scoped to a frozen task policy.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .store import NotFound, encoded

MODULES = {f'jiuwenswarm.factory.{name}': name + '.py' for name in (
    'prefill_workbench', 'prefill_worker', 'strata_prefill', 'strata_components',
    'benchmark', 'benchmark_worker', 'benchmark_data', 'benchmark_analysis', 'engine_adapters',
    'strata_lab', 'lab_recorder', 'lab_lifecycle', 'targets', 'job_packages')}
CHECKER = 'strata.prefill_profile.v1'
DIGEST = re.compile('[a-f0-9]{64}')


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ' has invalid or missing fields')


def _names(value, label, maximum=32):
    if (not isinstance(value, list) or not 1 <= len(value) <= maximum
            or any(not isinstance(v, str) or not v or len(v) > 256 for v in value)
            or len(set(value)) != len(value)):
        raise ValueError(label + ' must be a bounded list of unique names')
    return value


def _hash(value):
    return hashlib.sha256(encoded(value).encode('utf-8')).hexdigest()


def _file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _package(store, release):
    from jiuwenswarm.ccv2.ccv2 import Host
    base = getattr(store, '_store', store)
    host = Host(base.home / 'ccstore', session_grants=[])
    declaration, bundle = host.release(release)
    materials = declaration.get('materials', {})
    if 'verification_units' not in materials:
        raise ValueError('Package has no verification_units material')
    path = bundle / materials['verification_units']['path']
    if path.stat().st_size > 65536:
        raise ValueError('Verification-unit material exceeds 64 KiB')
    material = json.loads(path.read_text())
    _object(material, {'format', 'units', 'implementation_modules'}, 'verification_units')
    if material['format'] != 'factory-verification-units/1':
        raise ValueError('Unsupported domain verification-unit material')
    modules = _names(material['implementation_modules'], 'implementation_modules', 32)
    if set(modules) - set(MODULES):
        raise ValueError('Package requests an unsupported implementation module identity')
    closure = {name: _file(Path(__file__).with_name(MODULES[name])) for name in modules}
    units = material['units']
    if not isinstance(units, list) or not 1 <= len(units) <= 16:
        raise ValueError('Supply 1..16 verification units')
    seen = set()
    for unit in units:
        _object(unit, {'id', 'capabilities', 'checker', 'claim'}, 'unit')
        if (not isinstance(unit['id'], str) or not re.fullmatch('[a-z][a-z0-9._-]{0,63}', unit['id'])
                or unit['id'] in seen or not isinstance(unit['checker'], str)
                or not isinstance(unit['claim'], str) or not 1 <= len(unit['claim']) <= 2000):
            raise ValueError('Invalid verification-unit identity or claim')
        _names(unit['capabilities'], 'unit.capabilities')
        if set(unit['capabilities']) - set(declaration['capabilities']):
            raise ValueError('Verification unit names missing package capabilities')
        seen.add(unit['id'])
    identity = dict(release=release, package_id=declaration['id'], version=declaration['version'],
        unit_material_sha256=_file(path), implementation_module_sha256=closure,
        checker_module_sha256=_file(__file__), api_dispatch_sha256=_file(Path(__file__).with_name('api.py')))
    return declaration, material, identity


def inspect_package(store, release):
    declaration, material, identity = _package(store, release)
    return {'package': dict(identity, capabilities={name: {'needs': row['needs'], 'changes': row['changes']}
        for name, row in declaration['capabilities'].items()}, verification_units=material['units'],
        scope='Sealed package identity and known local implementation-file identity only; no execution or isolation guarantee.')}


def _flag(args, name):
    if args.count(name) != 1 or args.index(name) + 1 >= len(args):
        raise ValueError('Exactly one value required: ' + name)
    return args[args.index(name) + 1]


def _profile_pair(values):
    """Independent configuration check; never calls the producer's transformer."""
    _object(values, {'baseline_profile', 'candidate_profile'}, 'profile evidence')
    baseline, candidate = values['baseline_profile'], values['candidate_profile']
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        raise ValueError('Profiles must be objects')
    a, b = baseline.get('args'), candidate.get('args')
    if (not isinstance(a, list) or not isinstance(b, list) or not 1 <= len(a) <= 256
            or not all(isinstance(v, str) and v and len(v) <= 4096 and '\0' not in v and '\n' not in v for v in a + b)):
        raise ValueError('Invalid bounded profile argv')
    if len(a) != len(b) or _flag(a, '--prefill-chunk') != '256' or _flag(b, '--prefill-chunk') != '512':
        raise ValueError('Expected explicit prefill chunk 256 versus 512')
    for args in (a, b):
        for name, value in {'--experts':'6','--mmap-experts':'on','--cpu-threads':'8',
            '--reserve-mib':'16384','--vram-experts':'1.0','--dspark':'none','--dspark-conf':'0.65'}.items():
            if _flag(args, name) != value:
                raise ValueError('Fixed full-model profile changed: ' + name)
        if args.count('--no-expert-cache') != 1 or any('skip' in v.lower() for v in args if v.startswith('--')):
            raise ValueError('Static cache and full target execution required')
    if ('environment' in baseline) == ('env' in baseline):
        raise ValueError('Exactly one environment/env mapping required')
    env = baseline.get('environment', baseline.get('env'))
    allowed = {'DS4_ASYNC_T','DS4_UMA_HEADROOM_GIB','DS4_STORE_GB','DS4_COPY_ALL',
        'DS4_AHEAD','DS4_ENGRAM_THREADS','DS4_ENGRAM_CACHE_MB','STRATA_DS4_REUSE'}
    if (not isinstance(env, dict) or set(env) - allowed
            or any(not isinstance(v, str) or '\0' in v or '\n' in v for v in env.values())):
        raise ValueError('Unsupported effective-environment override')
    for name, value in {'STRATA_DS4_REUSE':'0','DS4_UMA_HEADROOM_GIB':'16','DS4_COPY_ALL':'0','DS4_STORE_GB':'0'}.items():
        if env.get(name) != value:
            raise ValueError('Fixed host/model obligation changed: ' + name)
    expected = copy.deepcopy(baseline)
    expected['args'][a.index('--prefill-chunk') + 1] = '512'
    if candidate != expected:
        raise ValueError('Profile pair changes more than one argument value')
    return dict(changed_variable='--prefill-chunk', baseline='256', candidate='512',
        full_experts=6, draft_enabled=False, adaptive_cache=False,
        limitation='Configuration invariant only; effective allocation, numeric behavior, quality and speed are unmeasured.')


def _save(store, task_id, kind, values):
    obs_id = kind.replace('_', '-') + '-' + _hash(values)
    try:
        existing = store.read(task_id, obs_id)
        if existing.get('kind') != kind or existing.get('values') != values:
            raise ValueError('Qualification observation identity conflict')
    except NotFound:
        try:
            store.append_observation(task_id, dict(obs_id=obs_id, kind=kind, values=values,
                limitations='Explicit scoped domain assessment only; no grants, execution, universal certification or promotion.'))
        except sqlite3.IntegrityError:
            existing = store.read(task_id, obs_id)
            if existing.get('kind') != kind or existing.get('values') != values:
                raise ValueError('Qualification observation identity conflict')
    return obs_id


def verify_unit(store, task_id, release, unit_id, evidence_id):
    _, material, identity = _package(store, release)
    unit = next((u for u in material['units'] if u['id'] == unit_id), None)
    if (unit is None or unit['checker'] != CHECKER
            or identity['package_id'] != 'engine.strata_prefill_workbench'
            or set(identity['implementation_module_sha256']) != set(MODULES)):
        raise ValueError('Missing unit or unsupported explicit checker')
    record = store.read(task_id, evidence_id)
    if record.get('task_id') != task_id or 'values' not in record:
        raise ValueError('Verification requires current-task observation evidence')
    values = record['values']
    if len(encoded(values).encode('utf-8')) > 1024 * 1024:
        raise ValueError('Profile evidence exceeds 1 MiB')
    try:
        observed = _profile_pair(values)
        verdict, reasons = 'passed', []
    except (ValueError, TypeError, KeyError) as exc:
        observed, verdict, reasons = {}, 'failed', [str(exc)]
    result = dict(schema_version=1, identity=identity, unit=unit, evidence_id=evidence_id,
        evidence_task_id=task_id, evidence_values_sha256=_hash(values), verdict=verdict,
        reasons=reasons, observed=observed, tier='bounded_configuration_invariant',
        checked_by=CHECKER, runtime_qualified=False, scientific_benefit='not_evaluated',
        execution_authorized=False, promotion_authorized=False)
    return {'verification': result, 'observation_id': _save(store, task_id, 'cc_unit_verification', result)}


def assess_admission(store, task_id, policy_id, verification_ids):
    _names(verification_ids, 'verification_ids', 32)
    configuration = store.get_task(task_id).get('constraints', {}).get('cc_qualification', {})
    policies = configuration.get('policies', []) if isinstance(configuration, dict) else []
    matches = [p for p in policies if isinstance(p, dict) and p.get('id') == policy_id]
    if len(matches) != 1:
        raise ValueError('Policy must identify one operator task constraint')
    policy = matches[0]
    _object(policy, {'id','release','capabilities','required_units','allowed_effects'}, 'policy')
    for name in ('capabilities','required_units'):
        _names(policy[name], 'policy.' + name)
    effects = policy['allowed_effects']
    if not isinstance(effects, list) or any(not isinstance(v, str) for v in effects):
        raise ValueError('Invalid policy effect ceiling')
    declaration, material, identity = _package(store, policy['release'])
    if set(policy['capabilities']) - set(declaration['capabilities']):
        raise ValueError('Policy capability absent from sealed release')
    units = {u['id']:u for u in material['units']}
    if set(policy['required_units']) - set(units):
        raise ValueError('Policy unit absent from sealed material')
    reasons, passed = [], set()
    for ref in verification_ids:
        record = store.read(task_id, ref)
        value = record.get('values', {})
        if not isinstance(value, dict):
            raise ValueError('Verification observation payload must be an object')
        if (record.get('task_id') != task_id or record.get('kind') != 'cc_unit_verification'
                or value.get('identity') != identity or value.get('evidence_task_id') != task_id):
            raise ValueError('Wrong-task, stale release/material/module/checker verification identity')
        unit = value.get('unit', {})
        if (not isinstance(unit, dict) or not isinstance(unit.get('id'), str)
                or unit['id'] not in units or unit != units[unit['id']] or value.get('checked_by') != CHECKER):
            raise ValueError('Verification unit/checker differs from sealed package')
        source = store.read(task_id, value['evidence_id'])
        if _hash(source.get('values')) != value.get('evidence_values_sha256'):
            raise ValueError('Verification evidence changed')
        # Re-evaluate the bounded check instead of trusting a caller-authored
        # observation that merely claims to be a qualification certificate.
        try:
            _profile_pair(source['values'])
            actual = 'passed'
        except (ValueError, TypeError, KeyError):
            actual = 'failed'
        if value.get('verdict') != actual:
            raise ValueError('Saved qualification verdict disagrees with independent check')
        if actual == 'passed':
            passed.add(unit['id'])
    missing = sorted(set(policy['required_units']) - passed)
    if missing:
        reasons.append('Required verification units not passed: ' + ', '.join(missing))
    for capability in policy['capabilities']:
        if set(declaration['capabilities'][capability]['changes']) - set(effects):
            reasons.append('Selected capability exceeds policy effect ceiling: ' + capability)
        if not any(capability in units[u]['capabilities'] for u in policy['required_units']):
            reasons.append('Selected capability lacks a required verification-unit boundary: ' + capability)
    result = dict(schema_version=1, policy_id=policy_id, policy_sha256=_hash(policy), identity=identity,
        capabilities=policy['capabilities'], verification_ids=verification_ids,
        verdict='eligible' if not reasons else 'blocked', reasons=reasons,
        claim_scope='Selected package capabilities under this operator policy and bounded configuration checks only',
        authority='No execution, installation, session grants or promotion; normal host admission remains mandatory.',
        runtime_qualified=False, scientific_benefit='not_evaluated', execution_authorized=False,
        promotion_authorized=False)
    return {'eligibility': result, 'observation_id': _save(store, task_id, 'cc_admission_assessment', result)}


def dispatch(store, task_id, operation, inputs):
    signatures = {'inspect_package': {'release'}, 'verify_unit': {'release','unit_id','evidence_id'},
                  'assess_admission': {'policy_id','verification_ids'}}
    if operation not in signatures:
        raise ValueError('Unknown CC qualification capability')
    _object(inputs, signatures[operation], 'inputs')
    if operation == 'inspect_package':
        return inspect_package(store, **inputs)
    if operation == 'verify_unit':
        return verify_unit(store, task_id, **inputs)
    return assess_admission(store, task_id, **inputs)
