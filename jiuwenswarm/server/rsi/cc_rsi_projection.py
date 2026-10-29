"""Finite public CC workbench projection; no workbench or Root capabilities.

An installation publisher must deliberately disclose this closed public schema.
Never point this adapter at a workbench record root, history export or ledger.
The web process cannot enter library_operator (which requires OS root). Human
actions require a separately installed authenticated operator broker and remain
unavailable here until that protected integration exists.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

MAX_PUBLIC_BYTES = 2 * 1024 * 1024
HASH = re.compile(r"[a-f0-9]{64}")


class ProjectionError(ValueError):
    pass


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ProjectionError("Public projection has unsupported fields")


def _text(value, *, nullable=False, limit=4096):
    if nullable and value is None:
        return
    if not isinstance(value, str) or len(value) > limit:
        raise ProjectionError("Public text exceeds its finite contract")


def _hash(value, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ProjectionError("Exact candidate hash is required")


def _rows(value, limit):
    if not isinstance(value, list) or len(value) > limit:
        raise ProjectionError("Public collection exceeds its finite contract")
    return value


def _gate(value, *, revision=False):
    _fields(value, "allowed blocker revision" if revision and isinstance(value, dict) and 'revision' in value else "allowed blocker")
    if type(value["allowed"]) is not bool:
        raise ProjectionError("Invalid action gate")
    _text(value["blocker"], nullable=True)
    if 'revision' in value:
        _hash(value['revision'])


def _ref(value):
    _fields(value, "id sha256")
    _text(value["id"])
    _hash(value["sha256"])


# ---------------------------------------------------------------------------
# Improvement-loop lineage (Interface C ``loop`` -> closed public run lineage).
#
# A run row may carry an optional ``lineage`` block. Legacy rows (historical
# Screening, R1/R2 failure records) have no such key and are validated and
# served exactly as before; the UI labels them "single attempt (legacy)".
# Every value is copied from the session result or left ``None`` (unknown);
# nothing is defaulted to 0, success or "kept".
# ---------------------------------------------------------------------------
LOOP_SCHEMA = 'ai4r-rsi-capsule-loop:1'
LINEAGE_SCHEMA = 'ai4r-cc-rsi-lineage:1'
STOP_REASONS = frozenset({'max_iterations', 'no_progress', 'budget', 'deadline', 'error'})
BACKEND_KINDS = frozenset({'host-codex', 'fake', 'openai-compatible', 'anthropic'})
ITERATION_STATUSES = frozenset({'passed', 'failed', 'evaluation_failed', 'not_evaluated', 'unknown'})
MAX_ITERATIONS = 64
MAX_CASES = 256
LINEAGE_FIELDS = ('schema max_iterations completed_iterations stop_reason model_backend model_calls '
                  'parent_node_id best_iteration best_node_id parent iterations')
ITERATION_FIELDS = ('iteration node_id candidate_ref status kept best passed_count case_count '
                    'correctness_parent correctness_candidate latency_ratio noise_floor_ratio above_noise '
                    'improved regressed summary feedback rationale failing_cases failure model_calls elapsed_s')
TEXT_LIMITS = {'summary': 1024, 'feedback': 4096, 'rationale': 4096}

# Lineage v2 (merge wave): the paired batched benchmark is the latency judge.
# A v1 block (no benchmark data in the loop) is still emitted byte-identically.
LINEAGE_SCHEMA_V2 = 'ai4r-cc-rsi-lineage:2'
BENCHMARK_REPORT_SCHEMA = 'ai4r-rsi-capsule-benchmark-report:1'
LATENCY_METHODS = frozenset({'paired_batched_benchmark', 'single_job_floor'})
IMPROVEMENT_BASES = frozenset({'correctness', 'paired_batched_benchmark'})
BENCHMARK_GATES = ('minimum_gain', 'ci_upper_bound', 'max_workload_regression')
BENCHMARK_FIELDS = 'report_ref relative_gain ratio_confidence_interval gates objective_met protected_jobs repetitions workloads'
LINEAGE_V2_FIELDS = LINEAGE_FIELDS + ' benchmark_baseline benchmark_baseline_status'
ITERATION_V2_FIELDS = ITERATION_FIELDS + ' latency_method benchmark improvement_basis benchmark_status'
MAX_WORKLOADS = 64
# ``benchmark_baseline`` is the parent A/A run (candidate = parent): the
# benchmark's own self-noise on the host, never a candidate gain.
BASELINE_KINDS = frozenset({'parent_a_a'})
BASELINE_STATUSES = frozenset({'measured', 'skipped', 'failed'})
# Per-iteration benchmark decision: ``ran`` (report present) or why not.
BENCHMARK_STATUSES = frozenset({'ran', 'not_run', 'skipped'})


def _benchmark_status(value, statuses, *, kind=False):
    """``{status, reason}`` (``kind`` too for the baseline) or None when unrecorded."""
    if not isinstance(value, dict) or value.get('status') not in statuses:
        return None
    out = {'status': value['status'], 'reason': _clip(value.get('reason'), 256)}
    if kind:
        out = {'kind': value.get('kind') if value.get('kind') in BASELINE_KINDS else None, **out}
    return out


def _signed(value):
    """Finite signed measured number (a gain may be negative), else unknown."""
    if type(value) in (int, float) and math.isfinite(value) and -1e6 <= value <= 1e6:
        return value
    return None


def _gate_passed(value):
    """A gate is a bool or ``{..., passed: bool}``; anything else is unknown."""
    if isinstance(value, dict):
        value = value.get('passed')
    return value if type(value) is bool else None


def _interval(value):
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(_measure(item) is not None for item in value) and value[0] <= value[1]):
        return [value[0], value[1]]
    return None


def _workloads(value):
    """Per-workload median ratios: ``[{id, median_ratio}]`` or ``{id: ratio}``."""
    if isinstance(value, dict):
        value = [{'id': key, 'median_ratio': item if not isinstance(item, dict) else item.get('median_ratio')}
                 for key, item in value.items()]
    if not isinstance(value, list):
        return None
    rows = []
    for item in value[:MAX_WORKLOADS]:
        if isinstance(item, dict) and isinstance(item.get('id'), str):
            rows.append({'id': _clip(item['id'], 256), 'median_ratio': _measure(item.get('median_ratio'))})
    return rows


def _repetitions(report):
    reps = _count(report.get('repetitions'))
    if reps is None and isinstance(report.get('protocol'), dict):
        reps = _count(report['protocol'].get('repetitions'))
    return reps


def project_benchmark(report):
    """Closed public view of one ``ai4r-rsi-capsule-benchmark-report:1``."""
    if not isinstance(report, dict):
        return None
    gates = report.get('gates') if isinstance(report.get('gates'), dict) else {}
    return {'report_ref': _source_ref(report.get('report_ref')),
            'relative_gain': _signed(report.get('relative_gain')),
            'ratio_confidence_interval': _interval(report.get('ratio_confidence_interval')),
            'gates': {key: _gate_passed(gates.get(key)) for key in BENCHMARK_GATES},
            'objective_met': _flag(report.get('objective_met')),
            'protected_jobs': _count(report.get('protected_jobs')),
            'repetitions': _repetitions(report),
            'workloads': _workloads(report.get('workloads', report.get('rows')))}


def improvement_basis(score, method, benchmark, correctness_parent, correctness_candidate):
    """Why an ``improved`` score may be claimed, or None (no claim).

    A correctness gain always counts. A latency gain counts only when it was
    judged by the paired batched benchmark and that report met its objective;
    a ``single_job_floor`` latency is never a measured speedup.
    """
    if score.get('improved') is not True or score.get('regressed') is True:
        return None
    if (correctness_parent is not None and correctness_candidate is not None
            and correctness_candidate > correctness_parent):
        return 'correctness'
    if method == 'paired_batched_benchmark' and benchmark is not None and benchmark['objective_met'] is True:
        return 'paired_batched_benchmark'
    return None


def _uses_benchmark(loop):
    """A loop result from the merge wave (benchmark-judged or explicitly floor-judged)."""
    if 'benchmark_baseline' in loop:
        return True
    for row in loop.get('iterations') or []:
        if isinstance(row, dict) and ('benchmark' in row or (
                isinstance(row.get('score'), dict) and 'latency_method' in row['score'])):
            return True
    return False


def _measure(value):
    """Finite non-negative measured number, else unknown."""
    if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1e12:
        return value
    return None


def _count(value):
    return value if type(value) is int and 0 <= value <= 1_000_000 else None


def _flag(value):
    return value if type(value) is bool else None


def _clip(value, limit):
    if not isinstance(value, str):
        return None
    if len(value) <= limit:
        return value
    marker = ' …[truncated]'
    return value[:limit - len(marker)] + marker


def _digest(value):
    return value if isinstance(value, str) and HASH.fullmatch(value) else None


def _source_ref(ref, sha=None):
    """Interface C allows a ref dict {id, sha256} or a str id plus candidate_sha256."""
    if isinstance(ref, dict):
        ident, digest = ref.get('id'), _digest(ref.get('sha256'))
    else:
        ident, digest = ref, _digest(sha)
    if isinstance(ident, str) and 0 < len(ident) <= 4096 and digest is not None:
        if sha is not None and _digest(sha) not in (None, digest):
            raise ProjectionError('Iteration candidate hash differs from its source ref')
        return {'id': ident, 'sha256': digest}
    return None


def _visible_summary(visible):
    if not isinstance(visible, dict):
        return None, None, 'not_evaluated', None, None
    passed, total = _count(visible.get('passed_count')), _count(visible.get('case_count'))
    failure = visible.get('failure')
    projected_failure = None
    if isinstance(failure, dict):
        projected_failure = {'exception_type': _clip(failure.get('exception_type'), 128),
                             'message': _clip(failure.get('message'), 1024)}
    if projected_failure is not None:
        status = 'evaluation_failed'
    elif passed is None or total is None or passed > total:
        status = 'unknown'
    else:
        status = 'passed' if passed == total else 'failed'
    cases = None
    rows = visible.get('rows')
    if isinstance(rows, list):
        cases = []
        for row in rows[:MAX_CASES]:
            if isinstance(row, dict) and row.get('task_success') is False and isinstance(row.get('fixture_id'), str):
                fixture_set = row.get('fixture_set')
                cases.append({'id': _clip(row['fixture_id'], 256),
                              'fixture_set': fixture_set if fixture_set in ('public', 'held_out') else None})
    return passed, total, status, cases, projected_failure


def _project_iteration(row, *, best_iteration, node_ids, version=1):
    if not isinstance(row, dict) or _count(row.get('iteration')) is None:
        raise ProjectionError('Loop iteration identity is required')
    score = row.get('score') if isinstance(row.get('score'), dict) else {}
    correctness = score.get('correctness') if isinstance(score.get('correctness'), dict) else {}
    ref = _source_ref(row.get('candidate_ref'), row.get('candidate_sha256'))
    passed, total, status, cases, failure = _visible_summary(row.get('visible'))
    node_id = node_ids.get(ref['sha256']) if ref is not None else None
    value = _project_iteration_v1(row, score, correctness, ref, passed, total, status, cases, failure,
                                  node_id=node_id, best_iteration=best_iteration)
    if version == 1:
        return value
    method = score.get('latency_method') if score.get('latency_method') in LATENCY_METHODS else None
    benchmark = project_benchmark(row.get('benchmark'))
    return dict(value, latency_method=method, benchmark=benchmark,
                improvement_basis=improvement_basis(score, method, benchmark,
                                                    value['correctness_parent'], value['correctness_candidate']),
                benchmark_status=_benchmark_status(row.get('benchmark_decision'), BENCHMARK_STATUSES))


def _project_iteration_v1(row, score, correctness, ref, passed, total, status, cases, failure, *,
                          node_id, best_iteration):
    return {'iteration': row['iteration'], 'node_id': node_id, 'candidate_ref': ref, 'status': status,
            'kept': _flag(row.get('kept')), 'best': best_iteration is not None and row['iteration'] == best_iteration,
            'passed_count': passed, 'case_count': total,
            'correctness_parent': _measure(correctness.get('parent')),
            'correctness_candidate': _measure(correctness.get('candidate')),
            'latency_ratio': _measure(score.get('latency_ratio')),
            'noise_floor_ratio': _measure(score.get('noise_floor_ratio')),
            'above_noise': _flag(score.get('above_noise')), 'improved': _flag(score.get('improved')),
            'regressed': _flag(score.get('regressed')),
            'summary': _clip(score.get('summary'), TEXT_LIMITS['summary']),
            'feedback': _clip(score.get('feedback'), TEXT_LIMITS['feedback']),
            'rationale': _clip(row.get('rationale'), TEXT_LIMITS['rationale']),
            'failing_cases': cases, 'failure': failure,
            'model_calls': _count(row.get('model_calls')), 'elapsed_s': _measure(row.get('elapsed_s'))}


def project_loop(result, *, node_ids=None, parent_node_id=None):
    """Project an Interface C session result's ``loop`` block for publication.

    Returns ``None`` for a legacy single-attempt result (no ``loop`` block), so
    the caller leaves the run row byte-identical. ``node_ids`` maps a published
    candidate sha256 to the node id the publisher created for it; an iteration
    whose candidate was not captured keeps ``node_id: None`` but still shows
    its score, feedback and source ref. Missing measurements stay ``None``.
    """
    if not isinstance(result, dict) or result.get('loop') is None:
        return None
    loop = result['loop']
    if not isinstance(loop, dict) or loop.get('schema') != LOOP_SCHEMA:
        raise ProjectionError('Unsupported improvement loop schema')
    node_ids = dict(node_ids or {})
    rows = loop.get('iterations')
    if not isinstance(rows, list) or len(rows) > MAX_ITERATIONS:
        raise ProjectionError('Loop iterations exceed their finite contract')
    version = 2 if _uses_benchmark(loop) else 1
    best = loop.get('best') if isinstance(loop.get('best'), dict) else None
    best_iteration = _count(best.get('iteration')) if best else None
    iterations = [_project_iteration(row, best_iteration=best_iteration, node_ids=node_ids, version=version)
                  for row in rows]
    best_row = next((row for row in iterations if row['best']), None)
    if best is not None and best_row is not None:
        best_ref = _source_ref(best.get('candidate_ref'))
        if best_ref is not None and best_row['candidate_ref'] is not None and best_ref['sha256'] != best_row['candidate_ref']['sha256']:
            raise ProjectionError('Best candidate differs from its iteration')
    backend = loop.get('model_backend')
    if isinstance(backend, dict):
        backend = {'kind': backend.get('kind') if backend.get('kind') in BACKEND_KINDS else None,
                   'model': _clip(backend.get('model'), 256), 'pinned_sha256': _digest(backend.get('pinned_sha256'))}
    else:
        backend = None
    calls = _count(result.get('model_calls'))
    if calls is None and iterations and all(row['model_calls'] is not None for row in iterations):
        calls = sum(row['model_calls'] for row in iterations)
    parent_passed, parent_total, parent_status, _, parent_failure = _visible_summary(loop.get('parent_visible'))
    parent_visible = loop.get('parent_visible') if isinstance(loop.get('parent_visible'), dict) else {}
    stop = loop.get('stop_reason')
    value = {'schema': LINEAGE_SCHEMA, 'max_iterations': _count(loop.get('max_iterations')),
             'completed_iterations': _count(loop.get('completed_iterations')),
             'stop_reason': stop if stop in STOP_REASONS else None, 'model_backend': backend,
             'model_calls': calls, 'parent_node_id': parent_node_id,
             'best_iteration': best_row['iteration'] if best_row else None,
             'best_node_id': best_row['node_id'] if best_row else None,
             'parent': {'status': parent_status, 'passed_count': parent_passed, 'case_count': parent_total,
                        'protected_wall_s': _measure(parent_visible.get('protected_wall_s')), 'failure': parent_failure},
             'iterations': iterations}
    if version == 2:
        value['schema'] = LINEAGE_SCHEMA_V2
        value['benchmark_baseline'] = project_benchmark(loop.get('benchmark_baseline'))
        value['benchmark_baseline_status'] = _benchmark_status(loop.get('benchmark_baseline_status'),
                                                               BASELINE_STATUSES, kind=True)
    _lineage(value)
    return value


def _benchmark(value):
    if value is None:
        return
    _fields(value, BENCHMARK_FIELDS)
    if value['report_ref'] is not None:
        _ref(value['report_ref'])
    gain = value['relative_gain']
    if gain is not None and (type(gain) not in (int, float) or not math.isfinite(gain) or not -1e6 <= gain <= 1e6):
        raise ProjectionError('Invalid measured benchmark gain')
    interval = value['ratio_confidence_interval']
    if interval is not None:
        if not isinstance(interval, list) or len(interval) != 2:
            raise ProjectionError('Benchmark confidence interval must be a pair')
        for item in interval:
            _nullable_number(item)
            if item is None:
                raise ProjectionError('Benchmark confidence interval must be measured')
        if interval[0] > interval[1]:
            raise ProjectionError('Benchmark confidence interval is inverted')
    _fields(value['gates'], ' '.join(BENCHMARK_GATES))
    for item in value['gates'].values():
        _nullable_flag(item)
    _nullable_flag(value['objective_met'])
    _nullable_count(value['protected_jobs']); _nullable_count(value['repetitions'])
    if value['workloads'] is not None:
        for row in _rows(value['workloads'], MAX_WORKLOADS):
            _fields(row, 'id median_ratio')
            _text(row['id'], limit=256)
            _nullable_number(row['median_ratio'])


def _nullable_number(value):
    if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0 or value > 1e12):
        raise ProjectionError('Invalid measured lineage value')


def _nullable_count(value):
    if value is not None and (type(value) is not int or value < 0):
        raise ProjectionError('Lineage count must be a measured integer')


def _nullable_flag(value):
    if value is not None and type(value) is not bool:
        raise ProjectionError('Lineage flag must be measured')


def _failure(value):
    if value is not None:
        _fields(value, 'exception_type message')
        _text(value['exception_type'], nullable=True, limit=128)
        _text(value['message'], nullable=True, limit=1024)


def _lineage(value, *, run=None, nodes=None):
    """Closed public lineage block; node references are checked when nodes are known."""
    v2 = isinstance(value, dict) and value.get('schema') == LINEAGE_SCHEMA_V2
    _fields(value, LINEAGE_V2_FIELDS if v2 else LINEAGE_FIELDS)
    if value['schema'] not in (LINEAGE_SCHEMA, LINEAGE_SCHEMA_V2):
        raise ProjectionError('Unsupported public lineage schema')
    if v2:
        _benchmark(value['benchmark_baseline'])
        status = value['benchmark_baseline_status']
        if status is not None:
            _fields(status, 'kind status reason')
            if status['kind'] is not None and status['kind'] not in BASELINE_KINDS:
                raise ProjectionError('Unknown benchmark baseline kind')
            if status['status'] not in BASELINE_STATUSES:
                raise ProjectionError('Unknown benchmark baseline status')
            _text(status['reason'], nullable=True, limit=256)
        if value['benchmark_baseline'] is not None and (status is None or status['status'] != 'measured'):
            raise ProjectionError('A published A/A baseline must be recorded as measured')
    for key in ('max_iterations', 'completed_iterations', 'model_calls', 'best_iteration'):
        _nullable_count(value[key])
    if value['stop_reason'] is not None and value['stop_reason'] not in STOP_REASONS:
        raise ProjectionError('Unknown loop stop reason')
    backend = value['model_backend']
    if backend is not None:
        _fields(backend, 'kind model pinned_sha256')
        if backend['kind'] is not None and backend['kind'] not in BACKEND_KINDS:
            raise ProjectionError('Unknown model backend kind')
        _text(backend['model'], nullable=True, limit=256)
        _hash(backend['pinned_sha256'], nullable=True)
    for key in ('parent_node_id', 'best_node_id'):
        _text(value[key], nullable=True)
    parent = value['parent']
    _fields(parent, 'status passed_count case_count protected_wall_s failure')
    if parent['status'] not in ITERATION_STATUSES:
        raise ProjectionError('Unknown parent evaluation status')
    _nullable_count(parent['passed_count']); _nullable_count(parent['case_count'])
    _nullable_number(parent['protected_wall_s']); _failure(parent['failure'])
    seen, best = set(), []
    for row in _rows(value['iterations'], MAX_ITERATIONS):
        _fields(row, ITERATION_V2_FIELDS if v2 else ITERATION_FIELDS)
        if v2:
            if row['latency_method'] is not None and row['latency_method'] not in LATENCY_METHODS:
                raise ProjectionError('Unknown latency method')
            _benchmark(row['benchmark'])
            decision = row['benchmark_status']
            if decision is not None:
                _fields(decision, 'status reason')
                if decision['status'] not in BENCHMARK_STATUSES:
                    raise ProjectionError('Unknown iteration benchmark status')
                _text(decision['reason'], nullable=True, limit=256)
                if (decision['status'] == 'ran') is not (row['benchmark'] is not None):
                    raise ProjectionError('Iteration benchmark status differs from its report')
            basis = row['improvement_basis']
            if basis is not None and (basis not in IMPROVEMENT_BASES or row['improved'] is not True
                                      or row['regressed'] is True):
                raise ProjectionError('Improvement basis requires an improved, non-regressed score')
            if basis == 'paired_batched_benchmark' and (
                    row['latency_method'] != 'paired_batched_benchmark' or row['benchmark'] is None
                    or row['benchmark']['objective_met'] is not True):
                raise ProjectionError('A measured speedup requires a met paired benchmark objective')
            if basis == 'correctness' and not (
                    row['correctness_parent'] is not None and row['correctness_candidate'] is not None
                    and row['correctness_candidate'] > row['correctness_parent']):
                raise ProjectionError('A correctness improvement requires a measured correctness gain')
        if type(row['iteration']) is not int or row['iteration'] < 0 or row['iteration'] in seen:
            raise ProjectionError('Distinct iteration numbers are required')
        seen.add(row['iteration'])
        _text(row['node_id'], nullable=True)
        if row['candidate_ref'] is not None:
            _ref(row['candidate_ref'])
        elif row['node_id'] is not None:
            raise ProjectionError('Iteration node requires its exact candidate ref')
        if row['status'] not in ITERATION_STATUSES:
            raise ProjectionError('Unknown iteration status')
        if type(row['best']) is not bool:
            raise ProjectionError('Best flag must be explicit')
        if row['best']:
            best.append(row)
        for key in ('kept', 'above_noise', 'improved', 'regressed'):
            _nullable_flag(row[key])
        for key in ('passed_count', 'case_count', 'model_calls'):
            _nullable_count(row[key])
        for key in ('correctness_parent', 'correctness_candidate', 'latency_ratio', 'noise_floor_ratio', 'elapsed_s'):
            _nullable_number(row[key])
        for key, limit in TEXT_LIMITS.items():
            _text(row[key], nullable=True, limit=limit)
        if row['failing_cases'] is not None:
            for case in _rows(row['failing_cases'], MAX_CASES):
                _fields(case, 'id fixture_set')
                _text(case['id'], limit=256)
                if case['fixture_set'] not in (None, 'public', 'held_out'):
                    raise ProjectionError('Unknown fixture set')
        _failure(row['failure'])
        if nodes is not None and row['node_id'] is not None:
            node = nodes.get(row['node_id'])
            if (node is None or node['hash'] != row['candidate_ref']['sha256']
                    or node['run_id'] != run['id'] or node['target_id'] != run['target_id']):
                raise ProjectionError('Iteration candidate node differs')
    if len(best) > 1 or (value['best_iteration'] is None) != (not best) or (
            best and (best[0]['iteration'] != value['best_iteration'] or best[0]['node_id'] != value['best_node_id'])):
        raise ProjectionError('Exactly the declared best iteration may carry the best flag')
    if value['best_iteration'] is None and value['best_node_id'] is not None:
        raise ProjectionError('Best node requires a best iteration')
    if nodes is not None and value['parent_node_id'] is not None:
        parent_node = nodes.get(value['parent_node_id'])
        if parent_node is None or parent_node['target_id'] != run['target_id']:
            raise ProjectionError('Loop parent node differs')
    return value


def validate_publication(value, *, workspace_id=None):
    """Reject accidental private/raw fields instead of recursively forwarding JSON."""
    scoped = isinstance(value, dict) and 'workspace_id' in value
    _fields(value, "workspace_id snapshot candidates" if scoped else "snapshot candidates")
    if scoped:
        _text(value['workspace_id'], limit=256)
        if not value['workspace_id']:
            raise ProjectionError('Public workspace identity is required')
    if workspace_id is not None and (not scoped or value['workspace_id'] != workspace_id):
        raise ProjectionError('Public workspace differs from fixed startup workspace')
    view = value["snapshot"]
    _fields(view, "schema_version revision generated_at availability blocker targets runs nodes")
    if view["schema_version"] != "1":
        raise ProjectionError("Unsupported CC publication version")
    for key in ("revision", "availability"):
        _text(view[key])
    for key in ("generated_at", "blocker"):
        _text(view[key], nullable=True)
    targets = {}
    for row in _rows(view["targets"], 64):
        _fields(row, "id name parent_hash active_hash run")
        for key in ("id", "name"):
            _text(row[key])
        _hash(row["parent_hash"], nullable=True)
        _hash(row["active_hash"], nullable=True)
        _gate(row["run"], revision=True)
        if row["id"] in targets:
            raise ProjectionError("Duplicate target")
        targets[row["id"]] = row
    runs = {}
    for row in _rows(view["runs"], 256):
        # ``lineage`` is optional: legacy single-attempt rows stay exactly as published.
        _fields(row, "id target_id stage status blockers budget activity" + (" lineage" if isinstance(row, dict) and "lineage" in row else ""))
        for key in ("id", "target_id", "stage", "status"):
            _text(row[key])
        if row["target_id"] not in targets or row["id"] in runs:
            raise ProjectionError("Run target or identity is unavailable")
        runs[row["id"]] = row
        for blocker in _rows(row["blockers"], 64):
            _text(blocker)
        budget = row["budget"]
        _fields(budget, "elapsed_seconds limit_seconds setup_calls diagnosis_calls proposal_calls generation_call_limit cost currency")
        for key, number in budget.items():
            if key == "currency":
                _text(number, nullable=True, limit=16)
            elif number is not None and (type(number) not in (int, float) or not math.isfinite(number) or number < 0 or number > 1e12):
                raise ProjectionError("Invalid measured budget")
            elif key.endswith('calls') or key == 'generation_call_limit':
                if number is not None and type(number) is not int:
                    raise ProjectionError("Call count must be a measured integer")
        for event in _rows(row["activity"], 512):
            _fields(event, "id at stage status summary")
            for item in event.values():
                _text(item)
    nodes = {}
    for row in _rows(view["nodes"], 512):
        fields = "id target_id run_id parent_id hash label evaluation_status admission_status activation_status correctness speed noise evidence_refs operator_receipts admit activate"
        if scoped or 'security_status' in row:
            fields += ' security_status'
        _fields(row, fields)
        security = row.get('security_status')
        if security is not None:
            _text(security, limit=64)
        if security is not None and security not in {'NOT_APPLICABLE', 'UNQUALIFIED', 'SECURITY_DEFERRED', 'QUALIFIED'}:
            raise ProjectionError('Unsupported capsule security status')
        generated = row['parent_id'] is not None or row['run_id'] is not None
        if generated and security == 'NOT_APPLICABLE':
            raise ProjectionError('Generated capsules require a security disposition')
        for key in ("id", "target_id", "label", "evaluation_status", "admission_status", "activation_status"):
            _text(row[key])
        for key in ("run_id", "parent_id", "correctness", "speed", "noise"):
            _text(row[key], nullable=True)
        _hash(row["hash"])
        if row["id"] in nodes or row["target_id"] not in targets:
            raise ProjectionError("Candidate target or identity is unavailable")
        if row["run_id"] is not None and (row["run_id"] not in runs or runs[row["run_id"]]["target_id"] != row["target_id"]):
            raise ProjectionError("Candidate run differs")
        for ref in _rows(row["evidence_refs"], 128):
            _ref(ref)
        for receipt in _rows(row['operator_receipts'], 64):
            _fields(receipt, 'action actor at receipt_ref')
            if receipt['action'] not in ('admit', 'activate'):
                raise ProjectionError('Unknown human receipt action')
            _text(receipt['actor']); _text(receipt['at']); _ref(receipt['receipt_ref'])
        _gate(row["admit"])
        _gate(row["activate"])
        if generated and security in {'UNQUALIFIED', 'SECURITY_DEFERRED'} and (
                row['admission_status'] != 'unadmitted' or row['activation_status'] != 'inactive'
                or row['operator_receipts'] or row['admit']['allowed'] or row['activate']['allowed']):
            raise ProjectionError('Unqualified development capsules cannot claim Library standing')
        nodes[row["id"]] = row
    for row in nodes.values():
        if row["parent_id"] is not None and (row["parent_id"] not in nodes or nodes[row["parent_id"]]["target_id"] != row["target_id"]):
            raise ProjectionError("Candidate parent differs")
        seen = {row["id"]}
        current = row
        while current["parent_id"] is not None:
            current = nodes[current["parent_id"]]
            if current["id"] in seen:
                raise ProjectionError("Capsule lineage is cyclic")
            seen.add(current["id"])
    for row in runs.values():
        if "lineage" in row:
            _lineage(row["lineage"], run=row, nodes=nodes)
    captured = set()
    for row in _rows(value["candidates"], 512):
        _fields(row, "node_id candidate_hash path parent_code candidate_code rationale blocker")
        for key in ("node_id", "path"):
            _text(row[key])
        _hash(row["candidate_hash"])
        if row["node_id"] in captured or row["node_id"] not in nodes or nodes[row["node_id"]]["hash"] != row["candidate_hash"]:
            raise ProjectionError("Captured candidate identity differs")
        captured.add(row["node_id"])
        for key in ("parent_code", "candidate_code"):
            _text(row[key], nullable=True, limit=262144)
        if row["candidate_code"] is not None and hashlib.sha256(row["candidate_code"].encode("utf-8")).hexdigest() != row["candidate_hash"]:
            raise ProjectionError("Captured candidate bytes differ from exact hash")
        parent_id = nodes[row['node_id']]['parent_id']
        parent_hash = nodes[parent_id]['hash'] if parent_id else row['candidate_hash']
        if row['parent_code'] is not None and hashlib.sha256(row['parent_code'].encode('utf8')).hexdigest() != parent_hash:
            raise ProjectionError('Captured parent bytes differ from lineage hash')
        for key in ("rationale", "blocker"):
            _text(row[key], nullable=True)
    return value


def unavailable(reason):
    return {"schema_version": "1", "revision": "unavailable", "generated_at": None,
            "availability": "BLOCKED", "blocker": reason, "targets": [], "runs": [], "nodes": []}


def _root_ancestors(path):
    for parent in path.parents:
        meta = parent.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ProjectionError('Public CC publication ancestry custody differs')


def _readonly_mount(path, text):
    if len(text.encode('utf8')) > 1024 * 1024:
        return False
    wanted = PurePosixPath(str(path))
    covering = []
    for line in text.splitlines():
        fields = line.split(' - ', 1)[0].split()
        if len(fields) < 6:
            return False
        mount = PurePosixPath(re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), fields[4]))
        if mount == wanted or mount in wanted.parents:
            covering.append((len(mount.parts), fields[5].split(','), mount))
    if not covering:
        return False
    depth = max(row[0] for row in covering)
    matches = [(flags, mount) for size, flags, mount in covering if size == depth]
    return (len(matches) == 1 and matches[0][1] in {wanted, wanted.parent}
            and 'ro' in matches[0][0] and 'rw' not in matches[0][0])


class CcRsiProjection:
    def __init__(self, publication_path=None, *, workspace_id=None):
        self.path = publication_path
        self.workspace_id = workspace_id if workspace_id is not None else os.environ.get('JIUWENSWARM_CC_RSI_WORKSPACE')

    def _read(self):
        if not self.path:
            raise ProjectionError("Public CC publisher is not installed. Protected runtime records are not browser-readable.")
        _text(self.workspace_id, limit=256)
        if not self.workspace_id:
            raise ProjectionError('Fixed startup CC workspace is not configured')
        path = Path(self.path)
        if not path.is_absolute() or '..' in path.parts:
            raise ProjectionError("Public CC publication path must be absolute")
        # Installed Linux publisher owns this file; web process has read-only
        # access. Refuse symlinks, hardlinks and app-writable publications.
        if os.name != "posix":
            raise ProjectionError("Protected public CC publisher requires the installed Unix runtime")
        _root_ancestors(path)
        if not _readonly_mount(path, Path('/proc/self/mountinfo').read_text(encoding='utf8')):
            raise ProjectionError('Public CC publication requires an explicit read-only mount')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_uid != 0 or meta.st_mode & 0o022 or meta.st_size > MAX_PUBLIC_BYTES:
                raise ProjectionError("Public CC publication custody differs")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_PUBLIC_BYTES + 1)
            if len(raw) > MAX_PUBLIC_BYTES:
                raise ProjectionError("Public CC publication exceeds finite limit")
            return validate_publication(json.loads(raw), workspace_id=self.workspace_id)
        finally:
            os.close(fd)

    def snapshot(self, params):
        try:
            view = self._read()["snapshot"]
        except ProjectionError as error:
            return unavailable(str(error))
        except OSError:
            return unavailable("Public CC publication cannot be read. Check the installed read-only mount and app file permissions.")
        except ValueError:
            return unavailable("Public CC publication is invalid. Republish the approved finite view; no private records were exposed.")
        # Publication cannot grant web actions. An installed broker must first
        # authenticate the human and independently rerun the real Library gates.
        for row in view["targets"]:
            row["run"] = {"allowed": False, "blocker": "Authenticated finite run broker is not installed."}
        for row in view["nodes"]:
            for action in ("admit", "activate"):
                row[action] = {"allowed": False, "blocker": "Authenticated human operator broker is not installed."}
        return view

    def candidate(self, params):
        if set(params) - {"node_id", "candidate_hash", "session_id", "_rsi_session_id"}:
            raise ProjectionError("Only an exact candidate identity may be requested")
        _text(params.get("node_id"))
        _hash(params.get("candidate_hash"))
        publication = self._read()
        for row in publication["candidates"]:
            if row["node_id"] == params["node_id"] and row["candidate_hash"] == params["candidate_hash"]:
                return row
        raise ProjectionError("Captured code for this exact candidate is unavailable")

    def operator_action(self, params):
        raise ProjectionError("Authenticated human operator broker is not installed. Use the protected finite Library operator; the web process cannot assume OS root.")

    def run_start(self, params):
        raise ProjectionError("Authenticated finite run broker is not installed. No model call was made.")
