"""The pilot task build contexts must never contain referee answers."""
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from benchmarks.harbor_pilot.prepare import prepare_bundle
from jiuwenswarm.research_sidecar.sequential_cases import load_cases


IMAGE = "python:3.12-slim@sha256:" + "3" * 64


class PrepareBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.samples = self.root / "samples"
        self.criteria = self.root / "private"
        self.criteria.mkdir()
        self.grader = self.root / "grade.py"
        self.grader.write_text("# standalone grading implementation\n", encoding="utf-8")
        for case, source_id in (("cpu", "case1-cpu"), ("paper", "case3-paper")):
            source = self.samples / "cases/demos-20261023" / (source_id + ".json")
            source.parent.mkdir(parents=True, exist_ok=True)
            public_name = f"demos-20261023/{source_id}/input.txt"
            public = self.samples / "inputs" / public_name
            public.parent.mkdir(parents=True)
            public.write_text("public task data", encoding="utf-8")
            document = {
                "schema_version": "sequential-cases:1",
                "cases": [{
                    "id": source_id,
                    "task": "Investigate the technical question using supplied data.",
                    "inputs": [
                        {"path": public_name, "kind": "docs"},
                        {"path": "obsolete-runtime.json", "upload": False},
                    ],
                    "setup": [{"trusted": True, "command": ["python", "historical-provenance.py"]}],
                    "repeats": 2,
                }],
            }
            source.write_text(json.dumps(document), encoding="utf-8")
            criteria = {"schema": "ai4r-harbor-criteria:1", "case_id": case}
            if case == "cpu":
                criteria["cpu"] = {"labels_path": "fixtures/test_labels.csv"}
            (self.criteria / (case + ".json")).write_text(json.dumps(criteria), encoding="utf-8")
        labels = self.criteria / "fixtures/test_labels.csv"
        labels.parent.mkdir()
        labels.write_text("id,label\nsecret-record,protected-answer\n", encoding="utf-8")

    def prepare(self, **kwargs):
        arguments = {
            "sample_root": self.samples,
            "destination": self.root / "bundle",
            "criteria_root": self.criteria,
            "python_image": IMAGE,
            "harbor_version": "0.24.0",
            "grader": self.grader,
        }
        arguments.update(kwargs)
        return prepare_bundle(**arguments)

    def test_contexts_separate_labels_and_drop_old_provenance(self):
        manifest = self.prepare()
        bundle = self.root / "bundle"
        for case in ("cpu", "paper"):
            case_document = load_cases(bundle / "cases" / (case + ".json"))
            case_row = case_document["cases"][0]
            self.assertEqual(case_row["repeats"], 1)
            self.assertEqual(case_row["setup"], [])
            self.assertEqual(len(case_row["inputs"]), 1)
            self.assertTrue(case_row["inputs"][0]["upload"])
            task = bundle / "tasks" / case
            self.assertTrue((task / "instruction.md").read_text().startswith("AI4R_HARBOR_CASE: " + case + "\n"))
            self.assertEqual({p.name for p in (task / "environment").iterdir()}, {"Dockerfile", ".dockerignore"})
            task_config = tomllib.loads((task / "task.toml").read_text())
            self.assertEqual(task_config["artifacts"], ["/app/ai4r-evidence"])
            self.assertEqual(task_config["verifier"]["environment_mode"], "separate")
            self.assertEqual(task_config["verifier"]["environment"]["network_mode"], "no-network")
        self.assertTrue((bundle / "tasks/cpu/tests/fixtures/test_labels.csv").is_file())
        self.assertIn("!fixtures/", (bundle / "tasks/cpu/tests/.dockerignore").read_text())
        for selected in manifest["files"]:
            if "protected-answer" in (bundle / selected["path"]).read_text():
                self.assertEqual(selected["audience"], "referee")
                self.assertIn("/tests/", selected["path"])
        self.assertFalse((bundle / "inputs/obsolete-runtime.json").exists())
        job = json.loads((bundle / "job.json").read_text())
        self.assertEqual(job["n_concurrent_trials"], 1)
        self.assertEqual(job["n_attempts"], 1)
        self.assertEqual(job["retry"]["max_retries"], 0)
        self.assertFalse(job["environment"]["delete"])
        self.assertEqual(job["agents"][0]["import_path"], "benchmarks.harbor_pilot.adapter:AI4ResearchAgent")

    def test_existing_bundle_is_never_overwritten(self):
        self.prepare()
        before = (self.root / "bundle/bundle-manifest.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "existing bundles"):
            self.prepare()
        self.assertEqual((self.root / "bundle/bundle-manifest.json").read_bytes(), before)

    def test_unpinned_image_rejected_before_destination_creation(self):
        with self.assertRaisesRegex(ValueError, "pinned"):
            self.prepare(python_image="python:latest")
        self.assertFalse((self.root / "bundle").exists())

    def test_missing_protected_labels_cannot_publish_a_job(self):
        (self.criteria / "fixtures/test_labels.csv").unlink()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse((self.root / "bundle").exists())

    def test_label_traversal_rejected_before_any_copy(self):
        (self.criteria / "cpu.json").write_text(json.dumps({
            "schema": "ai4r-harbor-criteria:1", "case_id": "cpu",
            "cpu": {"labels_path": "../outside.csv"},
        }))
        with self.assertRaisesRegex(ValueError, "relative"):
            self.prepare()
        self.assertFalse((self.root / "bundle").exists())


if __name__ == "__main__":
    unittest.main()
