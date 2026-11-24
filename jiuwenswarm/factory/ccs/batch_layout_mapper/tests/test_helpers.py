import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from tempfile import TemporaryDirectory
import unittest


CAPSULE = Path(__file__).resolve().parents[1]


class HelperTests(unittest.TestCase):
    def invoke(self, name, *args, **kwargs):
        return subprocess.run(
            [sys.executable, "-B", str(CAPSULE / "helpers" / f"{name}.py"), *map(str, args)],
            capture_output=True, text=True, **kwargs,
        )

    def test_expect_silent_checks_every_prefixed_line(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            log = Path(directory) / "candidate.log"
            command = [
                sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "helpers/check_markers.py"),
                str(log), "--name", "batch_layout_mapper", "--expect-silent",
            ]
            log.write_text("stock: loading\nother_batch_layout_mapper: active\n")
            silent = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(silent.returncode, 0, silent.stderr)
            log.write_text("INFO batch_layout_mapper: undocumented marker\n")
            noisy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(noisy.returncode, 1, noisy.stderr)
            self.assertEqual(json.loads(noisy.stdout)["unexpected_marker_lines"], [1])

    def test_marker_checker_requires_active_and_effective_load_mode(self):
        with TemporaryDirectory(dir=CAPSULE / "tests") as temp:
            log = Path(temp) / "server.log"
            log.write_text("load_tensors: loading model tensors (load_mode = none)\n"
                           "fixture: inactive (test control)\nfixture: stats decisions=0\n")
            args = (log, "--name", "fixture", "--require", "active", "--load-mode", "mmap")
            rejected = self.invoke("check_markers", *args)
            report = json.loads(rejected.stdout)
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(report["missing"], ["active"])
            self.assertEqual(report["load_modes"], ["none"])
            self.assertFalse(report["load_mode_matches"])

            log.write_text("load_tensors: loading model tensors (load_mode = mmap)\n"
                           "fixture: active n_batch=13\nfixture: layout begin=0 end=8\n")
            accepted = self.invoke("check_markers", *args, check=True)
            markers = json.loads(accepted.stdout)["markers"]
            self.assertEqual(markers["active"][0]["line"], 2)
            self.assertEqual(len(markers["layout"]), 1)

    def test_parity_compares_all_arms_with_shared_args(self):
        with TemporaryDirectory(dir=CAPSULE / "tests") as temp:
            root = Path(temp)
            wrapper = root / "fake-wrapper.sh"
            wrapper.write_text(
                'set -eu\n'
                '[[ "$3 $4 $5 $6 $7" == "5175 -ngl 0 -lv 4" ]]\n'
                'case "$2" in\n'
                '  */stock) [[ "$1" == */bare && ! -v LLAMA_BATCH_LAYOUT ]] ;;\n'
                '  */off) [[ "$1" == */candidate && ! -v LLAMA_BATCH_LAYOUT ]] ;;\n'
                '  */on) [[ "$1" == */candidate && "$LLAMA_BATCH_LAYOUT" == 1 ]] ;;\n'
                'esac\n'
                'tokens=1\n'
                'if [[ "$2" == */mismatch/on ]]; then tokens=2; fi\n'
                'printf \'{"content":"hi","tokens":[%s],"stop":true,"stop_type":"limit"}\' '
                '"$tokens" > "$2.json"\n'
            )
            for case, expected in (("match", True), ("mismatch", False)):
                with self.subTest(case=case):
                    result = self.invoke(
                        "parity", "--wrapper", wrapper, "--stock", root / "bare",
                        "--candidate", root / "candidate", "--out", root / case,
                        "--", "-ngl", "0", env={**os.environ, "LLAMA_BATCH_LAYOUT": "inherited"},
                    )
                    self.assertEqual(result.returncode, int(not expected), result.stderr)
                    self.assertEqual(json.loads(result.stdout)["matches_stock"],
                                     {"off": True, "on": expected})

    def test_prompt_sweep_covers_14_lengths_in_both_cache_modes(self):
        result = self.invoke("prompt_sweep", check=True)
        records = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(records), 28)
        self.assertEqual(len({record["id"] for record in records}), 28)
        for cold, primed in zip(records[::2], records[1::2]):
            self.assertEqual((cold["mode"], primed["mode"]), ("cold", "primed"))
            self.assertEqual(cold["prompt_tokens"], primed["prompt_tokens"])
            self.assertEqual(cold["shared_prefix_tokens"], 0)
            self.assertEqual(primed["shared_prefix_tokens"], primed["prompt_tokens"] // 2)


if __name__ == "__main__":
    unittest.main()
