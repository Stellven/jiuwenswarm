"""Synthetic trace fixtures only: no live model or captured predictor claims."""
import copy
import json
import pytest

from jiuwenswarm.factory import expert_prediction as prediction


def selected(expert):
    return dict(expert=expert, bytes=100)


def event(token, issued, demand, expert, predicted=()):
    return dict(phase='decode', token=token, layer=0, issued_ns=issued,
                demand_ns=demand, selected=[selected(expert)], predicted=list(predicted))


@pytest.fixture
def synthetic_trace():
    return dict(schema_version=1, origin='synthetic', requests=[
        dict(request_id='train-0', split='train', events=[event(0, 1, 10, 1)]),
        dict(request_id='test-0', split='test', events=[
            event(0, 20, 30, 2, [dict(expert=2, bytes=100, ready_ns=35),
                                dict(expert=9, bytes=100, ready_ns=25)]),
            event(1, 40, 50, 2, [dict(expert=2, bytes=100, ready_ns=45)])]),
    ])


def test_synthetic_observed_coverage_readiness_and_byte_waste_are_distinct(synthetic_trace):
    report = prediction.evaluate(synthetic_trace, k=2)
    observed = report['policies']['observed']
    assert observed['coverage_at_k'] == 1
    assert observed['timely_coverage_at_k'] == 0.5
    assert observed['waste_bytes_at_demand'] == 100
    assert report['observed_bytes']['prediction_requested'] == 300
    assert report['origin'] == 'synthetic'
    assert report['performance_gain'] == 'not_established'
    assert report['scoring_eligible'] is False


def test_frequency_never_learns_test_choices_and_last_token_uses_only_past(synthetic_trace):
    report = prediction.evaluate(synthetic_trace, k=2)
    frequency = report['policies']['frequency']
    last = report['policies']['last_token']
    assert frequency['coverage_at_k'] == 0
    assert last['coverage_at_k'] == 0.5
    assert last['empty_predictions'] == 1
    assert frequency['timely_coverage_at_k'] is None
    assert frequency['waste_bytes_at_demand'] is None


def test_last_token_cannot_see_previous_demand_that_has_not_happened(synthetic_trace):
    synthetic_trace['requests'][1]['events'][1]['issued_ns'] = 29
    assert prediction.evaluate(synthetic_trace, 2)['policies']['last_token']['coverage_at_k'] == 0


def test_last_token_history_resets_between_holdout_requests(synthetic_trace):
    synthetic_trace['requests'].append(dict(request_id='test-1', split='test',
                                           events=[event(0, 60, 70, 2)]))
    report = prediction.evaluate(synthetic_trace, 2)
    assert report['policies']['last_token']['empty_predictions'] == 2
    assert report['policies']['last_token']['coverage_at_k'] == pytest.approx(1/3)


def test_top_k_uses_observed_order(synthetic_trace):
    request = synthetic_trace['requests'][1]
    request['events'][0]['predicted'].reverse()
    report = prediction.evaluate(synthetic_trace, 1)
    assert report['policies']['observed']['coverage_at_k'] == 0.5
    assert report['policies']['observed']['waste_bytes_at_demand'] == 100


def test_frequency_ties_use_expert_id_and_not_future_selection(synthetic_trace):
    synthetic_trace['requests'][0]['events'][0]['selected'] = [selected(3), selected(1)]
    synthetic_trace['requests'][1]['events'][0]['selected'] = [selected(3)]
    assert prediction.evaluate(synthetic_trace, 1)['policies']['frequency']['coverage_at_k'] == 0
    assert prediction.evaluate(synthetic_trace, 2)['policies']['frequency']['coverage_at_k'] == 0.5


def test_phase_history_never_crosses_prefill_decode(synthetic_trace):
    synthetic_trace['requests'][1]['events'][1]['phase'] = 'prefill'
    result = prediction.evaluate(synthetic_trace, 2)
    assert result['policies']['last_token']['coverage_at_k'] == 0
    assert result['policies']['frequency']['empty_predictions'] == 1


@pytest.mark.parametrize('change', ['overlap', 'repeated_request', 'repeated_token',
    'duplicate_expert', 'read_before_issue', 'negative_bytes', 'unknown_field', 'boolean_k', 'future_train'])
def test_invalid_or_leaking_trace_fails_closed(synthetic_trace, change):
    trace = copy.deepcopy(synthetic_trace)
    test = trace['requests'][1]['events'][0]
    k = 2
    if change == 'overlap': test['issued_ns'] = 9
    elif change == 'repeated_request': trace['requests'][1]['request_id'] = 'train-0'
    elif change == 'repeated_token': trace['requests'][1]['events'][1]['token'] = 0
    elif change == 'duplicate_expert': test['selected'].append(selected(2))
    elif change == 'read_before_issue': test['predicted'][0]['ready_ns'] = 19
    elif change == 'negative_bytes': test['selected'][0]['bytes'] = -1
    elif change == 'unknown_field': test['future_choices'] = [2]
    elif change == 'boolean_k': k = True
    elif change == 'future_train': trace['requests'].reverse()
    with pytest.raises(ValueError): prediction.evaluate(trace, k)


def test_null_ready_is_not_credited_as_timely(synthetic_trace):
    synthetic_trace['requests'][1]['events'][1]['predicted'][0]['ready_ns'] = None
    report = prediction.evaluate(synthetic_trace, 2)
    assert report['policies']['observed']['coverage_at_k'] == 1
    assert report['policies']['observed']['timely_coverage_at_k'] == 0


def test_scoped_artifact_dispatch_preserves_synthetic_origin_and_source(store, synthetic_trace):
    raw = json.dumps(synthetic_trace).encode()
    store.put_artifact('t', 'synthetic-predictor', raw, 'application/json', None)
    result = prediction.dispatch(store.scoped('t'), 't', 'evaluate',
                                 dict(artifact_id='synthetic-predictor', k=2))
    assert result['analysis']['origin'] == 'synthetic'
    assert result['evidence']['kind'] == 'expert_prediction_offline'
    assert result['evidence']['source_artifacts'] == ['synthetic-predictor']


def test_event_bound_rejected(synthetic_trace):
    synthetic_trace['requests'][1]['events'] = [event(i, 20+i*2, 21+i*2, 2)
                                               for i in range(prediction.MAX_EVENTS)]
    with pytest.raises(ValueError, match='10000 events'):
        prediction.evaluate(synthetic_trace, 2)
