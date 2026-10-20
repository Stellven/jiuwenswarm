"""M1's default native entry cannot dispatch through legacy chat."""
import builtins
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from jiuwenswarm.channels.cli.main import main


class NativeCliEntryTests(unittest.TestCase):
    def test_protected_default_and_chat_use_only_installed_tui(self):
        package = types.ModuleType('jiuwenswarm_tui'); package.__path__ = []
        app = types.ModuleType('jiuwenswarm_tui.app'); app.main = Mock()
        with patch.dict(os.environ, {'JIUWENSWARM_M1_PROFILE': '1'}), \
                patch.dict(sys.modules, {'jiuwenswarm_tui': package, 'jiuwenswarm_tui.app': app}):
            for argv, expected in [(['jiuwenswarm'], ['jiuwenswarm']),
                                   (['jiuwenswarm', 'chat', '--help'], ['jiuwenswarm', '--help'])]:
                with patch.object(sys, 'argv', argv):
                    main(); self.assertEqual(sys.argv, expected)
            self.assertEqual(app.main.call_count, 2)

    def test_missing_installed_tui_is_closed_not_a_legacy_fallback(self):
        original = builtins.__import__
        def importing(name, *args, **kwargs):
            if name.startswith('jiuwenswarm_tui'): raise ImportError('controlled missing package')
            if name.startswith('jiuwenswarm.channels.cli.chat'): raise AssertionError('legacy dispatch attempted')
            return original(name, *args, **kwargs)
        with patch.dict(os.environ, {'JIUWENSWARM_M1_PROFILE': '1'}), \
                patch.object(sys, 'argv', ['jiuwenswarm']), patch('builtins.__import__', side_effect=importing):
            with self.assertRaises(SystemExit) as exited: main()
            self.assertEqual(exited.exception.code, 3)
