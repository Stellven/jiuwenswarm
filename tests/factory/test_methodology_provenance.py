"""Follow-up proposals identify the source of authorized historical evidence."""
import json

from jiuwenswarm.factory.methodology import dispatch


def test_followup_retains_prior_evidence_source_and_current_contract_scope(store):
    store.create_task(dict(task_id='historical', objective='Prior report', contract_id='old-contract'))
    store.put_artifact('historical', 'report', json.dumps({'status': 'failed', 'error': 'old failure'}).encode(),
                       'application/json', 'operator')
    store._db.execute('UPDATE tasks SET contract_id=? WHERE task_id=?', ('current-contract', 't'))
    before = store.get_task('t')
    result = dispatch(store.scoped('t', {'historical'}), 't', 'followup', {'evidence_ids': ['report']})['analysis']
    assert result['evidence_sources'] == [{'task_id': 'historical', 'evidence_id': 'report'}]
    assert result['source_task_id'] == 't'
    assert result['source_contract_id'] == 'current-contract'
    assert result['evidence_ids'] == ['report']
    assert result['requires_operator_admission'] is True
    assert result['status'] == 'proposal_only'
    assert store.get_task('t') == before
    # A same-ID current-task report takes precedence, and its actual origin is
    # explicit rather than accidentally attributed to the older task.
    store.put_artifact('t', 'report', b'{"status":"success"}', 'application/json', 'operator')
    local = dispatch(store.scoped('t', {'historical'}), 't', 'followup', {'evidence_ids': ['report']})['analysis']
    assert local['evidence_sources'] == [{'task_id': 't', 'evidence_id': 'report'}]
    assert local['source_contract_id'] == 'current-contract'
