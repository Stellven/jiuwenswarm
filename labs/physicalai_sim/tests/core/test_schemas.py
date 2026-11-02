"""V-BLK-SCHEMA (AC-002): IF-001@r1 records, enums and typed errors; exported schema equals the models."""
import copy

import pytest

from simlab import schemas
from simlab.contracts import parse_record
from simlab.contracts.enums import AttemptStatus, InvalidReason, ObjectiveKind, RunStatus
from fixtures import header, PROCEDURE, PERIOD, QPOS


def experiment():
    e = {"record": "simlab-experiment", "schema_version": "simlab-if-001@r1", **header(), "procedure": PROCEDURE,
         "measurements": [PERIOD], "trace_signals": [QPOS]}
    return copy.deepcopy(e)


def result():
    return {"record": "simlab-result", "schema_version": "simlab-if-001@r1", "run_id": "run-1", "experiment_id": "exp-1",
            "manifest_sha256": "0" * 64, "run_kind": "original", "status": "COMPLETED", "identity": {}, "hardware": {},
            "trials": [{"trial_id": "t1", "arm_id": "a", "condition": "nominal", "replicate": 0, "episode": 0,
                        "attempts": [{"attempt_id": "x1", "status": "INVALID", "invalid_reason": "numerical_failure"}]}],
            "anchoring": "unanchored", "provenance": {}}


def test_valid_records_pass():
    for name, data in (("simlab-experiment", experiment()), ("simlab-result", result()),
                       ("simlab-error", {"code": "E_UNKNOWN_RUN", "message": "x", "path": "", "severity": "error"}),
                       ("simlab-manifest", {"record": "simlab-manifest", "schema_version": "simlab-if-001@r1", "manifest_id": "man-1",
                                            "manifest_sha256": "a" * 64, "experiment_id": "exp-1",
                                            "artifacts": [{"path": "p.xml", "kind": "model_file", "sha256": "b" * 64, "bytes": 3}]})):
        model, findings = parse_record(name, data)
        assert findings == [] and model is not None, (name, findings)


@pytest.mark.parametrize("mutate,code,path", [
    (lambda e: e.pop("objective"), "E_SCHEMA_REQUIRED", "/objective"),
    (lambda e: e.update(colour="blue"), "E_SCHEMA_UNKNOWN_FIELD", "/colour"),
    (lambda e: e.update(objective_kind="verdict"), "E_SCHEMA_ENUM", "/objective_kind"),
    (lambda e: e["arms"][0].update(role="winner"), "E_SCHEMA_ENUM", "/arms/0/role"),
    (lambda e: e["resolved_configuration"].pop("timestep"), "E_SCHEMA_REQUIRED", "/resolved_configuration/timestep"),
    (lambda e: e["design"].update(replicates="two"), "E_SCHEMA_TYPE", "/design/replicates"),
    (lambda e: e.update(schema_version="simlab-if-001@r0"), "E_SCHEMA_ENUM", "/schema_version"),
])
def test_invalid_experiment_rejected_with_code(mutate, code, path):
    e = experiment()
    mutate(e)
    model, findings = parse_record("simlab-experiment", e)
    assert model is None
    assert (code, path) in {(f["code"], f["path"]) for f in findings}, findings


def test_result_status_enums_enforced():
    for field, bad in (("status", "PASSED"),):
        r = result(); r[field] = bad
        assert parse_record("simlab-result", r)[0] is None
    r = result(); r["trials"][0]["attempts"][0]["status"] = "RETRIED"
    assert parse_record("simlab-result", r)[1][0]["code"] == "E_SCHEMA_ENUM"
    r = result(); r["verdict"] = "supported"
    assert any(f["code"] == "E_SCHEMA_UNKNOWN_FIELD" and f["path"] == "/verdict" for f in parse_record("simlab-result", r)[1])


def test_fixed_enum_strings():
    assert {k.value for k in ObjectiveKind} == {"claim_test", "assumption_test", "mechanism", "design_comparison", "robustness",
                                               "follow_up", "exploration"}
    assert {k.value for k in InvalidReason} == {"numerical_failure", "protocol_violation", "incorrect_intervention",
                                               "missing_required_observation", "corrupted_record", "invalid_state_or_action_delivery"}
    assert {"COMPLETED", "INVALID", "LIMIT_REACHED", "INTERRUPTED", "BLOCKED"} <= {k.value for k in AttemptStatus}
    assert {"QUEUED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED"} <= {k.value for k in RunStatus}


def test_result_schema_has_no_verdict_field():
    props = schemas.generate()["simlab-result"]["properties"]
    assert not any("verdict" in p for p in props)


def test_exported_schema_matches_models():
    assert schemas.drift() == [], "run `simlab schema --write` and review the change (IF-001@r1 drift)"
    for name, s in schemas.generate().items():
        assert s["x-simlab-interface"] == "simlab-if-001@r1"
