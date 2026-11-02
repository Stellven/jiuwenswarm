"""V-BLK-STATUS (AC-006, AC-007, AC-008) with a deterministic fake executor (block level only).

The fake worker returns the status named by the trial parameter `fake`, so the
runner's bookkeeping is checked without physics. BOUNDARY checks use real MuJoCo.
"""
import json
import sys
from pathlib import Path

from simlab.authoring import Authoring
from simlab.contracts.records import Experiment
from simlab.runner.core import Runner
from simlab.runner.design import expand
from simlab.runner.results import build_result
from fixtures import PENDULUM, PERIOD, PROCEDURE, QPOS, header

FAKE = Path(__file__).with_name("fake_worker.py")


def make(store, head, required=True):
    a = Authoring(store)
    d = a.draft_create(head)["draft_id"]
    a.model_file_put(d, "pendulum.xml", PENDULUM)
    a.procedure_put(d, PROCEDURE)
    a.measurement_put(d, {**PERIOD, "required": required})
    a.observation_put(d, QPOS)
    return a.bind(d)["experiment"]


def design_head():
    scene = [{"extension_point": "scene", "artifact": "pendulum.xml"}]
    arms = [{"arm_id": a, "role": r, "components": scene, "params": {"L": 1.0, "m": 1.0, "damping": 0.0, "fake": f}}
            for a, r, f in (("base", "baseline", "COMPLETED"), ("treat", "treatment", "COMPLETED"), ("ctrl", "control", "COMPLETED"))]
    return header(arms=arms, design={
        "factors": [{"factor_id": "length", "levels": [{"level_id": "short", "settings": {"L": 0.5}}, {"level_id": "long", "settings": {"L": 1.0}}]},
                    {"factor_id": "mass", "levels": [{"level_id": "light", "settings": {"m": 0.5}}, {"level_id": "heavy", "settings": {"m": 2.0}}]}],
        "conditions": [{"condition_id": "short-light", "levels": {"length": "short", "mass": "light"}},
                       {"condition_id": "long-heavy", "levels": {"length": "long", "mass": "heavy"}}],
        "pairing": "paired", "replicates": 2, "episodes": 2, "randomness": {"seed_policy": "derived", "base_seed": 11}})


def test_design_expands_to_exact_trial_set(store):
    exp = Experiment.model_validate(make(store, design_head()))
    trials = expand(exp)
    assert len(trials) == 3 * 2 * 2 * 2
    keys = {(t["arm_id"], t["condition"], t["replicate"], t["episode"]) for t in trials}
    assert len(keys) == 24
    pairs = {}
    for t in trials:
        pairs.setdefault(t["pair_id"], set()).add(t["seeds"]["trial"])
    assert len(pairs) == 8 and all(len(s) == 1 for s in pairs.values()), "paired arms share seeds"
    assert expand(exp) == trials, "same seeds give the same trial set"
    assert {t["params"]["L"] for t in trials if t["condition"] == "short-light"} == {0.5}


def test_statuses_attempts_and_no_verdict(store, tmp_path):
    counter = tmp_path / "executions.log"
    head = header(arms=[{"arm_id": s.lower(), "role": "other", "components": [{"extension_point": "scene", "artifact": "pendulum.xml"}],
                         "params": {"L": 1.0, "m": 1.0, "damping": 0.0, "fake": s}}
                        for s in ("COMPLETED", "INVALID", "LIMIT_REACHED")],
                  feasibility=[{"dependency_id": "weights", "dependency_kind": "weights", "status": "missing", "reason": "not released",
                                "affected_arms": ["limit_reached"]}])
    exp = make(store, head, required=False)  # the fake executor writes no traces
    runner = Runner(store, start=False, worker_cmd=[sys.executable, str(FAKE), str(counter)])
    r1 = runner.submit(exp)
    r2 = runner.submit(exp)
    assert r1["run_id"] != r2["run_id"] and r1["experiment_id"] == r2["experiment_id"]
    runner.execute(r1["run_id"])
    res = build_result(store, r1["run_id"])
    by_arm = {t["arm_id"]: t["attempts"] for t in res["trials"]}
    assert by_arm["completed"][0]["status"] == "COMPLETED"
    assert by_arm["invalid"][0]["status"] == "INVALID" and by_arm["invalid"][0]["invalid_reason"] == "numerical_failure"
    assert by_arm["limit_reached"][0]["status"] == "BLOCKED" and "missing dependency weights" in by_arm["limit_reached"][0]["reason"]
    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)
    assert not [k for k in keys(res) if "verdict" in k.lower()], "the runner writes no verdict"
    executions = counter.read_text().splitlines()
    worker_attempts = [a for atts in by_arm.values() for a in atts if a["status"] != "BLOCKED"]
    assert len(executions) == len(worker_attempts) == 2, "no silent rerun: one execution per recorded attempt"
    assert res["anchoring"] == "unanchored"
    queued = store.run_row(r2["run_id"])
    assert queued["status"] == "QUEUED"
    assert runner.cancel(r2["run_id"])["status"] == "CANCELLED"
    assert build_result(store, r2["run_id"])["trials"] == []
