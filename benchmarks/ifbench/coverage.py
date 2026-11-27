"""Which of the 47 telemetry IDs a set of runs actually measured (e.g. baseline + profile run)."""
import json, os
from .telemetry import CATALOG

RANK = {"ok": 0, "not_applicable": 1, "unavailable": 2}


def coverage(run_dirs, out=None):
    best = {}
    for d in run_dirs:
        path = os.path.join(d, "telemetry.jsonl")
        if not os.path.exists(path):
            continue
        for line in open(path):
            r = json.loads(line)
            cur = best.get(r["id"])
            if cur is None or RANK.get(r["status"], 3) < RANK.get(cur["status"], 3):
                best[r["id"]] = {"status": r["status"], "run": os.path.basename(os.path.normpath(d)),
                                 "note": r.get("note") or r.get("source") or ""}
    rows = []
    for tid, (layer, unit, tier) in CATALOG.items():
        b = best.get(tid, {"status": "unavailable", "run": "", "note": "never recorded"})
        rows.append({"id": tid, "tier": tier, **b})
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    lines = [f"# Telemetry coverage: {', '.join(f'{v} {k}' for k, v in sorted(counts.items()))} (of {len(CATALOG)})", "",
             "| ID | tier | status | from run | note |", "|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['tier']} | {r['status']} | {r['run']} | {str(r['note'])[:110]} |" for r in rows]
    md = "\n".join(lines) + "\n"
    if out:
        open(out, "w").write(md)
    return md
