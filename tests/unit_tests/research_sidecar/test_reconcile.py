import asyncio
import httpx
from jiuwenswarm.research_sidecar.ledger import Ledger
from jiuwenswarm.research_sidecar.reconcile import submit_once


def test_ambiguous_delivery_reconciles_never_resubmits(tmp_path):
    class LostReply:
        submissions=0
        async def submit(self,payload):self.submissions+=1;raise httpx.ReadTimeout('controlled lost reply')
        async def reconcile(self,ident):return {'run_id':'one'}
    client=LostReply();ledger=Ledger(tmp_path/'ledger.sqlite');payload={'client_request_id':'a'}
    async def run():
        assert (await submit_once(client,payload,ledger,'attempt'))['run_id']=='one'
        assert (await submit_once(client,payload,ledger,'attempt'))['run_id']=='one'
    asyncio.run(run());assert client.submissions==1


def test_missing_reconciliation_after_lost_reply_stays_unknown_without_resend(tmp_path):
    from jiuwenswarm.research_sidecar.client import ClientError
    class Unknown:
        submissions=0
        async def submit(self,payload):self.submissions+=1;raise httpx.ReadTimeout('lost reply')
        async def reconcile(self,ident):raise ClientError('not found',status_code=404)
    client=Unknown();ledger=Ledger(tmp_path/'ledger.sqlite');payload={'client_request_id':'b'}
    async def run():
        for _ in range(2):
            value=await submit_once(client,payload,ledger,'attempt')
            assert value=={'delivery':'unknown','launched':True,'reconciliation':'not_found'}
    asyncio.run(run());assert client.submissions==1


def test_controlled_transport_discards_only_one_success_reply_and_reconciles(tmp_path):
    from jiuwenswarm.research_sidecar.client import DropSubmitReplyOnce
    # Explicit transport double tests fault wiring; actual HTTP proof is V03.
    seen=[]
    def handle(request):
        seen.append((request.method,request.url.path))
        return httpx.Response(200,json={'run_id':'one'})
    fault=DropSubmitReplyOnce(httpx.MockTransport(handle));ledger=Ledger(tmp_path/'ledger.sqlite')
    class Client:
        async def submit(self,payload):return (await self.http.post('/api/v1/runs',json=payload)).json()
        async def reconcile(self,identity):return (await self.http.get('/api/v1/runs',params={'client_request_id':identity})).json()
    async def work():
        client=Client();client.http=httpx.AsyncClient(base_url='http://controlled',transport=fault)
        assert await submit_once(client,{'client_request_id':'one'},ledger,'attempt')=={'run_id':'one'}
        assert await submit_once(client,{'client_request_id':'one'},ledger,'attempt')=={'run_id':'one'}
        await client.http.aclose()
    asyncio.run(work())
    assert seen==[('POST','/api/v1/runs'),('GET','/api/v1/runs'),('GET','/api/v1/runs')]
    assert fault.observations==[{'method':'POST','path':'/api/v1/runs','observed_reply_status':200,
        'fault':'discard_successful_submit_reply_once','actual_response_received':True}]
    assert [x['kind'] for x in ledger.events('attempt')]==['submitting','delivery_ambiguous','reconciled']
    ledger.close()



def test_claimed_evaluation_restart_reconciles_without_live_readiness_or_resend(tmp_path):
    import asyncio
    from jiuwenswarm.research_sidecar.runner import Runner
    from jiuwenswarm.research_sidecar.ledger import Ledger
    payload={'request_id':'unknown','case_id':'controlled','campaign_id':'campaign','evaluation_profile_id':'profile'}
    class HistoricalOnly:
        async def readiness(self):raise AssertionError('Historical reconciliation must not need live E1 readiness')
        async def evaluation_request(self,identity):return {'request_id':identity,'status':'started','result':None,'failure_ref':None,'invalid_for_product':True}
        async def evaluate(self,*args):raise AssertionError('Durable claim cannot be resent')
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');ledger.claim('row',{'entry_mode':'node_replay','request':payload})
        try:
            runner=Runner(HistoricalOnly(),ledger,tmp_path)
            row={'run_id':'row','campaign_id':'campaign','case_id':'controlled','case_version':1,'config_id':'fixed','repeat_index':0}
            value=await runner.execute(row,{'entry_mode':'node_replay'},inventory={'readiness':'blocked','inventory_id':'now-unavailable'},submission=payload,expected_pins={})
            assert value['launched'] and value['outcome']=='interrupted' and value['outcome_detail']['reason']=='evaluation_delivery_unknown'
            assert value['started_at'] is None
        finally:ledger.close()
    asyncio.run(work())



def test_unknown_restart_indexes_exact_prior_and_new_raw_http_bytes_without_overwrite(tmp_path):
    """Controlled HTTP responses and real durable ledger; no model/Run is invented."""
    import asyncio,base64,hashlib,json
    import httpx
    from jiuwenswarm.research_sidecar.client import ResearchClient
    from jiuwenswarm.research_sidecar.evidence import write_once,read_verified
    from jiuwenswarm.research_sidecar.ledger import Ledger
    from jiuwenswarm.research_sidecar.runner import Runner
    token=tmp_path/'token';token.write_text('controlled-only');token.chmod(0o600)
    payload={'request_id':'unknown','case_id':'controlled','campaign_id':'campaign','evaluation_profile_id':'profile'}
    reply={'request_id':'unknown','status':'started','result':None,'failure_ref':None,'invalid_for_product':True}
    # Deliberately preserve distinct whitespace rather than reserialize a reply.
    original_body=json.dumps(reply,indent=2).encode()+b'\n'
    next_body=b' '+json.dumps(reply,separators=(',',':')).encode()+b'\n'
    calls=[]
    def transport(body):
        def handle(request):
            calls.append((request.method,request.url.path))
            assert request.method=='GET'
            return httpx.Response(200,content=body,headers={'content-type':'application/json'})
        return httpx.MockTransport(handle)
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');ledger.claim('row',{'entry_mode':'node_replay','request':payload})
        prior=ResearchClient('http://controlled',token,transport=transport(original_body))
        folder=tmp_path/'results/runs/row'
        await prior.evaluation_request(payload['request_id'])
        old=write_once(folder/'evaluation-http-captures.json',{'responses':prior.evaluation_http_captures})
        old_bytes=(folder/'evaluation-http-captures.json').read_bytes()
        await prior.close();ledger.close()
        ledger=Ledger(tmp_path/'ledger.sqlite');client=ResearchClient('http://controlled',token,transport=transport(next_body))
        row={'run_id':'row','campaign_id':'campaign','case_id':'controlled','case_version':1,'config_id':'fixed','repeat_index':0}
        try:
            runner=Runner(client,ledger,tmp_path/'results')
            result=await runner.execute(row,{'entry_mode':'node_replay'},inventory={'readiness':'blocked','inventory_id':'unavailable'},submission=payload,expected_pins={})
            assert result['launched'] and result['outcome']=='interrupted' and result['outcome_detail']['reason']=='evaluation_delivery_unknown'
            assert result['app_run_id'] is None and result['model_calls']==[]
            captures=[ref for ref in result['exports'] if ref['artifact_type']=='evaluation-http-captures']
            assert len(captures)==2 and len({ref['path'] for ref in captures})==2
            assert any(ref['path']=='evaluation-http-captures.json' and ref['sha256']==old['sha256'] for ref in captures)
            bodies=[]
            for ref in captures:
                value=json.loads(read_verified(folder,ref))
                for response in value['responses']:
                    body=base64.b64decode(response['body_base64'],validate=True)
                    assert hashlib.sha256(body).hexdigest()==response['sha256']
                    bodies.append(body)
            assert bodies==[original_body,next_body]
            history=(folder/'run_record.json').read_bytes()
            assert await runner.execute(row,{'entry_mode':'node_replay'},inventory={'readiness':'blocked','inventory_id':'still-unavailable'},submission=payload,expected_pins={})==result
            assert (folder/'run_record.json').read_bytes()==history
            assert (folder/'evaluation-http-captures.json').read_bytes()==old_bytes
            assert not any(ref['artifact_type']=='evaluation-http-result' for ref in result['exports'])
            assert calls==[('GET','/api/v1/evaluation/requests/unknown')]*3
        finally:await client.close();ledger.close()
    asyncio.run(work())



def test_restart_keeps_prior_raw_inventory_when_no_response_is_received(tmp_path):
    import base64,hashlib,json
    from jiuwenswarm.research_sidecar.client import ResearchClient
    from jiuwenswarm.research_sidecar.evidence import write_once,read_verified
    from jiuwenswarm.research_sidecar.runner import Runner
    token=tmp_path/'token';token.write_text('controlled-only');token.chmod(0o600)
    payload={'request_id':'uncertain','case_id':'controlled','campaign_id':'campaign','evaluation_profile_id':'profile'}
    body=b'{"request_id":"uncertain","status":"started","result":null,"failure_ref":null,"invalid_for_product":true}\n'
    capture={'method':'GET','path':'/api/v1/evaluation/requests/uncertain','status_code':200,
        'body_base64':base64.b64encode(body).decode(),'sha256':hashlib.sha256(body).hexdigest()}
    folder=tmp_path/'results/runs/row';original=write_once(folder/'evaluation-http-captures.json',{'responses':[capture]})
    def lost(request):
        assert request.method=='GET'
        raise httpx.ReadTimeout('Controlled reconciliation response loss',request=request)
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');ledger.claim('row',{'entry_mode':'node_replay','request':payload})
        client=ResearchClient('http://controlled',token,transport=httpx.MockTransport(lost))
        try:
            row={'run_id':'row','campaign_id':'campaign','case_id':'controlled','case_version':1,'config_id':'fixed','repeat_index':0}
            result=await Runner(client,ledger,tmp_path/'results').execute(row,{'entry_mode':'node_replay'},
                inventory={'readiness':'blocked','inventory_id':'unavailable'},submission=payload,expected_pins={})
            assert result['launched'] and result['outcome']=='interrupted'
            assert result['outcome_detail']['reason']=='evaluation_delivery_unknown'
            captures=[ref for ref in result['exports'] if ref['artifact_type']=='evaluation-http-captures']
            assert captures==[{'artifact_type':'evaluation-http-captures','path':'evaluation-http-captures.json','sha256':original['sha256']}]
            assert json.loads(read_verified(folder,captures[0]))=={'responses':[capture]}
        finally:await client.close();ledger.close()
    asyncio.run(work())


def test_reconciliation_refusal_indexes_exact_non_json_http_response(tmp_path):
    import base64,hashlib,json
    from jiuwenswarm.research_sidecar.client import ResearchClient
    from jiuwenswarm.research_sidecar.evidence import read_verified
    from jiuwenswarm.research_sidecar.runner import Runner
    token=tmp_path/'token';token.write_text('controlled-only');token.chmod(0o600)
    payload={'request_id':'uncertain','case_id':'controlled','campaign_id':'campaign','evaluation_profile_id':'profile'}
    body=b'upstream unavailable\r\n\x00'
    seen=[]
    def refuse(request):
        seen.append(request.method)
        return httpx.Response(503,content=body)
    async def work():
        ledger=Ledger(tmp_path/'ledger.sqlite');ledger.claim('row',{'entry_mode':'node_replay','request':payload})
        client=ResearchClient('http://controlled',token,transport=httpx.MockTransport(refuse))
        try:
            row={'run_id':'row','campaign_id':'campaign','case_id':'controlled','case_version':1,'config_id':'fixed','repeat_index':0}
            result=await Runner(client,ledger,tmp_path/'results').execute(row,{'entry_mode':'node_replay'},
                inventory={'readiness':'blocked','inventory_id':'unavailable'},submission=payload,expected_pins={})
            assert result['launched'] and result['outcome']=='interrupted' and result['outcome_detail']['reason']=='evaluation_http_refused'
            assert result['model_calls']==[] and result['app_run_id'] is None and seen==['GET']
            captures=[ref for ref in result['exports'] if ref['artifact_type']=='evaluation-http-captures']
            assert len(captures)==1
            response=json.loads(read_verified(tmp_path/'results/runs/row',captures[0]))['responses'][0]
            assert response['status_code']==503 and base64.b64decode(response['body_base64'],validate=True)==body
            assert response['sha256']==hashlib.sha256(body).hexdigest()
        finally:await client.close();ledger.close()
    asyncio.run(work())


def test_existing_capture_cannot_claim_other_request_or_swapped_body(tmp_path):
    import base64,hashlib,json
    import pytest
    from jiuwenswarm.research_sidecar.evidence import write_once
    from jiuwenswarm.research_sidecar.runner import _evaluation_capture_inventory
    body=b'original raw response'
    valid={'method':'GET','path':'/api/v1/evaluation/requests/frozen','status_code':200,
        'body_base64':base64.b64encode(body).decode(),'sha256':hashlib.sha256(body).hexdigest()}
    for kind in ('body','request','filename','symlink','hardlink'):
        folder=tmp_path/kind;folder.mkdir()
        capture=dict(valid)
        if kind=='body':capture['body_base64']=base64.b64encode(b'swapped').decode()
        if kind=='request':capture['path']='/api/v1/evaluation/requests/foreign'
        name='evaluation-http-captures-'+('0'*64)+'.json' if kind=='filename' else 'evaluation-http-captures.json'
        target=folder/name
        if kind in {'symlink','hardlink'}:
            outside=tmp_path/(kind+'-original.json');write_once(outside,{'responses':[capture]})
            if kind=='symlink':target.symlink_to(outside)
            else:target.hardlink_to(outside)
            original=outside.read_bytes()
        else:write_once(target,{'responses':[capture]})
        with pytest.raises((ValueError,OSError)):
            _evaluation_capture_inventory(folder,[],entry_mode='node_replay',request_id='frozen')
        assert not (folder/'run_record.json').exists()
        if kind in {'symlink','hardlink'}:assert outside.read_bytes()==original


def test_identical_raw_capture_is_indexed_once_across_recovery(tmp_path):
    import base64,hashlib
    from jiuwenswarm.research_sidecar.evidence import write_once
    from jiuwenswarm.research_sidecar.runner import _evaluation_capture_inventory
    body=b'original raw response'
    capture={'method':'GET','path':'/api/v1/evaluation/requests/frozen','status_code':404,
        'body_base64':base64.b64encode(body).decode(),'sha256':hashlib.sha256(body).hexdigest()}
    original=write_once(tmp_path/'evaluation-http-captures.json',{'responses':[capture]})
    before=(tmp_path/'evaluation-http-captures.json').read_bytes()
    rows=_evaluation_capture_inventory(tmp_path,[capture],entry_mode='node_replay',request_id='frozen')
    assert rows==[{'artifact_type':'evaluation-http-captures','path':'evaluation-http-captures.json','sha256':original['sha256']}]
    assert (tmp_path/'evaluation-http-captures.json').read_bytes()==before
    assert len(list(tmp_path.iterdir()))==1
