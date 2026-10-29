"""Pinned bundle execution, once across the complete captured output set."""

from __future__ import annotations

import inspect
from dataclasses import dataclass,field
from typing import Any, Callable, Mapping

from ..contracts import Ref, ResearchError, validate


class CheckError(ResearchError):
    def __init__(self, check_id: str, detail: str):
        self.check_id = check_id
        super().__init__("check_failed", detail)


@dataclass(frozen=True)
class CheckContext:
    contract: Mapping
    store: Any
    inputs: Mapping
    outputs: Mapping
    output_refs: Mapping[str, Ref]
    observation: Mapping
    host_results: tuple[dict,...] = field(default_factory=tuple)

    def input_refs(self, port: str) -> tuple[Ref, ...]:
        matches = [p for p in self.contract.get("inputs", []) if p["name"] == port]
        if len(matches) != 1:
            raise ResearchError("input_binding", "Input port is absent or ambiguous")
        return tuple(matches[0]["artifact_refs"])

    def input_ref(self, port: str) -> Ref:
        refs = self.input_refs(port)
        if len(refs) != 1:
            raise ResearchError("input_binding", "Input requires exactly one artifact")
        return refs[0]

    def read_blob(self, ref: Ref) -> bytes:
        return self.store.read_blob(ref)

    def read_json(self, ref: Ref) -> dict:
        return self.store.read_record(ref)


class CheckRegistry:
    def __init__(self):
        self._bundles: dict[str, dict] = {}

    def register_bundle(self, bundle_id: str, check_ids, handler: Callable, *,
                        implementation_ref: Ref, profile_ref: Ref) -> None:
        ids = tuple(check_ids)
        validate("Ref", profile_ref)
        existing = [value for value in self._bundles.values() if value['bundle_id'] == bundle_id]
        if (not ids or len(ids) != len(set(ids))
                or any(value['profile_ref'] == dict(profile_ref) for value in existing)):
            raise ResearchError("check_registration", "Bundle and check identities must be unique")
        validate("Ref", implementation_ref)
        key = bundle_id if not existing else bundle_id + '#' + profile_ref['sha256']
        self._bundles[key] = {"bundle_id": bundle_id, "ids": ids, "handler": handler,
                                   "implementation_ref": dict(implementation_ref), "profile_ref": dict(profile_ref)}

    def contains(self, check_id: str) -> bool:
        return any(check_id in value["ids"] for value in self._bundles.values())

    async def run(self, bound_plan: Mapping, ctx: CheckContext, *, bundle_id: str) -> list[dict]:
        matches = [value for value in self._bundles.values()
                   if value['bundle_id'] == bundle_id and value['profile_ref'] == bound_plan['profile_ref']]
        bundle = matches[0] if len(matches) == 1 else None
        if (not bundle or bundle["implementation_ref"] not in bound_plan["runner_refs"]):
            raise ResearchError("check_pin_mismatch", "No exact registered implementation/profile for this bound bundle")
        ctx.read_blob(bundle["implementation_ref"])
        mandatory = tuple(bound_plan["mandatory_deterministic"])
        expected = tuple(dict.fromkeys([*bundle['ids'],*mandatory]))
        if len(mandatory) != len(set(mandatory)):
            raise ResearchError("check_plan_invalid", "Mandatory coverage differs from the registered bundle")
        try:
            values = bundle["handler"](ctx, ctx.inputs, ctx.outputs)
            if inspect.isawaitable(values):
                values = await values
            values = [*values,*ctx.host_results]
        except CheckError as exc:
            values = [{"check_id": exc.check_id, "outcome": "FAIL", "reason": exc.message, "evidence_refs": []}]
        except (OSError, TimeoutError) as exc:
            values = [{"check_id": key, "outcome": "ENVIRONMENT_BLOCKED", "reason": type(exc).__name__, "evidence_refs": []} for key in expected]
        counts = {key: sum(v.get("check_id") == key for v in values if isinstance(v, dict)) for key in expected}
        unknown = any(not isinstance(v, dict) or v.get("check_id") not in expected for v in values)
        results = []
        for check_id in expected:
            matches = [v for v in values if isinstance(v, dict) and v.get("check_id") == check_id]
            value = matches[0] if counts[check_id] == 1 else None
            if unknown or value is None or set(value) != {"check_id", "outcome", "reason", "evidence_refs"} or value.get("outcome") not in {"PASS", "FAIL", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE"} or not isinstance(value.get("reason"), str) or not value["reason"]:
                value = {"check_id": check_id, "outcome": "FAIL", "reason": "Missing, duplicate, unknown or malformed check result", "evidence_refs": []}
            for ref in value["evidence_refs"]:
                ctx.read_blob(ref)
            results.append(value)
        return results
