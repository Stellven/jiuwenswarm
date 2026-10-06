"""Isolated M0-002 block fixtures; no account, provider or network calls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import sqlite3
from uuid import uuid4

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, hash_json
from jiuwenswarm.ai4research.configuration import resolve_configuration
from jiuwenswarm.ai4research.identity import IdentityStore


@pytest.fixture
def baseline():
    discovered = "mock-discovery-" + uuid4().hex
    return {"provider": "mock", "model_ids": [discovered],
            "model_roles": {"compiler": discovered, "verifier": discovered},
            "pins": {role: {"capsule_id": role, "version": "fixture-r2", "sha256": hash_json({"role": role})} for role in ("compiler", "verifier")},
            "verification_profile": {"profile_id": "intent-fidelity-r2", "sha256": hash_json({"protected_fixture": "fidelity"}), "interface_revision": "M0-IF-007@r2"}}


@pytest.fixture
def local_identity(tmp_path):
    now = [1000.0]
    store = IdentityStore(tmp_path / "profile" / "identity.sqlite", clock=lambda: now[0])
    store.initialize({"timeout_seconds": 30})
    path = tmp_path / "workspace"
    path.mkdir()
    workspace = store.register_workspace(path)
    return store, workspace, now


def test_m0_002_b01_profile_survives_workspace_removal_and_restart(local_identity):
    store, workspace, _ = local_identity
    original = store.get_profile()
    assert store.register_workspace(workspace.workspace_path) == workspace
    from pathlib import Path
    Path(workspace.workspace_path).rmdir()
    restored = IdentityStore(store.db_path).initialize()
    assert restored.to_dict() == original.to_dict()
    assert not Path(workspace.workspace_path).exists()
    with pytest.raises(TypeError):
        restored.defaults["mode"] = "web"
    with pytest.raises(GovernanceError):
        store.register_workspace(store.db_path.parent)
    with pytest.raises(GovernanceError):
        store.initialize({"mode": "web"})
    updated = store.set_defaults({"mode": "web"})
    assert updated.user_id == original.user_id
    assert store.get_profile().defaults["mode"] == "web"


def test_m0_002_b01_bad_default_or_storage_never_provisions_an_account(tmp_path):
    store = IdentityStore(tmp_path / "identity.sqlite")
    with pytest.raises(GovernanceError):
        store.initialize({"previous_objective": "secret prior research"})
    with pytest.raises(GovernanceError) as missing:
        store.get_profile()
    assert missing.value.code == "environment_unavailable"
    damaged = tmp_path / "corrupt.sqlite"
    damaged.write_bytes(b"not a sqlite database")
    with pytest.raises(GovernanceError) as failure:
        IdentityStore(damaged)
    assert failure.value.code == "persistence_failed"


def test_m0_002_b02_session_hash_custody_expiry_and_revocation(local_identity):
    store, workspace, now = local_identity
    token = store.issue_session(workspace.workspace_id, ttl_seconds=10)
    context = store.authenticate(token, workspace.workspace_id, origin="http://127.0.0.1:5173", expected_origin="http://127.0.0.1:5173")
    assert context.user_id == store.get_profile().user_id
    assert token not in repr(context) and token not in json.dumps(context.to_dict())
    assert token.encode() not in store.db_path.read_bytes()
    with sqlite3.connect(store.db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
    assert "token_hash" in columns and "token" not in columns
    assert store.revoke_session(token) is True
    assert store.revoke_session(token) is False
    with pytest.raises(GovernanceError):
        IdentityStore(store.db_path, clock=lambda: now[0]).authenticate(token)
    replacement = store.issue_session(workspace.workspace_id, ttl_seconds=10)
    assert store.authenticate(replacement).workspace_id == workspace.workspace_id
    now[0] += 10
    with pytest.raises(GovernanceError):
        store.authenticate(replacement)


@pytest.mark.parametrize("client", [
    {"peer_host": "192.0.2.1"}, {"peer_host": "0.0.0.0"}, {"peer_host": "localhost"},
    {"origin": "http://evil.example", "expected_origin": "http://127.0.0.1:5173"},
    {"origin": "http://127.0.0.1:5174", "expected_origin": "http://127.0.0.1:5173"},
    {"origin": "http://127.0.0.1:5173"}, {"origin": [], "expected_origin": "http://127.0.0.1:5173"},
])
def test_m0_002_b02_denies_untrusted_peer_or_origin(local_identity, client):
    store, workspace, _ = local_identity
    token = store.issue_session(workspace.workspace_id)
    with pytest.raises(GovernanceError) as denied:
        store.authenticate(token, **client)
    assert denied.value.code == "policy_denied"
    assert token not in json.dumps(denied.value.as_dict())
    assert store.authenticate(token).workspace_id == workspace.workspace_id


def test_m0_002_b04_precedence_and_snapshot_are_detached(baseline):
    defaults = {"account": {"timeout_seconds": 20, "mode": "web"}, "machine": {"timeout_seconds": 30}, "project": {"timeout_seconds": 40}}
    frozen = resolve_configuration({"max_calls": 1}, defaults, baseline)
    before = frozen.to_dict()
    assert frozen["timeout_seconds"] == 40
    assert frozen["mode"] == "web" and frozen["max_calls"] == 1
    assert before["provenance"]["timeout_seconds"] == "project"
    assert before["provenance"]["max_calls"] == "requested"
    defaults["project"]["timeout_seconds"] = 70
    baseline["pins"]["compiler"]["sha256"] = "a" * 64
    before["effective"]["model_roles"]["compiler"] = "tampered"
    assert frozen.to_dict()["effective"]["model_roles"]["compiler"] != "tampered"
    assert frozen["timeout_seconds"] == 40
    with pytest.raises(TypeError):
        frozen["pins"]["compiler"]["sha256"] = "b" * 64
    with pytest.raises(FrozenInstanceError):
        frozen.fingerprint = "forged"
    assert resolve_configuration({}, defaults, baseline)["timeout_seconds"] == 70


@pytest.mark.parametrize("mutation", ["missing_models", "foreign_role", "missing_pin", "bad_hash", "duplicate_pins", "bad_profile", "credential"])
def test_m0_002_b04_malformed_protected_baseline_is_rejected(baseline, mutation):
    if mutation == "missing_models":
        baseline["model_ids"] = []
    elif mutation == "foreign_role":
        baseline["model_roles"]["verifier"] = "not-discovered"
    elif mutation == "missing_pin":
        del baseline["pins"]["verifier"]
    elif mutation == "bad_hash":
        baseline["pins"]["compiler"]["sha256"] = "not-a-hash"
    elif mutation == "duplicate_pins":
        baseline["pins"]["verifier"] = deepcopy(baseline["pins"]["compiler"])
    elif mutation == "bad_profile":
        baseline["verification_profile"]["interface_revision"] = "M0-IF-007@r1"
    else:
        baseline["pins"]["compiler"]["credential"] = "SECRET_CANARY"
    with pytest.raises(GovernanceError) as failure:
        resolve_configuration({}, {}, baseline)
    assert "SECRET_CANARY" not in json.dumps(failure.value.as_dict())


@pytest.mark.parametrize("options", [
    {"timeout_seconds": 0}, {"timeout_seconds": -1}, {"timeout_seconds": float("nan")},
    {"timeout_seconds": float("inf")}, {"timeout_seconds": 3601}, {"timeout_seconds": True},
    {"max_calls": 0}, {"max_calls": 3}, {"max_calls": True}, {"max_calls": 1.0},
    {"seed": -1}, {"seed": True}, {"seed": 2**63}, {"mode": []},
])
def test_m0_002_b05_invalid_limits_and_types_are_rejected(baseline, options):
    with pytest.raises(GovernanceError):
        resolve_configuration(options, {}, baseline)


def test_m0_002_b05_seed_and_usage_truth_are_explicit(baseline):
    baseline["provider"] = "codex_subscription"
    frozen = resolve_configuration({"seed": 123, "timeout_seconds": 10, "max_calls": 2}, {}, baseline)
    assert frozen["requested_seed"] == 123
    assert frozen["seed"] is None and frozen["effective_seed"] is None
    assert frozen["seed_support"] == "unavailable"
    assert frozen["per_role_max_calls"] == {"compiler": 1, "verifier": 1}
    assert frozen["automatic_retries"] == 0 and frozen["total_timeout_seconds"] == 20
    assert frozen["token_usage"]["available"] is False and frozen["cost_usage"]["available"] is False
    assert frozen["requires_real_model_evidence"] is True
    assert "real_model_evidence" not in frozen


def test_m0_002_b06_one_active_workspace_and_explicit_switch(local_identity, tmp_path):
    store, first, _ = local_identity
    second = store.register_workspace(tmp_path / "second-workspace")
    token = store.issue_session(first.workspace_id)
    with pytest.raises(GovernanceError):
        store.issue_session(second.workspace_id)
    with pytest.raises(GovernanceError):
        store.authenticate(token, second.workspace_id)
    store.revoke_session(token)
    second_token = store.issue_session(second.workspace_id)
    assert store.authenticate(second_token).workspace_id == second.workspace_id
    with pytest.raises(GovernanceError):
        store.authenticate(token)


@pytest.mark.parametrize("options", [{"remote_worker": "example.invalid"}, {"provider": "other"}, {"model_roles": {}}, {"gate_enabled": False}, {"advanced_compiler": True}, {"profile_id": "unapproved"}])
def test_m0_002_b06_client_cannot_enable_deferred_mechanisms(baseline, options):
    with pytest.raises(GovernanceError):
        resolve_configuration(options, {}, baseline)
    assert resolve_configuration({}, {}, baseline)["mock"] is True
