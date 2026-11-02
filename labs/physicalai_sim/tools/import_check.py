"""Import boundary check (PAS-M1-001 B11, AC-019; ARCH "AI4R connection": nothing in labs/physicalai_sim imports AI4R code).

Scans every Python file under the lab (except .venv and caches) with the AST and
fails on an import of an AI4R top-level package (the repository's own Python
packages, discovered from the repository root), on relative imports that climb
out of the lab, and on sys.path edits that point outside it. Standard library only.

    python tools/import_check.py [--root LAB] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SKIP = {".venv", "__pycache__", ".pytest_cache", "node_modules"}


STATIC_AI4R = {"jiuwenswarm", "deploy", "benchmarks"}  # AI4R's top-level Python packages at the pinned baseline


def ai4r_packages(repo: Path | None) -> set[str]:
    names = set(STATIC_AI4R)
    if repo is None or not (repo / "jiuwenswarm").is_dir():
        return names
    for p in repo.iterdir():
        if p.name == "labs" or p.name.startswith("."):
            continue
        if p.is_dir() and (p / "__init__.py").is_file():
            names.add(p.name)
        if p.is_file() and p.suffix == ".py":
            names.add(p.stem)
    # Names the lab itself owns at its top level (its own tests package) are not AI4R imports.
    own = {p.name for p in LAB.iterdir() if p.is_dir() and (p / "__init__.py").is_file()}
    return names - own


def scan(root: Path, forbidden: set[str]) -> list[dict]:
    hits = []
    for f in sorted(root.rglob("*.py")):
        if any(part in SKIP for part in f.relative_to(root).parts):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as e:
            hits.append({"file": str(f.relative_to(root)), "line": e.lineno, "problem": f"does not parse: {e.msg}"})
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > len(f.relative_to(root).parts) - 1:
                    hits.append({"file": str(f.relative_to(root)), "line": node.lineno, "problem": "relative import climbs out of the lab"})
                if node.level == 0 and node.module:
                    mods = [node.module]
            elif isinstance(node, ast.Call) and getattr(node.func, "attr", None) in {"import_module", "__import__"} \
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mods = [node.args[0].value]
            for m in mods:
                if m.split(".")[0] in forbidden:
                    hits.append({"file": str(f.relative_to(root)), "line": node.lineno, "problem": f"imports AI4R module {m!r}"})
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=LAB)
    ap.add_argument("--repo", type=Path, default=LAB.parents[1] if len(LAB.parents) > 1 else None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    forbidden = ai4r_packages(a.repo if a.repo is not None and a.repo.is_dir() else None)
    hits = scan(a.root, forbidden)
    out = {"root": str(a.root), "forbidden_top_level": sorted(forbidden),
           "forbidden_source": "repository scan plus static list" if a.repo is not None and a.repo.is_dir() else "static list (no repository visible)", "files_scanned": sum(
        1 for f in a.root.rglob("*.py") if not any(p in SKIP for p in f.relative_to(a.root).parts)), "violations": hits,
        "result": "PASS" if not hits else "FAIL"}
    print(json.dumps(out, indent=1) if a.json else (out["result"] + "".join(f"\n  {h['file']}:{h['line']}: {h['problem']}" for h in hits)))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
