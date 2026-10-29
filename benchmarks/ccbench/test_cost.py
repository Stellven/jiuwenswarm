"""Unit tests for cost.py. Offline, stdlib only."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost  # noqa: E402


def run(arm, cls, i, o, calls=1, wall=10.0):
    return dict(arm=arm, cls=cls, input_tokens=i, output_tokens=o, calls=calls, wall_s=wall)


class Table(unittest.TestCase):
    def test_per_arm_means_and_tokens_per_correct(self):
        runs = [run('plain', 'correct', 100, 10), run('plain', 'silent_wrong', 200, 20), run('plain', 'justified_halt', 50, 5),
                run('cc', 'correct', 40, 4, calls=0, wall=1.0), run('cc', 'correct_flagged', 60, 6, calls=2, wall=3.0)]
        t = cost.cost_table(runs)
        p = t['plain']
        self.assertEqual((p['runs'], p['counts']['correct'], p['counts']['wrong'], p['counts']['stopped']), (3, 1, 1, 1))
        self.assertAlmostEqual(p['mean_input'], 350 / 3)
        self.assertAlmostEqual(p['mean_total'], 385 / 3)
        self.assertEqual(p['tokens_per_correct'], 385)          # (110 + 220 + 55) / 1 correct
        c = t['cc']
        self.assertEqual(c['tokens_per_correct'], 55)           # (44 + 66) / 2
        self.assertEqual(c['mean_calls'], 1.0)
        self.assertEqual(c['mean_wall_s'], 2.0)

    def test_no_correct_is_none_and_missing_tokens_never_guessed(self):
        t = cost.cost_table([run('a', 'silent_wrong', 10, 1)])
        self.assertIsNone(t['a']['tokens_per_correct'])
        t = cost.cost_table([run('b', 'correct', 10, 1), run('b', 'correct', None, None)])
        self.assertIsNone(t['b']['tokens_per_correct'])
        self.assertEqual(t['b']['runs_missing_total'], 1)
        self.assertEqual(t['b']['tokens_per_correct_known_runs'], 11)
        self.assertEqual(t['b']['mean_input'], 10)
        self.assertEqual(t['b']['runs_with_split'], 1)

    def test_total_only_run_has_no_split(self):
        t = cost.cost_table([dict(arm='m', cls='correct', total_tokens=500, calls=1, wall_s=2)])
        self.assertEqual(t['m']['mean_total'], 500)
        self.assertIsNone(t['m']['mean_input'])
        self.assertEqual(t['m']['tokens_per_correct'], 500)

    def test_unknown_class_is_an_error(self):
        with self.assertRaises(ValueError):
            cost.cost_table([run('a', 'mystery', 1, 1)])

    def test_buckets(self):
        self.assertEqual(cost.bucket('wrong_halt'), 'false_stop')
        self.assertEqual(cost.bucket('wrong_delivered'), 'wrong')
        self.assertEqual(cost.bucket('stop_named'), 'stopped')

    def test_markdown_has_one_row_per_arm(self):
        text = cost.markdown(cost.cost_table([run('a', 'correct', 1, 1), run('b', 'correct', None, None)]))
        self.assertEqual(len([l for l in text.splitlines() if l.startswith('| a ') or l.startswith('| b ')]), 2)


class BreakEven(unittest.TestCase):
    def test_values(self):
        self.assertEqual(cost.break_even(10000, 1500), 7)
        self.assertEqual(cost.break_even(0, 5), 0)
        self.assertIsNone(cost.break_even(100, 0))
        self.assertIsNone(cost.break_even(100, -3))
        self.assertIsNone(cost.break_even(None, 3))


class SessionUsage(unittest.TestCase):
    def write(self, folder, name, value):
        (Path(folder) / name).parent.mkdir(parents=True, exist_ok=True)
        (Path(folder) / name).write_text(json.dumps(value), encoding='utf-8')

    def test_usage_json_and_controller_wall(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, 'usage.json', [dict(elapsed_s=1.5, usage=dict(input_tokens=100, output_tokens=7)),
                                         dict(elapsed_s=2.0, usage=dict(input_tokens=50, output_tokens=3))])
            self.write(d, 'controller-finished.json', dict(elapsed_s=72.956))
            u = cost.session_usage(d)
            self.assertEqual((u['input_tokens'], u['output_tokens'], u['total_tokens'], u['calls']), (150, 10, 160, 2))
            self.assertEqual((u['wall_s'], u['source']), (72.96, 'usage.json'))

    def test_partial_usage_gives_no_split(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, 'usage.json', [dict(usage=dict(input_tokens=100, output_tokens=7)), dict(usage=dict(input_tokens=None, output_tokens=None))])
            u = cost.session_usage(d)
            self.assertEqual(u['calls'], 2)
            self.assertIsNone(u['input_tokens'])
            self.assertIsNone(u['wall_s'])

    def test_broker_receipts_and_result_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, 'host-responses/a.response.json', dict(elapsed_s=1, usage=dict(input_tokens=9, output_tokens=1)))
            u = cost.session_usage(d)
            self.assertEqual((u['input_tokens'], u['source']), (9, 'host-responses'))
        with tempfile.TemporaryDirectory() as d:
            self.write(d, 'result.json', dict(model_calls=4))
            u = cost.session_usage(d)
            self.assertEqual((u['calls'], u['input_tokens'], u['source']), (4, None, None))

    def test_real_shape_session_if_present(self):
        real = Path.home() / 'huawei/outputs/ccbench-20261028/A-full/sessions/calc_absolute-r1'
        if not real.is_dir():
            self.skipTest('sample session not on this machine')
        u = cost.session_usage(real)
        self.assertEqual(u['calls'], 4)
        self.assertEqual(u['input_tokens'], 41522 + 39249 + 39574 + 41959)


if __name__ == '__main__':
    unittest.main()
