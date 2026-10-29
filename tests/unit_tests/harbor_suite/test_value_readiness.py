import hashlib
import json
import zipfile

import pytest

from benchmarks.harbor_suite.value_readiness import inspect_matrix, inspect_release, readiness


def matrix_file(path, *, count=8, calls=8, wall=120):
    value = {
        "schema": "cc-value-case-design-bank:1",
        "base_case_count": count,
        "cases": [{
            "case_id": f"case-{i:02d}", "status": "design_only_not_a_runnable_or_executed_trial",
            "repeats": 1, "primary_arms": ["jiuwenswarm_native_codex", "ai4r_cc_codex"],
            "total_model_call_cap": calls, "wall_cap_s": wall,
        } for i in range(count)],
        "interaction_overlays": ["i1"], "planning_overlays": ["p1"],
        "verification_task_overlays": {"clean_controls": 1, "mechanical_defects": 1,
                                        "semantic_or_evidence_defects": 1},
        "batch_policy": {"model_calls_max": 64},
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def release_archive(tmp_path):
    archive = tmp_path / "release.zip"
    root = "release"
    case = {
        "schema": "ai4r-harbor-suite-case:1", "id": "cc01-transfer", "module": "cc",
        "title": "Case", "scenario_ids": ["s01"], "milestone": "m1",
        "classification": "core_m1_acceptance", "requirements": ["B01"], "domains": ["c01"],
        "entrypoint": "single_cc", "objective": "Test objective",
        "primary_metric": {"name": "score", "definition": "pass / scheduled"},
        "budgets": {"wall_time_s": 60, "max_model_calls": 1, "physical_memory_mb": 1024,
                    "committed_memory_mb": 2048, "storage_mb": 512, "concurrency": 1,
                    "gpu_required": False},
        "product_prerequisites": ["binding"], "evidence_requirements": ["gate-decision"],
        "variants": [{"id": f"v{i}", "split": "development", "task": "Do the small task.",
                      "inputs": [], "expected_behavior": "complete", "seed": i} for i in range(3)],
        "oracle_version": "1",
    }
    payload = {"cases/cc01-transfer/case.json": json.dumps(case).encode()}
    manifest = {"schema": "ai4r-benchmark-case-release:1", "classification": "development",
                "case_count": 1, "variant_count": 3,
                "files": [{"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                          for name, raw in payload.items()]}
    payload["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in payload.items():
            bundle.writestr(f"{root}/{name}", raw)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  release.zip\n", encoding="ascii")
    return archive


def test_release_is_hash_checked_without_extraction(tmp_path):
    archive = release_archive(tmp_path)
    before = archive.read_bytes()
    result = inspect_release(archive)
    assert result["status"] == "verified"
    assert result["case_count"] == 1 and result["variant_count"] == 3
    assert result["extracted"] is False
    assert archive.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["release.zip", "release.zip.sha256"]


def test_release_checksum_mismatch_fails_before_reading_contents(tmp_path):
    archive = release_archive(tmp_path)
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum"):
        inspect_release(archive)


def test_worst_case_paired_batch_respects_total_and_declared_caps(tmp_path):
    matrix = matrix_file(tmp_path / "matrix.json")
    result = inspect_matrix(matrix, batch_size=8)
    batch = result["batch_preview"]
    assert result["base_designs"] == 8
    assert result["maximum_design_slots"] == 13
    assert batch["worst_case_paired_calls"] == 128
    assert batch["fits_total_budget_after_reserve"] is True
    assert batch["fits_declared_batch_limit"] is False
    assert batch["worst_case_serial_seconds"] == 1920
    assert batch["fits_controller_batch_limit"] is False


def test_readiness_labels_missing_live_evidence_without_claiming_a_model_call(tmp_path):
    archive = release_archive(tmp_path)
    matrix = matrix_file(tmp_path / "matrix.json")
    result = readiness(archive=archive, matrix=matrix, batch_size=1)
    assert result["read_only"] is True
    assert result["model_calls"] == 0
    assert result["evidence"]["status"] == "not_supplied"
    assert result["runtime"]["credential_or_model_probe_performed"] is False

