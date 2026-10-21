"""Local input setup exercises actual composition/storage and HTTP authorization."""
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from jiuwenswarm.research import bootstrap_gateway as gateway
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_workspace import initialize_local_inputs
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes


class LocalWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        ipc = self.root / 'ipc'
        ipc.mkdir(mode=0o700)
        self.env = {
            'JIUWENSWARM_M1_STATE': str(self.root / 'state'),
            'JIUWENSWARM_M1_ACCOUNTS': str(self.root / 'accounts'),
            'JIUWENSWARM_M1_CONFIG': str(self.root / 'missing.yaml'),
            'JIUWENSWARM_M1_ORIGIN': 'http://127.0.0.1:5173',
            'JIUWENSWARM_M1_LOCAL_WORKSPACE': '1',
        }
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env).start()
        os.environ.pop('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS', None)
        patch.object(gateway, 'BOOTSTRAP_HANDOFF', ipc / 'browser-bootstrap.json').start()
        patch.object(gateway, 'SQLiteRunStore', lambda root, **kw:
                     SQLiteRunStore(root, **dict(kw, input_root=self.root / 'inputs'))).start()
        self.attachment = None
        await self.start()

    async def start(self):
        self.channel = SimpleNamespace(set_handshake_auth=lambda callback: None)
        self.attachment = await gateway.attach_native_research(self.channel)
        token = self.attachment.authority.token_path.read_text()
        self.headers = {'Authorization': 'Bearer ' + token}
        self.app = FastAPI()
        mount_research_routes(self.app, self.channel)

    async def asyncTearDown(self):
        if self.attachment is not None:
            self.attachment.close()

    async def test_upload_refresh_restart_delete_and_execution_stays_blocked(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://127.0.0.1:5173', headers=self.headers) as client:
            actor = self.attachment.authority.authenticate(self.headers['Authorization'], 'status')
            defaults = self.attachment.service.client_defaults(actor)
            self.assertTrue(defaults['inputs_ready'])
            self.assertIsNone(defaults['configuration_ref'])
            with self.assertRaises(ResearchError):
                await self.attachment.service.ingest(actor, 'Do research')
            uploaded = await client.post('/api/v1/inputs/docs', data={'scope_id': 'local'}, files={'file': ('paper.md', b'# Local paper\n', 'text/markdown')})
            self.assertEqual(uploaded.status_code, 200, uploaded.text)
            identity = uploaded.json()['id']
            self.assertEqual((await client.get('/api/v1/inputs?scope_id=local')).json()[0]['id'], identity)
            self.assertEqual((await client.post('/api/v1/inputs/docs', data={'scope_id': 'foreign'}, files={'file': ('other.md', b'no')})).status_code, 403)
            self.assertEqual((await client.get('/api/v1/inputs?scope_id=foreign')).status_code, 403)
            self.assertEqual((await client.post('/api/v1/inputs/docs', headers={'Authorization': 'Bearer wrong'}, data={'scope_id': 'local'}, files={'file': ('other.md', b'no')})).status_code, 401)
        self.attachment.close()
        self.attachment = None
        await self.start()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://127.0.0.1:5173', headers=self.headers) as client:
            self.assertEqual((await client.get('/api/v1/inputs?scope_id=local')).json()[0]['id'], identity)
            self.assertEqual((await client.delete('/api/v1/inputs/' + identity)).json()['status'], 'deleted')
            self.assertEqual((await client.get('/api/v1/inputs?scope_id=local')).json()[0]['status'], 'deleted')

    async def test_unsafe_archive_and_nonlocal_initialization_are_refused(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('../escape.py', 'print(1)')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://127.0.0.1:5173', headers=self.headers) as client:
            result = await client.post('/api/v1/inputs/repo', data={'scope_id': 'local'}, files={'file': ('repo.zip', archive.getvalue())})
            self.assertEqual(result.status_code, 422)
            self.assertEqual((await client.get('/api/v1/inputs?scope_id=local')).json(), [])
        with self.assertRaises(ResearchError):
            initialize_local_inputs(self.attachment.store, account_id='owner', origin='http://192.168.1.2:5173')
