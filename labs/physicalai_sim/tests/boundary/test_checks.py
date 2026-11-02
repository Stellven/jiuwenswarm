"""V-CHECKS (AC-009) through the real service and real MuJoCo."""
import math

import fixtures as F
from fixtures import attempts, header, run, scene_arm


def by_id(res):
    return {c["check_id"]: c for c in res["checks"]}


def test_reruns_recomputation_anchoring_and_evidence_level(service):
    checks = [{"check_id": "timestep_rerun", "check_kind": "rerun", "required": True, "samples_per_arm": 5,
               "variations": [{"setting": "config.timestep", "values": [0.0005]}, {"setting": "param:m", "values": [2.0]}],
               "required_precision": {"period": {"rel": 0.001}}}]
    head = header(design={"replicates": 6, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 2}}, checks=checks)
    res = run(service, F.build(service, head=head))
    c = by_id(res)
    assert c["timestep_rerun"]["observed"]["samples_per_arm"] == 5
    assert len(c["timestep_rerun"]["observed"]["samples"]) == 5 * 2, "5 samples per arm x 2 variations"
    var = c["timestep_rerun"]["observed"]["variation_by_measurement"]["period"]
    assert var["n"] == 10 and var["max_rel_change"] < 0.001 and c["timestep_rerun"]["status"] == "pass"
    assert c["recomputation"]["status"] == "pass" and c["recomputation"]["observed"]["compared"] == 6
    assert c["watchdog"]["status"] == "pass"
    assert res["anchoring"] == "unanchored" and res["status"] == "COMPLETED"
    assert res["evidence_level"] == "simulation", "required checks pass"
    assert len(res["trials"]) == 6, "rerun samples are check executions, not counted trials"


def test_rerun_fails_beyond_required_precision(service):
    checks = [{"check_id": "length_rerun", "check_kind": "rerun", "samples_per_arm": 2,
               "variations": [{"setting": "param:L", "values": [1.1]}], "required_precision": {"period": {"rel": 0.001}}}]
    head = header(design={"replicates": 2, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 2}}, checks=checks)
    res = run(service, F.build(service, head=head))
    c = by_id(res)["length_rerun"]
    assert c["status"] == "fail" and c["affected_measurements"] == ["period"]
    mv = {m["measurement_id"]: m for m in res["measurement_validity"]}
    assert mv["period"]["validity"] == "invalid" and mv["period"]["failed_checks"] == ["length_rerun"]
    assert all(m["value"] is not None and m["validity"] == "invalid" for t in res["trials"] for m in t["measurements"]), "visible, not dropped"
    assert res["evidence_level"] is None


def test_planted_failing_known_answer_marks_only_its_measurement(service):
    L, g, th = 1.0, 9.81, 0.2
    k = math.sin(th / 2) ** 2
    a, b = 1.0, math.sqrt(1 - k)
    for _ in range(30):
        a, b = (a + b) / 2, math.sqrt(a * b)
    period = 2 * math.pi * math.sqrt(L / g) / a
    amp = {"measurement_id": "amplitude", "scope": "trial", "unit": "rad", "definition": {"kind": "max", "signal": "qpos:hinge"}}
    checks = [{"check_id": "ka_wrong", "check_kind": "known_answer", "measurement_id": "period", "expected": period * 1.2,
               "tolerance": {"rel": 0.005}, "origin": "planted wrong expectation (negative control)"},
              {"check_id": "ka_right", "check_kind": "known_answer", "measurement_id": "amplitude", "expected": th,
               "tolerance": {"rel": 0.005}, "origin": "initial condition"}]
    res = run(service, F.build(service, head=header(checks=checks), measurements=(F.PERIOD, amp)))
    c = by_id(res)
    assert c["ka_wrong"]["status"] == "fail" and c["ka_right"]["status"] == "pass"
    mv = {m["measurement_id"]: m["validity"] for m in res["measurement_validity"]}
    assert mv == {"period": "invalid", "amplitude": "valid"}
    vals = {m["measurement_id"]: m for m in res["trials"][0]["measurements"]}
    assert vals["period"]["value"] == vals["period"]["value"] and vals["period"]["validity"] == "invalid"
    assert abs(vals["period"]["value"] - period) / period < 0.005
    assert res["anchoring"] == "anchored" and res["evidence_level"] is None


def test_unexpected_control_arm_outcome_is_a_result(service):
    arms = [scene_arm("base", "baseline"), scene_arm("ctrl", "control", params={"L": 1.0, "m": 1.0, "damping": 5.0})]
    checks = [{"check_id": "ctrl_ran", "check_kind": "control_arm", "arms": ["ctrl"]}]
    meas = [{"measurement_id": "final", "scope": "trial", "unit": "rad", "definition": {"kind": "final", "signal": "qpos:hinge"}}]
    res = run(service, F.build(service, head=header(arms=arms, checks=checks), measurements=meas))
    assert by_id(res)["ctrl_ran"]["status"] == "pass" and res["anchoring"] == "anchored"
    assert res["evidence_level"] == "simulation"


def test_nonfinite_and_penetration_watchdogs(service):
    b = F.build(service, scene=F.STIFF, scene_path="stiff.xml", head=header(arms=[scene_arm(artifact="stiff.xml", params={})],
                resolved_configuration={**F.CONFIG, "integrator": "Euler", "timestep": 0.01}),
                procedure={"steps": [{"step_id": "s", "duration_s": 1.0}], "initial_state": {"qpos": {"s": 0.01}}},
                measurements=(), observations=({"signal": "qpos:s", "unit": "m"},))
    res = run(service, b)
    assert by_id(res)["watchdog"]["status"] == "fail" and attempts(res)[0]["invalid_reason"] == "numerical_failure"
    soft = F.BOX_DROP.replace('mass="0.5"', 'mass="0.5" solref="0.5 1"')
    b = F.build(service, scene=soft, scene_path="box.xml", head=header(arms=[scene_arm(artifact="box.xml", params={"z0": 0.3})],
                limits={"max_sim_time_s": 5, "max_wall_s": 60, "watchdog": {"max_penetration": 0.005}}),
                procedure={"steps": [{"step_id": "s", "duration_s": 1.5}]}, measurements=(), observations=({"signal": "xpos:box", "unit": "m"},))
    a = attempts(run(service, b))[0]
    assert (a["status"], a["stop"]) == ("COMPLETED", "watchdog:max_penetration"), a


def test_counted_comparison_needs_its_declarations(service):
    head = header(design={"replicates": 1, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 1},
                          "comparisons": [{"comparison_id": "c", "arms": ["a"], "unit_of_inference": "trial", "pairing": "none"}]})
    f = service.validate(experiment=F.build(service, head=head)["experiment"])["findings"]
    assert [x["code"] for x in f] == ["E_SEMANTIC_COMPARISON_INCOMPLETE"] and "aggregation" in f[0]["message"]
