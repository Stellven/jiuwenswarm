"""Seeded study candidate; deterministic, no I/O."""
import copy
import csv
import io
import unicodedata
from decimal import Decimal
from reference import calculate, table_normalize

def run(payload):
    p = copy.deepcopy(payload)
    if p['mode'] == 'json_numbers': p['values'] = [int(v) if type(v) is bool else v for v in p['values']]
    return calculate(p)
