"""Read-only integrity check against the previously captured supplied hashes."""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
baseline = json.loads((HERE / "v09-source-integrity.json").read_text(encoding="utf-8"))
files = []
for row in baseline["files"]:
    observed = dict(row)
    observed["observed_source_sha256"] = hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
    observed["observed_copy_sha256"] = hashlib.sha256((ROOT / row["copy"]).read_bytes()).hexdigest()
    observed["result"] = "PASS" if row["expected_sha256"] == observed["observed_source_sha256"] == observed["observed_copy_sha256"] else "FAIL"
    files.append(observed)
protected = subprocess.run(["git", "diff", "--exit-code", "--", "AGENTS.md", ".specify/memory/constitution.md"], cwd=ROOT, capture_output=True)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
candidate = json.loads((HERE / "integrated-R04-candidate.json").read_text(encoding="utf-8"))
unchanged = all(hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"] for row in candidate["files"])
record = {
    "verification": "V09 final source and candidate integrity",
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "command": ".venv-intent/Scripts/python.exe docs/code/Missions/M0/M0-001/evidence/v09-source-check.py",
    "expected": "Ten supplied contract copies retain captured hashes; protected files and HEAD unchanged; all frozen execution inputs unchanged",
    "candidate": candidate["candidate"], "candidate_files_unchanged": unchanged,
    "files": files, "protected_diff_exit_code": protected.returncode,
    "head": head, "expected_head": baseline["expected_head"],
    "limitations": ["Static integrity only; behavioral evidence and browser/container prerequisites are recorded separately."],
}
record["result"] = "PASS" if unchanged and protected.returncode == 0 and head == baseline["expected_head"] and all(row["result"] == "PASS" for row in files) else "FAIL"
(HERE / "v09-source-integrity-r02.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: record[key] for key in ("candidate", "candidate_files_unchanged", "protected_diff_exit_code", "head", "result")}))
raise SystemExit(0 if record["result"] == "PASS" else 1)
