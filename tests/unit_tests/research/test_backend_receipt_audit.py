"""Private offline receipt custody; rejected evidence never authorizes retries."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_model_relay import (LocalModelRelay, CapturedBackendReceipt,
    backend_output, MAX_BACKEND_RECEIPT_BYTES)
from jiuwenswarm.research.router_client import decode_frame
from tests.unit_tests.research.test_host_codex_route import binding, native, response, PROMPT, PIN


class BackendReceiptAuditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.runtime=Path(self.temp.name);self.runtime.chmod(0o700)
        self.custody=patch('jiuwenswarm.research.local_model_relay.private_path') if os.name=='nt' else None
        if self.custody:self.custody.start()
        class Catalog:
            def resolve(self,*args,**kwargs):return binding()
        self.backend=AsyncMock()
        self.relay=LocalModelRelay(Catalog(),self.runtime,backend=self.backend)
        self.payload={'request_id':'../request/path-is-data','endpoint_id':'local-host-codex61',
            'binding_sha256':PIN,'model':'gpt-6.1-sol','prompt':PROMPT,'timeout_s':10}

    def tearDown(self):
        self.relay.close()
        if self.custody:self.custody.stop()
        self.temp.cleanup()

    def audit(self):
        name=hashlib.sha256(self.payload['request_id'].encode()).hexdigest()
        directory=self.runtime/'backend-receipts'
        return directory/name,directory/(name+'.receipt'),directory/(name+'.json')

    async def test_rejected_native_receipt_is_captured_before_validation_and_latch_stays(self):
        bundle=native()
        # Actual forbidden execution is rejected after original stdout custody.
        bundle['wire_frames'].append({'direction':'in','raw':'{"method":"item/commandExecution/started","params":{}}\n'})
        original=response(bundle)
        stdout=json.dumps(original,ensure_ascii=False,indent=1).encode()+b'\n'
        self.backend.return_value=CapturedBackendReceipt(original,stdout)
        result=await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'],'outcome_unknown');self.assertIsNone(result['response_text'])
        _,receipt,meta=self.audit()
        self.assertEqual(receipt.read_bytes(),stdout)
        diagnostic=json.loads(meta.read_bytes())
        self.assertEqual(diagnostic['reason'],'native_validation_rejected')
        self.assertEqual(diagnostic['receipt']['sha256'],hashlib.sha256(stdout).hexdigest())
        self.assertEqual(diagnostic['receipt']['size'],len(stdout))
        self.assertEqual(diagnostic['receipt']['encoding'],'backend-stdout')
        self.assertEqual(diagnostic['request_id'],self.payload['request_id'])
        self.assertEqual(diagnostic['counts']['wire_frames'],len(bundle['wire_frames']))
        self.assertLess(diagnostic['counts']['response_text_bytes'],1024*1024)
        self.assertEqual(diagnostic['counts']['terminal_status'],'completed')
        self.assertEqual(diagnostic['bounds']['backend_receipt_bytes'],MAX_BACKEND_RECEIPT_BYTES)
        self.assertLess(meta.stat().st_size,16384)
        original_meta=meta.read_bytes()
        self.assertEqual(await self.relay.invoke(self.payload),result)
        self.assertEqual(meta.read_bytes(),original_meta)
        with self.assertRaises(ResearchError):await self.relay.invoke({**self.payload,'request_id':'next'})
        self.backend.assert_awaited_once()
        if os.name=='posix':
            self.assertEqual(stat.S_IMODE(receipt.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(meta.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(receipt.parent.stat().st_mode),0o700)
            self.assertEqual(receipt.stat().st_uid,os.geteuid())
            self.assertEqual(receipt.stat().st_nlink,1)

    async def test_malformed_and_nonzero_helper_stdout_are_kept_as_original_bytes(self):
        for index,(stdout,code,reason) in enumerate(((b'not-json\n',0,'invalid_json'),
                (json.dumps(response(native())).encode(),7,'nonzero_exit'))):
            self.payload['request_id']='transport-'+str(index)
            original=backend_output(stdout,code,decode_frame)
            self.backend.return_value=original
            # Isolate each transport failure: no clearing/recovery of its latch.
            if index:
                self.relay.close()
                other=self.runtime/'other';other.mkdir(mode=0o700)
                self.relay=LocalModelRelay(self.relay.catalog,other,backend=self.backend)
                self.runtime=other
            result=await self.relay.invoke(self.payload)
            self.assertEqual(result['outcome'],'outcome_unknown')
            _,receipt,meta=self.audit()
            self.assertEqual(receipt.read_bytes(),stdout)
            diagnostic=json.loads(meta.read_bytes())
            self.assertEqual(diagnostic['reason'],'backend_transport_rejected')
            self.assertEqual(diagnostic['transport_error'],reason)

    async def test_capture_failure_cannot_report_completed_or_overwrite_evidence(self):
        self.backend.return_value=response(native())
        with patch.object(self.relay,'_write_once',side_effect=OSError('offline custody unavailable')):
            result=await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'],'outcome_unknown')
        with self.assertRaises(ResearchError):await self.relay.invoke({**self.payload,'request_id':'next'})
        self.backend.assert_awaited_once()

    async def test_oversize_receipt_is_not_truncated_or_adopted(self):
        original=response(native())
        self.backend.return_value=CapturedBackendReceipt(original,b'x'*(MAX_BACKEND_RECEIPT_BYTES+1))
        result=await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'],'outcome_unknown')
        _,receipt,meta=self.audit()
        self.assertFalse(receipt.exists())
        self.assertEqual(json.loads(meta.read_bytes())['reason'],'receipt_capture_failed')

    async def test_known_failure_receipt_is_written_without_changing_wire_schema(self):
        self.relay.catalog.resolve=lambda *args,**kwargs:{**binding(),'backend':{'kind':'ssh-loopback-openai'}}
        self.backend.return_value={'outcome':'failed','http_status':503,'response_text':None,'provider_request_id':None}
        result=await self.relay.invoke(self.payload)
        self.assertEqual(set(result),{'request_id','binding_sha256','outcome','http_status','response_text','provider_request_id'})
        self.assertEqual(result['outcome'],'failed')
        _,receipt,meta=self.audit();diagnostic=json.loads(meta.read_bytes())
        self.assertEqual(diagnostic['reason'],'accepted')
        self.assertIsInstance(diagnostic['receipt'],dict)
        self.assertEqual(json.loads(receipt.read_bytes())['http_status'],503)


if __name__=='__main__':unittest.main()
