"""Multipart HTTP, canonical extraction and durable input-use boundary."""
import hashlib
import io
import zipfile

import pytest

from .shell_fixture import NativeShell


@pytest.mark.asyncio
async def test_exact_unicode_upload_is_copied_before_delete_and_active_use_conflicts(tmp_path):
    shell=await NativeShell().open(tmp_path)
    try:
        raw='Original café 😀\r\nSecond line\n'.encode()
        response=await shell.client.post('/api/v1/inputs/docs',headers=shell.headers,
            data={'scope_id':'project'},files={'file':('paper.txt',raw,'text/plain')})
        assert response.status_code==200,response.text
        record=response.json();assert record['content_sha256']==hashlib.sha256(raw).hexdigest()
        assert record['stored_path']=='workspace/input/docs/project/paper.txt'
        assert shell.store.read_upload(record['id'],'alice')==raw
        request=await shell.submission(uploads=[record['id']])
        intake=shell.store.read_record(request['intake_ref'],contract_id='qualified-intake')
        exact=shell.store.read_blob(intake['source_refs'][0])
        assert hashlib.sha256(exact).hexdigest()==record['text_sha256']
        # A real nonterminal store row reserves this actual upload. No acceptance is inserted.
        shell.store.create_run('active',account_id='alice',workspace_id='project',submission={})
        shell.store.reserve_uploads('active',[record['id']])
        blocked=await shell.client.delete('/api/v1/inputs/'+record['id'],headers=shell.headers)
        assert blocked.status_code==409 and blocked.json()['category']=='conflict'
        assert shell.store.read_upload(record['id'],'alice')==raw
        shell.store.set_run_state('active','halted',reason='controlled-terminal-fixture')
        deleted=await shell.client.delete('/api/v1/inputs/'+record['id'],headers=shell.headers)
        assert deleted.status_code==200 and deleted.json()['status']=='deleted'
        assert shell.store.read_blob(intake['source_refs'][0])==exact
        assert shell.calls==[]
    finally:await shell.close()


@pytest.mark.asyncio
async def test_foreign_scope_and_unsafe_zip_publish_no_input(tmp_path):
    shell=await NativeShell().open(tmp_path)
    try:
        foreign=await shell.client.post('/api/v1/inputs/docs',headers=shell.headers,
            data={'scope_id':'foreign'},files={'file':('paper.txt',b'foreign')})
        assert foreign.status_code==403
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:archive.writestr('../escape.txt','outside')
        rejected=await shell.client.post('/api/v1/inputs/repo',headers=shell.headers,
            data={'scope_id':'project'},files={'file':('source.zip',data.getvalue())})
        assert rejected.status_code==422
        assert shell.store.list_uploads('alice','project')==[]
        assert shell.store.list_uploads('alice','foreign')==[]
        assert not (tmp_path/'escape.txt').exists() and shell.calls==[]
    finally:await shell.close()
