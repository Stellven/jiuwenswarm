"""Validate M0 documentary invariants; never establish product runtime acceptance."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[3]
ERRORS = []


def require(condition, message):
    if not condition:
        ERRORS.append(message)


def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(path):
    return path.read_text(encoding="utf-8")


def validate(level):
    ERRORS.clear()
    registry, sources, manifest = load("registry.json"), load("source-coverage.json"), load("source-manifest.json")
    features = {f["id"]: f for f in registry["features"]}
    require(len(features) == len(registry["features"]) == 21, "Feature identities must be unique and complete (21)")
    require(registry["system_task"] == "M0-SYSTEM", "System TASK must be designated")
    primary = BASE / manifest["primary_prd"]
    require(sha(primary) == sources["primary_prd_sha256"], "Primary PRD coverage baseline is stale")
    prd_lines = text(primary).lstrip("\ufeff").splitlines()
    headings = [(m[1], i + 1) for i, line in enumerate(prd_lines) if (m := re.match(r"^#{2,4}\s+(\d+(?:\.\d+)+)\s+", line))]
    require(len(headings) == 184, "Expected original 184 numbered PRD headings")
    require([(c["id"], c["start"]) for c in sources["clauses"]] == headings, "Source coverage is incomplete or has inaccurate heading locators")
    for f in manifest["files"]:
        path = BASE / f["path"]
        require(path.is_file(), f"Missing registered source {f['path']}")
        if path.is_file():
            require(sha(path) == f["sha256"] and path.stat().st_size == f["bytes"], f"Changed source identity {f['path']}")
    indexed = {f["path"] for f in manifest["files"]}
    actual = {f.relative_to(BASE).as_posix() for f in (BASE / "source").rglob("*") if f.is_file()}
    require(indexed == actual, "Source manifest must include every source file exactly once")
    clauses = {c["id"]: c for c in sources["clauses"]}
    for c in sources["clauses"]:
        require(c["owners"], f"Unallocated source {c['id']}")
        expected = hashlib.sha256(("\n".join(prd_lines[c["start"] - 1:c["end"]]) + "\n").encode()).hexdigest()
        require(expected == c["sha256"], f"Source clause identity mismatch {c['id']}")
        for o in c["owners"]:
            require(o["task"] in features, f"Unknown source owner {o}")
            if o["task"] in features:
                require(o["ac"] in {a["id"] for a in features[o["task"]]["acceptance"]}, f"Unknown allocated AC {o}")
    visiting, visited = set(), set()

    def visit(task):
        if task in visited:
            return
        require(task not in visiting, f"Definition dependency cycle at {task}")
        if task in visiting:
            return
        visiting.add(task)
        for dep in features[task]["dependencies"]:
            require(dep in features, f"Unknown dependency {dep} for {task}")
            if dep in features:
                visit(dep)
        visiting.remove(task)
        visited.add(task)

    for task in features:
        visit(task)
    interface_owners = {}
    for task, feature in features.items():
        for interface in feature['interfaces']:
            require(interface not in interface_owners, f"Duplicate interface owner {interface}")
            interface_owners[interface] = task
    require(len(interface_owners) == 20, "Expected 20 uniquely owned interfaces")
    sections = {
        "TASK.md": ["## 1. Identity", "## 2. Spec Kit registry", "## 3. Dependencies", "## 4. Embedded cross-module agreements", "## 5. Changes and unresolved decisions"],
        "spec.md": ["## User Scenarios & Testing", "### Edge Cases", "## Requirements", "### Functional Requirements", "### Key Entities", "## Success Criteria", "### Measurable Outcomes", "## Scope and Assumptions"],
        "plan.md": ["## Summary", "## Technical Context", "## Constitution Check", "## Project Structure", "## Blocks and Dependencies", "## Interfaces and Technical Decisions", "## Verification Design", "## System Candidate and Journeys", "## Unresolved Decisions and Impact"],
        "tasks.md": ["## Work Items", "## Acceptance and Evidence Matrix", "## Dependency Order and Execution Notes", "## Current Verification Conclusion", "## Evidence Invalidation"],
    }
    totals = {"features": len(features), "prd_clauses": len(headings), "acceptance_criteria": 0, "blocks": 0, "checks": 0, "work_items": 0, "interfaces": 0, "source_files": len(indexed), "markdown_links": 0}
    for task, feature in features.items():
        directory = ROOT / feature["feature_directory"]
        require(directory == BASE / task, f"Parallel/incorrect feature directory {task}")
        docs = {}
        for filename, mandatory in sections.items():
            p = directory / filename
            require(p.is_file(), f"Missing native artifact {p}")
            if not p.is_file():
                continue
            docs[filename] = text(p)
            for section in mandatory:
                require(section in docs[filename], f"Missing required section {task}/{filename}: {section}")
            require(not re.search(r"[\u3400-\u9fff]", docs[filename]), f"Generated native artifact is not English: {task}/{filename}")
            require(not re.search(r"\[Fill\]|PENDING_DESIGN|\[FEATURE NAME\]|\[TASK-ID\]|\[DATE\]", docs[filename]), f"Unfilled scaffold in {task}/{filename}")
        if len(docs) != 4:
            continue
        spec, plan, work = docs["spec.md"], docs["plan.md"], docs["tasks.md"]
        acs = re.findall(r"^\| (AC-\d+) \|", spec, flags=re.M)
        blocks = re.findall(r"^\| (B\d+) \|", plan, flags=re.M)
        checks = re.findall(r"^\| (V\d+) \|", plan, flags=re.M)
        items = re.findall(r"^- \[[ x]\] (T\d+) ", work, flags=re.M)
        require(len(acs) == len(set(acs)), f"Duplicate AC identity {task}")
        require(set(acs) == {a["id"] for a in feature["acceptance"]}, f"Registry/spec AC mismatch {task}")
        require(len(blocks) == len(set(blocks)), f"Duplicate block {task}")
        require(len(checks) == len(set(checks)), f"Duplicate verification {task}")
        require(len(items) == len(set(items)), f"Duplicate work item {task}")
        matrix = re.findall(r"^\| \[(AC-\d+)\]\(spec.md\) \| (.+)$", work, flags=re.M)
        require({a for a, _ in matrix} == set(acs) and len(matrix) == len(acs), f"Missing/duplicate AC evidence mapping {task}")
        for ac in feature["acceptance"]:
            require(ac["block"] in blocks, f"Missing planned block {task}/{ac['id']}")
            for check in ac["checks"]:
                require(check in checks, f"Missing planned check {task}/{ac['id']}/{check}")
            require(ac["sources"] and all(s in clauses for s in ac["sources"]), f"Missing/invalid exact source refs {task}/{ac['id']}")
            mapping = next((m for a, m in matrix if a == ac["id"]), "")
            for check in ac["checks"]:
                require(check in mapping, f"Missing required check in matrix {task}/{ac['id']}/{check}")
            for item in re.findall(r"\bT\d+\b", mapping):
                require(item in items, f"Unknown mapped work {task}/{ac['id']}/{item}")
            require(re.search(r"\| (NOT_RUN|PASS|FAIL|BLOCKED|STALE|N/A) \|", "| " + mapping), f"Invalid evidence status {task}/{ac['id']}")
            if "| PASS |" in "| " + mapping:
                require(bool(re.search(r"\]\(evidence/[^)]+\.md\)", mapping)), f"PASS without retained evidence {task}/{ac['id']}")
                for item in re.findall(r"\bT\d+\b", mapping):
                    require(bool(re.search(rf"^- \[x\] {item} ", work, flags=re.M)), f"PASS with unfinished mapped work {task}/{ac['id']}/{item}")
            for check in ac['checks']:
                row = next((r for r in plan.splitlines() if r.startswith('| '+check+' |')), '')
                command_path = re.search(r'(?:pytest -o addopts= |python )(\S+\.py)', row)
                verification_item = re.search(rf'{check} / (T\d+)', mapping)
                if command_path and verification_item:
                    line = next((line for line in work.splitlines() if re.match(rf'^- \[[ x]\] {verification_item[1]} ', line)), '')
                    require(command_path[1] in line, f"Planned command/work path disagreement {task}/{check}")
        for interface in feature["interfaces"]:
            name = interface.split("@")[0]
            require(f"### {name} at r1" in docs["TASK.md"], f"Missing canonical owned IF {task}/{name}")
            consumers = sorted(t for t, f in features.items() if interface in f['consumed_interfaces'])
            require('consumers: '+', '.join(consumers)+' |' in docs['TASK.md'], f"IF consumer roster drift {task}/{interface}")
        require(len(feature['consumed_interfaces']) == len(set(feature['consumed_interfaces'])), f"Repeated consumed interface {task}")
        for interface in feature['consumed_interfaces']:
            require(interface in interface_owners, f"Unowned consumed interface {task}/{interface}")
            require(interface.split('@')[0]+'@r1' in docs['TASK.md'], f"Consumed interface not referenced by TASK {task}/{interface}")
            require(interface_owners.get(interface) != task, f"Self-consumed interface {task}/{interface}")
        totals["acceptance_criteria"] += len(acs)
        totals["blocks"] += len(blocks)
        totals["checks"] += len(checks)
        totals["work_items"] += len(items)
        totals["interfaces"] += len(feature["interfaces"])
    for a in sources["architecture"]:
        require((BASE / a["path"]).is_file() and bool(a["owners"]), f"Unallocated architecture {a['path']}")
        require(all(o in features for o in a["owners"]), f"Unknown architecture owner {a['path']}")
    if level == "BOUNDARY":
        for p in BASE.rglob("*.md"):
            if "source" in p.relative_to(BASE).parts:
                continue  # Source package historical links are recorded dispositions, not generated links.
            body = text(p)
            require(not re.search(r"[\u3400-\u9fff]", body), f"Generated prose is not English: {p}")
            stripped = re.sub(r"```.*?```", "", body, flags=re.S)
            for target in re.findall(r"\]\((<[^>]+>|[^)]+)\)", stripped):
                target = target.strip("<>")
                if re.match(r"https?://|mailto:", target):
                    continue
                filepart, _, fragment = target.partition("#")
                dest = (p.parent / filepart).resolve() if filepart else p
                require(dest.exists(), f"Broken generated link {p.relative_to(BASE)} -> {target}")
                if fragment and dest.is_file() and dest.suffix == ".md":
                    headings = [re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in re.findall(r"^#+\s+(.+)$", text(dest), flags=re.M)]
                    require(fragment in headings, f"Broken generated anchor {p.relative_to(BASE)} -> {target}")
                totals["markdown_links"] += 1
        for n in ("capsules.md", "glossary.md", "guard-design.md"):
            source = BASE / "source/build-package" / n
            main = ROOT / "docs/architecture/build-package" / n
            require(text(source).replace("\r\n", "\n") == text(main).replace("\r\n", "\n"), f"Clarification source-copy drift {n}")
        require("rather than a general equivalence" in text(BASE / "source/build-package/capsules.md"), "Verification/gating clarification missing")
        require("upstream source revision" in text(BASE / "source/build-package/guard-design.md"), "Rubric adaptation source clarification missing")
        gate_spec = text(BASE / "M0-007/spec.md")
        require("sciencediscovery/result-evaluator" in gate_spec and "sciencediscovery/citation-reviewer" in gate_spec and "inapplicable" in gate_spec, "Required rubric adaptation acceptance missing")
        library = text(BASE / 'M0-003/TASK.md')
        for capsule in ('search','screening','hypothesis','poc','benchmark','scientific_evaluator','report','verifier'):
            require(capsule+'_capsule.md' in library, f"Missing PRD primary capsule binding {capsule}")
        require('primary-registry.json' in library and '5.2.1' in library, 'Primary capsule seeding identity missing')
    return {"level": level, "status": "FAIL" if ERRORS else "PASS", "scope": "Documentation structure/source/traceability only; runtime NOT_RUN", "totals": totals, "errors": ERRORS}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", choices=("BLOCK", "BOUNDARY"), required=True)
    args = parser.parse_args()
    result = validate(args.level)
    print(json.dumps(result, indent=2))
    sys.exit(1 if ERRORS else 0)
