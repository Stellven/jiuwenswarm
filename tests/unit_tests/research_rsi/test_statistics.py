import pytest
from jiuwenswarm.research_rsi.statistics import qualify, exact_paired_p


def test_exact_independent_fixture_binomial_and_regression():
    assert exact_paired_p(5, 0) == 1 / 32
    result = qualify([0]*5+[1]*15, [1]*20)
    assert result['qualified_by'] == 'pass_gain'
    assert result['statistics']['pass_rate_gain'] == .25
    assert qualify([1]*20, [0]+[1]*19)['outcome'] == 'NO_IMPROVEMENT'
    assert qualify([0]+[1]*19, [1]*20)['outcome'] == 'INCONCLUSIVE'


def test_positive_gain_without_significance_is_inconclusive_and_timing_cannot_rescue_it():
    result=qualify([0]*4+[1]*16,[1]*20,parent_times=[10]*7,
        child_times=[1]*7,warmups=5,calibrated_noise=0)
    assert result['outcome']=='INCONCLUSIVE' and result['qualified_by']=='none'
    assert result['statistics']['p_value']==1/16
    assert result['statistics']['timing'] is None
    # A supported gain below a stricter meaningful-delta policy is no improvement.
    assert qualify([0]*5+[1]*15,[1]*20,min_pass_gain=.5)['outcome']=='NO_IMPROVEMENT'


def test_mean_of_three_lower_mean_is_regression():
    p = [[1,1,1]]*20
    c = [[1,1,1]]*19+[[1,1,0]]
    assert 'regression' in qualify(p,c,repeats=3)['reason']
    assert qualify(p,c,repeats=3)['qualified_by'] == 'none'


def test_timing_strict_noise_and_independence():
    # Exact source JSON decimals: .3 equals 3*.1. A Python 1/30 float
    # serializes below the rational1/30 and is not an equality fixture.
    kw = dict(parent_times=[10]*7, child_times=[7]*7, warmups=5, calibrated_noise=.1)
    assert qualify([1]*20,[1]*20,**kw)['qualified_by'] == 'none'
    kw['calibrated_noise']=.02
    assert qualify([1]*20,[1]*20,**kw)['qualified_by']=='timing_tiebreak'
    assert qualify([0]*20,[1]*20,independent=False)['outcome']=='INCONCLUSIVE'
    with pytest.raises(ValueError): qualify([1]*19,[1]*19)


def test_v2_fractional_means_are_not_binary_votes_or_direction_totals():
    parent=[[1,0,0]]*20
    child=[[1,1,0]]*10+[[1,0,0]]*10
    result=qualify(parent,child,repeats=3)
    stats=result['statistics']
    assert result['outcome']=='QUALIFIED'
    assert stats['parent_passed']==float(20/3)
    assert stats['child_passed']==10
    assert stats['gain_units']==10 and stats['loss_units']==0
    assert stats['pass_rate_gain']==float(1/6)
    assert stats['p_value']==1/1024
    assert stats['child_passed']-stats['parent_passed']!=stats['gain_units']-stats['loss_units']


def test_v2_fractional_regression_cannot_be_offset_by_other_gains():
    parent=[[1,0,0]]*20
    child=[[1,1,1]]*19+[[0,0,0]]
    result=qualify(parent,child,repeats=3)
    assert result['outcome']=='NO_IMPROVEMENT'
    assert result['statistics']['loss_units']==1


def test_zero_discordance_has_null_p_and_timing_uses_ratio_of_medians():
    assert exact_paired_p(0,0) is None
    result=qualify([1]*20,[1]*20,parent_times=[1,2,3,4,5,6,7],
        child_times=[.8,1.6,2.4,3.8,4,4.8,5.6],warmups=5,calibrated_noise=.001)
    assert result['statistics']['p_value'] is None
    assert result['statistics']['timing']['relative_gain']==.05
    assert result['outcome']=='NO_IMPROVEMENT'
def test_timing_exact_decimal_noise_boundary_has_no_float_rounding_escape():
    from jiuwenswarm.research_rsi.statistics import qualify
    # A 30% gain equals three times 10% noise and cannot satisfy strict greater.
    result=qualify([1]*20,[1]*20,parent_times=[10]*7,child_times=[7]*7,
        warmups=5,calibrated_noise=.1,min_timing_gain=.3,noise_multiplier=3)
    assert result['outcome']=='NO_IMPROVEMENT'
