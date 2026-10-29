import asyncio
import base64
import hashlib
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.ports import JobPort


def test_job_export_is_explicit_public_closure_not_store_directory(tmp_path):
    store=RecordStore(tmp_path)
    hidden=store.put({'secret_fixture':'never export'})
    attempt=store.put({'sequence':1});session=store.put({'session_id':'s'})
    result={'session_ref':session,'attempt_refs':[attempt],'referee_evidence_ref':None}
    result_ref=store.put(result);job={'id':'job_one','sha256':'a'*64}
    class Jobs:
        def resolve(self,ref):return {'approved':True}
    store.claim_job(job);store.finish_job(job,{'state':'terminal','result':[result,result_ref]})
    port=JobPort(Jobs(),store,allowed_refs=[job])
    value=asyncio.run(port.export(job))
    assert {r['kind'] for r in value['records']}=={'rsi-session-result','rsi-session','rsi-attempt'}
    assert hidden not in [r['ref'] for r in value['records']]
    for row in value['records']:
        assert hashlib.sha256(base64.b64decode(row['bytes_base64'],validate=True)).hexdigest()==row['ref']['sha256']
