"""Finite prepared capsule slots, independently consumed by native clicks.

The old Screening grant remains separate. Slot revisions bind Root prepared
sessions, never the changing global public tree. Browser requests carry only
target/revision/client request; each slot retains the original durable journal.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import stat
import struct
import threading

from . import cc_rsi_development as old
from .cc_rsi_projection import ProjectionError, _fields, _hash

POLICY = 'ai4r-cc-rsi-capsule-policy:1'
PROTOCOL = 'ai4r-cc-rsi-capsule:1'
SOCKET = '/run/ai4r-cc-rsi-development/capsule.sock'
GATEWAY_CONFIG = '/etc/ai4r/cc-rsi-capsule-gateway.json'


def policy(value):
    _fields(value, 'schema workspace_id origin actors gateway_key_id slots')
    if value['schema'] != POLICY or not isinstance(value['slots'], list) or not 1 <= len(value['slots']) <= 16:
        raise ProjectionError('Finite installed capsule policy required')
    seen = set()
    for slot in value['slots']:
        _fields(slot, 'target_id revision run_id')
        if slot['target_id'] not in {'utility.calculate', 'utility.table_normalize'} or slot['target_id'] in seen:
            raise ProjectionError('Distinct evaluated capsule slots required')
        seen.add(slot['target_id'])
        if not isinstance(slot['run_id'], str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', slot['run_id']) is None:
            raise ProjectionError('Finite prepared session identity required')
        old.policy(slot_policy(value, slot))
    if len({row['run_id'] for row in value['slots']}) != len(value['slots']):
        raise ProjectionError('Distinct prepared session identities required')
    return value


def slot_policy(value, slot):
    return {key: value[key] for key in ('workspace_id', 'origin', 'actors', 'gateway_key_id')} | {
        'schema': old.POLICY, **slot}


class InstalledCapsuleClient(old.InstalledDevelopmentClient):
    def exchange(self, value):
        endpoint = Path(SOCKET)
        for parent in endpoint.parents:
            meta = parent.lstat()
            if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
                raise ProjectionError('Capsule broker ancestry differs')
        meta = endpoint.lstat()
        if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != 0 or meta.st_gid != 10001 or stat.S_IMODE(meta.st_mode) != 0o660:
            raise ProjectionError('Capsule broker custody differs')
        raw = old.encoded(value)
        if len(raw) > old.MAX_FRAME: raise ProjectionError('Capsule request exceeds finite bound')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(45); client.connect(SOCKET)
            _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != 0: raise ProjectionError('Capsule broker peer differs')
            client.sendall(raw + b'\n'); response = bytearray()
            while not response.endswith(b'\n'):
                part = client.recv(min(4096, old.MAX_FRAME + 1 - len(response)))
                if not part or len(response) + len(part) > old.MAX_FRAME:
                    raise ProjectionError('Capsule acknowledgement unavailable; reconcile without replay')
                response.extend(part)
        reply = json.loads(response)
        if isinstance(reply, dict) and set(reply) == {'error'}:
            raise ProjectionError('Capsule broker refused; reconcile without replay')
        return reply

    def status(self): return self.exchange({'protocol': PROTOCOL, 'operation': 'status'})
    def start(self, params, assertion):
        return old.acknowledgement(self.exchange({'protocol': PROTOCOL, 'operation': 'start',
            'params': old.request(params), 'assertion': assertion}), params)


class NativeCapsuleAdapter:
    def __init__(self, authority, signer, client, installed_policy):
        self.policy = copy.deepcopy(policy(installed_policy))
        if self.policy['origin'] != authority.origin: raise ProjectionError('Native capsule origin differs')
        self.authority, self.signer, self.client = authority, signer, client
        self.slots = {row['target_id']: row for row in self.policy['slots']}

    def owns(self, target_id): return target_id in self.slots

    async def execute(self, headers, params):
        old.request(params)
        slot = self.slots.get(params['target_id'])
        if slot is None: raise ProjectionError('No installed prepared capsule slot')
        adapter = old.NativeDevelopmentAdapter(self.authority, self.signer, self.client, slot_policy(self.policy, slot))
        return await adapter.execute(headers, params)

    async def readiness(self, headers):
        principal = self.authority.authenticate_ws(headers, 'status')
        if self.policy['workspace_id'] not in principal.workspace_ids:
            raise ProjectionError('Native capsule workspace differs')
        rows = {key: {'revision': slot['revision'], 'run_id': slot['run_id'], 'run': {
            'allowed': False, 'blocker': 'Prepared capsule readiness is unavailable', 'revision': slot['revision']}} for key, slot in self.slots.items()}
        if principal.account_id not in self.policy['actors']: return rows
        try:
            status = await asyncio.to_thread(self.client.status)
            _fields(status, 'schema slots')
            if status['schema'] != 'ai4r-cc-rsi-capsule-status:1' or len(status['slots']) != len(self.slots):
                raise ProjectionError('Capsule readiness set differs')
            seen = set()
            validated = {}
            for row in status['slots']:
                target = row['target_id']
                if target not in self.slots or target in seen: raise ProjectionError('Capsule readiness target differs')
                old.validate_status(row, slot_policy(self.policy, self.slots[target])); seen.add(target)
                validated[target] = {'allowed': row['ready'], 'blocker': row['blocker'], 'revision': self.slots[target]['revision']}
            for target, gate in validated.items(): rows[target]['run'] = gate
        except (ProjectionError, OSError, ValueError, TypeError, KeyError): pass
        return rows

    async def snapshot(self, headers, params, *, base):
        view = copy.deepcopy(base)
        rows = await self.readiness(headers)
        for target in view.get('targets', []):
            if target['id'] in rows:
                row = rows[target['id']]
                target['run'] = dict(row['run'], revision=row['revision'])
        return view


class RootCapsuleEngine:
    def __init__(self, installed_policy, public_key, slots):
        self.policy = copy.deepcopy(policy(installed_policy)); self.lock = threading.RLock()
        self.engines = {}
        for slot in self.policy['slots']:
            journal, preflight, launch = slots[slot['target_id']]
            self.engines[slot['target_id']] = old.RootDevelopmentEngine(slot_policy(self.policy, slot), public_key,
                journal, preflight, launch)

    def handle(self, value):
        with self.lock:
            if value.get('operation') == 'status':
                _fields(value, 'protocol operation')
                if value['protocol'] != PROTOCOL: raise ProjectionError('Capsule protocol differs')
                return {'schema': 'ai4r-cc-rsi-capsule-status:1', 'slots': [engine.status() for engine in self.engines.values()]}
            _fields(value, 'protocol operation params assertion')
            if value['protocol'] != PROTOCOL or value['operation'] != 'start': raise ProjectionError('Capsule protocol differs')
            old.request(value['params'])
            engine = self.engines.get(value['params']['target_id'])
            if engine is None: raise ProjectionError('No installed prepared capsule slot')
            return engine.start(value['params'], value['assertion'])


def load_native_capsules(authority, workspace_id):
    from .cc_rsi_installation import protected_bytes
    if not os.path.lexists(GATEWAY_CONFIG): return None
    value = json.loads(protected_bytes(GATEWAY_CONFIG, uid=0, mode=0o440))
    _fields(value, 'schema policy gateway_public_key module_sha256')
    if (value['schema'] != 'ai4r-cc-rsi-capsule-gateway:1' or os.geteuid() != 10001 or os.getegid() != 10001
            or value['module_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            or policy(value['policy'])['workspace_id'] != workspace_id
            or os.environ.get('JIUWENSWARM_CC_RSI_WORKSPACE') != workspace_id
            or os.environ.get('JIUWENSWARM_CC_RSI_PUBLICATION') != old.PUBLICATION):
        raise ProjectionError('Capsule gateway installation differs')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from jiuwenswarm.research_rsi.signing import Signer
    secret = protected_bytes(old.GATEWAY_KEY, uid=10001, mode=0o400, limit=32)
    if len(secret) != 32: raise ProjectionError('Existing dedicated gateway key required')
    signer = Signer(Ed25519PrivateKey.from_private_bytes(secret), value['policy']['gateway_key_id'])
    if base64.urlsafe_b64encode(signer.public_bytes()).decode().rstrip('=') != value['gateway_public_key']:
        raise ProjectionError('Capsule gateway signing key differs')
    return NativeCapsuleAdapter(authority, signer, InstalledCapsuleClient(), value['policy'])
