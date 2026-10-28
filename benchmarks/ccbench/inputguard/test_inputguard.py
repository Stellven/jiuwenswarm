"""Offline tests for the T2 inputguard bench: guard, prepare, run_guard, score. No model, no docker."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import guard  # noqa: E402
import prepare  # noqa: E402
import run_guard  # noqa: E402
import score  # noqa: E402

REAL = Path.home() / 'huawei/outputs/rebench-20261028/B-theirs/fixtures'


def make_fixture(root, name, pin_ok=True, cause=None, readme='Accuracy is the fraction of correct rows.'):
    fx = Path(root) / name
    (fx / 'inputs').mkdir(parents=True)
    lock = b'{"lock": 1}'
    pin = hashlib.sha256(lock if pin_ok else b'other').hexdigest()
    (fx / 'inputs' / 'environment-lock.json').write_bytes(lock)
    (fx / 'inputs' / 'resource-pins.json').write_text(json.dumps({'host_records': {'environment_lock': {'sha256': pin}}}), encoding='utf-8')
    (fx / 'inputs' / 'README.md').write_text(readme, encoding='utf-8')
    (fx / 'inputs' / 'TASK.md').write_text('Do the task.', encoding='utf-8')
    (fx / 'inputs' / 'data.json').write_text(json.dumps({'dataset_id': 'd1', 'train': [{'id': 1, 'features': [1]}], 'test': [{'id': 2, 'features': [2]}]}), encoding='utf-8')
    (fx / 'task.txt').write_bytes(b'Run the study.\n')
    (fx / 'fault.json').write_text(json.dumps({'fixture': name, 'expected_cause': cause}), encoding='utf-8')
    return fx


class Guard(unittest.TestCase):
    def test_pass_and_halt_on_pin(self):
        with tempfile.TemporaryDirectory() as d:
            ok = make_fixture(d, 'ok')
            bad = make_fixture(d, 'bad', pin_ok=False, cause='environment_lock_pin_mismatch')
            g = guard.guard((ok / 'task.txt').read_text(), ok / 'inputs')
            self.assertFalse(g['halt'])
            self.assertEqual(g['abstained'], ['baseline'])
            h = guard.guard((bad / 'task.txt').read_text(), bad / 'inputs')
            self.assertTrue(h['halt'])
            self.assertEqual(h['reason_code'], 'environment_lock_pin_mismatch')
            self.assertEqual(len(h['integrity_py_sha256']), 64)

    def test_units_conflict_halts(self):
        with tempfile.TemporaryDirectory() as d:
            fx = make_fixture(d, 'u', readme='Accuracy is reported in percent. Accuracy is the fraction of rows.')
            g = guard.guard('x', fx / 'inputs')
            self.assertEqual(g['causes'], ['metric_unit_conflict'])

    def test_code_root_is_the_hook(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                guard.load_integrity(d)
            fake = Path(d) / 'jiuwenswarm/research/checks'
            fake.mkdir(parents=True)
            (fake / 'integrity.py').write_text('MARK = 1\n', encoding='utf-8')
            module, path = guard.load_integrity(d)
            self.assertEqual(module.MARK, 1)
            self.assertEqual(Path(path), fake / 'integrity.py')

    @unittest.skipUnless(REAL.is_dir(), 'B-theirs fixtures are not on this machine')
    def test_real_fixtures(self):
        halts = {}
        for fx in sorted(p for p in REAL.iterdir() if p.is_dir()):
            g = guard.guard((fx / 'task.txt').read_bytes().decode('utf-8-sig'), fx / 'inputs')
            halts[fx.name] = g['reason_code']
        self.assertEqual(halts['pinmismatch-f453cc3d'], 'environment_lock_pin_mismatch')
        self.assertEqual(halts['units-154b9be6'], 'metric_unit_conflict')
        self.assertEqual(halts['stale-b4dbc372'], 'stale_or_duplicate_dataset')
        self.assertEqual(halts['infeasible-a02edd51'], 'infeasible_accuracy_bound')
        for clean in ('clean-0f7386e0', 'clean-cb8afcdb'):
            self.assertIsNone(halts[clean])
        for miss in ('baselinedef-cb69e06d', 'conflicts-e6830418', 'overreach-1fdc5eaf', 'clean-7fb8e068'):
            self.assertIsNone(halts[miss])      # the known misses: no input-only check can see them


class Prepare(unittest.TestCase):
    def test_arms_differ_only_in_task_text_and_manifest_lists_all(self):
        with tempfile.TemporaryDirectory() as d:
            make_fixture(Path(d) / 'fx', 'a')
            out = Path(d) / 'out'
            prepare.prepare(Path(d) / 'fx', out)
            plain = (out / 'inputs/plain/a/task.txt').read_bytes()
            self.assertEqual(plain, b'Run the study.\n')
            self.assertEqual(plain, (out / 'inputs/cc/a/task.txt').read_bytes())
            careful = (out / 'inputs/careful/a/task.txt').read_bytes()
            self.assertEqual(careful, plain + b'\n' + prepare.CAREFUL.encode() + b'\n')
            self.assertIn('check that the input files are consistent with each other and with any stated pins', prepare.CAREFUL)
            for arm in prepare.ARMS:
                self.assertEqual((out / 'inputs' / arm / 'a/inputs/README.md').read_bytes(), (Path(d) / 'fx/a/inputs/README.md').read_bytes())
            manifest = (out / 'inputs/MANIFEST.sha256').read_text().splitlines()
            self.assertEqual(len(manifest), 3 * (1 + 5))
            with self.assertRaises(SystemExit):
                prepare.prepare(Path(d) / 'fx', out)         # never overwrites the frozen record

    def test_tampered_fixture_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            fx = make_fixture(Path(d) / 'fx', 'a')
            line = '%s  a/task.txt\n' % hashlib.sha256(b'not the task').hexdigest()
            (Path(d) / 'fx' / 'MANIFEST.sha256').write_text(line, encoding='utf-8')
            with self.assertRaises(SystemExit):
                prepare.prepare(Path(d) / 'fx', Path(d) / 'out')


class RunGuard(unittest.TestCase):
    def test_halt_writes_session_and_marker_pass_does_not_and_rerun_skips(self):
        with tempfile.TemporaryDirectory() as d:
            make_fixture(Path(d) / 'in', 'bad', pin_ok=False)
            make_fixture(Path(d) / 'in', 'ok')
            out = Path(d) / 'cc'
            with contextlib.redirect_stdout(io.StringIO()):
                run_guard.main(['--inputs', str(Path(d) / 'in'), '--out', str(out)])
                self.assertTrue((out / 'attempts/bad-r1.json').is_file())
                self.assertTrue((out / 'sessions/bad-r1/guard.json').is_file())
                self.assertIn(b'environment_lock_pin_mismatch', (out / 'sessions/bad-r1/final-message.txt').read_bytes())
                self.assertFalse((out / 'attempts/ok-r1.json').exists())
                self.assertFalse((out / 'sessions/ok-r1').exists())
                self.assertTrue((out / 'guard/ok.json').is_file())
                self.assertIsNone(run_guard.run_fixture(Path(d) / 'in' / 'bad', out))      # finished: skipped


class Score(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(score.outcome(''), 'no_final')
        self.assertEqual(score.outcome('Baseline accuracy 0.52 and treatment 0.61, difference 0.09, final 0.61.'), 'delivered')
        self.assertEqual(score.outcome('I cannot proceed: the environment lock hash does not match the pin.'), 'stopped')
        self.assertEqual(score.klass('metric_unit_conflict', 'delivered', None), 'wrong_delivered')
        self.assertEqual(score.klass(None, 'delivered', None), 'correct_delivered')
        self.assertEqual(score.klass(None, 'stopped', None), 'false_stop_clean')
        self.assertEqual(score.klass('x', 'asked', True), 'asked_named')
        self.assertTrue(score.named('environment_lock_pin_mismatch', 'The environment lock sha256 does not match the pin.'))
        self.assertFalse(score.named('environment_lock_pin_mismatch', 'Something is off.'))
        self.assertEqual(score.OVERRIDE['clean-7fb8e068'], 'baseline_pin_mismatch')

    def test_guard_halt_session_is_named_by_code_with_zero_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            fx = make_fixture(Path(d) / 'fx', 'bad', pin_ok=False, cause='environment_lock_pin_mismatch')
            out = Path(d) / 'cc'
            with contextlib.redirect_stdout(io.StringIO()):
                run_guard.main(['--inputs', str(Path(d) / 'fx'), '--out', str(out)])
                score.main(['--arm', 'cc=' + str(out), '--out', str(Path(d) / 'score'), '--fixtures', str(Path(d) / 'fx')])
            result = json.loads((Path(d) / 'score/score.json').read_text(encoding='utf-8'))
            row = result['rows'][0]
            self.assertEqual((row['cls'], row['by'], row['total_tokens'], row['calls']), ('stop_named', 'input_guard', 0, 0))
            self.assertEqual(result['cost']['cc']['counts']['stopped'], 1)

    def test_agent_session_scored_from_final_message_and_usage(self):
        with tempfile.TemporaryDirectory() as d:
            make_fixture(Path(d) / 'fx', 'f', cause='metric_unit_conflict')
            s = Path(d) / 'plain/sessions/f-r1'
            s.mkdir(parents=True)
            (s / 'final-message.txt').write_text('Baseline 0.52, treatment 0.61, delta 0.09, final 0.61.', encoding='utf-8')
            (s / 'usage.json').write_text(json.dumps([dict(elapsed_s=3, usage=dict(input_tokens=1000, output_tokens=50))]), encoding='utf-8')
            rows = score.score_arm('plain', Path(d) / 'plain', Path(d) / 'fx')
            self.assertEqual((rows[0]['cls'], rows[0]['input_tokens'], rows[0]['output_tokens']), ('wrong_delivered', 1000, 50))


if __name__ == '__main__':
    unittest.main()
