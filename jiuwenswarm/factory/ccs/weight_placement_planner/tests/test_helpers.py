"""Synthetic smoke coverage for the three helper CLIs."""
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
        temp = tempfile.TemporaryDirectory(dir=CAPSULE, prefix=".helper-fixture-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def cli(self, script, *args, status=0):
        result = subprocess.run([sys.executable, str(HELPERS / script), *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout

    def test_expect_silent_checks_every_prefixed_line(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            log = Path(directory) / "candidate.log"
            command = [
                sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "helpers/check_markers.py"),
                str(log), "--name", "weight_placement_planner", "--expect-silent",
            ]
            log.write_text("stock: loading\nother_weight_placement_planner: active\n")
            silent = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(silent.returncode, 0, silent.stderr)
            log.write_text("INFO weight_placement_planner: undocumented marker\n")
            noisy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(noisy.returncode, 1, noisy.stderr)
            self.assertEqual(json.loads(noisy.stdout)["unexpected_marker_lines"], [1])

    def test_marker_checker(self):
        script = "check_markers.py"
        self.cli(script, "--help")
        log = self.root / "server.log"
        log.write_text("load_tensors: loading (load_mode = none)\n"
                       "load_tensors: retry (load_mode = mmap)\n"
                       "demo: active\ndemo: assignment CPU\ndemo: stats\n")
        args = ("--name", "demo", "--expect-active")
        output = json.loads(self.cli(script, log, *args, "--load-mode", "mmap"))
        self.assertEqual(output["load_modes"], ["none", "mmap"])
        self.assertEqual(output["markers"], {"active": 1, "assignment": 1, "stats": 1})
        self.cli(script, log, *args, "--load-mode", "none", status=1)

    def test_plan_validator(self):
        script = "validate_plan.py"
        self.cli(script, "--help")
        plan = self.root / "plan.json"
        plan.write_text('{"version":1,"overrides":[{"pattern":"^tensor$","buft":"CPU"}]}')
        self.assertIn("1 override", self.cli(script, plan))
        for invalid in (
            '{"version":true,"overrides":[]}',
            '{"version":1,"version":1,"overrides":[]}',
            '{"version":2,"overrides":[]}',
            '{"version":1,"overrides":[],"extra":0}',
            '{"version":1,"overrides":[{"pattern":"x","buft":"CPU","extra":0}]}',
            json.dumps({"version": 1, "overrides": [{"pattern": "x", "buft": "CPU"}] * 4096}),
            " " * (4 * 1024 * 1024 + 1),
        ):
            with self.subTest(case=invalid[:80]):
                plan.write_text(invalid)
                self.cli(script, plan, status=1)

    def test_parity_wrapper(self):
        script = "parity.py"
        self.cli(script, "--help")
        stub = self.root / "synthetic.sh"
        stub.write_text("""set -eu
test "$3" = 5175
test "${*: -2}" = '-lv 4'
case "$1" in
    stock) test -z "${FIXTURE_GATE-}" ;;
esac
printf '{"tokens":[1,2]}\\n' > "$2.json"
printf 'load_tensors: loaded (load_mode = mmap)\\n' > "$2.server.log"
if [ "${FIXTURE_GATE-}" = 1 ] && [ "$1" != silent ]; then
    printf 'demo: active\\ndemo: stats\\n' >> "$2.server.log"
fi
""")
        model = self.root / "synthetic-model"
        model.touch()
        args = ("--one-shot", stub, "--stock-bin", "stock", "--model", model,
                "--gate", "FIXTURE_GATE", "--name", "demo", "--load-mode", "mmap")
        self.cli(script, *args, "--candidate-bin", "candidate", "--output", self.root / "off")
        output = self.cli(script, *args, "--candidate-bin", "candidate",
                          "--active", "--output", self.root / "on")
        self.assertIn("Completion tokens match", output)
        self.cli(script, *args, "--candidate-bin", "silent", "--active",
                 "--output", self.root / "silent", status=1)
