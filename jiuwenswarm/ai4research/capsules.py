"""M0-IF-003@r2: the protected, two-definition trial capsule library.

Only host administration calls admission/standing methods. These methods are not
client or model endpoints. Admission prerequisites are observations supplied by
the protected readiness/check owners, not claims extracted from model output.
Packaged templates are hydrated once into immutable candidates; seeding never
admits or activates them. Fixture-only standing cannot resolve for real work.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .common import GovernanceError, canonical_json, hash_json, sha256_bytes, utc_now

INTERFACE_REVISION = "M0-IF-003@r2"
SCHEMA_REVISION = "2.11"
ROLES = ("intent_compiler", "intent_verifier")
_COMMON_BODY = {"intent/__init__.py", "intent/models.py", "common.py", "runner.py", "bridge.py", "capsules.py"}
_VERIFIER_BODY = {"verification/profile.json", "verification/upstream-adaptation.json",
                  "verification/upstream/result-evaluator.md", "verification/upstream/citation-reviewer.md",
                  "verification/upstream/LICENSE", "verification/gate.py", "verification/__init__.py"}
_DEPENDENCIES = {"common.py", "runner.py", "bridge.py", "capsules.py"}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ANY = object()
_REF = {"ref": str, "sha256": str}
_PORT = {"name": str, "artifact_type": str, "required": bool,
         "schema_ref": str, "check_id": str, "description": str}
_PROVENANCE = {"generating_model": (str, type(None)), "prompt_ref": str,
               "trajectory_ref": (str, type(None))}
_CHECK = {"id": str, "kind": str, "target": str, "runner": _REF,
          "anchor": str, "over": [str], "author": str,
          "written_before_body": bool, "held_out": bool, "signal_source": str,
          "owner": str, "assurance": str}
_SHAPE = {
    "schema_version": str,
    "identity": {
        "name": str, "version_label": str, "kind": str, "carrier": _REF,
        "body": [{"path": str, "sha256": str}],
        "summary": str, "load_mode": str,
        "remote": {"endpoint": str, "version": str, "interface_version_range": str},
        "overlays": [{"kind": str, "ref": str, "sha256": str, "source": str}],
        "lineage": {"parent": (str, type(None)), "co_parents": [str],
                    "relation": str, "builder": str, "build_trigger": str,
                    "context_capsules": [str], "diagnosis_inputs": [str],
                    "builder_ref": str, "provenance": _PROVENANCE},
    },
    "ports": {"inputs": [_PORT], "outputs": [_PORT]},
    "needs": {
        "when": [{"id": str, "check": {"path": str, "operator": str, "value": _ANY},
                  "state_source": str, "evaluable_at": str, "max_age_s": (int, float),
                  "on_unknown": str, "on_unavailable": str, "parity_check": str}],
        "external": [{"ref": str, "kind": str, "pin": {"sha256": str},
                      "pinned": bool, "decl_hash": str, "unpinned_purpose": str,
                      "floating": {"purpose": str, "role": str, "contracts": [str]}}],
        "network": str,
        "resources": [{"resource_key": str, "mode": str}],
        "injects": [{"service_key": str, "interface_version_range": str}],
        "model": {"tool_calling": bool, "min_context": int, "modalities": [str],
                  "families": [str], "excludes": [str]},
    },
    "changes": {
        "effect_class": str,
        "effects": [{"id": str, "resource_key": str, "op": str, "scope": str,
                     "idempotent": bool, "reversibility": str, "undo": (str, type(None)),
                     "risk": {"severity": str, "blast_radius": str, "irreversibility": str},
                     "assurance": str}],
        "provides": [{"service_key": str, "interface_version": str, "commutative": bool}],
        "invariants": [{"id": str, "statement": str, "check_id": str}],
    },
    "guarantees": {
        "checks": [_CHECK], "acceptance": [str],
        "evals": [{"suite_ref": str, "sha256": str, "metric": str,
                   "threshold": _ANY, "held_out": bool}],
        "unanchored": [str],
        "quality": {"criterion": str, "judge": str, "target_rate": (int, float),
                    "window": int, "min_observations": int},
        "exempt": (bool, {"reason": str}),
    },
    "budget": {
        "per_call": {"tokens": int, "wall_s": (int, float), "cost": (int, float),
                     "tool_calls": int, "iterations": int},
        "enforcement": {"tokens": str, "wall_s": str, "cost": str,
                        "tool_calls": str, "iterations": str},
        "on_exhaust": str,
    },
    "members": [{"role": str, "decl_hash": str}],
    "structure": {"type": str, "direction": str, "nodes": [str],
                  "edges": [{"source": str, "target": str, "relation": str}],
                  "loop_guards": [str]},
    "wiring": [{"from": str, "to": str}],
    "evolution": {"frozen": [str], "notes_for_builder": [str]},
    "coverage": {"undeclared_notes": [str]},
}

# Every combined inventory concept is retained or explicitly rejected as a
# non-executable legacy/future representation; unknown authority is never ignored.
FIELD_DISPOSITION = {
    "schema_version/identity.name/kind/version_label": "supported",
    "identity.carrier/body": "supported; local immutable closure",
    "identity.remote": "future; rejected for trial execution",
    "identity.summary/load_mode": "supported metadata; no planner",
    "identity.overlays": "future; nonempty overlays rejected",
    "identity.lineage/provenance": "retained authored-version provenance; no RSI",
    "ports.inputs/outputs": "supported canonical artifact_type/schema_ref/check_id",
    "legacy ports.type/check": "incompatible; explicit migration required",
    "needs.when": "empty with rationale; general predicates deferred",
    "legacy predicate path/op/value": "incompatible; no silent reinterpretation",
    "needs.external": "supported local hash-pinned source dependencies only",
    "needs.external.floating/model/service/capsule/secret pins": "future; not executable",
    "needs.network": "none for CC; protected injected model bridge only",
    "legacy network directions": "incompatible; do not imply authorization",
    "needs.resources/injects/model": "supported scoped metadata; no provider selection",
    "legacy string resources/injects": "incompatible; explicit migration required",
    "changes.effect_class/effects/risk/assurance": "supported; text-only read boundary",
    "changes.provides/invariants": "retained typed compatibility metadata",
    "legacy string provides/invariants": "incompatible; explicit migration required",
    "guarantees.checks/acceptance/evals/unanchored": "supported exact checks/coverage",
    "legacy runner/runner_hash": "incompatible; canonical hashed runner required",
    "guarantees.quality": "compatibility metadata; no measured quality claim",
    "guarantees.exempt": "retained false; no author-controlled exemption",
    "budget.per_call/enforcement/on_exhaust": "supported time/call controls",
    "legacy budget.tokens/time_s/money/concurrency": "incompatible; explicit migration required",
    "members/structure/wiring": "future; nonempty composition rejected",
    "evolution.frozen/notes_for_builder": "retained promises/advice; no mutation authority",
    "coverage.undeclared_notes": "retained explanatory metadata; no runtime authority",
    "decl_hash/contract_hash/context_cost_tokens/flags/derived needs/effects": "host computed; never authored",
}


def _fail(code: str, message: str) -> None:
    raise GovernanceError(code, message)


def _shape(value: Any, shape: Any, path: str) -> None:
    if shape is _ANY:
        return
    if isinstance(shape, dict):
        if not isinstance(value, dict):
            _fail("invalid_input", f"Expected object at {path}")
        if set(value) - set(shape):
            _fail("invalid_input", f"Unknown authority field at {path}")
        for key, item in value.items():
            _shape(item, shape[key], f"{path}.{key}")
    elif isinstance(shape, list):
        if not isinstance(value, list):
            _fail("invalid_input", f"Expected array at {path}")
        for item in value:
            _shape(item, shape[0], f"{path}[]")
    elif isinstance(shape, tuple):
        for variant in shape:
            try:
                _shape(value, variant, path)
                return
            except GovernanceError:
                pass
        _fail("invalid_input", f"Unsupported value at {path}")
    elif not isinstance(value, shape) or (shape in (int, float) and isinstance(value, bool)):
        _fail("invalid_input", f"Incorrect type at {path}")


def _required(value: Mapping, fields: tuple[str, ...], path: str) -> None:
    if any(key not in value for key in fields):
        _fail("invalid_input", f"Missing required field at {path}")


def _hash(value: Any) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _fail("invalid_input", "Expected a lowercase SHA256 identity")
    return value


def _role(value: str) -> str:
    if value not in ROLES:
        _fail("incompatible_revision", "Only the two registered trial roles are supported")
    return value


def _scope(value: str) -> str:
    if value in ("real", "model-backed"):
        return "real"
    if value == "fixture-only":
        return value
    _fail("invalid_input", "Admission scope must be real or fixture-only")


def validate_declaration(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a defensive canonical declaration; never drop unknown fields."""
    try:
        declaration = json.loads(canonical_json(value))
    except (TypeError, ValueError):
        _fail("invalid_input", "Declaration must contain finite JSON values")
    _shape(declaration, _SHAPE, "capsule")
    _required(declaration, ("schema_version", "identity", "ports", "needs", "changes", "guarantees", "budget"), "capsule")
    if declaration["schema_version"] != SCHEMA_REVISION:
        _fail("incompatible_revision", "Unsupported declaration revision; explicit migration is required")
    identity = declaration["identity"]
    _required(identity, ("name", "version_label", "kind", "carrier", "body", "summary", "lineage"), "identity")
    _role(identity["name"])
    if identity["kind"] != "skill" or identity.get("remote") or identity.get("overlays"):
        _fail("incompatible_revision", "Only local text-only trial skills are executable")
    expected_carrier = "intent/compiler.prompt.md" if identity["name"] == "intent_compiler" else "intent/verifier.prompt.md"
    if identity["carrier"].get("ref") != expected_carrier:
        _fail("ineligible_pin", "Trial role and implementation carrier are swapped")
    body_paths = [item.get("path") for item in identity["body"]]
    expected_body = _COMMON_BODY | (_VERIFIER_BODY if identity["name"] == "intent_verifier" else set())
    if len(body_paths) != len(set(body_paths)) or set(body_paths) != expected_body:
        _fail("incompatible_revision", "Trial implementation must declare its exact supported source closure")
    if not identity["version_label"].strip() or not identity["summary"].strip() or len(identity["summary"]) > 400:
        _fail("invalid_input", "Version/summary must be explicit and summary bounded")
    lineage = identity["lineage"]
    _required(lineage, ("relation", "builder", "build_trigger", "provenance"), "lineage")
    if lineage["relation"] not in ("authored", "revision"):
        _fail("incompatible_revision", "Runtime evolution is not part of the trial")
    for field in ("parent",):
        if lineage.get(field) is not None:
            _hash(lineage[field])
    if any(declaration.get(field) for field in ("members", "structure", "wiring")):
        _fail("incompatible_revision", "Internal composition is not supported by the trial")
    ports = declaration["ports"]
    _required(ports, ("inputs", "outputs"), "ports")
    for direction in ("inputs", "outputs"):
        if not ports[direction]:
            _fail("invalid_input", "Typed trial ports are required")
        names = []
        for port in ports[direction]:
            _required(port, ("name", "artifact_type", "schema_ref"), "port")
            if not all(port[key].strip() for key in ("name", "artifact_type", "schema_ref")):
                _fail("invalid_input", "Port identity and schema are required")
            if direction == "outputs":
                _required(port, ("check_id",), "output")
            else:
                _required(port, ("required",), "input")
            names.append(port["name"])
        if len(names) != len(set(names)):
            _fail("invalid_input", "Duplicate port identity")
    compiler = identity["name"] == "intent_compiler"
    input_types = {"original_request": ("text/plain", "M0-IF-020@r2/original_text")}
    if not compiler:
        input_types["candidate"] = ("IntermediateIntent", "M0-IF-020@r2/IntermediateIntent")
    if {item["name"] for item in ports["inputs"]} != set(input_types):
        _fail("incompatible_revision", "Unsupported trial input contract")
    for port in ports["inputs"]:
        if (port["artifact_type"], port["schema_ref"]) != input_types[port["name"]] or port["required"] is not True:
            _fail("incompatible_revision", "Trial input type/schema or requiredness is incompatible")
    output = ("intent", "IntermediateIntent", "M0-IF-020@r2/IntermediateIntent") if compiler else ("assessment", "IntentAssessment", "M0-IF-007@r2/IntentAssessment")
    if len(ports["outputs"]) != 1 or tuple(ports["outputs"][0][key] for key in ("name", "artifact_type", "schema_ref")) != output:
        _fail("incompatible_revision", "Unsupported trial output contract")
    needs = declaration["needs"]
    _required(needs, ("when", "external", "network", "resources", "injects"), "needs")
    if needs["when"] or needs["network"] != "none" or needs.get("model", {}).get("tool_calling", False):
        _fail("incompatible_revision", "Trial skills have no authored predicate engine, tools or network")
    if not declaration.get("coverage", {}).get("undeclared_notes"):
        _fail("invalid_input", "Empty authored preconditions require an explicit host-readiness rationale")
    if any(item.get("mode") != "read" for item in needs["resources"]):
        _fail("policy_denied", "Trial context resources are read-only")
    resources = [item.get("resource_key") for item in needs["resources"]]
    expected_resources = {"original_request"} | (set() if compiler else {"exact_candidate", "protected_fidelity_profile"})
    if len(resources) != len(set(resources)) or set(resources) != expected_resources:
        _fail("policy_denied", "Trial context cannot include control, credentials or unrelated resources")
    if needs["injects"] != [{"service_key": "static_text_model_bridge", "interface_version_range": "M0-IF-001@r2"}]:
        _fail("policy_denied", "Only the protected static trial model bridge can be injected")
    if needs.get("model", {}).get("modalities", ["text"]) != ["text"]:
        _fail("policy_denied", "Only text model context is supported")
    for dependency in needs["external"]:
        _required(dependency, ("ref", "kind", "pin", "pinned"), "dependency")
        if dependency["kind"] != "package" or dependency["pinned"] is not True or dependency.get("floating"):
            _fail("incompatible_revision", "Only explicit local source dependencies are supported")
        _required(dependency["pin"], ("sha256",), "dependency.pin")
        _hash(dependency["pin"]["sha256"])
    dependencies = [item["ref"] for item in needs["external"]]
    if len(dependencies) != len(set(dependencies)) or set(dependencies) != _DEPENDENCIES:
        _fail("incompatible_revision", "Complete pinned shared trial dependencies are required")
    if declaration["changes"].get("effect_class") != "read_only":
        _fail("policy_denied", "Trial implementation effects must be read-only")
    for effect in declaration["changes"].get("effects", []):
        _required(effect, ("id", "resource_key", "op", "scope", "idempotent", "reversibility"), "effect")
        if effect["op"] not in ("read", "model_invoke"):
            _fail("policy_denied", "Undeclared trial mutation/tool effect")
        if effect["op"] == "model_invoke" and (effect["resource_key"] != "approved_static_model_bridge" or effect["idempotent"] is not False):
            _fail("policy_denied", "The model route is protected and completion is never assumed repeat-safe")
    guarantees = declaration["guarantees"]
    _required(guarantees, ("checks", "acceptance", "unanchored"), "guarantees")
    if guarantees.get("exempt") not in (None, False):
        _fail("policy_denied", "Author-controlled verification exemption is forbidden")
    ids = []
    for check in guarantees["checks"]:
        _required(check, ("id", "kind", "target", "runner", "owner"), "check")
        _required(check["runner"], ("ref", "sha256"), "check.runner")
        _hash(check["runner"]["sha256"])
        ids.append(check["id"])
    if not ids or len(ids) != len(set(ids)) or not guarantees["acceptance"] or not set(guarantees["acceptance"]) <= set(ids):
        _fail("invalid_input", "Unique checks and covered acceptance IDs are required")
    if not {"output-schema", "implementation-integrity"} <= set(guarantees["acceptance"]):
        _fail("policy_denied", "Mandatory declaration integrity/schema checks cannot be waived")
    if any(port["check_id"] not in ids for port in ports["outputs"]):
        _fail("invalid_input", "Every output must name a declared check")
    limits = declaration["budget"].get("per_call", {})
    _required(limits, ("wall_s", "tool_calls", "iterations"), "budget.per_call")
    if not math.isfinite(limits["wall_s"]) or limits["wall_s"] <= 0 or limits["tool_calls"] != 0 or limits["iterations"] != 1:
        _fail("policy_denied", "Trial limits require finite time, no tools and one model pass")
    enforcement = declaration["budget"].get("enforcement", {})
    if any(enforcement.get(key) != "hard" for key in ("wall_s", "tool_calls", "iterations")) or declaration["budget"].get("on_exhaust") != "fail":
        _fail("policy_denied", "Trial time/call enforcement cannot be inert or permissive")
    _required(identity["carrier"], ("ref", "sha256"), "carrier")
    _hash(identity["carrier"]["sha256"])
    for body in identity["body"]:
        _required(body, ("path", "sha256"), "body")
        _hash(body["sha256"])
    return declaration


def make_capsule_markdown(declaration: Mapping) -> str:
    """A derived inspection view, never an independent declaration."""
    data = validate_declaration(declaration)
    return (f"# {data['identity']['name']}\n\n"
            "Generated from the canonical capsule.json declaration.\n\n"
            f"Declaration SHA256: `{hash_json(data)}`\n\n```json\n"
            + json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n```\n")


@dataclass(frozen=True)
class CapsulePin:
    role: str
    decl_hash: str
    implementation_hash: str
    contract_hash: str
    declaration_bytes: bytes
    admission_scope: str | None = None
    standing: str = "candidate"

    @property
    def declaration(self) -> dict:
        return json.loads(self.declaration_bytes)

    @property
    def closure_hash(self) -> str:
        return self.implementation_hash

    @property
    def sha256(self) -> str:
        return self.decl_hash

    def to_dict(self) -> dict:
        return {"role": self.role, "decl_hash": self.decl_hash, "sha256": self.decl_hash,
                "implementation_hash": self.implementation_hash, "closure_hash": self.implementation_hash,
                "contract_hash": self.contract_hash, "interface_revision": INTERFACE_REVISION,
                "schema_revision": SCHEMA_REVISION, "admission_scope": self.admission_scope,
                "standing": self.standing, "declaration": self.declaration}


class CapsuleLibrary:
    """Protected local immutable versions plus append-only admission/standing.

    root_dir is the ai4research package directory. No file locator can escape it
    or traverse a symlink/reparse point. db_path is controlled by the host, never
    supplied by a client. Admission and human_authorized are trusted host inputs.
    """

    def __init__(self, db_path: str | Path, root_dir: str | Path):
        self.db_path = Path(db_path)
        raw_root = Path(root_dir).absolute()
        try:
            metadata = raw_root.lstat()
            if raw_root.is_symlink() or getattr(metadata, "st_file_attributes", 0) & 0x400:
                _fail("policy_denied", "Package root cannot be a symlink or reparse point")
            self.root_dir = raw_root.resolve(strict=True)
            if not self.root_dir.is_dir():
                _fail("environment_unavailable", "Package root is not an available directory")
        except OSError:
            _fail("environment_unavailable", "Package root is unavailable")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._db() as db:
                db.executescript("""
                CREATE TABLE IF NOT EXISTS capsule_versions (
                    decl_hash TEXT PRIMARY KEY, role TEXT NOT NULL,
                    declaration BLOB NOT NULL, implementation_hash TEXT NOT NULL,
                    contract_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capsule_sources (
                    decl_hash TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL,
                    body BLOB NOT NULL, PRIMARY KEY(decl_hash,path));
                CREATE TABLE IF NOT EXISTS capsule_admissions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, decl_hash TEXT NOT NULL,
                    scope TEXT NOT NULL, accepted INTEGER NOT NULL, evidence BLOB NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capsule_standing (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, decl_hash TEXT NOT NULL,
                    action TEXT NOT NULL, actor_id TEXT NOT NULL, scope TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capsule_active (
                    role TEXT PRIMARY KEY, decl_hash TEXT NOT NULL, scope TEXT NOT NULL);
                """)
                for table in ("capsule_versions", "capsule_sources", "capsule_admissions", "capsule_standing"):
                    for action in ("UPDATE", "DELETE"):
                        db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_deny_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable capsule history'); END")
        except sqlite3.Error:
            _fail("persistence_failed", "Capsule library initialization failed")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _read(self, ref: str) -> bytes:
        if not isinstance(ref, str) or not ref or "\\" in ref or ":" in ref:
            _fail("policy_denied", "Only relative package file locators are allowed")
        parsed = PurePosixPath(ref)
        if parsed.is_absolute() or any(part in ("..", ".", "") for part in ref.split("/")):
            _fail("policy_denied", "Package locator escapes its scope")
        target = self.root_dir
        try:
            for component in parsed.parts:
                target = target / component
                metadata = target.lstat()
                if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
                    _fail("policy_denied", "Symlink/reparse package locators are forbidden")
            resolved = target.resolve(strict=True)
            if not resolved.is_relative_to(self.root_dir) or not resolved.is_file():
                _fail("policy_denied", "Package resource is not a scoped regular file")
            # Check the opened inode as well as the path, closing simple substitution races.
            fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                    _fail("policy_denied", "Package resource changed during capture")
                return stream.read()
        except GovernanceError:
            raise
        except OSError:
            _fail("environment_unavailable", "Required package resource is unavailable")

    def _closure(self, declaration: Mapping) -> dict[str, tuple[str, bytes]]:
        refs = [(declaration["identity"]["carrier"]["ref"], declaration["identity"]["carrier"]["sha256"])]
        refs += [(x["path"], x["sha256"]) for x in declaration["identity"]["body"]]
        refs += [(x["ref"], x["pin"]["sha256"]) for x in declaration["needs"]["external"]]
        refs += [(x["runner"]["ref"], x["runner"]["sha256"]) for x in declaration["guarantees"]["checks"]]
        refs += [(x["suite_ref"], x["sha256"]) for x in declaration["guarantees"].get("evals", [])]
        result: dict[str, tuple[str, bytes]] = {}
        for path, expected in refs:
            _hash(expected)
            body = self._read(path)
            if sha256_bytes(body) != expected:
                _fail("ineligible_pin", "Pinned package content has changed")
            if path in result and result[path][0] != expected:
                _fail("invalid_input", "Conflicting dependency identities")
            result[path] = (expected, body)
        if not result:
            _fail("invalid_input", "Implementation closure is empty")
        return result

    def stage(self, declaration: Mapping) -> CapsulePin:
        """Validate/capture an inactive candidate; no admission or activation."""
        value = validate_declaration(declaration)
        closure = self._closure(value)
        digest = hash_json(value)
        implementation = hash_json({path: item[0] for path, item in closure.items()})
        contract = hash_json({key: value.get(key) for key in ("ports", "needs", "changes", "guarantees", "budget")} | {"frozen": value.get("evolution", {}).get("frozen", [])})
        try:
            with self._db() as db:
                parent = value["identity"]["lineage"].get("parent")
                if parent:
                    old = db.execute("SELECT role FROM capsule_versions WHERE decl_hash=?", (parent,)).fetchone()
                    if not old or old["role"] != value["identity"]["name"]:
                        _fail("ineligible_pin", "Authored parent lineage is missing or belongs to another role")
                db.execute("INSERT OR IGNORE INTO capsule_versions VALUES(?,?,?,?,?,?)",
                           (digest, value["identity"]["name"], canonical_json(value), implementation, contract, utc_now()))
                for path, (expected, body) in closure.items():
                    db.execute("INSERT OR IGNORE INTO capsule_sources VALUES(?,?,?,?)", (digest, path, expected, body))
            return self.get(digest)
        except sqlite3.Error:
            _fail("persistence_failed", "Capsule candidate persistence failed")

    def seed_builtin(self) -> dict[str, CapsulePin]:
        """Hydrate only trusted packaged templates, retaining new inactive identities.

        Null template hashes mean 'capture at explicit host seeding', never a
        valid declaration pin. Existing non-null hashes are checked, not replaced.
        No model-supplied template or new role is accepted by this operation.
        """
        prepared = []
        for role in ROLES:
            try:
                value = json.loads(self._read(f"declaration/library/{role}.json"))
            except (ValueError, UnicodeError):
                _fail("invalid_input", "Packaged capsule template is malformed")
            if value.get("identity", {}).get("name") != role:
                _fail("invalid_input", "Packaged role identity is swapped")
            references = [(value["identity"]["carrier"], "ref", "sha256")]
            references += [(x, "path", "sha256") for x in value["identity"]["body"]]
            references += [(x["runner"], "ref", "sha256") for x in value["guarantees"]["checks"]]
            references += [(x["pin"], None, "sha256", x["ref"]) for x in value["needs"]["external"]]
            for entry in references:
                obj, key, hash_key = entry[:3]
                ref = obj[key] if key else entry[3]
                observed = sha256_bytes(self._read(ref))
                if obj[hash_key] is not None and obj[hash_key] != observed:
                    _fail("ineligible_pin", "Packaged static source pin no longer matches")
                obj[hash_key] = observed
            prepared.append(validate_declaration(value))
        # Both definitions are validated before any seeding; candidates remain inactive.
        return {value["identity"]["name"]: self.stage(value) for value in prepared}

    def get(self, decl_hash: str) -> CapsulePin:
        _hash(decl_hash)
        try:
            with self._db() as db:
                row = db.execute("SELECT * FROM capsule_versions WHERE decl_hash=?", (decl_hash,)).fetchone()
                if not row:
                    _fail("ineligible_pin", "Unknown capsule identity")
                admission = db.execute("SELECT scope FROM capsule_admissions WHERE decl_hash=? AND accepted=1 ORDER BY seq DESC LIMIT 1", (decl_hash,)).fetchone()
                standing = db.execute("SELECT action,scope FROM capsule_standing WHERE decl_hash=? ORDER BY seq DESC LIMIT 1", (decl_hash,)).fetchone()
                body = bytes(row["declaration"])
                if sha256_bytes(body) != row["decl_hash"]:
                    _fail("ineligible_pin", "Stored declaration integrity is invalid")
                return CapsulePin(row["role"], row["decl_hash"], row["implementation_hash"], row["contract_hash"], body,
                                  standing["scope"] if standing else (admission["scope"] if admission else None),
                                  standing["action"] if standing else ("admitted_inactive" if admission else "candidate"))
        except sqlite3.Error:
            _fail("persistence_failed", "Capsule history retrieval failed")

    def _candidate(self, role: str, decl_hash: str | None) -> CapsulePin:
        _role(role)
        if decl_hash is None:
            try:
                with self._db() as db:
                    row = db.execute("SELECT decl_hash FROM capsule_versions WHERE role=? ORDER BY rowid DESC LIMIT 1", (role,)).fetchone()
            except sqlite3.Error:
                _fail("persistence_failed", "Capsule candidate retrieval failed")
            if not row:
                _fail("ineligible_pin", "No packaged candidate exists for this role")
            decl_hash = row["decl_hash"]
        pin = self.get(decl_hash)
        if pin.role != role:
            _fail("ineligible_pin", "Capsule identity is bound to a different role")
        return pin

    def admit(self, role: str, prerequisites: Mapping, *, decl_hash: str | None = None) -> CapsulePin:
        """Protected host decision from actual readiness/definition-review receipts.

        Scope is fixture-only or real. checks_passed/review_passed refer to
        definition/adaptation evidence, not a future runtime semantic verdict.
        The protected evidence owner validates receipt custody before this call.
        """
        pin = self._candidate(role, decl_hash)
        self._closure(pin.declaration)
        required = ("runtime_ready", "security_ready", "profile_ready", "checks_passed", "review_passed", "scope", "evidence_refs")
        _required(prerequisites, required, "host admission evidence")
        if set(prerequisites) - set(required):
            _fail("invalid_input", "Unknown host admission prerequisite")
        if any(not isinstance(prerequisites[key], bool) for key in required[:5]):
            _fail("invalid_input", "Protected readiness/review observations must be booleans")
        scope = _scope(prerequisites["scope"])
        refs = prerequisites["evidence_refs"]
        if not isinstance(refs, list) or not refs:
            _fail("invalid_input", "Admission requires attributable protected evidence references")
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {"ref", "sha256"} or not isinstance(ref["ref"], str) or not ref["ref"].strip():
                _fail("invalid_input", "Admission evidence references require identity and SHA256")
            _hash(ref["sha256"])
        ready = all(prerequisites[key] is True for key in required[:5])
        evidence = canonical_json(dict(prerequisites) | {"subject_decl_hash": pin.decl_hash, "implementation_hash": pin.implementation_hash})
        try:
            with self._db() as db:
                db.execute("INSERT INTO capsule_admissions(decl_hash,scope,accepted,evidence,created_at) VALUES(?,?,?,?,?)", (pin.decl_hash, scope, int(ready), evidence, utc_now()))
        except sqlite3.Error:
            _fail("persistence_failed", "Capsule admission decision persistence failed")
        if not ready:
            _fail("environment_unavailable", "Required runtime, profile, security or definition-review prerequisite is unavailable")
        return self.get(pin.decl_hash)

    def activate(self, role: str, decl_hash: str | None = None, *, human_authorized: bool = False, actor_id: str | None = None, required_scope: str | None = None) -> CapsulePin:
        return self.set_standing(role, decl_hash, "active", human_authorized=human_authorized, actor_id=actor_id, required_scope=required_scope)

    def set_standing(self, role: str, decl_hash: str | None, action: str, *, human_authorized: bool = False, actor_id: str | None = None, required_scope: str | None = None) -> CapsulePin:
        """Authenticated host admin only; never deserialize authority from a model."""
        if human_authorized is not True or not isinstance(actor_id, str) or not actor_id.strip():
            _fail("policy_denied", "Authenticated human host authority is required for standing changes")
        if action not in ("active", "suspended", "deprecated"):
            _fail("invalid_input", "Unknown capsule standing action")
        if decl_hash is None and action != "active":
            try:
                with self._db() as db:
                    row = db.execute("SELECT decl_hash FROM capsule_active WHERE role=?", (_role(role),)).fetchone()
            except sqlite3.Error:
                _fail("persistence_failed", "Current standing target retrieval failed")
            if not row:
                _fail("ineligible_pin", "There is no activated standing target")
            decl_hash = row["decl_hash"]
        pin = self._candidate(role, decl_hash)
        scope = _scope(required_scope) if required_scope is not None else pin.admission_scope
        if scope is None:
            _fail("ineligible_pin", "Admission does not exist for this candidate")
        if action == "active":
            self._closure(pin.declaration)
        try:
            with self._db() as db:
                accepted = db.execute("SELECT seq FROM capsule_admissions WHERE decl_hash=? AND scope=? AND accepted=1", (pin.decl_hash, scope)).fetchone()
                if not accepted:
                    _fail("ineligible_pin", "Required admission scope is unavailable")
                db.execute("INSERT INTO capsule_standing(decl_hash,action,actor_id,scope,created_at) VALUES(?,?,?,?,?)", (pin.decl_hash, action, actor_id, scope, utc_now()))
                if action == "active":
                    db.execute("INSERT INTO capsule_active VALUES(?,?,?) ON CONFLICT(role) DO UPDATE SET decl_hash=excluded.decl_hash,scope=excluded.scope", (role, pin.decl_hash, scope))
        except sqlite3.Error:
            _fail("persistence_failed", "Human standing action persistence failed")
        return self.get(pin.decl_hash)

    def suspend(self, role: str, decl_hash: str | None = None, **authority) -> CapsulePin:
        return self.set_standing(role, decl_hash, "suspended", **authority)

    def deprecate(self, role: str, decl_hash: str | None = None, **authority) -> CapsulePin:
        return self.set_standing(role, decl_hash, "deprecated", **authority)

    def rollback(self, role: str, decl_hash: str, **authority) -> CapsulePin:
        return self.activate(role, decl_hash, **authority)

    def resolve(self, role: str, *, decl_hash: str | None = None, required_scope: str | None = None) -> CapsulePin:
        _role(role)
        if decl_hash is None:
            try:
                with self._db() as db:
                    row = db.execute("SELECT decl_hash FROM capsule_active WHERE role=?", (role,)).fetchone()
                if not row:
                    _fail("ineligible_pin", "Role has no human-activated default")
                decl_hash = row["decl_hash"]
            except sqlite3.Error:
                _fail("persistence_failed", "Activated pin retrieval failed")
        pin = self._candidate(role, decl_hash)
        return self.validate_pin(pin, required_scope=required_scope)

    def validate_pin(self, pin: CapsulePin | Mapping, *, required_scope: str | None = None) -> CapsulePin:
        requested = pin.to_dict() if isinstance(pin, CapsulePin) else dict(pin)
        role = _role(requested.get("role"))
        digest = requested.get("decl_hash") or requested.get("sha256")
        _hash(digest)
        if requested.get("decl_hash") and requested.get("sha256") and requested["decl_hash"] != requested["sha256"]:
            _fail("ineligible_pin", "Declaration identity aliases disagree")
        current = self._candidate(role, digest)
        if current.standing != "active":
            _fail("ineligible_pin", "Pinned version is not activated or is suspended/deprecated")
        if required_scope is not None and current.admission_scope != _scope(required_scope):
            _fail("ineligible_pin", "Fixture-only admission cannot resolve for real work")
        for key, expected in (("implementation_hash", current.implementation_hash), ("closure_hash", current.implementation_hash), ("contract_hash", current.contract_hash)):
            if key in requested and requested[key] != expected:
                _fail("ineligible_pin", "Pinned implementation/contract identity is stale or swapped")
        for key, expected in (("interface_revision", INTERFACE_REVISION), ("schema_revision", SCHEMA_REVISION)):
            if key in requested and requested[key] != expected:
                _fail("incompatible_revision", "Unsupported pin revision")
        if "declaration" in requested and hash_json(requested["declaration"]) != current.decl_hash:
            _fail("ineligible_pin", "Pinned declaration payload has changed")
        closure = self._closure(current.declaration)
        if hash_json({path: value[0] for path, value in closure.items()}) != current.implementation_hash:
            _fail("ineligible_pin", "Implementation closure identity is invalid")
        return current

    def source_snapshot(self, decl_hash: str) -> dict[str, bytes]:
        """Historical inspection bytes; this method grants no execution eligibility."""
        pin = self.get(decl_hash)
        try:
            with self._db() as db:
                rows = db.execute("SELECT path,sha256,body FROM capsule_sources WHERE decl_hash=?", (pin.decl_hash,)).fetchall()
            if any(sha256_bytes(bytes(row["body"])) != row["sha256"] for row in rows):
                _fail("ineligible_pin", "Stored source closure integrity is invalid")
            return {row["path"]: bytes(row["body"]) for row in rows}
        except sqlite3.Error:
            _fail("persistence_failed", "Historical capsule closure retrieval failed")

    def history(self, role: str) -> dict:
        _role(role)
        try:
            with self._db() as db:
                versions = [dict(row) for row in db.execute("SELECT decl_hash,role,implementation_hash,contract_hash,created_at FROM capsule_versions WHERE role=? ORDER BY rowid", (role,))]
                admissions = [dict(row) for row in db.execute("SELECT a.seq,a.decl_hash,a.scope,a.accepted,a.created_at FROM capsule_admissions a JOIN capsule_versions v USING(decl_hash) WHERE v.role=? ORDER BY a.seq", (role,))]
                standing = [dict(row) for row in db.execute("SELECT s.* FROM capsule_standing s JOIN capsule_versions v USING(decl_hash) WHERE v.role=? ORDER BY s.seq", (role,))]
            return {"versions": versions, "admissions": admissions, "standing": standing}
        except sqlite3.Error:
            _fail("persistence_failed", "Capsule audit history retrieval failed")
