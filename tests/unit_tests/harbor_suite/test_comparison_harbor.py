"""Offline real-Harbor configuration/agent fixtures; no model or Docker calls."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import pytest

from benchmarks.harbor_suite import comparison, comparison_harbor as subject
from tests.unit_tests.harbor_suite.test_comparison import assignment
from tests.unit_tests.research.test_host_codex_route import binding


@pytest.mark.usefixtures("benchmark_case_assets")
class BaselineHarborTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.interpreter = Path(sys.executable).resolve()
        self.assignment = assignment()
        self.assignment["output_contracts"]["screening_result"]["schema"] = {"type": "object"}
        self.variant = {"stage": "evaluation", "output_links": {}, "classification": "pass", "findings": {}}
        self.private_config = self.root/"private-payload.json"
        fixture = binding()
        fixture["model"]["max_prompt_bytes"] = 131072
        self.private_config.write_text(json.dumps({"model": fixture["model"], "timeout_s": 30,
            "codex_executable": str(self.interpreter), "working_directory": str(self.root),
            "codex_sha256": "b"*64, "account_fingerprint": "c"*64}))
        self.workspace = self.root/"native-workspace"
        comparison.prepare(self.assignment, self.workspace, private_config=self.private_config,
            control=self.root/"native-private-control", timeout_s=30)
        self.bundle = self.root/"bundle"
        subject.prepare_baseline_task(self.bundle, self.assignment, self.variant,
            quality_port="screening_result", python_image="python:3.12-slim@sha256:"+"1"*64)
        self.wrapper = self.root/"host-wrapper.py"
        self.wrapper.write_text("# offline fixture; never executed\n")
        self.controls = self.root/"implementation"
        self.controls.mkdir()
        (self.controls/"helper.py").write_text("# frozen implementation fixture\n")
        self.host_path = self.root/"host-only.json"
        self.observer = self.root/"observer-private"
        subject.freeze_host_config(self.host_path, task_root=self.bundle/"task", workspace=self.workspace,
            command=[str(self.interpreter), str(self.wrapper)], cwd=self.root,
            public_root=self.workspace/"public", private_control=self.observer,
            control_files=[self.interpreter, self.wrapper, self.private_config],
            control_trees=[self.controls])

    def tearDown(self):
        self.temp.cleanup()

    def write_public(self, *, card="full original card", status="completed"):
        outputs = {"screening_result": {"classification": "pass", "aggregation_rule": "m1_conjunctive_v1",
                   "findings": [], "completeness": {"status": "complete"}}, "card": card}
        report = {"assignment_sha256": comparison.assignment_digest(self.assignment), "status": status,
                  "outputs": outputs if status == "completed" else None, "effective_model": "gpt-6.1-sol",
                  "usage": {"input_tokens": 12, "output_tokens": 7}, "cost_usd": None}
        public = self.workspace/"public"
        (public/"result.json").write_text(json.dumps(report))
        (public/"original.txt").write_text(" \n"+json.dumps(outputs)+"\n")
        if status == "completed":
            (public/"outputs.json").write_text(json.dumps(outputs))
        return report

    def export(self):
        return subject._export_public(subject.load_host_config(self.host_path),
            {"status": "observer_returned", "returncode": 0})

    def test_actual_harbor_models_accept_serial_no_retry_job_and_separate_grader(self):
        from harbor.models.job.config import JobConfig
        from harbor.models.task.config import TaskConfig
        job = JobConfig.model_validate(json.loads((self.bundle/"job-host.json").read_text()))
        self.assertEqual(job.n_attempts, 1)
        self.assertEqual(job.retry.max_retries, 0)
        self.assertEqual(job.n_concurrent_trials, 1)
        config = TaskConfig.model_validate(tomllib.loads((self.bundle/"task/task.toml").read_text()))
        self.assertEqual(config.verifier.environment_mode, "separate")
        instruction = (self.bundle/"task/instruction.md").read_text()
        self.assertNotIn('"classification":"pass"', instruction)
        self.assertNotIn("account_fingerprint", instruction)
        self.assertFalse((self.bundle/"jobs").exists())  # No fabricated job/result.

    def test_probe_performs_no_subprocess_and_changed_control_subtree_is_rejected(self):
        with patch("asyncio.create_subprocess_exec", side_effect=AssertionError("no process")), patch(
                "jiuwenswarm.research.local_model_codex.execute", side_effect=AssertionError("no inference")):
            self.assertFalse(subject.probe_host_config(self.host_path)["effect_performed"])
        (self.controls/"helper.py").write_text("# changed\n")
        with self.assertRaises(ValueError):
            subject.probe_host_config(self.host_path)

    def test_grader_recomputes_original_content_format_and_no_native_auth_claim(self):
        self.write_public()
        public = self.export()
        result = subject.grade(public, self.bundle/"task/tests", self.root/"grade-output")
        self.assertEqual(result["rewards"], {"content_success": 1, "format_success": 1, "public_artifact_integrity": 1})
        self.assertFalse(result["native_provenance"]["independently_verified_by_grader"])
        self.assertEqual(result["binding_requirement"], "not_applicable_to_plain_native_baseline")
        self.assertEqual(comparison._read(self.root/"grade-output/reward.json"), result["rewards"])

    def test_full_port_format_and_common_content_stay_separate(self):
        self.write_public(card=123)
        result = subject.grade(self.export(), self.bundle/"task/tests", self.root/"grade-output")
        self.assertEqual(result["rewards"]["content_success"], 1)
        self.assertEqual(result["rewards"]["format_success"], 0)
        self.assertFalse(result["format"]["ports"]["card"]["valid"])

    @unittest.skipUnless(os.name == "posix", "Actual Linux ownership/mode regression")
    def test_public_grader_files_are_readable_under_private_umask(self):
        previous = os.umask(0o077)
        try:
            self.write_public()
            output = self.root/"public-grade-output"
            subject.grade(self.export(), self.bundle/"task/tests", output)
            comparison._write(self.root/"private-claim.json", {"private": True})
        finally:
            os.umask(previous)
        self.assertEqual(output.stat().st_mode & 0o777, 0o755)
        for name in ("assessment.json", "reward.json"):
            self.assertEqual((output/name).stat().st_mode & 0o777, 0o644)
        self.assertEqual((self.root/"private-claim.json").stat().st_mode & 0o777, 0o600)

    def test_original_artifact_change_invalidates_integrity_and_content_credit(self):
        self.write_public()
        public = self.export()
        (public/"original.txt").write_text('{"swapped":true}')
        result = subject.grade(public, self.bundle/"task/tests", self.root/"grade-output")
        self.assertEqual(result["rewards"]["public_artifact_integrity"], 0)
        self.assertEqual(result["rewards"]["content_success"], 0)

    def test_sanitized_parsed_claim_does_not_override_original_answer(self):
        self.write_public()
        public = self.workspace/"public"
        report = comparison._read(public/"result.json")
        report["outputs"]["screening_result"]["classification"] = "changed"
        (public/"result.json").write_text(json.dumps(report))
        (public/"outputs.json").write_text(json.dumps(report["outputs"]))
        result = subject.grade(self.export(), self.bundle/"task/tests", self.root/"grade-output")
        self.assertEqual(result["rewards"]["public_artifact_integrity"], 0)

    def test_noncompleted_answer_is_not_scored_or_repaired(self):
        self.write_public(status="outcome_unknown")
        result = subject.grade(self.export(), self.bundle/"task/tests", self.root/"grade-output")
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertEqual(result["rewards"]["public_artifact_integrity"], 1)
        self.assertEqual(result["rewards"]["content_success"], 0)
        self.assertEqual(result["rewards"]["format_success"], 0)

    def test_private_files_cannot_be_exported_and_frozen_grader_changes_fail(self):
        (self.workspace/"public/original-receipt.json").write_text("private")
        with self.assertRaises(ValueError):
            self.export()
        (self.bundle/"task/tests/variant.json").write_text("{}")
        with self.assertRaises(ValueError):
            subject.grade(self.workspace/"public", self.bundle/"task/tests", self.root/"out")

    def test_agent_dispatches_one_frozen_argv_and_uploads_only_public_output(self):
        from harbor.models.agent.context import AgentContext
        context = AgentContext()
        agent = subject.NativeCodexBaselineAgent(logs_dir=self.root/"harbor-agent-logs",
            host_config=str(self.host_path), host_config_sha256=subject._pin(self.host_path)["sha256"])
        environment = SimpleNamespace(upload_dir=AsyncMock())
        process = SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0)
        async def fixture_process(*args, **kwargs):
            self.assertEqual(list(args), [str(self.interpreter), str(self.wrapper)])
            self.assertTrue(str(kwargs["stdout"].name).startswith(str(self.observer)))
            self.write_public()
            return process
        async def exercise():
            await agent.setup(environment)
            instruction = (self.bundle/"task/instruction.md").read_text()
            with patch("asyncio.create_subprocess_exec", side_effect=fixture_process) as launch:
                await agent.run(instruction, environment, context)
                with self.assertRaises(ValueError):
                    await agent.run(instruction, environment, context)
                self.assertEqual(launch.call_count, 1)
        asyncio.run(exercise())
        self.assertEqual(environment.upload_dir.await_args.kwargs,
            {"source_dir": self.workspace/"public", "target_dir": "/app/baseline-public"})
        self.assertEqual(context.n_input_tokens, 12)
        self.assertNotIn("c"*64, json.dumps(context.metadata))
        self.assertFalse((self.root/"harbor-agent-logs").exists())


if __name__ == "__main__":
    unittest.main()
