import sys
sys.dont_write_bytecode = True
import json
import tempfile
import unittest
from pathlib import Path

import modelbench as mb
import checker
import reference
import reference_trap
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


TRAP_FILE = 'cases-trap.json'
TRAP = {c['id']: c for c in rh.load_cases(cases_file=TRAP_FILE)}
TRAP_PRE = 'import re\nimport unicodedata\nfrom decimal import Decimal, ROUND_HALF_EVEN\n'


def key(t):
    return json.dumps(t, sort_keys=True)


class TrapCases(unittest.TestCase):
    def test_eight_cases_with_required_suite_sizes(self):
        self.assertEqual(len(TRAP), 8)
        for c in TRAP.values():
            self.assertEqual(len(c['gate']), 4, c['id'])
            self.assertTrue(6 <= len(c['score']) <= 10, c['id'])
            self.assertTrue(c['trap'], c['id'])
            self.assertTrue(hasattr(reference_trap, c['function']), c['id'])

    def test_reference_passes_all_suites(self):
        for c in TRAP.values():
            code = TRAP_PRE + src(getattr(reference_trap, c['function']))
            for suite in ('gate', 'score'):
                out = checker.run_tests(code, c['function'], c[suite])
                self.assertTrue(all(r['ok'] for r in out['results']) and out['results'],
                                (c['id'], suite, [r['detail'] for r in out['results'] if not r['ok']]))

    def test_gate_and_score_are_disjoint(self):
        for c in TRAP.values():
            gate_pairs = {key(t) for t in c['gate']}
            score_pairs = {key(t) for t in c['score']}
            self.assertFalse(gate_pairs & score_pairs, c['id'])
            # stronger: no score input (args) appears in the gate, so a gate quote can never reveal a score input
            self.assertFalse({json.dumps(t['args']) for t in c['gate']} & {json.dumps(t['args']) for t in c['score']}, c['id'])
            self.assertEqual(len(gate_pairs), len(c['gate']), c['id'])
            self.assertEqual(len(score_pairs), len(c['score']), c['id'])

    def test_spec_examples_hold_and_are_not_test_inputs(self):
        for c in TRAP.values():
            ns = {}
            exec(TRAP_PRE + src(getattr(reference_trap, c['function'])), ns)
            used = {json.dumps(t['args']) for t in c['gate'] + c['score']}
            for ex in c['examples']:
                self.assertTrue(eval(ex, ns), ex)
                call_args = eval('[' + ex[len(c['function']) + 1:].split(') ==')[0] + ']', ns)
                self.assertNotIn(json.dumps(call_args), used, ex)

    def test_naive_readings_are_caught_by_both_suites(self):
        # for each case one natural misreading; the gate AND the score suite must each fail it
        naive = {
            'parse_size': "import re\ndef parse_size(s):\n    parts = s.split()\n    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in ('B', 'KB', 'MB', 'GB'):\n        raise ValueError('x')\n    return int(parts[0]) * {'B': 1, 'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3}[parts[1]]\n",
            'bucket_counts': "def bucket_counts(values, edges):\n    n = len(edges) - 1\n    c = [0] * n\n    for v in values:\n        for i in range(n):\n            if edges[i] <= v < edges[i + 1]:\n                c[i] += 1\n    return c\n",
            'competition_rank': "def competition_rank(scores):\n    d = sorted(set(scores), reverse=True)\n    return [d.index(s) + 1 for s in scores]\n",
            'consistent_groups': "def consistent_groups(groups):\n    return sorted(k for k, v in groups.items() if all(x > 0 for x in v) or all(x < 0 for x in v))\n",
            'is_anagram': "def is_anagram(a, b):\n    return sorted(a.lower().replace(' ', '')) == sorted(b.lower().replace(' ', ''))\n",
            'to_cents': "from decimal import Decimal, ROUND_HALF_UP\ndef to_cents(amount):\n    return int((Decimal(amount) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))\n",
            'format_delta': "def format_delta(x):\n    t = '%.1f' % x\n    return t if t.startswith('-') else '+' + t\n",
            'collapse_adjacent': "def collapse_adjacent(items):\n    out = []\n    for it in items:\n        if it not in out:\n            out.append(it)\n    return out\n",
        }
        self.assertEqual(set(naive), set(TRAP))
        for fn, code in naive.items():
            for suite in ('gate', 'score'):
                out = checker.run_tests(code, fn, TRAP[fn][suite])
                self.assertFalse(all(r['ok'] for r in out['results']), (fn, suite))

    def test_gate_of_naive_reading_leaks_no_score_input_in_retry(self):
        case = TRAP['collapse_adjacent']
        bad = "def collapse_adjacent(items):\n    out = []\n    for it in items:\n        if it not in out:\n            out.append(it)\n    return out\n"
        with tempfile.TemporaryDirectory() as tmp:
            call = fake_call([reply_for(bad), reply_for(src(reference_trap.collapse_adjacent))])
            res = rh.run_unit(case, 'cc', 1, 'm', Path(tmp) / 'cc-r1', call=call)
            self.assertTrue(res['retried'])
            for t in case['score']:
                self.assertNotIn(json.dumps(t['args']), call.calls[1][0])
            self.assertTrue(rh.score_unit(case, Path(tmp) / 'cc-r1')['passed_all'])


class CasesFileOption(unittest.TestCase):
    def test_manifest_names(self):
        self.assertEqual(rh.manifest_name(), 'MANIFEST.sha256')
        self.assertEqual(rh.manifest_name('cases.json'), 'MANIFEST.sha256')
        self.assertEqual(rh.manifest_name('cases-trap.json'), 'MANIFEST-trap.sha256')

    def test_default_is_original_cases(self):
        self.assertEqual(len(rh.load_cases()), 10)
        self.assertEqual({c['id'] for c in rh.load_cases(cases_file=TRAP_FILE)} & {c['id'] for c in rh.load_cases()}, set())

    def test_both_manifests_match(self):
        self.assertEqual(rh.check_manifest(), [])
        self.assertEqual(rh.check_manifest(TRAP_FILE), [])

    def test_manifest_check_detects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in (TRAP_FILE, 'MANIFEST-trap.sha256'):
                (tmp / name).write_bytes((HERE / name).read_bytes())
            path = str(tmp / TRAP_FILE)
            self.assertEqual(rh.check_manifest(path), [])
            (tmp / TRAP_FILE).write_bytes((tmp / TRAP_FILE).read_bytes() + b' ')
            problems = rh.check_manifest(path)
            self.assertEqual(len(problems), 1)
            self.assertIn('differs', problems[0])
            (tmp / 'MANIFEST-trap.sha256').unlink()
            self.assertIn('missing', rh.check_manifest(path)[0])

    def test_unknown_case_id_and_cli_plan(self):
        with self.assertRaises(SystemExit):
            rh.load_cases(['merge_intervals'], TRAP_FILE)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rh.main(['plan', '--cases', TRAP_FILE])
        text = buf.getvalue()
        self.assertIn('parse_size', text)
        self.assertNotIn('merge_intervals', text)
        self.assertIn('8 cases', text)

    def test_score_reads_the_same_file(self):
        case = TRAP['collapse_adjacent']
        good = src(reference_trap.collapse_adjacent)
        with tempfile.TemporaryDirectory() as tmp:
            call = fake_call([reply_for(good)])
            rh.run_unit(case, 'plain', 1, 'm', Path(tmp) / 'heldout' / 'mm' / case['id'] / 'plain-r1', call=call)
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                summary = rh.score('mm', tmp, TRAP_FILE)
            self.assertEqual(summary['plain']['case_pass_rate'], 1.0)
            with self.assertRaises(KeyError):
                rh.score('mm', tmp)  # default file does not know this case


if __name__ == '__main__':
    unittest.main()
