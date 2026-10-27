import re
from decimal import Decimal, DecimalException, Inexact, localcontext, ROUND_HALF_EVEN

from ...contracts import ResearchError
from ..packet import output_packet, produced, validate_packet

# Arithmetic precision and the input bounds share one number. A value of at
# most PRECISION digits and adjusted exponent magnitude of at most PRECISION is
# accepted; a sum that would need more than PRECISION digits is refused rather
# than rounded (see the Inexact guard below).
PRECISION = 128
MAX_TEXT = 160
NUMBER = re.compile(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
OPS = {'count', 'sum', 'mean', 'min', 'max'}


def _shape(packet):
    data = packet['data']
    if type(data) is not dict:
        raise ValueError('packet.data must be an object holding table and calculation')
    missing = [key for key in ('table', 'calculation') if key not in data]
    if missing:
        nested = ' Found a nested "data" key: remove the extra data wrapper.' if type(data.get('data')) is dict else ''
        raise ValueError('packet.data lacks ' + ' and '.join(missing) + '; keys present: ' + repr(sorted(data)) + '.' + nested)
    table, request = data['table'], data['calculation']
    if type(table) is not dict or set(table) != {'columns', 'rows'}:
        raise ValueError('table must be an object with exactly columns and rows')
    if type(request) is not dict or set(request) != {'columns', 'operations', 'numeric_mode'}:
        raise ValueError('calculation must be an object with exactly columns, operations and numeric_mode')
    return table, request


def calculate(packet):
    validate_packet(packet)
    try:
        table, request = _shape(packet)
        columns, rows = table['columns'], table['rows']
        selected, operations = request['columns'], request['operations']
        if (type(columns) is not list or not 0 < len(columns) <= 128 or any(type(x) is not str for x in columns)
                or len(set(columns)) != len(columns) or type(rows) is not list or len(rows) > 10000
                or any(type(row) is not list or len(row) != len(columns) for row in rows)):
            raise ValueError('bounded rectangular table required')
        if (type(selected) is not list or not selected or len(set(selected)) != len(selected) or not set(selected) <= set(columns)
                or type(operations) is not list or not operations or len(set(operations)) != len(operations) or not set(operations) <= OPS):
            raise ValueError('unique known columns and operations required')
        mode = request['numeric_mode']
        if mode not in {'json_numbers', 'decimal_strings'}:
            raise ValueError('explicit numeric_mode required')
        result = {}
        with localcontext() as context:
            context.prec, context.rounding = PRECISION, ROUND_HALF_EVEN
            for column in selected:
                values = []
                for row in rows:
                    value = row[columns.index(column)]
                    if ((mode == 'json_numbers' and type(value) not in (int, float))
                            or (mode == 'decimal_strings' and (type(value) is not str or len(value) > MAX_TEXT or not NUMBER.fullmatch(value)))):
                        raise ValueError('invalid numeric value; no implicit conversion or missing values')
                    number = Decimal(str(value))
                    if (not number.is_finite() or len(number.as_tuple().digits) > PRECISION
                            or abs(number.adjusted()) > PRECISION):
                        raise ValueError('finite bounded decimal value required (at most 128 digits, exponent magnitude 128)')
                    values.append(number)
                if not values and set(operations) & {'mean', 'min', 'max'}:
                    raise ValueError('empty column has no requested mean/min/max')
                total = None
                if set(operations) & {'sum', 'mean'}:
                    context.clear_flags()
                    total = sum(values, Decimal(0))
                    if context.flags[Inexact]:
                        raise ValueError('sum needs more than 128 significant digits; refusing to round it')
                metrics = {}
                for operation in operations:
                    if operation == 'count': metrics[operation] = len(values)
                    elif operation == 'sum': metrics[operation] = str(total)
                    elif operation == 'mean': metrics[operation] = str(total / len(values))
                    # Equal values with different spellings (-0.00, 0.00) report the first one in row order.
                    elif operation == 'min': metrics[operation] = str(min(values))
                    elif operation == 'max': metrics[operation] = str(max(values))
                result[column] = metrics
        return {'arithmetic': 'decimal128_half_even', 'columns': result}
    except (ValueError, TypeError, KeyError, DecimalException) as error:
        raise ResearchError('calculation_input', str(error)[:240]) from error


async def execute(ctx, inputs):
    packet = inputs['packet']
    return {'result': produced(output_packet(packet, data=dict(packet['data'], calculation_result=calculate(packet))))}
