"""Ordinary, serialized M1 app-container jobs; no namespace/cgroup claims."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import stat
import sys
import tempfile
import time

from .executor import ExecutorBlocked, _await, _utc

MODE = 'm1_app_process'


def process_members(pgid):
    result = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == pgid and fields[0] != 'Z':
                result.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return result


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _link(source, target):
    if target.exists() or target.is_symlink():
        raise ExecutorBlocked('M1_PROCESS_RESOURCE_ALREADY_IN_USE')
    target.symlink_to(source, target_is_directory=source.is_dir())


def prepare_command(executor, job):
    work = executor._workspace(job.cwd)
    argv = list(job.argv)
    if not argv or argv[0] not in {'/usr/local/bin/python3', '/usr/local/bin/python3.12', '/environment/bin/python'}:
        raise ExecutorBlocked('EXECUTABLE_NOT_AUTHORIZED')
    # Reuse exact captured-resource and prepared-environment verifiers.
    executor._mount_arguments(job.readonly_mounts)
    if job.environment is not None:
        if executor.environment_verifier is None or job.environment.ref != job.environment_ref:
            raise ExecutorBlocked('PREPARED_ENVIRONMENT_UNVERIFIED')
        executor.environment_verifier(job.environment)
        argv = [str(job.environment.source)+arg[len('/environment'):] if arg.startswith('/environment/') else arg for arg in argv]
        reserved = work / '.venv'
        if reserved.is_dir() and not reserved.is_symlink() and not any(reserved.iterdir()):
            reserved.rmdir()
        if not reserved.exists() and not reserved.is_symlink():
            reserved.symlink_to(job.environment.source, target_is_directory=True)
        if not reserved.is_symlink() or reserved.resolve() != job.environment.source.resolve():
            raise ExecutorBlocked('PREPARED_ENVIRONMENT_UNVERIFIED')
    elif argv[0].startswith('/environment/'):
        raise ExecutorBlocked('PREPARED_ENVIRONMENT_UNAVAILABLE')
    return argv


async def run(executor, job, command, *, output_parent, stdin_bytes=None,
              stdout_line_observer=None, stdout_line_limit=None):
    if executor.runtime_ref is None:
        raise ExecutorBlocked('M1_FROZEN_RUNTIME_REQUIRED')
    if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}', job.job_id)
            or type(job.memory_mb) is not int or job.memory_mb <= 0
            or type(job.pids_max) is not int or job.pids_max <= 0):
        raise ExecutorBlocked('EFFECTIVE_RESOURCE_LIMIT_INVALID')
    async with executor._process_lock:
        aliases = []
        resources = Path('/resources')
        metadata = resources.lstat()
        if resources.is_symlink() or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ExecutorBlocked('M1_PROCESS_RESOURCE_CUSTODY_REQUIRED')
        try:
            for mount in getattr(job, 'readonly_mounts', ()):
                target = resources / Path(mount.target).relative_to('/resources')
                if target.parent != resources:
                    raise ExecutorBlocked('M1_PROCESS_RESOURCE_PATH_INVALID')
                _link(Path(mount.source), target)
                aliases.append((target, Path(mount.source)))
            return await _run(executor, job, command, output_parent=output_parent,
                stdin_bytes=stdin_bytes, stdout_line_observer=stdout_line_observer,
                stdout_line_limit=stdout_line_limit)
        finally:
            for target, source in reversed(aliases):
                if not target.is_symlink() or os.readlink(target) != str(source):
                    raise ExecutorBlocked('M1_PROCESS_RESOURCE_ALIAS_CHANGED')
                target.unlink()


async def _run(executor, job, command, *, output_parent, stdin_bytes,
               stdout_line_observer, stdout_line_limit):
    limit = getattr(job, 'output_limit_bytes', None) or 1024 * 1024
    if type(limit) is not int or not 0 < limit <= 8388608:
        raise ExecutorBlocked('OUTPUT_CAPTURE_LIMIT_INVALID')
    output = output_parent / (job.job_id+'.capture')
    output.mkdir(mode=0o700)
    cwd = Path(getattr(job, 'cwd', getattr(job, 'environment', output_parent)))
    proof = {'schema': 'ai4r-m1-process:1', 'execution_mode': MODE, 'mode': MODE,
        'runtime_ref': dict(executor.runtime_ref), 'job_id': job.job_id,
        'contract_ref': dict(job.contract_ref), 'invocation_id': job.invocation_id}
    manifest = dict(uid=executor.uid, gid=executor.gid, argv=list(command), cwd=str(cwd),
        memory_mb=job.memory_mb, pids_max=job.pids_max, proof=proof,
        environment={'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'HOME': str(cwd), 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            'UV_NO_CACHE': '1', 'UV_OFFLINE': '1'})
    process = None
    gate_read, gate_write = os.pipe()
    readers = []
    proof_bytes = b''
    termination = 'completed'
    started_at, began = _utc(), time.monotonic()
    stopped = None
    def kill():
        if process is not None:
            stop_group(process)
    try:
        with tempfile.TemporaryFile(mode='w+b') as descriptor:
            descriptor.write(json.dumps(manifest).encode()); descriptor.flush(); descriptor.seek(0)
            if executor.lifecycle_observer:
                executor.lifecycle_observer('process_scope_prepared', job, output, None)
            process = await asyncio.create_subprocess_exec(sys.executable, '-I',
                str(Path(__file__).with_name('_m1_process_child.py')), str(gate_read), str(descriptor.fileno()),
                pass_fds=(gate_read, descriptor.fileno()), start_new_session=True,
                stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        os.close(gate_read); gate_read = -1
        executor.active[job.job_id] = (process, output)
        executor.owned_groups[job.job_id] = {'path': output, 'inode': output.stat().st_ino,
            'invocation_id': job.invocation_id, 'pgid': process.pid, 'execution_mode': MODE}
        if executor.lifecycle_observer:
            executor.lifecycle_observer('process_created', job, output, process.pid)
        os.write(gate_write, b'1'); os.close(gate_write); gate_write = -1
        async def capture(stream, path, *, observe=False):
            nonlocal proof_bytes, stopped
            total, pending = 0, b''
            with path.open('xb') as destination:
                if observe:
                    first = await stream.readline()
                    if first.startswith(b'AI4R_M1_PROCESS_V1 ') and len(first) <= 8192:
                        proof_bytes = first[len(b'AI4R_M1_PROCESS_V1 '):].rstrip(b'\n')
                    else:
                        pending = first
                while True:
                    chunk = pending or await stream.read(65536)
                    pending = b''
                    if not chunk:
                        break
                    remaining = max(0, limit-total)
                    destination.write(chunk[:remaining]); total += min(len(chunk), remaining)
                    if len(chunk) > remaining:
                        stopped = stopped or 'output_limit_exceeded'; kill()
                    if observe and stdout_line_observer:
                        if stdout_line_limit is not None and len(chunk) > stdout_line_limit:
                            stopped = stopped or 'event_frame_limit'; kill()
                        else:
                            for line in chunk.splitlines(keepends=True):
                                reason = await _await(stdout_line_observer(line))
                                if reason:
                                    stopped = stopped or str(reason); kill()
                destination.flush(); os.fsync(destination.fileno())
        stdout, stderr = output/'stdout', output/'stderr'
        readers = [asyncio.create_task(capture(process.stdout, stdout, observe=True)),
                   asyncio.create_task(capture(process.stderr, stderr))]
        if stdin_bytes is not None:
            try:
                process.stdin.write(stdin_bytes); await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdin.close()
        try:
            async with asyncio.timeout(max(0, job.timeout_s-(time.monotonic()-began))):
                await process.wait()
        except TimeoutError:
            termination = 'timeout'; kill(); await process.wait()
        except asyncio.CancelledError:
            termination = 'cancelled'; kill(); await process.wait()
        kill()
        async with asyncio.timeout(3):
            await asyncio.gather(*readers)
        if process_members(process.pid):
            raise ExecutorBlocked('M1_PROCESS_CLEANUP_UNCONFIRMED')
        proof_value = json.loads(proof_bytes) if proof_bytes else {}
        if not (proof_value.get('ready') is True and proof_value.get('job_id') == job.job_id
                and proof_value.get('executor_uid') == executor.uid and proof_value.get('runtime_ref') == executor.runtime_ref):
            termination = 'process_observation_failure'
        if stopped and termination == 'completed':
            termination = stopped
        proof_ref = await _await(executor.capture(proof_bytes, media_type='application/json'))
        result = {'job_id': job.job_id, 'contract_ref': dict(job.contract_ref), 'invocation_id': job.invocation_id,
            'argv': list(job.argv), 'started_at': started_at, 'ended_at': _utc(), 'wall_time_s': time.monotonic()-began,
            'timeout_s': job.timeout_s, 'exit_code': process.returncode, 'termination_reason': termination,
            'stdout_ref': await _await(executor.capture(stdout.read_bytes(), media_type='text/plain')),
            'stderr_ref': await _await(executor.capture(stderr.read_bytes(), media_type='text/plain')),
            'observed_runtime': True, 'identity': {'executor_uid': executor.uid, 'executor_gid': executor.gid},
            'runtime_ref': dict(executor.runtime_ref), 'execution_mode': MODE,
            'observed_limits': {'execution_mode': MODE, 'process_observation_ref': proof_ref,
                'network': 'inherited', 'namespaces': 'shared_app_container', 'memory_max': None, 'pids_max': None,
                'address_space_limit_bytes': job.memory_mb*1024*1024, 'uid_process_limit': job.pids_max,
                'cpu_affinity': proof_value.get('cpu_affinity'), 'process_group_cleanup': True}}
        for field in ('sequence','role','repeat_index','seed','subject_ref','hardware_ref'):
            if hasattr(job, field):
                value = getattr(job, field)
                result[field] = dict(value) if field.endswith('_ref') else value
        (output/'finished.json').write_text(json.dumps({'job_id':job.job_id,'pgid':process.pid,
            'invocation_id':job.invocation_id,'process_group_cleanup':True}))
        return result
    finally:
        kill()
        if process is not None:
            await process.wait()
        for task in readers:
            if not task.done():
                task.cancel()
        if readers:
            await asyncio.gather(*readers, return_exceptions=True)
        for fd in (gate_read, gate_write):
            if fd >= 0:
                os.close(fd)
        executor.active.pop(job.job_id, None)
