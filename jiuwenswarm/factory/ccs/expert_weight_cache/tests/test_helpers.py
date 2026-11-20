import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
HELPERS = HERE.parent / "helpers"
NAME = "fixture_cache"
MMAP = "load_tensors: loading tensors (load_mode = mmap)\n"


class HelpersTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.log = self.scratch / "server.log"

    def run_cli(self, helper, *args):
        return subprocess.run([sys.executable, "-B", str(HELPERS / helper), *map(str, args)],
                              capture_output=True, text=True)

    def test_expect_silent_checks_every_prefixed_line(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            log = Path(directory) / "candidate.log"
            command = [
                sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "helpers/check_markers.py"),
                str(log), "--name", "expert_weight_cache", "--expect-silent",
            ]
            log.write_text("stock: loading\nother_expert_weight_cache: active\n")
            silent = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(silent.returncode, 0, silent.stderr)
            log.write_text("INFO expert_weight_cache: undocumented marker\n")
            noisy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(noisy.returncode, 1, noisy.stderr)
            self.assertEqual(json.loads(noisy.stdout)["unexpected_marker_lines"], [1])

    def test_markers_require_active_mmap(self):
        helper = "check_markers.py"
        self.assertEqual(self.run_cli(helper, "--help").returncode, 0)
        args = (self.log, "--name", NAME, "--require-active")
        self.log.write_text(MMAP + f"INFO {NAME}: active cap_mib=1\n")
        result = self.run_cli(helper, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"mmap"', result.stdout)
        self.log.write_text(MMAP.replace("mmap", "none") + f"{NAME}: active cap_mib=1\n")
        self.assertEqual(self.run_cli(helper, *args).returncode, 1)
        self.log.write_text(MMAP + f"{NAME}: inactive (test bypass)\n")
        self.assertEqual(self.run_cli(helper, *args).returncode, 1)

    def test_stats_bound_and_reuse(self):
        helper = "check_cache_stats.py"
        self.assertEqual(self.run_cli(helper, "--help").returncode, 0)
        self.log.write_text(MMAP + f"{NAME}: active cap_mib=1\n"
                            f"{NAME}: stats leases=2 reuses=1 evictions=0 "
                            "bytes_copied_saved=4 peak_bytes=8\n")
        args = (self.log, "--name", NAME, "--expect", "reuse", "--admitted-bytes")
        self.assertEqual(self.run_cli(helper, *args, 8).returncode, 0)
        self.assertEqual(self.run_cli(helper, *args, 7).returncode, 1)

    def test_parity_runs_same_configuration_and_detects_mismatch(self):
        helper = "run_parity.py"
        self.assertEqual(self.run_cli(helper, "--help").returncode, 0)
        stub = self.scratch / "one-shot"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "assert sys.argv[3:] == ['5175', '-ngl', '0', '-lm', 'mmap']\n"
            "assert pathlib.Path(os.environ['MODEL']).name == 'model'\n"
            "prefix = pathlib.Path(sys.argv[2])\n"
            "gate = os.getenv('LLAMA_EXPERT_CACHE')\n"
            "assert gate == ('1' if prefix.name == 'candidate_on' else None)\n"
            "token = 9 if prefix.parent.name == 'mismatch' and gate else 1\n"
            "prefix.with_suffix('.json').write_text(json.dumps("
            "{'tokens': [token], 'content': 'text', 'stop_type': 'limit'}))\n"
        )
        stub.chmod(0o700)
        args = ("--one-shot", stub, "--stock", self.scratch / "base",
                "--candidate", self.scratch / "candidate", "--model", self.scratch / "model")
        for output, expected in (("match", 0), ("mismatch", 1)):
            with self.subTest(output=output):
                result = self.run_cli(helper, *args, "--output", self.scratch / output,
                                      "--", "-ngl", "0", "-lm", "mmap")
                self.assertEqual(result.returncode, expected, result.stderr)
        result = self.run_cli(helper, *args, "--output", self.scratch / "other-port",
                              "--", "--port=8080")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.scratch / "other-port").exists())


if __name__ == "__main__":
    unittest.main()
