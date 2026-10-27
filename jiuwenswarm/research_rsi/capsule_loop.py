"""Iterative whole-capsule improvement loop (diagnose -> propose -> evaluate -> keep-best).

The loop is general over registered capsules: it never names a capsule, case
or answer. Each iteration issues exactly one governed diagnosis call and (when
the diagnosis is usable) one governed proposal call through fresh
``BoundedDiagnosis`` / ``GuardedProposer`` instances, so every prompt, raw
response, candidate byte string, visible result and score is captured in the
store exactly like the historical single attempt. Captured-but-invalid
responses reject only that iteration; unknown effects (no response, uncertain
containment, evaluator failure) stop the loop. Nothing is ever retried.

Evaluation goes through ``runtime.evaluate`` (Interface A) and scoring through
``targets.capsule_objective`` (Interface B). Held-out rows reach the model only
as case ids with pass/fail plus whatever the objective's ``feedback`` discloses.
"""
from __future__ import annotations

import json
import math
import time

from .diagnosis import BoundedDiagnosis
from .profiles import Limits
from .proposer import GuardedProposer, proposal_context
from .records import encoded
from .targets.capsules import public_fixtures
from .targets.capsule_executor import BINDING_SCHEMA, pin, validate_candidate_binding

LOOP_SCHEMA = 'ai4r-rsi-capsule-loop:1'
ITERATION_SCHEMA = 'ai4r-rsi-capsule-loop-iteration:1'
FEEDBACK_SCHEMA = 'ai4r-rsi-capsule-loop-feedback:1'
MODEL_VIEW_SCHEMA = 'ai4r-rsi-capsule-loop-model-view:1'
VISIBLE_V1 = 'ai4r-rsi-whole-capsule-visible-result:1'
VISIBLE_V2 = 'ai4r-rsi-whole-capsule-visible-result:2'
STOP_REASONS = ('max_iterations', 'no_progress', 'budget', 'deadline', 'error')
MAX_BODY_BYTES = 256 * 1024
MAX_FEEDBACK_CHARS = 16 * 1024
MAX_CHECK_BYTES = 1536
HISTORY_WINDOW = 5
DEFAULTS = {'max_iterations': 5, 'max_no_progress': 3, 'trials': 3, 'per_call_s': 120}
CEILINGS = {'max_iterations': 50, 'max_no_progress': 50, 'trials': 20, 'wall_s': 3600,
            'per_call_s': 300, 'max_model_calls': 100}
CONTRACT_KEYS = ('diagnosis_contract_ref', 'proposal_contract_ref')


def need(condition, message):
    if not condition:
        raise ValueError(message)


class LoopStop(Exception):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


# --------------------------------------------------------------- configuration

def _limit(value, key, default, low=1):
    item = value.get(key, default)
    need(type(item) is int and low <= item <= CEILINGS[key], 'FINITE_LOOP_' + key.upper() + '_REQUIRED')
    return item


def validate_loop_configuration(value, session):
    """Closed ``session['loop']``; inner fields default, the backend never does."""
    from .model_backends import validate_backend_configuration
    allowed = {'model_backend', 'max_iterations', 'max_no_progress', 'trials', 'wall_s',
               'per_call_s', 'max_model_calls', 'max_executions', 'contracts'}
    need(isinstance(value, dict) and set(value) <= allowed, 'CLOSED_LOOP_CONFIGURATION_REQUIRED')
    need('model_backend' in value, 'EXPLICIT_MODEL_BACKEND_REQUIRED')
    backend = validate_backend_configuration(value['model_backend'])
    grant = session['grant']
    grant_wall = grant.get('limits', {}).get('wall_s', CEILINGS['wall_s'])
    iterations = _limit(value, 'max_iterations', DEFAULTS['max_iterations'])
    wall = _limit(value, 'wall_s', min(CEILINGS['wall_s'], grant_wall))
    result = {'model_backend': backend, 'max_iterations': iterations,
              'max_no_progress': _limit(value, 'max_no_progress', DEFAULTS['max_no_progress']),
              'trials': _limit(value, 'trials', DEFAULTS['trials']), 'wall_s': wall,
              'per_call_s': _limit(value, 'per_call_s', min(DEFAULTS['per_call_s'], wall)),
              'max_model_calls': _limit(value, 'max_model_calls', min(CEILINGS['max_model_calls'], 2 * iterations), low=2),
              'max_executions': None, 'contracts': [], 'source': 'session'}
    # Noise calibration needs at least three parent trials (Interface B).
    result['parent_trials'] = max(3, result['trials'])
    need(result['per_call_s'] <= result['wall_s'], 'CONSISTENT_LOOP_LIMITS_REQUIRED')
    if 'max_executions' in value:
        need(type(value['max_executions']) is int and value['max_executions'] > 0, 'FINITE_LOOP_MAX_EXECUTIONS_REQUIRED')
        result['max_executions'] = value['max_executions']
    contracts = value.get('contracts', [])
    need(isinstance(contracts, list) and len(contracts) < CEILINGS['max_iterations'], 'BOUNDED_LOOP_CONTRACTS_REQUIRED')
    seen = {encoded(session[key]) for key in CONTRACT_KEYS}
    for row in contracts:
        need(isinstance(row, dict) and set(row) == set(CONTRACT_KEYS), 'CLOSED_ITERATION_CONTRACT_PAIR_REQUIRED')
        for key in CONTRACT_KEYS:
            pin(row[key])
            need(encoded(row[key]) not in seen, 'DISTINCT_ITERATION_CONTRACTS_REQUIRED')
            seen.add(encoded(row[key]))
    result['contracts'] = contracts
    return result


def legacy_loop_configuration(session):
    """A v1 session (no ``loop``) is exactly the historical one-shot attempt."""
    grant_wall = session['grant'].get('limits', {}).get('wall_s', CEILINGS['wall_s'])
    return {'model_backend': {'kind': 'host-codex'}, 'max_iterations': 1, 'max_no_progress': 1,
            'trials': 1, 'wall_s': min(CEILINGS['wall_s'], grant_wall),
            'per_call_s': min(DEFAULTS['per_call_s'], CEILINGS['wall_s'], grant_wall),
            'max_model_calls': 2, 'max_executions': None, 'contracts': [], 'source': 'legacy-v1-session',
            'parent_trials': 1}


def loop_configuration(session):
    if 'loop' in session:
        return validate_loop_configuration(session['loop'], session)
    return legacy_loop_configuration(session)


def iteration_contracts(session):
    """Ordered governed work-contract pairs, iteration 1 = the session's own pair."""
    first = {key: session[key] for key in CONTRACT_KEYS}
    return [first] + list(session.get('loop', {}).get('contracts', []))


def improver_ref(session, iteration):
    pairs = iteration_contracts(session)
    return pairs[min(iteration, len(pairs)) - 1]['proposal_contract_ref']


def loop_run_context_ids(session):
    """Run-context ids the preparation must create for every contract pair."""
    ids = set()
    for index, _ in enumerate(iteration_contracts(session), start=1):
        for role in ('diagnosis', 'proposal'):
            ids.add('rsi-development:' + session['id'] + ':' + role + ('' if index == 1 else ':' + str(index)))
    return ids


# ------------------------------------------------------------ visible results

def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _evaluation_fixtures(objective=None):
    if objective is None:
        try:
            from .targets import capsule_objective as objective
        except ImportError:
            return None
    return getattr(objective, 'evaluation_fixtures', None)


def inventory_complete(objective=None):
    return callable(_evaluation_fixtures(objective))


def case_inventory(name, objective=None):
    """fixture id -> visibility label over every evaluated case.

    The inventory comes from the *same* Interface B objective that scores the
    loop (``runtime.objective`` when composed, else the installed
    ``capsule_objective``), so the case list a result is checked against is
    the one its scores are computed over. Without an objective owner only the
    historical public set is known and held-out rows are label-checked only.
    """
    rows = _evaluation_fixtures(objective)
    if callable(rows):
        return {row['id']: row['fixture_set'] for row in rows(name)}
    return {row['id']: 'public' for row in public_fixtures(name)}


def baseline_ids(name, objective=None):
    """Ids of the historical ``public`` baseline set (the parent control cases)."""
    fixtures = getattr(objective, 'fixtures', None) if objective is not None else None
    rows = fixtures(name, fixture_set='public') if callable(fixtures) else public_fixtures(name)
    return [row['id'] for row in rows]


def parent_control_passed(result, name, objective=None):
    """Root parent control: the evaluation is complete and the parent passes
    its historical public baseline.

    Harder ``public_extended``/``held_out`` cases may fail for the parent --
    that is the headroom the loop exists to close -- so a v2 ``failure``
    summary of a failing *case* does not fail the control. Refusals and
    unknown effects never produce a result (the dispatcher raises/halts).
    """
    if not isinstance(result, dict):
        return False
    if result.get('schema') == VISIBLE_V1:
        return result.get('passed') is True
    rows = result.get('rows')
    if not isinstance(rows, list) or len(rows) != result.get('case_count'):
        return False
    outcome = {row.get('fixture_id'): row.get('task_success') for row in rows if isinstance(row, dict)}
    baseline = [row.get('fixture_id') for row in rows if isinstance(row, dict) and row.get('fixture_group') == 'public']
    if not any('fixture_group' in row for row in rows if isinstance(row, dict)):
        baseline = baseline_ids(name, objective)
    return bool(baseline) and all(outcome.get(ident) is True for ident in baseline)


def validate_visible_v2(result, value, role, candidate_ref, *, iteration, trials, objective=None):
    """Interface A visible result; protected identities checked where carried."""
    need(isinstance(result, dict) and result.get('schema') == VISIBLE_V2 and result.get('role') == role
         and result.get('iteration') == iteration and result.get('subject_sha256') == candidate_ref['sha256'],
         'EXACT_ROOT_VISIBLE_RESULT_V2_REQUIRED')
    failure = result.get('failure')
    need(failure is None or (isinstance(failure, dict) and set(failure) == {'exception_type', 'message'}
         and all(isinstance(failure[k], str) for k in failure)), 'CLOSED_EVALUATION_FAILURE_REQUIRED')
    for key in ('passed_count', 'case_count', 'executions'):
        need(type(result.get(key)) is int and result[key] >= 0, 'EXACT_EVALUATION_COUNTS_REQUIRED')
    rows = result.get('rows')
    need(isinstance(rows, list) and len(rows) <= result['case_count']
         and 0 <= result['passed_count'] <= result['case_count']
         and result['executions'] <= result['case_count'] * max(1, trials), 'BOUNDED_EVALUATION_ROWS_REQUIRED')
    inventory = case_inventory(value['capsule_name'], objective)
    complete = inventory_complete(objective)
    need(not complete or result['case_count'] == len(inventory), 'EXACT_CASE_INVENTORY_COUNT_REQUIRED')
    ids = []
    for row in rows:
        need(isinstance(row, dict) and isinstance(row.get('fixture_id'), str)
             and row.get('fixture_set') in ('public', 'held_out') and type(row.get('task_success')) is bool
             and _finite(row.get('protected_wall_s')) and isinstance(row.get('receipt'), dict),
             'EXACT_EVALUATION_ROW_REQUIRED')
        need(inventory.get(row['fixture_id'], row['fixture_set']) == row['fixture_set']
             and (row['fixture_id'] in inventory or row['fixture_set'] == 'held_out' and not complete),
             'UNKNOWN_OR_RELABELLED_FIXTURE_ROW')
        need(row.get('candidate_ref', candidate_ref) == candidate_ref
             and row['receipt'].get('subject_ref', candidate_ref) == candidate_ref, 'ROW_SUBJECT_DIFFERS')
        if 'evidence_ref' in row:
            pin(row['evidence_ref'])
        ids.append(row['fixture_id'])
    need(len(ids) == len(set(ids)), 'DUPLICATE_EVALUATION_ROW')
    need(sum(row['task_success'] for row in rows) == result['passed_count'], 'PASSED_COUNT_DIFFERS')
    need(_finite(result.get('protected_wall_s'))
         and math.isclose(sum(row['protected_wall_s'] for row in rows), result['protected_wall_s'], rel_tol=1e-9, abs_tol=1e-9),
         'PROTECTED_WALL_DIFFERS')
    walls = result.get('trial_wall_s', [])
    need(isinstance(walls, list) and all(_finite(w) for w in walls)
         and (len(walls) == trials if trials > 1 and failure is None else len(walls) <= max(1, trials)),
         'EXACT_TRIAL_WALLS_REQUIRED')
    if 'grant_ref' in result:
        need(result['grant_ref'] == value['grant_ref'], 'EVALUATION_GRANT_DIFFERS')
    need(result.get('security', 'UNQUALIFIED') == 'UNQUALIFIED' and result.get('model_calls', 0) == 0,
         'UNQUALIFIED_MODEL_FREE_EVALUATION_REQUIRED')
    if 'result_ref' in result:
        pin(result['result_ref'])
    return result


def validate_visible(result, value, role, candidate_ref, *, iteration, trials, objective=None):
    if isinstance(result, dict) and result.get('schema') == VISIBLE_V1:
        from .capsule_session import validate_evaluation
        return validate_evaluation(result, value, role, candidate_ref)
    return validate_visible_v2(result, value, role, candidate_ref, iteration=iteration, trials=trials,
                               objective=objective)


def _scoring_row(row, walls):
    """A v2 row as the objective reads it: per-case trial walls for min-of-k,
    and the bounded ``actual_task_output`` envelope unwrapped (a truncated
    prefix is not an output and is dropped rather than diffed)."""
    item = dict(row)
    if walls and len(walls) > 1:
        item['trial_wall_s'] = walls
    task = item.get('actual_task_output')
    if isinstance(task, dict) and set(task) == {'value', 'truncated', 'bytes'}:
        if task['truncated'] or task['value'] is None:
            item.pop('actual_task_output')
        else:
            item['actual_task_output'] = task['value']
    return item


def normalized(result, value, candidate_ref, iteration):
    """Interface A view of a v1 or v2 result, used for scoring/feedback only."""
    if result.get('schema') == VISIBLE_V2:
        walls = {}
        for trial in [result['rows']] + [rows for rows in result.get('trial_rows') or [] if isinstance(rows, list)]:
            for row in trial:
                if isinstance(row, dict) and _finite(row.get('protected_wall_s')):
                    walls.setdefault(row.get('fixture_id'), []).append(row['protected_wall_s'])
        return {**result, 'rows': [_scoring_row(row, walls.get(row['fixture_id'])) for row in result['rows']]}
    rows = [{'fixture_id': row['fixture_id'], 'fixture_set': 'public', 'task_success': row['task_success'],
             'protected_wall_s': row['protected_wall_s'], 'output_bytes': row.get('output_bytes', 0),
             'checks': row.get('independent_check') or {}, 'receipt': row.get('receipt', {})} for row in result['rows']]
    return {'schema': VISIBLE_V2, 'role': result['role'], 'iteration': iteration,
            'subject_sha256': candidate_ref['sha256'], 'passed_count': result['passed_count'],
            'case_count': len(public_fixtures(value['capsule_name'])), 'protected_wall_s': result['protected_wall_s'],
            'trial_wall_s': [result['protected_wall_s']], 'rows': rows, 'executions': result['executions'],
            'failure': None, 'source_schema': VISIBLE_V1}


def all_passed(view):
    return view['failure'] is None and view['passed_count'] == view['case_count'] == len(view['rows'])


def _bounded_checks(checks):
    raw = encoded(checks) if checks is not None else b'null'
    return checks if len(raw) <= MAX_CHECK_BYTES else {'truncated_json': raw[:MAX_CHECK_BYTES].decode('utf8', 'ignore')}


def model_view(view, label):
    """What the model may see: public detail, held-out ids and pass/fail only."""
    rows = []
    for row in view['rows']:
        if row['fixture_set'] == 'public':
            rows.append({'fixture_id': row['fixture_id'], 'fixture_set': 'public', 'task_success': row['task_success'],
                         'protected_wall_s': row['protected_wall_s'], 'output_bytes': row.get('output_bytes'),
                         'checks': _bounded_checks(row.get('checks'))})
        else:
            rows.append({'fixture_id': row['fixture_id'], 'fixture_set': 'held_out', 'task_success': row['task_success']})
    return {'schema': MODEL_VIEW_SCHEMA, 'label': label, 'subject_sha256': view['subject_sha256'],
            'passed_count': view['passed_count'], 'case_count': view['case_count'],
            'public_protected_wall_s': sum(r['protected_wall_s'] for r in view['rows'] if r['fixture_set'] == 'public'),
            'rows': rows, 'failure': view['failure']}


HELD_OUT_REVIEW_KEYS = ('fixture_id', 'fixture_set', 'task_success', 'protected_wall_s', 'evidence_ref')


def reviewer_visible(result):
    """Visible result for lineage rows: held-out rows carry ids/pass/fail/timing only.

    The exact Root bytes stay pinned by ``result_ref`` (and returned unchanged at
    the session's top level); ``loop`` rows are what the UI projects. This is
    the publisher's ``reviewer_view`` contract exactly (held-out ``trial_rows``
    stay as Root sealed them: pass/fail per check id, no outputs).
    """
    rows = [{key: row[key] for key in HELD_OUT_REVIEW_KEYS if key in row}
            if isinstance(row, dict) and row.get('fixture_set') == 'held_out' else row
            for row in result.get('rows', [])]
    return {**result, 'rows': rows}


def noise_record(calibration, parent_view):
    """``loop.noise``: method, the parent trial walls and the objective's output verbatim."""
    floor = None
    if isinstance(calibration, dict):
        floor = calibration.get('noise_floor_ratio', calibration.get('floor_ratio'))
    return {'method': 'capsule_objective.calibrate_noise', 'trials': len(parent_view['trial_wall_s']),
            'parent_wall_s_trials': list(parent_view['trial_wall_s']),
            'floor_ratio': floor if _finite(floor) else None, 'objective': calibration}


def trial_views(view):
    walls = view.get('trial_wall_s') or []
    return [{**view, 'protected_wall_s': wall, 'trial_wall_s': [wall], 'trial_index': index}
            for index, wall in enumerate(walls)]


def validate_score(score):
    need(isinstance(score, dict) and type(score.get('improved')) is bool and type(score.get('regressed')) is bool
         and isinstance(score.get('summary'), str) and isinstance(score.get('feedback'), str)
         and isinstance(score.get('correctness'), dict), 'INTERFACE_B_SCORE_REQUIRED')
    return score


# ------------------------------------------------------------------- feedback

def _fmt(value):
    return 'n/a' if value is None else ('%.4g' % value if isinstance(value, float) else str(value))


def compose_feedback(*, entry, parent_view, incumbent, history, noise):
    """Structured + textual feedback for the next diagnosis/proposal."""
    lines = ['Iteration %d outcome: %s. %s' % (entry['iteration'], entry['outcome'], entry['reason'])]
    view = entry.get('view')
    structured = {'iteration': entry['iteration'], 'outcome': entry['outcome'], 'reason': entry['reason'],
                  'candidate_ref': entry.get('candidate_ref'), 'rationale': entry.get('rationale'),
                  'failing_case_ids': [], 'not_executed_case_ids': [], 'timings': [], 'score_summary': None,
                  'latency_ratio': None}
    if entry.get('rationale'):
        lines.append('Prior rationale: ' + entry['rationale'][:600])
    if view is not None:
        failing = [row for row in view['rows'] if not row['task_success']]
        structured['failing_case_ids'] = [row['fixture_id'] for row in failing]
        executed = {row['fixture_id'] for row in view['rows']}
        structured['not_executed_case_ids'] = [row['fixture_id'] for row in parent_view['rows']
                                               if row['fixture_id'] not in executed]
        if failing:
            lines.append('Failing cases: ' + ', '.join('%s (%s)' % (r['fixture_id'], r['fixture_set']) for r in failing))
            for row in failing:
                if row['fixture_set'] == 'public':
                    lines.append('  %s checks: %s' % (row['fixture_id'],
                        json.dumps(_bounded_checks(row.get('checks')), sort_keys=True, ensure_ascii=False)))
        else:
            lines.append('Failing cases: none (%d/%d passed).' % (view['passed_count'], view['case_count']))
        if structured['not_executed_case_ids']:
            lines.append('Not executed (evaluation stopped early): ' + ', '.join(structured['not_executed_case_ids']))
        before = {row['fixture_id']: row['protected_wall_s'] for row in parent_view['rows'] if row['fixture_set'] == 'public'}
        timing = []
        for row in view['rows']:
            if row['fixture_set'] == 'public' and row['fixture_id'] in before:
                old, new = before[row['fixture_id']], row['protected_wall_s']
                delta = new - old
                timing.append({'fixture_id': row['fixture_id'], 'parent_s': old, 'candidate_s': new, 'delta_s': delta})
                lines.append('  timing %s: parent %.6fs -> candidate %.6fs (delta %+.6fs%s)' % (row['fixture_id'], old, new, delta,
                    ', %+.1f%%' % (100 * delta / old) if old > 0 else ''))
        structured['timings'] = timing
        if timing:
            lines.insert(len(lines) - len(timing), 'Timing deltas vs parent (public cases):')
    score = entry.get('score')
    if score is not None:
        structured['score_summary'] = score['summary']
        structured['latency_ratio'] = score.get('latency_ratio')
        lines.append('Score vs parent: %s (latency_ratio %s, noise_floor_ratio %s, above_noise %s)' % (
            score['summary'], _fmt(score.get('latency_ratio')), _fmt(score.get('noise_floor_ratio')), score.get('above_noise')))
        if score['feedback']:
            lines.append('Objective feedback: ' + score['feedback'])
    lines.append('Kept: %s. Current incumbent: %s (sha256 %s).' % (
        'yes' if entry['kept'] else 'no', incumbent['label'], incumbent['ref']['sha256'][:16]))
    if noise is not None:
        lines.append('Parent timing noise calibration: ' + json.dumps(noise, sort_keys=True)[:400])
    recent = [{'iteration': row['iteration'], 'outcome': row['outcome'], 'reason': row['reason'],
               'candidate_ref': row.get('candidate_ref'),
               'summary': (row.get('score') or {}).get('summary')} for row in history[-HISTORY_WINDOW:]]
    text = '\n'.join(lines)
    if len(text) > MAX_FEEDBACK_CHARS:
        text = text[:MAX_FEEDBACK_CHARS - 20] + '\n[truncated]'
    return {'schema': FEEDBACK_SCHEMA, 'after_iteration': entry['iteration'],
            'incumbent': {'label': incumbent['label'], 'sha256': incumbent['ref']['sha256']},
            'last': structured, 'recent': recent, 'text': text}


# ----------------------------------------------------------------------- loop

class CapsuleLoop:
    """One claimed session's loop. ``loop`` is filled in place for partial evidence."""

    def __init__(self, *, value, runtime, backend, objective, config, target, parent, visible,
                 parent_pin, loop, clock=time.monotonic):
        self.value, self.runtime, self.backend, self.objective = value, runtime, backend, objective
        self.config, self.target, self.parent, self.visible = config, target, parent, visible
        self.parent_pin, self.loop, self.clock = parent_pin, loop, clock
        self.store = runtime.store
        self.limits = Limits.from_mapping(dict(max_attempts=1, max_no_progress=1, wall_s=config['wall_s'],
            per_call_s=config['per_call_s'], session_query_limit=2, lifetime_query_limit=2))
        grant = value['grant']
        budget = grant.get('max_executions')
        if config['max_executions'] is not None:
            budget = config['max_executions'] if budget is None else min(budget, config['max_executions'])
        self.execution_budget = budget
        self.executions = 0
        self.model_calls = 0
        self.model_calls_known = True
        self.slowest = 0.0
        self.noise = None
        self.raw_parent = None
        self.raw_visible = {}  # iteration -> exact Root visible result

    # ------------------------------------------------------------ helpers
    def deadline_init(self):
        self.started = self.clock()
        self.deadline = self.started + self.config['wall_s']
        expires = self.value['grant'].get('expires_unix_s')
        if type(expires) is int:
            self.deadline = min(self.deadline, self.started + (expires - time.time()))

    def plan_trials(self):
        trials = self.config['trials']
        name = self.value['capsule_name']
        cases = len(self.objective.evaluation_fixtures(name))
        need(cases > 0, 'FINITE_CASE_INVENTORY_REQUIRED')
        parent, candidate = self.config['parent_trials'], trials
        budget = self.execution_budget
        if budget is not None and cases * (parent + candidate) > budget:
            candidate = 1
            parent = max(1, min(parent, budget // cases - 1))
            need(cases * (parent + candidate) <= budget, 'EXECUTION_BUDGET_BELOW_ONE_ITERATION')
        self.loop['trials'] = {'requested': trials, 'parent': parent, 'candidate': candidate, 'estimated_cases': cases}
        return parent, candidate

    async def evaluate(self, role, body, ref, binding, iteration, trials):
        raw = await self.runtime.evaluate(role, body=body, candidate_ref=ref, binding=binding,
                                          iteration=iteration, trials=trials)
        raw = validate_visible(raw, self.value, role, ref, iteration=iteration, trials=trials, objective=self.objective)
        self.executions += raw['executions']
        return raw, normalized(raw, self.value, ref, iteration)

    async def before_model(self):
        try:
            await self.runtime.before_model()
        except Exception as error:
            raise LoopStop('deadline' if 'DEADLINE' in str(error) else 'error', str(error)) from error

    def record_failure(self, error, phase):
        return self.store.put({'schema': 'ai4r-rsi-capsule-loop-failure:1', 'phase': phase,
            'exception_type': type(error).__name__, 'message': str(error)[:4096]})

    def check_calls(self, handle, expected, label):
        calls = getattr(handle, 'last_model_calls', None)
        if type(calls) is not int:
            self.model_calls_known = False
            raise ValueError('ACTUAL_GOVERNED_CALL_COUNT_UNAVAILABLE_' + label)
        self.model_calls += calls
        need(calls == expected, 'ONE_GOVERNED_CALL_PER_ROLE_REQUIRED_' + label)
        return calls

    def precheck(self, iteration, candidate_trials, case_count):
        if self.model_calls + 2 > self.config['max_model_calls']:
            return 'budget', 'MODEL_CALL_BUDGET_EXHAUSTED'
        capacity = self.backend.capacity()
        if capacity is not None and iteration > capacity:
            return 'budget', 'MODEL_BACKEND_HANDLES_EXHAUSTED'
        if self.execution_budget is not None and self.executions + case_count * candidate_trials > self.execution_budget:
            return 'budget', 'EXECUTION_BUDGET_EXHAUSTED'
        if self.clock() + self.slowest >= self.deadline:
            return 'deadline', 'LOOP_DEADLINE_REACHED'
        return None

    # ----------------------------------------------------------------- run
    async def run(self):
        loop, value, store = self.loop, self.value, self.store
        self.deadline_init()
        parent_ref = value['parent_body_ref']
        parent_trials, candidate_trials = self.plan_trials()
        began = self.clock()
        raw, parent_view = await self.evaluate('parent', self.parent, parent_ref, None, 0, parent_trials)
        self.raw_parent = raw
        self.slowest = self.clock() - began
        loop['parent_visible'] = reviewer_visible(raw)
        need(parent_control_passed(raw, value['capsule_name'], self.objective), 'PARENT_CONTROL_FAILED_NO_MODEL_CALL')
        if parent_trials >= 3 and len(parent_view.get('trial_wall_s') or []) >= 3:
            self.noise = self.objective.calibrate_noise(trial_views(parent_view))
            loop['noise'] = noise_record(self.noise, parent_view)
        else:
            self.noise = None
            loop['noise'] = None
            loop['limitations'].append('Parent timing noise not calibrated (fewer than three trials within the execution budget).')
        parent_model = model_view(parent_view, 'parent')
        self.parent_model_ref = store.put(parent_model)
        self.parent_model = parent_model
        incumbent = {'label': 'parent', 'iteration': 0, 'body': self.parent, 'ref': parent_ref,
                     'view': parent_view, 'model_ref': self.parent_model_ref, 'model': parent_model}
        seen = {parent_ref['sha256']: 'parent'}
        feedback, no_progress = None, 0
        stop = ('max_iterations', None)
        for iteration in range(1, self.config['max_iterations'] + 1):
            halt = self.precheck(iteration, candidate_trials, parent_view['case_count'])
            if halt is not None:
                stop = halt
                break
            entry = await self.iteration(iteration, incumbent, feedback, seen, parent_view, candidate_trials)
            loop['iterations'].append(entry['public'])
            loop['completed_iterations'] = iteration
            self.slowest = max(self.slowest, entry['public']['elapsed_s'])
            if entry['public']['kept']:
                no_progress = 0
                incumbent = {'label': 'iteration %d' % iteration, 'iteration': iteration, 'body': entry['body'],
                             'ref': entry['public']['candidate_ref'], 'view': entry['view'],
                             'model_ref': entry['model_ref'], 'model': entry['model']}
                loop['best'] = {'iteration': iteration, 'candidate_ref': entry['public']['candidate_ref'],
                                'score': entry['public']['score']}
            else:
                no_progress += 1
            feedback = compose_feedback(entry={**entry['public'], 'view': entry['view']}, parent_view=parent_view,
                                        incumbent=incumbent, history=loop['iterations'], noise=self.noise)
            entry['public']['next_feedback_ref'] = store.put(feedback)
            loop['iteration_record_refs'].append(store.put({'schema': ITERATION_SCHEMA, **entry['public']}))
            if entry['public']['outcome'] == 'error':
                stop = ('error', entry['public']['reason'])
                break
            if no_progress >= self.config['max_no_progress']:
                stop = ('no_progress', '%d consecutive iterations without improvement' % no_progress)
                break
        loop['stop_reason'], loop['stop_detail'] = stop
        return loop

    async def iteration(self, iteration, incumbent, feedback, seen, parent_view, candidate_trials):
        value, store, target = self.value, self.store, self.target
        began = self.clock()
        public = {'iteration': iteration, 'base': {'label': incumbent['label'], 'sha256': incumbent['ref']['sha256']},
                  'feedback_ref': None, 'diagnosis_ref': None, 'diagnosis_capture_ref': None,
                  'proposal_ref': None, 'proposal_prompt_ref': None, 'proposal_response_ref': None,
                  'proposal_capture': {}, 'candidate_ref': None, 'binding_ref': None,
                  'rationale': None, 'visible': None, 'score': None, 'score_ref': None, 'selection': None,
                  'kept': False, 'outcome': 'error', 'reason': '', 'model_calls': 0,
                  'generation_evidence_refs': [], 'generating_model': None, 'held_out_failing_ids': [],
                  'failure': None, 'failure_ref': None, 'elapsed_s': 0.0}
        entry = {'public': public, 'view': None, 'body': None, 'model_ref': None, 'model': None}
        if feedback is not None:
            public['feedback_ref'] = store.put(feedback)

        def finish(outcome, reason, error=None):
            public.update(outcome=outcome, reason=reason)
            if error is not None:
                public['failure'] = {'exception_type': type(error).__name__, 'message': str(error)[:4096]}
                public['failure_ref'] = self.record_failure(error, 'iteration-%d' % iteration)
            public['elapsed_s'] = self.clock() - began
            return entry

        try:
            diagnosis_handle, proposal_handle = self.backend.handles(iteration)
        except Exception as error:
            return finish('error', 'MODEL_HANDLES_UNAVAILABLE', error)
        if diagnosis_handle is proposal_handle or getattr(diagnosis_handle, 'used', False) or getattr(proposal_handle, 'used', False):
            return finish('error', 'TWO_SEPARATE_ONCE_ONLY_HANDLES_REQUIRED', ValueError('TWO_SEPARATE_ONCE_ONLY_HANDLES_REQUIRED'))
        diagnosis = BoundedDiagnosis(diagnosis_handle, store=store, limits=self.limits)
        proposer = GuardedProposer(proposal_handle, configuration_ref=value['configuration_ref'],
            improver_ref=improver_ref(value, iteration),
            limits=self.limits, store=store)

        def collect(handle):
            public['generation_evidence_refs'] += [ref for ref in getattr(handle, 'last_evidence', []) or []]
            model = getattr(handle, 'last_generating_model', None)
            if isinstance(model, str) and model:
                public['generating_model'] = model

        # -- diagnosis
        evidence = [{'ref': value['visible_context_ref'], 'content': self.visible},
                    {'ref': self.parent_model_ref, 'content': self.parent_model}]
        if incumbent['iteration']:
            evidence.append({'ref': incumbent['model_ref'], 'content': incumbent['model']})
        if feedback is not None:
            evidence.append({'ref': public['feedback_ref'], 'content': feedback})
            symptom = ('Improve the incumbent (%s) of %s beyond the parent on correctness first, then protected wall time. '
                       'Loop feedback follows.\n' % (incumbent['label'], value['capsule_name']) + feedback['text'])[:4096]
        else:
            symptom = value['observed_symptom']
        await self.before_model()
        try:
            diagnosed, public['diagnosis_ref'] = await diagnosis.diagnose(parent=self.parent_pin,
                profile_ref=value['preparation_ref'], preparation_ref=value['preparation_ref'],
                configuration_ref=value['configuration_ref'], authorized_component=value['authorized_component'],
                observed_symptom=symptom, evidence=evidence)
        except Exception as error:
            public['diagnosis_capture_ref'] = diagnosis.last_capture_ref
            collect(diagnosis_handle)
            try:
                public['model_calls'] = self.check_calls(diagnosis_handle, 1, 'DIAGNOSIS')
            except ValueError as count:
                return finish('error', 'DIAGNOSIS_CALL_COUNT_DIFFERS: ' + str(count)[:300], count)
            captured = (diagnosis.last_capture_ref is not None
                        and store.get(diagnosis.last_capture_ref).get('response_ref') is not None)
            return finish('rejected' if captured else 'error',
                          ('DIAGNOSIS_REJECTED: ' if captured else 'DIAGNOSIS_UNAVAILABLE: ') + str(error)[:500], error)
        finally:
            public['diagnosis_capture_ref'] = diagnosis.last_capture_ref
        collect(diagnosis_handle)
        try:
            public['model_calls'] = self.check_calls(diagnosis_handle, 1, 'DIAGNOSIS')
        except ValueError as error:
            return finish('error', 'DIAGNOSIS_CALL_COUNT_DIFFERS', error)

        # -- proposal
        history = [{'sequence': row['iteration'], 'rationale': row.get('rationale') or '',
                    'attempt_status': row['outcome'] + ': ' + ((row.get('score') or {}).get('summary') or row['reason'])[:300]}
                   for row in self.loop['iterations']]
        context = proposal_context({'visible': self.visible, 'diagnosis': diagnosed,
                                    'loop_feedback': feedback, 'incumbent_visible': incumbent['model']},
                                   body=incumbent['body'], history=history, mutable_path=target.carrier_path)
        await self.before_model()
        try:
            proposal = await proposer.propose(context, None)
        except Exception as error:
            public.update(proposal_prompt_ref=proposer.last_prompt_ref, proposal_response_ref=proposer.last_response_ref,
                          proposal_capture=dict(proposer.last_capture))
            collect(proposal_handle)
            try:
                public['model_calls'] += self.check_calls(proposal_handle, 1, 'PROPOSAL')
            except ValueError as count:
                return finish('error', 'PROPOSAL_CALL_COUNT_DIFFERS: ' + str(count)[:300], count)
            captured = proposer.last_response_ref is not None
            return finish('rejected' if captured else 'error',
                          ('PROPOSAL_REJECTED: ' if captured else 'PROPOSAL_UNAVAILABLE: ') + str(error)[:500], error)
        public.update(proposal_prompt_ref=proposer.last_prompt_ref, proposal_response_ref=proposer.last_response_ref,
                      proposal_capture=dict(proposer.last_capture))
        collect(proposal_handle)
        try:
            public['model_calls'] += self.check_calls(proposal_handle, 1, 'PROPOSAL')
        except ValueError as error:
            return finish('error', 'PROPOSAL_CALL_COUNT_DIFFERS', error)
        body = proposal['body'].encode('utf8')
        public['rationale'] = proposal['rationale']
        public['candidate_ref'] = store.put_bytes(body)
        candidate_sha256 = public['candidate_ref']['sha256']
        public['proposal_ref'] = store.put({'schema': 'ai4r-rsi-capsule-loop-proposal:1', 'iteration': iteration,
            'path': proposal['path'], 'candidate_ref': public['candidate_ref'], 'rationale': proposal['rationale'],
            'response_ref': proposer.last_response_ref})
        if not 0 < len(body) <= MAX_BODY_BYTES:
            return finish('rejected', 'CANDIDATE_BODY_EXCEEDS_BOUND', ValueError('CANDIDATE_BODY_EXCEEDS_BOUND'))
        if candidate_sha256 in seen:
            return finish('duplicate', 'IDENTICAL_TO_' + seen[candidate_sha256].upper().replace(' ', '_')
                          + '; not re-evaluated')
        seen[candidate_sha256] = 'iteration %d' % iteration

        # -- protected evaluation
        binding = {'schema': BINDING_SCHEMA, 'run_id': value['id'], 'capsule_name': value['capsule_name'],
            'runtime_manifest_sha256': value['grant']['runtime_manifest_sha256'],
            'parent_sha256': value['parent_body_ref']['sha256'], 'mutable_path': target.carrier_path,
            'candidate_ref': public['candidate_ref'], 'grant_sha256': value['grant_ref']['sha256']}
        try:
            validate_candidate_binding(binding, value['grant'], public['candidate_ref'])
            public['binding_ref'] = store.put(binding)
            raw, view = await self.evaluate('candidate', body, public['candidate_ref'], binding, iteration, candidate_trials)
        except Exception as error:
            return finish('error', 'CANDIDATE_EVALUATION_FAILED: ' + str(error)[:500], error)
        public['visible'] = reviewer_visible(raw)
        public['held_out_failing_ids'] = [row['fixture_id'] for row in view['rows']
                                          if row['fixture_set'] == 'held_out' and not row['task_success']]
        entry.update(view=view, body=body)
        self.raw_visible[iteration] = raw
        entry['model'] = model_view(view, 'iteration %d' % iteration)
        entry['model_ref'] = store.put(entry['model'])
        # A captured case failure (wrong output, raised, timed out) is a scored
        # outcome, never a loop stop: Root refusals and unknown effects raise
        # from ``runtime.evaluate`` above instead.

        # -- score and select
        try:
            noise = self.noise
            score = validate_score(self.objective.score(parent_view, view, noise=noise))
            selection = score if incumbent['iteration'] == 0 else validate_score(
                self.objective.score(incumbent['view'], view, noise=noise))
        except Exception as error:
            return finish('error', 'OBJECTIVE_SCORE_FAILED', error)
        public['score'] = score
        public['score_ref'] = store.put(score)
        public['selection'] = {'against': incumbent['label'], 'against_sha256': incumbent['ref']['sha256'],
                               'score': selection}
        kept = selection['improved'] and not selection['regressed']
        public['kept'] = kept
        reason = ('improved over %s: %s' % (incumbent['label'], selection['summary']) if kept else
                  'not kept vs %s (%s): %s' % (incumbent['label'],
                      'regressed' if selection['regressed'] else 'no improvement above noise', selection['summary']))
        return finish('kept' if kept else 'not_kept', reason)


def new_loop_record(config, backend_description):
    return {'schema': LOOP_SCHEMA, 'max_iterations': config['max_iterations'], 'completed_iterations': 0,
            'stop_reason': None, 'stop_detail': None, 'model_backend': backend_description,
            'configuration': {key: item for key, item in config.items() if key != 'contracts'},
            'model_calls': 0, 'iterations': [], 'best': None, 'parent_visible': None, 'noise': None, 'trials': None,
            'iteration_record_refs': [], 'limitations': []}


def selected_iteration(loop):
    """Best kept candidate, else the last evaluated one, else the last iteration."""
    rows = loop['iterations']
    if loop.get('best') is not None:
        return next(row for row in rows if row['iteration'] == loop['best']['iteration'])
    evaluated = [row for row in rows if row['visible'] is not None]
    if evaluated:
        return evaluated[-1]
    return rows[-1] if rows else None


def load_objective():
    from .targets import capsule_objective
    need(all(callable(getattr(capsule_objective, name, None))
             for name in ('score', 'calibrate_noise', 'fixtures', 'evaluation_fixtures')),
         'INTERFACE_B_OBJECTIVE_REQUIRED')
    return capsule_objective

