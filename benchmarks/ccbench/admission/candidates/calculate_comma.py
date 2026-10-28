"""Seeded study candidate; deterministic, no I/O."""
import copy
import csv
import io
import unicodedata
from decimal import Decimal
from reference import calculate, table_normalize

def run(payload):
    p = copy.deepcopy(payload)
    if p['mode'] == 'decimal_strings': p['values'] = [v.replace(',', '.') if type(v) is str else v for v in p['values']]
    return calculate(p)
