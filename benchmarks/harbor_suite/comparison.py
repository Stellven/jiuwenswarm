"""Frozen, single-turn native Codex baseline and paired offline comparisons.

Import, prepare and compare never authenticate or invoke inference. Only run()
can invoke the existing native helper, once, after a durable exclusive claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def assignment_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _loads(text):
    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")
    return json.loads(text, object_pairs_hook=_unique, parse_constant=invalid_constant)


def _read(path):
    return _loads(Path(path).read_text(encoding="utf-8-sig"))


def _sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _write(path, value, *, raw=False):
    """Exclusive durable creation; never overwrite an earlier observation."""
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value if raw else canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _validator(schema):
    from jsonschema.validators import validator_for
    from referencing import Registry
    from referencing.exceptions import NoSuchResource
    def no_external_resources(uri):
        raise NoSuchResource(ref=uri)
    cls = validator_for(schema)
    cls.check_schema(schema)
    return cls(schema, registry=Registry(retrieve=no_external_resources))


def validate_assignment(assignment):
    if not isinstance(assignment, dict) or set(assignment) != {
            "task", "inputs", "output_contracts", "limits"}:
        raise ValueError("Expected only frozen task, inputs, output_contracts and limits")
    if not isinstance(assignment["task"], (str, dict)) or not assignment["task"]:
        raise ValueError("Missing public task")
    if not isinstance(assignment["inputs"], dict) or not assignment["inputs"]:
        raise ValueError("Missing public inputs")
    for port, item in assignment["inputs"].items():
        if not isinstance(port, str) or not isinstance(item, dict) or set(item) != {"ref", "value"}:
            raise ValueError("Each public input requires its original ref and value")
        ref = item["ref"]
        if not isinstance(ref, dict) or not isinstance(ref.get("id"), str) or not isinstance(ref.get("sha256"), str):
            raise ValueError("Missing declared public input identity")
        if len(ref["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in ref["sha256"]):
            raise ValueError("Invalid declared input digest")
    contracts = assignment["output_contracts"]
    if not isinstance(contracts, dict) or not contracts:
        raise ValueError("Missing declared output contracts")
    for port, contract in contracts.items():
        if not isinstance(port, str) or not isinstance(contract, dict) or set(contract) != {"contract_id", "schema"}:
            raise ValueError("Each output requires contract_id and schema")
        if not isinstance(contract["contract_id"], str) or not contract["contract_id"]:
            raise ValueError("Missing output contract identity")
        _validator(contract["schema"])
    limits = assignment["limits"]
    if not isinstance(limits, dict):
        raise ValueError("Missing frozen common limits")
    if type(limits.get("max_model_calls")) is not int or not 1 <= limits["max_model_calls"] <= 20:
        raise ValueError("Unsupported common model-call cap")
    if (type(limits.get("wall_time_s")) not in {int, float}
            or not math.isfinite(limits["wall_time_s"]) or not 0 < limits["wall_time_s"] <= 600):
        raise ValueError("Unsupported common wall-time cap")
    canonical(assignment)
    return assignment


def make_prompt(assignment):
    validate_assignment(assignment)
    # Whitelist construction: no capsule body, criteria, oracle, gold or profile.
    public = {key: assignment[key] for key in ("task", "inputs", "output_contracts")}
    return ("Perform the following public assignment using only its supplied inputs. "
            "Return one JSON object whose keys are exactly the declared output ports, "
            "with each value satisfying that port's full declared JSON schema. "
            "Return the original answer directly, without Markdown fences or commentary.\n"
            + canonical(public).decode("utf-8"))


def _config(path):
    config = _read(path)
    required = {"model", "timeout_s", "codex_executable", "codex_sha256",
                "account_fingerprint", "working_directory"}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Private config must be the native helper payload template without prompt")
    model = config["model"]
    from jiuwenswarm.research.local_model_codex import MODEL_KEYS
    if (not isinstance(model, dict) or model.get("model_name") != "gpt-6.1-sol"
            or set(model) != MODEL_KEYS or model.get("reasoning_effort") != "medium"
            or model.get("enabled") is not True):
        raise ValueError("Baseline requires the qualified GPT-6.1-Sol medium identity")
    for key in ("codex_sha256", "account_fingerprint"):
        value = config[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Malformed private qualification pin")
    for number in (config["timeout_s"], model["timeout_s"]):
        if type(number) not in {int, float} or not math.isfinite(number) or not 0 < number <= 600:
            raise ValueError("Malformed qualified timeout")
    if (type(model["max_prompt_bytes"]) is not int or not 0 < model["max_prompt_bytes"] <= 1024*1024
            or type(model["context_window"]) is not int or model["context_window"] <= 0):
        raise ValueError("Malformed qualified model limits")
    return config


def prepare(assignment, workspace, *, private_config, control, timeout_s=120):
    """Freeze public assignment and private command pins; perform no model I/O."""
    validate_assignment(assignment)
    config = _config(private_config)
    if (type(timeout_s) not in {int, float} or not math.isfinite(timeout_s)
            or not 0 < timeout_s <= min(120, assignment["limits"]["wall_time_s"],
                                      config["timeout_s"], config["model"]["timeout_s"])):
        raise ValueError("One native call must fit the common and qualified call budgets")
    prompt = make_prompt(assignment)
    if len(prompt.encode("utf-8")) > config["model"]["max_prompt_bytes"]:
        raise ValueError("Frozen public prompt exceeds the qualified prompt-byte cap")
    workspace, control = Path(workspace).absolute(), Path(control).absolute()
    if control == workspace or workspace in control.parents or control in workspace.parents:
        raise ValueError("Shared private control and workspace must have separate roots")
    if any(part.lower() == "jobs" for part in control.parts):
        raise ValueError("Private native receipts cannot be stored under a Harbor jobs root")
    workspace.mkdir(mode=0o700)
    (workspace / "public").mkdir(mode=0o700)
    control.mkdir(parents=True, exist_ok=True, mode=0o700)
    if control.is_symlink():
        raise ValueError("Private control cannot be a symlink")
    frozen = {"schema": "native-codex-baseline-freeze:1", "assignment_sha256": assignment_digest(assignment),
              "private_config_sha256": assignment_digest(config), "timeout_s": timeout_s,
              "control": str(control.resolve()), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    _write(workspace / "assignment.json", assignment)
    _write(workspace / "prompt.txt", prompt.encode(), raw=True)
    _write(workspace / "frozen.json", frozen)
    return frozen


def check_format(outputs, contracts):
    result = {}
    if not isinstance(outputs, dict):
        return {"valid": False, "ports": {}, "error": "answer_not_object"}
    for port, contract in contracts.items():
        if port not in outputs:
            result[port] = {"valid": False, "error": "missing_port"}
            continue
        try:
            error = next(_validator(contract["schema"]).iter_errors(outputs[port]), None)
            result[port] = {"valid": error is None}
            if error is not None:
                result[port].update(error="schema_violation", path=list(error.absolute_path),
                                    validator=str(error.validator))
        except Exception as exc:
            result[port] = {"valid": False, "error": "schema_validation_unavailable",
                            "error_type": type(exc).__name__}
    extras = sorted(set(outputs) - set(contracts))
    return {"valid": not extras and all(v["valid"] for v in result.values()),
            "ports": result, "extra_ports": extras}


def run(workspace, *, private_config, execute_fn=None):
    """One effect, no retries. Unknown native outcomes retain the global claim."""
    workspace = Path(workspace).resolve()
    frozen, assignment = _read(workspace / "frozen.json"), _read(workspace / "assignment.json")
    config = _config(private_config)
    prompt = (workspace / "prompt.txt").read_bytes().decode("utf-8")
    if (assignment_digest(assignment) != frozen["assignment_sha256"]
            or assignment_digest(config) != frozen["private_config_sha256"]
            or hashlib.sha256(prompt.encode()).hexdigest() != frozen["prompt_sha256"]
            or prompt != make_prompt(assignment)):
        raise ValueError("Frozen assignment, prompt or private command pins changed")
    if not 0 < frozen["timeout_s"] <= min(120, assignment["limits"]["wall_time_s"],
                                         config["timeout_s"], config["model"]["timeout_s"]):
        raise ValueError("Frozen call budget exceeds the qualified common allowance")
    control = Path(frozen["control"])
    request_id = uuid.uuid4().hex
    claim = {"schema": "native-codex-baseline-claim:1", "request_id": request_id,
             "assignment_sha256": frozen["assignment_sha256"], "workspace": str(workspace),
             "started_at": datetime.now(timezone.utc).isoformat()}
    # Workspace claim prevents replay even after a known terminal cleared active.
    _write(workspace / "launched.json", claim)
    _write(control / "active.json", claim)
    private = control / ("request-" + request_id)
    private.mkdir(mode=0o700)
    report = {"schema": "native-codex-baseline-result:1", "arm": "native_codex_tool_free",
              "assignment_sha256": frozen["assignment_sha256"], "status": "outcome_unknown",
              "outputs": None, "format": None, "usage": None, "effective_model": None,
              "reasoning_effort": None, "native_terminal": None, "cost_usd": None,
              "call_limit": 1, "call_timeout_s": frozen["timeout_s"]}
    known = False
    started = time.monotonic()
    try:
        if execute_fn is None:
            from jiuwenswarm.research.local_model_codex import execute
            execute_fn = execute
        payload = {**config, "prompt": prompt, "timeout_s": frozen["timeout_s"]}
        response = execute_fn(payload)  # Exactly one authorized native helper invocation.
        report["native_call_latency_s"] = time.monotonic() - started
        _write(private / "original-response.json", response)
        raw = response.get("response_text")
        if not isinstance(raw, str):
            raise ValueError("Missing original native receipt")
        _write(private / "original-receipt.json", raw.encode("utf-8"), raw=True)
        from jiuwenswarm.research.local_models import native_codex_response
        bundle, observation, text = native_codex_response(raw,
            {"backend": config, "model": config["model"]}, prompt=prompt)
        if response.get("outcome") != bundle["outcome"]:
            raise ValueError("Native envelope outcome differs from validated receipt")
        known = bundle["outcome"] in {"completed", "failed"}
        report.update(status=bundle["outcome"], usage=observation["usage"],
            effective_model=observation["identity"]["effective"],
            reasoning_effort=(bundle["thread_start"] or {}).get("reasoningEffort"),
            native_terminal=((bundle["turn_completed"] or {}).get("turn") or {}).get("status"),
            error_code=bundle["error_code"],
            full_original_trace=_loads(raw).get("evidence", {}).get("full_original_trace", True))
        _write(workspace / "public" / "original.txt", text.encode("utf-8"), raw=True)
        if bundle["outcome"] == "completed":
            try:
                outputs = _loads(text)
            except (ValueError, TypeError):
                report["format"] = {"valid": False, "error": "invalid_json"}
            else:
                report["outputs"] = outputs
                report["format"] = check_format(outputs, assignment["output_contracts"])
                _write(workspace / "public" / "outputs.json", outputs)
    except Exception as exc:
        # Error messages can contain native/private values; publish only type.
        known = False
        report.update(status="outcome_unknown", diagnostic_type=type(exc).__name__)
        _write(private / "failure.json", {"type": type(exc).__name__})
    report["latency_s"] = time.monotonic() - started
    _write(private / "result.json", report)
    _write(workspace / "public" / "result.json", report)
    if known:
        # Preserve the original claim rather than deleting it to force dispatch.
        os.rename(control / "active.json", control / ("closed-" + request_id + ".json"))
        _sync_directory(control)
    return report


def compare(assignment, baseline, cc, *, variant, quality_port, content_evaluator=None):
    """Score common content independently from CC binding and full-port format."""
    validate_assignment(assignment)
    digest = assignment_digest(assignment)
    if any(arm.get("assignment_sha256") != digest for arm in (baseline, cc)):
        raise ValueError("Paired arms do not share the exact frozen public assignment")
    if quality_port not in assignment["output_contracts"]:
        raise ValueError("Quality port is not a declared output")
    if content_evaluator is None:
        from .contracts import resolve_cases_root
        path = resolve_cases_root() / "cc01-transfer" / "oracle.py"
        spec = importlib.util.spec_from_file_location("cc01_shared_content", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        content_evaluator = module.evaluate_content
    arms = {}
    for name, source in (("native_codex_tool_free", baseline), ("ai4r_cc", cc)):
        outputs = source.get("outputs")
        quality = None
        if source.get("status") == "completed" and isinstance(outputs, dict) and isinstance(outputs.get(quality_port), dict):
            quality = content_evaluator(outputs[quality_port], variant)
        arms[name] = {"status": source.get("status"), "usage": source.get("usage"),
            "latency_s": source.get("latency_s"), "effective_model": source.get("effective_model"),
            "native_call_latency_s": source.get("native_call_latency_s"),
            "reasoning_effort": source.get("reasoning_effort"), "cost_usd": source.get("cost_usd"),
            "format": check_format(outputs, assignment["output_contracts"]), "content": quality,
            "binding_assessment": source.get("binding_assessment") if name == "ai4r_cc" else "not_applicable"}
    return {"schema": "native-codex-ai4r-paired-comparison:1", "assignment_sha256": digest,
            "quality_port": quality_port, "arms": arms, "sample_pairs": 1,
            "inference": "Descriptive single pair; no improvement or generalization claim.",
            "human_review": "Separate review required where the content oracle marks semantic grounding unavailable."}


def verifier_metrics(rows):
    """Paired artifact decisions against frozen independent validity labels.

    Each row binds both decisions to exactly one artifact SHA-256. None means an
    unavailable decision, counted separately rather than treated as rejection.
    This function does not author, substitute or infer benchmark validity labels.
    """
    seen, result = set(), {}
    for row in rows:
        digest = row.get("artifact_sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest) or digest in seen
                or type(row.get("valid")) is not bool):
            raise ValueError("Expected unique artifact identity and frozen boolean validity")
        seen.add(digest)
        for arm in ("native_codex_tool_free", "ai4r_verifier"):
            decision = row.get(arm)
            if decision is not None and type(decision) is not bool:
                raise ValueError("Verifier decision must be boolean or unavailable")
            counts = result.setdefault(arm, {"false_accept": 0, "false_reject": 0,
                "true_accept": 0, "true_reject": 0, "unavailable": 0,
                "valid_artifacts": 0, "invalid_artifacts": 0})
            counts["valid_artifacts" if row["valid"] else "invalid_artifacts"] += 1
            if decision is None:
                key = "unavailable"
            elif row["valid"]:
                key = "true_accept" if decision else "false_reject"
            else:
                key = "false_accept" if decision else "true_reject"
            counts[key] += 1
    for counts in result.values():
        # Rates use observed decisions; unavailable counts remain explicit.
        accepted_invalid = counts["false_accept"] + counts["true_reject"]
        rejected_valid = counts["false_reject"] + counts["true_accept"]
        counts["false_accept_rate_observed"] = counts["false_accept"] / accepted_invalid if accepted_invalid else None
        counts["false_reject_rate_observed"] = counts["false_reject"] / rejected_valid if rejected_valid else None
    return {"schema": "paired-verifier-confusion:1", "paired_artifacts": len(seen), "arms": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--assignment", type=Path, required=True)
    prep.add_argument("--workspace", type=Path, required=True)
    prep.add_argument("--private-config", type=Path, required=True)
    prep.add_argument("--control", type=Path, required=True)
    prep.add_argument("--timeout-s", type=float, default=120)
    launch = commands.add_parser("run")
    launch.add_argument("--workspace", type=Path, required=True)
    launch.add_argument("--private-config", type=Path, required=True)
    paired = commands.add_parser("compare")
    for option in ("assignment", "baseline", "cc", "criteria", "output"):
        paired.add_argument("--" + option, type=Path, required=True)
    paired.add_argument("--variant", required=True)
    paired.add_argument("--quality-port", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(_read(args.assignment), args.workspace, private_config=args.private_config,
                         control=args.control, timeout_s=args.timeout_s)
        print(json.dumps({"workspace": str(args.workspace), "assignment_sha256": result["assignment_sha256"]}))
    elif args.command == "run":
        result = run(args.workspace, private_config=args.private_config)
        print(canonical(result).decode())
    else:
        result = compare(_read(args.assignment), _read(args.baseline), _read(args.cc),
                         variant=_read(args.criteria)["variants"][args.variant], quality_port=args.quality_port)
        _write(args.output, result)
        print(json.dumps({"report": str(args.output), "sample_pairs": 1}))


if __name__ == "__main__":
    main()
