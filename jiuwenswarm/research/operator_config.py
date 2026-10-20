"""Immutable, closed operator-config 1.0.0 (M1-IF-001@r1).

Preferences and credentials have different owners. This module never reads
environment overrides, writes the operator file, or resolves a newest version.
"""
from __future__ import annotations

import base64
import copy
import math
import re
from collections.abc import Callable, Mapping
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """Stable public reason; rejected configuration values are never echoed."""


def _require(condition: bool, code: str = "CONFIG_INVALID") -> None:
    if not condition:
        raise ConfigError(code)


def _keys(value, required: set[str]) -> None:
    _require(isinstance(value, dict) and set(value) == required, "CONFIG_KEYS_INVALID")


def _ref(value, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    _keys(value, {"id", "sha256"})
    _require(isinstance(value["id"], str) and bool(value["id"]))
    _require(isinstance(value["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]) is not None)


class _UniqueSafeLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ConfigError("CONFIG_DUPLICATE_OR_INVALID_KEY")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class OperatorConfiguration:
    """Captured once at startup; callers receive detached run snapshots."""

    def __init__(self, data: dict):
        self.__data = copy.deepcopy(data)

    @classmethod
    def from_mapping(cls, data: Mapping, *, resolve_profile: Callable | None = None):
        """Validate settings, resolving profiles through protected custody only.

        The resolver must verify original-byte Ref identity and the approved
        evaluation-profile contract. No user-supplied resolver is exposed by
        the control API. The binder separately resolves admitted plan pins.
        """
        _keys(data, {"schema_version", "cc", "rsi", "codex", "role_aliases"})
        _require(data["schema_version"] == "1.0.0", "CONFIG_VERSION_INVALID")
        cc, rsi, codex = data["cc"], data["rsi"], data["codex"]
        _keys(cc, {"plan_source", "plan_policy_ref", "static_template_ref", "evaluation_profile_ref", "router"})
        _require(cc["plan_source"] in ("static", "planned"))
        _ref(cc["plan_policy_ref"])
        _ref(cc["static_template_ref"])
        _ref(cc["evaluation_profile_ref"], nullable=True)
        router = cc["router"]
        _keys(router, {"enabled", "deadline_s", "profile_ref"})
        _require(type(router["enabled"]) is bool)
        deadline = router["deadline_s"]
        _require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline == 30)
        _ref(router["profile_ref"], nullable=True)
        _require(router["enabled"] or router["profile_ref"] is None, "ROUTER_OFF_PROFILE_NOT_NULL")
        _keys(codex, {"route_id"})
        route = codex["route_id"]
        _require(isinstance(route, str) and re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", route) is not None)
        aliases = data["role_aliases"]
        _require(isinstance(aliases, dict) and all(isinstance(k, str) and k and v == route for k, v in aliases.items()), "ROLE_ALIAS_INVALID")
        _keys(rsi, {"custodian_key_id", "custodian_public_key"})
        key_id, public = rsi["custodian_key_id"], rsi["custodian_public_key"]
        _require((key_id is None) == (public is None), "CUSTODIAN_KEY_PAIR_INVALID")
        if key_id is not None:
            _require(isinstance(key_id, str) and re.fullmatch(r"[a-z][a-z0-9_.:-]{0,63}", key_id) is not None, "CUSTODIAN_KEY_INVALID")
            _require(isinstance(public, str) and re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", public) is not None, "CUSTODIAN_KEY_INVALID")
            try:
                key_bytes = base64.b64decode(public + "=" * (-len(public) % 4), altchars=b"-_", validate=True)
            except (ValueError, TypeError):
                raise ConfigError("CUSTODIAN_KEY_INVALID") from None
            _require(len(key_bytes) == 32, "CUSTODIAN_KEY_INVALID")
        profile_ref = cc["evaluation_profile_ref"]
        if profile_ref is None:
            _require(not router["enabled"], "EVALUATION_PROFILE_REQUIRED")
        else:
            _require(resolve_profile is not None, "EVALUATION_PROFILE_UNAVAILABLE")
            try:
                profile = resolve_profile(copy.deepcopy(profile_ref))
            except Exception:
                raise ConfigError("EVALUATION_PROFILE_UNAVAILABLE") from None
            _require(isinstance(profile, Mapping) and type(profile.get("router_enabled")) is bool, "EVALUATION_PROFILE_INVALID")
            _require(profile["router_enabled"] == router["enabled"], "PROFILE_SWITCH_MISMATCH")
        return cls(data)

    @classmethod
    def load(cls, path: Path | str, *, resolve_profile: Callable | None = None):
        try:
            raw = Path(path).read_bytes()
        except OSError:
            raise ConfigError("CONFIG_UNAVAILABLE") from None
        # Configuration is small protected input, with a fixed parser ceiling
        # rather than a new operator-config field. Reject before parsing.
        _require(len(raw) <= 1024 * 1024, "CONFIG_TOO_LARGE")
        try:
            data = yaml.load(raw.decode("utf-8", errors="strict"), Loader=_UniqueSafeLoader)
        except (ValueError, yaml.YAMLError, RecursionError):
            raise ConfigError("CONFIG_INVALID") from None
        return cls.from_mapping(data, resolve_profile=resolve_profile)

    def snapshot(self) -> dict:
        return copy.deepcopy(self.__data)

    @property
    def codex_route_id(self) -> str:
        return self.__data["codex"]["route_id"]
