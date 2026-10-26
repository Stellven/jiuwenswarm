"""Evaluation pilot capture joins actual source contracts without live model calls."""
import copy

import pytest

from jiuwenswarm.research.evaluation_pilot import (
    capture_evaluation_pilot_profile,
    capture_evaluation_pilot_scope,
)
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.operator_config import OperatorConfiguration
from jiuwenswarm.research.state import json_bytes


async def _prepared_source(tmp_path):
    from tests.unit_tests.research.test_evaluation_authority import source_fixture
    store, provider, actor, _, _ = await source_fixture(tmp_path)
    resources = provider.resources
    admitted = resources.admitted
    settings = admitted.resources.operator.snapshot()
    settings["cc"]["evaluation_profile_ref"] = None
    base_configuration = store.put_blob(json_bytes(settings), media_type="application/json")
    snapshot_ref = resources.snapshot_ref
    original_contract_ref = provider.assets["cases"][0]["binding_ref"]
    original_contract = store.read_record(original_contract_ref, contract_id="subnode-execution-contract")
    declaration_ref = original_contract["bindings"][0]["declaration_ref"]
    declaration = store.read_record(declaration_ref, contract_id="capsule-declaration")
    verifier_ref = admitted.resources.composition.installed["verifier"]["declaration_ref"]
    binding = {
        **admitted.resources.exact_binding_refs,
        "configuration_ref": base_configuration,
        "workspace_id": provider.assets["workspace_id"],
        "protected_options": {"resource_inventory_ref": store.put_record(
            "resource-inventory", {"schema_version": "1.0.0", "id": "pilot-empty-inventory", "resources": []})},
    }
    pin = {"cc_name": declaration["identity"]["name"],
           "cc_version": declaration["identity"]["version_label"],
           "declaration_sha256": declaration_ref["sha256"]}
    prepared = capture_evaluation_pilot_profile(store,
        current_operator=settings, current_binding=binding, profile_id="pilot-ml",
        candidate_pins=[pin], verifier_cc_ref=verifier_ref,
        library_snapshot_ref=snapshot_ref)

    # The source contracts are recaptured under the exact phase-one config ref.
    contract = copy.deepcopy(original_contract)
    parent = store.read_record(contract["node_contract_ref"], contract_id="node-execution-contract")
    parent["configuration_ref"] = prepared["configuration_ref"]
    parent_ref = store.put_record("node-execution-contract", parent, record_id="pilot-parent")
    contract["configuration_ref"] = prepared["configuration_ref"]
    contract["node_contract_ref"] = parent_ref
    contract_ref = store.put_record("subnode-execution-contract", contract, record_id="pilot-source")
    check_ref = next(row["ref"] for row in store.iter_records(kinds=("bound-check-plan",))
                     if row["record"]["contract_ref"] == original_contract_ref)
    checks = store.read_record(check_ref)
    checks["contract_ref"] = contract_ref
    checks["node_contract_ref"] = parent_ref
    checks_ref = store.put_record("bound-check-plan", checks, record_id="pilot-source-checks")

    # source_fixture has an actual admitted source owner and a controlled test
    # subscription. Reuse it; no external/live model call is made.
    resources.admitted.resources.operator = OperatorConfiguration.from_mapping(
        prepared["operator_config"], resolve_profile=store.read_record)
    resources.admitted.resources.exact_binding_refs["configuration_ref"] = prepared["configuration_ref"]
    original = await admitted.execute(admitted.prepare(contract_ref, checks_ref, semantic_review=False))
    assert original.status == "completed" and original.observation_ref
    return store, provider, actor, prepared, contract_ref, checks_ref, original, pin, verifier_ref


def _case_closures(store, provider, contract_ref, original, verifier_ref):
    contract = store.read_record(contract_ref, contract_id="subnode-execution-contract")
    declaration_ref = contract["bindings"][0]["declaration_ref"]
    verifier_pin = provider.resources.admitted.resources.composition.installed["verifier"]["pin"]
    verifier_id = verifier_pin["cc_name"] + "@" + verifier_pin["cc_version"]
    replay_binding = store.append_record("evaluation-case-binding", {
        "schema": "ai4r-node-replay-binding:2", "id": "pilot-replay-binding",
        "contract_ref": contract_ref, "check_plan_ref": contract["check_plan_ref"] if "check_plan_ref" in contract else
            next(row["ref"] for row in store.iter_records(kinds=("bound-check-plan",))
                 if row["record"]["contract_ref"] == contract_ref),
        "output_refs": original.output_refs, "original_observation_ref": original.observation_ref,
        "verifier_cc_id": verifier_id, "host_records": [], "selected_output_port": "screening_result"})
    inputs = []
    e3_assets = [{"path": "e3/binding.json", "role": "binding", "artifact_ref": contract_ref}]
    for port in contract["inputs"]:
        for index, ref in enumerate(port["artifact_refs"]):
            path = f"e3/{port['name']}-{index}.json"
            e3_assets.append({"path": path, "role": "input", "artifact_ref": ref})
            inputs.append({"port": port["name"], "path": path, "sha256": ref["sha256"]})
    e3_assets.append({"path": "e3/declaration.json", "role": "declaration", "artifact_ref": declaration_ref})
    e3_case = {"case_id": "fresh-screening", "entry_point": "E3", "binding_ref": contract_ref, "assets": e3_assets}
    e3_request = {"request_id": "pilot-e3-1", "campaign_id": "pilot-campaign", "case_id": "fresh-screening",
        "evaluation_profile_id": "pilot-ml", "capsule_id": "pending",
        "capsule_version": "pending", "capsule_declaration_sha256": declaration_ref["sha256"],
        "binding": {"path": "e3/binding.json", "sha256": contract_ref["sha256"]},
        "inputs": inputs, "model_route": "codex-cli-default"}
    declaration_record = store.read_record(declaration_ref, contract_id="capsule-declaration")
    e3_request["capsule_id"] = declaration_record["identity"]["name"]
    e3_request["capsule_version"] = declaration_record["identity"]["version_label"]

    output_ref = original.output_refs["screening_result"]
    e2_assets = [
        {"path": "e2/declaration.json", "role": "declaration", "artifact_ref": declaration_ref},
        {"path": "e2/output.json", "role": "output", "artifact_ref": output_ref},
    ]
    e2_case = {"case_id": "source-screening", "entry_point": "E2", "binding_ref": replay_binding, "assets": e2_assets}
    e2_request = {"request_id": "pilot-e2-1", "campaign_id": "pilot-campaign", "case_id": "source-screening",
        "evaluation_profile_id": "pilot-ml", "verifier_cc_id": verifier_id,
        "declaration": {"path": "e2/declaration.json", "sha256": declaration_ref["sha256"]},
        "output": {"path": "e2/output.json", "sha256": output_ref["sha256"]},
        "node_id": contract["node_id"], "host_records": []}
    return [e3_case, e2_case], [
        {"entry_point": "E3", "request": e3_request, "limits": _limits(contract)},
        {"entry_point": "E2", "request": e2_request, "limits": _limits(contract)},
    ], replay_binding


def _limits(contract):
    return {key: min(contract["subnode_limits"][key], contract["bindings"][0]["limits"][key])
            for key in ("time_s", "model_calls", "memory_mb")}


@pytest.mark.asyncio
async def test_profile_then_captured_source_produces_e2_e3_startup_closure(tmp_path):
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider, InstalledEvaluationResources

    store, provider, actor, prepared, contract_ref, _, original, _, verifier_ref = await _prepared_source(tmp_path)
    cases, requests, _ = _case_closures(store, provider, contract_ref, original, verifier_ref)
    current_binding = prepared["bootstrap_binding"]
    result = capture_evaluation_pilot_scope(store, current_operator=prepared["operator_config"],
        current_binding=current_binding, profile_id="pilot-ml", account_id=provider.assets["account_id"],
        campaign_id="pilot-campaign", library_snapshot_ref=provider.resources.snapshot_ref,
        cases=cases, requests=requests)
    assert result["configuration_ref"] == prepared["configuration_ref"]
    assert result["profile_ref"] == prepared["profile_ref"]
    assert result["bootstrap_binding"]["protected_options"]["integrated_workflows"] is False
    assert result["bootstrap_binding"]["protected_options"]["paper_summary_workflow"] is False
    assert result["operator_config"]["cc"]["plan_policy_ref"] == prepared["operator_config"]["cc"]["plan_policy_ref"]
    assert result["bootstrap_binding"]["protected_options"]["evaluation_runtime_ref"] == result["runtime_ref"]
    assert store.read_record(result["profile_ref"], contract_id="evaluation-profile")["invalid_for_product"] is True
    from jiuwenswarm.research.evaluation_projection import private_record
    runtime = private_record(store, result["runtime_ref"], "evaluation-runtime")
    assert runtime["assets_ref"] == result["assets_ref"] and len(runtime["slots"]) == 2
    assets = store.read_record(result["assets_ref"])
    resources = InstalledEvaluationResources(provider.resources.admitted, profile_ref=result["profile_ref"],
        assets_ref=result["assets_ref"], library_snapshot_ref=provider.resources.snapshot_ref)
    pilot = EvaluationProvider(store, provider.resources.admitted.resources.operator,
        assets_ref=result["assets_ref"], resources=resources, library=provider.resources.admitted.library)
    resources.bind_runtime(result["runtime_ref"])
    assert set(pilot.available_entry_points) == {"E2", "E3"}, resources.unavailable_reasons
    for case in cases:
        req = next(row["request"] for row in result["requests"] if row["request"]["case_id"] == case["case_id"])
        pilot._validate(actor, req, case["entry_point"])
    assert assets["cases"] == [{"case_id": case["case_id"], "entry_point": case["entry_point"],
        "binding_ref": case["binding_ref"], "record_gate": False} for case in cases]
    assert not list(store.iter_records(kinds=("gate-decision", "acceptance-commit")))
    store.close()


@pytest.mark.asyncio
async def test_pilot_rejects_foreign_configuration_and_tampered_output_or_host_closure(tmp_path):
    store, provider, _, prepared, contract_ref, _, original, _, verifier_ref = await _prepared_source(tmp_path)
    cases, requests, replay_binding = _case_closures(store, provider, contract_ref, original, verifier_ref)
    foreign_cases = copy.deepcopy(cases)
    foreign_contract = store.read_record(contract_ref, contract_id="subnode-execution-contract")
    foreign_contract["configuration_ref"] = store.put_blob(b"another captured configuration")
    foreign_cases[0]["binding_ref"] = store.put_record("subnode-execution-contract", foreign_contract,
                                                         record_id="pilot-foreign-config-source")
    with pytest.raises(ResearchError, match="source contract"):
        capture_evaluation_pilot_scope(store, current_operator=prepared["operator_config"],
            current_binding=prepared["bootstrap_binding"], profile_id="pilot-ml", account_id=provider.assets["account_id"],
            campaign_id="pilot-campaign", library_snapshot_ref=provider.resources.snapshot_ref,
            cases=foreign_cases, requests=requests)
    bad_output_cases = copy.deepcopy(cases)
    bad_output_cases[1]["assets"][1]["artifact_ref"] = store.put_blob(b"different output")
    bad_output_requests = copy.deepcopy(requests)
    bad_output_requests[1]["request"]["output"]["sha256"] = bad_output_cases[1]["assets"][1]["artifact_ref"]["sha256"]
    with pytest.raises(ResearchError, match="original port bytes"):
        capture_evaluation_pilot_scope(store, current_operator=prepared["operator_config"],
            current_binding=prepared["bootstrap_binding"], profile_id="pilot-ml",
            account_id=provider.assets["account_id"], campaign_id="pilot-campaign",
            library_snapshot_ref=provider.resources.snapshot_ref, cases=bad_output_cases, requests=bad_output_requests)
    bad_hosts = copy.deepcopy(cases)
    bad_hosts[1]["assets"].append({"path": "e2/host.json", "role": "host_runtime_observation",
                                    "artifact_ref": store.put_blob(b"not the original host record")})
    bad_requests = copy.deepcopy(requests)
    bad_requests[1]["request"]["host_records"] = [{"record_type": "runtime_observation",
        "path": "e2/host.json", "sha256": bad_hosts[1]["assets"][-1]["artifact_ref"]["sha256"]}]
    with pytest.raises(ResearchError, match="original captured replay"):
        capture_evaluation_pilot_scope(store, current_operator=prepared["operator_config"],
            current_binding=prepared["bootstrap_binding"], profile_id="pilot-ml",
            account_id=provider.assets["account_id"], campaign_id="pilot-campaign",
            library_snapshot_ref=provider.resources.snapshot_ref, cases=bad_hosts, requests=bad_requests)
    store.close()


@pytest.mark.asyncio
async def test_pilot_rejects_changed_or_duplicate_finite_slots_and_preserves_prior_refs(tmp_path):
    store, provider, _, prepared, contract_ref, _, original, _, verifier_ref = await _prepared_source(tmp_path)
    cases, requests, _ = _case_closures(store, provider, contract_ref, original, verifier_ref)
    previous = list(store.iter_records())
    duplicate = copy.deepcopy(requests)
    duplicate[1]["request"]["request_id"] = duplicate[0]["request"]["request_id"]
    with pytest.raises(ResearchError, match="request IDs"):
        capture_evaluation_pilot_scope(store, current_operator=prepared["operator_config"],
            current_binding=prepared["bootstrap_binding"], profile_id="pilot-ml",
            account_id=provider.assets["account_id"], campaign_id="pilot-campaign",
            library_snapshot_ref=provider.resources.snapshot_ref, cases=cases, requests=duplicate)
    changed = copy.deepcopy(requests)
    changed[0]["request"]["model_route"] = "different-route"
    with pytest.raises(ResearchError, match="source capsule declaration"):
        capture_evaluation_pilot_scope(store, current_operator=prepared["operator_config"],
            current_binding=prepared["bootstrap_binding"], profile_id="pilot-ml",
            account_id=provider.assets["account_id"], campaign_id="pilot-campaign",
            library_snapshot_ref=provider.resources.snapshot_ref, cases=cases, requests=changed)
    previous_by_ref = {json_bytes(row["ref"]): row["record"] for row in previous}
    current_by_ref = {json_bytes(row["ref"]): row["record"] for row in store.iter_records()}
    assert all(current_by_ref.get(ref) == record for ref, record in previous_by_ref.items())
    store.close()
