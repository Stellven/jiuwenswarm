"""Benign metadata/approval controls; no boundary program or model executes."""
import asyncio
import copy
import hashlib
import os
import types

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_records.original_bytes import OriginalBytes
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi import security_runtime as runtime_module
from jiuwenswarm.research_rsi.security_runtime import (
    APPROVAL_SCHEMA, ProtectedOriginalKinds, RuntimeUnavailable, SecurityRuntime,
    import_metadata, validation_factory, worker_validation_factory,
)
from jiuwenswarm.research_rsi.worker import PublicBytes, WorkerBroker
from jiuwenswarm.research_records.contracts import ContractData


def pin(name='unit:metadata'):
    return {'id': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}


def approval():
    return dict(schema='ai4r-rsi-security-runtime-approval:1', plan_ref=pin('unit:plan'),
        scope_ref=pin('unit:scope'), validation_profile_ref=pin('unit:profile'),
        attack_pins_ref=pin('unit:attacks'), custodian_key_id='unit:public-key-only',
        custodian_public_key_sha256=hashlib.sha256(b'k'*32).hexdigest(),
        rpc_session_id='unit:fixed-custody-rpc', capability='unit:capability-not-a-live-secret')


def test_approval_cannot_choose_code_or_weaken_exact_scope():
    contract = ContractData(); value = approval(); contract.validate(APPROVAL_SCHEMA, value)
    for changed in (dict(value, factory='caller.module'), dict(value, skip_scope=True),
                    dict(value, approved=True), dict(value, capability='short')):
        with pytest.raises(ValueError): contract.validate(APPROVAL_SCHEMA, changed)
    missing = dict(value); missing.pop('attack_pins_ref')
    with pytest.raises(ValueError): contract.validate(APPROVAL_SCHEMA, missing)


@pytest.fixture
def originals(tmp_path, monkeypatch):
    # Public-only capture mechanics are tested cross-platform. These explicit
    # ownership gate doubles cannot execute a driver or qualify evidence.
    monkeypatch.setattr(runtime_module, '_root', lambda: None)
    monkeypatch.setattr(runtime_module, '_protected_store', lambda _: None)
    store = SQLiteRunStore(tmp_path/'capture')
    if os.name == 'posix':
        publisher = OriginalBytes(tmp_path/'public', writable=True)
        public = PublicBytes([publisher.root])
    else:
        # Windows cannot establish POSIX publication custody. Keep these
        # public import vectors in a clearly controlled transport instead of
        # weakening the actual OriginalBytes permission checks.
        class PublicVector:
            def __init__(self): self.raw = {}
            def put(self, value):
                raw = encoded(value); digest = hashlib.sha256(raw).hexdigest()
                pin = {'id': digest+'.json', 'sha256': digest}; self.raw[pin['id']] = raw; return pin
            def read(self, pin): return self.raw[pin['id']]
        publisher = PublicVector(); public = PublicBytes([]); public.read = publisher.read
    try: yield store, publisher, public
    finally: store.close()


def test_explicit_import_preserves_actual_profile_type_and_never_walks_json(originals):
    store, publisher, public = originals
    unrelated = pin('unit:absent-no-recursive-import')
    raw_ref = publisher.put({'public': 'metadata only', 'unfollowed_ref': unrelated})
    profile = dict(schema='ai4r-rsi-worker-profile:3', target_kind='normalize-labels-v1',
        process_policy='single_process_seccomp_v1', session_ref=unrelated, target_ref=unrelated,
        parent_ref=unrelated, contract_ref=unrelated, environment_ref=unrelated, hardware_ref=unrelated,
        memory_mb=128, pids_max=8, timeout_s=1)
    profile_ref = publisher.put(profile)
    before = store.connection.total_changes
    imported = import_metadata(store, public, [{'ref': raw_ref, 'kind': None},
        {'ref': profile_ref, 'kind': 'rsi-worker-profile'}])
    assert len(imported) == 2 and store.connection.total_changes > before
    assert store.record_kind(profile_ref) == 'rsi-worker-profile'
    assert store.read_blob(raw_ref) == public.read(raw_ref)
    with pytest.raises(ResearchError): store.read_blob(unrelated)
    kinds = ProtectedOriginalKinds(store)
    assert kinds(profile_ref) == 'rsi-worker-profile'
    assert kinds(raw_ref) == 'original-bytes'
    with pytest.raises(ResearchError): kinds(unrelated)


def test_import_rejects_case_type_forgery_and_batch_validates_before_writing(originals):
    store, publisher, public = originals
    raw_ref = publisher.put({'unit': 'No evidence owner'})
    before = store.connection.total_changes
    for kind in ('execution-receipt', 'rsi-security-case-observation', 'private-key', 'rsi-policy-denial'):
        with pytest.raises(RuntimeUnavailable):
            import_metadata(store, public, [{'ref': raw_ref, 'kind': kind}])
    with pytest.raises(RuntimeUnavailable):
        import_metadata(store, public, [{'ref': raw_ref, 'kind': None}, {'ref': raw_ref, 'kind': None}])
    assert store.connection.total_changes == before


def test_import_rejects_existing_foreign_typed_identity(originals):
    store, publisher, public = originals
    profile = dict(schema='ai4r-rsi-worker-profile:3', target_kind='ranking-v1',
        process_policy='single_process_seccomp_v1', session_ref=pin(), target_ref=pin(), parent_ref=pin(),
        contract_ref=pin(), environment_ref=pin(), hardware_ref=pin(), memory_mb=128, pids_max=8, timeout_s=1)
    profile_ref = publisher.put(profile)
    store._capture(public.read(profile_ref), record_id=profile_ref['id'], media_type='application/json', kind='foreign-owner')
    before = store.connection.total_changes
    with pytest.raises(RuntimeUnavailable):
        import_metadata(store, public, [{'ref': profile_ref, 'kind': 'rsi-worker-profile'}])
    assert store.record_kind(profile_ref) == 'foreign-owner'
    assert store.connection.total_changes == before


def test_prepare_captures_metadata_but_never_opens_campaign_or_calls_driver(originals, monkeypatch):
    """Controlled capture owners isolate phase ordering, never qualification."""
    store, publisher, public = originals; calls = []
    metadata = store.put_blob(encoded({'unit': 'Metadata phase-order control; not current source evidence'}))
    profile = dict(schema='ai4r-rsi-worker-profile:3', target_kind='ranking-v1',
        process_policy='single_process_seccomp_v1', session_ref=metadata, target_ref=metadata,
        parent_ref=metadata, contract_ref=metadata, environment_ref=metadata, hardware_ref=metadata,
        memory_mb=128, pids_max=8, timeout_s=1)
    profile_ref = publisher.put(profile)
    worker = object.__new__(WorkerBroker); worker.public = public; worker.profiles = {encoded(profile_ref): profile}
    runtime = SecurityRuntime(store, worker_owner=worker, public_key=b'k'*32, key_id='unit:key')
    attacks = dict(schema='unit:CONTROLLED-metadata', program_prefix_ref=metadata,
                   attacks={case: metadata for case in runtime_module.CASES})
    attack_ref = store.append_record('rsi-security-attack-pins', attacks)
    pins = dict(installed_build_ref=metadata, procedure_ref=metadata, assertion_manifest_ref=metadata,
        source_manifest_ref=metadata, source_refs=[{'path': 'research/contracts/rsi_security_cases.py', 'ref': metadata}])
    profile_pins_ref = store.append_record('rsi-security-profile-pins', pins)
    scope = dict(worker_driver_ref=metadata, executor_ref=metadata, probe_ref=metadata)
    scope_ref = store.append_record('rsi-security-scope', scope)
    def capture_pins(*args, **kwargs):
        calls.append('capture-pins')
        return dict(validation_profile_ref=profile_pins_ref, runtime_build_ref=metadata,
            attack_pins_ref=attack_ref, procedure_ref=metadata, assertion_manifest_ref=metadata)
    def capture_scope(*args, **kwargs): calls.append('capture-scope'); return {'scope_ref': scope_ref}
    class MetadataObserver:
        def __init__(self, *args, **kwargs): calls.append('construct-observer')
        def __call__(self, *args): pytest.fail('Preparation must not assert a case proof')
    class MetadataDriver:
        def __init__(self, *args, **kwargs):
            calls.append('construct-descriptor')
            self.descriptor_ref = store.append_record('rsi-security-driver', {'source_ref': metadata})
        def bind_plan(self, plan_ref): calls.append('bind-plan'); self.plan_ref = plan_ref
        async def observe(self, *args, **kwargs): pytest.fail('Metadata preparation dispatched a driver')
    def plan(*args, **kwargs): calls.append('capture-plan'); return store.append_record('rsi-security-campaign-plan', {'unit': 'CONTROLLED'})
    monkeypatch.setattr(runtime_module, 'capture_verification_pins', capture_pins)
    monkeypatch.setattr(runtime_module, 'capture_worker_scope', capture_scope)
    monkeypatch.setattr(runtime_module, 'FiniteCaseObserver', MetadataObserver)
    monkeypatch.setattr(runtime_module, 'SecurityBoundaryDriver', MetadataDriver)
    monkeypatch.setattr(runtime_module, 'prepare_security_campaign_plan', plan)
    monkeypatch.setattr(runtime_module, 'CampaignLedger', lambda *_: pytest.fail('Preparation opened a campaign ledger'))
    monkeypatch.setattr(runtime_module, 'RuntimeScopeObserver', lambda **_: pytest.fail('Preparation asserted live host scope'))
    result = runtime.prepare(case_bindings={}, environment_ref=metadata,
        originals=[{'ref': profile_ref, 'kind': 'rsi-worker-profile'}])
    assert result['status'] == 'CAPTURED_NOT_APPROVED'
    assert calls == ['capture-pins', 'capture-scope', 'construct-observer', 'construct-descriptor', 'capture-plan', 'bind-plan']
    assert runtime.metadata_materials() and not (store.root/'security-campaign.sqlite').exists()
    with pytest.raises(RuntimeUnavailable):
        runtime.prepare(case_bindings={}, environment_ref=metadata,
            originals=[{'ref': profile_ref, 'kind': 'rsi-worker-profile'}])


def runtime_without_preparation(store, public):
    worker = object.__new__(WorkerBroker); worker.public = public
    return SecurityRuntime(store, worker_owner=worker, public_key=b'k'*32, key_id='unit:public-key-only')


def prepared_runtime(store, public):
    runtime = runtime_without_preparation(store, public)
    approved = approval()
    runtime._prepared = {key: approved[key] for key in
        ('plan_ref', 'scope_ref', 'validation_profile_ref', 'attack_pins_ref')}
    return runtime


@pytest.mark.asyncio
async def test_missing_preparation_or_approval_never_reads_scope_or_claims_case(originals, monkeypatch):
    store, _, public = originals
    runtime = runtime_without_preparation(store, public)
    before = store.connection.total_changes
    result = await runtime.run_approved(approved_plan_refs=[], rpc_session_id='unit', capability='unit:no-effect-capability')
    assert result['blockers'] == ['METADATA_NOT_PREPARED']
    runtime = prepared_runtime(store, public)
    monkeypatch.setattr(store, 'read_record', lambda *a, **k: pytest.fail('No scope read without exact approval'))
    result = await runtime.run_approved(approved_plan_refs=[pin('unit:foreign-plan')],
        rpc_session_id='unit', capability='unit:no-effect-capability')
    assert result['blockers'] == ['EXACT_PLAN_APPROVAL_REQUIRED']
    assert store.connection.total_changes == before
    assert not (store.root/'security-campaign.sqlite').exists()


@pytest.mark.asyncio
async def test_missing_host_capture_blocks_before_campaign_or_signer(originals, monkeypatch):
    store, _, public = originals
    runtime = prepared_runtime(store, public)
    monkeypatch.setattr(store, 'read_record', lambda *_a, **_k: {'unit': 'scope metadata only'})
    class MissingScope:
        def __init__(self, **kwargs):
            assert kwargs['worker_owner'] is runtime.worker
        def __call__(self, _): raise ValueError('No actual host observation')
    monkeypatch.setattr(runtime_module, 'RuntimeScopeObserver', MissingScope)
    monkeypatch.setattr(runtime_module, 'CampaignLedger', lambda *_: pytest.fail('No ledger before host proof'))
    result = await runtime.run_approved(approved_plan_refs=[runtime._prepared['plan_ref']],
        rpc_session_id='unit', capability='unit:no-effect-capability')
    assert result['status'] == 'BLOCKED' and result['campaign_status_ref'] is None
    assert not (store.root/'security-campaign.sqlite').exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['false', 'bridge', 'integrity'])
async def test_missing_remote_signer_authority_blocks_before_campaign_or_driver(originals, monkeypatch, failure):
    store, _, public = originals
    runtime = prepared_runtime(store, public); calls = []
    scope = {'unit': 'controlled metadata; no kernel observation'}
    monkeypatch.setattr(store, 'read_record', lambda *_a, **_k: scope)
    class ControlledScope:
        def __init__(self, **kwargs): pass
        def __call__(self, value): calls.append('scope'); return value
    monkeypatch.setattr(runtime_module, 'RuntimeScopeObserver', ControlledScope)
    monkeypatch.setattr(runtime_module, 'build_verification_profile', lambda *_: calls.append('profile'))
    class MissingAuthority:
        key_id = 'unit:public-key-only'
        def __init__(self, *args, **kwargs): pass
        def public_bytes(self): return b'k'*32
        async def authorized(self):
            calls.append('custodian')
            if failure == 'bridge':
                from jiuwenswarm.research.bridge import BridgeError
                raise BridgeError('unit:RPC_NOT_READY')
            if failure == 'integrity':
                from jiuwenswarm.research.router_client import PlatformIntegrityError
                raise PlatformIntegrityError('unit:RPC_PEER_UNAVAILABLE')
            return False
    import sys
    monkeypatch.setitem(sys.modules, 'jiuwenswarm.research_rsi.security_custody',
                        types.SimpleNamespace(ValidationHaltSigner=MissingAuthority))
    monkeypatch.setattr(runtime_module, 'CampaignLedger', lambda *_: pytest.fail('No ledger before signer authority'))
    result = await runtime.run_approved(approved_plan_refs=[runtime._prepared['plan_ref']],
        rpc_session_id='unit', capability='unit:no-effect-capability')
    assert result['status'] == 'BLOCKED' and calls == ['scope', 'profile', 'custodian']


def publication_pending(runtime):
    runtime._authority = object()  # No authority is used without exact approval.
    runtime._publication = dict(status='REVIEW_REQUIRED', plan_ref=pin('unit:plan'),
        campaign_status_ref=pin('unit:status'), qualification_ref=pin('unit:qualification'),
        installation_closure_ref=pin('unit:closure'), scope_ref=pin('unit:scope'))
    return runtime._publication


def test_missing_publication_approval_never_calls_publisher(originals, monkeypatch):
    store, _, public = originals; runtime = prepared_runtime(store, public)
    publication_pending(runtime)
    monkeypatch.setattr(runtime_module, '_read_root_json', lambda *_: (_ for _ in ()).throw(FileNotFoundError()))
    from jiuwenswarm.research_rsi import security_publication
    monkeypatch.setattr(security_publication, 'publish_security_installation', lambda *a, **k: pytest.fail('No publication without approval'))
    before = store.connection.total_changes
    result = runtime.publish_from_approval_file()
    assert result['status'] == 'BLOCKED' and store.connection.total_changes == before


@pytest.mark.parametrize('field', ['plan_ref', 'campaign_status_ref', 'qualification_ref', 'installation_closure_ref', 'scope_ref'])
def test_inexact_publication_approval_cannot_touch_installation(originals, monkeypatch, field):
    store, _, public = originals; runtime = prepared_runtime(store, public)
    pending = publication_pending(runtime)
    approval = {key: value for key, value in pending.items() if key != 'status'}
    approval.update(schema='ai4r-rsi-security-runtime-publication-approval:1',
                    rpc_session_id='unit:scope', rpc_capability='A'*43)
    ContractData().validate(runtime_module.PUBLICATION_APPROVAL_SCHEMA, approval)
    approval[field] = pin('unit:foreign:'+field)
    monkeypatch.setattr(runtime_module, '_read_root_json', lambda *_: approval)
    monkeypatch.setattr(store, 'read_record', lambda *_a, **_k: pytest.fail('No closure read for inexact approval'))
    result = runtime.publish_from_approval_file()
    assert result['status'] == 'BLOCKED'


def test_reached_raw_empty_bytes_retain_original_digest_and_kind(originals):
    store, _, _ = originals
    empty = store.put_blob(b''); reached = runtime_module.ReachedOriginals(store)
    assert reached.read(empty) == b'' and reached.kind(empty) == 'original-bytes'
    assert list(reached.rows.values()) == [{'ref': empty, 'kind': 'original-bytes'}]


@pytest.mark.asyncio
async def test_missing_approval_file_and_foreign_pins_do_not_dispatch(originals, monkeypatch):
    store, _, public = originals; runtime = prepared_runtime(store, public)
    monkeypatch.setattr(runtime_module, 'read_approval', lambda: (_ for _ in ()).throw(FileNotFoundError()))
    assert (await runtime.run_from_approval_file())['blockers'] == ['EXACT_ROOT_APPROVAL_UNAVAILABLE']
    value = approval(); value['attack_pins_ref'] = pin('unit:foreign-attacks')
    monkeypatch.setattr(runtime_module, 'read_approval', lambda: value)
    assert (await runtime.run_from_approval_file())['blockers'] == ['EXACT_ROOT_APPROVAL_UNAVAILABLE']
    assert not (store.root/'security-campaign.sqlite').exists()


@pytest.mark.asyncio
async def test_bootstrap_rejects_unrelated_or_incomplete_owner_tuple_before_prepare(originals):
    store, _, public = originals
    callback = worker_validation_factory(store, public_key=b'k'*32, key_id='unit:key',
        case_bindings={}, environment_ref=pin(), originals=[])
    with pytest.raises(RuntimeUnavailable): await callback(())
    with pytest.raises(RuntimeUnavailable): await callback((object(), object()))
    assert not (store.root/'security-campaign.sqlite').exists()


def test_root_constructor_rejects_arbitrary_owner_without_kernel_effects(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_module, '_root', lambda: None)
    monkeypatch.setattr(runtime_module, '_protected_store', lambda _: None)
    store = SQLiteRunStore(tmp_path/'capture')
    try:
        with pytest.raises(RuntimeUnavailable):
            SecurityRuntime(store, worker_owner=object(), public_key=b'k'*32, key_id='unit:key')
    finally: store.close()


def test_runtime_config_is_closed_and_cannot_select_program_factory_or_private_key():
    import base64
    value = dict(schema='ai4r-rsi-security-runtime-config:1',
        campaign_root=str(runtime_module.CAMPAIGN_ROOT).replace('\\', '/'),
        custodian_public_key=base64.urlsafe_b64encode(b'k'*32).decode().rstrip('='),
        custodian_key_id='unit:public-pin', environment_ref=pin(),
        case_bindings={case: {'session_ref': pin('unit:session:'+case), 'worker_profile_ref': pin('unit:profile:'+case)}
                       for case in runtime_module.CASES}, originals=[{'ref': pin(), 'kind': None}])
    # The deployment path is POSIX even when schema controls run on Windows.
    value['campaign_root'] = '/var/lib/ai4r-rsi-validation-campaign'
    contract = ContractData(); contract.validate(runtime_module.CONFIG_SCHEMA, value)
    for changed in (dict(value, factory='caller:factory'), dict(value, command=['python']),
                    dict(value, private_key_file='/tmp/key'), dict(value, campaign_root='/tmp/arbitrary')):
        with pytest.raises(ValueError): contract.validate(runtime_module.CONFIG_SCHEMA, changed)


def test_restart_inspects_original_plan_without_reopening_write_owner(tmp_path, monkeypatch):
    store = SQLiteRunStore(tmp_path/'capture')
    plan = dict(schema='ai4r-rsi-security-campaign-plan:1', id='unit:prior-live-plan',
        scope_ref=pin(), observer_ref=pin(), driver_ref=pin(), verification_profile_ref=pin(),
        procedure_ref=pin(), assertion_manifest_ref=pin(),
        case_bindings={case: {'session_ref': pin('unit:session:'+case), 'worker_profile_ref': pin('unit:profile:'+case)}
                       for case in runtime_module.CASES})
    original_ref = store.append_record('rsi-security-campaign-plan', plan)
    root = store.root; store.close()
    monkeypatch.setattr(runtime_module, '_campaign_root', lambda value: root)
    monkeypatch.setattr(runtime_module, '_owned_path', lambda value, **kwargs: __import__('pathlib').Path(value))
    before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    result = runtime_module.inspect_existing_campaign(root)
    assert result['status'] == 'BLOCKED' and result['plan_refs'] == [original_ref]
    assert result['blockers'] == ['EXISTING_CAMPAIGN_REQUIRES_INSPECTION']
    assert before == {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    # Never present an immutable pre-WAL snapshot as current owner evidence.
    wal = root/'state'/'research.sqlite3-wal'; wal.write_bytes(b'unit:nonempty-WAL-do-not-checkpoint')
    result = runtime_module.inspect_existing_campaign(root)
    assert result['blockers'] == ['CURRENT_WAL_REQUIRES_ORIGINAL_OWNER'] and result['plan_refs'] == []
    assert wal.read_bytes() == b'unit:nonempty-WAL-do-not-checkpoint'
