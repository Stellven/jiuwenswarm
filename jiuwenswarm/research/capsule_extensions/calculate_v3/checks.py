"""Recompute selected statistics directly from original table values."""
import re
from decimal import Decimal, DecimalException, Inexact, localcontext, ROUND_HALF_EVEN

from ...contracts import ResearchError
from ..packet import validate_packet

PRECISION = 128


def check(ctx, inputs, outputs):
    schema = integrity = False
    try:
        source, result = inputs['packet'], outputs['result']
        validate_packet(source)
        validate_packet(result)
        schema = True
        request, table = source['data']['calculation'], source['data']['table']
        if set(request) != {'columns', 'operations', 'numeric_mode'} or set(table) != {'columns', 'rows'}: raise ValueError('shape')
        names, rows = table['columns'], table['rows']
        selected, ops = request['columns'], request['operations']
        if (type(names) is not list or not 0 < len(names) <= 128 or any(type(n) is not str for n in names) or len(set(names)) != len(names)
                or type(rows) is not list or len(rows) > 10000 or any(type(row) is not list or len(row) != len(names) for row in rows)
                or type(selected) is not list or not selected or len(set(selected)) != len(selected) or not set(selected) <= set(names)
                or type(ops) is not list or not ops or len(set(ops)) != len(ops) or not set(ops) <= {'count', 'sum', 'mean', 'min', 'max'}):
            raise ValueError('selection')
        mode = request['numeric_mode']
        metrics = {}
        with localcontext() as precision:
            precision.prec, precision.rounding = PRECISION, ROUND_HALF_EVEN
            for name in selected:
                values = []
                for row in rows:
                    raw = row[names.index(name)]
                    if mode == 'json_numbers':
                        if type(raw) not in (int, float): raise ValueError('json number')
                    elif mode == 'decimal_strings':
                        if type(raw) is not str or len(raw) > 160 or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', raw): raise ValueError('decimal string')
                    else: raise ValueError('mode')
                    value = Decimal(str(raw))
                    if (not value.is_finite() or len(value.as_tuple().digits) > PRECISION
                            or abs(value.adjusted()) > PRECISION): raise ValueError('numeric bounds')
                    values.append(value)
                if not values and any(op in {'mean', 'min', 'max'} for op in ops): raise ValueError('empty statistic')
                all_metrics = {'count': len(values)}
                # Equal values with different spellings (-0.00, 0.00) report the first one in row order.
                if values: all_metrics.update(min=str(min(values)), max=str(max(values)))
                if 'sum' in ops or 'mean' in ops:
                    precision.clear_flags()
                    total = Decimal(0)
                    for number in values: total += number
                    if precision.flags[Inexact]: raise ValueError('inexact sum')
                    all_metrics['sum'] = str(total)
                    if values: all_metrics['mean'] = str(total / len(values))
                metrics[name] = {op: all_metrics[op] for op in ops}
        expected = dict(source, data=dict(source['data'], calculation_result={'arithmetic': 'decimal128_half_even', 'columns': metrics}))
        integrity = result == expected
    except (ResearchError, KeyError, ValueError, TypeError, DecimalException):
        pass
    return [{'check_id': key, 'outcome': 'PASS' if ok else 'FAIL', 'reason': reason, 'evidence_refs': list(ctx.output_refs.values())}
        for key, ok, reason in [('result_schema', schema, 'Bounded exact packet envelope'),
            ('result_integrity', integrity, 'Explicit selected statistics independently recomputed from original values')]]
