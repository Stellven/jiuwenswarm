"""V-BLK-MEAS (AC-009): validity marks exactly the dependent measurements; anchoring; evidence level;
independent recomputation agrees with the primary measurements and detects a planted disagreement."""
import math

import numpy as np
import pytest

from simlab.checks import anchoring, evidence_level, known_answer_check, rerun_summary, validity, watchdog_check, within
from simlab.checks.recompute import recompute
from simlab.measure import trial_value

T = np.arange(0, 6.0005, 0.001)


def write(tmp_path, name, arr):
    p = tmp_path / f"{name}.npy"
    np.save(p, arr)
    return str(p)


@pytest.mark.parametrize("defn", [
    {"kind": "period", "signal": "x", "direction": "up"},
    {"kind": "final", "signal": "x"}, {"kind": "max", "signal": "x"}, {"kind": "mean", "signal": "x", "t_start": 1.0, "t_end": 2.0},
    {"kind": "at_time", "signal": "x", "t": 2.3456}, {"kind": "first_crossing_time", "signal": "x", "level": 0.1, "direction": "down"},
    {"kind": "decay_rate", "signal": "x"}, {"kind": "relative_drift", "signal": "e"}, {"kind": "fit_acceleration", "signal": "z"},
    {"kind": "displacement", "signal": "z"}, {"kind": "range", "signal": "x"}, {"kind": "max_abs", "signal": "x"},
])
def test_recomputation_agrees_with_primary(tmp_path, defn):
    x = 0.3 * np.exp(-0.2 * T) * np.cos(2 * math.pi * T / 1.7)
    traces = {"x": np.c_[T, x], "e": np.c_[T, 5 + 1e-3 * np.sin(T)], "z": np.c_[T, 2 - 0.5 * 9.81 * T ** 2]}
    files = {k: write(tmp_path, k, v) for k, v in traces.items()}
    a, b = trial_value(defn, traces, []), recompute(defn, files, [])
    assert a is not None and within(a, b, {"abs": 1e-9, "rel": 1e-9}), (defn, a, b)


def test_primary_values_are_correct():
    x = np.cos(2 * math.pi * T / 1.7)
    assert trial_value({"kind": "period", "signal": "x"}, {"x": np.c_[T, x]}, []) == pytest.approx(1.7, rel=1e-6)
    z = 2 - 0.5 * 9.81 * T ** 2
    assert trial_value({"kind": "fit_acceleration", "signal": "z"}, {"z": np.c_[T, z]}, []) == pytest.approx(-9.81, rel=1e-9)
    d = np.exp(-0.2 * T) * np.cos(2 * math.pi * T / 1.7)
    assert trial_value({"kind": "decay_rate", "signal": "x"}, {"x": np.c_[T, d]}, []) == pytest.approx(0.2, rel=1e-3)
    assert trial_value({"kind": "period", "signal": "x"}, {"x": np.c_[T, 1 + 0 * T]}, []) is None, "no crossing: missing observation"


def test_planted_disagreement_is_detected(tmp_path):
    x = np.cos(2 * math.pi * T / 1.7)
    f = write(tmp_path, "x", np.c_[T, x])
    primary = trial_value({"kind": "period", "signal": "x"}, {"x": np.c_[T, x]}, []) * 1.01  # tampered measurement
    assert not within(primary, recompute({"kind": "period", "signal": "x"}, {"x": f}, []), {"abs": 1e-9, "rel": 1e-9})


def test_failed_required_check_marks_exactly_dependents_invalid():
    checks = [known_answer_check({"check_id": "ka", "measurement_id": "period", "expected": 2.0, "tolerance": {"rel": 1e-3}, "required": True},
                                 [{"measurement_id": "period", "value": 2.5, "arm_id": "a", "condition": "c", "trial_id": "t"}]),
              {"check_id": "opt", "check_kind": "known_answer", "required": False, "status": "fail", "affected_measurements": ["height"]}]
    assert checks[0]["status"] == "fail" and checks[0]["observed"]["values"][0]["relative_error"] == pytest.approx(0.25)
    meas = [{"measurement_id": "period", "definition": {"kind": "period"}}, {"measurement_id": "height", "definition": {"kind": "max"}},
            {"measurement_id": "mean_period", "definition": {"kind": "set_mean", "of": "period"}}]
    v = validity(checks, meas)
    assert set(v) == {"period", "mean_period"}, "only the measurement and what derives from it; an optional failed check invalidates nothing"
    assert evidence_level("COMPLETED", checks) is None
    assert evidence_level("COMPLETED", checks[1:]) == "simulation"
    assert evidence_level("CANCELLED", []) is None


def test_anchoring():
    arms = [{"arm_id": "a", "role": "baseline"}]
    assert anchoring({"arms": arms, "checks": []}) == "unanchored"
    assert anchoring({"arms": arms + [{"arm_id": "c", "role": "control"}], "checks": []}) == "anchored"
    assert anchoring({"arms": arms, "checks": [{"check_kind": "known_answer"}]}) == "anchored"


def test_watchdog_and_rerun_semantics():
    w = watchdog_check([{"attempt_id": "1", "invalid_reason": None, "status": "COMPLETED", "stop": "watchdog:max_speed"},
                        {"attempt_id": "2", "invalid_reason": "numerical_failure", "status": "INVALID", "stop": "watchdog:nonfinite"}])
    assert w["status"] == "fail" and w["observed"]["divergence_stops"] == {"watchdog:max_speed": ["1"]}
    s = [{"trial_id": "t", "attempt": {"status": "COMPLETED"}, "original": {"p": 2.0}, "rerun": {"p": 2.01}}]
    assert rerun_summary({"check_id": "r", "required_precision": {}}, s, ["p"])["status"] == "pass", "no declared precision: reported only"
    assert rerun_summary({"check_id": "r", "required_precision": {"p": {"rel": 0.001}}}, s, ["p"])["status"] == "fail"
    assert rerun_summary({"check_id": "r", "required_precision": {"p": {"rel": 0.01}}}, s, ["p"])["status"] == "pass"
