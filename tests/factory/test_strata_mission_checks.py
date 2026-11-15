"""The retained-cell verifier must not accept comparisons across configurations."""
import copy
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2] / 'deploy/spark/check-strata-mission.py'
spec = importlib.util.spec_from_file_location('strata_mission_checks', path)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def cells():
    request = dict(canonical_sha256='a' * 64, generated_tokens=128, decode_tps=8.0)
    return [dict(status='verified_complete', comparison_group='b' * 64,
                 repeat_equal=True, requests=[copy.deepcopy(request), copy.deepcopy(request)])
            for _ in range(3)]


def test_matching_reference_requires_three_cells_and_one_output_identity():
    rows = cells()
    assert checks.summarize_results('task', rows)['deterministic_reference_accepted']
    assert not checks.summarize_results('task', rows[:2])['deterministic_reference_accepted']
    rows[0]['requests'][0]['canonical_sha256'] = 'c' * 64
    assert not checks.summarize_results('task', rows)['deterministic_reference_accepted']


@pytest.mark.parametrize('group', ['c' * 64, None])
def test_identical_outputs_cannot_hide_changed_or_missing_configuration(group):
    rows = cells()
    rows[0]['comparison_group'] = group
    report = checks.summarize_results('task', rows)
    assert report['fresh_process_output_identities'] == 1
    assert not report['configurations_comparable']
    assert not report['deterministic_reference_accepted']
