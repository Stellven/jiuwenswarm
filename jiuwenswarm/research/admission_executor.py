"""IF013: pre-admission jobs have their own authority, never an admitted grant."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import os
import secrets
import stat
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from .contracts import ResearchError, validate
from .bridge import BridgeError
from .executor import ExecutorBlocked, RestrictedExecutor
from .private_rpc import PrivateRPCServer
from .state import json_bytes


def require(value, reason):
    if not value:
        raise ResearchError('self_test_evidence', reason)


def timestamp():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def expiry(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def ref_record(store, ref, kind):
    require(store.record_kind(ref) == kind, 'Original protected ' + kind + ' capture required')
    value = store.read_record(ref)
    if kind in {'admission-self-test-request', 'admission-self-test-job', 'admission-self-test-result',
                'admission-self-test-candidate-execution'}:
        validate('urn:jiuwenswarm:m1-private:' + kind + ':1', value)
    return value


def canonical_path(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name
            and not any(ord(c) < 32 for c in name), 'Invalid candidate relative path')
    require(not PurePosixPath(name).is_absolute() and all(p not in {'', '.', '..'} for p in name.split('/')),
            'Invalid candidate relative path')
    return name


def installed_driver(store):
    root = Path(__file__).parent
    files = {name: store.put_blob((root / name).read_bytes())
             for name in ('_admission_driver.py', '_admission_candidate.py')}
    return store.put_blob(json_bytes(files))


def installed_runtime(store):
    path = Path(sys._base_executable).resolve(strict=True)
    return store.put_blob(json_bytes({'executable': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                     'version': list(sys.version_info[:3])}))


def prepare_admission_profile(store, *, configuration_ref, carrier_refs, limits):
    """Capture authoring data only; protected startup must explicitly select it."""
    store.read_blob(configuration_ref)
    validate('Limits', {k: limits[k] for k in ('time_s', 'memory_mb')} | {'model_calls': 0})
    require(type(limits.get('pids_max')) is int and limits['pids_max'] > 0, 'Explicit PID allowance required')
    for ref in carrier_refs: store.read_blob(ref)
    return store.append_record('admission-execution-profile', {
        'schema': 'ai4r-admission-execution-profile:1', 'id': 'admission-profile:' + uuid.uuid4().hex,
        'configuration_ref': configuration_ref, 'driver_ref': installed_driver(store),
        'runtime_ref': installed_runtime(store), 'carrier_refs': list(carrier_refs), 'limits': dict(limits),
        'supported_adapters': ['python_command_v1', 'python_fixture_v1'], 'max_candidate_calls': 1,
    })


class AdmissionTestProvider:
    """Protected APP issuer/authorizer; all reconstruction uses durable records."""
    def __init__(self, store, *, configuration_ref, execution_profile_ref, rpc):
        self.store, self.configuration_ref, self.profile_ref, self.rpc = store, configuration_ref, execution_profile_ref, rpc
        self.profile = ref_record(store, execution_profile_ref, 'admission-execution-profile')
        require(self.profile['configuration_ref'] == configuration_ref, 'Admission configuration differs')
        require(self.profile['schema'] == 'ai4r-admission-execution-profile:1', 'Unsupported admission profile')

    def _subject(self, test_id, declaration_ref, body_refs):
        declaration = self.store.read_record(declaration_ref, contract_id='capsule-declaration')
        matches = [t for t in declaration['guarantees'].get('self_tests', []) if t['id'] == test_id]
        require(len(matches) == 1, 'Self-test is not uniquely declared')
        test = matches[0]
        names = [canonical_path(p) for p in body_refs]
        require(len(set(n.casefold() for n in names)) == len(names), 'Ambiguous candidate paths')
        for path, ref in body_refs.items(): self.store.read_blob(ref)
        required = {p['path']: p['sha256'] for p in declaration['identity']['body']}
        required[declaration['identity']['carrier']['ref']] = declaration['identity']['carrier']['sha256']
        for dependency in declaration['needs']['external']:
            for key in ('pin', 'lockfile'):
                if pin := dependency.get(key): required[pin['ref']] = pin['sha256']
        for item in declaration['guarantees'].get('self_tests', []): required[item['ref']['ref']] = item['ref']['sha256']
        require(set(required) == set(body_refs) and all(body_refs[p]['sha256'] == digest for p, digest in required.items()),
                'Candidate/test/dependency closure differs from exact declared bytes')
        carrier = body_refs[declaration['identity']['carrier']['ref']]
        if carrier not in self.profile['carrier_refs']:
            raise ResearchError('self_test_adapter_unbuilt', 'Exact admission carrier adapter is not prebound')
        if (declaration['needs']['injects'] or declaration['needs'].get('secrets')
                or declaration['needs']['network']['mode'] != 'none'):
            raise ResearchError('self_test_adapter_unbuilt', 'Model or privileged admission carrier adapter is unbuilt')
        if 'python_' + test['kind'] + '_v1' not in self.profile['supported_adapters']:
            raise ResearchError('self_test_adapter_unbuilt', 'Required self-test adapter is unbuilt')
        return declaration, test

    def issue(self, test, declaration_ref, body_refs, *, actor, memory_mb):
        actor.require('library_admit')
        require(type(memory_mb) is int and memory_mb > 0, 'Actual admission memory allowance required')
        declaration, original = self._subject(test['id'], declaration_ref, body_refs)
        require(test == original, 'Self-test differs from the declaration')
        limits = {'time_s': min(self.profile['limits']['time_s'], declaration['budget']['per_call']['wall_s']),
                  'memory_mb': min(memory_mb, self.profile['limits']['memory_mb']), 'pids_max': self.profile['limits']['pids_max']}
        created = timestamp()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=limits['time_s'])).isoformat().replace('+00:00', 'Z')
        request = self.store.append_record('admission-self-test-request', {
            'schema': 'ai4r-admission-self-test-request:1', 'id': 'admission-request:' + uuid.uuid4().hex,
            'actor_id': actor.account_id, 'operation': 'library_admit', 'declaration_ref': declaration_ref,
            'test_id': test['id'], 'body_refs': copy.deepcopy(body_refs), 'configuration_ref': self.configuration_ref,
            'execution_profile_ref': self.profile_ref, 'admission_memory_mb': memory_mb, 'created_at': created, 'expires_at': expires})
        job = {'schema': 'ai4r-admission-self-test-job:1', 'id': 'admission-job:' + uuid.uuid4().hex,
               'admission_request_ref': request, 'declaration_ref': declaration_ref, 'test_id': test['id'],
               'test_ref': body_refs[test['ref']['ref']], 'body_refs': copy.deepcopy(body_refs),
               'configuration_ref': self.configuration_ref, 'execution_profile_ref': self.profile_ref,
               'driver_ref': self.profile['driver_ref'], 'limits': limits, 'created_at': created, 'expires_at': expires}
        validate('urn:jiuwenswarm:m1-private:admission-self-test-job:1', job)
        return self.store.append_record('admission-self-test-job', job)

    def _original_job(self, job_ref):
        """Reconstruct captured authority without renewing execution permission."""
        job = ref_record(self.store, job_ref, 'admission-self-test-job')
        request = ref_record(self.store, job['admission_request_ref'], 'admission-self-test-request')
        require(request['operation'] == 'library_admit' and bool(request['actor_id']), 'No original admission authority')
        require(job['configuration_ref'] == request['configuration_ref'] == self.configuration_ref
                and job['execution_profile_ref'] == request['execution_profile_ref'] == self.profile_ref,
                'Admission scope/profile changed')
        require(ref_record(self.store, self.profile_ref, 'admission-execution-profile') == self.profile, 'Profile changed')
        require(all(job[k] == request[k] for k in ('declaration_ref', 'test_id', 'body_refs', 'created_at', 'expires_at')),
                'Issued job differs from its original admission request')
        declaration, test = self._subject(job['test_id'], job['declaration_ref'], job['body_refs'])
        limits = {'time_s': min(self.profile['limits']['time_s'], declaration['budget']['per_call']['wall_s']),
                  'memory_mb': min(request['admission_memory_mb'], self.profile['limits']['memory_mb']),
                  'pids_max': self.profile['limits']['pids_max']}
        require(job['limits'] == limits and job['test_ref'] == job['body_refs'][test['ref']['ref']]
                and job['driver_ref'] == self.profile['driver_ref'], 'Admission effective job widened or changed')
        return copy.deepcopy(job)

    def authorize(self, job_ref):
        job = self._original_job(job_ref)
        require(expiry(job['expires_at']) > time.time(), 'Admission job expired')
        return job

    def for_admission(self, actor, memory_mb):
        actor.require('library_admit')
        issued = {}
        async def run(test, declaration_ref, body_refs):
            key = hashlib.sha256(json_bytes([test, declaration_ref, body_refs])).hexdigest()
            if key not in issued: issued[key] = self.issue(test, declaration_ref, body_refs, actor=actor, memory_mb=memory_mb)
            if self.rpc is None: raise ResearchError('self_test_unavailable', 'Admission executor IPC unavailable')
            try:
                result = self.rpc.run_admission_self_test(issued[key])
                result = await result if inspect.isawaitable(result) else result
            except BridgeError as error:
                if error.code not in {'ENVIRONMENT_BLOCKED', 'AUDIT_UNAVAILABLE', 'DELIVERY_UNKNOWN', 'timeout'}:
                    raise
                raise ResearchError('self_test_unavailable', 'Protected self-test facility or terminal evidence is unavailable; no retry',
                                    {'transport_code': error.code}) from None
            require(self.store.record_kind(result) == 'admission-self-test-result', 'No original admission result')
            return result
        return run


@dataclass(frozen=True)
class AdmissionKernelJob:
    job_id: str
    invocation_id: str
    contract_ref: dict
    cwd: Path
    timeout_s: float
    memory_mb: int
    pids_max: int
    argv: tuple
    readonly_mounts: tuple = field(default_factory=tuple)
    environment: object = None


class AdmissionExecutor:
    """Root-only finite producer; neither child receives store/broker authority."""
    def __init__(self, store, kernel, *, authorize, ledger, staging_root):
        self.store, self.kernel, self.authorize_job, self.ledger = store, kernel, authorize, ledger
        self.root = Path(staging_root)
        self.active = {}

    async def _authorize(self, ref):
        value = self.authorize_job(ref)
        value = await value if inspect.isawaitable(value) else value
        require(value == ref_record(self.store, ref, 'admission-self-test-job'), 'Admission authorization differs')
        return value

    def _write(self, root, name, data, *, private=False):
        target = root / canonical_path(name)
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write(data)
        target.chmod(0o400 if private else 0o444)
        if private: os.chown(target, 10002, 10002)
        return target

    def _command(self, kernel_job, resources, *, socket=None):
        command = self.kernel._sandbox(kernel_job)
        position = command.index('--')
        mounts = ['--ro-bind', str(resources), '/resources/input']
        if socket is not None: mounts += ['--ro-bind', str(socket), '/resources/invoke.sock']
        return command[:position] + mounts + command[position:]

    async def _execute(self, kernel_job, resources, *, socket=None):
        receipt = await self.kernel._run_kernel(kernel_job, self._command(kernel_job, resources, socket=socket),
                                                output_parent=kernel_job.cwd.parent)
        ref = self.store.append_record('admission-self-test-execution', receipt)
        require(receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0
                and receipt['observed_limits']['network'] == 'none', 'Actual confined self-test execution did not complete')
        return ref, receipt

    def _completed(self, job_ref, prior):
        """Read original completion only; the root ledger proves its prior claim.

        This path cannot create a new grant or effect. It uses the original
        captured profile, not current-time expiry or installed-runtime checks,
        and retains the independent consumer's full original-evidence checks.
        """
        require(isinstance(prior, dict) and set(prior) == {'result_ref'}, 'Malformed admission terminal envelope')
        validate('Ref', prior['result_ref'])
        job = ref_record(self.store, job_ref, 'admission-self-test-job')
        authority = AdmissionTestProvider(self.store, configuration_ref=job['configuration_ref'],
            execution_profile_ref=job['execution_profile_ref'], rpc=None)
        job = authority._original_job(job_ref)
        proof = ref_record(self.store, prior['result_ref'], 'admission-self-test-result')
        require(proof['job_ref'] == job_ref, 'Completed result belongs to another exact admission job')
        request = ref_record(self.store, job['admission_request_ref'], 'admission-self-test-request')
        declaration = self.store.read_record(job['declaration_ref'], contract_id='capsule-declaration')
        test = next(t for t in declaration['guarantees']['self_tests'] if t['id'] == job['test_id'])
        # The original driver catalog pins two captured programs. Reconciliation
        # reads both original blobs rather than comparing a later installation.
        driver = self.store.read_record(job['driver_ref'])
        require(set(driver) == {'_admission_driver.py', '_admission_candidate.py'}, 'Original driver closure differs')
        for ref in driver.values():
            validate('Ref', ref)
            self.store.read_blob(ref)
        from .checks.admission import verify_self_test
        verify_self_test(self.store, test, job['declaration_ref'], job['body_refs'], prior['result_ref'],
            memory_mb=request['admission_memory_mb'], configuration_ref=job['configuration_ref'],
            execution_profile_ref=job['execution_profile_ref'])
        return copy.deepcopy(prior['result_ref'])

    async def run(self, job_ref):
        validate('Ref', job_ref)
        claim = {'operation': 'admission_self_test', 'job_ref': job_ref}
        prior = self.ledger.lookup(claim)
        if prior is not None:
            return self._completed(job_ref, prior)
        job = await self._authorize(job_ref)
        key, prior = self.ledger.claim(claim)
        if prior is not None:
            return self._completed(job_ref, prior)
        if os.name != 'posix' or os.geteuid() != 0 or not isinstance(self.kernel, RestrictedExecutor):
            raise ResearchError('ENVIRONMENT_BLOCKED', 'Protected Linux admission broker required')
        if self.kernel.prerequisites():
            raise ResearchError('ENVIRONMENT_BLOCKED', 'Actual admission kernel prerequisites unavailable')
        profile = ref_record(self.store, job['execution_profile_ref'], 'admission-execution-profile')
        if (installed_driver(self.store) != profile['driver_ref'] or job['driver_ref'] != profile['driver_ref']
                or installed_runtime(self.store) != profile['runtime_ref']):
            raise ResearchError('ENVIRONMENT_BLOCKED', 'Installed admission driver/runtime differs from the approved profile')
        declaration = self.store.read_record(job['declaration_ref'], contract_id='capsule-declaration')
        test = next(t for t in declaration['guarantees']['self_tests'] if t['id'] == job['test_id'])
        workspace = self.kernel.workspace_root.resolve(strict=True)
        require(self.root.is_absolute() and self.root.resolve().is_relative_to(workspace), 'Admission staging escapes protected workspace')
        self.root.mkdir(mode=0o711, parents=True, exist_ok=True)
        require(not self.root.is_symlink() and self.root.stat().st_uid == 0
                and not stat.S_IMODE(self.root.stat().st_mode) & 0o022, 'Admission staging custody invalid')
        base = self.root / hashlib.sha256(json_bytes(job_ref)).hexdigest()[:24]
        base.mkdir(mode=0o711)
        deadline = time.monotonic() + min(job['limits']['time_s'], expiry(job['expires_at']) - time.time())
        candidates, candidate_values, sequence, candidate_started = [], {}, 0, False
        def kernel_job(role, argv):
            nonlocal sequence
            sequence += 1
            directory = base / (role + '-' + str(sequence)); directory.mkdir(mode=0o711)
            work = directory / 'work'; work.mkdir(mode=0o700); os.chown(work, 10002, 10002)
            return AdmissionKernelJob('admission-' + uuid.uuid4().hex, job['id'] + ':' + role, job_ref, work,
                max(0, deadline - time.monotonic()), job['limits']['memory_mb'], job['limits']['pids_max'], tuple(argv))
        async def invoke(payload):
            nonlocal candidate_started
            await self._authorize(job_ref)
            require(isinstance(payload, dict) and set(payload) == {'inputs'} and not candidate_started,
                    'Only one exact job-scoped candidate invocation is permitted')
            candidate_started = True
            input_ref = self.store.put_blob(json_bytes(payload['inputs']))
            resources = base / 'candidate-input'; resources.mkdir(mode=0o755)
            for name, ref in job['body_refs'].items(): self._write(resources / 'body', name, self.store.read_blob(ref))
            self._write(resources, 'candidate.py', Path(__file__).with_name('_admission_candidate.py').read_bytes())
            manifest = {'carrier': declaration['identity']['carrier']['ref'], 'inputs': payload['inputs'],
                        'failure_modes': [m['reason_code'] for m in declaration['guarantees'].get('failure_modes', [])]}
            self._write(resources, 'manifest.json', json_bytes(manifest))
            child = kernel_job('candidate', ['/usr/local/bin/python3', '-I', '-S', '/resources/input/candidate.py'])
            receipt_ref, receipt = await self._execute(child, resources)
            reported = json.loads(self.store.read_blob(receipt['stdout_ref']))
            require(set(reported) == {'end_state', 'outputs', 'reason_code'}, 'Malformed actual candidate result')
            outputs = reported['outputs']; require(isinstance(outputs, dict), 'Candidate output inventory invalid')
            if reported['end_state'] == 'pass':
                specs = {p['name']: p for p in declaration['ports']['outputs']}
                require(not set(outputs) - set(specs) and all(not p['required'] or name in outputs for name,p in specs.items()),
                        'Candidate output ports differ')
                require(reported['reason_code'] is None, 'Pass cannot report a failure reason')
                for name,value in outputs.items(): validate(specs[name]['schema_ref'], value)
            else:
                require(reported['end_state'] in manifest['failure_modes'] and not outputs
                        and reported['reason_code'] == reported['end_state'], 'Candidate failure state is not declared')
            output_refs = {name: self.store.put_blob(json_bytes(outputs[name])) for name in sorted(outputs)}
            captured = self.store.append_record('admission-self-test-candidate-execution', {
                'schema': 'ai4r-admission-self-test-candidate-execution:1', 'id': 'admission-candidate:' + uuid.uuid4().hex,
                'job_ref': job_ref, 'declaration_ref': job['declaration_ref'], 'body_refs': job['body_refs'],
                'input_ref': input_ref, 'execution_receipt_ref': receipt_ref, 'end_state': reported['end_state'],
                'output_refs': output_refs, 'reason_code': reported['reason_code'], 'recorded_at': timestamp()})
            candidates.append(captured)
            captured_record = ref_record(self.store, captured, 'admission-self-test-candidate-execution')
            response = {**reported, 'candidate_call_id': captured_record['id']}
            candidate_values[captured_record['id']] = (response, output_refs)
            return response
        capability, session = secrets.token_urlsafe(32), uuid.uuid4().hex
        server = PrivateRPCServer(base / 'ipc' / 'invoke.sock', protocol='ai4r-admission-invoke:1', session_id=session,
            capability=capability, handlers={'invoke': invoke}, allowed_uids={10002}, socket_mode=0o660,
            directory_mode=0o710, group_id=10002)
        try:
            await server.start()
            resources = base / 'driver-input'; resources.mkdir(mode=0o755)
            self._write(resources, 'run.py', Path(__file__).with_name('_admission_driver.py').read_bytes())
            self._write(resources, 'test', self.store.read_blob(job['test_ref']))
            self._write(resources, 'manifest.json', json_bytes({'kind': test['kind'], 'protocol': 'ai4r-admission-invoke:1',
                'session_id': session, 'capability': capability}), private=True)
            driver = kernel_job('driver', ['/usr/local/bin/python3', '-I', '-S', '/resources/input/run.py'])
            receipt_ref, receipt = await self._execute(driver, resources, socket=server.path)
            reported = json.loads(self.store.read_blob(receipt['stdout_ref']))
            require(len(candidates) == 1 and isinstance(reported, dict)
                    and reported.get('candidate_call_id') in candidate_values, 'Driver did not invoke the actual candidate')
            actual, output_refs = candidate_values[reported['candidate_call_id']]
            require(reported == actual and reported['end_state'] == test['expects'], 'Driver assertion/end state differs from actual candidate')
            result = self.store.append_record('admission-self-test-result', {
                'schema': 'ai4r-admission-self-test-result:1', 'id': 'admission-result:' + uuid.uuid4().hex,
                **{k: job[k] for k in ('declaration_ref','test_id','test_ref','body_refs','configuration_ref')},
                'job_ref': job_ref, 'execution_receipt_ref': receipt_ref, 'end_state': reported['end_state'],
                'output_refs': list(output_refs.values()), 'reason_code': reported['reason_code'],
                'candidate_execution_refs': candidates, 'driver_execution_ref': receipt_ref, 'model_call_refs': [],
                'recorded_at': timestamp()})
            self.ledger.complete(key, {'result_ref': result})
            ref_record(self.store, result, 'admission-self-test-result')
            return result
        except BaseException as error:
            self.store.append_record('admission-self-test-failure', {'id': 'admission-failure:' + uuid.uuid4().hex,
                'job_ref': job_ref, 'candidate_execution_refs': candidates, 'reason': getattr(error, 'code', type(error).__name__),
                'recorded_at': timestamp()})
            raise
        finally:
            await server.close()
