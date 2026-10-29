"""Fixed OS-root composition of the installed finite security campaign.

Preparation captures public metadata only. The same live instance waits for a
separate root approval of its exact plan before any boundary driver is called.
No record chooses Python code, a program, an executor, a signer or a key path.
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
import stat
import sqlite3

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.contracts.rsi_security import CASES
from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver
from jiuwenswarm.research.state import SQLiteRunStore
from .records import encoded
from .security_campaign import (
    CampaignLedger, SecurityCampaign, _protected_store, prepare_security_campaign_plan,
)
from .security_driver import SecurityBoundaryDriver
from .security_profile import capture_verification_pins, build_verification_profile
from .security_scope import RuntimeScopeObserver, capture_worker_scope
from .session_policy import validate_private
from .worker import PublicBytes, WorkerBroker, ref

APPROVAL_FILE = Path('/run/ai4r-rsi-validation/approval.json')
HOST_CAPTURE_FILE = Path('/run/ai4r-rsi-validation/runtime-observation.json')
CONFIG_FILE = Path('/run/ai4r-rsi-validation/runtime.json')
PUBLIC_ROOT = Path('/run/ai4r-rsi-validation/public')
CAMPAIGN_ROOT = Path('/var/lib/ai4r-rsi-validation-campaign')
PUBLICATION_APPROVAL_FILE = Path('/run/ai4r-rsi-validation/publication-approval.json')
CONFIG_SCHEMA = 'urn:ai4r:private:rsi-security-runtime-config:1'
APPROVAL_SCHEMA = 'urn:ai4r:private:rsi-security-runtime-approval:1'
PUBLICATION_APPROVAL_SCHEMA = 'urn:ai4r:private:rsi-security-runtime-publication-approval:1'
PUBLICATION_PREPARATION_SCHEMA = 'urn:ai4r:private:rsi-security-publication-preparation:1'
# These are metadata types, not a generic import/record-registration endpoint.
IMPORT_TYPES = {
    'capsule-declaration': 'capsule-declaration',
    'rsi-session': 'rsi-session',
    'rsi-target-profile': 'rsi-target-profile',
    'rsi-worker-profile': None,
}
MAX_ORIGINALS = 2048
MAX_BYTES = 4 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024


class RuntimeUnavailable(ValueError):
    pass


def _need(value):
    if not value: raise RuntimeUnavailable('Fixed approved security runtime dependencies are unavailable')


def _closed_json(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            _need(key not in value); value[key] = item
        return value
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(RuntimeUnavailable('Nonfinite protected metadata')))


def _root():
    _need(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0)


def import_metadata(store, public, originals):
    """Import an explicit root-nominated finite public closure with exact types.

    This never follows references in a JSON body. In particular calibration,
    hidden fixture, account, private-key and signer records are not importable
    typed owners. Unknown required originals must be explicitly supplied by the
    root launcher. This helper does not confer execution authority.
    """
    _root(); _protected_store(store)
    _need(type(store) is SQLiteRunStore and type(public) is PublicBytes)
    _need(isinstance(originals, (list, tuple)) and 0 < len(originals) <= MAX_ORIGINALS)
    prepared = []; ids = set(); total = 0
    for row in originals:
        _need(isinstance(row, dict) and set(row) == {'ref', 'kind'})
        pin = row['ref']; kind = row['kind']; ref(pin)
        _need(pin['id'] not in ids and (kind is None or kind in IMPORT_TYPES)); ids.add(pin['id'])
        raw = public.read(pin)
        _need(isinstance(raw, bytes) and 0 <= len(raw) <= MAX_BYTES
              and hashlib.sha256(raw).hexdigest() == pin['sha256'])
        total += len(raw); _need(total <= MAX_TOTAL)
        if kind is not None:
            value = _closed_json(raw)
            if kind == 'rsi-worker-profile':
                from .worker import validate_profile
                validate_profile(value)
            else: validate(IMPORT_TYPES[kind], value)
        # Reject a conflicting installed type before INSERT OR IGNORE could
        # leave an existing owner's index under a different name.
        try: existing = store.record_kind(pin)
        except ResearchError as error:
            _need(error.code == 'evidence_unavailable'); existing = None
        _need(existing is None or kind is None or existing == kind)
        prepared.append((copy.deepcopy(pin), kind, raw))
    for pin, kind, raw in prepared:
        store._capture(raw, record_id=pin['id'], media_type='application/json' if kind else 'application/octet-stream', kind=kind)
        _need(store.read_blob(pin) == raw and (kind is None or store.record_kind(pin) == kind))
    return tuple({'ref': pin, 'kind': kind} for pin, kind, _ in prepared)


def _blocked(code, prepared=None):
    result = {'schema': 'ai4r-rsi-security-runtime-status:1', 'status': 'BLOCKED',
              'blockers': [code], 'plan_ref': None if prepared is None else prepared['plan_ref'],
              'campaign_status_ref': None}
    return result


class ProtectedOriginalKinds:
    """Keep real record types; label verified untyped artifacts as raw only."""
    def __init__(self, store):
        _need(type(store) is SQLiteRunStore); self.store = store

    def __call__(self, pin):
        ref(pin)
        try: return self.store.record_kind(pin)
        except ResearchError as error:
            if error.code != 'evidence_unavailable': raise
        metadata = self.store.artifact_metadata(pin)
        _need(isinstance(metadata, dict) and set(metadata) == {'media_type'}
              and isinstance(metadata['media_type'], str))
        raw = self.store.read_blob(pin)
        _need(isinstance(raw, bytes) and hashlib.sha256(raw).hexdigest() == pin['sha256'])
        return 'original-bytes'


class ReachedOriginals:
    """Instrument fixed independent readers; never recursively walk JSON."""
    def __init__(self, store):
        self.store = store; self.kinds = ProtectedOriginalKinds(store); self.rows = {}; self.ids = set(); self.total = 0

    def read(self, pin):
        ref(pin); key = encoded(pin); raw = self.store.read_blob(pin)
        _need(isinstance(raw, bytes) and 0 <= len(raw) <= 16*1024*1024
              and hashlib.sha256(raw).hexdigest() == pin['sha256'])
        if key not in self.rows:
            _need(pin['id'] not in self.ids and len(self.rows) < 4096)
            self.total += len(raw); _need(self.total <= MAX_TOTAL)
            self.ids.add(pin['id']); self.rows[key] = {'ref': dict(pin), 'kind': self.kinds(pin)}
        return raw

    def kind(self, pin):
        self.read(pin); return self.rows[encoded(pin)]['kind']

    def reset(self):
        self.rows = {}; self.ids = set(); self.total = 0


class SecurityRuntime:
    """Actual installed owners only; constructor arguments come from Python."""
    def __init__(self, store, *, worker_owner, public_key, key_id):
        _root(); _protected_store(store)
        _need(type(store) is SQLiteRunStore and type(worker_owner) is WorkerBroker
              and type(worker_owner.public) is PublicBytes
              and isinstance(public_key, bytes) and len(public_key) == 32
              and isinstance(key_id, str) and re.fullmatch(r'[a-z][a-z0-9_.:-]{0,63}', key_id))
        self.store = store; self.worker = worker_owner
        self.public_key = public_key; self.key_id = key_id
        # Use these same callback objects in any eventual RSIQualification and
        # publish_security_installation invocation. Critical case records keep
        # their actual protected types; raw bytes never become typed evidence.
        self._reached = ReachedOriginals(store)
        self.read_original = self._reached.read
        self.original_kind = self._reached.kind
        self._prepared = None; self._driver = None; self._observer = None
        self._materials = None; self._campaign = None; self._ledger = None
        self._runtime_observer = None; self._publication = None; self._authority = None
        self._lock = asyncio.Lock()

    def prepare(self, *, case_bindings, environment_ref, originals):
        """Capture metadata and return exact refs for a separate approval.

        This method neither invokes RuntimeScopeObserver/kernel prerequisites
        nor contacts the remote signer. It does not open a campaign ledger,
        execute a case, emit a signed halt or manufacture a qualification.
        """
        _root(); _need(self._prepared is None and self._driver is None)
        imported = import_metadata(self.store, self.worker.public, originals)
        profiles = sorted((json.loads(key) for key in self.worker.profiles),
                          key=lambda pin: (pin['id'], pin['sha256']))
        _need(profiles and len(profiles) <= 100)
        ref(environment_ref); self.store.read_blob(environment_ref)
        for pin in profiles:
            _need(self.store.read_blob(pin) == self.worker.public.read(pin))
        captured = capture_verification_pins(self.store, worker_profile_refs=profiles)
        scope_capture = capture_worker_scope(self.store, worker_owner=self.worker,
            runtime_build_ref=captured['runtime_build_ref'], environment_ref=environment_ref)
        scope_ref = scope_capture['scope_ref']
        pins = self.store.read_record(captured['validation_profile_ref'])
        attacks = self.store.read_record(captured['attack_pins_ref'])
        observer = FiniteCaseObserver(self.store.read_blob, self.store.record_kind,
            attack_pins=attacks, public_key=self.public_key, key_id=self.key_id)
        observer_ref = next(row['ref'] for row in pins['source_refs']
                            if row['path'] == 'research/contracts/rsi_security_cases.py')
        # Creation is metadata only. The descriptor is unique to this actual
        # instance, preventing a restart from reusing a prepared driver/plan.
        driver = SecurityBoundaryDriver(self.store, worker_owner=self.worker,
            scope_ref=scope_ref, case_bindings=case_bindings, attack_pins=attacks,
            public_key=self.public_key, key_id=self.key_id)
        self._driver = driver
        plan_ref = prepare_security_campaign_plan(self.store, scope_ref=scope_ref,
            case_bindings=case_bindings, observer_ref=observer_ref, driver_ref=driver.descriptor_ref,
            verification_profile_ref=captured['validation_profile_ref'],
            procedure_ref=captured['procedure_ref'], assertion_manifest_ref=captured['assertion_manifest_ref'])
        driver.bind_plan(plan_ref)
        result = {'status': 'CAPTURED_NOT_APPROVED', 'plan_ref': plan_ref, 'scope_ref': scope_ref,
            **{name: captured[name] for name in ('validation_profile_ref', 'attack_pins_ref',
                'runtime_build_ref', 'procedure_ref', 'assertion_manifest_ref')}}
        self._prepared = copy.deepcopy(result); self._observer = observer
        self._materials = self._metadata_materials(imported, pins, attacks, driver)
        return copy.deepcopy(result)

    def _metadata_materials(self, imported, pins, attacks, driver):
        rows = {}; total = 0
        def include(pin, kind=None):
            nonlocal total
            ref(pin); old = rows.get(pin['id'])
            if old is not None:
                _need(old['ref'] == pin and (kind is None or old['kind'] == kind)); return
            raw = self.store.read_blob(pin); total += len(raw)
            _need(0 <= len(raw) <= MAX_BYTES and total <= MAX_TOTAL)
            _need(kind is None or self.store.record_kind(pin) == kind)
            rows[pin['id']] = {'ref': copy.deepcopy(pin), 'kind': kind, 'bytes': raw}
        for row in imported: include(row['ref'], row['kind'])
        prepared = self._prepared
        include(prepared['validation_profile_ref'], 'rsi-security-profile-pins')
        include(prepared['attack_pins_ref'], 'rsi-security-attack-pins')
        include(prepared['scope_ref'], 'rsi-security-scope')
        include(prepared['plan_ref'], 'rsi-security-campaign-plan')
        include(driver.descriptor_ref, 'rsi-security-driver')
        include(self.store.read_record(driver.descriptor_ref)['source_ref'])
        include(prepared['runtime_build_ref'])
        for name in ('installed_build_ref', 'procedure_ref', 'assertion_manifest_ref', 'source_manifest_ref'):
            include(pins[name])
        for row in pins['source_refs']: include(row['ref'])
        include(attacks['program_prefix_ref'])
        for case in CASES: include(attacks['attacks'][case])
        scope = self.store.read_record(prepared['scope_ref'])
        for name in ('worker_driver_ref', 'executor_ref', 'probe_ref'): include(scope[name])
        return tuple(rows[key] for key in sorted(rows))

    def metadata_materials(self):
        """Explicit public-only projection for an independent root publisher.

        Publish to an already approved broker PublicBytes root. The runtime
        does not traverse arbitrary record refs or publish a live installation.
        """
        _root(); _need(self._prepared is not None and self._materials is not None)
        return tuple({'ref': dict(row['ref']), 'kind': row['kind'], 'bytes': row['bytes']}
                     for row in self._materials)

    async def run_approved(self, *, approved_plan_refs, rpc_session_id, capability):
        """Run once only after root approves this exact still-live preparation."""
        _root()
        async with self._lock:
            prepared = self._prepared
            if prepared is None: return _blocked('METADATA_NOT_PREPARED')
            try:
                _need(isinstance(approved_plan_refs, (list, tuple)))
                for pin in approved_plan_refs: ref(pin)
                if encoded(prepared['plan_ref']) not in {encoded(pin) for pin in approved_plan_refs}:
                    return _blocked('EXACT_PLAN_APPROVAL_REQUIRED', prepared)
                _need(isinstance(rpc_session_id, str) and 0 < len(rpc_session_id) <= 256
                      and isinstance(capability, str) and 16 <= len(capability) <= 1024)
                scope = self.store.read_record(prepared['scope_ref'])
                # These fixed actual owners are remeasured before opening the
                # campaign ledger or issuing a case claim. Host capture bytes
                # must already be separately installed at the finite path.
                runtime = RuntimeScopeObserver(worker_owner=self.worker, approved_scope=scope,
                    runtime_capture_file=HOST_CAPTURE_FILE)
                _need(runtime(scope) == scope)
                build_verification_profile(self.store.read_blob, prepared['validation_profile_ref'])
                from .security_custody import ValidationHaltSigner
                signer = ValidationHaltSigner(self.store, plan_ref=prepared['plan_ref'],
                    scope_ref=prepared['scope_ref'], attack_pins_ref=prepared['attack_pins_ref'],
                    public_key=self.public_key, key_id=self.key_id,
                    rpc_session_id=rpc_session_id, capability=capability)
                _need(signer.public_bytes() == self.public_key and signer.key_id == self.key_id)
                # The finite remote owner must acknowledge this exact plan
                # before kernel effects, without signing or charging anything.
                from jiuwenswarm.research.bridge import BridgeError
                from jiuwenswarm.research.router_client import PlatformIntegrityError
                try: _need(await signer.authorized())
                except (BridgeError, PlatformIntegrityError, asyncio.TimeoutError):
                    return _blocked('CUSTODY_AUTHORITY_UNAVAILABLE', prepared)
                if self._campaign is None:
                    ledger = CampaignLedger(self.store)
                    try:
                        campaign = SecurityCampaign(self.store, ledger=ledger, signer=signer,
                            observer=self._observer, driver=self._driver,
                            approved_plan_refs=[prepared['plan_ref']], runtime_observer=runtime,
                            public_key=self.public_key, key_id=self.key_id)
                    except BaseException:
                        ledger.close(); raise
                    self._ledger = ledger; self._campaign = campaign
                    self._runtime_observer = runtime
                result_ref = await self._campaign.run(prepared['plan_ref'])
                result = self.store.read_record(result_ref)
                return {'schema': 'ai4r-rsi-security-runtime-status:1',
                    'status': result['status'], 'plan_ref': prepared['plan_ref'],
                    'campaign_status_ref': result_ref,
                    'blockers': [] if result['status'] == 'COMPLETE_OBSERVED' else ['CAMPAIGN_INCOMPLETE']}
            except (ValueError, KeyError, TypeError, OSError, AttributeError, ImportError, ResearchError):
                return _blocked('CURRENT_RUNTIME_OR_CUSTODY_AUTHORITY_UNAVAILABLE', prepared)

    async def run_from_approval_file(self):
        """Read the fixed root file once; absence is a no-effect blocked result."""
        try:
            approval = read_approval()
            prepared = self._prepared; _need(prepared is not None)
            _need(all(approval[name] == prepared[name] for name in
                ('plan_ref', 'scope_ref', 'validation_profile_ref', 'attack_pins_ref'))
                and approval['custodian_key_id'] == self.key_id
                and approval['custodian_public_key_sha256'] == hashlib.sha256(self.public_key).hexdigest())
        except (ValueError, KeyError, TypeError, OSError, ResearchError):
            return _blocked('EXACT_ROOT_APPROVAL_UNAVAILABLE', self._prepared)
        return await self.run_approved(approved_plan_refs=[approval['plan_ref']],
            rpc_session_id=approval['rpc_session_id'], capability=approval['capability'])

    def close(self):
        if self._ledger is not None: self._ledger.close(); self._ledger = None

    def prepare_publication(self, campaign_status_ref):
        """Recheck all thirteen cases and capture the minimal reached closure.

        The exact live RuntimeScopeObserver and original read/type callbacks
        remain attached to this owner for the separately approved publication.
        Metadata preparation itself never writes an installation directory.
        """
        from jiuwenswarm.research.contracts.rsi_security import RSIQualification
        from .profiles import freeze_profile
        from .security_scope import _root_bytes
        from .session_policy import _contracts
        _root(); prepared = self._prepared
        _need(prepared is not None and self._campaign is not None
              and type(self._runtime_observer) is RuntimeScopeObserver)
        if self._publication is not None:
            _need(self._publication['campaign_status_ref'] == campaign_status_ref)
            return copy.deepcopy(self._publication)
        status = self.store.read_record(campaign_status_ref)
        _need(self.store.record_kind(campaign_status_ref) == 'rsi-security-campaign-status'
              and status['status'] == 'COMPLETE_OBSERVED' and not status['missing_cases']
              and status['plan_ref'] == prepared['plan_ref'] and status['scope_ref'] == prepared['scope_ref'])
        verification = status['verification']
        _need(isinstance(verification, dict) and set(verification) ==
              {'verification_receipt_ref', 'artifact_refs', 'case_evidence_refs'})
        qualification = {'schema': 'ai4r-rsi-security-qualification:1',
            'scope_ref': prepared['scope_ref'], **copy.deepcopy(verification)}
        qualification['id'] = 'security-qualification:' + hashlib.sha256(encoded(qualification)).hexdigest()
        validate_private('urn:ai4r:private:rsi-security-qualification:1', qualification)
        qualification_ref = self.store.append_record('rsi-security-qualification', qualification)
        runtime_raw = _root_bytes(self._runtime_observer._capture_file, 65536)
        validate_private('urn:ai4r:private:rsi-runtime-observation:1', _closed_json(runtime_raw))
        runtime_ref = self.store.put_blob(runtime_raw)
        self._reached.reset()
        read = self.read_original; kinds = self.original_kind
        get = lambda pin: _closed_json(read(pin))
        get(qualification_ref); scope = get(prepared['scope_ref'])
        _need(self._runtime_observer(scope) == scope)
        pins = get(prepared['validation_profile_ref'])
        _need(pins['worker_profile_refs'] == scope['worker_profile_refs']
              and pins['attack_pins_ref'] == prepared['attack_pins_ref']
              and pins['assertion_manifest_ref'] == prepared['assertion_manifest_ref'])
        profile = build_verification_profile(read, prepared['validation_profile_ref'])
        attacks = get(prepared['attack_pins_ref'])
        observer = FiniteCaseObserver(read, kinds, attack_pins=attacks,
            public_key=self.public_key, key_id=self.key_id)
        authority = RSIQualification(read, qualification_ref, kind_reader=kinds,
            scope_observer=self._runtime_observer, validation_profile=profile,
            case_observer=observer, public_key=self.public_key, key_id=self.key_id)
        read(runtime_ref)
        for pin in scope['worker_profile_refs']:
            worker = get(pin); session = get(worker['session_ref'])
            target = get(session['target_profile_ref']); parent = get(session['parent_declaration_ref'])
            freeze_profile(target, parent, _contracts().validate)
            authority.require('session_start', session_ref=worker['session_ref'], worker_profile_ref=pin)
            authority.raw(worker['parent_ref'])
        # Capture only reads reached by the fixed profile/guard/publisher roots;
        # status, plan, driver, claim and producer proof records are excluded
        # unless an original case evidence list actually names one of them.
        manifest = {'schema': 'ai4r-rsi-security-installation:1',
            'qualification_ref': qualification_ref, 'scope_ref': prepared['scope_ref'],
            'validation_profile_ref': prepared['validation_profile_ref'],
            'assertion_manifest_ref': prepared['assertion_manifest_ref'],
            'attack_pins_ref': prepared['attack_pins_ref'], 'runtime_observation_ref': runtime_ref,
            'custodian_key_id': self.key_id,
            'custodian_public_key': base64.urlsafe_b64encode(self.public_key).decode().rstrip('='),
            'originals': sorted(self._reached.rows.values(), key=lambda row: (row['ref']['id'], row['ref']['sha256']))}
        closure = {'schema': 'ai4r-rsi-security-publication-preparation:1',
            'plan_ref': prepared['plan_ref'], 'campaign_status_ref': campaign_status_ref,
            'installation': manifest}
        validate_private(PUBLICATION_PREPARATION_SCHEMA, closure)
        closure_ref = self.store.append_record('rsi-security-publication-preparation', closure)
        result = {'schema': 'ai4r-rsi-security-runtime-review:1', 'status': 'REVIEW_REQUIRED',
            'plan_ref': prepared['plan_ref'], 'campaign_status_ref': campaign_status_ref,
            'qualification_ref': qualification_ref, 'installation_closure_ref': closure_ref,
            'scope_ref': prepared['scope_ref']}
        self._authority = authority; self._publication = copy.deepcopy(result)
        return result

    def publish_from_approval_file(self):
        """Separate exact root approval; plan approval never publishes."""
        _root(); publication = self._publication
        try:
            _need(publication is not None and self._authority is not None)
            approval = _read_root_json(PUBLICATION_APPROVAL_FILE, PUBLICATION_APPROVAL_SCHEMA)
            _need(all(approval[name] == publication[name] for name in
                ('plan_ref', 'campaign_status_ref', 'qualification_ref', 'installation_closure_ref', 'scope_ref')))
            closure = self.store.read_record(publication['installation_closure_ref'])
            validate_private(PUBLICATION_PREPARATION_SCHEMA, closure)
            _need(self.store.record_kind(publication['installation_closure_ref']) == 'rsi-security-publication-preparation'
                  and closure['plan_ref'] == publication['plan_ref']
                  and closure['campaign_status_ref'] == publication['campaign_status_ref'])
            manifest = dict(closure['installation'], rpc_session_id=approval['rpc_session_id'],
                            rpc_capability=approval['rpc_capability'])
            validate_private('urn:ai4r:private:rsi-security-installation:1', manifest)
            from .security_publication import publish_security_installation
            return publish_security_installation(manifest, read=self.read_original, kind_reader=self.original_kind,
                authority=self._authority, current_observer=self._runtime_observer)
        except (ValueError, KeyError, TypeError, OSError, AttributeError, ImportError, ResearchError):
            return {'status': 'BLOCKED', 'blockers': ['EXACT_PUBLICATION_APPROVAL_OR_CURRENT_PROOF_UNAVAILABLE'],
                    'plan_ref': None if publication is None else publication['plan_ref']}


def read_approval():
    """Fixed bounded root-owned metadata file, never a factory/program path."""
    return _read_root_json(APPROVAL_FILE, APPROVAL_SCHEMA)


def _read_root_json(path, schema):
    _root()
    _need(path.is_absolute() and not any(item.is_symlink() for item in (path, *path.parents)))
    for parent in path.parents:
        meta = parent.stat()
        _need(meta.st_uid == 0 and (not meta.st_mode & 0o022 or meta.st_mode & stat.S_ISVTX))
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        meta = os.fstat(descriptor)
        _need(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and meta.st_gid == 0 and stat.S_IMODE(meta.st_mode) == 0o600
              and meta.st_nlink == 1 and 0 < meta.st_size <= 65536)
        with os.fdopen(descriptor, 'rb', closefd=False) as stream: raw = stream.read(65537)
        _need(len(raw) <= 65536)
    finally: os.close(descriptor)
    value = _closed_json(raw); validate_private(schema, value)
    return value


def validation_factory(runtime, *, case_bindings, environment_ref, originals, prepared_callback=None):
    """Return a trusted worker_bootstrap.serve callback for this actual owner.

    The optional Python callback receives ``(metadata_refs, public_materials)``
    for the root launcher's console/public metadata owner. It cannot supply a
    driver, executor or approval. The
    broker keeps serving while an operator publishes metadata/host capture and
    installs the separate fixed approval file; no producer restart is needed.
    """
    _need(type(runtime) is SecurityRuntime)
    async def prepare_and_wait(brokers):
        _need(isinstance(brokers, tuple) and any(owner is runtime.worker for owner in brokers))
        captured = runtime.prepare(case_bindings=case_bindings,
            environment_ref=environment_ref, originals=originals)
        if prepared_callback is not None:
            # Trusted Python UI only, no decoded callback or activation path.
            _need(callable(prepared_callback))
            prepared_callback(copy.deepcopy(captured), runtime.metadata_materials())
        last_blocked = None
        while True:
            if APPROVAL_FILE.exists():
                outcome = await runtime.run_from_approval_file()
                if outcome['campaign_status_ref'] is not None:
                    if outcome['status'] != 'COMPLETE_OBSERVED': return outcome
                    return await _wait_publication(runtime, outcome['campaign_status_ref'])
            else:
                outcome = _blocked('EXACT_ROOT_APPROVAL_UNAVAILABLE', runtime._prepared)
            current = encoded(outcome)
            if current != last_blocked:
                print(json.dumps(outcome, sort_keys=True), flush=True); last_blocked = current
            await asyncio.sleep(10 if APPROVAL_FILE.exists() else 1)
    return prepare_and_wait


async def _wait_publication(runtime, campaign_status_ref):
    """Retain the live producer while a distinct publication review is pending."""
    review = None; last_blocked = None
    while review is None:
        try:
            review = runtime.prepare_publication(campaign_status_ref)
            print(json.dumps(review, sort_keys=True), flush=True)
        except (ValueError, KeyError, TypeError, OSError, AttributeError, ImportError, ResearchError):
            blocked = {'status': 'BLOCKED', 'blockers': ['CURRENT_PUBLICATION_PROOF_UNAVAILABLE'],
                       'campaign_status_ref': campaign_status_ref}
            current = encoded(blocked)
            if current != last_blocked:
                print(json.dumps(blocked, sort_keys=True), flush=True); last_blocked = current
            await asyncio.sleep(10)
    last_blocked = None
    while True:
        outcome = runtime.publish_from_approval_file()
        if outcome['status'] in {'PUBLISHED', 'OUTCOME_UNKNOWN'}: return outcome
        current = encoded(outcome)
        if current != last_blocked:
            print(json.dumps(outcome, sort_keys=True), flush=True); last_blocked = current
        await asyncio.sleep(10 if PUBLICATION_APPROVAL_FILE.exists() else 1)


def worker_validation_factory(store, *, public_key, key_id, case_bindings,
                              environment_ref, originals, prepared_callback=None):
    """Direct callback for ``await worker_bootstrap.serve(validation_factory=...)``.

    The root launcher supplies approved metadata values, never Python names.
    It creates the runtime only after bootstrap supplies the actual brokers.
    """
    _root(); _protected_store(store)
    async def compose(brokers):
        _need(isinstance(brokers, tuple) and len(brokers) == 2
              and all(type(owner) is WorkerBroker for owner in brokers)
              and sum(owner.hidden is False for owner in brokers) == 1
              and sum(owner.hidden is True for owner in brokers) == 1)
        visible = next(owner for owner in brokers if owner.hidden is False)
        _need(all(owner.profiles == visible.profiles for owner in brokers))
        runtime = SecurityRuntime(store, worker_owner=visible, public_key=public_key, key_id=key_id)
        try:
            return await validation_factory(runtime, case_bindings=case_bindings,
                environment_ref=environment_ref, originals=originals,
                prepared_callback=prepared_callback)(brokers)
        finally: runtime.close()
    return compose


def _owned_path(path, *, directory=False, mode=None, gid=None):
    path = Path(path)
    _need(path.is_absolute() and '..' not in path.parts
          and not any(item.is_symlink() for item in (path, *path.parents)))
    for parent in path.parents:
        meta = parent.stat()
        _need(meta.st_uid == 0 and (not meta.st_mode & 0o022 or meta.st_mode & stat.S_ISVTX))
    meta = path.lstat()
    _need((stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode))
          and meta.st_uid == 0 and (directory or meta.st_nlink == 1)
          and (mode is None or stat.S_IMODE(meta.st_mode) == mode)
          and (gid is None or meta.st_gid == gid))
    return path


def load_config():
    """One fixed root-owned config with data pins, never executable selection."""
    _root(); path = _owned_path(CONFIG_FILE, mode=0o600, gid=0)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        meta = os.fstat(descriptor)
        _need(meta.st_uid == 0 and meta.st_gid == 0 and stat.S_IMODE(meta.st_mode) == 0o600
              and stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and 0 < meta.st_size <= 1024*1024)
        with os.fdopen(descriptor, 'rb', closefd=False) as stream: raw = stream.read(1024*1024+1)
        _need(len(raw) <= 1024*1024)
    finally: os.close(descriptor)
    value = _closed_json(raw); validate_private(CONFIG_SCHEMA, value)
    return value


def _campaign_root(value):
    _need(Path(value) == CAMPAIGN_ROOT)
    _root(); path = _owned_path(value, directory=True, mode=0o700)
    # Linux-native owner semantics are required; a Windows/9p/shared mount
    # cannot become custody by chmod or a JSON ownership assertion.
    from .preparation_runtime import _native_fs
    _native_fs(path)
    _need(not (path == PUBLIC_ROOT or path in PUBLIC_ROOT.parents or PUBLIC_ROOT in path.parents))
    return path


def inspect_existing_campaign(root):
    """Safe metadata inspection only; restarting never creates a new producer.

    A live WAL cannot be truthfully inspected through an immutable snapshot;
    report that limitation without checkpointing, opening the write owner or
    replaying a pending plan. The original live process remains authoritative.
    """
    path = _campaign_root(root)
    result = {'schema': 'ai4r-rsi-security-runtime-status:1', 'status': 'BLOCKED',
        'blockers': ['EXISTING_CAMPAIGN_REQUIRES_INSPECTION'], 'plan_refs': [],
        'plan_ref': None, 'campaign_status_ref': None}
    db = path/'state'/'research.sqlite3'
    try:
        _owned_path(db, mode=0o600)
        for suffix in ('-wal', '-journal'):
            side = Path(str(db)+suffix)
            if side.exists() and side.stat().st_size:
                result['blockers'] = ['CURRENT_WAL_REQUIRES_ORIGINAL_OWNER']; return result
        connection = sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1', uri=True)
        try:
            rows = connection.execute("SELECT a.id,a.sha256 FROM artifacts a JOIN records r ON a.id=r.id WHERE r.kind='rsi-security-campaign-plan' ORDER BY r.rowid LIMIT 33").fetchall()
        finally: connection.close()
        _need(len(rows) <= 32)
        for identity, digest in rows:
            pin = {'id': identity, 'sha256': digest}; ref(pin)
            original = _owned_path(path/'artifacts'/'sha256'/digest[:2]/digest)
            _need(original.stat().st_size <= MAX_BYTES)
            raw = original.read_bytes(); _need(hashlib.sha256(raw).hexdigest() == digest)
            validate_private('urn:ai4r:private:rsi-security-campaign-plan:1', _closed_json(raw))
            result['plan_refs'].append(pin)
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, ResearchError):
        result['blockers'] = ['EXISTING_CAPTURE_UNAVAILABLE']; result['plan_refs'] = []
    return result


def _publish_metadata(prepared, materials):
    """Only the explicit finite public projection, never live installation."""
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    root = _owned_path(PUBLIC_ROOT, directory=True, mode=0o2750, gid=13000)
    publisher = OriginalBytes(root, writable=True)
    for row in materials:
        _need(set(row) == {'ref', 'kind', 'bytes'})
        publisher.put_ref(row['ref'], row['bytes'])
        os.chown(root/(row['ref']['sha256']+'.bytes'), 0, 13000)
    os.chown(root/'original-byte-index.json', 0, 13000)
    print(json.dumps({'schema': 'ai4r-rsi-security-runtime-preparation:1', **prepared},
                     sort_keys=True), flush=True)


async def serve_validation(broker_config_path):
    """Installed CLI owner: prepare, wait for root approval, then run once.

    ``broker_config_path`` is the existing protected worker configuration. The
    fixed runtime.json contains only public metadata and the private campaign
    store path. A preexisting capture is inspected and returned BLOCKED; it is
    never reopened as a fresh driver or automatically replayed.
    """
    config = load_config(); root = _campaign_root(config['campaign_root'])
    _owned_path(PUBLIC_ROOT, directory=True, mode=0o2750, gid=13000)
    if any(root.iterdir()):
        outcome = inspect_existing_campaign(root)
        print(json.dumps(outcome, sort_keys=True), flush=True); return outcome
    public = base64.b64decode(config['custodian_public_key']+'='*(-len(config['custodian_public_key'])%4),
                              altchars=b'-_', validate=True)
    _need(len(public) == 32)
    store = SQLiteRunStore(root)
    try:
        callback = worker_validation_factory(store, public_key=public, key_id=config['custodian_key_id'],
            case_bindings=config['case_bindings'], environment_ref=config['environment_ref'],
            originals=config['originals'], prepared_callback=_publish_metadata)
        async def compose(brokers):
            _need(all(PUBLIC_ROOT.resolve() in owner.public.roots for owner in brokers))
            outcome = await callback(brokers)
            print(json.dumps(outcome, sort_keys=True), flush=True)
        from .worker_bootstrap import serve
        await serve(broker_config_path, validation_factory=compose)
    finally: store.close()
