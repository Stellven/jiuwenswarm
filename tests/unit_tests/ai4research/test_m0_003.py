"""Independent M0-003 local assertions; fixture admission is never live acceptance."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from jiuwenswarm.ai4research import capsules
from jiuwenswarm.ai4research.common import GovernanceError, hash_json


def make_package(tmp_path: Path) -> Path:
    """Isolated visible local fixtures, explicitly not real model/profile evidence."""
    root = tmp_path / "package"
    root.mkdir()
    templates = Path(capsules.__file__).parent / "declaration" / "library"
    for role in capsules.ROLES:
        data = json.loads((templates / f"{role}.json").read_text(encoding="utf-8"))
        manifest = root / "declaration" / "library" / f"{role}.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(data), encoding="utf-8")
        refs = [data["identity"]["carrier"]["ref"]] + [item["path"] for item in data["identity"]["body"]]
        for ref in refs:
            resource = root / ref
            resource.parent.mkdir(parents=True, exist_ok=True)
            if not resource.exists():
                resource.write_text(f"Independent visible fixture: {ref}\n", encoding="utf-8")
    return root


def prerequisites(**updates) -> dict:
    value = {"runtime_ready": True, "security_ready": True, "profile_ready": True,
             "checks_passed": True, "review_passed": True, "scope": "fixture-only",
             "evidence_refs": [{"ref": "isolated-definition-check-receipt", "sha256": hash_json({"independent_fixture": True})}]}
    return value | updates


@pytest.fixture
def library(tmp_path):
    result = capsules.CapsuleLibrary(tmp_path / "library.sqlite", make_package(tmp_path))
    result.seed_builtin()
    return result


def active(library, role="intent_compiler"):
    library.admit(role, prerequisites())
    return library.activate(role, human_authorized=True, actor_id="fixture-product-user", required_scope="fixture-only")


def test_m0_003_b01_canonical_roundtrip_and_derived_markdown(library):
    pin = library._candidate("intent_compiler", None)
    declaration = pin.declaration
    declaration["guarantees"]["quality"] = {"criterion": "retained future metadata", "judge": "protected", "target_rate": 0.9, "window": 10, "min_observations": 10}
    declaration["evolution"]["notes_for_builder"] = ["Advisory text grants no mutation authority."]
    canonical = capsules.validate_declaration(declaration)
    assert canonical == declaration
    document = capsules.make_capsule_markdown(canonical)
    encoded = document.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(encoded) == declaration
    assert hash_json(declaration) in document
    assert "members/structure/wiring" in capsules.FIELD_DISPOSITION
    assert pin.declaration != declaration  # Defensive view; mutation cannot change stored identity.


@pytest.mark.parametrize("mutation,code", [
    (lambda x: x.update(run_id="producer-run"), "invalid_input"),
    (lambda x: x.update(schema_version="2.9"), "incompatible_revision"),
    (lambda x: x["identity"].update(kind="composite"), "incompatible_revision"),
    (lambda x: x.update(members=[{"role": "member", "decl_hash": "0" * 64}]), "incompatible_revision"),
    (lambda x: x["ports"]["outputs"][0].update(type="legacy-shape"), "invalid_input"),
    (lambda x: x["needs"].update(provider="producer-selected"), "invalid_input"),
    (lambda x: x["guarantees"].update(exempt=True), "policy_denied"),
    (lambda x: x["budget"]["enforcement"].update(wall_s="post_hoc"), "policy_denied"),
    (lambda x: x["budget"]["per_call"].update(wall_s=float("inf")), "invalid_input"),
    (lambda x: x["needs"]["resources"].append({"resource_key": "credentials", "mode": "read"}), "policy_denied"),
    (lambda x: x["needs"].update(injects=[{"service_key": "shell", "interface_version_range": "r2"}]), "policy_denied"),
    (lambda x: x["ports"]["outputs"][0].update(schema_ref="producer-favorable-schema"), "incompatible_revision"),
    (lambda x: x["guarantees"].update(acceptance=["output-schema"]), "policy_denied"),
])
def test_m0_003_b01_authority_and_future_forms_are_rejected(library, mutation, code):
    declaration = library._candidate("intent_compiler", None).declaration
    mutation(declaration)
    with pytest.raises(GovernanceError) as error:
        capsules.validate_declaration(declaration)
    assert error.value.code == code


def test_m0_003_b01_unseeded_template_is_not_a_valid_declaration(library):
    template = json.loads((library.root_dir / "declaration/library/intent_compiler.json").read_text())
    with pytest.raises(GovernanceError):
        capsules.validate_declaration(template)


@pytest.mark.parametrize("ref", ["intent/compiler.prompt.md", "intent/models.py", "bridge.py", "capsules.py"])
def test_m0_003_b02_changed_closure_never_runs_under_old_identity(library, ref):
    pin = active(library)
    old_bytes = library.source_snapshot(pin.decl_hash)[ref]
    (library.root_dir / ref).write_text("changed implementation\n", encoding="utf-8")
    with pytest.raises(GovernanceError) as error:
        library.validate_pin(pin)
    assert error.value.code == "ineligible_pin"
    assert library.source_snapshot(pin.decl_hash)[ref] == old_bytes
    changed = library.seed_builtin()["intent_compiler"]
    assert changed.decl_hash != pin.decl_hash
    assert changed.implementation_hash != pin.implementation_hash
    assert changed.standing == "candidate"


def test_m0_003_b02_missing_dependency_and_swapped_role_are_blocked(library):
    pin = library._candidate("intent_compiler", None)
    swapped = pin.declaration
    swapped["identity"]["carrier"]["ref"] = "intent/verifier.prompt.md"
    with pytest.raises(GovernanceError) as error:
        library.stage(swapped)
    assert error.value.code == "ineligible_pin"
    (library.root_dir / "runner.py").unlink()
    with pytest.raises(GovernanceError) as error:
        library.stage(pin.declaration)
    assert error.value.code == "environment_unavailable"


@pytest.mark.parametrize("locator", ["../secret.txt", "/etc/passwd", "C:/secret.txt", "intent\\compiler.prompt.md", "intent/../secret.txt"])
def test_m0_003_b02_path_escape_is_denied(library, locator):
    with pytest.raises(GovernanceError) as error:
        library._read(locator)
    assert error.value.code == "policy_denied"


def test_m0_003_b02_actual_symlink_or_reparse_is_not_a_source_pin(library, tmp_path):
    target = library.root_dir / "intent/compiler.prompt.md"
    target.unlink()
    outside = tmp_path / "outside-prompt.md"
    outside.write_text("outside-scope canary", encoding="utf-8")
    try:
        os.symlink(outside, target)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"Host cannot create required symlink probe: {error.errno}")
        # Windows file symlinks can need privilege. A real directory junction
        # exercises the same reparse-point denial without treating a mock as QA.
        link = library.root_dir / "reparse-probe"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside.parent)], capture_output=True, check=False)
        assert result.returncode == 0, "Required actual filesystem reparse probe is unavailable"
        try:
            with pytest.raises(GovernanceError) as denied:
                library._read("reparse-probe/outside-prompt.md")
            assert denied.value.code == "policy_denied"
        finally:
            os.rmdir(link)  # Remove only the junction entry, never its target.
        return
    with pytest.raises(GovernanceError) as error:
        library.seed_builtin()
    assert error.value.code == "policy_denied"


@pytest.mark.parametrize("missing", ["runtime_ready", "security_ready", "profile_ready", "checks_passed", "review_passed"])
def test_m0_003_b03_failed_prerequisite_records_refusal_without_activation(library, missing):
    with pytest.raises(GovernanceError) as error:
        library.admit("intent_compiler", prerequisites(**{missing: False}))
    assert error.value.code == "environment_unavailable"
    assert library.history("intent_compiler")["admissions"][-1]["accepted"] == 0
    with pytest.raises(GovernanceError):
        library.resolve("intent_compiler")
    repaired = library.admit("intent_compiler", prerequisites())
    assert repaired.standing == "admitted_inactive"
    assert len(library.history("intent_compiler")["admissions"]) == 2


def test_m0_003_b03_fixture_admission_cannot_become_real(library):
    pin = active(library)
    assert library.resolve("intent_compiler", required_scope="fixture-only").decl_hash == pin.decl_hash
    with pytest.raises(GovernanceError) as error:
        library.resolve("intent_compiler", required_scope="real")
    assert error.value.code == "ineligible_pin"
    with pytest.raises(GovernanceError):
        library.admit("intent_verifier", prerequisites(evidence_refs=[]))
    with pytest.raises(GovernanceError):
        library.admit("intent_verifier", prerequisites(producer_pass=True))


def test_m0_003_b04_human_only_activation_and_append_only_history(library):
    admitted = library.admit("intent_compiler", prerequisites())
    assert admitted.standing == "admitted_inactive"
    with pytest.raises(GovernanceError) as error:
        library.activate("intent_compiler", actor_id="model-claim")
    assert error.value.code == "policy_denied"
    with pytest.raises(GovernanceError):
        library.activate("intent_compiler", human_authorized=True)
    pin = active(library)
    assert library.resolve("intent_compiler").decl_hash == pin.decl_hash
    with sqlite3.connect(library.db_path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable capsule history"):
            db.execute("DELETE FROM capsule_versions")
    assert library.history("intent_compiler")["standing"][-1]["actor_id"] == "fixture-product-user"


def test_m0_003_b04_frozen_pin_suspension_and_explicit_rollback(library):
    old = active(library)
    newer = old.declaration
    newer["identity"]["version_label"] = "explicit-authored-r2-revision"
    newer["identity"]["lineage"].update(parent=old.decl_hash, relation="revision")
    candidate = library.stage(newer)
    library.admit("intent_compiler", prerequisites(), decl_hash=candidate.decl_hash)
    library.activate("intent_compiler", candidate.decl_hash, human_authorized=True, actor_id="fixture-product-user")
    assert library.resolve("intent_compiler").decl_hash == candidate.decl_hash
    assert library.validate_pin(old).decl_hash == old.decl_hash
    library.suspend("intent_compiler", old.decl_hash, human_authorized=True, actor_id="fixture-product-user")
    with pytest.raises(GovernanceError):
        library.validate_pin(old)
    assert library.resolve("intent_compiler").decl_hash == candidate.decl_hash
    restored = library.rollback("intent_compiler", old.decl_hash, human_authorized=True, actor_id="fixture-product-user")
    assert restored.decl_hash == old.decl_hash
    library.suspend("intent_compiler", old.decl_hash, human_authorized=True, actor_id="fixture-product-user")
    with pytest.raises(GovernanceError):
        library.resolve("intent_compiler")  # Never silently substitutes the newer eligible version.
    assert len(library.history("intent_compiler")["versions"]) == 2


def test_m0_003_b04_missing_or_swapped_pin_identity_cannot_resolve(library):
    pin = active(library)
    with pytest.raises(GovernanceError):
        library.validate_pin({"role": "intent_compiler"})
    changed = pin.to_dict() | {"implementation_hash": "0" * 64}
    with pytest.raises(GovernanceError):
        library.validate_pin(changed)
    with pytest.raises(GovernanceError):
        library.validate_pin(pin.to_dict() | {"role": "intent_verifier"})


def test_m0_003_b04_default_suspension_targets_activated_not_newest_candidate(library):
    old = active(library)
    newer = old.declaration
    newer["identity"]["version_label"] = "unadmitted-new-candidate"
    candidate = library.stage(newer)
    library.suspend("intent_compiler", human_authorized=True, actor_id="fixture-product-user")
    assert library.get(old.decl_hash).standing == "suspended"
    assert library.get(candidate.decl_hash).standing == "candidate"
    with pytest.raises(GovernanceError):
        library.resolve("intent_compiler")


def test_m0_003_b03_failed_admission_persistence_does_not_create_eligibility(library):
    with sqlite3.connect(library.db_path) as db:
        db.execute("CREATE TRIGGER inject_admission_failure BEFORE INSERT ON capsule_admissions BEGIN SELECT RAISE(ABORT, 'independent injected storage fault'); END")
    with pytest.raises(GovernanceError) as error:
        library.admit("intent_compiler", prerequisites())
    assert error.value.code == "persistence_failed"
    assert library.history("intent_compiler")["admissions"] == []
    with pytest.raises(GovernanceError):
        library.activate("intent_compiler", human_authorized=True, actor_id="fixture-product-user")


def test_m0_003_b04_standing_failure_cannot_expose_an_active_pointer(library):
    library.admit("intent_compiler", prerequisites())
    with sqlite3.connect(library.db_path) as db:
        db.execute("CREATE TRIGGER inject_standing_failure BEFORE INSERT ON capsule_standing BEGIN SELECT RAISE(ABORT, 'independent injected storage fault'); END")
    with pytest.raises(GovernanceError) as error:
        library.activate("intent_compiler", human_authorized=True, actor_id="fixture-product-user")
    assert error.value.code == "persistence_failed"
    assert library.history("intent_compiler")["standing"] == []
    with pytest.raises(GovernanceError):
        library.resolve("intent_compiler")
