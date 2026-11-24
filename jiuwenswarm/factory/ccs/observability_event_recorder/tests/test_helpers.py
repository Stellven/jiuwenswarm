import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CAPSULE = Path(__file__).resolve().parents[1]


class HelperTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def run_helper(self, name, *args, status=0):
        result = subprocess.run(
            [sys.executable, '-B', str(CAPSULE / 'helpers' / name), *map(str, args)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout

    def test_expect_silent_checks_every_prefixed_line(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            log = Path(directory) / "candidate.log"
            command = [
                sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "helpers/check_markers.py"),
                str(log), "--name", "runtime_event_recorder", "--expect-silent",
            ]
            log.write_text("stock: loading\nother_runtime_event_recorder: active\n")
            silent = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(silent.returncode, 0, silent.stderr)
            log.write_text("INFO runtime_event_recorder: undocumented marker\n")
            noisy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(noisy.returncode, 1, noisy.stderr)
            self.assertEqual(json.loads(noisy.stdout)["unexpected_marker_lines"], [1])

    def test_markers_and_effective_mode(self):
        self.run_helper('check_markers.py', '--help')
        log = CAPSULE / 'tests' / 'fixtures' / 'active.log'
        args = ('check_markers.py', log, '--expect', 'active', '--load-mode')
        report = json.loads(self.run_helper(*args, 'none'))
        self.assertEqual(report['markers'], {'active': 1, 'inactive': 0, 'stats': 1})
        self.assertEqual(report['load_modes'], ['none'])
        self.run_helper(*args, 'mmap', status=1)

    def test_parity_plan_and_check(self):
        self.run_helper('parity.py', '--help')
        command = self.run_helper('parity.py', 'plan', '/stock', '/candidate',
                                  '/model with spaces.gguf', self.directory,
                                  self.directory / 'trace.jsonl', '--', '-ngl', '0')
        self.assertEqual(command.count('-ngl 0 --port 5175 --host 127.0.0.1 -lv 4'), 3)
        self.assertEqual(command.count('LLAMA_EVENT_REC='), 1)
        self.assertIn("'MODEL=/model with spaces.gguf'", command)
        for arm in ('stock', 'off', 'on'):
            (self.directory / f'{arm}.json').write_text('{"tokens":[42],"content":"result"}')
        self.assertEqual(json.loads(self.run_helper('parity.py', 'check', self.directory)),
                         {'stock_vs_off': True, 'stock_vs_on': True})
        (self.directory / 'on.json').write_text('{"tokens":[43],"content":"result"}')
        self.run_helper('parity.py', 'check', self.directory, status=1)

    def test_jsonl_coverage_and_loss(self):
        self.run_helper('check_jsonl.py', '--help')
        trace = self.directory / 'trace.jsonl'
        manifest = self.directory / 'dispatch.json'
        manifest.write_text('[[0,1],[0,2]]')
        event = '{"type":"event","microbatch":0,"layer":1}\n'
        summary = '{"type":"summary","expected":2,"written":1,"lost":1}\n'
        trace.write_text(event + summary)
        output = self.run_helper('check_jsonl.py', trace, manifest, '--expect-loss')
        self.assertEqual(json.loads(output), {'expected': 2, 'written': 1, 'lost': 1})
        self.run_helper('check_jsonl.py', trace, manifest, status=1)
        trace.write_text(event + event + summary)
        self.run_helper('check_jsonl.py', trace, manifest, '--expect-loss', status=1)
