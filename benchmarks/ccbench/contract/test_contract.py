import sys
sys.dont_write_bytecode = True
import csv
import io
import json
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

import modelbench as mb
import contract
import run_contract as rc

HERE = Path(__file__).resolve().parent
CASES = {c['id']: c for c in rc.load_cases()}


def rows(case):
    return list(csv.DictReader(io.StringIO(case['data_csv'])))


def r(x, d):
    return format(D(x).quantize(D(1).scaleb(-d), rounding=ROUND_HALF_UP), 'f')


class GoldRecomputedFromCsv(unittest.TestCase):
    """A second derivation of the gold straight from each case's CSV text (not from the authoring variables)."""

    def test_latency(self):
        v = [int(x['latency_ms']) for x in rows(CASES['latency'])]
        g = CASES['latency']['gold']
        self.assertEqual((g['mean_latency_s'], g['max_latency_s'], g['request_count']), (r(D(sum(v)) / len(v) / 1000, 3), r(D(max(v)) / 1000, 3), len(v)))

    def test_orders(self):
        x = rows(CASES['orders'])
        a, f = sum(int(i['amount_cents']) for i in x), sum(int(i['refund_cents']) for i in x)
        g = CASES['orders']['gold']
        self.assertEqual((g['net_revenue_usd'], g['refund_rate'], g['orders_with_refund']), (r(D(a - f) / 100, 2), r(D(f) / a, 4), sum(int(i['refund_cents']) > 0 for i in x)))

    def test_shipments(self):
        f = {'kg': D(1), 'lb': D('0.45359237'), 'g': D('0.001')}
        kg = {i['shipment_id']: D(i['weight']) * f[i['unit']] for i in rows(CASES['shipments'])}
        g = CASES['shipments']['gold']
        self.assertEqual((g['total_kg'], g['heaviest_shipment'], g['count_over_10kg']), (r(sum(kg.values()), 2), max(kg, key=kg.get), sum(v > 10 for v in kg.values())))

    def test_monthly(self):
        x = rows(CASES['monthly'])
        v = [int(i['revenue_usd']) for i in x]
        g = CASES['monthly']['gold']
        self.assertEqual((g['change_pct'], g['best_month'], g['any_decline']), (r(D(v[-1] - v[0]) / v[0] * 100, 1), x[v.index(max(v))]['month'], any(b < a for a, b in zip(v, v[1:]))))

    def test_temps(self):
        x = rows(CASES['temps'])
        c = [(D(i['temp_f']) - 32) * 5 / 9 for i in x]
        g = CASES['temps']['gold']
        self.assertEqual((g['mean_temp_c'], g['hottest_day'], g['days_above_30c']), (r(sum(c) / len(c), 1), x[c.index(max(c))]['date'], sum(v > 30 for v in c)))

    def test_files(self):
        x = rows(CASES['files'])
        s = [int(i['size_bytes']) for i in x]
        g = CASES['files']['gold']
        self.assertEqual((g['total_gib'], g['largest_file'], g['largest_share']), (r(D(sum(s)) / 2 ** 30, 3), x[s.index(max(s))]['path'], r(D(max(s)) / sum(s), 3)))

    def test_sessions(self):
        d = [int((datetime.fromisoformat(i['end']) - datetime.fromisoformat(i['start'])).total_seconds()) for i in rows(CASES['sessions'])]
        g = CASES['sessions']['gold']
        self.assertEqual((g['total_hours'], g['longest_session_minutes'], g['mean_session_minutes']),
                         (r(D(sum(d)) / 3600, 2), int(r(D(max(d)) / 60, 0)), r(D(sum(d)) / len(d) / 60, 1)))

    def test_survey(self):
        x = rows(CASES['survey'])
        v = [int(i['score']) for i in x if i['score'] not in ('', 'NA')]
        g = CASES['survey']['gold']
        self.assertEqual((g['mean_score'], g['response_rate'], g['n_missing']), (r(D(sum(v)) / len(v), 2), r(D(len(v)) / len(x), 3), len(x) - len(v)))

    def test_customers(self):
        seen, tot = [], {}
        for i in rows(CASES['customers']):
            t = tuple(i.values())
            if t not in seen:
                seen.append(t)
                tot[i['customer_id']] = tot.get(i['customer_id'], D(0)) + D(i['spend_usd'])
        g = CASES['customers']['gold']
        self.assertEqual((g['purchases'], g['total_spend_usd'], g['top_customer_id']), (len(seen), r(sum(tot.values()), 2), max(tot, key=tot.get)))

    def test_grades(self):
        x = rows(CASES['grades'])
        w = sum(int(i['weight']) for i in x)
        g = CASES['grades']['gold']
        self.assertEqual((g['weighted_mean_pct'], g['pass_share'], g['top_student']),
                         (r(D(sum(int(i['exam_pct']) * int(i['weight']) for i in x)) / w, 2), r(D(sum(int(i['exam_pct']) >= 60 for i in x)) / len(x), 2),
                          max(x, key=lambda i: int(i['exam_pct']))['student']))

    def test_manifest_and_shape(self):
        self.assertEqual(mb.verify_manifest(HERE), [])
        self.assertEqual(len(CASES), 10)
        for c in CASES.values():
            self.assertEqual(set(c['gold']), {p['name'] for p in c['ports']})
            # the gold itself is inside the declared range (so the validator never rejects a correct answer)
            for p in c['ports']:
                if p['type'] in ('number', 'integer'):
                    self.assertTrue(D(str(p['min'])) <= D(str(c['gold'][p['name']])) <= D(str(p['max'])), (c['id'], p['name']))
            gold_obj = json.loads(json.dumps({k: (float(v) if isinstance(v, str) and p['type'] == 'number' else v) for p in c['ports'] for k, v in [(p['name'], c['gold'][p['name']])]}))
            self.assertEqual(contract.validate(json.dumps(gold_obj), c['ports'])[0], [], c['id'])


class Validator(unittest.TestCase):
    ports = CASES['orders']['ports']

    def test_clean_reply_and_fence(self):
        text = '```json\n{"net_revenue_usd": 6848.65, "refund_rate": 0.0408, "orders_with_refund": 3}\n```'
        self.assertEqual(contract.validate(text, self.ports)[0], [])

    def test_unit_and_type_slips_are_caught(self):
        v = contract.validate('{"net_revenue_usd": 6848.653, "refund_rate": 4.08, "orders_with_refund": 3.0}', self.ports)[0]
        joined = ' '.join(v)
        self.assertIn('3 decimals', joined)
        self.assertIn('above the maximum 1', joined)
        self.assertIn('integer', joined)

    def test_keys_strings_and_bools(self):
        v = contract.validate('{"net_revenue_usd": "6848.65", "orders_with_refund": true, "extra": 1}', self.ports)[0]
        joined = ' '.join(v)
        self.assertIn('missing required field refund_rate', joined)
        self.assertIn('unexpected field extra', joined)
        self.assertIn('must be a JSON number', joined)
        self.assertEqual(contract.validate('no json here', self.ports)[0], ['no JSON object found'])
        self.assertEqual(contract.validate('', self.ports)[0], ['empty reply'])

    def test_validator_does_not_read_gold(self):
        import inspect
        self.assertNotIn('gold', inspect.getsource(contract.validate))
        self.assertNotIn('gold', inspect.getsource(contract.check_value))

    def test_scoring_separates_correct_from_compliant(self):
        gold = CASES['orders']['gold']
        ok = contract.score_reply('{"net_revenue_usd": 6848.65, "refund_rate": 0.0408, "orders_with_refund": 3}', self.ports, gold)
        self.assertTrue(ok['correct_and_compliant'])
        pct = contract.score_reply('{"net_revenue_usd": 6848.65, "refund_rate": 4.08, "orders_with_refund": 3}', self.ports, gold)
        self.assertFalse(pct['all_correct'])
        self.assertFalse(pct['compliant'])
        extra = contract.score_reply('{"net_revenue_usd": 6848.65, "refund_rate": 0.0408, "orders_with_refund": 3, "note": "x"}', self.ports, gold)
        self.assertTrue(extra['all_correct'])
        self.assertFalse(extra['compliant'])
        self.assertFalse(extra['correct_and_compliant'])
        self.assertFalse(contract.score_reply('garbage', self.ports, gold)['parsed'])
        # a wrong value inside the declared range is compliant but wrong: the contract cannot fix correctness
        wrong = contract.score_reply('{"net_revenue_usd": 6000.00, "refund_rate": 0.0408, "orders_with_refund": 3}', self.ports, gold)
        self.assertTrue(wrong['compliant'])
        self.assertFalse(wrong['all_correct'])


def fake_call(replies):
    seq = list(replies)
    calls = []

    def call(prompt, d):
        calls.append(prompt)
        return dict(reply=seq.pop(0), tokens=50, elapsed_s=1.0, ok=True, dir=str(d))
    call.calls = calls
    return call


class Units(unittest.TestCase):
    def test_cc_retries_on_violation_and_carries_reason(self):
        case = CASES['orders']
        good = json.dumps({k: (float(v) if isinstance(v, str) else v) for k, v in case['gold'].items()})
        with tempfile.TemporaryDirectory() as d:
            call = fake_call(['{"net_revenue_usd": 6848.65, "refund_rate": 4.08, "orders_with_refund": 3}', good])
            res = rc.run_unit(case, 'cc', 1, 'm', Path(d) / 'cc-r1', call=call)
            self.assertTrue(res['retried'])
            self.assertIn('above the maximum 1', call.calls[1])
            self.assertIn('refund_rate', call.calls[1])
            row = rc.score_unit(case, Path(d) / 'cc-r1')
            self.assertTrue(row['correct_and_compliant'])
            self.assertFalse(row['first_correct_and_compliant'])
            self.assertEqual(res['cost']['calls'], 2)

    def test_cc_clean_first_reply_no_retry_and_others_never_retry(self):
        case = CASES['orders']
        bad = '{"net_revenue_usd": 6848.65, "refund_rate": 4.08, "orders_with_refund": 3}'
        with tempfile.TemporaryDirectory() as d:
            for arm in ('plain', 'verify'):
                res = rc.run_unit(case, arm, 1, 'm', Path(d) / arm, call=fake_call([bad]))
                self.assertFalse(res['retried'])
            self.assertEqual(rc.first_prompt(case, 'plain'), rc.first_prompt(case, 'cc'))
            self.assertIn('check each value', rc.first_prompt(case, 'verify'))
            self.assertNotIn('check each value', rc.first_prompt(case, 'plain'))
            self.assertIn(case['data_csv'], rc.first_prompt(case, 'plain'))

    def test_aggregate_and_pairs(self):
        base = dict(fields={'a': True}, compliant=True, retried=False, violations=[], final_sha256='x', cost=dict(calls=1, tokens=5, wall_s=1.0), first_correct_and_compliant=True)
        rows_ = [dict(base, case='c', arm='cc', rep=1, all_correct=True, correct_and_compliant=True),
                 dict(base, case='c', arm='plain', rep=1, all_correct=False, correct_and_compliant=False, first_correct_and_compliant=False),
                 dict(base, case='c', arm='cc', rep=2, all_correct=True, correct_and_compliant=True, final_sha256='y')]
        s = rc.aggregate(rows_)
        self.assertEqual(s['cc']['correct_and_compliant'], 1.0)
        self.assertEqual(s['plain']['correct_and_compliant'], 0.0)
        self.assertEqual(s['cc']['identical_reply_across_reps'], 0.0)
        self.assertEqual(rc.paired(rows_)['plain'], dict(pairs=1, cc_only=1, other_only=0))


if __name__ == '__main__':
    unittest.main()
