"""Seeded study candidate; deterministic, no I/O."""
import copy
import csv
import io
import unicodedata
from decimal import Decimal
from reference import calculate, table_normalize

def run(payload):
    p = copy.deepcopy(payload)
    p['values'] = [abs(v) if type(v) in (int, float) else v.lstrip('-') if type(v) is str else v for v in p['values']]
    return calculate(p)
