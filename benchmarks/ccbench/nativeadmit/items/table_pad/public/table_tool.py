import copy
import csv
import io
import json
import math
import re
import sys
from decimal import Decimal, localcontext, ROUND_HALF_EVEN


def table_normalize(p):
    try:
        cols = p['columns']
        if type(cols) is not list or not 0 < len(cols) <= 128 or any(type(c) is not str or not 0 < len(c) <= 200 for c in cols) or len(set(cols)) != len(cols):
            raise ValueError()
        if p['format'] == 'csv':
            d = p['delimiter']
            if type(d) is not str or len(d) != 1 or d in '\r\n\x00"':
                raise ValueError()
            rows = list(csv.reader(io.StringIO(p['text'], newline=''), delimiter=d, strict=True))
            if not rows or rows.pop(0) != cols:
                raise ValueError()
        elif p['format'] == 'json' and p['delimiter'] is None:
            def unique(pairs):
                result = {}
                for k, v in pairs:
                    if k in result: raise ValueError()
                    result[k] = v
                return result
            records = json.loads(p['text'], object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if type(records) is not list or any(type(r) is not dict or set(r) != set(cols) for r in records):
                raise ValueError()
            rows = [[r[c] for c in cols] for r in records]
        else: raise ValueError()
        if len(rows) > 10000 or any(len(r) != len(cols) for r in rows): raise ValueError()
        if any(type(v) not in (str, int, float, bool, type(None)) or type(v) is float and not math.isfinite(v) for r in rows for v in r): raise ValueError()
        return {'status': 'ok', 'columns': cols[:], 'rows': rows}
    except (ValueError, KeyError, TypeError, csv.Error):
        return {'status': 'error'}


def run(payload):
    p = copy.deepcopy(payload)
    if p['format'] == 'csv':
        rows = list(csv.reader(io.StringIO(p['text']), delimiter=p['delimiter']))
        rows = [rows[0]] + [r + [''] * max(0, len(p['columns'])-len(r)) for r in rows[1:]] if rows else []
        s = io.StringIO(); csv.writer(s, delimiter=p['delimiter']).writerows(rows); p['text'] = s.getvalue()
    return table_normalize(p)


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
