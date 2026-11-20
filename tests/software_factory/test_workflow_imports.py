"""Contract checks against actual imported upstream source, without device claims.

Set FACTORY_LIBRARY_IMPORT_ROOT to a completed import directory to run the
source checks. Their explicit skip when sources are absent is not engineering
or hardware acceptance. Input-custody checks always run and use actual files.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from jiuwenswarm.software_factory import library_operations as operations
from jiuwenswarm.software_factory.workflow_imports import (
    PROJECTS, _evidence, _googletest_parts, _strata_parts,
    import_project, parent_composition, validate_composition,
)


class InputCustodyTests(unittest.TestCase):
    def test_changed_artifact_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "algorithm.json"
            path.write_text('{"operation":"routing"}\n')
            artifact = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(operations._read({"algorithm": artifact}, "algorithm")["operation"], "routing")
            path.write_text('{"operation":"different"}\n')
            with self.assertRaisesRegex(ValueError, "changed"):
                operations._read({"algorithm": artifact}, "algorithm")

    def test_importer_rejects_unreviewed_repository_before_process(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "reviewed"):
                import_project(Path(directory), "https://example.invalid/not-approved")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_source_evidence_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            (Path(directory) / "outside.cpp").write_text("int outside;\n")
            with self.assertRaisesRegex(ValueError, "escapes"):
                _evidence(root, "../outside.cpp")

    def test_source_project_manifest_detects_changed_cpp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {}
            for relative in ("src/strata_core.cpp", "include/strata_core.h", "CMakeLists.txt"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("real inspected bytes\n")
                files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = {"schema": "factory.source-project.v1", "source_dir": str(root), "files": files}
            self.assertEqual(operations._checked_project(manifest), root)
            (root / "src/strata_core.cpp").write_text("changed bytes\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                operations._checked_project(manifest)

    def test_packaging_refreshes_exact_source_integrity_and_preserves_construction_bytes(self):
        """Metadata-only regression; this does not claim compilation or math."""
        from jiuwenswarm.software_factory.native_build import prepare
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "construction"
            source.mkdir()
            original_cmake = b"cmake_minimum_required(VERSION 3.24)\nproject(integrity_test LANGUAGES CXX)\n"
            (source / "CMakeLists.txt").write_bytes(original_cmake)
            original_metadata = {
                "source_commit": "a" * 40,
                "native_generation": {"complete": False, "precision_policy": "Unverified test metadata"},
                "generated_files": [{"path": "CMakeLists.txt", "sha256": hashlib.sha256(original_cmake).hexdigest(),
                                     "bytes": len(original_cmake)}],
            }
            original_project = (json.dumps(original_metadata) + "\n").encode()
            (source / "project.json").write_bytes(original_project)
            tests = root / "tests.cpp"
            tests.write_text("// Isolated metadata regression input; not executed as acceptance.\n")
            results = root / "results.json"
            results.write_text('{"scope":"metadata unit test"}\n')
            project = {"files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source.iterdir()}}
            files = operations._package_contents(source, project, tests, results, "b" * 40, "c" * 64)
            delivered = root / "delivered"
            for relative, raw in files.items():
                path = delivered / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            metadata = json.loads(files["project.json"])
            cmake_entry = next(row for row in metadata["generated_files"] if row["path"] == "CMakeLists.txt")
            self.assertNotEqual(cmake_entry["sha256"], hashlib.sha256(original_cmake).hexdigest())
            self.assertEqual(cmake_entry["sha256"], hashlib.sha256(files["CMakeLists.txt"]).hexdigest())
            self.assertEqual(files["reference/factory-original-CMakeLists.txt"], original_cmake)
            self.assertEqual(files["reference/factory-original-project.json"], original_project)
            self.assertEqual(metadata["factory_packaging"]["consumed_project_manifest_sha256"], "c" * 64)
            report = prepare(delivered, root / "not-built", source_only=True)
            self.assertEqual(report["source_integrity"], "PASS")
            self.assertFalse(report["native_device_validated"])
            self.assertEqual(report["native_compilation"], "NOT_RUN")
            (delivered / "CMakeLists.txt").write_text("changed after delivery\n")
            with self.assertRaisesRegex(ValueError, "Generated source changed"):
                prepare(delivered, root / "not-built", source_only=True)


class ReferenceCoverageTests(unittest.TestCase):
    """Isolated test-only reports; none represent a production executable run."""
    selected = [{"source_id": "source/a.cu:first", "binding": "invoke_first", "name": "first", "operation": "router"}]

    def inspect(self, directory: str, checks: list[dict], complete=True, **kwargs):
        path = Path(directory) / "test-only-process-stdout.log"
        path.write_text(json.dumps({"backend": "CPU", "coverage_complete": complete,
                                   "outputs_compared": 100000, "operation_checks": checks}) + "\n")
        return operations._baseline_report({"stdout_path": str(path)}, self.selected, **kwargs)

    def check(self, source_id="source/a.cu:first", status="passed", count=3):
        return {"source_id": source_id, "status": status, "outputs_compared": count,
                "max_abs_error": 0.0, "name": "first", "operation": "router"}

    def test_unrelated_comparisons_cannot_cover_selected_unverified_source(self):
        with tempfile.TemporaryDirectory() as directory:
            checks = [self.check(status="unverified", count=0), self.check("unrelated/b.cu:other", count=100000)]
            with self.assertRaisesRegex(ValueError, "source/a.cu:first"):
                self.inspect(directory, checks)

    def test_exit_success_without_complete_coverage_is_not_original_reference_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "incomplete"):
                self.inspect(directory, [self.check()], complete=False)

    def test_selected_counts_preserve_actual_checks_and_separate_unrelated_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.inspect(directory, [self.check(), self.check("unrelated/b.cu:other", count=100000)])
            self.assertEqual(result["outputs_compared"], 3)
            self.assertTrue(result["coverage_complete"])
            self.assertEqual(result["selected_source_ids"], ["source/a.cu:first"])
            self.assertEqual(len(result["unselected_operation_checks"]), 1)
            self.assertFalse(result["native_device_validated"])

    def test_explicit_optional_reference_retains_unverified_status(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.inspect(directory, [self.check(status="unverified", count=0)], complete=False,
                                  require_original_reference=False)
            self.assertEqual(result["status"], "unverified")
            self.assertFalse(result["coverage_complete"])
            self.assertFalse(result["reported_coverage_complete"])

    def test_duplicate_source_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.inspect(directory, [self.check(), self.check()])

    def test_shared_convenience_call_cannot_cover_two_selected_producers(self):
        selected = [self.selected[0], {"source_id": "source/b.cu:second", "binding": "invoke_second",
                                       "name": "second", "operation": "router"}]
        with self.assertRaisesRegex(ValueError, "unique binding"):
            operations._check_test_calls("strata_core::route(values, 2);", selected)
        operations._check_test_calls("strata_core::invoke_first(values, 2); strata_core::invoke_second(values, 2);", selected)
        # A single selected producer can still use its unambiguous public API.
        operations._check_test_calls("strata_core::route(values, 2);", self.selected)


class ParentCompositionTests(unittest.TestCase):
    """Reviewed graph-definition fixtures; no execution or produced-file claims."""
    @staticmethod
    def port(kind):
        return {"semantic_type": kind, "required": True}

    def strata_parts(self):
        return [
            {"id": "extract", "inputs": {}, "outputs": {"algorithm": self.port("source.algorithm")}},
            {"id": "generate", "inputs": {"algorithm": self.port("source.algorithm")},
             "outputs": {"project": self.port("source.project"), "cpp": self.port("source.cpp")}},
            {"id": "report", "inputs": {"algorithm": self.port("source.algorithm")},
             "outputs": {"report": self.port("analysis.report")}},
            {"id": "package", "inputs": {"project": self.port("source.project"), "results": self.port("verification.report")},
             "outputs": {"package": self.port("delivery.source_zip")}},
        ]

    def test_parent_dependencies_come_from_actual_bindings_and_external_boundary(self):
        composition = parent_composition("strata", self.strata_parts())
        edges = {(edge["from"], edge["to"], edge["output"], edge["input"]) for edge in composition["edges"]}
        self.assertEqual(edges, {("extract", "generate", "algorithm", "algorithm"),
                                 ("extract", "report", "algorithm", "algorithm"),
                                 ("generate", "package", "project", "project")})
        package = next(node for node in composition["nodes"] if node["id"] == "package")
        self.assertEqual(package["bindings"]["results"], {"node": "$input", "port": "verified_results"})
        self.assertEqual(package["depends_on"], ["generate"])
        self.assertFalse(composition["output_contracts"]["report"]["required"])
        self.assertFalse(composition["executable"])
        self.assertEqual(composition["execution_support"], "parts_only")
        self.assertFalse(composition["validation"]["parent_execution_performed"])

    def test_reordering_display_nodes_cannot_change_parent_dependencies(self):
        parts = self.strata_parts()
        composition = parent_composition("strata", parts)
        composition["nodes"].reverse()
        validated = validate_composition(parts, composition)
        self.assertEqual(set(tuple(sorted(edge.items())) for edge in composition["edges"]),
                         set(tuple(sorted(edge.items())) for edge in validated["edges"]))

    def test_unknown_part_output_external_input_and_missing_required_bindings_are_rejected(self):
        parts = self.strata_parts()
        original = parent_composition("strata", parts)
        for mutate, message in [
            (lambda value: value["nodes"][0].update(part="invented"), "unknown callable part"),
            (lambda value: value["nodes"][1]["bindings"]["algorithm"].update(port="invented"), "unknown producer output"),
            (lambda value: value["nodes"][3]["bindings"]["results"].update(port="invented"), "external input"),
            (lambda value: value["nodes"][1].update(bindings={}), "required declared"),
        ]:
            candidate = deepcopy(original)
            mutate(candidate)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_composition(parts, candidate)

    def test_semantic_mismatch_and_invented_dependencies_are_rejected(self):
        parts = self.strata_parts()
        original = parent_composition("strata", parts)
        incompatible = deepcopy(parts)
        incompatible[1]["inputs"]["algorithm"]["semantic_type"] = "test.framework"
        with self.assertRaisesRegex(ValueError, "incompatible semantic"):
            validate_composition(incompatible, original)
        original["nodes"][1]["depends_on"] = ["report"]
        with self.assertRaisesRegex(ValueError, "dependencies disagree"):
            validate_composition(parts, original)

    def test_dependency_cycle_is_rejected(self):
        port = self.port("same.type")
        parts = [{"id": "transform", "inputs": {"value": port}, "outputs": {"value": port}}]
        definition = {"inputs": {}, "nodes": [
            {"id": "first", "part": "transform", "bindings": {"value": {"node": "second", "port": "value"}}},
            {"id": "second", "part": "transform", "bindings": {"value": {"node": "first", "port": "value"}}}],
            "outputs": {"value": {"node": "first", "port": "value"}}}
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            validate_composition(parts, definition)


class ActualProjectImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get("FACTORY_LIBRARY_IMPORT_ROOT", "/workspace/factory-library-project-check"))
        paths = [cls.root / "imports" / identifier / "workflow-bundle.json" for identifier in ("strata", "googletest")]
        if not all(path.is_file() for path in paths):
            raise unittest.SkipTest("Actual two-project imports are absent; no network/build/device result is implied")
        cls.bundles = [json.loads(path.read_text()) for path in paths]

    def test_real_commits_remotes_and_clean_upstream_sources(self):
        for bundle in self.bundles:
            source = Path(bundle["source"]["checkout"])
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
            self.assertEqual(commit, bundle["source"]["revision"])
            self.assertEqual(len(commit), 40)
            self.assertEqual(subprocess.check_output(["git", "status", "--porcelain"], cwd=source, text=True), "")
            remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=source, text=True).strip()
            self.assertIn(remote.removesuffix(".git"), PROJECTS)

    def test_every_callable_has_real_source_evidence_and_wrapper(self):
        for bundle in self.bundles:
            self.assertGreater(len(bundle["subworkflows"]), 1)
            for part in bundle["subworkflows"]:
                self.assertTrue(Path(part["wrapper_manifest"]).is_file())
                self.assertEqual(part["provenance"]["origin_kind"], "factory_wrapper")
                self.assertFalse(part["provenance"]["upstream_is_workflow"])
                for evidence in part["source_evidence"]:
                    self.assertEqual(hashlib.sha256(Path(evidence["absolute_path"]).read_bytes()).hexdigest(), evidence["sha256"])
                    self.assertTrue(evidence["excerpt"])
                implementation = part["implementation"]
                if implementation["type"] == "agent":
                    prompt = Path(implementation["prompt_path"]).read_text()
                    self.assertIn("independent", prompt)
                    self.assertIn('"outputs"', prompt)
                else:
                    self.assertTrue(callable(getattr(operations, implementation["entrypoint"].split(":")[1])))

    def test_cross_workflow_ports_bind_without_schema_renaming(self):
        parts = {bundle["id"]: {part["id"]: part for part in bundle["subworkflows"]} for bundle in self.bundles}
        strata, googletest = parts["strata"], parts["googletest"]
        self.assertEqual(strata["extract"]["outputs"]["algorithm"]["semantic_type"], googletest["design_tests"]["inputs"]["algorithm"]["semantic_type"])
        self.assertEqual(strata["generate"]["outputs"]["project"]["semantic_type"], googletest["verify"]["inputs"]["project"]["semantic_type"])
        self.assertEqual(googletest["verify"]["outputs"]["results"]["semantic_type"], strata["package"]["inputs"]["results"]["semantic_type"])
        self.assertEqual(googletest["design_tests"]["implementation"]["type"], "agent")

    def test_new_definitions_read_actual_source_and_expose_bound_parent_graphs(self):
        for bundle in self.bundles:
            source = Path(bundle["source"]["checkout"])
            factory = _strata_parts if bundle["id"] == "strata" else _googletest_parts
            parts = factory(source, bundle["source"]["revision"])
            composition = parent_composition(bundle["id"], parts)
            self.assertEqual(composition["origin"], "factory_owned_wrapper")
            self.assertEqual({node["part"] for node in composition["nodes"]}, {part["id"] for part in parts})
            for part in parts:
                self.assertTrue(part["inspection"]["source_evidence"])
                implementation = part["inspection"]["implementation"]
                self.assertTrue(Path(implementation["path"]).is_file())
                self.assertGreaterEqual(implementation["line"], 1)
                self.assertGreaterEqual(implementation["end_line"], implementation["line"])
                for row in part["inspection"]["inputs"] + part["inspection"]["outputs"]:
                    self.assertTrue(row["expected_filename"])
                    self.assertFalse(row["production_observed"])
            if bundle["id"] == "googletest":
                nodes = {node["id"]: node for node in composition["nodes"]}
                self.assertEqual(nodes["design_tests"]["bindings"]["algorithm"], {"node": "$input", "port": "algorithm"})
                self.assertEqual(nodes["verify"]["bindings"]["project"], {"node": "$input", "port": "project"})
                self.assertEqual(nodes["verify"]["depends_on"], ["design_tests", "prepare"])


if __name__ == "__main__":
    unittest.main()
