"""Freeze the supplied CPU and paper demos into two isolated Harbor tasks.

The generated bundle contains protected verifier material. Only each task's
``environment/`` directory is the agent image build context. Never mount or
upload the whole bundle into AI4Research or an evaluated agent environment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

from jiuwenswarm.research_sidecar.sequential_cases import load_cases, validate_cases


CASE_SOURCES = {
    "cpu": "cases/demos-20261023/case1-cpu.json",
    "paper": "cases/demos-20261023/case3-paper.json",
}
ADAPTER = "benchmarks.harbor_pilot.adapter:AI4ResearchAgent"
IMAGE_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:\-]*@sha256:[a-f0-9]{64}$")
MAX_SOURCE_BYTES = 128 * 1024 * 1024


def _regular(path: Path, *, limit: int = MAX_SOURCE_BYTES) -> bytes:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink source paths are not permitted")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("bounded regular source file required: " + str(path))
    return path.read_bytes()


def _relative(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("safe relative fixture path required")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} or ":" in part for part in path.parts):
        raise ValueError("safe relative fixture path required")
    return Path(*path.parts)


def _json(raw: bytes) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field: " + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def _encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _pin(raw: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _task_toml(case_id: str, deadline: float) -> bytes:
    # These sandboxes carry only exported evidence; the application and its
    # model calls remain on the separately pinned, authenticated product host.
    return f'''schema_version = "1.4"
artifacts = ["/app/ai4r-evidence"]

[metadata]
case_id = "{case_id}"
purpose = "AI4Research Harbor compatibility pilot; not full benchmark acceptance"

[agent]
timeout_sec = {float(deadline) + 180.0}

[environment]
cpus = 1
memory_mb = 256
storage_mb = 2048
network_mode = "no-network"

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[verifier.environment]
cpus = 1
memory_mb = 512
storage_mb = 2048
network_mode = "no-network"
'''.encode("utf-8")


def prepare_bundle(
    sample_root: Path | str,
    destination: Path | str,
    *,
    criteria_root: Path | str,
    python_image: str,
    harbor_version: str,
    grader: Path | str | None = None,
) -> dict[str, Any]:
    """Create a new complete bundle; refuse an existing destination.

    ``criteria_root`` is referee-owned preparation material containing exactly
    the selected cpu.json/paper.json criteria and any explicitly named CPU
    labels file. It is never an input mount or an agent build context.
    """
    sample_root = Path(sample_root).absolute()
    criteria_root = Path(criteria_root).absolute()
    destination = Path(destination).absolute()
    if not IMAGE_PIN.fullmatch(python_image):
        raise ValueError("python image must be pinned by lowercase SHA-256 digest")
    if not isinstance(harbor_version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,79}", harbor_version):
        raise ValueError("explicit installed Harbor version required")
    if destination.exists() or any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("new non-symlink destination required; existing bundles are immutable")
    if not destination.parent.is_dir():
        raise ValueError("destination parent must exist")
    for source_root in (sample_root, criteria_root):
        resolved = source_root.resolve(strict=True)
        target = destination.resolve()
        if target == resolved or target.is_relative_to(resolved) or resolved.is_relative_to(target):
            raise ValueError("destination must be separate from sample and criteria roots")
    grader_path = Path(grader) if grader is not None else Path(__file__).with_name("grade.py")
    grader_bytes = _regular(grader_path.absolute(), limit=1024 * 1024)

    # Validate and gather every byte before publishing the new bundle. In
    # particular, a missing label or invalid case must not leave a usable job.
    payloads: dict[str, bytes] = {}
    protected_paths: set[str] = set()
    provenance: dict[str, Any] = {}
    for case_id, source_name in CASE_SOURCES.items():
        source_path = sample_root / source_name
        source_bytes = _regular(source_path, limit=16 * 1024 * 1024)
        document = load_cases(source_path)
        if len(document["cases"]) != 1:
            raise ValueError("each demo source must contain exactly one case")
        case = document["cases"][0]
        public_inputs = [row for row in case["inputs"] if row["upload"]]
        if not public_inputs:
            raise ValueError("demo must have explicit public inputs")
        case = {
            **case,
            "inputs": public_inputs,
            "setup": [],
            "steps": [],
            "collection": [],
            "repeats": 1,
        }
        visible = validate_cases({
            "schema_version": "sequential-cases:1", "policy": "stop",
            "limits": document["limits"], "cases": [case],
        })
        case_name = f"cases/{case_id}.json"
        payloads[case_name] = _encode(visible)
        source_inputs = {}
        for row in public_inputs:
            name = "inputs/" + row["path"]
            raw = _regular(sample_root / "inputs" / _relative(row["path"]))
            if name in payloads and payloads[name] != raw:
                raise ValueError("conflicting public fixture paths")
            payloads[name] = raw
            source_inputs[row["path"]] = _pin(raw)

        task_root = f"tasks/{case_id}"
        instruction = f"AI4R_HARBOR_CASE: {case_id}\n\n{case['task']}\n"
        payloads[task_root + "/instruction.md"] = instruction.encode("utf-8")
        payloads[task_root + "/task.toml"] = _task_toml(case_id, case["limits"]["deadline_s"])
        payloads[task_root + "/environment/Dockerfile"] = (
            f"FROM {python_image}\nWORKDIR /app\n"
        ).encode("utf-8")
        payloads[task_root + "/environment/.dockerignore"] = b"*\n!Dockerfile\n!.dockerignore\n"
        criteria_bytes = _regular(criteria_root / (case_id + ".json"), limit=4 * 1024 * 1024)
        criteria = _json(criteria_bytes)
        if not isinstance(criteria, dict) or criteria.get("schema") != "ai4r-harbor-criteria:1" or criteria.get("case_id") != case_id:
            raise ValueError("protected criteria schema/case differs from selected task")
        verifier_files = {
            "grade.py": grader_bytes,
            "criteria.json": criteria_bytes,
            "test.sh": b"#!/bin/sh\nset -eu\npython /tests/grade.py --evidence /app/ai4r-evidence --criteria /tests/criteria.json --output /logs/verifier\n",
        }
        if case_id == "cpu":
            cpu = criteria.get("cpu")
            if not isinstance(cpu, dict) or not isinstance(cpu.get("labels_path"), str):
                raise ValueError("CPU criteria must declare a protected labels_path")
            label_relative = _relative(cpu["labels_path"])
            label_name = label_relative.as_posix()
            if label_name in {"Dockerfile", "grade.py", "criteria.json", "test.sh", ".dockerignore"}:
                raise ValueError("protected labels conflict with verifier files")
            verifier_files[label_name] = _regular(criteria_root / label_relative, limit=4 * 1024 * 1024)
        verifier_files["Dockerfile"] = (
            f"FROM {python_image}\nWORKDIR /tests\nCOPY . /tests/\nRUN chmod 0555 /tests/test.sh\n"
        ).encode("utf-8")
        # A nested fixture needs its parent directory admitted too; Docker
        # cannot discover an allowed child inside an excluded parent.
        allowlist = set(verifier_files)
        for name in verifier_files:
            allowlist.update(parent.as_posix() + "/" for parent in PurePosixPath(name).parents if parent != PurePosixPath("."))
        allowed = "\n".join("!" + name for name in sorted(allowlist))
        verifier_files[".dockerignore"] = ("*\n" + allowed + "\n!.dockerignore\n").encode("utf-8")
        for name, raw in verifier_files.items():
            selected = task_root + "/tests/" + name
            payloads[selected] = raw
            protected_paths.add(selected)
        provenance[case_id] = {
            "source_case": source_name, "source_case_pin": _pin(source_bytes),
            "source_public_inputs": source_inputs,
            "changes": ["removed historical provenance and command phases", "one deliberate pilot attempt"],
        }

    # Absolute paths refer to the host on which this bundle is prepared.
    # Credentials remain exclusively in the separately provided adapter config.
    job = {
        "job_name": "ai4r-harbor-pilot",
        "jobs_dir": (destination / "harbor-results").as_posix(),
        "n_attempts": 1,
        "n_concurrent_trials": 1,
        "retry": {"max_retries": 0},
        "environment": {"type": "docker", "delete": False},
        "agents": [{"name": None, "import_path": ADAPTER}],
        "tasks": [{"path": (destination / "tasks" / case).as_posix()} for case in CASE_SOURCES],
    }
    payloads["job.json"] = _encode(job)
    manifest = {
        "schema": "ai4r-harbor-bundle:1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "harbor_version": harbor_version,
        "python_image": python_image,
        "classification": "development_compatibility_pilot",
        "protected_material_present": True,
        "provenance": provenance,
        "files": [
            {"path": name, "audience": "referee" if name in protected_paths else "visible", **_pin(raw)}
            for name, raw in sorted(payloads.items())
        ],
    }
    payloads["bundle-manifest.json"] = _encode(manifest)
    destination.mkdir(mode=0o750)
    # Publish the runnable job and completion manifest only after all selected
    # task bytes have been durably written. A failed preparation stays visible.
    order = sorted(name for name in payloads if name not in {"job.json", "bundle-manifest.json"})
    for name in [*order, "job.json", "bundle-manifest.json"]:
        raw = payloads[name]
        target = destination / _relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-root", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--criteria-root", required=True, type=Path)
    parser.add_argument("--python-image", required=True)
    parser.add_argument("--harbor-version", required=True)
    args = parser.parse_args(argv)
    manifest = prepare_bundle(**vars(args))
    print(json.dumps({"destination": str(args.destination.absolute()), "case_count": len(manifest["provenance"]), "classification": manifest["classification"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
