"""Offline protocol/budget checks. Never authenticate or invoke a model."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from benchmarks.harbor_suite import native_value as subject


TOOLS = [{"type": "function", "function": {"name": "read_file", "parameters": {
    "type": "object", "properties": {"path": {"type": "string"}},
    "required": ["path"], "additionalProperties": False}}}]


class NativeValueTests(unittest.TestCase):
    def test_controller_timeout_records_actual_terminal_returncode_and_containment_requirement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps({"variant": "native", "task": "Public task",
                "binding": str(root / "existing-binding.json")}))
            output = root / "run"
            child = SimpleNamespace(pid=12345, returncode=-9, wait=Mock(side_effect=[
                subject.subprocess.TimeoutExpired("worker", 345), -9]))
            with patch.object(subject.subprocess, "Popen", return_value=child), \
                    patch.object(subject.subprocess, "run"), patch.object(subject.os, "killpg", create=True):
                self.assertEqual(subject.run(spec_path, output), 2)
            end = json.loads((output / "controller-finished.json").read_text())
            self.assertEqual(end["returncode"], -9)
            self.assertEqual(end["status"], "containment_required")
            self.assertGreaterEqual(end["elapsed_s"], 0)

    def test_controller_records_caps_before_spawn_and_actual_elapsed_after_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps({"variant": "native", "task": "Public task",
                "binding": str(root / "existing-binding.json"), "max_model_calls": 80, "wall_time_s": 600}))
            output = root / "run"
            def spawn(*args, **kwargs):
                start = json.loads((output / "controller-start.json").read_text())
                self.assertEqual(start["assigned_caps"], {"max_model_calls": 80, "max_tool_calls": 30, "wall_time_s": 600})
                self.assertTrue(start["started_at"].endswith("+00:00"))
                return SimpleNamespace(wait=lambda **kw: 0)
            with patch.object(subject.subprocess, "Popen", side_effect=spawn):
                self.assertEqual(subject.run(spec_path, output), 0)
            end = json.loads((output / "controller-finished.json").read_text())
            self.assertEqual(end["returncode"], 0)
            self.assertEqual(end["status"], "completed")
            self.assertGreaterEqual(end["elapsed_s"], 0)

    def test_matched_eighty_call_ceiling_preserves_default_and_rejects_eighty_one(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "spec.json"
            spec = {"variant": "native", "task": "Bounded public task",
                    "binding": str(Path(temp) / "existing-binding.json")}
            path.write_text(json.dumps(spec))
            self.assertEqual(subject.load_spec(path)["max_model_calls"], 12)
            spec["max_model_calls"] = 80
            path.write_text(json.dumps(spec))
            self.assertEqual(subject.load_spec(path)["max_model_calls"], 80)
            spec["max_model_calls"] = 81
            path.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, "max_model_calls"):
                subject.load_spec(path)

    def test_larger_local_ceiling_cannot_override_host_campaign_denial(self):
        with tempfile.TemporaryDirectory() as temp:
            claims = []
            async def host_guard(*args):
                claims.append(1)
                raise RuntimeError("HOST_CAMPAIGN_BUDGET_EXHAUSTED")
            scope = subject.CompletionScope(host_guard,
                {"max_model_calls": 80, "max_tool_calls": 80, "wall_time_s": 600}, temp)
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, "HOST_CAMPAIGN_BUDGET_EXHAUSTED"):
                    asyncio.run(scope.invoke([], []))
            self.assertEqual(len(claims), 1)

    def test_text_bridge_disables_speculative_vision_probe_without_removing_tools(self):
        import yaml
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "state" / "config").mkdir(parents=True)
            template = root / "template.yaml"
            template.write_text("react: {}\nmodes:\n  agent:\n    tools: [bash, skill_tool]\n", encoding="utf-8")
            utils = SimpleNamespace(prepare_workspace=lambda **kwargs: None,
                get_agent_workspace_dir=lambda: root / "state" / "agent" / "workspace",
                get_agent_skills_dir=lambda: root / "state" / "agent" / "workspace" / "skills")
            with patch.dict(sys.modules, {"jiuwenswarm.common.utils": utils}):
                subject.configure({"config_template": str(template), "max_model_calls": 4,
                                   "skill_dirs": []}, root, "gpt-6.1-sol")
            config = yaml.safe_load((root / "state" / "config" / "config.yaml").read_text())
            self.assertIs(config["react"]["enable_read_image_multimodal"], False)
            self.assertEqual(config["modes"]["agent"]["tools"], ["bash", "skill_tool"])

    def test_config_template_resolves_installed_package_outside_benchmark_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "site-packages" / "jiuwenswarm"
            template = package / "resources" / "config.yaml"
            template.parent.mkdir(parents=True)
            template.write_text("models: {}", encoding="utf-8")
            with patch.object(subject.importlib.util, "find_spec", return_value=SimpleNamespace(
                    origin=str(package / "__init__.py"))) as resolve:
                self.assertEqual(subject.config_template({}), template)
                resolve.assert_called_once_with("jiuwenswarm")
            override = root / "custom.yaml"
            override.write_text("models: {}", encoding="utf-8")
            with patch.object(subject.importlib.util, "find_spec", side_effect=AssertionError("unneeded resolution")):
                self.assertEqual(subject.config_template({"config_template": str(override)}), override)

    def test_tool_results_and_multiple_native_tool_selections_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            seen = []
            async def complete(prompt, timeout):
                seen.append(prompt)
                return {"text": json.dumps({"content": "inspect", "tool_calls": [
                    {"name": "read_file", "arguments": {"path": "a"}},
                    {"name": "read_file", "arguments": {"path": "b"}}]})}
            scope = subject.CompletionScope(complete,
                {"max_model_calls": 2, "max_tool_calls": 3, "wall_time_s": 10}, temp)
            messages = [{"role": "tool", "tool_call_id": "original-id", "content": "actual bytes"}]
            value = asyncio.run(scope.invoke(messages, TOOLS))
            self.assertEqual(len(value["tool_calls"]), 2)
            self.assertIn('"tool_call_id": "original-id"', seen[0])
            self.assertEqual(json.loads((Path(temp)/"completion-001-request.json").read_text())["messages"], messages)

    def test_unknown_tool_and_schema_invalid_args_rejected(self):
        for call in ({"name": "shell", "arguments": {}},
                     {"name": "read_file", "arguments": {"path": 5}}):
            with self.assertRaises(Exception):
                subject.parse_completion(json.dumps({"content": "", "tool_calls": [call]}), TOOLS)

    def test_provider_failure_latches_before_hidden_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            effects = []
            async def fail(*args):
                effects.append(1)
                raise RuntimeError("unknown completion outcome")
            scope = subject.CompletionScope(fail,
                {"max_model_calls": 2, "max_tool_calls": 3, "wall_time_s": 10}, temp)
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    asyncio.run(scope.invoke([], TOOLS))
            self.assertEqual(len(effects), 1)

    def test_budget_prevents_second_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            async def complete(*args):
                return {"text": '{"content":"done","tool_calls":[]}'}
            scope = subject.CompletionScope(complete,
                {"max_model_calls": 1, "max_tool_calls": 1, "wall_time_s": 10}, temp)
            asyncio.run(scope.invoke([], []))
            with self.assertRaisesRegex(RuntimeError, "budget"):
                asyncio.run(scope.invoke([], []))
            self.assertEqual(scope.calls, 1)

    def test_native_member_completions_queue_without_provider_contention(self):
        with tempfile.TemporaryDirectory() as temp:
            active = maximum = 0
            async def complete(*args):
                nonlocal active, maximum
                active += 1
                maximum = max(active, maximum)
                await asyncio.sleep(.02)
                active -= 1
                return {"text": '{"content":"done","tool_calls":[]}'}
            scope = subject.CompletionScope(complete,
                {"max_model_calls": 2, "max_tool_calls": 1, "wall_time_s": 10}, temp)
            async def pair():
                return await asyncio.gather(scope.invoke([], []), scope.invoke([], []))
            self.assertEqual(len(asyncio.run(pair())), 2)
            self.assertEqual(maximum, 1)
            self.assertGreaterEqual(json.loads((Path(temp)/"completion-002-request.json").read_text())["queue_wait_s"], 0)

    def test_isolation_removes_live_profile_and_provider_keys(self):
        with patch.dict(os.environ, {"JIUWENSWARM_DATA_DIR": "LIVE", "API_KEY": "secret",
                                    "AI4R_LOCAL_CHAT": "1", "CODEX_HOME": "LIVE"}):
            env = subject.child_environment(Path(tempfile.gettempdir()) / "native-value-env")
        self.assertNotIn("API_KEY", env)
        self.assertNotIn("CODEX_HOME", env)
        self.assertNotIn("AI4R_LOCAL_CHAT", env)
        self.assertEqual(env["JIUWENSWARM_AGENT_SDK"], "harness")
        self.assertNotEqual(env["JIUWENSWARM_DATA_DIR"], "LIVE")

    def test_variant_and_skill_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root/"ordinary-skill"
            skill.mkdir()
            (skill/"SKILL.md").write_text("---\nname: ordinary-skill\ndescription: Test\n---\nInspect files.")
            spec = {"task": "Inspect", "variant": "native", "skill_dirs": [str(skill)],
                    "binding": str(root/"binding.json")}
            path = root/"spec.json"
            path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):
                subject.load_spec(path)
            spec["variant"] = "native-skills"
            path.write_text(json.dumps(spec))
            self.assertEqual(subject.load_spec(path)["mode"], "agent.work.normal")

    def test_file_broker_checks_identity_and_preserves_request(self):
        async def trial(root, effective):
            async def host():
                while not list(root.glob("*.request.json")):
                    await asyncio.sleep(.01)
                request = json.loads(next(root.glob("*.request.json")).read_text())
                subject.write(root/(request["request_id"]+".response.json"), {
                    "schema": "native-value-completion-response:1", "request_id": request["request_id"],
                    "status": "completed", "text": "original", "identity": {"effective": effective},
                    "reasoning_effort": "medium", "usage": {"input_tokens": 3}})
            task = asyncio.create_task(host())
            try:
                return await subject.file_completion(root, "full conversation", 2, model="gpt-6.1-sol")
            finally:
                await task
        for model in ("gpt-6.1-sol", "unexpected-model"):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                if model == "unexpected-model":
                    with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                        asyncio.run(trial(root, model))
                else:
                    self.assertEqual(asyncio.run(trial(root, model))["text"], "original")
                self.assertEqual(len(list(root.glob("*.request.json"))), 1)


if __name__ == "__main__":
    unittest.main()
