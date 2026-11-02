"""V-REQ (AC-003): every objective kind is accepted; a follow-up records a valid parent; a bad parent is a finding."""
import pytest

import fixtures as F
from fixtures import header, run

KINDS = ["claim_test", "assumption_test", "mechanism", "design_comparison", "robustness", "follow_up", "exploration"]


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_validates(service, kind):
    assert service.validate(experiment=F.build(service, head=header(objective_kind=kind))["experiment"])["findings"] == []


def test_follow_up_parent(service):
    first = run(service, F.build(service))
    follow = F.build(service, head=header(objective_kind="follow_up", objective="Same pendulum, longer", parent={"run_id": first["run_id"]},
                                          arms=[F.scene_arm(params={"L": 2.0, "m": 1.0, "damping": 0.0})]))
    res = run(service, follow)
    assert res["parent"] == {"run_id": first["run_id"], "checkpoint_id": None}
    bad = F.build(service, head=header(objective_kind="follow_up", parent={"run_id": "run-00000000000000000000"}))
    f = service.validate(experiment=bad["experiment"])["findings"]
    assert [x["code"] for x in f] == ["E_SEMANTIC_PARENT_MISSING"]
    no_objective = dict(follow["experiment"]); no_objective.pop("objective")
    assert "E_SCHEMA_REQUIRED" in [x["code"] for x in service.validate(experiment=no_objective)["findings"]]
    bad_kind = dict(follow["experiment"], objective_kind="replication_of_a_claim")
    assert "E_SCHEMA_ENUM" in [x["code"] for x in service.validate(experiment=bad_kind)["findings"]]
