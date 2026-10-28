"""Typed, exact-byte future session joins for the public CC review publisher.

The caller is an OS-owned publisher with an explicit finite OriginalBytes read
grant and independently pinned custodian key. This module follows only named
session/result/attempt/body/referee and operator receipt positions. It never
opens fixture partitions, model traces, prompts, account packets or ledgers.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import re

from .cc_rsi_projection import ProjectionError, _fields, _hash, _ref, validate_publication


def need(value):
    if not value:
        raise ProjectionError('Typed public session/candidate join differs from exact originals')


PROGRESS_SCHEMA = 'ai4r-cc-rsi-prerequisite-progress:1'
_CALIBRATION_ROLES = ('intent', 'requirements', 'planner', 'verifier', 'search', 'screening',
                      'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')
PROGRESS_STAGES = frozenset(('setup', 'catalog_admission',
    'source_publication', 'security_qualification', 'timing', 'readiness', 'controller_assembly',
    'session_pending', 'diagnosis', 'proposal', 'candidate_evaluation', 'final_comparison', 'stopped',
    *(role + '_calibration' for role in _CALIBRATION_ROLES)))
PROGRESS_STATUSES = frozenset(('not_started', 'running', 'blocked', 'outcome_unknown', 'completed', 'stopped'))
PROGRESS_REASONS = {'provider_capacity': 'The provider refused capacity; no additional request is authorized.',
    'native_delivery_unknown': 'Native delivery remains unknown and requires reconciliation.',
    'runtime_prerequisite_unavailable': 'A protected runtime prerequisite is unavailable.'}
_GENERATION_STAGES = frozenset(('diagnosis', 'proposal', 'candidate_evaluation', 'final_comparison', 'stopped'))
_PROGRESS_MARKER = 'root-progress:'


def _progress_run(row):
    return bool(row['activity'] and re.fullmatch(_PROGRESS_MARKER + '[a-f0-9]{64}', row['activity'][0]['id']))


def append_progress(publication, progress, progress_ref):
    """Project a Root-observed finite aggregate grant, never a runtime lookup.

    File custody/SHA pin are enforced by the Root publisher before this pure
    join. There is no raw error/message/evidence field to leak private context.
    Observed candidate counts never create code nodes or qualification claims.
    """
    fields = 'schema run_id target_id parent_hash observed_at stage status setup_completed setup_unknown cumulative_setup_completed cumulative_setup_unknown diagnosis_calls proposal_calls candidate_count max_candidates max_generation_calls'
    if 'reason_code' in progress: fields += ' reason_code'
    if 'setup_failed' in progress or 'cumulative_setup_failed' in progress: fields += ' setup_failed cumulative_setup_failed'
    _fields(progress, fields)
    _ref(progress_ref)
    need(progress['schema'] == PROGRESS_SCHEMA
         and isinstance(progress['run_id'], str) and re.fullmatch('[a-z0-9][a-z0-9_.:-]{0,95}', progress['run_id'])
         and isinstance(progress['stage'], str) and progress['stage'] in PROGRESS_STAGES
         and isinstance(progress['status'], str) and progress['status'] in PROGRESS_STATUSES)
    _hash(progress['parent_hash'])
    need(isinstance(progress['observed_at'], str) and len(progress['observed_at']) <= 64)
    observed = datetime.fromisoformat(progress['observed_at'].replace('Z', '+00:00'))
    need(observed.tzinfo is not None)
    observed_at = observed.astimezone(timezone.utc).isoformat()
    count_keys = ('setup_completed', 'setup_unknown', 'cumulative_setup_completed', 'cumulative_setup_unknown',
                  'diagnosis_calls', 'proposal_calls', 'candidate_count', 'max_candidates', 'max_generation_calls')
    if 'setup_failed' in progress: count_keys += ('setup_failed', 'cumulative_setup_failed')
    need(all(type(progress[key]) is int and 0 <= progress[key] <= 1000000 for key in count_keys))
    if 'setup_failed' in progress: need(progress['setup_failed'] <= progress['cumulative_setup_failed'])
    reason = progress.get('reason_code')
    if 'reason_code' in progress:
        need(isinstance(reason, str) and reason in PROGRESS_REASONS and progress['status'] in ('blocked', 'outcome_unknown', 'stopped'))
        if reason == 'provider_capacity': need(progress.get('setup_failed', 0) > 0 and progress['status'] == 'blocked')
    need(progress['max_candidates'] == 1 and progress['max_generation_calls'] == 2
         and progress['setup_completed'] <= progress['cumulative_setup_completed']
         and progress['setup_unknown'] <= progress['cumulative_setup_unknown']
         and 0 <= progress['candidate_count'] <= progress['proposal_calls'] <= progress['diagnosis_calls'] <= 1
         and progress['diagnosis_calls'] + progress['proposal_calls'] <= progress['max_generation_calls'])
    if progress['stage'] not in _GENERATION_STAGES:
        need(progress['diagnosis_calls'] == progress['proposal_calls'] == progress['candidate_count'] == 0)
    if progress['stage'] == 'diagnosis':
        need(progress['proposal_calls'] == progress['candidate_count'] == 0)
    if progress['stage'] == 'proposal':
        need(progress['diagnosis_calls'] == 1)
    if progress['stage'] in ('candidate_evaluation', 'final_comparison'):
        need(progress['candidate_count'] == 1)
    if progress['setup_unknown']:
        need(progress['status'] in ('blocked', 'outcome_unknown', 'stopped'))
    if progress['status'] == 'not_started':
        need(progress['setup_completed'] == progress['setup_unknown'] == progress['diagnosis_calls'] == progress['proposal_calls'] == progress['candidate_count'] == 0)
        need(progress.get('setup_failed', 0) == 0)
    value = copy.deepcopy(validate_publication(publication)); view = value['snapshot']
    targets = [row for row in view['targets'] if row['id'] == progress['target_id']]
    need(len(targets) == 1 and targets[0]['parent_hash'] == progress['parent_hash'])
    need(any(row['target_id'] == progress['target_id'] and row['parent_id'] is None and row['hash'] == progress['parent_hash'] for row in view['nodes']))
    existing = [row for row in view['runs'] if row['id'] == progress['run_id']]
    need(len(existing) <= 1)
    if existing:
        need(_progress_run(existing[0]) and existing[0]['target_id'] == progress['target_id'])
        before = datetime.fromisoformat(existing[0]['activity'][0]['at'].replace('Z', '+00:00'))
        need(observed >= before)
    blocker = 'Root-observed progress is inspection only. Execution is owned by the existing runtime; no additional run or operator action is authorized.'
    summary = (f"Current run setup: {progress['setup_completed']} completed, {progress['setup_unknown']} unknown. "
        f"Cumulative setup/smoke: {progress['cumulative_setup_completed']} completed, {progress['cumulative_setup_unknown']} unknown. "
        f"Diagnosis/proposal started calls: {progress['diagnosis_calls']} + {progress['proposal_calls']} / 2. "
        f"Observed candidates: {progress['candidate_count']} / 1. Captured code and measured results require the signed terminal join.")
    if 'setup_failed' in progress:
        summary += f" Known failed setup calls: current {progress['setup_failed']}, cumulative {progress['cumulative_setup_failed']}; these remain charged."
    if reason is not None: summary += ' ' + PROGRESS_REASONS[reason]
    run = {'id': progress['run_id'], 'target_id': progress['target_id'], 'stage': progress['stage'], 'status': progress['status'],
        'blockers': [blocker], 'budget': {'elapsed_seconds': None, 'limit_seconds': None,
            'setup_calls': progress['cumulative_setup_completed'], 'diagnosis_calls': progress['diagnosis_calls'],
            'proposal_calls': progress['proposal_calls'], 'generation_call_limit': 2, 'cost': None, 'currency': None},
        'activity': [{'id': _PROGRESS_MARKER + progress_ref['sha256'], 'at': observed_at, 'stage': progress['stage'],
                      'status': progress['status'], 'summary': summary}]}
    if existing and existing[0] == run:
        return value
    view['runs'] = [row for row in view['runs'] if row['id'] != progress['run_id']] + [run]
    for target in view['targets']:
        target['run'] = {'allowed': False, 'blocker': blocker}
    for node in view['nodes']:
        node['admit'] = node['activate'] = {'allowed': False, 'blocker': 'Authenticated human operator broker is not installed.'}
    view['revision'] = hashlib.sha256(json.dumps([view['revision'], progress_ref], sort_keys=True).encode()).hexdigest()
    view['generated_at'] = observed_at; view['availability'] = 'ROOT_OBSERVED_PROGRESS'; view['blocker'] = blocker
    return validate_publication(value)


class ApprovedOriginals:
    """Each read is authorized before opening bytes; bounded across all joins."""
    def __init__(self, read, approved_refs):
        need(isinstance(approved_refs, list) and len(approved_refs) <= 512)
        for pin in approved_refs: _ref(pin)
        self.allowed = {json.dumps(pin, sort_keys=True) for pin in approved_refs}
        self.reader = read
        self.cache = {}
        self.total = 0

    def read(self, pin, maximum=262144):
        _ref(pin)
        key = json.dumps(pin, sort_keys=True)
        need(key in self.allowed)
        if key not in self.cache:
            raw = self.reader(pin)
            need(isinstance(raw, bytes) and len(raw) <= maximum and hashlib.sha256(raw).hexdigest() == pin['sha256'])
            self.total += len(raw)
            need(self.total <= 8 * 1024 * 1024)
            self.cache[key] = raw
        need(len(self.cache[key]) <= maximum)
        return self.cache[key]

    def get(self, pin):
        return json.loads(self.read(pin))


def append_session(publication, originals, *, session_ref, result_ref, public_key, key_id,
                   operator_receipt_refs=(), validate=None, verify=None):
    """Append one actual signed terminal and all captured candidates/attempts.

    Keys are supplied from the publisher's Root-owned installation grant, never
    taken from browser or candidate records. Passing validation/verification
    callbacks is solely for offline typed unit tests and trusted composition.
    Selection/evaluation never grants admission or activation.
    """
    if validate is None:
        from jiuwenswarm.research_rsi.session_policy import _contracts
        validate = _contracts().validate
    if verify is None:
        from jiuwenswarm.research_rsi.signing import verify
    from jiuwenswarm.research.contracts import validate as core_validate
    value = copy.deepcopy(validate_publication(publication))
    view = value['snapshot']
    session = originals.get(session_ref); validate('rsi-session', session)
    result = originals.get(result_ref); validate('rsi-session-result', result)
    verify(result, public_key, key_id)
    need(result['session_ref'] == session_ref and result['parent'] == session['parent']
         and len(result['attempt_refs']) == result['attempts_used'] <= session['limits']['max_attempts'])
    parent_declaration = originals.get(session['parent_declaration_ref'])
    core_validate('capsule-declaration', parent_declaration)
    profile = originals.get(session['target_profile_ref'])
    from jiuwenswarm.research_rsi.profiles import freeze_profile
    freeze_profile(profile, parent_declaration, validate)
    need(profile['mutable_paths'] == ['ranking_parent.txt'])
    parent_hash = profile['parent_ref']['sha256']
    parents = [row for row in view['nodes'] if row['hash'] == parent_hash]
    exact_parents = [row for row in parents if session['parent_declaration_ref'] in row['evidence_refs']]
    if exact_parents: parents = exact_parents
    need(len(parents) == 1)
    parent_node = parents[0]; target_id = parent_node['target_id']
    target_name = next(row['name'] for row in view['targets'] if row['id'] == target_id)
    need(target_id == 'research.screening@m1-4' and target_name.startswith(target_id))
    parent_code = originals.read(profile['parent_ref']).decode('utf8', errors='strict')
    run_id = session['session_id']
    prior_runs = [row for row in view['runs'] if row['id'] == run_id]
    need(len(prior_runs) <= 1 and all(_progress_run(row) and row['target_id'] == target_id for row in prior_runs))
    activity = []; nodes_by_attempt = {}; previous = None; times = []; model_calls = []
    for sequence, attempt_ref in enumerate(result['attempt_refs'], 1):
        attempt = originals.get(attempt_ref); validate('rsi-attempt', attempt)
        need(attempt['session_id'] == run_id and attempt['sequence'] == sequence and attempt['previous_ref'] == previous
             and attempt['parent_ref'] == profile['parent_ref'] and attempt['target_ref'] == session['target_profile_ref']
             and attempt['configuration_ref'] == session['configuration_ref'])
        previous = attempt_ref
        times.append(attempt['time_s']); model_calls.append(attempt['model_calls'])
        child = attempt['child_ref']
        # Attempts without a captured body stay in activity rather than becoming
        # invented capsule nodes. No rejection/model packet text is forwarded.
        activity.append({'id': attempt_ref['id'], 'at': result['recorded_at'], 'stage': 'candidate evaluation',
                         'status': attempt['attempt_status'], 'summary': f"Attempt {sequence}: {attempt['attempt_status']}; " +
                         ('captured code retained for review.' if child else 'no captured capsule body.')})
        if child is None: continue
        code = originals.read(child).decode('utf8', errors='strict')
        node_id = 'candidate:' + attempt_ref['sha256']
        gate = {'allowed': False, 'blocker': 'Authenticated human operator broker is not installed.'}
        node = {'id': node_id, 'target_id': target_id, 'run_id': run_id, 'parent_id': parent_node['id'], 'hash': child['sha256'],
                'label': f'Candidate {sequence} · {run_id}', 'evaluation_status': attempt['attempt_status'],
                'admission_status': 'unadmitted (no joined admission receipt)', 'activation_status': 'inactive',
                'correctness': None, 'speed': None, 'noise': None, 'evidence_refs': [attempt_ref, result_ref],
                'operator_receipts': [], 'admit': gate, 'activate': gate}
        view['nodes'].append(node); nodes_by_attempt[json.dumps(attempt_ref, sort_keys=True)] = node
        value['candidates'].append({'node_id': node_id, 'candidate_hash': child['sha256'], 'path': 'ranking_parent.txt',
                                    'parent_code': parent_code, 'candidate_code': code,
                                    'rationale': attempt['rationale'], 'blocker': None})
    finalist = nodes_by_attempt.get(json.dumps(result['final_attempt_ref'], sort_keys=True))
    if result['final_attempt_ref'] is not None:
        need(finalist is not None)
        finalist['evaluation_status'] = result['outcome'] + ' (selected for final evaluation)'
    if result['referee_evidence_ref'] is not None:
        need(finalist is not None)
        referee = originals.get(result['referee_evidence_ref']); validate('rsi-referee-evidence', referee)
        verify(referee, public_key, key_id)
        need(referee['attempt_ref'] == result['final_attempt_ref'] and referee['parent_ref'] == profile['parent_ref']
             and referee['child_ref']['sha256'] == finalist['hash'] and referee['target_ref'] == session['target_profile_ref'])
        # Only aggregate totals. Do not expose split Refs/names, fixture labels,
        # per-case outcomes, raw timings, security traces or hidden content.
        pairs = referee['pairs']
        finalist['correctness'] = '; '.join(f"Parent {pair['parent_passed']}/{pair['total']}; candidate {pair['child_passed']}/{pair['total']}" for pair in pairs)
        finalist['evidence_refs'].append(result['referee_evidence_ref'])
        stats = result['statistics'] or {}
        timing = stats.get('timing')
        if timing is not None:
            need(all(type(timing.get(key)) in (int, float) and math.isfinite(timing[key]) for key in
                     ('parent_median_s', 'child_median_s', 'relative_gain', 'calibrated_relative_noise')))
            finalist['speed'] = f"Parent median {timing['parent_median_s']}s; candidate {timing['child_median_s']}s; relative gain {timing['relative_gain']}"
            finalist['noise'] = str(timing['calibrated_relative_noise'])
    # A result's best candidate can exist even if the final comparison never
    # started. Join its declaration for real Library receipts independently.
    best = None
    if result['child_declaration_ref'] is not None:
        declaration = originals.get(result['child_declaration_ref']); core_validate('capsule-declaration', declaration)
        body = [row for row in declaration['identity']['body'] if row['path'] == 'ranking_parent.txt']
        need(len(body) == 1 and declaration['identity']['lineage']['parent'] == session['parent_declaration_ref']
             and result['child'] == {'cc_name': declaration['identity']['name'], 'cc_version': declaration['identity']['version_label'],
                                     'declaration_sha256': result['child_declaration_ref']['sha256']})
        matches = [row for row in view['nodes'] if row['run_id'] == run_id and row['hash'] == body[0]['sha256']]
        need(len(matches) == 1); best = matches[0]
        best['evidence_refs'].append(result['child_declaration_ref'])
    for receipt_ref in operator_receipt_refs:
        need(best is not None)
        receipt = originals.get(receipt_ref)
        human_receipt = None
        if receipt.get('schema') == 'ai4r-cc-rsi-human-receipt:1':
            human_receipt = receipt
            _fields(human_receipt, 'schema actor action action_id candidate_hash node_id operator_receipt_ref assertion_sha256 recorded_at')
            _hash(human_receipt['assertion_sha256'])
            need(human_receipt['candidate_hash'] == best['hash'] and human_receipt['node_id'] == best['id']
                 and human_receipt['action'] in ('admit', 'activate'))
            receipt = originals.get(human_receipt['operator_receipt_ref'])
            best['evidence_refs'].append(human_receipt['operator_receipt_ref'])
        need(receipt.get('command') in ('admit-rsi', 'standing') and isinstance(receipt.get('actor'), str)
             and bool(receipt['actor']) and isinstance(receipt.get('recorded_at'), str))
        if receipt['command'] == 'admit-rsi':
            need(receipt['status'] in ('admitted', 'rejected'))
            admission = originals.get(receipt['admission_ref']); core_validate('library-admission', admission)
            need(admission['candidate_ref'] == result['child_declaration_ref'] and admission['status'] == receipt['status'])
            best['admission_status'] = admission['status'] + ' (inactive on admission)'
            best['evidence_refs'].append(receipt['admission_ref'])
            action = 'admit'
        else:
            need(receipt['status'] == 'completed')
            standing = originals.get(receipt['standing_ref']); core_validate('activation-record', standing)
            admission = originals.get(standing['admission_ref']); core_validate('library-admission', admission)
            need(admission['candidate_ref'] == result['child_declaration_ref'] and admission['status'] == 'admitted'
                 and standing['actor'] == receipt['actor'] and standing['cc'] == admission['cc'])
            best['activation_status'] = f"Last recorded: {standing['to_standing']} ({standing['effect_scope']})"
            best['evidence_refs'].extend([standing['admission_ref'], receipt['standing_ref']])
            action = 'activate'
        best['evidence_refs'].append(receipt_ref)
        if human_receipt is not None:
            need(human_receipt['action'] == action)
        attribution = human_receipt or receipt
        best['operator_receipts'].append({'action': action, 'actor': attribution['actor'], 'at': attribution['recorded_at'], 'receipt_ref': receipt_ref})
    view['runs'] = [row for row in view['runs'] if row['id'] != run_id]
    view['runs'].append({'id': run_id, 'target_id': target_id, 'stage': 'terminal', 'status': result['outcome'],
                         'blockers': ['Historical review grants no new execution or operator authority.'],
                         'budget': {'elapsed_seconds': None, 'limit_seconds': session['limits']['wall_s'], 'setup_calls': None,
                                    'diagnosis_calls': None, 'proposal_calls': sum(model_calls) if all(type(count) is int for count in model_calls) else None,
                                    'generation_call_limit': None, 'cost': None, 'currency': None}, 'activity': activity})
    view['revision'] = hashlib.sha256(json.dumps([view['revision'], session_ref, result_ref, list(operator_receipt_refs)], sort_keys=True).encode()).hexdigest()
    remaining_progress = [row for row in view['runs'] if _progress_run(row)]
    if remaining_progress:
        latest = max(remaining_progress, key=lambda row: datetime.fromisoformat(row['activity'][0]['at'].replace('Z', '+00:00')))
        view['generated_at'] = max(datetime.fromisoformat(result['recorded_at'].replace('Z', '+00:00')),
            datetime.fromisoformat(latest['activity'][0]['at'].replace('Z', '+00:00'))).astimezone(timezone.utc).isoformat()
        view['availability'] = 'ROOT_OBSERVED_PROGRESS'; view['blocker'] = latest['blockers'][0]
    else:
        view['generated_at'] = result['recorded_at']; view['availability'] = 'HISTORICAL_REVIEW'
        view['blocker'] = 'Exact captured session history; current run eligibility and active plan binding require independent installed observation.'
    return validate_publication(value)
