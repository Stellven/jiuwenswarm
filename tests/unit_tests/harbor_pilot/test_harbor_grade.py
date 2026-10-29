"""Independent boundary tests, including deliberately self-consistent tampering."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

import pytest

from benchmarks.harbor_pilot.grade import Artifacts, assess, canonical, fingerprint, scientific


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def retained_record(path, folder, source):
    return {"path": path.relative_to(folder).as_posix(), "source": source, **fingerprint(path)}


@pytest.fixture
def evidence(tmp_path):
    root = tmp_path / "evidence"
    run_folder = root / "runs/case3-paper-r1"
    (run_folder / "artifacts").mkdir(parents=True)
    app_run = "run:original-123"
    content = {
        "paper_summary.md": b"Section IV: 120 primary revision pairs, 116 common-success articles. Table I: 68.4% Chinese and 57.4% English. 4 of 62 Chinese articles failed. Limitations apply.",
        "gates/gate_001.json": b'{"action":"advance","run_id":"run:original-123"}',
    }
    source_rows, files = [], []
    for name, raw in content.items():
        ref = {"id": "blob:" + hashlib.sha256(raw).hexdigest(), "sha256": hashlib.sha256(raw).hexdigest()}
        media = "text/markdown" if name.endswith(".md") else "application/json"
        source_rows.append({"path": name, "artifact_id": hashlib.sha256(canonical([name, ref])).hexdigest(),
                            "sha256": ref["sha256"], "size": len(raw), "media_type": media})
        files.append({"path": name, "artifact_ref": ref, "media_type": media, "audience": "researcher"})
    source = {"schema_version": "1.0.0", "run_id": app_run, "audience": "researcher", "execution_terminal": True,
              "artifacts": source_rows, "retention": {}, "redactions": []}
    source["manifest_sha256"] = hashlib.sha256(canonical(source)).hexdigest()
    retrieval = {"schema_version": "1.0.0", "id": "retrieval:one", "run_id": app_run, "audience": "researcher",
                 "artifact_refs": [r["artifact_ref"] for r in files], "files": files, "redactions": []}
    archive_path = run_folder / "artifacts/originals.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("client_retrieval.json", canonical(retrieval))
        for name, raw in content.items():
            archive.writestr(name, raw)
    inventory = {"schema_version": "1.0.0", "run_id": app_run, "audience": "researcher",
                 "source_manifest_sha256": source["manifest_sha256"], "client_retrieval": retrieval,
                 "verified_members": [{"path": r["path"], "sha256": r["sha256"], "size": r["size"], "media_type": r["media_type"]} for r in source_rows],
                 "total_uncompressed_bytes": sum(map(len, content.values())), "archive": fingerprint(archive_path)}
    inventory_path = run_folder / "artifacts/originals.inventory.json"
    write_json(inventory_path, inventory)
    run = {"schema_version": "sequential-run:1", "run_id": "case3-paper-r1", "campaign_id": "campaign-one",
           "case_id": "case3-paper", "repeat_index": 1, "app_run_id": app_run, "request_id": "request-one",
           "execution_state": "completed", "collection_state": "complete",
           "status": {"run_id": app_run, "client_request_id": "request-one", "status": "completed"},
           "collection_confirmation": {"status": "confirmed", "run_id": app_run, "audience": "researcher", "manifest_sha256": source["manifest_sha256"]},
           "artifacts": [retained_record(archive_path, run_folder, "app_archive"),
                         retained_record(inventory_path, run_folder, "app_archive_inventory")]}
    write_json(run_folder / "run_record.json", run)
    write_json(run_folder / "collection_manifest.json", source)
    write_json(root / "campaign.json", {"schema_version": "sequential-campaign:1", "campaign_id": "campaign-one", "cases": [{"id": "case3-paper", "repeats": 1}]})
    write_json(root / "host-inventory.json", {"captured_at": "2026-10-25T17:00:00Z", "physical_host": "test-host"})
    write_json(root / "pilot-receipt.json", {"schema": "ai4r-harbor-receipt:1", "case_id": "paper", "campaign_id": "campaign-one",
        "app_run_id": app_run, "request_id": "request-one", "execution_state": "completed", "collection_state": "complete",
        "terminal_confirmed": True, "evidence_complete": True, "custody": "live", "inventory_ref": "host-inventory.json"})
    return root


@pytest.fixture
def criteria():
    return {"schema": "ai4r-harbor-criteria:1", "case_id": "paper", "paper": {"checks": [
        {"id": "primary_pairs", "patterns": [r"120 primary"]},
        {"id": "citation", "patterns": [r"Table I"]}]}}


def edit_json(path, edit):
    value = json.loads(path.read_bytes())
    edit(value)
    write_json(path, value)


def test_valid_export_is_compatible_but_not_a_human_scientific_verdict(evidence, criteria):
    result = assess(evidence, criteria)
    assert result["success"] and result["live_integration"]
    assert result["scientific_assessment"]["limited_checks_passed"]
    assert result["scientific_assessment"]["task_success"] is None
    assert result["scientific_assessment"]["status"] == "human_review_required"


def test_historical_export_never_proves_new_live_integration(evidence, criteria):
    edit_json(evidence / "pilot-receipt.json", lambda r: r.update(custody="historical_replay"))
    assert not assess(evidence, criteria)["success"]
    criteria["allowed_custody"] = ["historical_replay"]
    result = assess(evidence, criteria)
    assert result["evidence_integrity"] and not result["live_integration"]


def test_missing_archive_cannot_pass_because_receipt_says_success(evidence, criteria):
    (evidence / "runs/case3-paper-r1/artifacts/originals.zip").unlink()
    result = assess(evidence, criteria)
    assert not result["success"] and not result["evidence_integrity"]
    assert "missing" in result["errors"][0]


def test_rewritten_outer_archive_hash_does_not_hide_changed_original(evidence, criteria):
    folder = evidence / "runs/case3-paper-r1"
    archive_path = folder / "artifacts/originals.zip"
    with zipfile.ZipFile(archive_path) as archive:
        rows = {name: archive.read(name) for name in archive.namelist()}
    rows["paper_summary.md"] = b"A fabricated answer with no source evidence."
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in rows.items():
            archive.writestr(name, raw)
    edit_json(folder / "run_record.json", lambda r: r["artifacts"][0].update(fingerprint(archive_path)))
    result = assess(evidence, criteria)
    assert not result["success"] and "member hash mismatch" in result["errors"][0]


def test_false_terminal_receipt_cannot_override_pending_app_status(evidence, criteria):
    edit_json(evidence / "runs/case3-paper-r1/run_record.json", lambda r: r["status"].update(status="running"))
    result = assess(evidence, criteria)
    assert not result["success"] and "terminal" in result["errors"][0]


def test_dropped_scheduled_attempt_cannot_be_omitted_from_denominator(evidence, criteria):
    edit_json(evidence / "campaign.json", lambda r: r["cases"][0].update(repeats=2))
    result = assess(evidence, criteria)
    assert not result["success"] and "attempt inventory" in result["errors"][0]
    assert result["scheduled_attempt_count"] == 2


def test_wrong_collection_confirmation_cannot_claim_collected(evidence, criteria):
    edit_json(evidence / "runs/case3-paper-r1/run_record.json", lambda r: r["collection_confirmation"].update(run_id="run:other"))
    assert not assess(evidence, criteria)["success"]


def test_safe_halt_has_collection_fidelity_but_no_task_success(evidence, criteria):
    folder = evidence / "runs/case3-paper-r1"
    edit_json(folder / "run_record.json", lambda r: (r.update(execution_state="halted"), r["status"].update(status="halted")))
    edit_json(evidence / "pilot-receipt.json", lambda r: r.update(execution_state="halted"))
    result = assess(evidence, criteria)
    assert result["evidence_integrity"] and not result["execution_completed"]
    assert result["scientific_assessment"]["task_success"] is False


def test_path_escape_in_retained_manifest_is_rejected(evidence, criteria):
    edit_json(evidence / "runs/case3-paper-r1/run_record.json", lambda r: r["artifacts"][0].update(path="../../outside.zip"))
    assert not assess(evidence, criteria)["success"]


def test_cpu_absent_predictions_are_not_scored(evidence, criteria):
    # A completed run is still insufficient when its required scientific output
    # is absent; changing only metadata cannot create predictions.
    cpu = {"schema": "ai4r-harbor-criteria:1", "case_id": "cpu", "runner_case_id": "case3-paper"}
    edit_json(evidence / "pilot-receipt.json", lambda r: r.update(case_id="cpu"))
    result = assess(evidence, cpu)
    assert result["evidence_integrity"]
    assert result["scientific_assessment"]["status"] == "missing_required_output"
    assert result["scientific_assessment"]["task_success"] is False


def test_actual_historical_archive_when_explicitly_supplied():
    location = os.environ.get("AI4R_HARBOR_REPLAY_ROOT")
    if not location:
        pytest.skip("Set AI4R_HARBOR_REPLAY_ROOT for retained external demo archives")
    root = Path(location)
    for ident in ("case1-cpu-r1", "case3-paper-r1"):
        folder = root / "runs" / ident
        row = json.loads((folder / "run_record.json").read_bytes())
        manifest = json.loads((folder / "collection_manifest.json").read_bytes())
        store = Artifacts(folder, row, manifest)
        assert len(store.paths) == len(manifest["artifacts"])
        if ident == "case3-paper-r1":
            assert "68.4" in store.text("paper_summary.md")


def test_cpu_arithmetic_requires_exact_unseen_ids_and_keeps_review_open(tmp_path):
    (tmp_path / "labels.csv").write_text("id,label\na,1\nb,0\nc,1\n", encoding="utf-8")
    rubric = {"case_id": "cpu", "cpu": {"labels_path": "labels.csv"}}

    class OriginalArtifacts:
        def text(self, name):
            return "id,label\na,1\nb,1\nc,1\n"

    result = scientific(OriginalArtifacts(), rubric, tmp_path, True)
    assert result["accuracy"] == 2 / 3 and result["sample_count"] == 3
    assert result["task_success"] is None

    class DuplicateArtifacts:
        def text(self, name):
            return "id,label\na,1\na,0\nc,1\n"

    with pytest.raises(ValueError, match="duplicate"):
        scientific(DuplicateArtifacts(), rubric, tmp_path, True)
