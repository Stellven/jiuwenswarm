"""Seeded study candidate; deterministic, no I/O."""
import copy
import csv
import io
import unicodedata
from decimal import Decimal
from reference import calculate, table_normalize

def run(payload):
    p = copy.deepcopy(payload)
    r = table_normalize(p)
    if r['status'] == 'ok': r['rows'] = [[v.strip() if type(v) is str else v for v in row] for row in r['rows']]
    return r
