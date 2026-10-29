"""A new session cannot bypass a durable unresolved security halt."""
import asyncio
import pytest

from jiuwenswarm.research_rsi.clearance import SessionClearance
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.mutation import SecurityViolation
from tests.unit_tests.research_rsi.test_session_policy import controller_fixture


def incident_fixture(tmp_path):
    store=RecordStore(tmp_path);ref=store.put({'unit':'captured session'})
    incident=store.record_security_halt('halted',ref,'operator','forbidden mutation')
    evidence=store.put({'unit':'independent remediation and verified guardrail capture'})
    record={'schema_version':'1.0.0','id':'clearance:unit','actor_id':'reviewer',
        'recorded_at':'2099-01-01T00:00:00Z','halted_session_id':'halted','violation_refs':[incident],
        'remediation_ref':evidence,'guardrail_evidence_refs':[evidence],'decision':'cleared',
        'effect_scope':'new_rsi_session_only'}
    return store,record


@pytest.mark.parametrize('fault',[None,'self','foreign','wrong_halt','wrong_incident','no_guardrail','stale'])
def test_clearance_requires_root_captured_independent_matching_evidence(tmp_path,fault):
    store,record=incident_fixture(tmp_path)
    try:
        with pytest.raises(ValueError):SessionClearance(store).require('new')
        if fault=='self':record['actor_id']='operator'
        elif fault=='foreign':record['actor_id']='unapproved'
        elif fault=='wrong_halt':record['halted_session_id']='other'
        elif fault=='wrong_incident':record['violation_refs']=[record['remediation_ref']]
        elif fault=='no_guardrail':record['guardrail_evidence_refs']=[]
        elif fault=='stale':record['recorded_at']='2000-01-01T00:00:00Z'
        pin=store.put(record)
        policy=store.put({'schema':'ai4r-rsi-clearance-policy:1','id':'policy:unit',
            'authorized_reviewers':['reviewer','operator'],'clearance_refs':[pin]})
        gate=SessionClearance(store,policy)
        if fault is not None:
            with pytest.raises(ValueError):gate.require('new')
            assert store.security_halts()[0]['clearance_ref'] is None
        else:
            gate.require('new')
            store.close();store=RecordStore(tmp_path)
            SessionClearance(store,policy).require('another-new')
            assert store.security_halts()[0]['clearance_ref']==pin
            with pytest.raises(ValueError,match='resume'):SessionClearance(store,policy).require('halted')
    finally:store.close()


def test_unresolved_halt_blocks_controller_before_new_exposure(tmp_path):
    f,records,ledger,controller,session,final,calls=controller_fixture(tmp_path)
    try:
        records.record_security_halt('prior',records.put({'unit':'prior session'}),'prior-operator','scope escape')
        with pytest.raises(ValueError,match='clearance'):
            asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='unit:set',
                visible_context={},parent_body_ref=f['attempt']['parent_ref'],finalize=final))
        assert calls==[] and ledger.db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0
    finally:records.close();ledger.close();f['store'].close()


def test_crash_before_incident_blob_publication_keeps_original_blocking_evidence(tmp_path,monkeypatch):
    store=RecordStore(tmp_path);pin=store.put({'unit':'captured session'})
    def fail(*_):raise OSError('controlled publication failure')
    monkeypatch.setattr(store,'put_bytes',fail)
    with pytest.raises(OSError):store.record_security_halt('halted',pin,'operator','scope escape')
    store.close();store=RecordStore(tmp_path)
    try:
        row=store.security_halts()[0]
        assert store.get(row['incident_ref'])['violation']=='scope escape'
        with pytest.raises(ValueError,match='clearance'):SessionClearance(store).require('new')
    finally:store.close()


def test_security_violation_persists_incident_before_terminal_and_new_session_gate(tmp_path):
    f,records,ledger,controller,session,_,calls=controller_fixture(tmp_path)
    async def forbidden(*_):raise SecurityViolation('attempted forbidden body path')
    controller.assess=forbidden
    try:
        result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='unit:set',
            visible_context={},parent_body_ref=f['attempt']['parent_ref']))
        assert result['outcome']=='SECURITY_HALTED' and result['queries_used']==1
        incident=records.get(records.security_halts()[0]['incident_ref'])
        assert incident['operator_id']==session['started_by'] and incident['session_id']==session['session_id']
        with pytest.raises(ValueError,match='clearance'):SessionClearance(controller.store).require('new')
        # An older build had original halt/attempts but no incident index.
        # Upgrading retains that block without rewriting signed evidence.
        records.db.execute('DELETE FROM security_halts')
        with pytest.raises(ValueError,match='clearance'):SessionClearance(controller.store).require('new')
        assert records.security_halts()[0]['session_id']==session['session_id']
    finally:records.close();ledger.close();f['store'].close()
