"""No controlled fixture grants operational security qualification."""
import pytest

from jiuwenswarm.research.state import SQLiteRunStore


def test_missing_qualification_is_not_a_caller_boolean_or_a_default(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification
    store=SQLiteRunStore(tmp_path/'state')
    guard=RSIQualification(store.read_blob,None)
    try:
        with pytest.raises(ValueError,match='qualification'):
            guard.require('session_start',session_ref={'id':'s','sha256':'a'*64})
        with pytest.raises(ValueError):
            RSIQualification(store.read_blob,True).require('admit',session_ref={'id':'s','sha256':'a'*64})
    finally:store.close()


def test_root_pinned_pass_string_cannot_replace_exact_scope_and_thirteen_original_cases(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification
    store=SQLiteRunStore(tmp_path/'state')
    fake=store.append_record('rsi-security-qualification',{'schema':'ai4r-rsi-security-qualification:1','id':'fake','qualified':True,'outcome':'PASS'})
    try:
        with pytest.raises(ValueError):RSIQualification(store.read_blob,fake).require('admit',session_ref=fake)
    finally:store.close()


def test_missing_production_guard_blocks_rsi_admission_before_custody_or_authority_mutation(tmp_path):
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.contracts import Principal,ResearchError
    store=SQLiteRunStore(tmp_path/'state');library=LibraryService(store)
    actor=Principal('operator',operations=frozenset({'library_admit'}))
    import asyncio
    try:
        with pytest.raises(ResearchError,match='qualification'):
            asyncio.run(library.admit_rsi({'id':'unknown','sha256':'a'*64},actor))
        assert not library.entries()
    finally:store.close()


def test_current_expected_verification_profile_cannot_be_read_from_claimed_receipt(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification
    store=SQLiteRunStore(tmp_path/'state')
    try:
        receipt=store.append_record('receipt',{'schema':'m1-verification-result:1','check_id':'M1-008/V15',
            'outcome':'PASS','dependency_mode':'real_boundary','command':['pytest'],'cwd':'/workspace',
            'started_at':'2026-10-17T00:00:00Z','ended_at':'2026-10-17T00:01:00Z'})
        guard=RSIQualification(store.read_blob,receipt)
        with pytest.raises(ValueError,match='current verification profile'):
            guard._receipt({'verification_receipt_ref':receipt},{})
    finally:store.close()


def test_distinct_cases_cannot_reuse_one_signed_halt_and_irrelevant_record(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification,CASES
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path/'fixture');store=fixture['store']
    result=dict(fixture['result']);result['outcome']='SECURITY_HALTED';result['qualified_by']='none';result['statistics']=None
    halt=store.append_record('rsi-session-result',fixture['signer'].sign(result))
    irrelevant=store.append_record('unrelated',{'irrelevant':True})
    guard=RSIQualification(store.read_blob,halt,kind_reader=store.record_kind)
    with pytest.raises(ValueError,match='reused|distinct'):
        guard._cases({'case_evidence_refs':{case:[halt,irrelevant] for case in CASES}}, {})
    store.close()


def test_absent_independent_case_observer_cannot_be_a_captured_pass_label(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification
    store=SQLiteRunStore(tmp_path/'state')
    try:
        guard=RSIQualification(store.read_blob,{'id':'not-an-authority','sha256':'a'*64},kind_reader=store.record_kind)
        with pytest.raises(ValueError,match='independent.*case'):
            guard._cases({'case_evidence_refs':{}}, {})
    finally:store.close()


@pytest.mark.parametrize('field',['candidate_id','procedure_sha256','source_baseline_sha256','native_pins','interface_revisions','profile_pins'])
def test_claimed_receipt_must_match_independently_current_pins(tmp_path,field):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification,CASES
    store=SQLiteRunStore(tmp_path/'state')
    expected={'candidate_id':'current','procedure_sha256':'a'*64,'source_baseline_sha256':'b'*64,
        'native_pins':{'M1-008/plan.md':'c'*64},'interface_revisions':{'M1-IF-015':'r1'},
        'profile_pins':{'worker':'d'*64},'assertion_manifest_sha256':'e'*64,
        'required_case_ids':{case:'test_security::'+case for case in CASES}}
    receipt={k:v for k,v in expected.items() if k not in {'assertion_manifest_sha256','required_case_ids'}}
    receipt[field]='stale' if isinstance(receipt[field],str) else {'stale':'f'*64}
    try:
        pin=store.append_record('receipt',receipt)
        guard=RSIQualification(store.read_blob,pin,validation_profile=expected)
        with pytest.raises(ValueError,match='stale or missing current '+field):guard._receipt({'verification_receipt_ref':pin},{})
    finally:store.close()


def test_subject_scope_binds_exact_parent_and_source_authorized_changed_declaration(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path);store=fixture['store'];package=fixture['package']
    try:
        guard=RSIQualification(store.read_blob,package['session_ref'])
        assert guard._subject('trial',package['session_ref'],package['parent_declaration_ref'])['session_id']==fixture['session']['session_id']
        assert guard._subject('trial',package['session_ref'],package['child_declaration_ref'])['session_id']==fixture['session']['session_id']
        with pytest.raises(ValueError,match='exact subject'):guard._subject('trial',package['session_ref'],None)
        with pytest.raises(ValueError,match='original parent'):guard._subject('admit',package['session_ref'],package['parent_declaration_ref'])
        unrelated=store.put_blob(b'foreign bare helper bytes with no parent declaration join')
        with pytest.raises((ValueError,UnicodeError)):guard._subject('trial',package['session_ref'],unrelated)
    finally:store.close()
