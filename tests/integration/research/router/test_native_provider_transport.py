"""Controlled native-client/SDK component checks, without endpoint qualification.

NativeProviders uses its real default factory, the pinned OpenJiuwen request and
response parser, and the real OpenAI SDK. Only HTTP transport is substituted;
all endpoint, authorization and response values below are inert test fixtures.
These checks make no live request and do not qualify a deployment or provider.
"""
from __future__ import annotations

import copy
import json

import httpx
import pytest

from jiuwenswarm.research.providers import NativeProviders, ProviderError


# The pinned pysbd dependency contains legacy regex string escapes. Python
# compilation labels these SyntaxWarnings with the source filename as module,
# so a dotted-module filter misses them. Preserve pytest's error policy for all
# other warnings while allowing only this known warning from pysbd source paths.
pytestmark = pytest.mark.filterwarnings(
    r"ignore:invalid escape sequence:SyntaxWarning:.*[/\\]pysbd[/\\]"
)


BASE_URL = "https://controlled-api.example.invalid/v1"
SELECTED_MODEL = "controlled-selected-model"
EFFECTIVE_MODEL = "controlled-response-model"
SENTINEL_KEY = "controlled-fixture-only-not-a-provider-credential"
PROMPT = "Controlled native transport fixture."
DEPLOYMENT_REF = {"id": "controlled-deployment", "sha256": "a" * 64}
ENDPOINT_REF = {"id": "controlled-endpoint", "sha256": "b" * 64}


def completion(*, usage=None, content="controlled answer", tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    body = {
        "id": "chatcmpl-controlled",
        "object": "chat.completion",
        "created": 0,
        "model": EFFECTIVE_MODEL,
        "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
    }
    if usage is not None:
        body["usage"] = copy.deepcopy(usage)
    return body


@pytest.fixture
def native_transport(monkeypatch, tmp_path, request):
    # Configure the pinned logger through its supported API before importing
    # model clients: their registry emits an initialization log on first import.
    # File output remains enabled and is confined to this owned pytest scratch.
    from openjiuwen.core.common.logging.log_config import (
        configure_log_config, get_log_config_snapshot,
    )
    original_logging = get_log_config_snapshot()
    controlled_logging = copy.deepcopy(original_logging)
    controlled_logging["log_path"] = str(tmp_path / "native-logs")
    configure_log_config(controlled_logging)
    request.addfinalizer(lambda: configure_log_config(original_logging))
    from openjiuwen.core.foundation.llm.model_clients import openai_model_client

    class ControlledWire:
        def __init__(self):
            self.response = completion()
            self.status = 200
            self.failure = None
            self.requests = []
            self.clients = []
            self.native_clients = []
            self.resolutions = []
            self.before_send = None

        async def handle(self, request):
            # The replacement transport never delegates to a socket transport.
            assert str(request.url) == BASE_URL + "/chat/completions"
            if self.before_send is not None:
                self.before_send()
            self.requests.append(request)
            if self.failure == "timeout":
                raise httpx.ReadTimeout("controlled timeout", request=request)
            if self.failure == "network":
                raise httpx.ConnectError("controlled connection failure", request=request)
            return httpx.Response(self.status, json=self.response,
                                  headers={"x-request-id": "controlled-request-id"}, request=request)

        def provider(self):
            endpoint = {
                "provider_id": "controlled",
                "base_url": BASE_URL,
                "models": [{"model_id": "controlled-model", "provider_model_name": SELECTED_MODEL}],
                "credential_env_var": "CONTROLLED_FIXTURE_KEY",
                "timeout_s": 7,
                "enabled": True,
            }
            deployment = {
                "model_id": "controlled-model",
                "provider": "controlled",
                "provider_model_name": SELECTED_MODEL,
                "adapter_id": "native-openai-chat-v1",
                "revision": "controlled-r1",
                "endpoint_ref": ENDPOINT_REF,
            }

            def resolve_deployment(ref, function):
                assert ref == DEPLOYMENT_REF and function == "worker"
                self.resolutions.append(("deployment", copy.deepcopy(ref)))
                return copy.deepcopy(deployment)

            def resolve_endpoint(ref):
                assert ref == ENDPOINT_REF
                self.resolutions.append(("endpoint", copy.deepcopy(ref)))
                return copy.deepcopy(endpoint)

            # Deliberately omit native_factory: exercise the production factory.
            return NativeProviders(resolve_deployment=resolve_deployment,
                resolve_endpoint=resolve_endpoint,
                credential_environment={"CONTROLLED_FIXTURE_KEY": SENTINEL_KEY})

        def assert_exact_once(self, *, resolution_rounds=1):
            # Bridge performs a non-effecting preflight, then invoke rechecks
            # the exact configuration. Neither stage may duplicate the send.
            assert self.resolutions == [("deployment", DEPLOYMENT_REF), ("endpoint", ENDPOINT_REF)] * resolution_rounds
            assert len(self.native_clients) == len(self.clients) == len(self.requests) == 1
            native, sdk, request = self.native_clients[0], self.clients[0], self.requests[0]
            config = native.model_client_config
            assert config.client_id == "governed-api-call"
            assert getattr(config.client_provider, "value", config.client_provider) == "OpenAI"
            assert getattr(config.api_mode, "value", config.api_mode) == "chat_completions"
            assert config.api_base == BASE_URL and config.api_key == SENTINEL_KEY
            assert config.max_retries == 0 and config.use_shared_llm_http_client is False
            # Endpoint allowance 7s remains the shorter limit than the caller's
            # 30s, including real native initialization on the first cold call.
            assert config.timeout == 7 and native.model_config.model_name == SELECTED_MODEL
            # The observer returns the actual SDK object without wrapping it.
            assert sdk.max_retries == 0 and str(sdk.base_url) == BASE_URL + "/"
            assert sdk.is_closed()
            assert request.method == "POST"
            assert request.headers["authorization"] == "Bearer " + SENTINEL_KEY
            assert request.headers["x-stainless-retry-count"] == "0"
            assert set(request.extensions["timeout"].values()) == {7}
            body = json.loads(request.content)
            assert body["model"] == SELECTED_MODEL and body["stream"] is False
            assert body["messages"] == [{"role": "user", "content": PROMPT}]
            assert "tools" not in body or body["tools"] is None

    wire = ControlledWire()
    transport = httpx.MockTransport(wire.handle)
    original_http_client = httpx.AsyncClient

    class ControlledHttpClient(original_http_client):
        def __init__(self, *args, **kwargs):
            # Disable environment proxy routing as part of transport isolation.
            # A proxy must never bypass the controlled transport, even if the
            # surrounding test process happens to inherit proxy settings.
            kwargs.update(transport=transport, proxy=None, trust_env=False)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(openai_model_client.httpx, "AsyncClient", ControlledHttpClient)
    original_builder = openai_model_client.OpenAIModelClient._build_async_openai_client

    def observe_builder(native, timeout=None):
        sdk = original_builder(native, timeout=timeout)
        wire.native_clients.append(native)
        wire.clients.append(sdk)
        return sdk

    monkeypatch.setattr(openai_model_client.OpenAIModelClient,
                        "_build_async_openai_client", observe_builder)
    return wire


@pytest.mark.asyncio
@pytest.mark.parametrize("usage,input_tokens,output_tokens", [
    ({"prompt_tokens": 17, "completion_tokens": 5, "total_tokens": 22}, 17, 5),
    (None, None, None),
    ({"prompt_tokens": 17, "total_tokens": 17}, 17, None),
], ids=["measured", "usage-absent", "completion-count-absent"])
async def test_actual_native_parser_preserves_raw_identity_and_available_usage(
        native_transport, usage, input_tokens, output_tokens):
    wire = native_transport
    wire.response = completion(usage=usage)
    result = await wire.provider().invoke(DEPLOYMENT_REF, PROMPT, timeout_s=30, call_function="worker")
    wire.assert_exact_once()
    assert result["text"] == "controlled answer" and result["observed_runtime"] is True
    assert result["identity"] == {"effective": EFFECTIVE_MODEL, "basis": "provider response.model"}
    assert result["provider_request_id"] == "controlled-request-id"
    assert result["usage"]["input_tokens"] == input_tokens
    assert result["usage"]["output_tokens"] == output_tokens
    assert result["usage"]["cost_amount"] is None
    assert SENTINEL_KEY not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [
    (401, "auth_failed"), (403, "auth_failed"), (429, "rate_limited"),
    (500, "provider_error"), (400, "invalid_request"), (409, "invalid_request"),
])
async def test_actual_sdk_status_errors_are_typed_without_retry(native_transport, status, code):
    wire = native_transport
    wire.status = status
    wire.response = {"error": {"message": "controlled fixture error",
                               "type": "controlled_fixture", "code": "controlled_fixture"}}
    with pytest.raises(ProviderError) as caught:
        await wire.provider().invoke(DEPLOYMENT_REF, PROMPT, timeout_s=30, call_function="worker")
    wire.assert_exact_once()
    error = caught.value
    assert str(error) == code and error.code == code and error.outcome_unknown is False
    assert error.observation["observed_runtime"] is True
    assert error.observation["provider_request_id"] == "controlled-request-id"
    assert error.observation["identity"]["effective"] is None
    assert error.observation["usage"]["input_tokens"] is None
    assert error.observation["usage"]["output_tokens"] is None
    assert error.observation["usage"]["cost_amount"] is None
    assert "controlled fixture error" not in str(error.observation)
    assert SENTINEL_KEY not in str(error.observation)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,code", [("timeout", "timeout"), ("network", "network_error")])
async def test_actual_sdk_uncertain_transport_outcomes_are_not_replayed(native_transport, failure, code):
    wire = native_transport
    wire.failure = failure
    with pytest.raises(ProviderError) as caught:
        await wire.provider().invoke(DEPLOYMENT_REF, PROMPT, timeout_s=30, call_function="worker")
    wire.assert_exact_once()
    error = caught.value
    assert str(error) == code and error.code == code and error.outcome_unknown is True
    assert error.observation["observed_runtime"] is True
    assert error.observation["identity"]["effective"] is None
    assert error.observation["provider_request_id"] is None
    assert error.observation["usage"]["input_tokens"] is None
    assert error.observation["usage"]["output_tokens"] is None
    assert error.observation["usage"]["cost_amount"] is None
    assert SENTINEL_KEY not in str(error.observation)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["blank", "tool-call"])
async def test_actual_native_parser_invalid_output_preserves_observations_without_replay(native_transport, kind):
    wire = native_transport
    tools = [{"id": "controlled-tool-call", "type": "function",
              "function": {"name": "controlled_tool", "arguments": "{}"}}] if kind == "tool-call" else None
    wire.response = completion(content="" if kind == "blank" else "controlled answer", tool_calls=tools,
                               usage={"prompt_tokens": 17, "completion_tokens": 5, "total_tokens": 22})
    with pytest.raises(ProviderError) as caught:
        await wire.provider().invoke(DEPLOYMENT_REF, PROMPT, timeout_s=30, call_function="worker")
    wire.assert_exact_once()
    error = caught.value
    assert str(error) == error.code == "invalid_output" and error.outcome_unknown is False
    assert error.observation["observed_runtime"] is True
    assert error.observation["identity"]["effective"] == EFFECTIVE_MODEL
    assert error.observation["provider_request_id"] == "controlled-request-id"
    assert error.observation["usage"]["input_tokens"] == 17
    assert error.observation["usage"]["output_tokens"] == 5
    assert error.observation["usage"]["cost_amount"] is None
    assert SENTINEL_KEY not in str(error.observation)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["success", "401", "timeout"])
async def test_actual_native_sdk_outcome_joins_bridge_and_durable_store(native_transport, tmp_path, kind):
    """Controlled selection + real local store/native SDK + mock HTTP only."""
    from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
    from jiuwenswarm.research.contracts import validate
    from tests.integration.research.router.test_dispatch_records import (
        Captures, FixedProvider, protected_context, reply_port,
    )

    captures = Captures(tmp_path / "state")
    context = protected_context()
    context["approved_model_ids"] = ["controlled-model"]
    decision = {"id": "controlled:decision", "selected_endpoint": "controlled-model",
                "deployment_ref": DEPLOYMENT_REF, "limits": dict(context["limits"])}
    port = reply_port(captures, {"kind": "decision", "decision": decision}, validator=lambda *_: True)
    fixed = FixedProvider(captures)
    wire = native_transport
    wire.response = completion(usage={"prompt_tokens": 17, "completion_tokens": 5, "total_tokens": 22})
    if kind == "401":
        wire.status = 401
        wire.response = {"error": {"message": "controlled fixture error", "type": "controlled_fixture"}}
    elif kind == "timeout":
        wire.failure = "timeout"

    def persisted_before_send():
        # Check the actual immutable store bytes at the HTTP effect boundary,
        # rather than relying only on the capture callback's in-memory list.
        for name in ("model-route", "route-record", "model-call-input", "model-call-start"):
            matches = [(value, ref) for actual, value, ref in captures.records if actual == name]
            assert len(matches) == 1
            value, ref = matches[0]
            assert json.loads(captures.store.read_blob(ref)) == value

    wire.before_send = persisted_before_send
    bridge = GovernedBridge(persist=captures.append, authorize=lambda _: context, revalidate=lambda _: context,
                            subscription_service=fixed, providers=wire.provider(), router_port=port,
                            validate_record=validate, read_evidence=captures.store.read_blob)
    try:
        if kind == "success":
            result = await bridge.call({}, PROMPT)
        else:
            with pytest.raises(BridgeError, match="auth_failed" if kind == "401" else "timeout") as caught:
                await bridge.call({}, PROMPT)
            result = {"route_ref": caught.value.route_ref, "call_ref": caught.value.call_ref}
        wire.assert_exact_once(resolution_rounds=2)
        assert fixed.calls == 0
        assert captures.values("model-call-refused") == []
        assert len(captures.values("route-record")) == len(captures.values("model-call-start")) == 1
        assert len(captures.values("model-call")) == 1
        refs = {actual: ref for actual, _, ref in captures.records}
        route = captures.values("route-record")[0]
        start = captures.values("model-call-start")[0]
        call = captures.values("model-call")[0]
        assert captures.values("model-route") == [decision]
        assert route["decision_source"] == "router" and route["model_id"] == "controlled-model"
        assert route["route_decision_ref"] == call["route_decision_ref"] == refs["model-route"]
        assert start["route_id"] == route["route_id"]
        assert start["route_ref"] == result["route_ref"] == refs["route-record"]
        assert start["input_ref"] == refs["model-call-input"]
        assert refs["model-call-input"] in call["evidence_refs"]
        assert start["call_claim_ref"] == context["call_claim_ref"]
        assert start["call_id"] == call["id"] == context["call_id"]
        assert call["deployment_ref"] == DEPLOYMENT_REF and call["observed_runtime"] is True
        assert call["identity"]["requested"] == "controlled-model"
        assert result["call_ref"] == refs["model-call"]
        assert json.loads(captures.store.read_blob(result["call_ref"])) == call
        if kind == "success":
            assert call["outcome"] == "completed" and call["provider_error_code"] is None
            assert call["identity"]["effective"] == EFFECTIVE_MODEL
            assert call["usage"]["input_tokens"] == 17 and call["usage"]["output_tokens"] == 5
            assert call["provider_request_id"] == "controlled-request-id"
            assert result["text"] == captures.values("model-call-output")[0]["text"] == "controlled answer"
            assert refs["model-call-output"] in call["evidence_refs"]
        else:
            assert call["outcome"] == ("outcome_unknown" if kind == "timeout" else "failed")
            assert call["provider_error_code"] == (None if kind == "timeout" else "auth_failed")
            assert call["identity"]["effective"] is None
            assert call["usage"]["input_tokens"] is None and call["usage"]["output_tokens"] is None
            assert call["provider_request_id"] == (None if kind == "timeout" else "controlled-request-id")
            assert captures.values("model-call-output") == []
        assert (call["ended_at"] is None) is (kind == "timeout")
        assert call["usage"]["cost_amount"] is None
        assert SENTINEL_KEY not in str(captures.records)
    finally:
        captures.store.close()
