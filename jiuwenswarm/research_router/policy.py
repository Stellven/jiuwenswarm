"""Deterministic source-bounded filtering and frozen development aggregates."""
from decimal import Decimal
import math


class NoRoute(ValueError):
    def __init__(self, code, exclusions=()):
        self.code = code
        self.exclusions = list(exclusions)
        super().__init__(code)


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def budget_compatible(request, candidate):
    context = request["selected_capsule"]["bound_context"]
    snapshot = context["budget_snapshot"]
    invocation = context["invocation_limits"]
    declared_wall=request['selected_capsule']['declaration']['budget']['per_call']['wall_s']
    ceilings=[invocation,context['subnode_limits'],context['node_limits']]
    node, sub = snapshot["node_remaining"], snapshot["subnode_remaining"]
    reserves = [snapshot[k] for k in ("verifier_reserved", "routing_reserved", "other_work_reserved")]
    for dimension in ("time_s", "model_calls", "memory_mb"):
        values = [*[cap[dimension] for cap in ceilings], node[dimension], sub[dimension], *[r[dimension] for r in reserves]]
        if any(not finite(x) or x < 0 for x in values): raise NoRoute("BUDGET_UNVERIFIABLE")
    if not finite(declared_wall) or declared_wall<=0:raise NoRoute('BUDGET_UNVERIFIABLE')
    limits = {"time_s": min(*[cap['time_s'] for cap in ceilings],declared_wall,sub["time_s"],node["time_s"] - sum(r["time_s"] for r in reserves)),
              "model_calls": min(*[cap['model_calls'] for cap in ceilings],sub["model_calls"],node["model_calls"] - sum(r["model_calls"] for r in reserves)),
              "memory_mb": min(*[cap['memory_mb'] for cap in ceilings],sub["memory_mb"],node["memory_mb"])}
    if limits["time_s"] <= 0 or limits["model_calls"] < 1 or limits["memory_mb"] <= 0:
        raise NoRoute("BUDGET_EXCEEDED")
    if candidate.get("minimum_memory_mb", 0) > limits["memory_mb"]: raise NoRoute("ENVIRONMENT_BLOCKED")
    # These optional dimensions are never inferred from invocation counts or account credit.
    for dimension, value_key in (("tokens", "tokens_remaining"), ("cost", "cost_remaining")):
        if dimension in candidate.get("required_hard_limits", []):
            if not finite(snapshot.get(value_key)): raise NoRoute("BUDGET_UNVERIFIABLE")
            if dimension not in candidate.get("hard_limit_enforcement", []): raise NoRoute("LIMIT_UNSUPPORTED")
            if snapshot[value_key] <= 0: raise NoRoute("BUDGET_EXCEEDED")
    return limits


def _compatible(request, candidate, requirements):
    caps = candidate.get("capabilities", {})
    declaration = request["selected_capsule"]["declaration"]
    needs = declaration.get("needs", {}).get("model", {})
    if request["task_category"] not in candidate.get("categories", []): return "TASK_MISMATCH"
    if "model_allowlist" in requirements and candidate["model_id"] not in requirements["model_allowlist"]: return "MODEL_SCOPE_DENIED"
    if candidate["model_id"] in requirements.get("excludes", []) or candidate.get("family") in requirements.get("excludes", []): return "MODEL_SCOPE_DENIED"
    if "families" in requirements and candidate.get("family") not in requirements["families"]: return "MODEL_SCOPE_DENIED"
    # Request/profile requirements only narrow the selected Capsule's needs.
    # Declaration families is optional/mayempty; keep empty unrestricted.
    if candidate.get("family") in needs.get("excludes", []): return "MODEL_SCOPE_DENIED"
    if needs.get("families") and candidate.get("family") not in needs["families"]: return "MODEL_SCOPE_DENIED"
    modalities = set(needs.get("modalities", ["text"])) | set(requirements.get("modalities", []))
    if not modalities <= set(caps.get("modalities", [])): return "CAPABILITY_UNVERIFIED"
    if (needs.get("tool_calling") or requirements.get("tool_calling")) and caps.get("tool_calling") is not True: return "CAPABILITY_UNVERIFIED"
    if requirements.get("native_structured_output") and caps.get("native_structured_output") is not True: return "CAPABILITY_UNVERIFIED"
    if caps.get("context_tokens", 0) < max(needs.get("min_context", 0), requirements.get("min_context", 0), candidate.get("default_context_floor", 0)): return "CONTEXT_EXCEEDED"
    # A candidate may narrow a bound contract but cannot acquire new authority.
    allowed = request["selected_capsule"]["bound_context"].get("effective_authority", {})
    if not set(candidate.get("required_tools", [])) <= set(allowed.get("tools", [])): return "POLICY_DENIED"
    if not set(candidate.get("required_write_roots", [])) <= set(allowed.get("write_roots", [])): return "POLICY_DENIED"
    return None


def choose(request, candidates, profile, policy, aggregates, scope_key):
    if profile.get("policy_mode", "development_profile") != "development_profile": raise NoRoute("PROFILE_UNAVAILABLE")
    approved = set(profile.get("approved_model_ids", []))
    req = dict(request.get("requirements", {}))
    extra = profile.get("extra_requirements", {})
    # Two explicit allowlists are intersected, never replaced by the wider list.
    for key, value in extra.items():
        if key == "model_allowlist" and key in req: req[key] = sorted(set(req[key]) & set(value))
        elif key == "min_context": req[key] = max(req.get(key, 0), value)
        elif key in {"modalities", "excludes"}: req[key] = sorted(set(req.get(key, [])) | set(value))
        elif key == "families" and key in req: req[key] = sorted(set(req[key]) & set(value))
        elif isinstance(value, bool): req[key] = bool(req.get(key)) or value
        else: req[key] = value
    compatible, exclusions = [], []
    for candidate in candidates:
        reason = "MODEL_SCOPE_DENIED" if candidate["model_id"] not in approved else _compatible(request, candidate, req)
        if reason is None:
            try: budget_compatible(request, candidate)
            except NoRoute as exc: reason = exc.code
        if reason: exclusions.append({"model_id": candidate["model_id"], "reason_codes": [reason]})
        else: compatible.append(candidate)
    if not compatible: raise NoRoute("NO_COMPATIBLE_MODEL", exclusions)
    covered = []
    for candidate in compatible:
        matches = [a for a in aggregates if a.get("model_id") == candidate["model_id"]
                   and a.get("task_category") == request["task_category"]
                   and a.get("declaration_sha256") == request["selected_capsule"]["declaration_ref"]["sha256"]
                   and a.get("deployment_sha256") == candidate["deployment_ref"]["sha256"]
                   and a.get("scope_key") == scope_key and a.get("frozen") is True and a.get("oracle_eligible") is True]
        if len(matches) != 1:
            exclusions.append({"model_id": candidate["model_id"], "reason_codes": ["PROFILE_COVERAGE_MISSING"]}); continue
        observation = matches[0]
        required = ("quality", "uncertainty", "expected_complete_cost", "sample_count", "repeat_count")
        if any(not finite(observation.get(k)) for k in required) or "quality_floor" not in policy or "max_uncertainty" not in policy:
            exclusions.append({"model_id": candidate["model_id"], "reason_codes": ["PROFILE_COVERAGE_MISSING"]}); continue
        if observation["sample_count"] <= 0 or observation["repeat_count"] <= 0 or observation["expected_complete_cost"] < 0:
            exclusions.append({"model_id": candidate["model_id"], "reason_codes": ["PROFILE_COVERAGE_MISSING"]}); continue
        if observation["quality"] < policy["quality_floor"] or observation["uncertainty"] > policy["max_uncertainty"]:
            exclusions.append({"model_id": candidate["model_id"], "reason_codes": ["PROFILE_COVERAGE_MISSING"]}); continue
        if observation.get("currency") != policy.get("currency"):
            exclusions.append({"model_id": candidate["model_id"], "reason_codes": ["BUDGET_UNVERIFIABLE"]}); continue
        covered.append((candidate, observation))
    if not covered:
        baseline = next((x for x in compatible if x["model_id"] == policy.get("compatible_baseline_id")), None)
        if baseline: return baseline, compatible, exclusions, "compatible_baseline"
        raise NoRoute("PROFILE_COVERAGE_MISSING", exclusions)
    priorities = policy.get("priority", [])
    def key(pair):
        candidate, observation = pair
        latency = observation.get("expected_latency_s") if request.get("preferences", {}).get("speed") else 0
        if not finite(latency): latency = float("inf")
        priority = priorities.index(candidate["model_id"]) if candidate["model_id"] in priorities else len(priorities)
        return Decimal(str(observation["expected_complete_cost"])), latency, priority, candidate["model_id"]
    covered.sort(key=key)
    return covered[0][0], compatible, exclusions, "single_candidate" if len(compatible) == 1 else "development_profile_policy"

