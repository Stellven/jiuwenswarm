"""Interface B: a movable, noise-aware objective over public + held-out cases."""
import asyncio
import copy
import importlib
import importlib.util
from pathlib import Path
from time import perf_counter

import pytest

from jiuwenswarm.research.capsule_extensions.packet import produced, validate_packet
from jiuwenswarm.research_rsi.targets import capsules
from jiuwenswarm.research_rsi.targets.capsule_objective import (
    MIN_MARGIN, RULE, calibrate_noise, evaluation_fixtures, fixtures, score,
)

NAMES = ['utility.calculate', 'utility.table_normalize']
HARDER = ('public_extended', 'held_out')


def visible(rows, *, trials=None, name='unit.capsule', failure=None, schema=2):
    """rows: (fixture_id, fixture_set, task_success, wall_s, output_bytes[, extra])."""
    out = []
    for ident, fixture_set, ok, wall, size, *extra in rows:
        row = {'fixture_id': ident, 'task_success': ok, 'protected_wall_s': wall, 'output_bytes': size,
               'checks': {}, 'receipt': None}
        if schema == 2:
            row['fixture_set'] = fixture_set
        if extra:
            row.update(extra[0])
        out.append(row)
    total = sum(row['protected_wall_s'] for row in out)
    result = {'schema': f'ai4r-rsi-whole-capsule-visible-result:{schema}', 'capsule_name': name, 'rows': out,
              'passed_count': sum(row['task_success'] for row in out), 'protected_wall_s': total,
              'failure': failure}
    if schema == 2:
        result.update(case_count=len(out), trial_wall_s=list(trials) if trials else [total])
    return result


def three(ok_b=True, wall=1.0):
    return [('a', 'public', True, wall / 2, 100), ('b', 'public', ok_b, wall / 4, 100),
            ('h1', 'held_out', True, wall / 4, 50)]


# ---- fixture contract -------------------------------------------------------

@pytest.mark.parametrize('name', NAMES)
def test_fixtures_interface_returns_fresh_sets_and_public_matches_baseline(name):
    assert fixtures(name, fixture_set='public') == capsules.public_fixtures(name)
    for fixture_set in capsules.FIXTURE_SETS:
        rows = fixtures(name, fixture_set=fixture_set)
        assert rows and all(set(row) == {'id', 'packet', 'expected_task_output'} for row in rows)
        rows[0]['packet']['data'].clear()
        assert fixtures(name, fixture_set=fixture_set)[0]['packet']['data']
    tagged = evaluation_fixtures(name)
    assert [row['fixture_set'] for row in tagged].count('held_out') == capsules.registered_capsule(name).held_out_case_count
    ids = [row['id'] for row in tagged]
    assert len(ids) == len(set(ids))
    with pytest.raises(ValueError):
        fixtures(name, fixture_set='hidden')


# ---- the objective is movable for every real parent --------------------------

def _min_wall(fn, k=3):
    best = None
    for _ in range(k):
        started = perf_counter(); fn(); elapsed = perf_counter() - started
        best = elapsed if best is None else min(best, elapsed)
    return best


@pytest.mark.parametrize('name', NAMES)
def test_current_parent_has_headroom_on_harder_cases(name):
    """Real parent, in process, over every set: some harder case fails or is materially slow.

    "Materially slow" means the parent's min-of-3 wall is >= 1.5x the cost of
    the unavoidable packet envelope for that case (validating the input and
    emitting the expected output packet), on a case large enough to time.
    """
    result = asyncio.run(capsules.evaluate_in_process(name, trials=3))
    groups = {row['fixture_id']: row['fixture_group'] for row in result['rows']}
    assert result['case_count'] == sum(len(capsules.fixture_set(name, s)) for s in capsules.FIXTURE_SETS)
    failing = sorted(row['fixture_id'] for row in result['rows'] if not row['task_success'])
    assert all(row['task_success'] for row in result['rows'] if row['fixture_group'] == 'public')
    execute, _, key = capsules._carrier(name)
    slow = {}
    for row in result['rows']:
        if row['fixture_group'] not in HARDER or not row['task_success']:
            continue
        case = next(c for s in HARDER for c in capsules.fixture_set(name, s) if c['id'] == row['fixture_id'])
        expected = copy.deepcopy(case['packet']); expected['data'][key] = case['expected_task_output']
        floor = _min_wall(lambda: (validate_packet(case['packet']), produced(expected)))
        if floor >= 0.002:
            slow[row['fixture_id']] = min(row['trial_wall_s']) / floor
    materially_slow = sorted(ident for ident, ratio in slow.items() if ratio >= 1.5)
    print(name, 'failing', failing, 'parent/envelope wall ratios', {k: round(v, 2) for k, v in slow.items()})
    assert all(groups[ident] in HARDER for ident in failing)
    assert failing or materially_slow, 'Harder cases are not hard enough: no failure and no latency headroom'


def _patched_calculate_execute():
    """A hand-made candidate (test-only, never installed): ordering-stable max."""
    source = Path(importlib.import_module(
        'jiuwenswarm.research.capsule_extensions.calculate.worker').__file__).read_text('utf-8')
    assert source.count('str(max(values))') == 1
    package = 'jiuwenswarm.research.capsule_extensions.calculate'
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(package + '._unit_candidate', loader=None))
    module.__package__ = package
    exec(compile(source.replace('str(max(values))', 'str(sorted(values)[-1])'), '<unit-candidate>', 'exec'), module.__dict__)
    return module.execute


def test_historical_parent_and_a_real_fix_move_the_objective_end_to_end(monkeypatch):
    name = 'utility.calculate'
    # Preserve the historical max-tie regression under its own checker; the
    # selected m1-4 parent already fixes it and has no correctness headroom.
    from dataclasses import replace
    original_target = capsules.registered_capsule
    legacy_worker = importlib.import_module(capsules._PACKAGE + '.calculate.worker').execute
    legacy_check = importlib.import_module(capsules._PACKAGE + '.calculate.checks').check
    target = replace(original_target(name), check_ids=('packet_schema', 'packet_integrity'))
    monkeypatch.setattr(capsules, 'registered_capsule', lambda key: target if key == name else original_target(key))
    original_carrier = capsules._carrier
    monkeypatch.setattr(capsules, '_carrier', lambda key: (legacy_worker, legacy_check, target.task_output_key)
                        if key == name else original_carrier(key))
    parents = [asyncio.run(capsules.evaluate_in_process(name)) for _ in range(3)]
    noise = calibrate_noise(parents)
    candidate = asyncio.run(capsules.evaluate_in_process(name, role='candidate', execute=_patched_calculate_execute()))
    result = score(parents[0], candidate, noise=noise)
    assert result['improved'] and not result['regressed']
    assert result['correctness']['candidate'] == 1.0 > result['correctness']['parent']
    assert any(ident.startswith('h') for ident in result['newly_passed'])
    back = score(candidate, parents[0], noise=noise)
    assert back['regressed'] and not back['improved']
    assert 'max-tie-trailing-zeros' in back['feedback']
    held = {row['id']: row for row in fixtures(name, fixture_set='held_out')}
    for ident, row in held.items():
        assert repr(row['expected_task_output']['columns'])[:40] not in back['feedback']


# ---- score() on hand-built visible results ---------------------------------

def test_regression_is_never_an_improvement_even_when_faster():
    parent = visible(three(), trials=[1.0, 1.02, 1.01])
    candidate = visible(three(ok_b=False, wall=0.2), trials=[0.2])
    result = score(parent, candidate)
    assert result['regressed'] and not result['improved']
    assert result['correctness'] == {'parent': 1.0, 'candidate': 2 / 3}
    assert result['newly_failed'] == ['b'] and 'REGRESSIONS' in result['feedback'] and 'public [b]' in result['feedback']
    crashed = visible(three(), trials=[1.0], failure={'exception_type': 'TimeoutError', 'message': 'deadline'})
    assert score(parent, crashed)['regressed']


def test_pure_correctness_gain_improves_even_when_slower():
    parent = visible(three(ok_b=False), trials=[1.0, 1.01, 1.02])
    candidate = visible(three(wall=1.3), trials=[1.3])
    result = score(parent, candidate, noise=calibrate_noise([parent] * 3))
    assert result['improved'] and not result['regressed'] and result['newly_passed'] == ['b']
    assert result['latency_ratio'] == pytest.approx((1.3 / 2 + 1.3 / 4) / (1.0 / 2 + 1.0 / 4))
    assert result['correctness'] == {'parent': 2 / 3, 'candidate': 1.0}


def test_latency_gain_inside_noise_is_not_an_improvement():
    trials = [visible(three(), trials=[wall]) for wall in (1.0, 1.10, 1.05)]
    noise = calibrate_noise(trials)
    assert noise['noise_floor_ratio'] == pytest.approx(1 / 1.10)
    assert noise['margin'] == pytest.approx(0.10) and noise['samples'] == 3
    candidate = visible(three(wall=0.95), trials=[0.95, 0.96])
    result = score(trials[0], candidate, noise=noise)
    assert result['latency_ratio'] == pytest.approx(0.95)
    assert not result['above_noise'] and not result['improved'] and not result['regressed']
    assert 'within noise' in result['summary']


def test_latency_gain_outside_noise_is_an_improvement():
    trials = [visible(three(), trials=[wall]) for wall in (1.0, 1.10, 1.05)]
    candidate = visible(three(wall=0.80), trials=[0.85, 0.80, 0.82])
    result = score(trials[1], candidate, noise=calibrate_noise(trials))
    assert result['latency_ratio'] == pytest.approx(0.80)  # min-of-k on both sides
    assert result['above_noise'] and result['improved'] and not result['regressed']
    assert 'faster above noise' in result['feedback']


def test_uncalibrated_latency_never_counts_and_quiet_parent_still_needs_minimum_margin():
    parent = visible(three(), trials=[1.0])
    assert not score(parent, visible(three(wall=0.5), trials=[0.5]))['improved']
    quiet = calibrate_noise([visible(three(), trials=[1.0])] * 3)
    assert quiet['noise_floor_ratio'] == pytest.approx(1 / (1 + MIN_MARGIN))
    assert not score(parent, visible(three(wall=0.99), trials=[0.99]), noise=quiet)['improved']
    assert score(parent, visible(three(wall=0.97), trials=[0.97]), noise=quiet)['improved']
    # Repeated trials inside the parent result calibrate themselves.
    inline = score(visible(three(), trials=[1.0, 1.2, 1.1]), visible(three(wall=0.9), trials=[0.9]))
    assert inline['noise_floor_ratio'] == pytest.approx(1 / 1.2) and not inline['improved']


def test_calibrate_noise_requires_three_comparable_trials():
    for trials in ([], [visible(three())], [visible(three())] * 2):
        with pytest.raises(ValueError):
            calibrate_noise(trials)
    with pytest.raises(ValueError):
        calibrate_noise([visible(three()), visible(three()), visible(three()[:2])])
    with pytest.raises(ValueError):
        calibrate_noise([visible(three(), trials=[float('nan')])] * 3)


def test_feedback_withholds_held_out_details_and_diffs_public_failures():
    name = 'utility.calculate'
    public = {row['id']: row for row in fixtures(name, fixture_set='public_extended')}
    held = fixtures(name, fixture_set='held_out')[0]
    actual = copy.deepcopy(public['max-tie-trailing-zeros']['expected_task_output'])
    actual['columns']['price']['max'] = '1.00'
    secret = repr(held['expected_task_output'])
    parent_rows = [('max-tie-trailing-zeros', 'public', True, 0.1, 10), (held['id'], 'held_out', True, 0.1, 10),
                   ('json-numbers', 'public', True, 0.1, 10)]
    candidate_rows = [('max-tie-trailing-zeros', 'public', False, 0.1, 9, {'actual_task_output': actual}),
                      (held['id'], 'held_out', False, 0.1, 9,
                       {'error': {'exception_type': 'ResearchError', 'message': 'SECRET ' + secret},
                        'actual_task_output': {'leak': secret}}),
                      ('json-numbers', 'public', False, 0.1, 10,
                       {'error': {'exception_type': 'ValueError', 'message': 'public reason'}})]
    result = score(visible(parent_rows, name=name), visible(candidate_rows, name=name))
    feedback = result['feedback']
    assert 'calculation_result.columns.price.max: expected "1.0", actual "1.00"' in feedback
    assert 'json-numbers: raised ValueError: public reason' in feedback
    assert 'SECRET' not in feedback and 'leak' not in feedback and secret[:30] not in feedback
    assert held['id'] in feedback and 'withheld' in feedback
    assert 'Output size' in feedback and len(feedback) <= 6000
    assert score(visible(parent_rows, name=name), visible(candidate_rows, name=name)) == result


def test_version_one_visible_results_are_scored_with_held_out_inferred_from_fixtures():
    name = 'utility.calculate'
    held = fixtures(name, fixture_set='held_out')[0]['id']
    rows = [('json-numbers', None, True, 0.5, 10), (held, None, True, 0.5, 10)]
    parent = visible(rows, name=name, schema=1)
    candidate = visible([rows[0], (held, None, False, 0.5, 10)], name=name, schema=1)
    result = score(parent, candidate)
    assert result['regressed'] and result['case_counts']['candidate']['held_out'] == [0, 1]
    assert set(result) >= {'correctness', 'latency_ratio', 'noise_floor_ratio', 'above_noise', 'improved',
                           'regressed', 'summary', 'feedback'}
    assert result['rule'] == RULE


def test_long_failure_lists_keep_feedback_bounded():
    rows = [(f'case-{i:04d}-' + 'x' * 40, 'public', True, 0.01, 10) for i in range(400)]
    bad = [(ident, s, False, w, b, {'actual_task_output': {'v': 'y' * 1000}}) for ident, s, _, w, b in rows]
    result = score(visible(rows), visible(bad))
    assert result['regressed'] and len(result['feedback']) <= 6000
    assert '+380 more' in result['feedback'] and 'Public failure details' in result['feedback']
