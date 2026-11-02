"""Deterministic fake executor for block-level runner tests only (V-BLK-STATUS).

Returns the status named by the trial parameter `fake` and logs each execution,
so the runner's bookkeeping is checked without physics. Never used at BOUNDARY level.
"""
import json
import sys
from pathlib import Path

job = json.loads(sys.stdin.read())
with Path(sys.argv[1]).open("a") as fh:
    fh.write(job["out_dir"] + "\n")
status = str(job.get("params", {}).get("fake", "COMPLETED"))
print(json.dumps({"status": status, "invalid_reason": "numerical_failure" if status == "INVALID" else None,
                  "reason": "fake executor", "stop": "completed", "traces": [], "events": [], "checkpoints": [], "steps": 0,
                  "worker_resources": {"cpu_s": 0, "peak_rss_mb": 1, "write_bytes": 0}}))
