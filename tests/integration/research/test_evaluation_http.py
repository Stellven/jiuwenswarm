"""Actual HTTP scope controls using explicit disposable provider doubles.

These tests establish adapter authorization, not model/campaign qualification.
"""
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock
import copy
import io
import json
import zipfile
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.shell_auth import SessionAuthority
from jiuwenswarm.research.contracts import ResearchError


def setup(root):
    config={'id':'config','sha256':'a'*64};profile={'id':'profile','sha256':'b'*64}
    runtime={'id':'evaluation-runtime:controlled','sha256':'c'*64}
    assets_ref={'id':'evaluation-assets:controlled','sha256':'d'*64}
    auth=SessionAuthority(root/'sessions','http://testserver')
    auth.initialize(Principal('owner',frozenset({'work'}),frozenset({'status','readiness','submit'})))
    context={'account_id':'owner','workspace_id':'work','configuration_ref':config,'profile_ref':profile,'profile_id':'approved'}
    auth.configure_evaluation(context,run_lookup=lambda _:None,run_reconcile=lambda *_:[],campaign_id='one',
        runtime_ref=runtime,assets_ref=assets_ref)
    grant=auth.issue_evaluation({'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':'one'},root/'evaluation-token')
    header={'Authorization':'Bearer '+(root/'evaluation-token').read_text(encoding='ascii')}
    provider=SimpleNamespace(available_entry_points=('E2','E3'),assets={'profile_ref':profile,'configuration_ref':config,
        'workspace_id':'work','account_id':'owner','campaign_id':'one'},profile={'profile_id':'approved'},
        node_replay=AsyncMock(return_value={'invalid_for_product':True,'replay_id':'controlled'}),
        single_cc=AsyncMock(return_value={'invalid_for_product':True,'invocation_id':'controlled'}),
        get=Mock(return_value={'invalid_for_product':True,'status':'claimed'}),runtime_ref=runtime,assets_ref=assets_ref)
    provider.resources=SimpleNamespace(authority=SimpleNamespace(runtime_ref=copy.deepcopy(runtime)))
    provider.request_scope=Mock(side_effect=lambda *_: {**{key:copy.deepcopy(provider.assets[key]) for key in
        ('account_id','workspace_id','campaign_id','profile_ref','configuration_ref')},
        'profile_id':provider.profile['profile_id'],'runtime_ref':copy.deepcopy(runtime),'assets_ref':copy.deepcopy(assets_ref)})
    service=SimpleNamespace(evaluation_provider=provider,evaluation_reader=provider)
    channel=SimpleNamespace(research_profile=True,research_service=service,research_authority=auth,set_handshake_auth=Mock())
    from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
    app=FastAPI();mount_research_routes(app,channel)
    return auth,provider,app,header,grant


def test_actual_http_requires_exact_token_campaign_and_supported_operation_before_effect(tmp_path):
    auth,provider,app,header,grant=setup(tmp_path)
    try:
        with TestClient(app) as client:
            for route,op in [('node-replay',provider.node_replay),('single-cc',provider.single_cc)]:
                request={'request_id':'controlled','campaign_id':'one','evaluation_profile_id':'approved'}
                response=client.post('/api/v1/evaluation/'+route,json=request,headers=header)
                assert response.status_code==200 and response.json()['invalid_for_product'] is True
                op.assert_awaited_once();op.reset_mock()
                for change in [{'campaign_id':'foreign'},{'evaluation_profile_id':'foreign'}]:
                    assert client.post('/api/v1/evaluation/'+route,json=request|change,headers=header).status_code==403
                main={'Authorization':'Bearer '+auth.token_path.read_text(encoding='ascii')}
                assert client.post('/api/v1/evaluation/'+route,json=request,headers=main).status_code in {401,403}
                op.assert_not_called()
            auth.revoke_evaluation(grant['grant_id'])
            assert client.post('/api/v1/evaluation/single-cc',json=request,headers=header).status_code==401
    finally:auth.close()


def test_missing_profile_provider_is_unavailable_without_alternate_product_path(tmp_path):
    auth,provider,app,header,_=setup(tmp_path)
    try:
        app.state.research_service.evaluation_provider=None
        with TestClient(app) as client:
            response=client.post('/api/v1/evaluation/single-cc',json={'campaign_id':'one','evaluation_profile_id':'approved'},headers=header)
            assert response.status_code==503
        provider.single_cc.assert_not_called()
    finally:auth.close()


def test_reconcile_uses_exact_token_even_when_live_resources_become_unavailable(tmp_path):
    auth,provider,app,header,_=setup(tmp_path)
    try:
        provider.available_entry_points=()
        with TestClient(app) as client:
            for _ in range(2):
                response=client.get('/api/v1/evaluation/requests/claimed',headers=header)
                assert response.status_code==200 and response.json()['status']=='claimed'
            provider.assets['campaign_id']='foreign'
            assert client.get('/api/v1/evaluation/requests/claimed',headers=header).status_code==403
        assert provider.get.call_count==2
        provider.single_cc.assert_not_called();provider.node_replay.assert_not_called()
    finally:auth.close()


def historical_reader(provider):
    """Explicit HTTP-only fixture; it does not qualify a core event closure."""
    runtime = {'id': 'evaluation-runtime:controlled', 'sha256': 'c' * 64}
    assets = {'id': 'evaluation-assets:controlled', 'sha256': 'd' * 64}
    scope = {key: copy.deepcopy(provider.assets[key]) for key in
             ('account_id', 'workspace_id', 'campaign_id', 'profile_ref', 'configuration_ref')}
    scope.update(profile_id=provider.profile['profile_id'], runtime_ref=runtime, assets_ref=assets)
    response = {'request_id': 'claimed', 'status': 'outcome_unknown', 'result': None,
                'failure_ref': None, 'invalid_for_product': True}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('evaluation_export.json', json.dumps({'controlled_http_fixture': True}))
        archive.writestr('originals/packet.stdout', b'original\x00packet\n')
    reader = SimpleNamespace(runtime_ref=copy.deepcopy(runtime), assets_ref=copy.deepcopy(assets),
        request_scope=Mock(return_value=scope), get=Mock(return_value=response),
        export_bytes=Mock(return_value=output.getvalue()))
    return reader, scope, response, output.getvalue()


def bind_historical_runtime(auth, provider, reader, root):
    context = {key: copy.deepcopy(provider.assets[key]) for key in
               ('account_id', 'workspace_id', 'configuration_ref', 'profile_ref')}
    context['profile_id'] = provider.profile['profile_id']
    auth.configure_evaluation(context, run_lookup=lambda _: None, run_reconcile=lambda *_: [],
        campaign_id=provider.assets['campaign_id'], runtime_ref=reader.runtime_ref, assets_ref=reader.assets_ref)
    binding = {'schema': 'ai4r-evaluation-grant:1',
        **{key: value for key, value in context.items() if key != 'account_id'},
        'campaign_id': provider.assets['campaign_id']}
    auth.issue_evaluation(binding, root / 'historical-token')
    return {'Authorization': 'Bearer ' + (root / 'historical-token').read_text(encoding='ascii')}, context


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_historical_request_reader_survives_execution_provider_loss(tmp_path, representation):
    auth, provider, app, headers, _ = setup(tmp_path)
    reader, scope, expected, expected_zip = historical_reader(provider)
    headers, _ = bind_historical_runtime(auth, provider, reader, tmp_path)
    app.state.research_service.evaluation_reader = reader
    app.state.research_service.evaluation_provider = None
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/claimed', headers=headers)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        if representation == 'json':
            assert response.json() == expected
            reader.get.assert_called_once()
            reader.export_bytes.assert_not_called()
        else:
            assert response.headers['content-type'].split(';')[0] == 'application/zip'
            assert response.content == expected_zip
            reader.export_bytes.assert_called_once()
            reader.get.assert_not_called()
        reader.request_scope.assert_called_once()
        provider.get.assert_not_called()
        provider.node_replay.assert_not_called(); provider.single_cc.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('representation', ['json', 'zip'])
@pytest.mark.parametrize('dimension', ['account_id', 'workspace_id', 'campaign_id', 'profile_id',
    'profile_ref', 'configuration_ref', 'runtime_ref', 'assets_ref'])
def test_historical_http_uses_original_request_scope_before_any_response_bytes(tmp_path, representation, dimension):
    auth, provider, app, headers, _ = setup(tmp_path)
    reader, scope, _, _ = historical_reader(provider)
    headers, _ = bind_historical_runtime(auth, provider, reader, tmp_path)
    app.state.research_service.evaluation_reader = reader
    # Keep CURRENT provider metadata authorized. Only the persisted request
    # context is foreign; authorizing from provider metadata would leak bytes.
    scope[dimension] = (scope[dimension] | {'sha256': 'e' * 64}) if dimension.endswith('_ref') else 'foreign'
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/claimed', headers=headers)
        assert response.status_code in {401, 403, 404}
        reader.get.assert_not_called(); reader.export_bytes.assert_not_called()
        provider.get.assert_not_called()
        provider.node_replay.assert_not_called(); provider.single_cc.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_unknown_historical_request_cannot_fall_back_to_current_provider(tmp_path, representation):
    auth, provider, app, headers, _ = setup(tmp_path)
    reader, _, _, _ = historical_reader(provider)
    headers, _ = bind_historical_runtime(auth, provider, reader, tmp_path)
    reader.request_scope.side_effect = ResearchError('not_found', 'No owned historical request')
    app.state.research_service.evaluation_reader = reader
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/unknown', headers=headers)
        assert response.status_code == 404
        reader.get.assert_not_called(); reader.export_bytes.assert_not_called()
        provider.get.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('dimension', ['runtime_ref', 'assets_ref'])
def test_private_runtime_binding_change_revokes_original_historical_token(tmp_path, dimension):
    auth, provider, app, _, _ = setup(tmp_path)
    reader, _, _, _ = historical_reader(provider)
    headers, context = bind_historical_runtime(auth, provider, reader, tmp_path)
    app.state.research_service.evaluation_reader = reader
    changed = {'runtime_ref': reader.runtime_ref, 'assets_ref': reader.assets_ref}
    changed[dimension] = changed[dimension] | {'sha256': 'e' * 64}
    try:
        auth.configure_evaluation(context, run_lookup=lambda _: None, run_reconcile=lambda *_: [],
            campaign_id='one', **changed)
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/claimed', headers=headers)
        assert response.status_code == 401
        reader.request_scope.assert_not_called(); reader.get.assert_not_called(); reader.export_bytes.assert_not_called()
        provider.get.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_current_provider_metadata_cannot_authorize_a_foreign_stored_request(tmp_path, representation):
    auth, provider, app, headers, _ = setup(tmp_path)
    reader, scope, _, _ = historical_reader(provider)
    scope['campaign_id'] = 'another-campaign-same-account'
    app.state.research_service.evaluation_reader = reader
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/foreign', headers=headers)
        assert response.status_code in {401, 403}
        reader.get.assert_not_called(); reader.export_bytes.assert_not_called()
        provider.get.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_revocation_during_historical_read_prevents_response_publication(tmp_path, representation):
    auth, provider, app, _, _ = setup(tmp_path)
    reader, _, expected, expected_zip = historical_reader(provider)
    headers, _ = bind_historical_runtime(auth, provider, reader, tmp_path)
    app.state.research_service.evaluation_reader = reader
    def revoke_and_return(*args, **kwargs):
        # Root fixture uses the real token owner; returned bytes are deliberately
        # available but must not be published after this grant is revoked.
        with auth._lock:
            auth.db.execute("UPDATE grants SET revoked=1 WHERE kind='evaluation_http'")
        return expected_zip if representation == 'zip' else expected
    if representation == 'zip':
        headers = headers | {'Accept': 'application/zip'}
        reader.export_bytes.side_effect = revoke_and_return
    else: reader.get.side_effect = revoke_and_return
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/claimed', headers=headers)
        assert response.status_code == 401
        assert response.content != expected_zip
        assert response.json().get('status') != expected['status']
    finally: auth.close()


def actual_history_app(root, *, grant_campaign=None):
    """Connect the actual read-only core reader and actual token/HTTP adapter.

    The source fixture is a minimal historical journal, not a qualified worker
    or complete production export closure.
    """
    from tests.unit_tests.research.test_evaluation_history import historical_store
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, runtime, request_ref, actor, request, event = historical_store(root / 'store')
    reader = EvaluationReader(store, runtime_ref=runtime)
    scope = reader.request_scope(actor, request['request_id'])
    auth = SessionAuthority(root / 'sessions', 'http://testserver')
    auth.initialize(Principal(actor.account_id, actor.workspace_ids, frozenset({'status', 'readiness', 'submit'}), actor.audiences))
    context = {key: scope[key] for key in ('account_id', 'workspace_id', 'configuration_ref', 'profile_ref', 'profile_id')}
    auth.configure_evaluation(context, run_lookup=lambda _: None, run_reconcile=lambda *_: [],
        campaign_id=None if grant_campaign else scope['campaign_id'], runtime_ref=runtime, assets_ref=scope['assets_ref'])
    grant = {'schema': 'ai4r-evaluation-grant:1', **{k: v for k, v in context.items() if k != 'account_id'},
             'campaign_id': grant_campaign or scope['campaign_id']}
    auth.issue_evaluation(grant, root / 'actual-history-token')
    headers = {'Authorization': 'Bearer ' + (root / 'actual-history-token').read_text(encoding='ascii')}
    service = SimpleNamespace(evaluation_provider=None, evaluation_reader=reader)
    channel = SimpleNamespace(research_profile=True, research_service=service, research_authority=auth, set_handshake_auth=Mock())
    from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
    app = FastAPI(); mount_research_routes(app, channel)
    return store, auth, app, headers, request, request_ref


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_actual_core_reader_http_preserves_original_journal_bytes_without_execution(tmp_path, representation):
    store, auth, app, headers, request, request_ref = actual_history_app(tmp_path)
    before = {name: list(store.connection.execute('SELECT * FROM ' + name)) for name in
              ('runs', 'requests', 'nodes', 'attempts', 'acceptance', 'model_calls', 'tool_calls')}
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/' + request['request_id'], headers=headers)
        assert response.status_code == 200 and response.headers['cache-control'] == 'private, no-store'
        if representation == 'json':
            assert response.json() == {'request_id': request['request_id'], 'status': 'started',
                'result': None, 'failure_ref': None, 'invalid_for_product': True}
        else:
            assert response.headers['content-type'].split(';')[0] == 'application/zip'
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                manifest = json.loads(archive.read('evaluation_export.json'))
                assert set(archive.namelist()) == {'evaluation_export.json'} | {f['path'] for f in manifest['files']}
                item = next(f for f in manifest['files'] if f['kind'] == 'original_request')
                original_ref = store.read_record(request_ref)['original_request_ref']
                assert item['artifact_ref'] == original_ref and archive.read(item['path']) == store.read_blob(original_ref)
        assert before == {name: list(store.connection.execute('SELECT * FROM ' + name)) for name in before}
    finally: auth.close(); store.close()


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_actual_reader_http_denies_same_account_foreign_campaign(tmp_path, representation):
    store, auth, app, headers, request, _ = actual_history_app(tmp_path, grant_campaign='same-account-foreign-campaign')
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/' + request['request_id'], headers=headers)
        assert response.status_code == 403
        assert 'evaluation_export' not in response.text and 'original_request' not in response.text
    finally: auth.close(); store.close()


@pytest.mark.parametrize('representation', ['json', 'zip'])
def test_actual_reader_http_unknown_identity_never_invokes_execution(tmp_path, representation):
    store, auth, app, headers, _, _ = actual_history_app(tmp_path)
    if representation == 'zip': headers = headers | {'Accept': 'application/zip'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/evaluation/requests/not-owned', headers=headers)
        assert response.status_code == 404 and not list(store.connection.execute('SELECT * FROM model_calls'))
    finally: auth.close(); store.close()


@pytest.mark.parametrize('route', ['node-replay', 'single-cc'])
def test_evaluation_post_preserves_original_utf8_body_for_the_private_owner(tmp_path, route):
    auth, provider, app, headers, _ = setup(tmp_path)
    original = b' { "request_id" : "controlled", "campaign_id": "one",\n "evaluation_profile_id":"approved", "note":"\\u00e9" }\n'
    operation = provider.node_replay if route == 'node-replay' else provider.single_cc
    try:
        with TestClient(app) as client:
            response = client.post('/api/v1/evaluation/' + route, content=original,
                                   headers=headers | {'Content-Type': 'application/json'})
        assert response.status_code == 200
        operation.assert_awaited_once()
        assert operation.await_args.args[1] == json.loads(original)
        assert operation.await_args.kwargs == {'original_body': original}
    finally: auth.close()


INVALID_BODIES = {
    'duplicate_root': b'{"request_id":"same","request_id":"same","campaign_id":"one","evaluation_profile_id":"approved"}',
    'duplicate_nested': b'{"campaign_id":"one","evaluation_profile_id":"approved","input":{"port":1,"port":2}}',
    'nan': b'{"campaign_id":"one","evaluation_profile_id":"approved","n":NaN}',
    'infinity': b'{"campaign_id":"one","evaluation_profile_id":"approved","n":Infinity}',
    'negative_infinity': b'{"campaign_id":"one","evaluation_profile_id":"approved","n":-Infinity}',
    'utf16': '{"campaign_id":"one","evaluation_profile_id":"approved"}'.encode('utf-16'),
    'invalid_utf8': b'{"campaign_id":"one","evaluation_profile_id":"approved","text":"\xff"}',
    'trailing_bytes': b'{"campaign_id":"one","evaluation_profile_id":"approved"} trailing',
}


@pytest.mark.parametrize('route', ['node-replay', 'single-cc'])
@pytest.mark.parametrize('body_name', list(INVALID_BODIES))
def test_evaluation_post_rejects_non_strict_json_before_provider_claim(tmp_path, route, body_name):
    auth, provider, app, headers, _ = setup(tmp_path)
    try:
        with TestClient(app) as client:
            response = client.post('/api/v1/evaluation/' + route, content=INVALID_BODIES[body_name],
                                   headers=headers | {'Content-Type': 'application/json'})
        assert response.status_code == 422
        provider.node_replay.assert_not_called(); provider.single_cc.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('route', ['node-replay', 'single-cc'])
@pytest.mark.parametrize('dimension', ['profile_ref', 'runtime_ref', 'assets_ref'])
def test_evaluation_post_checks_private_provider_pins_against_original_token(tmp_path, route, dimension):
    auth, provider, app, headers, _ = setup(tmp_path)
    if dimension == 'profile_ref':
        provider.assets[dimension] = provider.assets[dimension] | {'sha256': 'e' * 64}
    elif dimension == 'runtime_ref':
        provider.resources.authority.runtime_ref = provider.runtime_ref | {'sha256': 'e' * 64}
    else: provider.assets_ref = provider.assets_ref | {'sha256': 'e' * 64}
    try:
        with TestClient(app) as client:
            response = client.post('/api/v1/evaluation/' + route,
                json={'campaign_id': 'one', 'evaluation_profile_id': 'approved'}, headers=headers)
        assert response.status_code == 403
        provider.node_replay.assert_not_called(); provider.single_cc.assert_not_called()
    finally: auth.close()


@pytest.mark.parametrize('route', ['node-replay', 'single-cc'])
def test_evaluation_post_requires_bound_private_runtime_before_provider_claim(tmp_path, route):
    auth, provider, app, headers, _ = setup(tmp_path)
    provider.resources.authority = None
    try:
        with TestClient(app) as client:
            response = client.post('/api/v1/evaluation/' + route,
                json={'campaign_id': 'one', 'evaluation_profile_id': 'approved'}, headers=headers)
        assert response.status_code == 503
        provider.node_replay.assert_not_called(); provider.single_cc.assert_not_called()
    finally: auth.close()


@pytest.mark.asyncio
async def test_actual_http_private_owner_runs_two_slots_once_and_reads_after_loss(tmp_path):
    """Real HTTP/auth/core with an explicit controlled subscription carrier.

    Checking eligibility is fixture-controlled. This is no live model, native
    socket/kernel, calibrated campaign or complete QA acceptance claim.
    """
    import httpx
    from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes
    store, provider, actor, first, prompts = await source_fixture(tmp_path / 'source')
    second = first | {'request_id': first['request_id'] + '-second'}
    runtime_ref = capture_runtime(store, provider, [first, second])
    owner = provider.resources.bind_runtime(runtime_ref)
    reader = EvaluationReader(store, runtime_ref=runtime_ref)
    auth = SessionAuthority(tmp_path / 'sessions', 'http://testserver')
    auth.initialize(Principal(actor.account_id, actor.workspace_ids, frozenset({'status', 'readiness', 'submit'})))
    context = {'account_id': actor.account_id, 'workspace_id': provider.assets['workspace_id'],
        'configuration_ref': provider.assets['configuration_ref'], 'profile_ref': provider.profile_ref,
        'profile_id': provider.profile['profile_id']}
    auth.configure_evaluation(context, run_lookup=lambda _: None, run_reconcile=lambda *_: [],
        campaign_id=provider.assets['campaign_id'], runtime_ref=runtime_ref, assets_ref=provider.assets_ref)
    auth.issue_evaluation({'schema': 'ai4r-evaluation-grant:1',
        **{key: value for key, value in context.items() if key != 'account_id'},
        'campaign_id': provider.assets['campaign_id']}, tmp_path / 'actual-private-token')
    headers = {'Authorization': 'Bearer ' + (tmp_path / 'actual-private-token').read_text(encoding='ascii')}
    service = SimpleNamespace(evaluation_provider=provider, evaluation_reader=reader)
    channel = SimpleNamespace(research_profile=True, research_service=service, research_authority=auth, set_handshake_auth=Mock())
    app = FastAPI(); mount_research_routes(app, channel)
    tables = ('runs', 'requests', 'nodes', 'attempts', 'acceptance', 'model_calls', 'tool_calls')
    before = {name: list(store.connection.execute('SELECT * FROM ' + name)) for name in tables}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://testserver') as client:
            results = []
            for request in (first, second):
                raw = b'  ' + json.dumps(request, indent=2).encode('utf-8') + b'\n'
                response = await client.post('/api/v1/evaluation/single-cc', content=raw,
                    headers=headers | {'Content-Type': 'application/json'})
                assert response.status_code == 200, response.text
                results.append(response.json())
                rows = list(store.connection.execute('SELECT request_ref FROM evaluation_requests WHERE slot=?',
                    ('slot' + str(len(results) - 1),)))
                assert len(rows) == 1
                original = store.read_record(json.loads(rows[0]['request_ref']))['original_request_ref']
                assert store.read_blob(original) == raw
                duplicate = await client.post('/api/v1/evaluation/single-cc', content=raw, headers=headers)
                assert duplicate.status_code == 200 and duplicate.json() == response.json()
            assert len(prompts) == 2 and results[0]['invocation_id'] != results[1]['invocation_id']
            service.evaluation_provider = None
            for request in (first, second):
                response = await client.get('/api/v1/evaluation/requests/' + request['request_id'], headers=headers)
                assert response.status_code == 200 and response.json()['status'] == 'completed'
                exported = await client.get('/api/v1/evaluation/requests/' + request['request_id'],
                    headers=headers | {'Accept': 'application/zip'})
                assert exported.status_code == 200
                with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                    manifest = json.loads(archive.read('evaluation_export.json'))
                    captured = next(item for item in manifest['files'] if item['kind'] == 'original_request')
                    assert archive.read(captured['path']) == b'  ' + json.dumps(request, indent=2).encode('utf-8') + b'\n'
            assert len(prompts) == 2
        assert before == {name: list(store.connection.execute('SELECT * FROM ' + name)) for name in tables}
    finally: auth.close(); store.close()
