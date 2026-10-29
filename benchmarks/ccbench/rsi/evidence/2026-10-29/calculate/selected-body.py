import copy
from decimal import Decimal, DecimalException, Inexact, localcontext, ROUND_HALF_EVEN

from ...contracts import ResearchError
from ...runner import ProducedArtifact
from ...state import json_bytes
from ..packet import PACKET, validate_packet
from ..calculate_v3.worker import MAX_TEXT, NUMBER, OPS, PRECISION, _shape


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
        operation_set = set(operations)
        needs_total = bool(operation_set & {'sum', 'mean'})
        needs_nonempty = bool(operation_set & {'mean', 'min', 'max'})
        decimal_strings = mode == 'decimal_strings'
        indices = {column: index for index, column in enumerate(columns)}
        count = len(rows)
        result = {}
        # Cache only successfully validated, exact conversion spellings.
        # Decimal values are immutable; this cache is confined to one call.
        converted = {}
        cached_number = converted.get
        decimal = Decimal
        fullmatch = NUMBER.fullmatch
        with localcontext() as context:
            context.prec, context.rounding = PRECISION, ROUND_HALF_EVEN
            for column in selected:
                index = indices[column]
                values = []
                append = values.append
                for row in rows:
                    value = row[index]
                    if ((not decimal_strings and type(value) not in (int, float))
                            or (decimal_strings and (type(value) is not str or len(value) > MAX_TEXT or not fullmatch(value)))):
                        raise ValueError('invalid numeric value; no implicit conversion or missing values')
                    text = str(value)
                    number = cached_number(text)
                    if number is None:
                        number = decimal(text)
                        if (not number.is_finite() or len(number.as_tuple().digits) > PRECISION
                                or abs(number.adjusted()) > PRECISION):
                            raise ValueError('finite bounded decimal value required (at most 128 digits, exponent magnitude 128)')
                        converted[text] = number
                    append(number)
                if not values and needs_nonempty:
                    raise ValueError('empty column has no requested mean/min/max')
                total = None
                if needs_total:
                    context.clear_flags()
                    total = sum(values, Decimal(0))
                    if context.flags[Inexact]:
                        raise ValueError('sum needs more than 128 significant digits; refusing to round it')
                metrics = {}
                for operation in operations:
                    if operation == 'count':
                        metrics[operation] = count
                    elif operation == 'sum':
                        metrics[operation] = str(total)
                    elif operation == 'mean':
                        metrics[operation] = str(total / count)
                    elif operation == 'min':
                        metrics[operation] = str(min(values))
                    elif operation == 'max':
                        metrics[operation] = str(max(values))
                result[column] = metrics
        return {'arithmetic': 'decimal128_half_even', 'columns': result}
    except (ValueError, TypeError, KeyError, DecimalException) as error:
        raise ResearchError('calculation_input', str(error)[:240]) from error


async def execute(ctx, inputs):
    packet = inputs['packet']
    calculation_result = calculate(packet)
    # Validate each envelope once and copy the preserved packet only once.
    result = copy.deepcopy(packet)
    result['data']['calculation_result'] = calculation_result
    result['limitations'] = list(dict.fromkeys(result['limitations']))
    validate_packet(result)
    return {'result': ProducedArtifact(
        json_bytes(result), PACKET, 'application/json', 'result.json'
    )}
