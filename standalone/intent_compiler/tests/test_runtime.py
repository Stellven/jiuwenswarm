"""Architecture-derived connected runtime challenges; model fixture labels explicit."""
import json
from pathlib import Path

import pytest

from intent_compiler.config import Config
from intent_compiler.intake import qualify
from intent_compiler.model import ModelResult, unavailable_usage
from intent_compiler.runtime import Runtime, SmokeBridge, _schema
from intent_compiler.store import Store, StoreError


def prepared(tmp_path, **settings):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = Config(tmp_path / "state", inputs, auth_token="test-token", model_mode="smoke", profile_id="compiler-smoke", **settings)
    store = Store(config.state_dir)
    run, _ = store.create_run("one", {"request": "Study latency and return an evidence-grounded report."}, config.account_id, config.workspace_id)
    qualified = qualify(config, store, run, "Study latency and return an evidence-grounded report.")
    store.update_run(run, qualified=qualified, status="queued", stage="qualified")
    return config, store, run


class MutatedBridge(SmokeBridge):
    def __init__(self, role, mutate):
        super().__init__()
        self.role, self.mutate = role, mutate

    def invoke(self, **kwargs):
        result = super().invoke(**kwargs)
        if kwargs["role"] == self.role:
            result = self.mutate(result, kwargs)
        return result


def changed(result, change):
    payload = json.loads(result.text)
    change(payload)
    result.text = result.raw_stdout = json.dumps(payload)
    return result


def test_whole_node_four_calls_three_decisions_and_exact_consumer(tmp_path):
    config, store, run = prepared(tmp_path)
    bridge = SmokeBridge()
    runtime = Runtime(config, store, bridge)
    status = runtime.run(run)
    assert status["status"] == "completed", status
    assert bridge.calls == ["intention", "intention.verifier", "requirements", "requirements.verifier"]
    assert store.accepted(run, "intention")["id"] == "Intent_IR.json"
    assert store.accepted(run, "requirements") == store.accepted(run, "node")
    assert runtime.consume(run)["schema_version"] == "2.0.0"
    node = store.get_json(run, "Gate_Node.json")
    assert node["scope_kind"] == "node" and node["subnode_id"] is None
    assert len(node["invocation_refs"]) == 4 and len(node["internal_decision_refs"]) == 2
    assert store.get_run(run)["invalid_for_product"] is True
    contract = store.get_json(run, "requirements_Subnode_Contract.json")
    assert contract["input_refs"][0] == store.accepted(run, "intention")
    with pytest.raises(RuntimeError, match="replay"):
        runtime.run(run)


@pytest.mark.parametrize("mode", ["invalid_json", "wrong_version", "bad_span", "unknown_ref", "duplicate_id", "no_output", "timeout", "oversized"])
def test_bad_intent_avoids_verifier_and_requirements(tmp_path, mode):
    config, store, run = prepared(tmp_path)
    def mutation(result, _):
        if mode == "invalid_json":
            result.text = "{"
        elif mode == "no_output":
            result.text, result.outcome = None, "no_output"
        elif mode == "timeout":
            result.outcome, result.error = "timeout", "Frozen call timeout"
        elif mode == "oversized":
            result.text = "x" * (config.max_output_bytes + 1)
        else:
            def alter(payload):
                if mode == "wrong_version": payload["schema_version"] = "0.1"
                if mode == "bad_span": payload["in_scope"][0]["source_spans"][0]["end"] = 9999
                if mode == "unknown_ref": payload["request_ref"]["sha256"] = "0" * 64
                if mode == "duplicate_id": payload["in_scope"][0]["id"] = "problem"
            changed(result, alter)
        return result
    bridge = MutatedBridge("intention", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted", status
    assert bridge.calls == ["intention"]
    assert store.accepted(run, "node") is None
    gate = store.get_json(run, "Gate_Intention.json")
    assert gate["assessment_ref"] is None and gate["action"] == "halt"
    if mode in ("no_output", "oversized"):
        assert gate["output_refs"] == []
        assert store.get_json(run, "Intention_Failure_Receipt.json")["outputs"] == []


@pytest.mark.parametrize("mode", ["missing", "duplicate", "stale_subject", "stale_context", "unknown_evidence", "malformed", "semantic_fail", "inconclusive"])
def test_assessment_fail_closed_despite_overall_pass(tmp_path, mode):
    config, store, run = prepared(tmp_path)
    def mutation(result, _):
        def alter(payload):
            if mode == "missing": payload["findings"].pop()
            if mode == "duplicate": payload["findings"].append(payload["findings"][0])
            if mode == "stale_subject": payload["subject_ref"]["sha256"] = "0" * 64
            if mode == "stale_context": payload["review_context_ref"]["sha256"] = "0" * 64
            if mode == "unknown_evidence": payload["findings"][0]["evidence_refs"][0]["id"] = "unprovided"
            if mode in ("semantic_fail", "inconclusive"):
                value = "FAIL" if mode == "semantic_fail" else "INCONCLUSIVE"
                payload["verdict"] = value
                payload["findings"][0]["outcome"] = value
        if mode == "malformed": result.text = "invalid"
        else: changed(result, alter)
        return result
    bridge = MutatedBridge("intention.verifier", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted", status
    assert bridge.calls == ["intention", "intention.verifier"]
    assert store.accepted(run, "intention") is None and store.accepted(run, "node") is None
    assert status["candidate_refs"][0]["id"] == "Intent_IR.json"


def test_topic_uncertainty_needs_semantic_review_then_halts(tmp_path):
    config, store, run = prepared(tmp_path)
    def mutation(result, _):
        return changed(result, lambda payload: payload.update(readiness={"status": "needs_clarification", "reason": "Unknown requested purpose"}))
    bridge = MutatedBridge("intention", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted"
    assert bridge.calls == ["intention", "intention.verifier"]
    assert store.accepted(run, "intention") is None


def test_requirement_semantic_loss_does_not_release(tmp_path):
    config, store, run = prepared(tmp_path)
    def mutation(result, _):
        return changed(result, lambda payload: payload.update(verdict="FAIL", findings=[dict(f, outcome="FAIL", reason="User constraint omitted") for f in payload["findings"]]))
    bridge = MutatedBridge("requirements.verifier", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert len(bridge.calls) == 4 and status["status"] == "halted"
    assert store.accepted(run, "intention") is not None and store.accepted(run, "requirements") is None
    assert store.accepted(run, "node") is None


def test_storage_failure_after_pass_never_publishes(tmp_path, monkeypatch):
    config, store, run = prepared(tmp_path)
    original = store.accept
    def broken(run_id, scope, *args):
        if scope == "node": raise StoreError("Injected durable node commit failure")
        return original(run_id, scope, *args)
    monkeypatch.setattr(store, "accept", broken)
    status = Runtime(config, store).run(run)
    assert status["status"] == "halted"
    assert store.accepted(run, "requirements") is not None
    assert store.accepted(run, "node") is None
    with pytest.raises(RuntimeError, match="No committed"):
        Runtime(config, store).consume(run)


def test_cancel_during_work_stops_review_dispatch(tmp_path):
    config, store, run = prepared(tmp_path)
    def mutation(result, _):
        store.request_cancel(run, "cancel1")
        return result
    bridge = MutatedBridge("intention", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "cancelled" and bridge.calls == ["intention"]
    assert store.accepted(run, "node") is None


def test_observed_token_overrun_blocks_successor(tmp_path):
    config, store, run = prepared(tmp_path, token_budget=10)
    def mutation(result, _):
        result.usage = {**unavailable_usage(), "input_tokens": 10, "output_tokens": 5}
        return result
    bridge = MutatedBridge("intention", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted" and bridge.calls == ["intention"]
    assert "token spend" in status["reasons"][0]


def test_preserves_unknown_telemetry_and_actual_admission_dependency_pins(tmp_path):
    config, store, run = prepared(tmp_path)
    runtime = Runtime(config, store)
    assert runtime.run(run)["status"] == "completed"
    observation = store.get_json(run, "intention_Invocation_Observation.json")
    assert observation["usage"]["cost_amount"] is None
    assert observation["usage"]["input_tokens"] is None
    assert observation["observed_runtime"] is True
    admission = store.get_json(run, "intention_Admission.json")
    assert admission["invalid_for_product"] is True
    assert len(admission["dependency_refs"]) >= 3
    for ref in admission["implementation_refs"] + admission["dependency_refs"]:
        store.read_bytes(run, ref)


def test_restart_pauses_and_forbids_inplace_replay(tmp_path):
    config, store, run = prepared(tmp_path)
    store.update_run(run, status="running")
    reopened = Store(config.state_dir)
    reopened.pause_interrupted()
    assert reopened.get_run(run)["status"] == "paused"
    with pytest.raises(RuntimeError, match="replay"):
        Runtime(config, reopened).run(run)


@pytest.mark.parametrize("role", ["intention.verifier", "requirements.verifier"])
def test_observed_verifier_token_overrun_never_commits_or_dispatches(tmp_path, role):
    config, store, run = prepared(tmp_path, token_budget=10)
    def mutation(result, _):
        result.usage = {**unavailable_usage(), "input_tokens": 20, "output_tokens": 20}
        return result
    class BudgetBridge(MutatedBridge):
        def invoke(self, **kwargs):
            result = super().invoke(**kwargs)
            if kwargs["role"] != role:
                result.usage = {**unavailable_usage(), "input_tokens": 1, "output_tokens": 1}
            return result
    bridge = BudgetBridge(role, mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted" and "token spend" in status["reasons"][0]
    assert bridge.calls[-1] == role and store.accepted(run, "node") is None
    assert store.accepted(run, role.split(".")[0]) is None


@pytest.mark.parametrize("usage", [None, {"input_tokens": True, "output_tokens": 1}, {"input_tokens": -1, "output_tokens": 1}])
def test_selected_token_bound_fails_closed_when_actual_usage_unavailable(tmp_path, usage):
    config, store, run = prepared(tmp_path, token_budget=100)
    def mutation(result, _):
        if usage is not None:
            result.usage = {**unavailable_usage(), **usage}
        return result
    bridge = MutatedBridge("intention", mutation)
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted" and bridge.calls == ["intention"]
    assert store.accepted(run, "node") is None


@pytest.mark.parametrize("kind", ["inactive", "dependency", "body", "authority", "template"])
def test_binding_rejects_changed_admission_template_or_authority_before_model(tmp_path, monkeypatch, kind):
    config, store, run = prepared(tmp_path)
    original = store.get_json
    def read(run_id, ref):
        payload = original(run_id, ref)
        identity = ref["id"] if isinstance(ref, dict) else ref
        if identity == "intention_Admission.json":
            if kind == "inactive": payload["status"] = "inactive"
            if kind == "dependency": payload["dependency_refs"] = []
            if kind == "body": payload["implementation_refs"] = payload["dependency_refs"][:1]
            if kind == "authority": payload["authority"]["tools"] = []
        if identity == "intention_Template.json" and kind == "template":
            payload["input_ports"][0]["name"] = "other"
        return payload
    monkeypatch.setattr(store, "get_json", read)
    bridge = SmokeBridge()
    status = Runtime(config, store, bridge).run(run)
    assert status["status"] == "halted" and bridge.calls == []
    assert store.accepted(run, "node") is None


def test_no_external_resource_read_grants_and_transport_preserves_full_host_validation(tmp_path):
    config, store, run = prepared(tmp_path)
    assert Runtime(config, store).run(run)["status"] == "completed"
    node = store.get_json(run, "Intention_Node_Contract.json")
    assert node["authority_ceiling"]["resource_reads"] == []
    for role in ("intention", "intention_verifier", "requirements", "requirements_verifier"):
        contract = store.get_json(run, role + "_Subnode_Contract.json")
        assert contract["bindings"][0]["effective_authority"]["resource_reads"] == []
        assert contract["input_refs"]
    schema = _schema("research-brief")
    assert "ext" not in schema["properties"] and "allOf" not in schema["properties"]["constraints"]["items"]
    brief = Runtime(config, store).consume(run)
    brief["constraints"][0]["operator"] = "qualitative"
    from intent_compiler.checks import schema_errors
    assert schema_errors("research-brief", brief), "Transport adaptation never weakens authoritative validation"


def test_operator_evaluation_profile_labels_all_internal_admissions(tmp_path):
    from dataclasses import replace
    config, store, run = prepared(tmp_path)
    config = replace(config, model_mode="codex", profile_id="compiler-evaluation")
    bridge = SmokeBridge()
    bridge.synthetic = False
    assert Runtime(config, store, bridge).run(run)["status"] == "completed"
    for role in ("intention", "intention_verifier", "requirements", "requirements_verifier"):
        assert store.get_json(run, role + "_Admission.json")["invalid_for_product"] is True
    assert store.get_run(run)["invalid_for_product"] is True
