"""Compiler verification cases through real loopback HTTP and configured model.

This is component verification, not SU01 scoring or a downstream benchmark.
Protected challenge injection is labelled and is unavailable to product clients.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import uuid

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intent_compiler.api import create_app
from intent_compiler.client import CompilerClient, ClientError
from intent_compiler.config import Config
from intent_compiler.model import CodexBridge
from intent_compiler.runtime import Runtime
from intent_compiler.store import Store
from record_candidate import capture

CASES = {
    "actionable": {"request": "Investigate ways to reduce the latency of the supplied retrieval baseline while preserving retrieval quality. Keep all work local with no cloud training or new datasets. Return an evidence-grounded research report describing the baseline comparison and limitations.", "expected": "completed"},
    "omissions": {"request": "Study how to reduce latency of a document retrieval baseline without lowering retrieval quality. Return an evidence-grounded report. I have not chosen a method, numeric improvement threshold or hardware.", "expected": "completed"},
    "topic": {"request": "Document retrieval.", "expected": "halted"},
    "contradiction": {"request": "Investigate reducing retrieval latency and return a report. All research must use only a single GPU, and all research must use exactly four GPUs at the same time. Both requirements are mandatory.", "expected": "halted"},
    "unsupported_interpretation": {"request": "Investigate retrieval latency and return an evidence-grounded report. Do not choose a method yet and keep all work local.", "expected": "halted", "injection": "intention"},
    "lost_constraint": {"request": "Investigate retrieval latency and return an evidence-grounded report. No cloud training is permitted and no new datasets may be used.", "expected": "halted", "injection": "requirements"},
}


class ChallengeBridge(CodexBridge):
    invalid_for_product = True

    def __init__(self, config, injection):
        super().__init__(config)
        self.injection = injection

    def invoke(self, **kwargs):
        result = super().invoke(**kwargs)
        if kwargs["role"] != self.injection or result.text is None or result.outcome != "completed":
            return result
        payload = json.loads(result.text)
        if self.injection == "intention":
            statement = payload["interpretation"].get("desired_change") or payload["interpretation"].get("problem")
            if statement:
                statement["text"] = "The user requires a new neural retriever with cloud training and a 50 percent latency improvement."
        else:
            # Preserve IDs, all relationship links and default assumption pointers.
            # This isolates semantic loss from mechanical schema/closure failure.
            for section in ("constraints", "out_of_scope", "mandatory_requirements"):
                for value in payload[section]:
                    if value.get("origin") != "system_default" and any(term in value["text"].lower() for term in ("cloud", "dataset")):
                        value["text"] = "Keep implementation choices unspecified until planning."
            for section in ("acceptance_expectations", "evidence_obligations"):
                for value in payload[section]:
                    if any(term in value["description"].lower() for term in ("cloud", "dataset")):
                        value["description"] = "Document the report's limitations."
        result.settings.update(protected_challenge={"stage": self.injection, "original_model_output_sha256": hashlib.sha256(result.text.encode()).hexdigest(),
                               "injection": "Unsupported attributed interpretation" if self.injection == "intention" else "Remove mandatory user restrictions", "invalid_for_product": True})
        result.text = json.dumps(payload, ensure_ascii=False)
        return result


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_available(client, run_id, case_output, item):
    """Retrieve current available evidence even when a challenge never dispatches."""
    if run_id is None or item.get("export") == "captured":
        return
    try:
        client.export(run_id, case_output / "evidence.zip")
        item["export"] = "captured"
    except (ClientError, RuntimeError, ValueError, OSError) as exc:
        item["export_error"] = {"type": type(exc).__name__, "reason": str(exc), "detail": getattr(exc, "detail", None)}


def campaign(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected = args.cases.split(",") if args.cases else list(CASES)
    if any(name not in CASES for name in selected):
        raise ValueError("Unknown verification case")
    # Freeze expectation/source/configuration before the first model invocation.
    frozen = {"schema_version": "1.0.0", "cases": {name: CASES[name] for name in selected}, "repetitions": 1,
              "expected_source": "compiler-verification.md Cases and evidence; exact labelled inputs fixed before calls",
              "quality_threshold": None, "quality_limitation": "One sample per labelled case; no semantic reliability claim", "automatic_retries": 0}
    write_json(output / "frozen-cases.json", frozen)
    candidate = capture(output / "candidate.json")
    base_config = Config.from_env()
    token = base_config.auth_token or secrets.token_urlsafe(32)
    input_root = output / "visible-input"
    (input_root / "docs").mkdir(parents=True, exist_ok=True)
    (input_root / "docs" / "baseline.md").write_text("Visible local reference: the existing document retrieval baseline has latency and retrieval quality as its relevant metrics. No empirical measurements are supplied.\n", encoding="utf-8")
    base_config = replace(base_config, input_root=input_root, input_directory=input_root / "docs", auth_token=token, model_mode="codex")
    write_json(output / "frozen-configuration.json", base_config.freeze())
    observed = []
    for name in selected:
        case = CASES[name]
        config = replace(base_config, state_dir=output / name / "state", profile_id="compiler-evaluation" if case.get("injection") else "compiler-only")
        config.state_dir.mkdir(parents=True, exist_ok=True)
        store = Store(config.state_dir)
        bridge = ChallengeBridge(config, case["injection"]) if case.get("injection") else CodexBridge(config)
        runtime = Runtime(config, store, bridge)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(config, store, runtime), log_level="warning", host="127.0.0.1", port=port))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        client = CompilerClient("http://127.0.0.1:" + str(port), token, config.account_id, config.workspace_id)
        began = time.monotonic()
        item = {"case": name, "expected": case["expected"], "protected_challenge": bool(case.get("injection")), "candidate": candidate["candidate"]}
        run_id = None
        try:
            readiness = client.readiness()
            write_json(output / name / "readiness.json", readiness)
            if not readiness["ready"]:
                item.update(result="BLOCKED", reason="Real model/enforcement/storage prerequisite unavailable", prerequisites=readiness["prerequisites"])
            else:
                request_id = "verification-" + name + "-" + uuid.uuid4().hex
                status = client.submit(case["request"], client_request_id=request_id, profile_id=config.profile_id, readiness=readiness)
                run_id = status["run_id"]
                # Reconciliation is an ordinary client read, never a resubmission.
                assert client.reconcile(request_id)["run_id"] == run_id
                terminal = client.wait(run_id, timeout=config.node_time_s + 30)
                write_json(output / name / "status.json", terminal)
                actual = terminal["status"]
                item.update(result="PASS" if actual == case["expected"] else "FAIL", actual=actual, run_id=run_id, reasons=terminal["reasons"])
                if actual == "completed":
                    result = client.result(run_id)
                    write_json(output / name / "consumer-result.json", result)
                item["model_calls"] = sum(store.get_json(run_id, r["ref"])["model_calls"] or 0 for r in store.artifacts(run_id) if r["artifact_type"] == "invocation-observation")
                if case.get("injection"):
                    stage = case["injection"]
                    names = {r["id"] for r in store.artifacts(run_id)}
                    verifier_observation = stage + "_verifier_Invocation_Observation.json"
                    if verifier_observation not in names:
                        item.update(result="FAIL", semantic_negative_verified=False, matching_verifier="not_dispatched")
                        raise RuntimeError("Matching challenge stage/verifier was not dispatched; semantic challenge unverified")
                    settings = store.get_json(run_id, stage + "_Adapter_Settings.json")
                    assessment_name = "Intent_Assessment.json" if stage == "intention" else "Requirements_Assessment.json"
                    mechanical = store.get_json(run_id, stage.title() + "_Checks.json")
                    assessment = store.get_json(run_id, assessment_name)
                    item["challenge_injected"] = bool(settings.get("protected_challenge"))
                    item["mechanical_checks_passed"] = all(r["outcome"] == "PASS" for r in mechanical["results"])
                    item["semantic_verdict"] = assessment["verdict"]
                    item["semantic_negative_verified"] = item["challenge_injected"] and item["mechanical_checks_passed"] and assessment["verdict"] in ("FAIL", "INCONCLUSIVE", "NEEDS_HUMAN")
                    if not item["semantic_negative_verified"]:
                        item["result"] = "FAIL"
                        item["reason"] = "Injected challenge requires mechanically valid candidate and actual non-advancing matching semantic verifier"
                client.export(run_id, output / name / "evidence.zip")
                item["export"] = "captured"
        except (ClientError, AssertionError, RuntimeError, ValueError, OSError) as exc:
            item.update(result="FAIL", reason=str(exc), detail=getattr(exc, "detail", None))
        finally:
            export_available(client, run_id, output / name, item)
            item["elapsed_s"] = time.monotonic() - began
            observed.append(item)
            write_json(output / "outcomes.json", {"candidate": candidate["candidate"], "cases": observed,
                       "false_acceptances": sum(x.get("actual") == "completed" and x["expected"] == "halted" for x in observed),
                       "false_refusals": sum(x.get("actual") == "halted" and x["expected"] == "completed" for x in observed),
                       "limitations": ["One repetition; uncontrolled provider variability", "Billing and served model identity may be unavailable", "Protected injected challenge outputs are invalid for product/admission"]})
            print(json.dumps(item, ensure_ascii=False), flush=True)
            client.close()
            server.should_exit = True
            thread.join(10)
            sock.close()
        if item["result"] == "BLOCKED":
            break
    return 0 if len(observed) == len(selected) and all(x["result"] == "PASS" for x in observed) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", default="", help="Comma separated predeclared verification cases, default all")
    sys.exit(campaign(parser.parse_args()))
