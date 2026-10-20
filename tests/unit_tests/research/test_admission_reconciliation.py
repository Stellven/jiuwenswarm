"""Completed IF013 reconciliation controls, using explicit forged-kernel unit data.

These records test custody/once validation only. They do not qualify a kernel,
carrier, admission, model or runtime profile.
"""
import copy
from pathlib import Path

import pytest

from jiuwenswarm.research import admission_executor as admission
from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.executor_rpc import ClaimLedger
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from tests.unit_tests.research.test_admission_self_tests import self_test_capture_fixture


class ReadOnlyCustody:
    """Only the existing finite custody reader surface, with no DB/scan/write."""
    def __init__(self, store):
        self.reads = []
        self.store = store

    def read_blob(self, ref):
        self.reads.append(('blob', copy.deepcopy(ref)))
        return self.store.read_blob(ref)

    def read_record(self, ref, **kwargs):
        self.reads.append(('record', copy.deepcopy(ref)))
        return self.store.read_record(ref, **kwargs)

    def record_kind(self, ref):
        self.reads.append(('kind', copy.deepcopy(ref)))
        return self.store.record_kind(ref)


def fixture(tmp_path):
    store, actor, test, declaration, bodies, proof = self_test_capture_fixture(tmp_path / 'state')
    result = store.append_record('admission-self-test-result', proof)
    job_ref = proof['job_ref']
    job = store.read_record(job_ref)
    provider = admission.AdmissionTestProvider(store, configuration_ref=job['configuration_ref'],
        execution_profile_ref=job['execution_profile_ref'], rpc=None)
    # Prove this original immutable job passes the live pre-effect authorizer.
    assert provider.authorize(job_ref) == job
    ledger = ClaimLedger(tmp_path / 'ledger')
    key = {'operation': 'admission_self_test', 'job_ref': job_ref}
    return store, ledger, key, result, proof, provider


def producer(store, ledger, tmp_path, authorize):
    return admission.AdmissionExecutor(ReadOnlyCustody(store), object(), authorize=authorize,
        ledger=ledger, staging_root=tmp_path / 'must-not-stage')


def fail_authorize(_):
    pytest.fail('Terminal reconciliation attempted fresh execution authorization')


def complete(ledger, key, result):
    identity, prior = ledger.claim(key)
    assert prior is None
    ledger.complete(identity, {'result_ref': result})


def snapshot(store, ledger):
    return (store.connection.execute('SELECT * FROM artifacts ORDER BY id').fetchall(),
            store.connection.execute('SELECT * FROM records ORDER BY id').fetchall(),
            ledger.db.execute('SELECT * FROM claims ORDER BY identity').fetchall())


@pytest.mark.asyncio
@pytest.mark.parametrize('expired', [False, True], ids=['live-window', 'expired'])
async def test_completed_exact_ref_reconciles_after_store_and_ledger_reopen_without_effects(tmp_path, monkeypatch, expired):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    complete(ledger, key, result)
    ledger.close()
    store.close()
    store = SQLiteRunStore(tmp_path / 'state')
    ledger = ClaimLedger(tmp_path / 'ledger')
    if expired:
        monkeypatch.setattr(admission.time, 'time', lambda: admission.expiry(store.read_record(key['job_ref'])['expires_at']) + 1)
    before = snapshot(store, ledger)
    subject = producer(store, ledger, tmp_path, fail_authorize)
    monkeypatch.setattr(ledger, 'claim', lambda _: pytest.fail('Read-only reconcile created or consumed a claim'))
    try:
        assert await subject.run(copy.deepcopy(key['job_ref'])) == result
        assert await subject.run(copy.deepcopy(key['job_ref'])) == result
        assert snapshot(store, ledger) == before and subject.active == {}
        assert not (tmp_path / 'must-not-stage').exists()
        read_refs = [ref for _, ref in subject.store.reads]
        for ref in (key['job_ref'], result, proof['candidate_execution_refs'][0], proof['driver_execution_ref'], proof['output_refs'][0]):
            assert ref in read_refs
    finally:
        ledger.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['result_kind', 'result_hash', 'foreign_job', 'missing_candidate', 'foreign_candidate',
    'driver_inventory', 'candidate_inventory', 'wrong_configuration', 'model_call', 'terminal_envelope'])
async def test_completed_cache_revalidates_original_evidence_before_return(tmp_path, fault):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    if fault == 'result_kind':
        result = store.put_blob(json_bytes(proof))
    elif fault == 'result_hash':
        result = dict(result, sha256='0' * 64)
    elif fault == 'foreign_job':
        proof['job_ref'] = proof['test_ref']
    elif fault == 'missing_candidate':
        proof['candidate_execution_refs'] = []
    elif fault == 'foreign_candidate':
        candidate = store.read_record(proof['candidate_execution_refs'][0])
        candidate['job_ref'] = proof['test_ref']
        candidate['id'] += ':foreign'
        proof['candidate_execution_refs'] = [store.append_record('admission-self-test-candidate-execution', candidate)]
    elif fault == 'driver_inventory':
        receipt = store.read_record(proof['driver_execution_ref'])
        reported = store.read_record(receipt['stdout_ref'])
        reported['outputs'] = {}
        receipt['stdout_ref'] = store.put_blob(json_bytes(reported))
        proof['execution_receipt_ref'] = proof['driver_execution_ref'] = store.append_record('admission-self-test-execution', receipt)
    elif fault == 'candidate_inventory':
        proof['output_refs'] = [store.put_blob(json_bytes({'time_s':2,'model_calls':0,'memory_mb':1}))]
    elif fault == 'wrong_configuration':
        proof['configuration_ref'] = proof['test_ref']
    elif fault == 'model_call':
        proof['model_call_refs'] = [proof['test_ref']]
    if fault not in {'result_kind', 'result_hash', 'terminal_envelope'}:
        proof['id'] += ':tampered'
        result = store.append_record('admission-self-test-result', proof)
    complete(ledger, key, result)
    if fault == 'terminal_envelope':
        ledger.db.execute('UPDATE claims SET result=?', (json_bytes({'result_ref':result,'authorized':True}).decode(),))
    before = snapshot(store, ledger)
    try:
        with pytest.raises((ResearchError, BridgeError)):
            await producer(store, ledger, tmp_path, provider.authorize).run(key['job_ref'])
        assert snapshot(store, ledger) == before
        assert not (tmp_path / 'must-not-stage').exists()
    finally:
        ledger.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['configuration', 'profile', 'runtime', 'driver', 'driver_body', 'body', 'test', 'request',
    'candidate_input', 'candidate_output', 'candidate_probe', 'driver_stdout', 'driver_stderr'])
async def test_completed_cache_requires_original_full_custody_bytes(tmp_path, missing):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    job = store.read_record(key['job_ref'])
    profile = store.read_record(job['execution_profile_ref'])
    candidate = store.read_record(proof['candidate_execution_refs'][0])
    candidate_receipt = store.read_record(candidate['execution_receipt_ref'])
    driver = store.read_record(proof['driver_execution_ref'])
    refs = {'configuration': job['configuration_ref'], 'profile': job['execution_profile_ref'],
        'runtime': profile['runtime_ref'], 'driver': job['driver_ref'],
        'driver_body': store.read_record(job['driver_ref'])['_admission_driver.py'], 'body': job['body_refs']['candidate.py'],
        'test': job['test_ref'], 'request': job['admission_request_ref'], 'candidate_input': candidate['input_ref'],
        'candidate_output': proof['output_refs'][0], 'candidate_probe': candidate_receipt['observed_limits']['isolation_probe_ref'],
        'driver_stdout': driver['stdout_ref'], 'driver_stderr': driver['stderr_ref']}
    complete(ledger, key, result)
    # Remove only this disposable fixture's exact original bytes.
    store.blobs.path_for(refs[missing]['sha256']).unlink()
    before = snapshot(store, ledger)
    try:
        with pytest.raises((ResearchError, BridgeError)):
            await producer(store, ledger, tmp_path, provider.authorize).run(key['job_ref'])
        assert snapshot(store, ledger) == before
        assert not (tmp_path / 'must-not-stage').exists()
    finally:
        ledger.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('claimed', [False, True], ids=['unclaimed', 'started-unknown'])
async def test_expired_uncompleted_job_never_claims_or_replays(tmp_path, monkeypatch, claimed):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    if claimed:
        ledger.claim(key)
    ledger.close()
    ledger = ClaimLedger(tmp_path / 'ledger')
    monkeypatch.setattr(admission.time, 'time', lambda: admission.expiry(store.read_record(key['job_ref'])['expires_at']) + 1)
    before = snapshot(store, ledger)
    try:
        with pytest.raises((ResearchError, BridgeError)):
            await producer(store, ledger, tmp_path, provider.authorize).run(key['job_ref'])
        assert snapshot(store, ledger) == before and not (tmp_path / 'must-not-stage').exists()
    finally:
        ledger.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['wrong_hash', 'unknown_id'])
async def test_completed_job_identity_cannot_be_rebound(tmp_path, fault):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    complete(ledger, key, result)
    wrong = dict(key['job_ref'], **({'sha256': '0' * 64} if fault == 'wrong_hash' else {'id': 'unknown-job'}))
    before = snapshot(store, ledger)
    try:
        with pytest.raises((ResearchError, BridgeError)):
            await producer(store, ledger, tmp_path, provider.authorize).run(wrong)
        assert snapshot(store, ledger) == before and not (tmp_path / 'must-not-stage').exists()
    finally:
        ledger.close()
        store.close()


def test_ledger_lookup_is_select_only_exact_and_survives_reopen(tmp_path):
    ledger = ClaimLedger(tmp_path / 'ledger')
    key = {'operation':'admission_self_test', 'job_ref':{'id':'job','sha256':'a'*64}}
    result = {'result_ref':{'id':'result','sha256':'b'*64}}
    try:
        assert ledger.lookup(key) is None
        assert ledger.db.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 0
        identity, _ = ledger.claim(key)
        with pytest.raises(BridgeError, match='DELIVERY_UNKNOWN'):
            ledger.lookup(key)
        ledger.complete(identity, result)
        ledger.close()
        ledger = ClaimLedger(tmp_path / 'ledger')
        before = ledger.db.total_changes
        assert ledger.lookup(copy.deepcopy(key)) == result
        assert ledger.lookup({'operation':'other','job_ref':key['job_ref']}) is None
        assert ledger.lookup({'operation':key['operation'],'job_ref':dict(key['job_ref'],sha256='c'*64)}) is None
        assert ledger.db.total_changes == before
        assert ledger.claim(key) == (identity,result)  # Existing claim semantics unchanged.
    finally:
        ledger.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [None, [], 'not-an-envelope'], ids=['null', 'array', 'string'])
async def test_completed_malformed_ledger_payload_never_becomes_absent_or_authorizes(tmp_path, payload):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    identity, _ = ledger.claim(key)
    ledger.complete(identity, payload)
    before = snapshot(store, ledger)
    try:
        with pytest.raises(BridgeError, match='AUDIT_UNAVAILABLE'):
            await producer(store, ledger, tmp_path, fail_authorize).run(key['job_ref'])
        assert snapshot(store, ledger) == before and not (tmp_path / 'must-not-stage').exists()
    finally:
        ledger.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [None, [], 'not-an-envelope'], ids=['null', 'array', 'string'])
async def test_concurrent_malformed_completion_between_lookup_and_claim_never_reexecutes(tmp_path, monkeypatch, payload):
    store, ledger, key, result, proof, provider = fixture(tmp_path)
    original_lookup = ledger.lookup
    observations = {}
    authorizations = []
    before = snapshot(store, ledger)

    def concurrent_completion(actual_key):
        assert actual_key == key and original_lookup(actual_key) is None
        identity, prior = ledger.claim(actual_key)
        assert prior is None
        ledger.complete(identity, payload)
        observations['completed'] = ledger.db.execute('SELECT * FROM claims').fetchall()
        observations['changes'] = ledger.db.total_changes
        return None  # Exact result of the first SELECT before the competing completion.

    def authorize(ref):
        authorizations.append(copy.deepcopy(ref))
        return provider.authorize(ref)

    monkeypatch.setattr(ledger, 'lookup', concurrent_completion)
    subject = producer(store, ledger, tmp_path, authorize)
    try:
        with pytest.raises(BridgeError, match='AUDIT_UNAVAILABLE'):
            await subject.run(key['job_ref'])
        assert authorizations == [key['job_ref']]  # The initial live check is allowed, never another grant.
        assert snapshot(store, ledger)[:2] == before[:2]
        assert ledger.db.execute('SELECT * FROM claims').fetchall() == observations['completed']
        assert ledger.db.total_changes == observations['changes']
        assert not (tmp_path / 'must-not-stage').exists() and subject.active == {}
    finally:
        ledger.close()
        store.close()
