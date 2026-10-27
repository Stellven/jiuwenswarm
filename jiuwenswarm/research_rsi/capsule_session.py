"""One public whole-capsule development session: an iterative improvement loop.

Each iteration is one governed diagnosis plus one governed proposal, a Root
evaluation of the candidate and an Interface B score (see capsule_loop). This
controller interprets model responses as bytes only. Execution belongs to
the separately owned Root dispatcher; no candidate is imported by this module.
"""
from __future__ import annotations

import asyncio
import hashlib
import sqlite3

from .capsule_loop import (CapsuleLoop, load_objective, loop_configuration, loop_run_context_ids,
    new_loop_record, selected_iteration)
from .records import encoded
from .targets.capsules import registered_capsule, public_fixtures
from .targets.capsule_runtime import BOOTSTRAP_SCHEMA
from .targets.capsule_executor import (BINDING_SCHEMA, GRANT_SCHEMA, LOOP_GRANT_SCHEMA,
    MAX_LOOP_EXECUTIONS, pin)

SCHEMA = 'ai4r-rsi-capsule-session:1'
RESULT_SCHEMA = 'ai4r-rsi-capsule-session-result:1'
MAX_BODY_BYTES = 256 * 1024
# Historical single-attempt limits; loop limits are now session configuration.
LIMITS = dict(max_attempts=1, max_no_progress=1, wall_s=3600,
              per_call_s=120, session_query_limit=2, lifetime_query_limit=2)


def need(value, message):
    if not value:
        raise ValueError(message)


def validate_session(value):
    fields = {'schema', 'id', 'capsule_name', 'grant', 'grant_ref', 'parent_body_ref',
        'parent_declaration_ref', 'visible_context_ref', 'preparation_ref',
        'configuration_ref', 'diagnosis_contract_ref', 'proposal_contract_ref',
        'native_scope_ref', 'authorized_component', 'observed_symptom'}
    # ``loop`` is optional only for historical v1 sessions; when present it
    # must name its model backend (see capsule_loop.validate_loop_configuration).
    need(isinstance(value, dict) and fields <= set(value) <= fields | {'loop'} and value['schema'] == SCHEMA,
         'CLOSED_CAPSULE_SESSION_REQUIRED')
    target = registered_capsule(value['capsule_name'])
    need(target.public_evaluation_available, target.adapter_blocker)
    grant = value['grant']
    need(grant.get('schema') in (GRANT_SCHEMA, LOOP_GRANT_SCHEMA) and grant.get('bootstrap_schema') == BOOTSTRAP_SCHEMA,
         'GUARDED_BOOTSTRAP_GRANT_REQUIRED')
    # An iterative session needs the iterative (v3) grant and vice versa: a v2
    # grant authorizes exactly one parent and one candidate evaluation (its
    # exact role budget is enforced by capsule_executor.validate_grant), so it
    # can only back the historical single attempt.
    need((grant['schema'] == LOOP_GRANT_SCHEMA) == ('loop' in value), 'ITERATIVE_SESSION_REQUIRES_LOOP_GRANT')
    if grant['schema'] == LOOP_GRANT_SCHEMA:
        need(type(grant.get('max_executions')) is int and 0 < grant['max_executions'] <= MAX_LOOP_EXECUTIONS,
             'FINITE_LOOP_EXECUTION_BUDGET_REQUIRED')
    need(grant['run_id'] == value['id'] and grant['capsule_name'] == value['capsule_name']
         and grant['roles'] == ['parent', 'candidate']
         and grant['parent_sha256'] == value['parent_body_ref']['sha256'], 'EXACT_SESSION_GRANT_REQUIRED')
    for key in fields:
        if key.endswith('_ref'):
            pin(value[key])
    need(hashlib.sha256(encoded(grant)).hexdigest() == value['grant_ref']['sha256'], 'GRANT_DIGEST_DIFFERS')
    need(value['diagnosis_contract_ref'] != value['proposal_contract_ref'], 'DISTINCT_GOVERNED_WORK_REQUIRED')
    for key in ('authorized_component', 'observed_symptom'):
        need(isinstance(value[key], str) and 0 < len(value[key]) <= 4096, 'BOUNDED_CONTEXT_REQUIRED')
    need(value['authorized_component'] == target.carrier_path, 'EXACT_CARRIER_SCOPE_REQUIRED')
    loop_configuration(value)
    return value


def claim(store, value):
    """Consume before any effect; crashes and failures never imply a retry."""
    with store.lock:
        store.db.execute('CREATE TABLE IF NOT EXISTS capsule_session_claims(id TEXT PRIMARY KEY,ref TEXT NOT NULL)')
        reference = store.put(value)
        try:
            store.db.execute('INSERT INTO capsule_session_claims VALUES(?,?)', (value['id'], encoded(reference).decode()))
        except sqlite3.IntegrityError:
            raise ValueError('CAPSULE_SESSION_ALREADY_CLAIMED_NO_REPLAY') from None
    return reference


def validate_evaluation(result, value, role, candidate_ref):
    """Require protected Root evidence and the exact finite public inventory."""
    total = len(public_fixtures(value['capsule_name']))
    need(isinstance(result, dict) and result.get('schema') == 'ai4r-rsi-whole-capsule-visible-result:1'
         and result.get('role') == role and type(result.get('executions')) is int
         and 0 < result['executions'] <= total
         and type(result.get('passed_count')) is int and 0 <= result['passed_count'] <= result['executions']
         and result.get('passed') is (result['passed_count'] == total)
         and result.get('grant_ref') == value['grant_ref']
         and result.get('security') == 'UNQUALIFIED' and result.get('model_calls') == 0,
         'EXACT_ROOT_PUBLIC_EVALUATION_REQUIRED')
    pin(result['result_ref'])
    rows = result['rows']
    expected_ids = [row['id'] for row in public_fixtures(value['capsule_name'])]
    need(len(rows) == result['executions']
         and [row['fixture_id'] for row in rows] == expected_ids[:len(rows)]
         and all(row['candidate_ref'] == candidate_ref and row['group_empty'] is True
                 and row['runtime_manifest_sha256'] == value['grant']['runtime_manifest_sha256']
                 and row['receipt']['subject_ref'] == candidate_ref for row in rows)
         and sum(row['task_success'] for row in rows) == result['passed_count']
         and sum(row['protected_wall_s'] for row in rows) == result['protected_wall_s'], 'ACTUAL_PUBLIC_ROWS_REQUIRED')
    for row in rows:
        pin(row['evidence_ref'])
    return result


async def execute(value, runtime, *, models=None):
    """Claim once, then run the configured diagnose/propose/evaluate loop.

    ``models`` is an explicit unit-test seam: a ``ModelBackend`` of exactly the
    configured kind, or (historically) a flat list of once-only handles. When
    omitted the backend named by ``value['loop']['model_backend']`` is built;
    a v1 session without ``loop`` is the historical host-codex single attempt.
    Runtime composition supplies only the fixed governed resources and a Root
    IPC evaluator, and must drop controller authority before invoking this.
    """
    from .model_backends import ModelBackend, ExplicitHandles, backend_from_configuration
    value = validate_session(value)
    config = loop_configuration(value)
    store = runtime.store
    parent = store.read(value['parent_body_ref'])
    need(isinstance(parent, bytes) and 0 < len(parent) <= MAX_BODY_BYTES
         and hashlib.sha256(parent).hexdigest() == value['parent_body_ref']['sha256'], 'EXACT_BOUNDED_PARENT_REQUIRED')
    visible = store.get(value['visible_context_ref'])
    declaration = store.get(value['parent_declaration_ref'])
    target = registered_capsule(value['capsule_name'])
    need(declaration['identity']['name'] == value['capsule_name']
         and declaration['identity']['carrier']['ref'] == target.carrier_path.removeprefix('research/')
         and any(row['path'] == target.carrier_path.removeprefix('research/') and row['sha256'] == value['parent_body_ref']['sha256']
                 for row in declaration['identity']['body']), 'DECLARED_PARENT_BODY_DIFFERS')
    kind = config['model_backend']['kind']
    if models is None:
        backend = backend_from_configuration(config['model_backend'])
    elif isinstance(models, ModelBackend):
        need(models.kind == kind, 'MODEL_BACKEND_DIFFERS_FROM_CONFIGURATION')
        backend = models
    else:
        backend = ExplicitHandles(models, kind)
    backend.bind(runtime=runtime, session=value)
    objective = getattr(runtime, 'objective', None) or load_objective()
    session_ref = claim(store, value)
    loop = new_loop_record(config, backend.describe())
    result = {'schema': RESULT_SCHEMA, 'id': value['id'], 'capsule_name': value['capsule_name'],
        'session_ref': session_ref, 'security': 'UNQUALIFIED', 'security_campaigns': 'DEFERRED',
        'qualification_ref': None, 'package_ref': None, 'admission_ref': None, 'activation_ref': None,
        'hidden_evaluation': 'NOT_RUN', 'final_evaluation': 'NOT_RUN', 'parent_visible': None,
        'candidate_visible': None, 'candidate_ref': None, 'binding_ref': None, 'rationale': None,
        'diagnosis_ref': None, 'status': 'ERROR_NO_REPLAY', 'exception_type': None, 'loop': loop}
    parent_pin = {'cc_name': value['capsule_name'], 'cc_version': declaration['identity']['version_label'],
                  'declaration_sha256': value['parent_declaration_ref']['sha256']}
    engine = CapsuleLoop(value=value, runtime=runtime, backend=backend, objective=objective, config=config,
        target=target, parent=parent, visible=visible, parent_pin=parent_pin, loop=loop,
        **({'clock': runtime.clock} if callable(getattr(runtime, 'clock', None)) else {}))
    failure = None
    try:
        await engine.run()
    except Exception as error:
        failure = error
        loop['stop_reason'], loop['stop_detail'] = 'error', str(error)[:4096]
    finally:
        rows = loop['iterations']
        result['parent_visible'] = engine.raw_parent
        chosen = selected_iteration(loop)
        if chosen is not None:
            # Top level keeps the exact Root result (publication joins it by result_ref).
            raw = engine.raw_visible.get(chosen['iteration'])
            result.update(candidate_ref=chosen['candidate_ref'], candidate_visible=raw,
                rationale=chosen['rationale'], binding_ref=chosen['binding_ref'], diagnosis_ref=chosen['diagnosis_ref'],
                diagnosis_capture_ref=chosen['diagnosis_capture_ref'], proposal_prompt_ref=chosen['proposal_prompt_ref'],
                proposal_response_ref=chosen['proposal_response_ref'], proposal_capture=chosen['proposal_capture'],
                generating_model=chosen['generating_model'], selected_iteration=chosen['iteration'])
        else:
            result.update(diagnosis_capture_ref=None, proposal_prompt_ref=None, proposal_response_ref=None,
                          proposal_capture={}, generating_model=None, selected_iteration=None)
        result['generation_evidence_refs'] = [ref for row in rows for ref in row['generation_evidence_refs']]
        result['model_calls'] = sum(row['model_calls'] for row in rows) if engine.model_calls_known else None
        loop['model_calls'] = result['model_calls']
        evaluated = [row for row in rows if row['visible'] is not None]
        if evaluated and failure is None:
            result['status'] = 'VISIBLE_EVALUATED_UNQUALIFIED'
        if result['status'] == 'ERROR_NO_REPLAY' or loop['stop_reason'] == 'error':
            last = failure if failure is not None else next(
                (row['failure'] for row in reversed(rows) if row['failure'] is not None), None)
            if isinstance(last, BaseException):
                kind_name, message = type(last).__name__, str(last)
            elif last is not None:
                kind_name, message = last['exception_type'], last['message']
            else:
                kind_name, message = 'NoCandidateEvaluated', loop['stop_detail'] or 'No candidate was evaluated'
            result['exception_type'] = kind_name
            result['failure_ref'] = store.put({'schema': 'ai4r-rsi-capsule-session-failure:1',
                'session_ref': session_ref, 'exception_type': kind_name, 'message': str(message)[:4096],
                'stop_reason': loop['stop_reason']})
        result['limitations'] = ['Public synthetic fixtures only; no measured improvement inferred beyond the recorded scores.',
            'Security campaigns and qualification deferred; no production mutation authority.'] + loop['limitations']
        result['loop_ref'] = store.put(loop)
        result['result_ref'] = store.put(result)
    return result


async def run_session(value, runtime, *, models=None):
    # The loop stops itself before its configured deadline; this is the hard ceiling.
    config = loop_configuration(validate_session(value))
    return await asyncio.wait_for(execute(value, runtime, models=models),
                                  timeout=config['wall_s'] + 2 * config['per_call_s'] + 60)
