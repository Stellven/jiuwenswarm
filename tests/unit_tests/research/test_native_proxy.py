import unittest
from types import SimpleNamespace
from unittest.mock import patch
from jiuwenswarm.channels.web.app_web import _SpaStaticHandler


class NativeProxyTests(unittest.TestCase):
    def test_protected_exact_origin_and_host(self):
        with patch.dict('os.environ', {'JIUWENSWARM_M1_PROFILE': '1', 'JIUWENSWARM_M1_ORIGIN': 'http://private:5173'}):
            handler = SimpleNamespace(headers={'Origin': 'http://private:5173'})
            self.assertTrue(_SpaStaticHandler._research_origin_allowed(handler, 'private:5173'))
            self.assertFalse(_SpaStaticHandler._research_origin_allowed(handler, 'foreign:5173'))
            handler.headers = {'Origin': 'http://foreign.invalid'}
            self.assertFalse(_SpaStaticHandler._research_origin_allowed(handler, 'private:5173'))
            handler.headers = {}
            self.assertTrue(_SpaStaticHandler._research_origin_allowed(handler, 'private:5173'))

    def test_no_change_outside_research_profile(self):
        with patch.dict('os.environ', {'JIUWENSWARM_M1_PROFILE': '0'}):
            self.assertTrue(_SpaStaticHandler._research_origin_allowed(SimpleNamespace(headers={}), 'legacy:5173'))
