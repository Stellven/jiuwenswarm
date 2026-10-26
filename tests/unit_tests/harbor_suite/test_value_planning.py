"""Production component checks against independently specified constraints."""
from pathlib import Path
import ast
import subprocess
import sys
import tempfile
import json
import unittest

from benchmarks.harbor_suite import value_planning as subject

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/research/planning"


class PlanningComponentTests(unittest.TestCase):
    def test_production_and_independent_python_against_constructed_expectations(self):
        rows = subject.cases(FIXTURES)
        self.assertEqual(len(rows), 8)
        for row in rows:
            with self.subTest(row["challenge"]):
                measured = subject.production_measure(row["packet"])
                self.assertEqual(measured["answer"], row["expected"])
                self.assertEqual(subject.ordinary_validate(row["packet"]), row["expected"])
                self.assertFalse(measured["admission_claim"])
                self.assertFalse(measured["full_unit_primary"])

    def test_materialized_skill_executes_without_product_imports_or_private_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "cases"
            result = subject.prepare(FIXTURES, root)
            self.assertTrue(result["all_production_answers_match"])
            script = root / "public/planning-validator-skill/validate_plan.py"
            parsed = ast.parse(script.read_text())
            imports = [alias.name for node in ast.walk(parsed) if isinstance(node, ast.Import) for alias in node.names]
            self.assertEqual(imports, ["json", "sys"])
            packet = root / "public/planning-07/candidate.json"
            run = subprocess.run([sys.executable, str(script), str(packet)], check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(run.stdout), {"reject": True,
                "failed_checks": ["brief_coverage", "budget_ceilings", "resource_feasibility"]})
            self.assertFalse(list((root / "public").rglob("*.expected.json")))


if __name__ == "__main__":
    unittest.main()
