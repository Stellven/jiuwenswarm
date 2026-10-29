"""Actual HTTP routing with disposable grants and controlled service effects.

This is a local adapter control, not the mapped real startup/proxy qualification.
"""
import copy
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.shell_auth import SessionAuthority


def test_actual_http_rejects_same_account_foreign_campaign_before_effect_or_bytes(tmp_path):
    config={'id':'config','sha256':'a'*64};profile={'id':'profile','sha256':'b'*64}
    auth=SessionAuthority(tmp_path/'sessions','http://testserver')
    auth.initialize(Principal('owner',frozenset({'work'}),frozenset({'status','submit','readiness','export','reconcile','cancel'})))
    context={'account_id':'owner','workspace_id':'work','configuration_ref':config,'profile_ref':profile,'profile_id':'approved'}
    run={'id':'run:one','account_id':'owner','workspace_id':'work','submission':{'profile_id':'approved','configuration_ref':config,'evaluation':{'campaign_id':'one'}}}
    auth.configure_evaluation(context,run_lookup=lambda _:copy.deepcopy(run),run_reconcile=lambda *_:[copy.deepcopy(run)])
    binding={'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':'two'}
    auth.issue_evaluation(binding,tmp_path/'token')
    header={'Authorization':'Bearer '+(tmp_path/'token').read_text(encoding='ascii')}
    service=SimpleNamespace(submit=AsyncMock(),get=AsyncMock(),cancel=AsyncMock(),list=AsyncMock(),artifact=AsyncMock(),artifact_bytes=AsyncMock())
    channel=SimpleNamespace(research_profile=True,research_authority=auth,research_service=service,set_handshake_auth=Mock())
    from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
    app=FastAPI();mount_research_routes(app,channel)
    with TestClient(app) as client:
        requests=[('POST','/api/v1/runs',{'workspace_id':'work',**run['submission']}),
            ('GET','/api/v1/runs/run:one',None),('GET','/api/v1/runs?client_request_id=one',None),
            ('POST','/api/v1/runs/run:one/cancel',{'request_id':'cancel'}),('GET','/api/v1/runs/run:one/export',None)]
        for method,path,payload in requests:
            response=client.request(method,path,headers=header,json=payload)
            assert response.status_code==403,(path,response.status_code,response.text)
        assert client.get('/api/v1/runs/run:one/export',headers={**header,'Accept':'application/zip'}).status_code==403
        assert client.post('/api/v1/evaluation/credentials',headers=header).status_code==404
    for method in vars(service).values():method.assert_not_called()
    auth.close()


def test_actual_http_uses_own_campaign_grant_and_revocation(tmp_path):
    config={'id':'config','sha256':'a'*64};profile={'id':'profile','sha256':'b'*64}
    auth=SessionAuthority(tmp_path/'sessions','http://testserver')
    auth.initialize(Principal('owner',frozenset({'work'}),frozenset({'status','submit'})))
    context={'account_id':'owner','workspace_id':'work','configuration_ref':config,'profile_ref':profile,'profile_id':'approved'}
    submission={'workspace_id':'work','profile_id':'approved','configuration_ref':config,'evaluation':{'campaign_id':'one'}}
    run={'id':'run:one','account_id':'owner','workspace_id':'work','submission':submission}
    auth.configure_evaluation(context,run_lookup=lambda _:copy.deepcopy(run),run_reconcile=lambda *_:[copy.deepcopy(run)])
    result=auth.issue_evaluation({'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':'one'},tmp_path/'token')
    header={'Authorization':'Bearer '+(tmp_path/'token').read_text(encoding='ascii')}
    service=SimpleNamespace(submit=AsyncMock(return_value={'run_id':'run:one'}),get=AsyncMock(return_value={'run_id':'run:one'}))
    channel=SimpleNamespace(research_profile=True,research_authority=auth,research_service=service,set_handshake_auth=Mock())
    from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
    app=FastAPI();mount_research_routes(app,channel)
    with TestClient(app) as client:
        assert client.post('/api/v1/runs',json=submission,headers=header).status_code==200
        assert client.get('/api/v1/runs/run:one',headers=header).status_code==200
        auth.revoke_evaluation(result['grant_id'])
        assert client.get('/api/v1/runs/run:one',headers=header).status_code==401
    service.submit.assert_awaited_once();service.get.assert_awaited_once()
    auth.close()
