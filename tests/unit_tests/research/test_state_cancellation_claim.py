"""Mechanical once-claim guard with real SQLite/source cancellation rows.

The caller supplies protected identity only; this fixture is not a canonical
Capsule contract and confers no worker/model/executor authority.
"""
import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.parametrize('clear_reason', [False, True])
def test_acknowledged_cancellation_prevents_new_claim_but_preserves_history(tmp_path, clear_reason):
    store = SQLiteRunStore(tmp_path)
    try:
        store.create_run('run:cancelled', account_id='alice', workspace_id='project', submission={})
        store.create_run('run:other', account_id='alice', workspace_id='project', submission={})
        identity = {'run_id': 'run:cancelled', 'node_id': 'node', 'subnode_id': 'work', 'attempt_id': 'node-a1'}
        ref = store.append_record('controlled-ledger-identity', {'id': 'ledger:work', **identity})
        assert store.claim_attempt(ref, identity) is True
        original = store.get_attempt('run:cancelled', 'node', 'work', 'node-a1')
        receipt = store.request_cancellation('run:cancelled', 'alice', 'cancel:original')
        assert receipt['request_id'] == 'cancel:original' and receipt['status'] == 'requested'
        if clear_reason:
            # A stale host projection cannot remove the durable cancellation.
            with store.transaction() as db: db.execute('UPDATE runs SET reason=NULL WHERE id=?', ('run:cancelled',))
        assert store.claim_attempt(ref, identity) is False
        assert store.get_attempt('run:cancelled', 'node', 'work', 'node-a1') == original
        next_identity = identity | {'subnode_id': 'reviewer'}
        next_ref = store.append_record('controlled-ledger-identity', {'id': 'ledger:reviewer', **next_identity})
        with pytest.raises(ResearchError): store.claim_attempt(next_ref, next_identity)
        assert store.connection.execute('SELECT COUNT(*) FROM attempts WHERE run_id=?', ('run:cancelled',)).fetchone()[0] == 1
        assert store.get_cancellation('run:cancelled', 'cancel:original') == receipt
        other = identity | {'run_id': 'run:other'}
        other_ref = store.append_record('controlled-ledger-identity', {'id': 'ledger:other', **other})
        assert store.claim_attempt(other_ref, other) is True
        assert store.connection.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0] == 0
    finally:
        store.close()
