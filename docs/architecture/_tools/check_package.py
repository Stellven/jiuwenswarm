#!/usr/bin/env python3
"""Read-only integrity checker for the portable architecture package.

Uses only the Python standard library. Run from anywhere with
``python check_package.py [--root PACKAGE] [--repo CHECKOUT]``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path, PurePosixPath


SKIP_DIRS = {"old", ".obsidian", ".git", ".cache", "cache", "__pycache__"}
LINK_RE = re.compile(r"(!?)\[([^\]]*)\](?:\(\s*(?:<([^>]+)>|((?:[^()]|\([^()]*\))+?))(?:\s+[^)]*)?\s*\)|\[([^]]*)\])")
SHORTCUT_RE = re.compile(r"(?<!!)\[([^]]+)\](?![(:])")
REF_DEF_RE = re.compile(r"^\s*\[([^]]+)\]:\s*(?:<([^>]+)>|([^\s]+))", re.M)
HTML_LINK_RE = re.compile(r"(?:href|src)\s*=\s*['\"]([^'\"]+)['\"]", re.I)
ID_RE = re.compile(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", re.I)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def relpath(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def active(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return not any(p.lower() in SKIP_DIRS or p.startswith(".") and p.lower() in SKIP_DIRS for p in parts)


def markdown_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Ignore fenced code blocks, including indented content inside the fence.
    out, fence = [], None
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence is None and m:
            fence = m.group(1)[0]
            continue
        if fence is not None:
            if re.match(r"^\s{0,3}" + re.escape(fence) + r"{3,}\s*$", line):
                fence = None
            continue
        out.append(line)
    return "\n".join(out)


def slug_heading(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\- ]", "", text.lower(), flags=re.UNICODE)
    return text.strip().replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = markdown_text(path)
    found = set(ID_RE.findall(text))
    used: dict[str, int] = {}
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if m:
            base = slug_heading(m.group(1))
            n = used.get(base, 0)
            used[base] = n + 1
            found.add(base if n == 0 else f"{base}-{n}")
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, help="package root (defaults to parent of _tools)")
    ap.add_argument("--repo", type=Path, help="optional target-main checkout for live provenance checks")
    args = ap.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    repo = args.repo.resolve() if args.repo else None
    errors: list[str] = []
    counts = {"active_documents": 0, "links": 0, "manifest_files": 0, "snapshots": 0,
              "live_projections": 0, "live_authorities": 0}
    manifest_path = root / "package-manifest.json"
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"invalid manifest: {e}")
    else:
        errors.append("package-manifest.json is missing")
    if not isinstance(manifest, dict):
        errors.append("manifest must be an object")
        manifest = {}

    docs = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"} and active(p, root))
    counts["active_documents"] = len(docs)
    link_count = 0
    for doc in docs:
        text = markdown_text(doc)
        refs = {k.strip().lower(): (a or b) for k, a, b in REF_DEF_RE.findall(text)}
        used_refs = set()
        candidates: list[str] = []
        for m in LINK_RE.finditer(text):
            dest = m.group(3) or m.group(4)
            if dest:
                candidates.append(dest)
            elif m.group(5) is not None:
                label = (m.group(5) or m.group(2)).strip().lower()
                used_refs.add(label)
                dest = refs.get(label)
                if dest:
                    candidates.append(dest)
                else:
                    errors.append(f"{doc.relative_to(root).as_posix()}: unresolved reference link [{label}]")
        for m in SHORTCUT_RE.finditer(text):
            label = m.group(1).strip().lower()
            if label in refs and label not in used_refs:
                candidates.append(refs[label])
                used_refs.add(label)
        candidates.extend(HTML_LINK_RE.findall(text))
        for raw in candidates:
            link_count += 1
            value = urllib.parse.unquote(raw.strip())
            if not value or value.startswith(("#", "//")):
                fragment = urllib.parse.unquote(value[1:]) if value.startswith("#") else ""
                if fragment and fragment not in anchors(doc):
                    errors.append(f"{doc.relative_to(root).as_posix()}: missing fragment #{fragment}")
                continue
            parsed = urllib.parse.urlsplit(value)
            if parsed.scheme or parsed.netloc:
                continue
            target = (doc.parent / urllib.parse.unquote(parsed.path)).resolve() if parsed.path else doc.resolve()
            if not inside(target, root):
                errors.append(f"{doc.relative_to(root).as_posix()}: link escapes package: {raw}")
                continue
            if not target.exists():
                errors.append(f"{doc.relative_to(root).as_posix()}: missing local link: {raw}")
                continue
            fragment = urllib.parse.unquote(parsed.fragment)
            if fragment and target.suffix.lower() in {".md", ".txt"} and fragment not in anchors(target):
                errors.append(f"{doc.relative_to(root).as_posix()}: missing fragment in {raw}")
    counts["links"] = link_count

    def check_file_record(record: dict, label: str, expected_keys=("sha256", "hash")) -> Path | None:
        value = record.get("path")
        if not isinstance(value, str):
            errors.append(f"{label}: missing path")
            return None
        path = (root / value).resolve()
        if not inside(path, root):
            errors.append(f"{label}: path escapes package: {value}")
            return None
        if not path.is_file():
            errors.append(f"{label}: missing file: {value}")
            return path
        expected = next((record[k] for k in expected_keys if isinstance(record.get(k), str)), None)
        if not expected:
            errors.append(f"{label}: SHA-256 is required: {value}")
        if expected and digest(path).lower() != expected.lower():
            errors.append(f"{label}: SHA-256 mismatch: {value}")
        return path

    files = manifest.get("files", [])
    if not isinstance(files, list):
        errors.append("manifest files must be an array")
        files = []
    counts["manifest_files"] = len(files)
    recorded: set[str] = set()
    for i, rec in enumerate(files):
        if not isinstance(rec, dict):
            errors.append(f"files[{i}] must be an object")
            continue
        check_file_record(rec, f"files[{i}]")
        if isinstance(rec.get("path"), str):
            recorded.add(relpath(rec["path"]))
    # The inventory covers every shipped file (including images, schemas, scripts,
    # and dotfiles), while excluding the manifest itself to avoid a hash cycle.
    inventory = sorted(p for p in root.rglob("*") if p.is_file() and active(p, root)
                       and p.resolve() != manifest_path.resolve())
    required = {p.relative_to(root).as_posix() for p in inventory}
    missing = sorted(required - recorded)
    extra = sorted(recorded - required)
    if missing:
        errors.append(f"manifest omits {len(missing)} active package files")
    if extra:
        errors.append(f"manifest lists {len(extra)} paths outside the active package inventory")

    prd = manifest.get("current_prd")
    if isinstance(prd, dict):
        p = check_file_record(prd, "current_prd", ("sha256", "hash"))
        if not prd.get("sha256") and not prd.get("hash"):
            errors.append("current_prd must include sha256")
    else:
        errors.append("manifest current_prd must be an object with path and sha256")

    snapshots = manifest.get("snapshots", [])
    if not isinstance(snapshots, list):
        errors.append("snapshots must be an array")
        snapshots = []
    counts["snapshots"] = len(snapshots)
    if not snapshots:
        errors.append("snapshots must be a nonempty array")
    inputs_path = root / "_tools" / "snapshot-inputs.json"
    try:
        input_records = json.loads(inputs_path.read_text(encoding="utf-8"))["snapshots"]
        identity = lambda r: (r.get("path"), r.get("origin"), r.get("repository"), r.get("commit"), r.get("source_sha256"))
        if not isinstance(input_records, list) or {identity(x) for x in input_records if isinstance(x, dict)} != {identity(x) for x in snapshots if isinstance(x, dict)}:
            errors.append("snapshots do not match _tools/snapshot-inputs.json identities")
    except (OSError, ValueError, KeyError, TypeError):
        errors.append("_tools/snapshot-inputs.json is missing or invalid")
    target_main = manifest.get("target_main")
    if not isinstance(target_main, str) or not target_main:
        errors.append("manifest target_main commit is required")
    for i, rec in enumerate(snapshots):
        if not isinstance(rec, dict):
            continue
        if rec.get("repository") != "target-main" or rec.get("commit") != target_main:
            errors.append(f"snapshots[{i}] must identify target-main at manifest target_main")
    for i, rec in enumerate(snapshots):
        if not isinstance(rec, dict):
            errors.append(f"snapshots[{i}] must be an object")
            continue
        check_file_record(rec, f"snapshots[{i}]")
        if not rec.get("source_sha256"):
            errors.append(f"snapshots[{i}] must include source_sha256")
        elif isinstance(rec.get("path"), str):
            snapshot_path = (root / rec["path"]).resolve()
            if snapshot_path.is_file() and digest(snapshot_path) != rec["source_sha256"]:
                errors.append(f"snapshots[{i}]: snapshot bytes differ from source_sha256")
        originpath = rec.get("originpath") or rec.get("origin")
        if repo and rec.get("repository") == "target-main" and not (rec.get("commit") and originpath):
            errors.append(f"snapshots[{i}]: target-main provenance requires commit and origin")
        if repo and rec.get("repository") == "target-main" and rec.get("commit") and originpath:
            origin = str(originpath).replace("\\", "/").lstrip("/")
            try:
                result = subprocess.run(["git", "-C", str(repo), "show", f"{rec['commit']}:{origin}"], capture_output=True, check=True)
                actual = hashlib.sha256(result.stdout).hexdigest()
                if actual != rec["source_sha256"]:
                    errors.append(f"snapshots[{i}]: provenance mismatch for {origin}")
            except (subprocess.CalledProcessError, OSError) as e:
                errors.append(f"snapshots[{i}]: cannot verify {origin} at {rec['commit']}: {e}")

    projections = manifest.get("live_projections", [])
    if not isinstance(projections, list):
        errors.append("live_projections must be an array")
        projections = []
    counts["live_projections"] = len(projections)
    if len(projections) != 2:
        errors.append("live_projections must contain exactly the two canonical M1 projections")
    projection_origins = {r.get("origin") or r.get("originpath") for r in projections if isinstance(r, dict)}
    if projection_origins != {"docs/code/Missions/M1/TASKS.md", "docs/code/Missions/M1/TRIAL-1/TASK.md"}:
        errors.append("live_projections must cover canonical TASKS.md and TRIAL-1/TASK.md")
    for i, rec in enumerate(projections):
        if not isinstance(rec, dict):
            errors.append(f"live_projections[{i}] must be an object")
            continue
        check_file_record(rec, f"live_projections[{i}]")
        origin = rec.get("originpath") or rec.get("origin")
        if not origin or not rec.get("source_sha256"):
            errors.append(f"live_projections[{i}] must include origin and source_sha256")
        if repo and origin:
            source = (repo / str(origin)).resolve()
            if not inside(source, repo) or not source.is_file():
                errors.append(f"live_projections[{i}]: live source missing: {origin}")
            elif digest(source) != rec["source_sha256"]:
                errors.append(f"live_projections[{i}]: live source changed: {origin}")

    authorities = manifest.get("live_authorities", [])
    if not isinstance(authorities, list):
        errors.append("live_authorities must be an array")
        authorities = []
    counts["live_authorities"] = len(authorities)
    required_authorities = {"docs/code/Missions/M1/TASKS.md", "docs/code/Missions/M1/TRIAL-1/TASK.md",
                            "docs/code/Code_SOP.md", "docs/code/SPEC_KIT_WORKFLOW.md", "docs/code/VERIFICATION.md",
                            ".specify/memory/constitution.md", "plugins/spec-kit/README.md"}
    authority_paths = {r.get("path") for r in authorities if isinstance(r, dict)}
    if authority_paths != required_authorities:
        errors.append("live_authorities must list the seven canonical authority paths")
    for i, rec in enumerate(authorities):
        value = rec.get("path") if isinstance(rec, dict) else rec
        if not isinstance(value, str):
            errors.append(f"live_authorities[{i}] must include repo-relative path")
            continue
        if repo:
            target = (repo / value).resolve()
            if not inside(target, repo) or not target.is_file():
                errors.append(f"live_authorities[{i}]: live authority missing: {value}")

    if repo:
        try:
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            ancestor = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", str(target_main), head], capture_output=True)
            if ancestor.returncode != 0:
                errors.append("target_main is not an ancestor of checkout HEAD")
        except (subprocess.CalledProcessError, OSError) as e:
            errors.append(f"cannot verify target_main checkout ancestry: {e}")

    baseline = manifest.get("source_baseline")
    if isinstance(baseline, dict):
        blpath = baseline.get("path")
        if not isinstance(blpath, str):
            errors.append("source_baseline.path is required")
        else:
            bp = (root / blpath).resolve()
            if not inside(bp, root) or not bp.is_file():
                errors.append(f"source_baseline missing: {blpath}")
            else:
                if not baseline.get("sha256"):
                    errors.append("source_baseline.sha256 is required")
                elif digest(bp) != baseline["sha256"]:
                    errors.append("source_baseline SHA-256 mismatch")
                try:
                    data = json.loads(bp.read_text(encoding="utf-8"))
                    entries = data.get("architecture", []) if isinstance(data, dict) else []
                    if not isinstance(entries, list):
                        errors.append("source_baseline architecture must be an array")
                        entries = []
                    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    aggregate = baseline.get("architecture_aggregate_sha256")
                    data_aggregate = data.get("architecture_aggregate_sha256")
                    candidates = {hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
                    path_names = []
                    pairs = []
                    for item in entries:
                        s = item.get("path", "") if isinstance(item, dict) else ""
                        sh = item.get("sha256", "") if isinstance(item, dict) else ""
                        if not s or not sh:
                            errors.append("source_baseline architecture entries require path and sha256")
                            continue
                        path_names.append(s)
                        pairs.append(f"{s} {sh}")
                        local = root / Path(*PurePosixPath(s).parts)
                        if not inside(local, root) or not local.is_file():
                            errors.append(f"source_baseline core file missing: {s}")
                        elif digest(local) != sh:
                            errors.append(f"source_baseline core file SHA-256 mismatch: {s}")
                    expected_core = {p.relative_to(root).as_posix() for p in root.rglob("*.md")
                                     if active(p, root) and "sources" not in p.relative_to(root).parts}
                    if set(path_names) != expected_core or len(path_names) != len(set(path_names)):
                        errors.append("source_baseline must inventory every active core Markdown file exactly once")
                    canonical_digest = next(iter(candidates))
                    if not aggregate or aggregate != canonical_digest or data_aggregate != canonical_digest:
                        errors.append("source_baseline architecture aggregate must match canonical JSON in manifest and baseline")
                except (ValueError, OSError, AttributeError) as e:
                    errors.append(f"source_baseline invalid: {e}")
    else:
        errors.append("manifest source_baseline must be an object")

    # Cross-check the packaged PRD subsection IDs against the coverage allocation table.
    if isinstance(prd, dict) and isinstance(prd.get("path"), str) and p and p.is_file():
        coverage_files = list(root.rglob("coverage-allocation.md"))
        if not coverage_files:
            errors.append("coverage-allocation.md is missing")
        else:
            prd_text = markdown_text(p)
            cov_text = "\n".join(markdown_text(x) for x in coverage_files)
            id_rx = re.compile(r"(?<!\w)§\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
            prd_list = re.findall(r"^#{2,5}\s+([1-6]\.\d+(?:\.\d+)?)\s", prd_text, re.M)
            prd_ids = set(prd_list)
            cov_ids = set(id_rx.findall(cov_text))
            # Prefer IDs that appear in table rows, matching the published coverage format.
            table_ids = set()
            for line in cov_text.splitlines():
                if "|" in line:
                    table_ids.update(id_rx.findall(line))
            if table_ids:
                cov_ids = table_ids
            if len(prd_ids) != 184:
                errors.append(f"current PRD has {len(prd_ids)} subsection IDs; expected 184")
            if len(prd_list) != len(prd_ids):
                errors.append("current PRD contains duplicate subsection IDs")
            if prd_ids != cov_ids:
                errors.append(f"coverage allocation ID mismatch ({len(prd_ids - cov_ids)} absent from coverage, {len(cov_ids - prd_ids)} extra)")
            mapping_rows = [line for line in cov_text.splitlines() if line.strip().startswith("|") and not re.match(r"\s*\|\s*:?-{2,}", line)]
            data_rows = [line for line in mapping_rows if re.search(r"^\s*\|\s*§\s*[1-6]\.\d+", line)]
            row_ids, bad_rows = [], False
            for line in data_rows:
                cells = [x.strip() for x in line.strip().strip("|").split("|")]
                if len(cells) != 4 or any(not cell for cell in cells):
                    bad_rows = True
                elif (m := re.match(r"§\s*([1-6]\.\d+(?:\.\d+)?)\b", cells[0])):
                    row_ids.append(m.group(1))
            if bad_rows or len(row_ids) != len(set(row_ids)) or set(row_ids) != prd_ids:
                errors.append("coverage must contain exactly one complete four-column mapping row per PRD subsection")
            delivery_path = root / "delivery-phases.md"
            delivery_text = markdown_text(delivery_path) if delivery_path.is_file() else ""
            stage_rows = [line for line in delivery_text.splitlines() if line.strip().startswith("|") and re.search(r"\bStage\s+[0-8]\b", line, re.I)]
            stage_numbers = [re.search(r"\bStage\s+([0-8])\b", line, re.I).group(1) for line in stage_rows]
            missing_stages = [str(n) for n in range(9) if stage_numbers.count(str(n)) != 1]
            if missing_stages:
                errors.append("delivery-phases.md must contain exactly one explicit table row for each stage 0-8: " + ",".join(missing_stages))
            effort_names = {"Advanced intention compiler", "Agent Team / Cluster planning", "Dynamic CC discovery/binding",
                            "Heterogeneous model routing", "Alternate verifier", "Applicable OpenJiuwen Code Mode"}
            effort_rows = []
            phase_start = delivery_text.find("## Phase 3 is accounted M1 work")
            if phase_start >= 0:
                for line in delivery_text[phase_start:].splitlines():
                    if line.strip().startswith("|"):
                        cells = [x.strip() for x in line.strip().strip("|").split("|")]
                        if len(cells) == 3 and cells[0] in effort_names:
                            effort_rows.append(cells[0])
            if len(effort_rows) != 6 or set(effort_rows) != effort_names:
                errors.append("delivery-phases.md must map each of the six named Phase-3 efforts exactly once")

    # Validate canonical live-program identity from packaged projections (and live checkout in repo mode).
    task_register = root / "sources/live-program/TASKS.md"
    trial_task = root / "sources/live-program/TRIAL-1/TASK.md"
    if repo:
        task_register = repo / "docs/code/Missions/M1/TASKS.md"
        trial_task = repo / "docs/code/Missions/M1/TRIAL-1/TASK.md"
    try:
        register_text = markdown_text(task_register)
        trial_text = markdown_text(trial_task)
        register_rows = [line for line in register_text.splitlines() if re.match(r"\s*\|\s*\[TRIAL-1\]\(", line)]
        main_rows = [line for line in register_text.splitlines() if re.match(r"\s*\|\s*\[M1-001\]\(", line)]
        if len(register_rows) != 1 or "TRIAL-1/TASK.md" not in register_rows[0] or "docs/code/Missions/M1/TRIAL-1/" not in register_rows[0]:
            errors.append("canonical TASKS register must contain exactly one TRIAL-1 row with its colocated native feature")
        if len(main_rows) != 1 or not re.search(r"Codex CLI model invocation", main_rows[0], re.I):
            errors.append("canonical TASKS register must preserve main M1-001 as the Codex CLI model invocation")
        if not re.search(r"^#\s+TASK:\s*TRIAL-1\b", trial_text, re.M) or "docs/code/Missions/M1/TRIAL-1/" not in trial_text or "TRIAL-IF-001" not in trial_text:
            errors.append("canonical TRIAL-1 TASK must preserve its colocated feature path and TRIAL-IF-001 identity")
    except OSError as e:
        errors.append(f"canonical live-program registration files missing: {e}")

    result = {"status": "PASS" if not errors else "FAIL", "mode": "repo" if repo else "portable",
              "counts": counts, "errors": errors, "runtime": "NOT_RUN"}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
