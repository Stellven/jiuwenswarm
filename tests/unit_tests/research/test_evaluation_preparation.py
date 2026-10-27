"""Offline launcher tests; controlled admissions are never live CC evidence."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.admitted_measurement import AdmittedResourceContext
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.evaluation_preparation import capture_assignment_intake, publish_frozen_inputs, prepare_single_cc
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from benchmarks.harbor_suite.contracts import resolve_cases_root


CASE = resolve_cases_root() / 'cc01-transfer'
pytestmark = pytest.mark.usefixtures("benchmark_case_assets")


def published_screening(store, *, intake_ref=None):
    artifacts = {p.name: p.read_bytes() for p in (CASE / 'public').iterdir()}
    brief = json.loads(artifacts['brief.json'])
    brief['schema_version'] = '3.0.0'
    for target in brief['target_metrics']:
        target['comparison_status'] = 'qualitative'
    if intake_ref is not None:
        brief['intake_ref'] = intake_ref
        brief['intent_ref'] = store.read_record(intake_ref)['request_ref']
    # Publication does not manufacture a library declaration. This unit checks
    # public data/alias handling alone; use the content portion of criteria.
    criteria = json.loads((CASE / 'referee/criteria.json').read_bytes())
    selected = criteria['variants']['screen-missing']
    selected.pop('binding')
    criteria['variants'] = {'screen-missing': selected}
    return publish_frozen_inputs(store, artifacts=artifacts,
        input_aliases={'brief': 'brief.json', 'candidate_set': 'candidate_set.json',
                       'screening_rubric': 'screening_rubric.json'},
        criteria=criteria, replacements={'brief.json': json_bytes(brief)})


def test_publication_resolves_full_dependency_closure_before_freezing_criteria(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        value = published_screening(store)
        order = [r['alias'] for r in value['transformations']]
        assert order.index('filter_notes.txt') < order.index('brief.json') < order.index('search_scope.json') < order.index('candidate_set.json')
        candidate = store.read_record(value['input_refs']['candidate_set'])
        assert candidate['brief_ref'] == value['input_refs']['brief']
        assert candidate['scope_ref'] == value['published']['search_scope.json']
        assert value['criteria']['variants']['screen-missing']['input_refs'] == value['input_refs']
        assert all(r['original_ref']['sha256'] == hashlib.sha256((CASE/'public'/r['alias']).read_bytes()).hexdigest()
                   for r in value['transformations'])
        assert [r['alias'] for r in value['transformations'] if r['format_adapted']] == ['brief.json']
        assert not list(store.iter_records(kinds=('library-admission', 'evaluation-request', 'model-call')))
    finally:
        store.close()


@pytest.mark.parametrize('fault', ['hash', 'cycle'])
def test_publication_rejects_unfrozen_aliases_and_cycles(tmp_path, fault):
    store = SQLiteRunStore(tmp_path)
    raw = b'public source'
    artifacts = {'source.txt': raw, 'input.json': json_bytes({'ref': {'id': 'source.txt', 'sha256': '0'*64}})}
    if fault == 'cycle':
        artifacts = {'input.json': b'{}'}
        replacement = json_bytes({'ref': {'id': 'input.json', 'sha256': hashlib.sha256(b'{}').hexdigest()}})
    else:
        replacement = artifacts['input.json']
    try:
        with pytest.raises(ResearchError):
            publish_frozen_inputs(store, artifacts=artifacts, input_aliases={'input': 'input.json'},
                                 criteria={}, replacements={'input.json': replacement})
    finally:
        store.close()


async def prepared_fixture(tmp_path, fault=None, *, manual_model=False, objective=None):
    from tests.unit_tests.research.test_budget_ceiling import installed_library
    from jiuwenswarm.research.capsules.assets import register_research_capsules
    from jiuwenswarm.research.runner import CapsuleRunner
    store, registry, checks, library, installed, actor = await installed_library(tmp_path, scientific=True)
    register_research_capsules(registry, checks, library, store, assets={k:v for k,v in installed.items() if k == 'screening'})
    snapshot = library.snapshot()
    profile = store.put_record('evaluation-profile', {'schema_version':'1.0.0', 'id':'unit:profile',
        'profile_id':'unit:e3', 'plan_source':'static', 'router_enabled':False, 'router_version':None,
        'model_route':'codex-cli-default', 'library_snapshot_sha256':snapshot['sha256'],
        'candidate_pins':[], 'verifier_cc_ref':installed['verifier']['declaration_ref'],
        'invalid_for_product':True, 'allowed_entry_points':['E3']})
    limits = {'time_s':300, 'model_calls':3, 'memory_mb':512}
    policy = store.put_record('plan-policy', {'schema_version':'1.0.0','id':'unit-e3-policy',
        'max_nodes':12,'allowed_effect_classes':['pure','read'],'allow_network':False,'required_stages':[],
        'aggregate_limits':limits,'max_attempts_per_node':1})
    settings = {'schema_version':'1.0.0','cc':{'plan_source':'static','plan_policy_ref':policy,
        'static_template_ref':policy,'evaluation_profile_ref':profile,
        'router':{'enabled':False,'deadline_s':30,'profile_ref':None}},
        'codex':{'route_id':'codex-cli-default'},'rsi':{'custodian_key_id':None,'custodian_public_key':None},'role_aliases':{}}
    operator = SimpleNamespace(snapshot=lambda:copy.deepcopy(settings))
    configuration = store.append_record('approved-configuration', {'operator':settings})
    final = store.put_record('node-finalization-profile', {'schema_version':'2.0.0','id':'unit:final',
        'mandatory_deterministic':['internal_acceptance','external_output','aggregate_limits'],
        'semantic_assessment_reuse':'accepted_requirements','additional_model_calls':0})
    executor = SimpleNamespace(read_only_prerequisites=lambda: {'ready':True})
    runner = CapsuleRunner(store, registry, checks, model=object(), executor=executor, check_assets=library.check_assets)
    composition = SimpleNamespace(library=library, runner=runner, registry=registry, installed=installed)
    selection = store.put_record('model-selection-profile', {'schema_version':'1.0.0','id':'unit-fixed',
        'policy_mode':'fixed_baseline','approved_model_ids':['codex-cli-default'],'extra_requirements':{},
        'selection_allowance':{'enabled':False,'deployment_ref':None,'model_calls':0,'time_s':0,'output_tokens':0,'disclosure_scope':[]},
        'alternate_model_id':None,'policy_ref':policy})
    exact = {'configuration_ref':configuration,'model_selection_profile_ref':selection,'deployment_ref':policy,
             'workspace_id':'unit','protected_options':{'finalization_profile_ref':final,
                'profile_ref':profile,'workspace_ref':configuration,'input_directory_ref':configuration}}
    resources = AdmittedResourceContext(store,operator,composition,Principal('operator',frozenset({'unit'})),exact,executor)
    store.create_run('unit:source', account_id='operator',workspace_id='unit',submission={'intent':'Unit frozen source only'})
    store.set_run_state('unit:source','halted',reason='source_only')
    qualified = capture_assignment_intake(resources,
        Principal('operator',frozenset({'unit'}),frozenset({'ingest'})),
        text='Frozen Screening assignment for unit control only.')
    intake_ref = qualified['intake_ref']
    published = published_screening(store, intake_ref=None if fault == 'intake' else intake_ref)
    authority = {'network':'none','network_allowlist':[],'resource_reads':list(published['published'].values()),'tools':[],'write_roots':[]}
    if fault != 'original_request':
        authority['resource_reads'].append(store.read_record(intake_ref)['request_ref'])
    if fault == 'authority': authority['tools'] = ['shell']
    if fault == 'active': store.set_run_state('unit:source','running')
    before = {table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
              for table in ['library_versions','acceptance','model_calls','tool_calls']}
    selection_ref = None
    if manual_model:
        from tests.unit_tests.research.test_local_models import document
        from jiuwenswarm.research.local_models import LocalModelCatalog
        from jiuwenswarm.research.model_settings import ModelSettingsOwner
        import os
        catalog_path = tmp_path/'unit-models.json'
        catalog_path.write_text(json.dumps(document()), encoding='utf-8')
        catalog_path.chmod(0o600)
        model_owner = ModelSettingsOwner(store,tmp_path/'unit-private/keys.json',
            local_catalog=LocalModelCatalog(catalog_path,owner_uid=os.geteuid() if os.name=='posix' else 0))
        model_owner.settings({'account_id':'operator','action':'select','values':{'preset_id':'local-unit'}})
        selection_ref = model_owner.freeze({'account_id':'operator','run_id':'unit:source','parent_run_id':None})['selection_ref']
        composition.model_settings = model_owner
    try:
        result = prepare_single_cc(resources,source_run_id='unit:source',profile_ref=profile,
            library_snapshot_ref=snapshot,campaign_id='unit:campaign',case_id='capsule',request_id='unit:request',
            capsule_pin=installed['screening']['pin'],input_refs=published['input_refs'],node_id='unit_cc',
            limits=limits,template_ref=policy,authority_ceiling=authority,config_id='unit:config',
            account_model_selection_ref=selection_ref,objective=objective)
        assert before == {table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before}
        return store, result, resources
    except BaseException:
        store.close()
        raise


@pytest.mark.asyncio
@pytest.mark.parametrize('objective',[None,'Evaluate the supplied missing-baseline evidence only.'])
async def test_preparer_binds_assignment_objective_without_rewriting_historical_source(tmp_path,objective):
    store,value,_=await prepared_fixture(tmp_path,objective=objective)
    try:
        contract=store.read_record(value['source_contract_ref'])
        parent=store.read_record(contract['node_contract_ref'])
        assert parent['objective'] == (objective or 'Unit frozen source only')
        assert store.get_run('unit:source')['submission']['intent'] == 'Unit frozen source only'
        assert not list(store.iter_records(kinds=('evaluation-request','evaluation-assignment-grant','model-call-start')))
    finally:store.close()


@pytest.mark.asyncio
async def test_preparer_reuses_real_factory_and_freezes_exact_native_request_without_dispatch(tmp_path):
    store, value, resources = await prepared_fixture(tmp_path)
    try:
        contract = store.read_record(value['source_contract_ref'])
        runtime = store.read_record(value['evaluation_runtime_ref'])
        assert runtime['slots'][0]['request_sha256'] == hashlib.sha256(json_bytes(['E3',value['request']])).hexdigest()
        assert runtime['accepted'] is False and runtime['invalid_for_product'] is True
        assert contract['bindings'][0]['role'] == 'work'
        assert value['request']['capsule_version'] == 'm1-4'
        assert store.read_record(value['check_plan_ref'])['contract_ref'] == value['source_contract_ref']
        from jiuwenswarm.research.admitted_measurement import AdmittedMeasurementResources
        from jiuwenswarm.research.evaluation_provider import EvaluationProvider, InstalledEvaluationResources
        installed = InstalledEvaluationResources(AdmittedMeasurementResources(resources),
            profile_ref=value['profile_ref'], assets_ref=value['evaluation_assets_ref'],
            library_snapshot_ref=value['library_snapshot_ref'])
        provider = EvaluationProvider(store, resources.operator, assets_ref=value['evaluation_assets_ref'],
                                      resources=installed, library=resources.composition.library)
        installed.bind_runtime(value['evaluation_runtime_ref'])
        assert provider.available_entry_points == ('E3',)
        from jiuwenswarm.research.native_ports import NativePorts
        ports = NativePorts.__new__(NativePorts)
        ports.evaluation_provider = provider
        ports.operator, ports.composition = resources.operator, resources.composition
        ports.executor, ports.model_bridge = resources.executor, resources.composition.runner.model
        ports.bindings = {key:resources.exact_binding_refs[key] for key in
            ('configuration_ref','model_selection_profile_ref','deployment_ref','workspace_id')}
        ports.bindings['protected_options'] = {key:value[key] for key in
            ('evaluation_runtime_ref','evaluation_assets_ref','library_snapshot_ref')}
        prerequisites = [{'name':name,'status':'ready'} for name in
            ('build_identity','storage','auth','plan_policy','model','trajectory')]
        # Full scientific/E1 scope is unavailable; its blockers remain present.
        prerequisites += [{'name':'builder','status':'unavailable'}, {'name':'core_bindings','status':'unavailable'}]
        assert await ports._independent_single_cc_ready(prerequisites, identity_bound=True)
        assert not await ports._independent_single_cc_ready(prerequisites, identity_bound=False)
        prerequisites[5]['status'] = 'unavailable'
        assert not await ports._independent_single_cc_ready(prerequisites, identity_bound=True)
        prerequisites[5]['status'] = 'ready'
        ports.executor.read_only_prerequisites = lambda: {'ready':False}
        assert not await ports._independent_single_cc_ready(prerequisites, identity_bound=True)
        ports.executor.read_only_prerequisites = lambda: {'ready':True}
        ports.bindings['protected_options']['evaluation_runtime_ref'] = value['profile_ref']
        assert not await ports._independent_single_cc_ready(prerequisites, identity_bound=True)
        assert not list(store.iter_records(kinds=('evaluation-request','evaluation-assignment-grant','model-call-start','invocation-observation','gate-decision')))
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['authority','active','original_request'])
async def test_preparer_refuses_wider_effects_or_live_source_run(tmp_path, fault):
    with pytest.raises(ResearchError, match='evaluation_preparation'):
        await prepared_fixture(tmp_path, fault)


@pytest.mark.asyncio
async def test_preparer_rejects_a_brief_with_source_text_instead_of_qualified_intake_before_slots(tmp_path):
    with pytest.raises(ResearchError, match='Reference is not a JSON record'):
        await prepared_fixture(tmp_path, 'intake')
    import sqlite3
    with sqlite3.connect(tmp_path/'state/research.sqlite3') as database:
        assert database.execute("SELECT COUNT(*) FROM records WHERE kind IN "
            "('evaluation-assets','evaluation-runtime','evaluation-request','evaluation-assignment-grant')").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_e3_freezes_source_account_choice_without_creating_an_ordinary_private_run_or_mutable_lookup(tmp_path):
    from jiuwenswarm.research.admitted_measurement import AdmittedMeasurementResources
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider, InstalledEvaluationResources
    store, value, resources = await prepared_fixture(tmp_path, manual_model=True)
    try:
        installed = InstalledEvaluationResources(AdmittedMeasurementResources(resources),
            profile_ref=value['profile_ref'],assets_ref=value['evaluation_assets_ref'],
            library_snapshot_ref=value['library_snapshot_ref'])
        provider = EvaluationProvider(store,resources.operator,assets_ref=value['evaluation_assets_ref'],
            resources=installed,library=resources.composition.library)
        authority = installed.bind_runtime(value['evaluation_runtime_ref'])
        actor = Principal('operator',frozenset({'unit'}),frozenset({'evaluation_profile'}))
        request_ref = authority.accept_request(actor,value['request'],'E3')
        scope_ref = authority.prepare(request_ref)
        grant_ref = authority.prepare_assignment(scope_ref,'worker',None)
        grant, child, _ = authority.projection.load_execution(grant_ref)
        context = authority.start_assignment(grant_ref,resources.composition.runner._decode_inputs(child))
        await resources.composition.runner._await_start(context)
        protected = authority.authorize_model_context({'execution_id':grant['execution_id'],'call_ordinal':1})
        assert protected['evaluation_runtime_ref'] == value['evaluation_runtime_ref']
        assert protected['account_model_selection_ref'] == authority.runtime['account_model_selection_ref']
        model_owner = resources.composition.model_settings
        selected = model_owner.for_call(protected)
        assert selected['preset_id'] == 'local-unit'
        assert model_owner.chatgpt_for_call(protected) is None
        model_owner.settings({'account_id':'operator','action':'select','values':{'preset_id':'codex'}})
        assert model_owner.for_call(protected) == selected
        with pytest.raises(ResearchError,match='not_found'):
            store.get_run(child['run_id'])
        for changed in [dict(protected,account_model_selection_ref=value['profile_ref']),
                        {k:v for k,v in protected.items() if k != 'evaluation_runtime_ref'},
                        dict(protected,run_id='another-private-run')]:
            with pytest.raises(ResearchError,match='evaluation_model_binding'):
                model_owner.for_call(changed)
        # A controlled start/packet fixture verifies private custody only. No
        # provider, relay or inference adapter is invoked in this unit test.
        start = {'id':protected['call_id']+':start',
            **{k:protected[k] for k in ('run_id','invocation_id','execution_id','call_id','call_claim_ref','contract_ref')},
            'route_id':'unit-route','route_ref':value['profile_ref'],
            'input_ref':store.put_blob(b'controlled unit prompt'),'started_at':'2026-10-26T00:00:00Z'}
        start_ref = authority.capture_native('model-call-start',start,execution_id=grant['execution_id'])
        client = SimpleNamespace(trace=[('out','unit/request',{'text':'original fixture packet'}),
                                        ('in','unit/result',{'text':'original fixture response'})])
        trace_ref = model_owner._capture_local_trace(client,dict(protected,model_call_start_ref=start_ref),'completed')
        trace = store.read_record(trace_ref)
        captured = [e['capture_ref'] for e in authority.captures(request_ref,'trace')]
        assert captured == [*trace['event_refs'],trace_ref]
        assert store.read_record(store.read_record(trace['event_refs'][0])['raw_ref'])['payload'] == client.trace[0][2]
        assert not list(store.iter_records(kinds=('model-call','model-provider-observation')))
    finally:
        store.close()
