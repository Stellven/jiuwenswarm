import hashlib
from pathlib import Path
import sqlite3

import pytest

from jiuwenswarm.factory.store import (
    ArtifactConflict, NotFound, PersistenceFailed, ScopeDenied, StaleRevision, Store,
)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / 'store') as value:
        value.create_task({'task_id': 'a', 'objective': 'measure'})
        value.create_task({'task_id': 'b', 'objective': 'compare'})
        yield value


def test_restart_roundtrip(tmp_path):
    home = tmp_path / 'store'
    data = b'\x00evidence\xff\n'
    with Store(home) as store:
        store.create_task({'task_id': 'a', 'objective': 'measure'})
        artifact = store.put_artifact('a', 'blob', data, 'application/octet-stream', 'run')
    with Store(home) as store:
        assert store.artifact_bytes('a', 'blob') == data
        assert store.read_artifact('a', 'blob') == artifact
        assert artifact['sha256'] == hashlib.sha256(data).hexdigest()
        assert not Path(artifact['location']).is_absolute()
        assert store._db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert store._db.execute('PRAGMA synchronous').fetchone()[0] == 2


def test_stale_decision_rejected(store):
    with Store(store.home) as concurrent:
        first = store.advance_decision('a', 0, {'hypothesis': 'first'})
        with pytest.raises(StaleRevision):
            concurrent.advance_decision('a', 0, {'hypothesis': 'stale'})
        second = concurrent.advance_decision('a', 1, {'reason_for_change': 'new evidence'})
    assert first['rev'] == 1 and second['parent_rev'] == 1 and second['rev'] == 2
    assert store.get_task('a')['current_decision_rev'] == 2
    assert len(store.dump('a')['decisions']) == 2


def test_artifact_conflict_rejected(store):
    before = store.put_artifact('a', 'blob', b'one', 'text/plain', 'r')
    with pytest.raises(ArtifactConflict):
        store.put_artifact('a', 'blob', b'two', 'text/plain', 'r')
    assert store.read_artifact('a', 'blob') == before
    assert store.artifact_bytes('a', 'blob') == b'one'
    assert len(list((store.home / 'artifacts').rglob('*'))) == 2


def test_idempotent_artifact_put(store, tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'one')
    before = store.put_artifact('a', 'blob', source, 'text/plain', 'r')
    cursor = store.get_task('a')['evidence_cursor']
    assert store.put_artifact('a', 'blob', b'one', 'other/type', None) == before
    assert store.get_task('a')['evidence_cursor'] == cursor
    assert len(store.dump('a')['artifacts']) == 1


@pytest.mark.parametrize('stage', ['artifact_temp_fsynced', 'artifact_renamed', 'artifact_dir_fsynced', 'before_commit'])
def test_persistence_failure_no_ack(store, stage):
    cursor = store.get_task('a')['evidence_cursor']

    def fault(current):
        if current == stage:
            raise OSError('disk failure')

    store.fault = fault
    with pytest.raises(PersistenceFailed):
        store.put_artifact('a', 'blob', b'one', 'text/plain', 'r')
    store.fault = None
    with Store(store.home) as observer:
        with pytest.raises(NotFound):
            observer.read('a', 'blob')
        assert observer.get_task('a')['evidence_cursor'] == cursor
        assert not any(p.is_file() for p in (store.home / 'artifacts').rglob('*'))
        assert observer.put_artifact('a', 'blob', b'one', 'text/plain', 'r')['complete']


def test_decision_commit_failure_rolls_back_pointer(store):
    store.fault = lambda stage: (_ for _ in ()).throw(OSError('full'))
    with pytest.raises(PersistenceFailed):
        store.advance_decision('a', 0, {'hypothesis': 'lost'})
    assert store.get_task('a')['current_decision_rev'] == 0
    assert store.dump('a')['decisions'] == []


def test_cross_task_denied(store):
    scoped = store.scoped('a')
    for operation in [lambda: scoped.get_task('b'), lambda: scoped.query('b'),
                      lambda: scoped.read('b', 'b'), lambda: scoped.dump('b'),
                      lambda: scoped.artifact_bytes('b', 'blob'),
                      lambda: scoped.put_artifact('b', None, b'x', 'text/plain', None),
                      lambda: scoped.advance_decision('b', 0, {}),
                      lambda: scoped.append_observation('b', {})]:
        with pytest.raises(ScopeDenied):
            operation()


def test_cross_task_allowed_when_granted(store):
    blob = store.put_artifact('b', 'blob', b'hello', 'text/plain', None)
    scoped = store.scoped('a', readable=frozenset({'b'}))
    assert scoped.get_task('b')['objective'] == 'compare'
    assert scoped.read('b', 'blob')['sha256'] == blob['sha256']
    assert scoped.artifact_bytes('b', 'blob') == b'hello'
    assert scoped.query('b')['items']
    with pytest.raises(ScopeDenied):
        scoped.append_observation('b', {})


def test_observations_append_only(store):
    record = store.append_observation('a', {'obs_id': 'obs', 'kind': 'timing', 'values': {'seconds': 2}})
    with pytest.raises(ValueError):
        store.append_observation('a', {'obs_id': 'obs', 'values': {'seconds': 3}})
    assert store.read('a', 'obs') == record
    for target in (store, store.scoped('a')):
        assert not hasattr(target, 'update_observation')
        assert not hasattr(target, 'delete_observation')
    with pytest.raises(sqlite3.IntegrityError):
        store._db.execute("UPDATE observations SET kind='changed'")
    with pytest.raises(sqlite3.IntegrityError):
        store._db.execute('DELETE FROM observations')


def test_artifact_integrity_every_read(store):
    record = store.put_artifact('a', 'blob', b'one', 'text/plain', None)
    (store.home / record['location']).write_bytes(b'two')
    for read in (lambda: store.read_artifact('a', 'blob'), lambda: store.artifact_bytes('a', 'blob'),
                 lambda: store.read('a', 'blob'), lambda: store.dump('a'),
                 lambda: store.put_artifact('a', 'blob', b'one', 'text/plain', None)):
        with pytest.raises(PersistenceFailed):
            read()


def test_shared_blob_survives_failed_second_registration(store):
    first = store.put_artifact('a', 'blob', b'one', 'text/plain', None)
    store.fault = lambda stage: (_ for _ in ()).throw(OSError('full')) if stage == 'before_commit' else None
    with pytest.raises(PersistenceFailed):
        store.put_artifact('b', 'other', b'one', 'text/plain', None)
    assert store.read_artifact('a', 'blob') == first
    assert store.artifact_bytes('a', 'blob') == b'one'


def test_query_pagination_and_filters(store):
    for i in range(5):
        store.append_observation('a', {'kind': 'timing', 'values': {'needle': i}})
    first = store.query('a', kinds=['timing'], text='needle', limit=2)
    second = store.query('a', kinds=['timing'], since=first['cursor'], limit=2)
    third = store.query('a', kinds=['timing'], since=second['cursor'], limit=2)
    ids = [item['id'] for page in (first, second, third) for item in page['items']]
    assert len(ids) == len(set(ids)) == 5
    assert store.query('a', kinds=['timing'], since=third['cursor']) == {'items': [], 'cursor': third['cursor']}


def test_attempt_lifecycle_and_evaluation_fields(store):
    attempt = store.create_attempt('a', {'attempt_id': 'job', 'kind': 'build', 'idem_key': 'key', 'fingerprint': 'sha', 'request': {}})
    assert attempt['state'] == 'queued'
    running = store.transition_attempt('a', 'job', 'running', expected_state='queued', jobq_id='q1')
    assert running['started'] is not None
    with pytest.raises(StaleRevision):
        store.transition_attempt('a', 'job', 'failed', expected_state='queued')
    with pytest.raises(ValueError):
        store.transition_attempt('a', 'job', 'invented')
    store.transition_attempt('a', 'job', 'cancel_requested')
    final = store.transition_attempt('a', 'job', 'cancelled', cleanup_state='complete')
    assert [event['state'] for event in final['history']] == ['queued', 'running', 'cancel_requested', 'cancelled']
    with pytest.raises(ValueError):
        store.transition_attempt('a', 'job', 'running')
    evaluation = store.add_evaluation('a', {'contract_id': 'greedy', 'contract_version': '1', 'contract': {}, 'inputs': {}, 'execution_outcome': 'ok', 'correctness': 'fail', 'evidence_completeness': 'partial'})
    assert (evaluation['execution_outcome'], evaluation['correctness'], evaluation['evidence_completeness']) == ('ok', 'fail', 'partial')
    upload = store.add_upload('a', {'lab_run_id': 'lab', 'sha256': 'abc', 'ack_state': 'pending'})
    assert store.read('a', upload['upload_id']) == upload
