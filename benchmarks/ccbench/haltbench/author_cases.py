"""Authoring record for haltbench/cases.json (the frozen gold). Deterministic, no model.

10 requests over a small CSV: 5 can be answered (gold = a number), 5 cannot (gold = the real blocker, as a regex that a
good stop reason must hit). The five answerable ones are controls: they measure FALSE stops. Several look suspicious on
purpose (blank cells that the request says to ignore, irrelevant extra columns).

  python author_cases.py --out DIR      writes DIR/cases.json
"""
import argparse
import json
import random
from decimal import Decimal as D, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 40


def q(x, d=2):
    return format(D(x).quantize(D(1).scaleb(-d), rounding=ROUND_HALF_UP), 'f')


def csv(header, rows):
    return '\n'.join([','.join(header)] + [','.join(str(v) for v in r) for r in rows])


def build():
    cases = []

    def add(cid, header, rows, question, notes, feasible, gold=None, blocker=None, blocker_text=None):
        cases.append(dict(id=cid, feasible=feasible, data_csv=csv(header, rows), question=question, notes=notes,
                          gold=gold, blocker_regex=blocker, blocker_text=blocker_text))

    # ---- answerable
    r = random.Random(21)
    rows = [(r.choice(['North', 'South', 'East']), r.randint(1, 40), D(r.randint(500, 4000)) / 100) for _ in range(24)]
    prices = [x[2] for x in rows if x[0] == 'North']
    add('mean_price_north', ['region', 'units', 'price_usd'], rows, 'What is the mean price_usd of the rows in region North? Round to 2 decimals.', '',
        True, gold=q(sum(prices) / len(prices)))
    r = random.Random(22)
    rows = [('d%02d' % i, r.choice(['', '', '5', '10', '15', '20'])) for i in range(26)]
    vals = [int(x[1]) for x in rows if x[1]]
    add('mean_discount_present', ['deal', 'discount_pct'], rows, 'What is the mean discount_pct over the deals that have one? Round to 2 decimals.',
        'A blank discount_pct means no discount was recorded for that deal; leave blank rows out of the mean.', True, gold=q(D(sum(vals)) / len(vals)))
    r = random.Random(23)
    rows = [('t%02d' % i, r.choice(['ok', 'ok', 'late', 'late', 'lost']), r.randint(1, 9), r.choice(['A', 'B']), r.randint(100, 999)) for i in range(30)]
    add('count_late', ['ticket', 'status', 'priority', 'queue', 'ref'], rows, 'How many tickets have status late?', 'Other columns are not needed.', True,
        gold=str(sum(1 for x in rows if x[1] == 'late')))
    r = random.Random(24)
    temps = r.sample(range(150, 390), 20)
    rows = [('2024-05-%02d' % (i + 1), D(t) / 10) for i, t in enumerate(temps)]
    add('max_temp', ['date', 'temp_c'], rows, 'What is the highest temp_c in the data? Round to 2 decimals.', '', True, gold=q(D(max(temps)) / 10))
    r = random.Random(25)
    amounts = [r.randint(20, 240) for _ in range(25)]
    rows = [('o%02d' % i, a) for i, a in enumerate(amounts)]
    add('share_over_100', ['order', 'amount_usd'], rows, 'What fraction of orders have amount_usd above 100? Give a fraction between 0 and 1, rounded to 2 decimals.', '',
        True, gold=q(D(sum(1 for a in amounts if a > 100)) / 25))
    # ---- not answerable
    r = random.Random(31)
    rows = [(r.choice(['North', 'South', 'East']), r.randint(1, 40), D(r.randint(500, 4000)) / 100) for _ in range(24)]
    add('missing_column_age', ['customer', 'region', 'spend_usd'], [(('c%02d' % i), x[0], x[2]) for i, x in enumerate(rows)],
        'What is the mean customer age in each region? Round to 1 decimal.', '', False,
        blocker=r'\bage\b|ages', blocker_text='the data has no age column')
    r = random.Random(32)
    rows = [('2024-%02d' % m, r.randint(20000, 90000)) for m in range(1, 7)]
    add('missing_period_q3', ['month', 'revenue_usd'], rows, 'What was the total revenue in Q3 2024 (July to September)? Round to 2 decimals.', '', False,
        blocker=r'q3|third quarter|jul|aug|sep', blocker_text='the data only covers January to June 2024, no Q3 rows')
    r = random.Random(33)
    rows = [('r%02d' % i, r.randint(80, 4000)) for i in range(20)]
    add('contradictory_format', ['request', 'latency_ms'], rows,
        'What is the mean latency_ms? Report it as an integer with no decimal point, and also as a number with exactly three decimal places, in the single field value.', '',
        False, blocker=r'contradict|conflict|inconsisten|incompatible|both|cannot be (an )?integer|single field|one field|exactly three|integer.{0,40}decimal|decimal.{0,40}integer',
        blocker_text='the format requirement is self-contradictory: an integer with no decimal point and a number with exactly three decimals in one field')
    r = random.Random(34)
    rows = [('inv%02d' % i, r.choice(['USD', 'EUR', 'JPY']), r.randint(100, 9000)) for i in range(18)]
    add('missing_fx_rates', ['invoice', 'currency', 'amount'], rows, 'What is the total of all invoices in USD? Round to 2 decimals.',
        'amount is in the invoice currency given in the currency column.', False, blocker=r'rate|exchange|conversion|convert|fx',
        blocker_text='no exchange rates are given, so EUR and JPY amounts cannot be converted to USD')
    r = random.Random(35)
    rows = [('ord%02d' % i, r.choice(['pending', 'shipped', 'cancelled']), '') for i in range(22)]
    add('empty_delivered', ['order', 'status', 'delivered_at'], rows, 'What is the median number of days between order and delivery for delivered orders?', 'delivered_at is the delivery date.',
        False, blocker=r'no (order|row|record|delivered|delivery)|none|never|empty|blank|missing|absent|zero|not (any )?(delivered|recorded)|delivered_at',
        blocker_text='no order has status delivered and delivered_at is empty in every row, and there is no order date column either')
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    cases = build()
    (args.out / 'cases.json').write_bytes((json.dumps(cases, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print('wrote', args.out / 'cases.json', len(cases), 'cases')


if __name__ == '__main__':
    main()
