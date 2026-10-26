import json

import pytest

from benchmarks.harbor_suite.value_data import Dataset
from benchmarks.harbor_suite.value_view import load_catalogue, render


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_catalogue_counts_banks_separately_and_uses_only_public_task(tmp_path):
    bank = tmp_path / "base"
    public_task = {"id": "utility.calculate/clean", "objective": "Return exact decimal result."}
    write_json(bank / "manifest.json", {"schema": "ai4r-value-case-bank:1", "cases": [
        {"id": public_task["id"], "task_sha256": __import__("hashlib").sha256(
            json.dumps(public_task, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
         "readiness": "offline_worker_runnable", "measurement_status": "not_run",
         "source": {"kind": "local"}}
    ]})
    write_json(bank / "public" / "utility.calculate--clean.json", public_task)
    # A private oracle exists but must not be used or copied into the catalogue.
    (bank / "private").mkdir()
    (bank / "private" / "oracle.json").write_text('{"answer":"SECRET"}', encoding="utf-8")
    planning = tmp_path / "planning" / "manifest.json"
    write_json(planning, {"component_only": "not full unit", "cases": [
        {"case_id": "planning-01", "public_sha256": "a" * 64, "measurement_status": "not_run"}
    ]})
    rows, designs = load_catalogue(base_bank=bank, planning_manifest=planning,
        design_matrix=None)
    assert [(r["population"], r["case_id"]) for r in rows] == [
        ("base_frozen_80", "utility.calculate/clean"), ("planning_component_8", "planning-01")]
    assert rows[0]["description"] == public_task["objective"]
    assert "SECRET" not in json.dumps(rows)
    assert designs == []


def test_ledger_retains_all_records_and_labels_selected_paired_rerun(tmp_path):
    data = Dataset(tmp_path / "dataset")
    source_rows = [{"case_id": "table-1", "fault": "type", "input_sha256": "i1",
                    "artifact_sha256": "o1", "checker_accepted": True}]
    before = data.append("capability_probe", {"rows": source_rows, "scope": "direct"})
    after = data.append("capability_probe", {"rows": source_rows, "scope": "direct",
        "paired_with": before["id"]})
    failed = data.append("product_qualification", {"result": {"status": "failed"}, "scope": "E1"})
    output = tmp_path / "viewer"
    summary = render(catalogue=[], records=data.records(), output=output,
        selection={"record_ids": [after["id"]]})
    ledger = [json.loads(line) for line in (output / "run-ledger.jsonl").read_text().splitlines()]
    projections = {x["projection"]["record_id"]: x["projection"] for x in ledger}
    assert set(projections) == {before["id"], after["id"], failed["id"]}
    assert projections[after["id"]]["selected_in_current_report"] is True
    assert projections[before["id"]]["selected_in_current_report"] is False
    assert projections[after["id"]]["pair_relation"] == "explicitly paired rerun"
    assert projections[after["id"]]["known_repeats_of"] == before["id"]
    assert summary["dataset_record_count"] == 3
    assert summary["selected_dataset_record_count"] == 1
    assert summary["capability_probe_rows_retained"] == 2
    assert summary["capability_probe_unique_input_artifact_pairs_across_records"] == 1
    assert summary["capability_probe_repeat_observations_over_unique_coordinates"] == 1
    assert any(x["source_record"]["id"] == failed["id"] for x in ledger)
    with pytest.raises(ValueError, match="fresh directory"):
        render(catalogue=[], records=data.records(), output=output)


def test_design_matrix_stays_separate_from_frozen_case_population(tmp_path):
    matrix = tmp_path / "design.json"
    write_json(matrix, {"cases": [{"case_id": "intent-01", "family": "intent",
        "status": "design_only_not_a_runnable_or_executed_trial"}]})
    _, designs = load_catalogue(design_matrix=matrix)
    summary = render(catalogue=[], records=[], output=tmp_path / "out", designs=designs)
    assert summary["catalogue_rows_total_not_deduplicated_across_populations"] == 0
    assert summary["design_matrix_sketches_not_in_catalogue_count"] == 1
    text = (tmp_path / "out" / "README.md").read_text()
    assert "not an additional frozen/executed case" in (tmp_path / "out" / "design-matrix.csv").read_text()
    assert "kept separate from frozen runnable cases" in text
