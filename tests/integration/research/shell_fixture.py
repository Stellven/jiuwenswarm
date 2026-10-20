"""Actual HTTP/auth/store composition; compiler and containment are controlled.

This fixture grants no model or acceptance authority and asserts no live target.
"""
import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI

from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.intake import extract_document
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.shell_auth import SessionAuthority
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from jiuwenswarm.research.uploads import UploadManager


class NativeShell:
    async def open(self, root, *, compiler=None, recover=False, initialize=True, origin='http://testserver'):
        self.root=root;self.calls=[]
        self.store=SQLiteRunStore(root/'state',recover=recover)
        ref=self.store.put_blob(b'controlled protected configuration dependency')
        self.configuration=self.store.put_blob(json_bytes({'schema_version':'1.0.0',
            'cc':{'plan_source':'static','plan_policy_ref':ref,'static_template_ref':ref,
                'evaluation_profile_ref':None,'router':{'enabled':False,'deadline_s':30,'profile_ref':None}},
            'rsi':{'custodian_key_id':None,'custodian_public_key':None},
            'codex':{'route_id':'codex-cli-default'},'role_aliases':{}}))
        async def stopped(run_id, protected):
            self.calls.append(run_id)
            return {'accepted':False}
        self.service=ResearchService(self.store,registry=Registry(),model=None,
            compiler=compiler or stopped,
            upload_manager=UploadManager(self.store,self.store.input_root,extract_document,
                extraction_timeout_s=2,max_upload_bytes=1024*1024))
        self.service.configure_workspace('alice','project',configuration_ref=self.configuration,
            profile_ref=ref,workspace_ref=ref,input_directory_ref=ref)
        self.principal=Principal('alice',frozenset({'project'}),frozenset({
            'submit','status','reconcile','export','cancel','upload','list_uploads','delete_upload','readiness'}))
        self.authority=SessionAuthority(root/'sessions',origin)
        self.channel=SimpleNamespace(research_profile=True,research_service=self.service,
            research_authority=self.authority,set_handshake_auth=lambda callback:None)
        self.app=FastAPI();mount_research_routes(self.app,self.channel)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=origin)
        if initialize:
            self.challenge=urlsplit(self.authority.initialize(self.principal)).fragment.split('=',1)[1]
            response=await self.client.post('/auth/research/bootstrap',json={'challenge':self.challenge},
                headers={'Origin':origin})
            assert response.status_code==200,response.text
            self.token=response.json()['token']
        return self

    @property
    def headers(self):return {'Authorization':'Bearer '+self.token}

    async def submission(self, request_id='request:one', *, uploads=()):
        intake=await self.service.ingest(self.principal,'Investigate retrieval latency',uploads,workspace_id='project')
        return {'schema_version':'1.0.0','id':'submission:one','client_request_id':request_id,
            'account_id':'forged-client-account','workspace_id':'project',
            'configuration_ref':self.configuration,'intake_ref':intake}

    async def settle(self):
        pending=tuple(self.service._tasks.values())
        if pending:await asyncio.wait_for(asyncio.gather(*pending),5)

    async def close(self):
        pending=tuple(self.service._tasks.values())+tuple(self.service._containments.values())
        for task in pending:
            if not task.done():task.cancel()
        if pending:await asyncio.gather(*pending,return_exceptions=True)
        await self.client.aclose();self.authority.close();self.store.close()
