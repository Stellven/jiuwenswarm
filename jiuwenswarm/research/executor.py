"""Typed root-broker execution with UID, namespace and cgroup enforcement.

No Docker socket or privileged container is used. Missing kernel/delegation or
custody makes execution unavailable. Model code never runs as the broker UID.
Host integrations inject frozen job/resource factories, not arbitrary shell.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import os
import re
import shutil
import signal
import stat
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping


class ExecutorBlocked(RuntimeError):
    def __init__(self, reason):
        super().__init__(reason)
        self.code = "ENVIRONMENT_BLOCKED"
        self.reason = reason


@dataclass(frozen=True)
class ReadonlyMount:
    source: Path
    target: str
    ref: Mapping


@dataclass(frozen=True)
class PreparedEnvironment:
    source: Path
    ref: Mapping


@dataclass(frozen=True)
class InvocationBinding:
    contract_ref: Mapping
    invocation_id: str
    contract: Mapping
    execution_id: str | None = None


@dataclass(frozen=True)
class ExecutionJob:
    job_id: str
    invocation_id: str
    contract_ref: Mapping
    run_id: str
    node_id: str
    attempt_id: str
    sequence: int
    role: str
    repeat_index: int
    seed: int
    argv: tuple[str, ...]
    cwd: Path
    timeout_s: float
    memory_mb: int
    pids_max: int
    baseline_ref: Mapping
    validation_ref: Mapping
    environment_ref: Mapping
    subject_ref: Mapping
    hardware_ref: Mapping
    readonly_mounts: tuple[ReadonlyMount, ...] = field(default_factory=tuple)
    environment: PreparedEnvironment | None = None
    output_limit_bytes: int | None = None


@dataclass(frozen=True)
class BuilderJob:
    job_id: str
    run_id: str
    node_id: str
    attempt_id: str
    workspace: Path
    blueprint_ref: Mapping
    baseline_ref: Mapping
    validation_ref: Mapping
    environment_ref: Mapping
    credential_ref: Mapping
    timeout_s: float
    tool_limit: int
    memory_mb: int
    pids_max: int
    requested_model: str | None = None
    readonly_mounts: tuple[ReadonlyMount, ...] = field(default_factory=tuple)


async def _await(value):
    return await value if inspect.isawaitable(value) else value


def _utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RestrictedExecutor:
    """Protected broker implementation; unprivileged clients inject broker IPC.

    Factories and authorization are protected host integrations. Generated
    Python/CLI output cannot construct or change these policy objects.
    """
    def __init__(self, *, workspace_root, cgroup_root, authorize_job: Callable,
                 capture: Callable, executor_uid=10002, executor_gid=10002,
                 allowed_asset_roots=(), verify_mount=None, job_factory=None,
                 provisioner=None, hardware_probe=None, builder_collector=None,
                 builder_observer=None, environment_verifier=None, broker=None,
                 preparation_roots=(), authorize_provisioning=None, lifecycle_observer=None,
                 score_result=None, execution_mode='restricted', runtime_ref=None):
        if execution_mode not in {'restricted', 'm1_app_process'}:
            raise ExecutorBlocked('EXECUTION_MODE_INVALID')
        self.execution_mode, self.runtime_ref = execution_mode, copy.deepcopy(runtime_ref)
        self._process_lock = asyncio.Lock()
        self.process_receipt_capture = None
        self.workspace_root = Path(workspace_root).resolve()
        self.cgroup_root = Path(cgroup_root).resolve() if cgroup_root else None
        self.authorize_job, self.capture = authorize_job, capture
        self.uid, self.gid = executor_uid, executor_gid
        self.asset_roots = tuple(Path(p).resolve() for p in allowed_asset_roots)
        self.verify_mount, self.job_factory = verify_mount, job_factory
        self.provisioner, self.hardware_probe = provisioner, hardware_probe
        self.builder_collector, self.broker = builder_collector, broker
        self.builder_observer, self.environment_verifier = builder_observer, environment_verifier
        self.active = {}
        self.owned_groups = {}
        self.preparation_roots = tuple(Path(root).resolve() for root in preparation_roots)
        self.authorize_provisioning = authorize_provisioning
        self._provision_claims = set()
        self.lifecycle_observer = lifecycle_observer
        self.score_result = score_result

    def bind_invocation(self, *, contract_ref, invocation_id, contract, execution_id=None):
        if not isinstance(invocation_id, str) or not invocation_id or not isinstance(contract_ref, Mapping):
            raise ExecutorBlocked("PROTECTED_INVOCATION_BINDING_REQUIRED")
        return ExecutorInvocation(self, InvocationBinding(copy.deepcopy(contract_ref), invocation_id,
            copy.deepcopy(contract), execution_id))

    def prerequisites(self):
        reasons = []
        if os.name != "posix" or not hasattr(os, "geteuid"):
            return ["LINUX_REQUIRED"]
        if self.broker is None and os.geteuid() != 0:
            reasons.append("PROTECTED_ROOT_BROKER_UNAVAILABLE")
        if self.execution_mode == 'm1_app_process':
            if self.runtime_ref is None:
                reasons.append('M1_FROZEN_RUNTIME_REQUIRED')
            return reasons
        if not shutil.which("bwrap"):
            reasons.append("BUBBLEWRAP_UNAVAILABLE")
        if self.cgroup_root is None or not self.cgroup_root.is_dir():
            reasons.append("DELEGATED_CGROUP_UNAVAILABLE")
        else:
            for filename in ("cgroup.controllers", "cgroup.subtree_control"):
                if not (self.cgroup_root / filename).exists():
                    reasons.append("CGROUP_V2_REQUIRED")
                    break
            try:
                controls = (self.cgroup_root / "cgroup.controllers").read_text().split()
                if not {"memory", "pids"}.issubset(controls):
                    reasons.append("CGROUP_CONTROLLERS_UNAVAILABLE")
            except OSError:
                reasons.append("DELEGATED_CGROUP_UNREADABLE")
        return reasons

    def _workspace(self, path):
        candidate = Path(path)
        if candidate.is_symlink():
            raise ExecutorBlocked("WORKSPACE_SYMLINK_DENIED")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(self.workspace_root) or resolved == self.workspace_root:
            raise ExecutorBlocked("WORKSPACE_SCOPE_DENIED")
        parent = candidate
        while parent != self.workspace_root and parent.is_relative_to(self.workspace_root):
            if parent.is_symlink():
                raise ExecutorBlocked("WORKSPACE_SYMLINK_DENIED")
            parent = parent.parent
        if os.name == "posix":
            if resolved.stat().st_uid != self.uid:
                raise ExecutorBlocked("WORKSPACE_EXECUTOR_OWNERSHIP_REQUIRED")
            # Raw capture paths are siblings of the writable work directory.
            # Every ancestor must remain controlled by the root broker so an
            # executor cannot swap/rename that sibling into a protected path.
            parent = resolved.parent
            while parent.is_relative_to(self.workspace_root):
                custody = parent.stat()
                if custody.st_uid != 0 or stat.S_IMODE(custody.st_mode) & 0o022:
                    raise ExecutorBlocked("WORKSPACE_ANCESTOR_CUSTODY_INVALID")
                if parent == self.workspace_root:
                    break
                parent = parent.parent
        return resolved

    def _mount_arguments(self, mounts):
        result = []
        destinations = set()
        for mount in mounts:
            source = Path(mount.source).resolve(strict=True)
            if not any(source.is_relative_to(root) for root in self.asset_roots):
                raise ExecutorBlocked("RESOURCE_MOUNT_SCOPE_DENIED")
            if (not mount.target.startswith("/resources/") or ".." in Path(mount.target).parts
                    or mount.target in destinations or self.verify_mount is None):
                raise ExecutorBlocked("RESOURCE_MOUNT_INVALID")
            # Trusted captured-resource verifier checks exact files/inventory
            # against the immutable Ref. A caller-supplied hash is not proof.
            self.verify_mount(mount)
            destinations.add(mount.target)
            result.extend(["--ro-bind", str(source), mount.target])
        return result

    def _sandbox(self, job):
        if self.execution_mode == 'm1_app_process':
            from .m1_process import prepare_command
            return prepare_command(self, job)
        work = self._workspace(job.cwd)
        argv = tuple(job.argv)
        # No caller shell, package manager, arbitrary executable or escape CWD.
        if not argv or argv[0] not in {"/usr/local/bin/python3", "/usr/local/bin/python3.12", "/environment/bin/python"}:
            raise ExecutorBlocked("EXECUTABLE_NOT_AUTHORIZED")
        command = [shutil.which("bwrap"), "--unshare-all", "--unshare-user", "--die-with-parent", "--new-session", "--clearenv",
                   "--uid", str(self.uid), "--gid", str(self.gid), "--cap-drop", "ALL",
                   "--ro-bind", "/usr", "/usr", "--ro-bind", "/usr/local", "/usr/local",
                   "--ro-bind", "/lib", "/lib", "--proc", "/proc", "--dev", "/dev",
                   "--tmpfs", "/tmp", "--dir", "/resources", "--dir", "/workspace",
                   "--bind", str(work), "/workspace/poc", "--chdir", "/workspace/poc",
                   "--setenv", "PATH", "/environment/bin:/usr/local/bin:/usr/bin:/bin",
                   "--setenv", "PYTHONNOUSERSITE", "1", "--setenv", "PYTHONDONTWRITEBYTECODE", "1"]
        if Path("/lib64").exists():
            command.extend(["--ro-bind", "/lib64", "/lib64"])
        command.extend(self._mount_arguments(job.readonly_mounts))
        if job.environment is not None:
            if self.environment_verifier is None or job.environment.ref != job.environment_ref:
                raise ExecutorBlocked("PREPARED_ENVIRONMENT_UNVERIFIED")
            self.environment_verifier(job.environment)
            command.extend(["--ro-bind", str(job.environment.source), "/environment",
                            "--ro-bind", str(job.environment.source), "/workspace/poc/.venv"])
        elif argv[0] == "/environment/bin/python":
            raise ExecutorBlocked("PREPARED_ENVIRONMENT_UNAVAILABLE")
        probe = Path(__file__).with_name("_executor_probe.py").resolve()
        command.extend(["--ro-bind", str(probe), "/executor-probe.py"])
        expected = {"uid": self.uid, "gid": self.gid,
                    "parent_network_namespace": os.readlink('/proc/self/ns/net'),
                    "denied_paths": ["/var/lib/ai4r", "/var/lib/ai4r-accounts", "/run/ai4r",
                                     "/var/run/docker.sock", "/hidden-fixtures"]}
        command.extend(["--", "/usr/local/bin/python3", "-I", "/executor-probe.py",
                        json.dumps(expected, separators=(",", ":")), *argv])
        return command

    def _cgroup(self, job):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}", job.job_id):
            raise ExecutorBlocked("JOB_ID_INVALID")
        if type(job.memory_mb) is not int or job.memory_mb <= 0 or type(job.pids_max) is not int or job.pids_max <= 0:
            raise ExecutorBlocked("EFFECTIVE_RESOURCE_LIMIT_INVALID")
        group = self.cgroup_root / job.job_id
        try:
            group.mkdir(mode=0o700)  # refuse an existing/foreign job group
            (group / "memory.max").write_text(str(job.memory_mb * 1024 * 1024))
            if (group / "memory.swap.max").exists():
                (group / "memory.swap.max").write_text("0")
            (group / "pids.max").write_text(str(job.pids_max))
            if not (group / "cgroup.kill").exists():
                raise ExecutorBlocked("ATOMIC_PROCESS_TREE_KILL_UNAVAILABLE")
            self.owned_groups[job.job_id] = {'path': group, 'inode': group.stat().st_ino,
                                            'invocation_id': job.invocation_id}
            if self.lifecycle_observer is not None:
                self.lifecycle_observer('group_created',job,group,None)
        except OSError:
            raise ExecutorBlocked("CGROUP_DELEGATION_UNQUALIFIED") from None
        return group

    async def measure_job(self, contract, inputs, **selection):
        if self.job_factory is None:
            raise ExecutorBlocked("FROZEN_EXECUTION_JOB_FACTORY_UNAVAILABLE")
        job = await _await(self.job_factory(contract, inputs, **selection))
        if not isinstance(job, ExecutionJob):
            raise ExecutorBlocked("FROZEN_EXECUTION_JOB_INVALID")
        return job

    async def provision(self, contract, inputs, lock_pins):
        if self.provisioner is None:
            raise ExecutorBlocked("OFFLINE_ENVIRONMENT_PROVISIONER_UNAVAILABLE")
        return await _await(self.provisioner(contract, inputs, lock_pins))

    async def hardware_inventory(self, contract):
        if self.hardware_probe is None:
            raise ExecutorBlocked("EFFECTIVE_HARDWARE_PROBE_UNAVAILABLE")
        return await _await(self.hardware_probe(contract))

    async def collect_builder(self, contract):
        if self.builder_collector is None:
            raise ExecutorBlocked("BUILDER_OUTPUT_CUSTODY_UNAVAILABLE")
        return await _await(self.builder_collector(contract))

    @staticmethod
    async def _wait_empty(group, *, timeout_s=2):
        deadline = time.monotonic() + timeout_s
        while True:
            events = dict(line.split() for line in (group / "cgroup.events").read_text().splitlines())
            if events.get("populated") == "0" and not (group / "cgroup.procs").read_text().strip():
                return
            if time.monotonic() >= deadline:
                raise ExecutorBlocked("EXECUTOR_PROCESS_TREE_DID_NOT_EXIT")
            await asyncio.sleep(0.01)

    def _preparation_path(self, supplied):
        candidate = Path(supplied)
        if candidate.is_symlink():
            raise ExecutorBlocked('PROVISIONING_SYMLINK_DENIED')
        resolved = candidate.resolve(strict=True)
        if candidate.absolute() != resolved:
            raise ExecutorBlocked('PROVISIONING_PATH_ALIAS_DENIED')
        root = next((root for root in self.preparation_roots if resolved.is_relative_to(root) and resolved != root), None)
        if root is None:
            raise ExecutorBlocked('PROVISIONING_ROOT_DENIED')
        parent = resolved.parent
        while parent.is_relative_to(root):
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                raise ExecutorBlocked('PROVISIONING_ANCESTOR_CUSTODY_INVALID')
            if parent == root: break
            parent = parent.parent
        return resolved

    async def run_provisioning(self, job, *, binding):
        """Run only the typed frozen offline installer under the qualified kernel."""
        from .execution_jobs import ProvisioningJob
        if (not isinstance(job, ProvisioningJob) or not isinstance(binding, InvocationBinding)
                or job.contract_ref != binding.contract_ref or job.invocation_id != binding.invocation_id
                or self.authorize_provisioning is None):
            raise ExecutorBlocked('PROTECTED_PROVISIONING_BINDING_REQUIRED')
        authorized = await _await(self.authorize_provisioning(job, binding=binding))
        if authorized != job:
            raise ExecutorBlocked('PROTECTED_PROVISIONING_JOB_INVALID')
        failures = self.prerequisites()
        if failures: raise ExecutorBlocked(';'.join(failures))
        if type(job.timeout_s) not in (int, float) or not 0 < job.timeout_s <= 3600:
            raise ExecutorBlocked('EFFECTIVE_WALL_LIMIT_INVALID')
        if (Path(job.uv_path).resolve() != Path('/usr/local/bin/uv').resolve()
                or Path(job.python_path).resolve() != Path(sys._base_executable).resolve()):
            raise ExecutorBlocked('PROVISIONING_EXECUTABLE_NOT_PINNED')
        environment = self._preparation_path(job.environment)
        wheelhouse = self._preparation_path(job.wheelhouse)
        requirements = self._preparation_path(job.requirements)
        if (environment.name != 'venv' or wheelhouse.name != 'wheelhouse' or requirements.name != 'requirements.txt'
                or environment.parent != wheelhouse.parent or environment.parent != requirements.parent
                or not environment.is_dir() or not wheelhouse.is_dir() or not requirements.is_file()
                or hashlib.sha256(requirements.read_bytes()).hexdigest() != job.requirements_ref['sha256']):
            raise ExecutorBlocked('PROVISIONING_CAPTURE_IDENTITY_INVALID')
        if len(job.wheel_refs) > 500 or {p.name for p in wheelhouse.iterdir()} != set(job.wheel_refs):
            raise ExecutorBlocked('PROVISIONING_WHEEL_INVENTORY_INVALID')
        for source in (wheelhouse, requirements):
            info = source.lstat()
            if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o222:
                raise ExecutorBlocked('PROVISIONING_CAPTURE_CUSTODY_INVALID')
        for filename, ref in job.wheel_refs.items():
            if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.+-]*\.whl', filename):
                raise ExecutorBlocked('PROVISIONING_WHEEL_NAME_INVALID')
            wheel = wheelhouse / filename
            if (wheel.is_symlink() or not wheel.is_file() or wheel.stat().st_uid != 0
                    or stat.S_IMODE(wheel.stat().st_mode) & 0o222
                    or hashlib.sha256(wheel.read_bytes()).hexdigest() != ref['sha256']):
                raise ExecutorBlocked('PROVISIONING_WHEEL_BYTES_CHANGED')
        if job.job_id in self._provision_claims:
            raise ExecutorBlocked('PROVISIONING_JOB_REPLAY_DENIED')
        self._provision_claims.add(job.job_id)
        # The destination was created by the trusted provisioner. Inspect every
        # entry before ownership changes; never follow candidate symlinks.
        entries = [environment, *environment.rglob('*')]
        for entry in entries:
            info = entry.lstat()
            if info.st_uid != 0 or (not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)):
                raise ExecutorBlocked('PROVISIONING_DESTINATION_CUSTODY_INVALID')
            if entry.is_symlink():
                target = entry.resolve(strict=True)
                if not target.is_relative_to(environment) and target != Path(job.python_path).resolve():
                    raise ExecutorBlocked('PROVISIONING_DESTINATION_SYMLINK_DENIED')
        for entry in entries:
            os.chown(entry, self.uid, self.gid, follow_symlinks=False)
        if self.execution_mode == 'm1_app_process':
            replacements = {'/environment': str(environment), '/wheelhouse': str(wheelhouse),
                            '/resources/requirements.txt': str(requirements)}
            command = list(job.argv)
            for index, argument in enumerate(command):
                for prefix, target in replacements.items():
                    if argument == prefix or argument.startswith(prefix+'/'):
                        command[index] = target+argument[len(prefix):]
                        break
            return await self._run_kernel(job, command, output_parent=environment.parent)
        command = [shutil.which('bwrap'), '--unshare-all', '--unshare-user', '--die-with-parent', '--new-session', '--clearenv',
                   '--uid', str(self.uid), '--gid', str(self.gid), '--cap-drop', 'ALL',
                   '--ro-bind', '/usr', '/usr', '--ro-bind', '/usr/local', '/usr/local', '--ro-bind', '/lib', '/lib',
                   '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/resources',
                   '--bind', str(environment), '/environment', '--ro-bind', str(wheelhouse), '/wheelhouse',
                   '--ro-bind', str(requirements), '/resources/requirements.txt', '--chdir', '/environment',
                   '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
                   '--setenv', 'UV_NO_CACHE', '1', '--setenv', 'UV_OFFLINE', '1',
                   '--setenv', 'PYTHONNOUSERSITE', '1', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1']
        if Path('/lib64').exists(): command.extend(['--ro-bind', '/lib64', '/lib64'])
        probe = Path(__file__).with_name('_executor_probe.py').resolve()
        command.extend(['--ro-bind', str(probe), '/executor-probe.py', '--', '/usr/local/bin/python3', '-I', '/executor-probe.py',
            json.dumps({'uid': self.uid, 'gid': self.gid, 'parent_network_namespace': os.readlink('/proc/self/ns/net'),
                'denied_paths': ['/var/lib/ai4r', '/var/lib/ai4r-accounts', '/run/ai4r', '/var/run/docker.sock', '/hidden-fixtures']}), *job.argv])
        return await self._run_kernel(job, command, output_parent=environment.parent)

    async def run(self, job: ExecutionJob):
        job = await _await(self.authorize_job(job))
        if not isinstance(job, ExecutionJob):
            raise ExecutorBlocked("PROTECTED_EXECUTION_JOB_REQUIRED")
        if self.broker is not None:
            return await self.broker.run(job)
        failures = self.prerequisites()
        if failures:
            raise ExecutorBlocked(";".join(failures))
        if type(job.timeout_s) not in (int, float) or not 0 < job.timeout_s <= 3600:
            raise ExecutorBlocked("EFFECTIVE_WALL_LIMIT_INVALID")
        command = self._sandbox(job)
        result = await self._run_kernel(job, command, output_parent=self._workspace(job.cwd).parent)
        return {**result, 'sequence': job.sequence, 'role': job.role, 'repeat_index': job.repeat_index,
                'seed': job.seed, 'subject_ref': dict(job.subject_ref), 'hardware_ref': dict(job.hardware_ref)}

    async def _run_kernel(self, job, command, *, output_parent, stdin_bytes=None,
                          stdout_line_observer=None, stdout_line_limit=None):
        """Shared broker-only lifecycle: gate, identity drop, cgroup and proof."""
        if self.execution_mode == 'm1_app_process':
            from .m1_process import run
            result = await run(self, job, command, output_parent=output_parent, stdin_bytes=stdin_bytes,
                stdout_line_observer=stdout_line_observer, stdout_line_limit=stdout_line_limit)
            if self.process_receipt_capture is not None:
                await _await(self.process_receipt_capture(copy.deepcopy(result)))
            return result
        output_limit = getattr(job, 'output_limit_bytes', None)
        if output_limit is not None and (type(output_limit) is not int or not 0 < output_limit <= 8388608):
            raise ExecutorBlocked('OUTPUT_CAPTURE_LIMIT_INVALID')
        group = self._cgroup(job)
        gate_read, gate_write = os.pipe()
        manifest = tempfile.TemporaryFile(mode="w+b")
        manifest.write(json.dumps({"uid": self.uid, "gid": self.gid, "argv": command,
                                   "environment": {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}}).encode())
        manifest.flush(); manifest.seek(0)
        started_at, start = _utc(), time.monotonic()
        process = None
        termination = "completed"
        observation_stop = None
        output_dir = output_parent / (job.job_id + ".capture")
        output_dir.mkdir(mode=0o700)
        try:
            process = await asyncio.create_subprocess_exec(sys.executable, "-m", "jiuwenswarm.research._executor_child",
                str(gate_read), str(manifest.fileno()), pass_fds=(gate_read, manifest.fileno()),
                stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=True)
            os.close(gate_read); gate_read = -1
            self.active[job.job_id] = (process, group)
            if self.lifecycle_observer is not None:
                self.lifecycle_observer('process_created',job,group,process.pid)
            (group / "cgroup.procs").write_text(str(process.pid))
            os.write(gate_write, b"1"); os.close(gate_write); gate_write = -1

            proof_bytes = b''
            async def capture_stream(stream, path, *, observe=False):
                nonlocal proof_bytes, observation_stop
                with path.open("xb") as output:
                    captured_bytes = 0
                    def write_bounded(chunk):
                        nonlocal captured_bytes, observation_stop
                        available = len(chunk) if output_limit is None else max(0, output_limit - captured_bytes)
                        output.write(chunk[:available])
                        captured_bytes += min(len(chunk), available)
                        if len(chunk) > available and observation_stop is None:
                            observation_stop = 'output_limit_exceeded'
                            (group / 'cgroup.kill').write_text('1')
                    if observe:
                        frame = await stream.readline()
                        prefix = b'AI4R_EXECUTOR_PROBE_V1 '
                        if frame.startswith(prefix) and len(frame) <= 4096 + len(prefix) + 1:
                            proof_bytes = frame[len(prefix):].rstrip(b'\n')
                        else:
                            write_bounded(frame)
                    pending = b''
                    line_overflow = False
                    while chunk := await stream.read(65536):
                        write_bounded(chunk)
                        if observe and stdout_line_observer is not None and not line_overflow:
                            pending += chunk
                            while b'\n' in pending:
                                line, pending = pending.split(b'\n', 1)
                                reason = ('event_frame_limit' if stdout_line_limit is not None and len(line) > stdout_line_limit
                                          else await _await(stdout_line_observer(line + b'\n')))
                                if reason and observation_stop is None:
                                    observation_stop = str(reason)
                                    (group / 'cgroup.kill').write_text('1')
                            if stdout_line_limit is not None and len(pending) > stdout_line_limit:
                                observation_stop = observation_stop or 'event_frame_limit'
                                (group / 'cgroup.kill').write_text('1')
                                line_overflow, pending = True, b''
                    if observe and pending and stdout_line_observer is not None:
                        reason = await _await(stdout_line_observer(pending))
                        if reason and observation_stop is None:
                            observation_stop = str(reason)
                            (group / 'cgroup.kill').write_text('1')
                    output.flush(); os.fsync(output.fileno())

            async def send_input():
                if stdin_bytes is None:
                    return
                try:
                    process.stdin.write(stdin_bytes)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    process.stdin.close()

            stdout_path, stderr_path = output_dir / "stdout", output_dir / "stderr"
            readers = [asyncio.create_task(capture_stream(process.stdout, stdout_path, observe=True)),
                       asyncio.create_task(capture_stream(process.stderr, stderr_path))]
            writer = asyncio.create_task(send_input())
            try:
                async with asyncio.timeout(max(0, job.timeout_s - (time.monotonic() - start))):
                    await process.wait()
            except TimeoutError:
                termination = "timeout"
                (group / "cgroup.kill").write_text("1")
                await process.wait()
            except asyncio.CancelledError:
                termination = "cancelled"
                (group / "cgroup.kill").write_text("1")
                await process.wait()
            # Kill descendants even if their parent exited and left pipes open.
            (group / "cgroup.kill").write_text("1")
            await self._wait_empty(group)
            await asyncio.gather(*readers)
            await writer
            if observation_stop is not None and termination == 'completed':
                termination = observation_stop
            try:
                proof = json.loads(proof_bytes)
                if not isinstance(proof, dict) or len(proof_bytes) > 4096:
                    raise ValueError("invalid proof")
            except (ValueError, UnicodeError):
                proof = {"ready": False, "failure": "EXECUTOR_ISOLATION_OBSERVATION_UNAVAILABLE"}
            proof_ref = await _await(self.capture(proof_bytes, media_type="application/json"))
            if proof.get("ready") is not True:
                termination = "isolation_failure"
            memory_events = (group / "memory.events").read_text()
            pids_events = (group / "pids.events").read_text()
            if any(line.startswith("oom_kill ") and int(line.split()[1]) for line in memory_events.splitlines()):
                termination = "resource_limit_exceeded"
            if any(line.startswith("max ") and int(line.split()[1]) for line in pids_events.splitlines()):
                termination = "resource_limit_exceeded"
            stdout_ref = await _await(self.capture(stdout_path.read_bytes(), media_type="text/plain"))
            stderr_ref = await _await(self.capture(stderr_path.read_bytes(), media_type="text/plain"))
            return {"job_id": job.job_id, "contract_ref": dict(job.contract_ref), "invocation_id": job.invocation_id,
                    "argv": list(job.argv), "started_at": started_at, "ended_at": _utc(),
                    "wall_time_s": time.monotonic() - start, "timeout_s": job.timeout_s,
                    "exit_code": process.returncode,
                    "termination_reason": termination, "stdout_ref": stdout_ref, "stderr_ref": stderr_ref,
                    "identity": {"executor_uid": self.uid, "executor_gid": self.gid},
                    "observed_limits": {"memory_max": (group / "memory.max").read_text().strip(),
                                        "pids_max": (group / "pids.max").read_text().strip(),
                                        "network": proof.get("network"), "isolation_probe_ref": proof_ref,
                                        "cpu_affinity": proof.get('cpu_affinity')},
                    "memory_events": memory_events, "pids_events": pids_events, "observed_runtime": True}
        finally:
            if gate_read >= 0: os.close(gate_read)
            if gate_write >= 0: os.close(gate_write)
            manifest.close()
            if process is not None and process.returncode is None:
                (group / "cgroup.kill").write_text("1")
                await process.wait()
                await self._wait_empty(group)
            self.active.pop(job.job_id, None)
            # Raw files remain until the owner verifies captured evidence and
            # performs explicit bounded job cleanup. Never recursively delete.


class ExecutorInvocation:
    """Read-only binding and once-only issued jobs for one runner invocation."""
    def __init__(self, executor, binding):
        self._executor, self._binding = executor, binding
        self._issued, self._claimed = {}, set()

    def _contract(self, contract):
        if contract != self._binding.contract:
            raise ExecutorBlocked("INVOCATION_CONTRACT_MISMATCH")
        return copy.deepcopy(self._binding.contract)

    async def measure_job(self, contract, inputs, **selection):
        factory = self._executor.job_factory
        if factory is None:
            raise ExecutorBlocked("FROZEN_EXECUTION_JOB_FACTORY_UNAVAILABLE")
        job = await _await(factory(self._contract(contract), inputs, binding=copy.deepcopy(self._binding), **selection))
        if (not isinstance(job, ExecutionJob) or job.invocation_id != self._binding.invocation_id
                or job.contract_ref != self._binding.contract_ref or job.job_id in self._issued):
            raise ExecutorBlocked("FROZEN_EXECUTION_JOB_INVALID")
        self._issued[job.job_id] = copy.deepcopy(job)
        return job

    async def run(self, job):
        if not isinstance(job, ExecutionJob) or self._issued.get(job.job_id) != job:
            raise ExecutorBlocked("UNISSUED_EXECUTION_JOB")
        if job.job_id in self._claimed:
            raise ExecutorBlocked("EXECUTION_JOB_ALREADY_CLAIMED")
        self._claimed.add(job.job_id)
        raw = await self._executor.run(copy.deepcopy(job))
        # The kernel runner has drained its process/cgroup before returning.
        # An installed root scorer may append provenance, never replace stdout.
        if self._executor.score_result is not None:
            original = copy.deepcopy(raw)
            scored = await _await(self._executor.score_result(copy.deepcopy(job), copy.deepcopy(raw),
                binding=copy.deepcopy(self._binding)))
            if (type(scored) is not dict or not set(original)<=set(scored)
                    or any(scored[key] != value for key, value in original.items())
                    or set(scored)-set(original) not in (set(), {'trusted_scoring_ref'})):
                raise ExecutorBlocked('TRUSTED_SCORING_CHANGED_EXECUTION_RECEIPT')
            return scored
        return raw

    async def provision(self, contract, inputs, lock_pins):
        if self._executor.provisioner is None:
            raise ExecutorBlocked("OFFLINE_ENVIRONMENT_PROVISIONER_UNAVAILABLE")
        return await _await(self._executor.provisioner(self._contract(contract), inputs, lock_pins,
            binding=copy.deepcopy(self._binding)))

    async def hardware_inventory(self, contract):
        if self._executor.hardware_probe is None:
            raise ExecutorBlocked("EFFECTIVE_HARDWARE_PROBE_UNAVAILABLE")
        return await _await(self._executor.hardware_probe(self._contract(contract), binding=copy.deepcopy(self._binding)))

    async def collect_builder(self, contract):
        if self._executor.builder_collector is None:
            raise ExecutorBlocked("BUILDER_OUTPUT_CUSTODY_UNAVAILABLE")
        return await _await(self._executor.builder_collector(self._contract(contract), binding=copy.deepcopy(self._binding)))

    async def builder_observation(self, contract):
        if self._executor.builder_observer is None:
            raise ExecutorBlocked("BUILDER_RUNTIME_OBSERVATION_UNAVAILABLE")
        return await _await(self._executor.builder_observer(self._contract(contract), binding=copy.deepcopy(self._binding)))

    async def builder_test(self, contract, *, manifest_ref, tests_ref, ordinal):
        service = getattr(self._executor, 'builder_test_service', None)
        if service is None:
            raise ExecutorBlocked('BUILDER_TEST_SERVICE_UNAVAILABLE')
        # Native clients use the durable broker RPC. This in-process seam is
        # available only with a protected host-installed input resolver.
        resolver = getattr(self._executor, 'builder_input_resolver', None)
        if resolver is None:
            raise ExecutorBlocked('BUILDER_INPUT_RESOLVER_UNAVAILABLE')
        actual = self._contract(contract)
        return await service.test(actual, await _await(resolver(actual)), binding=copy.deepcopy(self._binding),
            manifest_ref=manifest_ref, tests_ref=tests_ref, ordinal=ordinal)

    async def builder_action(self, contract, *, action, arguments, ordinal, model_ordinal):
        service = getattr(self._executor, 'builder_agent_service', None)
        resolver = getattr(self._executor, 'builder_input_resolver', None)
        if service is None or resolver is None:
            raise ExecutorBlocked('BUILDER_AGENT_SERVICE_UNAVAILABLE')
        actual = self._contract(contract)
        return await service.action(actual, await _await(resolver(actual)), binding=copy.deepcopy(self._binding),
            action=action, arguments=arguments, ordinal=ordinal, model_ordinal=model_ordinal)
