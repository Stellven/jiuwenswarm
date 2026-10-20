import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from jiuwenswarm.gateway.channel_manager.web.web_channel_app import _reject_unauthorized_handshake


class NativeAuthBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_native_hook_is_not_authentication(self):
        socket = SimpleNamespace(client=None, url=SimpleNamespace(path='/ws', query=''), headers={},
                                 send_denial_response=AsyncMock())
        channel = SimpleNamespace(research_profile=True, authenticate_handshake=AsyncMock(return_value=None))
        denied, actor = await _reject_unauthorized_handshake(channel, socket)
        self.assertTrue(denied)
        self.assertIsNone(actor)
        socket.send_denial_response.assert_awaited_once()

    async def test_ordinary_native_profile_keeps_existing_optional_hook(self):
        socket = SimpleNamespace(client=None, url=SimpleNamespace(path='/ws', query=''), headers={},
                                 send_denial_response=AsyncMock())
        channel = SimpleNamespace(research_profile=False, authenticate_handshake=AsyncMock(return_value=None))
        self.assertEqual(await _reject_unauthorized_handshake(channel, socket), (False, None))
