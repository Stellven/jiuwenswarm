"""Oracle unit tests for f1-tb08-box-stack: correct evidence passes, defective evidence fails, missing evidence never passes."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("oracle_f1_tb08_box_stack", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
CRITERIA = json.loads((HERE / "referee" / "criteria.json").read_text())


def status(g):
    return {c["id"]: c["status"] for c in g["checks"]}


class OracleTests(unittest.TestCase):
    def test_correct_passes(self):
        g = oracle.evaluate({'variant_id': 'equal-masses', 'execution': {'status': 'COMPLETED'}, 'result': {'run_id': 'run-x', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}], 'measurements': {'floor_force': 29.43, 'top_drift': 1e-07, 'penetration': 0.0004}}]}, 'traces': {'contact:normal_force:floor:g1': [[0, 29.0], [2, 29.43]]}}, CRITERIA)
        self.assertTrue(all(s == "pass" for s in status(g).values()), g)

    def test_defective_fails(self):
        g = oracle.evaluate({'variant_id': 'equal-masses', 'execution': {'status': 'COMPLETED'}, 'result': {'run_id': 'run-x', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}], 'measurements': {'floor_force': 0.0, 'top_drift': 1e-07, 'penetration': 0.0}}]}, 'traces': {'contact:normal_force:floor:g1': [[0, 0.0], [2, 0.0]]}}, CRITERIA)
        self.assertIn("fail", status(g).values(), g)

    def test_missing_evidence_never_passes(self):
        for ev in ({"variant_id": next(iter(CRITERIA["variants"]))}, {"variant_id": "nope"}):
            g = oracle.evaluate(ev, CRITERIA)
            self.assertFalse(g["checks"] and all(c["status"] == "pass" for c in g["checks"]), g)

    def test_stdlib_only(self):
        import ast, sys
        tree = ast.parse((HERE / "oracle.py").read_text())
        mods = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
            a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertTrue(mods <= set(sys.stdlib_module_names) | {""}, mods)


if __name__ == "__main__":
    unittest.main()
