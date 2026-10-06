"""Strict immutable configuration for M0-IF-002@r2's two-role trial."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import math
import re
from types import MappingProxyType
from typing import Any

from .common import GovernanceError, canonical_json, hash_json


MAX_TIMEOUT_SECONDS = 3600
OPTION_KEYS = frozenset({"mode", "timeout_seconds", "max_calls", "seed", "profile_id"})
BASELINE_KEYS = OPTION_KEYS | {"provider", "model_ids", "model_roles", "pins", "verification_profile", "runtime_identity"}
LAYERS = ("account", "machine", "project")
ROLES = frozenset({"compiler", "verifier"})
HASH = re.compile(r"[0-9a-f]{64}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
SECRET_KEY = re.compile(r"token|password|secret|credential|api[_-]?key", re.I)


def _copy_json(value: Any) -> Any:
    try:
        raw = canonical_json(value)
        if len(raw) > 65536:
            raise ValueError()
        return json.loads(raw)
    except (TypeError, ValueError, OverflowError):
        raise GovernanceError("invalid_input", "Configuration must be bounded finite JSON.") from None


def _reject_secrets(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY.search(key):
                raise GovernanceError("policy_denied", "Credential-bearing configuration is not permitted.")
            _reject_secrets(child)
    elif isinstance(value, list):
        for child in value:
            _reject_secrets(child)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def validate_trial_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate options without supplying defaults or admitting a model route."""
    if options is None:
        return {}
    if not isinstance(options, Mapping) or any(not isinstance(key, str) for key in options):
        raise GovernanceError("invalid_input", "Trial options must be a string-keyed object.")
    if set(options) - OPTION_KEYS:
        raise GovernanceError("invalid_input", "Unsupported trial option.")
    result = _copy_json(dict(options))
    if "mode" in result and (not isinstance(result["mode"], str) or result["mode"] not in {"web", "headless"}):
        raise GovernanceError("invalid_input", "Trial mode must be web or headless.")
    if "timeout_seconds" in result:
        duration = result["timeout_seconds"]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 < duration <= MAX_TIMEOUT_SECONDS:
            raise GovernanceError("invalid_input", "Trial timeout must be positive, finite and bounded.")
        result["timeout_seconds"] = float(duration)
    if "max_calls" in result and (type(result["max_calls"]) is not int or not 1 <= result["max_calls"] <= 2):
        raise GovernanceError("invalid_input", "Trial total call ceiling must be one or two.")
    if "seed" in result and result["seed"] is not None and (type(result["seed"]) is not int or not 0 <= result["seed"] < 2**63):
        raise GovernanceError("invalid_input", "Requested seed must be a nonnegative bounded integer or null.")
    if "profile_id" in result and (not isinstance(result["profile_id"], str) or not SAFE_ID.fullmatch(result["profile_id"])):
        raise GovernanceError("invalid_input", "Profile identity is malformed.")
    return result


def _reference(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise GovernanceError("invalid_input", f"Protected {label} reference must be an object.")
    result = _copy_json(dict(value))
    _reject_secrets(result)
    if not isinstance(result.get("sha256"), str) or not HASH.fullmatch(result["sha256"]):
        raise GovernanceError("invalid_input", f"Protected {label} reference requires exact SHA256.")
    for key in ("decl_hash", "implementation_hash", "closure_hash", "contract_hash", "dependency_sha256"):
        if key in result and (not isinstance(result[key], str) or not HASH.fullmatch(result[key])):
            raise GovernanceError("invalid_input", f"Protected {label} hash metadata is malformed.")
    if "decl_hash" in result and result["decl_hash"] != result["sha256"]:
        raise GovernanceError("invalid_input", f"Protected {label} declaration identities disagree.")
    if "closure_hash" in result and "implementation_hash" in result and result["closure_hash"] != result["implementation_hash"]:
        raise GovernanceError("invalid_input", f"Protected {label} closure identities disagree.")
    if label in ROLES and "role" in result and (not isinstance(result["role"], str) or result["role"] not in {label, "intent_" + label}):
        raise GovernanceError("invalid_input", "Protected role assignment is swapped or malformed.")
    return result


@dataclass(frozen=True, slots=True)
class FrozenTrialProfile(Mapping[str, Any]):
    """A detached immutable snapshot; callers receive copies for persistence."""

    _value: Mapping[str, Any] = field(repr=False)
    fingerprint: str

    def __getitem__(self, key: str) -> Any:
        return self._value["effective"][key]

    def __iter__(self):
        return iter(self._value["effective"])

    def __len__(self) -> int:
        return len(self._value["effective"])

    def to_dict(self) -> dict[str, Any]:
        result = _thaw(self._value)
        result["fingerprint"] = self.fingerprint
        return result


def resolve_configuration(requested: Mapping[str, Any] | None, defaults: Mapping[str, Any] | None, baseline: Mapping[str, Any]) -> FrozenTrialProfile:
    """Resolve account, machine, project, then permitted request options.

    Model discovery, the static role assignments and pinned references are
    host inputs. This resolver never probes a provider or certifies readiness.
    """
    if not isinstance(baseline, Mapping) or set(baseline) - BASELINE_KEYS:
        raise GovernanceError("invalid_input", "Malformed or unsupported trial baseline.")
    base = _copy_json(dict(baseline))
    _reject_secrets(base)
    if not isinstance(base.get("provider"), str) or base["provider"] not in {"codex_subscription", "mock"}:
        raise GovernanceError("policy_denied", "Only the static Codex baseline or labeled mock is supported.")
    runtime_identity = base.get("runtime_identity")
    if runtime_identity is not None:
        if not isinstance(runtime_identity, dict) or set(runtime_identity) != {"account_fingerprint", "account_epoch", "runtime_version"}:
            raise GovernanceError("invalid_input", "Malformed runtime account generation.")
        if not isinstance(runtime_identity["account_fingerprint"], str) or not HASH.fullmatch(runtime_identity["account_fingerprint"]) or any(not isinstance(runtime_identity[key], str) or not runtime_identity[key].strip() for key in ("account_epoch", "runtime_version")):
            raise GovernanceError("invalid_input", "Runtime account generation must be an observed protected identity.")
    model_ids = base.get("model_ids")
    if not isinstance(model_ids, list) or not model_ids or any(not isinstance(value, str) or not value.strip() or len(value) > 256 for value in model_ids) or len(model_ids) != len(set(model_ids)):
        raise GovernanceError("environment_unavailable", "Authenticated model discovery is unavailable or malformed.")
    roles = base.get("model_roles")
    if not isinstance(roles, dict) or set(roles) != ROLES or any(not isinstance(model, str) or model not in model_ids for model in roles.values()):
        raise GovernanceError("environment_unavailable", "Static role selections must be resolved from discovered models.")
    pins = base.get("pins")
    if not isinstance(pins, dict) or set(pins) != ROLES:
        raise GovernanceError("invalid_input", "Exactly compiler and verifier pins are required.")
    pins = {role: _reference(pin, role) for role, pin in pins.items()}
    if pins["compiler"]["sha256"] == pins["verifier"]["sha256"]:
        raise GovernanceError("invalid_input", "Compiler and verifier require distinct implementation pins.")
    profile = _reference(base.get("verification_profile"), "verification profile")
    if not isinstance(profile.get("profile_id"), str) or not SAFE_ID.fullmatch(profile["profile_id"]) or profile.get("interface_revision") != "M0-IF-007@r2":
        raise GovernanceError("invalid_input", "Protected verification profile identity/revision is malformed.")
    selected_id = base.get("profile_id", profile["profile_id"])
    base_options = validate_trial_options({key: value for key, value in base.items() if key in OPTION_KEYS})
    values = {"mode": "headless", "timeout_seconds": 180.0, "max_calls": 2, "seed": None, "profile_id": selected_id}
    values.update(base_options)
    provenance = {key: "baseline" for key in values}
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, Mapping):
        raise GovernanceError("invalid_input", "Defaults must be a configuration object.")
    if any(key in LAYERS for key in defaults):
        if set(defaults) - set(LAYERS):
            raise GovernanceError("invalid_input", "Configuration layers cannot mix with unscoped options.")
        layers = {name: validate_trial_options(defaults.get(name)) for name in LAYERS}
    else:
        layers = {"account": validate_trial_options(defaults), "machine": {}, "project": {}}
    explicit = validate_trial_options(requested)
    for name, options in (*layers.items(), ("requested", explicit)):
        values.update(options)
        provenance.update({key: name for key in options})
    values = validate_trial_options(values)
    if values["profile_id"] != selected_id:
        raise GovernanceError("policy_denied", "Clients cannot replace the approved trial profile.")
    desired_seed = values["seed"]
    effective = {**values, "seed": None, "requested_seed": desired_seed, "effective_seed": None,
                 "seed_support": "unavailable", "seed_unavailable_reason": "The trial bridge does not expose effective seed control.",
                 "provider": base["provider"], "model_roles": roles, "pins": pins, "verification_profile": profile,
                 "runtime_identity": runtime_identity,
                 "per_role_max_calls": {role: 1 for role in sorted(ROLES)},
                 "per_role_timeout_seconds": {role: values["timeout_seconds"] for role in sorted(ROLES)},
                 "total_timeout_seconds": 2 * values["timeout_seconds"], "automatic_retries": 0,
                 "mock": base["provider"] == "mock", "requires_real_model_evidence": base["provider"] != "mock",
                 "token_usage": {"available": False, "reason": "Per-call usage is supplied only by actual runner observations."},
                 "cost_usage": {"available": False, "reason": "Account allowance is not per-call consumption."}}
    snapshot = {"interface_revision": "M0-IF-002@r2", "requested": explicit, "defaults": layers,
                "precedence": ["baseline", *LAYERS, "requested"], "provenance": provenance,
                "model_discovery": list(model_ids), "effective": effective}
    return FrozenTrialProfile(_freeze(snapshot), hash_json(snapshot))
