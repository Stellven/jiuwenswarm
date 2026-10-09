"""Copy exact observable native runtime counters into the trial accounting input.

Failed invocations remain records with unknown counters. No token estimates or
credentials are read. Re-running deduplicates by captured invocation identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def harvest(evidence_root: Path, destination: Path):
    records = {}
    for path in sorted(evidence_root.glob("live-*/**/*_Invocation_Observation.json")):
        observation = json.loads(path.read_text(encoding="utf-8"))
        if observation.get("model_calls") != 1 or not observation.get("observed_runtime"):
            continue
        raw_path = path.with_name(path.name.replace("_Invocation_Observation.json", "_Raw_Response.txt"))
        native = {}
        if raw_path.is_file():
            for line in raw_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "turn.completed":
                    native = event.get("usage") or {}
        def counter(value):
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        incoming = counter(observation["usage"].get("input_tokens"))
        outgoing = counter(observation["usage"].get("output_tokens"))
        usage = {"input_tokens": incoming, "cached_input_tokens": counter(native.get("cached_input_tokens")),
                 "output_tokens": outgoing, "reasoning_output_tokens": counter(native.get("reasoning_output_tokens")),
                 "total_tokens": incoming + outgoing if incoming is not None and outgoing is not None else None}
        evidence = {"observation_path": str(path.resolve()), "observation_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "native_stdout_path": str(raw_path.resolve()),
                    "native_stdout_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.is_file() else None,
                    "outcome": observation["outcome"], "model_identity": observation["model_identity"],
                    "limitation": "Native input/output/cache counters when reported; reasoning, billing and served identity may be unavailable"}
        record = {"call_id": observation["id"], "model": observation["model_identity"].get("effective"),
                  "usage": usage, "evidence": evidence}
        if record["call_id"] in records and records[record["call_id"]] != record:
            raise ValueError("Conflicting immutable runtime invocation evidence")
        records[record["call_id"]] = record
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for _, value in sorted(records.items())), encoding="utf-8")
    print(json.dumps({"runtime_invocations": len(records), "usage_available_invocations": sum(r["usage"]["total_tokens"] is not None for r in records.values()),
                      "output": str(destination)}))
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    harvest(args.evidence_root, args.destination)
