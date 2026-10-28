#!/usr/bin/env python3
"""Root fixed development-click broker. No generic command RPC is exposed.

The installed wrapper has exactly two verbs: preflight (read-only) and run.
Its bytes/interpreter/authorization/runner are Root-pinned before every click.
Only the reviewed wrapper implements the actual V18 worker launch topology.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import sys
import threading
import time

from jiuwenswarm.research.cc_ui_runtime import module

installation = module('cc_rsi_installation')
dev = None
CONFIG = '/etc/ai4r/cc-rsi-development-root.json'
ROOT = Path('/var/lib/ai4r-cc-rsi-development')
MODULE = '/opt/ai4r-cc-rsi-development/cc_rsi_development.py'
ENV = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','PYTHONDONTWRITEBYTECODE':'1','HOME':'/root',
       'PYTHONPATH':'/opt/ai4r-rsi-frozen-v18-03ed3199:/opt/ai4r-rsi-host-codex/site-packages'}


def need(condition, reason):
    if not condition: raise ValueError(reason)


def pin(value, *, executable=False):
    dev._fields(value, 'path sha256')
    dev._hash(value['sha256'])
    target = Path(value['path'])
    need(target.is_absolute(), 'ABSOLUTE_ROOT_PIN_REQUIRED')
    # Interpreters may be symlinks in images. The configuration must pin their
    # resolved regular file, so path substitution cannot redirect execution.
    for parent in target.parents:
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022, 'ROOT_PIN_ANCESTRY_DIFFERS')
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and not info.st_mode & 0o022
             and (not executable or info.st_mode & 0o111) and info.st_size <= 64 * 1024 * 1024, 'ROOT_PIN_CUSTODY_DIFFERS')
        with os.fdopen(fd, 'rb', closefd=False) as stream: digest = hashlib.sha256(stream.read()).hexdigest()
        need(digest == value['sha256'], 'ROOT_PIN_BYTES_DIFFER')
    finally: os.close(fd)
    return str(target)


def load(path=CONFIG):
    global dev
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_REQUIRED')
    value = json.loads(installation.protected_bytes(path, uid=0, mode=0o600))
    installation._fields(value, 'schema policy gateway_public_key interpreter wrapper authorization runner approved_plan_sha256 module service_sha256')
    installation._fields(value['module'], 'path sha256')
    need(value['module']['path'] == MODULE, 'FIXED_DEVELOPMENT_MODULE_REQUIRED')
    raw = installation.protected_bytes(MODULE, uid=0, mode=0o444)
    need(hashlib.sha256(raw).hexdigest() == value['module']['sha256'], 'DEVELOPMENT_MODULE_BYTES_DIFFER')
    if dev is None:
        # Load only this new, Root-pinned composition module; preserve every
        # installed V18 package file and its qualification hashes unchanged.
        name = '_ai4r_cc_runtime.cc_rsi_development'
        spec = importlib.util.spec_from_file_location(name, MODULE)
        dev = importlib.util.module_from_spec(spec)
        sys.modules[name] = dev
        spec.loader.exec_module(dev)
    need(value['schema'] == 'ai4r-cc-rsi-development-root:1', 'ROOT_INSTALLATION_SCHEMA_DIFFERS')
    dev.policy(value['policy'])
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value['policy']['run_id']) is not None, 'FINITE_RUN_ID_REQUIRED')
    dev._hash(value['approved_plan_sha256'])
    need(value['module']['sha256'] == hashlib.sha256(Path(dev.__file__).read_bytes()).hexdigest()
         and value['service_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'INSTALLED_SOURCE_DIFFERS')
    for key in ('interpreter', 'wrapper', 'authorization', 'runner'): pin(value[key], executable=key == 'interpreter')
    public = base64.b64decode(value['gateway_public_key'] + '=' * (-len(value['gateway_public_key']) % 4), altchars=b'-_', validate=True)
    need(len(public) == 32, 'FRESH_GATEWAY_PUBLIC_KEY_REQUIRED')
    return value, public


class Journal:
    def __init__(self, run_id):
        self.root = ROOT / run_id
        ROOT.mkdir(mode=0o700, exist_ok=True)
        self.root.mkdir(mode=0o700, exist_ok=True)
        for path in (self.root, *self.root.parents):
            meta = path.lstat()
            need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o022, 'JOURNAL_CUSTODY_DIFFERS')
        need(stat.S_IMODE(self.root.stat().st_mode) == 0o700, 'PRIVATE_ROOT_JOURNAL_REQUIRED')

    def write(self, name, value):
        raw = dev.encoded(value)
        fd = os.open(self.root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        return {'id': 'development-click:' + hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest()}

    def read(self, name):
        path = self.root / name
        if not os.path.lexists(path): return None
        return json.loads(installation.protected_bytes(path, uid=0, mode=0o600))

    def lookup(self):
        claim, ack = self.read('claim.json'), self.read('ack.json')
        need(claim is not None or ack is None, 'DANGLING_DEVELOPMENT_ACK')
        return None if claim is None else {'identity': claim['identity'], 'ack': ack}

    def claim(self, identity, assertion):
        self.write('claim.json', {'schema': 'ai4r-cc-rsi-development-claim:1', 'identity': identity, 'assertion': assertion})

    def accept(self, value): return self.write('launch.json', value)
    def acknowledge(self, value): self.write('ack.json', value)


class FixedLauncher:
    def __init__(self, config, journal): self.config, self.journal = config, journal

    def argv(self, verb):
        need(verb in ('preflight', 'run'), 'FIXED_LAUNCH_VERB_REQUIRED')
        for name in ('interpreter', 'wrapper', 'authorization', 'runner'): pin(self.config[name], executable=name == 'interpreter')
        return [self.config['interpreter']['path'], '-B', self.config['wrapper']['path'], verb]

    def preflight(self):
        result = subprocess.run(self.argv('preflight'), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=20, check=True, env=ENV)
        need(len(result.stdout) <= dev.MAX_FRAME, 'PREFLIGHT_EXCEEDS_BOUND')
        reply = json.loads(result.stdout)
        dev._fields(reply, 'schema ready run_id approved_plan_sha256 authorization_sha256')
        need(reply == {'schema': 'ai4r-cc-rsi-development-preflight:1', 'ready': True,
            'run_id': self.config['policy']['run_id'], 'approved_plan_sha256': self.config['approved_plan_sha256'],
            'authorization_sha256': self.config['authorization']['sha256']}, 'REVIEWED_PLAN_NOT_READY')

    def launch(self):
        argv = self.argv('run')
        log = os.open(self.journal.root/'launcher.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        gate_read, gate_write = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(gate_write)
                # The child cannot reach the launcher before Root persisted its
                # exact process identity. No inherited service/database/socket.
                token = os.read(gate_read, 1)
                if token != b'1': os._exit(125)
                os.close(gate_read)
                os.setsid()
                os.dup2(log, 1); os.dup2(log, 2)
                limit = os.sysconf('SC_OPEN_MAX')
                os.closerange(3, min(limit, 1048576))
                null = os.open('/dev/null', os.O_RDWR)
                os.dup2(null, 0)
                if null > 2: os.close(null)
                os.execve(argv[0], argv, ENV)
            except BaseException: os._exit(126)
        os.close(gate_read)
        os.close(log)
        try:
            proc = Path('/proc') / str(pid)
            text = (proc / 'stat').read_text()
            owner = {'pid': pid, 'start_ticks': int(text[text.rfind(')') + 2:].split()[19]),
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'pid_namespace': os.readlink(proc / 'ns/pid'), 'mount_namespace': os.readlink(proc / 'ns/mnt'),
                'expected_argv': argv, 'argv_sha256': hashlib.sha256(dev.encoded(argv)).hexdigest(),
                'run_id': self.config['policy']['run_id'], 'approved_plan_sha256': self.config['approved_plan_sha256'],
                'deadline_unix': int(time.time()) + 3900}
            self.journal.write('owner.json', owner)
            os.write(gate_write, b'1')
        finally: os.close(gate_write)
        def reap():
            _, status = os.waitpid(pid, 0)
            self.journal.write('launcher-exit.json', {'pid': pid, 'wait_status': status, 'recorded_unix': int(time.time())})
        threading.Thread(target=reap, daemon=True).start()
        return owner


def serve(config_path=CONFIG):
    config, public = load(config_path)
    journal = Journal(config['policy']['run_id'])
    launcher = FixedLauncher(config, journal)
    engine = dev.RootDevelopmentEngine(config['policy'], public, journal, launcher.preflight, launcher.launch)
    endpoint = Path(dev.SOCKET)
    endpoint.parent.mkdir(mode=0o750, exist_ok=True)
    for parent in endpoint.parents:
        meta = parent.lstat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o022, 'SOCKET_ANCESTRY_DIFFERS')
    # Never remove an existing service socket or infer it is stale.
    need(not os.path.lexists(endpoint), 'EXISTING_BROKER_REQUIRES_EXACT_CESSATION')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(endpoint)); os.chown(endpoint, 0, 10001); os.chmod(endpoint, 0o660)
        os.chown(endpoint.parent, 0, 10001); os.chmod(endpoint.parent, 0o750)
        server.listen(4)
        while True:
            client, _ = server.accept()
            with client:
                client.settimeout(30)
                try:
                    _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    need(uid == 10001, 'NATIVE_GATEWAY_UID_REQUIRED')
                    raw = bytearray()
                    while not raw.endswith(b'\n'):
                        part = client.recv(min(4096, dev.MAX_FRAME + 1 - len(raw)))
                        need(bool(part) and len(raw) + len(part) <= dev.MAX_FRAME, 'FINITE_REQUEST_REQUIRED')
                        raw.extend(part)
                    # Revalidate config/source custody before each request.
                    need(load(config_path)[0] == config, 'ROOT_INSTALLATION_CHANGED')
                    reply = engine.handle(json.loads(raw))
                    if raw and json.loads(raw).get('operation') == 'status':
                        stopped = journal.read('launcher-exit.json')
                        if stopped is not None:
                            code = os.waitstatus_to_exitcode(stopped['wait_status'])
                            reply['blocker'] = ('Development launcher completed; inspect the published actual result' if code == 0
                                else 'Development launcher failed with exit ' + str(code) + '; inspect retained evidence without replay')
                except Exception:
                    reply = {'error': 'Development request blocked; reconcile without replay'}
                client.sendall(dev.encoded(reply) + b'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=CONFIG)
    serve(parser.parse_args().config)
