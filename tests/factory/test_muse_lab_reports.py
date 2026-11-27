"""Report comparison and chart checks with no lab or model execution."""

from scripts.spark.build_muse_lab_reports import (
    AFTER_PAGE_DROP, FIRST_AFTER_START, FOLLOW_UP, WARM_SERVER, Report, TimingRow, gain, metric_chart,
)


def test_time_rate_and_accuracy_gains_use_their_own_units():
    assert gain(91.4509, 585.174, 's') == '6.4× faster (−84%)'
    assert gain(120, 100, 's') == '1.2× slower (+20%)'
    assert gain(3.7, 1, 'tok/s') == '3.7× (+270%)'
    assert gain(.916, .94, '%') == '−2.4 points'
    assert gain(509, 0, 'tokens') == 'relative change unavailable'


def test_each_chart_uses_one_axis_and_marks_the_current_arm():
    chart = metric_chart('first-token-512', 'First token', 'Matched requests', 's', [
        ('A', 100, []), ('AQB', 50, []), ('AQBC', 25, ['vs AQB — 2× faster (−50%)']),
    ], 'AQBC')
    assert 'data-axis-max="100"' in chart
    assert 'data-arm="AQBC" data-value="25" data-current="true"' in chart
    assert chart.count('data-current="true"') == 1
    for width in ('100.00000000%', '50.00000000%', '25.00000000%'):
        assert f'width:{width}' in chart
    assert '25.00 s' in chart
    assert '2× faster (−50%)' in chart


def test_tolerance_and_missing_matches_follow_recorded_workload(tmp_path):
    def row(arm, state, ttft_ms):
        return TimingRow(arm, '512', state, {'ttft_ms': ttft_ms}, [])

    report = Report(tmp_path, tmp_path, 2)
    base = row('A', WARM_SERVER, 200)
    control = row('AQB', WARM_SERVER, 100)
    followup = row('AQB', FOLLOW_UP, 100)
    cold_control = row('AQB', AFTER_PAGE_DROP, 100)
    report.original_r8 = {base.key: base}
    report.run2_results = {r.key: r for r in (control, followup, cold_control)}
    acceptance = {
        'standard_regression_tolerance': .1,
        'standard': [{
            'request': 'p512', 'judged': True, 'median_candidate_to_control': {'derived_ttft_ms': .95},
        }],
    }
    assert report.timing_comparisons(row('AQBC', WARM_SERVER, 95), 'ttft_ms', acceptance=acceptance) == [
        'same as AQB',
    ]
    assert report.timing_comparisons(row('AQBC', FOLLOW_UP, 95), 'ttft_ms', acceptance=acceptance) == [
        'same as AQB',
    ]
    assert report.timing_comparisons(row('AQBC', FIRST_AFTER_START, 130), 'ttft_ms', acceptance=acceptance) == [
    ]
    acceptance['standard'][0]['median_candidate_to_control']['derived_ttft_ms'] = .5
    assert report.timing_comparisons(row('AQBC', WARM_SERVER, 50), 'ttft_ms', acceptance=acceptance)[0] == (
        'vs AQB — 2× faster (−50%)'
    )


def test_accuracy_highlights_only_a_recorded_or_inherited_score(tmp_path):
    report = Report(tmp_path, tmp_path, 2)
    paired = {'acc_ref': .94, 'acc_cand': .916, 'n': 250}
    passed = report.accuracy_chart(paired, identity={'status': 'passed', 'inherited_accuracy': .916})
    assert 'data-axis-max="1"' in passed
    assert 'data-arm="AQBC" data-value="0.916" data-current="true"' in passed
    assert 'same as AQB' in passed
    assert '−2.4 points' in passed
    refused = report.accuracy_chart(paired, identity={'status': 'refused'})
    assert 'data-arm="AQBC"' not in refused
