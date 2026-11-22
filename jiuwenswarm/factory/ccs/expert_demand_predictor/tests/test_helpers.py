import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CAPSULE = Path(__file__).resolve().parents[1]
HELPERS = CAPSULE / "helpers"


class HelperTests(unittest.TestCase):
    def setUp(self):
        scratch = CAPSULE / "tests/.cc-state"
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def invoke(self, helper, *args):
        return subprocess.run(
            [sys.executable, str(HELPERS / helper), *map(str, args)],
            capture_output=True, text=True, check=False,
        )

    def test_expect_silent_checks_every_prefixed_line(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            log = Path(directory) / "candidate.log"
            command = [
                sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "helpers/check_markers.py"),
                str(log), "--name", "expert_demand_predictor", "--expect-silent",
            ]
            log.write_text("stock: loading\nother_expert_demand_predictor: active\n")
            silent = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(silent.returncode, 0, silent.stderr)
            log.write_text("INFO expert_demand_predictor: undocumented marker\n")
            noisy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(noisy.returncode, 1, noisy.stderr)
            self.assertEqual(json.loads(noisy.stdout)["unexpected_marker_lines"], [1])

    def test_marker_counts_and_load_mode(self):
        log = self.root / "server.log"
        name = "expert_demand_predictor"
        log.write_text(
            "I load_tensors: loading model tensors (load_mode = none)\n"
            f"I {name}: inactive (unmapped)\nI {name}: stats hits=0\n"
            f"I unrelated_{name}: active mmap\n"
        )
        result = self.invoke("check_markers.py", log, "--require-active", "--require-mmap")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "load_modes": ["none"], "markers": {"active": 0, "inactive": 1, "stats": 1},
        })

    def test_parity_plan_and_comparison(self):
        plan = self.invoke("parity_template.py", "plan", "/stock", "/candidate", "/model",
                           self.root, "--", "-ngl", "0")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        lines = plan.stdout.splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertTrue(line.endswith("5175 -ngl 0 -lm mmap -lv 4"))
        self.assertTrue(lines[0].startswith("env -u LLAMA_EXPERT_PREDICT "))
        self.assertTrue(lines[2].startswith("env LLAMA_EXPERT_PREDICT=1 "))

        for name, tokens in (("stock", [3, 4]), ("off", [3, 4]), ("on", [3, 5])):
            (self.root / f"{name}.json").write_text(json.dumps({"content": "same", "tokens": tokens}))
        result = self.invoke("parity_template.py", "compare", self.root)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "candidate_off_matches": True, "candidate_on_matches": False,
        })

    def test_replay_uses_causal_history_and_resets_per_request(self):
        result = self.invoke("replay_score.py", HELPERS / "synthetic_trace.jsonl",
                             "--layers", 2, "--bytes-per-expert", 4096)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "coverage": 4 / 7, "forecasts": 4, "hits": 4, "misses": 3,
            "requests": 2, "simulated_wasted_bytes": 7 * 4096, "targets": 4,
        })


if __name__ == "__main__":
    unittest.main()
