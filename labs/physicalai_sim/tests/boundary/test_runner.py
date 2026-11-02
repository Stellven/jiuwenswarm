"""V-RUNNER (AC-006, AC-007, AC-008) through the real service and real MuJoCo."""
import copy
import json
import sqlite3
import time

import fixtures as F
from fixtures import attempts, header, run, scene_arm


def test_design_expansion_and_scopes(service):
    arms = [scene_arm("base", "baseline"), scene_arm("treat", "treatment", params={"L": 1.0, "m": 1.0, "damping": 0.3}),
            scene_arm("ctrl", "control")]
    design = {"factors": [{"factor_id": "length", "levels": [{"level_id": "short", "settings": {"L": 0.5}}, {"level_id": "long", "settings": {"L": 1.0}}]},
                          {"factor_id": "start", "levels": [{"level_id": "low", "settings": {"theta0": 0.1}}, {"level_id": "high", "settings": {"theta0": 0.4}}]}],
              "conditions": [{"condition_id": "short-low", "levels": {"length": "short", "start": "low"}},
                             {"condition_id": "long-high", "levels": {"length": "long", "start": "high"}}],
              "pairing": "paired", "replicates": 2, "episodes": 2, "randomness": {"seed_policy": "derived", "base_seed": 3}}
    for a in arms:
        a["params"]["theta0"] = 0.2
    meas = [{"measurement_id": "final_angle", "scope": "trial", "unit": "rad", "definition": {"kind": "final", "signal": "qpos:hinge"}},
            {"measurement_id": "damping_effect", "scope": "pair", "unit": "rad",
             "definition": {"kind": "pair_difference", "of": "final_angle", "arms": ["base", "treat"]}},
            {"measurement_id": "mean_final", "scope": "set", "unit": "rad", "definition": {"kind": "set_mean", "of": "final_angle"}}]
    proc = {"steps": [{"step_id": "swing", "duration_s": 0.3}], "initial_state": {"qpos": {"hinge": "${theta0}"}}}
    b = F.build(service, head=header(arms=arms, design=design), procedure=proc, measurements=meas)
    res = run(service, b)
    assert res["status"] == "COMPLETED"
    assert len(res["trials"]) == 24
    assert {(t["arm_id"], t["condition"], t["replicate"], t["episode"]) for t in res["trials"]} == {
        (a, c, r, e) for a in ("base", "treat", "ctrl") for c in ("short-low", "long-high") for r in (0, 1) for e in (0, 1)}
    assert all(t["attempts"][0]["status"] == "COMPLETED" for t in res["trials"])
    pairs = [m for m in res["cross_trial_measurements"] if m["scope"] == "pair"]
    sets = [m for m in res["cross_trial_measurements"] if m["scope"] == "set"]
    assert len(pairs) == 8 and all(m["value"] is not None for m in pairs)
    assert len(sets) == 6 and all(m["n"] == 4 for m in sets)
    seeds = {}
    for t in res["trials"]:
        seeds.setdefault(t["pair_id"], set()).add(json.dumps(t["attempts"][0]["seeds"], sort_keys=True))
    assert all(len(s) == 1 for s in seeds.values())
    again = run(service, b)
    assert again["run_id"] != res["run_id"]
    assert [t["attempts"][0]["seeds"] for t in again["trials"]] == [t["attempts"][0]["seeds"] for t in res["trials"]]
    assert [m["value"] for t in again["trials"] for m in t["measurements"]] == [m["value"] for t in res["trials"] for m in t["measurements"]]


def _one(service, *, scene=F.PENDULUM, scene_path="pendulum.xml", arm=None, procedure=None, measurements=(), observations=(F.QPOS,),
         components=(), head_over=None, **h):
    head = header(arms=[arm or scene_arm(artifact=scene_path)], **(head_over or {}), **h)
    b = F.build(service, scene=scene, scene_path=scene_path, head=head, procedure=procedure or {"steps": [{"step_id": "s", "duration_s": 0.5}]},
                measurements=measurements, observations=observations, components=components)
    return run(service, b)


def test_numerical_failure(service):
    res = _one(service, scene=F.STIFF, scene_path="stiff.xml", arm=scene_arm(artifact="stiff.xml", params={}),
               observations=({"signal": "qpos:s", "unit": "m"},), procedure={"steps": [{"step_id": "s", "duration_s": 1.0}],
                                                                         "initial_state": {"qpos": {"s": 0.01}}},
               resolved_configuration={**F.CONFIG, "integrator": "Euler", "timestep": 0.01})
    a = attempts(res)[0]
    assert (a["status"], a["invalid_reason"]) == ("INVALID", "numerical_failure"), a
    assert res["status"] == "COMPLETED", "the run continues after an invalid trial"


def test_protocol_violation(service):
    proc = {"steps": [{"step_id": "settle", "duration_s": 0.5, "require": [{"signal": "qvel:hinge", "op": "abs<", "value": 1e-6}]},
                      {"step_id": "push", "duration_s": 0.5}], "initial_state": {"qpos": {"hinge": 0.3}}}
    a = attempts(_one(service, procedure=proc))[0]
    assert (a["status"], a["invalid_reason"], a["stop"]) == ("INVALID", "protocol_violation", "require:settle"), a


def test_incorrect_intervention_from_random_value(service):
    design = {"replicates": 6, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 5, "random_variables": [
        {"name": "push", "distribution": {"kind": "normal", "mean": 0.5, "std": 1.0}}]}}
    proc = {"steps": [{"step_id": "s", "duration_s": 0.3}],
            "interventions": [{"intervention_id": "kick", "at_s": 0.1, "action": "add_qvel", "target": "hinge", "value": "${push}", "bounds": [0, 1]}]}
    res = _one(service, procedure=proc, design=design)
    for t in res["trials"]:
        a = t["attempts"][0]
        trial = t
        # recompute the sampled push the same way the runner does
    from simlab.runner.design import derive, sample_random_variables
    from simlab.contracts.records import Experiment
    statuses = [(t["attempts"][0]["status"], t["attempts"][0]["invalid_reason"]) for t in res["trials"]]
    assert ("INVALID", "incorrect_intervention") in statuses and ("COMPLETED", None) in statuses, statuses
    for t in res["trials"]:
        a = t["attempts"][0]
        if a["status"] == "INVALID":
            assert "outside its declared bounds" in a["reason"]


def test_missing_required_observation(service):
    meas = [{"measurement_id": "impact_time", "scope": "trial", "unit": "s", "required": True,
             "definition": {"kind": "event_time", "event_id": "impact"}}]
    proc = {"steps": [{"step_id": "fall", "duration_s": 0.2}], "events": [{"event_id": "impact", "kind": "contact_begin", "geoms": ["box_geom", "floor"]}]}
    a = attempts(_one(service, scene=F.BOX_DROP, scene_path="box.xml", arm=scene_arm(artifact="box.xml", params={"z0": 5.0}),
                      procedure=proc, measurements=meas, observations=({"signal": "xpos:box", "unit": "m"},)))[0]
    assert (a["status"], a["invalid_reason"]) == ("INVALID", "missing_required_observation"), a


def test_invalid_action_delivery(service):
    bad = "def control(obs, params, ctx):\n    return [float('nan')]\n"
    arm = scene_arm(artifact="act.xml", params={}, extra=[{"extension_point": "controller", "artifact": "bad.py"}])
    a = attempts(_one(service, scene=F.ACTUATED, scene_path="act.xml", arm=arm, components=[("bad.py", "controller", bad)]))[0]
    assert (a["status"], a["invalid_reason"]) == ("INVALID", "invalid_state_or_action_delivery"), a


def test_corrupted_record(service, data_dir):
    res = _one(service, procedure=F.PROCEDURE, measurements=(F.PERIOD,))
    assert attempts(res)[0]["status"] == "COMPLETED"
    con = sqlite3.connect(data_dir / "simlab.sqlite")
    path = con.execute("SELECT path FROM traces WHERE run_id=?", (res["run_id"],)).fetchone()[0]
    with open(path, "r+b") as fh:
        fh.seek(-8, 2)
        fh.write(b"\x00" * 8)
    after = service.result(run_id=res["run_id"])
    a = attempts(after)[0]
    assert (a["status"], a["invalid_reason"]) == ("INVALID", "corrupted_record"), a
    assert after["trials"][0]["measurements"][0]["validity"] == "invalid", "kept visible, marked invalid"


def test_divergence_completed_at_its_bound(service):
    proc = {"steps": [{"step_id": "s", "duration_s": 1.0}], "initial_state": {"qvel": {"hinge": 50.0}}}
    a = attempts(_one(service, procedure=proc, limits={"max_sim_time_s": 5, "max_wall_s": 60, "watchdog": {"max_speed": 10.0}}))[0]
    assert (a["status"], a["stop"]) == ("COMPLETED", "watchdog:max_speed"), a


def test_limits(service):
    a = attempts(_one(service, procedure={"steps": [{"step_id": "s", "duration_s": 3.0}]}, limits={"max_sim_time_s": 0.5, "max_wall_s": 60}))[0]
    assert (a["status"], a["stop"]) == ("LIMIT_REACHED", "limit:max_sim_time_s"), a
    a = attempts(_one(service, procedure={"steps": [{"step_id": "s", "duration_s": 200.0}]}, limits={"max_sim_time_s": 500, "max_wall_s": 0.3},
                      resolved_configuration={**F.CONFIG, "timestep": 0.0001}))[0]
    assert (a["status"], a["stop"]) == ("LIMIT_REACHED", "limit:max_wall_s"), a
    spin = "def control(obs, params, ctx):\n    while True:\n        pass\n"
    arm = scene_arm(artifact="act.xml", params={}, extra=[{"extension_point": "controller", "artifact": "spin.py"}])
    a = attempts(_one(service, scene=F.ACTUATED, scene_path="act.xml", arm=arm, components=[("spin.py", "controller", spin)],
                      limits={"max_sim_time_s": 5, "max_wall_s": 60, "component": {"cpu_s": 1, "memory_mb": 1536}}))[0]
    assert (a["status"], a["stop"]) == ("LIMIT_REACHED", "limit:component_cpu_s"), a
    hog = "def control(obs, params, ctx):\n    x = bytearray(4 * 1024 ** 3)\n    return [0.0]\n"
    arm = scene_arm(artifact="act.xml", params={}, extra=[{"extension_point": "controller", "artifact": "hog.py"}])
    a = attempts(_one(service, scene=F.ACTUATED, scene_path="act.xml", arm=arm, components=[("hog.py", "controller", hog)],
                      limits={"max_sim_time_s": 5, "max_wall_s": 60, "component": {"cpu_s": 30, "memory_mb": 1024}}))[0]
    assert (a["status"], a["stop"]) == ("LIMIT_REACHED", "limit:component_memory_mb"), a


def test_cancel_running_and_queued(service):
    proc = {"steps": [{"step_id": "s", "duration_s": 12.0}], "initial_state": {"qpos": {"hinge": 0.3}}}
    head = header(design={"replicates": 3, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 1}},
                  resolved_configuration={**F.CONFIG, "timestep": 0.0001}, limits={"max_sim_time_s": 30, "max_wall_s": 120})
    b = F.build(service, head=head, procedure=proc)
    long_run = service.submit(experiment=b["experiment"])["run_id"]
    queued = service.submit(experiment=b["experiment"])["run_id"]
    assert service.status(run_id=queued)["status"] == "QUEUED"
    assert service.cancel(run_id=queued)["status"] == "CANCELLED"
    assert service.result(run_id=queued)["trials"] == []
    deadline = time.monotonic() + 120
    while service.status(run_id=long_run)["attempts_by_status"].get("COMPLETED", 0) < 1:
        assert time.monotonic() < deadline
        time.sleep(0.2)
    while "RUNNING" not in service.status(run_id=long_run)["attempts_by_status"]:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert service.cancel(run_id=long_run)["status"] == "CANCELLED"
    res = service.result(run_id=long_run)
    st = [t["attempts"][0]["status"] for t in res["trials"]]
    assert st[0] == "COMPLETED" and st[-1] == "INTERRUPTED" and len(st) == 2, st
    assert res["trials"][0]["measurements"], "completed trials are kept"
    err = None
    try:
        service.cancel(run_id=long_run)
    except Exception as e:  # noqa: BLE001
        err = e
    assert getattr(err, "code", None) == "E_ALREADY_TERMINAL"
