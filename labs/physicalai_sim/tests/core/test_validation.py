"""V-BLK-VALID (AC-003, AC-005, AC-009 comparison findings, Edge Cases): every finding at once; never by kind."""
import copy

import pytest

from simlab.authoring import Authoring
from simlab.validation import validate
from fixtures import PENDULUM, PERIOD, PROCEDURE, QPOS, header


class _Shim:
    """Authoring calls in the client's keyword style, for block-level tests on a bare store."""
    def __init__(self, store):
        self.a = Authoring(store)

    def __getattr__(self, name):
        return getattr(self.a, name)


def bound(store, head=None, procedure=None, scene=PENDULUM, measurements=(PERIOD,), observations=(QPOS,)):
    a = Authoring(store)
    d = a.draft_create(head or header())["draft_id"]
    a.model_file_put(d, "pendulum.xml", scene)
    a.procedure_put(d, procedure or PROCEDURE)
    for m in measurements:
        a.measurement_put(d, m)
    for o in observations:
        a.observation_put(d, o)
    return a.bind(d)["experiment"]


def codes(findings):
    return sorted(f["code"] for f in findings)


def test_clean_control_has_zero_findings(store):
    assert validate(bound(store), store)[1] == []


@pytest.mark.parametrize("kind", ["claim_test", "assumption_test", "mechanism", "design_comparison", "robustness", "follow_up", "exploration"])
def test_every_objective_kind_validates(store, kind):
    assert validate(bound(store, head=header(objective_kind=kind)), store)[1] == []


def test_single_defects_each_give_their_code(store):
    cases = {
        "E_SEMANTIC_NO_ORIGIN": header(protocol_items=[{"item_id": "n", "item_kind": "trial_count", "value": 3}]),
        "E_SEMANTIC_ZERO_TRIALS": header(design={"replicates": 0, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 1}}),
        "E_SEMANTIC_COMPARISON_INCOMPLETE": header(design={"replicates": 1, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 1},
                                                          "comparisons": [{"comparison_id": "c", "arms": ["a"], "unit_of_inference": "trial"}]}),
        "E_SEMANTIC_PARENT_MISSING": header(parent={"run_id": "run-does-not-exist"}),
        "E_SEMANTIC_ENGINE_FLAG": header(resolved_configuration={**header()["resolved_configuration"], "enable_flags": ["ipc"]}),
        "E_SEMANTIC_ENGINE": header(engines=[{"engine": "mujoco", "version": "3.16.0", "why": "older"}]),
        "E_SEMANTIC_TEMPLATE": header(arms=[{"arm_id": "a", "role": "baseline", "components": [{"extension_point": "scene", "artifact": "pendulum.xml"}],
                                              "params": {"L": 1.0}}]),
    }
    for code, head in cases.items():
        f = validate(bound(store, head=head), store)[1]
        assert code in codes(f), (code, f)


def test_undeclared_checkpoint_and_unknown_target(store):
    proc = copy.deepcopy(PROCEDURE)
    proc["checkpoints"] = [{"checkpoint_point_id": "cp", "step_end": "no-such-step"}]
    proc["interventions"] = [{"intervention_id": "push", "at_s": 1.0, "action": "add_qvel", "target": "no_joint", "value": 1.0}]
    f = validate(bound(store, procedure=proc), store)[1]
    assert {"E_SEMANTIC_UNDECLARED_CHECKPOINT", "E_SEMANTIC_UNKNOWN_TARGET"} <= set(codes(f))


def test_mjcf_compile_error_includes_engine_message(store):
    f = validate(bound(store, scene="<mujoco><worldbody><body><joint type='hinge'/></body></worldbody></mujoco>"), store)[1]
    assert any(x["code"] == "E_SEMANTIC_MJCF_COMPILE" and "MuJoCo" in x["message"] for x in f), f


def test_asset_tampered_after_bind(store):
    exp = bound(store)
    m = store.get_manifest(exp["assets"]["manifest_id"])
    p = store.blob_path(m["artifacts"][0]["sha256"])
    p.chmod(0o644)
    p.write_bytes(b"<mujoco/>")
    assert "E_SEMANTIC_ASSET_HASH" in codes(validate(exp, store)[1])


def test_changed_experiment_no_longer_matches_its_manifest(store):
    exp = bound(store)
    exp["objective"] = "something else"
    assert "E_SEMANTIC_MANIFEST_BINDING" in codes(validate(exp, store)[1])


def test_unbound_experiment(store):
    exp = bound(store)
    exp.pop("assets")
    assert "E_NOT_BOUND" in codes(validate(exp, store)[1])


def test_many_defects_all_returned_together(store):
    """Five independent defects of different kinds come back in one call: schema and semantic together.
    (Dropping the unknown field restores the bound content, so no manifest-binding finding is due.)"""
    head = header(protocol_items=[{"item_id": "n", "item_kind": "trial_count", "value": 3}],
                  design={"replicates": 1, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 1},
                          "comparisons": [{"comparison_id": "c", "arms": ["a"], "unit_of_inference": "trial"}]},
                  engines=[{"engine": "mujoco", "version": "3.16.0", "why": "older"}])
    proc = copy.deepcopy(PROCEDURE)
    proc["checkpoints"] = [{"checkpoint_point_id": "cp", "step_end": "missing-step"}]
    exp = bound(store, head=head, procedure=proc)
    exp["colour"] = "blue"
    f = validate(exp, store)[1]
    assert codes(f) == sorted(["E_SCHEMA_UNKNOWN_FIELD", "E_SEMANTIC_NO_ORIGIN", "E_SEMANTIC_COMPARISON_INCOMPLETE", "E_SEMANTIC_ENGINE",
                               "E_SEMANTIC_UNDECLARED_CHECKPOINT"]), f
