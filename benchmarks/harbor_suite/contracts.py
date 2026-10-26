"""Benchmark-owned authoring metadata; never a product wire contract."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = "ai4r-harbor-suite-case:1"
EXPECTED = {
    "cc01-transfer": ("cc", "single_cc"),
    "cc02-binding": ("cc", "single_cc"),
    "mr01-quality": ("mr", "routing"),
    "mr02-compatibility": ("mr", "routing"),
    "rsi01-improvement": ("rsi", "rsi"),
    "rsi02-containment": ("rsi", "rsi"),
    "vf01-mechanical": ("verifier", "node_replay"),
    "vf02-semantic": ("verifier", "node_replay"),
    "pipeline01-experiment": ("pipeline", "run"),
    "pipeline02-recovery": ("pipeline", "run"),
}
ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
FIELDS = set("schema id module title scenario_ids milestone classification requirements domains entrypoint objective primary_metric budgets product_prerequisites evidence_requirements variants oracle_version".split())
VARIANT_FIELDS = set("id split task inputs expected_behavior seed".split())


def strict_json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError("duplicate JSON field: " + key)
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or "\0" in value or value.startswith("/")
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("canonical relative path required")
    return value


def regular(path, max_bytes=16 * 1024 * 1024):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink paths are forbidden")
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("bounded regular file required: " + str(path))
    return path


def pin(path):
    path = regular(path, 128 * 1024 * 1024)
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def read_json(path):
    return strict_json(regular(path).read_bytes())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_case(case, folder=None):
    require(isinstance(case, dict) and set(case) == FIELDS and case.get("schema") == SCHEMA,
            "suite case fields differ from AUTHORING.md")
    ident = case["id"]
    require(ident in EXPECTED and (case["module"], case["entrypoint"]) == EXPECTED[ident],
            "case identity/module/entrypoint differs from the ten-case suite")
    for key in ("title", "objective", "oracle_version"):
        require(isinstance(case[key], str) and bool(case[key].strip()), "missing " + key)
    for key in ("scenario_ids", "requirements", "domains", "product_prerequisites", "evidence_requirements"):
        require(isinstance(case[key], list) and bool(case[key])
                and all(isinstance(v, str) and v for v in case[key]), "missing string list: " + key)
    require(all(re.fullmatch(r"s(?:0[1-9]|10)", s) for s in case["scenario_ids"]), "invalid scenario mapping")
    require(all(re.fullmatch(r"c0[1-8]", s) for s in case["domains"]), "invalid domain mapping")
    require(all(re.fullmatch(r"(?:B|CC|PL|RT|RS|VF|LH|SU)\d{2}", s) for s in case["requirements"]),
            "invalid requirement mapping")
    later = case["module"] in {"mr", "rsi"}
    require(case["milestone"] == ("m2" if later else "m1"), "incorrect benchmark milestone")
    require(case["classification"] == ("m2_m3_progress" if later else "core_m1_acceptance"),
            "incorrect benchmark classification")
    metric = case["primary_metric"]
    require(isinstance(metric, dict) and set(metric) == {"name", "definition"}
            and all(isinstance(v, str) and v for v in metric.values()), "primary metric lacks denominator")
    budget = case["budgets"]
    keys = {"wall_time_s", "max_model_calls", "physical_memory_mb", "committed_memory_mb",
            "storage_mb", "concurrency", "gpu_required"}
    require(isinstance(budget, dict) and set(budget) == keys, "invalid budget fields")
    require(all(type(budget[k]) is int and budget[k] > 0 for k in keys - {"gpu_required"}),
            "finite positive integer budgets required")
    require(budget["concurrency"] == 1 and budget["gpu_required"] is False
            and budget["committed_memory_mb"] >= budget["physical_memory_mb"], "invalid fast CPU profile")
    rows = case["variants"]
    require(isinstance(rows, list) and 3 <= len(rows) <= 128, "at least three distinct variants required")
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == VARIANT_FIELDS, "invalid variant fields")
        require(isinstance(row["id"], str) and ID.fullmatch(row["id"]) and row["id"] not in seen,
                "duplicate or invalid variant identity")
        seen.add(row["id"])
        require(row["split"] == "development", "authored fixtures cannot claim held-out custody")
        require(isinstance(row["task"], str) and 10 <= len(row["task"]) <= 100000, "bounded task required")
        require(row["expected_behavior"] in {"complete", "halt"}, "explicit expected behavior required")
        require(type(row["seed"]) is int and row["seed"] >= 0, "explicit nonnegative fixture seed required")
        require(isinstance(row["inputs"], list), "input inventory required")
        paths = set()
        for item in row["inputs"]:
            require(isinstance(item, dict) and set(item) == {"path", "kind"}, "invalid public input")
            name = relative(item["path"])
            require(name.startswith("public/") and name not in paths and item["kind"] in {"docs", "datasets", "repo"},
                    "only explicit public inputs may be transmitted")
            paths.add(name)
            if folder:
                regular(Path(folder) / name, 16 * 1024 * 1024)
    if folder:
        for name in ("oracle.py", "test_oracle.py", "README.md", "referee/criteria.json"):
            regular(Path(folder) / name)
        criteria = read_json(Path(folder) / "referee/criteria.json")
        require(isinstance(criteria, dict), "protected criteria must be an object")
    return case


def resolve_cases_root(root=None):
    """Select explicit assets, then operator environment, then bundled defaults.

    A selected external root never silently falls back to repository fixtures.
    Frozen bundles retain their own pinned copies and do not consult this setting.
    """
    selected = root if root is not None else os.environ.get("AI4R_BENCHMARK_CASES_DIR")
    if selected is None:
        return Path(__file__).parent / "cases"
    if not str(selected).strip():
        raise ValueError("benchmark cases directory must not be empty")
    return Path(selected).expanduser().absolute()


def load_cases(root=None):
    root = resolve_cases_root(root)
    result = []
    for ident in EXPECTED:
        folder = root / ident
        case = validate_case(read_json(folder / "case.json"), folder)
        require(case["id"] == ident, "case directory identity mismatch")
        result.append(case)
    return result


def task_key(case_id, variant_id, repeat):
    require(case_id in EXPECTED and type(repeat) is int and repeat > 0, "invalid task key scope")
    suffix = hashlib.sha256(canonical([variant_id, repeat])).hexdigest()[:12]
    return case_id + "-" + suffix


def validate_bundle(bundle, *, selected=None, index_only=False):
    """Validate a frozen bundle without importing Harbor or application code."""
    bundle = Path(bundle)
    manifest = read_json(bundle / "bundle-manifest.json")
    require(manifest.get("schema") == "ai4r-harbor-suite-bundle:1", "wrong bundle schema")
    seen = set()
    for row in manifest["files"]:
        name = relative(row["path"])
        relevant = name == "task-index.json" or (not index_only and (
            selected is None or name.startswith("tasks/"+selected["task_key"]+"/")
            or name == "cases/"+selected["task_key"]+".json"
            or name in {"inputs/"+p for p in selected["public_inputs"]}))
        require(name not in seen and (not relevant or pin(bundle/name) ==
                {k: row[k] for k in ("sha256", "size")}), "frozen bundle changed")
        seen.add(name)
    require("task-index.json" in seen, "frozen task index missing")
    return read_json(bundle / "task-index.json")
