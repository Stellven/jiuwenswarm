"""Read-only joins over original product export bytes for paired reporting.

Counts the entire exported pipeline, including compiler/planner and every shared
verifier. Observation.model_calls is never summed: parent/child observations can
overlap. This does not grade content, infer unreported money, or establish E3.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

_CALL = re.compile(r"evidence/model-call-[0-9a-f]{64}\.json\Z")
_OBSERVATION = re.compile(r"evidence/invocation-observation-[0-9a-f]{64}\.json\Z")


def _json(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError("Duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def _ref_key(ref):
    if not isinstance(ref, dict) or set(ref) != {"id", "sha256"}:
        raise ValueError("Expected original id/SHA256 Ref")
    if not isinstance(ref["id"], str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
        raise ValueError("Invalid original Ref")
    return ref["id"], ref["sha256"]


def _sum_reported(calls, field):
    values = [(call.get("usage") or {}).get(field) for call in calls]
    reported = [value for value in values if type(value) in (int, float) and value >= 0]
    return {"total": sum(reported) if len(reported) == len(values) else None,
            "reported_calls": len(reported), "missing_calls": len(values) - len(reported)}


def audit_archive(path, *, expected_run_id=None, max_uncompressed_bytes=2 * 1024**3):
    path = Path(path)
    source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member names")
        if sum(member.file_size for member in members) > max_uncompressed_bytes:
            raise ValueError("Export exceeds explicit uncompressed byte bound")
        for name in names:
            logical = PurePosixPath(name)
            if logical.is_absolute() or ".." in logical.parts or "\\" in name or str(logical) != name:
                raise ValueError("Noncanonical ZIP member path")
        retrieval = _json(archive.read("client_retrieval.json"))
        run_id = retrieval["run_id"]
        if expected_run_id is not None and run_id != expected_run_id:
            raise ValueError("Export belongs to another run")
        by_path, by_ref = {}, {}
        for item in retrieval["files"]:
            member = item["path"]
            if member in by_path:
                raise ValueError("Duplicate retrieval inventory path")
            key = _ref_key(item["artifact_ref"])
            raw = archive.read(member)
            if hashlib.sha256(raw).hexdigest() != key[1]:
                raise ValueError("Original export bytes differ from Ref: " + member)
            by_path[member] = item["artifact_ref"]
            by_ref.setdefault(key, []).append(member)
        if set(names) != set(by_path) | {"client_retrieval.json"}:
            raise ValueError("ZIP population differs from declared retrieval inventory")
        calls = []
        call_refs = {}
        for name in sorted(by_path):
            if not _CALL.fullmatch(name):
                continue
            call = _json(archive.read(name))
            if call["id"] in call_refs:
                raise ValueError("Duplicate actual model-call identity")
            call_refs[call["id"]] = by_path[name]
            calls.append(call)
        observations = []
        joined_calls = set()
        missing_outputs = []
        for name in sorted(by_path):
            if not _OBSERVATION.fullmatch(name):
                continue
            observed = _json(archive.read(name))
            if observed["run_id"] != run_id:
                raise ValueError("Invocation observation belongs to another run")
            related = []
            for ref in observed.get("trace_refs", []):
                if ref["id"] in call_refs:
                    if ref != call_refs[ref["id"]]:
                        raise ValueError("Invocation/model-call exact Ref mismatch")
                    related.append(ref)
                    joined_calls.add(ref["id"])
            outputs = []
            for ref in observed["output_refs"]:
                paths = by_ref.get(_ref_key(ref), [])
                if not paths:
                    missing_outputs.append({"observation_ref": by_path[name], "output_ref": ref})
                outputs.append({"ref": ref, "archive_paths": paths})
            observations.append({"observation_ref": by_path[name], "node_id": observed["node_id"],
                "subnode_id": observed["subnode_id"], "cc_name": observed["cc_name"],
                "outcome": observed["outcome"], "model_call_refs": related, "output_refs": outputs})
        functions = Counter(call.get("call_function", "unreported") for call in calls)
        return {"schema": "ai4r-value-product-evidence-audit:1", "archive_sha256": source_sha,
            "run_id": run_id, "verified_members": len(by_path), "scope": "whole_exported_pipeline",
            "model_calls": len(calls), "call_functions": dict(functions),
            "call_outcomes": dict(Counter(call["outcome"] for call in calls)),
            "usage": {field: _sum_reported(calls, field) for field in
                      ("input_tokens", "output_tokens", "cost_amount")},
            "all_model_calls_joined": joined_calls == set(call_refs),
            "unjoined_call_ids": sorted(set(call_refs) - joined_calls),
            "missing_output_refs": missing_outputs, "invocations": observations,
            "original_model_calls": calls, "content_grade": None,
            "limitations": "Exact exported bytes and provenance joins only. Effort needs original wire evidence. No E3 or scientific acceptance claim."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    print(json.dumps(audit_archive(args.archive, expected_run_id=args.run_id), ensure_ascii=False))


if __name__ == "__main__":
    main()
