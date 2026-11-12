"""Summarise Nsight Systems CSV exports from one traced lab run.

Traced runs perturb timing, so these figures explain where time goes; they are
never speed evidence. Only the A/B gate on untraced runs makes speed claims.
"""
from __future__ import annotations

import csv
from pathlib import Path
import re

REPORTS = {'kernels': 'nsys_cuda_gpu_kern_sum.csv', 'cuda_api': 'nsys_cuda_api_sum.csv',
           'os_runtime': 'nsys_osrt_sum.csv', 'memcpy': 'nsys_cuda_gpu_mem_time_sum.csv'}
TOP = 10


def short_name(name):
    """Kernel template names are long; keep the function and its first template arguments."""
    name = re.sub(r'^void ', '', name)
    head = name.split('(const', 1)[0].split('(float', 1)[0]
    return head[:120]


def _rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def summarize(root):
    root = Path(root)
    if not (root / 'nsys.nsys-rep').is_file():
        return None
    out = dict(traced=True, note='Nsight Systems trace; timing is perturbed, use for breakdown only',
               report_bytes=(root / 'nsys.nsys-rep').stat().st_size, missing=[])
    for key, name in REPORTS.items():
        path = root / name
        if not path.is_file():
            out['missing'].append(name)
            continue
        rows = _rows(path)
        total_ns = sum(float(r.get('Total Time (ns)') or 0) for r in rows)
        count_key = 'Instances' if 'Instances' in (rows[0] if rows else {}) else ('Num Calls' if rows and 'Num Calls' in rows[0] else 'Count')
        top = []
        for r in rows[:TOP]:
            top.append(dict(name=short_name(r.get('Name') or r.get('Operation') or ''),
                            percent=float(r.get('Time (%)') or 0),
                            total_ms=round(float(r.get('Total Time (ns)') or 0) / 1e6, 3),
                            count=int(float(r.get(count_key) or 0))))
        out[key] = dict(total_ms=round(total_ns / 1e6, 3), entries=len(rows), top=top)
    return out
