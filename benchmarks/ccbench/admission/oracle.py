"""Independent observable semantics: Fraction arithmetic and integer rounding.

No candidate/reference or declaration-generator imports. CSV decoding uses the
stdlib parser (shared trusted primitive); JSON uses object-pair lists rather
than the candidate's object hook. Type-tagged comparison avoids True == 1.
"""
import csv
import io
import json
import math
import re
from fractions import Fraction


def rounded_decimal(q, precision=128):
    if not q: return '0'
    sign = '-' if q < 0 else ''
    q = abs(q)
    exponent = len(str(q.numerator)) - len(str(q.denominator))
    if q < Fraction(10) ** exponent: exponent -= 1
    scale = precision - 1 - exponent
    scaled = q * Fraction(10) ** scale
    n, remainder = divmod(scaled.numerator, scaled.denominator)
    if 2 * remainder > scaled.denominator or 2 * remainder == scaled.denominator and n % 2:
        n += 1
    return sign + str(n) + 'e' + str(-scale)


def aggregate(p):
    raw, mode, op = p['values'], p['mode'], p['operation']
    if type(raw) is not list or len(raw) > 10000 or mode not in ['json_numbers', 'decimal_strings'] or op not in ['count', 'sum', 'mean', 'min', 'max']: raise ValueError()
    values = []
    for value in raw:
        if mode == 'json_numbers' and type(value) not in [int, float]: raise ValueError()
        if mode == 'decimal_strings' and (type(value) is not str or len(value) > 100): raise ValueError()
        s = str(value)
        if not re.fullmatch(r'[+-]?[0123456789]+(?:\.[0123456789]+)?(?:[eE][+-]?[0123456789]+)?', s): raise ValueError()
        mantissa, *exp = re.split('[eE]', s)
        digits = mantissa.lstrip('+-').replace('.', '').lstrip('0') or '0'
        exponent = (int(exp[0]) if exp else 0) - (len(mantissa.split('.')[1]) if '.' in mantissa else 0)
        adjusted = exponent + len(digits) - 1
        if len(digits) > 28 or abs(adjusted) > 28: raise ValueError()
        values.append(Fraction(s))
    if not values and op in ['mean', 'min', 'max']: raise ValueError()
    if op == 'count': return {'status': 'ok', 'value': len(values)}
    total = sum(values, Fraction())
    if op == 'sum': result = total
    elif op == 'mean': result = total / len(values)
    elif op == 'min': result = min(values)
    else: result = max(values)
    return {'status': 'ok', 'value': rounded_decimal(result)}


def table(p):
    columns = p['columns']
    if type(columns) is not list or not 1 <= len(columns) <= 128 or any(type(x) is not str or not 1 <= len(x) <= 200 for x in columns) or len(set(columns)) != len(columns): raise ValueError()
    if p['format'] == 'csv':
        delimiter = p['delimiter']
        if type(delimiter) is not str or len(delimiter) != 1 or delimiter in '\n\r\0"': raise ValueError()
        reader = csv.reader(io.StringIO(p['text'], newline=''), delimiter=delimiter, strict=True)
        if next(reader, None) != columns: raise ValueError()
        rows = list(reader)
    elif p['format'] == 'json' and p['delimiter'] is None:
        class Pairs(list): pass
        records = json.loads(p['text'], object_pairs_hook=Pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(records) is not list: raise ValueError()
        rows = []
        for record in records:
            if type(record) is not Pairs or len(record) != len(columns) or {k for k, _ in record} != set(columns): raise ValueError()
            rows.append([next(v for k, v in record if k == col) for col in columns])
    else: raise ValueError()
    if len(rows) > 10000 or any(len(r) != len(columns) for r in rows): raise ValueError()
    for row in rows:
        for v in row:
            if type(v) not in [str, int, float, bool, type(None)] or type(v) is float and not math.isfinite(v): raise ValueError()
    return {'status': 'ok', 'columns': columns, 'rows': rows}


def expected(tool, p):
    try: return aggregate(p) if tool == 'calculate' else table(p)
    except (ValueError, TypeError, KeyError, csv.Error, ArithmeticError): return {'status': 'error'}


def tagged(v):
    if isinstance(v, dict): return ('dict', sorted((k, tagged(x)) for k, x in v.items()))
    if isinstance(v, list): return ('list', [tagged(x) for x in v])
    return (type(v).__name__, v)


def matches(tool, p, actual):
    want = expected(tool, p)
    if tool == 'calculate' and want['status'] == 'ok' and p['operation'] != 'count':
        if type(actual) is not dict or set(actual) != {'status', 'value'} or actual['status'] != 'ok' or type(actual['value']) is not str: return False
        try: return Fraction(want['value']) == Fraction(actual['value'])
        except (ValueError, ZeroDivisionError): return False
    return tagged(want) == tagged(actual)
