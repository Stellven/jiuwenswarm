"""Focused login protocol checks; no real provider credentials or network."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError

class LoginControls(unittest.IsolatedAsyncioTestCase):
    async def test_m1_device_login_and_pending_status(self):
        with tempfile.TemporaryDirectory() as directory:
            async def request(method, params=None):
                if method == 'account/login/start':
                    self.assertEqual(params, {'type': 'chatgptDeviceCode'})
                    return {'type':'chatgptDeviceCode','loginId':'fixture','verificationUrl':'https://auth.openai.com/codex/device','userCode':'ABCD-EFGH'}
                if method == 'account/read': return {'account':None}
                return {}
            transport=SimpleNamespace(listeners=set(),start=AsyncMock(),close=AsyncMock(),request=request)
            service=SubscriptionService(Path(directory),transport=transport)
            with patch.dict(os.environ, {'JIUWENSWARM_M1_PROFILE':'1'}):
                login=await service.login()
                self.assertEqual(login['user_code'],'ABCD-EFGH')
                status=await service.status()
                self.assertEqual(status['auth_url'],login['auth_url'])
                self.assertEqual(status['state'],'signing_in')
                await service.cancel_login('fixture')
                self.assertIsNone((await service.status())['user_code'])

    async def test_device_login_rejects_foreign_url(self):
        with tempfile.TemporaryDirectory() as directory:
            transport=SimpleNamespace(listeners=set(),start=AsyncMock(),close=AsyncMock(),request=AsyncMock(return_value={'type':'chatgptDeviceCode','loginId':'fixture','verificationUrl':'https://evil.invalid','userCode':'ABCD-EFGH'}))
            service=SubscriptionService(Path(directory),transport=transport)
            with patch.dict(os.environ, {'JIUWENSWARM_M1_PROFILE':'1'}), self.assertRaisesRegex(CodexError,'LOGIN_PROTOCOL_ERROR'):
                await service.login()
            transport.close.assert_awaited_once()
