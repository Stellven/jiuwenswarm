"""Protected consumption of observed definition checks, never model verdicts."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .bridge import _safe_path
from .common import GovernanceError, sha256_bytes


def validate_admission_receipt(path, pins):
    """Require retained, exact definition checks and a separate scoped review.

    The trusted local operator supplies this file. It has no HTTP setter, does
    not certify model fidelity, and cannot authorize a runtime gate decision.
    """
    if path is None:
        raise GovernanceError("admission_evidence_missing", "Observed definition check and review evidence is required.")
    path = _safe_path(path)
    try:
        raw = path.read_bytes()
        if len(raw) > 131072:
            raise ValueError()
        receipt = json.loads(raw)
        required = {"schema_revision", "scope", "pins", "checks", "independent_review"}
        if not isinstance(receipt, dict) or set(receipt) != required or receipt["schema_revision"] != "definition-admission-r2":
            raise ValueError()
        if receipt["scope"] != "provisional-definition-eligibility; not connected trial acceptance":
            raise ValueError()
        expected = {role: pin.decl_hash for role, pin in pins.items()}
        if receipt["pins"] != expected:
            raise GovernanceError("admission_evidence_stale", "Definition evidence belongs to different implementation pins.")
        references = []
        def read_reference(reference):
            if set(reference) != {"path", "sha256"}:
                raise ValueError()
            target = _safe_path(path.parent / reference["path"])
            if not target.is_relative_to(path.parent) or not target.is_file():
                raise ValueError()
            content = target.read_bytes()
            if len(content) > 16777216 or sha256_bytes(content) != reference["sha256"]:
                raise GovernanceError("admission_evidence_stale", "Retained definition evidence changed.")
            references.append({"ref": target.name, "sha256": reference["sha256"]})
            return content
        checks = receipt["checks"]
        if set(checks) != {"junit", "required_cases"} or not checks["required_cases"]:
            raise ValueError()
        report = ET.fromstring(read_reference(checks["junit"]))
        cases = list(report.iter("testcase"))
        observed = {case.get("classname", "") + "::" + case.get("name", "") for case in cases}
        if not cases or any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
            raise GovernanceError("admission_checks_failed", "Definition checks contain failures, errors, skips or no cases.")
        required_cases = checks["required_cases"]
        if (not isinstance(required_cases, list) or any(not isinstance(item, str) for item in required_cases)
                or len(set(required_cases)) != len(required_cases) or not set(required_cases) <= observed):
            raise GovernanceError("admission_checks_missing", "Required definition self-tests were not observed.")
        # Each of these obligations needs an independently asserted test group.
        for group in ("test_m0_003", "test_intent_compiler", "test_m0_007"):
            if not any(group + "::" in case for case in required_cases):
                raise GovernanceError("admission_checks_missing", "Declaration, intent contract and protected profile checks are required.")
        review = json.loads(read_reference(receipt["independent_review"]))
        if (not isinstance(review, dict) or set(review) != {"schema_revision", "pins", "source", "observations", "result", "limitations"}
                or review["schema_revision"] != "definition-review-r2" or review["pins"] != expected
                or review["source"] != "independently scoped code and source assessment" or review["result"] != "PASS"):
            raise GovernanceError("admission_review_missing", "Independent scoped definition review is incomplete.")
        obligations = {"two_cc_scope", "closure_and_provenance", "typed_contracts", "protected_fidelity_rubric", "upstream_adaptation", "no_gate_authority"}
        observations = review["observations"]
        if (not isinstance(observations, list) or any(not isinstance(o, dict) for o in observations)
                or {o.get("obligation") for o in observations} != obligations
                or len(observations) != len(obligations)
                or any(o.get("result") != "PASS" or not isinstance(o.get("reason"), str) or not o["reason"].strip()
                       for o in observations)):
            raise GovernanceError("admission_review_missing", "Every scoped definition-review obligation needs retained reasons.")
        return {"ready": True, "scope": receipt["scope"], "receipt_sha256": sha256_bytes(raw),
                "evidence_refs": [{"ref": path.name, "sha256": sha256_bytes(raw)}, *references],
                "observed_cases": len(cases), "limitations": review["limitations"]}
    except GovernanceError:
        raise
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        raise GovernanceError("admission_evidence_invalid", "Definition admission evidence is unreadable or malformed.") from exc
