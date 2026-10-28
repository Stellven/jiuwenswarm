"""Candidate-side implementations. No imports from the generator or oracle."""
import csv
import io
import json
import math
import re
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
