"""Observed documentary fault fixtures in isolated copies; no runtime calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


BASE = Path(__file__).resolve().parents[3]
ROOT = BASE.parents[3]
OUTPUT = Path(__file__).resolve().parent
RUN_ID = "RUN-20261006-RUNTIME-LOCAL-1-DOCS"
CASES = (
    ("third_authored_cc", "Exactly two authored capabilities"),
    ("future_extra_task", "Current register must contain only nine tasks"),
    ("alternate_authority", "registry must be r2 with immediate-plan sole authority"),
    ("missing_immediate_plan_allocation", "Scope allocation/AC locator reciprocity differs"),
    ("changed_source", "Changed source identity"),
    ("broken_current_link", "Broken generated link"),
    ("unobserved_pass", "PASS without linked observed evidence"),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(name: str, value: object) -> None:
    path = OUTPUT / name
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite immutable run artifact: {name}")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def invoke(command: list[str], cwd: Path, env: dict | None = None) -> dict:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)
    stdout, stderr = completed.stdout.decode("utf-8", errors="replace"), completed.stderr.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(stdout)
    except ValueError:
        parsed = None
    return {"command": command, "cwd": str(cwd), "exit_code": completed.returncode,
            "stdout": stdout, "stderr": stderr, "stdout_sha256": sha(completed.stdout),
            "stderr_sha256": sha(completed.stderr), "parsed": parsed}


def check(base: Path, level: str) -> dict:
    root = base.parents[3]
    return invoke([sys.executable, str(base / "tools/validate_framework.py"), "--level", level], root)


def load(base: Path, name: str) -> dict:
    return json.loads((base / name).read_text(encoding="utf-8"))


def edit_json(base: Path, name: str, mutate) -> None:
    value = load(base, name)
    mutate(value)
    (base / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def mutate(base: Path, case: str) -> None:
    if case == "third_authored_cc":
        edit_json(base, "registry.json", lambda value: value["authored_capabilities"].append("delivery_cc"))
    elif case == "future_extra_task":
        feature = {"id": "M0-008", "feature_directory": "docs/code/Missions/M0/M0-008", "scope_authority": "source/build-package/immediate-plan.md", "acceptance": [], "deferred_acceptance": [], "dependencies": [], "interfaces": [], "consumed_interfaces": []}
        edit_json(base, "registry.json", lambda value: value["features"].append(feature))
        (base / "M0-008").mkdir()
    elif case == "alternate_authority":
        edit_json(base, "registry.json", lambda value: value.update(scope_authority="source/PRD - AI4Research.txt"))
    elif case == "missing_immediate_plan_allocation":
        edit_json(base, "source-coverage.json", lambda value: value["active_scope_units"][2].update(owners=[]))
    elif case == "changed_source":
        path = base / "source/build-package/immediate-plan.md"
        path.write_bytes(path.read_bytes() + b"\nIsolated unauthorized source fixture.\n")
    elif case == "broken_current_link":
        with (base / "README.md").open("a", encoding="utf-8") as stream:
            stream.write("\n[Broken isolated fixture](missing-scope-r2-fixture.md)\n")
    elif case == "unobserved_pass":
        path = base / "M0-001/tasks.md"
        body = path.read_text(encoding="utf-8")
        row = next(line for line in body.splitlines() if line.startswith("| [AC-001](spec.md) |"))
        cells = [cell.strip() for cell in row.split("|")[1:-1]]
        cells[4], cells[5] = "PASS", "No observed evidence"
        replacement = "| " + " | ".join(cells) + " |"
        path.write_text(body.replace(row, replacement, 1), encoding="utf-8")
    else:
        raise ValueError(case)


def main(plugin_root: Path) -> int:
    manifest = load(BASE, "source-manifest.json")
    original_sources = {entry["path"]: sha((BASE / entry["path"]).read_bytes()) for entry in manifest["files"]}
    template = plugin_root / "templates/EVIDENCE_TEMPLATE.md"
    metadata = {"run_id": RUN_ID, "revision": "r2", "utc": datetime.now(timezone.utc).isoformat(),
                "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                "scope": "Documentary M0-SYSTEM AC-001 only; runtime NOT_RUN",
                "template": {"path": str(template), "sha256": sha(template.read_bytes())},
                "cases_frozen_before_measurement": [{"id": case, "expected_status": "FAIL", "required_error_fragment": fragment} for case, fragment in CASES]}
    initial = {level: check(BASE, level) for level in ("BLOCK", "BOUNDARY")}
    save("scope-r2-checker-initial.json", {**metadata, "observations": initial})
    if any(result["exit_code"] != 0 or not result["parsed"] or result["parsed"]["status"] != "PASS" for result in initial.values()):
        return 1

    native = []
    pointer = ROOT / ".specify/feature.json"
    pointer_before = sha(pointer.read_bytes()) if pointer.exists() else None
    helper = plugin_root / "scripts/powershell/check-prerequisites.ps1"
    for feature in load(BASE, "registry.json")["features"]:
        environment = dict(os.environ, SPECIFY_FEATURE_DIRECTORY=feature["feature_directory"], SPECIFY_FEATURE_NO_PERSIST="1")
        observation = invoke(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper), "-Json", "-RequireSpec", "-RequireTasks", "-IncludeTasks"], ROOT, environment)
        observation["task"] = feature["id"]
        observation["expected_feature_directory"] = str((ROOT / feature["feature_directory"]).resolve())
        parsed = observation["parsed"]
        observation["pass"] = observation["exit_code"] == 0 and isinstance(parsed, dict) and Path(parsed["FEATURE_DIR"]).resolve() == Path(observation["expected_feature_directory"])
        native.append(observation)
    pointer_after = sha(pointer.read_bytes()) if pointer.exists() else None
    save("scope-r2-native-prerequisites.json", {**metadata, "helper": {"path": str(helper), "sha256": sha(helper.read_bytes())}, "no_persist": True,
            "feature_pointer_before": pointer_before, "feature_pointer_after": pointer_after,
            "observations": native, "passed": sum(item["pass"] for item in native), "required": 9})

    parent = (ROOT / ".codex-tmp").resolve()
    parent.mkdir(exist_ok=True)
    if not parent.is_relative_to(ROOT.resolve()):
        raise RuntimeError("Fault fixture parent escapes the workspace")
    results = []
    with tempfile.TemporaryDirectory(prefix="scope-r2-fault-", dir=parent) as temporary:
        scratch = Path(temporary).resolve()
        if not scratch.is_relative_to(parent):
            raise RuntimeError("Fault fixture cleanup target escapes intended directory")
        seed_root = scratch / "seed"
        seed = seed_root / "docs/code/Missions/M0"
        shutil.copytree(BASE, seed, ignore=shutil.ignore_patterns("__pycache__"))
        originals = seed_root / "docs/architecture/build-package"
        originals.mkdir(parents=True)
        for name in ("capsules.md", "glossary.md", "guard-design.md"):
            shutil.copy2(ROOT / "docs/architecture/build-package" / name, originals / name)
        # The current documentary validator resolves executable module/manual
        # ownership targets. Copy only regular authored source bytes; execute
        # no runtime or provider from the isolated documentary fixture.
        shutil.copytree(ROOT / "jiuwenswarm/ai4research", seed_root / "jiuwenswarm/ai4research",
                        ignore=shutil.ignore_patterns("__pycache__"))
        baseline = check(seed, "BOUNDARY")
        results.append({"id": "isolated_valid_baseline", "expected_status": "PASS", "pass": baseline["exit_code"] == 0, "observation": baseline})
        for case, fragment in CASES:
            fixture_root = scratch / case
            shutil.copytree(seed_root, fixture_root)
            base = fixture_root / "docs/code/Missions/M0"
            mutate(base, case)
            observation = check(base, "BOUNDARY")
            parsed = observation["parsed"] or {}
            passed = observation["exit_code"] == 1 and parsed.get("status") == "FAIL" and any(fragment in error for error in parsed.get("errors", []))
            results.append({"id": case, "expected_status": "FAIL", "required_error_fragment": fragment, "pass": passed, "observation": observation})
        recovery = check(seed, "BOUNDARY")
        results.append({"id": "isolated_unchanged_recovery", "expected_status": "PASS", "pass": recovery["exit_code"] == 0, "observation": recovery})
    unchanged = original_sources == {path: sha((BASE / path).read_bytes()) for path in original_sources}
    save("scope-r2-fault-observations.json", {**metadata, "original_sources_unchanged": unchanged, "isolated_fixture_cleanup": "Only checked workspace-contained temporary copies were removed",
            "observations": results, "passed": sum(result["pass"] for result in results), "required": len(results)})
    successful = all(item["pass"] for item in native) and pointer_before == pointer_after and all(result["pass"] for result in results) and unchanged
    print(json.dumps({"run_id": RUN_ID, "native_passed": sum(item["pass"] for item in native), "fault_passed": sum(result["pass"] for result in results), "original_sources_unchanged": unchanged, "status": "PASS" if successful else "FAIL"}, indent=2))
    return 0 if successful else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", type=Path, required=True)
    args = parser.parse_args()
    sys.exit(main(args.plugin_root.resolve()))
