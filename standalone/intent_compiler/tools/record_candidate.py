"""Record dirty-tree execution identity without collecting credentials or diffs."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path


def capture(output: Path):
    root = Path(__file__).resolve().parents[3]
    package = root / "standalone/intent_compiler"
    feature = root / "docs/code/Missions/M0/M0-001"
    paths = [p for p in package.rglob("*") if p.is_file() and not any(
        part in {"node_modules", "__pycache__", ".pytest_cache", "intent-state", "intent-input"}
        for part in p.relative_to(package).parts)]
    paths += [root / "AGENTS.md", root / ".specify/memory/constitution.md"]
    paths += [feature / name for name in ("TASK.md", "spec.md", "plan.md", "source-baseline.json")]
    files = [{"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size,
              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths) if p.exists()]
    identity = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)
    dirty = git("diff", "--binary", "--", "standalone/intent_compiler", "docs/code/Missions/M0/M0-001/spec.md", "docs/code/Missions/M0/M0-001/plan.md", "docs/code/Missions/M0/M0-001/TASK.md")
    record = {"schema_version": "1.0.0", "candidate": "sha256:" + identity,
              "recorded_at": datetime.now(timezone.utc).isoformat(),
              "head": git("rev-parse", "HEAD").decode().strip(),
              "branch": git("branch", "--show-current").decode().strip(),
              "relevant_tracked_diff_sha256": hashlib.sha256(dirty).hexdigest(),
              "files": files, "platform": platform.platform(), "python": sys.version,
              "dependencies": sorted([f"{d.metadata['Name']}=={d.version}" for d in distributions()]),
              "scope": "Execution code/tests/build assets/contracts/profiles/dependency and normative inputs; ordinary progress, raw evidence and changing usage counters excluded"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": record["candidate"], "files": len(files), "output": str(output)}))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    capture(parser.parse_args().output)
