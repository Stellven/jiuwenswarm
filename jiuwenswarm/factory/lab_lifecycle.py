"""Host-owned quiet leases and exact-owner process/container recovery.

The files are a trusted same-user channel, not a multi-user sandbox. Reboot
recovery is deliberately not automatic: process identities include boot/start.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import time
import uuid


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('x') as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def process_identity(pid=None):
    pid = os.getpid() if pid is None else pid
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return dict(pid=pid, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    start_ticks=int(fields[19]))
    except (OSError, ValueError, IndexError):
        return None


def process_matches(identity):
    return bool(identity) and process_identity(identity['pid']) == identity


class QuietLease:
    """Participating lab work excludes builds/CPU work, across process death.

    A recorder passes ``fd`` to its independent guardian; the guardian keeps
    the same flock alive until owned workload cleanup has been observed.
    """
    def __init__(self, root, kind='lab', timeout_s=60):
        if kind not in {'lab', 'build', 'cpu'} or timeout_s < 0:
            raise ValueError('Invalid lease kind or timeout')
        self.root, self.kind, self.timeout_s = Path(root), kind, timeout_s
        self.stream = None
        self.receipt = None

    @property
    def fd(self):
        return self.stream.fileno()

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.stream = (self.root/'lab.lock').open('a+')
        wanted = fcntl.LOCK_EX if self.kind == 'lab' else fcntl.LOCK_SH
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                fcntl.flock(self.fd, wanted | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self.stream.close(); self.stream = None
                    raise TimeoutError('Lab lease blocks participating ' + self.kind + ' work')
                time.sleep(.05)
        self.receipt = self.root/('lease-' + uuid.uuid4().hex + '.json')
        atomic_json(self.receipt, dict(kind=self.kind, owner=process_identity(), state='held', acquired_at=time.time()))
        return self

    def __exit__(self, *args):
        if self.stream:
            if self.receipt:
                record = json.loads(self.receipt.read_text())
                atomic_json(self.receipt, dict(record, state='released', released_at=time.time()))
            # close, not LOCK_UN: an inherited guardian may still own this lock.
            self.stream.close(); self.stream = None


def docker(*args, required=True):
    result = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=30)
    if len(result.stdout) + len(result.stderr) > 4*1024*1024:
        raise RuntimeError('Docker control output exceeded bound')
    if required and result.returncode:
        raise RuntimeError('Docker ' + str(args[0]) + ': ' + result.stderr[:2048])
    return result


def load_intent(output):
    output = Path(output).resolve()
    intent = json.loads((output/'intent.json').read_text())
    if (intent.get('output') != str(output)
            or not re.fullmatch(r'factory-lab-[a-f0-9]{32}', intent.get('container_name', ''))
            or not re.fullmatch(r'[a-f0-9]{32}', intent.get('nonce', ''))
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', intent.get('image', ''))):
        raise ValueError('Invalid durable lab intent')
    return intent


def inspect_owned(intent):
    result = docker('inspect', intent['container_name'], required=False)
    if result.returncode:
        # Docker connectivity errors are not evidence the resource is absent.
        if 'no such object' in result.stderr.lower() or 'no such container' in result.stderr.lower():
            return None
        raise RuntimeError('Cannot establish owned container state: ' + result.stderr[:2048])
    info = json.loads(result.stdout)[0]
    labels = info['Config'].get('Labels') or {}
    if (info['Name'] != '/' + intent['container_name'] or info['Image'] != intent['image']
            or labels.get('factory.lab.nonce') != intent['nonce']
            or labels.get('factory.lab.owner') != 'spark-lab-v1'):
        raise ValueError('Container differs from exact durable ownership intent')
    receipt = Path(intent['output'])/'container.json'
    if receipt.exists() and json.loads(receipt.read_text())['container_id'] != info['Id']:
        raise ValueError('Container ID differs from durable create receipt')
    return info


def seal_manifest(output, state):
    output = Path(output)
    files = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name not in {'manifest.json', 'guardian-stop.json'} and not path.name.startswith('.'):
            with path.open('rb') as stream:
                files[path.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    previous = output/'manifest.json'
    if previous.exists():
        old = json.loads(previous.read_text())
        if old.get('state') == state and old.get('files') == files:
            return old
    value = dict(schema_version=1, state=state, sealed_at=time.time(), files=files)
    atomic_json(output/'manifest.json', value)
    return value


def recover_run(output, reason='recorder_lost', *, seal=True):
    """Remove only the exact owned container; preserve first recovery receipt."""
    output = Path(output).resolve()
    intent = load_intent(output)
    with (output/'recovery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        info = inspect_owned(intent)
        record = dict(reason=reason, container_missing=info is None, removed=False,
                      recovered_at=time.time(), owner=intent['owner'])
        if info:
            atomic_json(output/'inspect-final.json', info)
            record.update(container_id=info['Id'], was_running=info['State']['Running'],
                          container_exit_code=info['State']['ExitCode'], container_oom_killed=info['State']['OOMKilled'])
            docker('rm', '-f', info['Id'])
        # Recheck by exact name and ownership; a daemon failure is not cleanup.
        record['removed'] = inspect_owned(intent) is None
        if not (output/'recovery.json').exists():
            atomic_json(output/'recovery.json', record)
        if seal:
            if not (output/'report.json').exists():
                atomic_json(output/'report.json', dict(schema_version=1, reason=reason, quiescent=record['removed'],
                    container_removed=record['removed'], evidence_completeness='partial', recovery=record,
                    limitations=['Recorder was interrupted; partial records are not a successful measurement.',
                                 'Process recovery tested; reboot and power-loss recovery not qualified.']))
            state = json.loads((output/'report.json').read_text()).get('evidence_completeness', 'partial')
            seal_manifest(output, state)
        return record


def guardian(output, lease_fd=None):
    """Independent deadline/owner watchdog; no agent, model, or queue decisions."""
    output = Path(output).resolve()
    intent = load_intent(output)
    # Do not operate on stale process credentials after reboot.
    if intent['owner']['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Reboot reconciliation requires explicit host recovery')
    lost_at = None
    while True:
        if (output/'guardian-stop.json').exists():
            return
        expired = time.monotonic() >= intent['deadline_monotonic']
        alive = process_matches(intent['owner'])
        if not alive or expired:
            lost_at = lost_at or time.monotonic()
            reason = 'deadline' if expired else 'recorder_lost'
            try:
                info = inspect_owned(intent)
                # A create RPC can complete after owner death. Do not declare
                # missing until its bounded control-call timeout has elapsed.
                if info is not None or time.monotonic()-lost_at >= 32:
                    recover_run(output, reason)
                    return
            except Exception as exc:
                atomic_json(output/'guardian-error.json', dict(error=type(exc).__name__ + ': ' + str(exc), at=time.time()))
                if time.monotonic()-lost_at > 60:
                    return
        time.sleep(.2)



class OwnedContainerGuard:
    """Guard a native build, CPU, or GPU lab Docker command with the same exact ownership.

    The caller must inject ``name`` and every entry of ``labels`` into Docker
    create/run. Writable build mounts are the builder's separate admission
    responsibility. This does not interpret compilation output or score runs.
    """
    def __init__(self, output, image, *, lease_root=None, kind='build', timeout_s=5400):
        if (not re.fullmatch(r'sha256:[a-f0-9]{64}', image) or kind not in {'build', 'cpu', 'lab'}
                or type(timeout_s) not in (int, float) or not 0 < timeout_s <= 5400):
            raise ValueError('Invalid guarded native container specification')
        self.output = Path(output).resolve()
        self.image, self.lease_root, self.kind, self.timeout_s = image, lease_root, kind, timeout_s
        self.lease = self.process = None
        self.intent = None

    @property
    def name(self):
        return self.intent['container_name']

    @property
    def labels(self):
        return {'factory.lab.owner': 'spark-lab-v1', 'factory.lab.nonce': self.intent['nonce'],
                'factory.lab.role': self.kind}

    def __enter__(self):
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            if self.lease_root is not None:
                self.lease = QuietLease(self.lease_root, self.kind, timeout_s=self.timeout_s)
                self.lease.__enter__()
            self.intent = dict(schema_version=1, output=str(self.output), nonce=uuid.uuid4().hex,
                container_name='factory-lab-'+uuid.uuid4().hex, image=self.image, owner=process_identity(),
                deadline_monotonic=time.monotonic()+self.timeout_s+10, role=self.kind)
            atomic_json(self.output/'intent.json', self.intent)
            args = [sys.executable, '-m', 'jiuwenswarm.factory.lab_lifecycle', 'guard', str(self.output)]
            inherited = ()
            if self.lease:
                args += ['--lease-fd', str(self.lease.fd)]; inherited = (self.lease.fd,)
            with (self.output/'guardian.log').open('ab') as log:
                self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                                start_new_session=True, pass_fds=inherited)
            atomic_json(self.output/'guardian.json', dict(identity=process_identity(self.process.pid)))
            return self
        except BaseException:
            if self.lease: self.lease.__exit__(None, None, None)
            raise

    def record_cid(self, cid):
        if not re.fullmatch(r'[a-f0-9]{64}', cid):
            raise ValueError('Invalid Docker container ID')
        atomic_json(self.output/'container.json', dict(container_id=cid))
        inspect_owned(self.intent)

    def __exit__(self, exc_type, exc, traceback):
        try:
            record = recover_run(self.output, 'command_failed' if exc_type else 'completed', seal=False)
            atomic_json(self.output/'report.json', dict(schema_version=1, role=self.kind,
                reason='command_failed' if exc_type else 'completed', container_removed=record['removed'],
                evidence_completeness='partial' if exc_type else 'complete', recovery=record))
            if record['removed']:
                atomic_json(self.output/'guardian-stop.json', dict(reason='cleanup_observed'))
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired: pass
            seal_manifest(self.output, 'partial' if exc_type else 'complete')
        finally:
            if self.lease: self.lease.__exit__(exc_type, exc, traceback)
        return False

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['recover', 'guard'])
    parser.add_argument('output', type=Path)
    parser.add_argument('--lease-fd', type=int)
    args = parser.parse_args()
    if args.operation == 'guard':
        try: guardian(args.output, args.lease_fd)
        finally:
            if args.lease_fd is not None:
                os.close(args.lease_fd)
    else:
        print(json.dumps(recover_run(args.output)))


if __name__ == '__main__':
    main()
