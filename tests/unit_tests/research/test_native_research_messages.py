import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.shell_auth import SessionAuthority
from jiuwenswarm.gateway.channel_manager.web.research_http import native_research_message


class NativeResearchMessages(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_only_captures_and_spoofed_actor_does_not_bind(self):
        with tempfile.TemporaryDirectory() as directory:
            authority = SessionAuthority(directory, 'http://private:5173')
            authority.initialize(Principal('owner', frozenset({'work'}), frozenset({'submit', 'status', 'settings'})))
            token = authority.token_path.read_text()
            socket = SimpleNamespace(request_headers={'Host': 'private:5173', 'Authorization': 'Bearer ' + token, 'X-User-Id': 'foreign'})
            service = SimpleNamespace(ingest=AsyncMock(return_value={'id': 'intake', 'sha256': 'a' * 64}))
            channel = SimpleNamespace(research_authority=authority, research_service=service)
            handled, payload = await native_research_message(channel, socket, 'chat.send', {'content': 'bounded question', 'workspace_id': 'work', 'user_id': 'foreign'})
            self.assertTrue(handled); self.assertTrue(payload['qualified'])
            self.assertEqual(service.ingest.await_args.args[0].account_id, 'owner')
            for method in ['chat.resume', 'chat.user_answer', 'chat.interrupt', 'session.message.continue_queued',
                           'project.git.commit', 'team.mq.publish', 'rsi.training.start', 'unknown.mutate', 'swarmflow.resume']:
                with self.subTest(method=method), self.assertRaises(ResearchError):
                    await native_research_message(channel, socket, method, {})
            authority.revoke(token)
            with self.assertRaises(ResearchError):
                await native_research_message(channel, socket, 'config.get', {})
            authority.close()

    async def test_refusal_mode_authenticates_but_cannot_start_research_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            authority = SessionAuthority(directory, 'http://private:5173')
            authority.initialize(Principal('owner', frozenset({'work'}), frozenset({'submit','status','settings'})))
            token=authority.token_path.read_text()
            ws=SimpleNamespace(request_headers={'Host':'private:5173','Authorization':'Bearer '+token})
            service=SimpleNamespace(ingest=AsyncMock())
            channel=SimpleNamespace(research_authority=authority,research_service=service,
                                    research_refusal_reason='operator_configuration_unavailable')
            for method in ('chat.send','models.validate','config.set','session.create'):
                with self.subTest(method=method),self.assertRaises(ResearchError) as observed:
                    await native_research_message(channel,ws,method,{'content':'attempt work'})
                self.assertEqual(observed.exception.code,'unavailable')
            service.ingest.assert_not_awaited()
            for method in ('codex.auth.status', 'codex.auth.login', 'codex.auth.cancel', 'codex.auth.logout', 'codex.models.list'):
                handled, _ = await native_research_message(channel, ws, method, {})
                self.assertFalse(handled)
            authority.revoke(token)
            with self.assertRaises(ResearchError) as observed:
                await native_research_message(channel,ws,'config.get',{})
            self.assertEqual(observed.exception.code,'auth')
            authority.close()

    async def test_account_control_does_not_require_execution_backend(self):
        import asyncio
        import os
        from unittest.mock import patch
        from jiuwenswarm.server.front.router import MethodRouter
        from jiuwenswarm.common.schema.agent import AgentRequest, AgentResponse
        from jiuwenswarm.common.schema.message import ReqMethod
        admission = SimpleNamespace(dispatch=AsyncMock())
        router = MethodRouter(SimpleNamespace(), admission)
        ws = SimpleNamespace(send=AsyncMock())
        request = AgentRequest(request_id='auth-only', channel_id='web', req_method=ReqMethod('codex.auth.status'))
        response = AgentResponse(request_id='auth-only', channel_id='web', ok=True, payload={'state': 'signed_out'})
        with patch.dict(os.environ, {'JIUWENSWARM_M1_PROFILE': '1', 'JIUWENSWARM_AGENT_SDK': 'codex_subscription'}), \
                patch('jiuwenswarm.server.runtime.gateway_adapter.codex_adapter.CodexAccountAdapter.handle', AsyncMock(return_value=response)) as handle:
            await router.dispatch(ws, request, asyncio.Lock())
        handle.assert_awaited_once_with(request)
        admission.dispatch.assert_not_awaited()
        ws.send.assert_awaited_once()
