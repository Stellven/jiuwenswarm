"""Protected, model-free preparation of finite admitted E3 assignments.

This module is a launcher library, not an HTTP interface. Its caller supplies
actual installed resources and independently approved profile/configuration.
It never admits a capsule, changes settings, issues a credential or executes work.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid

from .contracts import ResearchError, validate
from .state import json_bytes


def require(value, message):
    if not value:
        raise ResearchError('evaluation_preparation', message)


def _json(raw):
    def members(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'Duplicate frozen JSON member')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=members,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def publish_frozen_inputs(store, *, artifacts, input_aliases, criteria, replacements=None):
    """Relocate exact Ref aliases in a finite public dependency DAG.

    artifacts maps logical alias to original bytes. Explicit replacements are
    pre-freeze format adaptations, retained with their original source hashes.
    Every alias reference must match its ORIGINAL bytes before relocation. No
    admission/body/check asset is imported through this data-only operation.
    """
    require(type(artifacts) is dict and artifacts and len(artifacts) <= 128,
            'A finite original public input inventory is required')
    require(all(isinstance(k, str) and k and isinstance(v, bytes) for k, v in artifacts.items()),
            'Public input aliases must name original bytes')
    replacements = replacements or {}
    require(type(replacements) is dict and set(replacements) <= set(artifacts)
            and all(isinstance(v, bytes) for v in replacements.values()), 'Unknown format adaptation')
    require(type(input_aliases) is dict and input_aliases and set(input_aliases.values()) <= set(artifacts),
            'Typed inputs must name exact frozen aliases')
    published, visiting, receipts = {}, set(), []

    def relocate(value):
        if type(value) is dict:
            if set(value) == {'id', 'sha256'}:
                validate('Ref', value)
                if value['id'] in artifacts:
                    require(hashlib.sha256(artifacts[value['id']]).hexdigest() == value['sha256'],
                            'Alias digest differs from original public bytes: ' + value['id'])
                    return publish(value['id'])
                store.read_blob(value)
                return copy.deepcopy(value)
            return {key: relocate(item) for key, item in value.items()}
        if type(value) is list:
            return [relocate(item) for item in value]
        return value

    def publish(alias):
        if alias in published:
            return copy.deepcopy(published[alias])
        require(alias not in visiting, 'Cyclic frozen input aliases')
        visiting.add(alias)
        original = artifacts[alias]
        raw = replacements.get(alias, original)
        if alias.endswith('.json'):
            value = _json(raw)
            relocated = relocate(value)
            if relocated != value:
                raw = json_bytes(relocated)
        ref = store.put_blob(raw, media_type='application/json' if alias.endswith('.json') else 'text/plain')
        original_ref = store.put_blob(original, media_type='application/octet-stream')
        receipts.append({'alias': alias, 'original_ref': original_ref, 'artifact_ref': ref,
                         'format_adapted': alias in replacements})
        published[alias] = ref
        visiting.remove(alias)
        return copy.deepcopy(ref)

    inputs = {name: publish(alias) for name, alias in input_aliases.items()}
    overlay = relocate(criteria)
    # search criteria are keyed by source identity as well as carrying the Ref.
    for variant in overlay.get('variants', {}).values():
        if 'sources' in variant:
            variant['sources'] = {published.get(key, {'id': key})['id']: value
                                  for key, value in variant['sources'].items()}
    return {'input_refs': inputs, 'criteria': overlay,
            'published': copy.deepcopy(published), 'transformations': receipts}


def capture_assignment_intake(resources, principal, *, text, upload_refs=()):
    """Capture the actual supplied assignment through the existing qualifier.

    The protected caller supplies an ingest-authorized principal. This helper
    grants no permission and authors no intake/provenance record itself. The
    returned request Ref must be explicitly included in the original parent
    read ceiling when an admitted capsule declares original_request reads.
    """
    from .admitted_measurement import AdmittedResourceContext
    from .intake import qualify_intake
    require(type(resources) is AdmittedResourceContext, 'Actual protected installed resources are required')
    workspace = resources.exact_binding_refs['workspace_id']
    principal.require('ingest', workspace)
    require(principal.account_id == resources.principal.account_id,
            'Assignment qualifier belongs to another account')
    options = resources.exact_binding_refs['protected_options']
    intake_ref = qualify_intake(resources.store, principal, text, upload_refs,
        workspace_id=workspace, profile_ref=options['profile_ref'],
        workspace_ref=options['workspace_ref'], input_directory_ref=options['input_directory_ref'])
    intake = resources.store.read_record(intake_ref, contract_id='qualified-intake')
    require(intake['user_id'] == principal.account_id
            and resources.store.read_blob(intake['request_ref']) == text.encode('utf-8'),
            'Qualified assignment differs from the actual supplied task')
    return {'intake_ref': intake_ref, 'request_ref': intake['request_ref']}


def prepare_single_cc(resources, *, source_run_id, profile_ref, library_snapshot_ref,
                      campaign_id, case_id, request_id, capsule_pin, input_refs,
                      node_id, limits, template_ref, authority_ceiling,
                      config_id, repeat_index=0, account_model_selection_ref=None, objective=None):
    """Capture one canonical subject and the exact native E3 runtime/slot.

    source_run_id is an existing operator-owned *source capture*, never the
    identity of the later private execution. It must be terminal. Inputs have
    already been published and the caller freezes returned request/criteria
    BEFORE authorizing a worker. No ordinary run is launched here. An explicit
    objective binds the actual supplied assignment when the ownership source
    capture has a different historical task; omission preserves the source task.
    """
    from .admitted_measurement import AdmittedResourceContext, AdmittedMeasurementResources
    from .binding import ContractFactory
    require(type(resources) is AdmittedResourceContext, 'Actual protected installed resources are required')
    store, operator, composition = resources.store, resources.operator, resources.composition
    require(composition.library.store is store and composition.runner.store is store,
            'Installed composition belongs to another store')
    expected = resources.exact_binding_refs
    configuration_ref = expected['configuration_ref']
    settings = operator.snapshot()
    captured = store.read_record(configuration_ref)
    require(captured.get('operator', captured) == settings, 'Configuration differs from approved operator bytes')
    require(settings['cc']['evaluation_profile_ref'] == profile_ref, 'Profile differs from approved operator')
    profile = store.read_record(profile_ref, contract_id='evaluation-profile')
    require(store.record_kind(profile_ref) == 'evaluation-profile' and profile['invalid_for_product'] is True
            and 'E3' in profile['allowed_entry_points'] and profile['router_enabled'] is False
            and settings['cc']['router']['enabled'] is False
            and profile['model_route'] == settings['codex']['route_id'], 'Approved fixed E3 profile is unavailable')
    snapshot = store.read_record(library_snapshot_ref, contract_id='library-snapshot')
    require(store.record_kind(library_snapshot_ref) == 'library-snapshot'
            and library_snapshot_ref['sha256'] == profile['library_snapshot_sha256'], 'Frozen Library snapshot differs')
    require(capsule_pin in [{k: row[k] for k in capsule_pin} for row in snapshot['entries']],
            'Requested subject is absent from the approved snapshot')
    row = composition.library.get(capsule_pin['cc_name'], capsule_pin['cc_version'])
    declaration = store.read_record(row['declaration_ref'], contract_id='capsule-declaration')
    admission = store.read_record(row['admission_ref'], contract_id='library-admission')
    require(row['standing'] == 'active' and admission['status'] == 'admitted'
            and admission['cc'] == capsule_pin and admission['candidate_ref'] == row['declaration_ref']
            and row['declaration_ref']['sha256'] == capsule_pin['declaration_sha256'],
            'Exact active admitted capsule is unavailable')
    composition.library.eligible_association(row['declaration_ref'])
    require(declaration['needs']['network']['mode'] == 'none'
            and declaration['budget']['per_call']['tool_calls'] == 0,
            'This finite launcher supports tool-free admitted assignments only')
    run = store.get_run(source_run_id, account_id=resources.principal.account_id)
    require(run['workspace_id'] == expected['workspace_id'] and run['state'] in {'halted', 'completed'},
            'Canonical source must be a terminal operator-owned workspace capture')
    require(objective is None or isinstance(objective, str) and objective.strip(),
            'An explicit assignment objective must be nonempty text')
    assignment_objective = objective if objective is not None else run['submission'].get(
        'intent', 'Frozen private capsule assignment')
    if account_model_selection_ref is not None:
        from .evaluation_model_binding import source_model_selection
        source_model_selection(store, account_model_selection_ref,
            account_id=resources.principal.account_id, source_run_id=source_run_id)
    require(type(input_refs) is dict, 'Named finite input Refs are required')
    declared = declaration['ports']['inputs']
    require(set(input_refs) == {p['name'] for p in declared}, 'Exact declared input port inventory is required')
    ports = []
    for port in declared:
        ref = input_refs[port['name']]
        validate('Ref', ref)
        raw = store.read_blob(ref)
        validate(port['schema_ref'], _json(raw))
        ports.append({'name': port['name'], 'contract_id': port['schema_ref'],
                      'version': ContractFactory._version(port['schema_ref']),
                      'required': port['required'], 'artifact_refs': [ref]})
    authority = copy.deepcopy(authority_ceiling)
    require(authority['network'] == 'none' and not authority['network_allowlist']
            and not authority['tools'] and not authority['write_roots']
            and all(ref in authority['resource_reads'] for ref in input_refs.values()),
            'Finite assignment must remain tool-free within its original read ceiling')
    policy_ref = settings['cc']['plan_policy_ref']
    policy = store.read_record(policy_ref, contract_id='plan-policy')
    require(set(limits) == {'time_s', 'model_calls', 'memory_mb'} and all(
        0 <= limits[key] <= policy['aggregate_limits'][key] for key in limits), 'Assignment exceeds approved policy')
    verifier = composition.installed['verifier']
    require(profile['verifier_cc_ref'] == verifier['declaration_ref'], 'Profile reviewer differs from installed reviewer')
    factory = ContractFactory(store, composition.library, verifier_pin=verifier['pin'],
                              finalization_profile_ref=expected['protected_options']['finalization_profile_ref'])
    outputs = [{'name': p['name'], 'contract_id': p['schema_ref'],
                'version': factory._version(p['schema_ref']), 'required': p['required']}
               for p in declaration['ports']['outputs']]
    store.read_blob(template_ref)
    parent_ref = factory.prepare_parent(source_run_id, node_id,
        [{'subnode_id': 'subject', 'cc': capsule_pin}], inputs=ports, outputs=outputs,
        objective=assignment_objective,
        requirement_ids=['private-evaluation-assignment'], limits=copy.deepcopy(limits),
        policy_ref=policy_ref, configuration_ref=configuration_ref,
        template_ref=template_ref, authority_ceiling=authority)
    # Named-port schema validation alone does not establish the original data
    # lineage. Reuse the owning whole-parent classifier before freezing slots:
    # e.g. Brief.intake_ref must resolve to a genuine qualified-intake record,
    # and declared original_request reads need the exact captured read grant.
    from .attempt_resources import attempt_resource_disposition
    disposition = attempt_resource_disposition(store, parent_ref)
    require(not disposition.requires_broker,
            'Finite tool-free assignment has unresolved or shared resources requiring the protected broker')
    contract_ref, checks_ref, _ = factory.bind_subnode(parent_ref, 'subject', ports, role='work')
    # Reuse the actual owner's complete admission/check/body/authority validation.
    AdmittedMeasurementResources(resources)._validate(contract_ref, checks_ref)
    entries = [{'path': 'binding.json', 'sha256': contract_ref['sha256'],
                'artifact_ref': contract_ref, 'role': 'binding'}]
    inputs = []
    for port in ports:
        name = 'inputs/' + port['name'] + '.json'
        ref = port['artifact_refs'][0]
        entries.append({'path': name, 'sha256': ref['sha256'], 'artifact_ref': ref, 'role': 'input'})
        inputs.append({'port': port['name'], 'path': name, 'sha256': ref['sha256']})
    suffix = uuid.uuid4().hex
    assets_ref = store.append_record('evaluation-assets', {
        'schema': 'ai4r-evaluation-assets:1', 'id': 'evaluation-assets:' + suffix,
        'profile_ref': profile_ref, 'configuration_ref': configuration_ref,
        'account_id': resources.principal.account_id, 'workspace_id': expected['workspace_id'],
        'campaign_id': campaign_id, 'entries': entries,
        'cases': [{'case_id': case_id, 'entry_point': 'E3', 'binding_ref': contract_ref, 'record_gate': False}]})
    request = {'request_id': request_id, 'campaign_id': campaign_id, 'case_id': case_id,
        'evaluation_profile_id': profile['profile_id'], 'capsule_id': capsule_pin['cc_name'],
        'capsule_version': capsule_pin['cc_version'], 'capsule_declaration_sha256': capsule_pin['declaration_sha256'],
        'binding': {'path': 'binding.json', 'sha256': contract_ref['sha256']},
        'inputs': inputs, 'model_route': profile['model_route']}
    slots = [{'slot_id': 'slot:' + suffix, 'request_id': request_id, 'entry_point': 'E3', 'case_id': case_id,
              'config_id': config_id, 'repeat_index': repeat_index,
              'request_sha256': hashlib.sha256(json_bytes(['E3', request])).hexdigest(), 'limits': copy.deepcopy(limits)}]
    schedule_ref = store.put_blob(json_bytes(slots), media_type='application/json')
    runtime = {'schema': 'ai4r-evaluation-runtime:1', 'id': 'evaluation-runtime:' + suffix,
        'account_id': resources.principal.account_id, 'workspace_id': expected['workspace_id'],
        'campaign_id': campaign_id, 'profile_ref': profile_ref, 'assets_ref': assets_ref,
        **{k: expected[k] for k in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
        'policy_ref': policy_ref, 'library_snapshot_ref': library_snapshot_ref,
        'schedule_ref': schedule_ref, 'slots': slots, 'accepted': False, 'invalid_for_product': True}
    if account_model_selection_ref is not None:
        runtime['account_model_selection_ref'] = copy.deepcopy(account_model_selection_ref)
    validate('urn:ai4r:private:evaluation-runtime:1', runtime)
    runtime_ref = store.append_record('evaluation-runtime', runtime)
    return {'request': request, 'source_contract_ref': contract_ref, 'check_plan_ref': checks_ref,
            'evaluation_assets_ref': assets_ref, 'evaluation_runtime_ref': runtime_ref,
            'library_snapshot_ref': library_snapshot_ref, 'configuration_ref': configuration_ref,
            'profile_ref': profile_ref}
