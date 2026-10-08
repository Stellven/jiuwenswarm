"""Prepare or explicitly execute a protected, headless verifier campaign.

The default is offline preparation. Only --execute-model may create the native
model adapter. This development evaluator cannot write product gate/run state,
activate a capsule, or produce an accepted intent artifact.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from jiuwenswarm.research.contracts import (FIDELITY_PROFILE, VERIFIER_INSTRUCTIONS,
    ResearchError, canonical, digest, parse_json, timestamp, validate_assessment,
    validate_call, validate_intent)
from jiuwenswarm.research.library import CapsuleLibrary
from jiuwenswarm.research.security import protect_directory

DEFAULT_FIXTURES = REPOSITORY / "tests/research/fixtures/intent_challenges.json"
SEMANTIC_VERDICTS = {"PASS", "FAIL", "INCONCLUSIVE"}
MAX_CASES = 128
MAX_RECORDS = 512
_CREDENTIAL = re.compile(
    r"sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._~-]{16,}|"
    r'(?i:api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token|client[_-]?secret|password)'
    r'["\s]*[:=]\s*["\']?[^"\'\s,}]{8,}'
)


class CampaignError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _write_new(path, value):
    """Fsync an immutable record before reporting it or making another call."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise CampaignError("CAMPAIGN_OUTPUT_EXISTS")
    temporary = path.with_name(".pending-" + uuid.uuid4().hex)
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except OSError:
        raise CampaignError("CAMPAIGN_STORAGE_FAILED") from None
    finally:
        temporary.unlink(missing_ok=True)


def _claim(request, value):
    text, quote = (value, value) if isinstance(value, str) else (value["text"], value["quote"])
    start = request.index(quote)
    return {"text": text, "quote": quote, "start": start, "end": start + len(quote)}


def fixture_candidate(case):
    request = case["request"]
    candidate = {"schema_version": "intent.v1", "request_hash": digest(request.encode("utf-8")),
                 "objective": [_claim(request, case.get("objective", request))],
                 "desired_outcome": [_claim(request, x) for x in case.get("desired_outcome", [])],
                 "scope": [_claim(request, x) for x in case.get("scope", [])],
                 "constraints": [_claim(request, x) for x in case.get("constraints", [])],
                 "omissions": copy.deepcopy(case.get("omissions", [])),
                 "conflicts": copy.deepcopy(case.get("conflicts", []))}
    validate_intent(candidate, request, candidate["request_hash"])
    return candidate


@dataclass
class PreparedCampaign:
    manifest: dict
    manifest_hash: str
    fixture_path: Path
    output_dir: Path
    library: CapsuleLibrary

    def assert_bindings(self):
        try:
            persisted = parse_json((self.output_dir / "manifest.json").read_text(encoding="utf-8"))
            if (digest(persisted) != self.manifest_hash or persisted != self.manifest
                    or digest(self.fixture_path.read_bytes()) != self.manifest["fixture_sha256"]
                    or digest(Path(__file__).read_bytes()) != self.manifest["evaluation_code_sha256"]
                    or digest(FIDELITY_PROFILE) != self.manifest["profile_sha256"]
                    or self.library.resolve() != self.manifest["capsule_pins"]):
                raise CampaignError("CAMPAIGN_BINDING_CHANGED")
        except (OSError, ResearchError):
            raise CampaignError("CAMPAIGN_BINDING_CHANGED") from None


def prepare_campaign(fixture_path, output_dir, *, model=None, timeout_seconds=60,
                     repetitions=1, seed=None):
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 600 or type(repetitions) is not int or not 1 <= repetitions <= 100
            or (seed is not None and type(seed) is not int)):
        raise CampaignError("CAMPAIGN_OPTIONS_INVALID")
    if model is not None and (not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,200}", model)):
        raise CampaignError("CAMPAIGN_OPTIONS_INVALID")
    fixture_path, output_dir = Path(fixture_path).resolve(), Path(output_dir).absolute()
    if output_dir.is_symlink():
        raise CampaignError("CAMPAIGN_STORAGE_FAILED")
    try:
        raw = fixture_path.read_bytes()
        if len(raw) > 2 * 1024 * 1024 or _CREDENTIAL.search(raw.decode("utf-8")):
            raise CampaignError("CHALLENGE_FIXTURE_INVALID")
        fixtures = parse_json(raw.decode("utf-8"))
        if fixtures.get("schema_version") != "intent-challenges.v1" or not isinstance(fixtures.get("cases"), list):
            raise CampaignError("CHALLENGE_FIXTURE_INVALID")
        criteria = fixtures.get("criteria", {})
        if not isinstance(criteria, dict):
            raise CampaignError("CHALLENGE_CRITERIA_INVALID")
        for key in ("mandatory_refusal_rate", "faithful_acceptance_rate"):
            if type(criteria.get(key)) not in (int, float) or not 0 <= criteria[key] <= 1:
                raise CampaignError("CHALLENGE_CRITERIA_INVALID")
        selected, seen = [], set()
        for case in fixtures["cases"]:
            if not isinstance(case, dict):
                raise CampaignError("CHALLENGE_FIXTURE_INVALID")
            if case.get("fault"):
                continue
            if (not isinstance(case.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", case["id"])
                    or case["id"] in seen or case.get("expected_verdict") not in SEMANTIC_VERDICTS
                    or type(case.get("expected_acceptance")) is not bool
                    or case["expected_acceptance"] != (case["expected_verdict"] == "PASS")
                    or not isinstance(case.get("request"), str) or not case["request"].strip()
                    or len(case["request"].encode("utf-8")) > 64 * 1024):
                raise CampaignError("CHALLENGE_FIXTURE_INVALID")
            seen.add(case["id"])
            selected.append({"id": case["id"], "category": case.get("category"), "request": case["request"],
                             "candidate": fixture_candidate(case), "expected_verdict": case["expected_verdict"],
                             "expected_acceptance": case["expected_acceptance"]})
        if not selected or len(selected) > MAX_CASES or len(selected) * repetitions > MAX_RECORDS:
            raise CampaignError("NO_BOUNDED_SEMANTIC_CASES")
        if not any(c["expected_acceptance"] for c in selected) or not any(not c["expected_acceptance"] for c in selected):
            raise CampaignError("CHALLENGE_LABEL_COVERAGE_INVALID")
        protect_directory(output_dir)
        output_dir = output_dir.resolve()
        if (output_dir / "manifest.json").exists():
            raise CampaignError("CAMPAIGN_OUTPUT_EXISTS")
        library = CapsuleLibrary(output_dir / "capsules")
        manifest = {"schema_version": "intent-fidelity-campaign.v1", "evaluation_id": uuid.uuid4().hex,
                    "created_at": timestamp(), "mode": "headless-development", "product_valid": False,
                    "gate_state_written": False, "fixture_sha256": digest(raw),
                    "evaluation_code_sha256": digest(Path(__file__).read_bytes()),
                    "profile_sha256": digest(FIDELITY_PROFILE), "capsule_pins": library.resolve(),
                    "criteria": copy.deepcopy(criteria), "strict_expected_verdict_match": True,
                    "model": model, "timeout_seconds": timeout_seconds, "repetitions": repetitions,
                    "calls_per_case": 1, "automatic_retries": 0,
                    "failure_policy": {"semantic_refusal_or_timeout": "record_and_continue",
                                       "identity_or_binding_change": "stop_new_calls"},
                    "seed": {"requested": seed, "effective": None, "control": "unavailable"},
                    "cases": selected,
                    "limitations": ["A separate invocation does not establish independent model errors.",
                                    "Repeated trials characterize observed outcomes; they do not prove calibrated truth.",
                                    "Fixture thresholds describe this frozen challenge set; they are not general real-model reliability acceptance criteria.",
                                    "Campaign results cannot admit or activate a verifier or establish product completion."]}
        _write_new(output_dir / "manifest.json", manifest)
        return PreparedCampaign(manifest, digest(manifest), fixture_path, output_dir, library)
    except (KeyError, ValueError, TypeError, UnicodeError, ResearchError):
        raise CampaignError("CHALLENGE_FIXTURE_INVALID") from None
    except OSError:
        raise CampaignError("CAMPAIGN_STORAGE_FAILED") from None


def _safe_text(text):
    return _CREDENTIAL.sub("[REDACTED_CREDENTIAL]", text)


def _safe_value(value):
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_safe_value(x) for x in value]
    if isinstance(value, dict):
        return {key: _safe_value(item) for key, item in value.items()}
    return value


def _usage(value, depth=0):
    if not isinstance(value, dict) or depth > 2:
        return "unavailable"
    allowed = {"input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
               "inputTokens", "outputTokens", "totalTokens", "cachedInputTokens", "reasoningOutputTokens"}
    usage = {key: number for key, number in value.items() if key in allowed and type(number) is int and number >= 0}
    for key in ("last", "total"):
        nested = _usage(value.get(key), depth + 1)
        if isinstance(nested, dict):
            usage[key] = nested
    return usage or "unavailable"


def _error_code(exc):
    code = getattr(exc, "code", "")
    allowed = {"SIGN_IN_REQUIRED", "SUBSCRIPTION_REQUIRED", "MODEL_UNAVAILABLE", "MODEL_TIMEOUT",
               "MODEL_SECURITY_UNAVAILABLE", "RUNTIME_UNAVAILABLE", "RUNTIME_DISCONNECTED", "MODEL_PROTOCOL_ERROR",
               "MODEL_TOOLS_FORBIDDEN", "MODEL_CONFIGURATION_MISMATCH", "MODEL_OUTPUT_LIMIT", "MODEL_EVENT_LIMIT",
               "MODEL_TURN_FAILED", "MODEL_THREAD_REUSED", "PROFILE_IN_USE", "PROFILE_CONFIG_CONFLICT"}
    allowed.update({"MODEL_ACCOUNT_CHANGED", "ACCOUNT_IDENTITY_UNAVAILABLE"})
    return code if code in allowed else "MODEL_UNAVAILABLE"


def dry_run_report(prepared):
    prepared.assert_bindings()
    report = {"schema_version": "intent-fidelity-results.v1", "evaluation_id": prepared.manifest["evaluation_id"],
              "manifest_sha256": prepared.manifest_hash, "status": "PREPARED_NOT_MEASURED", "passed": False,
              "product_valid": False, "model_backed": False, "measured": False, "model_calls": 0,
              "case_count": len(prepared.manifest["cases"]), "repetitions": prepared.manifest["repetitions"],
              "gate_state_written": False, "admission_eligible": False,
              "limitations": prepared.manifest["limitations"] + ["Offline preparation only; no model readiness or invocation occurred."]}
    _write_new(prepared.output_dir / "preparation.json", report)
    return report


async def run_campaign(prepared, model, *, model_backed=False):
    """Injected models support offline tests; only the CLI opts into native calls."""
    prepared.assert_bindings()
    manifest, records = prepared.manifest, []
    readiness_code = None
    auth_context_hash = None
    try:
        ready = await asyncio.wait_for(model.readiness(), manifest["timeout_seconds"])
        if not isinstance(ready, dict) or ready.get("ready") is not True or ready.get("security") is not True:
            readiness_code = "MODEL_SECURITY_UNAVAILABLE" if isinstance(ready, dict) and ready.get("security") is not True else "MODEL_UNAVAILABLE"
        elif isinstance(ready.get("auth_context_hash"), str) and re.fullmatch(r"[a-f0-9]{64}", ready["auth_context_hash"]):
            auth_context_hash = ready["auth_context_hash"]
        elif model_backed:
            readiness_code = "ACCOUNT_IDENTITY_UNAVAILABLE"
    except asyncio.TimeoutError:
        readiness_code = "MODEL_TIMEOUT"
    except Exception as exc:
        readiness_code = _error_code(exc)
    model_binding = {"manifest_sha256": prepared.manifest_hash, "at": timestamp(),
                     "model_backed": model_backed, "model": manifest["model"],
                     "auth_context_hash": auth_context_hash,
                     "auth_context_control": "native-context-bound" if model_backed and auth_context_hash else "test-only-unmeasured",
                     "readiness_code": readiness_code or "READY"}
    _write_new(prepared.output_dir / "model-binding.json", model_binding)
    stop_reason = None
    for case in manifest["cases"]:
        for repetition in range(1, manifest["repetitions"] + 1):
            subject = {"evaluation_id": manifest["evaluation_id"],
                       "case_id": digest((manifest["evaluation_id"] + ":" + case["id"]).encode("utf-8")),
                       "repetition": repetition,
                       "request_hash": case["candidate"]["request_hash"], "candidate_hash": digest(case["candidate"]),
                       "compiler_pin": manifest["capsule_pins"]["compiler"], "verifier_pin": manifest["capsule_pins"]["verifier"],
                       "profile_hash": manifest["profile_sha256"], "evaluation_code_hash": manifest["evaluation_code_sha256"]}
            record = {"case": case["id"], "category": case["category"], "repetition": repetition, "subject": subject,
                      "expected_verdict": case["expected_verdict"], "expected_acceptance": case["expected_acceptance"],
                      "observed_verdict": "ENVIRONMENT_BLOCKED", "reason": readiness_code or "NOT_RUN",
                      "calls": 0, "raw": None, "raw_sha256": None, "assessment": None,
                      "assessment_valid": False,
                      "provider": "unavailable", "model": "unavailable", "usage": "unavailable", "cost": "unavailable",
                      "thread_id": "unavailable",
                      "auth_context_expected_hash": auth_context_hash, "auth_context_hash": None,
                      "auth_context_verified": False,
                      "duration_ms": 0, "product_valid": False, "model_backed": model_backed, "gate_state_written": False}
            if not stop_reason and not readiness_code:
                start = time.monotonic()
                try:
                    prepared.assert_bindings()
                    candidate_text = canonical(case["candidate"]).decode("utf-8")
                    payload = copy.deepcopy({"request": case["request"], "candidate": case["candidate"],
                        "candidate_text": candidate_text, "subject": subject, "fidelity_profile": FIDELITY_PROFILE,
                        "declared_responsibility": "Extract attributed intent; preserve omissions and conflicts without choosing a solution"})
                    record["calls"] = 1
                    result = await asyncio.wait_for(model.complete(role="verifier", instructions=VERIFIER_INSTRUCTIONS,
                        payload=payload, model=manifest["model"], timeout_seconds=manifest["timeout_seconds"]),
                        manifest["timeout_seconds"])
                    duration_ms = (time.monotonic() - start) * 1000
                    if isinstance(result, dict) and isinstance(result.get("text"), str):
                        raw = result["text"]
                        record.update(raw=_safe_text(raw[:256 * 1024]), raw_sha256=digest(raw.encode("utf-8")),
                                      raw_redacted=_safe_text(raw) != raw)
                    validate_call(result, duration_ms, manifest["timeout_seconds"])
                    if model_backed and result["provider"] != "openai":
                        raise ResearchError("MODEL_ROUTE_MISMATCH")
                    if manifest["model"] is not None and result.get("model") != manifest["model"]:
                        raise ResearchError("MODEL_ROUTE_MISMATCH")
                    observed_auth = result.get("auth_context_hash")
                    if model_backed and observed_auth != auth_context_hash:
                        raise CampaignError("MODEL_ACCOUNT_CHANGED")
                    if record.get("raw_redacted"):
                        raise ResearchError("SENSITIVE_MODEL_OUTPUT")
                    assessment = parse_json(result["text"])
                    verdict, reason = validate_assessment(assessment, subject, case["request"], candidate_text)
                    prepared.assert_bindings()
                    record.update(observed_verdict=verdict, reason=reason, assessment=_safe_value(assessment),
                                  assessment_valid=True,
                                  provider=result["provider"] if result["provider"] in {"openai", "mock"} else "test-provider",
                                  model=_safe_value(result.get("model")) if isinstance(result.get("model"), (str, type(None))) else "unavailable",
                                  thread_id=_safe_text(result["thread_id"]) if isinstance(result.get("thread_id"), str) else "unavailable",
                                  auth_context_hash=observed_auth if isinstance(observed_auth, str) and re.fullmatch(r"[a-f0-9]{64}", observed_auth) else None,
                                  auth_context_verified=model_backed and observed_auth == auth_context_hash,
                                  usage=_usage(result.get("usage")))
                except asyncio.TimeoutError:
                    record["reason"] = "MODEL_TIMEOUT"
                except CampaignError as exc:
                    record["reason"], stop_reason = exc.code, exc.code
                except ResearchError as exc:
                    record.update(observed_verdict="FAIL", reason=exc.code)
                except Exception as exc:
                    record["reason"] = _error_code(exc)
                    if record["reason"] in {"MODEL_ACCOUNT_CHANGED", "ACCOUNT_IDENTITY_UNAVAILABLE"}:
                        stop_reason = record["reason"]
                finally:
                    record["duration_ms"] = round((time.monotonic() - start) * 1000, 3)
            elif stop_reason:
                record["reason"] = stop_reason + "_NOT_RUN"
            accepted = record["observed_verdict"] == "PASS"
            record.update(observed_acceptance=accepted,
                          false_acceptance=not case["expected_acceptance"] and accepted,
                          false_refusal=case["expected_acceptance"] and not accepted,
                          expected_verdict_match=case["expected_verdict"] == record["observed_verdict"])
            _write_new(prepared.output_dir / (case["id"] + "." + str(repetition) + ".json"), record)
            records.append(record)
    negative = [r for r in records if not r["expected_acceptance"]]
    positive = [r for r in records if r["expected_acceptance"]]
    measured = all(r["calls"] == 1 and r["assessment_valid"] for r in records)
    refusal_rate = sum(r["assessment_valid"] and not r["observed_acceptance"] for r in negative) / len(negative)
    acceptance_rate = sum(r["assessment_valid"] and r["observed_acceptance"] for r in positive) / len(positive)
    observed_variation = {case["id"]: sorted({r["observed_verdict"] for r in records if r["case"] == case["id"]}) for case in manifest["cases"]}
    passed = measured and all(r["expected_verdict_match"] for r in records) and (
        refusal_rate >= manifest["criteria"]["mandatory_refusal_rate"]
        and acceptance_rate >= manifest["criteria"]["faithful_acceptance_rate"])
    report = {"schema_version": "intent-fidelity-results.v1", "evaluation_id": manifest["evaluation_id"],
              "manifest_sha256": prepared.manifest_hash, "status": "COMPLETED" if passed else "FAILED",
              "passed": passed, "measured": measured, "model_backed": model_backed, "product_valid": False,
              "real_model_fidelity_measured": model_backed and measured,
              "measurement_kind": "model-backed" if model_backed else "scripted-test",
              "model_calls": sum(r["calls"] for r in records), "gate_state_written": False,
              "model_call_count_kind": "bounded bridge invocation attempts", "provider_call_count": "unavailable",
              "reliability_claim": "descriptive characterization of this fixed challenge set only", "admission_eligible": False,
              "criteria": manifest["criteria"], "mandatory_refusal_rate": refusal_rate,
              "faithful_acceptance_rate": acceptance_rate, "false_acceptances": sum(r["false_acceptance"] for r in records),
              "false_refusals": sum(r["false_refusal"] for r in records), "observed_variation": observed_variation,
              "seed": manifest["seed"], "cases": records,
              "model_binding_sha256": digest(model_binding),
              "limitations": manifest["limitations"] + ([] if model_backed else ["Injected test provider; real-model fidelity remains unmeasured."])}
    _write_new(prepared.output_dir / "results.json", report)
    return report


def create_native_model(output_dir):
    # Deliberately lazy: offline preparation never starts authentication/model IPC.
    from jiuwenswarm.research.model import CodexModel
    return CodexModel(Path(output_dir) / "model")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    parser.add_argument("--output", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--execute-model", action="store_true")
    args = parser.parse_args(argv)
    output = Path(args.output) if args.output else REPOSITORY / "tmp" / ("intent-fidelity-" + uuid.uuid4().hex)
    try:
        prepared = prepare_campaign(args.fixtures, output, model=args.model, timeout_seconds=args.timeout,
                                    repetitions=args.repetitions, seed=args.seed)
        if not args.execute_model:
            report = dry_run_report(prepared)
            exit_code = 0  # Preparation succeeded; passed/measured remain explicitly false.
        else:
            async def execute():
                model = create_native_model(output)
                try:
                    return await run_campaign(prepared, model, model_backed=True)
                finally:
                    await model.close()
            report = asyncio.run(execute())
            exit_code = 0 if report["passed"] else 2
        print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False), flush=True)
        return exit_code
    except (CampaignError, ResearchError) as exc:
        print(json.dumps({"error": exc.code, "product_valid": False, "passed": False}), flush=True)
        return 2
    except (OSError, ValueError, RuntimeError):
        print(json.dumps({"error": "CAMPAIGN_ENVIRONMENT_BLOCKED", "product_valid": False, "passed": False}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
