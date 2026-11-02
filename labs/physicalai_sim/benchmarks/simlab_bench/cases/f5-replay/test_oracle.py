"""Oracle unit tests for f5-replay: correct evidence passes, defective evidence fails, missing evidence never passes."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("oracle_f5_replay", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
CRITERIA = json.loads((HERE / "referee" / "criteria.json").read_text())


def status(g):
    return {c["id"]: c["status"] for c in g["checks"]}


class OracleTests(unittest.TestCase):
    def test_correct_passes(self):
        g = oracle.evaluate({'variant_id': 'controlled-noisy', 'result': {'run_id': 'r1', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'second_run': {'run_id': 'r2', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'replay': {'run_id': 'r3', 'run_kind': 'replay', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': [{'check_id': 'replay_identity', 'status': 'pass'}]}}, CRITERIA)
        self.assertTrue(all(s == "pass" for s in status(g).values()), g)

    def test_defective_fails(self):
        g = oracle.evaluate({'variant_id': 'controlled-noisy', 'result': {'run_id': 'r1', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'second_run': {'run_id': 'r2', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'replay': {'run_id': 'r3', 'run_kind': 'replay', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'}], 'measurements': {'x': 1.0}}], 'checks': [{'check_id': 'replay_identity', 'status': 'pass'}]}}, CRITERIA)
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
