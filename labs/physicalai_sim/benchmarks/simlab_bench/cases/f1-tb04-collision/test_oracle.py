"""Oracle unit tests for f1-tb04-collision: correct evidence passes, defective evidence fails, missing evidence never passes."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("oracle_f1_tb04_collision", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
CRITERIA = json.loads((HERE / "referee" / "criteria.json").read_text())


def status(g):
    return {c["id"]: c["status"] for c in g["checks"]}


class OracleTests(unittest.TestCase):
    def test_correct_passes(self):
        g = oracle.evaluate({'variant_id': 'elastic-1to1', 'execution': {'status': 'COMPLETED'}, 'result': {'run_id': 'run-x', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}], 'measurements': {'restitution': 1.0, 'momentum_drift': 1e-15}}]}, 'traces': {'qvel:ja': [[0.0, 1.0], [0.3, 0.0]], 'qvel:jb': [[0.0, 0.0], [0.3, 1.0]]}, 'events': [{'t': 0.1, 'event_id': 'touch', 'kind': 'contact_begin'}, {'t': 0.2, 'event_id': 'release', 'kind': 'contact_end'}]}, CRITERIA)
        self.assertTrue(all(s == "pass" for s in status(g).values()), g)

    def test_defective_fails(self):
        g = oracle.evaluate({'variant_id': 'elastic-1to1', 'execution': {'status': 'COMPLETED'}, 'result': {'run_id': 'run-x', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}], 'measurements': {'restitution': 0.7, 'momentum_drift': 0.2}}]}, 'traces': {'qvel:ja': [[0.0, 1.0], [0.3, 0.1]], 'qvel:jb': [[0.0, 0.0], [0.3, 0.8]]}}, CRITERIA)
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
