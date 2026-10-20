"""Independent routing boundary expectations from M1-IF-001/008."""
import asyncio
import copy

import pytest

from jiuwenswarm.research.router_client import (
    CodexRouter, PlatformIntegrityError, RouterPort, decode_frame, encode_frame,
)


def context(enabled=False, function="worker"):
    return {"call_function": function, "router": {"enabled": enabled, "deadline_s": 30,
            "profile_ref": {"id": "profile", "sha256": "a" * 64} if enabled else None},
            "route_request": {"execution_id": "execution"}, "approved_model_ids": ["approved"]}


@pytest.mark.asyncio
async def test_fixed_default_does_not_require_export_catalog_or_profile():
    choice = await CodexRouter().select({})
    assert choice.model_id == "codex-cli-default"
    assert choice.decision_source == "codex_router_disabled"
    assert choice.route_decision_ref is None


@pytest.mark.asyncio
async def test_verifier_bypasses_router_even_when_enabled():
    port = RouterPort("unused", peer_uid=10001)
    async def forbidden(_):
        raise AssertionError("Router consulted for verifier")
    port._exchange = forbidden
    assert (await port.select(context(True, "verifier"))).decision_source == "codex_router_disabled"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,reason", [(FileNotFoundError(), "missing"), (ConnectionResetError(), "error"), (TimeoutError(), "timeout")])
async def test_prestart_transport_failures_have_attributed_fixed_route(failure, reason):
    port = RouterPort("unused", peer_uid=10001)
    async def fail(_):
        raise failure
    port._exchange = fail
    choice = await port.select(context(True))
    assert choice.model_id == "codex-cli-default"
    assert choice.decision_source == "codex_router_failed"
    assert choice.router_failure == reason


@pytest.mark.asyncio
async def test_router_integrity_fault_never_falls_back():
    port = RouterPort("unused", peer_uid=10001)
    async def answer(_):
        return {"protocol": "ai4r-router-ipc:1", "kind": "integrity_fault",
                "execution_id": "execution", "reason": "forged", "failed_checks": ["pins"]}
    port._exchange = answer
    with pytest.raises(PlatformIntegrityError):
        await port.select(context(True))


@pytest.mark.asyncio
async def test_missing_profile_is_explicit_no_route():
    data = context(True)
    data["router"]["profile_ref"] = None
    choice = await RouterPort("unused", peer_uid=10001).select(data)
    assert choice.router_failure == "no_route"
    assert choice.router_halt_code == "PROFILE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_unapproved_reply_cannot_select_model():
    port = RouterPort("unused", peer_uid=10001)
    async def answer(_):
        return {"protocol": "ai4r-router-ipc:1", "kind": "decision", "decision": {"selected_endpoint": "foreign"}}
    port._exchange = answer
    assert (await port.select(context(True))).router_failure == "unapproved_model"


def test_frame_ceiling_is_exact_and_nonfinite_or_duplicate_json_is_refused():
    payload = {"x": "a" * (4 * 1024 * 1024 - 8)}
    assert len(encode_frame(payload)) == 4 * 1024 * 1024 + 4
    assert decode_frame(encode_frame(payload)[4:]) == payload
    with pytest.raises(ValueError):
        encode_frame({"x": payload["x"] + "b"})
    with pytest.raises(ValueError):
        decode_frame(b'{"x":NaN}')
    with pytest.raises(ValueError):
        decode_frame(b'{"x":1,"x":2}')


def test_unknown_operator_deadline_cannot_weaken_the_fixed_boundary():
    data = context(True)
    data["router"]["deadline_s"] = 31
    with pytest.raises(PlatformIntegrityError):
        RouterPort.validate_settings(data)


@pytest.mark.asyncio
async def test_fixed_baseline_profile_never_contacts_selector():
    data = context(True)
    data["model_selection_profile"] = {"policy_mode": "fixed_baseline"}
    port = RouterPort("unused", peer_uid=10001)
    async def forbidden(_):
        raise AssertionError("fixed baseline contacted selector")
    port._exchange = forbidden
    assert (await port.select(data)).decision_source == "codex_router_disabled"


def provider_fixture():
    from types import SimpleNamespace
    entry = {"provider_id": "approved", "base_url": "https://api.example.invalid/v1",
             "models": [{"model_id": "approved-model", "provider_model_name": "exact-provider-model"}],
             "credential_env_var": "APPROVED_KEY", "timeout_s": 7, "enabled": True}
    deployment = {"model_id": "approved-model", "provider": "approved",
                  "provider_model_name": "exact-provider-model", "adapter_id": "native-openai-chat-v1",
                  "revision": "r1", "endpoint_ref": {"id": "endpoint", "sha256": "b" * 64}}
    calls = []
    class Client:
        async def _parse_response(self, raw, parser=None):
            # Mirrors the native parser's lossy missing-usage defaults. The
            # adapter must observe raw bytes/fields before this normalization.
            return SimpleNamespace(content="answer", tool_calls=[], usage_metadata={"input_tokens": 0, "output_tokens": 0})
        async def invoke(self, **kwargs):
            calls.append(kwargs)
            return await self._parse_response(SimpleNamespace(model="actual-provider-model", _request_id="request-1", usage=None))
    return entry, deployment, Client(), calls


@pytest.mark.asyncio
async def test_native_provider_uses_exact_approved_identity_zero_retry_and_raw_usage():
    from jiuwenswarm.research.providers import NativeProviders
    entry, deployment, client, calls = provider_fixture()
    configs = []
    def factory(config, model):
        configs.append((config, model))
        return client
    providers = NativeProviders(resolve_deployment=lambda ref, function: deployment,
        resolve_endpoint=lambda ref: entry, credential_environment={"APPROVED_KEY": "private-key"}, native_factory=factory)
    result = await providers.invoke({"id": "deployment", "sha256": "a" * 64}, "prompt", timeout_s=2, call_function="worker")
    assert len(calls) == 1
    assert calls[0]["model"] == "exact-provider-model" and calls[0]["timeout"] == 2
    assert calls[0]["tools"] is None
    assert configs[0][0]["max_retries"] == 0
    assert configs[0][0]["use_shared_llm_http_client"] is False
    assert result["identity"]["effective"] == "actual-provider-model"
    assert result["provider_request_id"] == "request-1"
    assert result["usage"]["input_tokens"] is None
    assert result["usage"]["output_tokens"] is None
    assert result["usage"]["cost_amount"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation,expected", [("disabled", "auth_failed"), ("foreign", "invalid_request"),
    ("unsafe_url", "invalid_request"), ("missing_key", "auth_failed"), ("unknown_adapter", "invalid_request")])
async def test_provider_refuses_unapproved_or_unavailable_before_native_effect(mutation, expected):
    from jiuwenswarm.research.providers import NativeProviders, ProviderError
    entry, deployment, client, calls = provider_fixture()
    env = {"APPROVED_KEY": "private-key"}
    if mutation == "disabled": entry["enabled"] = False
    if mutation == "foreign": deployment["provider_model_name"] = "unregistered"
    if mutation == "unsafe_url": entry["base_url"] = "https://credential:secret@example.invalid"
    if mutation == "missing_key": env.clear()
    if mutation == "unknown_adapter": deployment["adapter_id"] = "unqualified-tools"
    providers = NativeProviders(resolve_deployment=lambda ref, function: deployment,
        resolve_endpoint=lambda ref: entry, credential_environment=env,
        native_factory=lambda *_: (_ for _ in ()).throw(AssertionError("native client constructed")))
    with pytest.raises(ProviderError) as caught:
        await providers.invoke({"id": "deployment", "sha256": "a" * 64}, "prompt", timeout_s=2, call_function="worker")
    assert caught.value.code == expected and calls == []


@pytest.mark.asyncio
async def test_provider_maps_wrapped_failure_once_without_exposing_private_exception():
    from jiuwenswarm.research.providers import NativeProviders, ProviderError
    entry, deployment, client, calls = provider_fixture()
    async def fail(**kwargs):
        calls.append(kwargs)
        cause = RuntimeError("credential-private-value")
        cause.status_code = 429
        raise RuntimeError("native wrapper with private input") from cause
    client.invoke = fail
    providers = NativeProviders(resolve_deployment=lambda ref, function: deployment,
        resolve_endpoint=lambda ref: entry, credential_environment={"APPROVED_KEY": "private-key"},
        native_factory=lambda *_: client)
    with pytest.raises(ProviderError) as caught:
        await providers.invoke({"id": "deployment", "sha256": "a" * 64}, "prompt", timeout_s=2, call_function="worker")
    assert caught.value.code == "rate_limited" and len(calls) == 1
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_provider_failure_retains_observed_response_before_parser_rejects():
    from types import SimpleNamespace
    from jiuwenswarm.research.providers import NativeProviders, ProviderError
    entry, deployment, client, calls = provider_fixture()
    async def reject(raw, **kwargs): raise ValueError('private response parser details')
    client._parse_response = reject
    async def invoke(**kwargs):
        calls.append(kwargs)
        return await client._parse_response(SimpleNamespace(model='observed-on-failure',
            _request_id='response-request-id', usage=SimpleNamespace(prompt_tokens=13, completion_tokens=5)))
    client.invoke = invoke
    providers = NativeProviders(resolve_deployment=lambda *_: deployment,
        resolve_endpoint=lambda _: entry, credential_environment={'APPROVED_KEY': 'never-export'},
        native_factory=lambda *_: client)
    with pytest.raises(ProviderError) as caught:
        await providers.invoke({'id':'deployment','sha256':'a'*64}, 'prompt', timeout_s=2, call_function='worker')
    observation = caught.value.observation
    assert observation['identity']['effective'] == 'observed-on-failure'
    assert observation['usage']['input_tokens'] == 13 and observation['usage']['output_tokens'] == 5
    assert observation['provider_request_id'] == 'response-request-id'
    assert observation['observed_runtime'] is True and len(calls) == 1
    assert 'never-export' not in str(observation) and 'private' not in str(caught.value)


@pytest.mark.asyncio
async def test_provider_status_failure_retains_only_typed_request_id_from_wrapped_error():
    from jiuwenswarm.research.providers import NativeProviders, ProviderError
    entry, deployment, client, calls = provider_fixture()
    async def invoke(**kwargs):
        calls.append(kwargs)
        cause = RuntimeError('private provider body')
        cause.status_code, cause.request_id = 429, 'status-request-id'
        raise RuntimeError('private native wrapper') from cause
    client.invoke = invoke
    providers = NativeProviders(resolve_deployment=lambda *_: deployment, resolve_endpoint=lambda _: entry,
        credential_environment={'APPROVED_KEY':'private-key'}, native_factory=lambda *_: client)
    with pytest.raises(ProviderError) as caught:
        await providers.invoke({'id':'deployment','sha256':'a'*64}, 'prompt', timeout_s=2, call_function='worker')
    assert caught.value.code == 'rate_limited' and len(calls) == 1
    assert caught.value.observation['provider_request_id'] == 'status-request-id'
    assert caught.value.observation['usage']['input_tokens'] is None
    assert 'private' not in str(caught.value.observation)
