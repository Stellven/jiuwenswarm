"""HTTP cancellation cannot acknowledge while an actual owner is outstanding."""
import asyncio

import pytest

from .shell_fixture import NativeShell


@pytest.mark.asyncio
async def test_http_cancel_awaits_both_owners_and_reconciles_without_new_effect(tmp_path):
    shell=await NativeShell().open(tmp_path);entered=asyncio.Event();release=asyncio.Event();effects=[]
    class Owner:
        def __init__(self,name):self.name=name
        async def contain_run(self,run_id,request_id):
            effects.append((self.name,run_id,request_id));entered.set();await release.wait()
            return {'contained':True,'run_id':run_id,'request_id':request_id}
    task=None
    try:
        shell.service.model=Owner('model');shell.service.executor=Owner('executor')
        shell.store.create_run('active',account_id='alice',workspace_id='project',submission={})
        shell.store.set_run_state('active','running')
        partial=shell.store.put_blob(b'original partial evidence\x00\xff')
        task=asyncio.create_task(shell.client.post('/api/v1/runs/active/cancel',
            json={'request_id':'cancel:one'},headers=shell.headers))
        await asyncio.wait_for(entered.wait(),5);await asyncio.sleep(0)
        assert not task.done() and shell.store.get_run('active')['state']=='running'
        release.set();response=await asyncio.wait_for(task,5)
        assert response.status_code==200 and response.json()['status']=='terminal'
        assert shell.store.get_run('active')['state']=='halted'
        assert shell.store.read_blob(partial)==b'original partial evidence\x00\xff'
        repeated=await shell.client.post('/api/v1/runs/active/cancel',
            json={'request_id':'cancel:one'},headers=shell.headers)
        assert repeated.json()==response.json() and len(effects)==2
        shell.store.create_run('other',account_id='alice',workspace_id='project',submission={})
        conflict=await shell.client.post('/api/v1/runs/other/cancel',
            json={'request_id':'cancel:one'},headers=shell.headers)
        assert conflict.status_code==409 and len(effects)==2
    finally:
        release.set()
        if task is not None:await asyncio.gather(task,return_exceptions=True)
        await shell.close()
