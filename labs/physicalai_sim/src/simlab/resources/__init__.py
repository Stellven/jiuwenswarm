"""Resource records (PAS-M1-001 B10, research.md R11) and the compute log.

Every run, check-group run and benchmark run records wall time, CPU time,
peak RAM, GPU and peak VRAM when used, and disk written. Inside a container
the cgroup v2 files are authoritative; outside one, getrusage and /proc are.
"""
from __future__ import annotations

import csv
import json
import os
import resource
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

CGROUP = Path("/sys/fs/cgroup")
COMPUTE_LOG_HEADER = ["date", "task", "what ran", "wall s", "CPU s", "peak RAM MB", "peak VRAM MB", "disk MB", "notes"]


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def cgroup_cpu_usec() -> int | None:
    try:
        for line in (CGROUP / "cpu.stat").read_text().splitlines():
            k, v = line.split()
            if k == "usage_usec":
                return int(v)
    except OSError:
        return None
    return None


def cgroup_memory_peak() -> int | None:
    return _read_int(CGROUP / "memory.peak")


def system_memory_mb() -> dict:
    info = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) // 1024
    except OSError:
        return {}
    return {"total_mb": info.get("MemTotal"), "available_mb": info.get("MemAvailable"),
            "used_mb": (info.get("MemTotal", 0) - info.get("MemAvailable", 0)),
            "swap_used_mb": info.get("SwapTotal", 0) - info.get("SwapFree", 0)}


def gpu_memory_used_mb() -> float | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True).stdout
        return float(out.split()[0])
    except (subprocess.SubprocessError, ValueError, IndexError, OSError):
        return None


def dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def proc_write_bytes(pid: int | str = "self") -> int | None:
    try:
        for line in Path(f"/proc/{pid}/io").read_text().splitlines():
            if line.startswith("write_bytes:"):
                return int(line.split()[1])
    except OSError:
        return None
    return None


@dataclass
class ResourceMeter:
    """Measures one run. Use as a context manager; read .record afterwards.

    peak RAM: cgroup memory.peak when inside a dedicated cgroup (container),
    else max RSS of self and children. GPU: sampled only when gpu=True.
    """
    disk_dir: Path | None = None
    gpu: bool = False
    sample_s: float = 0.5
    record: dict = field(default_factory=dict)

    def __enter__(self):
        self._t0 = time.monotonic()
        self._ru0 = resource.getrusage(resource.RUSAGE_SELF)
        self._rc0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        self._cg_cpu0 = cgroup_cpu_usec()
        self._disk0 = dir_size_bytes(self.disk_dir) if self.disk_dir else 0
        self._wb0 = proc_write_bytes() or 0
        self._vram_peak = None
        self._stop = threading.Event()
        if self.gpu:
            self._thread = threading.Thread(target=self._sample_gpu, daemon=True)
            self._thread.start()
        return self

    def _sample_gpu(self):
        while not self._stop.is_set():
            v = gpu_memory_used_mb()
            if v is not None:
                self._vram_peak = v if self._vram_peak is None else max(self._vram_peak, v)
            self._stop.wait(self.sample_s)

    def __exit__(self, *exc):
        self._stop.set()
        wall = time.monotonic() - self._t0
        ru = resource.getrusage(resource.RUSAGE_SELF)
        rc = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (ru.ru_utime - self._ru0.ru_utime + ru.ru_stime - self._ru0.ru_stime
               + rc.ru_utime - self._rc0.ru_utime + rc.ru_stime - self._rc0.ru_stime)
        cg1 = cgroup_cpu_usec()
        cpu_source = "getrusage(self+children)"
        if self._cg_cpu0 is not None and cg1 is not None and os.environ.get("SIMLAB_IN_CONTAINER") == "1":
            cpu = (cg1 - self._cg_cpu0) / 1e6
            cpu_source = "cgroup cpu.stat"
        peak_cg = cgroup_memory_peak() if os.environ.get("SIMLAB_IN_CONTAINER") == "1" else None
        peak_rss = max(ru.ru_maxrss, rc.ru_maxrss) / 1024.0
        disk = (dir_size_bytes(self.disk_dir) - self._disk0) if self.disk_dir else 0
        wb = (proc_write_bytes() or 0) - self._wb0
        self.record = {
            "wall_s": round(wall, 3),
            "cpu_s": round(cpu, 3),
            "cpu_source": cpu_source,
            "peak_ram_mb": round(peak_cg / 2**20, 1) if peak_cg else round(peak_rss, 1),
            "peak_ram_source": "cgroup memory.peak" if peak_cg else "max rss (self, children)",
            "gpu": "nvidia" if self.gpu else "none",
            "peak_vram_mb": self._vram_peak if self.gpu else None,
            "disk_written_mb": round(max(disk, wb, 0) / 2**20, 3),
        }
        return False


def compute_log_append(path: Path, *, task: str, what: str, wall_s, cpu_s, peak_ram_mb, peak_vram_mb,
                       disk_mb, notes: str = "", date: str | None = None) -> list:
    path = Path(path)
    new = not path.exists() or path.stat().st_size == 0
    row = [date or time.strftime("%Y-%m-%d %H:%M:%S %Z"), task, what,
           "" if wall_s is None else wall_s, "" if cpu_s is None else cpu_s,
           "" if peak_ram_mb is None else peak_ram_mb,
           "n/a (no GPU)" if peak_vram_mb is None else peak_vram_mb,
           "" if disk_mb is None else disk_mb, notes]
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COMPUTE_LOG_HEADER)
        w.writerow(row)
    return row


def compute_log_main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="simlab compute-log")
    sub = ap.add_subparsers(dest="op", required=True)
    a = sub.add_parser("append")
    a.add_argument("--log", type=Path, required=True)
    a.add_argument("--task", required=True)
    a.add_argument("--what", required=True)
    a.add_argument("--from-record", type=Path, help="JSON file holding a resources record")
    for k in ("wall-s", "cpu-s", "peak-ram-mb", "peak-vram-mb", "disk-mb"):
        a.add_argument("--" + k, type=float)
    a.add_argument("--notes", default="")
    args = ap.parse_args(argv)
    rec = {}
    if args.from_record:
        rec = json.loads(args.from_record.read_text())
        rec = rec.get("resources", rec)
    row = compute_log_append(
        args.log, task=args.task, what=args.what,
        wall_s=args.wall_s if args.wall_s is not None else rec.get("wall_s"),
        cpu_s=args.cpu_s if args.cpu_s is not None else rec.get("cpu_s"),
        peak_ram_mb=args.peak_ram_mb if args.peak_ram_mb is not None else rec.get("peak_ram_mb"),
        peak_vram_mb=args.peak_vram_mb if args.peak_vram_mb is not None else rec.get("peak_vram_mb"),
        disk_mb=args.disk_mb if args.disk_mb is not None else rec.get("disk_written_mb"),
        notes=args.notes)
    print(json.dumps(row))
    return 0
