import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.calculate.worker import calculate, execute
from jiuwenswarm.research.capsule_extensions.calculate.checks import check
from jiuwenswarm.research.contracts import ResearchError


def packet(values, mode='json_numbers', operations=None):
    return {'schema_version': '1.0.0', 'data': {'table': {'columns': ['v'], 'rows': [[v] for v in values]},
        'calculation': {'columns': ['v'], 'operations': operations or ['count', 'sum', 'mean', 'min', 'max'], 'numeric_mode': mode}},
        'files': [], 'trust': 'low', 'provenance': [], 'limitations': ['source remains uncertain']}


@pytest.mark.asyncio
@pytest.mark.parametrize('values,mode', [([1, 2, 3], 'json_numbers'), (['001', '2.0', '3e0'], 'decimal_strings')])
async def test_calculation_is_explicit_correct_checked_and_tainted(values, mode):
    source = packet(values, mode)
    result = json.loads((await execute(None, {'packet': source}))['result'].data)
    metrics = result['data']['calculation_result']['columns']['v']
    assert metrics['count'] == 3 and float(metrics['mean']) == 2
    assert float(metrics['sum']) == 6 and result['trust'] == 'low'
    ctx = SimpleNamespace(output_refs={})
    assert all(r['outcome'] == 'PASS' for r in check(ctx, {'packet': source}, {'result': result}))
    result['data']['calculation_result']['columns']['v']['sum'] = '100'
    assert check(ctx, {'packet': source}, {'result': result})[-1]['outcome'] == 'FAIL'


@pytest.mark.parametrize('value', [packet([True]), packet([None]), packet(['1']), packet(['NaN'], 'decimal_strings'),
    packet(['1e9999'], 'decimal_strings'), packet([' 1 '], 'decimal_strings'), packet([]), packet([float('inf')])])
def test_invalid_numeric_inputs_fail_without_inference(value):
    with pytest.raises(ResearchError): calculate(value)


def test_empty_count_sum_and_repeating_mean_have_declared_semantics():
    assert calculate(packet([], operations=['count', 'sum']))['columns']['v'] == {'count': 0, 'sum': '0'}
    result = calculate(packet([1, 0, 0], operations=['mean']))
    assert result['arithmetic'] == 'decimal128_half_even'
    assert len(result['columns']['v']['mean']) == 130
