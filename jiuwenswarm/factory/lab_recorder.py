"""Bounded stdlib Docker recorder with durable intent and independent recovery.

No dependency on the historical external collector. Input is driven by native
READY/DONE boundaries. The caller owns experiment interpretation and scoring.
"""
from __future__ import annotations

from contextlib import nullcontext
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
import uuid

from .lab_lifecycle import (QuietLease, atomic_json, docker, inspect_owned,
                            process_identity, recover_run, seal_manifest)

GATE = "import os,sys;assert sys.stdin.buffer.readline()==b'FACTORY_EXEC\\n';os.execv(sys.argv[1],sys.argv[1:])"


def host_available():
    return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                    if line.startswith('MemAvailable:')))*1024


def cgroup_path(pid):
    relative = next(line[3:] for line in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if line.startswith('0::'))
    root = Path('/sys/fs/cgroup')
    path = (root/relative.lstrip('/')).resolve(strict=True)
    if not path.is_relative_to(root) or path == root:
        raise RuntimeError('Container lacks a dedicated host cgroup')
    return path


def memory_sample(group=None, pid=None):
    mem = {k: int(v) for k, v in re.findall(r'^(MemTotal|MemAvailable|Cached|SwapFree):\s+(\d+) kB',
                                          Path('/proc/meminfo').read_text(), re.M)}
    sample = dict(monotonic_ns=time.monotonic_ns(), host_kib=mem, available_bytes=mem['MemAvailable']*1024,
                  memory_events={}, cgroup_current=None, cgroup_peak=None)
    if group:
        for name, key in [('memory.events', 'memory_events'), ('cpu.stat', 'cpu_stat')]:
            try: sample[key] = {k: int(v) for k, v in (line.split() for line in (group/name).read_text().splitlines())}
            except OSError as exc:
                if exc.errno not in (errno.ENOENT, errno.ESRCH, errno.ENODEV): raise
        try: sample['cgroup_current'] = int((group/'memory.current').read_text())
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.ESRCH, errno.ENODEV): raise
        try: sample['cgroup_peak'] = int((group/'memory.peak').read_text())
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.ESRCH, errno.ENODEV): raise
        try: sample['io_stat'] = (group/'io.stat').read_text()
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.ESRCH, errno.ENODEV): raise
    if pid:
        try:
            status = Path(f'/proc/{pid}/status').read_text()
            sample['process_memory_bytes'] = {key: int(value)*1024 for key, value in
                re.findall(r'^(VmRSS|VmHWM|VmSize):\s+(\d+) kB', status, re.M)}
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.ESRCH, errno.ENODEV, errno.EACCES, errno.EPERM): raise
        try: sample['process_io'] = {k: int(v) for k, v in re.findall(r'^(\w+): (\d+)$', Path(f'/proc/{pid}/io').read_text(), re.M)}
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.ESRCH, errno.ENODEV, errno.EACCES, errno.EPERM): raise
            sample['process_io_status'] = dict(status='not_measured', errno=exc.errno)
    return sample


class Journal:
    """Flush per chunk; target a one-second fsync cadence (scheduler dependent)."""
    def __init__(self, output):
        self.output = Path(output)
        self.files = {name: (self.output/name).open('xb') for name in
                      ('stdout.log', 'stderr.log', 'stdin-wire.log', 'samples.jsonl', 'pipe-events.jsonl')}
        self.offsets = dict(stdin=0, stdout=0, stderr=0)
        self.sequence = 0
        self.last_sync = time.monotonic()
        self.next_sync = self.last_sync+1
        self.max_sync_gap_s = 0
        self.total = 0

    def chunk(self, stream, block):
        target = {'stdin': 'stdin-wire.log', 'stdout': 'stdout.log', 'stderr': 'stderr.log'}[stream]
        self.files[target].write(block); self.files[target].flush()
        event = dict(schema_version=1, sequence=self.sequence, monotonic_ns=time.monotonic_ns(),
                     clock_domain='host_monotonic', stream=stream, offset=self.offsets[stream],
                     observed_bytes=len(block), retained_bytes=len(block), truncated=False)
        self.files['pipe-events.jsonl'].write((json.dumps(event)+'\n').encode())
        self.files['pipe-events.jsonl'].flush()
        self.offsets[stream] += len(block); self.sequence += 1
        self.total += len(block) + 512
        self.sync()

    def sample(self, value):
        self.files['samples.jsonl'].write((json.dumps(value)+'\n').encode())
        self.files['samples.jsonl'].flush(); self.total += len(json.dumps(value))
        self.sync()

    def sync(self, force=False):
        if force or time.monotonic() >= self.next_sync:
            for stream in self.files.values():
                stream.flush(); os.fsync(stream.fileno())
            now = time.monotonic()
            self.max_sync_gap_s = max(self.max_sync_gap_s, now-self.last_sync)
            atomic_json(self.output/'checkpoint.json', dict(sequence=self.sequence, offsets=self.offsets,
                monotonic_ns=time.monotonic_ns(), fsync_interval_s=1, max_observed_sync_gap_s=self.max_sync_gap_s))
            self.last_sync = now
            self.next_sync = now+1

    def close(self):
        self.sync(force=True)
        for stream in self.files.values(): stream.close()


def validate_spec(argv, image, mounts, environment, protocol, timeout_s, interval_ms, guard_gib, memory_bytes, cpus):
    if (not re.fullmatch(r'sha256:[a-f0-9]{64}', image)
            or not argv or not all(isinstance(v, str) and v and '\0' not in v for v in argv)):
        raise ValueError('Immutable image and nonempty argv required')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (timeout_s, interval_ms, guard_gib, memory_bytes, cpus)):
        raise ValueError('Finite numeric limits required')
    if not (0 < timeout_s <= 3600 and 100 <= interval_ms <= 5000 and 0 < guard_gib <= 64
            and 32*2**20 <= memory_bytes <= 104*2**30 and 0 < cpus <= 8):
        raise ValueError('Recorder limits outside approved boundaries')
    for source, target in mounts:
        source = Path(source).resolve(strict=True)
        if (source == Path('/') or not str(target).startswith('/') or str(target) == '/'
                or str(target).startswith(('/proc', '/sys', '/dev')) or str(target) == '/var/run/docker.sock'
                or any(c in str(source)+str(target) for c in ('\0', '\n', ','))):
            raise ValueError('Invalid readonly mount')
    for key, value in environment.items():
        if (not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or not isinstance(value, str)
                or any(c in value for c in ('\0', '\n'))
                or key in {'LD_PRELOAD', 'PYTHONPATH', 'PYTHONHOME', 'HOME'}):
            raise ValueError('Invalid recorder environment')
    if protocol is not None:
        if not isinstance(protocol, bytes) or len(protocol) > 1024*1024:
            raise ValueError('Protocol must be bytes within 1 MiB')
        lines = protocol.splitlines(keepends=True)
        if (not lines or lines[-1] != b'QUIT\n' or not all(line.startswith(b'GEN ') and line.endswith(b'\n') for line in lines[:-1])):
            raise ValueError('Native protocol requires GEN lines followed by QUIT')


def create_argv(argv, intent, *, mounts, gpu, environment, memory_bytes, cpus):
    command = ['create', '--pull', 'never', '--no-healthcheck', '--name', intent['container_name'], '--interactive', '--read-only',
               '--user', f'{os.getuid()}:{os.getgid()}', '--network', 'none', '--ipc', 'private', '--cgroupns', 'private',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--pids-limit', '256', '--log-driver', 'none',
               '--cpus', str(cpus), '--memory', str(int(memory_bytes)), '--memory-swap', str(int(memory_bytes)),
               '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=67108864,mode=1777', '--entrypoint', '/usr/bin/python3',
               '--env', 'HOME=/tmp', '--label', 'factory.lab.owner=spark-lab-v1', '--label', 'factory.lab.nonce='+intent['nonce']]
    for source, target in mounts:
        command += ['--mount', f'type=bind,src={Path(source).resolve()},dst={target},readonly']
    for key, value in sorted(environment.items()): command += ['--env', key+'='+value]
    if gpu: command += ['--device', 'nvidia.com/gpu=0']
    return command + [intent['image'], '-c', GATE, *argv]


def verify_boundary(info, intent, *, memory_bytes, cpus, environment):
    h, c = info['HostConfig'], info['Config']
    if not (info['Image'] == intent['image'] and h['ReadonlyRootfs'] and not h['Privileged']
            and h['NetworkMode'] == 'none' and h['IpcMode'] == 'private' and h['CgroupnsMode'] == 'private'
            and h['Memory'] == memory_bytes and h['MemorySwap'] == memory_bytes
            and h['NanoCpus'] == int(cpus*1e9) and h['PidsLimit'] == 256
            and h.get('PidMode', '') in ('', 'private') and h.get('UTSMode', '') in ('', 'private')
            and h.get('UsernsMode') != 'host' and c['User'] == f'{os.getuid()}:{os.getgid()}'
            and h['CapDrop'] == ['ALL'] and not h.get('CapAdd')
            and any(v in ('no-new-privileges', 'no-new-privileges:true') for v in h['SecurityOpt'])
            and h['LogConfig']['Type'] == 'none' and not c.get('Volumes')
            and all((m['Type'] == 'bind' and not m['RW']) or (m['Type'] == 'tmpfs' and m['Destination'] == '/tmp')
                    for m in info.get('Mounts', []))):
        raise RuntimeError('Created container failed boundary inspection')
    effective = dict(entry.split('=', 1) for entry in c.get('Env', []) if '=' in entry)
    if any(effective.get(k) != v for k, v in environment.items()):
        raise RuntimeError('Created container environment differs')
    blocked = {'DS4_PROF', 'DS4_PROF_SYNC', 'DS4_TRACE', 'STRATA_DS4_SLOT_KEEP', 'STRATA_DS4_SLOT_DIR', 'LD_PRELOAD'}
    if environment.get('DS4_PROF') == '1' and effective.get('DS4_PROF') == '1':
        blocked.remove('DS4_PROF')
    if blocked.intersection(effective):
        raise RuntimeError('Image inherits uncontrolled profiler or preload settings')


def run_container(argv, *, output, image, mounts=(), gpu=False, environment=None, protocol=None,
                  timeout_s=900, interval_ms=1000, guard_gib=8, memory_bytes=104*2**30, cpus=8,
                  lease_root=None, output_limit=16*1024*1024):
    if isinstance(protocol, (str, Path)):
        with Path(protocol).open('rb') as stream: protocol = stream.read(1024*1024+1)
    environment = dict(environment or {})
    validate_spec(argv, image, mounts, environment, protocol, timeout_s, interval_ms, guard_gib, memory_bytes, cpus)
    if not 1024 <= output_limit <= 32*1024*1024:
        raise ValueError('Invalid output bound')
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    intent = dict(schema_version=1, output=str(output), nonce=uuid.uuid4().hex,
                  container_name='factory-lab-'+uuid.uuid4().hex, image=image, owner=process_identity(),
                  deadline_monotonic=start+timeout_s+10, fsync_interval_s=1, durability_tail='Since last checkpoint; scheduling and I/O may delay the nominal cadence')
    atomic_json(output/'intent.json', intent)
    if protocol is not None:
        with (output/'stdin.log').open('xb') as stream:
            stream.write(protocol); stream.flush(); os.fsync(stream.fileno())
    report = dict(schema_version=1, reason='setup_failure', image=image, container_name=intent['container_name'],
                  engine_argv=list(argv), memory_bytes=memory_bytes, swap_extra_bytes=0, cpus=cpus,
                  interval_ms=interval_ms, guard_gib=guard_gib, fsync_interval_s=1, durability_tail='Since last checkpoint; scheduling and I/O may delay the nominal cadence',
                  quiescent=False, container_removed=False, evidence_completeness='partial')
    lease = QuietLease(lease_root, 'lab', timeout_s=timeout_s) if lease_root else nullcontext()
    guardian = process = journal = selector = None
    with lease as held:
        try:
            guardian_args = [sys.executable, '-m', 'jiuwenswarm.factory.lab_lifecycle', 'guard', str(output)]
            inherited = ()
            if held is not None:
                guardian_args += ['--lease-fd', str(held.fd)]; inherited = (held.fd,)
            with (output/'guardian.log').open('ab') as log:
                guardian = subprocess.Popen(guardian_args, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                           start_new_session=True, pass_fds=inherited)
            atomic_json(output/'guardian.json', dict(identity=process_identity(guardian.pid)))
            if host_available() < guard_gib*2**30:
                raise RuntimeError('Host memory below guard before create')
            command = create_argv(argv, intent, mounts=mounts, gpu=gpu, environment=environment,
                                  memory_bytes=memory_bytes, cpus=cpus)
            report['create_argv'] = command
            cid = docker(*command).stdout.strip()
            if not re.fullmatch(r'[a-f0-9]{64}', cid): raise RuntimeError('Invalid created container ID')
            atomic_json(output/'container.json', dict(container_id=cid))
            info = inspect_owned(intent); verify_boundary(info, intent, memory_bytes=memory_bytes, cpus=cpus, environment=environment)
            atomic_json(output/'inspect-created.json', info)
            process = subprocess.Popen(['docker', 'start', '--attach', '--interactive', cid], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                info = inspect_owned(intent)
                if info['State']['Running'] and info['State']['Pid']: break
                if process.poll() is not None: raise RuntimeError('Attach exited before exec barrier')
                time.sleep(.05)
            else: raise TimeoutError('Container exec-barrier timeout')
            pid = info['State']['Pid']; group = cgroup_path(pid)
            atomic_json(output/'host-process.json', dict(identity=process_identity(pid), cgroup=str(group)))
            journal = Journal(output); selector = selectors.DefaultSelector()
            for pipe, label in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
                os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ, label)
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
            pending = b'FACTORY_EXEC\n'; lines = protocol.splitlines(keepends=True) if protocol is not None else []
            input_index = 0; ready = False; stdout_tail = b''; next_sample = 0; output_bytes = 0
            while True:
                now = time.monotonic()
                if now-start >= timeout_s: report['reason'] = 'timeout'; break
                if now >= next_sample:
                    value = memory_sample(group, pid); journal.sample(value)
                    if value['available_bytes'] < guard_gib*2**30: report['reason'] = 'memory_guard'; break
                    if any(value['memory_events'].get(k, 0) for k in ('oom', 'oom_kill', 'oom_group_kill')):
                        report['reason'] = 'oom_event'; break
                    next_sample = now+interval_ms/1000
                journal.sync()
                for key, _ in selector.select(timeout=.1):
                    label = key.data
                    if label == 'stdin':
                        count = os.write(key.fileobj.fileno(), pending[:4096]); journal.chunk('stdin', pending[:count]); pending = pending[count:]
                        if not pending:
                            selector.unregister(process.stdin)
                            # QUIT is the native termination signal. Keep the pipe open until
                            # exit: Strata has a detached stdin reader; injecting EOF races
                            # its destruction of the input mutex after QUIT.
                            if protocol is None: process.stdin.close()
                        continue
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block: selector.unregister(key.fileobj); continue
                    output_bytes += len(block)
                    if output_bytes > output_limit:
                        report['reason'] = 'output_limit'; break
                    journal.chunk(label, block)
                    if label == 'stdout' and protocol is not None:
                        stdout_tail += block
                        if len(stdout_tail) > 1024*1024: raise RuntimeError('Protocol line exceeds 1 MiB')
                        while b'\n' in stdout_tail:
                            line, stdout_tail = stdout_tail.split(b'\n', 1)
                            advance = (line.startswith(b'READY') and not ready) or (line.startswith(b'DONE ') and ready)
                            if line.startswith(b'READY'): ready = True
                            if advance and input_index < len(lines):
                                if pending: raise RuntimeError('Native protocol response before input drained')
                                pending = lines[input_index]; input_index += 1
                                selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
                if report['reason'] == 'output_limit' or journal.total > 64*1024*1024:
                    if report['reason'] != 'output_limit': report['reason'] = 'telemetry_limit'
                    break
                if process.poll() is not None and not selector.get_map():
                    report['reason'] = 'completed' if process.returncode == 0 else 'command_failed'
                    if protocol is not None and (input_index != len(lines) or pending): report['reason'] = 'native_replay_incomplete'
                    break
        except BaseException as exc:
            report.update(reason='cancelled' if isinstance(exc, (SystemExit, KeyboardInterrupt)) else 'recorder_error',
                          error=type(exc).__name__+': '+str(exc))
        finally:
            previous = {}
            for sig in (signal.SIGTERM, signal.SIGINT):
                previous[sig] = signal.getsignal(sig); signal.signal(sig, signal.SIG_IGN)
            try:
                if selector: selector.close()
                if journal:
                    journal.close()
                    report['max_observed_sync_gap_s'] = journal.max_sync_gap_s
                record = recover_run(output, report['reason'], seal=False)
                report.update(container_removed=record['removed'], quiescent=record['removed'])
                if 'container_exit_code' in record:
                    report['container_exit_code'] = record['container_exit_code']
                    report['container_oom_killed'] = record['container_oom_killed']
                    if record['container_oom_killed']: report['reason'] = 'oom_event'
                if process:
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
                    for pipe in (process.stdin, process.stdout, process.stderr):
                        if pipe and not pipe.closed: pipe.close()
                if report['reason'] == 'completed' and report.get('container_exit_code') == 0 and report['container_removed']:
                    report['evidence_completeness'] = 'complete'
            except Exception as exc:
                report['cleanup_error'] = type(exc).__name__+': '+str(exc)
            finally:
                report['duration_s'] = time.monotonic()-start
                atomic_json(output/'report.json', report)
                # Stop only after successful scoped cleanup; otherwise the guardian
                # remains responsible and the partial report does not mask it.
                if report['container_removed']:
                    atomic_json(output/'guardian-stop.json', dict(reason='cleanup_observed'))
                    if guardian:
                        try: guardian.wait(timeout=3)
                        except subprocess.TimeoutExpired: pass
                seal_manifest(output, report['evidence_completeness'])
                for sig, handler in previous.items(): signal.signal(sig, handler)
    return report
