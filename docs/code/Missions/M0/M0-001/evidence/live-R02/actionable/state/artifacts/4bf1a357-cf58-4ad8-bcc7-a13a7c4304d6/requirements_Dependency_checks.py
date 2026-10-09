"""Protected mechanical validation for M0-IF-001/002/003@r1.

These checks establish shape and exact relationships. Meaning, source support and
purpose remain independently assigned semantic-review obligations. A valid
assessment is data; only the runtime's durable gate can grant acceptance.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

CONTRACTS = Path(__file__).with_name("contracts")
ADVANCING = {"PASS", "PASS_WITH_KNOWN_LIMITATIONS"}
EXT_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _finite_errors(value: Any) -> list[str]:
    return ["JSON numeric value must be finite"] if any(
        isinstance(x, float) and not math.isfinite(x) for x in _walk(value)
    ) else []


@lru_cache(maxsize=1)
def _schemas():
    docs = [json.loads(p.read_bytes()) for p in sorted(CONTRACTS.glob("*.schema.json"))]
    registry = Registry().with_resources(
        (doc["$id"], Resource.from_contents(doc)) for doc in docs
    )
    validators = {}
    for doc in docs:
        Draft202012Validator.check_schema(doc)
        validator = Draft202012Validator(doc, registry=registry, format_checker=FormatChecker())
        validators[doc["$id"]] = validator
        validators[doc["$id"].split(":")[-2]] = validator
    return validators


def validate_schema(name: str, payload: Any) -> list[str]:
    """Validate a supplied critical schema offline, by short name or schema URN."""
    validator = _schemas().get(name)
    if validator is None:
        return [f"Unknown critical schema: {name}"]
    errors = _finite_errors(payload)
    for error in sorted(validator.iter_errors(payload), key=lambda e: str(list(e.path))):
        location = "/" + "/".join(str(x) for x in error.path)
        errors.append(f"{location}: {error.message}")
    return errors


schema_errors = validate_schema


@lru_cache(maxsize=1)
def _field_catalog():
    value = json.loads((CONTRACTS / "field-contracts.json").read_bytes())
    return value["types"], {x["name"]: x for x in value["interfaces"]}


def validate_field_contract(name: str, payload: Any) -> list[str]:
    """Validate required public fields without inventing another schema library."""
    types, interfaces = _field_catalog()
    item = interfaces.get(name) or next((i for i in interfaces.values() if i["id"] == name), None)
    if item is None:
        return [f"Unknown field contract: {name}"]

    def fields(value, expected, path):
        if not isinstance(value, dict):
            return [f"{path}: expected object"]
        errors = [f"{path}: unknown core field {key}" for key in value.keys() - expected.keys() - {"ext"}]
        for key, info in expected.items():
            if key not in value:
                if info["required"]:
                    errors.append(f"{path}: missing {key}")
                continue
            errors.extend(typed(value[key], info["type"], f"{path}/{key}"))
        if "ext" in value and (not isinstance(value["ext"], dict) or any(
            not isinstance(k, str) or not EXT_NAME.fullmatch(k) for k in value["ext"]
        )):
            errors.append(f"{path}: invalid namespaced extension")
        return errors

    def typed(value, kind, path):
        if kind.startswith("nullable-"):
            return [] if value is None else typed(value, kind[9:], path)
        if kind.endswith("[]"):
            return [f"{path}: expected array"] if not isinstance(value, list) else [
                e for idx, x in enumerate(value) for e in typed(x, kind[:-2], f"{path}/{idx}")
            ]
        if kind in types:
            return fields(value, types[kind]["fields"], path)
        valid = {
            "string": isinstance(value, str) and bool(value),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
            "boolean": isinstance(value, bool),
            "sha256": isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value)),
        }
        return [] if valid.get(kind, False) else [f"{path}: invalid {kind}"]

    errors = fields(payload, item["fields"], "") + _finite_errors(payload)
    version = item["fields"].get("schema_version", {}).get("meaning", "")
    match = re.search(r"\d+\.\d+\.\d+", version)
    if isinstance(payload, dict) and match and payload.get("schema_version") != match.group():
        errors.append("/schema_version: incompatible field-contract version")
    return errors


def _key(ref):
    return (ref.get("id"), ref.get("sha256")) if isinstance(ref, dict) else (None, None)


def _registry(sources):
    """Accept captured text+refs, trusted refs, or exact UTF-8 text inputs."""
    refs, texts = [], {}
    for identity, value in sources.items():
        if isinstance(value, str):
            texts[identity] = value
            refs.append({"id": identity, "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()})
        elif isinstance(value, dict):
            if "text" in value:
                texts[identity] = value["text"]
            ref = value.get("ref", value if set(value) == {"id", "sha256"} else None)
            if ref is not None:
                refs.append(ref)
    return refs, texts


def _unique_ids(rows):
    ids = [row["id"] for row in rows]
    return [f"Duplicate local ID: {identity}" for identity, count in Counter(ids).items() if count > 1]


def _unique_refs(refs, label):
    keys = [_key(ref) for ref in refs]
    return [f"{label}: duplicate reference"] if len(keys) != len(set(keys)) else []


def check_intent(payload, sources, request_ref, context_refs) -> list[str]:
    errors = validate_schema("intent-ir", payload)
    if errors:
        return errors
    source_refs, texts = _registry(sources)
    allowed = {_key(ref) for ref in [request_ref, *context_refs]}
    if payload["request_ref"] != request_ref:
        errors.append("Intent request_ref differs from protected original request")
    if request_ref["id"] not in texts:
        errors.append("Original request text is unavailable")
    if any(_key(ref) not in allowed for ref in payload["context_refs"]):
        errors.append("Intent context_refs includes an unqualified or stale reference")
    errors.extend(_unique_refs(payload["context_refs"], "Intent context_refs"))
    # A bare string is captured UTF-8 text; explicit refs support PDF extraction/BOM originals.
    supplied = {_key(ref) for ref in source_refs}
    if any(_key(ref) not in supplied for ref in [request_ref, *payload["context_refs"]]):
        errors.append("Intent source text/reference identity differs from captured input")
    rows = [x for x in payload["interpretation"].values() if x is not None]
    for name in ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets", "uncertainties"):
        rows.extend(payload[name])
    errors.extend(_unique_ids(rows))
    for row in rows:
        for span in row.get("source_spans", []):
            ref = span["source_ref"]
            text = texts.get(ref["id"])
            if _key(ref) not in allowed or _key(ref) not in supplied:
                errors.append(f"{row['id']}: source span uses an unqualified or stale reference")
            if not isinstance(text, str) or not 0 <= span["start"] < span["end"] <= len(text):
                errors.append(f"{row['id']}: source span must be nonempty and within exact Unicode text")
    # needs_clarification, topic-only and explicit conflict are valid candidate representations.
    return errors


def _pointer(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("expected a nonempty JSON pointer")
    owner = None
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise ValueError("invalid JSON pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            if value.get("origin") == "system_default":
                owner = value
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
            value = value[int(token)]
        else:
            raise ValueError("invalid JSON pointer traversal")
    if isinstance(value, dict) and value.get("origin") == "system_default":
        owner = value
    return value, owner


def check_brief(payload, intake_ref, intent_ref, sources, resource_refs, policy_ref, policy) -> list[str]:
    errors = validate_schema("research-brief", payload)
    if errors:
        return errors
    source_refs, _ = _registry(sources)
    allowed = {_key(ref) for ref in [intake_ref, intent_ref, policy_ref, *source_refs, *resource_refs]}
    if payload["intake_ref"] != intake_ref or payload["intent_ref"] != intent_ref:
        errors.append("Brief intake/accepted Intent identity mismatch")
    for value in _walk(payload):
        if isinstance(value, dict) and set(value) == {"id", "sha256"} and _key(value) not in allowed:
            errors.append(f"Brief contains unqualified or stale reference: {value['id']}")
    if any(_key(ref) not in {_key(r) for r in source_refs} for ref in payload["context_refs"]):
        errors.append("Brief context_refs is not qualified source context")
    errors.extend(_unique_refs(payload["context_refs"], "Brief context_refs"))
    rows = [payload["objective"]]
    for name in ("in_scope", "out_of_scope", "mandatory_requirements", "optional_preferences", "constraints",
                 "target_metrics", "deliverables", "acceptance_expectations", "evidence_obligations",
                 "assumptions", "unresolved_items", "input_bindings"):
        rows.extend(payload[name])
    errors.extend(_unique_ids(rows))
    mandatory = {row["id"] for row in payload["mandatory_requirements"]}
    requirements = mandatory | {row["id"] for row in payload["optional_preferences"]}
    for kind in ("acceptance_expectations", "evidence_obligations", "target_metrics"):
        covered = set()
        for row in payload[kind]:
            links = row["requirement_ids"]
            if not set(links) <= requirements or len(links) != len(set(links)):
                errors.append(f"{row['id']}: unknown or duplicate requirement link")
            covered.update(links)
        if kind != "target_metrics" and not mandatory <= covered:
            errors.append(f"{kind}: missing coverage for mandatory requirements")
    expected = Counter(_key(ref) for ref in resource_refs)
    if Counter(_key(ref) for ref in payload["resource_refs"]) != expected or Counter(
        _key(row["resource_ref"]) for row in payload["input_bindings"]
    ) != expected:
        errors.append("Brief supplied resource/input-binding inventory differs from qualified intake")
    errors.extend(_unique_refs(payload["resource_refs"], "Brief resources"))
    if any(row["blocking"] for row in payload["unresolved_items"]):
        errors.append("Brief has blocking unresolved items")
    defaults = [row for row in rows if row.get("origin") == "system_default"]
    for row in defaults:
        if row not in payload["constraints"] or not (
            row["category"] == "hardware" and row["scope"] == "scientific_execution"
            and row["operator"] == "eq" and row["unit"] is None
            and row["normalized_value"] == policy.get("hardware_profile") == "single_gpu"
            and policy_ref in row["source_refs"]
        ):
            errors.append(f"{row['id']}: unsupported system default")
    accounted = set()
    for assumption in payload["assumptions"]:
        if assumption["authority_ref"] != policy_ref:
            errors.append(f"{assumption['id']}: unsupported default authority")
        for pointer in assumption["affected_fields"]:
            try:
                _, owner = _pointer(payload, pointer)
            except (KeyError, IndexError, ValueError, TypeError):
                errors.append(f"{assumption['id']}: nonexistent affected field {pointer}")
                continue
            if owner not in defaults or owner is None or policy_ref not in owner["source_refs"]:
                errors.append(f"{assumption['id']}: affected field is not an attributed system default")
            else:
                accounted.add(owner["id"])
    if {row["id"] for row in defaults} != accounted:
        errors.append("Every applied system default requires an assumption pointing to its actual field")
    if payload["assumptions"] or defaults:
        if payload["confirmation"]["basis"] != "authorized_assumptions" or policy_ref not in payload["confirmation"]["source_refs"]:
            errors.append("Applied defaults require authorized-assumptions confirmation with protected policy")
    return errors


def check_assessment(payload, subject_ref, review_context_ref, criteria, allowed_evidence) -> list[str]:
    errors = validate_schema("verifier-assessment", payload)
    if errors:
        return errors
    if payload["subject_ref"] != subject_ref or payload["review_context_ref"] != review_context_ref:
        errors.append("Assessment subject/review context identity mismatch")
    if len(criteria) != len(set(criteria)) or not criteria:
        errors.append("Protected semantic assignment must contain unique criteria")
    if Counter(row["criterion_id"] for row in payload["findings"]) != Counter(criteria):
        errors.append("Assessment must cover each assigned criterion exactly once")
    allowed = {_key(ref) for ref in allowed_evidence}
    if any(_key(ref) not in allowed for row in payload["findings"] for ref in row["evidence_refs"]):
        errors.append("Assessment finding uses unavailable, stale or unauthorized evidence")
    if payload["verdict"] in ADVANCING and (
        any(row["outcome"] != "PASS" for row in payload["findings"]) or payload["uncertainties"]
        or payload["required_correction"] is not None
    ):
        errors.append("Advancing assessment contradicts mandatory findings, uncertainty or correction")
    return errors


def check_gate(payload) -> list[str]:
    """Local gate invariants; runtime separately checks references and durable commit."""
    errors = validate_schema("gate-decision", payload)
    if errors:
        return errors
    for name in ("input_refs", "output_refs", "invocation_refs", "internal_decision_refs", "accepted_refs"):
        errors.extend(_unique_refs(payload[name], f"Gate {name}"))
    if payload["scope_kind"] == "node":
        if payload["contract_ref"] != payload["node_contract_ref"]:
            errors.append("Node gate must bind the enclosing node contract")
        if payload["action"] == "advance" and len(payload["internal_decision_refs"]) != 2:
            errors.append("Compiler node release requires both work-subnode decisions")
        if payload["action"] == "advance" and payload["accepted_refs"] != payload["output_refs"]:
            errors.append("Node gate must release its exact external output inventory")
    elif payload["internal_decision_refs"]:
        errors.append("Work-subnode gate cannot substitute aggregate internal decisions")
    if payload["action"] == "advance" and any(ref not in payload["output_refs"] for ref in payload["accepted_refs"]):
        errors.append("Gate cannot accept unreviewed output references")
    return errors
