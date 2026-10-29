import pytest

from jiuwenswarm.research_router.policy import NoRoute, budget_compatible
from .test_policy import request
from .test_catalog import entry


def test_verifier_reservation_cannot_be_borrowed():
    r = request(); r["selected_capsule"]["bound_context"]["budget_snapshot"]["node_remaining"]["model_calls"] = 2
    with pytest.raises(NoRoute, match="BUDGET_EXCEEDED"): budget_compatible(r, entry())


def test_memory_is_minimum_ceiling_not_additive_spend():
    assert budget_compatible(request(), entry())["memory_mb"] == 256
    r = request(); r["selected_capsule"]["bound_context"]["budget_snapshot"]["node_remaining"]["memory_mb"] = 128
    assert budget_compatible(r, entry())["memory_mb"] == 128


def test_all_frozen_contract_and_declaration_ceilings_remain_binding():
    r=request();context=r['selected_capsule']['bound_context']
    context['subnode_limits']['time_s']=7;context['node_limits']['memory_mb']=96
    r['selected_capsule']['declaration']['budget']['per_call']['wall_s']=5
    limits=budget_compatible(r,entry())
    assert limits['time_s']==5 and limits['memory_mb']==96

