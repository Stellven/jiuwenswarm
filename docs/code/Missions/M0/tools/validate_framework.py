"""Validate joint r3 Phase 1/TRIAL-1 traceability; never establish runtime acceptance."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import unquote

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[3]
AUTHORITY = "source/build-package/immediate-plan.md"
PRODUCT_AUTHORITY = "source/PRD - AI4Research.txt"
ALIGNMENT = "one-program-two-views"
CAPABILITY_SCOPE = "implemented TRIAL-1 only; not Phase1 ceiling"
SUPPLIED_AUTHORITY_HASHES = {
    PRODUCT_AUTHORITY: "897af8427e2cf4e2427a2097b9b9e8a5a427a7de53b89f4e541d2cc437594036",
    AUTHORITY: "0a7c21c2933c0be3b07e67cedaa91d2bd1706ca4382c364eb474ae616b919ec3",
}
FEATURES = {*(f"M0-{n:03}" for n in range(1, 8)), "M0-TRIAL-1", "M0-SYSTEM"}
INTERFACES = {*(f"M0-IF-{n:03}@r2" for n in range(1, 8)), "M0-IF-020@r2"}
ERRORS: list[str] = []
LOCATOR = re.compile(r"immediate-plan\.md:L(\d+)-L(\d+)\Z")
PRODUCT_LOCATOR = re.compile(r"PRD - AI4Research\.txt:L(\d+)-L(\d+)\Z")
ACTIVE_DISPOSITIONS = {"ACTIVE_PHASE_1", "GLOBAL_PHASE_1", "MIXED_PHASE_1"}
CONTEXT_DISPOSITIONS = {"SEPARATE_PHASE_2", "SEPARATE_PHASE_3", "FUTURE_CONTEXT", "EXCLUDED_PHASE_1"}
BULLET_DISPOSITIONS = {"required", "conditional", "excluded", "context", "separate_phase2", "separate_phase3"}
SELECTION_FIELDS = {"requiredLines", "boundaryLines", "excludedLines", "supportingLines", "conditionalLines"}
# This reviewed leaf inventory is independent of the mutable allocation JSON.
# A missing unit cannot be concealed by removing both of its reciprocal owners.
PRODUCT_UNIT_IDS = {
    "PRD-1.3.P1", "PRD-1.5.P1", "PRD-5.PREFACE", "PRD-6.14.P1",
    *(f"PRD-1.4-{name}" for name in ("gate-locked", "runtime-contract", "evidence", "preregistration", "scientific-negative", "fail-fast")),
    *(f"PRD-1.{n}" for n in range(6, 10)),
    *(f"PRD-2.{n}" for n in range(1, 13)),
    *(f"PRD-3.{section}.{n}" for section, count in ((0, 2), (1, 5), (2, 7), (3, 6), (4, 7), (5, 5), (6, 5), (7, 4), (8, 6), (9, 4)) for n in range(1, count + 1)),
    *(f"PRD-4.{section}.{n}" for section, count in ((1, 4), (2, 9), (3, 4), (5, 5), (6, 5), (7, 5), (8, 3), (9, 5)) for n in range(1, count + 1)),
    *(f"PRD-5.{section}.{n}" for section, count in ((1, 4), (2, 3), (3, 3), (4, 4), (5, 2), (6, 5)) for n in range(1, count + 1)),
    *(f"PRD-6.{n}" for n in range(1, 11)),
}
PY_PATH = re.compile(r"(?<![\w./-])([\w./-]+\.py)(?![\w./-])")
PLACEHOLDER = re.compile(r"\[Fill\]|PENDING_DESIGN|\[FEATURE NAME\]|\[TASK-ID\]|\[DATE\]|\[TODO\]", re.I)
SECTIONS = {
    "TASK.md": ["## 1. Identity", "## 2. Spec Kit registry", "## 3. Dependencies", "## 4. Embedded cross-module agreements", "## 5. Changes and unresolved decisions"],
    "spec.md": ["## User Scenarios & Testing", "### Edge Cases", "## Requirements", "### Functional Requirements", "### Key Entities", "## Success Criteria", "### Measurable Outcomes", "## Scope and Assumptions"],
    "plan.md": ["## Summary", "## Technical Context", "## Constitution Check", "## Project Structure", "## Blocks and Dependencies", "## Interfaces and Technical Decisions", "## Verification Design", "## System Candidate and Journeys", "## Unresolved Decisions and Impact"],
    "tasks.md": ["## Work Items", "## Acceptance and Evidence Matrix", "## Dependency Order and Execution Notes", "## Current Verification Conclusion", "## Evidence Invalidation"],
}


def require(condition: object, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(values: list, label: str) -> None:
    repeated = sorted(str(value) for value, count in Counter(values).items() if count > 1)
    require(not repeated, f"Duplicate {label}: {', '.join(repeated)}")


def rows(body: str, pattern: str) -> list[list[str]]:
    result = []
    for line in body.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
            if cells and re.fullmatch(pattern, cells[0]):
                result.append(cells)
    return result


def ranges(refs: object, label: str, count: int, *, product: bool = False, allow_empty: bool = False) -> list[tuple[int, int]]:
    field = "productRefs" if product else "scopeRefs"
    require(isinstance(refs, list) and (allow_empty or bool(refs)), f"Missing {field}: {label}")
    result = []
    for ref in refs if isinstance(refs, list) else []:
        match = (PRODUCT_LOCATOR if product else LOCATOR).fullmatch(ref) if isinstance(ref, str) else None
        require(match is not None, f"Unnormalized scope locator {label}: {ref}")
        if match:
            start, end = map(int, match.groups())
            require(1 <= start <= end <= count, f"Invalid scope range {label}: {ref}")
            result.append((start, end))
    if isinstance(refs, list):
        unique([str(ref) for ref in refs], f"scope locator {label}")
    return result


def command_paths(cell: str) -> set[str]:
    """Extract script/test targets, rather than interpreter or fixture names."""
    result = set()
    for code in re.findall(r"`([^`]+)`", cell):
        try:
            tokens = shlex.split(code)
        except ValueError:
            require(False, f"Malformed planned command: {code}")
            continue
        if tokens and Path(tokens[0]).name.lower() in {"python", "python.exe", "python3", "pytest", "pytest.exe"}:
            result.update(token for token in tokens[1:] if PY_PATH.fullmatch(token))
            if "-m" in tokens:
                offset = tokens.index("-m") + 1
                if offset < len(tokens) and tokens[offset].startswith("jiuwenswarm."):
                    target = tokens[offset].replace(".", "/") + ".py"
                    require((ROOT / target).is_file(), f"Planned module command target is absent: {target}")
                    result.add(target)
    if re.search(r"manual procedure(?:\s*\([^)]*\))?:", cell, re.I):
        targets = set(PY_PATH.findall(cell))
        require(bool(targets) and all((ROOT / target).is_file() for target in targets),
                "Manual verification needs actual owning implementation paths")
        result.update(targets)
    return result


def pass_evidence(directory: Path, task: str, ac: dict, matrix: list[str], work: dict) -> None:
    for item in set(re.findall(r"\bT\d+\b", " ".join(matrix[2:4]))):
        require(item in work and work[item][0].lower() == "x", f"PASS with unfinished work {task}/{ac['id']}/{item}")
    links = re.findall(r"\]\((?:<)?(evidence/[^)>]+)(?:>)?\)", matrix[5])
    require(bool(links), f"PASS without linked observed evidence {task}/{ac['id']}")
    bodies = []
    for link in links:
        path = (directory / unquote(link.split("#", 1)[0])).resolve()
        require(path.is_relative_to((directory / "evidence").resolve()), f"PASS evidence escapes owned custody {task}/{ac['id']}")
        require(path.is_file(), f"Missing PASS evidence {task}/{ac['id']}: {link}")
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".txt"}:
            bodies.append(text(path))
    body = "\n".join(bodies)
    revision = "r3" if task == "M0-SYSTEM" and (ac["id"] == "AC-001" or ac.get("phase1Units")) else "r2"
    require(bool(re.search(rf"\b{revision}\b", body)), f"PASS evidence lacks {revision} attribution {task}/{ac['id']}")
    require(ac["id"] in body and all(check in body for check in ac["checks"]), f"PASS evidence lacks required AC/check observations {task}/{ac['id']}")
    for check in ac["checks"]:
        require(any(re.search(rf"\b{re.escape(check)}\b", line) and re.search(r"\bPASS\b", line) for line in body.splitlines()), f"PASS evidence lacks a passing observed check row {task}/{ac['id']}/{check}")
    require(bool(re.search(r"observ(?:ed|ations)|actual outcome", body, re.I)), f"PASS evidence lacks observed outcomes {task}/{ac['id']}")
    require(bool(re.search(r"command|procedure", body, re.I)) and bool(re.search(r"exit(?:[_ ]code)?|counts", body, re.I)), f"PASS evidence lacks procedure/exit/count observations {task}/{ac['id']}")
    require(bool(re.search(r"\b[0-9a-f]{40}(?:[0-9a-f]{24})?\b", body)), f"PASS evidence lacks exact candidate identity {task}/{ac['id']}")
    if ac.get("phase1Units"):
        proofs = []
        for link in links:
            path = (directory / unquote(link.split("#", 1)[0])).resolve()
            if path.is_file() and path.suffix.lower() == ".json":
                value = json.loads(text(path))
                if isinstance(value, dict) and value.get("evidence_kind") == "phase1-connected-acceptance":
                    proofs.append(value)
        require(bool(proofs), f"Phase 1 PASS needs new native connected evidence, not TRIAL/documentary evidence: {task}/{ac['id']}")
        for proof in proofs:
            authorities = json.loads(text(BASE / "registry.json"))["scope_authorities"]
            require(proof.get("task_id") == task and proof.get("ac_id") == ac["id"], f"Phase 1 evidence subject differs: {task}/{ac['id']}")
            require(proof.get("source_authorities") == authorities, f"Phase 1 evidence source identities differ: {task}/{ac['id']}")
            require(proof.get("checks") == {check: "PASS" for check in ac["checks"]}, f"Phase 1 evidence check outcomes differ: {task}/{ac['id']}")
            require(proof.get("execution_mode") == "observed-native" and proof.get("mock") is False, f"Phase 1 PASS lacks observed native execution: {task}/{ac['id']}")
            require(isinstance(proof.get("observations"), list) and bool(proof["observations"]), f"Phase 1 PASS lacks actual observations: {task}/{ac['id']}")
            require(bool(re.fullmatch(r"[0-9a-f]{64}", str(proof.get("candidate_sha256", "")))), f"Phase 1 evidence lacks exact candidate: {task}/{ac['id']}")


def anchors(body: str) -> set[str]:
    result = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)["\']', body, re.I))
    counts = Counter()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", body, re.M):
        heading = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading)
        anchor = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        result.add(anchor + (f"-{counts[anchor]}" if counts[anchor] else ""))
        counts[anchor] += 1
    return result


def boundary(totals: dict) -> None:
    for path in sorted(BASE.rglob("*.md")):
        parts = set(path.relative_to(BASE).parts)
        if parts & {"source", "context", "evidence", "history"} or "history" in path.stem.lower():
            continue
        body = text(path)
        require(not re.search(r"[\u3400-\u9fff]", body), f"Current generated prose is not English: {path.relative_to(BASE)}")
        require(not PLACEHOLDER.search(body), f"Unfilled generated scaffold: {path.relative_to(BASE)}")
        for target in re.findall(r"\]\((<[^>]+>|[^)]+)\)", re.sub(r"```.*?```", "", body, flags=re.S)):
            target = target.strip()
            target = target[1:target.index(">")] if target.startswith("<") else re.sub(r'\s+["\'][^"\']*["\']$', "", target)
            if re.match(r"[a-z][a-z0-9+.-]*://|mailto:", target, re.I):
                continue
            filepart, _, fragment = unquote(target).partition("#")
            destination = (path.parent / filepart).resolve() if filepart else path
            require(destination.exists(), f"Broken generated link {path.relative_to(BASE)} -> {target}")
            if fragment and destination.is_file() and destination.suffix.lower() == ".md":
                require(fragment in anchors(text(destination)), f"Broken generated anchor {path.relative_to(BASE)} -> {target}")
            totals["markdown_links"] += 1
    for name in ("capsules.md", "glossary.md", "guard-design.md"):
        snapshot, original = BASE / "source/build-package" / name, ROOT / "docs/architecture/build-package" / name
        require(snapshot.is_file() and original.is_file(), f"Missing clarified source copy: {name}")
        if snapshot.is_file() and original.is_file():
            require(snapshot.read_bytes() == original.read_bytes(), f"Clarified source-copy byte drift: {name}")


def product_coverage(coverage: dict, features: dict, prd: list[str], headings: list, totals: dict) -> None:
    """Check reviewed Phase 1 units without promoting separate phases or partial reuse."""
    product_units = coverage.get("prd_phase1_units", [])
    require(isinstance(product_units, list) and len(product_units) == 148, "Expected 148 active reviewed Phase 1 source units")
    unique([unit["id"] for unit in product_units], "product unit")
    unit_map = {unit["id"]: unit for unit in product_units}
    require(set(unit_map) == PRODUCT_UNIT_IDS, "Phase 1 product-unit inventory differs; omissions/separate Phase 2/3 promotion are forbidden")
    allocation = {}
    for task, feature in features.items():
        for ac in feature["acceptance"]:
            refs = ranges(ac.get("productRefs"), f"{task}/{ac['id']}", len(prd), product=True, allow_empty=True)
            ids = ac.get("phase1Units")
            require(isinstance(ids, list), f"Missing phase1Units: {task}/{ac['id']}")
            if not isinstance(ids, list):
                ids = []
            unique(ids, f"product allocation {task}/{ac['id']}")
            require(set(ids) <= set(unit_map), f"Unknown Phase 1 allocated unit: {task}/{ac['id']}")
            allocation[task, ac["id"]] = set(ids)
            if ids:
                require(task == "M0-SYSTEM" and ac["id"] in {f"AC-{n:03}" for n in range(18, 28)}, f"Whole Phase 1 ownership incorrectly replaces retained TRIAL criterion: {task}/{ac['id']}")
                expected_refs = {(unit_map[identifier]["start"], unit_map[identifier]["end"]) for identifier in ids if identifier in unit_map}
                require(set(refs) == expected_refs, f"Product locator/whole-unit ownership differs: {task}/{ac['id']}")
    numbered = {identifier: (line, headings[i + 1][2] - 1 if i + 1 < len(headings) else len(prd)) for i, (identifier, _, line) in enumerate(headings)}
    for unit in product_units:
        identifier, start, end = unit["id"], unit["start"], unit["end"]
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(prd), f"Invalid product segment range: {identifier}")
        if not (type(start) is int and type(end) is int and 1 <= start <= end <= len(prd)):
            continue
        clause = identifier.removeprefix("PRD-")
        if clause in numbered:
            expected_start, expected_end = numbered[clause]
            parent_headers = [line for line in range(expected_start + 1, expected_end + 1) if re.match(r"^#{1,4}\s+\d+\.\s", prd[line - 1])]
            # A chapter preface has separate provenance and cannot be silently
            # attached to the previous component's source ownership.
            expected_end = parent_headers[0] - 1 if parent_headers and clause != "5.6.5" else expected_end
            require((start, end) == (expected_start, expected_end), f"Product leaf does not retain its exact original numbered segment: {identifier}")
        else:
            special = {"PRD-1.3.P1": (87, 128), "PRD-1.5.P1": (262, 282), "PRD-5.PREFACE": (2261, 2265), "PRD-6.14.P1": (2853, 2864), "PRD-1.4-gate-locked": (211, 220), "PRD-1.4-runtime-contract": (221, 236), "PRD-1.4-evidence": (237, 240), "PRD-1.4-preregistration": (241, 246), "PRD-1.4-scientific-negative": (247, 254), "PRD-1.4-fail-fast": (255, 261)}
            require((start, end) == special.get(identifier), f"Selected mixed/global segment differs from reviewed source boundary: {identifier}")
        require(unit.get("applicability") in ACTIVE_DISPOSITIONS, f"Product obligation is incorrectly future-only: {identifier}")
        require(all(isinstance(unit.get(key), str) and unit[key].strip() and not re.search(r"[\u3400-\u9fff]", unit[key]) for key in ("title", "selection", "rationale")), f"Product selection/rationale must be explicit English: {identifier}")
        segment = ("\n".join(prd[start - 1:end]) + "\n").encode("utf-8")
        require(hashlib.sha256(segment).hexdigest() == unit["sha256"], f"Changed product segment hash: {identifier}")
        owners = [(owner["task"], owner["ac"]) for owner in unit.get("owners", [])]
        unique(owners, f"product owner {identifier}")
        require(len(owners) == 1, f"Source unit needs exactly one complete product acceptance owner: {identifier}")
        expected = {key for key, ids in allocation.items() if identifier in ids}
        require(bool(owners) and set(owners) == expected, f"Product owner/AC allocation reciprocity differs: {identifier}")
        selected = unit.get("selected_lines", {})
        require(isinstance(selected, dict) and SELECTION_FIELDS <= set(selected), f"Product exact semantic line selection is missing: {identifier}")
        classifications = {}
        for field in SELECTION_FIELDS:
            values = selected.get(field, []) if isinstance(selected, dict) else []
            require(isinstance(values, list), f"Invalid product line selection {identifier}/{field}")
            if not isinstance(values, list):
                continue
            unique(values, f"selected product line {identifier}/{field}")
            for line in values:
                require(type(line) is int and start <= line <= end, f"Selected line escapes product segment: {identifier}/{line}")
                require(line not in classifications, f"Selected product line has contradictory classifications: {identifier}/{line}")
                classifications[line] = field
        require(bool(set(selected.get("requiredLines", [])) | set(selected.get("boundaryLines", [])) | set(selected.get("conditionalLines", []))), f"Active product unit has no applicable duty/boundary: {identifier}")
        require({line for line in range(start, end + 1) if prd[line - 1].strip()} <= set(classifications), f"Product semantic selection silently omits source lines: {identifier}")
        bullet_lines = []
        for bullet in unit.get("source_bullets", []):
            line = bullet.get("line")
            bullet_lines.append(line)
            require(type(line) is int and start <= line <= end and bullet.get("text") == prd[line - 1], f"Product bullet text/source locator differs: {identifier}/{line}")
            require(bullet.get("disposition") in BULLET_DISPOSITIONS, f"Unknown product bullet disposition: {identifier}/{line}")
            expected_fields = {"required": {"requiredLines", "boundaryLines"}, "conditional": {"conditionalLines"}, "excluded": {"excludedLines", "boundaryLines"}, "context": {"supportingLines"}, "separate_phase2": {"excludedLines"}, "separate_phase3": {"excludedLines"}}
            require(classifications.get(line) in expected_fields.get(bullet.get("disposition"), set()), f"Product bullet/selected-line disposition differs: {identifier}/{line}")
        unique(bullet_lines, f"product source bullet {identifier}")
        future = False
        for line in range(start, end + 1):
            source_line = prd[line - 1]
            if "Future State (Blacklist for M1)" in source_line:
                future = True
            if future:
                require(classifications.get(line) not in {"requiredLines", "conditionalLines"}, f"Future blacklist is promoted to required Phase 1 implementation: {identifier}/{line}")
        if identifier == "PRD-6.14.P1":
            require(all(classifications.get(line) == "excludedLines" for line in (2857, 2861)), "Core full-M1 Stage 8/Phase 2 requirements must not be promoted into Phase 1 completion")
    context = coverage["prd_context"]
    require(len(context) == len(headings) == 184 and [(entry["id"], entry["title"], entry["line"]) for entry in context] == headings, "All 184 numbered PRD headings must retain exact source identity")
    aliases = {"1.1": {"PRD-1.3.P1"}, "1.2": {"PRD-1.3.P1"}, "6.13": {"PRD-1.7"}}
    for entry in context:
        identifier = entry["id"]
        ids = entry.get("phase1Units", [])
        require(isinstance(ids, list), f"Missing heading product-unit index: {identifier}")
        if not isinstance(ids, list):
            continue
        unique(ids, f"heading product unit {identifier}")
        require(entry.get("disposition") in ACTIVE_DISPOSITIONS | CONTEXT_DISPOSITIONS, f"Unknown PRD heading applicability: {identifier}")
        expected = {uid for uid in unit_map if uid.removeprefix("PRD-") == identifier or uid.removeprefix("PRD-").startswith(identifier + ".") or uid.removeprefix("PRD-").startswith(identifier + "-")}
        if identifier in aliases:
            expected = aliases[identifier]
            require(bool(entry.get("role")), f"Supporting product heading needs explicit interpretation role: {identifier}")
        require(set(ids) == expected, f"PRD heading/product-unit index differs: {identifier}")
        require((entry.get("disposition") in ACTIVE_DISPOSITIONS) == bool(ids), f"PRD active/context heading classification differs: {identifier}")
        owner_set = {tuple((owner["task"], owner["ac"])) for uid in ids if uid in unit_map for owner in unit_map[uid]["owners"]}
        indexed_owners = [(owner["task"], owner["ac"]) for owner in entry.get("owners", [])]
        unique(indexed_owners, f"heading owner {identifier}")
        require(set(indexed_owners) == owner_set, f"Heading/product owner reciprocity differs: {identifier}")
        if identifier == "4.4" or identifier.startswith("4.4.") or identifier == "6.11":
            require(entry.get("disposition") == "SEPARATE_PHASE_2" and not ids, f"Separate Phase 2 RSI execution promoted: {identifier}")
        if identifier == "6.12":
            require(entry.get("disposition") == "SEPARATE_PHASE_3" and not ids, "Separate Phase 3 dynamic execution promoted")
    totals["phase1_product_units"] = len(product_units)
    totals["context_prd_headings"] = len(context)
    context_units = coverage.get("prd_context_units", [])
    expected_context = {"PRD-4.1.5", "PRD-4.2.10", *(f"PRD-4.4.{n}" for n in range(1, 11))}
    require({unit.get("id") for unit in context_units} == expected_context and len(context_units) == 12, "Separate/future source-unit context inventory differs")
    for unit in context_units:
        require(unit.get("applicability") in CONTEXT_DISPOSITIONS and not unit.get("owners"), f"Separate/future context unit has active ownership: {unit.get('id')}")
        start, end = unit["start"], unit["end"]
        require(1 <= start <= end <= len(prd), f"Invalid context source range: {unit['id']}")
        segment = ("\n".join(prd[start - 1:end]) + "\n").encode("utf-8")
        require(hashlib.sha256(segment).hexdigest() == unit["sha256"], f"Changed separate/future context segment hash: {unit['id']}")
        selection = unit.get("selected_lines", {})
        require(not selection.get("requiredLines") and not selection.get("boundaryLines") and not selection.get("conditionalLines"), f"Separate/future context execution promoted into Phase 1: {unit['id']}")


def validate(level: str) -> dict:
    ERRORS.clear()
    totals = {key: 0 for key in ("features", "source_files", "active_scope_units", "phase1_product_units", "context_prd_headings", "acceptance_criteria", "deferred_acceptance", "blocks", "checks", "work_items", "interfaces", "authored_capabilities", "markdown_links")}
    try:
        registry, coverage, manifest = [json.loads(text(BASE / name)) for name in ("registry.json", "source-coverage.json", "source-manifest.json")]
        features = {feature["id"]: feature for feature in registry["features"]}
        unique([feature["id"] for feature in registry["features"]], "feature")
        require(set(features) == FEATURES and len(registry["features"]) == 9, "Current register must contain only nine tasks: M0-001 through M0-007, M0-TRIAL-1, M0-SYSTEM")
        require(registry.get("active_slice") == "TRIAL-1" and registry.get("system_task") == "M0-SYSTEM", "Current slice/system owner is incorrect")
        for document, name in ((registry, "registry"), (coverage, "coverage"), (manifest, "manifest")):
            require(document.get("revision") == "r3" and document.get("scope_authority") == AUTHORITY, f"{name} must be r3 with the legacy immediate-plan architecture path")
            require(document.get("alignment") == ALIGNMENT, f"{name} must align one program's two source views")
            expected_authorities = {"product": {"path": PRODUCT_AUTHORITY, "scope": "M1 Delivery Phase 1", "sha256": sha(BASE / PRODUCT_AUTHORITY)}, "architecture": {"path": AUTHORITY, "scope": "TRIAL-1", "sha256": sha(BASE / AUTHORITY)}}
            require(document.get("scope_authorities") == expected_authorities, f"{name} substitutes/omits joint product and architecture authority identities")
        for path, expected_hash in SUPPLIED_AUTHORITY_HASHES.items():
            require(sha(BASE / path) == expected_hash, f"Original supplied authority bytes changed: {path}")
        capabilities = registry.get("authored_capabilities", [])
        require(Counter(capabilities) == Counter(("intent_compiler", "intent_verifier")), "Exactly two implemented TRIAL-1 authored capabilities are required")
        require(registry.get("capability_scope") == CAPABILITY_SCOPE, "The implemented Intent pair must not become a global Phase 1 capability ceiling")
        directories = {path.name for path in BASE.iterdir() if path.is_dir() and path.name.startswith("M0-")}
        require(directories == FEATURES, "Current root feature directories include missing/inactive work; M0-008 through M0-019 must be archived context")
        totals["features"], totals["authored_capabilities"] = len(features), len(capabilities)

        sources = manifest["files"]
        source_paths = [entry["path"] for entry in sources]
        unique(source_paths, "source path")
        actual = {path.relative_to(BASE).as_posix() for path in (BASE / "source").rglob("*") if path.is_file()}
        require(len(sources) == 68 and set(source_paths) == actual, "Manifest must enumerate all 68 preserved supplied source files exactly once")
        for entry in sources:
            path = (BASE / entry["path"]).resolve()
            require(path.is_relative_to((BASE / "source").resolve()), f"Source escapes snapshot: {entry['path']}")
            require(path.is_file(), f"Missing source: {entry['path']}")
            if path.is_file():
                require(sha(path) == entry["sha256"] and path.stat().st_size == entry["bytes"], f"Changed source identity: {entry['path']}")
        totals["source_files"] = len(sources)
        authority = BASE / AUTHORITY
        lines = text(authority).splitlines()
        for document, name in ((coverage, "coverage"), (manifest, "manifest")):
            require(document.get("authority_sha256") == sha(authority), f"Stale immediate-plan identity: {name}")
        headings = [(i + 1, match[1]) for i, line in enumerate(lines) if (match := re.match(r"^#{1,2}\s+(.+)$", line))]
        expected_units = [(start, headings[i + 1][0] - 1 if i + 1 < len(headings) else len(lines), title) for i, (start, title) in enumerate(headings)]
        units = coverage["active_scope_units"]
        require(len(units) == len(expected_units) == 8, "Expected eight immediate-plan heading segments")
        require([(unit["start"], unit["end"], unit["title"]) for unit in units] == expected_units, "Immediate-plan segment inventory/locators differ")
        unique([unit["id"] for unit in units], "scope unit")
        totals["active_scope_units"] = len(units)
        prd = text(BASE / PRODUCT_AUTHORITY).splitlines()
        prd_headings = [(match[1], match[2].strip(), i + 1) for i, line in enumerate(prd) if (match := re.match(r"^#{2,4}\s+(\d+(?:\.\d+)+)\s+(.+)$", line))]
        product_coverage(coverage, features, prd, prd_headings, totals)

        allocated = {}
        for task, feature in features.items():
            require(feature.get("scope_authority") == AUTHORITY and feature.get("scope_authorities") == expected_authorities, f"Feature substitutes joint source authority: {task}")
            unique([ac["id"] for ac in feature["acceptance"]], f"registry AC {task}")
            for ac in feature["acceptance"]:
                allocated[task, ac["id"]] = ranges(ac.get("scopeRefs"), f"{task}/{ac['id']}", len(lines))
            deferred_ids = []
            for entry in feature.get("deferred_acceptance", []):
                ac = entry.get("ac", entry.get("acId", entry.get("id")))
                require(isinstance(ac, str) and bool(re.fullmatch(r"AC-\d+", ac)), f"Invalid deferred AC: {task}")
                deferred_ids.append(ac)
                require(ac not in {item["id"] for item in feature["acceptance"]}, f"Deferred AC is also active: {task}/{ac}")
                require(entry.get("pass_claim") is not True and not entry.get("current_work"), f"Deferred AC creates current work/PASS: {task}/{ac}")
                for key in ("implementation_work", "checks", "tasks"):
                    require(not entry.get(key), f"Deferred AC creates active {key}: {task}/{ac}")
                require(not isinstance(entry.get("work"), list) or not entry["work"], f"Deferred AC creates active work: {task}/{ac}")
                for key in ("status", "result", "current_result", "acceptance"):
                    require(str(entry.get(key, "")).strip() not in {"PASS", "N/A"}, f"Deferred AC improperly passed/exempted: {task}/{ac}")
                ranges(entry.get("scopeRefs"), f"deferred {task}/{ac}", len(lines))
            unique(deferred_ids, f"deferred AC {task}")
            totals["deferred_acceptance"] += len(deferred_ids)
        for unit in units:
            segment = ("\n".join(lines[unit["start"] - 1:unit["end"]]) + "\n").encode("utf-8")
            require(hashlib.sha256(segment).hexdigest() == unit["sha256"], f"Changed immediate-plan segment hash: {unit['id']}")
            owners = [(owner["task"], owner["ac"]) for owner in unit["owners"]]
            unique(owners, f"scope owner {unit['id']}")
            expected = {key for key, spans in allocated.items() if any(start <= unit["end"] and end >= unit["start"] for start, end in spans)}
            require(bool(owners) and set(owners) == expected, f"Scope allocation/AC locator reciprocity differs: {unit['id']}")

        visiting, visited = set(), set()
        def visit(task: str) -> None:
            if task in visited:
                return
            if task in visiting:
                require(False, f"Definition dependency cycle: {task}")
                return
            visiting.add(task)
            unique(features[task]["dependencies"], f"dependency {task}")
            for dependency in features[task]["dependencies"]:
                require(dependency in features, f"Inactive/unknown dependency: {task} -> {dependency}")
                if dependency in features:
                    visit(dependency)
            visiting.remove(task)
            visited.add(task)
        for task in features:
            visit(task)
        interface_owners = {}
        for task, feature in features.items():
            for interface in feature["interfaces"]:
                require(interface not in interface_owners, f"Duplicate IF owner: {interface}")
                interface_owners[interface] = task
        require(set(interface_owners) == INTERFACES, "Expected eight unique owned IF@r2 agreements")
        totals["interfaces"] = len(interface_owners)

        for task, feature in features.items():
            directory = ROOT / feature["feature_directory"]
            require(directory.resolve() == (BASE / task).resolve(), f"Incorrect/parallel feature directory: {task}")
            docs = {}
            for name, mandatory in SECTIONS.items():
                path = directory / name
                require(path.is_file(), f"Missing native artifact: {task}/{name}")
                if not path.is_file():
                    continue
                docs[name] = text(path)
                for section in mandatory:
                    require(section in docs[name], f"Missing native section {task}/{name}: {section}")
                require(not re.search(r"[\u3400-\u9fff]", docs[name]), f"Native artifact is not English: {task}/{name}")
                require(not PLACEHOLDER.search(docs[name]), f"Unfilled native scaffold: {task}/{name}")
                require(not re.search(r"M0-IF-\d+@r1", docs[name]), f"Historical IF used in current artifact: {task}/{name}")
            if len(docs) != 4:
                continue
            ac_rows, block_rows, check_rows = rows(docs["spec.md"], r"AC-\d+"), rows(docs["plan.md"], r"B\d+"), rows(docs["plan.md"], r"V\d+")
            matrix_rows = rows(docs["tasks.md"], r"\[AC-\d+\]\(spec\.md\)")
            items = re.findall(r"^- \[([ xX])\] (T\d+) (.+)$", docs["tasks.md"], re.M)
            for values, label in (([row[0] for row in ac_rows], "spec AC"), ([row[0] for row in block_rows], "block"), ([row[0] for row in check_rows], "check"), ([row[0] for row in matrix_rows], "matrix AC"), ([item[1] for item in items], "work")):
                unique(values, f"{label} {task}")
            ac_map, block_map, check_map = ({row[0]: row for row in collection} for collection in (ac_rows, block_rows, check_rows))
            matrix = {re.search(r"AC-\d+", row[0])[0]: row for row in matrix_rows}
            work = {item: (checked, line) for checked, item, line in items}
            acceptance = feature["acceptance"]
            require(set(ac_map) == set(matrix) == {ac["id"] for ac in acceptance}, f"Registry/spec/work AC disagreement: {task}")
            require(set(block_map) == {ac["block"] for ac in acceptance}, f"Registry/plan block disagreement: {task}")
            require(set(check_map) == {check for ac in acceptance for check in ac["checks"]}, f"Registry/plan check disagreement: {task}")
            deferred = {entry.get("ac", entry.get("acId", entry.get("id"))) for entry in feature.get("deferred_acceptance", [])}
            for item, (_, line) in work.items():
                require(not (set(re.findall(r"\bAC-\d+\b", line)) & deferred), f"Deferred AC allocated current work: {task}/{item}")
                require(set(re.findall(r"\bAC-\d+\b", line)) <= set(ac_map), f"Unknown current AC in work: {task}/{item}")
                require(set(re.findall(r"\bB\d+\b", line)) <= set(block_map), f"Unknown current block in work: {task}/{item}")
                require(set(re.findall(r"\bV\d+\b", line)) <= set(check_map), f"Unknown current check in work: {task}/{item}")
            for ac in acceptance:
                identifier, block = ac["id"], ac["block"]
                spec_row, block_row, mapping = ac_map.get(identifier, []), block_map.get(block, []), matrix.get(identifier, [])
                if not spec_row or not block_row or not mapping:
                    continue
                require(set(re.findall(r"immediate-plan\.md:L\d+-L\d+", spec_row[1])) == set(ac["scopeRefs"]), f"Registry/spec scope locators differ: {task}/{identifier}")
                if ac.get("phase1Units"):
                    require(set(re.findall(r"PRD - AI4Research\.txt:L\d+-L\d+", spec_row[1])) == set(ac["productRefs"]), f"Registry/spec active product locators differ: {task}/{identifier}")
                require(identifier in " ".join(block_row) and block in mapping[1], f"Block/AC matrix association differs: {task}/{identifier}")
                require(len(mapping) == 7, f"Malformed evidence matrix: {task}/{identifier}")
                if len(mapping) != 7:
                    continue
                mapped = set(re.findall(r"\bT\d+\b", " ".join(mapping[2:4])))
                require(bool(re.findall(r"\bT\d+\b", mapping[2])) and mapped <= set(work), f"Missing/unknown mapped work: {task}/{identifier}")
                require(set(re.findall(r"\bV\d+\b", mapping[3])) == set(ac["checks"]), f"Matrix required checks differ: {task}/{identifier}")
                require(mapping[4] in {"NOT_RUN", "PASS", "FAIL", "BLOCKED", "STALE", "INCONCLUSIVE", "NOT_READY"}, f"Invalid current acceptance result: {task}/{identifier}")
                if mapping[4] == "PASS":
                    pass_evidence(directory, task, ac, mapping, work)
                for check in ac["checks"]:
                    row = check_map.get(check, [])
                    mapped_item = re.findall(rf"\b{re.escape(check)} / (T\d+)\b", mapping[3])
                    require(len(mapped_item) == 1, f"Check needs one verification work item: {task}/{check}")
                    if not row or len(mapped_item) != 1:
                        continue
                    require(len(row) == 7 and row[1] in {"BLOCK", "BOUNDARY"}, f"Malformed planned check: {task}/{check}")
                    if len(row) != 7:
                        continue
                    require(block in row[2] and identifier in row[2], f"Check subject disagrees: {task}/{check}")
                    require(bool(row[3]) and "Failure:" in row[4] and "Recovery:" in row[4], f"Check lacks fixture/failure/recovery cases: {task}/{check}")
                    paths = command_paths(row[5])
                    require(bool(paths), f"Check lacks concrete Python command target: {task}/{check}")
                    item = mapped_item[0]
                    line = work.get(item, ("", ""))[1]
                    require(check in line and row[1] in line and block in line and identifier in line, f"Verification work disagrees: {task}/{check}/{item}")
                    require(paths <= set(PY_PATH.findall(line)), f"Planned command/work path disagreement: {task}/{check}")
                    if "--level" in row[5]:
                        require(f"--level {row[1]}" in row[5], f"Document command level differs: {task}/{check}")
                    if "pytest" in row[5]:
                        require("collect nonzero" in row[5].lower(), f"Pytest plan omits nonzero collection requirement: {task}/{check}")
            for interface in feature["interfaces"]:
                heading = f"### {interface.split('@')[0]} at r2"
                require(docs["TASK.md"].count(heading) == 1, f"Missing/duplicate owned IF definition: {task}/{interface}")
                section = docs["TASK.md"].split(heading, 1)[-1].split("\n### ", 1)[0].split("\n## ", 1)[0]
                roster = re.search(r"^\| Provider and consumers \| ([^|]+)\|", section, re.M)
                expected = sorted(consumer for consumer, other in features.items() if interface in other["consumed_interfaces"])
                if roster:
                    provider, _, consumers = roster[1].strip().partition("; consumers: ")
                    require(provider == task and [value.strip() for value in consumers.split(",") if value.strip()] == expected, f"IF owner/reciprocal consumer roster differs: {task}/{interface}")
                else:
                    require(False, f"Missing IF owner/consumer roster: {task}/{interface}")
                for field in ("Purpose", "Inputs", "Outputs", "States/invariants", "Errors/timeout/retry/cancellation", "Effects/idempotency"):
                    require(f"| {field} |" in section, f"Incomplete owned IF {task}/{interface}: {field}")
            unique(feature["consumed_interfaces"], f"consumed IF {task}")
            for interface in feature["consumed_interfaces"]:
                require(interface in interface_owners and interface_owners.get(interface) != task, f"Unowned/self-consumed IF: {task}/{interface}")
                require(interface in docs["TASK.md"], f"Consumed IF missing from TASK: {task}/{interface}")
            for key, collection in (("acceptance_criteria", ac_rows), ("blocks", block_rows), ("checks", check_rows), ("work_items", items)):
                totals[key] += len(collection)
        require(totals["acceptance_criteria"] == totals["blocks"] == 68, "Expected 58 retained TRIAL plus ten active Phase 1 AC/block identities")
        require(totals["checks"] == 136, "Expected two required checks for each of 68 active acceptance criteria")
        if level == "BOUNDARY":
            boundary(totals)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        require(False, f"Invalid/missing documentary input: {type(exc).__name__}: {exc}")
    return {"level": level, "status": "FAIL" if ERRORS else "PASS", "scope": "Joint r3 Phase 1/TRIAL-1 documentation/source/traceability only; runtime NOT_RUN", "alignment": ALIGNMENT, "scope_authorities": {"product": PRODUCT_AUTHORITY, "architecture": AUTHORITY}, "totals": totals, "errors": ERRORS.copy()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("BLOCK", "BOUNDARY"), required=True)
    arguments = parser.parse_args()
    result = validate(arguments.level)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    sys.exit(1 if result["errors"] else 0)
