"""Frozen profile interpretation, without online learning or model selection calls."""
from .policy import NoRoute


def validate_profile(profile):
    mode = profile.get("policy_mode")
    if mode not in {"development_profile", "fixed_baseline"}:
        raise NoRoute("PROFILE_UNAVAILABLE")
    allowance = profile.get("selection_allowance", {})
    if allowance.get("enabled") or allowance.get("model_calls", 0) != 0:
        raise NoRoute("PROFILE_UNAVAILABLE")
    return profile

