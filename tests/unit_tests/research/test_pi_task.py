import hashlib
import json
import platform

from jiuwenswarm.research import trusted_pi
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research.pi_task import capture_pi_task
from jiuwenswarm.research.state import SQLiteRunStore


def test_capture_pi_task_materials_and_explicit_provenance(tmp_path, monkeypatch):
    def fake_profile(directory, public_ref):
        return {"protocol": "ai4r-pi:1", "public_dataset_ref": public_ref,
                "reference_path": str(tmp_path / "pi-reference.txt"),
                "reference_sha256": "a" * 64, "source_sha256": "b" * 64,
                "methods": ["method-a", "method-b"], "unseen_precisions": [23457, 67891, 99991],
                "measured_precisions": [10000, 100000], "repetitions": 5,
                "max_stdout_bytes": 1048576}
    monkeypatch.setattr(trusted_pi, "capture_pi_profile", fake_profile)
    store = SQLiteRunStore(tmp_path / "store")
    try:
        task = capture_pi_task(store, tmp_path / "private")
        assert set(task["builder_inputs"]) == {"blueprint", "baseline_resource", "validation_resource", "lock"}
        assert set(task["benchmark_inputs"]) == {"hypothesis_blueprint", "baseline_resource",
            "validation_resource", "environment_lock", "poc_manifest", "poc_artifact_bundle", "build_receipt"}
        assert all(task["benchmark_inputs"][key] is None for key in
                   ("poc_manifest", "poc_artifact_bundle", "build_receipt"))
        blueprint = store.read_record(task["builder_inputs"]["blueprint"])
        validate("hypothesis-blueprint", blueprint)
        assert blueprint["repeat_count"] == 5 and blueprint["seed"] == 42
        assert blueprint["metrics"][0]["metric_id"] == "elapsed_s"
        assert blueprint["outcome_rules"][0]["success"]["comparator"] == "lt"
        baseline = store.read_record(task["builder_inputs"]["baseline_resource"])
        baseline_file = next(row for row in baseline["files"] if row["path"] == "baseline.py")
        source = store.read_blob(baseline_file["artifact_ref"])
        assert hashlib.sha256(source).hexdigest() == baseline["revision"]
        compile(source, "baseline.py", "exec")
        assert b"approximate_pi(digits)" in source and b"/resources/validation/data.json" in source
        validation_resource = store.read_record(task["builder_inputs"]["validation_resource"])
        data = json.loads(store.read_blob(validation_resource["files"][0]["artifact_ref"]))
        assert data == {"schema": "ai4r-pi-cases:1", "digits": 100000}
        assert task["approved_environments"][0]["platform_fact"] == [
            platform.system(), platform.machine(), platform.python_version()]
        assert task["scoring_profile"]["public_dataset_ref"] == task["builder_inputs"]["validation_resource"]
        assert "no prior search or screening" in task["provenance"]
    finally:
        store.close()


def test_capture_pi_task_fills_only_accepted_builder_refs(tmp_path, monkeypatch):
    monkeypatch.setattr(trusted_pi, "capture_pi_profile", lambda _directory, public_ref: {
        "protocol": "ai4r-pi:1", "public_dataset_ref": public_ref})
    store = SQLiteRunStore(tmp_path / "store")
    try:
        accepted = {key: {"id": key, "sha256": "c" * 64} for key in
                    ("poc_manifest", "poc_artifact_bundle", "build_receipt")}
        task = capture_pi_task(store, tmp_path / "private", accepted_inputs=accepted)
        for key, value in accepted.items():
            assert task["benchmark_inputs"][key] == value
        assert task["benchmark_inputs"]["baseline_resource"] == task["builder_inputs"]["baseline_resource"]
    finally:
        store.close()
