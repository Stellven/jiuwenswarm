"""V-X1.5 (AC-011, AC-012): replay is identical on the same machine and build; save, restore and branch reproduce the
continuation; each checked with its declared rule; a changed-seed control is detected as different."""
import copy
import json
import sqlite3

import numpy as np

import fixtures as F
from fixtures import header, run, scene_arm
from simlab.store import Store

NOISY = '''
def control(obs, params, ctx):
    return [float(ctx.rng.normal(0.0, 0.3)) - params.get("kp", 3.0) * obs["qpos"][0]]
'''
PROC = {"steps": [{"step_id": "settle", "duration_s": 1.0}, {"step_id": "push", "duration_s": 1.5}],
        "initial_state": {"qpos": {"hinge": "${theta0}"}},
        "interventions": [{"intervention_id": "kick", "at_s": 1.6, "action": "add_qvel", "target": "hinge", "value": 0.8}],
        "checkpoints": [{"checkpoint_point_id": "after_settle", "step_end": "settle"}]}
RULE = "bitwise-equal per-step state digests and equal measurement values"


def build(service, base_seed=21):
    arm = scene_arm(artifact="act.xml", params={"kp": 3.0}, extra=[{"extension_point": "controller", "artifact": "noisy.py", "params": {"kp": 3.0}}])
    design = {"replicates": 2, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": base_seed, "random_variables": [
        {"name": "theta0", "distribution": {"kind": "uniform", "low": 0.1, "high": 0.5}}]}}
    meas = [{"measurement_id": "final_angle", "scope": "trial", "unit": "rad", "definition": {"kind": "final", "signal": "qpos:hinge"}},
            {"measurement_id": "peak", "scope": "trial", "unit": "rad", "definition": {"kind": "max_abs", "signal": "qpos:hinge"}}]
    return F.build(service, scene=F.ACTUATED, scene_path="act.xml", head=header(arms=[arm], design=design), procedure=PROC,
                   measurements=meas, observations=({"signal": "qpos:hinge", "unit": "rad"}, {"signal": "ctrl:torque", "unit": "N m"}),
                   components=[("noisy.py", "controller", NOISY)])


def digests(res):
    return [t["attempts"][-1]["state_digest"] for t in res["trials"]]


def test_replay_identical_and_changed_seed_differs(service, data_dir):
    orig = run(service, build(service))
    assert orig["status"] == "COMPLETED" and all(digests(orig))
    rep = service.replay(run_id=orig["run_id"])
    res = F.wait_result(service, rep["run_id"])
    assert res["run_kind"] == "replay" and res["replay_of"] == orig["run_id"] and res["run_id"] != orig["run_id"]
    ident = next(c for c in res["checks"] if c["check_id"] == "replay_identity")
    assert ident["status"] == "pass" and ident["observed"]["trials_compared"] == 2 and RULE.split(" and ")[0] in ident["observed"]["rule"]
    assert digests(res) == digests(orig)
    assert [m["value"] for t in res["trials"] for m in t["measurements"]] == [m["value"] for t in orig["trials"] for m in t["measurements"]]
    st = Store(data_dir)
    ex = json.loads(st.q1("SELECT exec FROM attempts WHERE attempt_id=?", (res["trials"][0]["attempts"][0]["attempt_id"],))["exec"])
    assert ex["replayed_actions"] and ex["replayed_actions"] > 0, "replay fed the recorded actions"
    changed = run(service, build(service, base_seed=22))
    assert set(digests(changed)).isdisjoint(digests(orig)), "the changed-seed control is detected as different"


def test_not_replayable_on_another_build(service, data_dir):
    orig = run(service, build(service))
    con = sqlite3.connect(data_dir / "simlab.sqlite")
    ident = json.loads(con.execute("SELECT identity FROM runs WHERE run_id=?", (orig["run_id"],)).fetchone()[0])
    ident["build_id"] = "0" * 64
    con.execute("UPDATE runs SET identity=? WHERE run_id=?", (json.dumps(ident), orig["run_id"]))
    con.commit()
    try:
        service.replay(run_id=orig["run_id"])
        raise AssertionError("replay claimed across builds")
    except Exception as e:  # noqa: BLE001
        assert getattr(e, "code", "") == "E_NOT_REPLAYABLE" and "build_id" in str(e)


def rows_from(service, res, t0):
    ref = next(x["ref"] for x in res["traces"] if x["signal"] == "qpos:hinge" and x["trial_id"] == res["trials"][0]["trial_id"])
    return np.array(service.fetch(ref=ref, t_start=t0, max_rows=200000)["rows"])


def test_restore_continue_and_branch(service, data_dir):
    orig = run(service, build(service))
    cp = next(c for c in orig["checkpoints"] if c["trial_id"] == orig["trials"][0]["trial_id"])
    assert abs(cp["time_s"] - 1.0) < 1e-9
    same = service.branch(checkpoint_id=cp["checkpoint_id"])
    cont = run(service, {"experiment": service.bind(draft_id=same["draft_id"])["experiment"]})
    assert cont["parent"]["checkpoint_id"] == cp["checkpoint_id"] and cont["run_id"] != orig["run_id"]
    a, b = rows_from(service, orig, cp["time_s"]), rows_from(service, cont, cp["time_s"])
    assert a.shape == b.shape and np.array_equal(a, b), "restore-and-continue equals the uninterrupted run, bit for bit"
    st = Store(data_dir)
    sa = json.loads(st.q1("SELECT exec FROM attempts WHERE attempt_id=?", (orig["trials"][0]["attempts"][0]["attempt_id"],))["exec"])
    sb = json.loads(st.q1("SELECT exec FROM attempts WHERE attempt_id=?", (cont["trials"][0]["attempts"][0]["attempt_id"],))["exec"])
    assert sa["suffix_digests"]["after_settle"] == sb["suffix_digests"]["restore"]
    # a what-if branch: a harder kick from the same saved state
    whatif = service.branch(checkpoint_id=cp["checkpoint_id"])
    service.intervention_put(draft_id=whatif["draft_id"], intervention={**PROC["interventions"][0], "value": 2.0})
    br = run(service, {"experiment": service.bind(draft_id=whatif["draft_id"])["experiment"]})
    assert br["parent"]["checkpoint_id"] == cp["checkpoint_id"]
    c = rows_from(service, br, cp["time_s"])
    before = a[:, 0] < 1.6 - 1e-9
    assert np.array_equal(a[before], c[before]), "identical until the changed intervention"
    assert not np.array_equal(a[~before], c[~before]), "different after it"
