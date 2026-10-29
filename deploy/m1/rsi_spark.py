"""Finite root-owned Unix socket relay to the existing Spark vLLM service.

Linux/WSL only; prepare pins one operator-selected SSH user@host. Serve/status
accept no destination or path overrides; remote model API and model stay fixed.
No inference, remote configuration, keys, or model downloads are performed here.
"""
from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import selectors
import socket
import stat
import struct
import subprocess
import threading
import time
import uuid

ROOT = Path('/var/lib/ai4r-rsi-spark')
RUN = Path('/run/ai4r-rsi-spark')
SOCKET = RUN / 'model.sock'
PROFILE = ROOT / 'profile.json'
ATTESTATION = ROOT / 'listener.json'
PUBLIC_PROFILE = RUN / 'profile.json'
PUBLIC_ATTESTATION = RUN / 'listener.json'
MODEL = 'Qwen3.8-27B-NVFP4'
SSH = '/mnt/c/Windows/System32/OpenSSH/ssh.exe'
GID = 13000
CALLER_UID = 12001
MAX_SECONDS = 120
MAX_BYTES = 16 * 1024 * 1024
MAX_CONNECTIONS = 2
BUFFER = 65536


def require_root():
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        raise ValueError('Linux root is required')


def checked(path, kind, mode=None, gid=0):
    """Reject symlinks, writable ancestors, and unexpected custody."""
    path = Path(path)
    for ancestor in reversed(path.parents):
        meta = ancestor.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ValueError('Unsafe protected ancestry')
    meta = path.lstat()
    if not kind(meta.st_mode) or (meta.st_uid, meta.st_gid) != (0, gid):
        raise ValueError('Unexpected protected object custody')
    if mode is not None and stat.S_IMODE(meta.st_mode) != mode:
        raise ValueError('Unexpected protected object mode')
    return meta


def boot_id():
    value = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value):
        raise ValueError('Unexpected Linux boot identity')
    return value


def validate_target(value):
    if (not isinstance(value, str) or len(value) > 320 or value.count('@') != 1 or
            not re.fullmatch('[A-Za-z0-9_.:@-]+', value, re.ASCII)):
        raise ValueError('Expected an explicit SSH user@hostname or user@IP')
    user, host = value.split('@')
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_.-]{0,31}', user, re.ASCII):
        raise ValueError('Invalid SSH user')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        labels = host.split('.')
        if (len(host) > 253 or not all(re.fullmatch('[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label,
                                                    re.ASCII) for label in labels)):
            raise ValueError('Invalid SSH host') from None
    return value


def profile(ssh_target, source_epoch=None, boot=None):
    value = {'schema': 'ai4r-rsi-spark:1', 'model': MODEL, 'ssh_user_host': validate_target(ssh_target),
            'remote': '127.0.0.1:8000', 'socket': str(SOCKET),
            'protocol': 'openai', 'profile': str(PROFILE)}
    if source_epoch is not None:
        value['source_epoch'] = source_epoch
        value['boot_id'] = boot if boot is not None else boot_id()
    return value


def public_profile(value):
    return {key: item for key, item in value.items() if key != 'ssh_user_host'}


def write_new(path, value, gid=0, mode=0o600):
    """Publish a fully fsynced file atomically, refusing existing objects."""
    path = Path(path)
    temporary = path.parent / ('.spark-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchown(stream.fileno(), 0, gid)
            os.fchmod(stream.fileno(), mode)
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink()


def prepare(ssh_target):
    require_root()
    validate_target(ssh_target)
    # Both trees must be fresh. Refuse all existing objects before writing.
    for path in (ROOT, RUN):
        if os.path.lexists(path):
            raise ValueError('Spark preparation requires fresh fixed directories')
        checked(path.parent, stat.S_ISDIR)
    ROOT.mkdir(mode=0o700)
    os.chmod(ROOT, 0o700)
    RUN.mkdir(mode=0o710)
    os.chown(RUN, 0, GID)
    os.chmod(RUN, 0o710)
    value = profile(ssh_target, uuid.uuid4().hex)
    write_new(PROFILE, value)
    write_new(PUBLIC_PROFILE, public_profile(value), GID, 0o640)
    return {'state': 'prepared', **public_profile(value)}


def load_profile():
    require_root()
    checked(ROOT, stat.S_ISDIR, 0o700)
    checked(RUN, stat.S_ISDIR, 0o710, GID)
    checked(PROFILE, stat.S_ISREG, 0o600)
    value = json.loads(PROFILE.read_bytes())
    epoch = value.get('source_epoch')
    if (not isinstance(epoch, str) or not re.fullmatch('[a-f0-9]{32}', epoch) or
            value != profile(value.get('ssh_user_host'), epoch)):
        raise ValueError('Unknown finite Spark profile')
    checked(PUBLIC_PROFILE, stat.S_ISREG, 0o640, GID)
    if json.loads(PUBLIC_PROFILE.read_bytes()) != public_profile(value):
        raise ValueError('Public Spark profile differs from protected profile')
    return value


def ssh_command(value):
    return [SSH, '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=12', '-W', '127.0.0.1:8000', validate_target(value.get('ssh_user_host'))]


def ssh_environment():
    # WSL_INTEROP is required for Windows OpenSSH; no provider credentials pass.
    allowed = {'PATH', 'WSL_INTEROP', 'SYSTEMROOT', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP'}
    return {key: value for key, value in os.environ.items() if key in allowed}


def peer_allowed(connection):
    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    return uid in (0, CALLER_UID)


def pump(connection, process, seconds=MAX_SECONDS, byte_limit=MAX_BYTES):
    """Bounded duplex relay with backpressure and EOF propagation; no logging."""
    connection.setblocking(False)
    os.set_blocking(process.stdin.fileno(), False)
    os.set_blocking(process.stdout.fileno(), False)
    upstream = bytearray()
    downstream = bytearray()
    client_eof = server_eof = stdin_closed = False
    transferred = 0
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and transferred < byte_limit:
        if client_eof and not upstream and not stdin_closed:
            process.stdin.close()
            stdin_closed = True
        if server_eof and not downstream:
            return
        with selectors.DefaultSelector() as selector:
            client_events = (selectors.EVENT_READ if not client_eof and len(upstream) < BUFFER else 0)
            if downstream:
                client_events |= selectors.EVENT_WRITE
            if client_events:
                selector.register(connection, client_events, 'client')
            if not server_eof and len(downstream) < BUFFER:
                selector.register(process.stdout, selectors.EVENT_READ, 'output')
            if upstream and not stdin_closed:
                selector.register(process.stdin, selectors.EVENT_WRITE, 'input')
            if not selector.get_map():
                return
            events = selector.select(min(0.5, max(0, deadline - time.monotonic())))
            for key, mask in events:
                try:
                    if key.data == 'client':
                        if mask & selectors.EVENT_READ:
                            data = connection.recv(min(BUFFER - len(upstream), byte_limit - transferred))
                            client_eof = not data
                            upstream.extend(data)
                            transferred += len(data)
                        if mask & selectors.EVENT_WRITE and downstream:
                            count = connection.send(downstream)
                            del downstream[:count]
                    elif key.data == 'output':
                        data = os.read(process.stdout.fileno(), min(BUFFER - len(downstream), byte_limit - transferred))
                        server_eof = not data
                        downstream.extend(data)
                        transferred += len(data)
                    else:
                        count = os.write(process.stdin.fileno(), upstream)
                        del upstream[:count]
                    if transferred > byte_limit:
                        return
                except BlockingIOError:
                    continue


def relay(connection, slots, value):
    process = None
    try:
        if not peer_allowed(connection):
            return
        process = subprocess.Popen(ssh_command(value), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=ssh_environment(), close_fds=True)
        pump(connection, process)
    except (OSError, ValueError):
        pass  # Deliberately no request, response, or SSH stderr logging.
    finally:
        connection.close()
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout):
                if stream and not stream.closed:
                    stream.close()
        slots.release()


def start_ticks(pid):
    # comm may contain spaces or ')'; fields after its final ')' start at field 3.
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def serve():
    value = load_profile()
    if any(os.path.lexists(path) for path in (SOCKET, ATTESTATION, PUBLIC_ATTESTATION)):
        raise ValueError('Existing socket or listener attestation requires operator review')
    slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(SOCKET))
        os.chown(SOCKET, 0, GID)
        os.chmod(SOCKET, 0o660)
        listener.listen(MAX_CONNECTIONS)
        inode = checked(SOCKET, stat.S_ISSOCK, 0o660, GID).st_ino
        attestation = {**public_profile(value), 'pid': os.getpid(), 'start_ticks': start_ticks(os.getpid()),
                       'socket_inode': inode}
        write_new(ATTESTATION, attestation)
        write_new(PUBLIC_ATTESTATION, attestation, GID, 0o640)
        # Foreground lifetime is controlled by the operator; no daemon or service mutation.
        try:
            while True:
                connection, _ = listener.accept()
                if not slots.acquire(blocking=False):
                    connection.close()
                    continue
                threading.Thread(target=relay, args=(connection, slots, value), daemon=True).start()
        finally:
            # Preserve attestations after abnormal exit; never unlink unexpected objects.
            if SOCKET.lstat().st_ino == inode:
                SOCKET.unlink()
            if ATTESTATION.read_bytes() == (json.dumps(attestation, sort_keys=True) + '\n').encode():
                ATTESTATION.unlink()
            if PUBLIC_ATTESTATION.read_bytes() == (json.dumps(attestation, sort_keys=True) + '\n').encode():
                PUBLIC_ATTESTATION.unlink()


def read_endpoint(path, expected_pid):
    connection = http.client.HTTPConnection('localhost', timeout=15)
    connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.sock.settimeout(15)
    try:
        connection.sock.connect(str(SOCKET))
        pid, uid, _ = struct.unpack('3i', connection.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != 0 or pid != expected_pid:
            raise ValueError('Listener peer differs')
        connection.request('GET', path, headers={'Connection': 'close'})
        response = connection.getresponse()
        body = response.read(65537)
        if response.status != 200 or len(body) > 65536:
            raise ValueError('Spark read-only metadata probe failed')
        return json.loads(body) if body else None
    finally:
        connection.close()


def status():
    protected = load_profile()
    meta = checked(SOCKET, stat.S_ISSOCK, 0o660, GID)
    checked(ATTESTATION, stat.S_ISREG, 0o600)
    value = json.loads(ATTESTATION.read_bytes())
    expected = public_profile(protected)
    if set(value) != set(expected) | {'pid', 'start_ticks', 'socket_inode'}:
        raise ValueError('Unknown listener attestation')
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValueError('Listener profile differs')
    checked(PUBLIC_ATTESTATION, stat.S_ISREG, 0o640, GID)
    if json.loads(PUBLIC_ATTESTATION.read_bytes()) != value:
        raise ValueError('Public listener attestation differs')
    if value['socket_inode'] != meta.st_ino or value['start_ticks'] != start_ticks(value['pid']):
        raise ValueError('Stale listener attestation')
    # Every metadata connection checks actual listener credentials before sending.
    read_endpoint('/health', value['pid'])
    models = read_endpoint('/v1/models', value['pid'])
    listed = models.get('data', [])
    if len(listed) != 1 or listed[0].get('id') != MODEL:
        raise ValueError('Served model differs from the approved existing model')
    version = read_endpoint('/version', value['pid'])
    return {'state': 'healthy', 'model': MODEL, 'version': version.get('version'),
            'max_model_len': listed[0].get('max_model_len'), 'profile': str(PROFILE),
            'socket': str(SOCKET)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest='operation', required=True)
    preparation = sub.add_parser('prepare', allow_abbrev=False)
    preparation.add_argument('--ssh-target', required=True, type=validate_target)
    sub.add_parser('serve', allow_abbrev=False)
    sub.add_parser('status', allow_abbrev=False)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.ssh_target) if args.operation == 'prepare' else {'serve': serve, 'status': status}[args.operation]()
        if result is not None:
            print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        parser.exit(1, 'Spark operation failed; check fixed profile, custody, listener, and trusted SSH access.\n')


if __name__ == '__main__':
    main()
