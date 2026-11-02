"""V-BLK-STATE (AC-012): a checkpoint holds world state, random state, pending events and action history; restoring it
in a fresh process continues exactly; a checkpoint missing a part is rejected with a typed error."""
import json

import fixtures as F
from fixtures import header, run, scene_arm
from simlab.store import Store
from simlab.validation import validate

PROC = {"steps": [{"step_id": "a", "duration_s": 1.0}, {"step_id": "b", "duration_s": 1.0}], "initial_state": {"qpos": {"hinge": 0.3}},
        "interventions": [{"intervention_id": "kick", "at_s": 1.5, "action": "add_qvel", "target": "hinge", "value": 0.5}],
        "checkpoints": [{"checkpoint_point_id": "after_a", "step_end": "a"}]}
NOISY = '''
def control(obs, params, ctx):
    return [float(ctx.rng.normal(0.0, 0.2)) - 2.0 * obs["qpos"][0]]
'''


def built(service):
    arm = scene_arm(artifact="act.xml", params={}, extra=[{"extension_point": "controller", "artifact": "noisy.py"}])
    return F.build(service, scene=F.ACTUATED, scene_path="act.xml", head=header(arms=[arm]), procedure=PROC, measurements=(),
                   observations=(F.QPOS,), components=[("noisy.py", "controller", NOISY)])


def test_checkpoint_parts_and_restore(service, data_dir):
    res = run(service, built(service))
    cp = res["checkpoints"][0]
    st = Store(data_dir)
    row = st.get_checkpoint(cp["checkpoint_id"])
    meta = json.loads(st.get_blob(row["files"]["meta.json"]))
    assert set(meta["parts"]) == {"world_state", "random_state", "pending_events", "action_history"}
    assert meta["pending"] == ["kick"] and meta["rng_state"]["bit_generator"] == "PCG64" and meta["step_index"] == 1000
    assert {"state.npy", "actions.npy", "meta.json"} == set(row["files"])
    d = service.branch(checkpoint_id=cp["checkpoint_id"])["draft_id"]
    b = service.bind(draft_id=d)
    br = run(service, b)
    a0 = st.q1("SELECT exec FROM attempts WHERE attempt_id=?", (res["trials"][0]["attempts"][0]["attempt_id"],))["exec"]
    a1 = st.q1("SELECT exec FROM attempts WHERE attempt_id=?", (br["trials"][0]["attempts"][0]["attempt_id"],))["exec"]
    assert json.loads(a0)["suffix_digests"]["after_a"] == json.loads(a1)["suffix_digests"]["restore"], "continuation is bitwise identical"
    assert json.loads(a1)["restored"]["pending_restored"] == ["kick"] and json.loads(a1)["restored"]["pending_changed"] == []


def test_incomplete_checkpoint_rejected(service, data_dir):
    res = run(service, built(service))
    cp = res["checkpoints"][0]
    st = Store(data_dir)
    row = st.get_checkpoint(cp["checkpoint_id"])
    meta = json.loads(st.get_blob(row["files"]["meta.json"]))
    for drop in ("rng_state", "pending"):
        damaged = {k: v for k, v in meta.items() if k != drop}
        sha = st.put_blob(json.dumps(damaged).encode())
        cid = cp["checkpoint_id"] + "x" + drop[:3]
        st.add_checkpoint({**row, "checkpoint_id": cid, "files": {**row["files"], "meta.json": sha}})
        d = service.branch(checkpoint_id=cid)["draft_id"]
        f = service.validate(experiment=service.bind(draft_id=d)["experiment"])["findings"]
        assert [x["code"] for x in f] == ["E_SEMANTIC_CHECKPOINT_INCOMPATIBLE"] and ("random_state" in f[0]["message"] or "pending_events" in f[0]["message"])
    cid = cp["checkpoint_id"] + "noacts"
    st.add_checkpoint({**row, "checkpoint_id": cid, "files": {k: v for k, v in row["files"].items() if k != "actions.npy"}})
    f = service.validate(experiment=service.bind(draft_id=service.branch(checkpoint_id=cid)["draft_id"])["experiment"])["findings"]
    assert "action_history" in f[0]["message"]
