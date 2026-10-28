"""One public whole-capsule development attempt using governed model handles.

This controller interprets model responses as bytes only. Execution belongs to
the separately owned Root dispatcher; no candidate is imported by this module.
"""
from __future__ import annotations

import asyncio
import hashlib
import sqlite3

from .diagnosis import BoundedDiagnosis
from .profiles import Limits
from .proposer import GuardedProposer, proposal_context
from .records import encoded
from .targets.capsules import registered_capsule, public_fixtures
from .targets.capsule_runtime import BOOTSTRAP_SCHEMA
from .targets.capsule_executor import BINDING_SCHEMA, GRANT_SCHEMA, pin, validate_candidate_binding

SCHEMA = 'ai4r-rsi-capsule-session:1'
RESULT_SCHEMA = 'ai4r-rsi-capsule-session-result:1'
MAX_BODY_BYTES = 256 * 1024
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
    need(isinstance(value, dict) and set(value) == fields and value['schema'] == SCHEMA,
         'CLOSED_CAPSULE_SESSION_REQUIRED')
    target = registered_capsule(value['capsule_name'])
    need(target.public_evaluation_available, target.adapter_blocker)
    grant = value['grant']
    need(grant.get('schema') == GRANT_SCHEMA and grant.get('bootstrap_schema') == BOOTSTRAP_SCHEMA,
         'GUARDED_BOOTSTRAP_GRANT_REQUIRED')
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
    """Default handles reuse canonical IsolatedResources + NativeEffectLease.

    ``models`` is an explicit unit-test seam, never a provider configuration.
    Runtime composition supplies only the fixed governed resources and a Root
    IPC evaluator, and must drop controller authority before invoking this.
    """
    value = validate_session(value)
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
    session_ref = claim(store, value)
    if models is None:
        # Imported here to leave the ordinary library controller provider-free.
        factory = getattr(runtime, 'development_model_factory', None)
        if factory is None:
            from deploy.m1.rsi_development_run import DevelopmentModel
            factory = DevelopmentModel
        models = [factory(runtime.resources, runtime.lease, value[key], value['id'])
                  for key in ('diagnosis_contract_ref', 'proposal_contract_ref')]
    need(len(models) == 2 and models[0] is not models[1], 'TWO_SEPARATE_ONCE_ONLY_HANDLES_REQUIRED')
    diagnosis = BoundedDiagnosis(models[0], store=store, limits=Limits.from_mapping(LIMITS))
    proposer = GuardedProposer(models[1], configuration_ref=value['configuration_ref'],
        improver_ref=value['proposal_contract_ref'], limits=Limits.from_mapping(LIMITS), store=store)
    result = {'schema': RESULT_SCHEMA, 'id': value['id'], 'capsule_name': value['capsule_name'],
        'session_ref': session_ref, 'security': 'UNQUALIFIED', 'security_campaigns': 'DEFERRED',
        'qualification_ref': None, 'package_ref': None, 'admission_ref': None, 'activation_ref': None,
        'hidden_evaluation': 'NOT_RUN', 'final_evaluation': 'NOT_RUN', 'parent_visible': None,
        'candidate_visible': None, 'candidate_ref': None, 'binding_ref': None, 'rationale': None,
        'status': 'ERROR_NO_REPLAY', 'exception_type': None}
    try:
        baseline = validate_evaluation(await runtime.evaluate('parent', body=parent,
            candidate_ref=value['parent_body_ref'], binding=None), value, 'parent', value['parent_body_ref'])
        result['parent_visible'] = baseline
        need(baseline['passed'], 'PARENT_CONTROL_FAILED_NO_MODEL_CALL')
        evidence = [{'ref': value['visible_context_ref'], 'content': visible},
                    {'ref': baseline['result_ref'], 'content': baseline}]
        parent_pin = {'cc_name': value['capsule_name'], 'cc_version': declaration['identity']['version_label'],
                      'declaration_sha256': value['parent_declaration_ref']['sha256']}
        await runtime.before_model()
        diagnosed, diagnosis_ref = await diagnosis.diagnose(parent=parent_pin,
            profile_ref=value['preparation_ref'], preparation_ref=value['preparation_ref'],
            configuration_ref=value['configuration_ref'], authorized_component=value['authorized_component'],
            observed_symptom=value['observed_symptom'], evidence=evidence)
        result['diagnosis_ref'] = diagnosis_ref
        context = proposal_context({'visible': visible, 'diagnosis': diagnosed}, body=parent,
                                   history=[], mutable_path=target.carrier_path)
        await runtime.before_model()
        proposal = await proposer.propose(context, None)
        body = proposal['body'].encode('utf8')
        result.update(candidate_ref=store.put_bytes(body), rationale=proposal['rationale'])
        need(0 < len(body) <= MAX_BODY_BYTES, 'CANDIDATE_BODY_EXCEEDS_BOUND')
        binding = {'schema': BINDING_SCHEMA, 'run_id': value['id'], 'capsule_name': value['capsule_name'],
            'runtime_manifest_sha256': value['grant']['runtime_manifest_sha256'],
            'parent_sha256': value['parent_body_ref']['sha256'], 'mutable_path': target.carrier_path,
            'candidate_ref': result['candidate_ref'], 'grant_sha256': value['grant_ref']['sha256']}
        validate_candidate_binding(binding, value['grant'], result['candidate_ref'])
        result['binding_ref'] = store.put(binding)
        result['candidate_visible'] = validate_evaluation(await runtime.evaluate('candidate', body=body,
            candidate_ref=result['candidate_ref'], binding=binding), value, 'candidate', result['candidate_ref'])
        need(all(model.last_model_calls == 1 for model in models), 'TWO_ACTUAL_GOVERNED_CALLS_REQUIRED')
        result['status'] = 'VISIBLE_EVALUATED_UNQUALIFIED'
    except Exception as error:
        result['exception_type'] = type(error).__name__
        result['failure_ref'] = store.put({'schema': 'ai4r-rsi-capsule-session-failure:1',
            'session_ref': session_ref, 'exception_type': type(error).__name__, 'message': str(error)[:4096]})
    finally:
        result.update(diagnosis_capture_ref=diagnosis.last_capture_ref,
            proposal_prompt_ref=proposer.last_prompt_ref, proposal_response_ref=proposer.last_response_ref,
            proposal_capture=proposer.last_capture,
            generation_evidence_refs=[ref for model in models for ref in getattr(model, 'last_evidence', [])],
            generating_model=proposer.last_generating_model,
            model_calls=(sum(getattr(model, 'last_model_calls', None) or 0 for model in models)
                if all(type(getattr(model, 'last_model_calls', None)) is int
                       or getattr(model, 'used', None) is False for model in models) else None),
            limitations=['Public synthetic fixtures only; no measured improvement inferred.',
                         'Security campaigns and qualification deferred; no production mutation authority.'])
        result['result_ref'] = store.put(result)
    return result


async def run_session(value, runtime, *, models=None):
    return await asyncio.wait_for(execute(value, runtime, models=models), timeout=LIMITS['wall_s'])
