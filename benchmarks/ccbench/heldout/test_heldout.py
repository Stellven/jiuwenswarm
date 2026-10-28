import sys
sys.dont_write_bytecode = True
import json
import tempfile
import unittest
from pathlib import Path

import modelbench as mb
import checker
import reference
import run_heldout as rh

HERE = Path(__file__).resolve().parent
CASES = {c['id']: c for c in rh.load_cases()}


def src(fn):
    import inspect
    return inspect.getsource(fn)


class GoldConsistency(unittest.TestCase):
    def test_ten_cases_disjoint_suites(self):
        self.assertEqual(len(CASES), 10)
        for c in CASES.values():
            self.assertGreaterEqual(len(c['gate']), 4)
            self.assertGreaterEqual(len(c['score']), 6)
            gate = {json.dumps(t, sort_keys=True) for t in c['gate']}
            score = {json.dumps(t, sort_keys=True) for t in c['score']}
            self.assertFalse(gate & score, c['id'])

    def test_reference_passes_both_suites(self):
        # the hand-written expected values and the independent reference agree
        for c in CASES.values():
            code = src(getattr(reference, c['function']))
            if c['function'] == 'brackets_balanced':
                code = src(reference.brackets_balanced)
            pre = 'import re\nfrom datetime import date, timedelta\nfrom decimal import Decimal, ROUND_HALF_UP\n'
            for suite in ('gate', 'score'):
                out = checker.run_tests(pre + code, c['function'], c[suite])
                self.assertTrue(all(r['ok'] for r in out['results']), (c['id'], suite, [r['detail'] for r in out['results'] if not r['ok']]))

    def test_examples_in_spec_hold_for_reference(self):
        pre = 'import re\nfrom datetime import date, timedelta\nfrom decimal import Decimal, ROUND_HALF_UP\n'
        for c in CASES.values():
            ns = {}
            exec(pre + src(getattr(reference, c['function'])), ns)
            for ex in c['examples']:
                self.assertTrue(eval(ex.split('#')[0], ns), ex)

    def test_naive_solutions_are_caught(self):
        naive = {
            'round_half_up': "def round_half_up(value, ndigits):\n    return ('%.' + str(ndigits) + 'f') % round(float(value), ndigits)\n",
            'merge_intervals': "def merge_intervals(intervals):\n    out = []\n    for s, e in sorted(intervals):\n        if out and s < out[-1][1]:\n            out[-1][1] = max(out[-1][1], e)\n        else:\n            out.append([s, e])\n    return out\n",
            'compare_versions': "def compare_versions(a, b):\n    return (a > b) - (a < b)\n",
        }
        for fn, code in naive.items():
            gate = checker.run_tests(code, fn, CASES[fn]['gate'])
            score = checker.run_tests(code, fn, CASES[fn]['score'])
            self.assertFalse(all(r['ok'] for r in gate['results'] + score['results']), fn)

    def test_manifest_matches_frozen_cases(self):
        self.assertEqual(mb.verify_manifest(HERE), [])


class Checker(unittest.TestCase):
    def test_same_is_strict(self):
        self.assertFalse(checker.same(True, 1))
        self.assertFalse(checker.same(1, 1.0))
        self.assertTrue(checker.same([[1, 2]], [[1, 2]]))
        self.assertFalse(checker.same({'a': 1}, {'a': True}))

    def test_banned_and_timeout_and_crash(self):
        t = [{'args': [1], 'expect': 1}]
        self.assertIn('refused', checker.run_tests('import os\ndef f(x): return x\n', 'f', t)['fatal'])
        self.assertIn('refused', checker.run_tests('def f(x): return open("a")\n', 'f', t)['fatal'])
        hang = checker.run_tests('def f(x):\n    while True: pass\n', 'f', t, timeout=2)
        self.assertTrue(hang['timed_out'])
        self.assertFalse(hang['results'][0]['ok'])
        self.assertFalse(checker.run_tests('def f(x:\n', 'f', t)['results'][0]['ok'])
        self.assertFalse(checker.run_tests('def g(x): return x\n', 'f', t)['results'][0]['ok'])
        self.assertFalse(checker.run_tests(None, 'f', t)['results'][0]['ok'])

    def test_raises_and_print_noise(self):
        t = [{'args': [''], 'raises': 'ValueError'}, {'args': [2], 'expect': 4}]
        code = 'def f(x):\n    print("noise")\n    if x == "": raise ValueError("e")\n    return x * 2\n'
        self.assertEqual([r['ok'] for r in checker.run_tests(code, 'f', t)['results']], [True, True])
        wrong = 'def f(x):\n    raise KeyError("e")\n'
        self.assertEqual([r['ok'] for r in checker.run_tests(wrong, 'f', t)['results']], [False, False])

    def test_selftest(self):
        code = 'def f(x): return x + 1\n'
        self.assertEqual(checker.run_selftest(code, 'assert f(1) == 2\n')[0], 'pass')
        status, text = checker.run_selftest(code, 'assert f(1) == 3\n')
        self.assertEqual(status, 'fail')
        self.assertIn('AssertionError', text)
        self.assertEqual(checker.run_selftest(code, '')[0], 'skipped')


def reply_for(code, tests=None):
    text = '```python\n%s\n```' % code
    return text + ('\n```python\n%s\n```' % tests if tests else '')


GOOD = src(reference.compare_versions)
BAD = "def compare_versions(a, b):\n    return (a > b) - (a < b)\n"


def fake_call(replies):
    seq = list(replies)
    calls = []

    def call(prompt, d):
        calls.append((prompt, d))
        return dict(reply=seq.pop(0), tokens=100, elapsed_s=1.5, ok=True, dir=str(d))
    call.calls = calls
    return call


class Units(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = CASES['compare_versions']

    def tearDown(self):
        self.tmp.cleanup()

    def unit(self, arm, replies):
        call = fake_call(replies)
        res = rh.run_unit(self.case, arm, 1, 'm', Path(self.tmp.name) / (arm + '-r1'), call=call)
        return res, call

    def test_cc_retry_carries_failure_reason_and_rescues(self):
        res, call = self.unit('cc', [reply_for(BAD), reply_for(GOOD)])
        self.assertTrue(res['retried'])
        self.assertEqual(res['cost']['calls'], 2)
        self.assertEqual(res['cost']['tokens'], 200)
        retry_prompt = call.calls[1][0]
        self.assertIn('expected', retry_prompt)
        self.assertIn('independent checks', retry_prompt)
        # the retry shows gate inputs only, never a score-suite input
        for t in self.case['score']:
            self.assertNotIn(json.dumps(t['args']), retry_prompt)
        row = rh.score_unit(self.case, Path(self.tmp.name) / 'cc-r1')
        self.assertTrue(row['passed_all'])
        self.assertFalse(row['first_passed_all'])

    def test_cc_no_retry_when_gate_passes(self):
        res, call = self.unit('cc', [reply_for(GOOD)])
        self.assertFalse(res['retried'])
        self.assertEqual(len(call.calls), 1)

    def test_cc_unextractable_reply_retries(self):
        res, _ = self.unit('cc', ['I cannot do that', reply_for(GOOD)])
        self.assertTrue(res['retried'])

    def test_plain_and_verify_never_retry(self):
        for arm in ('plain', 'verify'):
            res, call = self.unit(arm, [reply_for(BAD)])
            self.assertFalse(res['retried'])
            self.assertEqual(len(call.calls), 1)
            self.assertFalse(rh.score_unit(self.case, Path(self.tmp.name) / (arm + '-r1'))['passed_all'])
        self.assertIn('check your function', rh.first_prompt(self.case, 'verify'))
        self.assertNotIn('check your function', rh.first_prompt(self.case, 'plain'))
        self.assertEqual(rh.first_prompt(self.case, 'plain'), rh.first_prompt(self.case, 'cc'))

    def test_selftest_uses_models_own_tests_only(self):
        # own test passes although the function is wrong: no retry (a weak self-checker misses it)
        res, call = self.unit('selftest', [reply_for(BAD, "assert compare_versions('1', '2') == -1")])
        self.assertFalse(res['retried'])
        self.assertEqual(res['check_status'], 'pass')
        # own test fails: one retry carrying the model's own failure text
        res, call = rh.run_unit(self.case, 'selftest', 2, 'm', Path(self.tmp.name) / 'st2', call=fake_call(
            [reply_for(BAD, "assert compare_versions('1.0', '1.0.0') == 0"), reply_for(GOOD)])), None
        self.assertTrue(res['retried'])
        self.assertTrue(rh.score_unit(self.case, Path(self.tmp.name) / 'st2')['passed_all'])

    def test_selftest_without_tests_block_skips_retry(self):
        res, _ = self.unit('selftest', [reply_for(BAD)])
        self.assertEqual(res['check_status'], 'skipped')
        self.assertFalse(res['retried'])

    def test_aggregate_counts_all_units_and_pairs(self):
        rows = [dict(case='a', arm='cc', rep=1, passes=[True, True], passed_all=True, first_passed_all=False, retried=True, cost=dict(calls=2, tokens=10, wall_s=2.0)),
                dict(case='a', arm='plain', rep=1, passes=[True, False], passed_all=False, first_passed_all=False, retried=False, cost=dict(calls=1, tokens=None, wall_s=1.0)),
                dict(case='a', arm='cc', rep=2, passes=[False, False], passed_all=False, first_passed_all=False, retried=True, cost=dict(calls=2, tokens=10, wall_s=2.0)),
                dict(case='a', arm='plain', rep=2, passes=[True, True], passed_all=True, first_passed_all=True, retried=False, cost=dict(calls=1, tokens=None, wall_s=1.0))]
        s = rh.aggregate(rows)
        self.assertEqual(s['cc']['case_pass_rate'], 0.5)
        self.assertEqual(s['cc']['rescued'], 1)
        self.assertEqual(s['plain']['tokens'], None)
        self.assertEqual(s['plain']['units_missing_tokens'], 2)
        self.assertEqual(s['plain']['test_pass_rate'], 0.75)
        self.assertEqual(rh.paired(rows)['plain'], dict(pairs=2, cc_only=1, other_only=1))


if __name__ == '__main__':
    unittest.main()
