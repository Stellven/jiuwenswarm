"""Run frozen M1-INTENT/V07 cases against the existing application-owned Codex profile.

No login, credential copying, retry or configuration change is performed.
Host-authored deficient fixtures are explicitly separate from provider output.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from jiuwenswarm.ai4research.intent.bridge import CodexBridge
from jiuwenswarm.ai4research.intent.gate import semantic_gate, tier1
from jiuwenswarm.ai4research.intent.models import FrozenPolicy, GateDecision, InvocationEvidence, sha256_text
from jiuwenswarm.ai4research.intent.prompts import compiler_prompt, verifier_prompt
from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore, encode_json
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService

FIXTURES = Path(__file__).with_name("fixtures") / "live_intent_campaign_v1.json"


def write_json(path: Path, value: object):
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def preserve_prompt(path: Path, content: str):
    """Retain exact diagnostics; never rewrite host-owned required evidence."""
    data = content.encode("utf-8")
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError("PROMPT_EVIDENCE_MISMATCH")
    else:
        with path.open("xb") as output:
            output.write(data)


def expected_outcome(case: dict, result: dict) -> tuple[str, list[str]]:
    if result.get("verdict") == "ENVIRONMENT_BLOCKED":
        return "BLOCKED", ["External model environment did not complete required review."]
    reasons = []
    if result.get("state") != case["expected_state"]:
        reasons.append("State differs from frozen expectation.")
    if result.get("verdict") not in case["expected_verdicts"]:
        reasons.append("Verdict differs from frozen expectation.")
    if case["expected_state"] == "ACCEPTED":
        if not result.get("accepted_reference"):
            reasons.append("No durably accepted reference.")
        intent = result.get("accepted_intent") or {}
        for field, needles in case.get("required_quotes", {}).items():
            quotes = [item["source_quote"] for item in intent.get(field, [])]
            for needle in needles:
                if not any(needle in quote for quote in quotes):
                    reasons.append(f"Required {field} source phrase absent: {needle}")
    elif result.get("accepted_reference"):
        reasons.append("Blocking case exposed an accepted reference.")
    return ("FAIL", reasons) if reasons else ("PASS", [])


async def deficient_review(case: dict, store: IntentStore, bridge: CodexBridge, policy: FrozenPolicy) -> dict:
    """One real verifier call; compiler-shaped evidence is an identified host fixture."""
    run_id = uuid.uuid4().hex
    original = case["input"]
    candidate = dict(case["candidate"], run_id=run_id, input_sha256=sha256_text(original))
    raw_candidate = encode_json(candidate)
    # This is not a claimed model invocation. It is the deterministic test
    # harness input to the protected semantic gate, recorded as such below.
    fixture_observation = InvocationEvidence(
        invocation_id="host-fixture-" + case["id"], role="compiler", run_id=run_id,
        conversation_id="host-fixture-no-provider-conversation-" + run_id,
        model=None, prompt_sha256=sha256_text(compiler_prompt(original, run_id)),
        status="completed", elapsed_seconds=0.0, raw_output=raw_candidate,
        tools=[], effects=[], usage=None,
    )
    lock = store.claim_runtime()
    try:
        store.create(run_id, original, "live-campaign", store.profile_id, str(REPO), policy.model_dump(mode="json"),
                     {"agreement": "M1-IF-INTENT@r1", "campaign_fixture": case["id"], "producer": "host_fixture"})
        store.write(run_id, "intervention.json", encode_json({
            "producer": "host_fixture", "not_provider_output": True, "compiler_model_calls": 0,
            "fixture_id": case["id"], "fixture_sha256": hashlib.sha256(FIXTURES.read_bytes()).hexdigest(),
            "input_sha256": sha256_text(original), "candidate_sha256": sha256_text(raw_candidate),
            "defect": case["defect"], "synthetic_observation_id": fixture_observation.invocation_id,
            "usage": None,
        }))
        store.write(run_id, "compiler.fixture.json", encode_json(fixture_observation.model_dump(mode="json")))
        store.write(run_id, "candidate.raw.json", raw_candidate)
        parsed, preliminary = tier1(raw_candidate, original, run_id, fixture_observation, policy)
        store.write(run_id, "tier1.json", encode_json(preliminary.model_dump(mode="json")))
        decision = preliminary
        if parsed is not None and preliminary.verdict == "PASS":
            store.state(run_id, "VERIFYING")
            prompt = verifier_prompt(original, raw_candidate, run_id)
            store.write(run_id, "verifier.prompt.txt", prompt)
            started = time.monotonic()
            observed = await bridge.invoke("verifier", prompt, run_id, policy)
            observed = observed.model_copy(update={"elapsed_seconds": max(observed.elapsed_seconds, time.monotonic() - started)})
            store.write(run_id, "verifier.json", encode_json(observed.model_dump(mode="json")))
            store.write(run_id, "assessment.raw.json", observed.raw_output)
            decision = semantic_gate(observed.raw_output, original, raw_candidate, run_id,
                                     fixture_observation, observed, policy)
        store.write(run_id, "computed-gate.json", encode_json(decision.model_dump(mode="json")))
        # A fixture review never publishes a production accepted reference.
        # Preserve the actual computed result when the defect escapes detection.
        completion = decision if not decision.accepted else GateDecision(
            verdict="FAIL", tier1=True, tier2=False, reasons=["CAMPAIGN_DEFECT_ADVANCED: computed gate accepted host fixture"], warnings=[])
        store.complete(run_id, completion)
        return {"run_id": run_id, "state": "HALTED" if not decision.accepted else "WOULD_ADVANCE",
                "verdict": decision.verdict, "reasons": decision.reasons,
                "accepted_reference": None, "producer": "host_fixture", "actual_compiler_calls": 0,
                "synthetic_evidence": "compiler.fixture.json", "durable": True}
    finally:
        lock.close()


async def campaign(args) -> dict:
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture_bytes = FIXTURES.read_bytes()
    fixtures = json.loads(fixture_bytes)
    (output / "frozen-fixtures.json").write_bytes(fixture_bytes)
    policy = FrozenPolicy()
    manifest = {
        "interface": "M1-IF-INTENT@r1", "fixtures_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python_executable": sys.executable, "python_version": platform.python_version(),
        "platform": platform.platform(), "subscription_root": str(args.subscription_root.resolve()),
        "command": [sys.executable, str(Path(__file__).resolve()), "--subscription-root", str(args.subscription_root.resolve()),
                    "--output-dir", str(output)],
        "policy": policy.model_dump(mode="json"), "packages": {name: version(name) for name in ("pydantic", "openai-codex-cli-bin")},
        "source_sha256": {name: hashlib.sha256((REPO / "jiuwenswarm/ai4research/intent" / name).read_bytes()).hexdigest()
                          for name in ("models.py", "gate.py", "prompts.py", "bridge.py", "service.py", "store.py")},
        "native_source_sha256": {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in (REPO / "jiuwenswarm/server/runtime/codex_subscription/service.py",
                                              REPO / "jiuwenswarm/server/runtime/codex_subscription/transport.py")},
        "normal_expected": "N01-N05 ACCEPTED; N06 material missing dataset INCONCLUSIVE/HALTED",
        "deficient_expected": "D01-D03 host-authored deficient fixtures HALTED, FAIL or INCONCLUSIVE; one real verifier each",
        "measurement_scope": {
            "compiler_policy": "Independent frozen compiler/verifier bounds: 60 seconds per call, 120 seconds total, 2 calls, no configured token cap.",
            "input_research_limits": "User-stated research budgets are captured only as downstream intent constraints; no research execution or downstream budget compliance is demonstrated.",
            "example_N02": "30 seconds, 2 model calls and 1000 tokens in N02 describe requested downstream research bounds, not the compiler campaign's operational limits.",
        },
        "limitations": ["Nine frozen cases do not establish population reliability or performance.",
                        "Deficient candidates are host fixtures; synthetic compiler evidence has no model call or usage."],
    }
    write_json(output / "manifest.json", manifest)
    subscription = SubscriptionService(args.subscription_root)
    results = []
    try:
        try:
            status = await asyncio.wait_for(subscription.status(), 10)
        except Exception as error:
            code = str(error) if str(error) in {"PROFILE_IN_USE", "RUNTIME_VERSION_MISMATCH", "PROFILE_CONFIG_CONFLICT"} else type(error).__name__
            status = {"state": "BLOCKED", "error": code}
        write_json(output / "managed-status.json", status)
        if status.get("state") != "ready":
            for case in fixtures["normal_cases"] + fixtures["deficient_cases"]:
                results.append({"case_id": case["id"], "result": "BLOCKED", "reasons": ["Managed profile prerequisite: " + status.get("state", "unknown")]})
        else:
            bridge = CodexBridge(subscription)
            store = IntentStore(output / "state")
            service = IntentService(store, bridge, policy)
            for case in fixtures["normal_cases"]:
                print(json.dumps({"case_id": case["id"], "event": "starting"}), flush=True)
                result = await service.execute(case["input"], "live-campaign", store.profile_id, str(REPO))
                run_dir = store.artifact_root / result["run_id"]
                preserve_prompt(run_dir / "compiler.prompt.txt", compiler_prompt(case["input"], result["run_id"]))
                if (run_dir / "verifier.json").exists():
                    raw = (run_dir / "candidate.raw.json").read_text(encoding="utf-8")
                    preserve_prompt(run_dir / "verifier.prompt.txt", verifier_prompt(case["input"], raw, result["run_id"]))
                outcome, reasons = expected_outcome(case, result)
                results.append({"case_id": case["id"], "result": outcome, "expectation_reasons": reasons, "observed": result})
                print(json.dumps({"case_id": case["id"], "result": outcome, "verdict": result["verdict"]}), flush=True)
            for case in fixtures["deficient_cases"]:
                print(json.dumps({"case_id": case["id"], "event": "starting", "producer": "host_fixture"}), flush=True)
                result = await deficient_review(case, store, bridge, policy)
                outcome, reasons = expected_outcome(case, result)
                results.append({"case_id": case["id"], "result": outcome, "expectation_reasons": reasons, "observed": result})
                print(json.dumps({"case_id": case["id"], "result": outcome, "verdict": result["verdict"]}), flush=True)
    finally:
        await subscription.transport.close()
    report = {"result": "FAIL" if any(item["result"] == "FAIL" for item in results) else
              "BLOCKED" if any(item["result"] == "BLOCKED" for item in results) else "PASS",
              "cases": results, "manifest": "manifest.json", "status": "managed-status.json",
              "actual_usage": [], "output_dir": str(output), "limitations": manifest["limitations"]}
    for path in (output / "state/runs").glob("*/verifier.json"):
        invocation = json.loads(path.read_text(encoding="utf-8"))
        report["actual_usage"].append({key: invocation[key] for key in
                                      ("invocation_id", "conversation_id", "run_id", "role", "route", "model", "status", "elapsed_seconds", "usage")})
    for path in (output / "state/runs").glob("*/compiler.json"):
        invocation = json.loads(path.read_text(encoding="utf-8"))
        report["actual_usage"].append({key: invocation[key] for key in
                                      ("invocation_id", "conversation_id", "run_id", "role", "route", "model", "status", "elapsed_seconds", "usage")})
    write_json(output / "campaign-result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription-root", type=Path, required=True, help="Existing native application-owned profile; no credential copying")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; retained campaign history is never overwritten")
    args = parser.parse_args()
    report = asyncio.run(campaign(args))
    print(json.dumps({"result": report["result"], "report": str(args.output_dir / "campaign-result.json")}), flush=True)
    return 0 if report["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
