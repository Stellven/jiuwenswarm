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
from pathlib import Path

from deploy.m1.rsi_development_run import (encoded, need, protected, exclusive,
    prepare_work_contexts)


async def prepare_session(*, core, library, runner, operator, records, lease_records,
                          value, parent_body, parent_declaration, visible_context):
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.uploads import UploadManager
    from jiuwenswarm.research.intake import extract_document, qualify_intake
    from jiuwenswarm.research_rsi.capsule_session import SCHEMA, validate_session, MAX_BODY_BYTES
    from jiuwenswarm.research_rsi.targets.capsule_executor import validate_grant
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule, public_fixtures
    grant = value['grant']
    validate_grant(grant, value['runtime_manifest'])
    target = registered_capsule(grant['capsule_name'])
    need(grant['roles'] == ['parent', 'candidate'] and len(parent_body) <= MAX_BODY_BYTES
         and hashlib.sha256(parent_body).hexdigest() == grant['parent_sha256'], 'EXACT_MUTATION_GRANT_AND_PARENT_REQUIRED')
    need(parent_declaration['identity']['name'] == grant['capsule_name']
         and parent_declaration['identity']['carrier']['ref'] == target.carrier_path.removeprefix('research/')
         and any(row['path'] == target.carrier_path.removeprefix('research/') and row['sha256'] == grant['parent_sha256']
                 for row in parent_declaration['identity']['body']), 'ORIGINAL_DECLARATION_BODY_DIFFERS')
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
    for run_id in prepared['run_contexts']:
        core.reserve_uploads(run_id, [row['id'] for row in uploaded])
    for key in ('diagnosis_contract_ref', 'proposal_contract_ref'):
        contract = core.read_record(prepared[key], contract_id='subnode-execution-contract')
        runner._require_child_authority(prepared[key], contract)
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
    session = validate_session({'schema': SCHEMA, 'id': grant['run_id'], 'capsule_name': grant['capsule_name'],
        'grant': grant, 'grant_ref': grant_ref, 'parent_body_ref': parent_ref,
        'parent_declaration_ref': parent_declaration_ref, 'visible_context_ref': visible_ref,
        'preparation_ref': preparation_ref, 'configuration_ref': exact['configuration_ref'],
        'diagnosis_contract_ref': prepared['diagnosis_contract_ref'],
        'proposal_contract_ref': prepared['proposal_contract_ref'], 'native_scope_ref': native_scope_ref,
        'authorized_component': target.carrier_path, 'observed_symptom': value['observed_symptom']})
    return {'schema': 'ai4r-rsi-capsule-prepared:1', 'session': session,
            'run_contexts': prepared['run_contexts'], 'intake_ref': intake_ref,
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
    need(set(value) == fields and value['schema'] == 'ai4r-rsi-capsule-prepare-configuration:1',
         'CLOSED_ROOT_PREPARATION_CONFIGURATION_REQUIRED')
    exact = value['exact_binding_refs']
    core = SQLiteRunStore(value['core_root'], recover=False, input_root=value['input_root'])
    records, leases = RecordStore(value['record_root']), RecordStore(value['native_lease_root'])
    try:
        configuration = core.read_record(exact['configuration_ref'])
        operator = OperatorConfiguration.from_mapping(configuration.get('operator', configuration), resolve_profile=core.read_record)
        need(operator.snapshot()['cc']['router']['enabled'] is False, 'FIXED_NATIVE_MODEL_REQUIRED')
        library = LibraryService(core, executor=None)
        library.check_assets.bind_calibration_runtime(exact['protected_options']['calibration_runtime_ref'],
            **{key: exact[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')})
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
