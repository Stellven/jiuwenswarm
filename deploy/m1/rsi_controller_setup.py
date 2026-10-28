"""Capture two unaccepted governed work contexts after real catalog admission.

This operator helper uploads only a finite, Root-approved public source view.
It never constructs a model owner, admits a Capsule, executes a fixture,
claims an invocation, assembles a private job, or starts an RSI session.
Mount this script beside rsi_operational_bootstrap.py, both read-only.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
from datetime import datetime, timezone

_bootstrap_spec = importlib.util.spec_from_file_location('rsi_controller_bootstrap',
    Path(__file__).with_name('rsi_operational_bootstrap.py'))
bootstrap = importlib.util.module_from_spec(_bootstrap_spec)
_bootstrap_spec.loader.exec_module(bootstrap)

APPROVAL = Path('/run/ai4r-rsi/controller-assembly.json')
SESSION_PUBLIC_ROOT = Path('/var/lib/ai4r-rsi-session-public')
STAGES = frozenset(('intent', 'requirements', 'planner', 'verifier', 'search', 'screening',
                    'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery'))
SOURCE_PATHS = frozenset(('targets/__init__.py', 'targets/ranking.py', 'worker.py', 'fixed_resources.py'))
need = bootstrap.need
encoded = bootstrap.encoded


def authorized(value):
    grant = bootstrap.protected_json(APPROVAL, root_owned=True)
    fields = {'schema', 'action_id', 'operations', 'request_text', 'expires_at', 'account_id',
              'configuration_ref', 'model_selection_profile_ref', 'deployment_ref', 'source_export_ref',
              'session_ref', 'target_profile_ref', 'worker_profile_ref', 'visible_context_ref', 'public_original_refs'}
    need(set(grant) == fields and grant['schema'] == 'ai4r-rsi-controller-assembly-approval:1'
         and grant['operations'] == ['ingest', 'upload', 'prepare_controller']
         and isinstance(grant['request_text'], str) and grant['request_text'].strip()
         and len(grant['request_text'].encode('utf8')) <= 8192
         and all(grant[key] == value[key] for key in ('account_id', 'configuration_ref', 'model_selection_profile_ref', 'deployment_ref')))
    import re
    need(isinstance(grant['action_id'], str) and re.fullmatch('[a-z0-9][a-z0-9_.:-]{0,79}', grant['action_id']))
    expiry = datetime.fromisoformat(grant['expires_at'].replace('Z', '+00:00'))
    need(expiry.tzinfo is not None and 0 < (expiry - datetime.now(timezone.utc)).total_seconds() <= 86400)
    need(isinstance(grant['public_original_refs'], list) and 1 <= len(grant['public_original_refs']) <= 96
         and len({encoded(pin) for pin in grant['public_original_refs']}) == len(grant['public_original_refs']))
    return grant


def public_context(public, value, grant):
    """Follow only finite named public positions, never a recursive Ref walk."""
    from jiuwenswarm.research_rsi.session_policy import _contracts
    from jiuwenswarm.research_rsi.profiles import freeze_profile, Limits
    from jiuwenswarm.research_rsi.worker import validate_profile, ref
    from jiuwenswarm.research_rsi.targets import registered_helper
    allowed = {encoded(pin) for pin in grant['public_original_refs']}
    materials = {}
    def read(pin):
        ref(pin)
        need(encoded(pin) in allowed)  # Ref is approved before opening bytes.
        raw = public.read(pin)
        need(isinstance(raw, bytes) and len(raw) <= 512 * 1024 and hashlib.sha256(raw).hexdigest() == pin['sha256'])
        raw.decode('utf8', errors='strict')
        try: document = json.loads(raw)
        except ValueError: document = None
        if isinstance(document, dict):
            tag = document.get('schema', '')
            need(not isinstance(tag, str) or not tag.startswith(('ai4r-rsi-calibration', 'ai4r-rsi-private-',
                'ai4r-rsi-fixture', 'ai4r-rsi-ranking-preparation', 'ai4r-rsi-helper-preparation',
                'ai4r-rsi-opportunity-preparation', 'ai4r-rsi-ranking-review', 'ai4r-rsi-opportunity-review',
                'ai4r-rsi-oracle', 'ai4r-subscription-account', 'ai4r-native-governed')))
        materials[encoded(pin)] = (pin, raw)
        return raw
    get = lambda pin: json.loads(read(pin))
    source = public.get(grant['source_export_ref'])
    need(source['schema'] == 'ai4r-rsi-parent-source-export:1' and source['status'] == 'NOT_ADMISSION'
         and source['stage'] == 'screening' and source['configuration_ref'] == value['configuration_ref']
         and source['installed_source_sha256'] == value['installed_source_sha256'])
    session = get(grant['session_ref']); _contracts().validate('rsi-session', session)
    target = get(grant['target_profile_ref']); parent = get(source['parent_declaration_ref'])
    freeze_profile(target, parent, _contracts().validate)
    worker = validate_profile(get(grant['worker_profile_ref']))
    limits = Limits.from_mapping(session['limits'])
    need(session['started_by'] == value['account_id'] and session['configuration_ref'] == value['configuration_ref']
         and session['target_profile_ref'] == grant['target_profile_ref']
         and session['parent_declaration_ref'] == source['parent_declaration_ref']
         and session['pass_count_repeats'] == 1
         and limits.max_attempts == 1 and limits.per_call_s == 120
         and worker['schema'] == 'ai4r-rsi-worker-profile:3' and worker['target_kind'] == 'ranking-v1'
         and worker['session_ref'] == grant['session_ref'] and worker['target_ref'] == grant['target_profile_ref']
         and worker['parent_ref'] == target['parent_ref'])
    for pin in [*source['parent_body_refs'].values(), *source['external_refs'].values()]: read(pin)
    need(set(source['parent_body_refs']) == {row['path'] for row in parent['identity']['body']})
    for row in parent['identity']['body']: need(source['parent_body_refs'][row['path']]['sha256'] == row['sha256'])
    external = {row['pin']['ref']: row['pin']['sha256'] for row in parent['needs']['external'] if row.get('pin')}
    need(set(source['external_refs']) == set(external)
         and all(source['external_refs'][name]['sha256'] == digest for name, digest in external.items()))
    need(source['parent_body_refs'][target['mutable_paths'][0]] == target['parent_ref'])
    visible = get(grant['visible_context_ref'])
    need(set(visible) == {'context', 'mandatory_fixtures', 'required_test_refs'}
         and visible['required_test_refs'] == target['required_test_refs']
         and len(visible['mandatory_fixtures']) == len(target['required_test_refs']) == 12)
    helper = registered_helper('ranking-v1')
    need(visible['context']['schema'] == 'ai4r-rsi-visible-ranking-cases:1'
         and visible['context']['parent_ref'] == target['parent_ref'] and len(visible['context']['cases']) == 12)
    cases = {row['id']: row for row in visible['context']['cases']}
    need(len(cases) == 12)
    seen = set()
    import jiuwenswarm.research_rsi as package
    source_root = Path(package.__file__).parent
    for item in visible['mandatory_fixtures']:
        need(set(item) == {'input_ref', 'test_ref'} and item['test_ref'] in target['required_test_refs'])
        seen.add(encoded(item['test_ref']))
        definition = get(item['test_ref'])
        need(definition['schema'] == 'ai4r-rsi-frozen-helper-test:1' and definition['target_kind'] == 'ranking-v1'
             and definition['parent_ref'] == target['parent_ref'] and definition['input_ref'] == item['input_ref']
             and definition['execution_performed'] is False and set(definition['source_refs']) == SOURCE_PATHS)
        case = cases[definition['case_id']]
        need(definition['input_ref']['sha256'] == hashlib.sha256(encoded(case['inputs'])).hexdigest()
             and definition['expected_ref']['sha256'] == hashlib.sha256(encoded(case['expected'])).hexdigest()
             and definition['development_export_ref']['sha256'] == hashlib.sha256(encoded(visible['context'])).hexdigest())
        inputs = get(item['input_ref'])
        need(inputs == case['inputs']); helper.validate_visible_inputs(inputs)
        need(get(definition['expected_ref']) == case['expected'])
        export = get(definition['development_export_ref'])
        need(export == visible['context'])
        for name, pin in definition['source_refs'].items(): need(read(pin) == (source_root / name).read_bytes())
    need(len(seen) == 12 and set(materials) == allowed)
    need(sum(len(raw) for _, raw in materials.values()) <= 4 * 1024 * 1024)
    # Original Ref identities and bytes remain visible and attributable. This
    # is an actual operator-attached source document, not an acceptance record.
    document = {'schema': 'ai4r-rsi-authorized-request-context:1', 'session_ref': grant['session_ref'],
                'purpose': 'One unaccepted bounded diagnosis and one proposal; no tools or hidden evidence',
                'originals': [{'ref': pin, 'utf8': raw.decode('utf8')} for pin, raw in
                              (materials[key] for key in sorted(materials))]}
    return encoded(document), source, session


async def capture_intake(core, actor, options, document, request_text):
    """Use the real upload/intake ownership path, with exact direct documents."""
    from jiuwenswarm.research.uploads import UploadManager
    from jiuwenswarm.research.intake import extract_document, qualify_intake
    uploads = UploadManager(core, bootstrap.ROOT / 'input', extract_document,
                            extraction_timeout_s=30, max_upload_bytes=4 * 1024 * 1024)
    documents = {'rsi-authorized-context.txt': document}
    for row in json.loads(document)['originals']:
        documents['rsi-source-' + row['ref']['sha256'] + '.txt'] = row['utf8'].encode('utf8')
    uploaded = [await uploads.upload(actor, 'docs', 'local', name, raw) for name, raw in sorted(documents.items())]
    intake = qualify_intake(core, actor, request_text, [row['id'] for row in uploaded], workspace_id='local',
        profile_ref=options['profile_ref'], workspace_ref=options['workspace_ref'],
        input_directory_ref=options['input_directory_ref'])
    return intake, uploaded


async def prepare_controller():
    value = bootstrap.load()
    grant = authorized(value)
    output_path = bootstrap.ROOT / 'controller-assembly.json'
    need(not output_path.exists() and not (bootstrap.ROOT / 'controller-assembly-started.json').exists())
    from jiuwenswarm.research_rsi.worker import PublicBytes
    public = PublicBytes([str(bootstrap.PUBLIC_ROOT), str(SESSION_PUBLIC_ROOT)])
    document, source, session = public_context(public, value, grant)
    from jiuwenswarm.research.accounts import AccountStore
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.bootstrap_core import compose_core
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.compiler import input_port
    from jiuwenswarm.research.binding import ContractFactory, validate_child_authority
    from jiuwenswarm.research.attempt_resources import attempt_resource_disposition
    with bootstrap.private_creation():
        accounts = AccountStore(bootstrap.ROOT / 'identity')
        core = SQLiteRunStore(bootstrap.ROOT / 'core', recover=False, input_root=bootstrap.ROOT / 'input')
        try:
            need(accounts.primary()['account_id'] == value['account_id'])
            binding = bootstrap.validate_capture(core, value)
            actor = Principal(value['account_id'], frozenset({'local'}), frozenset({'ingest', 'upload'}), frozenset({'researcher'}))
            operator = OperatorConfiguration.from_mapping(core.read_record(value['configuration_ref']))
            async def unavailable(_): raise ValueError('Metadata assembly cannot execute readiness')
            composition = await compose_core(store=core, operator=operator, model=None, executor=None,
                readiness=unavailable, upload_manager=None, principal=actor,
                configuration_ref=value['configuration_ref'], model_selection_profile_ref=value['model_selection_profile_ref'],
                deployment_ref=value['deployment_ref'], workspace_id='local', initialize=False,
                protected_options=binding['protected_options'])
            need(not composition.diagnostics and set(composition.installed) == STAGES)
            need(composition.installed['screening']['declaration_ref'] == source['parent_declaration_ref'])
            # An exclusive Root/action marker makes incomplete assembly explicit;
            # no changed grant or later retry can allocate extra runnable work.
            bootstrap.write_new(bootstrap.ROOT / 'controller-assembly-started.json', grant)
            options = binding['protected_options']
            # Each original is attached as exact document bytes as well as
            # appearing in the identity index. Thus qualified-intake.source_refs
            # directly grants the actual parent/helper/development contents to
            # InvocationContext.refs_in(inputs), without an ambient read grant.
            intake, uploaded = await capture_intake(core, actor, options, document, grant['request_text'])
            original = core.read_record(intake)
            ports = [input_port('request', 'qualified-intake:field-contract:2', intake)]
            work = composition.installed['intent']
            declaration = core.read_record(work['declaration_ref'])
            outputs = [{'name': row['name'], 'contract_id': row['schema_ref'],
                'version': ContractFactory._version(row['schema_ref']), 'required': row['required']} for row in declaration['ports']['outputs']]
            factory = composition.compiler.factory
            run_contexts = {}; contracts = {}; parents = {}
            for role in ('diagnosis', 'proposal'):
                run_id = 'rsi:' + grant['action_id'] + ':' + role
                core.create_run(run_id, account_id=value['account_id'], workspace_id='local', submission={'intake_ref': intake})
                core.reserve_uploads(run_id, [row['id'] for row in uploaded])
                authority = {'network': 'none', 'network_allowlist': [], 'tools': [], 'write_roots': [],
                    'resource_reads': [intake, original['request_ref'], *original['source_refs']]}
                parent = factory.prepare_parent(run_id, role,
                    [{'subnode_id': role, 'cc': work['pin'], 'depends_on': []}], inputs=ports, outputs=outputs,
                    objective='Unaccepted governed RSI ' + role + ' over the exact qualified permitted request context',
                    requirement_ids=['rsi_' + role], limits={'time_s': 240, 'model_calls': 2, 'memory_mb': 256},
                    policy_ref=operator.snapshot()['cc']['plan_policy_ref'], configuration_ref=value['configuration_ref'],
                    template_ref=options['compiler_template_ref'], authority_ceiling=authority)
                contract, check_plan, _ = factory.bind_subnode(parent, role, ports, role='work')
                actual = core.read_record(contract)
                validate_child_authority(core, parent, role, ports, effective_authority=actual['bindings'][0]['effective_authority'])
                need(actual['subnode_limits'] == {'time_s': 120, 'model_calls': 1, 'memory_mb': 256}
                     and not attempt_resource_disposition(core, parent).requires_broker)
                context = {key: value[key] for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')}
                context.update(router=operator.snapshot()['cc']['router'], run_limits={'time_s': 240, 'model_calls': 2, 'memory_mb': 256})
                composition.runner.configure_run(run_id, **context)
                composition.runner._require_child_authority(contract, actual)
                composition.runner._require_check_assets(actual)
                contracts[role] = contract; parents[role] = {'parent_ref': parent, 'check_plan_ref': check_plan}
                run_contexts[run_id] = context
            result = {'schema': 'ai4r-rsi-controller-assembly:1', 'status': 'PREPARED_NOT_STARTED',
                'account_id': value['account_id'], 'configuration_ref': value['configuration_ref'],
                'session_ref': grant['session_ref'], 'intake_ref': intake, 'uploaded_source_refs': original['source_refs'],
                'diagnosis_contract_ref': contracts['diagnosis'], 'proposer_contract_refs': [contracts['proposal']],
                'parents': parents, 'run_contexts': run_contexts, 'maximum_exposed_model_calls': 2,
                'reserved_review_dispatch': False, 'accepted': False, 'source_public_refs': grant['public_original_refs']}
            bootstrap.write_new(output_path, result)
            return result
        finally:
            core.close(); accounts.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('prepare-controller',))
    parser.add_argument('--generation', required=True)
    args = parser.parse_args(argv)
    bootstrap.select_generation(args.generation)
    print(json.dumps(asyncio.run(prepare_controller()), sort_keys=True))


if __name__ == '__main__':
    main()
