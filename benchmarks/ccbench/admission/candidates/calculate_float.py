"""Seeded study candidate; deterministic, no I/O."""
import copy
import csv
import io
import unicodedata
from decimal import Decimal
from reference import calculate, table_normalize

def run(payload):
    p = copy.deepcopy(payload)
    r = calculate(p)
    if r['status'] == 'ok' and p['operation'] != 'count': r['value'] = str(float(r['value']))
    return r
