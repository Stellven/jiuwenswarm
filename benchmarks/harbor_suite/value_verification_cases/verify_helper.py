"""Ordinary standalone reconstruction helper; no product or answer imports."""
import copy
import csv
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def escape(text):
    return ''.join('\\' + char if char in '\\`*_{}[]()#+-.!|>' else char for char in html.escape(text, quote=False))


def validate_packet(packet):
    if set(packet) != {'schema_version', 'data', 'files', 'trust', 'provenance', 'limitations'} or packet['schema_version'] != '1.0.0':
        raise ValueError('Packet shape differs')
    names = set()
    for item in packet['files']:
        name = item['path']
        if name in names or any(part in ('', '.', '..') for part in name.split('/')) or '\\' in name or ':' in name:
            raise ValueError('Invalid file path')
        names.add(name)
        if hashlib.sha256(item['text'].encode()).hexdigest() != item['sha256']:
            raise ValueError('File digest differs')


def expected(task):
    source = task['original_packet']; validate_packet(source)
    result = copy.deepcopy(source); values = result['data']; operation = task['operation']
    if operation == 'table_normalize':
        request = values['table_request']; columns = request['columns']
        raw = next(item['text'] for item in source['files'] if item['path'] == request['file'])
        if request['format'] == 'csv':
            rows = list(csv.reader(io.StringIO(raw, newline=''), delimiter=request['delimiter'], strict=True))
            if rows.pop(0) != columns: raise ValueError('Header differs')
        else:
            records = json.loads(raw)
            if any(set(row) != set(columns) for row in records): raise ValueError('Columns differ')
            rows = [[row[column] for column in columns] for row in records]
        if any(len(row) != len(columns) for row in rows): raise ValueError('Ragged table')
        values['table'] = {'columns': columns, 'rows': rows}
    elif operation == 'calculate':
        request = values['calculation']; table = values['table']; metrics = {}
        with localcontext() as context:
            context.prec = 128; context.rounding = ROUND_HALF_EVEN
            for column in request['columns']:
                raw = [row[table['columns'].index(column)] for row in table['rows']]
                if request['numeric_mode'] == 'json_numbers':
                    if any(type(value) not in (int, float) for value in raw): raise ValueError('Not numeric')
                elif request['numeric_mode'] == 'decimal_strings':
                    if any(type(value) is not str or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', value) for value in raw): raise ValueError('Not decimal strings')
                else: raise ValueError('Unknown numeric mode')
                numbers = [Decimal(str(value)) for value in raw]
                total = sum(numbers, Decimal(0)); statistics = {'count': len(numbers), 'sum': str(total)}
                if numbers: statistics.update(mean=str(total / len(numbers)), min=str(min(numbers)), max=str(max(numbers)))
                metrics[column] = {name: statistics[name] for name in request['operations']}
        values['calculation_result'] = {'arithmetic': 'decimal128_half_even', 'columns': metrics}
    elif operation == 'markdown_report':
        request = values['report']; parts = ['# ' + escape(request['title']), 'Trust: ' + source['trust']]
        for section in request['sections']:
            parts.append('## ' + escape(section['heading']) + '\n\n' + escape(section['text']))
        for key in request['data_keys']:
            parts.append('## ' + escape(key) + '\n\n```json\n' + json.dumps(values[key], sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n```')
        if source['limitations']:
            parts.append('## Limitations\n\n' + '\n'.join('- ' + escape(value) for value in source['limitations']))
        text = '\n\n'.join(parts) + '\n'; digest = hashlib.sha256(text.encode()).hexdigest()
        if request['path'] in {item['path'] for item in source['files']}: raise ValueError('File collision')
        values['report_manifest'] = {'path': request['path'], 'sha256': digest, 'size_bytes': len(text.encode()),
            'data_keys': request['data_keys'], 'input_files': [{'path': item['path'], 'sha256': item['sha256']} for item in source['files']],
            'trust': source['trust'], 'provenance': source['provenance']}
        result['files'].append({'path': request['path'], 'text': text, 'sha256': digest})
    else:
        raise ValueError('Unsupported operation')
    return result


def difference(wanted, actual, path='$'):
    if type(wanted) is not type(actual): return path + ': expected ' + type(wanted).__name__ + ', got ' + type(actual).__name__
    if type(wanted) is dict:
        if wanted.keys() != actual.keys(): return path + ': object keys differ'
        for key in wanted:
            found = difference(wanted[key], actual[key], path + '.' + key)
            if found: return found
    elif type(wanted) is list:
        if len(wanted) != len(actual): return path + ': sequence length differs'
        for index, (left, right) in enumerate(zip(wanted, actual)):
            found = difference(left, right, path + '[' + str(index) + ']')
            if found: return found
    elif wanted != actual:
        return path + ': value differs from independently reconstructed original transformation'
    return None


def verify(task):
    try:
        proposed = task['proposed_packet']; validate_packet(proposed)
        wanted = expected(task)
        mismatch = difference(wanted, proposed)
        return {'id': task['id'], 'verdict': 'unsafe' if mismatch else 'safe',
                'reason': mismatch or 'All fields, scalar types, files, hashes and requested transformation match independent reconstruction.'}
    except (KeyError, TypeError, ValueError, ArithmeticError, StopIteration, csv.Error) as error:
        return {'id': task['id'], 'verdict': 'unsafe', 'reason': 'Validation/reconstruction refused: ' + str(error)}


if __name__ == '__main__':
    batch = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    print(json.dumps({'results': [verify(task) for task in batch['cases']]}, ensure_ascii=False, indent=2))
