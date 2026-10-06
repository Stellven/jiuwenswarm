"""Fixed development verifier measurements; never a CC or release path.

The CLI has no mock fallback and never changes labels or invokes a compiler.
Independent subjects are not claimed to be outputs of a production compiler.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import time
import uuid

from .common import GovernanceError, canonical_json, hash_json, sha256_bytes, utc_now
from .bridge import _safe_path
from .configuration import resolve_configuration
from .intent.models import validate_intent
from .runner import TrialRunner
from .service import _private_descriptor, _validate_custody, bootstrap
from .state import RunStore
from .verification.gate import aggregate

CORPUS_SHA256 = "a312d6e3ef3de2ef1b4f35d6d65c0c581e15fb180a557700c18b86c3d21ba193"
CASE_IDS = ("faithful", "omission-visible", "omitted-constraint", "unsupported-addition",
            "scope-drift", "conflict", "ambiguity", "evidence-mismatch", "candidate-injection")
SCOPE = "Development-only independent-subject verifier characterization; no production release or connected pipeline acceptance."


def load_corpus(path):
    with _safe_path(path).open("rb") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072 or sha256_bytes(raw) != CORPUS_SHA256:
        raise GovernanceError("corpus_changed", "Challenge bytes differ from the independently frozen corpus.")
    corpus = json.loads(raw)
    if corpus["repetitions_real"] != 3 or tuple(case["id"] for case in corpus["cases"]) != CASE_IDS:
        raise GovernanceError("corpus_changed", "Challenge categories or repetition policy changed.")
    for case in corpus["cases"]:
        validate_intent(canonical_json(case["candidate"]), case["original"], "UNBOUND")
    return corpus


def _write(path, value):
    raw = canonical_json(value) + b"\n"
    fd = _private_descriptor(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path), "sha256": sha256_bytes(raw)}


class DevelopmentCapture:
    """TrialRunner capture adapter with separate truthful development events.

    Production RunStore's compiler-before-verifier lifecycle is untouched.
    This adapter records independent-subject verifier attempts in its own event
    vocabulary, strips production-attempt metadata, and retains exact original
    attribution in characterization_artifact events. It cannot release output.
    """

    def __init__(self, directory):
        self._store = RunStore(directory / "captures.sqlite", directory / "artifacts", gate_authority=object())

    def create_run(self, **values):
        if values.get("contract", {}).get("scope") != SCOPE:
            raise GovernanceError("policy_denied", "Development capture rejects production contracts.")
        return self._store.create_run(**values)

    def get_run(self, run_id, *, caller_id):
        run = self._store.get_run(run_id, caller_id=caller_id)
        if run["contract"].get("scope") != SCOPE or run["accepted_ref"] is not None:
            raise GovernanceError("policy_denied", "Characterization cannot inspect or accept production work.")
        attempts = {}
        for event in run["events"]:
            if event["event_type"] == "characterization_invocation_started":
                attempt = event["payload"]
                attempts[attempt["attempt_id"]] = {**attempt, "outcome": "RUNNING"}
            elif event["event_type"] == "characterization_invocation_finished":
                attempt = event["payload"]
                attempts[attempt["attempt_id"]].update(attempt)
        return {**run, "status": "CHARACTERIZATION_ONLY", "attempts": list(attempts.values()),
                "compiler": {"status": "NOT_RUN", "reason": "Independently authored fixed subject; no compiler call claimed."}}

    def begin_attempt(self, run_id, role, *, caller_id):
        run = self.get_run(run_id, caller_id=caller_id)
        if role != "verifier" or run["attempts"]:
            raise GovernanceError("policy_denied", "Each independent subject permits one verifier attempt and no compiler or replay.")
        attempt = {"role": "verifier", "node_id": "intent", "attempt_id": uuid.uuid4().hex,
                   "invocation_id": uuid.uuid4().hex, "started_at": utc_now(), "scope": SCOPE}
        self._store.record_event(run_id, "characterization_invocation_started", attempt, caller_id=caller_id)
        return attempt

    def put_artifact(self, run_id, content, *, caller_id, **metadata):
        run = self.get_run(run_id, caller_id=caller_id)
        attempt_id = metadata.pop("attempt_id", None)
        invocation_id = metadata.pop("invocation_id", None)
        if attempt_id:
            matches = [attempt for attempt in run["attempts"] if attempt["attempt_id"] == attempt_id]
            if not matches or matches[0]["outcome"] != "RUNNING" or invocation_id != matches[0]["invocation_id"]:
                raise GovernanceError("policy_denied", "Characterization artifact has no current exact producing invocation.")
        ref = self._store.put_artifact(run_id, content, caller_id=caller_id, **metadata)
        self._store.record_event(run_id, "characterization_artifact", {
            "reference": ref, "attempt_id": attempt_id, "invocation_id": invocation_id,
            "scope": SCOPE, "production_attempt": False}, caller_id=caller_id)
        return ref

    def get_artifact(self, reference, *, caller_id):
        self.get_run(reference["run_id"], caller_id=caller_id)
        return self._store.get_artifact(reference, caller_id=caller_id)

    def finish_attempt(self, run_id, attempt_id, *, outcome, evidence, caller_id):
        run = self.get_run(run_id, caller_id=caller_id)
        attempt = next((attempt for attempt in run["attempts"] if attempt["attempt_id"] == attempt_id), None)
        if not attempt or attempt["outcome"] != "RUNNING":
            raise GovernanceError("policy_denied", "Characterization attempt cannot be forged or rewritten.")
        outcome = "SUCCEEDED" if outcome.upper() == "SUCCESS" else outcome.upper()
        if outcome == "SUCCEEDED" and (evidence.get("model_calls") != 1 or not evidence.get("output_ref")):
            raise GovernanceError("invalid_input", "A completed verifier needs actual call/output observations.")
        for key in ("prompt_ref", "observation_ref", "output_ref"):
            ref = evidence.get(key)
            if ref:
                self.get_artifact(ref, caller_id=caller_id)
                bound = [event["payload"] for event in run["events"] if event["event_type"] == "characterization_artifact"
                         and event["payload"]["reference"] == ref]
                if not bound or bound[0]["attempt_id"] != attempt_id:
                    raise GovernanceError("invalid_input", "Capture belongs to a different development invocation.")
        result = {**attempt, "outcome": outcome, "evidence": evidence, "finished_at": utc_now()}
        self._store.record_event(run_id, "characterization_invocation_finished", result, caller_id=caller_id)
        return result

    def commit_decision(self, *args, **kwargs):
        raise GovernanceError("policy_denied", "Development characterization has no accepted-artifact release capability.")


def _runtime(readiness):
    model = readiness.get("model", {})
    return {key: model.get(key) for key in ("account_fingerprint", "account_epoch", "runtime_version")}


async def _ready(application, frozen, fixture_mode):
    readiness = await application.readiness()
    is_mock = bool(getattr(application.bridge, "is_mock", False))
    if not readiness.get("ready") or is_mock != fixture_mode or not application.baseline:
        raise GovernanceError("environment_unavailable", "Required real definitions, model account or protected runtime is unavailable.")
    if not fixture_mode:
        if not readiness.get("identity_security", {}).get("ready") or not readiness.get("model", {}).get("security_ready"):
            raise GovernanceError("security_unavailable", "Characterization requires supported real private custody and IPC.")
        if _runtime(readiness) != frozen:
            raise GovernanceError("account_changed", "Frozen model account generation changed during characterization.")
    return readiness


async def run_campaign(application, context, *, corpus_path, output_dir, fixture_mode=False):
    """Run fixed verifier measurements; fixture_mode is Python-test-only."""
    corpus = load_corpus(corpus_path)
    output = _safe_path(output_dir)
    if output.is_relative_to(Path(context.workspace_path).absolute()):
        raise GovernanceError("policy_denied", "Challenge labels and measurement custody must remain outside the trial workspace.")
    output = _validate_custody(output)
    if any(output.iterdir()):
        raise GovernanceError("policy_denied", "A campaign needs new empty custody; old measurements cannot be overwritten or replayed.")
    campaign_id = uuid.uuid4().hex
    baseline = copy.deepcopy(application.baseline)
    frozen_runtime = (baseline or {}).get("runtime_identity")
    pins = dict(application.pins)
    cases = []
    for case in corpus["cases"]:
        for repetition in range(1, 4):
            run_id = hash_json({"campaign": campaign_id, "case": case["id"], "repetition": repetition})[:32]
            candidate = copy.deepcopy(case["candidate"])
            candidate["run_id"] = run_id
            cases.append({**case, "candidate": candidate, "repetition": repetition, "run_id": run_id,
                          "candidate_sha256": hash_json(candidate)})
    manifest = {"revision": corpus["revision"], "scope": SCOPE, "campaign_id": campaign_id,
                "corpus_sha256": CORPUS_SHA256, "criterion": corpus["acceptance_rule"], "repetitions_real": 3,
                "fixture_mode": fixture_mode, "profile_sha256": application.profile_sha256,
                "pins": {role: pin.to_dict() for role, pin in pins.items()}, "runtime_identity": frozen_runtime,
                "baseline": baseline, "cases": cases, "labels_disclosed_to_assessor": False,
                "compiler": "NOT_RUN", "created_at": utc_now(), "limitations": corpus["limitations"]}
    manifest_ref = _write(output / "manifest.json", manifest)
    capture = DevelopmentCapture(output / "development-state")
    runner = TrialRunner(application.bridge, application.library, capture)
    outcomes = []
    stopped = None
    try:
        await _ready(application, frozen_runtime, fixture_mode)
        for pin in pins.values():
            application.library.validate_pin(pin, required_scope="fixture-only" if fixture_mode else "real")
    except GovernanceError as exc:
        stopped = exc.code
    for ordinal, case in enumerate(cases, 1):
        record = {"case_id": case["id"], "repetition": case["repetition"], "run_id": case["run_id"],
                  "expected": case["expected"], "required_finding": case["required_finding"],
                  "candidate_hash": case["candidate_sha256"], "profile_hash": application.profile_sha256,
                  "compiler": "NOT_RUN", "scope": SCOPE, "fixture_mode": fixture_mode,
                  "false_acceptance": False, "false_refusal": False, "label_match": False,
                  "accepted_ref": None, "assessment_ref": None, "attempts": [],
                  "actual_model_calls": 0, "calls_observation": "No verifier invocation has been dispatched."}
        run = None
        started = time.monotonic()
        if stopped:
            record.update(observed="NOT_RUN", result="NOT_RUN", reason=stopped, actual_model_calls=0,
                          calls_observation="No invocation was dispatched because a prerequisite was blocked.")
        else:
            try:
                await _ready(application, frozen_runtime, fixture_mode)
                configuration = resolve_configuration({"mode": "headless"}, {}, baseline).to_dict()
                contract = {"interface_revision": "M0-IF-007@r2", "scope": SCOPE, "run_id": case["run_id"],
                    "node_id": "intent", "responsibility": "Read-only faithful intermediate Intent assessment.",
                    "user_id": context.user_id, "workspace_id": context.workspace_id,
                    "source_sha256": sha256_bytes(case["original"].encode("utf-8")),
                    "subject_sha256": case["candidate_sha256"], "profile_sha256": application.profile_sha256,
                    "runtime_identity": frozen_runtime, "allowed_effects": [], "automatic_retries": 0,
                    "subject_origin": "independently authored frozen challenge; compiler NOT_RUN"}
                run = capture.create_run(user_id=context.user_id, workspace_id=context.workspace_id,
                    caller_id=context.user_id, client_request_id=case["run_id"], run_id=case["run_id"],
                    original_text=case["original"], configuration=configuration, contract=contract,
                    pins=manifest["pins"], mode="headless")
                subject = capture.put_artifact(run["run_id"], canonical_json(case["candidate"]),
                    artifact_type="independent_challenge_subject", origin="observed", caller_id=context.user_id)
                validate_intent(capture.get_artifact(subject, caller_id=context.user_id), case["original"], run["run_id"])
                deterministic = [{"check_id": "D1", "status": "PASS", "reason": "Frozen independent subject schema/source/spans validated.",
                                  "evidence_refs": ["original", "candidate"]}]
                execution = {"compiler": {"status": "NOT_RUN", "reason": "Independent development subject; no compiler output or success claimed."},
                             "subject_ref": subject, "subject_sha256": subject["sha256"],
                             "origin": "independently authored development fixture", "model_calls": 0,
                             "compiler_model_calls": 0, "effects": []}
                inputs = {"original_text": case["original"], "candidate": case["candidate"],
                    "subject_sha256": subject["sha256"], "source_sha256": run["original_ref"]["sha256"],
                    "contract": contract, "contract_sha256": hash_json(contract),
                    "profile": json.loads(application.profile_bytes), "profile_sha256": application.profile_sha256,
                    "execution": execution, "deterministic": deterministic}
                deadline = time.monotonic() + min(configuration["effective"]["timeout_seconds"], 300)
                assessment, evidence = await runner.invoke(run, "verifier", inputs, pin=pins["verifier"],
                    model=configuration["effective"]["model_roles"]["verifier"], deadline=deadline, caller_id=context.user_id)
                record["assessment_ref"] = assessment
                await _ready(application, frozen_runtime, fixture_mode)
                application.library.validate_pin(pins["verifier"], required_scope="fixture-only" if fixture_mode else "real")
                decision = aggregate(capture.get_artifact(assessment, caller_id=context.user_id),
                    subject_ref=subject, original_ref=run["original_ref"], contract=contract,
                    profile_sha256=application.profile_sha256, deterministic=deterministic,
                    evidence_refs=[run["original_ref"], subject, assessment])
                observed = "PASS" if decision["mandatory_pass"] else decision["verdict"]
                required = case["required_finding"]
                required_match = not required or any(check["check_id"] == required and check["status"] == case["expected"]
                                                     for check in decision["checks"])
                matched = observed == case["expected"] and required_match
                record.update(observed=observed, label_match=matched, result="MATCH" if matched else "MISMATCH",
                    findings=decision["checks"], limitations=decision["limitations"], raw_observation_ref=evidence.get("observation_ref"),
                    false_acceptance=case["expected"] != "PASS" and observed == "PASS",
                    false_refusal=case["expected"] == "PASS" and observed != "PASS")
            except GovernanceError as exc:
                record.update(observed="ENVIRONMENT_BLOCKED" if exc.code in {"environment_unavailable", "security_unavailable", "account_changed", "ineligible_pin"} else "HALT",
                              result="HALT", reason=exc.code, false_refusal=case["expected"] == "PASS")
                if exc.code in {"environment_unavailable", "security_unavailable", "account_changed", "ineligible_pin"}:
                    stopped = exc.code
            if run:
                captured = capture.get_run(run["run_id"], caller_id=context.user_id)
                record["attempts"] = captured["attempts"]
                record["artifacts"] = captured["artifacts"]
                calls = [attempt.get("evidence", {}).get("model_calls") for attempt in captured["attempts"]]
                record["actual_model_calls"] = sum(calls) if calls and all(type(call) is int for call in calls) else None
                record["calls_observation"] = "Observed verifier invocation metadata." if record["actual_model_calls"] is not None else "Reliable completed call accounting unavailable; never inferred as zero."
        record["elapsed_seconds"] = time.monotonic() - started
        record["usage_availability"] = [{"usage": attempt.get("evidence", {}).get("usage"),
            "unavailable_reason": attempt.get("evidence", {}).get("usage_unavailable_reason", "Reliable per-call usage not supplied."),
            "cost": attempt.get("evidence", {}).get("cost"), "seed": attempt.get("evidence", {}).get("seed")}
            for attempt in record["attempts"]]
        record["output_reference"] = _write(output / f"case-{ordinal:02d}.json", record)
        outcomes.append(record)
    matched = sum(record["label_match"] for record in outcomes)
    status = "ENVIRONMENT_BLOCKED" if stopped else "FIXTURE_ONLY" if fixture_mode else "COMPLETE_MATCH" if matched == 27 else "MEASURED_FAILURE"
    report = {"status": status, "scope": SCOPE, "manifest": manifest_ref, "corpus_sha256": CORPUS_SHA256,
              "expected_observations": 27, "recorded_observations": len(outcomes), "matched_observations": matched,
              "false_acceptances": sum(record["false_acceptance"] for record in outcomes),
              "false_refusals": sum(record["false_refusal"] for record in outcomes), "outcomes": outcomes,
              "accepted_ref": None, "production_release": False, "compiler": "NOT_RUN",
              "limitations": corpus["limitations"], "blocked_reason": stopped}
    report["report_reference"] = _write(output / "report.json", report)
    return report


async def _main(args):
    application = None
    try:
        application, _, _, token_path = await bootstrap(args.state_dir, args.workspace,
            origin="http://127.0.0.1:4311", model=args.model, admission_receipt=args.admission_receipt)
        fd = _private_descriptor(token_path, os.O_RDONLY)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            context = application.identity.authenticate(stream.read(1025))
        report = await run_campaign(application, context, corpus_path=args.corpus, output_dir=args.output_dir)
        print(json.dumps({"status": report["status"], "scope": SCOPE, "report": report["report_reference"],
                          "matched_observations": report["matched_observations"], "expected_observations": 27,
                          "false_acceptances": report["false_acceptances"], "false_refusals": report["false_refusals"],
                          "production_release": False, "blocked_reason": report["blocked_reason"]}))
        return 0 if report["status"] == "COMPLETE_MATCH" else 3 if report["status"] == "ENVIRONMENT_BLOCKED" else 2
    except (GovernanceError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "code": getattr(exc, "code", "input_unavailable"), "scope": SCOPE,
                          "production_release": False}))
        return 3
    finally:
        if application:
            try:
                await application.shutdown()
            finally:
                try:
                    await application.bridge.close()
                finally:
                    application.process_lease.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True, help="Exact premeasurement locked-candidates.json; expected labels never enter assessor context.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New private directory outside the workspace; no overwrite or resume.")
    parser.add_argument("--model", help="Exact model ID from authenticated native discovery.")
    parser.add_argument("--admission-receipt", type=Path, help="Protected current definition eligibility receipt; absence blocks real admission.")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
