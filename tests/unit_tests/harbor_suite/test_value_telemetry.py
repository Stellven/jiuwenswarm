import pytest

from benchmarks.harbor_suite.value_telemetry import summarize_records


def row(number, kind='model-call', usage=None):
    return {'kind': kind, 'ref': {'id': str(number), 'sha256': str(number) * 64},
            'record': {'usage': usage if usage is not None else {'input_tokens': 10, 'output_tokens': 5}}}


def test_missing_usage_is_not_zero_and_partial_sum_stays_separate():
    result = summarize_records([row(1), row(2, usage={})])
    assert result['model_calls'] == 2
    assert result['usage']['input_tokens']['total'] is None
    assert result['usage']['input_tokens']['observed_partial_sum'] == 10
    assert result['usage']['cost_usd']['total'] is None
    assert result['gpu_seconds'] is None


def test_original_ref_exported_under_multiple_roles_is_counted_once():
    first = row(1)
    duplicate = dict(first, kind='model_call')
    result = summarize_records([first, duplicate, row(2, kind='tool-observation')])
    assert result['model_calls'] == 1 and result['tool_observations'] == 1
    assert result['usage']['input_tokens']['total'] == 10
    with pytest.raises(ValueError):
        summarize_records([first, dict(first, record={'usage': {'input_tokens': 999}})])
