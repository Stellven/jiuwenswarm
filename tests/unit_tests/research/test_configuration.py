import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jiuwenswarm.research.configuration import PreferenceError, resolve_preferences


class PreferenceTests(unittest.TestCase):
    def test_precedence_frozen_values_and_no_protected_injection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            account = {'timezone': 'UTC', 'workspace_input': 'workspace/input', 'single_gpu': True}
            result = resolve_preferences(account, {'timezone': 'America/Toronto'}, {'timezone': 'Europe/London'}, root=root)
            self.assertEqual(result['timezone'], 'Europe/London')
            account['single_gpu'] = False
            self.assertTrue(result['single_gpu'])
            for value in [{'cc': {}}, {'codex': {}}, {'workspace_input': '../escape'},
                          {'ingestion_extensions': ['.exe']}, {'single_gpu': 'yes'}, {'timezone': 'not/a/timezone'}]:
                with self.assertRaises(PreferenceError):
                    resolve_preferences(value, {}, {}, root=root)
