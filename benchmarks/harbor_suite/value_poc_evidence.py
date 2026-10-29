"""Read-only POC evidence projection; never dispatches or grades prose.

Original product archive custody and native broker joins reuse existing strict
auditors. Receipt discovery is an inventory, not proof of scientific completion.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from .value_product_evidence import audit_archive
from .value_trace_identity import project_archive
from .value_pair import native_evidence


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def response_labels(case_id, primitive_grade):
    """Display pinned V1 predicates without calling an honest halt a PoC."""
    value = dict(primitive_grade)
    valid = value.pop("valid_completion", None)
    value["valid_response"] = valid
    if case_id == "poc-002":
        value["correct_impossibility_handling"] = valid
        value["usable_scientific_completion"] = False
    elif case_id == "poc-001":
        value["correct_impossibility_handling"] = None
        value["usable_scientific_completion"] = valid
    else:
        raise ValueError(case_id)
    value["pinned_primitive_predicate_unchanged"] = True
    return value


def receipt_inventory(rows):
    """Deduplicate same original receipt IDs; reject conflicting identities.

    rows=(location, original JSON bytes). No absent receipt population is zero.
    Only exact scientific schema markers count; arbitrary 'metrics' do not.
    """
    schemas = {"ai4r-classification-scoring-receipt:1": "scoring",
               "urn:ai4r:prediction-build-receipt:2.0.0": "build"}
    found, identities = [], {}
    for location, raw in rows:
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(record, dict):
            continue
        kind = schemas.get(record.get("schema"))
        # Product artifact IDs below are schema-local constants, not global
        # identities; use original-byte digest when preserving multiple attempts.
        if record.get("id") == "build_receipt" and record.get("schema_version") in {"2.0.0", "3.0.0", "4.0.0"} and "readiness" in record:
            kind = "build"
        elif record.get("id") == "execution_receipt" and record.get("schema_version") == "1.0.0" and "blueprint_ref" in record:
            kind = "execution"
        elif record.get("id") == "empirical_results" and record.get("schema_version") == "2.0.0" and isinstance(record.get("runs"), list):
            kind = "empirical"
        if kind is None:
            continue
        identity = record.get("id")
        if not isinstance(identity, str) or not identity:
            raise ValueError("Scientific receipt lacks original identity")
        digest = _sha(raw)
        key = (kind, identity if kind == "scoring" else digest)
        if key in identities:
            previous = identities[key]
            if previous["sha256"] != digest:
                raise ValueError("Conflicting scientific receipt identity")
            previous["locations"].append(location)
            continue
        row = {"kind": kind, "id": identity, "sha256": digest,
               "locations": [location], "original_record": record}
        identities[key] = row
        found.append(row)
    scores = [row for row in found if row["kind"] == "scoring"]
    jobs = [row["original_record"].get("job_id") for row in scores]
    if scores and (None in jobs or len(set(jobs)) != len(jobs)):
        raise ValueError("Scoring receipts duplicate or omit job identities")
    return {"original_receipts": found, "unique_scoring_receipts_observed": len(scores) if scores else None,
            "scientific_runs_complete": None,
            "limitation": "Inventory only; absent receipts unknown. Receipt identity/execution/build/score closure still requires source-linked review."}


def product(archive, *, expected_run_id=None, model="gpt-6.1-sol", effort="medium"):
    audit = audit_archive(archive, expected_run_id=expected_run_id)
    identity = project_archive(archive, expected_model=model, expected_effort=effort)
    if identity["source_archive"]["sha256"] != audit["archive_sha256"]:
        raise ValueError("Product provenance auditors disagree on archive identity")
    if set(identity["projection"]["expected_call_ids"]) != {r["id"] for r in audit["original_model_calls"]}:
        raise ValueError("Original model-call populations differ")
    with zipfile.ZipFile(archive) as zf:
        rows = [(name, zf.read(name)) for name in zf.namelist() if name.endswith(".json")]
    bundles = []
    for name, raw in rows:
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict) and value.get("run_id") == audit["run_id"] and all(k in value for k in ("gate_decisions", "node_dispatches", "missing_evidence")):
            dispatches, gates = value["node_dispatches"], value["gate_decisions"]
            bundles.append({"location": name, "sha256": _sha(raw), "original_record": value,
                            "snapshot_facts": {
                                "node_dispatch_count": len(dispatches),
                                "node_ids_dispatched": [r["node_id"] for r in dispatches],
                                "advancing_node_gate_count": sum(r.get("scope_kind") == "node" and r.get("action") == "advance" for r in gates),
                                "gate_decision_count": len(gates),
                                "status": value.get("status"),
                                "do_not_sum_across_snapshots": True}})
    return {"arm": "cc", "original_archive": str(Path(archive).resolve()),
            "audit": audit, "identity": identity, "run_bundles": bundles,
            "science": receipt_inventory(rows), "content_judgment": None,
            "failed_stage": None, "honest_halt": None,
            "notes": "Inspect exact bundle dispatch/gate records; no stage completion inferred from invocation alone. Multiple bundle snapshots are not summed."}


def native(run, broker, *, measurement=None, model="gpt-6.1-sol"):
    joined, sources = native_evidence(run, broker, expected_model=model)
    run = Path(run)
    result_path = run / "result.json"
    result_raw = result_path.read_bytes()
    rows = []
    if measurement:
        root = Path(measurement)
        paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
        rows = [(str(p.resolve()), p.read_bytes()) for p in paths]
    return {"arm": "native", "joined_model_evidence": joined,
            "source_files": [{"path": str(p.resolve()), "sha256": _sha(p.read_bytes())} for p in sources],
            "original_result": {"path": str(result_path.resolve()), "sha256": _sha(result_raw), "record": json.loads(result_raw)},
            "measurement_files": [{"path": path, "sha256": _sha(raw)} for path, raw in rows],
            "science": receipt_inventory(rows), "content_judgment": None,
            "limitation": "Measurement responses may wrap receipts. Preserve source files; no six-run inference from a response count or aggregate accuracy. Frozen build SHA must join original measurement inputs."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="arm", required=True)
    cc = sub.add_parser("cc")
    cc.add_argument("archive")
    cc.add_argument("--run-id")
    nt = sub.add_parser("native")
    nt.add_argument("run")
    nt.add_argument("broker")
    nt.add_argument("--measurement")
    for p in (cc, nt):
        p.add_argument("--model", default="gpt-6.1-sol")
        p.add_argument("--output", required=True)
    args = parser.parse_args()
    destination = Path(args.output)
    if destination.exists():
        raise FileExistsError("Append-only evidence: choose a new output path")
    value = product(args.archive, expected_run_id=args.run_id, model=args.model) if args.arm == "cc" else native(args.run, args.broker, measurement=args.measurement, model=args.model)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
    print(str(destination.resolve()))


if __name__ == "__main__":
    main()
