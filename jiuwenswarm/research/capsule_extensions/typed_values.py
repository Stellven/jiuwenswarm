"""Independent JSON type fidelity layered on existing exact-value checks."""
import csv
import io
import json


def exact(left, right):
    return json.dumps(left, sort_keys=True, ensure_ascii=False, allow_nan=False) == json.dumps(
        right, sort_keys=True, ensure_ascii=False, allow_nan=False)


def fidelity(source, result, operation):
    try:
        owned = {'table_normalize': 'table', 'calculate': 'calculation_result',
                 'markdown_report': 'report_manifest'}[operation]
        # Python equality considers True == 1 and 1 == 1.0. Preserve inherited
        # JSON types as well as values without executing producer code.
        if any(not exact(value, result['data'][key]) for key, value in source['data'].items() if key != owned):
            return False
        for key in ('trust', 'provenance', 'limitations'):
            if not exact(source[key], result[key]):
                return False
        if not exact(source['files'], result['files'][:len(source['files'])]):
            return False
        if operation == 'table_normalize':
            request = source['data']['table_request']
            text = next(f['text'] for f in source['files'] if f['path'] == request['file'])
            columns = request['columns']
            if request['format'] == 'csv':
                rows = list(csv.reader(io.StringIO(text, newline=''), delimiter=request['delimiter'], strict=True))[1:]
            else:
                rows = [[r[column] for column in columns] for r in json.loads(text)]
            return exact({'columns': columns, 'rows': rows}, result['data']['table'])
        if operation == 'calculate':
            metrics = result['data']['calculation_result']['columns']
            return all(type(value) is (int if key == 'count' else str)
                       for values in metrics.values() for key, value in values.items())
        return True
    except (KeyError, ValueError, TypeError, IndexError, StopIteration, csv.Error):
        return False


def checked(legacy, ctx, inputs, outputs, operation):
    rows = legacy(ctx, inputs, outputs)
    valid = fidelity(inputs.get('packet', {}), outputs.get('result', {}), operation)
    rename = {'packet_schema': 'result_schema', 'packet_integrity': 'result_integrity'}
    result = []
    for row in rows:
        row = dict(row, check_id=rename[row['check_id']])
        if row['check_id'] == 'result_integrity':
            row['outcome'] = 'PASS' if valid and row['outcome'] == 'PASS' else 'FAIL'
            row['reason'] += '; independently preserve JSON types and original input fields'
        result.append(row)
    return result

