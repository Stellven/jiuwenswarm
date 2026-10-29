"""Independent referee arithmetic. Uses only the standard library; never imports product bodies.

Used by generate_tasks.py to compute gold numbers from the raw supplied text, so the gold
does not depend on the capability bodies being scored.
"""
import csv
import io
import json
from decimal import Decimal, localcontext, ROUND_HALF_EVEN


def rows_from_csv(text, delimiter=','):
    rows = list(csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True))
    return rows[0], rows[1:]


def rows_from_json(text, columns):
    return [[r[c] for c in columns] for r in json.loads(text)]


def stats(values, operations):
    """values: list of str|int|float. Returns {op: value} in the exact output types of the contract
    (count is an int; sum/mean/min/max are decimal strings)."""
    with localcontext() as ctx:
        ctx.prec, ctx.rounding = 128, ROUND_HALF_EVEN
        nums = [Decimal(str(v)) for v in values]
        total = sum(nums, Decimal(0))
        out = {}
        for op in operations:
            if op == 'count':
                out[op] = len(nums)
            elif op == 'sum':
                out[op] = str(total)
            elif op == 'mean':
                out[op] = str(total / len(nums))
            elif op == 'min':
                out[op] = str(min(nums))
            elif op == 'max':
                out[op] = str(max(nums))
            else:
                raise ValueError(op)
        return out
