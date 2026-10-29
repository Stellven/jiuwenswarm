from copy import deepcopy

import pytest

from jiuwenswarm.research_router.policy import NoRoute, choose
from .test_catalog import entry


def policy():
    return {"quality_floor": 0.8, "max_uncertainty": 0.1,
            "currency": "USD", "priority": ["b", "a"], "compatible_baseline_id": None}


def request():
    return {"task_category": "software_systems_and_performance", "requirements": {},
            "preferences": {}, "selected_capsule": {"declaration_ref": {"sha256": "c" * 64},
            "declaration": {"needs": {"model": {"modalities": ["text"], "tool_calling": False}},"budget":{"per_call":{"wall_s":20}}},
            "bound_context": {"invocation_limits": {"time_s": 20, "model_calls": 1, "memory_mb": 256},
            "subnode_limits":{"time_s":20,"model_calls":1,"memory_mb":256},
            "node_limits":{"time_s":60,"model_calls":4,"memory_mb":512},
            "budget_snapshot": {"node_remaining": {"time_s": 60, "model_calls": 4, "memory_mb": 512},
            "subnode_remaining": {"time_s": 20, "model_calls": 1, "memory_mb": 256},
            "verifier_reserved": {"time_s": 20, "model_calls": 1, "memory_mb": 256},
            "routing_reserved": {"time_s": 0, "model_calls": 0, "memory_mb": 256},
            "other_work_reserved": {"time_s": 20, "model_calls": 1, "memory_mb": 256}}}}}


def aggregate(model, cost):
    return {"model_id": model, "task_category": "software_systems_and_performance",
            "declaration_sha256": "c" * 64, "deployment_sha256": "a" * 64,
            "scope_key": "bounded-code", "quality": 0.9, "uncertainty": 0.05,
            "expected_complete_cost": cost, "currency": "USD", "sample_count": 10,
            "repeat_count": 1, "frozen": True, "oracle_eligible": True}


def test_lowest_complete_cost_then_priority_including_singleton_coverage():
    candidates = [entry(model_id="a"), entry(model_id="b")]
    profile = {"approved_model_ids": ["a", "b"], "extra_requirements": {}, "policy_mode": "development_profile"}
    chosen = choose(request(), candidates, profile, policy(), [aggregate("a", 3), aggregate("b", 2)], "bounded-code")
    assert chosen[0]["model_id"] == "b"
    with pytest.raises(NoRoute, match="PROFILE_COVERAGE_MISSING"):
        choose(request(), candidates[:1], profile, policy(), [], "bounded-code")


def test_json_port_does_not_imply_native_json_and_empty_allowlist_denies():
    r = request(); r["requirements"] = {"model_allowlist": []}
    with pytest.raises(NoRoute): choose(r, [entry()], {"approved_model_ids": ["test.executor"]}, policy(), [], "x")


def test_ablation_refused_before_any_selection():
    with pytest.raises(NoRoute, match="PROFILE_UNAVAILABLE"):
        choose(request(), [], {"policy_mode": "bounded_llm_ablation"}, policy(), [], "x")


def test_m1_policy_mode_boundaries(tmp_path):
    import asyncio
    from jiuwenswarm.research.router_client import RouterPort
    from jiuwenswarm.research_router.profiles import validate_profile
    port=RouterPort(tmp_path/'absent.sock',peer_uid=0)
    context={'call_function':'worker','router':{'enabled':True,'deadline_s':30},'model_selection_profile':{'policy_mode':'fixed_baseline'}}
    choice=asyncio.run(port.select(context))
    assert choice.decision_source=='codex_router_disabled' and choice.route_decision_ref is None
    assert validate_profile({'policy_mode':'development_profile','selection_allowance':{'enabled':False,'model_calls':0}})
    with pytest.raises(NoRoute):validate_profile({'policy_mode':'bounded_llm_ablation'})

