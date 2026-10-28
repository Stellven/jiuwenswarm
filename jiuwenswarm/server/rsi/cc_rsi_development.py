"""One explicitly installed, unqualified development run from a native click.

This protocol has no Library operation, arbitrary command, model or path field.
Root installs a finite launcher and a reviewed plan; the web process can only
request that exact run once. Interrupted delivery never creates a second run.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import threading
import time

from .cc_rsi_projection import CcRsiProjection, ProjectionError, _fields, _hash, _ref, _text

PROTOCOL = 'ai4r-cc-rsi-development:1'
ASSERTION = 'ai4r-cc-rsi-native-development-click:1'
POLICY = 'ai4r-cc-rsi-development-policy:1'
SOCKET = '/run/ai4r-cc-rsi-development/broker.sock'
GATEWAY_CONFIG = '/etc/ai4r/cc-rsi-development-gateway.json'
GATEWAY_KEY = '/etc/ai4r/cc-rsi-development-gateway.key'
PUBLICATION = '/run/ai4r-rsi-ui/publication.json'
MAX_FRAME = 16384


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def request(value):
    _fields(value, 'target_id revision client_request_id')
    for field in ('target_id', 'client_request_id'):
        if not isinstance(value[field], str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:._-]{0,159}', value[field]) is None:
            raise ProjectionError('Exact finite development identity required')
    _hash(value['revision'])
    return value


def policy(value):
    _fields(value, 'schema workspace_id origin actors gateway_key_id target_id revision run_id')
    if value['schema'] != POLICY: raise ProjectionError('Unknown development policy')
    for key in ('workspace_id', 'origin', 'gateway_key_id', 'target_id', 'run_id'):
        _text(value[key])
        if not value[key]: raise ProjectionError('Installed development identity required')
    if not isinstance(value['actors'], list) or not value['actors'] or len(value['actors']) > 16 or len(set(value['actors'])) != len(value['actors']):
        raise ProjectionError('Finite native development accounts required')
    for actor in value['actors']: _text(actor)
    _hash(value['revision'])
    return value


def acknowledgement(value, params, run_id=None):
    _fields(value, 'client_request_id target_id revision run_id status security_status receipt_ref')
    if (any(value[key] != params[key] for key in params)
            or value['status'] != 'ACCEPTED_UNQUALIFIED' or value['security_status'] != 'SECURITY_DEFERRED'
            or not isinstance(value['run_id'], str) or not value['run_id']
            or run_id is not None and value['run_id'] != run_id):
        raise ProjectionError('Development acknowledgement differs; reconcile without replay')
    _ref(value['receipt_ref'])
    return value


class InstalledDevelopmentClient:
    def exchange(self, value):
        from .cc_rsi_installation import protected_bytes
        # Check every ancestor, including the run directory's ancestors.
        endpoint = Path(SOCKET)
        for parent in endpoint.parents:
            meta = parent.lstat()
            if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
                raise ProjectionError('Development broker ancestry differs')
        meta = endpoint.lstat()
        if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != 0 or meta.st_gid != 10001 or stat.S_IMODE(meta.st_mode) != 0o660:
            raise ProjectionError('Development broker custody differs')
        raw = encoded(value)
        if len(raw) > MAX_FRAME: raise ProjectionError('Development request exceeds bound')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(30)
            client.connect(SOCKET)
            _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != 0: raise ProjectionError('Development broker peer differs')
            client.sendall(raw + b'\n')
            response = bytearray()
            while not response.endswith(b'\n'):
                part = client.recv(min(4096, MAX_FRAME + 1 - len(response)))
                if not part or len(response) + len(part) > MAX_FRAME:
                    raise ProjectionError('Development acknowledgement unavailable; reconcile without replay')
                response.extend(part)
        reply = json.loads(response)
        if isinstance(reply, dict) and set(reply) == {'error'}: raise ProjectionError('Development broker refused; reconcile without replay')
        return reply

    def status(self): return self.exchange({'protocol': PROTOCOL, 'operation': 'status'})
    def start(self, params, assertion):
        return acknowledgement(self.exchange({'protocol': PROTOCOL, 'operation': 'start',
                                              'params': request(params), 'assertion': assertion}), params)


class NativeDevelopmentAdapter:
    def __init__(self, authority, signer, client, installed_policy, *, projection=None, clock=time.time):
        self.policy = copy.deepcopy(policy(installed_policy))
        if self.policy['origin'] != authority.origin: raise ProjectionError('Native development origin differs')
        self.authority, self.signer, self.client, self.clock = authority, signer, client, clock
        self.projection = projection or CcRsiProjection(PUBLICATION, workspace_id=self.policy['workspace_id'])

    def principal(self, headers):
        from jiuwenswarm.research.contracts import ResearchError
        principal = self.authority.authenticate_ws(headers, 'status')
        if self.policy['workspace_id'] not in principal.workspace_ids:
            raise ResearchError('auth', 'The native session cannot access this development workspace', {'http_status': 403})
        return principal

    async def execute(self, headers, params):
        principal = self.principal(headers)
        request(params)
        if (principal.account_id not in self.policy['actors'] or params['target_id'] != self.policy['target_id']
                or params['revision'] != self.policy['revision']):
            raise ProjectionError('No installed development grant for this exact target revision')
        now = int(self.clock())
        assertion = self.signer.sign({'schema': ASSERTION, 'actor': principal.account_id,
            'workspace_id': self.policy['workspace_id'], 'origin': self.policy['origin'],
            **params, 'issued_at': now, 'expires_at': now + 30})
        result = await asyncio.to_thread(self.client.start, params, assertion)
        return acknowledgement(result, params, self.policy['run_id'])

    async def snapshot(self, headers, params, *, base=None):
        principal = self.principal(headers)
        view = copy.deepcopy(base if base is not None else self.projection.snapshot(params))
        # Publication is data, never an authorization. Status comes from Root.
        for target in view.get('targets', []):
            target['run'] = {'allowed': False, 'blocker': 'Development broker readiness is unavailable'}
        if principal.account_id not in self.policy['actors']: return view
        try:
            status = await asyncio.to_thread(self.client.status)
            validate_status(status, self.policy)
        except (ProjectionError, OSError, ValueError, TypeError, KeyError): return view
        if view.get('revision') == self.policy['revision']:
            for target in view.get('targets', []):
                if target.get('id') == self.policy['target_id']:
                    target['run'] = {'allowed': status['ready'], 'blocker': None if status['ready'] else status['blocker']}
        return view


def validate_status(value, installed_policy):
    _fields(value, 'target_id revision run_id ready phase blocker security_status')
    if (any(value[key] != installed_policy[key] for key in ('target_id', 'revision', 'run_id'))
            or type(value['ready']) is not bool or value['security_status'] != 'SECURITY_DEFERRED'
            or value['phase'] not in ('READY', 'BLOCKED', 'CLAIMED', 'LAUNCHED')
            or value['ready'] != (value['phase'] == 'READY')
            or value['ready'] and value['blocker'] is not None
            or not value['ready'] and not isinstance(value['blocker'], str)):
        raise ProjectionError('Closed development readiness required')
    return value


class RootDevelopmentEngine:
    """Callbacks are fixed installed code, not serialized or caller-selected.

    preflight reobserves the reviewed plan without effects. journal.claim is
    durable before launch; a crash thereafter is an issued, non-replayable run.
    """
    def __init__(self, installed_policy, public_key, journal, preflight, launch, *, clock=time.time):
        self.policy, self.public_key = copy.deepcopy(policy(installed_policy)), public_key
        self.journal, self.preflight, self.launch, self.clock = journal, preflight, launch, clock
        self.lock = threading.RLock()

    def status(self):
        with self.lock:
            claim = self.journal.lookup()
            phase, ready = ('LAUNCHED' if claim and claim.get('ack') else 'CLAIMED', False) if claim else ('BLOCKED', False)
            if claim is None:
                try: self.preflight(); phase, ready = 'READY', True
                except (ProjectionError, OSError, ValueError, TypeError, KeyError): pass
            return {key: self.policy[key] for key in ('target_id', 'revision', 'run_id')} | {
                'ready': ready, 'phase': phase, 'blocker': None if ready else 'An issued run cannot replay' if claim else 'Development prerequisites are unavailable',
                'security_status': 'SECURITY_DEFERRED'}

    def start(self, params, assertion):
        from jiuwenswarm.research_rsi.signing import verify
        request(params)
        _fields(assertion, 'schema actor workspace_id origin target_id revision client_request_id issued_at expires_at signer_key_id signature')
        now = int(self.clock())
        if (assertion['schema'] != ASSERTION or assertion['actor'] not in self.policy['actors']
                or any(assertion[key] != self.policy[key] for key in ('workspace_id', 'origin', 'target_id', 'revision'))
                or any(assertion[key] != params[key] for key in params)
                or type(assertion['issued_at']) is not int or type(assertion['expires_at']) is not int
                or not assertion['issued_at'] <= now < assertion['expires_at'] <= assertion['issued_at'] + 30):
            raise ProjectionError('Exact current native development assertion required')
        verify(assertion, self.public_key, self.policy['gateway_key_id'])
        with self.lock:
            old = self.journal.lookup()
            identity = {'actor': assertion['actor'], **params}
            if old is not None:
                if old['identity'] == identity and old.get('ack') is not None:
                    return acknowledgement(old['ack'], params, self.policy['run_id'])
                raise ProjectionError('Development run already issued; reconcile without replay')
            self.preflight()
            self.journal.claim(identity, assertion)
            owner = self.launch()
            receipt = self.journal.accept({'schema': 'ai4r-cc-rsi-development-launch:1',
                **identity, 'run_id': self.policy['run_id'], 'owner': owner,
                'security_status': 'SECURITY_DEFERRED'})
            ack = {**params, 'run_id': self.policy['run_id'], 'status': 'ACCEPTED_UNQUALIFIED',
                   'security_status': 'SECURITY_DEFERRED', 'receipt_ref': receipt}
            self.journal.acknowledge(ack)
            return acknowledgement(ack, params, self.policy['run_id'])

    def handle(self, value):
        if value.get('operation') == 'status':
            _fields(value, 'protocol operation')
            if value['protocol'] != PROTOCOL: raise ProjectionError('Development protocol differs')
            return self.status()
        _fields(value, 'protocol operation params assertion')
        if value['protocol'] != PROTOCOL or value['operation'] != 'start': raise ProjectionError('Development protocol differs')
        return self.start(value['params'], value['assertion'])


def load_native_development(authority, workspace_id):
    from .cc_rsi_installation import protected_bytes
    if not os.path.lexists(GATEWAY_CONFIG): return None
    if (not workspace_id or os.environ.get('JIUWENSWARM_CC_RSI_WORKSPACE') != workspace_id
            or os.environ.get('JIUWENSWARM_CC_RSI_PUBLICATION') != PUBLICATION):
        raise ProjectionError('Development publication must match the fixed native startup workspace')
    value = json.loads(protected_bytes(GATEWAY_CONFIG, uid=0, mode=0o440))
    _fields(value, 'schema policy gateway_public_key module_sha256')
    if (value['schema'] != 'ai4r-cc-rsi-development-gateway:1' or os.geteuid() != 10001 or os.getegid() != 10001
            or value['module_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            or policy(value['policy'])['workspace_id'] != workspace_id):
        raise ProjectionError('Development gateway installation differs')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from jiuwenswarm.research_rsi.signing import Signer
    secret = protected_bytes(GATEWAY_KEY, uid=10001, mode=0o400, limit=32)
    if len(secret) != 32: raise ProjectionError('Dedicated development gateway key required')
    signer = Signer(Ed25519PrivateKey.from_private_bytes(secret), value['policy']['gateway_key_id'])
    if base64.urlsafe_b64encode(signer.public_bytes()).decode().rstrip('=') != value['gateway_public_key']:
        raise ProjectionError('Development gateway signing key differs')
    return NativeDevelopmentAdapter(authority, signer, InstalledDevelopmentClient(), value['policy'])
