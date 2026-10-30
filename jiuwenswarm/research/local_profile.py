"""Explicit local operator capture, separate from admission and readiness.

The launcher opt-in captures an immutable policy, fixed subscription deployment,
workspace bindings, explicitly imported external resources and private guard
fixtures. It creates no calibrated eligibility, admissions, credentials,
experiment measurements or observed hardware.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import stat
from importlib.resources import files
from pathlib import Path

from .contracts import ResearchError, validate
from .operator_config import OperatorConfiguration
from .state import SQLiteRunStore, json_bytes

PROFILE_NAME = 'local-research-unified-v5'
PREVIOUS_PROFILE_NAME = 'local-research-v6'
GOVERNANCE_PROFILE_NAME = 'local-research-v5'


def _write_once(path, value):
    raw = json_bytes(value)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise ResearchError('local_profile_conflict', 'Existing local operator capture differs; no implicit policy replacement')
    else:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def _profile_stages(store, profiles):
    result={}
    for ref in profiles:
        value=store.read_record(ref);parts=value['id'].split(':')
        if len(parts)<3 or parts[0]!='authored-local-catalog' or parts[1] in result:
            raise ResearchError('local_profile_conflict','Captured calibration stage identities are invalid or ambiguous')
        result[parts[1]]=(ref,value)
    return result


def _previous_calibration_requests(store, runtime_ref):
    with store._lock:
        exists=store.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='private_calibration_requests'").fetchone()
        rows=store.connection.execute('SELECT * FROM private_calibration_requests').fetchall() if exists else []
    result={}
    for row in rows:
        ref=json.loads(row['request_ref']);request=store.read_record(ref)
        if request.get('runtime_ref')!=runtime_ref:continue
        validate('urn:ai4r:private:check-calibration-request:1',request)
        if store.record_kind(ref)!='check-calibration-request' or request['id']!=row['id']:
            raise ResearchError('local_profile_conflict','Original calibration request identity is inconsistent')
        item={'request_ref':ref,'state':row['state'],
              'receipt_ref':json.loads(row['receipt_ref']) if row['receipt_ref'] else None,'containment_ref':None}
        if item['receipt_ref'] is not None:store.read_blob(item['receipt_ref'])
        if row['cancel_id']:
            containment_ref=store.record_ref(row['cancel_id']);containment=store.read_record(containment_ref)
            run_id='calibration-run:'+request['id'].split(':',1)[1]
            if (row['state']!='cancelled' or store.record_kind(containment_ref)!='calibration-containment'
                    or containment.get('request_ref')!=ref or containment.get('contained') is not True
                    or containment.get('owner_ack')!={'contained':True,'run_id':run_id,'request_id':row['cancel_id']}):
                raise ResearchError('local_profile_conflict','Original scoped cancellation acknowledgement is unavailable')
            item['containment_ref']=containment_ref
        result.setdefault(request['calibration_profile_ref']['sha256'],[]).append(item)
    return result


_UNSET = object()


def _static_template(store, *, screening_version='m1-4', delivery_version='m1-5'):
    """Capture a new opt-in template without changing installed historical bytes."""
    from .releases import apply_template_releases
    raw = files('jiuwenswarm.research_assets').joinpath('planner/static-template.json').read_bytes()
    return apply_template_releases(store, raw, {'intent': 'm1-6', 'requirements': 'm1-8',
        'screening': screening_version, 'delivery': delivery_version}, 'local_profile_conflict')


def _screening_static_template(store, screening_version):
    return _static_template(store, screening_version=screening_version)


def _require_science_resources(store, static_ref, inventory_ref):
    """Refuse a profile whose static template names science resources the inventory lacks.

    Planning checks every accepted run input against the captured inventory, so an
    empty one makes every plan infeasible. Fail here, naming the setting, instead.
    """
    from .local_science import SCIENCE_RESOURCE_KEYS
    template = json.loads(store.read_blob(static_ref))
    needed = sorted({port['run_input_key'] for node in template['nodes'] for port in node['inputs']
                     if port['source_kind'] == 'accepted_ref' and port['run_input_key'] in SCIENCE_RESOURCE_KEYS})
    available = {row['resource_key'] for row in store.read_record(inventory_ref)['resources']}
    missing = [key for key in needed if key not in available]
    if missing:
        raise ResearchError('local_profile_science_resources',
            'The static template needs science resources %s but the captured resource inventory has none of them. '
            'Set JIUWENSWARM_M1_EXTERNAL_DATASET (and JIUWENSWARM_M1_EXTERNAL_SCORING_PINS) to import the public dataset, '
            'or capture a profile whose template needs none.' % ', '.join(missing), {'missing': missing})


def capture_local_profile(store, directory, *, input_root=Path('/workspace/input'), development_builtin_catalog=True,
                          public_dataset_path=None, scoring_pins=None, legacy_checking_refresh=False, capability_dag=False,
                          requested_model='gpt-6.1-sol', evidence_aware_review=False, screening_version='m1-4', requirements_version='m1-8',
                          intent_version=_UNSET, delivery_version='m1-5', allow_missing_science=False, model_backend=None,
                          plan_source=_UNSET):
    from .releases import RELEASES, capture_default, implicit_release, release_facts, require_release
    # An unnamed Intent release adopts what an existing profile froze; a new profile
    # takes the current capture default. A checking-only refresh never moves it.
    intent_adopts_frozen = intent_version is _UNSET
    if intent_version is _UNSET:
        intent_version = implicit_release('intent') if legacy_checking_refresh else capture_default('intent')
    for stage, value in (('intent', intent_version), ('requirements', requirements_version),
                         ('screening', screening_version), ('delivery', delivery_version)):
        require_release(stage, value, 'local_profile_conflict')
        if legacy_checking_refresh and value != implicit_release(stage):
            raise ResearchError('local_profile_conflict', 'Checking-only refresh cannot change the %s release; use a fresh profile'
                                % ('captured Screening' if stage == 'screening' else RELEASES[stage]['label']))
    # An unnamed plan source adopts what an existing profile froze; a new profile
    # takes 'static', the library default. The product entry (main) names 'planned'.
    plan_adopts_frozen = plan_source is _UNSET
    if plan_adopts_frozen:
        plan_source = 'static'
    if plan_source not in {'static', 'planned'}:
        raise ResearchError('local_profile_conflict', 'Plan source must be static or planned')
    if requested_model not in {'gpt-6-luna', 'gpt-6.1-sol'} or type(evidence_aware_review) is not bool:
        raise ResearchError('local_profile_conflict', 'Pilot model and review mode must be explicit supported selections')
    from .fixed_subscription import HOST_CODEX_BACKEND, deployment_backend
    if model_backend not in (None, HOST_CODEX_BACKEND) or (model_backend == HOST_CODEX_BACKEND and requested_model != 'gpt-6.1-sol'):
        raise ResearchError('local_profile_conflict', 'Unsupported explicit fixed subscription backend')
    directory = Path(directory)
    if not directory.is_absolute() or directory.is_symlink() or input_root.is_symlink() or not input_root.is_dir():
        raise ResearchError('local_profile_custody', 'Local operator and input directories must be real absolute directories')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = directory.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o700 or metadata.st_uid != os.geteuid():
        raise ResearchError('local_profile_custody', 'Local operator directory has another owner or unsafe permissions')
    config_path, binding_path = directory / 'config.json', directory / 'bootstrap.json'
    if config_path.exists() or binding_path.exists():
        # Ordinary recreation retains the captured policy and immutable refs.
        from .bootstrap_gateway import _protected_file
        envelope = json.loads(_protected_file(str(binding_path)))
        if set(envelope) != {'binding_ref'}:
            raise ResearchError('local_profile_conflict', 'Local bootstrap locator is invalid')
        validate('Ref', envelope['binding_ref'])
        binding = store.read_record(envelope['binding_ref'])
        if intent_adopts_frozen and not legacy_checking_refresh:
            intent_version = binding['protected_options'].get('intent_version', implicit_release('intent'))
        if binding['protected_options'].get('intent_version','m1-6') != intent_version:
            raise ResearchError('local_profile_conflict','Frozen Intent release changed; use a fresh profile directory')
        if binding['protected_options'].get('requirements_version','m1-8') != requirements_version:
            raise ResearchError('local_profile_conflict','Frozen Requirements release changed; use a fresh profile directory')
        if binding['protected_options'].get('screening_version','m1-4') != screening_version:
            raise ResearchError('local_profile_conflict','Frozen Screening release changed; use a fresh profile directory')
        if binding['protected_options'].get('delivery_version',implicit_release('delivery')) != delivery_version:
            raise ResearchError('local_profile_conflict','Frozen Delivery release changed; use a fresh profile directory')
        if (deployment_backend(store.read_record(binding['deployment_ref'])) != (model_backend or 'codex')
                or store.read_record(binding['deployment_ref']).get('requested_model') != requested_model
                or binding['protected_options'].get('evidence_aware_review', False) != evidence_aware_review):
            raise ResearchError('local_profile_conflict', 'Frozen model or review mode changed; use a fresh profile directory')
        operator = OperatorConfiguration.load(config_path, resolve_profile=store.read_record)
        if store.read_record(binding['configuration_ref']) != operator.snapshot():
            raise ResearchError('local_profile_conflict', 'Local configuration differs from its captured identity')
        if not plan_adopts_frozen and operator.snapshot()['cc']['plan_source'] != plan_source:
            raise ResearchError('local_profile_conflict', 'Frozen plan source changed; use a fresh profile directory')
        from .capability_planning import is_capability_policy
        if capability_dag != is_capability_policy(store.read_record(operator.snapshot()['cc']['plan_policy_ref'])):
            raise ResearchError('local_profile_conflict', 'Policy selection changed; use a fresh explicit profile directory')
        return {'configuration_path': str(config_path), 'binding_path': str(binding_path), 'binding_ref': envelope['binding_ref']}

    previous = directory.parent / PREVIOUS_PROFILE_NAME
    if development_builtin_catalog:
        previous=next((directory.parent/name for name in ('local-research-v7','local-research-v6','local-research-v5')
            if (directory.parent/name/'config.json').exists() or (directory.parent/name/'bootstrap.json').exists()),previous)
    if legacy_checking_refresh and ((previous / 'config.json').exists() or (previous / 'bootstrap.json').exists()):
        # This generation changes checking bindings, not operator governance.
        # Keep every prior Ref and original file; capture only the revised
        # calibration profiles/runtime in a new immutable bootstrap directory.
        from .bootstrap_gateway import _protected_file
        locator = json.loads(_protected_file(str(previous / 'bootstrap.json')))
        if set(locator) != {'binding_ref'}:
            raise ResearchError('local_profile_conflict', 'Previous local bootstrap locator is invalid')
        validate('Ref', locator['binding_ref'])
        prior = store.read_record(locator['binding_ref'])
        operator = OperatorConfiguration.load(previous / 'config.json', resolve_profile=store.read_record)
        if store.read_record(prior['configuration_ref']) != operator.snapshot():
            raise ResearchError('local_profile_conflict', 'Previous local governance capture is inconsistent')
        for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref'):
            validate('Ref', prior[key]); store.read_blob(prior[key])
        installed_static = files('jiuwenswarm.research_assets').joinpath('planner/static-template.json').read_bytes()
        if store.read_blob(operator.snapshot()['cc']['static_template_ref']) != installed_static:
            raise ResearchError('local_profile_conflict', 'Checking-only refresh cannot change the captured static release')
        if development_builtin_catalog:
            # Explicit local development installs exact shipped builtins. It
            # performs no calibration capture, call, PASS or strict-table edit.
            binding=copy.deepcopy(prior)
            binding['previous_binding_ref']=locator['binding_ref']
            binding['binding_generation']=PROFILE_NAME
            options=binding['protected_options']
            for key in list(options):
                if key.startswith('calibration_'):options.pop(key)
            options['development_builtin_catalog']=True
            binding_ref=store.put_blob(json_bytes(binding),media_type='application/json')
            _write_once(config_path,operator.snapshot());_write_once(binding_path,{'binding_ref':binding_ref})
            return {'configuration_path':str(config_path),'binding_path':str(binding_path),'binding_ref':binding_ref}
        from .catalog_calibration import capture_catalog_calibration
        old_runtime=store.read_record(prior['protected_options']['calibration_runtime_ref'])
        old_profiles=_profile_stages(store,old_runtime['approved_profile_refs'])
        generations={stage:value['id'].split(':generation:',1)[1] for stage,(_,value) in old_profiles.items()
            if ':generation:' in value['id']}
        history=_previous_calibration_requests(store,prior['protected_options']['calibration_runtime_ref'])
        def capture_checking():
            return asyncio.run(capture_catalog_calibration(store,
                configuration_ref=prior['configuration_ref'],model_selection_profile_ref=prior['model_selection_profile_ref'],
                deployment_ref=prior['deployment_ref'],profile_generations=generations))
        calibration=capture_checking();current=_profile_stages(store,calibration['profile_refs']);fresh=[]
        if set(current)!=set(old_profiles):
            raise ResearchError('local_profile_conflict','Checking-only refresh cannot silently change the stage inventory')
        for stage,(old_ref,_) in old_profiles.items():
            if current[stage][0]!=old_ref:continue
            incomplete=[item for item in history.get(old_ref['sha256'],[]) if item['state']!='completed']
            with store._lock:
                issued=store.connection.execute('SELECT 1 FROM calibration_attempts WHERE profile_sha=? LIMIT 1',
                    (old_ref['sha256'],)).fetchone() if incomplete else None
            if not issued:continue
            if any(item['state']!='cancelled' or item['containment_ref'] is None for item in incomplete):
                raise ResearchError('local_profile_conflict','An unchanged issued profile requires confirmed scoped containment before supersession')
            generations[stage]='superseded-'+PREVIOUS_PROFILE_NAME+'-to-'+PROFILE_NAME
            fresh.append(stage)
        if fresh:
            calibration=capture_checking();current=_profile_stages(store,calibration['profile_refs'])
        supersessions=[{'stage':stage,'previous_profile_ref':old_ref,'profile_ref':current[stage][0],
            'previous_requests':history.get(old_ref['sha256'],[]),
            'reason':('Explicit fresh calibration identity after contained incomplete issued work; original claims are retained'
                if stage in fresh else 'Authored checking contract or fixture changed; original outcomes remain unchanged')}
            for stage,(old_ref,_) in old_profiles.items() if old_ref!=current[stage][0]]
        binding = copy.deepcopy(prior)
        binding['previous_binding_ref'] = locator['binding_ref']
        binding['binding_generation'] = PROFILE_NAME
        binding['protected_options'].update(calibration_runtime_ref=calibration['runtime_ref'],
            calibration_profile_refs=calibration['profile_refs'], calibration_limitations=calibration['limitations'],
            calibration_supersessions=supersessions,calibration_profile_generations=generations)
        binding_ref = store.put_blob(json_bytes(binding), media_type='application/json')
        _write_once(config_path, operator.snapshot())
        _write_once(binding_path, {'binding_ref': binding_ref})
        return {'configuration_path': str(config_path), 'binding_path': str(binding_path), 'binding_ref': binding_ref}

    static_ref = _static_template(store,screening_version=screening_version,delivery_version=delivery_version)
    from .unified_planning import integrated_plan_policy
    from .capability_planning import capability_plan_policy
    policy_ref = store.put_record('plan-policy', capability_plan_policy() if capability_dag else integrated_plan_policy())
    operator = OperatorConfiguration.from_mapping({'schema_version': '1.0.0',
        'cc': {'plan_source': plan_source, 'plan_policy_ref': policy_ref, 'static_template_ref': static_ref,
               'evaluation_profile_ref': None, 'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
        'codex': {'route_id': 'codex-cli-default'},
        'role_aliases': {role: 'codex-cli-default' for role in ('worker', 'planner', 'verifier')},
        'rsi': {'custodian_key_id': None, 'custodian_public_key': None}}).snapshot()
    configuration = store.put_blob(json_bytes(operator), media_type='application/json')
    selection = store.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': GOVERNANCE_PROFILE_NAME + '.selection',
        'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
        'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []},
        'alternate_model_id': None, 'policy_ref': policy_ref})
    deployment = store.put_blob(json_bytes({'schema': 'ai4r-fixed-subscription:1', 'id': GOVERNANCE_PROFILE_NAME + '.deployment',
        'route_id': 'codex-cli-default', 'requested_model': requested_model, 'endpoint': 'local-protected-IPC'}), media_type='application/json')
    if model_backend == HOST_CODEX_BACKEND:
        deployment_value = store.read_record(deployment)
        deployment_value.update(schema='ai4r-fixed-subscription:2', backend=HOST_CODEX_BACKEND, reasoning_effort='medium')
        deployment = store.put_blob(json_bytes(deployment_value), media_type='application/json')
    defaults = store.put_record('default-policy', {'schema_version': '1.0.0', 'id': GOVERNANCE_PROFILE_NAME + '.defaults',
        'hardware_profile': 'single_gpu', 'automatic_retries': 0})
    finalization = store.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': GOVERNANCE_PROFILE_NAME + '.finalization',
        'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
        'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
    capture = lambda name, value: store.put_blob(json_bytes({'schema': 'ai4r-local-' + name + ':1', **value}), media_type='application/json')
    profile = capture('profile', {'id': GOVERNANCE_PROFILE_NAME, 'model': 'gpt-6.1-sol', 'hardware_ceiling': 'single_gpu'})
    if model_backend == HOST_CODEX_BACKEND:
        profile_value = store.read_record(profile)
        profile_value.update(schema='ai4r-local-profile:2', backend=HOST_CODEX_BACKEND, reasoning_effort='medium')
        profile = store.put_blob(json_bytes(profile_value), media_type='application/json')
    workspace = capture('workspace', {'id': 'local', 'input_root': str(input_root), 'poc_root': '/workspace/poc'})
    inputs = capture('input-directory', {'id': GOVERNANCE_PROFILE_NAME + '.inputs', 'path': str(input_root), 'readable': os.access(input_root, os.R_OK)})
    public_dataset_path = public_dataset_path or os.environ.get('JIUWENSWARM_M1_EXTERNAL_DATASET')
    scoring_pins_path = os.environ.get('JIUWENSWARM_M1_EXTERNAL_SCORING_PINS')
    if scoring_pins is None and scoring_pins_path:
        from .bootstrap_gateway import _protected_file
        scoring_pins = json.loads(_protected_file(scoring_pins_path))
    science = None
    if public_dataset_path is not None:
        from .local_science import capture_local_science_resources
        science = capture_local_science_resources(store, public_path=public_dataset_path, scoring_pins=scoring_pins)
        inventory = science['resource_inventory_ref']
    else:
        inventory = store.put_record('resource-inventory', {'schema_version': '1.0.0',
            'id': 'external_dataset_not_imported', 'resources': []})
    if not allow_missing_science:
        _require_science_resources(store, static_ref, inventory)
    calibration=None
    if not development_builtin_catalog:
        from .catalog_calibration import capture_catalog_calibration
        calibration=asyncio.run(capture_catalog_calibration(store,configuration_ref=configuration,
            model_selection_profile_ref=selection,deployment_ref=deployment))
    bounds = capture('search-bounds', {'id': GOVERNANCE_PROFILE_NAME + '.search', 'connectors': ['local_documents'], 'max_queries': 3, 'max_hits_per_query': 3})
    # The source-owned Search bound has its own closed shape.
    bounds_value = store.read_record(bounds)
    bounds_value['schema'] = 'ai4r-search-bounds:1'
    bounds = store.put_blob(json_bytes(bounds_value), media_type='application/json')
    options = {'profile_ref': profile, 'workspace_ref': workspace, 'input_directory_ref': inputs,
        'default_policy_ref': defaults, 'finalization_profile_ref': finalization,
        'compiler_template_ref': capture('compiler-template', {'id': GOVERNANCE_PROFILE_NAME + '.compiler', 'subnodes': ['intent', 'requirements']}),
        'planner_template_ref': capture('planner-template', {'id': PROFILE_NAME + '.planner', 'plan_contract': 'plan-proposal:field-contract:3', 'selection': 'admitted_typed_dag'}),
        # Preserve the existing 180s host headroom as Intent grows by 300s.
        'compiler_limits': {'time_s': release_facts('intent', intent_version).get('compiler_time_s', 600), 'model_calls': 4, 'memory_mb': 16384},
        'planner_limits': {'time_s': 600, 'model_calls': 3, 'memory_mb': 16384},
        'resource_inventory_ref': inventory, 'search_bounds_ref': bounds,
        'authority_ceiling': {'network': 'allowlist', 'network_allowlist': ['approved_package_index'],
                              'resource_reads': science['resource_reads'] if science else [], 'write_roots': ['/workspace/poc'], 'tools': ['deepsearch', 'codesearch', 'builder_action']},
        'document_extraction_timeout_s': 30, 'max_upload_bytes': 20 * 1024 * 1024,
        'run_inputs': science['run_inputs'] if science else {}, 'host_records': science['host_records'] if science else {},
        'development_builtin_catalog':development_builtin_catalog, 'integrated_workflows':True,
        'screening_version':screening_version,'requirements_version':requirements_version,'delivery_version':delivery_version}
    if intent_version != implicit_release('intent'):
        options['intent_version'] = intent_version
    if evidence_aware_review:
        options['evidence_aware_review'] = True
    if science is not None:
        options['local_science_resources_ref'] = store.put_blob(json_bytes(science), media_type='application/json')
    if calibration is not None:
        options.update(calibration_runtime_ref=calibration['runtime_ref'],
            calibration_profile_refs=calibration['profile_refs'],calibration_limitations=calibration['limitations'])
    binding = store.put_blob(json_bytes({'workspace_id': 'local', 'host_id': 'local', 'configuration_ref': configuration,
        'model_selection_profile_ref': selection, 'deployment_ref': deployment, 'protected_options': options}), media_type='application/json')
    _write_once(config_path, operator)
    _write_once(binding_path, {'binding_ref': binding})
    return {'configuration_path': str(config_path), 'binding_path': str(binding_path), 'binding_ref': binding}


def main():
    if os.name != 'posix' or os.geteuid() != 10001 or os.environ.get('JIUWENSWARM_M1_LOCAL_RESEARCH') != '1':
        raise ResearchError('local_profile_identity', 'Local research capture requires explicit launcher opt-in and the product OS identity')
    root = Path(os.environ['JIUWENSWARM_M1_STATE'])
    store = SQLiteRunStore(root, input_root='/workspace/input', recover=False)
    try:
        # Release selections are protected settings. An unset one keeps its capture default
        # (or, for an existing profile directory, what that profile froze).
        from .releases import release_options_from_environment
        directory = root / 'operator' / PROFILE_NAME
        options = release_options_from_environment(os.environ)
        # The Planner is the product path. JIUWENSWARM_M1_PLAN_SOURCE=static is an
        # explicit bench/RSI reproduction setting. Unset, an existing profile keeps
        # what it froze and a new one is captured as 'planned'.
        if 'JIUWENSWARM_M1_PLAN_SOURCE' in os.environ:
            options['plan_source'] = os.environ['JIUWENSWARM_M1_PLAN_SOURCE']
        elif not ((directory / 'config.json').exists() or (directory / 'bootstrap.json').exists()):
            options['plan_source'] = 'planned'
        # A new product profile also selects the current Requirements and Screening
        # releases (the library defaults stay m1-8 and m1-4 for benches and RSI).
        # JIUWENSWARM_M1_REQUIREMENTS_VERSION / _SCREENING_VERSION override; an
        # existing profile keeps what it froze.
        if not ((directory / 'config.json').exists() or (directory / 'bootstrap.json').exists()):
            options.setdefault('requirements_version', 'm1-9')
            options.setdefault('screening_version', 'm1-5')
        capture_local_profile(store, directory, **options)
    finally:
        store.close()


if __name__ == '__main__':
    main()
