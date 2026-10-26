"""Freeze ten development cases into isolated Harbor 1.4 tasks.

The complete bundle is referee material. Upload only the explicitly inventoried
public inputs, never the bundle, tests, criteria or oracle to the product.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile

from .contracts import canonical, load_cases, pin, read_json, regular, relative, resolve_cases_root, task_key

IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:\-]*@sha256:[a-f0-9]{64}$")
ADAPTER = "benchmarks.harbor_suite.adapter:AI4ResearchSuiteAgent"


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def single_file_repo_zip(member, raw):
    """Package unchanged public source bytes in a deterministic upload asset."""
    relative(member)
    output = io.BytesIO()
    info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_STORED
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(info, raw)
    return output.getvalue()


def materialize_input(item, raw):
    actual = dict(item)
    if item['kind'] == 'repo' and Path(item['path']).suffix.lower() != '.zip':
        actual['path'] += '.zip'
        raw = single_file_repo_zip(item['path'], raw)
    return actual, raw


def runner_case(key, case, variant, *, inputs=None):
    from jiuwenswarm.research_sidecar.sequential_cases import validate_cases
    return validate_cases({"schema_version": "sequential-cases:1", "policy": "stop",
        "limits": {"deadline_s": case["budgets"]["wall_time_s"]}, "cases": [{"id": key,
        "task": variant["task"], "repeats": 1, "collection_mode": "archive",
        "inputs": [{"path": case["id"]+"/"+v["path"], "destination": v["path"],
                    "kind": v["kind"], "upload": True} for v in (variant["inputs"] if inputs is None else inputs)]}]})


def prepare(destination, *, python_image, profile="smoke", expected_model="gpt-6.1-sol",
            harbor_version="0.24.0", cases_root=None, case_ids=(), variant_ids=(), evaluation_overlay=None):
    destination = Path(destination).absolute()
    if destination.exists() or not destination.parent.is_dir() or any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("new non-symlink destination with existing parent required")
    if not IMAGE.fullmatch(python_image):
        raise ValueError("digest-pinned Python image required")
    if profile not in {"smoke", "campaign"} or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", expected_model):
        raise ValueError("explicit profile and model identity required")
    if harbor_version != "0.24.0":
        raise ValueError("this generator is validated against Harbor 0.24.0")
    cases_root = resolve_cases_root(cases_root).absolute()
    if destination.is_relative_to(cases_root) or cases_root.is_relative_to(destination):
        raise ValueError("bundle and authored cases must be separate")
    cases = load_cases(cases_root)
    if (not isinstance(case_ids, (tuple, list))
            or any(not isinstance(ident, str) or not ident for ident in case_ids)
            or len(set(case_ids)) != len(case_ids)
            or set(case_ids) - {case['id'] for case in cases}):
        raise ValueError("case selection requires unique known nonempty case IDs")
    if case_ids:
        selected = set(case_ids)
        cases = [case for case in cases if case['id'] in selected]
    if (not isinstance(variant_ids, (tuple, list)) or any(not isinstance(v, str) or not v for v in variant_ids)
            or len(set(variant_ids)) != len(variant_ids)
            or (variant_ids and set(variant_ids) - {v['id'] for c in cases for v in c['variants']})):
        raise ValueError("variant selection requires unique known nonempty variant IDs")
    overlay = None
    if evaluation_overlay is not None:
        from .evaluation import validate_overlay
        overlay = validate_overlay(read_json(evaluation_overlay))
        matches = [(c, v) for c in cases for v in c['variants']
                   if (not variant_ids or v['id'] in variant_ids)]
        if (profile != 'smoke' or len(matches) != 1 or matches[0][0]['entrypoint'] != 'single_cc'
                or (matches[0][0]['id'], matches[0][1]['id']) != (overlay['case_id'], overlay['variant_id'])):
            raise ValueError("prepared evaluation overlay requires one exact smoke variant")
        if overlay.get('prepared_inputs') and set(overlay['prepared_inputs']) != {i['path'] for i in matches[0][1]['inputs']}:
            raise ValueError('prepared public inventory differs from selected assignment')
    repeats = 1 if profile == "smoke" else 3
    payloads = {}; protected = set(); tasks = []
    def add(name, raw, *, secret=False):
        relative(name)
        if name in payloads and payloads[name] != raw:
            raise ValueError("conflicting frozen path: " + name)
        payloads[name] = raw
        if secret:
            protected.add(name)
    # Offline validators contain neutral publication/data only, never app code,
    # network clients, credentials or execution authority.
    repo = Path(__file__).resolve().parents[2]
    neutral = {}
    for name in ("jiuwenswarm/__init__.py", "jiuwenswarm/research_records/__init__.py",
                 "jiuwenswarm/research_records/contracts.py", "jiuwenswarm/research_sidecar/__init__.py",
                 "jiuwenswarm/research_sidecar/evidence.py", "jiuwenswarm/research_sidecar/frozen_records.py",
                 "jiuwenswarm/research_sidecar/evaluation_records.py"):
        neutral[name] = regular(repo / name).read_bytes()
    contract_root = repo / "jiuwenswarm/research_contracts"
    for source in sorted(contract_root.rglob("*")):
        if source.is_file() and source.suffix in {".json", ".py"} and "__pycache__" not in source.parts:
            neutral[source.relative_to(repo).as_posix()] = regular(source).read_bytes()
    for case in cases:
        folder = cases_root / case["id"]
        for variant in case["variants"]:
            if variant_ids and variant['id'] not in variant_ids:
                continue
            for repeat in range(1, repeats + 1):
                key = task_key(case["id"], variant["id"], repeat)
                public = {}; adapted_inputs = []; transforms = []; original_public = {}
                for item in variant["inputs"]:
                    source = regular(folder / item["path"])
                    name = case["id"] + "/" + item["path"]
                    raw = source.read_bytes()
                    source_pin = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                    original_public[name] = source_pin
                    if overlay and overlay.get('prepared_inputs'):
                        published = overlay['prepared_inputs'][item['path']]
                        raw = regular(published['path']).read_bytes()
                        if hashlib.sha256(raw).hexdigest() != published['artifact_ref']['sha256']:
                            raise ValueError('prepared public bytes changed before freezing')
                    add("inputs/" + name, raw)
                    actual, raw = materialize_input(item, raw)
                    if actual["path"] != item["path"]:
                        archive_name = case["id"] + "/" + actual["path"]
                        archive_pin = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                        add("inputs/" + archive_name, raw)
                        transforms.append({"schema": "ai4r-single-file-repo-zip:1",
                            "source": {"path": name, **source_pin},
                            "archive": {"path": archive_name, **archive_pin}, "member": item["path"]})
                        name = archive_name
                    if name in public:
                        raise ValueError("materialized public input paths conflict")
                    public[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                    adapted_inputs.append(actual)
                task = {"schema": "ai4r-harbor-suite-task:1", "task_key": key,
                        "case_id": case["id"], "variant_id": variant["id"], "repeat": repeat,
                        "profile": profile, "split": "development", "entrypoint": case["entrypoint"],
                        "expected_model": expected_model, "case": case, "variant": variant,
                        "public_inputs": public, "case_pin": pin(folder / "case.json"),
                        "criteria_pin": pin(folder / "referee/criteria.json"), "oracle_pin": pin(folder / "oracle.py")}
                criteria_raw = (folder / "referee/criteria.json").read_bytes()
                if overlay:
                    criteria_raw = encode(overlay['criteria'])
                    task['criteria_pin'] = {'sha256': hashlib.sha256(criteria_raw).hexdigest(), 'size': len(criteria_raw)}
                    task['evaluation_binding'] = overlay['binding']
                    task['evaluation_overlay_pin'] = pin(evaluation_overlay)
                    task['authored_public_input_pins'] = original_public
                    if overlay.get('prepared_inputs'):
                        task['evaluation_publication_refs'] = {case['id']+'/'+name: item['artifact_ref']
                            for name, item in overlay['prepared_inputs'].items()}
                    task['evaluation_controller_pins'] = {name: pin(Path(__file__).with_name(name))
                        for name in ('adapter.py', 'evaluation.py', 'contracts.py', 'prepare.py')}
                    task['measurement_note'] = 'Development assignment adapted to the installed admitted catalog; no held-out transfer claim.'
                if transforms:
                    task["input_transform"] = transforms
                task["protected_material_pins"] = {
                    p.relative_to(folder).as_posix(): pin(p) for p in sorted((folder/"referee").rglob("*")) if p.is_file()}
                if overlay:
                    task['protected_material_pins']['referee/criteria.json'] = task['criteria_pin']
                    task['protected_material_pins']['referee/evaluation-overlay.json'] = task['evaluation_overlay_pin']
                implementation = {"grade.py": Path(__file__).with_name("grade.py").read_bytes(),
                                  "evidence.py": Path(__file__).with_name("evidence.py").read_bytes(),
                                  "pilot_grade.py": Path(__file__).parents[1].joinpath("harbor_pilot/grade.py").read_bytes(), **neutral}
                task["implementation_pins"] = {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                                                for name, raw in sorted(implementation.items())}
                if case["entrypoint"] == "run":
                    raw_runner = encode(runner_case(key, case, variant, inputs=adapted_inputs))
                    add("cases/"+key+".json", raw_runner)
                    task["runner_case_pin"] = {"sha256": hashlib.sha256(raw_runner).hexdigest(), "size": len(raw_runner)}
                tasks.append(task)
                base = "tasks/" + key
                instruction = (f"AI4R_HARBOR_TASK_KEY: {key}\n\n{variant['task']}\n\n"
                               + "Public inputs:\n" + "\n".join(item["path"] for item in variant["inputs"]) + "\n")
                add(base + "/instruction.md", instruction.encode("utf-8"))
                deadline = case["budgets"]["wall_time_s"]
                config = f'''schema_version = "1.4"
artifacts = ["/app/ai4r-evidence"]
[metadata]
case_id = "{case['id']}"
variant_id = "{variant['id']}"
classification = "{case['classification']}"
split = "development"
[agent]
timeout_sec = {deadline + 180}.0
[environment]
cpus = 1
memory_mb = 256
storage_mb = 2048
network_mode = "no-network"
[verifier]
timeout_sec = 180.0
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 512
storage_mb = 2048
network_mode = "no-network"
'''
                add(base + "/task.toml", config.encode())
                add(base + "/environment/Dockerfile", f"FROM {python_image}\nWORKDIR /app\n".encode())
                add(base + "/environment/.dockerignore", b"*\n!Dockerfile\n!.dockerignore\n")
                files = {"task.json": encode(task), "criteria.json": criteria_raw,
                         "oracle.py": (folder / "oracle.py").read_bytes(),
                         "grade.py": Path(__file__).with_name("grade.py").read_bytes(),
                         "evidence.py": Path(__file__).with_name("evidence.py").read_bytes(),
                         "pilot_grade.py": Path(__file__).parents[1].joinpath("harbor_pilot/grade.py").read_bytes(),
                         "test.sh": b"#!/bin/sh\nset -eu\npython /tests/grade.py --evidence /app/ai4r-evidence --task /tests/task.json --criteria /tests/criteria.json --output /logs/verifier\n",
                         **neutral}
                for source in sorted((folder/"referee").rglob("*")):
                    if source.is_file():
                        files[source.relative_to(folder).as_posix()] = regular(source).read_bytes()
                if overlay:
                    files['referee/criteria.json'] = criteria_raw
                    files['referee/evaluation-overlay.json'] = regular(evaluation_overlay).read_bytes()
                # Pinned packages install at image build; runtime has no network.
                files["requirements.txt"] = ("jsonschema==4.26.0\nreferencing==0.37.0\nattrs==26.1.0\n"
                    "jsonschema-specifications==2025.9.1\nrpds-py==2026.9.1\n").encode()
                files["Dockerfile"] = (f"FROM {python_image}\nWORKDIR /tests\nCOPY requirements.txt /tests/requirements.txt\n"
                    "RUN pip install --no-cache-dir -r /tests/requirements.txt\nCOPY . /tests/\n"
                    "RUN chmod 0555 /tests/test.sh\n").encode()
                # Only known frozen verifier files enter this context.
                allowed = set(files)
                for name in files:
                    allowed.update(p.as_posix()+"/" for p in Path(name).parents if p != Path("."))
                files[".dockerignore"] = ("*\n"+"\n".join("!"+n for n in sorted(allowed))+"\n!.dockerignore\n").encode()
                for name, raw in files.items():
                    add(base + "/tests/" + name, raw, secret=True)
    job = {"job_name": "ai4r-suite-"+profile, "jobs_dir": (destination/"harbor-results").as_posix(),
           "n_attempts": 1, "n_concurrent_trials": 1, "retry": {"max_retries": 0},
           "environment": {"type": "docker", "delete": False},
           "agents": [{"name": None, "import_path": ADAPTER}],
           "tasks": [{"path": (destination/"tasks"/t["task_key"]).as_posix()} for t in tasks]}
    add("task-index.json", encode({"schema": "ai4r-harbor-suite-index:1", "tasks": tasks}))
    add("job.json", encode(job))
    manifest = {"schema": "ai4r-harbor-suite-bundle:1", "created_at": datetime.now(timezone.utc).isoformat(),
                "harbor_version": harbor_version, "python_image": python_image, "profile": profile,
                "expected_model": expected_model, "case_count": len(cases), "task_count": len(tasks),
                "repeats": repeats, "classification": "development", "protected_material_present": True,
                "files": [{"path": n, "audience": "referee" if n in protected else "visible",
                           "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)} for n, raw in sorted(payloads.items())]}
    add("bundle-manifest.json", encode(manifest))
    destination.mkdir()
    for name in sorted(payloads, key=lambda n: (n in {"job.json", "bundle-manifest.json"}, n)):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payloads[name]); stream.flush(); os.fsync(stream.fileno())
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--cases-root", type=Path,
                        help="External case assets (otherwise AI4R_BENCHMARK_CASES_DIR or bundled cases)")
    parser.add_argument("--python-image", required=True)
    parser.add_argument("--profile", choices=["smoke", "campaign"], default="smoke")
    parser.add_argument("--expected-model", default="gpt-6.1-sol")
    parser.add_argument("--case", dest="case_ids", action="append", default=[],
                        help="Freeze only this authored case ID; repeat for more cases (default: all ten)")
    parser.add_argument("--variant", dest="variant_ids", action="append", default=[])
    parser.add_argument("--evaluation-overlay", type=Path)
    args = parser.parse_args(argv)
    manifest = prepare(**vars(args))
    print(json.dumps({k: manifest[k] for k in ("case_count", "task_count", "profile", "expected_model")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
