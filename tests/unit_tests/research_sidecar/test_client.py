import asyncio
import httpx


def test_explicit_virtual_host_authority_preserves_transport_endpoint_and_validates(tmp_path):
    import pytest
    from jiuwenswarm.research_sidecar.client import ResearchClient, ClientError
    token=tmp_path/'token';token.write_text('controlled-private-token');token.chmod(0o600)
    seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(200,json={'schema_version':'1.0.0','defaults':{}})
    async def work():
        client=ResearchClient('http://private-service:5173',token,http_authority='127.0.0.1:5175',transport=httpx.MockTransport(handle))
        try:await client.context()
        finally:await client.close()
        assert seen[0].url.host=='private-service' and seen[0].headers['host']=='127.0.0.1:5175'
        for value in ('http://host','host/path','user@host','host\r\nX-Evil: true','host:0','host:65536','host:', 'bad host', '//host'):
            with pytest.raises(ClientError):ResearchClient('http://private-service:5173',token,http_authority=value)
    asyncio.run(work())
from jiuwenswarm.research_sidecar.client import ResearchClient


def test_authorization_same_origin_supported_paths_only(tmp_path):
    token=tmp_path/'token';token.write_text('disposable-test-token');token.chmod(0o600);seen=[]
    def handle(req):
        seen.append(req)
        assert req.headers['authorization']=='Bearer disposable-test-token'
        return httpx.Response(200,json={'schema_version':'1.0.0','id':'readiness:test','client_contract_version':'1.0.0','instance_id':'test','build_id':'test',
            'operations':['submit'],'prerequisites':[],'ready':True,'evaluation_profile':None,'fault_injection':False,
            'pins':{'app_build':'test','client_contract_version':'1.0.0','library_snapshot_sha256':'a'*64,'plan_policy_ref':{'id':'p','sha256':'b'*64},'check_bundle_set_sha256':'c'*64,'router_enabled':False,'router_version':None}})
    async def work():
        client=ResearchClient('http://test',token,transport=httpx.MockTransport(handle))
        assert (await client.readiness())['ready'];await client.close()
    asyncio.run(work())
    assert str(seen[0].url)=='http://test/api/v1/readiness'


def test_source_upload_kinds_and_validated_refusal_are_preserved(tmp_path):
    import pytest
    from jiuwenswarm.research_sidecar.client import ClientError
    token=tmp_path/'token';token.write_text('disposable-test-token');token.chmod(0o600)
    source=tmp_path/'visible.txt';source.write_text('controlled visible input');seen=[]
    error={'schema_version':'1.0.0','id':'error:controlled','category':'validation','message':'Controlled refused fixture.',
        'request_id':None,'run_id':None,'evidence_refs':[],'correction':'Inspect the controlled request.'}
    def handle(request):
        seen.append(request)
        if request.method == 'GET' and request.url.path == '/api/v1/inputs':
            return httpx.Response(200, json=[])
        return httpx.Response(422,json=error)
    async def work():
        client=ResearchClient('http://test',token,transport=httpx.MockTransport(handle))
        for kind in ('docs','repo','datasets'):
            with pytest.raises(ClientError) as captured:await client.upload(kind,'scope',source)
            assert captured.value.response_record==error
            assert str(seen[-1].url)=='http://test/api/v1/inputs/'+kind
        count=len(seen)
        with pytest.raises(ClientError):await client.upload('document','scope',source)
        assert len(seen)==count
        await client.close()
    asyncio.run(work())


async def actual_evaluation_http(root,*,single=False,bad_span=True):
    """Actual ASGI/finite token/core owner; native transport is controlled."""
    from types import SimpleNamespace
    from fastapi import FastAPI
    from jiuwenswarm.research.shell_auth import SessionAuthority
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
    if single:
        from tests.unit_tests.research.test_evaluation_provider import installed_provider
        store,provider,actor,payload=await installed_provider(root/'core')
    else:
        from tests.unit_tests.research.test_evaluation_replay import replay_fixture
        store,provider,actor,payload,_,_=await replay_fixture(root/'core',bad_span=bad_span,record_gate=True)
    from tests.unit_tests.research.evaluation_runtime_fixture import bind_request_runtime
    owner = bind_request_runtime(store, provider, payload, 'E3' if single else 'E2')
    assets=provider.assets;authority=SessionAuthority(root/'auth','http://testserver')
    authority.initialize(Principal(actor.account_id,actor.workspace_ids,frozenset({'readiness','status','submit'})))
    context={k:assets[k] for k in ('account_id','workspace_id','configuration_ref')}
    context.update(profile_ref=provider.profile_ref,profile_id=provider.profile['profile_id'])
    authority.configure_evaluation(context,run_lookup=lambda _:None,run_reconcile=lambda *_:[],campaign_id=assets['campaign_id'],
                                   runtime_ref=owner.runtime_ref, assets_ref=provider.assets_ref)
    token=root/'evaluation-token'
    authority.issue_evaluation({'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':assets['campaign_id']},token)
    async def readiness(principal):
        return {'schema_version':'1.0.0','id':'ready:finite','client_contract_version':'1.0.0','instance_id':'finite','build_id':'controlled',
            'operations':['node_replay' if p=='E2' else 'single_cc' for p in provider.available_entry_points],
            'prerequisites':[],'ready':False,'evaluation_profile':provider.profile['profile_id'],'fault_injection':False,
            'pins':{'app_build':'controlled','client_contract_version':'1.0.0','library_snapshot_sha256':provider.profile['library_snapshot_sha256'],
                'plan_policy_ref':{'id':'p','sha256':'a'*64},'check_bundle_set_sha256':'b'*64,'router_enabled':False,'router_version':None}}
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    service=SimpleNamespace(evaluation_provider=provider,readiness=readiness,
        evaluation_reader=EvaluationReader(store, runtime_ref=owner.runtime_ref))
    channel=SimpleNamespace(research_profile=True,research_service=service,research_authority=authority,set_handshake_auth=lambda _:None)
    app=FastAPI();mount_research_routes(app,channel)
    return store,provider,payload,app,authority,token


def test_actual_e2_http_runner_reconciles_lost_reply_without_product_submit_or_replay(tmp_path):
    from jiuwenswarm.research_sidecar.runner import Runner
    from jiuwenswarm.research_sidecar.ledger import Ledger
    from jiuwenswarm.research_sidecar.adapters.verifier import validate_citation
    async def work():
        store,provider,payload,app,authority,token=await actual_evaluation_http(tmp_path)
        paths=[]
        class LoseReply(httpx.AsyncBaseTransport):
            def __init__(self):self.inner=httpx.ASGITransport(app=app);self.dropped=False
            async def handle_async_request(self,req):
                paths.append((req.method,req.url.path));response=await self.inner.handle_async_request(req)
                if req.method=='POST' and not self.dropped:
                    self.dropped=True;await response.aclose();raise httpx.ReadTimeout('Controlled actual reply loss',request=req)
                return response
            async def aclose(self):await self.inner.aclose()
        client=ResearchClient('http://testserver',token,transport=LoseReply());ledger=Ledger(tmp_path/'ledger.sqlite')
        row={'run_id':'evaluation-row','campaign_id':'campaign','case_id':payload['case_id'],'case_version':1,'config_id':'finite','repeat_index':0}
        runner=Runner(client,ledger,tmp_path/'results')
        before=len(list(store.iter_records(kinds=('model-call-start',))))
        try:
            result=await runner.execute(row,{'entry_mode':'node_replay'},inventory={'readiness':'ready','inventory_id':'finite'},submission=payload,expected_pins={})
            assert result['launched'] and result['app_run_id'] is None
            value=__import__('json').loads((tmp_path/'results/runs/evaluation-row/evaluation-result.json').read_bytes())
            # Actual source-span Tier1 counterpart proves the same tier ordering;
            # this is not a claim that the complete C001 citation campaign ran.
            validate_citation({'tier1':value['tier1_verdict'],'tier2':value['tier2_verdict'],'advanced':value['advanced'],'verifier_calls':len(value['model_calls'])})
            assert any('original' in reason.lower() for reason in result['limitations'])
            import base64,hashlib,json
            from jiuwenswarm.research_sidecar.evidence import read_verified
            folder=tmp_path/'results/runs/evaluation-row'
            captures=[ref for ref in result['exports'] if ref['artifact_type']=='evaluation-http-captures']
            assert len(captures)==1 and captures[0]['path']=='evaluation-http-captures.json'
            original=read_verified(folder,captures[0]);capture=json.loads(original)
            assert capture['responses'] and all(response['method']=='GET' for response in capture['responses'])
            for response in capture['responses']:
                raw=base64.b64decode(response['body_base64'],validate=True)
                assert hashlib.sha256(raw).hexdigest()==response['sha256']
                assert json.loads(raw)['result']==value and b'Bearer ' not in raw
            history=(folder/'run_record.json').read_bytes()
            repeated=await runner.execute(row,{'entry_mode':'node_replay'},inventory={'readiness':'ready','inventory_id':'finite'},submission=payload,expected_pins={})
            assert repeated==result and (folder/'run_record.json').read_bytes()==history
            assert read_verified(folder,captures[0])==original
            assert len([p for p in paths if p==('POST','/api/v1/evaluation/node-replay')])==1
            assert not any(path=='/api/v1/runs' for _,path in paths)
            assert any(method=='GET' and '/evaluation/requests/' in path for method,path in paths)
            assert len(list(store.iter_records(kinds=('model-call-start',))))==before
            assert len(list(store.iter_records(kinds=('evaluation-request',))))==1
        finally:await client.close();ledger.close();authority.close();store.close()
    asyncio.run(work())


def test_actual_e3_http_uses_installed_owner_and_missing_provider_has_zero_new_effects(tmp_path):
    from jiuwenswarm.research_sidecar.client import ClientError
    import pytest
    async def work():
        store,provider,payload,app,authority,token=await actual_evaluation_http(tmp_path,single=True)
        client=ResearchClient('http://testserver',token,transport=httpx.ASGITransport(app=app))
        try:
            result=await client.evaluate('single_cc',payload)
            assert result['invalid_for_product'] and result['status']=='blocked'
            assert (await client.evaluation_request(payload['request_id']))['result']==result
            assert await client.evaluate('single_cc',payload)==result
            assert len(list(store.iter_records(kinds=('evaluation-invocation-observation',))))==1
            assert not list(store.iter_records(kinds=('invocation-observation',)))
            app.state.research_service.evaluation_provider=None
            with pytest.raises(ClientError) as error:await client.evaluate('single_cc',payload|{'request_id':'missing-profile'})
            assert error.value.status_code==503
            assert len(list(store.iter_records(kinds=('evaluation-invocation-observation',))))==1
        finally:await client.close();authority.close();store.close()
    asyncio.run(work())



def test_actual_e2_valid_counterpart_runs_only_independent_reviews_and_preserves_claim_once(tmp_path):
    async def work():
        store,provider,payload,app,authority,token=await actual_evaluation_http(tmp_path,bad_span=False)
        client=ResearchClient('http://testserver',token,transport=httpx.ASGITransport(app=app))
        before={row['ref']['id'] for row in store.iter_records(kinds=('model-call-start',))}
        try:
            value=await client.evaluate('node_replay',payload)
            assert value['tier1_verdict']=='PASS' and value['tier2_verdict'] in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'}
            assert value['model_calls'] and all(call['role']=='verifier' for call in value['model_calls'])
            count=len(list(store.iter_records(kinds=('model-call-start',))))
            assert count>len(before)
            assert await client.evaluate('node_replay',payload)==value
            assert len(list(store.iter_records(kinds=('model-call-start',))))==count
            assert not list(store.iter_records(kinds=('acceptance-commit',)))
        finally:await client.close();authority.close();store.close()
    asyncio.run(work())


def test_ambiguous_started_evaluation_is_read_only_reconciled_without_second_post(tmp_path):
    from jiuwenswarm.research_sidecar.reconcile import evaluation_once
    from jiuwenswarm.research_sidecar.ledger import Ledger
    import pytest
    token=tmp_path/'token';token.write_text('controlled-token');token.chmod(0o600);seen=[]
    payload={'request_id':'unknown','case_id':'controlled','campaign_id':'campaign','evaluation_profile_id':'profile'}
    def handle(request):
        seen.append(request.method)
        if request.method=='POST':raise httpx.ReadTimeout('Controlled loss after server claim',request=request)
        return httpx.Response(200,json={'request_id':'unknown','status':'started','result':None,'failure_ref':None,'invalid_for_product':True})
    async def work():
        client=ResearchClient('http://controlled',token,transport=httpx.MockTransport(handle));ledger=Ledger(tmp_path/'ledger.sqlite')
        try:
            for _ in range(2):
                value=await evaluation_once(client,'node_replay',payload,ledger,'row')
                assert value['delivery']=='unknown' and value['launched']
            assert seen==['POST','GET','GET']
            with pytest.raises(ValueError):await evaluation_once(client,'single_cc',payload,ledger,'row')
            assert seen==['POST','GET','GET']
        finally:await client.close();ledger.close()
    asyncio.run(work())
