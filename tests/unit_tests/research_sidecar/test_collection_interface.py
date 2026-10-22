"""Connected ordinary HTTP collection, using disposable non-model fixtures."""
import asyncio
import hashlib
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.shell_auth import SessionAuthority
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from jiuwenswarm.research.uploads import UploadManager
from jiuwenswarm.research.intake import extract_document
from jiuwenswarm.research_sidecar.client import ResearchClient, ClientError


def test_actual_intake_upload_scoped_snapshot_stream_and_confirmation(tmp_path):
    async def work():
        store=SQLiteRunStore(tmp_path/'state');ref=store.put_blob(b'protected')
        configuration=store.put_blob(json_bytes({'schema_version':'1.0.0','cc':{'plan_source':'static','plan_policy_ref':ref,
            'static_template_ref':ref,'evaluation_profile_ref':None,'router':{'enabled':False,'deadline_s':30,'profile_ref':None}},
            'rsi':{'custodian_key_id':None,'custodian_public_key':None},'codex':{'route_id':'codex-cli-default'},'role_aliases':{}}))
        service=ResearchService(store,registry=Registry(),model=None)
        service.configure_workspace('alice','project',configuration_ref=configuration,profile_ref=ref,workspace_ref=ref,input_directory_ref=ref)
        service.upload_manager=UploadManager(store,tmp_path/'uploads',extract_document,extraction_timeout_s=3,max_upload_bytes=1024)
        principal=Principal('alice',frozenset({'project'}),frozenset({'submit','status','export','upload','reconcile'}))
        authority=SessionAuthority(tmp_path/'auth','http://testserver');authority.initialize(principal)
        channel=SimpleNamespace(research_profile=True,research_service=service,research_authority=authority,set_handshake_auth=lambda _:None)
        app=FastAPI();mount_research_routes(app,channel)
        client=ResearchClient('http://testserver',authority.token_path,transport=httpx.ASGITransport(app=app))
        try:
            context=await client.context();assert context['defaults']['workspace_id']=='project'
            source=tmp_path/'visible.txt';source.write_text('Only permitted original input')
            upload=await client.upload('docs','project',source)
            intake=await client.prepare_intake('Research the supplied input',[upload['id']])
            qualified=store.read_record(intake['intake_ref'],contract_id='qualified-intake')
            assert store.read_blob(qualified['request_ref'])==b'Research the supplied input'
            assert len(qualified['upload_refs'])==1 and intake['submission_defaults']['interaction_mode']=='headless'
            with pytest.raises(ClientError) as error:
                await client.prepare_intake('Foreign workspace',[],workspace_id='foreign')
            assert error.value.status_code==403
            # Deliberately no model request: allocate the owned terminal fixture.
            submission={**intake['submission_defaults'],'client_request_id':'request-1','intake_ref':intake['intake_ref']}
            store.create_run('run:owned',account_id='alice',workspace_id='project',submission=submission)
            store.set_run_state('run:owned','halted',reason='controlled_fixture')
            events=await client.events('run:owned')
            assert events['events']==[] and events['metrics']['cpu'] is None
            raw=b'Actual fixture artifact bytes\n';output=store.put_blob(raw)
            store.append_record('invocation-observation',{'id':'observation:fixture','run_id':'run:owned','output_refs':[output]})
            manifest=await client.artifacts('run:owned')
            item=next(item for item in manifest['artifacts'] if item['sha256']==output['sha256'])
            destination=tmp_path/'collected.bin'
            received=await client.download_artifact('run:owned',item['artifact_id'],destination,sha256=item['sha256'],size=item['size'])
            assert destination.read_bytes()==raw and received['sha256']==hashlib.sha256(raw).hexdigest()
            assert await client.download_artifact('run:owned',item['artifact_id'],destination,sha256=item['sha256'],size=item['size'])==received
            with pytest.raises(ClientError):
                await client.confirm_collection('run:owned',manifest['manifest_sha256'],[])
            receipt=await client.confirm_collection('run:owned',manifest['manifest_sha256'],manifest['artifacts'])
            assert receipt['status']=='confirmed'
            assert await client.confirm_collection('run:owned',manifest['manifest_sha256'],manifest['artifacts'])==receipt
            assert store.read_blob(output)==raw
            # A separate account cannot use the artifact identity as authority.
            other=Principal('bob',frozenset({'project'}),frozenset({'export'}))
            authority.initialize(other)
            other_client=ResearchClient('http://testserver',authority.token_path,transport=httpx.ASGITransport(app=app))
            try:
                with pytest.raises(ClientError) as error:await other_client.artifacts('run:owned')
                assert error.value.status_code==404
            finally:await other_client.close()
        finally:await client.close();authority.close();store.close()
    asyncio.run(work())


def test_interrupted_or_bad_download_never_publishes_or_overwrites(tmp_path):
    async def work():
        token=tmp_path/'token';token.write_text('fixture-only');token.chmod(0o600)
        async def handle(request):return httpx.Response(200,content=b'truncated')
        client=ResearchClient('http://fixture',token,transport=httpx.MockTransport(handle))
        destination=tmp_path/'artifact'
        try:
            with pytest.raises(ClientError):
                await client.download_artifact('run','artifact',destination,sha256='a'*64,size=20)
            assert not destination.exists() and not list(tmp_path.glob('.download-*'))
            destination.write_bytes(b'existing sentinel')
            with pytest.raises(ClientError):
                await client.download_artifact('run','artifact',destination,sha256='a'*64,size=20)
            assert destination.read_bytes()==b'existing sentinel'
        finally:await client.close()
    asyncio.run(work())
