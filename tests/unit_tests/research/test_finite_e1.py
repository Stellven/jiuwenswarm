"""Finite E1 authority controls; component cases never prove a live campaign."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import Binder, plan_checks
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore


def plan_inputs():
    root = Path('tests/fixtures/research/planning')
    return [json.loads((root / name).read_bytes()) for name in (
        'static_template.json', 'lifecycle_research_brief.json', 'library_snapshot.json',
        'resource_inventory.json', 'plan_policy.json')]


async def observe_compile(store, *, protected, submission=None):
    calls = []

    async def compiler(run_id, context):
        calls.append((run_id, copy.deepcopy(context)))
        return {'accepted': False}

    service = ResearchService(store, registry=Registry(), model=None, compiler=compiler)
    store.create_run('run:finite-control', account_id='owner', workspace_id='work', submission=submission or {})
    await service._execute('run:finite-control', protected)
    return calls, store.get_run('run:finite-control')


@pytest.mark.asyncio
async def test_unresolved_protected_finite_binding_never_starts_compiler(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        unavailable = {'id': 'finite-binding:unresolved', 'sha256': '7' * 64}
        calls, run = await observe_compile(store, protected={'finite_e1_binding_ref': unavailable})
        assert calls == [], 'A missing finite adapter must block before Compiler; ordinary fallback invents provenance.'
        assert run['state'] == 'halted'
        assert not list(store.iter_records(kinds=('run-plan', 'gate-decision', 'acceptance-commit')))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ordinary_mode_still_starts_exactly_one_compiler(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        calls, run = await observe_compile(store, protected={})
        assert len(calls) == 1
        assert run['state'] == 'halted' and run['reason'] == 'compiler_did_not_release'
    finally:
        store.close()


@pytest.mark.asyncio
async def test_client_profile_name_and_marker_do_not_authorize_finite_execution(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        calls, _ = await observe_compile(store, protected={}, submission={
            'profile_id': 'qa_capsule_screening_v1', 'invalid_for_product': True})
        assert len(calls) == 1
        assert not list(store.iter_records(kinds=('finite-e1-fixture-qualification', 'run-plan')))
    finally:
        store.close()


def test_ordinary_partial_template_keeps_delivery_and_required_stage_rejection():
    source, brief, library, resources, policy = plan_inputs()
    source['nodes'] = [node for node in source['nodes'] if node['node_id'] == 'screening']
    source['nodes'][0]['predecessors'] = []
    _, results = plan_checks(source, brief, library, resources, policy, plan_source='static')
    assert next(row for row in results if row['check_id'] == 'delivery_leaf_coverage')['outcome'] == 'FAIL'


def test_ordinary_binder_rejects_schema_valid_unaccepted_imported_brief(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        source, brief, _, _, _ = plan_inputs()
        source_ref = store.put_blob(json.dumps(source).encode())
        brief_ref = store.put_blob(json.dumps(brief).encode())
        other = store.put_blob(b'not used before accepted-Brief check')
        with pytest.raises(ResearchError) as observed:
            Binder(store, None, None).freeze(source_ref, brief_ref, other, other, other, other)
        assert observed.value.code == 'unaccepted_input'
        assert not store.is_accepted(brief_ref)
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'run-plan')))
    finally:
        store.close()


@pytest.mark.parametrize('binding', [None, {}, {'schema': 'ai4r-finite-e1-binding:1'},
    {'schema': 'ai4r-finite-e1-binding:1', 'id': 'client:marker', 'invalid_for_product': True}],
    ids=['missing', 'empty', 'partial', 'marker'])
def test_finite_owner_requires_exact_protected_binding_without_defaults(tmp_path, binding):
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from tests.unit_tests.research.test_operator_config import valid_config

    store = SQLiteRunStore(tmp_path)
    try:
        operator = OperatorConfiguration.from_mapping(valid_config())
        configuration = store.append_record('approved-configuration', {'operator': operator.snapshot()})
        offered = store.append_record('finite-e1-binding', binding) if binding else None
        with pytest.raises(ResearchError):
            FiniteE1(store, operator, binding_ref=offered, configuration_ref=configuration, library=None)
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'run-plan')))
    finally:
        store.close()


def test_finite_owner_refuses_binding_registered_under_foreign_kind(tmp_path):
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from tests.unit_tests.research.test_operator_config import valid_config

    store = SQLiteRunStore(tmp_path)
    try:
        operator = OperatorConfiguration.from_mapping(valid_config())
        configuration = store.append_record('approved-configuration', {'operator': operator.snapshot()})
        ref = store.put_blob(b'visible fixture')
        forged = store.append_record('evaluation-case-binding', {
            'schema': 'ai4r-finite-e1-binding:1', 'id': 'finite:foreign-kind',
            'profile_ref': ref, 'configuration_ref': configuration, 'template_ref': ref,
            'policy_ref': ref, 'qualification_policy_ref': ref})
        with pytest.raises(ResearchError):
            FiniteE1(store, operator, binding_ref=forged, configuration_ref=configuration, library=None)
        assert not list(store.iter_records(kinds=('finite-e1-fixture-qualification', 'run-plan')))
    finally:
        store.close()


def finite_case_definition():
    """Independent approved visible slots: request bytes come from intake."""
    case = {'case_id': 'campaign__screening__fixed__r01', 'request_sha256': '1' * 64,
        'uploads': [
            {'filename': 'brief.json', 'kind': 'datasets', 'role': 'brief',
             'contract_id': 'research-brief', 'artifact_ref': {'id': 'brief:visible', 'sha256': '2' * 64}, 'source': 'original'},
            {'filename': 'candidates.json', 'kind': 'datasets', 'role': 'candidate_set',
             'contract_id': 'candidate-set', 'artifact_ref': {'id': 'candidate:visible', 'sha256': '3' * 64}, 'source': 'original'}],
        'inputs': {'brief': 'brief', 'candidate_set': 'candidate_set', 'original_request': 'original_request'},
        'module_scope': {'mandatory_requirements': [], 'deliverables': [
            {'id': 'deliverable:card', 'name': 'opportunity_card.json', 'description': 'Ranked module result', 'artifact_type': 'opportunity_card'}],
            'acceptance_expectations': [], 'evidence_obligations': [], 'target_metrics': []}}
    policy = {'limits': {'max_uploads': 8, 'max_total_bytes': 1048576, 'max_member_bytes': 262144,
                        'max_visible_refs': 16, 'max_archive_members': 16, 'max_archive_uncompressed_bytes': 1048576}}
    template = {'nodes': [{'outputs': [{'name': 'opportunity_card', 'artifact_type': 'opportunity_card'}]}]}
    return case, policy, template


def test_direct_intake_request_needs_no_redundant_upload_or_resource_wrapper():
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    case, policy, template = finite_case_definition()
    FiniteE1._validate_case(case, set(case['inputs']), policy, template)


def test_visible_support_allows_multiple_files_and_paired_original_extraction():
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    case, policy, template = finite_case_definition()
    case['uploads'].extend([
        {'filename': 'source.txt', 'kind': 'docs', 'role': 'visible_support', 'contract_id': None,
         'artifact_ref': {'id': 'source:original', 'sha256': '4' * 64}, 'source': 'original'},
        {'filename': 'source.txt', 'kind': 'docs', 'role': 'visible_support', 'contract_id': None,
         'artifact_ref': {'id': 'source:extracted', 'sha256': '5' * 64}, 'source': 'extracted'},
        {'filename': 'scope.json', 'kind': 'datasets', 'role': 'visible_support', 'contract_id': 'search-scope',
         'artifact_ref': {'id': 'search_scope', 'sha256': '6' * 64}, 'source': 'original'}])
    FiniteE1._validate_case(case, set(case['inputs']), policy, template)


@pytest.mark.parametrize('fault', ['public_kind', 'duplicate_slot', 'ambiguous_primary', 'id_collision', 'report_promise'])
def test_closed_visible_policy_rejects_transport_and_scope_ambiguity(fault):
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    case, policy, template = finite_case_definition()
    if fault == 'public_kind':
        case['uploads'][0]['kind'] = 'resources'
    elif fault == 'duplicate_slot':
        case['uploads'].append(copy.deepcopy(case['uploads'][0]))
    elif fault == 'ambiguous_primary':
        other = copy.deepcopy(case['uploads'][0]);other['filename'] = 'second_brief.json'
        case['uploads'].append(other)
    elif fault == 'id_collision':
        case['uploads'][1]['artifact_ref']['id'] = case['uploads'][0]['artifact_ref']['id']
    else:
        case['module_scope']['deliverables'][0]['artifact_type'] = 'research_report'
    with pytest.raises(ResearchError):
        FiniteE1._validate_case(case, set(case['inputs']), policy, template)


# Append to the existing finite tests only after its active frozen run closes.
async def visible_run(tmp_path, *, ambient_ref=False, archive=False, segment=False, injected_fault=None):
    """Actual upload/intake/state; explicitly controlled checking eligibility."""
    import hashlib
    import io
    import zipfile
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.intake import qualify_intake
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.profiles import EvaluationProfiles
    from jiuwenswarm.research.state import json_bytes
    from jiuwenswarm.research.uploads import UploadManager
    from tests.unit_tests.research.test_budget_ceiling import installed_library
    from tests.unit_tests.research.test_operator_config import valid_config

    store, registry, checks, library, installed, operator_actor = await installed_library(tmp_path, scientific=True)
    actor = Principal('owner', frozenset({'work'}), frozenset({'upload', 'ingest', 'submit', 'status'}))
    request = b'Rank the supplied candidate ideas and return the scoring record and selected opportunity card. This is a bounded Screening module evaluation; do not promise an experiment, measurements or research report.'
    if segment:
        request = b'Rank the supplied visible ideas, select one opportunity and freeze one hypothesis blueprint using the supplied baseline and validation resources. This is a bounded two-node module evaluation; do not implement, execute or promise research results.'
    request_ref = store.put_blob(request)
    payloads = []

    def visible(filename, value, role='visible_support', contract=None):
        raw = value if isinstance(value, bytes) else json_bytes(value)
        ref = {'id': 'visible:' + filename, 'sha256': hashlib.sha256(raw).hexdigest()}
        payloads.append((filename, raw, role, contract, ref))
        return ref

    context_ref = visible('context.txt', b'Visible original fixture context')
    extra_inputs = {}
    if segment:
        requirements = visible('requirements.txt', b'# Controlled prepared environment; no packages required.\n')
        approval = visible('approval.txt', b'Controlled static prepared-environment approval; no security qualification claim.\n')
        environment_ref = visible('environment.json', {'schema_version': '1.0.0', 'id': 'environment_lock',
            'platform': 'Controlled CPython on Linux', 'requirements_ref': requirements, 'package_refs': [],
            'approval_ref': approval}, contract='environment-lock')
        for role, filename, raw in [('baseline_resource', 'baseline.txt', b'Visible unchanged baseline fixture'),
                                    ('validation_resource', 'validation.txt', b'Visible fixed validation fixture')]:
            body_ref = visible(filename, raw)
            extra_inputs[role] = visible(role + '.json', {'schema_version': '1.0.0', 'id': role,
                'kind': 'supplied baseline' if role == 'baseline_resource' else 'supplied validation data',
                'origin': 'Owned visible controlled file', 'revision': 'controlled-v1',
                'files': [{'path': filename, 'artifact_ref': body_ref, 'media_type': 'text/plain', 'audience': 'authorized researcher'}],
                'access': 'read-only experiment', 'license': 'synthetic fixture', 'availability': 'available',
                'environment_ref': environment_ref}, role, 'resource-snapshot')
    original_intake = visible('original_intake.json', {
        'schema_version': '2.0.0', 'id': 'intake:visible-source', 'request_ref': request_ref,
        'source_refs': [], 'offset_basis': 'Unicode code points', 'resource_refs': list(extra_inputs.values()), 'upload_refs': [],
        'rejected_inputs': [], 'user_id': 'owner', 'profile_ref': context_ref,
        'workspace_ref': context_ref, 'input_directory_ref': context_ref}, contract='qualified-intake')
    intent = json.loads(Path('tests/fixtures/research/compiler/intent_ir.json').read_bytes())

    def replace_refs(value):
        if isinstance(value, dict):
            if set(value) == {'id', 'sha256'}:
                return request_ref
            return {key: replace_refs(nested) for key, nested in value.items()}
        if isinstance(value, list):
            return [replace_refs(nested) for nested in value]
        return value

    intent = replace_refs(intent)
    intent['interpretation']['requested_result']['text'] = 'Frozen hypothesis blueprint from ranked visible ideas' if segment else 'Scoring record and selected opportunity card'
    for item in intent['interpretation'].values():
        item['source_spans'] = [{'source_ref': request_ref, 'start': 0, 'end': len(request.decode())}]
    intent_ref = visible('intent.json', intent, contract='intent-ir')
    brief = replace_refs(json.loads(Path('tests/fixtures/research/planning/lifecycle_research_brief.json').read_bytes()))
    brief['schema_version'] = '3.0.0'
    brief.update(intent_ref=intent_ref, intake_ref=original_intake, constraints=[], target_metrics=[], input_bindings=[], resource_refs=[])
    brief['mandatory_requirements'] = [{'id': 'requirement:ranking', 'text': 'Score and rank the visible ideas and preserve their identities',
        'origin': 'user', 'source_refs': [request_ref]}]
    brief['deliverables'] = [
        {'id': 'deliverable:scores', 'name': 'screening_result.json', 'description': 'Bounded score and ranking record', 'artifact_type': 'screening_result'},
        {'id': 'deliverable:card', 'name': 'opportunity_card.json', 'description': 'Selected Top1 opportunity card', 'artifact_type': 'opportunity_card'}]
    brief['acceptance_expectations'] = [{'id': 'acceptance:ranking', 'requirement_ids': ['requirement:ranking'], 'description': 'The pair agrees on the selected idea'}]
    brief['evidence_obligations'] = [{'id': 'evidence:ranking', 'requirement_ids': ['requirement:ranking'], 'description': 'Retain the exact score/rank/card pair'}]
    if segment:
        brief['mandatory_requirements'][0]['text'] = 'Rank supplied ideas and freeze one bounded testable hypothesis'
        brief['deliverables'] = [{'id': 'deliverable:blueprint', 'name': 'hypothesis_blueprint.json',
            'description': 'One frozen hypothesis blueprint; no implementation or experiment results', 'artifact_type': 'hypothesis_blueprint'}]
        brief['acceptance_expectations'][0]['description'] = 'The blueprint uses the selected opportunity and exact visible resources'
        brief['evidence_obligations'][0]['description'] = 'Retain ranking, committed opportunity and original frozen blueprint provenance'
        brief['resource_refs'] = list(extra_inputs.values())
    if ambient_ref:
        brief['context_refs'] = [store.put_blob(b'ambient record that was never an allowed upload')]
    brief_ref = visible('brief.json', brief, 'brief', 'research-brief')
    citation_raw = b'Indexed lookup avoids repeated scans of the same visible records.'
    citation = visible('citation.txt', citation_raw)
    scope = {'schema_version': '1.0.0', 'id': 'search_scope', 'brief_ref': brief_ref,
        'connectors': ['local_documents'], 'max_queries': 1, 'max_hits_per_query': 1,
        'local_document_refs': [citation], 'topic_hints': []}
    scope_ref = visible('scope.json', scope, contract='search-scope')
    candidates = json.loads(Path('tests/fixtures/research/pipeline/source-valid/candidate_set.json').read_bytes())
    candidates.pop('ext', None)
    candidates.update(brief_ref=brief_ref, scope_ref=scope_ref, queries=['indexed lookup'],
        connector_outcomes=[{'connector': 'local_documents', 'status': 'used', 'reason': 'One supplied visible source', 'citations_captured': 1}],
        citations=[{'id': 'citation:index', 'source_ref': citation, 'connector': 'local_documents', 'query': 'indexed lookup',
            'title': 'Visible source', 'locator': 'citation.txt', 'char_start': 0, 'char_end': len(citation_raw),
            'excerpt': citation_raw.decode(), 'excerpt_sha256': citation['sha256']}], ideas=candidates['ideas'][:1])
    candidates['ideas'][0]['citation_ids'] = ['citation:index']
    candidate_ref = visible('candidates.json', candidates, 'candidate_set', 'candidate-set')
    if archive:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as package:
            package.writestr('baseline.txt', b'visible baseline')
        visible('baseline.zip', buffer.getvalue())

    source, _, _, _, policy = plan_inputs()
    source['id'] = 'finite_screening_visible'
    source['template_name'] = 'qa_capsule_screening_v1'
    node = next(value for value in source['nodes'] if value['node_id'] == 'screening')
    node['cc'] = installed['screening']['pin']
    node['predecessors'] = []
    node['deliverable_ids'] = ['all_deliverables']
    node['limits'] = {'time_s': 240, 'model_calls': 3, 'memory_mb': 512}
    for port in node['inputs']:
        if port['name'] == 'candidate_set':
            port.update(source_kind='accepted_ref', run_input_key='candidate_set', accepted_ref=None, future=None)
    source['nodes'] = [node]
    source['coverage'] = [{'selector': selector, 'node_ids': ['screening']} for selector in
        ['all_mandatory_requirements', 'all_deliverables', 'all_evidence_obligations']]
    source['limits'] = dict(node['limits'])
    stages = ['research.screening']
    candidate_pins = [installed['screening']['pin']]
    if segment:
        node['deliverable_ids'] = []
        second = next(value for value in plan_inputs()[0]['nodes'] if value['node_id'] == 'hypothesis')
        second['cc'] = installed['hypothesis']['pin']
        second['deliverable_ids'] = ['all_deliverables']
        second['limits'] = {'time_s': 240, 'model_calls': 2, 'memory_mb': 512}
        source['nodes'] = [node, second]
        source['template_name'] = 'controlled_segment_v1'
        source['coverage'] = [{'selector': 'all_mandatory_requirements', 'node_ids': ['screening', 'hypothesis']},
            {'selector': 'all_deliverables', 'node_ids': ['hypothesis']},
            {'selector': 'all_evidence_obligations', 'node_ids': ['screening', 'hypothesis']}]
        source['limits'] = {'time_s': 480, 'model_calls': 5, 'memory_mb': 512}
        stages.append('research.hypothesis')
        candidate_pins.append(installed['hypothesis']['pin'])
    template_ref = store.put_record('static-template', source)
    policy.update(id='finite_visible_policy', required_stages=stages, allow_network=False,
                  aggregate_limits=dict(source['limits']))
    policy_ref = store.put_record('plan-policy', policy)
    snapshot_ref = library.snapshot(candidate_pins=candidate_pins)
    profile = {'schema_version': '1.0.0', 'id': 'profile:finite-visible', 'profile_id': 'controlled_segment_v1' if segment else 'qa_capsule_screening_v1',
        'plan_source': 'static', 'router_enabled': False, 'router_version': None, 'model_route': 'codex-cli-default',
        'library_snapshot_sha256': snapshot_ref['sha256'], 'candidate_pins': candidate_pins,
        'verifier_cc_ref': installed['verifier']['declaration_ref'], 'invalid_for_product': True, 'allowed_entry_points': ['E1', 'E4'] if injected_fault else ['E1']}
    profile_ref = store.put_record('evaluation-profile', profile)
    configuration = valid_config()
    configuration['cc'].update(static_template_ref=template_ref, plan_policy_ref=policy_ref, evaluation_profile_ref=profile_ref)
    operator = OperatorConfiguration.from_mapping(configuration, resolve_profile=store.read_record)
    configuration_ref = store.append_record('approved-configuration', {'operator': configuration})
    fault_plan_ref = None
    if injected_fault:
        fault_plan_ref = store.append_record('evaluation-fault-plan', {'schema': 'ai4r-evaluation-faults:1',
            'id': 'faults:controlled-segment', 'profile_ref': profile_ref, 'campaign_id': 'component',
            'fault_plan': [{'fault_id': 'fault:controlled-hold', 'kind': 'delay_gate_persistence',
                'target': {'node_id': 'screening', 'artifact_type': None},
                'parameters': {'node_id': 'screening', 'delay_s': 2},
                'expected_observation_sha256': hashlib.sha256(b'Controlled assertion: successor absent before node commit').hexdigest()}]})
        actor = Principal(actor.account_id, actor.workspace_ids, actor.operations | {'evaluation_profile'}, actor.audiences)
    profiles = EvaluationProfiles(store, operator, fault_plan_ref=fault_plan_ref)
    uploader = UploadManager(store, store.input_root, None, extraction_timeout_s=10, max_upload_bytes=1048576)
    uploads = []
    slots = []
    for filename, raw, role, contract, ref in payloads:
        kind = 'repo' if filename.endswith('.zip') else 'datasets'
        uploads.append(await uploader.upload(actor, kind, 'work', filename, raw))
        slots.append({'filename': filename, 'kind': kind, 'role': role, 'contract_id': contract,
                      'artifact_ref': ref, 'source': 'original'})
    host_context = store.put_blob(b'Actual protected account/workspace context')
    intake_ref = qualify_intake(store, actor, request.decode(), [row['id'] for row in uploads], workspace_id='work',
        profile_ref=host_context, workspace_ref=host_context, input_directory_ref=host_context)
    case = {'case_id': 'component__screening__fixed__r01', 'request_sha256': request_ref['sha256'],
        'uploads': slots, 'inputs': {key: key for key in ['brief', 'candidate_set', 'original_request', *extra_inputs]},
        'module_scope': {key: copy.deepcopy(brief[key]) for key in ['mandatory_requirements', 'deliverables', 'acceptance_expectations', 'evidence_obligations', 'target_metrics']}}
    qualification = {'schema': 'ai4r-finite-e1-qualification-policy:1', 'id': 'qualification:finite-visible',
        'profile_ref': profile_ref, 'template_ref': template_ref, 'plan_policy_ref': policy_ref,
        'stages': stages, 'terminal_ports': [port['name'] for port in source['nodes'][-1]['outputs']],
        'limits': {'max_uploads': 16, 'max_total_bytes': 1048576, 'max_member_bytes': 262144, 'max_visible_refs': 32,
                   'max_archive_members': 16, 'max_archive_uncompressed_bytes': 1048576}, 'cases': [case]}
    qualification_ref = store.append_record('finite-e1-qualification-policy', qualification)
    binding_ref = store.append_record('finite-e1-binding', {'schema': 'ai4r-finite-e1-binding:1', 'id': 'binding:finite-visible',
        'profile_ref': profile_ref, 'configuration_ref': configuration_ref, 'template_ref': template_ref,
        'policy_ref': policy_ref, 'qualification_policy_ref': qualification_ref})
    inventory = {'schema_version': '1.0.0', 'id': 'finite_visible_inventory', 'resources': [
        {'resource_key': 'original_request', 'kind': 'file', 'available': True, 'quantity': None, 'ref': request_ref}]}
    if segment:
        inventory['resources'].extend({'resource_key': key, 'kind': 'file', 'available': True, 'quantity': None, 'ref': ref} for key, ref in {**extra_inputs, 'environment_lock': environment_ref}.items())
    protected = {'configuration_ref': configuration_ref, 'profile_id': profile['profile_id'], 'library_snapshot_ref': snapshot_ref,
        'verifier_cc_ref': profile['verifier_cc_ref'], 'candidate_pins': profile['candidate_pins'], 'plan_source': 'static',
        'finite_e1_binding_ref': binding_ref, 'resource_inventory_ref': store.put_record('resource-inventory', inventory),
        'profile_ref': host_context, 'workspace_ref': host_context, 'input_directory_ref': host_context,
        'run_pins': {'app_build': 'controlled-component', 'client_contract_version': '1.0.0', 'library_snapshot_sha256': snapshot_ref['sha256'],
            'plan_policy_ref': policy_ref, 'check_bundle_set_sha256': __import__('jiuwenswarm.research.run_evidence', fromlist=['check_bundle_digest']).check_bundle_digest(store.read_record(snapshot_ref)), 'router_enabled': False, 'router_version': None}}
    submission = {'schema_version': '1.0.0', 'id': 'submission:finite-visible', 'client_request_id': 'finite-visible-1',
        'account_id': 'owner', 'workspace_id': 'work', 'intake_ref': intake_ref, 'configuration_ref': configuration_ref,
        'plan_source': 'static', 'profile_id': profile['profile_id'], 'evaluation': {
            'campaign_id': 'component', 'run_id': case['case_id'], 'inventory_id': 'finite_visible_inventory'}}
    if injected_fault:
        submission['fault_id'] = 'fault:controlled-hold'
    store.create_run('run:finite-visible', account_id='owner', workspace_id='work', submission=submission)
    profiles.bind_run('run:finite-visible', submission, protected, principal=actor)
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    owner = FiniteE1(store, operator, binding_ref=binding_ref, configuration_ref=configuration_ref, library=library)
    if segment:
        protected['host_records'] = {'environment_lock': environment_ref}
    owner._component_profiles = profiles
    return store, owner, protected, uploads, {'brief': brief_ref, 'candidate_set': candidate_ref, 'original_request': request_ref, **extra_inputs}, registry, checks


@pytest.mark.asyncio
async def test_live_owned_visible_uploads_qualify_without_producing_acceptance(tmp_path):
    from jiuwenswarm.research.finite_evaluation import QUALIFICATION_CHECKS
    store, owner, protected, uploads, inputs, _, _ = await visible_run(tmp_path)
    try:
        receipt_ref = owner.qualify('run:finite-visible', protected)
        receipt = store.read_record(receipt_ref)
        assert receipt['status'] == 'qualified' and receipt['invalid_for_product'] is True
        assert receipt['input_refs'] == inputs
        assert [row['check_id'] for row in receipt['results']] == list(QUALIFICATION_CHECKS)
        assert all(row['outcome'] == 'PASS' for row in receipt['results'])
        assert all(not store.is_accepted(ref) for ref in inputs.values())
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'model-call', 'dispatch-start')))
        assert owner.qualify('run:finite-visible', protected) == receipt_ref
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['deleted_upload', 'ambient_ref', 'inventory_swap', 'id_collision', 'archive_adapter'])
async def test_qualification_rejects_unowned_closure_or_blocks_missing_adapter(tmp_path, fault):
    store, owner, protected, uploads, inputs, _, _ = await visible_run(tmp_path, ambient_ref=fault == 'ambient_ref', archive=fault == 'archive_adapter')
    try:
        if fault == 'deleted_upload':
            store.delete_upload(uploads[0]['id'], 'owner')
        elif fault == 'inventory_swap':
            value = store.read_record(protected['resource_inventory_ref']);value['id'] = 'finite_swapped_inventory'
            value['resources'][0]['ref'] = store.put_blob(b'other request')
            protected['resource_inventory_ref'] = store.put_record('resource-inventory', value)
        elif fault == 'id_collision':
            store.put_blob(b'other immutable body', record_id=inputs['brief']['id'])
        receipt = store.read_record(owner.qualify('run:finite-visible', protected))
        if fault == 'archive_adapter':
            assert receipt['status'] == 'qualified' and receipt['reason'] is None
            original = next(row for row in uploads if row['filename'] == 'baseline.zip')
            raw = store.read_upload(original['id'], 'owner')
            slot = next(row for row in next(iter(owner._cases.values()))['uploads'] if row['filename'] == 'baseline.zip')
            assert slot['artifact_ref'] in receipt['visible_refs']
            assert store.read_blob(slot['artifact_ref']) == raw
        else:
            assert receipt['status'] in {'rejected', 'blocked'} and receipt['reason']
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'model-call', 'dispatch-start')))
    finally:
        store.close()


# Adopt after the active frozen source run completes.
@pytest.mark.asyncio
async def test_qualified_import_freezes_genuine_finite_plan_without_acceptance_fiction(tmp_path):
    import inspect
    from jiuwenswarm.research.finite_evaluation import FINITE_PLAN_CHECKS, FiniteE1
    store, owner, protected, _, inputs, _, checks = await visible_run(tmp_path)
    try:
        qualification_ref = owner.qualify('run:finite-visible', protected)
        assert store.read_record(qualification_ref)['status'] == 'qualified'
        context = owner.plan_context('run:finite-visible', protected)
        binder = Binder(store, owner.library, checks, finite_e1=owner)
        binding = store.read_record(owner.binding_ref)
        plan_ref = binder.freeze(binding['template_ref'], inputs['brief'], protected['library_snapshot_ref'],
            protected['resource_inventory_ref'], binding['policy_ref'], binding['configuration_ref'],
            plan_source='static', finite_context=context)
        plan = store.read_record(plan_ref, contract_id='run-plan')
        assert plan['frozen'] is True and plan['brief_ref'] == inputs['brief']
        assert [node['cc']['cc_name'] for node in plan['nodes']] == ['research.screening']
        candidate_port = next(port for port in plan['nodes'][0]['inputs'] if port['name'] == 'candidate_set')
        assert candidate_port['accepted_ref'] == inputs['candidate_set']
        proof = store.read_record(plan['acceptance_ref'], contract_id='deterministic-check-result')
        assert [row['check_id'] for row in proof['results']] == list(FINITE_PLAN_CHECKS)
        assert all(row['outcome'] == 'PASS' for row in proof['results'])
        assert 'delivery_leaf_coverage' not in [row['check_id'] for row in proof['results']]
        check_plan = store.read_record(proof['check_plan_ref'], contract_id='bound-check-plan')
        assert any(store.read_blob(ref) == Path(inspect.getfile(FiniteE1)).read_bytes()
                   for ref in check_plan['runner_refs'])
        binder.validate_acceptance(plan)
        assert not store.is_accepted(inputs['brief']) and not store.is_accepted(inputs['candidate_set'])
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'model-call', 'dispatch-start')))
        records = list(store.iter_records(run_id='run:finite-visible', kinds=('finite-e1-plan-binding',)))
        assert len(records) == 1 and records[0]['record']['plan_ref'] == plan_ref
        assert records[0]['record']['qualification_ref'] == qualification_ref
        assert binder.freeze(binding['template_ref'], inputs['brief'], protected['library_snapshot_ref'],
            protected['resource_inventory_ref'], binding['policy_ref'], binding['configuration_ref'],
            plan_source='static', finite_context=context) == plan_ref
        assert len(list(store.iter_records(run_id='run:finite-visible', kinds=('finite-e1-plan-binding',)))) == 1
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['foreign_template', 'foreign_policy', 'foreign_inventory', 'forged_context', 'deleted_after_qualification'])
async def test_finite_static_plan_cannot_outlive_or_widen_exact_qualification(tmp_path, fault):
    store, owner, protected, uploads, inputs, _, checks = await visible_run(tmp_path)
    try:
        owner.qualify('run:finite-visible', protected)
        context = owner.plan_context('run:finite-visible', protected)
        binder = Binder(store, owner.library, checks, finite_e1=owner)
        binding = store.read_record(owner.binding_ref)
        source_ref, policy_ref = binding['template_ref'], binding['policy_ref']
        inventory_ref = protected['resource_inventory_ref']
        if fault == 'foreign_template':
            value = store.read_record(source_ref);value['id'] = 'foreign_finite_template'
            source_ref = store.put_record('static-template', value)
        elif fault == 'foreign_policy':
            value = store.read_record(policy_ref);value['id'] = 'foreign_finite_policy'
            policy_ref = store.put_record('plan-policy', value)
        elif fault == 'foreign_inventory':
            value = store.read_record(inventory_ref);value['id'] = 'foreign_finite_inventory'
            inventory_ref = store.put_record('resource-inventory', value)
        elif fault == 'forged_context':
            context = {'invalid_for_product': True, 'qualification_ref': owner.qualify('run:finite-visible', protected)}
        else:
            store.delete_upload(uploads[0]['id'], 'owner')
        with pytest.raises(ResearchError):
            binder.freeze(source_ref, inputs['brief'], protected['library_snapshot_ref'], inventory_ref,
                policy_ref, binding['configuration_ref'], plan_source='static', finite_context=context)
        assert not list(store.iter_records(kinds=('run-plan', 'gate-decision', 'acceptance-commit', 'dispatch-start')))
    finally:
        store.close()


async def finite_execution_fixture(tmp_path, fault, *, segment=False, injected_fault=None):
    from jiuwenswarm.research.binding import ContractFactory
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.capsules.assets import register_research_capsules
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.runner import CapsuleRunner
    from jiuwenswarm.research.scheduler import Scheduler
    store, owner, protected, uploads, inputs, registry, checks = await visible_run(tmp_path, segment=segment, injected_fault=injected_fault)
    row = owner.library.get('research.screening', owner._profile['candidate_pins'][0]['cc_version'])
    association = owner.library.association(row['declaration_ref'])
    asset = {'declaration_ref': row['declaration_ref'], 'body_refs': row['body_refs'],
        'bundle_ref': association['bundle_ref'], 'profile_ref': association['profile_ref'],
        'runner_ref': store.read_record(association['bundle_ref'])['checks'][0]['runner_ref'],
        'implementation_refs': tuple(row['body_refs'][body['path']] for body in store.read_record(row['declaration_ref'])['identity']['body'])}
    register_research_capsules(registry, checks, owner.library, store, assets={'screening': asset})
    if segment:
        row_h = owner.library.get('research.hypothesis', owner._profile['candidate_pins'][1]['cc_version'])
        assoc_h = owner.library.association(row_h['declaration_ref'])
        asset_h = {'declaration_ref': row_h['declaration_ref'], 'body_refs': row_h['body_refs'],
            'bundle_ref': assoc_h['bundle_ref'], 'profile_ref': assoc_h['profile_ref'],
            'runner_ref': store.read_record(assoc_h['bundle_ref'])['checks'][0]['runner_ref'],
            'implementation_refs': tuple(row_h['body_refs'][body['path']] for body in store.read_record(row_h['declaration_ref'])['identity']['body'])}
        register_research_capsules(registry, checks, owner.library, store, assets={'hypothesis': asset_h})
    final = store.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': 'finite_final',
        'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
        'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
    verifier = store.read_record(owner._profile['verifier_cc_ref'])['identity']
    factory = ContractFactory(store, owner.library, verifier_pin={'cc_name': verifier['name'],
        'cc_version': verifier['version_label'], 'declaration_sha256': owner._profile['verifier_cc_ref']['sha256']}, finalization_profile_ref=final)
    runner = CapsuleRunner(store, registry, checks, model=None, check_assets=owner.library.check_assets, faults=owner._component_profiles if injected_fault else None)
    selection = store.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': 'finite_fixed',
        'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
        'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0,
            'output_tokens': 0, 'disclosure_scope': []}, 'alternate_model_id': None, 'policy_ref': owner._binding['policy_ref']})
    protected.update(model_selection_profile_ref=selection, deployment_ref=store.put_blob(b'Actual controlled subscription binding'),
        router=copy.deepcopy(owner._operator['cc']['router']), run_limits=copy.deepcopy(owner._policy['aggregate_limits']),
        authority_ceiling={'network': 'none', 'network_allowlist': [], 'resource_reads': [inputs['brief'], inputs['candidate_set'], inputs['original_request'], store.read_record(store.get_run('run:finite-visible')['submission']['intake_ref'])['request_ref'], row['body_refs']['screening_rubric.json']], 'write_roots': [], 'tools': []},
        host_records=dict(protected.get('host_records', {}), screening_rubric=row['body_refs']['screening_rubric.json']))
    if segment:
        protected['authority_ceiling']['resource_reads'].extend([*inputs.values(), protected['host_records']['environment_lock']])
    prompts = []
    class ControlledSubscription:
        async def invoke_governed(self, prompt, *, model, timeout_s):
            prompts.append(prompt)
            payload = json.loads(prompt.split('<subject_payload>\n', 1)[1].split('\n</subject_payload>', 1)[0])
            if set(payload) == {'subject_declaration', 'subject_output'}:
                criteria = json.loads(prompt.split('Criteria for this output:\n', 1)[1].split('\n\n<subject_payload>', 1)[0])
                reply = {'findings': [{'criterion_id': c['criterion_id'], 'outcome': 'FAIL' if fault == 'review_failure' else 'PASS',
                    'reason': 'Controlled independent reply; no semantic quality claim'} for c in criteria],
                    'uncertainties': [], 'limitations': [], 'required_correction': 'Controlled rejection' if fault == 'review_failure' else None}
            elif 'input_refs' in payload and 'opportunity' in payload:
                reply = json.loads(Path('tests/fixtures/research/pipeline/source-valid/hypothesis_blueprint.json').read_bytes())
                reply.pop('ext', None)
                reply.pop('dependent_variables')
                reply.update(brief_ref=payload['input_refs']['brief'], opportunity_ref=payload['input_refs']['opportunity'],
                    validation_resource_ref=payload['input_refs']['validation_resource'],
                    resource_refs=[payload['input_refs']['baseline_resource'], payload['input_refs']['validation_resource']],
                    environment_ref=payload['baseline_resource']['environment_ref'], constraints=[])
                reply['baseline_identity'].update(resource_ref=payload['input_refs']['baseline_resource'], revision='controlled-v1', entry_point='baseline.txt')
                # Generate the controlled reply for the current registered
                # protocol; the historical latency/quality fixture stays intact.
                reply['metrics'] = [dict(metric, aggregation='mean', target_id=None)
                                    for metric in payload['measurement_protocol']['metrics']]
                reply['outcome_rules'] = [
                    {'metric_id': metric['metric_id'],
                     'success': {'operand': 'treatment', 'comparator': 'gt' if metric['direction'] == 'higher_better' else 'lt',
                                 'reference': 'baseline', 'factor': 1, 'offset': 0},
                     'falsification': {'operand': 'treatment', 'comparator': 'le' if metric['direction'] == 'higher_better' else 'ge',
                                       'reference': 'baseline', 'factor': 1, 'offset': 0},
                     'middle': 'INCONCLUSIVE', 'conditional_rule': None, 'conditional_meaning': None}
                    for metric in reply['metrics']]
            else:
                scores = json.loads(Path('tests/fixtures/research/pipeline/source-valid/screening_result.json').read_bytes())['scores'][:1]
                if fault == 'invalid_score': scores[0]['total'] = 15
                reply = {'scores': scores, 'opportunity_statement': 'An exact visible index avoids repeated scans.'}
            return {'text': json.dumps(reply), 'identity': {'effective': None, 'basis': 'Controlled subscription fixture'},
                'usage': {}, 'provider_request_id': None, 'observed_runtime': True}
    runner.model = GovernedBridge(persist=store.append_record, authorize=runner.authorize_model_context,
        revalidate=runner.authorize_model_dispatch, subscription_service=ControlledSubscription(), validate_record=validate)
    binder = Binder(store, owner.library, checks, finite_e1=owner)
    scheduler = Scheduler(store, runner, factory, binder, library=owner.library)
    return store, owner, protected, inputs, scheduler, prompts


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['valid', 'invalid_score', 'review_failure', 'cancelled_before'])
async def test_finite_execution_uses_actual_scheduler_worker_independent_reviews_and_commits(tmp_path, fault):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, fault)
    try:
        if fault == 'cancelled_before':
            store.request_cancellation('run:finite-visible', 'owner', 'cancel:finite')
            with pytest.raises(ResearchError):
                await owner.execute('run:finite-visible', protected, scheduler=scheduler)
            assert not prompts and not list(store.iter_records(kinds=('dispatch-start', 'acceptance-commit', 'model-call-start')))
            return
        result = await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert result['status'] == ('completed' if fault == 'valid' else 'partial'), {'result': result, 'observations': [r['record'] for r in store.iter_records(kinds=('invocation-observation',))], 'failed_checks': [row for r in store.iter_records(kinds=('deterministic-check-result',)) for row in r['record']['results'] if row['outcome'] != 'PASS'], 'gates': [r['record']['reasons'] for r in store.iter_records(kinds=('gate-decision',))]}
        plan = store.read_record(result['plan_ref'], contract_id='run-plan')
        assert [n['cc']['cc_name'] for n in plan['nodes']] == ['research.screening']
        dispatches = list(store.iter_records(run_id='run:finite-visible', kinds=('dispatch-record',)))
        assert len(dispatches) == 1 and dispatches[0]['record']['phase'] == 'planned'
        assert dispatches[0]['record']['run_plan_ref'] == result['plan_ref']
        accepted = store.accepted_outputs('run:finite-visible', 'screening')
        if fault == 'valid':
            assert set(accepted) == {'screening_result', 'opportunity_card'}
            assert len(list(store.iter_records(kinds=('verifier-assessment',)))) == 2
            assert len(prompts) == 3
            assert all(store.is_accepted(ref, run_id='run:finite-visible') for ref in accepted.values())
        else:
            assert not accepted
            assert list(store.iter_records(kinds=('gate-decision',)))
            if fault == 'invalid_score':
                assert len(prompts) == 1 and not list(store.iter_records(kinds=('verifier-assessment',)))
                assert any(row['outcome'] == 'FAIL' and row['check_id'] != 'host_authority' for r in store.iter_records(kinds=('deterministic-check-result',)) for row in r['record']['results'])
            else:
                assert len(prompts) == 3 and len(list(store.iter_records(kinds=('verifier-assessment',)))) == 2
        assert not store.is_accepted(inputs['brief']) and not store.is_accepted(inputs['candidate_set'])
        assert all(row['record']['node_id'] == 'screening' for row in store.iter_records(kinds=('invocation-observation',)))
        assert not any(row['record'].get('phase') == 'pre_plan' for row in dispatches)
        before = len(prompts)
        assert await owner.execute('run:finite-visible', protected, scheduler=scheduler) == result
        assert len(prompts) == before
    finally:
        store.close()


@pytest.mark.asyncio
async def test_finite_bootstrap_resolves_exact_path_without_compiler_resources_or_full_template(tmp_path, monkeypatch):
    from jiuwenswarm.research import bootstrap_core
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    try:
        # Eligibility is explicitly controlled, as in all component fixtures;
        # real composition, exact byte resolution and registration execute.
        monkeypatch.setattr(bootstrap_core, 'LibraryService', lambda *a, **k: owner.library)
        actor = Principal('owner', workspace_ids=frozenset({'work'}), operations=frozenset({'submit', 'status'}))
        options = {key: copy.deepcopy(protected[key]) for key in ('finite_e1_binding_ref', 'profile_ref',
            'workspace_ref', 'input_directory_ref', 'resource_inventory_ref', 'authority_ceiling', 'host_records')}
        options['finalization_profile_ref'] = scheduler.factory.finalization_profile_ref
        result = await bootstrap_core.compose_core(store=store, operator=OperatorConfiguration.from_mapping(owner._operator, resolve_profile=store.read_record),
            model=None, executor=None, readiness=None, upload_manager=None, principal=actor,
            configuration_ref=protected['configuration_ref'], model_selection_profile_ref=protected['model_selection_profile_ref'],
            deployment_ref=protected['deployment_ref'], workspace_id='work', protected_options=options, initialize=False)
        assert not result.diagnostics, result.diagnostics
        assert result.service.finite_e1.binding_ref == owner.binding_ref
        assert result.compiler is None and result.planner is None and result.scheduler is not None
        assert result.static_template_ref == owner._binding['template_ref']
        assert set(result.installed) == {'verifier', 'screening'}
        assert not prompts and not list(store.iter_records(kinds=('dispatch-start', 'gate-decision', 'model-call-start', 'acceptance-commit')))
    finally:
        store.close()
