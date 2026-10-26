"""Protected scientific resource preparation and exact invocation-bound jobs.

Profiles are host inputs admitted with the resource catalog. Capsules receive
neither this factory nor authority to choose commands, approval pins or roots.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import sys
import time
import uuid
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .contracts import ResearchError, contract_schema, validate
from .environment import inspect_wheel, normalize_name, validate_lock, verify_inventory
from .executor import ExecutionJob, InvocationBinding, PreparedEnvironment, ReadonlyMount
from .inspection import safe_named_path
from .process_evidence import validate_process_evidence
from .state import json_bytes, utc_now


def _new_root_traversable(path, *, mode=0o711):
    """Create one new broker directory with traversal despite umask 077.

    Existing paths are never adopted or repaired. The opened inode must still
    have root custody before a non-writable search permission is granted.
    """
    if mode not in {0o711, 0o555}:
        raise ResearchError('auth', 'Scientific directory mode is not authorized')
    path.mkdir(mode=mode)
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ResearchError('auth', 'New scientific directory lacks broker custody')
        os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)


def allocate_science_workspace(root, binding, sequence, role, *, uid=10002, gid=10002):
    """Broker-only finite allocator; callers never choose a filesystem path."""
    if os.name != 'posix' or os.geteuid() != 0 or not isinstance(binding, InvocationBinding):
        raise ResearchError('unavailable', 'Protected root broker allocation is required')
    if type(sequence) is not int or sequence < 1 or role not in {'baseline', 'treatment', 'builder_test'}:
        raise ResearchError('validation', 'Invalid scientific allocation identity')
    supplied = Path(root)
    if supplied.is_symlink():
        raise ResearchError('validation', 'Scientific workspace root cannot be a symlink')
    root = supplied.resolve(); root.mkdir(parents=True, exist_ok=True, mode=0o711)
    if root.stat().st_uid != 0 or stat.S_IMODE(root.stat().st_mode) & 0o022:
        raise ResearchError('auth', 'Scientific workspace root lacks broker custody')
    key = hashlib.sha256(json_bytes({'contract_ref': binding.contract_ref, 'invocation_id': binding.invocation_id,
                                    'sequence': sequence, 'role': role})).hexdigest()
    parent = root / key
    _new_root_traversable(parent)  # existing/replayed/foreign allocation is refused
    work = parent / 'work'; work.mkdir(mode=0o700)
    reserved = work / '.venv'; _new_root_traversable(reserved, mode=0o555)
    os.chown(work, uid, gid)
    return work


@dataclass(frozen=True)
class ApprovedEnvironment:
    lock_ref: Mapping
    approval_ref: Mapping
    platform_fact: tuple[str, str, str]
    wheel_filenames: Mapping[str, str]


@dataclass(frozen=True)
class ScienceProfile:
    asset_root: Path
    environment_root: Path
    memory_mb: int
    pids_max: int
    run_timeout_s: float
    provision_timeout_s: float
    baseline_arguments: tuple[str, ...]
    treatment_arguments: tuple[str, ...]
    uv_path: Path
    python_path: Path


@dataclass(frozen=True)
class ProvisioningJob:
    """Finite trusted installer job; the broker owns OS containment and custody."""
    job_id: str
    contract_ref: Mapping
    invocation_id: str
    environment: Path
    wheelhouse: Path
    requirements: Path
    requirements_ref: Mapping
    wheel_refs: Mapping[str, Mapping]
    uv_path: Path
    python_path: Path
    timeout_s: float
    memory_mb: int
    pids_max: int

    @property
    def argv(self):
        return (str(self.uv_path), 'pip', 'install', '--python', '/environment/bin/python',
                '--offline', '--no-index', '--no-deps', '--only-binary', ':all:', '--require-hashes',
                '--find-links', '/wheelhouse', '--requirements', '/resources/requirements.txt')


def _binding(contract, binding):
    if not isinstance(binding, InvocationBinding) or binding.contract != contract or not binding.invocation_id:
        raise ResearchError('auth', 'A protected exact invocation binding is required')


def _input_ref(contract, name):
    rows = [row for row in contract['inputs'] if row['name'] == name]
    if len(rows) != 1 or len(rows[0]['artifact_refs']) != 1:
        raise ResearchError('validation', 'One exact named scientific input is required')
    return rows[0]['artifact_refs'][0]


def _hash_tree(root):
    result = {}
    for item in sorted(root.rglob('*')):
        if item.is_symlink():
            # Python's venv executable links may only point to the explicitly
            # configured interpreter. Other symlinks are rejected by verifier.
            result[item.relative_to(root).as_posix()] = {'link': os.readlink(item)}
        elif item.is_file():
            result[item.relative_to(root).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


class ScienceExecutionAdapter:
    def __init__(self, store, profile: ScienceProfile, *, approved_environments,
                 workspace_allocator: Callable, hardware_capture: Callable, provision_runner: Callable | None = None,
                 scorer=None):
        for value in [profile.memory_mb, profile.pids_max, profile.run_timeout_s, profile.provision_timeout_s]:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError('Explicit positive protected scientific limits are required')
        self.store, self.profile = store, profile
        self.approved = {entry.lock_ref['sha256']: entry for entry in approved_environments}
        self.workspace_allocator, self.hardware_capture = workspace_allocator, hardware_capture
        self.provision_runner = provision_runner
        self.scorer = scorer
        self._measurement_jobs = {}
        self._pi_last, self._pi_pending = {}, set()
        self._prepared, self._mounts, self._hardware, self._started = {}, {}, {}, {}

    def score_result(self, job, raw, *, binding):
        """Root-only post-cessation scoring; preserve original child stdout."""
        if self.scorer is None:
            return raw  # Explicit legacy v2 execution remains unchanged.
        _binding(binding.contract, binding)
        known = self._measurement_jobs.pop(job.job_id, None)
        if (known is None or known[0] != job or job.contract_ref != binding.contract_ref
                or job.invocation_id != binding.invocation_id
                or raw.get('job_id') != job.job_id or raw.get('contract_ref') != dict(job.contract_ref)
                or raw.get('invocation_id') != job.invocation_id):
            raise ResearchError('auth', 'Trusted scoring requires the original issued public-data job')
        if getattr(self.scorer,'protocol',None)=='ai4r-pi:1':
            self._pi_last[binding.invocation_id]=job.sequence
            self._pi_pending.discard(binding.invocation_id)
        if getattr(self.scorer,'protocol',None)=='ai4r-pi:1':
            return self.scorer.score(job,raw,known[1])
        if (raw.get('observed_runtime') is not True or raw.get('exit_code') != 0
                or raw.get('termination_reason') != 'completed'):
            return raw  # Failed/unknown execution supplies no successful score.
        return self.scorer.score(job, raw, known[1])

    def _remaining(self, contract, binding, cap):
        start = self._started.setdefault(binding.invocation_id, time.monotonic())
        ceiling = min(contract['subnode_limits']['time_s'], contract['bindings'][0]['limits']['time_s'])
        remaining = min(cap, ceiling - (time.monotonic() - start))
        if remaining <= 0:
            raise ResearchError('budget_exhausted', 'Scientific invocation time is exhausted')
        return remaining

    def _approved_lock(self, contract, inputs):
        ref = _input_ref(contract, 'lock' if 'blueprint' in inputs else 'environment_lock')
        entry = self.approved.get(ref['sha256'])
        lock = inputs['lock' if 'blueprint' in inputs else 'environment_lock']
        if entry is None or dict(entry.lock_ref) != ref or dict(entry.approval_ref) != lock['approval_ref']:
            raise ResearchError('unavailable', 'Environment is absent from the protected approved catalog')
        actual = (platform.system(), platform.machine(), platform.python_version())
        if actual != tuple(entry.platform_fact):
            raise ResearchError('unavailable', 'Observed platform differs from the qualified lock platform mapping')
        if self.store.read_record(ref) != lock:
            raise ResearchError('validation', 'Environment bytes differ from the frozen named input')
        return entry, validate_lock(lock, self.store.read_blob, lock['platform'])

    async def _command(self, job, *, binding):
        if self.provision_runner is None:
            raise ResearchError('unavailable', 'Qualified protected provisioning broker is unavailable')
        observed = self.provision_runner(job, binding=binding)
        if asyncio.iscoroutine(observed): observed = await observed
        self.store.append_record('provisioning_execution', observed)
        refs = [observed['stdout_ref'], observed['stderr_ref']]
        for ref in refs: self.store.read_blob(ref)
        limits = observed['observed_limits']
        if observed.get('execution_mode') == 'm1_app_process':
            if not validate_process_evidence(self.store, observed, expected_uid=10002, expected_gid=10002,
                    contract_ref=dict(binding.contract_ref), invocation_id=binding.invocation_id,
                    job_id=job.job_id, expected_runtime_ref=getattr(self, 'runtime_ref', None)):
                raise ResearchError('unavailable', 'M1 provisioning process evidence is not joined to its frozen runtime')
            if observed['exit_code'] != 0 or observed['termination_reason'] != 'completed':
                raise ResearchError('provisioning_failed', 'Trusted offline provisioning failed', {'evidence_refs': refs})
            return refs
        proof = self.store.read_record(limits['isolation_probe_ref'])
        if (observed.get('contract_ref') != binding.contract_ref or observed.get('invocation_id') != binding.invocation_id
                or observed.get('observed_runtime') is not True or proof.get('ready') is not True
                or proof.get('executor_uid') != 10002 or proof.get('executor_gid') != 10002
                or int(proof.get('cap_effective', '-1'), 16) != 0 or proof.get('no_new_privileges') != '1'
                or limits.get('network') != 'none' or proof.get('network') != 'none'
                or not 0 < int(limits['memory_max']) <= job.memory_mb * 1024 * 1024
                or not 0 < int(limits['pids_max']) <= job.pids_max):
            raise ResearchError('unavailable', 'Actual provisioning containment was not proved', {'evidence_refs': refs})
        if observed['exit_code'] != 0 or observed['termination_reason'] != 'completed':
            raise ResearchError('provisioning_failed', 'Trusted offline provisioning failed', {'evidence_refs': refs})
        return refs

    async def provisioner(self, contract, inputs, lock_pins, *, binding, builder_manifest_ref=None):
        _binding(contract, binding)
        if os.name != 'posix' or os.geteuid() != 0:
            raise ResearchError('unavailable', 'Protected Linux broker provisioning is required')
        entry, pins = self._approved_lock(contract, inputs)
        lock_port = 'lock' if builder_manifest_ref is not None else 'environment_lock'
        if builder_manifest_ref is not None:
            declaration = self.store.read_record(contract['bindings'][0]['declaration_ref'])
            if declaration['identity']['name'] != 'research.builder' or declaration['identity']['version_label'] not in {'m1-13','m1-14','m1-15','m1-16','m1-17','m1-18'}:
                raise ResearchError('auth', 'Development provisioning requires the exact Builder release')
        if pins != dict(lock_pins):
            raise ResearchError('validation', 'Provisioner pins differ from exact complete lock')
        if binding.invocation_id in self._prepared:
            raise ResearchError('conflict', 'Provisioning is never silently replayed')
        supplied_root = self.profile.environment_root
        if supplied_root.is_symlink():
            raise ResearchError('validation', 'Prepared environment root is unsafe')
        root = supplied_root.resolve()
        root.mkdir(parents=True, exist_ok=True, mode=0o711)
        owned = root / ('env-' + uuid.uuid4().hex)
        _new_root_traversable(owned)
        environment, wheelhouse = owned / 'venv', owned / 'wheelhouse'
        wheelhouse.mkdir(mode=0o700)
        effects, started = [], time.monotonic()
        active_effect = 'create_venv'
        active_target = '/workspace/poc/.venv'
        receipt = {'schema_version': '1.0.0', 'id': 'provisioning_receipt',
            'environment_lock_ref': _input_ref(contract, lock_port), 'poc_manifest_ref': builder_manifest_ref if builder_manifest_ref is not None else _input_ref(contract, 'poc_manifest'),
            'status': 'failed', 'python_version': platform.python_version(), 'venv_path': '/workspace/poc/.venv',
            'runner_user': 'executor:10002', 'packages': [], 'network_policy_used': 'none',
            'network_allowlist': [], 'unlisted_network_requests': 0,
            'effects': effects, 'limits': {'wall_s_limit': self._remaining(contract, binding, self.profile.provision_timeout_s), 'wall_s_used': 0}}
        try:
            # Stdlib venv construction does not import/install candidate wheels.
            if self.profile.python_path.resolve() != Path(sys._base_executable).resolve():
                raise ResearchError('unavailable', 'Protected interpreter differs from the prepared platform')
            venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
            effects.append({'op': 'create_venv', 'target': active_target, 'outcome': 'ok'})
            hashed, wheel_refs = [], {}
            for ref in inputs[lock_port]['package_refs']:
                raw = self.store.read_blob(ref); name, version, _ = inspect_wheel(raw)
                filename = entry.wheel_filenames.get(ref['sha256'])
                if not filename or not safe_named_path(filename) or '/' in filename or not filename.endswith('.whl'):
                    raise ResearchError('unavailable', 'Approved wheel filename/tag identity is unavailable')
                from packaging.utils import parse_wheel_filename
                wheel_name, wheel_version, _, tags = parse_wheel_filename(filename)
                from packaging.tags import sys_tags
                if normalize_name(wheel_name) != name or str(wheel_version) != version or not set(tags).intersection(sys_tags()):
                    raise ResearchError('unavailable', 'Approved wheel is incompatible with the observed runtime')
                (wheelhouse / filename).write_bytes(raw)
                (wheelhouse / filename).chmod(0o444)
                wheel_refs[filename] = dict(ref)
                hashed.append(name + '==' + version + ' --hash=sha256:' + ref['sha256'])
            if pins:
                wheelhouse.chmod(0o555)
                active_effect, active_target = 'install_package', '/workspace/poc/.venv'
                requirements = owned / 'requirements.txt'
                requirements.write_text('\n'.join(hashed) + '\n', encoding='utf-8')
                requirements.chmod(0o444)
                requirements_ref = self.store.put_blob(requirements.read_bytes(), media_type='text/plain')
                job = ProvisioningJob('provision-' + uuid.uuid4().hex, binding.contract_ref, binding.invocation_id,
                    environment, wheelhouse, requirements, requirements_ref, wheel_refs, self.profile.uv_path, self.profile.python_path,
                    self._remaining(contract, binding, self.profile.provision_timeout_s),
                    min(self.profile.memory_mb, contract['subnode_limits']['memory_mb'], contract['bindings'][0]['limits']['memory_mb']),
                    self.profile.pids_max)
                await self._command(job, binding=binding)
            # Read distribution metadata from the trusted parent process. Never
            # run the newly prepared interpreter or execute an installed .pth.
            sites = list((environment / 'lib').glob('python*/site-packages'))
            packages = [{'name': normalize_name(dist.metadata['Name']), 'version': dist.version}
                        for dist in importlib.metadata.distributions(path=[str(site) for site in sites])]
            packages.sort(key=lambda row: row['name']); verify_inventory(pins, packages)
            installed = [{'name': row['name'], 'locked_version': pins[row['name']],
                          'installed_version': row['version'], 'hash_verified': True} for row in packages]
            effects.extend({'op': 'install_package', 'target': row['name'] + '==' + row['version'],
                            'outcome': 'ok'} for row in packages)
            tree = _hash_tree(environment)
            for relative, value in tree.items():
                if isinstance(value, dict):
                    destination = (environment / relative).resolve()
                    # Venv's internal lib64 -> lib link stays inside the frozen
                    # tree. External executable links name only pinned Python.
                    if not destination.is_relative_to(environment.resolve()) and destination != self.profile.python_path.resolve():
                        raise ResearchError('validation', 'Unapproved environment symlink')
            prepared = PreparedEnvironment(environment, _input_ref(contract, lock_port))
            for item in environment.rglob('*'):
                if not item.is_symlink():
                    item.chmod(0o555 if item.is_dir() or os.access(item, os.X_OK) else 0o444)
            environment.chmod(0o555)
            self._prepared[binding.invocation_id] = (prepared, tree, pins)
            receipt.update(status='succeeded', packages=installed)
        except BaseException as exc:
            effects.append({'op': active_effect, 'target': active_target, 'outcome': 'failed'})
            receipt['limits']['wall_s_used'] = time.monotonic() - started
            validate('provisioning-receipt', receipt)
            self.store.append_record('provisioning_failure', {'run_id': contract['run_id'], 'contract_ref': binding.contract_ref,
                'invocation_id': binding.invocation_id, 'reason': getattr(exc, 'code', type(exc).__name__), 'receipt': receipt})
            raise
        finally:
            receipt['limits']['wall_s_used'] = time.monotonic() - started
        validate('provisioning-receipt', receipt)
        return receipt

    def environment_verifier(self, prepared):
        matches = [entry for entry in self._prepared.values() if entry[0] == prepared]
        if len(matches) != 1 or _hash_tree(prepared.source) != matches[0][1]:
            raise ResearchError('validation', 'Prepared environment bytes/inventory changed')

    def _resource(self, value, ref, target):
        validate('resource-snapshot', value)
        if value['availability'] != 'available' or self.store.read_record(ref) != value:
            raise ResearchError('unavailable', 'Exact captured resource is unavailable')
        directory = self.profile.asset_root.resolve() / ref['sha256']
        expected = {file['path']: file['artifact_ref'] for file in value['files']}
        if len(expected) != len(value['files']) or any(not safe_named_path(path) for path in expected):
            raise ResearchError('validation', 'Unsafe or duplicate resource path')
        if not directory.exists():
            directory.mkdir(parents=True, mode=0o755)
            for path, artifact_ref in expected.items():
                item = directory / path; item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(self.store.read_blob(artifact_ref)); item.chmod(0o444)
            # Only newly staged approved bytes are exposed to the executor.
            # mkdir's mode is narrowed by production umask 077, including every
            # intermediate directory; restore the intended read/traverse modes
            # before publishing this snapshot root as a read-only mount.
            for item in directory.rglob('*'):
                if item.is_dir():
                    item.chmod(0o755)
            directory.chmod(0o755)
        mount = ReadonlyMount(directory, target, ref)
        self._mounts[(str(directory), ref['sha256'])] = expected
        self.verify_mount(mount)
        return mount

    def verify_mount(self, mount):
        expected = self._mounts.get((str(mount.source), mount.ref['sha256']))
        if expected is None or mount.source.is_symlink() or not mount.source.resolve().is_relative_to(self.profile.asset_root.resolve()):
            raise ResearchError('auth', 'Resource mount is outside its protected prepared inventory')
        directories = [mount.source, *(item for item in mount.source.rglob('*') if item.is_dir())]
        for directory in directories:
            metadata = directory.lstat()
            if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0
                    or stat.S_IMODE(metadata.st_mode) != 0o755):
                raise ResearchError('validation', 'Prepared resource directory custody/mode changed')
        actual = _hash_tree(mount.source)
        if actual != {name: ref['sha256'] for name, ref in expected.items()}:
            raise ResearchError('validation', 'Prepared resource bytes changed')

    async def hardware_probe(self, contract, *, binding):
        _binding(contract, binding)
        if binding.invocation_id in self._hardware:
            return dict(self._hardware[binding.invocation_id])
        if self.hardware_capture is None:
            raise ResearchError('unavailable', 'Actual same-sandbox hardware capture is unavailable')
        prepared = self._prepared.get(binding.invocation_id)
        if prepared is None:
            raise ResearchError('unavailable', 'Hardware observation requires the exact prepared environment')
        capture = self.hardware_capture(binding, prepared_environment=prepared[0],
            timeout_s=self._remaining(contract, binding, self.profile.run_timeout_s),
            memory_mb=min(self.profile.memory_mb, contract['subnode_limits']['memory_mb'], contract['bindings'][0]['limits']['memory_mb']),
            pids_max=self.profile.pids_max)
        if asyncio.iscoroutine(capture): capture = await capture
        inventory, evidence_ref = capture['inventory'], capture['observation_ref']
        observation = self.store.read_record(evidence_ref)
        if (observation.get('contract_ref') != binding.contract_ref or observation.get('invocation_id') != binding.invocation_id
                or observation.get('observed_runtime') is not True or observation.get('inventory') != inventory):
            raise ResearchError('unavailable', 'Hardware capture does not prove this actual sandbox')
        import jsonschema
        schema = contract_schema('execution-receipt')
        jsonschema.Draft202012Validator({'$ref': '#/$defs/HardwareInventory', '$defs': schema['$defs']}).validate(inventory)
        if inventory['gpu_count'] > 0 and any(inventory[key] is None for key in ['gpu_model', 'gpu_memory_mb', 'driver_version', 'cuda_version']):
            raise ResearchError('unavailable', 'Observed GPU facts are incomplete')
        self._hardware[binding.invocation_id] = dict(inventory)
        return dict(inventory)

    async def job_factory(self, contract, inputs, *, binding, role, repeat_index, seed, sequence, subject_ref, hardware_ref, case_id=None):
        _binding(contract, binding)
        blueprint = inputs['hypothesis_blueprint']; manifest = inputs['poc_manifest']
        pi = getattr(self.scorer, 'protocol', None) == 'ai4r-pi:1'
        case_public = None
        if pi:
            from .pi_protocol import validate_pi_request
            declaration=self.store.read_record(contract['bindings'][0]['declaration_ref'])
            if declaration['identity']['name']!='research.benchmark' or declaration['identity']['version_label']not in {'pi-m1-1','pi-m1-2','pi-m1-3','pi-m1-4'}:
                raise ResearchError('auth','Pi requires its separately admitted immutable Benchmark release')
            if (blueprint['repeat_count'] != 5 or _input_ref(contract,'validation_resource') != self.scorer.profile['public_dataset_ref']):
                raise ResearchError('auth','Pi measurements require the exact frozen host task')
            if (binding.invocation_id in self._pi_pending or sequence != self._pi_last.get(binding.invocation_id,0)+1
                    or _input_ref(contract,'baseline_resource') != blueprint['baseline_identity']['resource_ref']
                    or _input_ref(contract,'validation_resource') != blueprint['validation_resource_ref']
                    or _input_ref(contract,'poc_artifact_bundle') != manifest['archive_ref']
                    or manifest['blueprint_ref'] != _input_ref(contract,'hypothesis_blueprint')):
                raise ResearchError('auth','Pi requires original accepted inputs and completed baseline-first sequence')
            validate_pi_request(self.store.read_blob(inputs['validation_resource']['files'][0]['artifact_ref']))
            digits = self.scorer.digits_for(case_id)
            if case_id in ('pi-10000','pi-100000'):
                expected_sequence = (0 if case_id=='pi-10000' else 10) + (0 if role=='baseline' else 5) + repeat_index + 1
                valid_repeat = type(repeat_index) is int and 0 <= repeat_index < 5
            else:
                expected_sequence = (20 + int(case_id[-1]) if case_id.startswith('pi-unseen-') else
                    24 + ('pi-boundary-0','pi-boundary-1','pi-boundary-2','pi-boundary-17').index(case_id))
                valid_repeat = repeat_index == 0 and role == 'treatment'
            case_public = {'case_id':case_id,'digits':digits}
        else:
            if case_id is not None:
                raise ResearchError('auth','Pi case selection is unavailable in the classification host profile')
            expected_sequence = repeat_index + 1 + (blueprint['repeat_count'] if role == 'treatment' else 0)
            valid_repeat = type(repeat_index) is int and 0 <= repeat_index < blueprint['repeat_count']
        expected_subject = blueprint['baseline_identity']['resource_ref'] if role == 'baseline' else manifest['archive_ref']
        if (role not in {'baseline', 'treatment'} or not valid_repeat
                or sequence != expected_sequence or seed != blueprint['seed'] or subject_ref != expected_subject):
            raise ResearchError('validation', 'Job selection differs from frozen protocol')
        prepared = self._prepared.get(binding.invocation_id)
        inventory = self._hardware.get(binding.invocation_id)
        if prepared is None or inventory is None or self.store.read_blob(hardware_ref) != json_bytes(inventory):
            raise ResearchError('unavailable', 'Exact prepared environment and observed hardware are required')
        self.environment_verifier(prepared[0])
        baseline = self._resource(inputs['baseline_resource'], _input_ref(contract, 'baseline_resource'), '/resources/baseline')
        validation = self._resource(inputs['validation_resource'], _input_ref(contract, 'validation_resource'), '/resources/validation')
        if pi:
            # One host-selected request replaces the public precision. Neither
            # reference answers nor their private directory are mounted.
            public = copy.deepcopy(inputs['validation_resource'])
            request = self.store.put_blob(json_bytes({'schema':'ai4r-pi-cases:1','digits':digits}))
            public.update(id='pi-case-'+case_id,revision=request['sha256'])
            public['files'] = [dict(public['files'][0],artifact_ref=request)]
            public_ref = self.store.put_record('resource-snapshot',public)
            validation = self._resource(public,public_ref,'/resources/validation')
            from .pi_protocol import inspect_pi_bundle
        elif self.scorer is not None:
            from .checks.prediction_bundle import inspect_bundle
        else:
            from .checks.research import inspect_bundle
        bundle = self.store.read_blob(manifest['archive_ref'])
        protocol = {'output_protocol': 'ai4r-predictions:1'} if self.scorer is not None and not pi else {}
        checked = inspect_pi_bundle(bundle,prepared[2]) if pi else inspect_bundle(bundle, [metric['metric_id'] for metric in blueprint['metrics']], prepared[2], **protocol)
        poc = {'schema_version': '1.0.0', 'id': 'prepared_poc', 'kind': 'accepted POC', 'origin': 'accepted POC archive',
               'revision': manifest['archive_ref']['sha256'], 'files': [{'path': name, 'artifact_ref': self.store.put_blob(raw),
               'media_type': 'text/plain', 'audience': 'researcher'} for name, raw in checked['files'].items()],
               'access': 'read-only', 'license': 'not stated in accepted POC manifest', 'availability': 'available', 'environment_ref': blueprint['environment_ref']}
        poc_ref = self.store.put_record('resource-snapshot', poc)
        treatment = self._resource(poc, poc_ref, '/resources/poc')
        entry = blueprint['baseline_identity']['entry_point']
        if not safe_named_path(entry) or entry not in {file['path'] for file in inputs['baseline_resource']['files']}:
            raise ResearchError('validation', 'Baseline entry point is absent from exact resource')
        replacements = {'entry_point': '/resources/baseline/' + entry, 'seed': str(seed), 'role': role,
                        'repeat_index': str(repeat_index), 'validation_path': '/resources/validation'}
        template = self.profile.baseline_arguments if role == 'baseline' else self.profile.treatment_arguments
        try: arguments = tuple(value.format_map(replacements) for value in template)
        except (KeyError, ValueError) as exc: raise ResearchError('unavailable', 'Qualified entry-point adapter is unavailable') from exc
        script = '/resources/baseline/' + entry if role == 'baseline' else '/resources/poc/run_benchmark.py'
        argv=('/environment/bin/python',script,*arguments)
        if pi and case_id not in ('pi-10000','pi-100000'):
            # Independent post-submission cases exercise the declared function
            # directly, so a harness cannot conceal an inert interface.
            runner=('import sys,json;from pathlib import Path;sys.path.insert(0,"/resources/poc");'
                    'from poc_patch import approximate_pi;'
                    'n=json.loads(Path("/resources/validation/data.json").read_text())["digits"];'
                    'print(json.dumps({"digits":n,"decimal":approximate_pi(n)}))')
            argv=('/environment/bin/python','-c',runner)
        cwd = self.workspace_allocator(binding, sequence, role)
        if asyncio.iscoroutine(cwd): cwd = await cwd
        memory = min(self.profile.memory_mb, contract['subnode_limits']['memory_mb'], contract['bindings'][0]['limits']['memory_mb'])
        job = ExecutionJob(job_id='science-' + uuid.uuid4().hex, invocation_id=binding.invocation_id,
            contract_ref=binding.contract_ref, run_id=contract['run_id'], node_id=contract['node_id'], attempt_id=contract['attempt_id'],
            sequence=sequence, role=role, repeat_index=repeat_index, seed=seed,
            argv=argv, cwd=Path(cwd),
            timeout_s=self._remaining(contract, binding, min(30,self.profile.run_timeout_s) if pi else self.profile.run_timeout_s), memory_mb=memory,
            pids_max=min(64,self.profile.pids_max) if pi else self.profile.pids_max, baseline_ref=baseline.ref, validation_ref=validation.ref,
            environment_ref=prepared[0].ref, subject_ref=subject_ref, hardware_ref=hardware_ref,
            readonly_mounts=(baseline, validation, treatment), environment=prepared[0],
            output_limit_bytes=1048576 if pi else None)
        if self.scorer is not None:
            self._measurement_jobs[job.job_id] = (copy.deepcopy(job), case_public if pi else copy.deepcopy(inputs['validation_resource']))
            if pi:self._pi_pending.add(binding.invocation_id)
        return job
