"""Run one operator command under the host monitor and write its resource record.

    python tools/measure.py --record out.json --log ../missions/.../compute-log.csv \
        --task PAS-M1-001/T005 --what "docker build simlab-runner" -- docker build ...

Exit code is the command's. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hostmon  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=Path, required=True)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--task", default="")
    ap.add_argument("--what", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--interval-s", type=float, default=3.0)
    ap.add_argument("--stdout", type=Path)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    mon = hostmon.HostMonitor(interval_s=a.interval_s).start()
    start_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.monotonic()
    out = open(a.stdout, "w") if a.stdout else None
    proc = subprocess.run(cmd, stdout=out or None, stderr=subprocess.STDOUT if out else None)
    wall = time.monotonic() - t0
    if out:
        out.close()
    summary = mon.stop()
    rc = resource.getrusage(resource.RUSAGE_CHILDREN)
    rec = {"record": "simlab-operator-measure", "cmd": cmd, "start_utc": start_utc, "exit_code": proc.returncode,
           "wall_s": round(wall, 2), "cpu_s_host_children": round(rc.ru_utime + rc.ru_stime, 2),
           "host": summary, "samples": mon.samples}
    a.record.parent.mkdir(parents=True, exist_ok=True)
    a.record.write_text(json.dumps(rec, indent=1))
    if a.log:
        new = not a.log.exists() or a.log.stat().st_size == 0
        with a.log.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["date", "task", "what ran", "wall s", "CPU s", "peak RAM MB", "peak VRAM MB", "disk MB", "notes"])
            peak = summary.get("vm_used_peak_mb")
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S %Z"), a.task, a.what, rec["wall_s"],
                        f"{rec['cpu_s_host_children']} (client side only)", f"{peak} (WSL VM used, peak)",
                        summary.get("gpu_mem_peak_mb") if summary.get("gpu_mem_peak_mb") else "n/a (no GPU use)",
                        "", f"exit {proc.returncode}. {a.notes}".strip()])
    print(json.dumps({k: rec[k] for k in ("exit_code", "wall_s")} | {"host": summary}))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
