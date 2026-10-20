"""Real native session grants protect the actual durable service seam."""
import pytest

from .shell_fixture import NativeShell


@pytest.mark.asyncio
async def test_cookie_bootstrap_query_and_client_actor_cannot_grant_http_authority(tmp_path):
    shell=await NativeShell().open(tmp_path)
    try:
        request=await shell.submission()
        for headers in ({},{'Authorization':'Bearer invalid'}):
            response=await shell.client.post('/api/v1/runs?user_id=alice',json=request,headers=headers)
            assert response.status_code==401 and response.json()['category']=='auth'
        reused=await shell.client.post('/auth/research/bootstrap',json={'challenge':shell.challenge},
            headers={'Origin':'http://testserver'})
        assert reused.status_code==401
        assert not shell.store.list_runs(account_id='alice') and shell.calls==[]
        foreign=await shell.client.post('/api/v1/runs',json=dict(request,workspace_id='foreign'),headers=shell.headers)
        assert foreign.status_code==403
        assert shell.token not in foreign.text and shell.challenge not in foreign.text
    finally:await shell.close()


@pytest.mark.asyncio
async def test_revocation_persists_across_authority_and_service_reopen(tmp_path):
    shell=await NativeShell().open(tmp_path);token=shell.token
    response=await shell.client.post('/auth/research/logout',headers=shell.headers)
    assert response.status_code==200 and response.json()=={'revoked':True}
    await shell.close()
    reopened=await NativeShell().open(tmp_path,recover=True,initialize=False);reopened.token=token
    try:
        response=await reopened.client.get('/api/v1/runs?client_request_id=unknown',headers=reopened.headers)
        assert response.status_code==401 and token not in response.text
        assert not reopened.store.list_runs(account_id='alice') and reopened.calls==[]
    finally:await reopened.close()
