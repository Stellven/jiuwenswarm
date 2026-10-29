"""Seeded study candidate; deterministic, no I/O."""
import copy
import csv
import io
import unicodedata
from decimal import Decimal
from reference import calculate, table_normalize

def run(payload):
    p = copy.deepcopy(payload)
    if p['format'] == 'csv':
        rows = list(csv.reader(io.StringIO(p['text']), delimiter=p['delimiter']))
        rows = [rows[0]] + [r + [''] * max(0, len(p['columns'])-len(r)) for r in rows[1:]] if rows else []
        s = io.StringIO(); csv.writer(s, delimiter=p['delimiter']).writerows(rows); p['text'] = s.getvalue()
    return table_normalize(p)
