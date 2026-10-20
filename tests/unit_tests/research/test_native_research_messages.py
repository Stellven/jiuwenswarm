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

    async def test_refusal_mode_authenticates_but_cannot_start_any_native_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            authority = SessionAuthority(directory, 'http://private:5173')
            authority.initialize(Principal('owner', frozenset({'work'}), frozenset({'submit','status','settings'})))
            token=authority.token_path.read_text()
            ws=SimpleNamespace(request_headers={'Host':'private:5173','Authorization':'Bearer '+token})
            service=SimpleNamespace(ingest=AsyncMock())
            channel=SimpleNamespace(research_authority=authority,research_service=service,
                                    research_refusal_reason='operator_configuration_unavailable')
            for method in ('chat.send','codex.auth.login','models.validate','config.set','session.create'):
                with self.subTest(method=method),self.assertRaises(ResearchError) as observed:
                    await native_research_message(channel,ws,method,{'content':'attempt work'})
                self.assertEqual(observed.exception.code,'unavailable')
            service.ingest.assert_not_awaited()
            authority.revoke(token)
            with self.assertRaises(ResearchError) as observed:
                await native_research_message(channel,ws,'config.get',{})
            self.assertEqual(observed.exception.code,'auth')
            authority.close()
