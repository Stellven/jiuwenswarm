"""SIMLAB check groups (PAS-M1-001 B11, AC-018; test plan "Check groups"; pattern: deploy/m1/capsule_checks.py).

One command per group. On the host this launches the simlab-runner image with no
network, a memory cap ([confirm: 4 GB]) and the source mounted read-only, and
runs the same file inside the container, which writes the five evidence files:
launch.json, source-manifest.json, pytest.log, junit.xml, result.json.

    python tools/check_groups.py --group core|executors|benchmark|all [--output DIR] [--timeout-s N] [--live]
    python tools/check_groups.py --group core --negative-control source-change    # expects exit 2
    python tools/check_groups.py --group core --negative-control timeout          # expects exit 124

Exit codes: 0 passed, 1 failed, 2 source changed during the run, 124 timeout.
Live or model-dependent tests are skipped unless --live, and reported as skipped.
Standard library only (the inside half runs under the image's Python).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[1] if len(LAB.parents) > 1 else LAB
IMAGE = os.environ.get("SIMLAB_IMAGE", "simlab-runner:dev")
MEMORY = os.environ.get("SIMLAB_CHECK_MEMORY", "4g")  # [confirm: 4 GB] (TASKS §6 Q-01)
BOUNDARY_CORE = ["test_x13_findings.py", "test_requests.py", "test_authoring.py", "test_runner.py", "test_checks.py", "test_data.py",
                 "test_tool_parity.py", "test_doctor.py"]
BOUNDARY_EXEC = ["test_x15_replay_branch.py", "test_always.py"]
GROUPS = {
    "core": ["tests/core"] + [f"tests/boundary/{f}" for f in BOUNDARY_CORE],
    "executors": ["tests/executors"] + [f"tests/boundary/{f}" for f in BOUNDARY_EXEC],
    "benchmark": ["benchmarks/simlab_bench/tests", "tests/bench"],
}
SCOPES = ["src", "tests", "tools", "benchmarks/simlab_bench", "docker", "pyproject.toml", "uv.lock"]


def capture_source(root: Path) -> dict:
    paths = set()
    for scope in SCOPES:
        p = root / scope
        if p.is_file():
            paths.add(p)
        elif p.is_dir():
            paths.update(x for x in p.rglob("*") if x.is_file())
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if "__pycache__" not in p.parts and p.suffix != ".pyc" and ".pytest_cache" not in p.parts}


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cgroup() -> dict:
    out = {}
    try:
        out["memory_peak_mb"] = round(int(Path("/sys/fs/cgroup/memory.peak").read_text()) / 2**20, 1)
    except (OSError, ValueError):
        out["memory_peak_mb"] = None
    try:
        for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines():
            k, v = line.split()
            if k == "usage_usec":
                out["cpu_s"] = round(int(v) / 1e6, 3)
    except OSError:
        out["cpu_s"] = None
    try:
        out["memory_max"] = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    except OSError:
        out["memory_max"] = None
    return out


# ------------------------------------------------------------------ inside the container
def inside(a) -> int:
    root = Path("/src")
    out = Path("/evidence")
    targets = sorted({t for g in GROUPS.values() for t in g}) if a.group == "all" else GROUPS[a.group]
    targets = [t for t in targets if (root / t).exists()]
    before = capture_source(root)
    write(out / "source-manifest.json", before)
    source_hash = hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    cmd = [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider", "-q", "-rA", *targets, "--tb=short",
           "--junitxml=" + str(out / "junit.xml"), *(["--live"] if a.live else [])]
    result = {"schema": "simlab-check-group:1", "group": a.group, "targets": targets, "command": cmd, "python": sys.version,
              "source_manifest_sha256": source_hash, "timeout_s": a.timeout_s, "status": "running",
              "scope": "SIMLAB phase 1 checks inside simlab-runner; live and model-dependent tests are opt-in (--live)"}
    write(out / "result.json", result)
    t0 = time.monotonic()
    with (out / "pytest.log").open("xb") as log:
        proc = subprocess.Popen(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=a.timeout_s)
            result["status"] = "passed" if code == 0 else "failed"
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as e:
            result["status"] = "timeout" if isinstance(e, subprocess.TimeoutExpired) else "interrupted"
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    continue
            code = 124 if result["status"] == "timeout" else 130
    result["elapsed_s"] = round(time.monotonic() - t0, 3)
    after = capture_source(root)
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    result["source_changes"] = changed
    if changed:
        result["status"], code = "source_changed", 2
    junit = out / "junit.xml"
    if junit.exists():
        suites = list(ET.parse(junit).getroot().iter("testsuite"))
        counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
        result["counts"] = counts
        result["skipped_tests"] = [f"{c.get('classname')}::{c.get('name')}: {(c.find('skipped').get('message') or '')[:160]}"
                                   for c in ET.parse(junit).getroot().iter("testcase") if c.find("skipped") is not None]
    result["exit_code"] = code
    result["resources_container"] = cgroup()
    result["files"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name != "result.json"}
    write(out / "result.json", result)
    print(json.dumps({k: result.get(k) for k in ("group", "status", "exit_code", "counts", "elapsed_s")}, sort_keys=True))
    return code


# ------------------------------------------------------------------ on the host
def host(a) -> int:
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out = (a.output or (REPO / ".test_logs" / "simlab" / a.group / run_id)).resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o777)
    timeout = a.timeout_s
    if a.negative_control == "timeout":
        timeout = 5
    name = f"simlab-check-{a.group}-{uuid.uuid4().hex[:8]}"
    uid, gid = os.getuid(), os.getgid()
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "none", "--memory", MEMORY, "--memory-swap", MEMORY,
           "--pids-limit", "1024", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
           "--user", f"{uid}:{gid}", "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g",
           "--tmpfs", f"/data:rw,nosuid,nodev,size=2g,uid={uid},gid={gid}",
           "-v", f"{LAB}:/src:ro", "-v", f"{out}:/evidence:rw",
           "-e", "SIMLAB_IN_CONTAINER=1", "-e", "SIMLAB_TEST_DATA_ROOT=/data", "-e", "SIMLAB_SOURCE_DIR=/src/src",
           "-e", "PYTHONPATH=/src/src:/src/tests", "-e", "HOME=/tmp", "-e", "SIMLAB_HOST_ID=" + os.uname().nodename,
           "--entrypoint", "python", IMAGE, "/src/tools/check_groups.py", "--inside", "--group", a.group,
           "--timeout-s", str(timeout), *(["--live"] if a.live else [])]
    image = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], capture_output=True, text=True).stdout.strip()
    launch = {"schema": "simlab-check-launch:1", "run_id": run_id, "group": a.group, "image": IMAGE, "image_id": image,
              "memory_cap": MEMORY, "network": "none", "source_mount": f"{LAB}:/src:ro", "negative_control": a.negative_control,
              "timeout_s": timeout, "docker_command": cmd, "host": os.uname().nodename,
              "git_head": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    write(out / "launch.json", launch)
    marker = LAB / "tests" / f"_negative_control_{uuid.uuid4().hex[:6]}.txt"
    planted = threading.Event()

    def plant():
        time.sleep(8)
        marker.write_text("negative control: a source change during the run\n")
        planted.set()
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    th = None
    if a.negative_control == "source-change":
        th = threading.Thread(target=plant, daemon=True)
        th.start()
    peak = {"mem_mb": 0.0}
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name], capture_output=True, text=True)
            v = r.stdout.split("/")[0].strip()
            for unit, f in (("GiB", 1024), ("MiB", 1), ("KiB", 1 / 1024)):
                if v.endswith(unit):
                    try:
                        peak["mem_mb"] = max(peak["mem_mb"], float(v[:-len(unit)]) * f)
                    except ValueError:
                        pass
            stop.wait(3)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    stdout, _ = proc.communicate()
    stop.set()
    wall = time.monotonic() - t0
    if th is not None:
        th.join(30)
        marker.unlink(missing_ok=True)
    code = proc.returncode
    launch.update(ended_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), wall_s=round(wall, 2), container_exit=code,
                  container_stdout_tail=stdout[-3000:], docker_stats_peak_mem_mb=round(peak["mem_mb"], 1),
                  negative_control_planted=planted.is_set() if a.negative_control == "source-change" else None)
    write(out / "launch.json", launch)
    result = json.loads((out / "result.json").read_text()) if (out / "result.json").exists() else {}
    res_c = result.get("resources_container") or {}
    if a.compute_log:
        import csv  # noqa: PLC0415
        log = Path(a.compute_log)
        with log.open("a", newline="") as fh:
            csv.writer(fh).writerow([time.strftime("%Y-%m-%d %H:%M:%S %Z"), a.task, f"check group {a.group}"
                                     + (f" (negative control {a.negative_control})" if a.negative_control else ""), round(wall, 2),
                                     res_c.get("cpu_s"), res_c.get("memory_peak_mb"), "n/a (no GPU)",
                                     round(sum(p.stat().st_size for p in out.iterdir() if p.is_file()) / 2**20, 3),
                                     f"exit {code}; {result.get('counts')}; evidence {out.relative_to(REPO) if out.is_relative_to(REPO) else out}"])
    print(json.dumps({"group": a.group, "exit_code": code, "status": result.get("status"), "counts": result.get("counts"),
                      "wall_s": round(wall, 1), "memory_peak_mb": res_c.get("memory_peak_mb"), "evidence": str(out)}))
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--group", choices=[*GROUPS, "all"], required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--timeout-s", type=int, default=1800)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--negative-control", choices=["source-change", "timeout"])
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--compute-log", default=str(LAB / "missions" / "PAS-M1" / "compute-log.csv"))
    ap.add_argument("--task", default="PAS-M1-001")
    a = ap.parse_args(argv)
    return inside(a) if a.inside else host(a)


if __name__ == "__main__":
    raise SystemExit(main())
