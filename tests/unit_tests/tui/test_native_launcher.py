"""Installed native launcher resolution; no TUI or service is started."""
import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

LAUNCHER = Path(__file__).resolve().parents[3] / 'packages/jiuwenswarm-tui/jiuwenswarm_tui/app.py'
spec = importlib.util.spec_from_file_location('native_tui_launcher_test', LAUNCHER)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class NativeLauncherTests(unittest.TestCase):
    def test_installed_main_package_compiled_assets_are_found_without_import(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'site-packages/jiuwenswarm'
            entry = package / 'channels/tui/frontend/dist/index.js'
            entry.parent.mkdir(parents=True)
            entry.write_text('// frozen build\n', encoding='utf-8')
            package_spec = types.SimpleNamespace(submodule_search_locations=[str(package)])
            with patch.object(launcher.importlib.util, 'find_spec', return_value=package_spec):
                self.assertEqual(launcher._source_dist_entry_path(), entry)

    def test_node_exec_receives_exact_entry_and_arguments(self):
        with patch.object(launcher.shutil, 'which', return_value='/usr/local/bin/node'), \
                patch.object(launcher.subprocess, 'run', return_value=types.SimpleNamespace(returncode=7)) as run:
            self.assertEqual(launcher._run_source_dist(Path('/native/dist/index.js'), ['--help']), 7)
            run.assert_called_once_with(['/usr/local/bin/node', str(Path('/native/dist/index.js')), '--help'], check=False)
