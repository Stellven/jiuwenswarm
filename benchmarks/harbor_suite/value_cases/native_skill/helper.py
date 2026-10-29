"""Ordinary standalone Python assistance; no package/product/oracle imports."""
import csv
import hashlib
import html
import io
import json
import re
import sys
from decimal import Decimal, localcontext, ROUND_HALF_EVEN


def escaped(value):
    value = html.escape(value, quote=False)
    return ''.join('\\' + c if c in '\\`*_{}[]()#+-.!|>' else c for c in value)


def solve(task):
    family = task['id'].split('/')[0]
    if family not in ('utility.table_normalize', 'utility.calculate', 'utility.markdown_report', 'utility.packet_report'):
        raise NotImplementedError('This helper does not execute research or protected workflows')
    p = task['inputs']; data = p['data']
    try:
        names = set()
        for f in p['files']:
            if f['path'] in names or hashlib.sha256(f['text'].encode()).hexdigest() != f['sha256']:
                raise ValueError('Invalid source identity')
            names.add(f['path'])
        if family == 'utility.table_normalize':
            r = data['table_request']; columns = r['columns']
            if not columns or len(columns) != len(set(columns)):
                raise ValueError('Invalid columns')
            text = next(f['text'] for f in p['files'] if f['path'] == r['file'])
            if r['format'] == 'csv':
                records = list(csv.reader(io.StringIO(text, newline=''), delimiter=r['delimiter'], strict=True))
                if records.pop(0) != columns:
                    raise ValueError('Header mismatch')
                rows = records
            elif r['format'] == 'json' and r['delimiter'] is None:
                def unique(pairs):
                    obj = {}
                    for key, value in pairs:
                        if key in obj:
                            raise ValueError('Duplicate key')
                        obj[key] = value
                    return obj
                records = json.loads(text, object_pairs_hook=unique)
                if type(records) is not list or any(type(x) is not dict or set(x) != set(columns) for x in records):
                    raise ValueError('Record mismatch')
                rows = [[x[c] for c in columns] for x in records]
            else:
                raise ValueError('Unsupported format')
            if any(len(row) != len(columns) or any(type(v) not in (str, bool, int, float, type(None)) for v in row) for row in rows):
                raise ValueError('Nonrectangular or nonscalar table')
            content = {'table': {'columns': columns, 'rows': rows}}
        elif family == 'utility.calculate':
            request = data['calculation']; table = data['table']; answer = {}
            with localcontext() as context:
                context.prec = 128; context.rounding = ROUND_HALF_EVEN
                for col in request['columns']:
                    raw = [row[table['columns'].index(col)] for row in table['rows']]
                    if request['numeric_mode'] == 'json_numbers':
                        if any(type(v) not in (int, float) for v in raw):
                            raise ValueError('No boolean coercion')
                    elif request['numeric_mode'] == 'decimal_strings':
                        if any(type(v) is not str or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', v) for v in raw):
                            raise ValueError('Invalid decimal')
                    else:
                        raise ValueError('Unknown numeric mode')
                    values = [Decimal(str(v)) for v in raw]
                    if any(not v.is_finite() for v in values):
                        raise ValueError('Nonfinite value')
                    metrics = {}
                    for op in request['operations']:
                        if op == 'count': metrics[op] = len(values)
                        elif op == 'sum': metrics[op] = str(sum(values, Decimal(0)))
                        elif op == 'mean': metrics[op] = str(sum(values, Decimal(0)) / len(values))
                        elif op == 'min': metrics[op] = str(min(values))
                        elif op == 'max': metrics[op] = str(max(values))
                        else: raise ValueError('Unknown operation')
                    answer[col] = metrics
            content = {'calculation_result': {'arithmetic': 'decimal128_half_even', 'columns': answer}}
        else:
            request = data['report']
            if request['path'] in names or any(c in request['title'] for c in '\r\n'):
                raise ValueError('Collision or invalid title')
            pieces = ['# ' + escaped(request['title']), 'Trust: ' + p['trust']]
            for section in request['sections']:
                pieces.append('## ' + escaped(section['heading']) + '\n\n' + escaped(section['text']))
            for key in request['data_keys']:
                pieces.append('## ' + escaped(key) + '\n\n```json\n' + json.dumps(data[key], sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n```')
            if p['limitations']:
                pieces.append('## Limitations\n\n' + '\n'.join('- ' + escaped(x) for x in p['limitations']))
            content = {'report_text': '\n\n'.join(pieces) + '\n',
                       'selected_data': {k: data[k] for k in request['data_keys']}}
        return {'status': 'complete', 'content': content}
    except (ValueError, KeyError, TypeError, StopIteration, IndexError, ArithmeticError, csv.Error):
        return {'status': 'halt', 'content': {}}


if __name__ == '__main__':
    print(json.dumps(solve(json.load(sys.stdin)), ensure_ascii=False, allow_nan=False))
