"""IF014 payload binding is checked before routing and again at dispatch."""
import copy
import hashlib
import json
from time import monotonic

import pytest

from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
from jiuwenswarm.research.router_client import PlatformIntegrityError, RouteChoice


def context(prompt):
    ref = {"id": "private-pin", "sha256": "a" * 64}
    return dict(run_id="calibration-private-run", node_id="calibration",
        subnode_id="verifier", attempt_id="case", invocation_id="invocation",
        execution_id="execution", call_id="call", call_claim_ref=ref,
        contract_ref=ref, model_selection_profile_ref=ref, deployment_ref=ref,
        call_function="verifier", limits=dict(time_s=2, model_calls=1, memory_mb=64),
        execution_deadline_monotonic_s=monotonic()+2,
        expected_prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())


def bridge_fixture(protected, live=None):
    effects = {"claims": [], "routes": [], "provider": [], "records": []}
    def persist(kind, record):
        effects["records"].append((kind, copy.deepcopy(record)))
        return dict(id=record.get("id", record.get("route_id")),
                    sha256=hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest())
    def authorize(request):
        effects["claims"].append(request)
        return protected
    class Router:
        async def select(self, value):
            effects["routes"].append(copy.deepcopy(value))
            return RouteChoice("codex-cli-default")
    class Provider:
        async def invoke_governed(self, prompt, **kwargs):
            effects["provider"].append(prompt)
            return dict(text='{"passed":true}', identity={}, usage={}, observed_runtime=True)
    port = GovernedBridge(persist=persist, authorize=authorize,
        revalidate=lambda _: protected if live is None else live,
        subscription_service=Provider(), router_port=Router())
    return port, effects


@pytest.mark.asyncio
@pytest.mark.parametrize("actual", ["changed", "subject\nexpected_label=true", "subject ", "subject\r\n"])
async def test_changed_calibration_text_has_no_route_or_provider_effect(actual):
    port, effects = bridge_fixture(context("subject"))
    with pytest.raises(PlatformIntegrityError, match="PROTECTED_PROMPT_MISMATCH"):
        await port.call({"execution_id": "execution", "call_ordinal": 1}, actual)
    assert len(effects["claims"]) == 1
    assert effects["routes"] == effects["provider"] == effects["records"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "", "a"*63, "A"*64, 1, {"sha256": "a"*64}])
async def test_malformed_private_hash_cannot_disable_binding(bad):
    protected=context("subject");protected["expected_prompt_sha256"]=bad
    port,effects=bridge_fixture(protected)
    with pytest.raises(PlatformIntegrityError, match="PROTECTED_PROMPT_HASH_INVALID"):
        await port.call({}, "subject")
    assert effects["routes"] == effects["provider"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["remove", "replace", "add"])
async def test_dispatch_cannot_remove_replace_or_add_payload_authority(change):
    protected=context("subject");live=copy.deepcopy(protected)
    if change=="remove":live.pop("expected_prompt_sha256")
    elif change=="replace":live["expected_prompt_sha256"]="b"*64
    else:protected.pop("expected_prompt_sha256")
    port,effects=bridge_fixture(protected,live)
    with pytest.raises(BridgeError):
        await port.call({}, "subject")
    assert len(effects["routes"])==1 and effects["provider"]==[]
    assert not any(kind in {"model-call-start","model-call"} for kind,_ in effects["records"])
    refusal=next(row for kind,row in effects["records"] if kind=="model-call-refused")
    assert refusal["reason_code"]=="DISPATCH_CONTEXT_CHANGED"
    assert refusal["call_claim_ref"]==protected["call_claim_ref"]


@pytest.mark.asyncio
async def test_exact_unicode_text_dispatches_once_with_unchanged_public_call_shape():
    prompt='Instruction\n\n<subject_payload>\n{"text":"café"}\n</subject_payload>'
    port,effects=bridge_fixture(context(prompt))
    await port.call({"execution_id":"execution","call_ordinal":1},prompt)
    assert effects["provider"]==[prompt] and len(effects["routes"])==1
    call=next(row for kind,row in effects["records"] if kind=="model-call")
    assert call["outcome"]=="completed" and call["call_function"]=="verifier"
    assert "expected_prompt_sha256" not in call


@pytest.mark.asyncio
async def test_ordinary_authority_keeps_existing_unbound_prompt_contract():
    protected=context("subject");protected.pop("expected_prompt_sha256")
    port,effects=bridge_fixture(protected)
    await port.call({},"ordinary exact caller payload")
    assert effects["provider"]==["ordinary exact caller payload"]
