"""Configuration tests use JSON files (also a YAML subset) and no network."""
import json
import tempfile
import unittest
from pathlib import Path

from jiuwenswarm.research.configuration import resolve_configuration
from jiuwenswarm.research.contracts import ResearchError


class ConfigurationTests(unittest.TestCase):
    def test_defaults_are_real_static_route(self):
        config = resolve_configuration()
        self.assertEqual(config["profile"], "codex")
        self.assertEqual(config["timeout_seconds"], 60)

    def test_local_over_global_cli_over_local_and_no_secret_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "global.json", Path(folder) / "local.json"
            first.write_text(json.dumps({"research": {"timeout_seconds": 50, "compiler_model": "configured-a"}, "credentials": {"api_key": "never captured"}}))
            second.write_text(json.dumps({"research": {"timeout_seconds": 30, "verifier_model": "configured-b"}}))
            config = resolve_configuration(first, second, {"timeout_seconds": 20})
            self.assertEqual(config["timeout_seconds"], 20)
            self.assertEqual(config["compiler_model"], "configured-a")
            self.assertEqual(config["verifier_model"], "configured-b")
            self.assertNotIn("credentials", config)
            self.assertNotIn("never captured", repr(config))

    def test_control_bypass_and_invalid_limits_refused(self):
        for override in ({"disable_gate": True}, {"profile": "dynamic"}, {"timeout_seconds": True}, {"timeout_seconds": float("nan")}, {"timeout_seconds": 0}, {"compiler_model": []}):
            with self.subTest(override=override), self.assertRaises(ResearchError):
                resolve_configuration(overrides=override)

    def test_unknown_config_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text('{"research":{"disable_gate":true}}')
            with self.assertRaises(ResearchError):
                resolve_configuration(project_path=path)


if __name__ == "__main__":
    unittest.main()
