"""Materialize items/ and referee/. Offline, deterministic. Run once, then freeze by SHA256SUMS.

Usage: python build_items.py --out DIR  (writes DIR/items, DIR/referee, DIR/equivalence.json).
Reads admission/ sources (read-only).
"""
import argparse
import copy
import csv
import importlib
import importlib.util
import io
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADM = HERE.parent / 'admission'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ADM))
sys.path.insert(0, str(HERE))
import oracle  # noqa: E402
from derive import derive_tests  # noqa: E402
import jobs  # noqa: E402
import build_candidates  # noqa: E402  (SOURCES only; main() is guarded)

GT = {r['candidate']: r for r in json.loads((ADM / 'ground_truth.json').read_text(encoding='utf-8'))}
DECL = json.loads((ADM / 'declarations.json').read_text(encoding='utf-8'))
REF_SRC = (ADM / 'reference.py').read_text(encoding='utf-8')
SOURCES = build_candidates.SOURCES

HEADER = 'import copy\nimport csv\nimport io\nimport json\nimport math\nimport re\nimport sys\nfrom decimal import Decimal, localcontext, ROUND_HALF_EVEN\n\n\n'


def func_text(name):
    start = REF_SRC.index('def ' + name)
    nxt = REF_SRC.find('\n\n\ndef ', start + 1)
    return REF_SRC[start:] if nxt < 0 else REF_SRC[start:nxt + 1]


CALC_CLI = '''

def main(argv):
    if len(argv) < 3:
        print('usage: calc_tool.py FILE.csv COLUMN OPERATION [--where COLUMN=VALUE]')
        print('operations: count sum mean min max')
        return 2
    path, column, operation = argv[:3]
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if '--where' in argv:
        key, val = argv[argv.index('--where') + 1].split('=', 1)
        rows = [r for r in rows if r[key] == val]
    result = run({'values': [r[column] for r in rows], 'mode': 'decimal_strings', 'operation': operation})
    if result['status'] != 'ok':
        print('error: could not compute')
        return 1
    print(result['value'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
'''

TABLE_CLI = '''

def main(argv):
    if len(argv) < 1:
        print('usage: table_tool.py FILE.csv|FILE.json')
        return 2
    path = argv[0]
    is_json = path.lower().endswith('.json')
    with open(path, encoding='utf-8', newline='') as f:
        text = f.read()
    if is_json:
        columns = list(json.loads(text)[0].keys())
    else:
        columns = next(csv.reader(io.StringIO(text, newline='')))
    result = run({'text': text, 'format': 'json' if is_json else 'csv', 'columns': columns, 'delimiter': None if is_json else ','})
    print(json.dumps(result))
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
'''


def public_module(candidate, tool):
    body = SOURCES[candidate]
    run = 'def run(payload):\n    p = copy.deepcopy(payload)\n' + '\n'.join('    ' + l for l in body.splitlines()) + '\n'
    core = func_text('calculate' if tool == 'calculate' else 'table_normalize')
    return HEADER + core.rstrip('\n') + '\n\n\n' + run + (CALC_CLI if tool == 'calculate' else TABLE_CLI)


def csv_text(header, rows):
    s = io.StringIO(newline='')
    w = csv.writer(s, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    return s.getvalue()


def d2(x):
    return f'{x:.2f}'


# ---------------------------------------------------------------- data ----
def data_calc_absolute():
    r = random.Random(1101)
    rows = []
    for i in range(36):
        amt = r.randint(2500, 90000) / 100
        if r.random() < 0.3:
            amt = -r.randint(500, 30000) / 100
        rows.append([f'2026-09-{1 + i % 28:02d}', r.choice(['ops', 'sales', 'infra', 'travel']), d2(amt)])
    return 'ledger.csv', csv_text(['date', 'account', 'amount'], rows), 'amount'


def data_calc_float():
    r = random.Random(1102)
    rows = [[f'tr{i:03d}', r.choice(['alpha', 'beta', 'gamma']), str(r.randint(10**15, 9 * 10**15) | 1)] for i in range(30)]
    return 'transfers.csv', csv_text(['id', 'host', 'bytes'], rows), 'bytes'


def data_calc_truncate():
    r = random.Random(1103)
    rows = [[f'run{i:03d}', r.choice(['m1', 'm2', 'm3']), f'{r.randint(800, 4000) / 10:.1f}'] for i in range(40)]
    return 'runs.csv', csv_text(['run', 'machine', 'latency_ms'], rows), 'latency_ms'


def data_calc_empty():
    r = random.Random(1104)
    rows = [[r.choice(['Porto', 'Madrid', 'Oslo']), f'R{1000 + i}', d2(r.randint(500, 9000) / 100)] for i in range(30)]
    return 'refunds.csv', csv_text(['store', 'order', 'refund'], rows), 'refund'


def data_calc_comma():
    r = random.Random(1105)
    rows = []
    for i in range(30):
        v = r.choice([r.randint(120, 990), r.randint(1000, 9999), r.randint(10000, 48000)])
        rows.append([f'INV-{500 + i}', r.choice(['Acme', 'Borealis', 'Cobalt']), f'{v:,}'])
    return 'invoices.csv', csv_text(['invoice', 'client', 'amount'], rows), 'amount'


def data_calc_reference():
    r = random.Random(1106)
    rows = [[f'2026-10-{1 + i % 28:02d}', r.choice(['north', 'south']), f'{r.randint(-120, 280) / 10:.1f}'] for i in range(32)]
    return 'temps.csv', csv_text(['day', 'station', 'temp_c'], rows), 'temp_c'


NAMES = ['Ana Silva', 'Bo Tran', 'Cleo Park', 'Dev Rao', 'Eli Voss', 'Fay Chen', 'Gus Holm', 'Ida Lund', 'Jon Kerr', 'Kai Mori']


def data_table_numeric():
    r = random.Random(1201)
    rows = []
    for i in range(30):
        zc = f'{r.randint(10000, 99999):05d}'
        if i in (3, 8, 12, 16, 21):
            zc = f'0{r.randint(1000, 9999)}'
        rows.append([f'C-{1001 + i}', r.choice(NAMES), r.choice(['Boston', 'Denver', 'Austin', 'Newark']), zc])
    rows[16][3] = '02134'
    return 'customers.csv', csv_text(['customer_id', 'name', 'city', 'zip'], rows)


def data_table_sorted():
    r = random.Random(1202)
    ids = r.sample(range(1000, 9999), 30)
    rows = [[f'O-{n}', r.choice(['cable', 'dock', 'hub', 'stand']), d2(r.randint(500, 9000) / 100)] for n in ids]
    rows[-1][0] = 'O-1204'
    rows[-1][2] = '18.75'
    return 'orders.csv', csv_text(['order_id', 'item', 'amount'], rows)


def data_table_strip():
    r = random.Random(1203)
    notes = ['refund pending', 'awaiting parts', 'called back', 'escalated', 'closed by phone', 'needs follow-up']
    rows = []
    for i in range(25):
        n = r.choice(notes)
        if i in (2, 9):
            n = n + ' '
        rows.append([f'T-{100 + i}', r.choice(NAMES), n])
    for row in rows:
        if row[0] == 'T-114':
            row[2] = '  awaiting parts  '
    return 'tickets.csv', csv_text(['ticket', 'customer', 'note'], rows)


def data_table_float():
    r = random.Random(1204)
    recs = [{'shipment_id': 9007199254740993 + 2 * r.randint(50, 400000), 'dest': r.choice(['Rotterdam', 'Hamburg', 'Antwerp']), 'kg': r.randint(10, 900) / 2} for _ in range(25)]
    return 'shipments.json', json.dumps(recs, indent=1) + '\n'


def data_table_pad():
    r = random.Random(1205)
    rows = []
    for i in range(30):
        phone = f'555-{r.randint(1000, 9999)}' if r.random() < 0.75 else ''
        rows.append([NAMES[i % len(NAMES)] + f' {i}', f'user{i}@example.org', phone])
    rows[11] = ['Bo Tran 11', '555-0142']
    return 'contacts.csv', csv_text(['name', 'email', 'phone'], rows)


def data_table_reference():
    r = random.Random(1206)
    rows = [[f'{r.randint(1, 99999):05d}', r.choice(['  bolt', 'nut ', 'washer', ' clip ']), str(r.randint(1, 400)), f'B{r.randint(1, 9)}'] for _ in range(28)]
    rows[-1][0] = '00417'
    rows[3][0] = '00052'
    return 'stock.csv', csv_text(['code', 'desc', 'qty', 'bin'], rows)


# ---------------------------------------------------------------- items ----
def prefix(tool):
    return 'Our team uses calc_tool.py for this. Use it to ' if tool == 'calculate' else 'Our team uses table_tool.py to read data files. Use it to '


ITEMS = []


def calc_item(cand, id_, data, op, where, phrase, **extra):
    fname, text, col = data
    ITEMS.append(dict(id=id_, cand=cand, tool='calculate', fname=fname, text=text, col=col, op=op, where=where, phrase=phrase, **extra))


calc_item('calculate_absolute', 'calc_absolute', data_calc_absolute(), 'sum', None, 'compute the total of the amount column in ledger.csv and give me the number.')
calc_item('calculate_float', 'calc_float', data_calc_float(), 'sum', None, 'compute the total of the bytes column in transfers.csv and give me the number.')
calc_item('calculate_truncate', 'calc_truncate', data_calc_truncate(), 'mean', None, 'compute the mean of the latency_ms column in runs.csv and give me the number.')
calc_item('calculate_empty', 'calc_empty', data_calc_empty(), 'sum', 'store=Lisbon', 'compute the total of the refund column in refunds.csv for the Lisbon store (the store column) and give me the number.')
calc_item('calculate_comma', 'calc_comma', data_calc_comma(), 'sum', None, 'compute the total of the amount column in invoices.csv and give me the number.', intended_thousands=True)
calc_item('calculate_reference', 'calc_reference', data_calc_reference(), 'mean', None, 'compute the mean of the temp_c column in temps.csv and give me the number.')


def table_item(cand, id_, data, extract, phrase, kind, **extra):
    fname, text = data
    ITEMS.append(dict(id=id_, cand=cand, tool='table_normalize', fname=fname, text=text, extract=extract, phrase=phrase, kind=kind, **extra))


table_item('table_normalize_numeric', 'table_numeric', data_table_numeric(), dict(type='where', key='customer_id', val='C-1017', field='zip'), 'look up the zip code for customer C-1017 in customers.csv and give me the number.', 'token')
table_item('table_normalize_sorted', 'table_sorted', data_table_sorted(), dict(type='last', field='amount'), 'load orders.csv and give me the amount on the last row of the file, which is the most recent order.', 'number')
table_item('table_normalize_strip', 'table_strip', data_table_strip(), dict(type='strlen', key='ticket', val='T-114', field='note'), 'read tickets.csv and tell me how many characters long the note on ticket T-114 is, counting every character. Give me the number.', 'number')
table_item('table_normalize_float', 'table_float', data_table_float(), dict(type='nth', n=14, field='shipment_id'), 'read shipments.json and give me the shipment_id of the 14th record.', 'token')
table_item('table_normalize_pad', 'table_pad', data_table_pad(), dict(type='count_nonempty', field='phone'), 'read contacts.csv and tell me how many contacts have a phone number listed. Give me the number.', 'number')
table_item('table_normalize_reference', 'table_reference', data_table_reference(), dict(type='last', field='code'), 'read stock.csv and give me the code on the last row of the file.', 'token')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def gold_for(it):
    """Gold via oracle.py (Fraction exact). Returns (answer or None, oracle_status, note)."""
    if it['tool'] == 'calculate':
        rows = list(csv.DictReader(io.StringIO(it['text'], newline='')))
        if it['where']:
            k, v = it['where'].split('=', 1)
            rows = [r for r in rows if r[k] == v]
        vals = [r[it['col']] for r in rows]
        exp = oracle.expected('calculate', {'values': vals, 'mode': 'decimal_strings', 'operation': it['op']})
        if exp['status'] == 'ok':
            return jobs.frac_str(Fraction(exp['value'])), 'ok', 'oracle value'
        if it.get('intended_thousands'):
            q = sum(Fraction(v.replace(',', '')) for v in vals)
            return jobs.frac_str(q), 'error', 'oracle rejects thousands separators; gold is the intended sum with the comma read as a thousands separator'
        raise AssertionError('unexpected oracle error')
    is_json = it['fname'].endswith('.json')
    cols = list(json.loads(it['text'])[0].keys()) if is_json else next(csv.reader(io.StringIO(it['text'], newline='')))
    payload = {'text': it['text'], 'format': 'json' if is_json else 'csv', 'columns': cols, 'delimiter': None if is_json else ','}
    exp = oracle.expected('table_normalize', payload)
    if exp['status'] != 'ok':
        return None, 'error', 'oracle rejects the file; no tool-correct answer exists'
    return jobs.extract({'extract': it['extract']}, exp), 'ok', 'oracle value'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args(argv).out
    items_dir, ref_dir = out / 'items', out / 'referee'
    items_dir.mkdir(parents=True, exist_ok=True)
    ref_dir.mkdir(parents=True, exist_ok=True)
    equiv = {}
    for it in ITEMS:
        pub = items_dir / it['id'] / 'public'
        pub.mkdir(parents=True, exist_ok=True)
        tool_file = 'calc_tool.py' if it['tool'] == 'calculate' else 'table_tool.py'
        (pub / tool_file).write_bytes(public_module(it['cand'], it['tool']).encode('utf-8'))
        (pub / it['fname']).write_bytes(it['text'].encode('utf-8'))
        (pub / 'task.txt').write_bytes((prefix(it['tool']) + it['phrase'] + '\n').encode('utf-8'))
        if it['tool'] == 'calculate':
            argv = [it['fname'], it['col'], it['op']] + (['--where', it['where']] if it['where'] else [])
            job = {'kind': 'calc', 'tool': it['tool'], 'tool_file': tool_file, 'argv': argv}
        else:
            job = {'kind': 'table', 'tool': it['tool'], 'tool_file': tool_file, 'argv': [it['fname']], 'extract': it['extract']}
        (items_dir / it['id'] / 'job.json').write_bytes((json.dumps(job, indent=1) + '\n').encode('utf-8'))
        # Equivalence of effect: public module vs admission candidate on every derived test and the witness.
        cand = importlib.import_module('candidates.' + it['cand']).run
        mod = load_module(pub / tool_file, 'pub_' + it['id'])
        tests = derive_tests(DECL[it['tool']])
        gt = GT[it['cand']]
        extra = [{'input': gt['witness']}] if gt['witness'] else []
        diffs = sum(json.dumps(cand(copy.deepcopy(t['input'])), sort_keys=True) != json.dumps(mod.run(copy.deepcopy(t['input'])), sort_keys=True) for t in tests + extra)
        equiv[it['id']] = {'tests_compared': len(tests) + len(extra), 'differences': diffs}
        assert diffs == 0, it['id']
        answer, ostatus, note = gold_for(it)
        got = jobs.tool_answer(pub, job)
        defective = gt['defective']
        kind = 'number' if it['tool'] == 'calculate' else it['kind']
        same = got is not None and answer is not None and (Fraction(got) == Fraction(answer) if kind == 'number' else got == answer)
        if defective:
            if answer is None:
                assert got is not None, 'padded output expected: ' + it['id']
            else:
                assert not same, 'defect does not change answer: ' + it['id']
        else:
            assert same, ('control mismatch', it['id'], got, answer)
        ref = {
            'id': it['id'], 'candidate': it['cand'], 'tool': it['tool'], 'defective': defective, 'defect': gt['defect'],
            'witness': gt['witness'], 'answer': answer, 'answer_kind': kind if answer is not None else None,
            'oracle_status': ostatus, 'tool_answer_on_this_data': got, 'expect_no_answer': answer is None, 'note': note,
        }
        (ref_dir / (it['id'] + '.json')).write_bytes((json.dumps(ref, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    (out / 'equivalence.json').write_bytes((json.dumps(equiv, indent=1) + '\n').encode('utf-8'))
    print(json.dumps(equiv, indent=1))


if __name__ == '__main__':
    main()
