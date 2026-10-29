"""Regressions for additive user targets, units and historical evidence."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import validate, ContractError
from jiuwenswarm.research.target_comparisons import comparison_rule, check_target_comparisons
from jiuwenswarm.research.science import rule_holds


def brief():
    return json.loads(Path('tests/fixtures/research/compiler/research_brief.json').read_text())


def test_five_points_is_additive_and_preserves_inclusive_boundary():
    target = {'comparison_status': 'quantitative', 'unit': 'percentage points',
              'comparison': {'comparator': 'ge', 'reference': 'baseline', 'factor': 1, 'offset': 5}}
    rule = comparison_rule(target, 'fraction')
    assert rule['factor'] == 1 and rule['offset'] == 0.05
    assert rule_holds(rule, 0.8, 0.85)
    assert not rule_holds(rule, 0.8, 0.84)  # A 5% relative gain does not meet five points.
    with pytest.raises(ValueError, match='incompatible'):
        comparison_rule(target, 'ms')


def test_current_schema_separates_unsupported_and_qualitative_targets():
    value = brief()
    target = value['target_metrics'][0]
    target.update(comparison_status='unsupported', comparison=None)
    validate('research-brief', value)  # Candidate can be retained for inspection.
    with pytest.raises(ValueError, match='unsupported_target_comparison'):
        check_target_comparisons(value)
    target['comparison_status'] = 'qualitative'
    check_target_comparisons(value)
    target['comparison'] = {'comparator': 'ge', 'reference': 'baseline', 'factor': 1, 'offset': 5}
    with pytest.raises(ContractError):validate('research-brief', value)


def test_historical_value_only_comparisons_keep_original_semantics():
    root = Path('jiuwenswarm/research/resources/calibration')
    old = json.loads((root / 'research_brief.json').read_text())
    validate('research-brief', old)
    assert old['schema_version'] == '2.0.0'
    rule = comparison_rule({'comparison': {'reference': 'baseline', 'comparator': 'le', 'value': 0.9}})
    assert rule == {'operand': 'treatment', 'reference': 'baseline', 'comparator': 'le', 'factor': 0.9, 'offset': 0}
    with pytest.raises(ContractError):validate('urn:jiuwenswarm:m1-design:research-brief:3.0.0', old)
