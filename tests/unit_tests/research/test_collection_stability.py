"""Collection bookkeeping cannot rename evidence; late evidence remains visible."""
import tempfile
from pathlib import Path
import unittest

from jiuwenswarm.research.collection import snapshot
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.state import SQLiteRunStore


class CollectionStabilityTests(unittest.TestCase):
    def test_snapshot_retains_exact_paths_and_admits_late_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteRunStore(Path(directory));ref=store.put_blob(b'controlled fixture')
            try:
                store.create_run('run:fixture',account_id='alice',workspace_id='project',submission={})
                store.set_run_state('run:fixture','completed')
                call={'schema_version':'1.0.0','id':'call:fixture','route_attempt_id':'route:fixture','route_decision_ref':None,
                    'execution_id':'execution','invocation_id':'invocation','purpose':'task_execution','call_function':'worker',
                    'deployment_ref':ref,'model_selection_profile_ref':ref,'provider_request_id':None,
                    'identity':{'requested':'fixture','effective':None,'basis':'controlled fixture'},
                    'started_at':'2026-10-22T00:00:00Z','ended_at':'2026-10-22T00:00:01Z','outcome':'completed',
                    'provider_error_code':None,'usage':{'input_tokens':None,'output_tokens':None,'cost_amount':None,
                        'currency':None,'unavailable_reasons':['controlled fixture']},'evidence_refs':[],'observed_runtime':False}
                store.put_record('model-call',call,record_id=call['id'])
                store.append_record('model-call-start',{'id':'start:fixture','run_id':'run:fixture','call_id':call['id']})
                service=ResearchService(store,registry=None,model=None)
                principal=Principal('alice',frozenset({'project'}),frozenset({'export'}))
                first=snapshot(service,principal,'run:fixture');second=snapshot(service,principal,'run:fixture')
                self.assertEqual(first,second)
                # The model-call start, the model call, and the run's contract index (always collected).
                self.assertEqual(len(first['artifacts']),3)
                self.assertIn('contracts/index.json',{item['path'] for item in first['artifacts']})
                store.append_record('escalation',{'id':'late:fixture','run_id':'run:fixture','reason_code':'late_capture'})
                late=snapshot(service,principal,'run:fixture')
                self.assertNotEqual(first['manifest_sha256'],late['manifest_sha256'])
                self.assertTrue({item['path'] for item in first['artifacts']}<{item['path'] for item in late['artifacts']})
            finally:store.close()


if __name__=='__main__':unittest.main()
