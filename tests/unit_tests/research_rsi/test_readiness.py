"""Read-only diagnosis does not manufacture runtime or IF015 authority."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pytest

from jiuwenswarm.research_rsi import readiness


def test_missing_config_has_specific_safe_blockers_without_creating_state(tmp_path, monkeypatch):
    path = tmp_path / 'private-fixture-label-secret-key' / 'missing.json'
    monkeypatch.setenv('AI4R_RSI_JOB_ROOT', 'forged-ready')
    report = readiness.check_doctor(str(path))
    assert report['status'] == 'BLOCKED' and report['operational_ready'] is False
    assert report['read_only'] is True and report['configured'] is False
    assert 'SERVICE_CONFIG' in report['blockers']
    assert 'IF015_AUTHORITY' in report['blockers']
    assert 'MODEL_RUNTIME' in report['blockers']
    assert 'private-fixture-label-secret-key' not in json.dumps(report)
    assert not path.parent.exists()


def test_doctor_never_instantiates_writable_stores_or_dispatches_diagnosis(tmp_path, monkeypatch):
    from jiuwenswarm.research_rsi import records
    from jiuwenswarm.research_rsi.diagnosis import BoundedDiagnosis
    from jiuwenswarm.research import state
    def forbidden(*args, **kwargs):
        pytest.fail('Read-only doctor attempted writable assembly or model dispatch')
    monkeypatch.setattr(records.RecordStore, '__init__', forbidden)
    monkeypatch.setattr(state.SQLiteRunStore, '__init__', forbidden)
    monkeypatch.setattr(BoundedDiagnosis, 'diagnose', forbidden)
    report = readiness.check_doctor(str(tmp_path / 'absent.json'))
    assert report['status'] == 'BLOCKED'


def test_required_neutral_schema_gap_is_explicit(tmp_path, monkeypatch):
    from jiuwenswarm.research_records import contracts
    class MissingSchemas:
        schemas = {}
    monkeypatch.setattr(contracts, 'ContractData', MissingSchemas)
    report = readiness.check_doctor(str(tmp_path / 'missing.json'))
    assert report['findings'][0]['check'] == 'SCHEMAS'
    assert report['findings'][0]['state'] == 'BLOCKED'


def test_duplicate_config_and_ready_boolean_are_not_fixed_configuration(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{"ready":false,"ready":true}')
    path.chmod(0o600)
    report = readiness.check_doctor(str(path))
    assert 'SERVICE_CONFIG' in report['blockers']
    assert report['status'] == 'BLOCKED'


def test_real_service_loader_still_requires_isolated_uid(tmp_path):
    path = tmp_path / 'config.json'
    value = {'schema': 'ai4r-rsi-jobs-service:1', 'socket_path': '/run/ai4r-rsi/jobs/jobs.sock',
        'allowed_peer_uids': [0], 'record_root': str(tmp_path), 'binding_id': 'native-isolated-v1',
        'resource_binding_ref': {'id': 'unused', 'sha256': 'a' * 64},
        'job_root': str(tmp_path), 'allowed_job_refs': [{'id': 'job_one', 'sha256': 'b' * 64}]}
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    if not hasattr(os, 'geteuid') or os.geteuid() != 12001:
        assert 'SERVICE_CONFIG' in readiness.check_doctor(str(path))['blockers']


def _reader_fixture(tmp_path):
    records = tmp_path / 'records'
    records.mkdir(mode=0o700)
    core = tmp_path / 'core'
    core.mkdir(mode=0o700)
    (core / 'state').mkdir(mode=0o700)
    database = core / 'state/research.sqlite3'
    db = sqlite3.connect(database)
    db.execute('CREATE TABLE artifacts (id TEXT PRIMARY KEY,sha256 TEXT)')
    db.execute('CREATE TABLE records (id TEXT PRIMARY KEY,kind TEXT)')
    raw = b'{"original":"indexed-only"}'
    digest = hashlib.sha256(raw).hexdigest()
    # A malicious-looking opaque ID remains a parameter in a protected index;
    # it never becomes a filesystem path or selects an arbitrary root.
    pin = {'id': '../../opaque-key-label', 'sha256': digest}
    db.execute('INSERT INTO artifacts VALUES(?,?)', (pin['id'], digest))
    db.execute('INSERT INTO records VALUES(?,?)', (pin['id'], 'unit-record'))
    db.commit()
    db.close()
    database.chmod(0o600)
    blob = core / 'artifacts/sha256' / digest[:2] / digest
    blob.parent.mkdir(parents=True, mode=0o700)
    blob.write_bytes(raw)
    blob.chmod(0o600)
    return records, core, database, blob, pin, raw


def _snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


def test_capture_reader_uses_only_existing_index_and_creates_no_files(tmp_path):
    records, core, database, blob, pin, raw = _reader_fixture(tmp_path)
    before = _snapshot(tmp_path)
    if os.name != 'posix':
        with pytest.raises(ValueError):
            readiness._ReadOnlyCaptures(records, uid=0)
        assert _snapshot(tmp_path) == before
        return
    reader = readiness._ReadOnlyCaptures(records, uid=os.getuid())
    try:
        reader.attach_core(core)
        assert reader.read(pin) == raw
        assert reader.record_kind(pin) == 'unit-record'
        with pytest.raises(sqlite3.OperationalError):
            reader.connection.execute('CREATE TABLE forbidden (id TEXT)')
        with pytest.raises(ValueError):
            reader.read(pin | {'id': 'not-in-the-index'})
    finally:
        reader.close()
    assert _snapshot(tmp_path) == before
    assert not Path(str(database) + '-wal').exists()
    assert not Path(str(database) + '-shm').exists()


def test_uncheckpointed_state_is_not_silently_ignored_or_recovered(tmp_path):
    records, core, database, *_ = _reader_fixture(tmp_path)
    wal = Path(str(database) + '-wal')
    wal.write_bytes(b'uncheckpointed-state-is-not-proof')
    before = _snapshot(tmp_path)
    if os.name != 'posix':
        with pytest.raises(ValueError):
            readiness._ReadOnlyCaptures(records, uid=0)
        return
    reader = readiness._ReadOnlyCaptures(records, uid=os.getuid())
    try:
        with pytest.raises(ValueError, match='uncheckpointed'):
            reader.attach_core(core)
    finally:
        reader.close()
    assert _snapshot(tmp_path) == before


def test_indexed_digest_mismatch_is_not_a_configured_capture(tmp_path):
    records, core, _, blob, pin, _ = _reader_fixture(tmp_path)
    blob.write_bytes(b'changed')
    if os.name != 'posix':
        with pytest.raises(ValueError):
            readiness._ReadOnlyCaptures(records, uid=0)
        return
    reader = readiness._ReadOnlyCaptures(records, uid=os.getuid())
    try:
        reader.attach_core(core)
        with pytest.raises(ValueError, match='digest'):
            reader.read(pin)
    finally:
        reader.close()


def test_static_captured_ready_and_pass_flags_never_create_if015_authority(monkeypatch):
    # Controlled composition exercises diagnostic branching, not real runtime
    # qualification. In particular these fabricated flags grant no authority.
    pin = {'id': 'unit', 'sha256': 'a' * 64}
    config = {'record_root': '/unit', 'resource_binding_ref': pin, 'allowed_job_refs': [pin]}
    binding = {'core_root': '/unit/core', 'clearance_policy_ref': pin, 'security_qualification_ref': pin}
    closed = []
    class Captures:
        def __init__(self, *args): pass
        def attach_core(self, *args): pass
        def get(self, *args): return {'ready': True, 'outcome': 'PASS'}
        def close(self): closed.append(True)
    monkeypatch.setattr(readiness, '_regular', lambda *a, **k: b'{}')
    monkeypatch.setattr(readiness, '_path', lambda value: Path(value))
    monkeypatch.setattr(readiness, 'load_config', lambda *a: config)
    monkeypatch.setattr(readiness, '_ReadOnlyCaptures', Captures)
    monkeypatch.setattr(readiness, '_resource_binding', lambda *a: binding)
    monkeypatch.setattr(readiness, '_isolation', lambda *a: None)
    monkeypatch.setattr(readiness, '_operator', lambda *a: {'ready': True})
    monkeypatch.setattr(readiness, '_jobs', lambda *a: [])
    monkeypatch.setattr(readiness, '_frozen_targets', lambda *a: None)
    monkeypatch.setattr(readiness, '_opportunity_preparation', lambda *a: None)
    report = readiness.check_doctor('/unit/config.json')
    assert closed == [True]
    assert report['status'] == 'BLOCKED' and report['operational_ready'] is False
    assert 'SECURITY_CAPTURE' in report['blockers']
    assert 'IF015_AUTHORITY' in report['blockers']
    assert 'CUSTODIAN_RUNTIME' in report['blockers']
    assert 'DIAGNOSIS_RUNTIME' in report['blockers']


def test_doctor_cli_selects_only_explicit_config_and_returns_blocked(capsys, monkeypatch):
    from jiuwenswarm.research_rsi.__main__ import main
    calls = []
    def checked(path):
        calls.append(path)
        return {'status': 'BLOCKED', 'read_only': True, 'blockers': ['IF015_AUTHORITY']}
    monkeypatch.setattr(readiness, 'check_doctor', checked)
    assert main(['doctor', '--config', '/protected/jobs.json']) == 2
    assert calls == ['/protected/jobs.json']
    assert json.loads(capsys.readouterr().out)['blockers'] == ['IF015_AUTHORITY']


def test_new_exact_job_has_preparation_and_diagnosis_contract_without_invented_opportunity(monkeypatch):
    pin = {'id': 'unit', 'sha256': 'a' * 64}
    job = {'schema': 'ai4r-rsi-session-job:2', 'session_ref': pin, 'preparation_ref': pin,
        'diagnosis_contract_ref': pin, 'visible_context_ref': pin, 'proposer_contract_refs': [pin],
        'worker_profile_ref': pin, 'fixture_identity': 'unit:public-fixture-identity', 'target_kind': 'ranking-v1'}
    raw = json.dumps(job).encode()
    grant = {'id': 'job_one', 'sha256': hashlib.sha256(raw).hexdigest()}
    config = {'allowed_job_refs': [grant], 'job_root': '/protected/jobs'}
    monkeypatch.setattr(readiness, '_regular', lambda *a, **k: raw)
    monkeypatch.setattr(readiness, '_path', lambda value: Path(value))
    reads = []
    class Reader:
        def read(self, ref): reads.append(ref)
    assert readiness._jobs(Reader(), config, {'approved_session_refs': [pin]}) == [job]
    assert reads == [pin]
    # A future model output cannot be precomputed into job authority.
    invalid = dict(job, opportunity_ref=pin)
    raw = json.dumps(invalid).encode()
    config['allowed_job_refs'] = [dict(grant, sha256=hashlib.sha256(raw).hexdigest())]
    with pytest.raises(ValueError):
        readiness._jobs(Reader(), config, {'approved_session_refs': [pin]})
