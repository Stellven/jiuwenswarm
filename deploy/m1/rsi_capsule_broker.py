"""Root-only finite capsule broker; no caller-selected command or authority."""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import sys

from jiuwenswarm.research.cc_ui_runtime import module

installation = module('cc_rsi_installation')
CONFIG = '/etc/ai4r/cc-rsi-capsule-root.json'
ROOT = Path('/var/lib/ai4r-cc-rsi-capsules')


def need(value, reason):
    if not value: raise ValueError(reason)


def pinned(value):
    installation._fields(value, 'path sha256')
    path = Path(value['path'])
    need(path.is_absolute() and '..' not in path.parts, 'ROOT_ABSOLUTE_PIN_REQUIRED')
    raw = installation.protected_bytes(path, uid=0, mode=0o444, limit=64*1024*1024)
    need(hashlib.sha256(raw).hexdigest() == value['sha256'], 'ROOT_PIN_BYTES_DIFFER')
    return raw


def load_module(name, pin):
    pinned(pin)
    spec = importlib.util.spec_from_file_location(name, pin['path'])
    result = importlib.util.module_from_spec(spec); sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def load(path):
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_BROKER_REQUIRED')
    value = json.loads(installation.protected_bytes(path, uid=0, mode=0o600))
    installation._fields(value, 'schema policy gateway_public_key module base_service interpreter wrapper slots service_sha256')
    need(value['schema'] == 'ai4r-cc-rsi-capsule-root:1'
         and value['service_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'ROOT_BROKER_SOURCE_DIFFERS')
    for key in ('module', 'base_service', 'wrapper'): pinned(value[key])
    for slot in value['slots']:
        installation._fields(slot, 'target_id configuration launcher_configuration')
        pinned(slot['configuration']); pinned(slot['launcher_configuration'])
    return value


def terminal_status(status, read):
    """Add the actual retained launcher outcome without reopening a slot."""
    result = dict(status)
    stopped = read('launcher-exit.json')
    if stopped is not None:
        need(type(stopped['wait_status']) is int and type(stopped['pid']) is int,
             'ACTUAL_LAUNCHER_EXIT_REQUIRED')
        code = os.waitstatus_to_exitcode(stopped['wait_status'])
        result.update(ready=False, phase='LAUNCHED', blocker=(
            'Development launcher completed; inspect the published actual result' if code == 0 else
            'Development launcher failed with exit '+str(code)+'; inspect retained evidence without replay'))
    return result


def serve(path=CONFIG):
    config = load(path)
    # Existing immutable service supplies durable journals and gated fork owner
    # identities; only this new namespace and fixed argv composition differ.
    base = load_module('_ai4r_capsule_base_service', config['base_service'])
    # Preserve existing old module bytes: load via already installed path.
    oldpath = '/opt/ai4r-cc-rsi-development/cc_rsi_development.py'
    oldraw = installation.protected_bytes(oldpath, uid=0, mode=0o444)
    old = load_module('_ai4r_cc_runtime.cc_rsi_development', {
        'path': oldpath, 'sha256': hashlib.sha256(oldraw).hexdigest()})
    cap = load_module('_ai4r_cc_runtime.cc_rsi_capsule', config['module'])
    cap.policy(config['policy']); base.dev = old; base.ROOT = ROOT
    need({r['target_id'] for r in config['slots']} == {r['target_id'] for r in config['policy']['slots']}
         and len(config['slots']) == len(config['policy']['slots']), 'EXACT_PREPARED_SLOT_SET_REQUIRED')
    base.pin(config['interpreter'], executable=True)

    class Launcher(base.FixedLauncher):
        def argv(self, verb):
            need(verb in ('preflight', 'run'), 'FINITE_CAPSULE_VERB_REQUIRED')
            need(load(path) == config, 'CAPSULE_INSTALLATION_CHANGED')
            base.pin(config['interpreter'], executable=True)
            return [config['interpreter']['path'], '-B', config['wrapper']['path'], verb,
                    '--configuration', self.config['launcher_configuration']['path'],
                    '--configuration-sha256', self.config['launcher_configuration']['sha256']]

        def preflight(self):
            import subprocess
            result = subprocess.run(self.argv('preflight'), check=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=45, env=base.ENV)
            need(len(result.stdout) <= old.MAX_FRAME, 'FINITE_CAPSULE_PREFLIGHT_REQUIRED')
            reply = json.loads(result.stdout)
            need(reply == {'schema': 'ai4r-rsi-capsule-launch-preflight:1', 'ready': True,
                'run_id': self.config['policy']['run_id'], 'configuration_sha256': self.config['configuration']['sha256']},
                'EXACT_PREPARED_CAPSULE_NOT_READY')

    slots = {}; journals = {}
    for item in config['slots']:
        slot = next(row for row in config['policy']['slots'] if row['target_id'] == item['target_id'])
        journal = base.Journal(slot['run_id'])
        launcher = Launcher(dict(item, policy=cap.slot_policy(config['policy'], slot),
            approved_plan_sha256=item['configuration']['sha256']), journal)
        slots[item['target_id']] = (journal, launcher.preflight, launcher.launch)
        journals[item['target_id']] = journal
    public = base64.b64decode(config['gateway_public_key'] + '='*(-len(config['gateway_public_key'])%4), altchars=b'-_', validate=True)
    need(len(public) == 32, 'EXACT_PUBLIC_KEY_REQUIRED')
    engine = cap.RootCapsuleEngine(config['policy'], public, slots)
    endpoint = Path(cap.SOCKET)
    need(endpoint.parent.is_dir() and not os.path.lexists(endpoint), 'FRESH_CAPSULE_SOCKET_REQUIRED')
    for parent in endpoint.parents:
        import stat
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022, 'SOCKET_ANCESTRY_DIFFERS')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(endpoint)); os.chown(endpoint, 0, 10001); os.chmod(endpoint, 0o660); server.listen(4)
        while True:
            client, _ = server.accept()
            with client:
                client.settimeout(45)
                try:
                    _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    need(uid == 10001, 'NATIVE_GATEWAY_UID_REQUIRED')
                    raw = bytearray()
                    while not raw.endswith(b'\n'):
                        part = client.recv(min(4096, old.MAX_FRAME + 1 - len(raw)))
                        need(part and len(raw)+len(part) <= old.MAX_FRAME, 'FINITE_CAPSULE_REQUEST_REQUIRED')
                        raw.extend(part)
                    need(load(path) == config, 'CAPSULE_INSTALLATION_CHANGED')
                    request = json.loads(raw)
                    reply = engine.handle(request)
                    if request.get('operation') == 'status':
                        reply['slots'] = [terminal_status(row, journals[row['target_id']].read)
                                          for row in reply['slots']]
                except Exception: reply = {'error': 'Capsule request blocked; reconcile without replay'}
                client.sendall(old.encoded(reply)+b'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--config', default=CONFIG)
    serve(parser.parse_args().config)
