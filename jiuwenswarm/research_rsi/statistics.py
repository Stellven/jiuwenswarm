"""Independent fixture-unit paired correctness and measured timing decisions."""
from fractions import Fraction
import math
import statistics


def mean_score_total(value,total,repeats):
    """Decode the canonical finite sum of binary one/three-repeat means."""
    if type(total) is not int or total<20 or type(repeats) is not int or repeats not in (1,3) or type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=total:raise ValueError('invalid mean-score total')
    numerator=round(value*repeats)
    fraction=Fraction(numerator,repeats)
    if value!=float(fraction):raise ValueError('total is not an exact canonical n/repeat mean sum')
    return fraction


def exact_paired_p(gains,losses):
    if type(gains) is not int or type(losses) is not int or min(gains,losses)<0:raise ValueError('paired counts must be nonnegative integers')
    n=gains+losses
    return float(Fraction(sum(math.comb(n,k) for k in range(gains,n+1)),2**n)) if n else None


def _means(values,repeats):
    result=[]
    for value in values:
        row=[value] if repeats==1 and not isinstance(value,(list,tuple)) else value
        if not isinstance(row,(list,tuple)) or len(row)!=repeats or any(type(x) not in (int,bool) or x not in (0,1) for x in row):raise ValueError('expected frozen binary repeat scores')
        result.append(Fraction(sum(row),repeats))
    return result


def qualify(parent,child,*,repeats=1,independent=True,mandatory_passed=True,integrity_passed=True,
            parent_times=None,child_times=None,warmups=0,calibrated_noise=None,
            min_pass_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3):
    if type(repeats) is not int or repeats not in (1,3) or len(parent)!=len(child) or len(parent)<20:raise ValueError('at least twenty paired fixture units required')
    policy=[min_pass_gain,alpha,min_timing_gain,noise_multiplier]
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in policy) or min_pass_gain<.05 or not 0<=alpha<=.05 or min_timing_gain<.1 or noise_multiplier<3:raise ValueError('qualification policy widened')
    p,c=_means(parent,repeats),_means(child,repeats)
    gains=sum(y>x for x,y in zip(p,c));losses=sum(y<x for x,y in zip(p,c));n=len(p)
    parent_total=sum(p,Fraction());child_total=sum(c,Fraction());exact_gain=(child_total-parent_total)/n
    gain=float(exact_gain)
    # M1-C006: sums remain fractional; paired directions count independent
    # fixtures once and are never inferred from the aggregate difference.
    encode_total=lambda x:x.numerator if x.denominator==1 else float(x)
    stats={'fixture_units':n,'parent_passed':encode_total(parent_total),'child_passed':encode_total(child_total),
           'gain_units':gains,'loss_units':losses,'pass_rate_gain':gain,'p_value':exact_paired_p(gains,losses),'timing':None}
    out={'outcome':'NO_IMPROVEMENT','qualified_by':'none','statistics':stats,'reason':'qualification thresholds not met'}
    if not independent:return {**out,'outcome':'INCONCLUSIVE','reason':'fixture independence unavailable'}
    if not mandatory_passed or not integrity_passed:return {**out,'outcome':'INVALID','reason':'mandatory or integrity prerequisite failed'}
    if losses:return {**out,'reason':'protected fixture regression'}
    if exact_gain>=Fraction(str(min_pass_gain)) and stats['p_value'] is not None and stats['p_value']<=alpha:return {**out,'outcome':'QUALIFIED','qualified_by':'pass_gain','reason':'paired mean-score gain'}
    if exact_gain>0 and (stats['p_value'] is None or stats['p_value']>alpha):
        return {**out,'outcome':'INCONCLUSIVE','reason':'positive gain lacks sufficient independent paired evidence'}
    if p!=c:return out
    if parent_times is None or child_times is None:return {**out,'outcome':'INCONCLUSIVE','reason':'equal passes without qualified timing capture'}
    if warmups!=5 or len(parent_times)!=7 or len(child_times)!=7:return {**out,'outcome':'INCONCLUSIVE','reason':'five warmups and seven alternating paired rounds required'}
    values=[*parent_times,*child_times,calibrated_noise]
    if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<0 for x in values) or any(x<=0 for x in [*parent_times,*child_times]):
        return {**out,'outcome':'INCONCLUSIVE','reason':'unreliable timing or calibration'}
    parent_median=statistics.median(parent_times);child_median=statistics.median(child_times)
    exact_timing_gain=1-Fraction(str(child_median))/Fraction(str(parent_median))
    median=float(exact_timing_gain)
    stats['timing']={'warmup_batches':5,'paired_rounds':7,'parent_median_s':statistics.median(parent_times),
        'child_median_s':statistics.median(child_times),'relative_gain':median,'calibrated_relative_noise':calibrated_noise,
        'noise_multiplier':noise_multiplier,'min_relative_gain':min_timing_gain}
    if exact_timing_gain>=Fraction(str(min_timing_gain)) and exact_timing_gain>Fraction(str(noise_multiplier))*Fraction(str(calibrated_noise)):
        return {**out,'outcome':'QUALIFIED','qualified_by':'timing_tiebreak','reason':'measured equal-pass timing'}
    return out
