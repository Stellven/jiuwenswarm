"""Exercise the relocated plugin against real, isolated PowerShell projects."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


class PluginIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not POWERSHELL:
            raise RuntimeError("PowerShell is required; these checks cannot be skipped.")
        cls.sandbox = tempfile.TemporaryDirectory(prefix="speckit_plugin_")
        cls.root = Path(cls.sandbox.name)
        cls.package = cls.root / "relocated plugin with spaces"
        shutil.copytree(PACKAGE, cls.package, ignore=shutil.ignore_patterns("__pycache__"))

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def setUp(self):
        self.project = self.root / self._testMethodName / "project with spaces"
        self.project.mkdir(parents=True)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("SPECIFY_")}

    def helper(self, name, *args, success=True):
        command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(self.package / "scripts" / "powershell" / name), *map(str, args)]
        result = subprocess.run(command, cwd=self.project, env=self.env,
                                capture_output=True, encoding="utf-8", errors="replace", timeout=30)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def initialize(self):
        return json.loads(self.helper("init-project.ps1", "-ProjectRoot", self.project, "-Json").stdout)

    def test_package_is_self_contained(self):
        manifest = json.loads((self.package / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "spec-kit")
        skills = list((self.package / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(skills), 12)
        self.assertTrue((self.package / "LICENSE").is_file())
        for skill in skills:
            self.assertNotIn(".specify/scripts/", skill.read_text(encoding="utf-8"))

    def test_initialization_preserves_project_files(self):
        self.initialize()
        constitution = self.project / ".specify/memory/constitution.md"
        constitution.write_text("Existing project principles\n", encoding="utf-8")
        override = self.project / ".specify/templates/overrides/spec-template.md"
        override.write_text("Existing override\n", encoding="utf-8")
        second = self.initialize()
        self.assertEqual(second["CREATED_FILES"], [])
        self.assertEqual(constitution.read_text(encoding="utf-8"), "Existing project principles\n")
        self.assertEqual(override.read_text(encoding="utf-8"), "Existing override\n")
        self.assertFalse((self.project / ".specify/scripts").exists())
        self.assertFalse((self.project / ".agents/skills").exists())

    def test_bundled_templates_and_project_override_priority(self):
        self.initialize()
        for name in ("spec-template", "plan-template", "tasks-template", "constitution-template", "checklist-template", "TASKS_TEMPLATE", "TASK_TEMPLATE", "EVIDENCE_TEMPLATE", "AGENTS_global", "AGENTS_local"):
            with self.subTest(template=name):
                output = json.loads(self.helper("resolve-template.ps1", name, "-Json").stdout)
                expected = (self.package / "templates" / f"{name}.md").read_text(encoding="utf-8")
                self.assertEqual(output["TEMPLATE_CONTENT"].replace("\r\n", "\n"), expected)
                override = self.project / f".specify/templates/overrides/{name}.md"
                override.write_text(f"Project override: {name}\n", encoding="utf-8")
                output = json.loads(self.helper("resolve-template.ps1", name, "-Json").stdout)
                self.assertEqual(output["TEMPLATE_CONTENT"].replace("\r\n", "\n"), f"Project override: {name}\n")

    def test_selected_feature_and_existing_plan_are_preserved(self):
        self.initialize()
        feature = self.project / "docs/code/Missions/UNIT/UNIT-001"
        feature.mkdir(parents=True)
        (feature / "spec.md").write_text("Selected spec\n", encoding="utf-8")
        (feature / "tasks.md").write_text("Existing work and evidence\n", encoding="utf-8")
        self.env["SPECIFY_FEATURE_DIRECTORY"] = "docs/code/Missions/UNIT/UNIT-001"
        (self.project / ".specify/feature.json").write_text(
            json.dumps({"feature_directory": "docs/code/Missions/UNIT/999-wrong"}), encoding="utf-8")
        planned = json.loads(self.helper("setup-plan.ps1", "-Json").stdout)
        self.assertEqual(Path(planned["FEATURE_DIR"]), feature)
        self.assertTrue((feature / "plan.md").read_text(encoding="utf-8"))
        (feature / "plan.md").write_text("Existing design and evidence\n", encoding="utf-8")
        self.helper("setup-plan.ps1", "-Json")
        self.assertEqual((feature / "plan.md").read_text(encoding="utf-8"), "Existing design and evidence\n")
        checked = json.loads(self.helper("check-prerequisites.ps1", "-Json", "-RequireSpec", "-RequireTasks", "-IncludeTasks").stdout)
        self.assertEqual(Path(checked["FEATURE_DIR"]), feature)
        tasks = json.loads(self.helper("setup-tasks.ps1", "-Json").stdout)
        self.assertEqual(Path(tasks["TASKS_TEMPLATE"]), self.package / "templates/tasks-template.md")
        self.assertEqual((feature / "tasks.md").read_text(encoding="utf-8"), "Existing work and evidence\n")

    def test_feature_creation_uses_bundled_spec(self):
        self.initialize()
        selected = self.project / "docs/code/Missions/UNIT/UNIT-001"
        selected.mkdir(parents=True)
        (selected / "TASK.md").write_text("Registered task\n", encoding="utf-8")
        self.env["SPECIFY_FEATURE_DIRECTORY"] = "docs/code/Missions/UNIT/UNIT-001"
        created = json.loads(self.helper("create-new-feature.ps1", "-Json", "-Number", "1",
                                         "-ShortName", "plugin-fixture", "Verify plugin feature generation").stdout)
        spec = Path(created["SPEC_FILE"])
        self.assertEqual(spec.parent, selected)
        self.assertFalse((self.project / "specs").exists())
        self.assertEqual(spec.read_text(encoding="utf-8"),
                         (self.package / "templates/spec-template.md").read_text(encoding="utf-8"))
        spec.write_text("Existing acceptance and references\n", encoding="utf-8")
        self.helper("create-new-feature.ps1", "-Json", "-Number", "1", "-ShortName", "plugin-fixture", "Reuse registered task")
        self.assertEqual(spec.read_text(encoding="utf-8"), "Existing acceptance and references\n")
        self.assertTrue((self.project / ".specify/feature.json").is_file())
        self.assertFalse((self.package / ".specify").exists())

    def test_registered_task_records_remain_project_owned(self):
        self.initialize()
        records = {
            "docs/code/Missions/UNIT/TASKS.md": "Program with existing allocation\n",
            "docs/code/Missions/UNIT/UNIT-001/TASK.md": "Feature directory: docs/code/Missions/UNIT/UNIT-001/\n",
            "docs/code/Missions/UNIT/UNIT-001/spec.md": "Existing acceptance criteria\n",
            "docs/code/Missions/UNIT/UNIT-001/plan.md": "Existing technical decisions\n",
            "docs/code/Missions/UNIT/UNIT-001/tasks.md": "Completed work and evidence\n",
        }
        for name, content in records.items():
            p = self.project / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        self.env["SPECIFY_FEATURE_DIRECTORY"] = "docs/code/Missions/UNIT/UNIT-001"
        self.initialize()
        self.helper("setup-plan.ps1", "-Json")
        self.helper("setup-tasks.ps1", "-Json")
        output = json.loads(self.helper("check-prerequisites.ps1", "-Json", "-RequireSpec", "-RequireTasks").stdout)
        self.assertEqual(Path(output["FEATURE_DIR"]), self.project / "docs/code/Missions/UNIT/UNIT-001")
        for name, content in records.items():
            self.assertEqual((self.project / name).read_text(encoding="utf-8"), content)
        self.assertFalse((self.package / "docs/code/Missions").exists())
        self.assertFalse((self.package / "specs").exists())

    def test_feature_creation_requires_registered_task(self):
        self.initialize()
        result = self.helper("create-new-feature.ps1", "-Json", "Unregistered task", success=False)
        self.assertIn("speckit-register", result.stderr)
        self.assertFalse((self.project / "specs").exists())

    def test_uninitialized_project_is_rejected_without_cache_writes(self):
        result = self.helper("resolve-template.ps1", "spec-template", "-Json", success=False)
        self.assertIn("speckit-init", result.stderr)
        self.assertFalse((self.package / ".specify").exists())
        self.assertFalse((self.project / ".specify").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
