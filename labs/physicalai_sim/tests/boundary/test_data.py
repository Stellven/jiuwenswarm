"""V-DATA (AC-013, AC-014): query by every key, fetched values equal those written, provenance, BLOCKED arm."""
import sqlite3

import numpy as np

import fixtures as F
from fixtures import header, run, scene_arm


def test_query_fetch_provenance_and_blocked_arm(service, data_dir):
    arms = [scene_arm("a", "baseline"), scene_arm("b", "treatment", params={"L": 0.5, "m": 1.0, "damping": 0.0}),
            scene_arm("learned", "treatment")]
    head = header(arms=arms, design={"replicates": 2, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 4}},
                  feasibility=[{"dependency_id": "generator_weights", "dependency_kind": "weights", "status": "missing",
                                "reason": "pretrained weights not available on this machine", "affected_arms": ["learned"]},
                               {"dependency_id": "mujoco", "dependency_kind": "engine", "status": "ran", "reason": "admitted executor"}])
    obs = (F.QPOS, {"signal": "energy:total", "unit": "J", "rate_hz": 100}, {"signal": "contacts", "unit": "", "rate_hz": 50})
    res = run(service, F.build(service, head=head, observations=obs))
    blocked = [t for t in res["trials"] if t["arm_id"] == "learned"]
    assert blocked and all(a["status"] == "BLOCKED" and "generator_weights" in a["reason"] for t in blocked for a in t["attempts"])
    assert all(not t["measurements"] for t in blocked) and not [x for x in res["traces"] if x["arm_id"] == "learned"]
    rid = res["run_id"]
    everything = service.query(run_id=rid)
    assert {x["arm_id"] for x in everything["traces"]} == {"a", "b"}
    by_arm = service.query(run_id=rid, arm_id="b")
    assert by_arm["traces"] and all(x["arm_id"] == "b" for x in by_arm["traces"])
    tid = res["trials"][0]["trial_id"]
    by_trial = service.query(run_id=rid, trial_id=tid)
    assert by_trial["traces"] and all(x["trial_id"] == tid for x in by_trial["traces"] + by_trial["measurements"] + by_trial["events"])
    by_sig = service.query(run_id=rid, signal="energy:total")
    assert len(by_sig["traces"]) == 4 and all(x["signal"] == "energy:total" for x in by_sig["traces"])
    combo = service.query(run_id=rid, arm_id="a", signal="qpos:hinge", t_start=1.0, t_end=2.0)
    assert len(combo["traces"]) == 2 and all(x["n_in_range"] == 1001 for x in combo["traces"])
    try:
        service.query(run_id=rid, signal="qpos:nothing")
        raise AssertionError("unknown signal accepted")
    except Exception as e:  # noqa: BLE001
        assert getattr(e, "code", "") == "E_UNKNOWN_SIGNAL"
    ref = combo["traces"][0]["ref"]
    got = service.fetch(ref=ref, t_start=1.0, t_end=2.0)
    path = sqlite3.connect(data_dir / "simlab.sqlite").execute("SELECT path FROM traces WHERE ref=?", (ref,)).fetchone()[0]
    raw = np.load(path)
    sel = raw[(raw[:, 0] >= 1.0) & (raw[:, 0] <= 2.0)]
    assert np.array_equal(np.array(got["rows"]), sel), "fetched values equal those written"
    contacts = service.query(run_id=rid, signal="contacts")["traces"]
    assert contacts and service.fetch(ref=contacts[0]["ref"])["columns"] == ["t", "geom1", "geom2", "dist", "normal_force"]
    p = res["provenance"]
    for k in ("source_revision", "build_id", "lock_sha256", "dependencies", "assets", "configuration", "randomness", "package",
              "run_id", "trial_ids", "attempt_ids", "raw_evidence", "analysis"):
        assert p.get(k) not in (None, "", [], {}), k
    assert p["raw_evidence"]["data_dir"] == str(data_dir.resolve()) and str(p["raw_evidence"]["run_dir"]).startswith(str(data_dir.resolve()))
    assert all(a["sha256"] for a in p["assets"])
    assert res["feasibility"][0]["status"] == "missing"
