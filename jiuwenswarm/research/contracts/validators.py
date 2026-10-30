"""Offline JSON validation from neutral package data, with no network resolution."""

from __future__ import annotations

import copy
import json
import math
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .types import ResearchError


class ContractError(ResearchError):
    pass


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return value is None or isinstance(value, (str, int, bool))


def _field_schema(field: Mapping[str, Any], types: Mapping[str, Any]) -> dict:
    expression = field.get("type", "object")
    if expression.startswith("nullable-"):
        result = {"anyOf": [{"type": "null"}, _field_schema({"type": expression[9:]}, types)]}
    elif expression.endswith("[]"):
        result = {"type": "array", "items": _field_schema({"type": expression[:-2]}, types)}
    elif expression in {"string", "markdown"}:
        result = {"type": "string"}
    elif expression == "sha256":
        result = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    elif expression in {"integer", "number", "boolean", "object"}:
        result = {"type": expression}
    elif expression in types:
        result = {"$ref": "#/$defs/" + expression}
    else:
        raise ContractError("unknown_type", f"Unimplemented source type {expression!r}")
    for source, target in (("enum", "enum"), ("pattern", "pattern"),
                           ("min_items", "minItems"), ("max_items", "maxItems")):
        if source in field:
            destination = result["items"] if expression.endswith("[]") and source in {"enum", "pattern"} else result
            if expression.startswith("nullable-") and source in {"enum", "pattern"}:
                destination = result["anyOf"][1]
            destination[target] = field[source]
    base = expression.removeprefix("nullable-")
    for source, number, string in (("min", "minimum", "minLength"),
                                    ("max", "maximum", "maxLength")):
        if source in field:
            result[string if base in {"string", "markdown"} else number] = field[source]
    return result


def _object_schema(fields: Mapping[str, Any], types: Mapping[str, Any]) -> dict:
    properties = {k: _field_schema(v, types) for k, v in fields.items()}
    version = re.search(r"(?:[Ff]ormat version|exactly)\s+`?([0-9]+\.[0-9]+\.[0-9]+)",
                        fields.get("schema_version", {}).get("meaning", ""))
    if version:
        properties["schema_version"] = {"const": version.group(1)}
    return {"type": "object", "properties": properties,
            "required": [k for k, v in fields.items() if v.get("required") is True],
            "additionalProperties": False}


@lru_cache(maxsize=1)
def _contracts() -> tuple[dict[str, dict], Registry]:
    root = files("jiuwenswarm.research_contracts")
    catalog = json.loads(root.joinpath("catalog.json").read_text("utf-8"))
    fields = json.loads(root.joinpath("field-contracts.json").read_text("utf-8"))
    types = dict(fields["types"])
    # Some tables refer to the PascalCase form of another interface by name.
    for entry in fields["interfaces"]:
        alias = "".join(part[:1].upper() + part[1:] for part in entry["name"].split("-"))
        types.setdefault(alias, {"fields": entry["fields"]})
    definitions = {name: _object_schema(value["fields"], types) for name, value in types.items()}
    schemas: dict[str, dict] = {}
    for name in types:
        schemas[name] = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                         "$ref": "#/$defs/" + name, "$defs": definitions}
    for contract in fields["interfaces"]:
        schema = _object_schema(contract["fields"], types)
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$defs"] = definitions
        if "schema_version" in schema["properties"]:
            schema["properties"]["schema_version"] = {"const": contract["version"]}
        schemas[contract["name"]] = schema
        schemas[contract["id"]] = schema
    resources: dict[str, Resource] = {}
    schema_root = root.joinpath("schemas")
    for entry in schema_root.iterdir():
        if entry.name.endswith(".json"):
            schema = json.loads(entry.read_text("utf-8"))
            if "$id" in schema:
                resources[schema["$id"]] = Resource.from_contents(schema)
                schemas[schema["$id"]] = schema
    for entry in catalog["contracts"]:
        identity = entry.get("schema_id")
        if identity and identity in schemas:
            schemas[entry["name"]] = schemas[identity]
    empirical_v2 = schemas.get("urn:jiuwenswarm:m1-design:empirical-results:2.0.0")
    if empirical_v2:
        schemas["empirical-results"] = empirical_v2
        schemas["empirical-results:field-contract:2"] = empirical_v2
    # Native versioned amendments are neutral package data with one TASK owner.
    lookup = json.loads(root.joinpath("contract_lookup.json").read_text("utf-8"))["contracts"]
    for name in ("rsi-attempt", "rsi-loop-feedback", "rsi-referee-evidence", "rsi-session-result"):
        for alias in (name, name + ":field-contract:2"):
            entry = lookup[alias]
            document = schemas[entry["schema_id"]]
            schemas[alias] = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                              "$ref": "#/$defs/" + entry["definition"], "$defs": document["$defs"]}
    # M1-I001 prose retains no_route/router_halt_code absent from the older field mirror.
    route = schemas.get("route-record")
    if route:
        halts = ["PROFILE_UNAVAILABLE", "NO_COMPATIBLE_MODEL", "MODEL_ACCESS_UNAVAILABLE", "TASK_MISMATCH",
                 "MODEL_SCOPE_DENIED", "CAPABILITY_UNVERIFIED", "CONTEXT_EXCEEDED", "POLICY_DENIED",
                 "ENVIRONMENT_BLOCKED", "BUDGET_EXCEEDED", "BUDGET_UNVERIFIABLE", "LIMIT_UNSUPPORTED",
                 "DEPLOYMENT_BLOCKED", "SERVICE_STALE", "PROFILE_COVERAGE_MISSING", "ALTERNATE_UNAVAILABLE",
                 "AUDIT_UNAVAILABLE", "ROUTING_IN_PROGRESS", "ROUTING_DEADLINE_EXCEEDED", "ROUTING_OUTCOME_UNKNOWN"]
        route["properties"]["router_halt_code"] = {"enum": [None, *halts]}
        route["required"] = list(dict.fromkeys([*route["required"], "router_halt_code"]))
        fallback = route["properties"]["router_failure"]["anyOf"][1]
        if "enum" in fallback and "no_route" not in fallback["enum"]:
            fallback["enum"] = [*fallback["enum"], "no_route"]
        # Source route_record_consistent is part of owning IF001/I001, although
        # the frozen field mirror predates its prose amendment.
        route.setdefault("allOf", []).extend([
            {"if": {"properties": {"decision_source": {"const": "codex_router_disabled"}}},
             "then": {"properties": {"router_enabled": {"const": False}}},
             "else": {"properties": {"router_enabled": {"const": True}}}},
            {"if": {"properties": {"decision_source": {"const": "codex_router_failed"}}},
             "then": {"properties": {"router_failure": {"type": "string"}}},
             "else": {"properties": {"router_failure": {"const": None}}}},
            {"if": {"properties": {"router_failure": {"const": "no_route"}}},
             "then": {"properties": {"router_halt_code": {"type": "string"}}},
             "else": {"properties": {"router_halt_code": {"const": None}}}},
            {"if": {"properties": {"decision_source": {"const": "router"}}},
             "then": {"properties": {"route_decision_ref": {"type": "object"}}},
             "else": {"properties": {"route_decision_ref": {"const": None}}}},
        ])
    return schemas, Registry().with_resources(resources.items())


@lru_cache(maxsize=None)
def field_meanings(contract_id: str) -> tuple:
    """(Owner.field, meaning) pairs for a field-contract interface and every type it reaches.

    Reviewers judge outputs against these contract meanings. URN schemas and
    unknown ids have none and return ().
    """
    fields = json.loads(files("jiuwenswarm.research_contracts").joinpath("field-contracts.json").read_text("utf-8"))
    types = dict(fields["types"])
    for entry in fields["interfaces"]:
        alias = "".join(part[:1].upper() + part[1:] for part in entry["name"].split("-"))
        types.setdefault(alias, {"fields": entry["fields"]})
    interface = next((entry for entry in fields["interfaces"] if contract_id in (entry["id"], entry["name"])), None)
    if interface is None:
        return ()
    pairs, pending, seen = [], [(interface["name"], interface["fields"])], set()
    while pending:
        owner, table = pending.pop(0)
        for name, field in table.items():
            if field.get("meaning"):
                pairs.append((owner + "." + name, field["meaning"]))
            base = field.get("type", "").removeprefix("nullable-").removesuffix("[]")
            if base in types and base not in seen:
                seen.add(base)
                pending.append((base, types[base]["fields"]))
    return tuple(pairs)


def contract_schema(contract_id: str) -> dict:
    schemas, _ = _contracts()
    key = contract_id
    if key not in schemas:
        raise ContractError("unknown_contract", f"No adopted contract {contract_id!r}")
    return copy.deepcopy(schemas[key])


@lru_cache(maxsize=None)
def _validator(contract_id: str) -> Draft202012Validator:
    """Reuse a validator over private, immutable installed schema data.

    Public callers still receive isolated copies from contract_schema(). The
    internal validator neither exposes nor changes the shared schema/registry.
    """
    schemas, registry = _contracts()
    return Draft202012Validator(schemas[contract_id], registry=registry)


def validate(contract_id: str, value: Any) -> None:
    if contract_id == 'route-record' and isinstance(value, dict) and value.get('schema_version') == '4.0.0':
        contract_id = 'urn:ai4r:automatic-route-record:4.0.0'
    if contract_id == 'route-record' and isinstance(value, dict) and value.get('schema_version') == '3.0.0':
        contract_id = 'urn:ai4r:automatic-route-record:3.0.0'
    if contract_id == 'route-record' and isinstance(value, dict) and value.get('schema_version') == '2.0.0':
        contract_id = 'urn:ai4r:manual-route-record:2.0.0'
    if contract_id == 'invocation-observation' and isinstance(value, dict) and value.get('schema_version') == '4.0.0':
        contract_id = 'urn:ai4r:invocation-observation:4.0.0'
    # Short-name reads retain historical evidence semantics; an explicit URN
    # still requires its exact version. New producers use the catalog's v3.
    if contract_id == 'research-brief' and isinstance(value, dict):
        contract_id = 'urn:jiuwenswarm:m1-design:research-brief:' + str(value.get('schema_version'))
    if not _finite(value):
        raise ContractError("invalid_json", "Values must be finite JSON data")
    schemas, _ = _contracts()
    if contract_id not in schemas:
        raise ContractError("unknown_contract", f"No adopted contract {contract_id!r}")
    try:
        errors = sorted(_validator(contract_id).iter_errors(value),
                        key=lambda e: "/".join(map(str, e.absolute_path)))
    except Exception as exc:
        raise ContractError("schema_unavailable", f"Cannot resolve adopted contract {contract_id}") from exc
    if errors:
        details = [{"path": "/" + "/".join(map(str, e.absolute_path)), "message": e.message}
                   for e in errors]
        raise ContractError("contract_invalid", f"{contract_id}: {details[0]['message']}", {"errors": details})
