"""Native grants bind server-side identities and separate HTTP from browser WS."""
import os
import tempfile
import unittest
from urllib.parse import urlsplit

from jiuwenswarm.research.contracts.types import Principal, ResearchError
from jiuwenswarm.research.shell_auth import SessionAuthority


class ShellAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.origin = 'http://127.0.0.1:5173'
        self.principal = Principal('owner', frozenset({'work'}), frozenset({'submit', 'status', 'settings'}))
        self.authority = SessionAuthority(self.tmp.name, self.origin)
        url = self.authority.initialize(self.principal)
        self.challenge = urlsplit(url).fragment.removeprefix('research_bootstrap=')

    def tearDown(self):
        self.authority.close()
        self.tmp.cleanup()

    def bootstrap(self):
        return self.authority.bootstrap(self.challenge, origin=self.origin, host='127.0.0.1:5173')

    def test_bootstrap_is_one_use_and_exact_origin(self):
        with self.assertRaises(ResearchError):
            self.authority.bootstrap(self.challenge, origin='http://evil.invalid', host='127.0.0.1:5173')
        result = self.bootstrap()
        self.assertIn('HttpOnly', result['set_cookie'])
        self.assertIn('SameSite=Strict', result['set_cookie'])
        self.assertNotEqual(result['token'], result['ws_token'])
        with self.assertRaises(ResearchError):
            self.bootstrap()

    def test_bearer_scope_and_spoofing(self):
        result = self.bootstrap()
        p = self.authority.authenticate('Bearer ' + result['token'], 'submit', 'work')
        self.assertEqual(p.account_id, 'owner')
        for header, operation, workspace in [(None, 'status', 'work'),
                                              ('Bearer ' + result['token'], 'submit', 'foreign'),
                                              ('Bearer ' + result['token'], 'delete', 'work')]:
            with self.assertRaises(ResearchError):
                self.authority.authenticate(header, operation, workspace)

    def test_cookie_is_not_http_bearer_and_revokes_active_ws(self):
        result = self.bootstrap()
        headers = {'host': '127.0.0.1:5173', 'origin': self.origin,
                   'cookie': 'ai4r_ws=' + result['ws_token'], 'x-user-id': 'foreign'}
        self.assertEqual(self.authority.authenticate_ws(headers, 'submit').account_id, 'owner')
        with self.assertRaises(ResearchError):
            self.authority.authenticate('Bearer ' + result['ws_token'], 'submit')
        self.authority.revoke(result['token'])
        with self.assertRaises(ResearchError):
            self.authority.authenticate_ws(headers, 'submit')

    @unittest.skipIf(os.name == 'nt', 'Windows file mode is not Linux custody evidence')
    def test_actual_mode(self):
        self.assertEqual(os.stat(self.authority.token_path).st_mode & 0o777, 0o600)
