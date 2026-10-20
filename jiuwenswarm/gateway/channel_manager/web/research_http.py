"""Authenticated native M1 HTTP boundary; all research work stays in ResearchService."""
from __future__ import annotations

import inspect
import json
import secrets
from types import SimpleNamespace

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from jiuwenswarm.research.contracts.types import ResearchError


async def _result(value):
    return await value if inspect.isawaitable(value) else value


def _evaluation_json(raw: bytes) -> dict:
    """Decode the original wire body without losing duplicate-key evidence."""
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('duplicate JSON key')
            value[key] = item
        return value
    def nonfinite(_): raise ValueError('nonfinite JSON value')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError) as error:
        raise ResearchError('validation', 'Strict UTF8 JSON is required') from error
    if not isinstance(value, dict): raise ResearchError('validation')
    return value


def _error(exc: ResearchError, request_id=None, run_id=None) -> JSONResponse:
    category = {'identity_conflict': 'conflict', 'upload_in_use': 'conflict'}.get(exc.code, exc.code)
    if category not in {'auth', 'validation', 'not_found', 'conflict', 'unavailable', 'internal'}:
        category = 'validation'
    status = {'auth': 401, 'validation': 422, 'not_found': 404, 'conflict': 409, 'unavailable': 503, 'internal': 500}[category]
    if category == 'auth' and exc.details.get('http_status') == 403:
        status = 403
    # Error strings are deliberately independent of arbitrary exception content.
    messages = {'auth': 'The request is outside the authenticated grant.', 'validation': 'The request does not satisfy the supported contract.',
                'not_found': 'The requested resource is unavailable.', 'conflict': 'The request conflicts with existing content or active use.',
                'unavailable': 'A required runtime prerequisite is unavailable.', 'internal': 'The request could not be durably completed.'}
    payload = {'schema_version': '1.0.0', 'id': 'error:' + secrets.token_hex(12), 'category': category,
               'message': messages[category], 'request_id': request_id, 'run_id': run_id,
               'evidence_refs': [], 'correction': 'Check the request and authenticated scope; inspect readiness before submitting new work.'}
    return JSONResponse(payload, status_code=status, headers={'Cache-Control': 'private, no-store'})


def mount_research_routes(app, channel) -> None:
    service = getattr(channel, 'research_service', None)
    authority = getattr(channel, 'research_authority', None)
    protected = bool(getattr(channel, 'research_profile', False))
    if service is None and not protected:
        return
    if service is None or authority is None:
        raise RuntimeError('Protected research profile requires its service and session authority')
    app.state.research_service = service
    app.state.research_authority = authority

    def handshake(**kwargs):
        try:
            p = authority.authenticate_ws(kwargs['headers'], 'status')
            return SimpleNamespace(success=True, user_id=p.account_id)
        except ResearchError:
            return SimpleNamespace(success=False, user_id='')
    channel.set_handshake_auth(handshake)

    async def invoke(request: Request, operation: str, callback, *, workspace_id=None, run_id=None, submission=None, client_request_id=None):
        principal = None
        try:
            principal = authority.authenticate(request.headers.get('authorization'), operation, workspace_id,
                                               request.query_params.get('audience'))
            authority.authorize_evaluation(request.headers.get('authorization'), operation,
                submission=submission, run_id=run_id, client_request_id=client_request_id)
            if getattr(channel, 'research_refusal_reason', None) and operation not in {
                    'status', 'readiness', 'reconcile', 'export', 'cancel', 'list_uploads'}:
                raise ResearchError('unavailable', 'Mandatory operator configuration is unavailable; inspection only')
            return JSONResponse(await _result(callback(principal)), headers={'Cache-Control': 'private, no-store'})
        except ResearchError as exc:
            if principal is not None and exc.code == 'auth' and 'http_status' not in exc.details:
                exc = ResearchError('auth', exc.message, dict(exc.details, http_status=403))
            return _error(exc, run_id=run_id)
        except Exception:
            return _error(ResearchError('internal'), run_id=run_id)

    @app.post('/auth/research/bootstrap')
    async def bootstrap(request: Request):
        try:
            value = await request.json()
            if not isinstance(value, dict) or set(value) != {'challenge'}:
                raise ResearchError('validation')
            grant = authority.bootstrap(value['challenge'], origin=request.headers.get('origin'), host=request.headers.get('host'))
            defaults = await _result(service.client_defaults(authority.authenticate('Bearer ' + grant['token'], 'status')))
            response = JSONResponse({'token': grant['token'], 'defaults': defaults})
            response.headers['set-cookie'] = grant['set_cookie']
            response.headers['cache-control'] = 'no-store'
            return response
        except ResearchError as exc:
            return _error(exc)
        except Exception:
            return _error(ResearchError('validation'))

    @app.post('/auth/research/logout')
    async def logout(request: Request):
        try:
            authority.authenticate(request.headers.get('authorization'), 'status')
            authority.revoke(request.headers['authorization'][7:])
            response = JSONResponse({'revoked': True})
            response.delete_cookie(authority.cookie_name, path='/', httponly=True, samesite='strict')
            return response
        except ResearchError as exc:
            return _error(exc)

    @app.get('/api/v1/readiness')
    async def readiness(request: Request):
        return await invoke(request, 'readiness', lambda p: service.readiness(p))

    @app.post('/api/v1/runs')
    async def submit(request: Request):
        try:
            authority.authenticate(request.headers.get('authorization'), 'submit')
            value = await request.json()
            if not isinstance(value, dict):
                raise ResearchError('validation')
        except ResearchError as exc:
            return _error(exc)
        except Exception:
            return _error(ResearchError('validation'))
        return await invoke(request, 'submit', lambda p: service.submit(p, value), workspace_id=value.get('workspace_id'), submission=value)

    async def evaluation(request: Request,entry_point: str):
        try:
            authorization=request.headers.get('authorization')
            # Authenticate before parsing input or exposing provider metadata.
            principal=authority.authenticate(authorization,'evaluation_profile')
            original_body=await request.body()
            value=_evaluation_json(original_body)
            provider=getattr(service,'evaluation_provider',None)
            if provider is None:raise ResearchError('unavailable','Approved evaluation resources are unavailable')
            owner=getattr(getattr(provider,'resources',None),'authority',None)
            if owner is None:raise ResearchError('unavailable','The protected private evaluation runtime is unavailable')
            assets=provider.assets
            if (value.get('campaign_id')!=assets['campaign_id']
                    or value.get('evaluation_profile_id')!=provider.profile['profile_id']):
                raise ResearchError('auth','Evaluation request differs from the exact campaign grant',{'http_status':403})
            authority.authorize_evaluation_entry(authorization,
                profile_id=provider.profile['profile_id'],workspace_id=assets['workspace_id'],
                campaign_id=assets['campaign_id'],configuration_ref=assets['configuration_ref'],
                profile_ref=assets['profile_ref'],runtime_ref=owner.runtime_ref,assets_ref=provider.assets_ref)
            callback=provider.node_replay if entry_point=='E2' else provider.single_cc
            return JSONResponse(await _result(callback(principal,value,original_body=original_body)),headers={'Cache-Control':'private, no-store'})
        except ResearchError as exc:return _error(exc)
        except Exception:return _error(ResearchError('internal'))

    @app.post('/api/v1/evaluation/node-replay')
    async def node_replay(request: Request):return await evaluation(request,'E2')

    @app.post('/api/v1/evaluation/single-cc')
    async def single_cc(request: Request):return await evaluation(request,'E3')

    @app.get('/api/v1/evaluation/requests/{request_id}')
    async def evaluation_status(request: Request,request_id: str):
        try:
            authorization=request.headers.get('authorization')
            principal=authority.authenticate(authorization,'evaluation_profile')
            reader=getattr(service,'evaluation_reader',None)
            if reader is None:raise ResearchError('unavailable','Approved historical evaluation reader is unavailable')
            scope=await _result(reader.request_scope(principal,request_id))
            fields={'account_id','workspace_id','campaign_id','profile_id','profile_ref',
                    'configuration_ref','runtime_ref','assets_ref'}
            if (not isinstance(scope,dict) or set(scope)!=fields
                    or scope['account_id']!=principal.account_id
                    or scope['runtime_ref']!=reader.runtime_ref):
                raise ResearchError('auth','Historical request differs from its protected runtime',{'http_status':403})
            def authorize_original():
                authority.authorize_evaluation_entry(authorization,**{key:scope[key] for key in fields-{'account_id'}})
            authorize_original()
            # Reading requires only the original protected scope and durable
            # reader. It cannot fall back to live execution or replay work.
            if 'application/zip' in request.headers.get('accept','').lower():
                contents=await _result(reader.export_bytes(principal,request_id,audience='researcher'))
                authorize_original()
                return Response(contents,media_type='application/zip',headers={'Cache-Control':'private, no-store',
                    'Content-Disposition':'attachment; filename="evaluation_export.zip"'})
            value=await _result(reader.get(principal,request_id))
            authorize_original()
            return JSONResponse(value,headers={'Cache-Control':'private, no-store'})
        except ResearchError as exc:return _error(exc)
        except Exception:return _error(ResearchError('internal'))

    @app.get('/api/v1/runs')
    async def reconcile(request: Request):
        try:
            authority.authenticate(request.headers.get('authorization'), 'reconcile')
        except ResearchError as exc:
            return _error(exc)
        client_id = request.query_params.get('client_request_id')
        if not client_id:
            return _error(ResearchError('validation'))
        async def unique_status(principal):
            rows = await _result(service.list(principal, client_request_id=client_id))
            if not isinstance(rows, list) or len(rows) > 1:
                raise ResearchError('internal', 'Idempotency uniqueness could not be established')
            if not rows:
                raise ResearchError('not_found', 'No delivered request was found')
            return rows[0]
        return await invoke(request, 'reconcile', unique_status, client_request_id=client_id)

    @app.get('/api/v1/runs/{run_id}')
    async def status(request: Request, run_id: str):
        return await invoke(request, 'status', lambda p: service.get(p, run_id), run_id=run_id)

    @app.get('/api/v1/runs/{run_id}/export')
    async def export(request: Request, run_id: str):
        audience = request.query_params.get('audience', 'researcher')
        if 'application/zip' in request.headers.get('accept', '').lower():
            try:
                principal = authority.authenticate(request.headers.get('authorization'), 'export', audience=audience)
                authority.authorize_evaluation(request.headers.get('authorization'), 'export', run_id=run_id)
                manifest, contents = await _result(service.artifact_bytes(principal, run_id, audience=audience))
                from jiuwenswarm.research.inspection import encode_export_zip
                return Response(encode_export_zip(manifest, contents), media_type='application/zip',
                                headers={'Cache-Control': 'private, no-store', 'Content-Disposition': 'attachment; filename="run_export.zip"'})
            except ResearchError as exc:
                return _error(exc, run_id=run_id)
            except Exception:
                return _error(ResearchError('internal'), run_id=run_id)
        return await invoke(request, 'export', lambda p: service.artifact(p, run_id, audience=audience), run_id=run_id)

    @app.post('/api/v1/runs/{run_id}/cancel')
    async def cancel(request: Request, run_id: str):
        try:
            authority.authenticate(request.headers.get('authorization'), 'cancel')
            value = await request.json()
            if not isinstance(value, dict) or set(value) != {'request_id'} or not isinstance(value['request_id'], str) or not value['request_id']:
                raise ResearchError('validation')
        except ResearchError as exc:
            return _error(exc, run_id=run_id)
        except Exception:
            return _error(ResearchError('validation'), run_id=run_id)
        return await invoke(request, 'cancel', lambda p: service.cancel(p, run_id, value['request_id']), run_id=run_id)

    @app.post('/api/v1/inputs/{kind}')
    async def upload(request: Request, kind: str):
        # Authorize before reading attacker-supplied multipart bytes.
        async def publish(p):
            form = await request.form()
            if set(form) != {'file', 'scope_id'} or not hasattr(form['file'], 'read'):
                raise ResearchError('validation')
            file = form['file']
            return await _result(service.upload(p, kind, str(form['scope_id']), file.filename, await file.read()))
        return await invoke(request, 'upload', publish)

    @app.get('/api/v1/inputs')
    async def inputs(request: Request):
        scope_id = request.query_params.get('scope_id')
        return await invoke(request, 'list_uploads', lambda p: service.uploads(p, scope_id))

    @app.delete('/api/v1/inputs/{upload_id}')
    async def delete_upload(request: Request, upload_id: str):
        return await invoke(request, 'delete_upload', lambda p: service.delete_upload(p, upload_id))


async def native_research_message(channel, ws, method: str, params: dict):
    """Return (handled, payload) before native file processing or dispatch.

    Every protected message is reauthenticated, including messages on an already
    open connection. A research prompt only captures/qualifies; the ordinary HTTP
    submit operation allocates the idempotent run before Compiler execution.
    """
    authority, service = channel.research_authority, channel.research_service
    headers = getattr(ws, 'request_headers', None) or getattr(getattr(ws, 'request', None), 'headers', {})
    if method == 'chat.send':
        principal = authority.authenticate_ws(headers, 'submit')
        if getattr(channel, 'research_refusal_reason', None):
            raise ResearchError('unavailable', 'Mandatory operator configuration is unavailable; inspection only')
        text = params.get('content', params.get('message', ''))
        if not isinstance(text, str) or not text.strip():
            raise ResearchError('validation', 'A research prompt is required')
        ref = await _result(service.ingest(principal, text, params.get('upload_refs', ()), workspace_id=params.get('workspace_id')))
        return True, {'intake_ref': ref, 'qualified': True}
    # Existing Settings/model-account handlers retain their own semantics after
    # this scope check. Their user_id comes from this server grant, never query.
    settings_methods = {'config.get', 'config.set', 'config.save_all', 'config.validate_model',
                        'models.list', 'models.get', 'models.replace_all', 'models.validate', 'models.upsert', 'models.delete', 'models.references',
                        'model_groups.list', 'model_groups.upsert', 'model_groups.delete', 'session.selection.set',
                        'codex.auth.status', 'codex.auth.login', 'codex.auth.cancel', 'codex.auth.logout', 'codex.models.list',
                        'locale.get_conf', 'locale.set_conf', 'research.preferences.get', 'research.preferences.save'}
    read_methods = {'initialize', 'channel.get', 'history.get', 'history.list_turns', 'session.list', 'session.get_metadata',
                    'session.preview', 'session.plan_status', 'session.archived.list', 'project.info', 'project.list',
                    'project.get_sessions', 'project.pinned_sessions', 'project.git.status', 'project.git.probe'}
    # Native conversation containers are UI state only. They cannot dispatch,
    # replay, restore files, change a project root or authorize research effects.
    ui_methods = {'session.create', 'session.switch', 'session.rename', 'session.pin', 'session.color_set'}
    if method not in settings_methods | read_methods | ui_methods:
        raise ResearchError('auth', 'Native mutation is unavailable in the protected research profile')
    operation = 'settings' if method in settings_methods else 'status'
    principal = authority.authenticate_ws(headers, operation)
    if getattr(channel, 'research_refusal_reason', None) and method not in (
            read_methods | {'config.get', 'locale.get_conf', 'research.preferences.get'}):
        raise ResearchError('unavailable', 'Mandatory operator configuration is unavailable; inspection only')
    setattr(ws, 'authenticated_user_id', principal.account_id)
    if method in {'research.preferences.get', 'research.preferences.save'}:
        preferences = getattr(channel, 'research_preferences', None)
        if preferences is None:
            raise ResearchError('unavailable', 'Native preference storage is unavailable')
        if method.endswith('.get'):
            return True, preferences.get(principal)
        if set(params) != {'scope', 'values'}:
            raise ResearchError('validation', 'Unsupported native preference request')
        return True, preferences.save(principal, params['scope'], params['values'])
    return False, None
