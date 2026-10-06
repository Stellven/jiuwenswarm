"""Actual local identity/configuration boundaries, with labeled mock discovery.

These checks do not establish native Web, provider, container or runner
acceptance. Those connected observations belong to M0-TRIAL-1 and SYSTEM.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from uuid import uuid4
from pathlib import Path

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, hash_json
from jiuwenswarm.ai4research.configuration import resolve_configuration
from jiuwenswarm.ai4research.identity import IdentityStore


@pytest.fixture
def boundary(tmp_path):
    store = IdentityStore(tmp_path / "profiles" / "identity.sqlite")
    user = store.initialize({"timeout_seconds": 30, "mode": "web"})
    workspace = store.register_workspace(tmp_path / "execution")
    model = "mock-discovery-" + uuid4().hex
    baseline = {"provider": "mock", "model_ids": [model], "model_roles": {"compiler": model, "verifier": model},
                "pins": {role: {"capsule_id": role, "sha256": hash_json({"fixture_implementation": role})} for role in ("compiler", "verifier")},
                "verification_profile": {"profile_id": "intent-fidelity-r2", "sha256": hash_json({"protected_fixture": "fidelity"}), "interface_revision": "M0-IF-007@r2"}}
    token = store.issue_session(workspace.workspace_id)
    return store, user, workspace, baseline, token


def test_m0_002_b01_attributed_snapshot_does_not_import_research_history(boundary):
    store, user, workspace, baseline, token = boundary
    context = store.authenticate(token, workspace.workspace_id)
    profile = resolve_configuration({"mode": "headless"}, store.get_profile().defaults, baseline)
    persisted = json.loads(json.dumps({"attribution": context.to_dict(), "configuration": profile.to_dict()}))
    assert persisted["attribution"]["user_id"] == user.user_id
    assert persisted["attribution"]["workspace_id"] == workspace.workspace_id
    assert persisted["configuration"]["effective"]["mode"] == "headless"
    assert token not in json.dumps(persisted)
    with pytest.raises(GovernanceError):
        store.set_defaults({"prior_request": "PRIVATE_PRIOR_OBJECTIVE"})
    assert store.get_profile().defaults["timeout_seconds"] == 30
    assert "PRIVATE_PRIOR_OBJECTIVE" not in json.dumps(profile.to_dict())


def test_m0_002_b02_authentication_refusal_precedes_configuration_and_effects(boundary):
    store, _, workspace, baseline, token = boundary
    effects = []
    def request(credential, **client):
        context = store.authenticate(credential, workspace.workspace_id, **client)
        frozen = resolve_configuration({}, store.get_profile().defaults, baseline)
        effects.append(context.workspace_id)
        return frozen
    for credential, client in [("invalid", {}), (token, {"peer_host": "192.0.2.2"}),
                                (token, {"origin": "http://evil.example", "expected_origin": "http://127.0.0.1:5173"})]:
        with pytest.raises(GovernanceError):
            request(credential, **client)
    assert effects == []
    assert request(token)["mock"] is True
    store.revoke_session(token)
    with pytest.raises(GovernanceError):
        request(token)
    replacement = store.issue_session(workspace.workspace_id)
    request(replacement)
    assert effects == [workspace.workspace_id, workspace.workspace_id]
    custody = store.custody_status()
    assert custody["session_storage"] == "sha256_only"
    if os.name == "nt":
        assert custody["ready"] is False and "ACL" in custody["reason"]
    else:
        assert custody["ready"] is True


def test_m0_002_b04_host_defaults_change_only_future_snapshots(boundary):
    store, _, _, baseline, token = boundary
    store.authenticate(token)
    frozen = resolve_configuration({}, {"account": store.get_profile().defaults, "machine": {"timeout_seconds": 40}, "project": {"timeout_seconds": 50}}, baseline)
    prior = frozen.to_dict()
    store.set_defaults({"timeout_seconds": 60})
    new = resolve_configuration({}, store.get_profile().defaults, baseline)
    assert frozen.to_dict() == prior
    assert frozen["timeout_seconds"] == 50 and new["timeout_seconds"] == 60
    assert frozen.fingerprint != new.fingerprint
    assert prior["effective"]["pins"] == baseline["pins"]
    assert prior["effective"]["verification_profile"] == baseline["verification_profile"]


def test_m0_002_b05_budget_contract_is_bounded_and_has_no_seed_or_retry_claim(boundary):
    store, _, _, baseline, token = boundary
    store.authenticate(token)
    frozen = resolve_configuration({"seed": 7, "max_calls": 1, "timeout_seconds": 2}, store.get_profile().defaults, baseline)
    manifest = frozen.to_dict()["effective"]
    assert manifest["max_calls"] == 1
    assert manifest["per_role_max_calls"] == {"compiler": 1, "verifier": 1}
    assert manifest["automatic_retries"] == 0
    assert manifest["requested_seed"] == 7 and manifest["effective_seed"] is None
    assert manifest["seed_support"] == "unavailable"
    assert manifest["mock"] is True and manifest["requires_real_model_evidence"] is False
    with pytest.raises(GovernanceError):
        resolve_configuration({"max_calls": 3}, store.get_profile().defaults, baseline)
    assert manifest == frozen.to_dict()["effective"]


def test_m0_002_b06_foreign_profile_and_concurrent_context_are_denied(boundary, tmp_path):
    store, _, first, baseline, token = boundary
    foreign = IdentityStore(tmp_path / "foreign-profile" / "identity.sqlite")
    foreign.initialize()
    foreign.register_workspace(tmp_path / "foreign-execution")
    with pytest.raises(GovernanceError):
        foreign.authenticate(token)
    second = store.register_workspace(tmp_path / "second-execution")
    with pytest.raises(GovernanceError):
        store.issue_session(second.workspace_id)
    store.revoke_session(token)
    def admit(workspace):
        try:
            return store.issue_session(workspace.workspace_id), workspace.workspace_id
        except GovernanceError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, [first, second]))
    accepted = [result for result in results if result is not None]
    assert len(accepted) == 1
    credential, workspace_id = accepted[0]
    assert store.authenticate(credential).workspace_id == workspace_id
    alternate = {**baseline, "provider": "experimental"}
    with pytest.raises(GovernanceError):
        resolve_configuration({}, {}, alternate)
    assert resolve_configuration({}, {}, baseline)["provider"] == "mock"


def test_m0_002_b04_owned_capsule_pin_records_freeze_without_identity_drift(boundary, tmp_path):
    from jiuwenswarm.ai4research.capsules import CapsuleLibrary
    import jiuwenswarm.ai4research.configuration as configuration
    _, _, _, baseline, _ = boundary
    library = CapsuleLibrary(tmp_path / "capsules.sqlite", Path(configuration.__file__).parent)
    candidates = library.seed_builtin()
    baseline["pins"] = {role: candidates["intent_" + role].to_dict() for role in ("compiler", "verifier")}
    frozen = resolve_configuration({}, {}, baseline)
    assert frozen.to_dict()["effective"]["pins"] == baseline["pins"]
    assert frozen["pins"]["compiler"]["decl_hash"] == candidates["intent_compiler"].sha256
    assert frozen["pins"]["verifier"]["closure_hash"] == candidates["intent_verifier"].implementation_hash
