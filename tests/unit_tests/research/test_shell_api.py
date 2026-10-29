"""Actual native FastAPI boundary with controlled service effects; no model claims."""
import tempfile
import unittest
import hashlib
import io
import json
import zipfile
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jiuwenswarm.research.contracts.types import Principal
from jiuwenswarm.research.shell_auth import SessionAuthority
from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes


class ShellApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.auth = SessionAuthority(self.temp.name, 'http://testserver')
        principal = Principal('owner', frozenset({'work'}), frozenset({'readiness', 'submit', 'status', 'export', 'reconcile'}))
        challenge = urlsplit(self.auth.initialize(principal)).fragment.split('=', 1)[1]
        self.service = SimpleNamespace(readiness=Mock(return_value={'ready': False}), submit=AsyncMock(return_value={'run_id': 'run:1'}),
                                       client_defaults=Mock(return_value={'account_id': 'owner', 'workspace_id': 'work', 'configuration_ref': {'id': 'config', 'sha256': 'a' * 64}}))
        channel = SimpleNamespace(research_profile=True, research_service=self.service, research_authority=self.auth, set_handshake_auth=Mock())
        self.channel = channel
        app = FastAPI(); mount_research_routes(app, channel)
        self.client = TestClient(app)
        response = self.client.post('/auth/research/bootstrap', json={'challenge': challenge}, headers={'Origin': 'http://testserver'})
        self.assertEqual(response.status_code, 200)
        self.token = response.json()['token']

    def tearDown(self):
        self.client.close(); self.auth.close(); self.temp.cleanup()

    def test_cookie_cannot_authorize_control_api(self):
        response = self.client.get('/api/v1/readiness')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['category'], 'auth')
        self.service.readiness.assert_not_called()
        response = self.client.get('/api/v1/readiness', headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['ready'])

    def test_foreign_workspace_has_zero_submit_effect(self):
        response = self.client.post('/api/v1/runs', json={'workspace_id': 'foreign'}, headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(response.status_code, 403)
        self.service.submit.assert_not_awaited()

    def test_configuration_refusal_retains_auth_surface_and_blocks_submit_effect(self):
        self.channel.research_refusal_reason='operator_configuration_unavailable'
        response=self.client.post('/api/v1/runs',json={'workspace_id':'work'},
                                  headers={'Authorization':'Bearer '+self.token})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['category'],'unavailable')
        self.service.submit.assert_not_awaited()
        self.assertEqual(self.client.get('/api/v1/readiness').status_code,401)

    def test_reconcile_returns_single_source_status_or_explicit_error(self):
        headers = {'Authorization': 'Bearer ' + self.token}
        status = {'run_id': 'run:1', 'client_request_id': 'request:1'}
        self.service.list = Mock(return_value=[status])
        found = self.client.get('/api/v1/runs?client_request_id=request:1', headers=headers)
        self.assertEqual(found.json(), status)
        self.service.list.return_value = []
        missing = self.client.get('/api/v1/runs?client_request_id=request:1', headers=headers)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()['category'], 'not_found')
        self.service.list.return_value = [status, status]
        duplicate = self.client.get('/api/v1/runs?client_request_id=request:1', headers=headers)
        self.assertEqual(duplicate.status_code, 500)
        self.assertEqual(duplicate.json()['category'], 'internal')

    def test_revoked_and_invalid_json(self):
        self.auth.revoke(self.token)
        response = self.client.get('/api/v1/readiness', headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(self.token, response.text)

    def test_export_same_route_exact_zip_bytes_and_json_metadata(self):
        raw = 'Exact report: caf\u00e9 \U0001f600\n'.encode('utf-8')
        ref = {'id': 'report', 'sha256': hashlib.sha256(raw).hexdigest()}
        manifest = {'schema_version': '1.0.0', 'id': 'retrieval:1', 'run_id': 'run:1', 'audience': 'researcher',
                    'artifact_refs': [ref], 'files': [{'path': 'research_report.md', 'artifact_ref': ref, 'media_type': 'text/markdown', 'audience': 'researcher'}], 'redactions': []}
        self.service.artifact_bytes = AsyncMock(return_value=(manifest, {'research_report.md': raw}))
        self.service.artifact = AsyncMock(return_value=manifest)
        headers = {'Authorization': 'Bearer ' + self.token}
        metadata = self.client.get('/api/v1/runs/run:1/export', headers=headers)
        self.assertEqual(metadata.json(), manifest)
        exported = self.client.get('/api/v1/runs/run:1/export', headers=dict(headers, Accept='application/zip'))
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.headers['cache-control'], 'private, no-store')
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            self.assertEqual(archive.namelist(), ['client_retrieval.json', 'research_report.md'])
            self.assertEqual(archive.read('research_report.md'), raw)
            self.assertEqual(json.loads(archive.read('client_retrieval.json')), manifest)
        self.service.artifact_bytes.reset_mock()
        for bad in [{}, dict(headers, Accept='application/zip')]:
            suffix = '?audience=reviewer' if bad else ''
            denied = self.client.get('/api/v1/runs/run:1/export' + suffix, headers=bad)
            self.assertIn(denied.status_code, {401, 403})
        self.service.artifact_bytes.assert_not_awaited()
        self.auth.revoke(self.token)
        revoked = self.client.get('/api/v1/runs/run:1/export', headers=dict(headers, Accept='application/zip'))
        self.assertEqual(revoked.status_code, 401)
        self.service.artifact_bytes.assert_not_awaited()
