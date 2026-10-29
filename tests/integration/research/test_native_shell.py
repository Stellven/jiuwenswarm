"""Native CLI subprocesses speak real loopback HTTP to the durable service.

This controlled local server is not the full product deployment or a model run.
"""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import io
import json
import socket
import sys
import zipfile

import pytest
import uvicorn

from .shell_fixture import NativeShell


@asynccontextmanager
async def actual_server(root):
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(16)
    origin='http://127.0.0.1:'+str(listener.getsockname()[1])
    shell=await NativeShell().open(root,origin=origin)
    server=uvicorn.Server(uvicorn.Config(shell.app,log_level='error',access_log=False,lifespan='off'))
    task=asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():await task
                await asyncio.sleep(.01)
        yield shell,origin
    finally:
        server.should_exit=True
        try:await asyncio.wait_for(task,5)
        finally:listener.close();await shell.close()


async def cli(shell,origin,*arguments):
    process=await asyncio.create_subprocess_exec(sys.executable,'-m','jiuwenswarm.channels.cli.main',
        'research','--origin',origin,'--token-file',str(shell.authority.token_path),*arguments,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:stdout,stderr=await asyncio.wait_for(process.communicate(),10)
    finally:
        if process.returncode is None:
            process.kill();await process.wait()
    assert shell.token.encode() not in stdout+stderr
    return process.returncode,stdout,stderr


@pytest.mark.asyncio
async def test_native_cli_actual_http_status_and_exclusive_export_are_inspection_only(tmp_path):
    async with actual_server(tmp_path) as (shell,origin):
        # Explicit state fixture: no accepted Capsule or gate decision is manufactured.
        shell.store.create_run('run:cli',account_id='alice',workspace_id='project',
            submission={'client_request_id':'request:cli'})
        shell.store.set_run_state('run:cli','halted',reason='controlled-fixture')
        original=shell.store.append_record('escalation',{'id':'escalation:cli','run_id':'run:cli','reason_code':'controlled-fixture'})
        before=list(shell.store.iter_records())
        code,stdout,stderr=await cli(shell,origin,'status','run:cli')
        assert code==1 and json.loads(stdout)['status']=='halted'
        output=tmp_path/'export.zip'
        code,stdout,stderr=await cli(shell,origin,'export','run:cli','--output',str(output))
        assert code==0 and json.loads(stdout)['bytes']==output.stat().st_size
        saved=output.read_bytes()
        with zipfile.ZipFile(io.BytesIO(saved)) as archive:
            manifest=json.loads(archive.read('client_retrieval.json'))
            assert any(file['artifact_ref']==original for file in manifest['files'])
            for file in manifest['files']:
                assert hashlib.sha256(archive.read(file['path'])).hexdigest()==file['artifact_ref']['sha256']
        code,stdout,stderr=await cli(shell,origin,'export','run:cli','--output',str(output))
        assert code==3 and output.read_bytes()==saved
        assert shell.calls==[] and list(shell.store.iter_records())==before


@pytest.mark.asyncio
async def test_native_cli_actual_upload_list_delete_and_revocation(tmp_path):
    async with actual_server(tmp_path) as (shell,origin):
        raw='CLI original café 😀\n'.encode();source=tmp_path/'paper.txt';source.write_bytes(raw)
        code,stdout,stderr=await cli(shell,origin,'upload','docs',str(source),'--scope','project')
        assert code==0
        record=json.loads(stdout);assert shell.store.read_upload(record['id'],'alice')==raw
        code,stdout,stderr=await cli(shell,origin,'uploads','--scope','project')
        assert code==0 and any(value['id']==record['id'] for value in json.loads(stdout))
        code,stdout,stderr=await cli(shell,origin,'delete-upload',record['id'])
        assert code==0 and json.loads(stdout)['status']=='deleted'
        shell.authority.revoke(shell.token)
        code,stdout,stderr=await cli(shell,origin,'uploads','--scope','project')
        assert code==3 and not stdout and json.loads(stderr.splitlines()[-1])['status']=='unavailable'
        assert shell.calls==[] and not shell.store.list_runs(account_id='alice')
