import copy
import csv
import io
import json
import math
import re
import sys
from decimal import Decimal, localcontext, ROUND_HALF_EVEN


def calculate(p):
    try:
        values, mode, op = p['values'], p['mode'], p['operation']
        if type(values) is not list or len(values) > 10000 or op not in ('count', 'sum', 'mean', 'min', 'max'):
            raise ValueError()
        if mode not in ('json_numbers', 'decimal_strings'):
            raise ValueError()
        parsed = []
        for v in values:
            if mode == 'json_numbers' and type(v) not in (int, float):
                raise ValueError()
            if mode == 'decimal_strings' and (type(v) is not str or len(v) > 100 or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', v)):
                raise ValueError()
            d = Decimal(str(v))
            if not d.is_finite() or len(d.as_tuple().digits) > 28 or abs(d.adjusted()) > 28:
                raise ValueError()
            parsed.append(d)
        if not parsed and op not in ('count', 'sum'):
            raise ValueError()
        with localcontext() as ctx:
            ctx.prec, ctx.rounding = 128, ROUND_HALF_EVEN
            if op == 'count': answer = len(parsed)
            elif op == 'sum': answer = str(sum(parsed, Decimal(0)))
            elif op == 'mean': answer = str(sum(parsed, Decimal(0)) / len(parsed))
            elif op == 'min': answer = str(min(parsed))
            else: answer = str(max(parsed))
        return {'status': 'ok', 'value': answer}
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return {'status': 'error'}


def run(payload):
    p = copy.deepcopy(payload)
    if p['mode'] == 'decimal_strings': p['values'] = [v.replace(',', '.') if type(v) is str else v for v in p['values']]
    return calculate(p)


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
