"""Snapshot and custody checks; these fixtures perform no app execution."""
import json
from pathlib import Path

import pytest

from benchmarks.harbor_pilot import replay


def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "campaign.json").write_text(json.dumps({"campaign_id": "archived"}))
    for name in replay.CASE_RUNS.values():
        folder = source / "runs" / name
        (folder / "artifacts").mkdir(parents=True)
        (folder / "run_record.json").write_text(json.dumps({
            "run_id": name, "request_id": "original-" + name, "app_run_id": "app-" + name,
            "execution_state": "completed", "collection_state": "complete",
        }))
        (folder / "collection_manifest.json").write_text("{}")
        (folder / "artifacts/originals.zip").write_bytes(b"placeholder; grading validates real ZIP bytes")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"captured_at": "2026-10-23T00:00:00Z"}))
    config = tmp_path / "replay.json"
    replay.freeze(source, inventory, config)
    return source, inventory, config


def test_replay_preserves_original_ids_and_never_claims_live_execution(tmp_path):
    _, _, config = fixture(tmp_path)
    receipt = replay.stage(config, "paper", tmp_path / "copy")
    assert receipt["custody"] == "historical_replay"
    assert receipt["live_execution_performed"] is False
    assert receipt["request_id"] == "original-case3-paper-r1"


def test_changed_original_evidence_is_refused_before_copying(tmp_path):
    source, _, config = fixture(tmp_path)
    (source / "runs/case1-cpu-r1/artifacts/originals.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frozen historical evidence changed"):
        replay.stage(config, "cpu", tmp_path / "copy")
    assert not (tmp_path / "copy").exists()


def test_inventory_mutated_during_copy_cannot_receive_frozen_receipt(tmp_path, monkeypatch):
    _, _, config = fixture(tmp_path)
    original = replay.shutil.copyfile

    def changed_copy(source, destination, *args, **kwargs):
        result = original(source, destination, *args, **kwargs)
        if Path(destination).name == "archived-host-inventory.json":
            Path(destination).write_text('{"captured_at":"substituted"}')
        return result

    monkeypatch.setattr(replay.shutil, "copyfile", changed_copy)
    with pytest.raises(ValueError, match="copied archived inventory differs"):
        replay.stage(config, "cpu", tmp_path / "copy")
    assert not (tmp_path / "copy/pilot-receipt.json").exists()
