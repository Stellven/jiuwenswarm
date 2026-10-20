"""Finite composition controls; no default campaign assets or authority."""
from types import SimpleNamespace
import copy
import pytest
from jiuwenswarm.research.contracts import ResearchError


def test_no_evaluation_profile_or_missing_assets_does_not_create_provider_or_records():
    from jiuwenswarm.research.bootstrap_gateway import compose_evaluation_provider
    class NoReads:
        def __getattr__(self,name):pytest.fail('Missing optional bindings must not read or manufacture state: '+name)
    product=SimpleNamespace(snapshot=lambda:{'cc':{'evaluation_profile_ref':None}})
    assert compose_evaluation_provider(store=NoReads(),operator=product,composition=None,principal=None,bindings={}) is None
    configured=SimpleNamespace(snapshot=lambda:{'cc':{'evaluation_profile_ref':{'id':'profile','sha256':'a'*64}}})
    with pytest.raises(ResearchError):compose_evaluation_provider(store=NoReads(),operator=configured,composition=None,principal=None,bindings={'protected_options':{}})


@pytest.mark.asyncio
async def test_literal_context_reuses_real_composition_without_new_snapshot_or_admission(tmp_path):
    from jiuwenswarm.research.admitted_measurement import AdmittedResourceContext,AdmittedMeasurementResources
    from tests.unit_tests.research.test_admitted_measurement import adapter_fixture
    store,adapter,contract,checks,_=await adapter_fixture(tmp_path)
    resources=adapter.resources
    composition=SimpleNamespace(runner=resources.runner,registry=resources.registry,library=resources.composition.library,
        installed=resources.composition.installed,checks=resources.composition.checks)
    counts={t:store.connection.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['library_versions','acceptance','model_calls']}
    context=AdmittedResourceContext(store,resources.operator,composition,resources.principal,resources.exact_binding_refs,resources.runner.executor)
    measured=AdmittedMeasurementResources(context)
    assert measured.runner is resources.runner and context.registry is resources.registry
    assert counts=={t:store.connection.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in counts}
    assert measured._validate(contract,checks)[0]['configuration_ref']==resources.exact_binding_refs['configuration_ref']
    store.close()


def history_startup(root):
    """Actual minimal historical ledger; no executable or qualified model owner."""
    from tests.unit_tests.research.test_evaluation_history import historical_store
    store, runtime_ref, request_ref, actor, request, _ = historical_store(root)
    runtime = store.read_record(runtime_ref)
    operator = SimpleNamespace(snapshot=lambda: {'cc': {
        'evaluation_profile_ref': runtime['profile_ref'], 'plan_policy_ref': runtime['policy_ref']}})
    bindings = {key: copy.deepcopy(runtime[key]) for key in
                ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref', 'workspace_id')}
    bindings['protected_options'] = {'evaluation_runtime_ref': runtime_ref,
        'evaluation_assets_ref': runtime['assets_ref'], 'library_snapshot_ref': runtime['library_snapshot_ref']}
    return store, runtime_ref, actor, request, operator, bindings


def test_historical_reader_startup_needs_no_executable_composition_or_profile_service(tmp_path):
    import jiuwenswarm.research.bootstrap_gateway as gateway
    store, runtime_ref, actor, request, operator, bindings = history_startup(tmp_path)
    before = list(store.iter_records())
    try:
        factory = getattr(gateway, 'compose_evaluation_reader', None)
        assert callable(factory), 'Protected read-only composition is unbuilt'
        reader = factory(store=store, operator=operator, principal=actor, bindings=bindings)
        from jiuwenswarm.research.evaluation_history import EvaluationReader
        assert type(reader) is EvaluationReader and reader.runtime_ref == runtime_ref
        assert reader.request_scope(actor, request['request_id'])['assets_ref'] == bindings['protected_options']['evaluation_assets_ref']
        assert reader.get(actor, request['request_id'])['status'] == 'started'
        assert list(store.iter_records()) == before
        assert not list(store.connection.execute('SELECT * FROM model_calls'))
    finally: store.close()


@pytest.mark.parametrize('dimension', ['account_id', 'workspace_id', 'configuration_ref', 'profile_ref',
    'model_selection_profile_ref', 'deployment_ref', 'policy_ref', 'assets_ref', 'library_snapshot_ref'])
def test_historical_reader_startup_rejects_a_foreign_protected_pin(tmp_path, dimension):
    import jiuwenswarm.research.bootstrap_gateway as gateway
    from jiuwenswarm.research.contracts import Principal
    store, _, actor, _, operator, bindings = history_startup(tmp_path)
    runtime = store.read_record(bindings['protected_options']['evaluation_runtime_ref'])
    foreign = {'id': 'foreign', 'sha256': 'f' * 64}
    if dimension == 'account_id':
        actor = Principal('foreign', actor.workspace_ids, actor.operations, actor.audiences)
    elif dimension == 'workspace_id': bindings[dimension] = 'foreign'
    elif dimension in {'profile_ref', 'policy_ref'}:
        captured = copy.deepcopy(operator.snapshot())
        captured['cc']['evaluation_profile_ref' if dimension == 'profile_ref' else 'plan_policy_ref'] = foreign
        operator = SimpleNamespace(snapshot=lambda: captured)
    elif dimension in {'assets_ref', 'library_snapshot_ref'}:
        bindings['protected_options']['evaluation_assets_ref' if dimension == 'assets_ref' else dimension] = foreign
    else: bindings[dimension] = foreign
    try:
        factory = getattr(gateway, 'compose_evaluation_reader', None)
        assert callable(factory), 'Protected read-only composition is unbuilt'
        with pytest.raises(ResearchError): factory(store=store, operator=operator, principal=actor, bindings=bindings)
        assert not list(store.connection.execute('SELECT * FROM model_calls'))
    finally: store.close()


def test_historical_reader_startup_refuses_runtime_shape_under_unowned_kind(tmp_path):
    import jiuwenswarm.research.bootstrap_gateway as gateway
    store, runtime_ref, actor, _, operator, bindings = history_startup(tmp_path)
    value = store.read_record(runtime_ref)
    value['id'] += ':unowned'
    bindings['protected_options']['evaluation_runtime_ref'] = store.append_record('unowned-source-shaped-runtime', value)
    assert store.record_kind(bindings['protected_options']['evaluation_runtime_ref']) == 'unowned-source-shaped-runtime'
    try:
        factory = getattr(gateway, 'compose_evaluation_reader', None)
        assert callable(factory), 'Protected read-only composition is unbuilt'
        with pytest.raises(ResearchError): factory(store=store, operator=operator, principal=actor, bindings=bindings)
    finally: store.close()


@pytest.mark.asyncio
async def test_attach_issues_historical_scope_when_execution_and_profile_services_are_absent(tmp_path, monkeypatch):
    """Actual startup/auth/store; core execution is explicitly unavailable."""
    import json
    import jiuwenswarm.research.bootstrap_gateway as gateway
    from jiuwenswarm.research.control import ResearchService
    from jiuwenswarm.research.runner import Registry
    from tests.unit_tests.research.test_evaluation_provider import installed_provider
    from tests.unit_tests.research.test_evaluation_authority import capture_runtime
    store, existing, actor, request = await installed_provider(tmp_path / 'source')
    original = existing.resources.admitted.resources
    runtime_ref = capture_runtime(store, existing, [request])
    owner = existing.resources.bind_runtime(runtime_ref)
    owner.accept_request(actor, request, 'E3')
    bindings = dict(original.exact_binding_refs)
    bindings.update(host_id='controlled-history-host')
    bindings['protected_options'] = {'evaluation_runtime_ref': runtime_ref,
        'evaluation_assets_ref': existing.assets_ref, 'library_snapshot_ref': existing.resources.snapshot_ref}
    binding_ref = store.append_record('bootstrap-binding', bindings)
    configuration = tmp_path / 'operator.yaml'; configuration.write_text('controlled-loader-fixture: true\n'); configuration.chmod(0o600)
    locator = tmp_path / 'binding.json'; locator.write_text(json.dumps({'binding_ref': binding_ref})); locator.chmod(0o600)
    accounts_root = tmp_path / 'accounts'
    accounts = gateway.AccountStore(accounts_root); accounts.primary()
    accounts.db.execute('UPDATE accounts SET account_id=? WHERE slot=?', (actor.account_id, 'primary')); accounts.db.commit(); accounts.close()
    handoff = tmp_path / 'ipc'; handoff.mkdir(mode=0o700)
    for name, value in {'JIUWENSWARM_M1_STATE': str(tmp_path / 'state'), 'JIUWENSWARM_M1_ACCOUNTS': str(accounts_root),
        'JIUWENSWARM_M1_CONFIG': str(configuration), 'JIUWENSWARM_M1_ORIGIN': 'http://testserver',
        'JIUWENSWARM_M1_BOOTSTRAP_BINDINGS': str(locator)}.items(): monkeypatch.setenv(name, value)
    monkeypatch.delenv('JIUWENSWARM_M1_RSI_INBOX', raising=False)
    monkeypatch.setattr(gateway, 'M1_REFUSAL_REASON', None)
    monkeypatch.setattr(gateway, 'BOOTSTRAP_HANDOFF', handoff / 'browser-bootstrap.json')
    monkeypatch.setattr(gateway, 'SQLiteRunStore', lambda *_args, **_kwargs: store)
    monkeypatch.setattr(gateway.OperatorConfiguration, 'load', lambda *_args, **_kwargs: original.operator)
    service = ResearchService(store, registry=Registry(), model=None)
    async def unavailable_core(**kwargs):
        assert kwargs['initialize'] is False and kwargs['model'] is None and kwargs['executor'] is None
        return SimpleNamespace(service=service, diagnostics=[], compiler=None, scheduler=None)
    monkeypatch.setattr(gateway, 'compose_core', unavailable_core)
    def no_execution(**kwargs): raise ResearchError('unavailable', 'Execution resources deliberately absent in this control')
    monkeypatch.setattr(gateway, 'compose_evaluation_provider', no_execution)
    attachment = None
    before_calls = list(store.connection.execute('SELECT * FROM model_calls'))
    try:
        attachment = await gateway.attach_native_research(SimpleNamespace())
        assert service.profiles is None and service.evaluation_provider is None
        assert service.evaluation_reader.runtime_ref == runtime_ref
        captured, _ = attachment.authority._startup_evaluation()
        assert captured['runtime_ref'] == runtime_ref and captured['assets_ref'] == existing.assets_ref
        assert captured['campaign_id'] == request['campaign_id']
        grant = {'schema': 'ai4r-evaluation-grant:1', **{key: captured[key] for key in
            ('workspace_id', 'configuration_ref', 'profile_ref', 'profile_id', 'campaign_id')}}
        attachment.authority.issue_evaluation(grant, tmp_path / 'history-token')
        token = (tmp_path / 'history-token').read_text(encoding='ascii')
        authenticated = attachment.authority.authenticate('Bearer ' + token, 'evaluation_profile')
        assert service.evaluation_reader.get(authenticated, request['request_id'])['status'] == 'started'
        assert list(store.connection.execute('SELECT * FROM model_calls')) == before_calls
        assert any(row['code'] == 'evaluation_resources_unavailable' for row in service.evaluation_diagnostics)
    finally:
        if attachment is not None: attachment.close()
        else: store.close()


def test_optional_history_absence_does_not_read_store_or_create_execution_authority():
    import jiuwenswarm.research.bootstrap_gateway as gateway
    class NoReads:
        def __getattr__(self, name): pytest.fail('Optional absence must not read state: ' + name)
    factory = getattr(gateway, 'compose_evaluation_reader', None)
    assert callable(factory), 'Protected read-only composition is unbuilt'
    operator = SimpleNamespace(snapshot=lambda: {'cc': {'evaluation_profile_ref': None}})
    assert factory(store=NoReads(), operator=operator, principal=None, bindings={}) is None
    operator = SimpleNamespace(snapshot=lambda: {'cc': {'evaluation_profile_ref': {'id': 'profile', 'sha256': 'a' * 64}}})
    assert factory(store=NoReads(), operator=operator, principal=None, bindings={'protected_options': {}}) is None


def test_execution_composition_requires_the_exact_runtime_before_touching_resources():
    from jiuwenswarm.research.bootstrap_gateway import compose_evaluation_provider
    class NoReads:
        def __getattr__(self, name): pytest.fail('Missing runtime must refuse before resource use: ' + name)
    pin = {'id': 'captured', 'sha256': 'a' * 64}
    operator = SimpleNamespace(snapshot=lambda: {'cc': {'evaluation_profile_ref': pin}})
    with pytest.raises(ResearchError):
        compose_evaluation_provider(store=NoReads(), operator=operator, composition=NoReads(),
            principal=NoReads(), bindings={'protected_options': {'evaluation_assets_ref': pin, 'library_snapshot_ref': pin}})


@pytest.mark.asyncio
async def test_captured_campaign_composition_reuses_exact_snapshot_and_subject_without_writes(tmp_path):
    from jiuwenswarm.research.bootstrap_gateway import compose_evaluation_provider
    from tests.unit_tests.research.test_evaluation_provider import installed_provider
    from tests.unit_tests.research.test_evaluation_authority import capture_runtime
    store,existing,actor,request=await installed_provider(tmp_path)
    original=existing.resources.admitted.resources
    composition=SimpleNamespace(runner=original.runner,registry=original.registry,library=original.composition.library,
        installed=original.composition.installed,checks=original.composition.checks)
    bindings=dict(original.exact_binding_refs)
    runtime_ref=capture_runtime(store,existing,[request])
    bindings['protected_options']={'evaluation_assets_ref':existing.assets_ref,'evaluation_runtime_ref':runtime_ref,
        'library_snapshot_ref':existing.resources.snapshot_ref}
    before=list(store.iter_records())
    result=compose_evaluation_provider(store=store,operator=original.operator,composition=composition,principal=actor,bindings=bindings)
    assert result.assets_ref==existing.assets_ref and result.assets['campaign_id']==request['campaign_id']
    assert result.resources.snapshot_ref==existing.resources.snapshot_ref
    assert result.resources.authority.runtime_ref==runtime_ref
    assert result.available_entry_points==('E3',)
    assert list(store.iter_records())==before
    store.close()
