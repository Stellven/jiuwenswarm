"""Author a frozen, evaluation-only E2/E3 pilot closure from captured source refs.

This module creates no model calls and grants no product acceptance. The caller
must install the returned operator configuration and bootstrap binding in a new
Docker app startup before using the existing authenticated evaluation API.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
import uuid

from .contracts import ResearchError, validate
from .operator_config import OperatorConfiguration
from .state import json_bytes


_ASSET_ROLES = {
    "declaration", "output", "binding", "input", "host_runtime_observation",
    "host_identity_record", "host_budget_record", "host_tool_observation",
}
_HOST_ROLE = {
    "runtime_observation": "host_runtime_observation",
    "identity_record": "host_identity_record",
    "budget_record": "host_budget_record",
    "tool_observation": "host_tool_observation",
}
_SAFE_PATH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*\Z")


def _fail(message):
    raise ResearchError("evaluation_pilot", message)


def _path(value):
    if not isinstance(value, str) or len(value) > 256 or not _SAFE_PATH.fullmatch(value):
        _fail("Pilot assets need canonical relative paths")
    if any(part in {".", ".."} for part in value.split("/")):
        _fail("Pilot asset path escapes its frozen inventory")
    return value


def _ref(store, ref):
    validate("Ref", ref)
    return copy.deepcopy(ref)


def _asset(entries, path, role):
    if not isinstance(path, str):
        _fail("Pilot request asset path is missing")
    matches = [row for row in entries if row["path"] == path and row["role"] == role]
    if len(matches) != 1:
        _fail("Pilot request does not resolve to one exact frozen asset")
    return {"path": path, "sha256": matches[0]["sha256"]}


def _source_contract(store, binding_ref, entry_point):
    if entry_point == "E3":
        if store.record_kind(binding_ref) != "subnode-execution-contract":
            _fail("E3 requires the exact captured subnode execution contract")
        contract = store.read_record(binding_ref, contract_id="subnode-execution-contract")
        return contract, None
    capture = store.read_record(binding_ref)
    if capture.get("schema") not in {"ai4r-node-replay-binding:1", "ai4r-node-replay-binding:2"}:
        _fail("E2 requires the exact captured node replay binding")
    if store.record_kind(capture.get("contract_ref")) != "subnode-execution-contract":
        _fail("E2 replay binding has no canonical source contract")
    contract = store.read_record(capture["contract_ref"], contract_id="subnode-execution-contract")
    return contract, capture


def _request_shape(store, entry_point, request, entries, case, contract, replay,
                   source_binding_ref, profile):
    common = {"request_id", "campaign_id", "case_id", "evaluation_profile_id"}
    if entry_point == "E2":
        fields = common | {"verifier_cc_id", "declaration", "output", "node_id", "host_records"}
    else:
        fields = common | {"capsule_id", "capsule_version", "capsule_declaration_sha256",
                           "binding", "inputs", "model_route"}
    if type(request) is not dict or set(request) != fields:
        _fail("Pilot request fields do not match the selected E2/E3 protocol")
    if request["case_id"] != case["case_id"]:
        _fail("Pilot request case differs from its frozen case")
    if entry_point == "E2":
        declaration = _asset(entries, request["declaration"].get("path") if isinstance(request["declaration"], dict) else None, "declaration")
        output = _asset(entries, request["output"].get("path") if isinstance(request["output"], dict) else None, "output")
        if request["declaration"].get("sha256") != declaration["sha256"] or request["output"].get("sha256") != output["sha256"]:
            _fail("E2 asset digest differs from the frozen artifact")
        if request["node_id"] != contract["node_id"] or request["verifier_cc_id"] != replay.get("verifier_cc_id"):
            _fail("E2 request differs from its original source node or verifier")
        declaration_ref = contract["bindings"][0]["declaration_ref"]
        if declaration["sha256"] != declaration_ref["sha256"]:
            _fail("E2 declaration is not the exact original source capsule")
        output_port = replay.get("selected_output_port") or next(iter(replay["output_refs"]))
        if replay["output_refs"].get(output_port, {}).get("sha256") != output["sha256"]:
            _fail("E2 replay output is not the exact original port bytes")
        if not isinstance(request["host_records"], list):
            _fail("E2 host-record closure must be a list")
        for row in request["host_records"]:
            if type(row) is not dict or set(row) != {"record_type", "path", "sha256"} or row["record_type"] not in _HOST_ROLE:
                _fail("E2 host-record closure contains an unsupported evidence role")
            captured = _asset(entries, row["path"], _HOST_ROLE[row["record_type"]])
            if row["sha256"] != captured["sha256"]:
                _fail("E2 host-record digest differs from the frozen artifact")
        submitted_hosts = [(row["record_type"], next(e["artifact_ref"]["sha256"] for e in entries
            if e["path"] == row["path"] and e["role"] == _HOST_ROLE[row["record_type"]]))
            for row in request["host_records"]]
        captured_hosts = [(row["record_type"], row["ref"]["sha256"]) for row in replay["host_records"]]
        if submitted_hosts != captured_hosts:
            _fail("E2 host-record closure differs from the original captured replay")
    else:
        binding_asset = _asset(entries, request["binding"].get("path") if isinstance(request["binding"], dict) else None, "binding")
        if request["binding"].get("sha256") != binding_asset["sha256"]:
            _fail("E3 binding digest differs from its frozen contract")
        binding_entry = next(e for e in entries if e["path"] == request["binding"]["path"] and e["role"] == "binding")
        if binding_entry["artifact_ref"] != source_binding_ref:
            _fail("E3 binding asset is not the exact captured source contract")
        declaration_ref = contract["bindings"][0]["declaration_ref"]
        declaration = store.read_record(declaration_ref, contract_id="capsule-declaration")
        if (request["capsule_id"] != declaration["identity"]["name"]
                or request["capsule_version"] != declaration["identity"]["version_label"]
                or request["capsule_declaration_sha256"] != declaration_ref["sha256"]
                or request["model_route"] != profile["model_route"]):
            _fail("E3 request differs from the exact source capsule declaration")
        if not isinstance(request["inputs"], list):
            _fail("E3 inputs must be a list")
        for row in request["inputs"]:
            if type(row) is not dict or set(row) != {"port", "path", "sha256"}:
                _fail("E3 input closure is malformed")
            captured = _asset(entries, row["path"], "input")
            if row["sha256"] != captured["sha256"]:
                _fail("E3 input digest differs from the frozen artifact")
        actual_inputs = [(item["port"], entries[next(i for i, x in enumerate(entries)
            if x["path"] == item["path"] and x["role"] == "input")]["artifact_ref"]["sha256"])
            for item in request["inputs"]]
        expected_inputs = [(port["name"], ref["sha256"]) for port in contract["inputs"] for ref in port["artifact_refs"]]
        if actual_inputs != expected_inputs:
            _fail("E3 request inputs differ from the exact captured source contract")
    return copy.deepcopy(request)


def capture_evaluation_pilot_profile(store, *, current_operator, current_binding,
                                     profile_id, candidate_pins, verifier_cc_ref,
                                     library_snapshot_ref):
    """Capture phase one before an invalid-for-product source run.

    Run the ordinary app flow under the returned configuration, then call
    ``capture_evaluation_pilot_scope`` with that source run's exact refs. This
    preserves the source contract's configuration identity.
    """
    settings = current_operator.snapshot() if hasattr(current_operator, "snapshot") else copy.deepcopy(current_operator)
    binding = copy.deepcopy(current_binding)
    if type(settings) is not dict or type(binding) is not dict:
        _fail("Pilot authoring needs captured operator settings and startup binding")
    if settings.get("cc", {}).get("evaluation_profile_ref") is not None:
        _fail("Use a new explicit pilot profile directory; an existing profile is immutable")
    if settings["cc"]["router"]["enabled"]:
        _fail("E2/E3 pilot requires the installed fixed-route evaluation runtime")
    snapshot_ref = _ref(store, library_snapshot_ref)
    snapshot = store.read_record(snapshot_ref, contract_id="library-snapshot")
    pins = copy.deepcopy(candidate_pins)
    if type(pins) is not list or not pins:
        _fail("At least one exact admitted candidate pin is required")
    snapshot_entries = {(row["cc_name"], row["cc_version"], row["declaration_sha256"])
                        for row in snapshot["entries"]}
    for pin in pins:
        validate("CcPin", pin)
        if (pin["cc_name"], pin["cc_version"], pin["declaration_sha256"]) not in snapshot_entries:
            _fail("Candidate pin is not present in the exact installed snapshot")
    try:
        verifier = store.read_record(verifier_cc_ref, contract_id="capsule-declaration")
    except ResearchError as error:
        raise ResearchError("evaluation_pilot", "Independent verifier must be an exact installed declaration") from error
    verifier_pin = (verifier["identity"]["name"], verifier["identity"]["version_label"], verifier_cc_ref["sha256"])
    if verifier_pin not in snapshot_entries:
        _fail("Independent verifier is not present in the exact installed snapshot")
    profile = {"schema_version": "1.0.0", "id": "evaluation-profile:" + uuid.uuid4().hex,
        "profile_id": profile_id, "plan_source": settings["cc"]["plan_source"],
        "router_enabled": settings["cc"]["router"]["enabled"], "router_version": None,
        "model_route": settings["codex"]["route_id"], "library_snapshot_sha256": snapshot_ref["sha256"],
        "candidate_pins": pins, "verifier_cc_ref": copy.deepcopy(verifier_cc_ref),
        "invalid_for_product": True, "allowed_entry_points": ["E1", "E2", "E3"]}
    validate("evaluation-profile", profile)
    profile_ref = store.put_record("evaluation-profile", profile)
    new_settings = copy.deepcopy(settings)
    new_settings["cc"]["evaluation_profile_ref"] = profile_ref
    OperatorConfiguration.from_mapping(new_settings, resolve_profile=store.read_record)
    configuration_ref = store.put_blob(json_bytes(new_settings), media_type="application/json")
    new_binding = copy.deepcopy(binding)
    new_binding["configuration_ref"] = configuration_ref
    new_binding["protected_options"] = copy.deepcopy(new_binding["protected_options"])
    # Integrated-workflow bootstrap rejects every non-null evaluation profile.
    # Preserve the current policy pin and run through the ordinary research
    # path; a non-null evaluation profile is incompatible with the shortcuts.
    new_binding["protected_options"]["integrated_workflows"] = False
    new_binding["protected_options"]["paper_summary_workflow"] = False
    new_binding_ref = store.put_blob(json_bytes(new_binding), media_type="application/json")
    return {"operator_config": new_settings, "configuration_ref": configuration_ref,
        "profile_ref": profile_ref, "bootstrap_binding": new_binding,
        "bootstrap_binding_ref": new_binding_ref,
        "provenance": "captured before source run; invalid_for_product=true"}


def capture_evaluation_pilot_scope(store, *, current_operator, current_binding,
                                   profile_id, account_id, campaign_id,
                                   library_snapshot_ref, cases, requests):
    """Capture phase two: exact E2/E3 source assets, slots and startup binding.

    `cases` is a list of closed case descriptions with `case_id`, `entry_point`,
    `binding_ref`, and `assets` (path/role/artifact_ref rows). `requests` is a
    list of `{entry_point, request}` rows whose request names only those paths.
    Inputs and outputs must already be captured in the immutable run store.
    """
    settings = current_operator.snapshot() if hasattr(current_operator, "snapshot") else copy.deepcopy(current_operator)
    if type(settings) is not dict or set(settings) != {"schema_version", "cc", "rsi", "codex", "role_aliases"}:
        _fail("Pilot authoring needs the exact captured operator settings")
    binding = copy.deepcopy(current_binding)
    if type(binding) is not dict or not {"configuration_ref", "model_selection_profile_ref", "deployment_ref", "workspace_id", "protected_options"} <= set(binding):
        _fail("Pilot authoring needs the exact captured startup binding")
    options = binding["protected_options"]
    if type(options) is not dict or "resource_inventory_ref" not in options:
        _fail("Pilot authoring requires the current protected local profile")
    if any(options.get(key) is not None for key in ("evaluation_assets_ref", "evaluation_runtime_ref")):
        _fail("Pilot scope authoring requires its exact profile-only startup")
    profile_ref = settings["cc"].get("evaluation_profile_ref")
    if profile_ref is None or store.record_kind(profile_ref) != "evaluation-profile":
        _fail("Capture the evaluation profile and source run first")
    profile = store.read_record(profile_ref, contract_id="evaluation-profile")
    if (profile["profile_id"] != profile_id or profile["invalid_for_product"] is not True
            or profile["allowed_entry_points"] != ["E1", "E2", "E3"]):
        _fail("Pilot scope must use its pre-captured invalid-for-product E1/E2/E3 profile")
    if settings["cc"]["router"]["enabled"]:
        _fail("E2/E3 pilot requires the installed fixed-route evaluation runtime")
    try:
        captured_configuration = store.read_blob(binding["configuration_ref"])
    except ResearchError as error:
        raise ResearchError("evaluation_pilot", "Active operator configuration ref is unavailable") from error
    if captured_configuration != json_bytes(settings):
        _fail("Active operator settings differ from their captured immutable configuration ref")
    if not isinstance(profile_id, str) or not re.fullmatch(r"[a-z][a-z0-9_.:-]{0,63}", profile_id):
        _fail("Evaluation profile identity is invalid")
    if not isinstance(campaign_id, str) or not re.fullmatch(r"[a-z][a-z0-9_.:-]{0,63}", campaign_id):
        _fail("Evaluation campaign identity is invalid")
    snapshot_ref = _ref(store, library_snapshot_ref)
    snapshot = store.read_record(snapshot_ref, contract_id="library-snapshot")
    pins = profile["candidate_pins"]
    snapshot_entries = {(row["cc_name"], row["cc_version"], row["declaration_sha256"])
                        for row in snapshot["entries"]}
    for pin in pins:
        validate("CcPin", pin)
        if (pin["cc_name"], pin["cc_version"], pin["declaration_sha256"]) not in snapshot_entries:
            _fail("Candidate pin is not present in the exact installed snapshot")
    verifier = store.read_record(profile["verifier_cc_ref"], contract_id="capsule-declaration")
    verifier_pin = (verifier["identity"]["name"], verifier["identity"]["version_label"], profile["verifier_cc_ref"]["sha256"])
    if verifier_pin not in snapshot_entries:
        _fail("Independent verifier is not present in the exact installed snapshot")
    if profile["library_snapshot_sha256"] != snapshot_ref["sha256"]:
        _fail("Pilot scope snapshot differs from its pre-captured profile")
    if not isinstance(cases, list) or not cases or len(cases) > 8:
        _fail("Pilot case inventory must contain one to eight cases")
    configuration_ref = binding["configuration_ref"]

    entries, frozen_cases, case_by_key = [], [], {}
    seen_paths = set()
    for source in cases:
        if type(source) is not dict or set(source) != {"case_id", "entry_point", "binding_ref", "assets"}:
            _fail("Pilot case description has unknown or missing fields")
        case_id, entry_point, binding_ref = source["case_id"], source["entry_point"], _ref(store, source["binding_ref"])
        if entry_point not in profile["allowed_entry_points"] or not isinstance(case_id, str) or not case_id:
            _fail("Pilot case identity or entry point is invalid")
        if (case_id, entry_point) in case_by_key:
            _fail("Pilot case identity is duplicated")
        contract, replay = _source_contract(store, binding_ref, entry_point)
        if contract["configuration_ref"] != binding["configuration_ref"]:
            _fail("Pilot source contract belongs to a different operator configuration")
        if type(source["assets"]) is not list:
            _fail("Pilot frozen assets must be a list")
        for asset in source["assets"]:
            if type(asset) is not dict or set(asset) != {"path", "role", "artifact_ref"} or asset["role"] not in _ASSET_ROLES:
                _fail("Pilot asset has an unsupported role or shape")
            path, ref, role = _path(asset["path"]), _ref(store, asset["artifact_ref"]), asset["role"]
            if path in seen_paths:
                _fail("Pilot asset path is duplicated")
            seen_paths.add(path)
            entries.append({"path": path, "sha256": ref["sha256"], "artifact_ref": ref, "role": role})
        if entry_point == "E3":
            if len(contract["bindings"]) != 1:
                _fail("E3 source contract must bind exactly one capsule")
            actual = contract["bindings"][0]["declaration_ref"]
            declaration = store.read_record(actual, contract_id="capsule-declaration")
            pin = {"cc_name": declaration["identity"]["name"], "cc_version": declaration["identity"]["version_label"],
                   "declaration_sha256": actual["sha256"]}
            if pin not in pins:
                _fail("E3 source capsule is not an exact candidate pin")
            binding_paths = [e for e in entries if e["role"] == "binding" and e["artifact_ref"] == binding_ref]
            if not binding_paths:
                _fail("E3 needs its canonical source binding captured as an asset")
        else:
            if replay is None:
                _fail("E2 replay binding provenance is inconsistent")
            if replay.get("record_gate") is True:
                _fail("E2 pilot replay cannot publish a product gate")
        frozen_cases.append({"case_id": case_id, "entry_point": entry_point,
                             "binding_ref": binding_ref, "record_gate": False})
        case_by_key[(case_id, entry_point)] = (contract, replay, binding_ref)

    assets = {"schema": "ai4r-evaluation-assets:1", "id": "evaluation-assets:" + uuid.uuid4().hex,
        "profile_ref": profile_ref, "configuration_ref": configuration_ref,
        "account_id": account_id, "workspace_id": binding["workspace_id"],
        "campaign_id": campaign_id, "entries": entries, "cases": frozen_cases}
    if not all(isinstance(assets[k], str) and assets[k] for k in ("account_id", "workspace_id", "campaign_id")):
        _fail("Pilot identity must use current protected account/workspace values")

    if not isinstance(requests, list) or not requests or len(requests) > 16:
        _fail("Pilot schedule must contain one to sixteen finite requests")
    slots, templates, request_ids = [], [], set()
    for index, row in enumerate(requests):
        if type(row) is not dict or set(row) != {"entry_point", "request", "limits"}:
            _fail("Pilot scheduled request has unknown or missing fields")
        entry_point, request = row["entry_point"], copy.deepcopy(row["request"])
        case = case_by_key.get((request.get("case_id") if isinstance(request, dict) else None, entry_point))
        if case is None:
            _fail("Pilot request does not name one frozen case")
        if request.get("campaign_id") != campaign_id or request.get("evaluation_profile_id") != profile_id:
            _fail("Pilot request campaign/profile differs from its frozen closure")
        request = _request_shape(store, entry_point, request, entries,
            {"case_id": request["case_id"]}, case[0], case[1], case[2], profile)
        if entry_point == "E2":
            request.setdefault("host_records", [])
        if not isinstance(request.get("request_id"), str) or not request["request_id"] or request["request_id"] in request_ids:
            _fail("Pilot request IDs must be unique and nonempty")
        request_ids.add(request["request_id"])
        limits = row["limits"]
        if type(limits) is not dict or set(limits) != {"time_s", "model_calls", "memory_mb"}:
            _fail("Pilot request needs finite declared time, call and memory limits")
        contract, replay, _ = case
        if (type(limits["time_s"]) not in (int, float) or not math.isfinite(limits["time_s"])
                or limits["time_s"] <= 0 or type(limits["model_calls"]) is not int
                or limits["model_calls"] < 0 or type(limits["memory_mb"]) is not int or limits["memory_mb"] < 1):
            _fail("Pilot request limits are invalid")
        ceilings = {key: min(contract["subnode_limits"][key], contract["bindings"][0]["limits"][key])
                    for key in ("time_s", "model_calls", "memory_mb")}
        if any(limits[key] > ceilings[key] for key in ("time_s", "model_calls", "memory_mb")):
            _fail("Pilot slot limits exceed the exact captured source contract")
        request_hash = hashlib.sha256(json_bytes([entry_point, request])).hexdigest()
        slots.append({"slot_id": "pilot-slot-" + str(index + 1), "request_id": request["request_id"],
            "entry_point": entry_point, "case_id": request["case_id"], "config_id": profile_id,
            "repeat_index": index, "request_sha256": request_hash, "limits": copy.deepcopy(limits)})
        templates.append({"entry_point": entry_point, "request": request})
    assets_ref = store.append_record("evaluation-assets", assets)
    schedule_ref = store.put_blob(json_bytes(slots), media_type="application/json")
    base_options = binding["protected_options"]
    runtime = {"schema": "ai4r-evaluation-runtime:1", "id": "evaluation-runtime:" + uuid.uuid4().hex,
        "account_id": assets["account_id"], "workspace_id": assets["workspace_id"], "campaign_id": campaign_id,
        "profile_ref": profile_ref, "assets_ref": assets_ref, "configuration_ref": configuration_ref,
        "model_selection_profile_ref": copy.deepcopy(binding["model_selection_profile_ref"]),
        "deployment_ref": copy.deepcopy(binding["deployment_ref"]),
        "policy_ref": copy.deepcopy(settings["cc"]["plan_policy_ref"]),
        "library_snapshot_ref": snapshot_ref, "schedule_ref": schedule_ref, "slots": slots,
        "accepted": False, "invalid_for_product": True}
    validate("urn:ai4r:private:evaluation-runtime:1", runtime)
    runtime_ref = store.append_record("evaluation-runtime", runtime)
    new_binding = copy.deepcopy(binding)
    new_binding["configuration_ref"] = configuration_ref
    new_binding["protected_options"] = copy.deepcopy(base_options)
    new_binding["protected_options"]["integrated_workflows"] = False
    new_binding["protected_options"]["paper_summary_workflow"] = False
    new_binding["protected_options"].update(evaluation_assets_ref=assets_ref,
        evaluation_runtime_ref=runtime_ref, library_snapshot_ref=snapshot_ref)
    new_binding_ref = store.put_blob(json_bytes(new_binding), media_type="application/json")
    return {"operator_config": settings, "configuration_ref": configuration_ref,
        "profile_ref": profile_ref, "assets_ref": assets_ref, "runtime_ref": runtime_ref,
        "schedule_ref": schedule_ref, "bootstrap_binding": new_binding,
        "bootstrap_binding_ref": new_binding_ref, "requests": templates,
        "provenance": "captured refs only; isolated E2/E3; invalid_for_product=true"}
