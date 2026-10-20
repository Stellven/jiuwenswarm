"""Protected completion preserves raw observations and source classification."""
import copy
import hashlib
import json

import pytest

from jiuwenswarm.research.checks.records import body_files_sha256,complete_observation,error_fingerprint
from tests.unit_tests.research.test_budget_ceiling import work_contract
from jiuwenswarm.research.state import utc_now


def test_body_digest_uses_sorted_utf8_tab_lines_independent_of_json_order():
    rows=[{'path':'z.py','sha256':'a'*64},{'path':'a.py','sha256':'b'*64}]
    expected=hashlib.sha256(('a.py\t'+'b'*64+'\nz.py\t'+'a'*64+'\n').encode()).hexdigest()
    assert body_files_sha256(rows)==expected==body_files_sha256(rows[::-1])


@pytest.mark.parametrize('outcome,action,verdict,platform,input_invalid,scientific,expected',[
    ('success','advance','PASS',False,False,False,'none'),
    ('interrupted','halt','FAIL',False,False,False,'infrastructure'),
    ('failed','halt','ENVIRONMENT_BLOCKED',False,True,False,'infrastructure'),
    ('failed','halt','FAIL',True,True,False,'infrastructure'),
    ('failed','halt','FAIL',False,True,False,'input'),
    ('success','advance','PASS',False,False,True,'scientific'),
    ('budget_exhausted','halt','FAIL',False,False,False,'capsule'),
])
def test_ordered_source_failure_rules(outcome,action,verdict,platform,input_invalid,scientific,expected):
    original={'id':'observation:fixture','cc_name':'research.evaluation','outcome':outcome,
        'failure_class':None,'error_fingerprint':None,'check_result_refs':[],
        'verifier_assessment_ref':None,'human_answer_ref':None}
    before=copy.deepcopy(original)
    result=complete_observation(original,decisions=[{'action':action,'verdict':verdict}],
        check_refs=[],platform_error=platform,input_invalid=input_invalid,scientific_negative=scientific)
    assert result['failure_class']==expected and original==before


def test_error_fingerprint_removes_source_volatile_details():
    left='failed 2026-10-16T22:00:00Z /tmp/job-abcdef/out.py pid=12345 run:abc 0x123abc 9999'
    right='failed 2026-10-17T23:10:20Z /tmp/job-ghijkl/out.py pid=65432 run:def 0x456def 8888'
    assert error_fingerprint(left)==error_fingerprint(right)
    assert error_fingerprint(None) is None


@pytest.mark.asyncio
async def test_completed_journal_is_separate_exact_and_idempotent(tmp_path):
    store,runner,ref,contract=await work_contract(tmp_path)
    ctx=runner._start_context(ref,contract,{})
    await runner._await_start(ctx)
    raw=runner._observation(runner._executions[ctx.execution_id],ref,utc_now(),{},'failed','output_invalid')
    raw_ref=store.put_record('invocation-observation',raw)
    before=store.read_blob(raw_ref)
    assert raw['failure_class'] is None and raw['error_fingerprint'] is None
    completed=complete_observation(raw,decisions=[],check_refs=[],error_text='output_invalid')
    link=store.publish_capsule_record(raw_ref,completed,decision_refs=[])
    assert store.read_blob(raw_ref)==before
    assert store.read_record(link['completed_ref'])['failure_class']=='capsule'
    snapshot=store.read_blob(link['records_snapshot_ref'])
    assert json.loads(snapshot)==completed
    assert (store.root/'records'/'records.jsonl').read_bytes()==snapshot
    assert store.publish_capsule_record(raw_ref,completed,decision_refs=[])==link
    assert (store.root/'records'/'records.jsonl').read_bytes()==snapshot
