import csv
import io
import json
import math

from ...contracts import ResearchError
from ..packet import output_packet, produced, validate_packet


def normalize(packet):
    validate_packet(packet)
    try:
        request = packet['data']['table_request']
        if set(request) != {'file', 'format', 'columns', 'delimiter'}:
            raise ValueError('explicit file, format, columns and delimiter required')
        columns = request['columns']
        if (type(columns) is not list or not 0 < len(columns) <= 128
                or any(type(x) is not str or not x or len(x) > 200 for x in columns) or len(set(columns)) != len(columns)):
            raise ValueError('unique bounded columns required')
        text = next(f['text'] for f in packet['files'] if f['path'] == request['file'])
        if request['format'] == 'csv':
            delimiter = request['delimiter']
            if type(delimiter) is not str or len(delimiter) != 1 or delimiter in '\r\n\x00"':
                raise ValueError('explicit one-character CSV delimiter required')
            rows = list(csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True))
            if not rows or rows.pop(0) != columns:
                raise ValueError('CSV header must exactly match columns')
        elif request['format'] == 'json' and request['delimiter'] is None:
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result: raise ValueError('duplicate JSON key')
                    result[key] = value
                return result
            records = json.loads(text, object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
            if type(records) is not list or any(type(r) is not dict or set(r) != set(columns) for r in records):
                raise ValueError('JSON must be records with exactly the selected columns')
            rows = [[record[key] for key in columns] for record in records]
        else:
            raise ValueError('format must be csv or json; JSON delimiter must be null')
        if len(rows) > 10000 or any(len(row) != len(columns) for row in rows):
            raise ValueError('bounded rectangular table required')
        if any(type(value) not in (str, int, float, bool, type(None)) or (type(value) is float and not math.isfinite(value)) for row in rows for value in row):
            raise ValueError('only finite scalar values are supported')
        return {'columns': columns, 'rows': rows}
    except (KeyError, ValueError, TypeError, StopIteration, csv.Error, RecursionError) as error:
        raise ResearchError('table_input', str(error)[:200]) from error


async def execute(ctx, inputs):
    packet = inputs['packet']
    data = dict(packet['data'], table=normalize(packet))
    return {'result': produced(output_packet(packet, data=data))}
