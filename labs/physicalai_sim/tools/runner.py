"""Start, stop and use the simlab-runner container (PAS-M1-001 B00; research.md R5).

    python tools/runner.py up      [--data-dir ~/simlab-data] [--image simlab-runner:dev]
    python tools/runner.py down
    python tools/runner.py exec -- simlab doctor --json

`up` passes the image ID and host ID into the container so every run identity
names the exact build (replay identity is claimed only on the same machine and
build). The container has no network, no published port and no secrets.
Standard library only.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
COMPOSE = LAB / "docker" / "compose.yaml"


def env_for(a) -> dict:
    data = Path(os.path.expanduser(a.data_dir)).resolve()
    data.mkdir(parents=True, exist_ok=True)
    image_id = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", a.image], capture_output=True, text=True).stdout.strip()
    if not image_id:
        raise SystemExit(f"image {a.image} is not built; run: docker build -f docker/Dockerfile -t {a.image} .")
    rev = subprocess.run(["git", "-C", str(LAB), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(LAB), "status", "--porcelain", "--", "."], capture_output=True, text=True).stdout.strip()
    return {**os.environ, "SIMLAB_DATA_DIR": str(data), "SIMLAB_IMAGE": a.image, "SIMLAB_IMAGE_ID": image_id,
            "SIMLAB_HOST_ID": os.uname().nodename, "SIMLAB_SOURCE_REVISION": rev + ("+uncommitted" if dirty else ""),
            "SIMLAB_UID": str(os.getuid()), "SIMLAB_GID": str(os.getgid())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["up", "down", "exec"])
    ap.add_argument("--data-dir", default=os.environ.get("SIMLAB_DATA_DIR", "~/simlab-data"))
    ap.add_argument("--image", default=os.environ.get("SIMLAB_IMAGE", "simlab-runner:dev"))
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.op == "down":
        return subprocess.run(["docker", "compose", "-f", str(COMPOSE), "down"], env={**os.environ, "SIMLAB_DATA_DIR": "/tmp"}).returncode
    env = env_for(a)
    if a.op == "up":
        r = subprocess.run(["docker", "compose", "-f", str(COMPOSE), "up", "-d", "--no-build", "simlab-runner"], env=env)
        print(f"simlab-runner up: image {env['SIMLAB_IMAGE_ID'][:19]}, data {env['SIMLAB_DATA_DIR']}, revision {env['SIMLAB_SOURCE_REVISION']}")
        return r.returncode
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    return subprocess.run(["docker", "exec", "-i", "simlab-runner", *cmd]).returncode


if __name__ == "__main__":
    sys.exit(main())
