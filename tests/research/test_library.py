"""Offline admission, source closure and audited standing checks."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jiuwenswarm.research.contracts import COMPILER_INSTRUCTIONS, ResearchError, canonical, digest
from jiuwenswarm.research.library import CapsuleLibrary, SOURCE_FILES


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        for relative in SOURCE_FILES:
            destination = self.sources / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(CapsuleLibrary._source(relative).read_bytes())
        self.source_patch = patch.object(CapsuleLibrary, "_source", side_effect=lambda relative: self.sources / relative)
        self.source_patch.start()
        self.library = CapsuleLibrary(self.root / "library")

    def tearDown(self):
        self.source_patch.stop()
        self.temporary.cleanup()

    def audit(self):
        return [json.loads(line) for line in self.library.audit_path.read_text().splitlines()]

    def assert_code(self, code, function):
        with self.assertRaises(ResearchError) as caught:
            function()
        self.assertEqual(caught.exception.code, code)

    def test_admission_is_executed_and_recorded_for_both_roles(self):
        pins = self.library.resolve()
        self.assertEqual(set(pins), {"compiler", "verifier"})
        for role, pin in pins.items():
            record = json.loads((self.library.root / pin / "admission.json").read_text())
            registry = json.loads((self.library.registry_root / (pin + ".json")).read_text())
            self.assertEqual(record["role"], role)
            self.assertEqual(record["status"], "ADMITTED")
            self.assertTrue(record["self_test"]["executed"])
            self.assertEqual(record["provider_invocations"], 0)
            self.assertEqual(record["semantic_evaluation"], "unmeasured")
            self.assertEqual(len(record["self_test"]["checks"]), 4)
            negative = next(check for check in record["self_test"]["checks"] if check["id"] == "negative_contract_boundaries")
            self.assertEqual(negative["observed_rejections"], 3)
            self.assertEqual(registry["admission_hash"], digest((self.library.root / pin / "admission.json").read_bytes()))
        self.assertEqual(self.audit()[0]["action"], "seed")
        self.assertEqual(self.audit()[0]["actor"], "initial-install-operator")

    def test_admission_runs_real_schema_checks_and_failure_does_not_admit(self):
        fresh = self.root / "failed-admission"
        with patch("jiuwenswarm.research.library.validate_intent", side_effect=ResearchError("FIXTURE_FAILURE")) as check:
            self.assert_code("CAPSULE_ADMISSION_SELF_TEST_FAILED", lambda: CapsuleLibrary(fresh))
        self.assertTrue(check.called)
        self.assertFalse(list((fresh / "registry").glob("*.json")))
        self.assertFalse((fresh / "standing-audit.jsonl").exists())

    def test_serialization_profile_is_explicit_and_preserves_optional_concepts(self):
        declaration = self.library.definitions["compiler"]
        self.assertEqual(declaration["schema_version"], "intent-capsule.v1")
        self.assertEqual(declaration["serialization_profile"], "intent-capsule.v1")
        self.assertFalse(declaration["source_compatibility"]["machine_schema_conformance"])
        self.assertEqual(declaration["source_compatibility"]["machine_schema_version"], "2.9")
        self.assertIn("co_parents", declaration["identity"]["lineage"])
        self.assertIn("provenance", declaration["identity"]["lineage"])
        self.assertIn("remote", declaration["identity"])
        self.assertIn("overlays", declaration["identity"])
        self.assertIn("quality", declaration["guarantees"])
        self.assertIn("per_call", declaration["budget"])
        self.assertIn("structure", declaration)
        self.assertIn("effects", declaration["compatibility_preservation"])
        self.assertEqual(declaration["budget"]["per_call"]["wall_s"], 600)
        self.assertEqual(declaration["budget"]["calls"], 1)

    def test_carrier_is_exact_snapshot_with_hash_matching_role_instructions(self):
        for role, declaration in self.library.definitions.items():
            folder = self.library.root / declaration["pin"]
            carrier = declaration["identity"]["carrier"]
            snapshot = (folder / carrier["ref"]).read_bytes()
            self.assertEqual(digest(snapshot), carrier["sha256"])
            self.assertEqual(snapshot, self.library._instructions(role).encode())
            self.assertEqual(self.library.validate_instructions(role, declaration["pin"], snapshot.decode()), carrier["sha256"])
        self.assert_code("CAPSULE_INSTRUCTIONS_CHANGED", lambda: self.library.validate_instructions(
            "compiler", self.library.definitions["compiler"]["pin"], COMPILER_INSTRUCTIONS + "\nTampered"))

    def test_restart_does_not_reseed_or_reexecute_existing_admission(self):
        before = self.library.audit_path.read_bytes()
        with patch.object(CapsuleLibrary, "_structural_test", side_effect=AssertionError("Unexpected re-admission")):
            restarted = CapsuleLibrary(self.library.root)
        self.assertEqual(restarted.resolve(), self.library.resolve())
        self.assertEqual(restarted.audit_path.read_bytes(), before)

    def test_source_and_snapshot_changes_are_blocked(self):
        source = self.sources / "model.py"
        source.write_bytes(source.read_bytes() + b"\n# changed native implementation\n")
        self.assert_code("CAPSULE_IMPLEMENTATION_CHANGED", self.library.resolve)
        source.write_bytes((self.library.root / self.library.definitions["compiler"]["pin"] / "implementation" / "model.py").read_bytes())
        snapshot = self.library.root / self.library.definitions["compiler"]["pin"] / "implementation" / "runner.py"
        snapshot.write_bytes(snapshot.read_bytes() + b"\n# changed stored implementation\n")
        self.assert_code("CAPSULE_IMPLEMENTATION_CHANGED", self.library.resolve)

    def test_in_memory_declaration_cannot_override_pinned_permissions(self):
        self.library.definitions["compiler"]["needs"]["model"]["tool_calling"] = True
        self.assert_code("CAPSULE_INTEGRITY", self.library.resolve)

    def test_suspension_deprecation_and_activation_are_append_only_audited(self):
        pin = self.library.definitions["compiler"]["pin"]
        before = self.library.audit_path.read_bytes()
        self.library.suspend("compiler", actor="fixture-operator")
        self.assert_code("CAPSULE_ACTIVATION_REQUIRED", self.library.resolve)
        self.library.deprecate("compiler", actor="fixture-operator")
        self.library.activate("compiler", pin, actor="fixture-operator")
        self.assertEqual(self.library.resolve()["compiler"], pin)
        self.assertTrue(self.library.audit_path.read_bytes().startswith(before))
        records = self.audit()
        self.assertEqual([record["action"] for record in records], ["seed", "suspend", "deprecate", "activate"])
        self.assertEqual([record["sequence"] for record in records], [1, 2, 3, 4])
        for previous, current in zip(records, records[1:]):
            self.assertEqual(current["previous_hash"], previous["sha256"])

    def test_new_source_versions_are_admitted_inactive_and_rollback_requires_restored_closure(self):
        original = self.library.resolve()
        source = self.sources / "model.py"
        original_source = source.read_bytes()
        source.write_bytes(original_source + b"\n# new installed revision\n")
        changed = CapsuleLibrary(self.library.root)
        self.assertEqual(len(list(changed.registry_root.glob("*.json"))), 4)
        self.assert_code("CAPSULE_ACTIVATION_REQUIRED", changed.resolve)
        for role in ("compiler", "verifier"):
            changed.activate(role, changed.definitions[role]["pin"])
        self.assertNotEqual(changed.resolve(), original)
        self.assert_code("CAPSULE_IMPLEMENTATION_CHANGED", lambda: changed.rollback("compiler", original["compiler"]))
        source.write_bytes(original_source)
        restored = CapsuleLibrary(self.library.root)
        for role in ("compiler", "verifier"):
            restored.rollback(role, original[role], actor="restore-operator")
        self.assertEqual(restored.resolve(), original)
        self.assertEqual([record["action"] for record in self.audit()][-2:], ["rollback", "rollback"])

    def test_role_swap_unregistered_pins_and_path_traversal_cannot_activate(self):
        verifier_pin = self.library.definitions["verifier"]["pin"]
        self.assert_code("CAPSULE_NOT_ADMITTED", lambda: self.library.activate("compiler", verifier_pin))
        self.assert_code("CAPSULE_NOT_ADMITTED", lambda: self.library.activate("compiler", "0" * 64))
        self.assert_code("CAPSULE_STANDING_INVALID", lambda: self.library.activate("compiler", "../outside"))

    def test_corrupted_admission_record_is_not_an_admission(self):
        pin = self.library.definitions["compiler"]["pin"]
        record_path = self.library.root / pin / "admission.json"
        record = json.loads(record_path.read_text())
        record["self_test"]["executed"] = False
        record_path.write_bytes(canonical(record))
        self.assert_code("CAPSULE_NOT_ADMITTED", self.library.resolve)

    def test_projection_tampering_and_audit_tampering_are_rejected(self):
        projection = json.loads(self.library.standing_path.read_text())
        pristine = canonical(projection)
        projection["roles"]["compiler"]["status"] = "deprecated"
        self.library.standing_path.write_bytes(canonical(projection))
        self.assert_code("CAPSULE_STANDING_INVALID", self.library.resolve)
        self.library.standing_path.write_bytes(pristine)
        records = self.audit()
        records[0]["changes"]["compiler"]["status"] = "deprecated"
        self.library.audit_path.write_bytes(b"\n".join(canonical(record) for record in records) + b"\n")
        self.assert_code("CAPSULE_AUDIT_INVALID", self.library.resolve)

    def test_committed_audit_survives_interrupted_projection_write(self):
        with patch.object(self.library, "_write_projection", side_effect=OSError("Interrupted projection")):
            with self.assertRaises(OSError):
                self.library.suspend("compiler")
        self.assert_code("CAPSULE_ACTIVATION_REQUIRED", self.library.resolve)
        recovered = json.loads(self.library.standing_path.read_text())
        self.assertEqual(recovered["sequence"], 2)
        self.assertEqual(recovered["roles"]["compiler"]["status"], "suspended")

    def test_invalid_syntax_or_stale_imported_prompt_fails_structural_admission(self):
        model_source = self.sources / "model.py"
        model_source.write_text("def invalid(:\n", encoding="utf-8")
        self.assert_code("CAPSULE_ADMISSION_SELF_TEST_FAILED", lambda: CapsuleLibrary(self.root / "syntax-failure"))
        model_source.write_bytes((self.library.root / self.library.definitions["compiler"]["pin"] / "implementation" / "model.py").read_bytes())
        source = self.sources / "contracts.py"
        source.write_text(source.read_text(encoding="utf-8") + '\nCOMPILER_INSTRUCTIONS = "Changed source after imports"\n', encoding="utf-8")
        self.assert_code("CAPSULE_ADMISSION_SELF_TEST_FAILED", lambda: CapsuleLibrary(self.root / "prompt-failure"))

    def test_audit_and_admission_growth_are_bounded(self):
        with patch("jiuwenswarm.research.library.MAX_AUDIT_RECORDS", 1):
            self.assert_code("CAPSULE_AUDIT_LIMIT", lambda: self.library.suspend("compiler"))
        source = self.sources / "model.py"
        source.write_bytes(source.read_bytes() + b"\n# new source\n")
        with patch("jiuwenswarm.research.library.MAX_ADMISSIONS", 2):
            self.assert_code("CAPSULE_ADMISSION_LIMIT", lambda: CapsuleLibrary(self.library.root))


if __name__ == "__main__":
    unittest.main()
