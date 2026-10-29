"""Scoring objective for capsule improvement (Interface B in docs/rsi-loop/INTERFACES.md).

Rule ``correctness_then_latency_above_noise``:

1. Correctness first. ``correctness`` is the passed fraction over every
   evaluated case (public, public_extended and held_out). A candidate that fails
   any case the parent passed, has a lower fraction, or raised where the parent
   did not is ``regressed`` and never ``improved``.
2. Latency only breaks ties, and only above the noise floor. Walls use the
   min-of-k estimator (minimum over repeated trials; timing noise is additive
   and positive). ``calibrate_noise`` measures how much the *parent* varies
   against itself over >=3 repeated trials: ``noise_floor_ratio = min / max``
   of the parent's trial walls, capped at ``1 / (1 + MIN_MARGIN)``. A candidate
   is faster above noise only when ``candidate_wall / parent_wall`` is strictly
   below that floor, i.e. it beats the parent by more than the parent ever beat
   itself. Without calibration latency never counts as an improvement.

Merge wave (docs/rsi-loop/INTERFACES.md, Interface E and the correctness
contract):

* Correctness contract. The checker is authoritative where the parent fails a
  case (a candidate passing it is an improvement). Where the parent passes a
  case, the candidate must also reproduce the parent's exact output bytes
  (``receipt.stdout_ref`` digest, else the checker's ``output_sha256``); a
  checker-accepted candidate that changes those bytes is ``regressed``.
* Latency judge. When a paired batched benchmark report (Interface E) is passed
  as ``benchmark=``, ``latency_ratio`` is its geomean median ratio,
  ``above_noise`` is its ``objective_met`` (every gate passed) and ``improved``
  is "no regression AND (correctness gain OR objective_met)"; the result says
  ``latency_method: "paired_batched_benchmark"``. Without a report the
  single-job min/max floor rule below applies, flagged
  ``latency_method: "single_job_floor"``.

``feedback`` is the text the proposer sees on the next iteration: failing and
fixed case ids (held-out ids are opaque labels; their inputs, expected outputs
and error messages are withheld), a bounded expected-vs-actual diff for public
failures only, timing deltas and output-size deltas.

Everything here is a deterministic pure function of its arguments plus the
installed fixture definitions; no clocks, randomness, network or writes.
"""
from __future__ import annotations

import json
import math
from statistics import median

from .capsules import FIXTURE_SETS, OBJECTIVE, fixture_set as _fixture_set, registered_capsule

RULE = OBJECTIVE
NOISE_SCHEMA = 'ai4r-rsi-capsule-noise:1'
MIN_MARGIN = 0.02            # a latency win must exceed 2% even with a perfectly quiet parent
MIN_TRIALS = 3
FEEDBACK_LIMIT = 6000        # characters
DIFF_CASES = 5
DIFF_PATHS = 8
VALUE_LIMIT = 160
TIMING_CASES = 6
ID_LIMIT = 20
BENCHMARK_REPORT_SCHEMA = 'ai4r-rsi-capsule-benchmark-report:1'
CONTRACT_RULE = 'checker_authoritative_where_parent_fails_parent_bytes_exact_where_parent_passes'
LATENCY_BENCHMARK = 'paired_batched_benchmark'
LATENCY_FLOOR = 'single_job_floor'


def fixtures(name: str, *, fixture_set: str) -> list[dict]:
    """Fresh fixture rows (id, packet, expected_task_output) of one named set.

    ``public`` is the historical baseline (``public_fixtures``), ``public_extended``
    the harder public cases, ``held_out`` the cases never shown to the proposer.
    """
    return _fixture_set(name, fixture_set)


def evaluation_fixtures(name: str) -> list[dict]:
    """Every case the loop evaluates, in a stable order, tagged for Interface A.

    ``fixture_set`` is the visibility label used in visible-result rows
    (``public`` or ``held_out``); ``fixture_group`` names the source set.
    """
    return [dict(row, fixture_set='held_out' if group == 'held_out' else 'public', fixture_group=group)
            for group in FIXTURE_SETS for row in _fixture_set(name, group)]


def _finite_wall(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _trial_samples(result):
    trials = result.get('trial_wall_s')
    samples = list(trials) if isinstance(trials, list) and trials else [result.get('protected_wall_s')]
    if not samples or not all(_finite_wall(v) for v in samples):
        raise ValueError('Finite non-negative protected wall times required')
    return samples


def _noise_from_samples(samples, case_count):
    low, high = min(samples), max(samples)
    if low <= 0:
        raise ValueError('Positive parent wall times required for noise calibration')
    spread = (high - low) / low
    margin = max(MIN_MARGIN, spread)
    return {'schema': NOISE_SCHEMA, 'rule': RULE, 'samples': len(samples), 'case_count': case_count,
            'min_wall_s': low, 'median_wall_s': median(samples), 'max_wall_s': high,
            'relative_spread': spread, 'margin': margin, 'noise_floor_ratio': 1 / (1 + margin)}


def calibrate_noise(parent_trials: list[dict]) -> dict:
    """Noise floor from >=3 repeated parent visible results over the same cases."""
    if not isinstance(parent_trials, list) or len(parent_trials) < MIN_TRIALS:
        raise ValueError(f'At least {MIN_TRIALS} parent visible results are required to calibrate noise')
    counts = {_case_count(result) for result in parent_trials}
    if len(counts) != 1:
        raise ValueError('Noise calibration trials must cover the same cases')
    samples = [v for result in parent_trials for v in _trial_samples(result)]
    return _noise_from_samples(samples, counts.pop())


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _is_ref(value):
    return (isinstance(value, dict) and set(value) == {'id', 'sha256'} and isinstance(value['id'], str)
            and isinstance(value['sha256'], str) and len(value['sha256']) == 64)


def output_identity(row):
    """Digest of the exact bytes a case produced, or None when not carried.

    The Root receipt's ``stdout_ref`` pins the captured child output; the
    independent checker's ``output_sha256`` is the same digest when present.
    """
    receipt = row.get('receipt')
    if isinstance(receipt, dict) and _is_ref(receipt.get('stdout_ref')):
        return receipt['stdout_ref']['sha256']
    for source in (row.get('independent_check'), row):
        if isinstance(source, dict) and isinstance(source.get('output_sha256'), str):
            return source['output_sha256']
    return None


# ------------------------------------------------------- Interface E reports

def benchmark_workloads(report):
    rows = report.get('workloads', report.get('rows'))
    return rows if isinstance(rows, list) else None


def benchmark_gates(report):
    """Gate rows ``{gate, passed, threshold, value}``; a gate is a bool or a
    dict carrying ``passed`` (and optionally ``threshold``/``value``)."""
    out = []
    for name, gate in report['gates'].items():
        if type(gate) is bool:
            out.append({'gate': name, 'passed': gate, 'threshold': None, 'value': None})
        else:
            out.append({'gate': name, 'passed': gate['passed'], 'threshold': gate.get('threshold'),
                        'value': gate.get('value')})
    return out


def validate_benchmark_report(report, *, parent_sha256=None, candidate_sha256=None):
    """Closed reader of an Interface E report (Codex's paired batched shape)."""
    def need(condition, message):
        if not condition:
            raise ValueError(message)
    need(isinstance(report, dict) and report.get('schema') == BENCHMARK_REPORT_SCHEMA, 'BENCHMARK_REPORT_SCHEMA_REQUIRED')
    need(type(report.get('objective_met')) is bool, 'BENCHMARK_OBJECTIVE_MET_REQUIRED')
    need(type(report.get('correctness_passed', True)) is bool, 'BENCHMARK_CORRECTNESS_FLAG_REQUIRED')
    measured = report.get('correctness_passed', True)
    if measured:
        need(_positive(report.get('median_ratio')), 'BENCHMARK_MEDIAN_RATIO_REQUIRED')
        if 'relative_gain' in report:
            need(type(report['relative_gain']) in (int, float)
                 and math.isclose(report['relative_gain'], 1 - report['median_ratio'], abs_tol=1e-9),
                 'BENCHMARK_RELATIVE_GAIN_DIFFERS')
        interval = report.get('ratio_confidence_interval')
        need(isinstance(interval, list) and len(interval) == 2 and all(_positive(v) for v in interval)
             and interval[0] <= interval[1], 'BENCHMARK_CONFIDENCE_INTERVAL_REQUIRED')
    else:
        # Correctness failed inside the benchmark: Root stops timing, so no ratio exists.
        need(not report['objective_met'] and all(report.get(key) is None for key in (
            'median_ratio', 'relative_gain', 'ratio_confidence_interval')), 'UNMEASURED_BENCHMARK_HAS_NO_RATIO')
    rows = benchmark_workloads(report)
    need(rows is not None and len(rows) > 0, 'BENCHMARK_WORKLOADS_REQUIRED')
    ids = []
    for row in rows:
        need(isinstance(row, dict) and isinstance(row.get('id'), str)
             and (_positive(row.get('median_ratio')) if measured else row.get('median_ratio') is None)
             and type(row.get('regression', False)) is bool and type(row.get('withheld', False)) is bool,
             'BENCHMARK_WORKLOAD_ROW_REQUIRED')
        ids.append(row['id'])
    need(len(ids) == len(set(ids)), 'DUPLICATE_BENCHMARK_WORKLOAD')
    gates = report.get('gates')
    need(isinstance(gates, dict) and gates and all(
        type(gate) is bool or (isinstance(gate, dict) and type(gate.get('passed')) is bool) for gate in gates.values()),
        'BENCHMARK_GATES_REQUIRED')
    need(not report['objective_met'] or (all(row['passed'] for row in benchmark_gates(report))
         and report.get('correctness_passed', True) is True), 'BENCHMARK_OBJECTIVE_CONTRADICTS_GATES')
    need(type(report.get('protected_jobs')) is int and report['protected_jobs'] >= 0, 'BENCHMARK_PROTECTED_JOBS_REQUIRED')
    refs = report.get('evidence_refs')
    need(isinstance(refs, list) and all(_is_ref(ref) for ref in refs), 'BENCHMARK_EVIDENCE_REFS_REQUIRED')
    for key, expected in (('parent_sha256', parent_sha256), ('candidate_sha256', candidate_sha256)):
        if expected is not None and key in report:
            need(report[key] == expected, 'BENCHMARK_SUBJECT_DIFFERS')
    return report


def benchmark_timings(report):
    """Per-workload median parent/candidate seconds: explicit fields, else the
    median of the paired ``samples`` ([parent_s, candidate_s] per repetition)."""
    samples = report.get('samples') if isinstance(report.get('samples'), dict) else {}
    out = []
    for row in benchmark_workloads(report):
        parent_s, candidate_s = row.get('parent_median_s'), row.get('candidate_median_s')
        pairs = samples.get(row['id'])
        if not (_positive(parent_s) and _positive(candidate_s)) and isinstance(pairs, list) and pairs and all(
                isinstance(pair, list) and len(pair) == 2 and all(_positive(v) for v in pair) for pair in pairs):
            parent_s, candidate_s = median(p for p, _ in pairs), median(c for _, c in pairs)
        ratio = row.get('median_ratio')
        out.append({'id': row['id'], 'split': row['split'] if isinstance(row.get('split'), str) else 'visible',
                    'withheld': row.get('withheld', False) is True,
                    'median_ratio': ratio,
                    'relative_gain': None if ratio is None else 1 - ratio,
                    'regression': row.get('regression', ratio is not None and ratio > 1),
                    'parent_median_s': parent_s if _positive(parent_s) else None,
                    'candidate_median_s': candidate_s if _positive(candidate_s) else None,
                    'floor_s': row['floor_s'] if _positive(row.get('floor_s')) else None})
    return out


def benchmark_summary(report):
    """The decision-relevant, model-visible digest of a validated report."""
    gates = benchmark_gates(report)
    measured = report.get('correctness_passed', True) is True
    correctness = report.get('correctness') if isinstance(report.get('correctness'), dict) else {}
    cases = correctness.get('cases') if isinstance(correctness.get('cases'), list) else []
    failure = correctness.get('failure') if isinstance(correctness.get('failure'), dict) else None
    return {'schema': report['schema'], 'correctness_passed': measured,
            'median_ratio': report['median_ratio'] if measured else None,
            'relative_gain': 1 - report['median_ratio'] if measured else None,
            'ratio_confidence_interval': list(report['ratio_confidence_interval']) if measured else None,
            'objective_met': report['objective_met'], 'gates': gates,
            'failed_gates': [row['gate'] for row in gates if not row['passed']],
            # Parent failed the checker on a benchmark case, candidate passed it.
            'checker_improvements': sum(1 for case in cases if isinstance(case, dict) and case.get('improved') is True),
            'correctness_failure': None if failure is None else {
                key: failure.get(key) for key in ('kind', 'role', 'rule') if key in failure},
            'workloads': benchmark_timings(report), 'protected_jobs': report['protected_jobs']}


def _rows(result):
    rows = result.get('rows')
    if not isinstance(rows, list):
        raise ValueError('Visible result rows required')
    held = _held_out_ids(result.get('capsule_name'))
    out = {}
    for row in rows:
        ident = row.get('fixture_id')
        if not isinstance(ident, str) or ident in out:
            raise ValueError('Unique fixture ids required in visible result rows')
        visibility = row.get('fixture_set') or ('held_out' if ident in held else 'public')
        walls = row.get('trial_wall_s') if isinstance(row.get('trial_wall_s'), list) and row.get('trial_wall_s') else [row.get('protected_wall_s')]
        out[ident] = {'held_out': visibility == 'held_out', 'success': row.get('task_success') is True,
                      'wall': min(walls) if all(_finite_wall(w) for w in walls) else None,
                      'output_bytes': row.get('output_bytes') if type(row.get('output_bytes')) is int else None,
                      'identity': output_identity(row), 'error': row.get('error'), 'row': row}
    return out


def _held_out_ids(name):
    try:
        if registered_capsule(name).public_evaluation_available:
            return {row['id'] for row in _fixture_set(name, 'held_out')}
    except ValueError:
        pass
    return set()


def _public_expected(name):
    try:
        if registered_capsule(name).public_evaluation_available:
            return {row['id']: row['expected_task_output'] for group in ('public', 'public_extended')
                    for row in _fixture_set(name, group)}
    except ValueError:
        pass
    return {}


def _case_count(result):
    count = result.get('case_count')
    rows = result.get('rows') or []
    return max(count if type(count) is int else 0, len(rows))


def _fraction(passed, total):
    return passed / total if total else 0.0


def _short(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= VALUE_LIMIT else text[:VALUE_LIMIT - 3] + '...'


def _diff(expected, actual, path, out):
    if len(out) >= DIFF_PATHS:
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in list(expected) + [k for k in actual if k not in expected]:
            if key not in actual:
                out.append(f'{path}.{key}: missing (expected {_short(expected[key])})')
            elif key not in expected:
                out.append(f'{path}.{key}: unexpected key (actual {_short(actual[key])})')
            else:
                _diff(expected[key], actual[key], f'{path}.{key}', out)
            if len(out) >= DIFF_PATHS:
                return
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append(f'{path}: length expected {len(expected)}, actual {len(actual)}')
        for index, (left, right) in enumerate(zip(expected, actual)):
            _diff(left, right, f'{path}[{index}]', out)
            if len(out) >= DIFF_PATHS:
                return
    elif type(expected) is not type(actual) or expected != actual:
        out.append(f'{path}: expected {_short(expected)}, actual {_short(actual)}')


def _actual_output(row, output_key):
    if 'actual_task_output' in row:
        return True, row['actual_task_output']
    raw = row.get('output')
    if isinstance(raw, (bytes, str)) and output_key:
        try:
            data = json.loads(raw).get('data', {})
            return output_key in data, data.get(output_key)
        except (ValueError, AttributeError):
            return False, None
    return False, None


def _ids(ids):
    shown = ', '.join(ids[:ID_LIMIT])
    return '[' + shown + (f', ... +{len(ids) - ID_LIMIT} more' if len(ids) > ID_LIMIT else '') + ']'


def _ms(value):
    return f'{value * 1000:.1f} ms'


def _total_wall(result, noise=None):
    samples = _trial_samples(result)
    wall = min(samples)
    if noise and _finite_wall(noise.get('min_wall_s')) and noise.get('case_count') == _case_count(result):
        wall = min(wall, noise['min_wall_s'])
    return wall


def score(parent: dict, candidate: dict, *, noise: dict | None = None, benchmark: dict | None = None) -> dict:
    if not isinstance(parent, dict) or not isinstance(candidate, dict):
        raise ValueError('Parent and candidate visible results required')
    name = candidate.get('capsule_name') or parent.get('capsule_name')
    prows, crows = _rows(parent), _rows(candidate)
    order = list(prows) + [ident for ident in crows if ident not in prows]
    held = {ident for ident in order if (prows.get(ident) or crows.get(ident))['held_out']}
    p_total, c_total = _case_count(parent), _case_count(candidate)
    p_passed = {i for i, r in prows.items() if r['success']}
    c_passed = {i for i, r in crows.items() if r['success']}
    correctness = {'parent': _fraction(len(p_passed), p_total), 'candidate': _fraction(len(c_passed), c_total)}
    newly_failed = [i for i in order if i in p_passed and i not in c_passed]
    newly_passed = [i for i in order if i in c_passed and i not in p_passed]
    still_failing = [i for i in order if i not in c_passed and i not in p_passed]
    crashed = bool(candidate.get('failure')) and not parent.get('failure')
    # Correctness contract: where the parent passes, the parent's exact bytes
    # are the specification; the checker alone decides only where it fails.
    both = [i for i in order if i in p_passed and i in c_passed]
    compared = [i for i in both if prows[i]['identity'] is not None and crows[i]['identity'] is not None]
    changed_bytes = [i for i in compared if prows[i]['identity'] != crows[i]['identity']]
    contract = {'rule': CONTRACT_RULE, 'parent_passed': len(p_passed), 'byte_compared': len(compared),
                'changed_bytes': changed_bytes, 'unverified': [i for i in both if i not in compared],
                'newly_failed': newly_failed, 'checker_fixed': newly_passed}
    regressed = (bool(newly_failed) or bool(changed_bytes) or correctness['candidate'] < correctness['parent']
                 or crashed)

    if noise is None and len(parent.get('trial_wall_s') or []) >= MIN_TRIALS:
        noise = _noise_from_samples(_trial_samples(parent), p_total)
    floor = noise.get('noise_floor_ratio') if isinstance(noise, dict) else None
    floor = floor if type(floor) is float and 0 < floor < 1 else None

    latency_ratio, basis, bench = None, None, None
    if benchmark is not None:
        validate_benchmark_report(benchmark, parent_sha256=parent.get('subject_sha256'),
                                  candidate_sha256=candidate.get('subject_sha256'))
        bench = benchmark_summary(benchmark)
        method = LATENCY_BENCHMARK
        contract['benchmark_correctness_passed'] = bench['correctness_passed']
        contract['benchmark_correctness_failure'] = bench['correctness_failure']
        contract['benchmark_checker_improvements'] = bench['checker_improvements']
        if bench['correctness_passed']:
            latency_ratio = bench['median_ratio']
            basis = (f"paired batched benchmark: geomean of {len(bench['workloads'])} per-workload median ratios, "
                     f"{benchmark['protected_jobs']} protected jobs")
            above_noise = bench['objective_met']
            slower_above_noise = bench['ratio_confidence_interval'][0] > 1
        else:
            # The benchmark's own (parent-relative, checker-authoritative)
            # correctness gate failed on its workloads or semantic edges.
            regressed = True
            basis = 'paired batched benchmark stopped on a correctness failure'
            above_noise = slower_above_noise = False
    else:
        method = LATENCY_FLOOR
        same_cases = set(prows) == set(crows) and p_total == c_total and p_passed == c_passed
        if same_cases and not crashed:
            try:
                p_wall, c_wall = _total_wall(parent, noise), _total_wall(candidate)
            except ValueError:
                p_wall = c_wall = None
            if p_wall and c_wall is not None:
                latency_ratio, basis = c_wall / p_wall, 'total min-of-k over identical case outcomes'
        if latency_ratio is None:
            common = [i for i in order if i in p_passed and i in c_passed
                      and prows[i]['wall'] is not None and crows[i]['wall'] is not None]
            p_sum = sum(prows[i]['wall'] for i in common)
            if common and p_sum > 0:
                latency_ratio = sum(crows[i]['wall'] for i in common) / p_sum
                basis = f'per-case walls over {len(common)} cases both passed'
        above_noise = latency_ratio is not None and floor is not None and latency_ratio < floor
        slower_above_noise = latency_ratio is not None and floor is not None and latency_ratio > 1 / floor
    gained = correctness['candidate'] > correctness['parent']
    improved = not regressed and (gained or (correctness['candidate'] == correctness['parent'] and above_noise))

    def split(ids):
        return [i for i in ids if i not in held], [i for i in ids if i in held]

    def counts(passed, rows):
        return {'public': [sum(1 for i in rows if i not in held and i in passed), sum(1 for i in rows if i not in held)],
                'held_out': [sum(1 for i in rows if i in held and i in passed), sum(1 for i in rows if i in held)]}

    by_set = {'parent': counts(p_passed, prows), 'candidate': counts(c_passed, crows)}
    verdict = 'REGRESSED' if regressed else 'IMPROVED' if improved else 'NOT IMPROVED'
    if bench is not None and not bench['correctness_passed']:
        failure = bench['correctness_failure'] or {}
        timing = ('paired batched benchmark stopped: correctness failed (%s, rule %s)'
                  % (failure.get('kind'), failure.get('rule')))
    elif bench is not None:
        low, high = bench['ratio_confidence_interval']
        timing = (f"paired batched benchmark ratio {latency_ratio:.3f} (gain {bench['relative_gain']:+.1%}), "
                  f"95% CI [{low:.3f}, {high:.3f}], objective "
                  + ('met' if above_noise else 'not met (failed gates: ' + (', '.join(bench['failed_gates']) or 'correctness') + ')'))
    elif latency_ratio is None:
        timing = 'latency not comparable'
    elif floor is None:
        timing = f'latency ratio {latency_ratio:.3f} (noise uncalibrated; not counted)'
    else:
        timing = (f'latency ratio {latency_ratio:.3f} vs noise floor {floor:.3f} '
                  f"({'faster above noise' if above_noise else 'slower above noise' if slower_above_noise else 'within noise'})")
    summary = (f"{verdict}: correctness {len(c_passed)}/{c_total} vs parent {len(p_passed)}/{p_total}; {timing}")

    lines = [f'Objective {RULE}. Verdict: {summary}.',
             'Correctness (passed/total): candidate public {0[0]}/{0[1]}, held-out {1[0]}/{1[1]}; '
             'parent public {2[0]}/{2[1]}, held-out {3[0]}/{3[1]}.'.format(
                 by_set['candidate']['public'], by_set['candidate']['held_out'],
                 by_set['parent']['public'], by_set['parent']['held_out'])]
    if candidate.get('failure'):
        failure = candidate['failure']
        lines.append(f"Candidate evaluation failure: {failure.get('exception_type')}: {str(failure.get('message'))[:300]}")
    if changed_bytes:
        public_ids, held_ids = split(changed_bytes)
        lines.append(f'CONTRACT REGRESSIONS (parent passed; candidate output bytes differ from the parent although the '
                     f'checker accepts them): public {_ids(public_ids)}; held-out {len(held_ids)} opaque id(s) '
                     f'{_ids(held_ids)}. Preserve the parent output exactly where the parent passes.')
    for label, ids in (('REGRESSIONS (parent passed, candidate failed)', newly_failed),
                       ('Fixed by candidate', newly_passed), ('Still failing', still_failing)):
        public_ids, held_ids = split(ids)
        if public_ids or held_ids:
            lines.append(f'{label}: public {_ids(public_ids)}; held-out {len(held_ids)} opaque id(s) {_ids(held_ids)}.')
    missing = [i for i in order if i not in crows]
    if missing:
        public_ids, held_ids = split(missing)
        lines.append(f'Not executed by candidate (counted as failed): public {_ids(public_ids)}; held-out {len(held_ids)}.')
    if any(i in held for i in order if i not in c_passed):
        lines.append('Held-out inputs, expected outputs and error messages are withheld; improve the general behaviour, '
                     'not the visible cases.')

    expected = _public_expected(name)
    try:
        output_key = registered_capsule(name).task_output_key
    except ValueError:
        output_key = None
    details = []
    for ident in [i for i in order if i not in held and i in crows and i not in c_passed][:DIFF_CASES]:
        row = crows[ident]
        if row['error']:
            error = row['error']
            details.append(f"- {ident}: raised {error.get('exception_type')}: {str(error.get('message'))[:200]}")
            continue
        captured, actual = _actual_output(row['row'], output_key)
        if ident not in expected:
            details.append(f'- {ident}: failed (no public expected output on record)')
        elif not captured:
            details.append(f'- {ident}: failed; actual output not captured; expected {_short(expected[ident])}')
        else:
            paths = []
            _diff(expected[ident], actual, output_key or 'output', paths)
            details.append(f'- {ident}: ' + ('; '.join(paths) if paths else
                           'task output matches; packet envelope or unrelated data was not preserved exactly'))
    if details:
        lines.append('Public failure details (expected vs actual, bounded):')
        lines.extend(details)

    lines.append('Timing: ' + timing + (f' [{basis}]' if basis else '') + '.')
    deltas = [(i, prows[i]['wall'], crows[i]['wall']) for i in order
              if i in prows and i in crows and prows[i]['wall'] is not None and crows[i]['wall'] is not None]
    deltas.sort(key=lambda item: -abs(item[2] - item[1]))
    for ident, before, after in deltas[:TIMING_CASES]:
        change = f'{(after - before) / before * 100:+.1f}%' if before > 0 else 'n/a'
        lines.append(f'  {ident}: parent {_ms(before)} -> candidate {_ms(after)} ({change})')
    sizes = [(i, prows[i]['output_bytes'], crows[i]['output_bytes']) for i in order
             if i in prows and i in crows and prows[i]['output_bytes'] is not None and crows[i]['output_bytes'] is not None]
    if sizes:
        before, after = sum(s[1] for s in sizes), sum(s[2] for s in sizes)
        changed = [f'{i} {a - b:+d} B' for i, b, a in sizes if a != b][:TIMING_CASES]
        lines.append(f'Output size: candidate {after} B vs parent {before} B ({after - before:+d} B)'
                     + (f"; changed: {', '.join(changed)}" if changed else '; unchanged per case') + '.')
    feedback = '\n'.join(lines)
    if len(feedback) > FEEDBACK_LIMIT:
        marker = '\n[feedback truncated]'
        feedback = feedback[:FEEDBACK_LIMIT - len(marker)] + marker

    return {'correctness': correctness, 'latency_ratio': latency_ratio, 'noise_floor_ratio': floor,
            'above_noise': above_noise, 'improved': improved, 'regressed': regressed,
            'summary': summary, 'feedback': feedback,
            'rule': RULE, 'slower_above_noise': slower_above_noise, 'case_counts': by_set,
            'newly_passed': newly_passed, 'newly_failed': newly_failed,
            'latency_method': method, 'contract': contract, 'benchmark': bench}
