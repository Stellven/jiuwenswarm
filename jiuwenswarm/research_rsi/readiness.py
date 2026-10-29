"""Read-only RSI diagnostics, distinct from execution or security authority.

Only fixed protected captures are inspected. This module never constructs a
writable store, replays recovery, opens a model backend, evaluates a fixture,
or accepts a configuration-selected Python callback. Static capture checks can
be CONFIGURED; current runtime eligibility requires the explicit live diagnostic
against the already running, independently qualified role owners.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .bootstrap import load_config

DEFAULT_CONFIG = '/run/ai4r-rsi/jobs-service.json'
MAX_BYTES = 4 * 1024 * 1024
PRIVATE_SCHEMAS = (
    'urn:ai4r:private:rsi-final-budget:1',
    'urn:ai4r:private:rsi-session-phase:1',
    'urn:ai4r:private:rsi-security-incident:1',
    'urn:ai4r:private:rsi-clearance-policy:1',
)
MESSAGES = {
    'SCHEMAS': 'Required neutral RSI contracts must be installed.',
    'SERVICE_CONFIG': 'Root-protected fixed jobs configuration and UID12001 are required.',
    'RESOURCE_BINDING': 'Exact protected workbench resource binding is required.',
    'ISOLATED_ROOTS': 'Controller, account, work and capture roots must have isolated role custody.',
    'CORE_SNAPSHOT': 'An existing protected checkpointed core index is required for read-only diagnosis.',
    'OPERATOR_PINS': 'Exact captured configuration, deployment, model profile and custodian public-key pin are required.',
    'AUTHORIZED_JOBS': 'Every allowlisted job must bind an exact approved immutable session.',
    'FROZEN_TARGETS': 'Frozen admitted parent, profile, worker, visible tests and final reserve must reconcile.',
    'OPPORTUNITY_PREPARATION': 'Canonical opportunity preparation must have independent protected approval and exact visible evidence.',
    'CLEARANCE_POLICY': 'A protected independent clearance policy must be captured.',
    'SECURITY_CAPTURE': 'An exact security qualification capture must be present; presence alone grants no authority.',
    'IF015_AUTHORITY': 'Current independent scope and thirteen-case authority require live owner inspection.',
    'WORKER_RUNTIME': 'Actual authenticated worker UID/profile/confinement has not been observed by this static diagnostic.',
    'CUSTODIAN_RUNTIME': 'Actual independent fixture custody, calibration and final-budget populations require the custodian observer.',
    'MODEL_RUNTIME': 'Already-running dedicated model access and containment require live inspection; this static diagnostic contacted no backend.',
    'DIAGNOSIS_RUNTIME': 'The bounded governed diagnosis contract requires live owner inspection; doctor never makes the diagnosis call.',
    'SESSION_HISTORY': 'Current durable clearance, phase, job and native-lease reconciliation requires its independent runtime owner.',
}


def _path(value):
    if not isinstance(value, (str, Path)):
        raise ValueError('path')
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('path')
    return path


def _regular(path, *, uid, maximum=MAX_BYTES):
    path = _path(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        meta = os.fstat(descriptor)
        owners = uid if isinstance(uid, tuple) else (uid,)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or
                meta.st_uid not in owners or meta.st_mode & 0o022 or meta.st_size > maximum):
            raise ValueError('custody')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError('size')
        return data
    finally:
        os.close(descriptor)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate')
            result[key] = value
        return result
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))


def _ref(pin):
    if (not isinstance(pin, dict) or set(pin) != {'id', 'sha256'} or
            not isinstance(pin['id'], str) or not pin['id'] or
            not isinstance(pin['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', pin['sha256'])):
        raise ValueError('ref')


def _directory(value, uid=12001, *, shared=False):
    path = _path(value)
    meta = path.stat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != uid:
        raise ValueError('directory')
    if shared:
        if meta.st_gid != 13000 or stat.S_IMODE(meta.st_mode) != 0o2750:
            raise ValueError('shared')
    elif meta.st_mode & 0o077:
        raise ValueError('private')
    return path


class _ReadOnlyCaptures:
    """Finite pinned-byte reads; immutable SQLite never creates WAL or SHM.

    Nonempty WAL/journal is refused because immutable SQLite would ignore its
    latest state. Diagnosis never checkpoints, recovers or migrates that state.
    """
    def __init__(self, record_root, *, uid=12001):
        self.root = _directory(record_root, uid)
        self.uid = uid
        self.core = None
        self.connection = None
        self.cache = {}
        self.total = 0

    def attach_core(self, core_root):
        self.core = _directory(core_root, self.uid)
        database = self.core / 'state/research.sqlite3'
        _regular(database, uid=self.uid, maximum=128 * 1024 * 1024)
        for suffix in ('-wal', '-journal'):
            side = _path(str(database) + suffix)
            if side.exists() and side.stat().st_size:
                raise ValueError('uncheckpointed')
        self.connection = sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)
        self.connection.execute('PRAGMA query_only=ON')
        self.connection.execute('PRAGMA trusted_schema=OFF')
        if dict(self.connection.execute("SELECT name,type FROM sqlite_master WHERE name IN ('artifacts','records')")) != {'artifacts': 'table', 'records': 'table'}:
            raise ValueError('protected index tables')
        self.connection.execute('SELECT id,sha256 FROM artifacts LIMIT 0')
        self.connection.execute('SELECT id,kind FROM records LIMIT 0')

    def read(self, pin):
        _ref(pin)
        identity = (pin['id'], pin['sha256'])
        if identity in self.cache:
            return self.cache[identity]
        if len(self.cache) >= 512 or self.total >= 64 * 1024 * 1024:
            raise ValueError('diagnostic ceiling')
        digest = pin['sha256']
        if pin['id'] == digest + '.json' and (self.root / pin['id']).exists():
            raw = _regular(self.root / pin['id'], uid=self.uid)
        else:
            if self.connection is None:
                raise ValueError('index unavailable')
            row = self.connection.execute('SELECT sha256 FROM artifacts WHERE id=?', (pin['id'],)).fetchone()
            if row is None or row[0] != digest:
                raise ValueError('indexed identity')
            raw = _regular(self.core / 'artifacts/sha256' / digest[:2] / digest, uid=self.uid)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('digest')
        self.cache[identity] = raw
        self.total += len(raw)
        return raw

    def get(self, pin):
        value = _json(self.read(pin))
        if not isinstance(value, dict):
            raise ValueError('record')
        return value

    def record_kind(self, pin):
        self.read(pin)
        if self.connection is None:
            raise ValueError('type index')
        row = self.connection.execute('SELECT r.kind FROM records r JOIN artifacts a ON r.id=a.id WHERE r.id=? AND a.sha256=?',
                                      (pin['id'], pin['sha256'])).fetchone()
        if row is None:
            raise ValueError('type absent')
        return row[0]

    def close(self):
        if self.connection is not None:
            self.connection.close()


def _resource_binding(reader, config):
    from .fixed_resources import closed
    binding = reader.get(config['resource_binding_ref'])
    fields = {'isolation_root', 'core_root', 'account_root', 'forbidden_roots', 'principal', 'exact_binding_refs',
              'run_contexts', 'custodian', 'worker', 'parent_directory', 'work_root', 'approved_session_refs',
              'public_root', 'public_record_refs', 'native_containment_ref'}
    versions = {'ai4r-rsi-workbench-resources:1': fields,
                'ai4r-rsi-workbench-resources:2': fields | {'security_qualification_ref'},
                'ai4r-rsi-workbench-resources:3': fields | {'security_qualification_ref', 'clearance_policy_ref'}}
    versions['ai4r-rsi-workbench-resources:4'] = versions['ai4r-rsi-workbench-resources:3'] | {'approved_preparation_refs'}
    if binding.get('schema') not in versions:
        raise ValueError('version')
    closed(binding, versions[binding['schema']], binding['schema'])
    return binding


def _isolation(config, binding):
    root = _directory(binding['isolation_root'])
    if not binding['forbidden_roots'] or not isinstance(binding['forbidden_roots'], list):
        raise ValueError('forbidden roots')
    forbidden = [_path(v) for v in binding['forbidden_roots']]
    forbidden.extend(Path(v) for v in ('/var/lib/ai4r', '/var/lib/ai4r-accounts', '/opt/ai4r-local'))
    for name in ('core_root', 'account_root', 'work_root', 'parent_directory'):
        path = _directory(binding[name])
        if not path.is_relative_to(root) or any(path == other or path.is_relative_to(other) or other.is_relative_to(path) for other in forbidden):
            raise ValueError('isolation')
    if not _directory(config['record_root']).is_relative_to(root) or not _directory(config['job_root']).is_relative_to(root):
        raise ValueError('capture isolation')
    _directory(binding['public_root'], shared=True)


def _operator(reader, binding):
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    exact = binding['exact_binding_refs']
    if set(exact) != {'configuration_ref', 'model_selection_profile_ref', 'deployment_ref', 'workspace_id', 'protected_options'}:
        raise ValueError('binding set')
    for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref'):
        reader.read(exact[key])
    captured = reader.get(exact['configuration_ref'])
    operator = OperatorConfiguration.from_mapping(captured.get('operator', captured), resolve_profile=reader.get).snapshot()
    if operator['rsi']['custodian_public_key'] is None or operator['rsi']['custodian_key_id'] is None:
        raise ValueError('public pin absent')
    # Inspecting the public pin never reads or mounts the custodian private key.
    return operator


def _jobs(reader, config, binding):
    from .fixed_resources import closed
    pins = config['allowed_job_refs']
    if not isinstance(pins, list) or not 0 < len(pins) <= 32 or not binding['approved_session_refs']:
        raise ValueError('job bound')
    jobs = []
    for pin in pins:
        _ref(pin)
        if not re.fullmatch('job_[a-z0-9_]+', pin['id']):
            raise ValueError('job identity')
        raw = _regular(_path(config['job_root']) / (pin['id'] + '.json'), uid=(0, 12001))
        if hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise ValueError('job digest')
        job = _json(raw)
        fields = {'session_ref', 'opportunity_ref', 'visible_context_ref', 'proposer_contract_refs', 'worker_profile_ref',
                  'fixture_identity', 'target_kind'}
        if job.get('schema') == 'ai4r-rsi-session-job:2':
            closed(job, fields - {'opportunity_ref'} | {'preparation_ref', 'diagnosis_contract_ref'}, 'ai4r-rsi-session-job:2')
        else:
            closed(job, fields, 'ai4r-rsi-session-job:1')
        if job['session_ref'] not in binding['approved_session_refs']:
            raise ValueError('session grant')
        reader.read(job['session_ref'])
        jobs.append(job)
    if len({json.dumps(job['session_ref'], sort_keys=True) for job in jobs}) != len(jobs):
        raise ValueError('duplicate session grants')
    return jobs


def _frozen_targets(reader, binding, jobs):
    from jiuwenswarm.research_records.contracts import ContractData
    from .profiles import freeze_profile, Limits
    from .session_policy import FinalBudget
    from .worker import validate_profile
    from .fixed_resources import closed
    validate = ContractData().validate
    closed(binding['worker'], {'socket_path', 'session_id', 'capability', 'requests_root', 'profile_ref'}, 'ai4r-rsi-worker-client:1')
    closed(binding['custodian'], {'socket_path', 'peer_uid', 'requests_root', 'public_roots'}, 'ai4r-rsi-custodian-client:1')
    if binding['custodian']['peer_uid'] != 12002:
        raise ValueError('custodian uid')
    for job in jobs:
        from .targets import registered_helper
        registered_helper(job['target_kind'])
        session = reader.get(job['session_ref'])
        validate('rsi-session', session)
        if session['started_by'] != binding['principal']['account_id']:
            raise ValueError('actor')
        parent = reader.get(session['parent_declaration_ref'])
        validate('capsule-declaration', parent)
        target = reader.get(session['target_profile_ref'])
        freeze_profile(target, parent, validate)
        if (target['parent_declaration_ref'] != session['parent_declaration_ref'] or
                session['configuration_ref'] != binding['exact_binding_refs']['configuration_ref'] or
                any(session[key] != target[key] for key in ('configuration_ref', 'improver_ref', 'scoring_adapter_ref'))):
            raise ValueError('frozen context')
        if session['parent'] != {'cc_name': parent['identity']['name'], 'cc_version': parent['identity']['version_label'],
                                 'declaration_sha256': session['parent_declaration_ref']['sha256']}:
            raise ValueError('parent pin')
        reader.read(target['parent_ref'])
        worker = validate_profile(reader.get(job['worker_profile_ref']))
        if (job['worker_profile_ref'] != binding['worker']['profile_ref'] or worker['session_ref'] != job['session_ref'] or
                worker['target_ref'] != session['target_profile_ref'] or worker['parent_ref'] != target['parent_ref'] or
                worker['target_kind'] != job['target_kind']):
            raise ValueError('worker scope')
        limits = Limits.from_mapping(session['limits'])
        if session['pass_count_repeats'] != 1 or worker['memory_mb'] > target['limits']['memory_mb'] or worker['timeout_s'] > min(target['limits']['time_s'], limits.per_call_s):
            raise ValueError('resource ceilings')
        if len(job['proposer_contract_refs']) != limits.max_attempts:
            raise ValueError('proposal bounds')
        for pin in job['proposer_contract_refs']:
            validate('subnode-execution-contract', reader.get(pin))
        genesis = reader.get(session['chain_root_ref'])
        if (genesis.get('target_ref') != session['target_profile_ref'] or genesis.get('hash_profile_ref') != session['hash_profile_ref'] or
                genesis.get('session_id') != session['session_id'] or genesis.get('interface_revision') != 'M1-IF-009@r2'):
            raise ValueError('genesis')
        reader.read(session['hash_profile_ref'])
        FinalBudget.for_session(session, reader, worker_profile=worker)
        visible = reader.get(job['visible_context_ref'])
        if set(visible) != {'context', 'mandatory_fixtures', 'required_test_refs'} or visible['required_test_refs'] != target['required_test_refs'] or not visible['mandatory_fixtures']:
            raise ValueError('visible obligations')
        for fixture in visible['mandatory_fixtures']:
            if set(fixture) != {'input_ref', 'test_ref'} or fixture['test_ref'] not in target['required_test_refs']:
                raise ValueError('visible binding')
            reader.read(fixture['input_ref'])
        for pin in target['required_test_refs'] + target['protected_refs']:
            reader.read(pin)
        if reader.connection is None:
            raise ValueError('admission index')
        row = reader.connection.execute('SELECT declaration_ref,admission_ref FROM library_versions WHERE name=? AND version=?',
                (session['parent']['cc_name'], session['parent']['cc_version'])).fetchone()
        if row is None or _json(row[0].encode()) != session['parent_declaration_ref']:
            raise ValueError('parent admission')
        admission_ref = _json(row[1].encode())
        admission = reader.get(admission_ref)
        validate('library-admission', admission)
        if reader.record_kind(admission_ref) != 'library-admission' or admission['status'] != 'admitted' or worker['memory_mb'] > admission['memory_mb']:
            raise ValueError('admitted resource scope')
        # Hash only declared parent files. No candidate code is imported/run.
        root = _path(binding['parent_directory'])
        expected = {row['path']: row['sha256'] for row in parent['identity']['body']}
        for dependency in parent['needs']['external']:
            pin = dependency.get('pin')
            if isinstance(pin, dict) and set(pin) == {'ref', 'sha256'}:
                expected[pin['ref']] = pin['sha256']
        paths = {p.relative_to(root).as_posix(): p for p in root.rglob('*') if p.is_file() or p.is_symlink()}
        if set(paths) != set(expected):
            raise ValueError('parent closure')
        for name, path in paths.items():
            if hashlib.sha256(_regular(path, uid=(0, 12001))).hexdigest() != expected[name]:
                raise ValueError('parent bytes')


def _opportunity_preparation(reader, binding, jobs):
    from .opportunity import validated_preparation
    from jiuwenswarm.research_records.contracts import ContractData
    for job in jobs:
        # Historical jobs remain inspectable, but their ad hoc START flags are
        # never sufficient for a new autonomous session.
        if job['schema'] != 'ai4r-rsi-session-job:2':
            raise ValueError('canonical preparation absent')
        session = reader.get(job['session_ref'])
        args = dict(approved_preparation_refs=binding['approved_preparation_refs'],
                    profile_ref=session['target_profile_ref'], parent=session['parent'])
        validated_preparation(reader, job['preparation_ref'], **args)
        ContractData().validate('subnode-execution-contract', reader.get(job['diagnosis_contract_ref']))


def check_doctor(config_path=None):
    """Return safe fixed-code findings. This diagnostic grants no authority."""
    findings = []
    reader = None
    errors = (ValueError, OSError, TypeError, KeyError, AttributeError, ImportError, RecursionError, sqlite3.Error)
    def check(code, operation):
        try:
            result = operation()
        except errors:
            findings.append({'check': code, 'state': 'BLOCKED', 'reason': MESSAGES[code]})
            return None
        findings.append({'check': code, 'state': 'CONFIGURED', 'reason': MESSAGES[code]})
        return result
    try:
        def schemas():
            from jiuwenswarm.research_records.contracts import ContractData
            contracts = ContractData()
            if any(name not in contracts.schemas for name in PRIVATE_SCHEMAS):
                raise ValueError('schema unavailable')
            return contracts
        check('SCHEMAS', schemas)
        def service_config():
            path = _path(config_path or DEFAULT_CONFIG)
            _json(_regular(path, uid=0))
            return load_config(path, 'jobs')
        config = check('SERVICE_CONFIG', service_config)
        if config is not None:
            def resources():
                nonlocal reader
                reader = _ReadOnlyCaptures(config['record_root'])
                return _resource_binding(reader, config)
            binding = check('RESOURCE_BINDING', resources)
            if binding is not None:
                isolation = check('ISOLATED_ROOTS', lambda: (_isolation(config, binding), True)[1])
                if isolation:
                    core = check('CORE_SNAPSHOT', lambda: (reader.attach_core(binding['core_root']), True)[1])
                    if core:
                        check('OPERATOR_PINS', lambda: _operator(reader, binding))
                    jobs = check('AUTHORIZED_JOBS', lambda: _jobs(reader, config, binding))
                    if jobs is not None:
                        check('FROZEN_TARGETS', lambda: (_frozen_targets(reader, binding, jobs), True)[1])
                        check('OPPORTUNITY_PREPARATION', lambda: (_opportunity_preparation(reader, binding, jobs), True)[1])
                    def policy():
                        from .session_policy import validate_private
                        validate_private('urn:ai4r:private:rsi-clearance-policy:1', reader.get(binding['clearance_policy_ref']))
                        return True
                    check('CLEARANCE_POLICY', policy)
                    def security_capture():
                        from jiuwenswarm.research_records.contracts import ContractData
                        captured = reader.get(binding['security_qualification_ref'])
                        ContractData().validate('urn:ai4r:private:rsi-security-qualification:1', captured)
                        return True
                    check('SECURITY_CAPTURE', security_capture)
    finally:
        if reader is not None:
            reader.close()
    # Static files cannot establish these current facts. Only authenticated
    # runtime owners can supply them; captured READY/PASS flags cannot.
    for code in ('IF015_AUTHORITY', 'WORKER_RUNTIME', 'CUSTODIAN_RUNTIME', 'MODEL_RUNTIME', 'DIAGNOSIS_RUNTIME', 'SESSION_HISTORY'):
        findings.append({'check': code, 'state': 'UNAVAILABLE', 'reason': MESSAGES[code]})
    static = [row for row in findings if row['state'] != 'UNAVAILABLE']
    return {'schema': 'ai4r-rsi-doctor:1', 'status': 'BLOCKED',
            'configured': bool(static) and all(row['state'] == 'CONFIGURED' for row in static),
            'read_only': True, 'operational_ready': False, 'findings': findings,
            'blockers': [row['check'] for row in findings if row['state'] != 'CONFIGURED']}


async def check_doctor_live(config_path=None,*,job_ref=None):
    """Query existing authenticated owners, without snapshot/checkpoint startup.

    In contrast to the static diagnostic this does not open immutable SQLite:
    a running service's WAL is inspected by its actual owner through SELECTs.
    """
    from .ports import request
    from .runtime_readiness import validate_report
    reports=[]
    try:
        path=_path(config_path or DEFAULT_CONFIG)
        _json(_regular(path,uid=0));config=load_config(path,'jobs')
        allowed=config['allowed_job_refs']
        if not isinstance(allowed,list) or not 0<len(allowed)<=32:raise ValueError('allowlist')
        for pin in allowed:_ref(pin)
        if job_ref is not None and job_ref not in allowed:raise ValueError('job grant')
    except (ValueError,OSError,TypeError,KeyError,AttributeError,ImportError,RecursionError):
        return {'schema':'ai4r-rsi-doctor-live:1','status':'BLOCKED','read_only':True,
                'operational_ready':False,'eligible_for':'human_session_start','ready_job_refs':[],
                'jobs':[],'blockers':['SERVICE_CONFIG']}
    for pin in ([job_ref] if job_ref is not None else allowed):
        try:
            reply=await request(config['socket_path'],12001,'session_readiness',pin,timeout=30)
            if reply.get('status')!='ok':raise ValueError('live owner')
            report=validate_report(reply['result'])
            if report['schema']!='ai4r-rsi-runtime-readiness:1':raise ValueError('wrong owner')
            reports.append({'job_ref':pin,'status':report['status'],'blockers':report['blockers'],'report':report})
        except (ValueError,OSError,TypeError,KeyError,AttributeError,ImportError,RecursionError):
            reports.append({'job_ref':pin,'status':'BLOCKED','blockers':['LIVE_SERVICE'],'report':None})
    ready=[row['job_ref'] for row in reports if row['status']=='READY']
    return {'schema':'ai4r-rsi-doctor-live:1','status':'READY' if ready else 'BLOCKED','read_only':True,
            'operational_ready':bool(ready),'eligible_for':'human_session_start','ready_job_refs':ready,
            'jobs':reports,'blockers':[] if ready else sorted({code for row in reports for code in row['blockers']})}
