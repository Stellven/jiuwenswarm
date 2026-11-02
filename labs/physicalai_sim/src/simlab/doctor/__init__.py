"""simlab doctor: environment readiness with typed failures (PAS-M1-001 B10; PRD SL-10.D; AC-016).

Each item is `ready`, `failed` (with a stable code) or `info`. The doctor is
ready only when every non-info item is ready. Degraded set-ups it must name:
a data directory inside the repository, a writable source mount, a credential
in the environment or a credential file, a reachable network, missing seccomp,
an executor that can open a socket, an engine version other than the pinned one,
and a SIMLAB-owned TCP listener.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CREDENTIAL_ENV = re.compile(r"(TOKEN|SECRET|PASSWORD|API_KEY|APIKEY|CREDENTIAL|ACCESS_KEY|PRIVATE_KEY|AUTH)", re.I)
CREDENTIAL_FILES = ["~/.codex/auth.json", "~/.claude/.credentials.json", "~/.aws/credentials", "~/.config/gcloud/credentials.db",
                    "~/.netrc", "~/.ssh/id_rsa", "~/.ssh/id_ed25519", "/run/secrets"]


def _item(name: str, ok: bool, code: str, detail, info: bool = False) -> dict:
    return {"item": name, "status": "info" if info else ("ready" if ok else "failed"), "code": None if ok or info else code, "detail": detail}


def pinned_versions(lock: Path | None) -> dict:
    """Versions pinned in uv.lock (the source of the image build)."""
    if lock is None or not lock.is_file():
        return {}
    out, name = {}, None
    for line in lock.read_text().splitlines():
        if line.startswith("name = "):
            name = line.split('"')[1]
        elif line.startswith("version = ") and name:
            out[name] = line.split('"')[1]
            name = None
    return out


def _probe_executor() -> dict:
    """Spawn a confined worker-like process and try a socket; it must be refused by the kernel filter."""
    code = ("import json, ctypes\nfrom simlab.executors.mujoco import sandbox\n"
            "info = sandbox.install({'cpu_s': 10, 'memory_mb': 1024})\n"
            "libc = ctypes.CDLL(None, use_errno=True)\nfd = libc.socket(2, 1, 0)\n"
            "print(json.dumps({'seccomp_mode': info['seccomp_mode'], 'socket_fd': fd, 'errno': ctypes.get_errno()}))\n")
    from simlab.runner.core import worker_env  # noqa: PLC0415

    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, env=worker_env(), cwd="/tmp")
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-500:]}
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
        return {"error": repr(e)}


def _routes() -> list[str]:
    try:
        lines = Path("/proc/net/route").read_text().splitlines()[1:]
    except OSError:
        return []
    return [ln.split()[0] for ln in lines if ln.split() and ln.split()[0] != "lo"]


def _tcp_listeners_of(pids: set[int]) -> list[str]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    try:
        import port_audit  # noqa: PLC0415
    except ImportError:
        return []
    return [f"{l['ip']}:{l['port']} (pid {l['pid']})" for l in port_audit.listeners() if l["pid"] in pids]


def run(data_dir: str | None = None, *, source_dir: str | None = None, lock: str | None = None, allow_network: bool = False) -> dict:
    items = []
    import mujoco  # noqa: PLC0415
    import numpy  # noqa: PLC0415

    from simlab import build_identity  # noqa: PLC0415
    from simlab.contracts import SimlabError  # noqa: PLC0415
    from simlab.store import resolve_data_dir  # noqa: PLC0415

    # versions against the lockfile
    b = build_identity.current()
    lock_path = Path(lock) if lock else None
    if lock_path is None:
        try:
            lock_path = build_identity.project_root() / "uv.lock"
        except FileNotFoundError:
            lock_path = None
    pins = pinned_versions(lock_path)
    want = pins.get("mujoco")
    items.append(_item("engine_version", want is not None and want == mujoco.__version__, "D_ENGINE_VERSION",
                       {"installed": mujoco.__version__, "pinned": want, "lock": str(lock_path) if lock_path else None}))
    items.append(_item("numpy_version", pins.get("numpy") in (None, numpy.__version__), "D_DEPENDENCY_VERSION",
                       {"installed": numpy.__version__, "pinned": pins.get("numpy")}))
    items.append(_item("python", sys.version_info[:2] == (3, 12), "D_PYTHON_VERSION", {"version": sys.version.split()[0]}))
    items.append(_item("build_identity", bool(b.get("build_id")), "D_BUILD_IDENTITY",
                       {"build_id": b.get("build_id"), "source": b.get("source"), "image_id": b.get("image_id")}))
    # data directory
    try:
        d = resolve_data_dir(data_dir, create=False)
        items.append(_item("data_dir", True, "D_DATA_DIR", {"path": str(d), "free_gb": round(shutil.disk_usage(d).free / 2**30, 1)}))
    except SimlabError as e:
        items.append(_item("data_dir", False, "D_DATA_DIR", e.message))
    # read-only source
    src = Path(source_dir or os.environ.get("SIMLAB_SOURCE_DIR") or Path(__file__).resolve().parents[1])
    writable = os.access(src, os.W_OK)
    try:
        ro_fs = bool(os.statvfs(src).f_flag & os.ST_RDONLY)
    except OSError:
        ro_fs = False
    in_container = os.environ.get("SIMLAB_IN_CONTAINER") == "1"
    items.append(_item("source_read_only", (not writable) or ro_fs, "D_SOURCE_WRITABLE",
                       {"path": str(src), "writable_by_this_user": writable, "read_only_filesystem": ro_fs,
                        "note": "required inside the runner container and check groups" if in_container else "host development checkout"},
                       info=not in_container and source_dir is None and not os.environ.get("SIMLAB_SOURCE_DIR")))
    # credentials
    env_hits = sorted(k for k in os.environ if CREDENTIAL_ENV.search(k))
    file_hits = [p for p in CREDENTIAL_FILES if Path(os.path.expanduser(p)).exists()]
    items.append(_item("no_credentials_in_env", not env_hits, "D_CREDENTIALS_PRESENT", {"variables": env_hits}))
    items.append(_item("no_credential_files", not file_hits, "D_CREDENTIALS_PRESENT", {"files": file_hits},
                       info=not in_container and not os.environ.get("SIMLAB_STRICT_CREDENTIALS")))
    # network
    routes = _routes()
    items.append(_item("container_network_none", allow_network or not routes, "D_NETWORK_REACHABLE",
                       {"non_loopback_routes": routes, "note": "phase 1 runs the runner with network_mode none"},
                       info=not in_container and not os.environ.get("SIMLAB_STRICT_NETWORK")))
    probe = _probe_executor()
    items.append(_item("seccomp_available", probe.get("seccomp_mode") == 2, "D_SECCOMP_UNAVAILABLE", probe))
    items.append(_item("executor_network_denied", probe.get("socket_fd") == -1, "D_EXECUTOR_NETWORK", probe))
    # host ports: SIMLAB itself opens none
    tcp = _tcp_listeners_of({os.getpid(), os.getppid()})
    items.append(_item("no_simlab_tcp_listener", not tcp, "D_HOST_PORT", {"listeners": tcp}))
    # inventory
    mem = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        if k in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            mem[k] = int(v.split()[0]) // 1024
    gpu = None
    if shutil.which("nvidia-smi"):
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"], capture_output=True, text=True)
        gpu = r.stdout.strip() or None
    items.append(_item("inventory", True, "", {"cpu_threads": os.cpu_count(), "memory_mb": mem, "gpu": gpu or "none visible",
                                               "in_container": in_container}, info=True))
    ready = all(i["status"] != "failed" for i in items)
    return {"record": "simlab-doctor", "ready": ready, "failed": [i["item"] for i in items if i["status"] == "failed"], "items": items}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="simlab doctor")
    ap.add_argument("--data-dir")
    ap.add_argument("--source-dir")
    ap.add_argument("--lock")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = run(a.data_dir, source_dir=a.source_dir, lock=a.lock)
    if a.json:
        print(json.dumps(out, indent=1, sort_keys=True))
    else:
        print("ready" if out["ready"] else "NOT READY: " + ", ".join(out["failed"]))
        for i in out["items"]:
            print(f"  {i['status']:6} {i['item']}" + (f"  [{i['code']}]" if i["code"] else ""))
    return 0 if out["ready"] else 1
