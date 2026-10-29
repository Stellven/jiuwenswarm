"""Connected controlled routing/bridge/storage; no live endpoint qualification.

Expected transitions come from model-routing-contract.md:47-55,75-88,124,213
and router-design.md:71. The selector reply and deployment availability are
explicit test inputs, not operational grants or evidence of model quality.
"""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import json
import multiprocessing
import os
from pathlib import Path
from time import monotonic

import pytest

from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
from jiuwenswarm.research.contracts import ContractError, Principal, ResearchError, validate
from jiuwenswarm.research.router_client import PlatformIntegrityError, RouterPort
from jiuwenswarm.research.providers import ProviderError
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.test_bridge import authorized_context


class Captures:
    def __init__(self, root, *, advance=None):
        self.store = SQLiteRunStore(root)
        self.records = []
        self.advance = advance
        self.fail_kind = None

    def append(self, kind, record):
        if kind == self.fail_kind:
            raise OSError("controlled protected capture failure")
        ref = self.store.append_record(kind, record)
        self.records.append((kind, copy.deepcopy(record), ref))
        if self.advance is not None:
            self.advance(kind)
        return ref

    def values(self, kind):
        return [value for actual, value, _ in self.records if actual == kind]


class FixedProvider:
    def __init__(self, captures):
        self.captures, self.calls = captures, 0

    async def invoke_governed(self, prompt, **kwargs):
        assert self.captures.values("route-record")
        assert self.captures.values("model-call-start")
        self.calls += 1
        return {"text": "controlled fixed answer", "identity": {}, "usage": {}, "observed_runtime": True}


class ApiProvider:
    def __init__(self, captures, *, error=None):
        self.captures, self.error, self.calls = captures, error, 0

    async def preflight(self, deployment_ref, **kwargs):
        assert self.captures.values("model-call-start") == []

    async def invoke(self, deployment_ref, prompt, **kwargs):
        assert self.captures.values("route-record")
        assert self.captures.values("model-call-start")
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"text": "controlled API answer", "identity": {"effective": "controlled-observed", "basis": "controlled adapter"},
                "usage": {}, "observed_runtime": True}


def protected_context():
    context = authorized_context()
    context["limits"]["time_s"] = 120
    context["execution_deadline_monotonic_s"] = monotonic() + 120
    context["router"] = {"enabled": True, "deadline_s": 30, "profile_ref": context["model_selection_profile_ref"]}
    context["route_request"] = {"execution_id": context["execution_id"]}
    context["approved_model_ids"] = ["controlled.api"]
    return context


def reply_port(captures, reply, *, validator=None):
    port = RouterPort("unused-controlled-transport", peer_uid=10001,
                      validate_decision=validator, persist_decision=captures.append)

    async def exchange(request):
        return {"protocol": "ai4r-router-ipc:1", **copy.deepcopy(reply)}

    port._exchange = exchange
    return port


def route_record():
    return {"schema_version": "1.0.0", "route_id": "route-controlled", "run_id": "run", "node_id": "node",
            "subnode_id": "worker", "invocation_id": "invocation", "router_enabled": True,
            "decision_source": "codex_router_failed", "router_failure": "no_route",
            "router_halt_code": "PROFILE_UNAVAILABLE", "model_id": "codex-cli-default",
            "route_decision_ref": None, "recorded_at": "2026-10-19T00:00:00Z"}


def accepted_api_port(captures, context):
    decision = {"id": "controlled:decision", "selected_endpoint": "controlled.api",
                "deployment_ref": {"id": "controlled:deployment", "sha256": "b" * 64},
                "limits": dict(context["limits"])}
    return reply_port(captures, {"kind": "decision", "decision": decision}, validator=lambda *_: True)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,unknown", [("auth_failed", False), ("rate_limited", False),
    ("timeout", True), ("provider_error", False), ("invalid_request", False),
    ("network_error", True), ("invalid_output", False)])
async def test_provider_error_and_unknown_matrix(tmp_path, code, unknown):
    """Real Bridge/store plus explicitly controlled provider failure input."""
    captures = Captures(tmp_path / "state")
    context = protected_context()
    observation = {"identity": {"effective": "controlled-observed", "basis": "controlled response"},
                   "usage": {"input_tokens": 7, "output_tokens": None},
                   "provider_request_id": "controlled-request", "observed_runtime": True}
    api = ApiProvider(captures, error=ProviderError(code, outcome_unknown=unknown, observation=observation))
    fixed = FixedProvider(captures)
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=api, router_port=accepted_api_port(captures, context),
                                validate_record=validate, read_evidence=captures.store.read_blob)
        with pytest.raises(BridgeError, match=code):
            await bridge.call({}, "controlled provider failure")
        assert api.calls == 1 and fixed.calls == 0
        assert len(captures.values("model-call-start")) == len(captures.values("model-call")) == 1
        call = captures.values("model-call")[0]
        assert call["outcome"] == ("outcome_unknown" if unknown else "failed")
        assert call["provider_error_code"] == (None if unknown else code)
        assert (call["ended_at"] is None) is unknown
        assert call["identity"]["effective"] == "controlled-observed"
        assert call["usage"]["input_tokens"] == 7 and call["usage"]["output_tokens"] is None
        assert call["usage"]["cost_amount"] is None
        route = captures.values("route-record")[0]
        start = captures.values("model-call-start")[0]
        assert route["route_id"] == start["route_id"]
        assert call["route_decision_ref"] == route["route_decision_ref"]
    finally:
        captures.store.close()


def test_route_record_projection_preserves_source_no_route_and_consistency():
    value = route_record()
    validate("route-record", value)
    for changes in ({"router_failure": "error"}, {"router_halt_code": None},
                    {"router_halt_code": "UNRECOGNIZED"}, {"route_decision_ref": {"id": "foreign", "sha256": "a" * 64}}):
        with pytest.raises(ContractError):
            validate("route-record", {**value, **changes})


@pytest.mark.asyncio
async def test_staged_mutation_cannot_replace_original_captured_decision(tmp_path):
    selected = []

    def stage(kind):
        if kind == "model-call-input":
            selected[0]["deployment_ref"] = {"id": "swapped", "sha256": "c" * 64}

    captures = Captures(tmp_path / "state", advance=stage)
    context = protected_context()
    decision = {"id": "controlled:decision", "selected_endpoint": "controlled.api",
                "deployment_ref": {"id": "controlled:deployment", "sha256": "b" * 64}, "limits": dict(context["limits"])}

    def valid(_, value):
        selected.append(value)

    port = reply_port(captures, {"kind": "decision", "decision": decision}, validator=valid)
    fixed, api = FixedProvider(captures), ApiProvider(captures)
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=api, router_port=port,
                                validate_record=validate, read_evidence=captures.store.read_blob)
        with pytest.raises(BridgeError, match="invalid_request"):
            await bridge.call({}, "controlled immutable-choice prompt")
        assert captures.values("model-route") == [decision]
        assert fixed.calls == api.calls == 0
        assert captures.values("model-call-start") == captures.values("model-call") == []
        assert captures.values("model-call-refused")[0]["reason_code"] == "FROZEN_ROUTE_CAPTURE_CHANGED"
    finally:
        captures.store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("halt", ["PROFILE_UNAVAILABLE", "AUDIT_UNAVAILABLE", "ROUTING_IN_PROGRESS", "BUDGET_UNVERIFIABLE"])
async def test_no_route_bridge_records_exact_fallback_before_one_fixed_call(tmp_path, halt):
    captures = Captures(tmp_path / "state")
    context = protected_context()
    fixed, api = FixedProvider(captures), ApiProvider(captures)
    port = reply_port(captures, {"kind": "no_route", "no_route": {"execution_id": context["execution_id"], "halt_code": halt}})
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=api, router_port=port, validate_record=validate,
                                read_evidence=captures.store.read_blob)
        result = await bridge.call({}, "controlled no-route prompt")
        route = captures.values("route-record")[0]
        outcome = captures.values("model-call")[0]
        start = captures.values("model-call-start")[0]
        assert route["router_failure"] == "no_route" and route["router_halt_code"] == halt
        assert route["route_decision_ref"] is None and outcome["route_decision_ref"] is None
        assert start["route_id"] == route["route_id"]
        assert result["route_ref"] == next(ref for kind, _, ref in captures.records if kind == "route-record")
        assert fixed.calls == 1 and api.calls == 0
        assert outcome["outcome"] == "completed" and outcome["usage"]["input_tokens"] is None
    finally:
        captures.store.close()


@pytest.mark.asyncio
async def test_separate_selector_no_route_reaches_exact_bridge_capture_and_fixed_dispatch(tmp_path):
    """Actual selector process/Unix IPC/store; fixed provider is controlled."""
    from tests.integration.research.router.test_ipc_boundary import _real_router, await_socket

    fixture = Path(__file__).resolve().parents[3] / "fixtures/research/router/protected-capture"
    request = json.loads((fixture / "request.json").read_bytes())
    context = protected_context()
    context.update(request["selected_capsule"]["bound_context"]["runtime"])
    context.update(execution_id=request["execution_id"], route_request=request,
                   model_selection_profile_ref=request["model_selection_profile_ref"], approved_model_ids=[])
    context["router"]["profile_ref"] = request["model_selection_profile_ref"]
    captures = Captures(tmp_path / "state")
    socket = tmp_path / "router.sock"
    process = multiprocessing.Process(target=_real_router,
        args=(str(socket), str(tmp_path / "router-audit"), str(fixture), str(tmp_path / "selector-env.json")))
    process.start()
    fixed, api = FixedProvider(captures), ApiProvider(captures)
    try:
        await_socket(process, socket)
        port = RouterPort(socket, peer_uid=os.getuid())
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=api, router_port=port, validate_record=validate)
        await bridge.call({}, "controlled real IPC prompt")
        route = captures.values("route-record")[0]
        assert route["router_failure"] == "no_route" and route["router_halt_code"] == "PROFILE_UNAVAILABLE"
        assert fixed.calls == 1 and api.calls == 0
        assert captures.values("model-call-start")[0]["route_id"] == route["route_id"]
        assert captures.values("model-call")[0]["outcome"] == "completed"
    finally:
        process.terminate()
        process.join(5)
        assert not process.is_alive()
        captures.store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["model-route", "route-record", "model-call-input", "health"])
@pytest.mark.parametrize("change", ["expiry", "authorization"])
async def test_frozen_decision_invalidated_during_staging_never_starts_or_switches(tmp_path, phase, change):
    now = [datetime(2026, 10, 19, tzinfo=timezone.utc)]
    authorized = [True]

    def stage(kind):
        if kind == phase:
            if change == "expiry":
                now[0] += timedelta(seconds=31)
            else:
                authorized[0] = False

    captures = Captures(tmp_path / "state", advance=stage)
    context = protected_context()
    until = now[0] + timedelta(seconds=30)
    decision = {"id": "controlled:decision", "selected_endpoint": "controlled.api",
                "deployment_ref": {"id": "controlled:deployment", "sha256": "b" * 64},
                "limits": dict(context["limits"]), "valid_until": until.strftime("%Y-%m-%dT%H:%M:%SZ")}
    checks = []
    health_checks = []

    async def healthy():
        health_checks.append(True)
        if len(health_checks) == 2:
            stage("health")
        await asyncio.sleep(0)
        return True

    def validate_selected(actual, value):
        # Controlled protected-validation boundary. The separate authority unit
        # tests cover exact original-byte/profile/qualification joins.
        checks.append(copy.deepcopy(value))
        assert actual == context and value == decision
        if now[0] >= until or not authorized[0]:
            raise ValueError("controlled frozen decision invalidated")

    port = reply_port(captures, {"kind": "decision", "decision": decision}, validator=validate_selected)
    fixed, api = FixedProvider(captures), ApiProvider(captures)
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=api, router_port=port, validate_record=validate,
                                read_evidence=captures.store.read_blob, health_check=healthy)
        with pytest.raises(BridgeError):
            await bridge.call({}, "controlled staging prompt")
        assert len(checks) >= 2
        assert fixed.calls == api.calls == 0
        assert captures.values("model-call-start") == []
        assert captures.values("model-route") == [decision]
        route = captures.values("route-record")[0]
        assert route["model_id"] == "controlled.api" and route["decision_source"] == "router"
        assert captures.values("model-call") == []
        refused = captures.values("model-call-refused")[0]
        assert refused["reason_code"] == "FROZEN_ROUTE_INVALIDATED"
        assert refused["route_decision_ref"] == route["route_decision_ref"]
        assert refused["call_claim_ref"] == context["call_claim_ref"]
        assert "prompt" not in refused
    finally:
        captures.store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing,code", [("key", "auth_failed"), ("disabled", "auth_failed"),
    ("unsafe_url", "invalid_request"), ("adapter", "invalid_request"), ("call_function", "invalid_request")])
async def test_local_api_prerequisite_refusal_has_no_started_model_call(tmp_path, missing, code):
    from jiuwenswarm.research.providers import NativeProviders
    from tests.unit_tests.research.test_router_client import provider_fixture

    captures = Captures(tmp_path / "state")
    context = protected_context()
    entry, deployment, _, calls = provider_fixture()
    environment = {"APPROVED_KEY": "controlled-private-sentinel"}
    if missing == "key":
        environment.clear()
    elif missing == "disabled":
        entry["enabled"] = False
    elif missing == "unsafe_url":
        entry["base_url"] = "http://forbidden.example.invalid/v1"
    elif missing == "adapter":
        deployment["adapter_id"] = "unqualified"
    else:
        context["call_function"] = "verifier"
    # Bypass selection only for this controlled provider-function negative: the
    # ordinary verifier bypass is asserted in the real IPC/RouterPort tests.
    port = accepted_api_port(captures, context)
    if missing == "call_function":
        original_select = port.select
        async def controlled_worker_selection(actual):
            return await original_select({**actual, "call_function": "worker"})
        port.select = controlled_worker_selection
    constructed = []
    def forbidden_factory(*_):
        constructed.append(True)
        raise AssertionError("Native client must not be constructed for a local refusal")
    providers = NativeProviders(resolve_deployment=lambda *_: deployment, resolve_endpoint=lambda _: entry,
                                credential_environment=environment, native_factory=forbidden_factory)
    fixed = FixedProvider(captures)
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=providers, router_port=port,
                                validate_record=validate, read_evidence=captures.store.read_blob)
        with pytest.raises(BridgeError, match=code):
            await bridge.call({}, "controlled API prerequisite prompt")
        assert constructed == calls == [] and fixed.calls == 0
        assert captures.values("model-call-start") == captures.values("model-call") == []
        assert captures.values("model-call-refused")[0]["reason_code"] == code
    finally:
        captures.store.close()


@pytest.mark.asyncio
async def test_unavailable_api_builder_tool_loop_refuses_before_start(tmp_path):
    captures = Captures(tmp_path / "state")
    context = protected_context()
    context["cc_name"] = "research.builder"
    fixed, api = FixedProvider(captures), ApiProvider(captures)
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                                subscription_service=fixed, providers=api, router_port=accepted_api_port(captures, context),
                                validate_record=validate, read_evidence=captures.store.read_blob, builder_launcher=object())
        with pytest.raises(BridgeError, match="invalid_request"):
            await bridge.call({}, "controlled unavailable tool-loop prompt")
        assert fixed.calls == api.calls == 0
        assert captures.values("model-call-start") == captures.values("model-call") == []
        assert captures.values("model-call-refused")[0]["reason_code"] == "invalid_request"
    finally:
        captures.store.close()


@pytest.mark.asyncio
async def test_final_authority_denial_precedes_call_start(tmp_path):
    captures = Captures(tmp_path / "state")
    context = authorized_context()
    provider = FixedProvider(captures)

    def deny(_):
        assert captures.values("model-call-start") == []
        raise PlatformIntegrityError("controlled final authority denial")

    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context,
                                revalidate=deny, subscription_service=provider, validate_record=validate)
        with pytest.raises(BridgeError):
            await bridge.call({}, "controlled authority prompt")
        assert provider.calls == 0
        assert captures.values("model-call-start") == []
        assert captures.values("model-call") == []
        assert captures.values("model-call-refused")[0]["reason_code"] == "dispatch_authorization_denied"
    finally:
        captures.store.close()


@pytest.mark.asyncio
async def test_refusal_consumes_real_claim_and_exports_only_to_owned_authorized_audience(tmp_path):
    from jiuwenswarm.research.control import ResearchService
    from jiuwenswarm.research.runner import Registry

    captures = Captures(tmp_path / "state")
    context = authorized_context()
    captures.store.create_run(context["run_id"], account_id="alice", workspace_id="project", submission={})
    provider = FixedProvider(captures)

    def claim(_):
        protected = copy.deepcopy(context)
        call_id, ref = captures.store.claim_model_call(protected, invocation_limit=1, node_limit=1, run_limit=1)
        return {**protected, "call_id": call_id, "call_claim_ref": ref}

    def deny(_):
        raise ResearchError("budget_exhausted", "controlled protected budget refusal")

    try:
        bridge = GovernedBridge(persist=captures.append, authorize=claim, revalidate=deny,
                                subscription_service=provider, validate_record=validate)
        with pytest.raises(BridgeError, match="budget_exhausted"):
            await bridge.call({}, "prompt-not-public-refusal-bytes")
        with pytest.raises(ResearchError, match="model_call_already_claimed"):
            await bridge.call({}, "prompt-not-public-refusal-bytes")
        assert provider.calls == 0
        assert captures.values("model-call-start") == captures.values("model-call") == []
        refused = captures.values("model-call-refused")[0]
        assert refused["reason_code"] == "budget_exhausted"
        assert captures.store.read_record(refused["call_claim_ref"])["call_id"] == refused["call_id"]
        service = ResearchService(captures.store, registry=Registry(), model=None)
        actor = Principal("alice", frozenset({"project"}), frozenset({"export"}), frozenset({"researcher", "reviewer"}))
        for audience in ("researcher", "reviewer"):
            manifest, contents = await service.artifact_bytes(actor, context["run_id"], audience=audience)
            files = [f for f in manifest["files"] if "model-call-refused" in f["path"]]
            assert len(files) == 1 and files[0]["audience"] == audience
            assert contents[files[0]["path"]] == captures.store.read_blob(files[0]["artifact_ref"])
            assert b"prompt-not-public-refusal-bytes" not in b"".join(contents.values())
        for foreign in (Principal("bob", actor.workspace_ids, actor.operations, actor.audiences),
                        Principal("alice", frozenset({"foreign-project"}), actor.operations, actor.audiences),
                        Principal("alice", actor.workspace_ids, frozenset(), actor.audiences)):
            with pytest.raises(ResearchError):
                await service.artifact_bytes(foreign, context["run_id"], audience="researcher")
    finally:
        captures.store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["route-record", "model-call-start"])
async def test_bridge_capture_failure_prevents_new_dispatch(tmp_path, fault):
    captures = Captures(tmp_path / "state")
    captures.fail_kind = fault
    context = authorized_context()
    provider = FixedProvider(captures)
    try:
        bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context,
                                revalidate=lambda _: context, subscription_service=provider, validate_record=validate)
        with pytest.raises(BridgeError, match="AUDIT_UNAVAILABLE"):
            await bridge.call({}, "controlled capture fault")
        assert provider.calls == 0
    finally:
        captures.store.close()
