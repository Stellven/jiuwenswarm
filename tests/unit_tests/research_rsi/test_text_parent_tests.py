"""Actual pure parent-test parsing with disposable captures; no model claims."""
import asyncio,hashlib
from jiuwenswarm.research.state import SQLiteRunStore


def test_frozen_text_tests_emit_measured_child_bound_receipts_and_reject_unknown_forms(tmp_path):
    from jiuwenswarm.research_rsi.text_checks import TextParentTests
    store=SQLiteRunStore(tmp_path/'core')
    parent=store.put_blob(b'{"identity":{"body":[{"path":"screening_prompt.txt","sha256":"parent"}]}}')
    body=store.put_blob(b'Use the fixed independent rules.')
    child=store.put_blob(b'{"identity":{"body":[{"path":"screening_prompt.txt","sha256":"'+body['sha256'].encode()+b'"}]}}')
    config=store.put_blob(b'configuration')
    binding=store.append_record('test-binding',{'parent_declaration_ref':parent,'child_declaration_ref':child,'configuration_ref':config,'child_body_refs':{'screening_prompt.txt':body},'dependency_refs':[]})
    test=store.append_record('rsi-parent-test',{'schema':'ai4r-screening-parent-test:1','id':'prompt','kind':'prompt_utf8','parent_declaration_ref':parent})
    owner=TextParentTests(store)
    receipts=asyncio.run(owner.run(binding,[test]))
    receipt=store.read_record(receipts[0]);assert receipt['outcome']=='PASS' and receipt['test_ref']==test and receipt['child_declaration_ref']==child
    checked=store.read_record(receipt['deterministic_result_ref']);assert checked['subject_ref']==child and checked['results'][0]['outcome']=='PASS'
    bad=store.append_record('rsi-parent-test',{'schema':'ai4r-screening-parent-test:1','id':'bad','kind':'arbitrary_command','parent_declaration_ref':parent})
    receipts=asyncio.run(owner.run(binding,[bad]));assert store.read_record(receipts[0])['outcome']=='ENVIRONMENT_BLOCKED'
    assert asyncio.run(owner.contain({'id':'trial','sha256':'a'*64}))['contained'] is True
    store.close()
