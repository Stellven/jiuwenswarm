"""Operator-authored frozen Pi task materials for the research pipeline."""
from __future__ import annotations

import hashlib
import inspect
import json
import platform
from pathlib import Path

from .contracts import validate
from .pi_protocol import _gauss_legendre, validate_pi_request
from .state import json_bytes


def _baseline_source() -> bytes:
    function = inspect.getsource(_gauss_legendre)
    source = (
        "import json\n"
        "import math\n"
        "from decimal import Decimal, localcontext\n"
        "from pathlib import Path\n\n"
        + function
        + "\n\ndef approximate_pi(digits):\n"
        "    return _gauss_legendre(digits)\n\n"
        "if __name__ == '__main__':\n"
        "    request = json.loads(Path('/resources/validation/data.json').read_text(encoding='utf-8'))\n"
        "    digits = request['digits']\n"
        "    print(json.dumps({'digits': digits, 'decimal': approximate_pi(digits)}, separators=(',', ':')))\n"
    )
    return source.encode("utf-8")


def _snapshot(store, *, id, kind, origin, revision, files, environment_ref, license_text):
    value = {
        "schema_version": "1.0.0", "id": id, "kind": kind, "origin": origin,
        "revision": revision,
        "files": [{"path": path, "artifact_ref": store.put_blob(raw, media_type=media),
                   "media_type": media, "audience": "authorized researcher"}
                  for path, raw, media in files],
        "access": "read-only", "license": license_text, "availability": "available",
        "environment_ref": environment_ref,
    }
    validate("resource-snapshot", value)
    return store.put_record("resource-snapshot", value)


def capture_pi_task(store, reference_directory, *, accepted_inputs=None):
    """Capture a complete, explicit Pi task and root-only scorer profile.

    `accepted_inputs`, when supplied, fills the three artifacts produced by the
    Builder: poc_manifest, poc_artifact_bundle, and build_receipt.
    """
    requirements_ref = store.put_blob(b"", media_type="text/plain")
    approval_ref = store.put_blob(json_bytes({
        "schema": "ai4r-pi-stdlib-environment-approval:1",
        "purpose": "Operator-authored Pi algorithm experiment; Python standard library only",
        "platform_fact": [platform.system(), platform.machine(), platform.python_version()],
        "network": "none", "gpu": False,
    }), media_type="application/json")
    lock = {
        "schema_version": "1.0.0", "id": "pi_stdlib_environment",
        "platform": platform.system().lower() + "-" + platform.machine().lower(),
        "requirements_ref": requirements_ref, "package_refs": [], "approval_ref": approval_ref,
    }
    validate("environment-lock", lock)
    lock_ref = store.put_record("environment-lock", lock)

    request_bytes = json_bytes({"schema": "ai4r-pi-cases:1", "digits": 100_000})
    request = validate_pi_request(request_bytes)
    validation_ref = _snapshot(store, id="pi_validation_resource", kind="public validation request",
        origin="Explicit operator-authored Pi protocol request; no hidden labels or answer are included",
        revision=hashlib.sha256(request_bytes).hexdigest(),
        files=[("data.json", request_bytes, "application/json")], environment_ref=lock_ref,
        license_text="Operator-authored protocol data")

    baseline_bytes = _baseline_source()
    baseline_ref = _snapshot(store, id="pi_baseline_resource", kind="immutable baseline implementation",
        origin="Captured standard-library Decimal Gauss-Legendre reference implementation",
        revision=hashlib.sha256(baseline_bytes).hexdigest(),
        files=[("baseline.py", baseline_bytes, "text/x-python")], environment_ref=lock_ref,
        license_text="First-party operator-authored baseline")

    # These provenance documents say exactly how the task was selected. They do
    # not claim search, screening, or prior scientific stages took place.
    brief_ref = store.put_blob(json_bytes({"schema": "ai4r-pi-task-provenance:1",
        "origin": "explicit_operator_assignment", "description": "Benchmark a candidate Python implementation of truncated decimal Pi",
        "prior_search_or_screening_claimed": False}))
    opportunity_ref = store.put_blob(json_bytes({"schema": "ai4r-pi-task-provenance:1",
        "origin": "explicit_operator_assignment", "selection": "fixed arithmetic benchmark",
        "prior_search_or_screening_claimed": False}))

    blueprint = {
        "schema_version": "2.0.0", "id": "hypothesis_blueprint",
        "brief_ref": brief_ref, "opportunity_ref": opportunity_ref,
        "claim": "The candidate computes truncated decimal Pi faster than the immutable Decimal Gauss-Legendre baseline at 100000 places.",
        "mechanism": "An alternative arithmetic algorithm or representation may reduce the work required to produce the requested decimal prefix.",
        "independent_variable": "Candidate implementation in poc_patch.py versus captured baseline.py",
        "dependent_variables": ["elapsed_s"],
        "baseline_identity": {"resource_ref": baseline_ref, "revision": hashlib.sha256(baseline_bytes).hexdigest(),
                              "entry_point": "baseline.py"},
        "validation_resource_ref": validation_ref,
        "resource_refs": [baseline_ref, validation_ref], "environment_ref": lock_ref,
        "metrics": [{"metric_id": "elapsed_s", "unit": "s",
            "measurement": "Protected executor wall time for producing and emitting the exact requested Pi prefix",
            "direction": "lower_better", "aggregation": "median", "target_id": None,
            "valid_min": 0, "valid_max": None}],
        "outcome_rules": [{"metric_id": "elapsed_s",
            "success": {"operand": "treatment", "comparator": "lt", "reference": "baseline", "factor": 1, "offset": 0},
            "falsification": {"operand": "treatment", "comparator": "ge", "reference": "baseline", "factor": 1, "offset": 0},
            "middle": "INCONCLUSIVE", "conditional_rule": None, "conditional_meaning": None}],
        "repeat_count": 5, "seed": 42, "seed_policy": "fixed_same_for_all_runs",
        "implementation_scope": {"poc_change_scope": ["Implement approximate_pi(digits) in poc_patch.py"],
            "must_not_change": ["baseline", "public_validation_request", "trusted_scoring_protocol", "benchmark_cases"],
            "max_patch_files": 1},
        "constraints": [], "verification_plan": [
            "Verify output schema and exact requested decimal length for every measured and unseen precision",
            "Verify decimal prefixes against the independently computed host-owned reference",
            "Compare five baseline and treatment timings at 10000 and 100000 places",
            "Check additional host-selected precisions and boundary requests at 0, 1, 2, and 17 places",
            "Preserve failed, incorrect, or slower outcomes without converting them into success"],
    }
    validate("hypothesis-blueprint", blueprint)
    blueprint_ref = store.put_record("hypothesis-blueprint", blueprint)

    # The private reference bytes/path and host-selected unseen digits stay in
    # this host return value; only the scorer receives them.
    from .trusted_pi import capture_pi_profile
    scoring_profile = capture_pi_profile(reference_directory, validation_ref)
    approved = [{"lock_ref": lock_ref, "approval_ref": approval_ref,
        "platform_fact": [platform.system(), platform.machine(), platform.python_version()],
        "wheel_filenames": {}}]

    builder_inputs = {"blueprint": blueprint_ref, "baseline_resource": baseline_ref,
        "validation_resource": validation_ref, "lock": lock_ref}
    benchmark_inputs = {"hypothesis_blueprint": blueprint_ref, "baseline_resource": baseline_ref,
        "validation_resource": validation_ref, "environment_lock": lock_ref,
        "poc_manifest": None, "poc_artifact_bundle": None, "build_receipt": None}
    if accepted_inputs is not None:
        if type(accepted_inputs) is not dict or set(accepted_inputs) != {"poc_manifest", "poc_artifact_bundle", "build_receipt"}:
            raise ValueError("accepted_inputs must contain the exact three accepted Builder artifacts")
        benchmark_inputs.update(accepted_inputs)
    return {"builder_inputs": builder_inputs, "benchmark_inputs": benchmark_inputs,
        "approved_environments": approved, "scoring_profile": scoring_profile,
        "provenance": "explicit operator assignment; no prior search or screening is represented"}
