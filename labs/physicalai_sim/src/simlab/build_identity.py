"""Build identity: a content digest of the lockfile, project metadata and source.

Written into the image at build time (/usr/local/share/simlab-build.json) and
recomputed by the doctor. Same machine + same build is the condition for exact
replay (TP Rules), so this digest is part of every run identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

BUILD_FILE = Path("/usr/local/share/simlab-build.json")


def project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "uv.lock").is_file():
            return parent
    raise FileNotFoundError("pyproject.toml and uv.lock not found above " + str(here))


def tree_digest(root: Path, rel_dirs: list[str], files: list[str]) -> tuple[str, int]:
    h = hashlib.sha256()
    count = 0
    paths: list[Path] = [root / f for f in files]
    for d in rel_dirs:
        base = root / d
        if base.is_dir():
            paths.extend(p for p in base.rglob("*") if p.is_file())
    for p in sorted(set(paths), key=lambda x: x.relative_to(root).as_posix()):
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode() + b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
        count += 1
    return h.hexdigest(), count


def compute(root: Path | None = None) -> dict:
    root = root or project_root()
    src_digest, n_src = tree_digest(root, ["src"], [])
    lock = (root / "uv.lock").read_bytes()
    try:
        import mujoco  # noqa: PLC0415

        mj = mujoco.__version__
    except Exception:  # pragma: no cover - reported, not hidden
        mj = None
    build_id, _ = tree_digest(root, ["src"], ["uv.lock", "pyproject.toml"])
    return {
        "record": "simlab-build-identity",
        "build_id": build_id,
        "source_digest": src_digest,
        "source_files": n_src,
        "lock_sha256": hashlib.sha256(lock).hexdigest(),
        "pyproject_sha256": hashlib.sha256((root / "pyproject.toml").read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "mujoco": mj,
        "machine": platform.machine(),
    }


def current() -> dict:
    """Identity of the running build: the baked file in an image, else computed."""
    if BUILD_FILE.is_file():
        data = json.loads(BUILD_FILE.read_text())
        data["source"] = "image"
    else:
        data = compute()
        data["source"] = "computed"
    data["image_id"] = os.environ.get("SIMLAB_IMAGE_ID", "none")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", type=Path)
    args = ap.parse_args(argv)
    data = compute()
    text = json.dumps(data, indent=2, sort_keys=True)
    if args.write:
        args.write.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
