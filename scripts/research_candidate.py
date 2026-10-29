"""Capture reproducible uncommitted execution inputs, excluding credentials.

Native tasks.md/evidence are progress, so they are excluded. Source/contract
identity remains pinned separately. A candidate receipt is never a test pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SCOPE = ("jiuwenswarm", "jiuwenbox", "packages/jiuwenswarm-tui",
                 "deploy/m1", "scripts", "tests", "pyproject.toml", "uv.lock", "pytest.ini", ".importlinter",
                 "LICENSE", "OPEN_SOURCE_SOFTWARE_NOTICE.md",
                 "docs/code/Missions/M1/source-baseline.json")
IGNORED_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", "dist", "build",
                       "private", "protected", "codex-home", "evidence"}
SECRET_FILES = {"auth.json", "credentials.json", "secrets.json"}
PRODUCT_WORKSPACE_ROOTS = ("jiuwenswarm/channels/web/frontend/src/features/workspace",
                           "jiuwenswarm/resources/agent/workspace")
PUBLIC_TEMPLATE_FILES = frozenset({"jiuwenswarm/resources/.env.template"})


def excluded(path: Path, *, tracked_product_workspaces=frozenset(), tracked_public_templates=frozenset()) -> bool:
    lowered = path.name.casefold()
    return (any(part.casefold() in IGNORED_DIRECTORIES for part in path.parts)
            or lowered in SECRET_FILES
            or ((lowered == ".env" or lowered.startswith(".env.")) and path.as_posix() not in tracked_public_templates)
            or path.suffix.lower() in {".key", ".pem", ".p12", ".pfx", ".pyc"}
            or (any(part.casefold() == "workspace" for part in path.parts) and path.as_posix() not in tracked_product_workspaces))


def _tracked_public_inputs(root, paths):
    """Only exact tracked shipped paths bypass workspace/environment guards."""
    selected = [Path(item) for item in paths]
    permitted = (*PRODUCT_WORKSPACE_ROOTS, *sorted(PUBLIC_TEMPLATE_FILES))
    relevant = [prefix for prefix in map(Path, permitted)
                if ((root / prefix).exists() or (root / prefix).is_symlink())
                and any(scope.is_relative_to(prefix) or prefix.is_relative_to(scope) for scope in selected)]
    if not relevant:
        return frozenset()
    try:
        command = subprocess.run(["git", "ls-files", "--cached", "-z", "--", *permitted],
                                 cwd=root, capture_output=True, check=False)
    except OSError:
        raise ValueError("TRACKED_PRODUCT_INVENTORY_UNAVAILABLE") from None
    if command.returncode != 0:
        raise ValueError("TRACKED_PRODUCT_INVENTORY_UNAVAILABLE")
    allowed = set()
    for raw in command.stdout.split(b"\0"):
        if not raw:
            continue
        name = raw.decode("utf-8", errors="strict")
        path = Path(name)
        if (path.is_absolute() or ".." in path.parts
                or not (name in PUBLIC_TEMPLATE_FILES or any(path.is_relative_to(Path(prefix)) for prefix in PRODUCT_WORKSPACE_ROOTS))):
            raise ValueError("TRACKED_PRODUCT_SCOPE_INVALID")
        allowed.add(path.as_posix())
    return frozenset(allowed)


def _require_no_alias(path, root):
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError("EXECUTION_SYMLINK_NOT_ALLOWED")
        if not current.is_relative_to(root):
            raise ValueError("EXECUTION_SCOPE_OUTSIDE_ROOT")
        current = current.parent


def _files(root, paths):
    result = set()
    tracked = _tracked_public_inputs(root, paths)
    for item in paths:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("EXECUTION_SCOPE_OUTSIDE_ROOT")
        selected = root / relative
        _require_no_alias(selected, root)
        candidates = selected.rglob("*") if selected.is_dir() else [selected]
        for path in candidates:
            logical = path.relative_to(root)
            if excluded(logical, tracked_product_workspaces=tracked, tracked_public_templates=tracked & PUBLIC_TEMPLATE_FILES):
                continue
            _require_no_alias(path, root)
            if not path.exists() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(root):
                raise ValueError("EXECUTION_SYMLINK_NOT_ALLOWED")
            result.add(path)
    return sorted(result, key=lambda p: p.relative_to(root).as_posix())


def _head(root):
    command = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, check=False)
    return command.stdout.decode().strip() if command.returncode == 0 else None


def capture_candidate(root, *, paths=DEFAULT_SCOPE, snapshot=None):
    root = Path(root).resolve()
    paths = tuple(paths)
    files, payloads = [], []
    for path in _files(root, paths):
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino):
            raise ValueError("EXECUTION_INPUT_CHANGED_DURING_CAPTURE")
        name = path.relative_to(root).as_posix()
        files.append({"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
        if snapshot:
            payloads.append((name, payload))
    if not files:
        raise ValueError("EMPTY_EXECUTION_INPUTS")
    identity = {"schema_version": "1.0.0", "base_head": _head(root), "scope": list(paths), "files": files}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    result = {**identity, "candidate_id": hashlib.sha256(encoded).hexdigest(),
              "captured_at": datetime.now(timezone.utc).isoformat(), "acceptance": "NOT_ASSESSED"}
    if snapshot:
        snapshot = Path(snapshot)
        # Exclusive creation preserves old snapshots and their original bytes.
        with zipfile.ZipFile(snapshot, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in payloads:
                item = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                item.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(item, payload)
        result["snapshot"] = {"path": str(snapshot), "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()}
    return result


def verify_candidate(root, manifest):
    current = capture_candidate(root, paths=manifest["scope"])
    old = {p["path"]: p["sha256"] for p in manifest["files"]}
    new = {p["path"]: p["sha256"] for p in current["files"]}
    changed = sorted(path for path in old.keys() | new.keys() if old.get(path) != new.get(path))
    if current["base_head"] != manifest["base_head"]:
        changed.append("git:HEAD")
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["capture", "verify"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--scope", action="append")
    parser.add_argument("--snapshot")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    if arguments.operation == "verify":
        changed = verify_candidate(arguments.root, json.loads(output.read_text(encoding="utf-8-sig")))
        print(json.dumps({"changed_execution_inputs": changed}))
        return int(bool(changed))
    result = capture_candidate(arguments.root, paths=arguments.scope or DEFAULT_SCOPE, snapshot=arguments.snapshot)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"candidate_id": result["candidate_id"], "files": len(result["files"]), "acceptance": "NOT_ASSESSED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
