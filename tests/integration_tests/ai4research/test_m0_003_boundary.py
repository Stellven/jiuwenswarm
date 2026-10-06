"""Actual local library/files/SQLite boundaries; no real model acceptance claim."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from jiuwenswarm.ai4research import capsules
from jiuwenswarm.ai4research.common import GovernanceError, hash_json
from tests.unit_tests.ai4research.test_m0_003 import prerequisites


def packaged_library(tmp_path):
    root = tmp_path / "packaged"
    shutil.copytree(Path(capsules.__file__).parent, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    library = capsules.CapsuleLibrary(tmp_path / "persistent/library.sqlite", root)
    pins = library.seed_builtin()
    return library, pins


def test_m0_003_b01_packaged_declaration_serialization_boundary(tmp_path):
    library, pins = packaged_library(tmp_path)
    assert set(pins) == {"intent_compiler", "intent_verifier"}
    for pin in pins.values():
        text = capsules.make_capsule_markdown(pin.declaration)
        decoded = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
        assert hash_json(decoded) == pin.decl_hash
        assert decoded["schema_version"] == "2.11"
        assert pin.standing == "candidate"
        with pytest.raises(GovernanceError):
            library.resolve(pin.role)
    extra = pins["intent_compiler"].declaration
    extra["identity"]["name"] = "scientific_evaluator"
    with pytest.raises(GovernanceError):
        library.stage(extra)


def test_m0_003_b02_profile_and_upstream_dependency_tamper_boundary(tmp_path):
    library, pins = packaged_library(tmp_path)
    role = "intent_verifier"
    library.admit(role, prerequisites(), decl_hash=pins[role].decl_hash)
    pin = library.activate(role, human_authorized=True, actor_id="local-fixture-admin")
    snapshot = library.source_snapshot(pin.decl_hash)
    source = "verification/upstream/result-evaluator.md"
    assert source in snapshot and "verification/profile.json" in snapshot
    (library.root_dir / source).write_bytes(snapshot[source] + b"\nchanged after review\n")
    with pytest.raises(GovernanceError) as error:
        library.validate_pin(pin, required_scope="fixture-only")
    assert error.value.code == "ineligible_pin"
    assert library.source_snapshot(pin.decl_hash)[source] == snapshot[source]
    updated = library.seed_builtin()[role]
    assert updated.decl_hash != pin.decl_hash and updated.standing == "candidate"
    with pytest.raises(GovernanceError):
        library.activate(role, updated.decl_hash, human_authorized=True, actor_id="local-fixture-admin")


def test_m0_003_b03_prerequisite_and_scope_boundary(tmp_path):
    library, pins = packaged_library(tmp_path)
    for role in capsules.ROLES:
        with pytest.raises(GovernanceError):
            library.admit(role, prerequisites(runtime_ready=False), decl_hash=pins[role].decl_hash)
        library.admit(role, prerequisites(), decl_hash=pins[role].decl_hash)
        library.activate(role, human_authorized=True, actor_id="local-fixture-admin")
        assert library.resolve(role, required_scope="fixture-only").decl_hash == pins[role].decl_hash
        with pytest.raises(GovernanceError):
            library.resolve(role, required_scope="real")
        assert [r["accepted"] for r in library.history(role)["admissions"]] == [0, 1]


def test_m0_003_b04_restart_and_current_suspension_boundary(tmp_path):
    library, pins = packaged_library(tmp_path)
    for role in capsules.ROLES:
        library.admit(role, prerequisites(), decl_hash=pins[role].decl_hash)
        library.activate(role, human_authorized=True, actor_id="local-fixture-admin")
    old_pin = library.resolve("intent_compiler", required_scope="fixture-only")
    reloaded = capsules.CapsuleLibrary(library.db_path, library.root_dir)
    assert reloaded.resolve("intent_compiler", required_scope="fixture-only").to_dict() == old_pin.to_dict()
    assert reloaded.source_snapshot(old_pin.decl_hash) == library.source_snapshot(old_pin.decl_hash)
    reloaded.suspend("intent_compiler", old_pin.decl_hash, human_authorized=True, actor_id="local-fixture-admin")
    with pytest.raises(GovernanceError):
        library.validate_pin(old_pin)
    assert reloaded.resolve("intent_verifier", required_scope="fixture-only").decl_hash == pins["intent_verifier"].decl_hash
    assert reloaded.history("intent_compiler")["standing"][-1]["action"] == "suspended"
