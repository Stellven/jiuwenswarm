"""Actual host-original evidence must cross the protected trace sink."""
import copy
import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.native_ports import capture_governed_trace_record
from jiuwenswarm.research.contracts import ResearchError
from tests.unit_tests.research_rsi.test_host_codex_backend import native

class HostOriginalSinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=SQLiteRunStore(Path(self.tmp.name)/'core');self.addCleanup(self.store.close)
        self.contract=self.store.put_blob(b'exact protected contract')
        claim=self.store.append_record('calibration-call-claim',{'id':'claim:owned'})
        self.scope={key:'owned-'+key for key in ('run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id','call_id')}
        self.scope['contract_ref']=self.contract
        start=self.store.append_record('model-call-start',dict(self.scope,id='start:owned',call_claim_ref=claim))
        self.scope['model_call_start_ref']=start
        self.raw=self.store.put_blob(json.dumps(native('public owned fixture')).encode())
        self.record={'schema':'ai4r-host-codex-original:1','scope':self.scope,'policy_sha256':'a'*64,'raw_ref':self.raw}
    def test_original_captured_once_with_exact_bytes_and_scope(self):
        ref=capture_governed_trace_record(self.store,'host-codex-native-original',self.record)
        self.assertEqual(self.store.read_record(ref),self.record)
        self.assertEqual(self.store.read_blob(self.store.read_record(ref)['raw_ref']),self.store.read_blob(self.raw))
    def test_original_raw_bytes_enter_private_calibration_audit_index(self):
        from jiuwenswarm.research.calibration_authority import _CaptureAuditIndex
        ref=capture_governed_trace_record(self.store,'host-codex-native-original',self.record)
        index=_CaptureAuditIndex(self.store);index.refresh(self.store)
        entries=list(index.by_execution[self.scope['execution_id']].values())
        originals=[item for item in entries if item[1]==ref]
        self.assertEqual(len(originals),1)
        self.assertIn(self.raw,originals[0][2])
    def test_known_predispatch_failure_does_not_become_audit_unknown(self):
        original=native('public',outcome='failed')
        original.update(binary_sha256=None,account_fingerprint=None,thread_start=None,turn_start=None,
                        turn_completed=None,wire_frames=[],error_code='auth_failed')
        value=dict(self.record,raw_ref=self.store.put_blob(json.dumps(original).encode()))
        ref=capture_governed_trace_record(self.store,'host-codex-native-original',value)
        self.assertEqual(self.store.read_record(ref),value)
    def test_foreign_call_scope_rejected(self):
        value=copy.deepcopy(self.record);value['scope']['call_id']='foreign'
        with self.assertRaises(ResearchError):capture_governed_trace_record(self.store,'host-codex-native-original',value)
    def test_closed_shape_policy_and_bundle_required(self):
        variants=[]
        for key,value in [('extra',True),('policy_sha256','invalid'),('schema','wrong')]:
            changed=copy.deepcopy(self.record);changed[key]=value;variants.append(changed)
        for raw in (b'{malformed',json.dumps(dict(native('public'),requested_model='foreign')).encode()):
            changed=copy.deepcopy(self.record);changed['raw_ref']=self.store.put_blob(raw);variants.append(changed)
        for changed in variants:
            with self.assertRaises(ResearchError):capture_governed_trace_record(self.store,'host-codex-native-original',changed)
        self.assertFalse(list(self.store.iter_records(kinds=('host-codex-native-original',))))

if __name__=='__main__':unittest.main()