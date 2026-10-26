"""Offline fixtures only: never start native Codex or read authentication."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pytest

from benchmarks.harbor_suite import comparison as subject
from jiuwenswarm.research.local_model_codex import pack_bundle
from tests.unit_tests.research.test_host_codex_route import native


def assignment():
    return {"task": "Use only the supplied public values.",
        "inputs": {"brief": {"ref": {"id": "public-brief", "sha256": "a" * 64},
                             "value": {"question": "fixture"}}},
        "output_contracts": {
            "screening_result": {"contract_id": "fixture-result", "schema": {
                "type": "object", "properties": {"answer": {"type": "integer"}},
                "required": ["answer"], "additionalProperties": False}},
            "card": {"contract_id": "fixture-card", "schema": {"type": "string"}}},
        "limits": {"wall_time_s": 600, "max_model_calls": 20}}


def fixture_response(payload, text, *, unknown=False):
    value = native(outcome="outcome_unknown" if unknown else "completed",
                   error="CONTAINMENT_UNCERTAIN" if unknown else None)
    value["account_fingerprint"] = payload["account_fingerprint"]
    value["binary_sha256"] = payload["codex_sha256"]
    if not unknown:
        value["turn_completed"]["turn"]["items"][0]["text"] = text
    for frame in value["wire_frames"]:
        parsed = json.loads(frame["raw"])
        if parsed.get("method") == "turn/start":
            parsed["params"]["input"][0]["text"] = payload["prompt"]
        if parsed.get("method") == "turn/completed":
            parsed["params"] = value["turn_completed"]
        frame["raw"] = json.dumps(parsed) + "\n"
    receipt = pack_bundle(value, value["wire_frames"], full=True,
        observed_frames=len(value["wire_frames"]),
        observed_bytes=sum(len(f["raw"].encode()) for f in value["wire_frames"]))
    return {"outcome": value["outcome"], "http_status": None,
            "response_text": json.dumps(receipt), "provider_request_id": "turn-fixture"}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "operator-pins.json"
        self.control = self.root / "private-control"
        self.config.write_text(json.dumps({
            "model": {"id": "qualified-native", "name": "Native Codex",
                "model_name": "gpt-6.1-sol", "revision": "fixture-qualification",
                "enabled": True, "context_window": 475000, "max_prompt_bytes": 131072,
                "timeout_s": 120, "reasoning_effort": "medium"},
            "timeout_s": 120, "codex_executable": str(self.root / "fixture.exe"),
            "codex_sha256": "b" * 64, "account_fingerprint": "c" * 64,
            "working_directory": str(self.root)}))

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, name="baseline"):
        workspace = self.root / name
        subject.prepare(assignment(), workspace, private_config=self.config, control=self.control)
        return workspace

    def test_prepare_is_offline_and_prompt_is_whitelisted(self):
        with patch("jiuwenswarm.research.local_model_codex.execute", side_effect=AssertionError("no inference")):
            workspace = self.prepare()
        prompt = (workspace / "prompt.txt").read_text()
        self.assertIn("public-brief", prompt)
        self.assertIn("fixture-card", prompt)
        self.assertNotIn("account_fingerprint", prompt)
        self.assertNotIn("max_model_calls", prompt)
        poisoned = assignment()
        poisoned["oracle"] = {"gold": "never supplied"}
        with self.assertRaises(ValueError):
            subject.make_prompt(poisoned)
        with self.assertRaises(ValueError):
            subject.prepare(assignment(), self.root / "too-long", private_config=self.config,
                            control=self.control, timeout_s=121)

    def test_original_v2_receipt_exact_answer_and_public_privacy(self):
        workspace = self.prepare()
        text = ' \n{"screening_result":{"answer":4},"card":"é — original"}\n'
        calls = []
        def execute(payload):
            calls.append(payload)
            return fixture_response(payload, text)
        report = subject.run(workspace, private_config=self.config, execute_fn=execute)
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["status"], "completed")
        self.assertTrue(report["format"]["valid"])
        self.assertEqual(report["usage"]["input_tokens"], 12)
        self.assertEqual(report["usage"]["output_tokens"], 7)
        self.assertEqual(report["effective_model"], "gpt-6.1-sol")
        self.assertEqual(report["reasoning_effort"], "medium")
        self.assertEqual(report["native_terminal"], "completed")
        self.assertEqual((workspace / "public/original.txt").read_bytes(), text.encode())
        receipts = list(self.control.glob("request-*/original-receipt.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text())["schema"], "ai4r-host-codex-response:2")
        self.assertIn("c" * 64, receipts[0].read_text())
        for public in (workspace / "public").iterdir():
            self.assertNotIn("c" * 64, public.read_text())
            self.assertNotIn("wire_frames", public.read_text())
        self.assertFalse((self.control / "active.json").exists())
        self.assertEqual(len(list(self.control.glob("closed-*.json"))), 1)
        with self.assertRaises(FileExistsError):
            subject.run(workspace, private_config=self.config, execute_fn=execute)
        self.assertEqual(len(calls), 1)

    def test_unknown_blocks_other_workspaces_with_shared_control(self):
        first = self.prepare("first")
        report = subject.run(first, private_config=self.config,
            execute_fn=lambda payload: fixture_response(payload, "", unknown=True))
        self.assertEqual(report["status"], "outcome_unknown")
        self.assertTrue((self.control / "active.json").exists())
        second = self.prepare("second")
        with self.assertRaises(FileExistsError), patch(
                "jiuwenswarm.research.local_model_codex.execute", side_effect=AssertionError("no replay")):
            subject.run(second, private_config=self.config)

    def test_lost_observer_exception_keeps_unknown_claim(self):
        workspace = self.prepare()
        def interrupted(_):
            raise RuntimeError("private transport description must not be public")
        report = subject.run(workspace, private_config=self.config, execute_fn=interrupted)
        self.assertEqual(report["status"], "outcome_unknown")
        self.assertTrue((self.control / "active.json").exists())
        self.assertNotIn("private transport", json.dumps(report))

    def test_unvalidated_model_receipt_cannot_publish_success(self):
        workspace = self.prepare()
        def wrong_identity(payload):
            response = fixture_response(payload, '{"screening_result":{"answer":4},"card":"x"}')
            receipt = json.loads(response["response_text"])
            receipt["requested_model"] = "different-model"
            response["response_text"] = json.dumps(receipt)
            return response
        report = subject.run(workspace, private_config=self.config, execute_fn=wrong_identity)
        self.assertEqual(report["status"], "outcome_unknown")
        self.assertIsNone(report["outputs"])
        self.assertTrue((self.control / "active.json").exists())
        self.assertFalse((workspace / "public/original.txt").exists())

    def test_schema_failure_retains_original_without_repair(self):
        workspace = self.prepare()
        report = subject.run(workspace, private_config=self.config,
            execute_fn=lambda payload: fixture_response(payload,
                '{"screening_result":{"answer":"wrong type"},"invented_port":1}'))
        self.assertEqual(report["status"], "completed")
        self.assertFalse(report["format"]["valid"])
        self.assertFalse(report["format"]["ports"]["screening_result"]["valid"])
        self.assertEqual(report["format"]["ports"]["card"]["error"], "missing_port")
        self.assertEqual(report["format"]["extra_ports"], ["invented_port"])
        self.assertEqual(report["outputs"]["screening_result"]["answer"], "wrong type")

    def test_private_receipts_cannot_be_under_harbor_jobs(self):
        with self.assertRaises(ValueError):
            subject.prepare(assignment(), self.root / "workspace", private_config=self.config,
                            control=self.root / "jobs/private")

    def test_frozen_input_and_command_pin_changes_fail_before_effect(self):
        workspace = self.prepare()
        changed = assignment()
        changed["inputs"]["brief"]["value"] = "changed"
        (workspace / "assignment.json").write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            subject.run(workspace, private_config=self.config,
                        execute_fn=lambda _: self.fail("must not execute"))
        self.assertFalse((workspace / "launched.json").exists())
        second = self.prepare("second")
        config = json.loads(self.config.read_text())
        config["codex_sha256"] = "d" * 64
        self.config.write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            subject.run(second, private_config=self.config,
                        execute_fn=lambda _: self.fail("must not execute"))

    def test_no_markdown_repair_and_duplicate_json_rejected(self):
        for index, text in enumerate(('```json\n{"answer":4}\n```', '{"x":1,"x":2}')):
            workspace = self.prepare("invalid" + str(index))
            report = subject.run(workspace, private_config=self.config,
                execute_fn=lambda payload: fixture_response(payload, text))
            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["format"], {"valid": False, "error": "invalid_json"})
            self.assertFalse((workspace / "public/outputs.json").exists())

    def test_external_schema_references_never_fetch_network(self):
        contracts = {"port": {"contract_id": "closed", "schema": {"$ref": "https://invalid.example/schema"}}}
        result = subject.check_format({"port": {}}, contracts)
        self.assertFalse(result["valid"])
        self.assertEqual(result["ports"]["port"]["error"], "schema_validation_unavailable")

    @pytest.mark.usefixtures("benchmark_case_assets")
    def test_compare_uses_shared_content_without_conflating_format_or_binding(self):
        common = assignment()
        output = {"classification": "pass", "aggregation_rule": "m1_conjunctive_v1",
                  "findings": [], "completeness": {"status": "complete"}}
        baseline = {"assignment_sha256": subject.assignment_digest(common), "status": "completed",
                    "outputs": {"screening_result": output, "card": "original"}}
        cc = copy.deepcopy(baseline)
        cc["binding_assessment"] = {"status": "fail"}
        del cc["outputs"]["card"]
        report = subject.compare(common, baseline, cc, quality_port="screening_result",
            variant={"stage": "evaluation", "output_links": {}, "classification": "pass", "findings": {}})
        for arm in report["arms"].values():
            self.assertEqual(arm["content"]["metrics"]["deterministic_content_success"], 1)
        self.assertEqual(report["arms"]["ai4r_cc"]["binding_assessment"], {"status": "fail"})
        self.assertFalse(report["arms"]["ai4r_cc"]["format"]["ports"]["card"]["valid"])
        cc["assignment_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            subject.compare(common, baseline, cc, quality_port="screening_result", variant={})

    def test_verifier_false_accept_false_reject_and_unavailable_are_separate(self):
        rows = [{"artifact_sha256": "1"*64, "valid": False,
                 "native_codex_tool_free": True, "ai4r_verifier": False},
                {"artifact_sha256": "2"*64, "valid": True,
                 "native_codex_tool_free": False, "ai4r_verifier": None}]
        result = subject.verifier_metrics(rows)
        self.assertEqual(result["arms"]["native_codex_tool_free"]["false_accept"], 1)
        self.assertEqual(result["arms"]["native_codex_tool_free"]["false_reject"], 1)
        self.assertEqual(result["arms"]["ai4r_verifier"]["unavailable"], 1)
        self.assertIsNone(result["arms"]["ai4r_verifier"]["false_reject_rate_observed"])
        with self.assertRaises(ValueError):
            subject.verifier_metrics(rows + [rows[0]])


if __name__ == "__main__":
    unittest.main()
