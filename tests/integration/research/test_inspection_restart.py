"""Actual durable status/export remains byte exact across service restart."""
import hashlib
import io
import json
import zipfile

import pytest

from jiuwenswarm.research.contracts import ResearchError
from .shell_fixture import NativeShell


@pytest.mark.asyncio
async def test_restart_inspection_exports_original_failure_evidence_without_replay(tmp_path):
    effects=[]
    async def fail(run_id,protected):
        effects.append(run_id)
        raise ResearchError('controlled_compiler_failure')
    shell=await NativeShell().open(tmp_path,compiler=fail)
    try:
        request=await shell.submission()
        response=await shell.client.post('/api/v1/runs',json=request,headers=shell.headers)
        assert response.status_code==200
        run_id=response.json()['run_id'];await shell.settle();token=shell.token
        response=await shell.client.get('/api/v1/runs/'+run_id+'/export',headers=dict(shell.headers,Accept='application/zip'))
        assert response.status_code==200,response.text
        original=response.content
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            manifest=json.loads(archive.read('client_retrieval.json'))
            assert manifest['files']
            for file in manifest['files']:
                assert hashlib.sha256(archive.read(file['path'])).hexdigest()==file['artifact_ref']['sha256']
        await shell.close();shell=None
        shell=await NativeShell().open(tmp_path,recover=True,initialize=False);shell.token=token
        before=list(shell.store.iter_records())
        status=await shell.client.get('/api/v1/runs/'+run_id,headers=shell.headers)
        assert status.status_code==200 and status.json()['status']=='halted'
        response=await shell.client.get('/api/v1/runs/'+run_id+'/export',headers=dict(shell.headers,Accept='application/zip'))
        assert response.status_code==200 and response.content==original
        assert response.headers['cache-control']=='private, no-store'
        assert list(shell.store.iter_records())==before and effects==[run_id] and shell.calls==[]
    finally:
        if shell is not None:await shell.close()
