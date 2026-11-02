"""Oracle unit tests for f1-tb09-determinism: correct evidence passes, defective evidence fails, missing evidence never passes."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("oracle_f1_tb09_determinism", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
CRITERIA = json.loads((HERE / "referee" / "criteria.json").read_text())


def status(g):
    return {c["id"]: c["status"] for c in g["checks"]}


class OracleTests(unittest.TestCase):
    def test_correct_passes(self):
        g = oracle.evaluate({'variant_id': 'controlled-noisy', 'result': {'run_id': 'r1', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'second_run': {'run_id': 'r2', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'replay': {'run_id': 'r3', 'run_kind': 'replay', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': [{'check_id': 'replay_identity', 'status': 'pass'}]}, 'checkpoint': {'time_s': 1.0}, 'original_after_checkpoint': {'qpos:hinge': [[1.0, 0], [1.01, 1], [1.02, 2], [1.03, 3], [1.04, 4], [1.05, 5], [1.06, 6], [1.07, 7], [1.08, 8], [1.09, 9], [1.1, 10], [1.11, 11], [1.12, 12], [1.13, 13], [1.1400000000000001, 14], [1.15, 15], [1.16, 16], [1.17, 17], [1.18, 18], [1.19, 19]]}, 'branch_after_checkpoint': {'qpos:hinge': [[1.0, 0], [1.01, 1], [1.02, 2], [1.03, 3], [1.04, 4], [1.05, 5], [1.06, 6], [1.07, 7], [1.08, 8], [1.09, 9], [1.1, 10], [1.11, 11], [1.12, 12], [1.13, 13], [1.1400000000000001, 14], [1.15, 15], [1.16, 16], [1.17, 17], [1.18, 18], [1.19, 19]]}}, CRITERIA)
        self.assertTrue(all(s == "pass" for s in status(g).values()), g)

    def test_defective_fails(self):
        g = oracle.evaluate({'variant_id': 'controlled-noisy', 'result': {'run_id': 'r1', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'second_run': {'run_id': 'r2', 'run_kind': 'original', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}], 'measurements': {'x': 1.0}}], 'checks': []}, 'replay': {'run_id': 'r3', 'run_kind': 'replay', 'status': 'COMPLETED', 'trials': [{'attempts': [{'status': 'COMPLETED', 'state_digest': 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'}], 'measurements': {'x': 1.0}}], 'checks': [{'check_id': 'replay_identity', 'status': 'pass'}]}, 'checkpoint': {'time_s': 1.0}, 'original_after_checkpoint': {'qpos:hinge': [[1.0, 0], [1.01, 1], [1.02, 2], [1.03, 3], [1.04, 4], [1.05, 5], [1.06, 6], [1.07, 7], [1.08, 8], [1.09, 9], [1.1, 10], [1.11, 11], [1.12, 12], [1.13, 13], [1.1400000000000001, 14], [1.15, 15], [1.16, 16], [1.17, 17], [1.18, 18], [1.19, 19]]}, 'branch_after_checkpoint': {'qpos:hinge': [[1.0, 0], [1.01, 1], [1.02, 2], [1.03, 3], [1.04, 4], [1.05, 5], [1.06, 6], [1.07, 7], [1.08, 8], [1.09, 9], [1.1, 10], [1.11, 11], [1.12, 12], [1.13, 13], [1.1400000000000001, 14], [1.15, 15], [1.16, 16], [1.17, 17], [1.18, 18], [1.19, 19]]}}, CRITERIA)
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
