"""Offline evidence assessment for the two-case Harbor compatibility pilot.

This module deliberately imports no app/client/Harbor code. It reads untrusted
bytes, never executes artifacts, and never equates a product verdict with truth.
The archive joins mirror the public collection contract, independently of the
producer's saved ``verified_members`` assertions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

MAX_JSON = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_MEMBER = 128 * 1024 * 1024
MAX_MEMBERS = 100000
MAX_TEXT = 4 * 1024 * 1024
TERMINAL = {"completed", "partial", "halted", "cancelled", "failed", "blocked", "interrupted"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non-finite JSON number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def safe_relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("unsafe evidence path")
    return value


def regular(root, relative):
    path = Path(root) / safe_relative(relative)
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("symlink evidence is forbidden")
    if not path.is_file():
        raise ValueError("required evidence file missing: " + relative)
    return path


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise ValueError("JSON evidence missing or oversized")
    return strict_json(path.read_bytes())


def fingerprint(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        while chunk := stream.read(65536):
            size += len(chunk)
            if size > MAX_TOTAL:
                raise ValueError("evidence exceeds finite byte policy")
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": size}


def check_fingerprint(path, record):
    if type(record.get("size")) is not int or record["size"] < 0:
        raise ValueError("invalid evidence byte count")
    if fingerprint(path) != {key: record[key] for key in ("sha256", "size")}:
        raise ValueError("evidence hash or byte count mismatch")


class Artifacts:
    """Verified original artifacts, with bounded text access and no extraction."""

    def __init__(self, folder, run, manifest):
        self.folder, self.run, self.manifest = Path(folder), run, manifest
        self.archive = None
        self.paths = {}
        self._validate()

    def _validate(self):
        source = self.manifest
        if (source.get("run_id") != self.run["app_run_id"]
                or source.get("audience") != "researcher" or source.get("execution_terminal") is not True):
            raise ValueError("collection scope or terminal execution differs")
        expected = hashlib.sha256(canonical({k: v for k, v in source.items() if k != "manifest_sha256"})).hexdigest()
        if source.get("manifest_sha256") != expected:
            raise ValueError("source collection manifest hash mismatch")
        confirmation = self.run.get("collection_confirmation", {})
        if (confirmation.get("status") != "confirmed" or confirmation.get("run_id") != source["run_id"]
                or confirmation.get("manifest_sha256") != expected or confirmation.get("audience") != "researcher"):
            raise ValueError("durable collection confirmation differs")
        source_rows = source.get("artifacts")
        if not isinstance(source_rows, list) or not source_rows or len(source_rows) > MAX_MEMBERS:
            raise ValueError("missing or oversized original artifact inventory")
        paths, identities, total = set(), set(), 0
        for row in source_rows:
            safe_relative(row["path"])
            if row["path"] in paths or row["artifact_id"] in identities:
                raise ValueError("duplicate source artifact path or identity")
            paths.add(row["path"]); identities.add(row["artifact_id"])
            if type(row["size"]) is not int or not 0 <= row["size"] <= MAX_MEMBER:
                raise ValueError("original artifact exceeds size policy")
            total += row["size"]
        if total > MAX_TOTAL:
            raise ValueError("original artifacts exceed total byte policy")
        retained = self.run.get("artifacts", [])
        if not isinstance(retained, list) or len(retained) > 4096:
            raise ValueError("retained physical artifact inventory exceeds policy")
        retained_paths = set()
        for row in retained:
            if row["path"] in retained_paths:
                raise ValueError("duplicate retained artifact path")
            retained_paths.add(row["path"])
            check_fingerprint(regular(self.folder, row["path"]), row)
        archive_rows = [r for r in retained if r.get("source") == "app_archive"]
        if archive_rows:
            if len(archive_rows) != 1:
                raise ValueError("ambiguous original archive")
            self._archive(regular(self.folder, archive_rows[0]["path"]))
        else:
            app_rows = {r.get("artifact_id"): r for r in retained if r.get("source") == "app"}
            if set(app_rows) != identities:
                raise ValueError("missing or extra downloaded original artifacts")
            for row in source_rows:
                saved = app_rows[row["artifact_id"]]
                if (saved["sha256"], saved["size"]) != (row["sha256"], row["size"]):
                    raise ValueError("downloaded original differs from app inventory")
                self.paths[row["path"]] = (regular(self.folder, saved["path"]), None)

    def _archive(self, path):
        with path.open("rb") as stream:
            footer = zipfile._EndRecData(stream)
        if (footer is None or footer[zipfile._ECD_ENTRIES_TOTAL] > MAX_MEMBERS + 1
                or footer[zipfile._ECD_SIZE] > 32 * 1024 * 1024):
            raise ValueError("archive metadata exceeds finite policy")
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = set()
            for entry in entries:
                safe_relative(entry.filename)
                mode = entry.external_attr >> 16
                if (entry.filename in names or entry.is_dir() or entry.flag_bits & 1
                        or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
                        or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                        or entry.file_size > (MAX_JSON if entry.filename == "client_retrieval.json" else MAX_MEMBER)):
                    raise ValueError("unsafe or oversized archive member")
                names.add(entry.filename)
            retrieval = strict_json(archive.read("client_retrieval.json"))
            if retrieval.get("run_id") != self.run["app_run_id"] or retrieval.get("audience") != "researcher":
                raise ValueError("archive retrieval scope differs")
            files = retrieval["files"]
            if (len(files) != len(self.manifest["artifacts"]) or len(entries) != len(files) + 1
                    or len({f["path"] for f in files}) != len(files)
                    or {f["path"] for f in files} != names - {"client_retrieval.json"}):
                raise ValueError("archive original inventory differs")
            actual_refs = {(f["artifact_ref"]["id"], f["artifact_ref"]["sha256"]) for f in files}
            if actual_refs != {(r["id"], r["sha256"]) for r in retrieval["artifact_refs"]}:
                raise ValueError("archive allowed refs differ")
            candidates = defaultdict(dict)
            actual = Counter()
            by_identity = {}
            total = 0
            verified = []
            for row in files:
                if row["audience"] != "researcher":
                    raise ValueError("archive file audience differs")
                ref = row["artifact_ref"]
                candidates[(ref["sha256"], row["media_type"])][ref["id"]] = ref
                digest, size = hashlib.sha256(), 0
                with archive.open(row["path"]) as stream:
                    while chunk := stream.read(65536):
                        size += len(chunk); total += len(chunk)
                        if size > MAX_MEMBER or total > MAX_TOTAL:
                            raise ValueError("archive expanded bytes exceed policy")
                        digest.update(chunk)
                if digest.hexdigest() != ref["sha256"]:
                    raise ValueError("original archive member hash mismatch")
                identity = (ref["id"], ref["sha256"], row["media_type"], size)
                actual[identity] += 1
                by_identity[identity] = row["path"]
                verified.append({"path": row["path"], "sha256": ref["sha256"], "size": size, "media_type": row["media_type"]})
            expected = Counter()
            for row in self.manifest["artifacts"]:
                refs = [ref for ref in candidates[(row["sha256"], row["media_type"])].values()
                        if hashlib.sha256(canonical([row["path"], ref])).hexdigest() == row["artifact_id"]]
                if len(refs) != 1:
                    raise ValueError("original reference identity differs")
                identity = (refs[0]["id"], row["sha256"], row["media_type"], row["size"])
                expected[identity] += 1
                self.paths[row["path"]] = (path, by_identity.get(identity))
            if actual != expected:
                raise ValueError("original identity/media/size multiplicity differs")
            inventory_rows = [r for r in self.run["artifacts"] if r.get("source") == "app_archive_inventory"]
            if len(inventory_rows) != 1:
                raise ValueError("saved archive inventory missing or ambiguous")
            inventory = read_json(regular(self.folder, inventory_rows[0]["path"]))
            if (inventory.get("run_id") != self.run["app_run_id"] or inventory.get("audience") != "researcher"
                    or inventory.get("source_manifest_sha256") != self.manifest["manifest_sha256"]
                    or inventory.get("client_retrieval") != retrieval
                    or inventory.get("total_uncompressed_bytes") != total
                    or inventory.get("verified_members") != verified):
                raise ValueError("retained archive inventory disagrees with independently verified bytes")

    def bytes(self, name):
        safe_relative(name)
        if name not in self.paths:
            return None
        path, member = self.paths[name]
        if member is None:
            if path.stat().st_size > MAX_TEXT:
                raise ValueError("assessment text exceeds size policy")
            raw = path.read_bytes()
        else:
            with zipfile.ZipFile(path) as archive:
                if archive.getinfo(member).file_size > MAX_TEXT:
                    raise ValueError("assessment text exceeds size policy")
                raw = archive.read(member)
        return raw

    def text(self, name):
        raw = self.bytes(name)
        return raw.decode("utf-8-sig") if raw is not None else None


def _csv(raw, id_column, label_column):
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames != [id_column, label_column]:
        raise ValueError("predictions/labels require exact ID and label columns")
    result = {}
    for row in reader:
        if None in row or not row[id_column] or row[id_column] in result or row[label_column] not in {"0", "1"}:
            raise ValueError("invalid or duplicate prediction/label row")
        result[row[id_column]] = row[label_column]
    if not result:
        raise ValueError("empty prediction/label data")
    return result


def scientific(artifacts, criteria, criteria_root, completed):
    if not completed:
        return {"status": "not_scored", "reason": "product execution did not complete", "task_success": False}
    if criteria["case_id"] == "paper":
        rubric = criteria.get("paper", {})
        text = artifacts.text(rubric.get("artifact_path", "paper_summary.md"))
        if text is None:
            return {"status": "missing_required_output", "task_success": False}
        checks = [{"id": row["id"], "passed": any(re.search(pattern, text, re.I) is not None for pattern in row["patterns"])}
                  for row in rubric.get("checks", [])]
        return {"status": "human_review_required", "task_success": None,
                "limited_checks": checks, "limited_checks_passed": bool(checks) and all(r["passed"] for r in checks),
                "scope": "Numeric/reference presence only; source fidelity and scientific interpretation need independent human review."}
    rubric = criteria.get("cpu", {})
    prediction = artifacts.text(rubric.get("prediction_path", "predictions.csv"))
    if prediction is None:
        return {"status": "missing_required_output", "task_success": False}
    truth_path = regular(criteria_root, rubric["labels_path"])
    if truth_path.stat().st_size > MAX_TEXT:
        raise ValueError("protected labels exceed size policy")
    id_column = rubric.get("id_column", "id")
    truth = _csv(truth_path.read_text(encoding="utf-8-sig"), id_column, rubric.get("label_column", "label"))
    predicted = _csv(prediction, id_column, rubric.get("prediction_column", "label"))
    if set(truth) != set(predicted):
        raise ValueError("predictions must cover each blind test ID exactly once")
    correct = sum(predicted[key] == value for key, value in truth.items())
    result = {"status": "human_review_required", "correct": correct, "sample_count": len(truth),
              "accuracy": correct / len(truth), "task_success": None,
              "scope": "Independent accuracy arithmetic; training method, baseline fairness, and conclusion require review."}
    baseline = rubric.get("baseline_accuracy")
    if baseline is not None:
        if type(baseline) not in (int, float) or not 0 <= baseline <= 1:
            raise ValueError("invalid frozen baseline accuracy")
        result["reference_accuracy_gap"] = result["accuracy"] - baseline
        result["reference_threshold_met"] = result["reference_accuracy_gap"] >= rubric.get("min_accuracy_gain", 0.05)
    return result


def assess(evidence, criteria, *, criteria_root=None):
    root = Path(evidence)
    assessment = {"schema": "ai4r-harbor-assessment:1", "case_id": criteria.get("case_id"),
                  "success": False, "evidence_integrity": False, "live_integration": False,
                  "attempts": [], "errors": [], "scheduled_attempt_count": 0,
                  "scientific_assessment": {"status": "not_scored", "task_success": False}}
    try:
        if criteria.get("schema") != "ai4r-harbor-criteria:1" or criteria.get("case_id") not in {"cpu", "paper"}:
            raise ValueError("unsupported protected criteria")
        receipt = read_json(regular(root, "pilot-receipt.json"))
        if receipt.get("schema") != "ai4r-harbor-receipt:1" or receipt.get("case_id") != criteria["case_id"]:
            raise ValueError("adapter receipt case differs")
        custody = receipt.get("custody")
        if custody not in criteria.get("allowed_custody", ["live"]):
            raise ValueError("evidence custody is not allowed for this assessment")
        assessment["custody"] = custody
        campaign = read_json(regular(root, "campaign.json"))
        if campaign.get("schema_version") != "sequential-campaign:1" or campaign.get("campaign_id") != receipt.get("campaign_id"):
            raise ValueError("campaign identity differs from adapter receipt")
        if (not isinstance(campaign.get("cases"), list) or not campaign["cases"]
                or len({row["id"] for row in campaign["cases"]}) != len(campaign["cases"])
                or any(type(row.get("repeats")) is not int or not 1 <= row["repeats"] <= 1000 for row in campaign["cases"])):
            raise ValueError("invalid scheduled case identities or repeat counts")
        expected = {row["id"] + "-r" + str(repeat): row["id"]
                    for row in campaign["cases"] for repeat in range(1, row["repeats"] + 1)}
        assessment["scheduled_attempt_count"] = len(expected)
        observed = {path.parent.name for path in (root / "runs").glob("*/run_record.json")}
        if not expected or observed != set(expected):
            raise ValueError("scheduled attempt inventory differs; attempts must not be dropped")
        desired_id = criteria.get("runner_case_id", "case1-cpu" if criteria["case_id"] == "cpu" else "case3-paper")
        selected = []
        for ident, case_id in expected.items():
            folder = root / "runs" / ident
            row = read_json(regular(root, "runs/" + ident + "/run_record.json"))
            attempt = {key: row.get(key) for key in ("run_id", "request_id", "app_run_id", "case_id", "execution_state", "collection_state")}
            assessment["attempts"].append(attempt)
            if (row.get("campaign_id"), row.get("case_id"), row.get("run_id")) != (campaign["campaign_id"], case_id, ident):
                raise ValueError("run identity differs from frozen schedule")
            for event in row.get("observations", {}).get("event_files", []):
                check_fingerprint(regular(folder, event["path"]), event)
            status = row.get("status") or {}
            if (row.get("execution_state") not in TERMINAL or row.get("collection_state") != "complete"
                    or status.get("status") != row["execution_state"] or status.get("run_id") != row.get("app_run_id")
                    or status.get("client_request_id") != row.get("request_id")):
                raise ValueError("execution or collection is unresolved or not independently terminal")
            store = Artifacts(folder, row, read_json(regular(folder, "collection_manifest.json")))
            attempt["evidence_integrity"] = True
            if case_id == desired_id:
                selected.append((row, store))
        if len(selected) != 1:
            raise ValueError("pilot requires one exact selected case attempt")
        row, store = selected[0]
        for key in ("app_run_id", "request_id", "execution_state", "collection_state"):
            if receipt.get(key) != row.get(key):
                raise ValueError("adapter receipt differs from original run")
        if receipt.get("terminal_confirmed") is not True or receipt.get("evidence_complete") is not True:
            raise ValueError("adapter did not confirm terminal complete collection")
        inventory = receipt.get("inventory_ref")
        if not isinstance(inventory, str):
            raise ValueError("fresh host inventory reference missing")
        inventory_record = read_json(regular(root, inventory))
        if not inventory_record.get("captured_at"):
            raise ValueError("inventory timestamp missing")
        assessment.update(success=True, evidence_integrity=True, live_integration=custody == "live",
                          execution_completed=row["execution_state"] == "completed")
        assessment["scientific_assessment"] = scientific(store, criteria, criteria_root or root, assessment["execution_completed"])
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile, RuntimeError, RecursionError) as error:
        assessment.update(success=False, evidence_integrity=False, live_integration=False, execution_completed=False)
        assessment["errors"].append(str(error))
    assessment["observed_attempt_count"] = len(assessment["attempts"])
    return assessment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--criteria", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    criteria = read_json(args.criteria)
    result = assess(args.evidence, criteria, criteria_root=args.criteria.parent)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "assessment.json").write_bytes(canonical(result))
    reward = {"evidence_integrity": float(result["evidence_integrity"]),
              "live_integration": float(result["live_integration"]),
              "execution_completed": float(result.get("execution_completed", False))}
    (args.output / "reward.json").write_bytes(canonical(reward))
    print(json.dumps({"success": result["success"], "custody": result.get("custody"), "errors": result["errors"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
