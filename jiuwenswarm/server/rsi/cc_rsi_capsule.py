"""Prepared capsule slots, independently consumed by native clicks.

Two explicitly configured slot modes exist; neither is ever autodetected.

``strict`` (every slot of policy v1, or a v2 slot with ``mode: strict``): one
finite Root-prepared revision per installed policy entry, its finite grant and
its original durable journal. Once consumed the slot stays consumed until Root
installs a new policy (today's behaviour, unchanged).

``durable`` (v2 slot with ``mode: durable``): one Root-owned development slot
per registered capsule. Root appends revisions to an append-only ledger. Each
revision has its own new journal, run identity, grant and work contracts made
by the ordinary preparation path. After any terminal run (or an unclaimed
revision whose grant horizon could no longer cover a whole run) Root retires
that revision and prepares a successor automatically. Consumed claims remain
consumed; a successor never replays one. Grants carry no mid-run expiry: a
revision is only claimable while its horizon covers the run's own deadline.

The old Screening grant remains separate. Slot revisions bind Root prepared
sessions, never the changing global public tree. Browser requests carry only
target/revision/client request and are signed with the existing gateway key.
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
import time

from . import cc_rsi_development as old
from .cc_rsi_projection import ProjectionError, _fields, _hash

POLICY = 'ai4r-cc-rsi-capsule-policy:1'
POLICY_V2 = 'ai4r-cc-rsi-capsule-policy:2'
PROTOCOL = 'ai4r-cc-rsi-capsule:1'
STATUS = 'ai4r-cc-rsi-capsule-status:1'
STATUS_V2 = 'ai4r-cc-rsi-capsule-status:2'
REVISION = 'ai4r-cc-rsi-capsule-durable-revision:1'
LEDGER = 'ai4r-cc-rsi-capsule-durable-ledger:1'
SOCKET = '/run/ai4r-cc-rsi-development/capsule.sock'
GATEWAY_CONFIG = '/etc/ai4r/cc-rsi-capsule-gateway.json'
MODES = ('durable', 'strict')
PHASES = ('READY', 'BLOCKED', 'CLAIMED', 'LAUNCHED', 'PREPARING', 'FAILED')
RUN_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
SLOT_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
LEDGER_KINDS = ('preparing', 'prepared', 'failed', 'retired', 'resumed')
UNAVAILABLE = 'Prepared capsule readiness is unavailable'
READINESS_STALE = 'READINESS_STALE'
READINESS_PENDING = 'READINESS_PENDING'
OBSERVATION = ('observed_unix_s', 'age_s')
# Configurable bounds (seconds); the defaults are the historical fixed values.
# ``click_window_s`` is the signed click's own validity from signing, checked
# at Root receipt; the gateway's window must not exceed the broker's.
GATEWAY_TIMEOUTS = {'exchange_s': 45, 'click_window_s': 30}
BROKER_TIMEOUTS = {'preflight_s': 45, 'request_s': 45, 'click_window_s': 30,
                   'readiness_refresh_s': 30, 'readiness_stale_s': 120}


def timeouts(value, defaults):
    """Closed, finite overrides of ``defaults``; a missing key keeps it."""
    if (not isinstance(value, dict) or not set(value) <= set(defaults)
            or any(type(item) is not int or not 1 <= item <= 3600 for item in value.values())):
        raise ProjectionError('Closed finite capsule timeouts required')
    result = {**defaults, **value}
    if 'readiness_stale_s' in result and result['readiness_stale_s'] < result['readiness_refresh_s']:
        raise ProjectionError('Readiness staleness bound must cover one refresh interval')
    return result


def _evaluable(target_id):
    """Any registered capsule with public evaluation; Builder etc. stay out."""
    if not isinstance(target_id, str) or not 0 < len(target_id) <= 160:
        raise ProjectionError('Distinct evaluated capsule slots required')
    try:
        from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
        target = registered_capsule(target_id)
    except Exception:
        raise ProjectionError('Distinct evaluated capsule slots required') from None
    if not getattr(target, 'public_evaluation_available', False):
        raise ProjectionError('Distinct evaluated capsule slots required')


def mode(slot):
    return slot.get('mode', 'strict')


def policy(value):
    if not isinstance(value, dict) or value.get('schema') not in (POLICY, POLICY_V2):
        raise ProjectionError('Finite installed capsule policy required')
    _fields(value, 'schema workspace_id origin actors gateway_key_id slots')
    if not isinstance(value['slots'], list) or not 1 <= len(value['slots']) <= 16:
        raise ProjectionError('Finite installed capsule policy required')
    seen, runs = set(), set()
    for slot in value['slots']:
        if value['schema'] == POLICY:
            _fields(slot, 'target_id revision run_id')
        elif isinstance(slot, dict) and slot.get('mode') == 'strict':
            _fields(slot, 'target_id mode revision run_id')
        elif isinstance(slot, dict) and slot.get('mode') == 'durable':
            _fields(slot, 'target_id mode slot_id')
        else:
            raise ProjectionError('Explicit capsule slot mode required')
        if slot['target_id'] in seen:
            raise ProjectionError('Distinct evaluated capsule slots required')
        _evaluable(slot['target_id'])
        seen.add(slot['target_id'])
        if mode(slot) == 'strict':
            if not isinstance(slot['run_id'], str) or RUN_ID.fullmatch(slot['run_id']) is None:
                raise ProjectionError('Finite prepared session identity required')
            runs.add(slot['run_id'])
            old.policy(slot_policy(value, slot))
        else:
            if not isinstance(slot['slot_id'], str) or SLOT_ID.fullmatch(slot['slot_id']) is None:
                raise ProjectionError('Durable slot identity required')
            runs.add('durable:' + slot['slot_id'])
            old.policy(revision_policy(value, slot['target_id'], '0' * 64, slot['slot_id'] + '-r1'))
    if len(runs) != len(value['slots']):
        raise ProjectionError('Distinct prepared session identities required')
    return value


def slot_policy(value, slot):
    """The existing single-revision development policy of a strict slot."""
    return revision_policy(value, slot['target_id'], slot['revision'], slot['run_id'])


def revision_policy(value, target_id, revision, run_id):
    return {key: value[key] for key in ('workspace_id', 'origin', 'actors', 'gateway_key_id')} | {
        'schema': old.POLICY, 'target_id': target_id, 'revision': revision, 'run_id': run_id}


def durable_run_id(slot_id, sequence):
    run_id = slot_id + '-r' + str(sequence)
    if type(sequence) is not int or sequence < 1 or RUN_ID.fullmatch(run_id) is None:
        raise ProjectionError('Finite durable revision identity required')
    return run_id


def validate_slot_status(value, installed_policy, slot):
    """Closed v2 readiness row for one installed slot (strict or durable).

    A cached Root observation also carries ``observed_unix_s`` and ``age_s``
    (both integers, or both null when Root has not observed the slot yet)."""
    base = 'target_id mode revision run_id sequence ready phase blocker security_status'
    _fields(value, base + (' observed_unix_s age_s' if isinstance(value, dict) and 'observed_unix_s' in value else ''))
    if 'observed_unix_s' in value and not (
            value['observed_unix_s'] is None is value['age_s']
            or type(value['observed_unix_s']) is int and type(value['age_s']) is int and value['age_s'] >= 0):
        raise ProjectionError('Closed capsule readiness observation required')
    if (value['target_id'] != slot['target_id'] or value['mode'] != mode(slot)
            or type(value['ready']) is not bool or value['security_status'] != 'SECURITY_DEFERRED'
            or value['phase'] not in PHASES or value['ready'] != (value['phase'] == 'READY')
            or value['ready'] and value['blocker'] is not None
            or not value['ready'] and (not isinstance(value['blocker'], str) or len(value['blocker']) > 1024)):
        raise ProjectionError('Closed capsule readiness required')
    if mode(slot) == 'strict':
        if value['revision'] != slot['revision'] or value['run_id'] != slot['run_id'] or value['sequence'] is not None:
            raise ProjectionError('Strict capsule readiness differs')
        return value
    known = [value[key] is not None for key in ('revision', 'run_id', 'sequence')]
    if any(known) and not all(known):
        raise ProjectionError('Durable revision identity is incomplete')
    if all(known):
        _hash(value['revision'])
        if value['run_id'] != durable_run_id(slot['slot_id'], value['sequence']):
            raise ProjectionError('Durable revision identity differs')
    elif value['phase'] in ('READY', 'CLAIMED', 'LAUNCHED'):
        raise ProjectionError('Active durable phase requires a revision')
    return value


class InstalledCapsuleClient(old.InstalledDevelopmentClient):
    def __init__(self, *, timeout_s=GATEWAY_TIMEOUTS['exchange_s']):
        self.timeout_s = timeouts({'exchange_s': timeout_s}, GATEWAY_TIMEOUTS)['exchange_s']

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
            client.settimeout(self.timeout_s); client.connect(SOCKET)
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
    def __init__(self, authority, signer, client, installed_policy, *, click_window_s=GATEWAY_TIMEOUTS['click_window_s']):
        self.policy = copy.deepcopy(policy(installed_policy))
        if self.policy['origin'] != authority.origin: raise ProjectionError('Native capsule origin differs')
        self.authority, self.signer, self.client = authority, signer, client
        self.click_window_s = timeouts({'click_window_s': click_window_s}, GATEWAY_TIMEOUTS)['click_window_s']
        self.slots = {row['target_id']: row for row in self.policy['slots']}

    def owns(self, target_id): return target_id in self.slots

    async def status_rows(self):
        """Root status, validated against the installed slot set."""
        status = await asyncio.to_thread(self.client.status)
        v2 = self.policy['schema'] == POLICY_V2
        _fields(status, 'schema slots')
        if status['schema'] != (STATUS_V2 if v2 else STATUS) or len(status['slots']) != len(self.slots):
            raise ProjectionError('Capsule readiness set differs')
        rows = {}
        for row in status['slots']:
            target = row.get('target_id') if isinstance(row, dict) else None
            if target not in self.slots or target in rows: raise ProjectionError('Capsule readiness target differs')
            slot = self.slots[target]
            if v2:
                rows[target] = validate_slot_status(row, self.policy, slot)
            else:
                old.validate_status(row, slot_policy(self.policy, slot))
                rows[target] = dict(row, mode='strict', sequence=None)
        return rows

    async def execute(self, headers, params):
        old.request(params)
        slot = self.slots.get(params['target_id'])
        if slot is None: raise ProjectionError('No installed prepared capsule slot')
        if mode(slot) == 'strict':
            installed = slot_policy(self.policy, slot)
        else:
            # The current revision is Root's; Root rechecks it under its own lock.
            row = (await self.status_rows())[slot['target_id']]
            if row['phase'] not in ('READY', 'CLAIMED', 'LAUNCHED') or row['revision'] != params['revision']:
                raise ProjectionError('No ready durable revision for this exact target revision')
            installed = revision_policy(self.policy, slot['target_id'], row['revision'], row['run_id'])
        # Signed only now, after the readiness read: its window starts at the click.
        adapter = old.NativeDevelopmentAdapter(self.authority, self.signer, self.client, installed,
                                               assertion_window_s=self.click_window_s)
        return await adapter.execute(headers, params)

    def _unavailable(self, slot):
        revision = slot.get('revision') if mode(slot) == 'strict' else None
        run_id = slot.get('run_id') if mode(slot) == 'strict' else None
        gate = {'allowed': False, 'blocker': UNAVAILABLE, 'phase': 'BLOCKED'}
        if revision is not None: gate['revision'] = revision
        return {'revision': revision, 'run_id': run_id, 'mode': mode(slot), 'run': gate}

    async def readiness(self, headers):
        principal = self.authority.authenticate_ws(headers, 'status')
        if self.policy['workspace_id'] not in principal.workspace_ids:
            raise ProjectionError('Native capsule workspace differs')
        rows = {key: self._unavailable(slot) for key, slot in self.slots.items()}
        if principal.account_id not in self.policy['actors']: return rows
        try:
            status = await self.status_rows()
        except (ProjectionError, OSError, ValueError, TypeError, KeyError):
            return rows
        for target, row in status.items():
            gate = {'allowed': row['ready'], 'blocker': row['blocker'], 'phase': row['phase']}
            if row['revision'] is not None: gate['revision'] = row['revision']
            for key in OBSERVATION:  # When and how long ago Root observed this row.
                if key in row: gate[key] = row[key]
            rows[target] = {'revision': row['revision'], 'run_id': row['run_id'], 'mode': row['mode'], 'run': gate}
        return rows

    async def snapshot(self, headers, params, *, base):
        view = copy.deepcopy(base)
        rows = await self.readiness(headers)
        for target in view.get('targets', []):
            if target['id'] in rows:
                target['run'] = dict(rows[target['id']]['run'])
        return view


class RevisionLedger:
    """Append-only Root ledger of one durable slot's revisions.

    Each entry is an exclusively linked file ``<sequence>.<kind>.json``; an
    entry is never rewritten or removed, and readers never see partial bytes.
    """
    def __init__(self, root, *, owner=None):
        self.root = Path(root)
        self.owner = os.geteuid() if owner is None else owner
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        meta = self.root.lstat()
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != self.owner
                or stat.S_IMODE(meta.st_mode) != 0o700):
            raise ProjectionError('Private durable slot ledger required')

    def append(self, sequence, kind, value):
        if type(sequence) is not int or not 1 <= sequence <= 99999999 or kind not in LEDGER_KINDS:
            raise ProjectionError('Closed durable ledger entry required')
        raw = old.encoded({'schema': LEDGER, 'sequence': sequence, 'kind': kind, 'value': value})
        name = '%08d.%s.json' % (sequence, kind)
        pending = self.root / ('.pending-%d-%d-%s' % (os.getpid(), threading.get_ident(), name))
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        finally:
            os.close(fd)
        try:
            os.link(pending, self.root / name)  # Fails rather than replace an entry.
        except FileExistsError:
            raise ProjectionError('Durable ledger entry already recorded; reconcile without replay') from None
        finally:
            os.unlink(pending)
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        return {'id': 'durable-slot:' + name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def entries(self):
        rows = {}
        for path in sorted(self.root.iterdir()):
            if path.name.startswith('.'):
                continue
            match = re.fullmatch(r'(\d{8})\.([a-z]+)\.json', path.name)
            meta = path.lstat()
            if (match is None or match.group(2) not in LEDGER_KINDS or not stat.S_ISREG(meta.st_mode)
                    or meta.st_uid != self.owner or stat.S_IMODE(meta.st_mode) & 0o077 or meta.st_size > 1024 * 1024):
                raise ProjectionError('Durable ledger custody differs')
            value = json.loads(path.read_bytes())
            sequence, kind = int(match.group(1)), match.group(2)
            if value.get('schema') != LEDGER or value.get('sequence') != sequence or value.get('kind') != kind:
                raise ProjectionError('Durable ledger entry differs')
            rows.setdefault(sequence, {})[kind] = value['value']
        return rows


def _blocker(error):
    text = str(error).strip().splitlines()
    text = text[-1] if text else type(error).__name__
    return ('Development prerequisites are unavailable: ' + text)[:512]


class CapsuleRevisionEngine(old.RootDevelopmentEngine):
    """The development engine with the click validated at Root receipt.

    A signed click is valid for its own window from signing
    (``issued_at <= received < expires_at <= issued_at + window``), checked
    against the time Root received it, before any lock, readiness refresh or
    preflight can delay it. Everything else is the installed engine's.
    """
    def __init__(self, installed_policy, public_key, journal, preflight, launch, *, clock=time.time,
                 assertion_window_s=BROKER_TIMEOUTS['click_window_s']):
        super().__init__(installed_policy, public_key, journal, preflight, launch, clock=clock)
        self.window = timeouts({'click_window_s': assertion_window_s}, BROKER_TIMEOUTS)['click_window_s']

    def start(self, params, assertion, *, received=None):
        from jiuwenswarm.research_rsi.signing import verify
        old.request(params)
        _fields(assertion, 'schema actor workspace_id origin target_id revision client_request_id issued_at expires_at signer_key_id signature')
        now = int(self.clock()) if received is None else received
        if (assertion['schema'] != old.ASSERTION or assertion['actor'] not in self.policy['actors']
                or any(assertion[key] != self.policy[key] for key in ('workspace_id', 'origin', 'target_id', 'revision'))
                or any(assertion[key] != params[key] for key in params)
                or type(assertion['issued_at']) is not int or type(assertion['expires_at']) is not int
                or not assertion['issued_at'] <= now < assertion['expires_at'] <= assertion['issued_at'] + self.window):
            raise ProjectionError('Exact current native development assertion required')
        verify(assertion, self.public_key, self.policy['gateway_key_id'])
        with self.lock:
            earlier = self.journal.lookup()
            identity = {'actor': assertion['actor'], **params}
            if earlier is not None:
                if earlier['identity'] == identity and earlier.get('ack') is not None:
                    return old.acknowledgement(earlier['ack'], params, self.policy['run_id'])
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
            return old.acknowledgement(ack, params, self.policy['run_id'])


class CachedReadiness:
    """Root readiness observed off the request path.

    ``refresh`` (the slot's background thread, at ``readiness_refresh_s`` and
    right after any state transition) runs the full preflight and stores the
    row with its observation time. ``status`` (the request path) never runs a
    preflight once the slot is monitored: phases that need no preflight
    (PREPARING, FAILED, CLAIMED, LAUNCHED) are read directly; READY/BLOCKED
    come from the cached observation of the same state, with its time and age.
    An observation older than ``readiness_stale_s`` reports BLOCKED with
    ``READINESS_STALE``. Unmonitored slots refresh inline, as before.
    Subclasses provide ``phase_row() -> (row, needs_preflight, signature)``,
    ``preflight_row(row)`` and ``advance()``.
    """
    def init_readiness(self, *, clock, refresh_s, stale_s):
        limits = timeouts({'readiness_refresh_s': refresh_s, 'readiness_stale_s': stale_s},
                          {key: BROKER_TIMEOUTS[key] for key in ('readiness_refresh_s', 'readiness_stale_s')})
        self.readiness_clock = clock
        self.refresh_s, self.stale_s = limits['readiness_refresh_s'], limits['readiness_stale_s']
        self.observation = None  # (row, observed_unix_s, signature)
        self.observation_lock, self.refreshing = threading.Lock(), threading.Lock()
        self.wake = threading.Event()
        self.monitored = False

    def advance(self):
        return None

    def notify(self):
        """A state transition happened: refresh now rather than at the interval."""
        self.wake.set()

    def refresh(self):
        with self.refreshing:
            try:
                self.advance()
            except (ProjectionError, OSError, ValueError, TypeError, KeyError):
                pass  # Recorded state is unchanged; the next refresh retries.
            row, needs, signature = self.phase_row()
            if needs:
                row = self.preflight_row(row)
                if self.phase_row()[2] != signature:
                    self.notify()  # Superseded while checking; observe the new state.
            observed = int(self.readiness_clock())
            with self.observation_lock:
                self.observation = (row, observed, signature)
            return row

    def due(self):
        with self.observation_lock:
            observation = self.observation
        if observation is None or int(self.readiness_clock()) - observation[1] >= self.refresh_s:
            return True
        return self.phase_row()[2] != observation[2]

    def stale_row(self, row, reason):
        return dict(row, ready=False, phase='BLOCKED', blocker=reason[:1024])

    def status(self):
        if not self.monitored:
            self.refresh()
        row, needs, signature = self.phase_row()
        now = int(self.readiness_clock())
        if not needs:
            return dict(row, observed_unix_s=now, age_s=0)
        with self.observation_lock:
            observation = self.observation
        if observation is None:
            self.notify()
            return dict(self.stale_row(row, READINESS_STALE + ': Root has not observed this slot yet'),
                        observed_unix_s=None, age_s=None)
        cached, observed, seen = observation
        age = max(0, now - observed)
        if age > self.stale_s:
            self.notify()
            return dict(self.stale_row(cached, READINESS_STALE + ': last Root observation is %d s old (bound %d s)'
                                       % (age, self.stale_s)), observed_unix_s=observed, age_s=age)
        if seen != signature:
            self.notify()
            return dict(self.stale_row(row, READINESS_PENDING + ': Root is checking the current revision'),
                        observed_unix_s=observed, age_s=age)
        if age >= self.refresh_s:
            self.notify()
        return dict(cached, observed_unix_s=observed, age_s=age)

    def monitor(self, *, stop=None, interval=5):
        """The slot's background thread: advance state and refresh readiness."""
        self.monitored = True
        while stop is None or not stop.is_set():
            try:
                if self.due():
                    self.refresh()
                else:
                    self.advance_locked()
            except Exception:
                pass  # The cached record ages; status reports it stale, never unavailable.
            self.wake.wait(min(interval, self.refresh_s))
            self.wake.clear()

    def advance_locked(self):
        try:
            self.advance()
        except (ProjectionError, OSError, ValueError, TypeError, KeyError):
            pass


class StrictSlot(CachedReadiness):
    """Cached readiness of one finite strict slot (policy v2)."""
    def __init__(self, engine, *, mode_fields, clock=time.time, readiness_refresh_s=BROKER_TIMEOUTS['readiness_refresh_s'],
                 readiness_stale_s=BROKER_TIMEOUTS['readiness_stale_s']):
        self.engine, self.mode_fields = engine, mode_fields
        self.init_readiness(clock=clock, refresh_s=readiness_refresh_s, stale_s=readiness_stale_s)

    def phase_row(self):
        policy_ = self.engine.policy
        claim = self.engine.journal.lookup()
        row = {key: policy_[key] for key in ('target_id', 'revision', 'run_id')} | self.mode_fields | {
            'security_status': 'SECURITY_DEFERRED'}
        if claim is None:
            return row | {'ready': False, 'phase': 'BLOCKED', 'blocker': 'Development prerequisites are unavailable'}, \
                True, ('unclaimed',)
        launched = claim.get('ack') is not None
        return row | {'ready': False, 'phase': 'LAUNCHED' if launched else 'CLAIMED',
                      'blocker': 'An issued run cannot replay'}, False, ('launched' if launched else 'claimed',)

    def preflight_row(self, row):
        try:
            self.engine.preflight()
        except (ProjectionError, OSError, ValueError, TypeError, KeyError):
            return row
        return dict(row, ready=True, phase='READY', blocker=None)

    def start(self, params, assertion, *, received):
        try:
            return self.engine.start(params, assertion, received=received)
        finally:
            self.notify()


class DurableSlot(CachedReadiness):
    """Root state machine of one durable development slot.

    Phases: PREPARING (successor preparation running) -> READY (unclaimed,
    preflight passes) or BLOCKED (unclaimed, preflight refuses) -> CLAIMED
    (journal claim, no acknowledgement) -> LAUNCHED (acknowledged, launcher
    not terminal) -> terminal: the revision is retired with its outcome and a
    successor is prepared (PREPARING). FAILED: automatic preparation failed
    ``max_consecutive_failures`` times; Root must append an explicit resume.

    Collaborators are fixed installed callables, never caller-selected:
    ``journal(run_id)`` (per-revision durable journal), ``preflight(record)``,
    ``launch(record, journal)``, ``prepare(sequence, run_id)`` (the ordinary
    preparation path; returns the revision's pinned payload),
    ``terminal(journal, record)`` (None, or ``{exit_code, reason}``) and
    ``reconcile(sequence, run_id)`` (None once every preparation step
    container of that revision is proven stopped, else why one still runs).
    """
    def __init__(self, installed_policy, slot, public_key, ledger, *, journal, preflight, launch, prepare,
                 terminal=None, reconcile=None, clock=time.time, launch_margin_s=300, max_consecutive_failures=3,
                 background=True, readiness_refresh_s=BROKER_TIMEOUTS['readiness_refresh_s'],
                 readiness_stale_s=BROKER_TIMEOUTS['readiness_stale_s'],
                 click_window_s=BROKER_TIMEOUTS['click_window_s']):
        if mode(slot) != 'durable': raise ProjectionError('Durable slot configuration required')
        self.policy = copy.deepcopy(installed_policy)
        self.target_id, self.slot_id = slot['target_id'], slot['slot_id']
        self.public_key, self.ledger, self.clock = public_key, ledger, clock
        self.journal, self.preflight, self.launch, self.prepare = journal, preflight, launch, prepare
        self.terminal = terminal or self.launcher_exit
        self.reconcile, self.waiting = reconcile, None
        if type(launch_margin_s) is not int or launch_margin_s < 0 or type(max_consecutive_failures) is not int \
                or not 1 <= max_consecutive_failures <= 100:
            raise ProjectionError('Finite durable slot limits required')
        self.margin, self.max_failures, self.background = launch_margin_s, max_consecutive_failures, background
        self.click_window_s = timeouts({'click_window_s': click_window_s}, BROKER_TIMEOUTS)['click_window_s']
        self.lock = threading.RLock()
        self.worker = None
        self.init_readiness(clock=clock, refresh_s=readiness_refresh_s, stale_s=readiness_stale_s)

    @staticmethod
    def launcher_exit(journal, record):
        stopped = journal.read('launcher-exit.json')
        if stopped is None: return None
        return {'exit_code': os.waitstatus_to_exitcode(stopped['wait_status']), 'reason': 'LAUNCHER_EXITED'}

    # ---------------------------------------------------------------- ledger
    def latest(self, rows=None):
        rows = self.ledger.entries() if rows is None else rows
        if not rows: return 0, {}
        sequence = max(rows)
        return sequence, rows[sequence]

    def failures(self, rows):
        count = 0
        for sequence in sorted(rows, reverse=True):
            kinds = rows[sequence]
            if 'resumed' in kinds or 'prepared' in kinds or 'failed' not in kinds:
                break
            count += 1
        return count

    def alive(self, sequence):
        return self.worker is not None and self.worker[0] == sequence and self.worker[1].is_alive()

    def record(self, sequence, run_id, payload):
        if not isinstance(payload, dict) or {'schema', 'target_id', 'slot_id', 'sequence', 'run_id', 'revision'} & set(payload):
            raise ProjectionError('Closed prepared revision payload required')
        for key in ('expires_unix_s', 'wall_s'):
            if type(payload.get(key)) is not int or payload[key] <= 0:
                raise ProjectionError('Finite prepared revision horizon required')
        value = {'schema': REVISION, 'target_id': self.target_id, 'slot_id': self.slot_id,
                 'sequence': sequence, 'run_id': run_id, **payload}
        return dict(value, revision=hashlib.sha256(old.encoded(value)).hexdigest())

    def begin(self, sequence):
        run_id = durable_run_id(self.slot_id, sequence)
        self.ledger.append(sequence, 'preparing', {'run_id': run_id, 'started_unix_s': int(self.clock())})
        self.notify()

        def work():
            try:
                record = self.record(sequence, run_id, self.prepare(sequence, run_id))
            except BaseException as error:
                self.ledger.append(sequence, 'failed', {'run_id': run_id, 'exception_type': type(error).__name__,
                    'message': str(error)[:1024], 'recorded_unix_s': int(self.clock())})
            else:
                self.ledger.append(sequence, 'prepared', record)
            finally:
                self.notify()
        if self.background:
            thread = threading.Thread(target=work, name='durable-slot-prepare-' + run_id, daemon=True)
            self.worker = (sequence, thread)
            thread.start()
        else:
            work()

    def retire(self, sequence, record, outcome):
        self.ledger.append(sequence, 'retired', {'run_id': record['run_id'], 'revision': record['revision'],
            'recorded_unix_s': int(self.clock()), **outcome})
        self.notify()

    def remaining(self, record):
        return record['expires_unix_s'] - int(self.clock())

    def steps_running(self, sequence, run_id):
        """Preparation step containers of a stopped revision must be proven
        stopped (or their terminal state adopted) before a successor starts."""
        self.waiting = None if self.reconcile is None else self.reconcile(sequence, run_id)
        return self.waiting is not None

    def tick(self):
        """Advance retirement/preparation; never claims, launches or replays."""
        with self.lock:
            rows = self.ledger.entries()
            sequence, kinds = self.latest(rows)
            if sequence == 0:
                return self.begin(1)
            if 'preparing' in kinds and not {'prepared', 'failed'} & set(kinds):
                if self.alive(sequence):
                    return None
                # Interrupted by a broker restart: its step container may still
                # run against the shared Core; wait for (or stop, when overdue)
                # and adopt it. The consumed preparation claim is retained and
                # reconciled, never re-entered.
                if self.steps_running(sequence, kinds['preparing']['run_id']):
                    return None
                self.ledger.append(sequence, 'failed', {'run_id': kinds['preparing']['run_id'],
                    'exception_type': 'PreparationInterrupted',
                    'message': 'PREPARATION_INTERRUPTED_RECONCILE_WITHOUT_REPLAY',
                    'recorded_unix_s': int(self.clock())})
                self.notify()
                rows = self.ledger.entries(); kinds = rows[sequence]
            if 'failed' in kinds and 'prepared' not in kinds:
                if self.steps_running(sequence, kinds['failed'].get('run_id') or durable_run_id(self.slot_id, sequence)):
                    return None
                if self.failures(rows) < self.max_failures:
                    return self.begin(sequence + 1)
                return None
            if 'retired' in kinds:
                return self.begin(sequence + 1)
            record = kinds['prepared']
            journal = self.journal(record['run_id'])
            if journal.lookup() is None:
                if self.remaining(record) < record['wall_s'] + self.margin:
                    self.retire(sequence, record, {'reason': 'GRANT_HORIZON_REFRESH_UNCLAIMED', 'exit_code': None})
                    return self.begin(sequence + 1)
                return None
            end = self.terminal(journal, record)
            if end is not None:
                self.retire(sequence, record, {'reason': str(end.get('reason', 'TERMINAL'))[:128],
                                               'exit_code': end.get('exit_code')})
                return self.begin(sequence + 1)
            return None

    advance = tick

    # ---------------------------------------------------------------- status
    def current(self, rows=None):
        sequence, kinds = self.latest(rows)
        if 'prepared' in kinds and 'retired' not in kinds:
            return kinds['prepared']
        return None

    def checked_preflight(self, record):
        if self.remaining(record) < record['wall_s'] + self.margin:
            raise ProjectionError('DURABLE_GRANT_HORIZON_INSUFFICIENT: the revision cannot cover a whole run')
        self.preflight(record)

    def phase_row(self):
        """The slot's phase from retained state only (no preflight): the row,
        whether READY/BLOCKED still needs a preflight, and a state signature."""
        rows = self.ledger.entries()
        sequence, kinds = self.latest(rows)
        row = {'target_id': self.target_id, 'mode': 'durable', 'revision': None, 'run_id': None,
               'sequence': None, 'ready': False, 'security_status': 'SECURITY_DEFERRED'}
        signature = (sequence, tuple(sorted(kinds)))
        record = self.current(rows)
        if record is None:
            if ('failed' in kinds and 'prepared' not in kinds and not self.alive(sequence)
                    and self.failures(rows) >= self.max_failures):
                failure = kinds['failed']
                return row | {'phase': 'FAILED', 'blocker': ('Automatic revision preparation failed ('
                    + str(failure.get('message'))[:300] + '); retained without replay. Root must resume preparation.')}, \
                    False, signature
            blocker = 'Root is preparing the next development revision'
            if self.waiting is not None:
                blocker = ('Root is waiting for an interrupted preparation step to stop before preparing again ('
                           + str(self.waiting)[:300] + ')')
            return row | {'phase': 'PREPARING', 'blocker': blocker}, False, signature
        row.update(revision=record['revision'], run_id=record['run_id'], sequence=record['sequence'])
        claim = self.journal(record['run_id']).lookup()
        if claim is not None:
            if claim.get('ack') is None:
                return row | {'phase': 'CLAIMED', 'blocker': 'An issued run cannot replay'}, False, signature + ('claimed',)
            return row | {'phase': 'LAUNCHED', 'blocker': 'Development run in progress; this revision cannot replay'}, \
                False, signature + ('launched',)
        return row | {'phase': 'BLOCKED', 'blocker': 'Root has not checked this revision yet'}, True, \
            signature + (record['revision'],)

    def preflight_row(self, row):
        record = self.current()
        if record is None or record['revision'] != row['revision']:
            return row
        try:
            self.checked_preflight(record)
        except Exception as error:  # Includes fixed preflight subprocess refusals.
            return row | {'phase': 'BLOCKED', 'blocker': _blocker(error)}
        return row | {'ready': True, 'phase': 'READY', 'blocker': None}

    def refresh(self):
        if not self.monitored:  # Inline (unmonitored): the historical locked status.
            with self.lock:
                return CachedReadiness.refresh(self)
        return CachedReadiness.refresh(self)

    def engine(self, record):
        journal = self.journal(record['run_id'])
        return CapsuleRevisionEngine(revision_policy(self.policy, self.target_id, record['revision'], record['run_id']),
            self.public_key, journal, lambda: self.checked_preflight(record),
            lambda: self.launch(record, journal), clock=self.clock, assertion_window_s=self.click_window_s)

    def start(self, params, assertion, *, received=None):
        # The click's own window is checked at receipt, never after a wait.
        received = int(self.clock()) if received is None else received
        old.request(params)
        try:
            with self.lock:
                self.tick()
                rows = self.ledger.entries()
                record = self.current(rows)
                if record is not None and params['revision'] == record['revision']:
                    return self.engine(record).start(params, assertion, received=received)
                # A retried delivery of an already accepted click returns its
                # retained acknowledgement; an unclaimed retired revision never runs.
                for kinds in rows.values():
                    earlier = kinds.get('prepared')
                    if earlier is not None and earlier['revision'] == params['revision'] \
                            and self.journal(earlier['run_id']).lookup() is not None:
                        return self.engine(earlier).start(params, assertion, received=received)
                raise ProjectionError('No ready durable revision for this exact target revision')
        finally:
            self.notify()

    def resume(self):
        """Explicit Root operator resume after FAILED; appends, never resets."""
        with self.lock:
            rows = self.ledger.entries()
            sequence, kinds = self.latest(rows)
            if not ('failed' in kinds and 'prepared' not in kinds and 'resumed' not in kinds):
                raise ProjectionError('Only a failed durable preparation can be resumed')
            result = self.ledger.append(sequence, 'resumed', {'recorded_unix_s': int(self.clock())})
            self.notify()
            return result


class RootCapsuleEngine:
    """Every installed slot. Under policy v2 each slot keeps a cached Root
    readiness record (see ``CachedReadiness``); ``monitor`` starts one
    background thread per slot so a status request never waits on a
    preflight. Policy v1 keeps its historical inline status rows."""
    def __init__(self, installed_policy, public_key, slots, *, limits=None):
        self.policy = copy.deepcopy(policy(installed_policy)); self.lock = threading.RLock()
        self.limits = timeouts(limits or {}, BROKER_TIMEOUTS)
        v2 = self.policy['schema'] == POLICY_V2
        self.engines = {}
        for slot in self.policy['slots']:
            item = slots[slot['target_id']]
            if mode(slot) == 'durable':
                if not isinstance(item, DurableSlot) or item.target_id != slot['target_id'] or item.slot_id != slot['slot_id']:
                    raise ProjectionError('Durable slot engine differs')
                self.engines[slot['target_id']] = item
            else:
                journal, preflight, launch = item
                engine = CapsuleRevisionEngine(slot_policy(self.policy, slot), public_key, journal, preflight, launch,
                                               assertion_window_s=self.limits['click_window_s'])
                self.engines[slot['target_id']] = StrictSlot(engine, mode_fields={'mode': 'strict', 'sequence': None},
                    readiness_refresh_s=self.limits['readiness_refresh_s'],
                    readiness_stale_s=self.limits['readiness_stale_s']) if v2 else engine

    def status_row(self, target):
        engine = self.engines[target]
        if isinstance(engine, CachedReadiness):
            return engine.status()
        return engine.status()  # Policy v1: the historical closed row.

    def handle(self, value):
        if value.get('operation') == 'status':
            _fields(value, 'protocol operation')
            if value['protocol'] != PROTOCOL: raise ProjectionError('Capsule protocol differs')
            # Monitored slots answer from their cached Root observation; one
            # slot's preflight never holds another slot's status or start.
            return {'schema': STATUS if self.policy['schema'] == POLICY else STATUS_V2,
                    'slots': [self.status_row(target) for target in self.engines]}
        received = int(time.time())
        _fields(value, 'protocol operation params assertion')
        if value['protocol'] != PROTOCOL or value['operation'] != 'start': raise ProjectionError('Capsule protocol differs')
        old.request(value['params'])
        engine = self.engines.get(value['params']['target_id'])
        if engine is None: raise ProjectionError('No installed prepared capsule slot')
        if isinstance(engine, DurableSlot):
            return engine.start(value['params'], value['assertion'], received=int(engine.clock()))
        with self.lock:
            return engine.start(value['params'], value['assertion'], received=received)

    def tick(self):
        for engine in self.engines.values():
            if isinstance(engine, DurableSlot):
                engine.tick()

    def monitor(self, *, stop=None, interval=5):
        """One background readiness/advance thread per cached slot."""
        threads = []
        for target, engine in self.engines.items():
            if isinstance(engine, CachedReadiness):
                engine.monitored = True
                thread = threading.Thread(target=engine.monitor, kwargs={'stop': stop, 'interval': interval},
                                          name='capsule-slot-readiness-' + target, daemon=True)
                thread.start(); threads.append(thread)
        return threads


def load_native_capsules(authority, workspace_id):
    from .cc_rsi_installation import protected_bytes
    if not os.path.lexists(GATEWAY_CONFIG): return None
    value = json.loads(protected_bytes(GATEWAY_CONFIG, uid=0, mode=0o440))
    # Optional ``timeouts``: {exchange_s, click_window_s}; defaults are historical.
    _fields(value, 'schema policy gateway_public_key module_sha256' + (' timeouts' if 'timeouts' in value else ''))
    limits = timeouts(value.get('timeouts', {}), GATEWAY_TIMEOUTS)
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
    return NativeCapsuleAdapter(authority, signer, InstalledCapsuleClient(timeout_s=limits['exchange_s']), value['policy'],
                                click_window_s=limits['click_window_s'])
