"""Actual native route to durable allocation; controlled compiler only."""
import asyncio

import pytest

from .shell_fixture import NativeShell


@pytest.mark.asyncio
async def test_concurrent_http_submit_and_reconcile_have_one_actor_owned_allocation(tmp_path):
    shell=await NativeShell().open(tmp_path)
    try:
        request=await shell.submission()
        first,duplicate=await asyncio.gather(*[
            shell.client.post('/api/v1/runs',json=request,headers=shell.headers) for _ in range(2)])
        assert first.status_code==duplicate.status_code==200
        run_id=first.json()['run_id'];assert duplicate.json()['run_id']==run_id
        await shell.settle()
        assert shell.calls==[run_id]
        assert shell.store.get_run(run_id)['account_id']=='alice'
        assert len(shell.store.list_runs(account_id='alice'))==1
        before=list(shell.store.iter_records())
        for _ in range(3):
            status=await shell.client.get('/api/v1/runs?client_request_id=request:one',headers=shell.headers)
            assert status.status_code==200 and status.json()['run_id']==run_id
        assert list(shell.store.iter_records())==before and shell.calls==[run_id]
    finally:await shell.close()


@pytest.mark.asyncio
async def test_changed_content_reuse_is_http_conflict_without_second_allocation(tmp_path):
    shell=await NativeShell().open(tmp_path)
    try:
        request=await shell.submission()
        first=await shell.client.post('/api/v1/runs',json=request,headers=shell.headers)
        assert first.status_code==200
        changed=await shell.client.post('/api/v1/runs',json=dict(request,interaction_mode='headless'),headers=shell.headers)
        assert changed.status_code==409 and changed.json()['category']=='conflict'
        await shell.settle()
        assert len(shell.calls)==len(shell.store.list_runs(account_id='alice'))==1
    finally:await shell.close()
