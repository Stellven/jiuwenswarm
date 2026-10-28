"""Trusted native authentication adapter and finite Root broker decision engine.

These are installation components, never enabled by a browser parameter or an
environment-only switch. The installer must delegate a dedicated gateway signing
key, pin its public key and operator accounts in Root policy, and supply the
existing protected Library preflight/executor. No app role gains Library rights.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import socket
import stat
import struct
import threading
import time
import uuid

from .cc_rsi_broker import HumanActionAuthorization
from .cc_rsi_projection import ProjectionError, _fields, _hash, _ref, _text

ASSERTION = 'ai4r-cc-rsi-native-human-action:1'


def load_root_operator_config(path='/etc/ai4r/cc-rsi-operator.json'):
    """An explicit installed Root grant; never read browser/Settings config."""
    if os.name != 'posix' or os.geteuid() != 0:
        raise ProjectionError('Separate installed Linux OS Root operator required')
    for parent in Path(path).parents:
        meta = parent.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ProjectionError('Root CC operator configuration ancestry differs')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_size > 262144:
            raise ProjectionError('Root CC operator configuration custody differs')
        with os.fdopen(fd, 'rb', closefd=False) as stream: value = json.loads(stream.read(262145))
    finally: os.close(fd)
    if not isinstance(value,dict): raise ProjectionError('Closed Root CC operator configuration required')
    fields = 'schema policy gateway_public_key gateway_uid socket_gid'
    if value.get('schema') == 'ai4r-cc-rsi-root-operator-installation:2': fields += ' library'
    _fields(value, fields)
    if value['schema'] not in ('ai4r-cc-rsi-root-operator-installation:1', 'ai4r-cc-rsi-root-operator-installation:2'):
        raise ProjectionError('Unknown Root CC operator installation')
    validate_operator_policy(value['policy'])
    key = base64.b64decode(value['gateway_public_key'] + '=' * (-len(value['gateway_public_key']) % 4), altchars=b'-_', validate=True)
    if len(key) != 32 or type(value['gateway_uid']) is not int or value['gateway_uid'] <= 0 or type(value['socket_gid']) is not int or value['socket_gid'] <= 0:
        raise ProjectionError('Pinned dedicated gateway identity and public key required')
    return value, key


class RootOperatorJournal:
    """Durable Root-only claims/receipts; interrupted effects never replay."""
    def __init__(self):
        if os.name != 'posix' or os.geteuid() != 0:
            raise ProjectionError('Separate installed Linux OS Root journal required')
        self.root = Path('/var/lib/ai4r-cc-rsi-operator')
        self.root.mkdir(mode=0o700, exist_ok=True)
        for path in (self.root, *self.root.parents):
            meta = path.lstat()
            if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
                raise ProjectionError('Root operator journal directory custody differs')
        if stat.S_IMODE(self.root.stat().st_mode) != 0o700:
            raise ProjectionError('Root operator journal must be private')
        database = self.root / 'actions.sqlite'
        if database.exists() or database.is_symlink():
            meta = database.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600:
                raise ProjectionError('Root operator journal file custody differs')
        self.db = sqlite3.connect(database, isolation_level=None, check_same_thread=False)
        os.chmod(database, 0o600)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS actions (identity TEXT PRIMARY KEY, claim TEXT NOT NULL, receipt TEXT)')
        self.lock = threading.RLock()

    def lookup(self, identity):
        with self.lock:
            row = self.db.execute('SELECT claim,receipt FROM actions WHERE identity=?', (identity,)).fetchone()
            return None if row is None else {'claim': json.loads(row[0]),
                                            'receipt': json.loads(row[1]) if row[1] is not None else None}

    def claim(self, identity, record):
        with self.lock:
            try: self.db.execute('INSERT INTO actions VALUES(?,?,NULL)', (identity, json.dumps(record, sort_keys=True)))
            except sqlite3.IntegrityError:
                raise ProjectionError('Exact human action was already issued; reconcile without replay') from None

    def complete(self, identity, record):
        raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
        digest = hashlib.sha256(raw).hexdigest(); target = self.root / (digest + '.json')
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        return {'id': 'cc-human-receipt:' + digest, 'sha256': digest}

    def acknowledge(self, identity, receipt):
        with self.lock:
            changed = self.db.execute('UPDATE actions SET receipt=? WHERE identity=? AND receipt IS NULL',
                (json.dumps(receipt, sort_keys=True), identity)).rowcount
            if changed != 1: raise ProjectionError('Root operator receipt state differs')

    def close(self):
        self.db.close()


class NativeCcOperatorAdapter:
    """Sign only a freshly authenticated native SessionAuthority principal.

    `operator_accounts` and the key are supplied by trusted installation, never
    from Settings, browser payloads, user_id or ordinary account login metadata.
    The independent Root broker repeats role, exact subject and signature checks.
    """
    def __init__(self, authority, signer, client, operator_accounts, *, clock=time.time, workspace_id=None):
        self.authority, self.signer, self.client = authority, signer, client
        self.accounts, self.clock = operator_accounts, clock
        self.pending = {}
        self.workspace_id = workspace_id

    async def execute(self, headers, params):
        from jiuwenswarm.research.contracts import ResearchError
        principal = self.authority.authenticate_ws(headers, 'status')
        if self.workspace_id is not None and self.workspace_id not in principal.workspace_ids:
            raise ResearchError('auth', 'The current native session cannot operate this Library workspace', {'http_status': 403})
        if not isinstance(params, dict) or set(params) != {'action', 'node_id', 'candidate_hash'}:
            raise ResearchError('validation', 'Only an exact capsule action is supported')
        action, node, digest = params['action'], params['node_id'], params['candidate_hash']
        if action not in ('admit', 'activate') or action not in self.accounts.get(principal.account_id, ()):
            raise ResearchError('auth', 'The native account has no installed CC operator grant', {'http_status': 403})
        try:
            _text(node); _hash(digest)
        except ProjectionError:
            raise ResearchError('validation', 'An exact capsule identity is required') from None
        key = (principal.account_id, action, node, digest)
        # Retain the same human action identity after uncertain delivery. The
        # Root journal also refuses any repeat effect for this candidate/action,
        # including requests from another independently authenticated operator.
        action_id = self.pending.setdefault(key, 'cc-human:' + uuid.uuid4().hex)
        now = int(self.clock())
        payload = {'schema': ASSERTION, 'actor': principal.account_id, 'action': action,
            'node_id': node, 'candidate_hash': digest, 'action_id': action_id,
            'origin': self.authority.origin, 'issued_at': now, 'expires_at': now + 30}
        if self.workspace_id is not None: payload['workspace_id'] = self.workspace_id
        assertion = self.signer.sign(payload)
        proof = base64.urlsafe_b64encode(json.dumps(assertion, sort_keys=True, separators=(',', ':')).encode()).decode()
        try:
            return await asyncio.to_thread(self.client.execute, action, node, digest,
                HumanActionAuthorization(principal.account_id, action_id, proof))
        except (ProjectionError, OSError, ValueError):
            raise ResearchError('unavailable', 'Protected operator acknowledgement unavailable; reconcile this exact action before retrying.') from None


def validate_operator_policy(policy):
    if not isinstance(policy,dict): raise ProjectionError('Closed Root operator policy required')
    fields = 'schema revision origin gateway_key_id operators candidates'
    if policy.get('schema') == 'ai4r-cc-rsi-root-operator-policy:2': fields += ' workspace_id'
    _fields(policy, fields)
    if policy['schema'] not in ('ai4r-cc-rsi-root-operator-policy:1', 'ai4r-cc-rsi-root-operator-policy:2'):
        raise ProjectionError('Unknown Root CC operator policy')
    if 'workspace_id' in policy:
        _text(policy['workspace_id'])
        if not policy['workspace_id']: raise ProjectionError('Exact Library workspace required')
    for key in ('revision', 'origin', 'gateway_key_id'): _text(policy[key])
    if not isinstance(policy['operators'], dict) or len(policy['operators']) > 64:
        raise ProjectionError('Finite Root operator grant required')
    for actor, actions in policy['operators'].items():
        _text(actor)
        if not isinstance(actions, list) or not actions or set(actions) - {'admit', 'activate'}:
            raise ProjectionError('Unknown Root operator role')
    if not isinstance(policy['candidates'], dict) or len(policy['candidates']) > 512:
        raise ProjectionError('Finite exact candidate grants required')
    for digest, row in policy['candidates'].items():
        _hash(digest); _fields(row, 'node_id admit_request_ref activate_request_ref'); _text(row['node_id'])
        for key in ('admit_request_ref', 'activate_request_ref'):
            if row[key] is not None: _ref(row[key])
    return policy


class RootOperatorEngine:
    """Finite engine for a separately installed Root Unix authority.

    `journal` owns durable claim/complete/lookup operations under OS Root.
    `preflight` checks actual signed package/source/qualification eligibility.
    `execute_library` maps only the Root-pinned immutable request Ref to the
    existing finite operator child with permanent UID10001 transition. Neither
    callback is selectable by a request. They must be installed, not mocks.
    """
    def __init__(self, policy, gateway_public_key, journal, preflight, execute_library, *, clock=time.time):
        self.policy = validate_operator_policy(policy)
        if not isinstance(gateway_public_key, bytes) or len(gateway_public_key) != 32:
            raise ProjectionError('Root-pinned gateway verification key required')
        self.public_key, self.journal, self.preflight, self.execute_library = gateway_public_key, journal, preflight, execute_library
        if not callable(preflight) or not callable(execute_library):
            raise ProjectionError('Installed real Library preflight and finite operator executor required')
        self.clock = clock

    def handle(self, request):
        from jiuwenswarm.research_rsi.signing import verify
        from .cc_rsi_broker import PROTOCOL
        _fields(request, 'protocol action node_id candidate_hash authorization')
        need = lambda value: value or self._deny()
        need(request['protocol'] == PROTOCOL and request['action'] in ('admit', 'activate'))
        auth = request['authorization']; _fields(auth, 'actor action_id proof')
        for item in auth.values(): _text(item)
        _hash(request['candidate_hash']); _text(request['node_id'])
        assertion = json.loads(base64.b64decode(auth['proof'], altchars=b'-_', validate=True))
        fields = 'schema actor action node_id candidate_hash action_id origin issued_at expires_at signature signer_key_id'
        if 'workspace_id' in self.policy: fields += ' workspace_id'
        _fields(assertion, fields)
        verify(assertion, self.public_key, self.policy['gateway_key_id'])
        now = self.clock()
        need(assertion['schema'] == ASSERTION and assertion['origin'] == self.policy['origin']
             and type(assertion['issued_at']) is int and type(assertion['expires_at']) is int
             and assertion['issued_at'] <= now < assertion['expires_at'] <= assertion['issued_at'] + 30)
        if 'workspace_id' in self.policy: need(assertion['workspace_id'] == self.policy['workspace_id'])
        need(all(assertion[key] == request[key] for key in ('action', 'node_id', 'candidate_hash'))
             and all(assertion[key] == auth[key] for key in ('actor', 'action_id')))
        actor, action, digest = auth['actor'], request['action'], request['candidate_hash']
        need(action in self.policy['operators'].get(actor, ()))
        candidate = self.policy['candidates'].get(digest)
        need(candidate is not None and candidate['node_id'] == request['node_id'])
        request_ref = candidate[action + '_request_ref']; need(request_ref is not None)
        # A different actor, policy revision or request mapping cannot create a
        # second effect identity for this exact candidate/action. Claims remain
        # quarantined until reconciliation; cached receipts retain their actor.
        identity = hashlib.sha256(json.dumps([action, digest], separators=(',', ':')).encode()).hexdigest()
        prior = self.journal.lookup(identity)
        if prior is not None:
            claim = prior.get('claim')
            need(isinstance(claim, dict) and claim.get('action') == action and claim.get('candidate_hash') == digest)
            if claim.get('request_ref') != request_ref:
                raise ProjectionError('Root request mapping changed for an issued candidate action; reconcile without replay')
            if claim.get('actor') != actor:
                if prior.get('receipt') is None:
                    raise ProjectionError('Candidate action from another authenticated operator is unresolved; reconcile without replay')
                raise ProjectionError('Candidate action was already handled by another authenticated operator; reconcile its original receipt')
            if prior.get('receipt') is None:
                raise ProjectionError('Prior operator delivery is unresolved; reconcile without replay')
            receipt = prior['receipt']
            _fields(receipt, 'action node_id candidate_hash actor receipt_ref')
            need(receipt['actor'] == actor and receipt['action'] == action and receipt['candidate_hash'] == digest
                 and receipt['node_id'] == request['node_id'])
            _ref(receipt['receipt_ref'])
            return receipt
        need(self.preflight(action, digest, request_ref) is True)
        # Claim is durable before the first Library effect. Any exception leaves
        # an unresolved claim; this engine never retries or releases it.
        self.journal.claim(identity, {'actor': actor, 'action': action, 'candidate_hash': digest,
                                     'action_id': auth['action_id'], 'request_ref': request_ref})
        terminal = self.execute_library('admit-rsi' if action == 'admit' else 'standing', request_ref)
        need(isinstance(terminal, dict) and terminal.get('request_ref') == request_ref
             and terminal.get('candidate_hash') == digest and terminal.get('status') == ('admitted_inactive' if action == 'admit' else 'activated'))
        _ref(terminal['operator_receipt_ref'])
        record = {'schema': 'ai4r-cc-rsi-human-receipt:1', 'actor': actor, 'action': action, 'action_id': auth['action_id'],
                  'candidate_hash': digest, 'node_id': request['node_id'], 'operator_receipt_ref': terminal['operator_receipt_ref'],
                  'recorded_at': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                  'assertion_sha256': hashlib.sha256(json.dumps(assertion, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        acknowledgement = {'action': action, 'node_id': request['node_id'], 'candidate_hash': digest, 'actor': actor,
                           'receipt_ref': self.journal.complete(identity, record)}
        self.journal.acknowledge(identity, acknowledgement)
        return acknowledgement

    @staticmethod
    def _deny():
        raise ProjectionError('Protected human operator proof, exact candidate grant or Library eligibility unavailable')


async def serve_root_operator(engine, installation):
    """Serve only the dedicated finite Root socket after explicit composition.

    Installation must pass an engine with real Library preflight/executor.
    This does not run from AgentServer, grant app root, or install itself.
    """
    from .cc_rsi_broker import SOCKET, MAX_FRAME
    if os.name != 'posix' or os.geteuid() != 0:
        raise ProjectionError('Separate installed Linux OS Root broker required')
    if installation.get('policy') != engine.policy:
        raise ProjectionError('Root broker engine differs from installed policy')
    directory = Path(SOCKET).parent
    directory.mkdir(mode=0o755, exist_ok=True)
    for path in (directory, *directory.parents):
        meta = path.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ProjectionError('Root broker directory custody differs')
    if os.path.lexists(SOCKET):
        raise ProjectionError('Prior Root broker endpoint exists; reconcile before reinstalling')
    async def handle(reader, writer):
        try:
            peer = writer.get_extra_info('socket')
            _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != installation['gateway_uid']:
                raise ProjectionError('Caller is outside the installed native gateway identity')
            raw = await asyncio.wait_for(reader.readuntil(b'\n'), 10)
            if len(raw) > MAX_FRAME:
                raise ProjectionError('Finite operator frame exceeded')
            request = json.loads(raw)
            receipt = await asyncio.to_thread(engine.handle, request)
            writer.write(json.dumps(receipt, separators=(',', ':'), allow_nan=False).encode() + b'\n')
            await writer.drain()
        except Exception:
            # No private path, auth proof, Library error or account packet is
            # reflected to the caller. The journal retains uncertain issuance.
            writer.write(b'{"error":"operator_acknowledgement_unavailable"}\n')
            try: await writer.drain()
            except (ConnectionError, OSError): pass
        finally:
            writer.close()
            await writer.wait_closed()
    server = await asyncio.start_unix_server(handle, path=SOCKET, limit=MAX_FRAME, start_serving=False)
    os.chown(SOCKET, 0, installation['socket_gid']); os.chmod(SOCKET, 0o660)
    await server.start_serving()
    return server
