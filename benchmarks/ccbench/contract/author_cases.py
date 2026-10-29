"""Authoring record for contract/cases.json (the frozen gold). Deterministic: fixed seeds, pure Python, no model.

Each case is a small CSV, a question, optional notes (conversion factors, definitions) and an output contract
(typed ports with unit, decimals, range, pattern). The gold is computed here with exact Decimal arithmetic and
round-half-up, straight from the rows, by code that knows nothing about the validator in contract.py.

  python author_cases.py --out DIR      writes DIR/cases.json
"""
import argparse
import json
import random
from datetime import date, datetime, timedelta
from decimal import Decimal as D, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 60


def q(x, d):
    """Round half up to d decimals; return the plain decimal string."""
    r = D(x).quantize(D(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return format(r, 'f')


def csv(header, rows):
    return '\n'.join([','.join(header)] + [','.join(str(v) for v in r) for r in rows])


def num(name, unit, decimals, lo, hi, desc):
    return dict(name=name, type='number', unit=unit, decimals=decimals, min=lo, max=hi, description=desc + ' Round half up to %d decimals.' % decimals)


def integer(name, unit, lo, hi, desc):
    return dict(name=name, type='integer', unit=unit, min=lo, max=hi, description=desc)


def string(name, pattern, desc):
    return dict(name=name, type='string', pattern=pattern, description=desc)


def boolean(name, desc):
    return dict(name=name, type='boolean', description=desc)


def frac(name, decimals, desc):
    return num(name, 'fraction', decimals, 0, 1, desc + ' A fraction between 0 and 1, not a percentage.')


def case(cid, header, rows, question, notes, ports, gold):
    assert set(gold) == {p['name'] for p in ports}, cid
    return dict(id=cid, data_csv=csv(header, rows), question=question, notes=notes, ports=ports, gold=gold)


def build():
    cases = []
    # 1 latency: data in ms, answer in seconds
    r = random.Random(1)
    ms = [r.randint(120, 2400) for _ in range(30)] + [9150, 11830]
    r.shuffle(ms)
    rows = [('r%03d' % (i + 1), v) for i, v in enumerate(ms)]
    cases.append(case('latency', ['request_id', 'latency_ms'], rows,
                      'What are the mean and the maximum request latency, and how many requests are in the data?', 'latency_ms is in milliseconds.',
                      [num('mean_latency_s', 'seconds', 3, 0, 60, 'Mean latency.'), num('max_latency_s', 'seconds', 3, 0, 60, 'Maximum latency.'),
                       integer('request_count', 'requests', 1, 100000, 'Number of requests.')],
                      dict(mean_latency_s=q(D(sum(ms)) / len(ms) / 1000, 3), max_latency_s=q(D(max(ms)) / 1000, 3), request_count=len(ms))))
    # 2 orders: cents to dollars, refund rate as fraction
    r = random.Random(2)
    rows = []
    for i in range(28):
        amt = r.randint(1500, 48000) + r.choice([0, 7, 33, 50, 99])
        ref = r.choice([0, 0, 0, 0, 0, r.randint(200, amt // 2)])
        rows.append(('o%03d' % (i + 1), amt, ref))
    gross, refund = sum(x[1] for x in rows), sum(x[2] for x in rows)
    cases.append(case('orders', ['order_id', 'amount_cents', 'refund_cents'], rows,
                      'What is the net revenue, the refund rate, and how many orders had a refund?',
                      'amount_cents and refund_cents are in US cents. Net revenue = total amount minus total refunds. Refund rate = total refunded / total amount.',
                      [num('net_revenue_usd', 'USD', 2, 0, 10000000, 'Net revenue.'), frac('refund_rate', 4, 'Refund rate.'),
                       integer('orders_with_refund', 'orders', 0, 100000, 'Orders with refund_cents > 0.')],
                      dict(net_revenue_usd=q(D(gross - refund) / 100, 2), refund_rate=q(D(refund) / D(gross), 4), orders_with_refund=sum(1 for x in rows if x[2] > 0))))
    # 3 shipments: mixed units
    r = random.Random(3)
    rows, kg = [], {}
    for i in range(24):
        u = r.choice(['kg', 'kg', 'lb', 'lb', 'g'])
        w = {'kg': D(r.randint(10, 190)) / 10, 'lb': D(r.randint(40, 520)) / 10, 'g': D(r.randint(400, 9000))}[u]
        sid = 'S%03d' % (i + 1)
        rows.append((sid, w, u))
        kg[sid] = {'kg': w, 'lb': w * D('0.45359237'), 'g': w / 1000}[u]
    top = sorted(kg.values())
    assert top[-1] != top[-2]
    cases.append(case('shipments', ['shipment_id', 'weight', 'unit'], rows,
                      'What is the total weight shipped, which shipment is the heaviest, and how many shipments weigh more than 10 kg?',
                      'unit is kg, lb or g. 1 lb = 0.45359237 kg and 1 g = 0.001 kg. Compare to 10 kg after converting.',
                      [num('total_kg', 'kg', 2, 0, 100000, 'Total weight.'), string('heaviest_shipment', r'^S\d{3}$', 'shipment_id of the heaviest shipment.'),
                       integer('count_over_10kg', 'shipments', 0, 1000, 'Shipments strictly heavier than 10 kg.')],
                      dict(total_kg=q(sum(kg.values()), 2), heaviest_shipment=max(kg, key=kg.get), count_over_10kg=sum(1 for v in kg.values() if v > 10))))
    # 4 monthly revenue: percent change
    r = random.Random(4)
    rev, v = [], 41000
    for m in range(12):
        v = v + r.randint(-3500, 6200)
        rev.append(v)
    rows = [('2023-%02d' % (m + 1), x) for m, x in enumerate(rev)]
    best = max(range(12), key=lambda i: rev[i])
    assert rev.count(max(rev)) == 1
    cases.append(case('monthly', ['month', 'revenue_usd'], rows,
                      'By what percentage did revenue change from the first to the last month, which month had the highest revenue, and did revenue fall in any month compared with the month before?',
                      'Percent change = (last - first) / first * 100. Revenue is in USD.',
                      [num('change_pct', 'percent', 1, -100, 10000, 'Percent change; 12.5 means 12.5 percent.'), string('best_month', r'^\d{4}-\d{2}$', 'Month with the highest revenue, YYYY-MM.'),
                       boolean('any_decline', 'True if some month is lower than the month before it.')],
                      dict(change_pct=q((D(rev[-1]) - rev[0]) / rev[0] * 100, 1), best_month=rows[best][0], any_decline=any(rev[i] < rev[i - 1] for i in range(1, 12)))))
    # 5 temperatures: F to C
    r = random.Random(5)
    start = date(2024, 7, 1)
    temps = [D(r.randint(640, 1040)) / 10 for _ in range(21)]
    assert len(set(temps)) == 21 and sorted(temps)[-1] != sorted(temps)[-2]
    rows = [((start + timedelta(days=i)).isoformat(), t) for i, t in enumerate(temps)]
    cel = [(t - 32) * 5 / 9 for t in temps]
    hot = max(range(21), key=lambda i: temps[i])
    cases.append(case('temps', ['date', 'temp_f'], rows,
                      'What was the mean daily temperature, which day was the hottest, and on how many days did the temperature exceed 30 degrees Celsius?',
                      'temp_f is in degrees Fahrenheit. C = (F - 32) * 5 / 9.',
                      [num('mean_temp_c', 'celsius', 1, -90, 60, 'Mean temperature.'), string('hottest_day', r'^\d{4}-\d{2}-\d{2}$', 'Date of the hottest day.'),
                       integer('days_above_30c', 'days', 0, 366, 'Days strictly above 30 C.')],
                      dict(mean_temp_c=q(sum(cel) / 21, 1), hottest_day=rows[hot][0], days_above_30c=sum(1 for c in cel if c > 30))))
    # 6 files: bytes to GiB
    r = random.Random(6)
    sizes = [r.randint(40_000_000, 900_000_000) for _ in range(18)] + [3_400_000_000]
    rows = [('/data/f%02d.bin' % i, s) for i, s in enumerate(sizes)]
    tot = sum(sizes)
    cases.append(case('files', ['path', 'size_bytes'], rows,
                      'What is the total size of all files, which file is the largest, and what share of the total does it take?',
                      'size_bytes is in bytes. 1 GiB = 1073741824 bytes.',
                      [num('total_gib', 'GiB', 3, 0, 100000, 'Total size.'), string('largest_file', r'^/data/f\d{2}\.bin$', 'Path of the largest file.'),
                       frac('largest_share', 3, 'Largest file size divided by total size.')],
                      dict(total_gib=q(D(tot) / 1073741824, 3), largest_file=rows[sizes.index(max(sizes))][0], largest_share=q(D(max(sizes)) / tot, 3))))
    # 7 sessions: timestamps to hours and minutes
    r = random.Random(7)
    rows, secs = [], []
    t0 = datetime(2024, 3, 4, 8, 0, 0)
    for i in range(16):
        s = t0 + timedelta(minutes=r.randint(0, 600), days=i)
        d = r.randint(12, 140) * 60 + r.choice([0, 0, 15, 30, 30, 45])
        rows.append(('u%02d' % (i + 1), s.isoformat(), (s + timedelta(seconds=d)).isoformat()))
        secs.append(d)
    assert secs.count(max(secs)) == 1
    cases.append(case('sessions', ['user', 'start', 'end'], rows,
                      'What is the total time spent in sessions, the length of the longest session, and the mean session length?',
                      'Timestamps are ISO 8601 in one time zone. Session length = end - start.',
                      [num('total_hours', 'hours', 2, 0, 100000, 'Total session time.'), integer('longest_session_minutes', 'minutes', 0, 100000, 'Longest session, rounded half up to a whole number of minutes.'),
                       num('mean_session_minutes', 'minutes', 1, 0, 100000, 'Mean session length.')],
                      dict(total_hours=q(D(sum(secs)) / 3600, 2), longest_session_minutes=int(D(max(secs)) / 60 + D('0.5')), mean_session_minutes=q(D(sum(secs)) / len(secs) / 60, 1))))
    # 8 survey: missing values
    r = random.Random(8)
    rows, vals = [], []
    for i in range(30):
        x = r.choice([1, 2, 3, 3, 4, 4, 4, 5, 5, 'NA', '', 'NA'])
        rows.append(('p%02d' % (i + 1), x))
        if x not in ('NA', ''):
            vals.append(x)
    cases.append(case('survey', ['respondent', 'score'], rows,
                      'What is the mean score, what share of respondents answered, and how many did not answer?',
                      'score is 1 to 5. A blank cell or the text NA means the respondent did not answer; leave those out of the mean.',
                      [num('mean_score', 'points', 2, 1, 5, 'Mean score of answered rows.'), frac('response_rate', 3, 'Answered rows divided by all rows.'),
                       integer('n_missing', 'respondents', 0, 100000, 'Rows without an answer.')],
                      dict(mean_score=q(D(sum(vals)) / len(vals), 2), response_rate=q(D(len(vals)) / 30, 3), n_missing=30 - len(vals))))
    # 9 customers: exact duplicate rows
    r = random.Random(9)
    base = []
    for i in range(20):
        cid = 'C%02d' % r.randint(1, 9)
        base.append((cid, r.choice(['Ana', 'Ben', 'Cy']) + str(i), '%d.%02d' % (r.randint(5, 400), r.randint(0, 99))))
    rows = list(base)
    for k in (2, 7, 11, 15):
        rows.insert(k + 3, base[k])
    uniq = []
    for x in rows:
        if x not in uniq:
            uniq.append(x)
    spend = {}
    for c, _, s in uniq:
        spend[c] = spend.get(c, D(0)) + D(s)
    ordered = sorted(spend.values())
    assert ordered[-1] != ordered[-2]
    cases.append(case('customers', ['customer_id', 'note', 'spend_usd'], rows,
                      'After removing export errors, how many purchases are there, what is the total spend, and which customer spent the most in total?',
                      'A row that is identical to an earlier row in every column is an export error: count it once. Rows with the same customer_id but any different value are separate purchases. spend_usd is in US dollars.',
                      [integer('purchases', 'rows', 0, 100000, 'Purchases after removing exact duplicate rows.'), num('total_spend_usd', 'USD', 2, 0, 10000000, 'Total spend after removing duplicates.'),
                       string('top_customer_id', r'^C\d{2}$', 'customer_id with the highest total spend.')],
                      dict(purchases=len(uniq), total_spend_usd=q(sum(spend.values()), 2), top_customer_id=max(spend, key=spend.get))))
    # 10 grades: weighted mean
    r = random.Random(10)
    scores = r.sample(range(35, 100), 18)
    rows = [('s%02d' % (i + 1), scores[i], r.choice([1, 1, 2, 3])) for i in range(18)]
    sc = {x[0]: x[1] for x in rows}
    assert sorted(sc.values())[-1] != sorted(sc.values())[-2]
    cases.append(case('grades', ['student', 'exam_pct', 'weight'], rows,
                      'What is the weight-adjusted mean exam score, what share of students scored at least 60, and who scored highest?',
                      'exam_pct is already a percentage (0 to 100). Weighted mean = sum(exam_pct * weight) / sum(weight). The pass share counts students (rows) with exam_pct >= 60, unweighted.',
                      [num('weighted_mean_pct', 'percent', 2, 0, 100, 'Weighted mean exam score as a percentage (0 to 100).'), frac('pass_share', 2, 'Share of students with exam_pct >= 60.'),
                       string('top_student', r'^s\d{2}$', 'student with the highest exam_pct.')],
                      dict(weighted_mean_pct=q(D(sum(x[1] * x[2] for x in rows)) / sum(x[2] for x in rows), 2), pass_share=q(D(sum(1 for x in rows if x[1] >= 60)) / 18, 2), top_student=max(sc, key=sc.get))))
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
