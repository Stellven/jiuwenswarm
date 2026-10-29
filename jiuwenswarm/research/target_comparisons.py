"""Versioned user-target arithmetic shared by compilation and Hypothesis checks."""
from decimal import Decimal


BRIEF_VERSION = '3.0.0'
BRIEF_CONTRACT = 'urn:jiuwenswarm:m1-design:research-brief:' + BRIEF_VERSION

# Offsets have the target's unit; factors are dimensionless. Unknown units
# must match exactly, rather than acquiring an invented conversion.
_UNITS = {
    'fraction': ('ratio', '1'), 'ratio': ('ratio', '1'),
    '%': ('ratio', '.01'), 'percent': ('ratio', '.01'),
    'percentage': ('ratio', '.01'), 'percentage points': ('ratio', '.01'),
    'percentage_points': ('ratio', '.01'), 'pp': ('ratio', '.01'),
    's': ('time', '1'), 'seconds': ('time', '1'), 'second': ('time', '1'),
    'ms': ('time', '.001'), 'milliseconds': ('time', '.001'),
    'us': ('time', '.000001'), 'microseconds': ('time', '.000001'),
    'ns': ('time', '.000000001'), 'nanoseconds': ('time', '.000000001'),
}


def comparison_rule(target, metric_unit=None):
    """Return an exact success rule; old value-only comparisons keep their meaning."""
    comparison = target.get('comparison')
    if comparison is None:
        return None
    if 'factor' not in comparison:
        return {'operand': 'treatment', 'comparator': comparison['comparator'],
                'reference': comparison['reference'],
                'factor': comparison['value'] if comparison['reference'] == 'baseline' else 0,
                'offset': comparison['value'] if comparison['reference'] == 'constant' else 0}
    offset = comparison['offset']
    if metric_unit is not None:
        source, destination = target['unit'].strip().lower(), metric_unit.strip().lower()
        if source != destination:
            before, after = _UNITS.get(source), _UNITS.get(destination)
            if before is None or after is None or before[0] != after[0]:
                raise ValueError('Target and measured metric units are incompatible')
            offset = float(Decimal(str(offset)) * Decimal(before[1]) / Decimal(after[1]))
    return {'operand': 'treatment', 'comparator': comparison['comparator'],
            'reference': comparison['reference'], 'factor': comparison['factor'], 'offset': offset}


def check_target_comparisons(brief):
    """A mandatory quantitative target cannot escape as an untyped null."""
    if brief['schema_version'] != BRIEF_VERSION:
        return  # Historical 2.0.0 evidence is interpreted under its original contract.
    for target in brief['target_metrics']:
        if target['comparison_status'] == 'unsupported':
            raise ValueError('unsupported_target_comparison: ' + target['id'] +
                             '; a mandatory quantitative target cannot be normalized')
        if target['comparison_status'] == 'quantitative':
            comparison_rule(target)
