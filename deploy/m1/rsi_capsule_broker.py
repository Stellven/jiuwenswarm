"""Root-only capsule broker; no caller-selected command or authority.

Configuration v1 (``ai4r-cc-rsi-capsule-root:1``) installs finite strict
slots exactly as before. Configuration v2 (``:2``) pairs a v2 policy with an
explicit ``mode`` per slot: ``strict`` slots keep their pinned finite
configuration; ``durable`` slots pin a slot template and are re-prepared by
this long-lived process after every terminal run (see ``cc_rsi_capsule``).
The broker needs no rotation per run: its own configuration never changes,
revisions live in each slot's append-only ledger and per-revision journals.
"""
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
import threading
import time

from jiuwenswarm.research.cc_ui_runtime import module

installation = module('cc_rsi_installation')
CONFIG = '/etc/ai4r/cc-rsi-capsule-root.json'
ROOT = Path('/var/lib/ai4r-cc-rsi-capsules')
PREFLIGHT = 'ai4r-rsi-capsule-launch-preflight:1'
PACKAGE_PROOF = {'source_closure', 'worker_traversal', 'dispatcher'}
MONITOR_INTERVAL_S = 5


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
    durable = isinstance(value, dict) and value.get('schema') == 'ai4r-cc-rsi-capsule-root:2'
    installation._fields(value, 'schema policy gateway_public_key module base_service interpreter wrapper slots service_sha256'
                         + (' slot_module' if durable else ''))
    need(value['schema'] in ('ai4r-cc-rsi-capsule-root:1', 'ai4r-cc-rsi-capsule-root:2')
         and value['service_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'ROOT_BROKER_SOURCE_DIFFERS')
    for key in ('module', 'base_service', 'wrapper') + (('slot_module',) if durable else ()): pinned(value[key])
    for slot in value['slots']:
        if not durable:
            installation._fields(slot, 'target_id configuration launcher_configuration')
        elif slot.get('mode') == 'durable':
            installation._fields(slot, 'target_id mode template launch_margin_s max_consecutive_failures')
            pinned(slot['template']); continue
        else:
            installation._fields(slot, 'target_id mode configuration launcher_configuration')
            need(slot['mode'] == 'strict', 'EXPLICIT_CAPSULE_SLOT_MODE_REQUIRED')
        pinned(slot['configuration']); pinned(slot['launcher_configuration'])
    return value


def preflight_reply(reply, run_id, configuration_sha256):
    """The launcher's exact readiness, including its package-closure proof."""
    need(isinstance(reply, dict) and set(reply) - PACKAGE_PROOF == {'schema', 'ready', 'run_id', 'configuration_sha256'}
         and reply['schema'] == PREFLIGHT and reply['ready'] is True and reply['run_id'] == run_id
         and reply['configuration_sha256'] == configuration_sha256, 'EXACT_PREPARED_CAPSULE_NOT_READY')
    if PACKAGE_PROOF & set(reply):
        need(set(reply) >= PACKAGE_PROOF and isinstance(reply['source_closure'], dict)
             and reply['source_closure'].get('complete') is True and isinstance(reply['worker_traversal'], str),
             'PACKAGE_CLOSURE_OR_TRAVERSAL_NOT_PROVEN')
    return reply


def refusal(error):
    """Bounded last line of a fixed preflight's refusal (its reason code)."""
    stderr = getattr(error, 'stderr', None) or b''
    lines = [line for line in stderr.decode('utf8', 'replace').splitlines() if line.strip()]
    return ValueError((lines[-1] if lines else type(error).__name__)[-480:])


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


def process_alive(owner, *, proc=Path('/proc'), boot=Path('/proc/sys/kernel/random/boot_id')):
    """Exact owner identity (pid, start ticks, boot) is still running."""
    try:
        if boot.read_text().strip() != owner['boot_id']:
            return False
        text = (proc / str(owner['pid']) / 'stat').read_text()
    except (OSError, KeyError, TypeError):
        return False
    return int(text[text.rfind(')') + 2:].split()[19]) == owner['start_ticks']


def durable_terminal(journal, record, *, alive=process_alive):
    """Terminal outcome of a durable revision from retained journal evidence.

    The reaper's ``launcher-exit.json`` is authoritative. Without it, an owner
    whose exact process identity is gone (broker restarted mid-run) or a
    claim whose launch failed before any owner was recorded (the fork never
    received its start token) is terminal too. Nothing is replayed.
    """
    stopped = journal.read('launcher-exit.json')
    if stopped is not None:
        need(type(stopped['wait_status']) is int, 'ACTUAL_LAUNCHER_EXIT_REQUIRED')
        return {'exit_code': os.waitstatus_to_exitcode(stopped['wait_status']), 'reason': 'LAUNCHER_EXITED'}
    owner = journal.read('owner.json')
    claim = journal.lookup()
    if owner is None:
        if claim is not None and claim.get('ack') is None:
            return {'exit_code': None, 'reason': 'LAUNCH_FAILED_BEFORE_START'}
        return None
    if not alive(owner):
        return {'exit_code': None, 'reason': 'LAUNCHER_EXIT_UNOBSERVED'}
    return None


def compose(path=CONFIG):
    """Load pinned modules and build the Root engine (no socket yet)."""
    config = load(path)
    durable = config['schema'] == 'ai4r-cc-rsi-capsule-root:2'
    # Existing immutable service supplies durable journals and gated fork owner
    # identities; only this new namespace and fixed argv composition differ.
    base = load_module('_ai4r_capsule_base_service', config['base_service'])
    # Preserve existing old module bytes: load via already installed path.
    oldpath = '/opt/ai4r-cc-rsi-development/cc_rsi_development.py'
    oldraw = installation.protected_bytes(oldpath, uid=0, mode=0o444)
    old = load_module('_ai4r_cc_runtime.cc_rsi_development', {
        'path': oldpath, 'sha256': hashlib.sha256(oldraw).hexdigest()})
    cap = load_module('_ai4r_cc_runtime.cc_rsi_capsule', config['module'])
    slot_module = load_module('_ai4r_capsule_durable_slot', config['slot_module']) if durable else None
    cap.policy(config['policy']); base.dev = old; base.ROOT = ROOT
    need({r['target_id'] for r in config['slots']} == {r['target_id'] for r in config['policy']['slots']}
         and len(config['slots']) == len(config['policy']['slots']), 'EXACT_PREPARED_SLOT_SET_REQUIRED')
    base.pin(config['interpreter'], executable=True)

    class Launcher(base.FixedLauncher):
        def argv(self, verb):
            need(verb in ('preflight', 'run'), 'FINITE_CAPSULE_VERB_REQUIRED')
            need(load(path) == config, 'CAPSULE_INSTALLATION_CHANGED')
            base.pin(config['interpreter'], executable=True)
            pinned(self.config['launcher_configuration'])
            return [config['interpreter']['path'], '-B', config['wrapper']['path'], verb,
                    '--configuration', self.config['launcher_configuration']['path'],
                    '--configuration-sha256', self.config['launcher_configuration']['sha256']]

        def preflight(self):
            import subprocess
            try:
                result = subprocess.run(self.argv('preflight'), check=True, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, env=base.ENV)
            except subprocess.CalledProcessError as error:
                raise refusal(error) from None
            need(len(result.stdout) <= old.MAX_FRAME, 'FINITE_CAPSULE_PREFLIGHT_REQUIRED')
            preflight_reply(json.loads(result.stdout), self.config['policy']['run_id'],
                            self.config['configuration']['sha256'])

    slots = {}; journals = {}; durable_slots = []
    for item in config['slots']:
        slot = next(row for row in config['policy']['slots'] if row['target_id'] == item['target_id'])
        if cap.mode(slot) == 'durable':
            need(item['mode'] == 'durable', 'EXPLICIT_CAPSULE_SLOT_MODE_REQUIRED')
            engine = durable_slot(config, item, slot, cap, base, slot_module, Launcher)
            slots[item['target_id']] = engine; durable_slots.append(engine)
            continue
        need(item.get('mode', 'strict') == 'strict', 'EXPLICIT_CAPSULE_SLOT_MODE_REQUIRED')
        journal = base.Journal(slot['run_id'])
        launcher = Launcher(dict(item, policy=cap.slot_policy(config['policy'], slot),
            approved_plan_sha256=item['configuration']['sha256']), journal)
        slots[item['target_id']] = (journal, launcher.preflight, launcher.launch)
        journals[item['target_id']] = journal
    engine = cap.RootCapsuleEngine(config['policy'], public_key(config), slots)
    return config, cap, old, engine, journals


def public_key(config):
    public = base64.b64decode(config['gateway_public_key'] + '='*(-len(config['gateway_public_key'])%4), altchars=b'-_', validate=True)
    need(len(public) == 32, 'EXACT_PUBLIC_KEY_REQUIRED')
    return public


def durable_slot(config, item, slot, cap, base, slot_module, Launcher, *, background=True):
    """One durable slot: ledger, per-revision journals and fixed callables."""
    template_pin = item['template']
    template = slot_module.load_template(template_pin)
    need(template['target_id'] == slot['target_id'] and template['slot_id'] == slot['slot_id'],
         'DURABLE_SLOT_TEMPLATE_IDENTITY_DIFFERS')
    ledger = cap.RevisionLedger(template['state_root'], owner=0)

    def launcher(record, journal):
        policy = cap.revision_policy(config['policy'], slot['target_id'], record['revision'], record['run_id'])
        return Launcher({'target_id': slot['target_id'], 'configuration': record['configuration'],
                         'launcher_configuration': record['launcher_configuration'], 'policy': policy,
                         'approved_plan_sha256': record['configuration']['sha256']}, journal)

    def prepare(sequence, run_id):
        current = slot_module.load_template(template_pin)  # Re-read: pins derive from current files.
        restore = slot_module.file_pin(current['launcher']['restore'])['path']
        def docker(*args):
            import subprocess
            return subprocess.run(['/usr/bin/python3', '-B', restore, 'client', '/usr/bin/docker', '--host',
                'unix:///run/ai4r-rsi-docker/docker.sock', *args], check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=45, env=base.ENV).stdout
        steps = slot_module.ContainerSteps(current, current['roots']['control'], docker)
        return slot_module.prepare_revision(current, sequence, run_id, run_step=steps)

    return cap.DurableSlot(config['policy'], slot, public_key(config), ledger,
        journal=base.Journal, preflight=lambda record: launcher(record, None).preflight(),
        launch=lambda record, journal: launcher(record, journal).launch(), prepare=prepare,
        terminal=durable_terminal, launch_margin_s=item['launch_margin_s'],
        max_consecutive_failures=item['max_consecutive_failures'], background=background)


def monitor(engine, *, interval=MONITOR_INTERVAL_S, stop=None):
    """Advance durable slots without UI polling (re-prepare after terminal)."""
    while stop is None or not stop.is_set():
        try:
            engine.tick()
        except Exception:
            pass  # Recorded state is unchanged; the next tick or status retries reading it.
        time.sleep(interval)


def serve(path=CONFIG):
    config, cap, old, engine, journals = compose(path)
    if config['schema'] == 'ai4r-cc-rsi-capsule-root:2':
        threading.Thread(target=monitor, args=(engine,), name='durable-slot-monitor', daemon=True).start()
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
                                          if row['target_id'] in journals else row for row in reply['slots']]
                except Exception: reply = {'error': 'Capsule request blocked; reconcile without replay'}
                client.sendall(old.encoded(reply)+b'\n')


def resume(path, target_id):
    """Explicit Root resume of a FAILED durable slot; appends one record."""
    config = load(path)
    need(config['schema'] == 'ai4r-cc-rsi-capsule-root:2', 'DURABLE_CONFIGURATION_REQUIRED')
    cap = load_module('_ai4r_cc_runtime.cc_rsi_capsule', config['module'])
    slot_module = load_module('_ai4r_capsule_durable_slot', config['slot_module'])
    item = next((row for row in config['slots'] if row['target_id'] == target_id and row.get('mode') == 'durable'), None)
    need(item is not None, 'INSTALLED_DURABLE_SLOT_REQUIRED')
    slot = next(row for row in config['policy']['slots'] if row['target_id'] == target_id)
    template = slot_module.load_template(item['template'])
    unused = lambda *args, **kwargs: need(False, 'RESUME_NEVER_LAUNCHES_OR_PREPARES')
    engine = cap.DurableSlot(config['policy'], slot, public_key(config), cap.RevisionLedger(template['state_root'], owner=0),
        journal=unused, preflight=unused, launch=unused, prepare=unused)
    return engine.resume()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', nargs='?', choices=('serve', 'resume'), default='serve')
    parser.add_argument('--config', default=CONFIG)
    parser.add_argument('--target')
    args = parser.parse_args()
    if args.operation == 'resume':
        print(json.dumps(resume(args.config, args.target), sort_keys=True))
    else:
        serve(args.config)
