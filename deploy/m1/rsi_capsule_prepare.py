"""Model-free preparation of one finite whole-capsule development session.

The Root caller supplies an exact isolated deployment binding and finite public
originals. Existing records are appended, never reseeded or rewritten. This
module creates ordinary upload/intake and ContractFactory work contracts only.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

from deploy.m1.rsi_development_run import (encoded, need, protected, exclusive,
    prepare_work_contexts, validate_calibration_binding)


LOOP_DEFAULTS = {'max_iterations': 5, 'max_no_progress': 3, 'trials': 3}


def iteration_run_id(run_id, role, iteration):
    """Run-context id of one loop iteration's governed work (iteration 1 is
    the historical ``rsi-development:<id>:<role>``)."""
    return 'rsi-development:' + run_id + ':' + role + ('' if iteration == 1 else ':' + str(iteration))



def validate_iteration_run_ids(run_id, max_iterations):
    """Reject invalid derived contract identifiers before consuming preparation."""
    need(type(max_iterations) is int and 1 <= max_iterations <= 100,
         'FINITE_LOOP_MAX_ITERATIONS_REQUIRED')
    need(isinstance(run_id, str), 'VALID_WORK_RUN_ID_REQUIRED')
    for iteration in range(1, max_iterations + 1):
        for role in ('diagnosis', 'proposal'):
            derived = iteration_run_id(run_id, role, iteration)
            need(re.fullmatch(r'[a-z0-9][a-z0-9_.:-]{0,63}', derived) is not None,
                 'DERIVED_WORK_RUN_ID_EXCEEDS_CONTRACT: ' + derived)


def loop_settings(loop):
    """Closed preparation view of ``session['loop']`` with documented defaults."""
    need(isinstance(loop, dict) and 'model_backend' in loop, 'EXPLICIT_MODEL_BACKEND_REQUIRED')
    settings = {**LOOP_DEFAULTS, **{key: item for key, item in loop.items() if key != 'contracts'}}
    for key in LOOP_DEFAULTS:
        need(type(settings[key]) is int and 1 <= settings[key] <= 100, 'FINITE_LOOP_' + key.upper() + '_REQUIRED')
    return settings


def prepare_iteration_work_contexts(*, core, library, runner, operator, exact, intake_ref, run_ids,
                                    work_capsule_refs, account_id):
    """The ordinary ContractFactory work-context preparation, for explicit ids.

    Same Intent/verifier admission checks, ports, limits and authority ceiling
    as the frozen ``prepare_work_contexts`` (whose ids are fixed to
    ``rsi-development:<action>:<role>``); only the run-context ids differ, so
    loop iterations k >= 2 get ``rsi-development:<id>:<role>:<k>``.
    """
    from jiuwenswarm.research.binding import ContractFactory
    from jiuwenswarm.research.compiler import input_port
    entries = {}
    for stage in ('intent', 'verifier'):
        declaration = core.read_record(work_capsule_refs[stage], contract_id='capsule-declaration')
        entry = library.get(declaration['identity']['name'], declaration['identity']['version_label'])
        need(entry['standing'] == 'active' and entry['declaration_ref'] == work_capsule_refs[stage], 'EXACT_INSTALLED_CAPSULE_REQUIRED')
        admission = core.read_record(entry['admission_ref'], contract_id='library-admission')
        need(admission['status'] == 'admitted', 'REAL_ADMISSION_REQUIRED')
        entries[stage] = dict(entry, pin=admission['cc'])
    intent, verifier = entries['intent'], entries['verifier']
    factory = ContractFactory(core, library, verifier_pin=verifier['pin'],
                              finalization_profile_ref=exact['protected_options']['finalization_profile_ref'])
    declaration = core.read_record(intent['declaration_ref'], contract_id='capsule-declaration')
    intake = core.read_record(intake_ref, contract_id='qualified-intake')
    ports = [input_port('request', 'qualified-intake:field-contract:2', intake_ref)]
    outputs = [{'name': row['name'], 'contract_id': row['schema_ref'],
                'version': ContractFactory._version(row['schema_ref']), 'required': row['required']}
               for row in declaration['ports']['outputs']]
    contracts, contexts = {}, {}
    for role in ('diagnosis', 'proposal'):
        run_id = run_ids[role]
        core.create_run(run_id, account_id=account_id, workspace_id=exact['workspace_id'], submission={'intake_ref': intake_ref})
        parent_ref = factory.prepare_parent(run_id, role,
            [{'subnode_id': role, 'cc': intent['pin'], 'depends_on': []}], inputs=ports, outputs=outputs,
            objective='Unqualified development ' + role, requirement_ids=['rsi_'+role],
            limits={'time_s': 240, 'model_calls': 2, 'memory_mb': 256},
            policy_ref=operator.snapshot()['cc']['plan_policy_ref'], configuration_ref=exact['configuration_ref'],
            template_ref=exact['protected_options']['compiler_template_ref'], authority_ceiling={
                'network': 'none', 'network_allowlist': [], 'tools': [], 'write_roots': [],
                'resource_reads': [intake_ref, intake['request_ref'], *intake['source_refs']]})
        contract, _, _ = factory.bind_subnode(parent_ref, role, ports, role='work')
        contexts[run_id] = {**{k: exact[k] for k in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
                            'router': operator.snapshot()['cc']['router'],
                            'run_limits': {'time_s': 240, 'model_calls': 2, 'memory_mb': 256}}
        runner.configure_run(run_id, **contexts[run_id])
        contracts[role+'_contract_ref'] = contract
    return dict(contracts, run_contexts=contexts)


async def prepare_session(*, core, library, runner, operator, records, lease_records,
                          value, parent_body, parent_declaration, visible_context):
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.uploads import UploadManager
    from jiuwenswarm.research.intake import extract_document, qualify_intake
    from jiuwenswarm.research_rsi.capsule_session import SCHEMA, validate_session, MAX_BODY_BYTES
    from jiuwenswarm.research_rsi.targets.capsule_executor import validate_grant
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule, public_fixtures, release_binding
    from jiuwenswarm.research_rsi.targets.capsule_executor import LOOP_GRANT_SCHEMA, grant_fixtures, loop_budget_for
    grant = value['grant']
    validate_grant(grant, value['runtime_manifest'])
    target = registered_capsule(grant['capsule_name'])
    loop = loop_settings(value['loop']) if value.get('loop') is not None else None
    validate_iteration_run_ids(grant['run_id'], loop['max_iterations'] if loop is not None else 1)
    from jiuwenswarm.research.utility_rsi_scope import require_scope
    exact_scope = value['exact_binding_refs']
    scope_configuration = core.read_record(exact_scope['configuration_ref'])
    utility_scope = require_scope(core, scope_configuration.get('operator', scope_configuration), exact_scope['protected_options'])
    if utility_scope is not None:
        need(utility_scope == {'schema': 'ai4r-utility-rsi-scope:1',
            'targets': ['utility.calculate', 'utility.table_normalize'],
            'work_stages': ['intent', 'verifier'], 'setup_model_calls': 12,
            'rsi_model_calls_per_target': 10, 'product_eligible': False}, 'EXACT_UTILITY_RSI_SCOPE_REQUIRED')
        need(grant['capsule_name'] in utility_scope['targets'] and loop is not None
             and loop['model_backend'] == {'kind': 'host-codex'}
             and loop['max_iterations'] <= 5, 'UTILITY_RSI_TARGET_AND_MODEL_BUDGET_REQUIRED')
    if loop is not None:
        # Budget derived from the loop configuration by the owner's function:
        # parent trials plus candidate trials for every iteration over the
        # grant's case list, plus (with a slot-materialized benchmark sizing)
        # the exact per-call benchmark jobs for the A/A baseline and every
        # iteration -- the same call the slot sizes the grant with.
        need(grant['schema'] == LOOP_GRANT_SCHEMA and grant['max_executions'] >= loop_budget_for(
            grant['capsule_name'], loop, case_count=len(grant_fixtures(grant))),
             'LOOP_GRANT_EXECUTION_BUDGET_TOO_SMALL')
    need(grant['roles'] == ['parent', 'candidate'] and len(parent_body) <= MAX_BODY_BYTES
         and hashlib.sha256(parent_body).hexdigest() == grant['parent_sha256'], 'EXACT_MUTATION_GRANT_AND_PARENT_REQUIRED')
    need(parent_declaration['identity']['name'] == grant['capsule_name']
         and parent_declaration['identity']['carrier']['ref'] == target.carrier_path.removeprefix('research/')
         and any(row['path'] == target.carrier_path.removeprefix('research/') and row['sha256'] == grant['parent_sha256']
                 for row in parent_declaration['identity']['body']), 'ORIGINAL_DECLARATION_BODY_DIFFERS')
    selected_release = None
    if value['runtime_manifest'].get('schema') == 'ai4r-rsi-capsule-runtime:2':
        selected_release = value['runtime_manifest']['target_bindings'][grant['capsule_name']]
        need(encoded(selected_release) == encoded(release_binding(grant['capsule_name'])),
             'FROZEN_RELEASE_BINDING_DIFFERS')
        need(parent_declaration['identity']['version_label'] == selected_release['version_label']
             and hashlib.sha256(encoded(parent_declaration)).hexdigest() == selected_release['declaration_sha256'],
             'EXACT_SELECTED_RELEASE_DECLARATION_REQUIRED')
    need(visible_context == {'schema': 'ai4r-rsi-whole-capsule-public-context:1',
        'capsule_name': grant['capsule_name'], 'mutable_path': target.carrier_path,
        'fixtures': public_fixtures(grant['capsule_name']),
        'metrics': list(target.metrics), 'labels': 'PUBLIC'}, 'EXACT_FINITE_PUBLIC_CONTEXT_REQUIRED')
    # Exclusive claim precedes all intake/contracts; a partial preparation is
    # retained for reconciliation and never silently retried.
    claim = Path(value['preparation_claim'])
    exclusive(claim, {'schema': 'ai4r-rsi-capsule-preparation-start:1', 'id': grant['run_id'],
                      'grant_sha256': hashlib.sha256(encoded(grant)).hexdigest()})
    exact = value['exact_binding_refs']
    parent_ref = core.put_blob(parent_body, media_type='text/x-python')
    parent_declaration_ref = core.put_blob(encoded(parent_declaration), media_type='application/json')
    visible_ref = core.put_blob(encoded(visible_context), media_type='application/json')
    grant_ref = records.put(grant)
    originals = [(parent_ref, parent_body), (parent_declaration_ref, encoded(parent_declaration)),
                 (visible_ref, encoded(visible_context)), (grant_ref, encoded(grant))]
    # Actual public originals directly enter the ordinary qualified intake.
    # Checking corpora, private records and account material are never traversed.
    document = encoded({'schema': 'ai4r-rsi-authorized-request-context:1',
        'purpose': 'Public whole-capsule development diagnosis and proposal only; no tools',
        'originals': [{'ref': ref, 'utf8': raw.decode('utf8')} for ref, raw in originals]})
    actor = Principal(value['account_id'], frozenset({exact['workspace_id']}),
                      frozenset({'upload', 'ingest'}), frozenset({'researcher'}))
    uploads = UploadManager(core, value['input_root'], extract_document,
                            extraction_timeout_s=30, max_upload_bytes=4*1024*1024)
    prefix = 'capsule-' + hashlib.sha256(grant['run_id'].encode('utf8')).hexdigest()[:32]
    documents = [(prefix+'-context.txt', document)] + [
        (prefix+'-source-'+ref['sha256']+'.txt', raw) for ref, raw in originals]
    uploaded = [await uploads.upload(actor, 'docs', exact['workspace_id'], name, raw)
                for name, raw in documents]
    options = exact['protected_options']
    intake_ref = qualify_intake(core, actor, value['request_text'], [row['id'] for row in uploaded],
        workspace_id=exact['workspace_id'], profile_ref=options['profile_ref'],
        workspace_ref=options['workspace_ref'], input_directory_ref=options['input_directory_ref'])
    prepared = prepare_work_contexts(core=core, library=library, runner=runner, operator=operator,
        exact=exact, intake_ref=intake_ref, action_id=grant['run_id'],
        work_capsule_refs=value['work_capsule_refs'], account_id=value['account_id'])
    pairs = [prepared]
    for iteration in range(2, (loop or {}).get('max_iterations', 1) + 1):
        # One genuine single-call diagnosis+proposal work pair per iteration.
        pairs.append(prepare_iteration_work_contexts(core=core, library=library, runner=runner, operator=operator,
            exact=exact, intake_ref=intake_ref, work_capsule_refs=value['work_capsule_refs'],
            account_id=value['account_id'], run_ids={role: iteration_run_id(grant['run_id'], role, iteration)
                                                      for role in ('diagnosis', 'proposal')}))
    run_contexts = {}
    for pair in pairs:
        run_contexts.update(pair['run_contexts'])
        for run_id in pair['run_contexts']:
            core.reserve_uploads(run_id, [row['id'] for row in uploaded])
        for key in ('diagnosis_contract_ref', 'proposal_contract_ref'):
            contract = core.read_record(pair[key], contract_id='subnode-execution-contract')
            runner._require_child_authority(pair[key], contract)
            runner._require_check_assets(contract)
            need(contract['bindings'][0]['role'] == 'work' and contract['subnode_limits']['model_calls'] == 1,
                 'GENUINE_SINGLE_CALL_INTENT_WORK_REQUIRED')
    # Scope is the same exact account/profile owner, with a new finite session
    # identity. The global subscription service still enforces actual ownership.
    native_scope_ref = lease_records.put({'schema': 'ai4r-rsi-capsule-native-scope:1',
        'run_id': grant['run_id'], 'account_root': value['account_root'],
        'configuration_ref': exact['configuration_ref'], 'deployment_ref': exact['deployment_ref']})
    preparation_ref = records.put({'schema': 'ai4r-rsi-capsule-preparation:1',
        'grant_ref': grant_ref, 'intake_ref': intake_ref, 'work_contexts': prepared,
        'public_original_refs': [ref for ref, _ in originals], 'model_calls': 0,
        'security': 'UNQUALIFIED', 'production_mutation': False})
    session_value = {'schema': SCHEMA, 'id': grant['run_id'], 'capsule_name': grant['capsule_name'],
        'grant': grant, 'grant_ref': grant_ref, 'parent_body_ref': parent_ref,
        'parent_declaration_ref': parent_declaration_ref, 'visible_context_ref': visible_ref,
        'preparation_ref': preparation_ref, 'configuration_ref': exact['configuration_ref'],
        'diagnosis_contract_ref': prepared['diagnosis_contract_ref'],
        'proposal_contract_ref': prepared['proposal_contract_ref'], 'native_scope_ref': native_scope_ref,
        'authorized_component': target.carrier_path, 'observed_symptom': value['observed_symptom']}
    if selected_release is not None:
        session_value['release_binding'] = selected_release
    if loop is not None:
        session_value['loop'] = {**{key: item for key, item in value['loop'].items() if key != 'contracts'},
            'contracts': [{key: pair[key] for key in ('diagnosis_contract_ref', 'proposal_contract_ref')}
                          for pair in pairs[1:]]}
        # The loop owner's own derivation must name exactly the prepared ids.
        from jiuwenswarm.research_rsi.capsule_loop import loop_run_context_ids
        need(loop_run_context_ids(session_value) == set(run_contexts), 'LOOP_RUN_CONTEXT_IDS_DIFFER')
    session = validate_session(session_value)
    return {'schema': 'ai4r-rsi-capsule-prepared:1', 'session': session,
            'run_contexts': run_contexts, 'intake_ref': intake_ref,
            'uploaded_ids': [row['id'] for row in uploaded], 'model_calls': 0}


async def prepare_configuration(value):
    """Closed, path-free public materials; all paths belong to Root config."""
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.runner import Registry, CapsuleRunner
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research_rsi.records import RecordStore
    fields = {'schema', 'core_root', 'input_root', 'record_root', 'native_lease_root',
        'account_root', 'account_id', 'preparation_claim', 'output_path', 'exact_binding_refs',
        'work_capsule_refs', 'grant', 'runtime_manifest', 'parent_body', 'parent_declaration',
        'visible_context', 'request_text', 'observed_symptom'}
    # ``loop`` (model backend + iteration limits) is optional: without it the
    # historical single-attempt session is prepared unchanged.
    need(fields <= set(value) <= fields | {'loop'} and value['schema'] == 'ai4r-rsi-capsule-prepare-configuration:1',
         'CLOSED_ROOT_PREPARATION_CONFIGURATION_REQUIRED')
    exact = value['exact_binding_refs']
    core = SQLiteRunStore(value['core_root'], recover=False, input_root=value['input_root'])
    records, leases = RecordStore(value['record_root']), RecordStore(value['native_lease_root'])
    try:
        configuration = core.read_record(exact['configuration_ref'])
        operator = OperatorConfiguration.from_mapping(configuration.get('operator', configuration), resolve_profile=core.read_record)
        need(operator.snapshot()['cc']['router']['enabled'] is False, 'FIXED_NATIVE_MODEL_REQUIRED')
        library = LibraryService(core, executor=None)
        validate_calibration_binding(core, exact, operator)

        verifier = core.read_record(value['work_capsule_refs']['verifier'], contract_id='capsule-declaration')
        entry = library.get(verifier['identity']['name'], verifier['identity']['version_label'])
        library.configure_verifier(core.read_record(entry['admission_ref'], contract_id='library-admission')['cc'])
        runner = CapsuleRunner(core, Registry(), CheckRegistry(), model=None, check_assets=library.check_assets)
        result = await prepare_session(core=core, library=library, runner=runner, operator=operator,
            records=records, lease_records=leases, value=value, parent_body=value['parent_body'].encode('utf8'),
            parent_declaration=value['parent_declaration'], visible_context=value['visible_context'])
        exclusive(value['output_path'], result)
        return result
    finally:
        leases.close(); records.close(); core.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--configuration-sha256', required=True)
    args = parser.parse_args(argv)
    need(os.name == 'posix' and os.geteuid() == 12001, 'ISOLATED_CORE_OWNER_REQUIRED')
    raw = protected(args.configuration, owner=0, maximum=4*1024*1024).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == args.configuration_sha256, 'EXACT_ROOT_CONFIGURATION_REQUIRED')
    from deploy.m1.rsi_development_run import closed_json
    result = asyncio.run(prepare_configuration(closed_json(raw)))
    print(json.dumps({'status': 'PREPARED_NOT_DISPATCHED', 'id': result['session']['id'], 'model_calls': 0}))


if __name__ == '__main__':
    main()
