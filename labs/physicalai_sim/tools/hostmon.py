"""Host-side resource sampler for operator tools (feasibility, builds, check groups).

Samples WSL VM memory (MemTotal - MemAvailable; Docker Desktop shares this VM),
per-container memory and CPU from the Docker API via `docker stats`, GPU memory
from nvidia-smi, and disk. Standard library only; imports no AI4R or SIMLAB code
so it can measure either.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path


def meminfo_mb() -> dict:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0]) // 1024
    return {"total": info["MemTotal"], "available": info["MemAvailable"],
            "used": info["MemTotal"] - info["MemAvailable"],
            "swap_used": info.get("SwapTotal", 0) - info.get("SwapFree", 0)}


def _mb(text: str) -> float | None:
    text = text.strip()
    units = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1024, "MB": 1, "GB": 1024}
    for u in sorted(units, key=len, reverse=True):
        if text.endswith(u):
            try:
                return float(text[: -len(u)]) * units[u]
            except ValueError:
                return None
    return None


def docker_stats() -> dict:
    if not shutil.which("docker"):
        return {}
    try:
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                             capture_output=True, text=True, timeout=30).stdout
    except subprocess.SubprocessError:
        return {}
    stats = {}
    for line in out.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        used = _mb(d.get("MemUsage", "").split("/")[0])
        stats[d.get("Name")] = {"mem_mb": None if used is None else round(used, 1),
                                "cpu_pct": d.get("CPUPerc"), "pids": d.get("PIDs")}
    return stats


def gpu_mb() -> float | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return float(out.split()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None


class HostMonitor:
    """Background sampler; .samples holds every sample, .summary() the peaks."""

    def __init__(self, interval_s: float = 2.0, containers: bool = True, gpu: bool = True):
        self.interval_s, self.containers, self.gpu = interval_s, containers, gpu
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.t0 = time.monotonic()

    def sample(self) -> dict:
        s = {"t_s": round(time.monotonic() - self.t0, 2), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "vm": meminfo_mb()}
        if self.containers:
            s["containers"] = docker_stats()
        if self.gpu:
            s["gpu_mem_mb"] = gpu_mb()
        return s

    def _run(self):
        while not self._stop.is_set():
            try:
                self.samples.append(self.sample())
            except Exception as exc:  # recorded, never hidden
                self.samples.append({"t_s": round(time.monotonic() - self.t0, 2), "error": repr(exc)})
            self._stop.wait(self.interval_s)

    def start(self):
        self._thread.start()
        return self

    def stop(self) -> dict:
        self._stop.set()
        self._thread.join(timeout=60)
        return self.summary()

    def summary(self) -> dict:
        vm = [s["vm"] for s in self.samples if "vm" in s]
        cont: dict[str, float] = {}
        for s in self.samples:
            for name, c in (s.get("containers") or {}).items():
                if c.get("mem_mb") is not None:
                    cont[name] = max(cont.get(name, 0.0), c["mem_mb"])
        gpus = [s["gpu_mem_mb"] for s in self.samples if s.get("gpu_mem_mb") is not None]
        return {
            "n_samples": len(self.samples),
            "vm_total_mb": vm[0]["total"] if vm else None,
            "vm_used_peak_mb": max((v["used"] for v in vm), default=None),
            "vm_available_min_mb": min((v["available"] for v in vm), default=None),
            "swap_used_peak_mb": max((v["swap_used"] for v in vm), default=None),
            "container_mem_peak_mb": cont,
            "gpu_mem_peak_mb": max(gpus) if gpus else None,
        }
