"""V03 regressions for durable acceptance of resolved runtime evidence.

The real local runtime generates each complete record chain with its explicitly
labelled smoke adapter. Mutations occur at the protected precommit seam, after
generation/checking, and receive new exact hashes. Thus hash validity alone cannot
hide a failed obligation, stale scope or unobserved output from release authority.
"""
import copy
from dataclasses import replace

import pytest

from intent_compiler.config import Config
from intent_compiler.intake import qualify
from intent_compiler.runtime import Runtime, SmokeBridge
from intent_compiler.store import Store, StoreError


def prepared(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = Config(tmp_path / "state", inputs, auth_token="acceptance-fixture-only",
                    model_mode="smoke", profile_id="compiler-smoke")
    store = Store(config.state_dir)
    request = "Investigate retrieval latency and deliver a reproducible comparison report."
    run, _ = store.create_run("durable-acceptance-case", {"request": request},
                              config.account_id, config.workspace_id)
    qualified = qualify(config, store, run, request)
    store.update_run(run, qualified=qualified, status="queued", stage="qualified")
    return config, store, run


def _mutate_chain(store, run, scope, gate, contract_ref, mode):
    gate = copy.deepcopy(gate)

    def capture(kind, payload):
        return store.put_json(run, f"Challenge_{mode}_{kind}.json", payload,
                              artifact_type="protected-test-challenge")

    def observation(role, change):
        index = next(i for i, ref in enumerate(gate["invocation_refs"])
                     if store.get_json(run, ref)["subnode_id"] == role)
        payload = store.get_json(run, gate["invocation_refs"][index])
        change(payload)
        gate["invocation_refs"][index] = capture(role.replace(".", "_") + "_Observation", payload)

    if mode in {"failed_deterministic", "missing_deterministic", "wrong_deterministic_subject"}:
        payload = store.get_json(run, gate["deterministic_result_ref"])
        if mode == "failed_deterministic":
            payload["results"][0]["outcome"] = "FAIL"
        elif mode == "missing_deterministic":
            payload["results"].pop()
        else:
            payload["subject_ref"] = store.get_json(run, contract_ref)["input_refs"][0]
        gate["deterministic_result_ref"] = capture("Checks", payload)
    elif mode in {"stale_contract_run", "stale_parent", "unknown_port_contract"}:
        payload = store.get_json(run, contract_ref)
        if mode == "stale_contract_run":
            payload["run_id"] = "unrelated-run"
        elif mode == "unknown_port_contract":
            payload["inputs"][0]["contract_id"] = "unregistered-evidence:1.0.0"
        else:
            parent = store.get_json(run, payload["node_contract_ref"])
            parent["node_id"] = "unrelated-node"
            payload["node_contract_ref"] = capture("Unrelated_Parent", parent)
        contract_ref = capture("Contract", payload)
        gate["contract_ref"] = contract_ref
    elif mode in {"missing_finding", "stale_assessment_subject", "stale_assessment_context", "failed_assessment_finding"}:
        payload = store.get_json(run, gate["assessment_ref"])
        if mode == "missing_finding":
            payload["findings"].pop()
        elif mode == "stale_assessment_subject":
            payload["subject_ref"] = store.get_json(run, contract_ref)["input_refs"][0]
        elif mode == "stale_assessment_context":
            payload["review_context_ref"] = store.get_json(run, contract_ref)["input_refs"][0]
        else:
            payload["findings"][0]["outcome"] = "FAIL"
        gate["assessment_ref"] = capture("Assessment", payload)
        # Keep the observed output ref coherent so criterion/subject validation,
        # rather than an incidental stale hash, must reject this assessment.
        observation(scope + ".verifier", lambda value: value.update(output_refs=[gate["assessment_ref"]]))
    elif mode in {"unobserved_output", "wrong_observed_output", "failed_work", "unobserved_runtime", "missing_reviewer"}:
        if mode == "missing_reviewer":
            gate["invocation_refs"] = [ref for ref in gate["invocation_refs"]
                                       if store.get_json(run, ref)["subnode_id"] == scope]
        else:
            def change(value):
                if mode == "unobserved_output":
                    value["output_refs"] = []
                elif mode == "wrong_observed_output":
                    value["output_refs"] = store.get_json(run, contract_ref)["input_refs"]
                elif mode == "failed_work":
                    value["outcome"] = "failed"
                else:
                    value["observed_runtime"] = False
            observation(scope, change)
    elif mode == "node_assessment_changed":
        # Even a structurally identical newly named record is not the exact
        # Requirements assessment committed by the internal gate.
        gate["assessment_ref"] = capture("Other_Assessment", store.get_json(run, gate["assessment_ref"]))
    elif mode == "node_wrong_observed_output":
        # Internal acceptance committed a particular observation. A newly
        # captured same-role observation must not replace it at node release,
        # even when every hash resolves and the role/parent fields agree.
        observation("requirements", lambda value: value.update(
            output_refs=store.get_json(run, contract_ref)["input_refs"]))
    else:
        raise AssertionError("Unknown test mutation")
    return capture("Gate", gate), contract_ref


@pytest.mark.parametrize("mode", [
    "failed_deterministic", "missing_deterministic", "wrong_deterministic_subject",
    "stale_contract_run", "stale_parent", "unknown_port_contract",
    "missing_finding", "stale_assessment_subject", "stale_assessment_context", "failed_assessment_finding",
    "unobserved_output", "wrong_observed_output", "failed_work", "unobserved_runtime", "missing_reviewer",
    "node_assessment_changed", "node_wrong_observed_output",
])
def test_durable_acceptance_rejects_hash_valid_false_gate(tmp_path, monkeypatch, mode):
    config, store, run = prepared(tmp_path)
    original = store.accept
    target_scope = "node" if mode.startswith("node_") else "intention"
    rejections = []

    def challenged(run_id, scope, subject_ref, gate_ref, contract_ref):
        if scope != target_scope:
            return original(run_id, scope, subject_ref, gate_ref, contract_ref)
        gate_ref, contract_ref = _mutate_chain(store, run_id, scope,
                                               store.get_json(run_id, gate_ref), contract_ref, mode)
        try:
            return original(run_id, scope, subject_ref, gate_ref, contract_ref)
        except StoreError as error:
            rejections.append(str(error))
            raise

    monkeypatch.setattr(store, "accept", challenged)
    bridge = SmokeBridge()
    status = Runtime(config, store, bridge).run(run)
    assert rejections, "Durable authority accepted a false gate with valid captured hashes"
    assert status["status"] == "halted", status
    assert store.accepted(run, target_scope) is None
    assert store.accepted(run, "node") is None
    if target_scope == "intention":
        assert bridge.calls == ["intention", "intention.verifier"]
        assert store.accepted(run, "requirements") is None
    else:
        assert len(bridge.calls) == 4
        assert store.accepted(run, "requirements") is not None


def test_valid_smoke_chain_has_exact_transaction_and_assessment_reuse(tmp_path):
    config, store, run = prepared(tmp_path)
    status = Runtime(config, store, SmokeBridge()).run(run)
    assert status["status"] == "completed", status
    subject = store.accepted(run, "node")
    assert subject == store.accepted(run, "requirements")
    record_ref = store.acceptance_record(run, "node")
    record = store.get_json(run, record_ref)
    gate = store.get_json(run, record["gate_ref"])
    assert record["output_refs"] == [subject]
    assert record["subnode_id"] is None and record["commit_id"]
    requirements_record = store.get_json(run, store.acceptance_record(run, "requirements"))
    requirements_gate = store.get_json(run, requirements_record["gate_ref"])
    assert gate["assessment_ref"] == requirements_gate["assessment_ref"]
    assert record["gate_ref"] == status["decision_ref"]
    assert store.get_json(run, subject)["schema_version"] == "2.0.0"


@pytest.mark.parametrize("input_tokens,output_tokens", [(20, 20), (None, None), (True, 0), (-1, 0)])
def test_durable_acceptance_enforces_configured_observed_token_bound(
        tmp_path, monkeypatch, input_tokens, output_tokens):
    config, store, run = prepared(tmp_path)
    config = replace(config, token_budget=10)

    class KnownUsageBridge(SmokeBridge):
        def invoke(self, **kwargs):
            result = super().invoke(**kwargs)
            result.usage.update(input_tokens=0, output_tokens=0)
            return result

    original = store.accept
    rejections = []

    def challenged(run_id, scope, subject_ref, gate_ref, contract_ref):
        if scope != "intention":
            return original(run_id, scope, subject_ref, gate_ref, contract_ref)
        gate = store.get_json(run_id, gate_ref)
        reviewer = store.get_json(run_id, gate["invocation_refs"][1])
        reviewer["usage"].update(input_tokens=input_tokens, output_tokens=output_tokens)
        gate["invocation_refs"][1] = store.put_json(run_id, "Challenge_Bounded_Reviewer.json", reviewer)
        gate_ref = store.put_json(run_id, "Challenge_Bounded_Gate.json", gate)
        try:
            return original(run_id, scope, subject_ref, gate_ref, contract_ref)
        except StoreError as error:
            rejections.append(str(error))
            raise

    monkeypatch.setattr(store, "accept", challenged)
    bridge = KnownUsageBridge()
    status = Runtime(config, store, bridge).run(run)
    assert rejections, "Durable authority ignored its configured observed token limit"
    assert status["status"] == "halted", status
    assert store.accepted(run, "intention") is None
    assert store.accepted(run, "node") is None
    assert bridge.calls == ["intention", "intention.verifier"]


def test_requirements_budget_includes_durably_accepted_intent_reviewer(tmp_path, monkeypatch):
    config, store, run = prepared(tmp_path)
    config = replace(config, token_budget=20)

    class KnownUsageBridge(SmokeBridge):
        def invoke(self, **kwargs):
            result = super().invoke(**kwargs)
            result.usage.update(input_tokens=0, output_tokens=0)
            return result

    original = store.accept
    rejected = []

    def challenged(run_id, scope, subject_ref, gate_ref, contract_ref):
        if scope == "node":
            return original(run_id, scope, subject_ref, gate_ref, contract_ref)
        gate = store.get_json(run_id, gate_ref)
        reviewer = store.get_json(run_id, gate["invocation_refs"][1])
        # Every isolated stage is below20, but aggregate reviewer spend is24.
        quantity = 8 if scope == "intention" else 4
        reviewer["usage"].update(input_tokens=quantity, output_tokens=quantity)
        gate["invocation_refs"][1] = store.put_json(run_id, f"Challenge_{scope}_Aggregate_Reviewer.json", reviewer)
        gate_ref = store.put_json(run_id, f"Challenge_{scope}_Aggregate_Gate.json", gate)
        try:
            return original(run_id, scope, subject_ref, gate_ref, contract_ref)
        except StoreError as error:
            rejected.append((scope, str(error)))
            raise

    monkeypatch.setattr(store, "accept", challenged)
    bridge = KnownUsageBridge()
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted", status
    assert store.accepted(run, "intention") is not None
    assert rejected and rejected[0][0] == "requirements", rejected
    assert store.accepted(run, "requirements") is None
    assert store.accepted(run, "node") is None
    assert len(bridge.calls) == 4


def test_valid_bounded_usage_includes_all_four_roles_and_node_release(tmp_path):
    config, store, run = prepared(tmp_path)
    config = replace(config, token_budget=8)

    class KnownUsageBridge(SmokeBridge):
        def invoke(self, **kwargs):
            result = super().invoke(**kwargs)
            result.usage.update(input_tokens=1, output_tokens=1)
            return result

    bridge = KnownUsageBridge()
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "completed", status
    assert len(bridge.calls) == 4
    assert store.accepted(run, "node") == store.accepted(run, "requirements")
    released = store.get_json(run, store.acceptance_record(run, "node"))
    gate = store.get_json(run, released["gate_ref"])
    counts = [store.get_json(run, ref)["usage"] for ref in gate["invocation_refs"]]
    assert sum(usage["input_tokens"] + usage["output_tokens"] for usage in counts) == 8
