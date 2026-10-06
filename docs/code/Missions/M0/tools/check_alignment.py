"""Exercise joint-scope documentary refusal in isolated copies; no runtime claims."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[3]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_checker():
    spec = importlib.util.spec_from_file_location("joint_alignment_validator", BASE / "tools/validate_framework.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def edit_json(base: Path, name: str, edit) -> None:
    path = base / name
    value = json.loads(read(path))
    edit(value)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def matrix_pass(base: Path, task: str, ac: str, *, old_evidence: bool = False, clear_evidence: bool = False) -> None:
    path = base / task / "tasks.md"
    body = read(path)
    matched = False
    result = []
    for line in body.splitlines():
        if line.startswith(f"| [{ac}](spec.md) |"):
            cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
            cells[4] = "PASS"
            if clear_evidence:
                cells[5] = "No observed evidence in this isolated false-PASS fixture."
            if old_evidence:
                old = next(row for row in body.splitlines() if row.startswith("| [AC-001](spec.md) |"))
                cells[5] = [cell.strip() for cell in re.split(r"(?<!\\)\|", old)[1:-1]][5]
            line = "| " + " | ".join(cells) + " |"
            matched = True
        result.append(line)
    if not matched:
        raise ValueError(f"Negative fixture cannot find matrix subject {task}/{ac}")
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


def copy_fixture(destination: Path, checker) -> tuple[Path, Path]:
    """Copy governed input and only explicitly referenced external local files."""
    repo = destination / "repo"
    base = repo / BASE.relative_to(ROOT)
    shutil.copytree(BASE, base, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("capsules.md", "glossary.md", "guard-design.md"):
        source = ROOT / "docs/architecture/build-package" / name
        target = repo / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for path in BASE.rglob("*.md"):
        if set(path.relative_to(BASE).parts) & {"source", "context", "evidence", "history"} or "history" in path.stem.lower():
            continue
        body = read(path)
        paths = [ROOT / relative for relative in checker.PY_PATH.findall(body)]
        for module in re.findall(r"\b-m\s+(jiuwenswarm(?:\.[A-Za-z_]\w*)+)", body):
            paths.append(ROOT / (module.replace(".", "/") + ".py"))
        body = re.sub(r"```.*?```", "", body, flags=re.S)
        for link in re.findall(r"\]\((<[^>]+>|[^)]+)\)", body):
            target = link[1:link.index(">")] if link.startswith("<") else re.sub(r'\s+["\'][^"\']*["\']$', "", link)
            if re.match(r"[a-z][a-z0-9+.-]*://|mailto:", target, re.I):
                continue
            paths.append((path.parent / unquote(target).split("#", 1)[0]).resolve())
        for source in paths:
            source = source.resolve()
            if not source.is_relative_to(ROOT) or source.is_relative_to(BASE) or not source.exists():
                continue
            target = repo / source.relative_to(ROOT)
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    return base, repo


def fault_cases():
    def third_cc(base):
        edit_json(base, "registry.json", lambda value: value["authored_capabilities"].append("third_trial_capability"))

    def extra_task(base):
        (base / "M0-008").mkdir()

    def alternate_authority(base):
        edit_json(base, "registry.json", lambda value: value["scope_authorities"]["architecture"].update(path="source/build-package/glossary.md"))

    def missing_ip_owner(base):
        edit_json(base, "source-coverage.json", lambda value: value["active_scope_units"][0]["owners"].pop())

    def changed_source(base):
        with (base / "source/PRD - AI4Research.txt").open("ab") as stream:
            stream.write(b"\nIsolated changed-source negative fixture.\n")

    def broken_link(base):
        with (base / "TASKS.md").open("a", encoding="utf-8") as stream:
            stream.write("\n[Isolated broken alignment fixture](alignment-fixture-missing.md)\n")

    def false_trial_pass(base):
        matrix_pass(base, "M0-001", "AC-001", clear_evidence=True)

    def future_only(base):
        edit_json(base, "source-coverage.json", lambda value: value["prd_phase1_units"][0].update(applicability="FUTURE_CONTEXT"))

    def missing_product_owner(base):
        edit_json(base, "source-coverage.json", lambda value: value["prd_phase1_units"][0]["owners"].clear())

    def global_cap(base):
        edit_json(base, "registry.json", lambda value: value.update(capability_scope="Exactly two capabilities for all Phase 1"))

    def phase2(base):
        edit_json(base, "source-coverage.json", lambda value: next(entry for entry in value["prd_context"] if entry["id"] == "6.11").update(disposition="ACTIVE_PHASE_1"))

    def phase3(base):
        edit_json(base, "source-coverage.json", lambda value: next(entry for entry in value["prd_context"] if entry["id"] == "6.12").update(disposition="ACTIVE_PHASE_1"))

    def false_phase1_pass(base):
        matrix_pass(base, "M0-SYSTEM", "AC-018", old_evidence=True)

    def sole_authority(base):
        edit_json(base, "registry.json", lambda value: value["scope_authorities"].pop("product"))

    def concealed_unit_omission(base):
        identifier = "PRD-1.3.P1"
        def coverage_edit(value):
            value["prd_phase1_units"] = [unit for unit in value["prd_phase1_units"] if unit["id"] != identifier]
            for entry in value["prd_context"]:
                if identifier in entry.get("phase1Units", []):
                    entry["phase1Units"].remove(identifier)
                    entry.update(disposition="FUTURE_CONTEXT", owners=[])
        def registry_edit(value):
            for feature in value["features"]:
                for ac in feature["acceptance"]:
                    if identifier in ac["phase1Units"]:
                        ac["phase1Units"].remove(identifier)
                        ac["productRefs"].remove("PRD - AI4Research.txt:L87-L128")
        edit_json(base, "source-coverage.json", coverage_edit)
        edit_json(base, "registry.json", registry_edit)

    return [
        ("third_authored_trial_capability", third_cc, "two implemented TRIAL-1"),
        ("inactive_extra_root_task", extra_task, "root feature directories"),
        ("alternate_architecture_authority", alternate_authority, "joint product and architecture authority"),
        ("missing_immediate_plan_owner", missing_ip_owner, "Scope allocation/AC locator reciprocity"),
        ("changed_supplied_source", changed_source, "Changed source identity"),
        ("broken_current_link", broken_link, "Broken generated link"),
        ("false_trial_PASS", false_trial_pass, "PASS without linked observed evidence"),
        ("phase1_obligation_future_only", future_only, "incorrectly future-only"),
        ("missing_product_owner", missing_product_owner, "Product owner/AC allocation reciprocity"),
        ("global_two_CC_ceiling", global_cap, "global Phase 1 capability ceiling"),
        ("separate_phase2_execution_promotion", phase2, "Separate Phase 2 RSI execution promoted"),
        ("separate_phase3_execution_promotion", phase3, "Separate Phase 3 dynamic execution promoted"),
        ("trial_evidence_relabelled_phase1_PASS", false_phase1_pass, "Phase 1 PASS needs new native connected evidence"),
        ("product_authority_removed", sole_authority, "joint product and architecture authority"),
        ("reciprocally_concealed_product_unit_omission", concealed_unit_omission, "product-unit inventory differs"),
    ]


def check(level: str) -> dict:
    checker = load_checker()
    inputs = {name: digest(BASE / name) for name in ("registry.json", "source-coverage.json", "source-manifest.json", "tools/validate_framework.py", "tools/check_alignment.py")}
    native = {path.relative_to(BASE).as_posix(): digest(path) for task in sorted(checker.FEATURES) for name in checker.SECTIONS if (path := BASE / task / name).is_file()}
    baseline = checker.validate(level)
    result = {"level": level, "scope": "Isolated joint-r3 documentary faults only; runtime NOT_RUN", "status": "FAIL", "baseline": baseline, "cases": [], "counts": {"baseline": 1, "isolated_controls": 0, "negative_cases": 0, "detected": 0, "recovery_reads": 0}, "sources_unchanged": False, "input_sha256": inputs, "native_records_sha256": native}
    if baseline["errors"]:
        result["reason"] = "Current documentary baseline must pass before causal negative checks are meaningful."
        return result
    originals = {path.relative_to(BASE).as_posix(): digest(path) for path in (BASE / "source").rglob("*") if path.is_file()}
    original_base, original_root = checker.BASE, checker.ROOT
    try:
        for name, fault, expected_error in fault_cases():
            # TemporaryDirectory owns only this checked, task-specific subtree.
            # The cleanup never enumerates or removes original source paths.
            with tempfile.TemporaryDirectory(prefix="m0-alignment-") as scratch:
                base, repo = copy_fixture(Path(scratch), checker)
                checker.BASE, checker.ROOT = base, repo
                fixture_baseline = checker.validate(level)
                if fixture_baseline["errors"]:
                    result["cases"].append({"name": name, "detected": False, "reason": "Isolated copy is not a valid baseline", "errors": fixture_baseline["errors"]})
                    break
                result["counts"]["isolated_controls"] += 1
                fault(base)
                observed = checker.validate("BOUNDARY" if name == "broken_current_link" else level)
                detected = observed["status"] == "FAIL" and any(expected_error in error for error in observed["errors"])
                result["cases"].append({"name": name, "control_status": fixture_baseline["status"], "control_errors": fixture_baseline["errors"], "expected_status": "FAIL", "observed_status": observed["status"], "detected": detected, "expected_error": expected_error, "errors": observed["errors"]})
    finally:
        checker.BASE, checker.ROOT = original_base, original_root
    after = {path.relative_to(BASE).as_posix(): digest(path) for path in (BASE / "source").rglob("*") if path.is_file()}
    result["sources_unchanged"] = originals == after
    result["recovery"] = {"kind": "Fresh read of original current records after isolated fixture disposal; no runtime recovery claim", "result": checker.validate(level)}
    result["counts"]["recovery_reads"] = 1
    result["counts"].update(negative_cases=len(result["cases"]), detected=sum(case["detected"] for case in result["cases"]))
    result["inputs_unchanged"] = inputs == {name: digest(BASE / name) for name in inputs} and native == {name: digest(BASE / name) for name in native}
    result["status"] = "PASS" if len(result["cases"]) == len(fault_cases()) and all(case["detected"] for case in result["cases"]) and result["sources_unchanged"] and result["inputs_unchanged"] and not result["recovery"]["result"]["errors"] else "FAIL"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("BLOCK", "BOUNDARY"), required=True)
    arguments = parser.parse_args()
    output = check(arguments.level)
    print(json.dumps(output, indent=2, ensure_ascii=True))
    sys.exit(0 if output["status"] == "PASS" else 1)
