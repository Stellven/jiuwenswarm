"""Independent original-file projection checks; never trust producer row counts."""
import csv
import io
import json

from ...contracts import ResearchError
from ..packet import validate_packet


def check(ctx, inputs, outputs):
    schema = integrity = False
    try:
        source, result = inputs['packet'], outputs['result']
        validate_packet(source)
        validate_packet(result)
        schema = True
        request = source['data']['table_request']
        if set(request) != {'file', 'format', 'columns', 'delimiter'}: raise ValueError('request')
        columns = request['columns']
        if type(columns) is not list or not 0 < len(columns) <= 128 or any(type(c) is not str or not c or len(c) > 200 for c in columns): raise ValueError('columns')
        text = [f['text'] for f in source['files'] if f['path'] == request['file']]
        if len(text) != 1 or len(set(columns)) != len(columns):
            raise ValueError('source selection')
        if request['format'] == 'csv':
            if type(request['delimiter']) is not str or len(request['delimiter']) != 1 or request['delimiter'] in '\r\n\x00\"': raise ValueError('delimiter')
            rows = list(csv.reader(io.StringIO(text[0], newline=''), delimiter=request['delimiter'], strict=True))
            if rows[0] != columns: raise ValueError('header')
            rows = rows[1:]
        elif request['format'] == 'json' and request['delimiter'] is None:
            def unique(pairs):
                if len({k for k, _ in pairs}) != len(pairs): raise ValueError('duplicate keys')
                return dict(pairs)
            records = json.loads(text[0], object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
            if type(records) is not list or any(type(r) is not dict for r in records): raise ValueError('records')
            if any(set(row) != set(columns) for row in records): raise ValueError('keys')
            rows = [[row[column] for column in columns] for row in records]
        else:
            raise ValueError('format')
        if len(rows) > 10000 or any(len(row) != len(columns) for row in rows): raise ValueError('rows')
        if any(type(v) not in (str, int, float, bool, type(None)) for row in rows for v in row): raise ValueError('scalar values')
        expected = dict(source, data=dict(source['data'], table={'columns': columns, 'rows': rows}))
        integrity = result == expected
    except (ResearchError, KeyError, TypeError, ValueError, IndexError, csv.Error):
        pass
    return [{'check_id': key, 'outcome': 'PASS' if ok else 'FAIL', 'reason': reason, 'evidence_refs': list(ctx.output_refs.values())}
        for key, ok, reason in [('packet_schema', schema, 'Bounded work packet and exact file digests'),
            ('packet_integrity', integrity, 'Every original source value and ordered column/row is preserved exactly')]]
