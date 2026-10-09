"""Reproduce read-only verification of the frozen real-model actionable evidence."""
import hashlib
import json
import pathlib
import sqlite3
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
root = HERE / "live-R06/actionable"
status = json.loads((root / "status.json").read_text(encoding="utf-8"))
consumer = json.loads((root / "consumer-result.json").read_text(encoding="utf-8"))
with sqlite3.connect("file:" + (root / "state/runs.sqlite3").as_posix() + "?mode=ro", uri=True) as con:
    rows = {scope: {"subject": json.loads(subject), "gate": json.loads(gate), "receipt": json.loads(receipt)}
            for scope, subject, gate, receipt in con.execute(
                "SELECT scope,subject,gate_ref,record_ref FROM acceptance WHERE run_id=?", (status["run_id"],))}
    inventory = dict(con.execute("SELECT name,hash FROM artifacts WHERE run_id=?", (status["run_id"],)))
assert set(rows) == {"intention", "requirements", "node"}
assert rows["node"]["subject"] == rows["requirements"]["subject"]
assert status["status"] == "completed" and status["stage"] == "released"
assert consumer["node_acceptance_ref"] == rows["node"]["receipt"]
assert consumer["output_refs"] == [rows["node"]["subject"]]
with zipfile.ZipFile(root / "evidence.zip") as archive:
    manifest = json.loads(archive.read("manifest.json"))
    for item in manifest["files"]:
        assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["artifact_ref"]["sha256"]
    subject = rows["node"]["subject"]
    found = next(item for item in manifest["files"] if item["artifact_ref"] == subject)
    brief = json.loads(archive.read(found["path"]))
    assert brief["schema_version"] == "2.0.0"
    assert consumer["research_brief"] == brief
observations = [name for name in inventory if name.endswith("_Invocation_Observation.json")]
assert len(observations) == 4
record = {
    "verification": "V06 independent durable release/export observation",
    "command": ".venv-intent/Scripts/python.exe docs/code/Missions/M0/M0-001/evidence/v06-release-check.py",
    "candidate": json.loads((root.parent / "candidate.json").read_text())["candidate"],
    "run_id": status["run_id"],
    "expected": "Three durable scope acceptances; four invocation observations; exact Brief2 consumer/export equality; all named export hashes verify",
    "observed": {"acceptance_scopes": sorted(rows), "invocation_observations": len(observations),
                 "brief_ref": subject, "status": status["status"], "stage": status["stage"],
                 "named_export_files_verified": len(manifest["files"]), "consumer_matches_exact_captured_brief": True},
    "result": "PASS",
    "limitations": ["One actionable sample; no reliability threshold or browser/container acceptance."]
}
(HERE / "v06-release-independent.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
