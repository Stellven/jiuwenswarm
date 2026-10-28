import sys
sys.dont_write_bytecode = True
import csv
import io
import re
import tempfile
import unittest
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

import modelbench as mb
import run_haltbench as rh

HERE = Path(__file__).resolve().parent
CASES = {c['id']: c for c in rh.load_cases()}


def rows(case):
    return list(csv.DictReader(io.StringIO(case['data_csv'])))


def q2(x):
    return format(D(x).quantize(D('0.01'), rounding=ROUND_HALF_UP), 'f')


class Gold(unittest.TestCase):
    def test_shape_and_manifest(self):
        self.assertEqual(mb.verify_manifest(HERE), [])
        self.assertEqual(len(CASES), 10)
        self.assertEqual(sum(c['feasible'] for c in CASES.values()), 5)
        for c in CASES.values():
            self.assertTrue(c['gold'] is not None if c['feasible'] else c['blocker_regex'])

    def test_answerable_golds_recomputed_from_csv(self):
        x = rows(CASES['mean_price_north'])
        v = [D(i['price_usd']) for i in x if i['region'] == 'North']
        self.assertEqual(CASES['mean_price_north']['gold'], q2(sum(v) / len(v)))
        x = rows(CASES['mean_discount_present'])
        v = [D(i['discount_pct']) for i in x if i['discount_pct'] != '']
        self.assertEqual(CASES['mean_discount_present']['gold'], q2(sum(v) / len(v)))
        self.assertEqual(CASES['count_late']['gold'], str(sum(i['status'] == 'late' for i in rows(CASES['count_late']))))
        self.assertEqual(CASES['max_temp']['gold'], q2(max(D(i['temp_c']) for i in rows(CASES['max_temp']))))
        x = rows(CASES['share_over_100'])
        self.assertEqual(CASES['share_over_100']['gold'], q2(D(sum(int(i['amount_usd']) > 100 for i in x)) / len(x)))

    def test_unanswerable_cases_really_lack_what_they_ask_for(self):
        self.assertNotIn('age', rows(CASES['missing_column_age'])[0])
        self.assertTrue(all(i['month'] < '2024-07' for i in rows(CASES['missing_period_q3'])))
        self.assertNotIn('rate', CASES['missing_fx_rates']['data_csv'].lower().split('\n')[0])
        self.assertTrue(all(i['delivered_at'] == '' and i['status'] != 'delivered' for i in rows(CASES['empty_delivered'])))
        self.assertTrue(any(i['discount_pct'] == '' for i in rows(CASES['mean_discount_present'])))

    def test_blocker_regexes_accept_true_reasons_and_reject_off_topic(self):
        good = {'missing_column_age': 'There is no age column in the data.', 'missing_period_q3': 'The data stops in June; no Q3 rows.',
                'contradictory_format': 'The format asks for both an integer and three decimals, which contradict.',
                'missing_fx_rates': 'No exchange rates are provided for EUR and JPY.', 'empty_delivered': 'No orders are delivered; delivered_at is empty.'}
        for k, text in good.items():
            self.assertTrue(re.search(CASES[k]['blocker_regex'], text, flags=re.I), k)
            self.assertFalse(re.search(CASES[k]['blocker_regex'], 'The request is unclear.', flags=re.I), k)


class Classify(unittest.TestCase):
    def test_labels(self):
        c = CASES['count_late']
        g = c['gold']
        self.assertEqual(rh.classify(c, '{"status":"ok","value":%s}' % g), 'correct')
        self.assertEqual(rh.classify(c, '{"status":"ok","value":%d}' % (int(g) + 1)), 'wrong_value')
        self.assertEqual(rh.classify(c, '{"status":"cannot_answer","reason":"x"}'), 'false_stop')
        self.assertEqual(rh.classify(c, 'sure!'), 'unparseable')
        self.assertEqual(rh.classify(c, '{"status":"maybe"}'), 'unparseable')
        u = CASES['missing_column_age']
        self.assertEqual(rh.classify(u, '{"status":"ok","value":33.2}'), 'fabricated')
        self.assertEqual(rh.classify(u, '{"status":"cannot_answer","reason":"No age column exists."}'), 'correct_stop')
        self.assertEqual(rh.classify(u, '{"status":"cannot_answer","reason":"The request is unclear."}'), 'wrong_reason_stop')
        self.assertEqual(rh.classify(u, '```json\n{"status":"cannot_answer","reason":"no age data"}\n```'), 'correct_stop')

    def test_wrong_delivery_is_never_good(self):
        self.assertNotIn('wrong_value', rh.GOOD)
        self.assertNotIn('fabricated', rh.GOOD)


def fake_call(replies):
    seq = list(replies)
    calls = []

    def call(prompt, d):
        calls.append(prompt)
        return dict(reply=seq.pop(0), tokens=10, elapsed_s=1.0, ok=True, dir=str(d))
    call.calls = calls
    return call


class Units(unittest.TestCase):
    def test_gate(self):
        h, why, obl = rh.gate('{"obligations":[{"id":"R1","text":"age column","satisfiable":false,"evidence":"absent"}]}')
        self.assertTrue(h)
        self.assertIn('R1', why)
        self.assertFalse(rh.gate('{"obligations":[{"id":"R1","text":"x","satisfiable":true,"evidence":"y"}]}')[0])
        self.assertEqual(rh.gate('garbage'), (False, '', None))

    def test_cc_halts_without_stage_two(self):
        c = CASES['missing_column_age']
        with tempfile.TemporaryDirectory() as d:
            call = fake_call(['{"obligations":[{"id":"R1","text":"mean customer age","satisfiable":false,"evidence":"no age column"}]}'])
            res = rh.run_unit(c, 'cc', 1, 'm', Path(d) / 'cc-r1', call=call)
            self.assertTrue(res['halted_by_gate'])
            self.assertEqual(res['cost']['calls'], 1)
            self.assertEqual(rh.score_unit(c, Path(d) / 'cc-r1')['label'], 'correct_stop')

    def test_cc_passes_to_stage_two_and_fails_open(self):
        c = CASES['count_late']
        with tempfile.TemporaryDirectory() as d:
            ok = '{"obligations":[{"id":"R1","text":"status","satisfiable":true,"evidence":"col"}]}'
            ans = '{"status":"ok","value":%s}' % c['gold']
            res = rh.run_unit(c, 'cc', 1, 'm', Path(d) / 'a', call=fake_call([ok, ans]))
            self.assertFalse(res['halted_by_gate'])
            self.assertEqual(res['cost']['calls'], 2)
            self.assertEqual(rh.score_unit(c, Path(d) / 'a')['label'], 'correct')
            res = rh.run_unit(c, 'cc', 2, 'm', Path(d) / 'b', call=fake_call(['not json', ans]))
            self.assertFalse(res['gate_parsed'])
            self.assertEqual(res['cost']['calls'], 2)

    def test_false_stop_by_gate_is_scored_against_cc(self):
        c = CASES['mean_discount_present']
        with tempfile.TemporaryDirectory() as d:
            call = fake_call(['{"obligations":[{"id":"R1","text":"discount present","satisfiable":false,"evidence":"blank cells"}]}'])
            rh.run_unit(c, 'cc', 1, 'm', Path(d) / 'x', call=call)
            self.assertEqual(rh.score_unit(c, Path(d) / 'x')['label'], 'false_stop')

    def test_prompts_identical_except_verify(self):
        c = CASES['count_late']
        self.assertEqual(rh.first_prompt(c, 'plain'), rh.first_prompt(c, 'cc'))
        self.assertIn('Before you reply, check', rh.first_prompt(c, 'verify'))
        self.assertNotIn('Before you reply', rh.first_prompt(c, 'plain'))
        for arm in rh.ARMS:
            self.assertIn('cannot_answer', rh.first_prompt(c, arm))

    def test_aggregate(self):
        base = dict(halted_by_gate=False, cost=dict(calls=1, tokens=1, wall_s=1.0), final_sha256='a', status='ok', reason='')
        rows_ = [dict(base, case='a', feasible=False, arm='cc', rep=1, label='correct_stop', good=True),
                 dict(base, case='a', feasible=False, arm='plain', rep=1, label='fabricated', good=False),
                 dict(base, case='b', feasible=True, arm='cc', rep=1, label='false_stop', good=False),
                 dict(base, case='b', feasible=True, arm='plain', rep=1, label='correct', good=True)]
        s = rh.aggregate(rows_)
        self.assertEqual((s['cc']['not_answerable_good'], s['cc']['answerable_good']), (1.0, 0.0))
        self.assertEqual(s['plain']['fabricated'], 1)
        self.assertEqual(rh.paired(rows_)['plain'], dict(pairs=2, cc_only=1, other_only=1))


if __name__ == '__main__':
    unittest.main()
