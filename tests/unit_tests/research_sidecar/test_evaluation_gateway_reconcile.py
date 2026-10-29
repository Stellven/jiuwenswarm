"""Gateway replies never establish whether an upstream E2/E3 effect ran."""
import asyncio
import base64
import hashlib

import httpx
import pytest

from jiuwenswarm.research_sidecar.client import ClientError, ResearchClient
from jiuwenswarm.research_sidecar.ledger import Ledger
from jiuwenswarm.research_sidecar.reconcile import evaluation_once


def result():
    return {'invocation_id':'controlled-invocation','status':'completed','output_refs':{},'check_results':[],
            'tool_effects_observed':False,'model_calls':[],'duration_s':32,'reason':None,'invalid_for_product':True}


@pytest.mark.parametrize('status',[500,502,503,504])
def test_server_reply_reconciles_same_id_without_post_retry_and_retains_original_bytes(tmp_path,status):
    token=tmp_path/'token';token.write_text('controlled-only');token.chmod(0o600)
    payload={'request_id':'frozen:one','case_id':'controlled','campaign_id':'campaign','evaluation_profile_id':'profile'}
    raw=b'upstream reply lost after original completion\r\n\x00';seen=[]
    def handle(request):
        seen.append((request.method,request.url.path))
        if request.method=='POST':return httpx.Response(status,content=raw)
        assert request.url.path=='/api/v1/evaluation/requests/frozen:one'
        return httpx.Response(200,json={'request_id':payload['request_id'],'status':'completed',
            'result':result(),'failure_ref':None,'invalid_for_product':True})
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');client=ResearchClient('http://controlled',token,transport=httpx.MockTransport(handle))
        try:
            assert await evaluation_once(client,'single_cc',payload,ledger,'attempt')==result()
            assert await evaluation_once(client,'single_cc',payload,ledger,'attempt')==result()
            original=client.evaluation_http_captures[0]
            assert original['status_code']==status and base64.b64decode(original['body_base64'])==raw
            assert original['sha256']==hashlib.sha256(raw).hexdigest()
            kinds=[event['kind'] for event in ledger.events('attempt')]
            assert 'evaluation_response_ambiguous' in kinds and 'evaluation_refused' not in kinds
            assert sum(method=='POST' for method,_ in seen)==1
            assert [method for method,_ in seen]==['POST','GET','GET']
        finally:await client.close();ledger.close()
    asyncio.run(work())


@pytest.mark.parametrize('status',[400,401,403,404,409,422,429])
def test_client_refusal_remains_refusal_without_reconciliation_or_retry(tmp_path,status):
    class Refused:
        calls=0
        async def evaluate(self,*args):
            self.calls+=1
            raise ClientError('controlled typed refusal',status_code=status,response_record={'controlled':'validation'})
        async def evaluation_request(self,*args):raise AssertionError('A typed client refusal is not an ambiguous POST')
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');client=Refused()
        try:
            with pytest.raises(ClientError) as error:
                await evaluation_once(client,'single_cc',{'request_id':'frozen'},ledger,'attempt')
            assert error.value.status_code==status and client.calls==1
            assert [row['kind'] for row in ledger.events('attempt')]==['evaluation_submitting','evaluation_refused']
        finally:ledger.close()
    asyncio.run(work())


@pytest.mark.parametrize('reconciliation',['not_found','transport_loss','server_error'])
def test_unresolved_history_after_502_never_becomes_unlaunched(tmp_path,reconciliation):
    class Uncertain:
        posts=0;gets=0
        async def evaluate(self,*args):
            self.posts+=1;raise ClientError('gateway timed out',status_code=502)
        async def evaluation_request(self,identity):
            assert identity=='frozen';self.gets+=1
            if reconciliation=='transport_loss':raise httpx.ReadTimeout('controlled history loss')
            raise ClientError('controlled history unavailable',status_code=404 if reconciliation=='not_found' else 503)
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');client=Uncertain()
        try:
            for _ in range(2):
                if reconciliation=='server_error':
                    with pytest.raises(ClientError) as error:
                        await evaluation_once(client,'single_cc',{'request_id':'frozen'},ledger,'attempt')
                    assert error.value.evaluation_delivery_unknown is True
                else:
                    value=await evaluation_once(client,'single_cc',{'request_id':'frozen'},ledger,'attempt')
                    assert value['delivery']=='unknown' and value['launched'] is True
            assert client.posts==1 and client.gets==2
            assert 'evaluation_refused' not in [row['kind'] for row in ledger.events('attempt')]
        finally:ledger.close()
    asyncio.run(work())
