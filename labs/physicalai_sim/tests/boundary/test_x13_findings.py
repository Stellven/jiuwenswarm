"""V-X1.3 (AC-005): a malformed experiment returns all findings at once; submit creates no run; clean controls run."""
import copy
import sqlite3

import fixtures as F
from fixtures import PROCEDURE, header, run, scene_arm

PLANTED = {
    "E_SCHEMA_UNKNOWN_FIELD": "/notes",
    "E_SEMANTIC_NO_ORIGIN": "/protocol_items/1/origin",
    "E_SEMANTIC_COMPARISON_INCOMPLETE": "/design/comparisons/0",
    "E_SEMANTIC_UNDECLARED_CHECKPOINT": "/procedure/checkpoints/0/step_end",
    "E_SEMANTIC_UNKNOWN_TARGET": "/procedure/interventions/0/target",
    "E_SEMANTIC_ENGINE": "/engines/0",
}


def defective_and_clean(service):
    arms = [scene_arm("a", "baseline"), scene_arm("b", "treatment", params={"L": 0.7, "m": 1.0, "damping": 0.0})]
    base = dict(arms=arms, design={"replicates": 1, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 9},
                                   "comparisons": [{"comparison_id": "length_effect", "arms": ["a", "b"], "unit_of_inference": "trial",
                                                    "pairing": "none", "aggregation": "difference of periods", "required_precision": 0.01}]})
    clean_proc = copy.deepcopy(PROCEDURE)
    clean_proc["checkpoints"] = [{"checkpoint_point_id": "mid", "step_end": "swing"}]
    clean_proc["interventions"] = [{"intervention_id": "kick", "at_s": 1.0, "action": "add_qvel", "target": "hinge", "value": 0.1}]
    bad_head = header(**copy.deepcopy(base))
    bad_head["protocol_items"].append({"item_id": "trials", "item_kind": "trial_count", "value": 1})
    bad_head["design"]["comparisons"][0].pop("aggregation")
    bad_head["engines"] = [{"engine": "mujoco", "version": "3.16.0", "why": "older engine"}]
    bad_proc = copy.deepcopy(clean_proc)
    bad_proc["checkpoints"][0]["step_end"] = "no-such-step"
    bad_proc["interventions"][0]["target"] = "elbow"
    bad = F.build(service, head=bad_head, procedure=bad_proc)["experiment"]
    bad["notes"] = "unrequested field"
    clean = F.build(service, head=header(**copy.deepcopy(base)), procedure=clean_proc)["experiment"]
    return bad, clean


def runs(data_dir):
    return sqlite3.connect(data_dir / "simlab.sqlite").execute("SELECT COUNT(*) FROM runs").fetchone()[0]


def test_all_findings_at_once_and_clean_controls_pass(service, data_dir):
    bad, clean = defective_and_clean(service)
    findings = service.validate(experiment=bad)["findings"]
    assert sorted((f["code"], f["path"]) for f in findings) == sorted(PLANTED.items()), findings
    assert all(f["severity"] == "error" and f["message"] for f in findings)
    before = runs(data_dir)
    sub = service.submit(experiment=bad)
    assert "run_id" not in sub and sorted(f["code"] for f in sub["findings"]) == sorted(PLANTED)
    assert runs(data_dir) == before, "a defective experiment creates no run"
    assert service.validate(experiment=clean)["findings"] == []
    res = run(service, {"experiment": clean})
    assert res["status"] == "COMPLETED" and all(t["attempts"][0]["status"] == "COMPLETED" for t in res["trials"])
    assert len(res["checkpoints"]) == 2
