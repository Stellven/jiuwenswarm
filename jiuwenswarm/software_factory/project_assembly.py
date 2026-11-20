"""Split a pinned Git tree into source modules and reassemble it from their manifests.

Modules own paths, modes, and object IDs. The project's Git object store holds
the shared source bytes, so repeated decompositions do not duplicate large files.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile


PROJECT_SCHEMA = "factory.project-assembly.v1"
MODULE_SCHEMA = "factory.project-source-module.v1"
COMMIT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
MODULE_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,95}")
GIT_MODES = {"100644", "100755", "120000", "160000"}


def _git(checkout: Path, *arguments: str) -> list[str]:
    return ["git", "--no-replace-objects", "-C", str(checkout), *arguments]


def _safe_path(path: str) -> None:
    parsed = PurePosixPath(path)
    if (
        not parsed.parts
        or parsed.is_absolute()
        or parsed.as_posix() != path
        or any(part.casefold() in {"..", ".git"} for part in parsed.parts)
        or any(char in path for char in ("\\", "\0", ":"))
    ):
        raise ValueError(f"Source path cannot be safely materialized: {path!r}")


def _tree(checkout: Path, revision: str) -> tuple[str, dict[str, dict[str, str]]]:
    if not isinstance(revision, str) or not COMMIT_ID.fullmatch(revision):
        raise ValueError("A full pinned Git commit ID is required")
    commit = subprocess.check_output(_git(checkout, "rev-parse", "--verify", f"{revision}^{{commit}}"))
    if commit.decode("ascii").strip() != revision:
        raise ValueError("Revision must identify the pinned commit object")
    tree = subprocess.check_output(_git(checkout, "rev-parse", f"{revision}^{{tree}}")).decode("ascii").strip()
    listing = subprocess.check_output(_git(checkout, "ls-tree", "-r", "-z", "--full-tree", tree))
    entries = {}
    for record in listing.rstrip(b"\0").split(b"\0") if listing else ():
        metadata, path_bytes = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = os.fsdecode(path_bytes)
        _safe_path(path)
        if mode not in GIT_MODES or kind != ("commit" if mode == "160000" else "blob"):
            raise ValueError(f"Unsupported Git object in {path!r}: {mode} {kind}")
        if path in entries:
            raise ValueError(f"Pinned tree contains duplicate source path: {path!r}")
        entries[path] = {"path": path, "mode": mode, "oid": oid}
    for path in entries:
        if any(parent.as_posix() in entries for parent in PurePosixPath(path).parents):
            raise ValueError(f"Pinned tree contains a file used as a directory: {path!r}")
    return tree, entries


def _write_json(path: Path, value: dict) -> str:
    data = (json.dumps(value, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _publish(staged: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    staged.rename(destination)


def split_project(
    checkout: Path,
    revision: str,
    destination: Path,
    classify: Callable[[str], str],
) -> dict:
    """Publish a disjoint source module manifest per group and a project index."""
    tree, entries = _tree(Path(checkout).resolve(), revision)
    groups = defaultdict(list)
    for path, entry in entries.items():
        module = classify(path)
        if not isinstance(module, str) or not MODULE_ID.fullmatch(module):
            raise ValueError(f"Invalid module ID for {path!r}: {module!r}")
        groups[module].append(entry)

    destination = Path(destination).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".split-") as pending:
        staged = Path(pending) / "project"
        (staged / "modules").mkdir(parents=True)
        manifest = {
            "schema": PROJECT_SCHEMA,
            "revision": revision,
            "tree": tree,
            "file_count": len(entries),
            "modules": [],
        }
        for module, files in sorted(groups.items()):
            relative = f"modules/{module}.json"
            digest = _write_json(
                staged / relative,
                {"schema": MODULE_SCHEMA, "id": module, "revision": revision, "files": files},
            )
            manifest["modules"].append(
                {"id": module, "manifest": relative, "sha256": digest, "file_count": len(files)}
            )
        _write_json(staged / "project.json", manifest)
        _publish(staged, destination)
    return manifest


def _read_modules(manifest_path: Path, manifest: dict, original: dict) -> dict:
    reconstructed = {}
    seen_modules = set()
    module_dir = manifest_path.parent / "modules"
    if module_dir.is_symlink():
        raise ValueError("Module directory must be owned by the project index")
    for record in manifest["modules"]:
        module = record["id"]
        if not MODULE_ID.fullmatch(module) or module in seen_modules:
            raise ValueError(f"Invalid or duplicate module: {module!r}")
        seen_modules.add(module)
        relative = f"modules/{module}.json"
        if record["manifest"] != relative:
            raise ValueError(f"Module manifest path mismatch: {module}")
        path = manifest_path.parent / relative
        if path.is_symlink():
            raise ValueError(f"Module manifest must be owned by the project index: {module}")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError(f"Module manifest digest mismatch: {module}")
        artifact = json.loads(data)
        if (
            artifact["schema"] != MODULE_SCHEMA
            or artifact["id"] != module
            or artifact["revision"] != manifest["revision"]
            or len(artifact["files"]) != record["file_count"]
        ):
            raise ValueError(f"Module manifest metadata mismatch: {module}")
        for entry in artifact["files"]:
            filename = entry["path"]
            if filename in reconstructed or entry != original.get(filename):
                raise ValueError(f"Module has duplicate or incompatible source entry: {filename!r}")
            reconstructed[filename] = entry
    missing = original.keys() - reconstructed.keys()
    if missing or len(reconstructed) != manifest["file_count"]:
        raise ValueError(f"Project source is incomplete: {len(missing)} tracked paths missing")
    return reconstructed


def _materialize(checkout: Path, tree: str, entries: dict, staged: Path) -> dict:
    gitlinks = {}
    hash_name = "sha1" if len(tree) == 40 else "sha256"
    with subprocess.Popen(
        _git(checkout, "cat-file", "--batch"), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    ) as process:
        for relative, entry in entries.items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            mode, oid = entry["mode"], entry["oid"]
            if mode == "160000":
                gitlinks[relative] = oid
                path.mkdir()
                continue
            process.stdin.write(oid.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[0] != oid.encode("ascii") or header[1] != b"blob":
                raise ValueError(f"Pinned blob unavailable for {relative!r}")
            payload = process.stdout.read(int(header[2]))
            framing = b"blob " + str(len(payload)).encode("ascii") + b"\0"
            if process.stdout.read(1) != b"\n" or hashlib.new(hash_name, framing + payload).hexdigest() != oid:
                raise ValueError(f"Pinned blob failed Git content verification: {relative!r}")
            if mode == "120000":
                path.symlink_to(os.fsdecode(payload))
            else:
                with path.open("xb") as output:
                    output.write(payload)
                path.chmod(0o755 if mode == "100755" else 0o644)
        process.stdin.close()
        if process.wait():
            raise ValueError("Git failed to read one or more pinned blobs")
    return gitlinks


def assemble_project(checkout: Path, manifest_path: Path, destination: Path) -> dict:
    """Validate all module artifacts, then publish their reconstructed source tree.

    Gitlinks are recorded in the returned receipt and materialized as empty
    directories. Fetching and building external submodules is a separate action.
    """
    checkout = Path(checkout).resolve()
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["schema"] != PROJECT_SCHEMA:
        raise ValueError("Unsupported project assembly manifest")
    revision = manifest["revision"]
    tree, original = _tree(checkout, revision)
    if tree != manifest["tree"]:
        raise ValueError("Project index does not match the pinned source tree")
    entries = _read_modules(manifest_path, manifest, original)

    destination = Path(destination).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".assemble-") as pending:
        staged = Path(pending) / "source"
        staged.mkdir()
        gitlinks = _materialize(checkout, tree, entries, staged)
        _publish(staged, destination)
    return {
        "schema": PROJECT_SCHEMA,
        "revision": revision,
        "tree": tree,
        "source_tree_matches": True,
        "module_count": len(manifest["modules"]),
        "file_count": len(entries),
        "source": str(destination),
        "gitlinks": gitlinks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    split = commands.add_parser("split", help="Create disjoint module manifests from a Git commit")
    split.add_argument("checkout", type=Path)
    split.add_argument("revision")
    split.add_argument("destination", type=Path)
    split.add_argument("--group", metavar="MODULE=PREFIX", action="append", default=[])
    split.add_argument("--default-module", default="project-support")
    assemble = commands.add_parser("assemble", help="Reconstruct source using module manifests")
    assemble.add_argument("checkout", type=Path)
    assemble.add_argument("manifest", type=Path)
    assemble.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "split":
        rules = []
        for rule in arguments.group:
            module, separator, prefix = rule.partition("=")
            if not separator or not MODULE_ID.fullmatch(module) or not prefix:
                split.error("--group requires MODULE=PREFIX")
            rules.append((prefix.rstrip("/"), module))
        rules.sort(key=lambda rule: len(rule[0]), reverse=True)

        def classify(path: str) -> str:
            return next(
                (module for prefix, module in rules if path == prefix or path.startswith(prefix + "/")),
                arguments.default_module,
            )

        receipt = split_project(arguments.checkout, arguments.revision, arguments.destination, classify)
    else:
        receipt = assemble_project(arguments.checkout, arguments.manifest, arguments.destination)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
