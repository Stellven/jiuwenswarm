import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.calculate.worker import calculate, execute
from jiuwenswarm.research.capsule_extensions.calculate.checks import check
from jiuwenswarm.research.capsule_extensions.calculate_v3.worker import calculate as calculate_v3, execute as execute_v3
from jiuwenswarm.research.capsule_extensions.calculate_v3.checks import check as check_v3
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


def wrapped(source):
    return dict(source, data={'data': source['data']})


@pytest.mark.parametrize('bad,fragment', [
    (wrapped(packet([1])), 'lacks table and calculation'),
    (wrapped(packet([1])), 'extra data wrapper'),
    (dict(packet([1]), data={'calculation': packet([1])['data']['calculation']}), 'lacks table;'),
    (dict(packet([1]), data={'table': packet([1])['data']['table']}), 'lacks calculation;'),
    (dict(packet([1]), data={'table': [1], 'calculation': packet([1])['data']['calculation']}), 'exactly columns and rows'),
])
def test_v3_shape_errors_say_what_is_wrong_not_a_bare_key(bad, fragment):
    with pytest.raises(ResearchError) as caught:
        calculate_v3(bad)
    assert caught.value.code == 'calculation_input' and fragment in str(caught.value)
    assert str(caught.value) != "'table'"


@pytest.mark.asyncio
@pytest.mark.parametrize('values,expected', [
    (['99999999999999999999999999999', '1'], '100000000000000000000000000000'),
    (['1e29', '1'], '100000000000000000000000000001'),
    (['1' * 128, '1e-5'], None),
])
async def test_v3_accepts_inputs_beyond_28_digits_with_exact_sums(values, expected):
    source = packet(values, 'decimal_strings', ['sum', 'min', 'max'])
    if expected is None:
        with pytest.raises(ResearchError, match='more than 128'):
            calculate_v3(dict(source, data=dict(source['data'], calculation=dict(source['data']['calculation'], operations=['sum']))))
        # min/max stay exact, so they are still answered when no sum is requested
        assert calculate_v3(dict(source, data=dict(source['data'], calculation=dict(source['data']['calculation'], operations=['min', 'max']))))
        return
    result = json.loads((await execute_v3(None, {'packet': source}))['result'].data)
    assert result['data']['calculation_result']['columns']['v']['sum'] == expected
    assert all(r['outcome'] == 'PASS' for r in check_v3(SimpleNamespace(output_refs={}), {'packet': source}, {'result': result}))


def test_v3_bounds_are_128_digits_and_exponent_128_and_checks_agree():
    ok = packet(['1' * 128, '1e128'], 'decimal_strings', ['min'])
    assert calculate_v3(ok)['columns']['v']['min']
    for bad in (['1' * 129], ['1e129'], ['1e-129']):
        with pytest.raises(ResearchError):
            calculate_v3(packet(bad, 'decimal_strings'))
        result = calculate(packet(['1'], 'decimal_strings'))  # v1 result shape, wrong for these inputs
        out = dict(packet(bad, 'decimal_strings'), data=dict(packet(bad, 'decimal_strings')['data'], calculation_result=result))
        rows = check_v3(SimpleNamespace(output_refs={}), {'packet': packet(bad, 'decimal_strings')}, {'result': out})
        assert rows[1]['outcome'] == 'FAIL'


def test_v3_still_refuses_what_v1_refused():
    for value in (packet([True]), packet([None]), packet(['1']), packet(['NaN'], 'decimal_strings'),
                  packet(['1e9999'], 'decimal_strings'), packet([' 1 '], 'decimal_strings'), packet([]), packet([float('inf')]),
                  packet(['$1'], 'decimal_strings'), packet(['5%'], 'decimal_strings')):
        with pytest.raises(ResearchError):
            calculate_v3(value)


def test_v3_agrees_with_v1_within_the_old_bounds():
    source = packet(['001', '2.50', '3e0', '-0.125'], 'decimal_strings')
    assert calculate_v3(source) == calculate(source)


@pytest.mark.asyncio
async def test_v3_worker_and_checks_agree_on_equal_values_with_different_spellings():
    source = packet(['-0.00', '0.00', '1.0', '1.00'], 'decimal_strings', ['sum', 'min', 'max'])
    result = json.loads((await execute_v3(None, {'packet': source}))['result'].data)
    metrics = result['data']['calculation_result']['columns']['v']
    assert (metrics['min'], metrics['max']) == ('-0.00', '1.0')
    assert all(r['outcome'] == 'PASS' for r in check_v3(SimpleNamespace(output_refs={}), {'packet': source}, {'result': result}))
