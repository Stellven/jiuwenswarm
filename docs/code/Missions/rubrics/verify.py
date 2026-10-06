"""Recompute retained evidence and token arithmetic; never award product acceptance."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f"Path escapes its declared root: {relative}")
    return path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(assessment_path: Path, repo: Path) -> dict:
    assessment = read_json(assessment_path)
    checks = []

    def record(name, passed, detail):
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    folder = assessment_path.parent
    for item in assessment["artifacts"]:
        base = repo if item["root"] == "repository" else folder
        path = contained(base, item["path"])
        actual = digest(path) if path.is_file() else None
        record(f"artifact:{item['id']}", actual == item["sha256"], {"expected": item["sha256"], "actual": actual})

    for candidate in assessment["candidates"]:
        manifest = read_json(contained(repo, candidate["manifest"]))
        entries = manifest[candidate["file_key"]]
        mismatches = []
        for item in entries:
            path = contained(repo, item["path"])
            if not path.is_file() or digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
                mismatches.append(item["path"])
        record(f"candidate:{candidate['id']}", not mismatches and len(entries) == candidate["file_count"],
               {"files": len(entries), "mismatches": mismatches})
        if candidate.get("snapshot_rule") == "path-sha256-lines":
            value = "".join(f"{entry['path']}:{entry['sha256']}\n" for entry in entries)
            actual = hashlib.sha256(value.encode("utf-8")).hexdigest()
            record(f"snapshot:{candidate['id']}", actual == candidate["snapshot_sha256"], actual)

    for observation in assessment["junit"]:
        cases = ET.parse(contained(repo, observation["path"])).getroot().findall(".//testcase")
        failed = sum(any(case.find(tag) is not None for tag in ("failure", "error")) for case in cases)
        skipped = sum(case.find("skipped") is not None for case in cases)
        actual = {"collected": len(cases), "passed": len(cases) - failed - skipped, "failed": failed, "skipped": skipped}
        record(f"junit:{observation['id']}", actual == observation["counts"], actual)

    native = assessment["native_acceptance"]
    registry = read_json(contained(repo, native["registry"]))
    counts = Counter()
    rows_seen = set()
    for feature in registry["features"]:
        text = contained(repo, feature["feature_directory"] + "/tasks.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| \[(AC-\d+)\]\(spec\.md\) \|.*?\| (PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN|STALE|N/A) \|", text, re.M)
        expected_ids = {item["id"] for item in feature["acceptance"]}
        actual_ids = {ac for ac, _ in rows}
        record(f"native-rows:{feature['id']}", actual_ids == expected_ids and len(rows) == len(expected_ids),
               {"expected": len(expected_ids), "observed": len(rows)})
        for ac, status in rows:
            identity = (feature["id"], ac)
            if identity in rows_seen:
                raise ValueError(f"Duplicate native acceptance row: {identity}")
            rows_seen.add(identity)
            counts[status] += 1
    record("native-acceptance-counts", dict(counts) == native["counts"], dict(counts))

    readiness = read_json(contained(repo, assessment["readiness"]["path"]))
    actual_readiness = {
        "ready": readiness["readiness"]["ready"],
        "status": readiness["projection"]["status"],
        "real_provider_calls": readiness["real_provider_calls"],
        "characterization_not_run": readiness["characterization"]["all_not_run"],
        "characterization_observations": readiness["characterization"]["observations"],
    }
    record("retained-real-readiness", actual_readiness == assessment["readiness"]["expected"], actual_readiness)

    tokens = assessment["tokens"]
    audit = read_json(contained(folder, tokens["audit"]))
    ledger = read_json(contained(folder, tokens["ledger"]))
    fields = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")
    totals = {field: 0 for field in fields}
    session_totals = {}
    response_ids = set()
    for row in ledger["responses"]:
        if row["response_id"] in response_ids:
            raise ValueError(f"Duplicate token response ID: {row['response_id']}")
        response_ids.add(row["response_id"])
        if row["root_turn_id"] != tokens["root_turn_id"]:
            raise ValueError("Token row belongs to an excluded iteration")
        if not tokens["start_utc"] <= row["timestamp"] <= tokens["end_utc"]:
            raise ValueError("Token row falls outside the selected first-pass window")
        values = row["usage"]
        if any(type(values[field]) is not int or values[field] < 0 for field in fields):
            raise ValueError("Token counters must be nonnegative integers")
        if values["total_tokens"] != values["input_tokens"] + values["output_tokens"]:
            raise ValueError("Token total double-counts or omits a component")
        if values["cached_input_tokens"] > values["input_tokens"] or values["reasoning_output_tokens"] > values["output_tokens"]:
            raise ValueError("Token subset exceeds its containing counter")
        session = session_totals.setdefault(row["session_id"], {field: 0 for field in fields})
        for field in fields:
            totals[field] += values[field]
            session[field] += values[field]
    record("tokens:selected-responses", totals == tokens["totals"] == audit["totals"],
           {"responses": len(response_ids), "totals": totals, "sessions": session_totals})
    record("tokens:session-attribution", session_totals == audit["session_totals"], session_totals)
    record("tokens:coverage", len(response_ids) == audit["unique_response_count"] and audit["root_turn_id"] == tokens["root_turn_id"],
           {"unique_responses": len(response_ids), "root_turn_id": audit["root_turn_id"]})

    unknown = {"BLOCKED", "NOT_RUN", "UNKNOWN", "STALE"}
    incomplete = [item["id"] for item in assessment["quality_checks"] if item["required"] and item["status"] in unknown]
    record("score:no-unsupported-total", not incomplete or assessment["total_quality_score"] is None, {"unobserved_required_checks": incomplete})
    record("report:no-independent-audit-claim", assessment["review"]["external_independent_audit_performed"] is False,
           "This check validates the M0 disclosure only; it cannot determine actual reviewer independence.")
    passed = all(item["status"] == "PASS" for item in checks)
    return {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "assessment_sha256": digest(assessment_path),
        "verifier_sha256": digest(Path(__file__)),
        "result": "PASS" if passed else "FAIL",
        "meaning": "Evidence consistency only; no provider invocation, code-quality award, product acceptance or certification.",
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment", type=Path, default=Path(__file__).parent / "M0" / "assessment.json")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    try:
        report = verify(args.assessment.resolve(), args.repo_root.resolve())
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        report = {"result": "FAIL", "error": str(error), "meaning": "Evidence verification failed; no product verdict issued."}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
