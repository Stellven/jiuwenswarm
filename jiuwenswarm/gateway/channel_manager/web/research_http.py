"""Authenticated native M1 HTTP boundary; all research work stays in ResearchService."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import secrets
from types import SimpleNamespace

from fastapi import Request
from fastapi.responses import JSONResponse, Response, FileResponse

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
            input_operation = operation in {'upload', 'list_uploads', 'delete_upload'} and service.upload_manager is not None
            if getattr(channel, 'research_refusal_reason', None) and not input_operation and operation not in {
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
            response = JSONResponse({'token': grant['token'], 'defaults': defaults,
                                     'reusable_bootstrap': authority.reusable_bootstrap})
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
        async def capabilities(principal):
            value = dict(await _result(service.readiness(principal)))
            if hasattr(service, 'ingest'):
                operations = list(value.get('operations', []))
                operations += ['context', 'events', 'artifacts', 'download_artifact', 'confirm_collection']
                if value.get('ready'): operations.append('prepare_intake')
                if service.upload_manager is not None: operations.append('upload')
                value['operations'] = list(dict.fromkeys(operations))
            return value
        return await invoke(request, 'readiness', capabilities)

    @app.get('/api/v1/context')
    async def client_context(request: Request):
        return await invoke(request, 'status', lambda p: {'schema_version': '1.0.0', 'defaults': service.client_defaults(p)})

    @app.post('/api/v1/intakes')
    async def prepare_intake(request: Request):
        try:
            authority.authenticate(request.headers.get('authorization'), 'submit')
            value = _evaluation_json(await request.body())
            if (set(value) != {'task', 'upload_refs', 'workspace_id'} or not isinstance(value['task'], str)
                    or not value['task'].strip() or not isinstance(value['upload_refs'], list)
                    or any(not isinstance(ref, str) for ref in value['upload_refs'])
                    or value['workspace_id'] is not None and not isinstance(value['workspace_id'], str)):
                raise ResearchError('validation')
        except ResearchError as exc: return _error(exc)
        async def capture(principal):
            workspace, protected = service._workspace(principal, value['workspace_id'])
            defaults = {'schema_version': '1.0.0', 'id': 'submission:' + secrets.token_hex(16),
                'account_id': principal.account_id, 'workspace_id': workspace,
                'configuration_ref': protected['configuration_ref'], 'plan_source': protected.get('plan_source', 'static'),
                'profile_id': protected.get('profile_id'), 'interaction_mode': 'headless'}
            # Qualification is identical to authenticated browser intake, without
            # creating or mutating an ordinary conversation/session.
            ref = await service.ingest(principal, value['task'], value['upload_refs'], workspace_id=workspace)
            return {'schema_version': '1.0.0', 'intake_ref': ref, 'qualified': True,
                    'workspace_id': workspace, 'submission_defaults': defaults}
        # Evaluation grants retain their exact submission policy; this ordinary
        # intake path cannot manufacture an evaluation campaign binding.
        return await invoke(request, 'submit', capture, workspace_id=value['workspace_id'], submission={})

    @app.get('/api/v1/runs/{run_id}/events')
    async def events(request: Request, run_id: str):
        from jiuwenswarm.research.workflow_inspection import run_timeline
        try:
            after = int(request.query_params.get('after', '0'))
            if after < 0: raise ValueError()
        except ValueError: return _error(ResearchError('validation'), run_id=run_id)
        def observed(principal):
            value = run_timeline(service, principal, run_id)
            rows = value['events']
            return {'schema_version': '1.0.0', 'run_id': run_id, 'revision': value['revision'],
                    'events': rows[after:after + 1000], 'next_after': min(len(rows), after + 1000),
                    'sampling': {'scope': 'owned_run_captured_workflow_events', 'contention': 'unknown'},
                    'metrics': {'cpu': None, 'memory': None, 'disk': None, 'gpu': None,
                                'model_usage': None},
                    'unavailable_metrics': ['cpu', 'memory', 'disk', 'gpu', 'model_usage']}
        return await invoke(request, 'status', observed, run_id=run_id)

    @app.get('/api/v1/runs/{run_id}/artifacts')
    async def artifact_list(request: Request, run_id: str):
        from jiuwenswarm.research.collection import snapshot
        audience = request.query_params.get('audience', 'researcher')
        return await invoke(request, 'export', lambda p: asyncio.to_thread(snapshot, service, p, run_id, audience), run_id=run_id)

    @app.get('/api/v1/runs/{run_id}/artifacts/{artifact_id}')
    async def artifact_download(request: Request, run_id: str, artifact_id: str):
        from jiuwenswarm.research.collection import artifact_path
        try:
            audience = request.query_params.get('audience', 'researcher')
            principal = authority.authenticate(request.headers.get('authorization'), 'export', audience=audience)
            authority.authorize_evaluation(request.headers.get('authorization'), 'export', run_id=run_id)
            path, item = await asyncio.to_thread(artifact_path, service, principal, run_id, artifact_id, audience)
            return FileResponse(path, media_type='application/octet-stream', headers={
                'Cache-Control': 'private, no-store', 'X-Content-SHA256': item['sha256'],
                'Content-Length': str(item['size'])})
        except ResearchError as exc: return _error(exc, run_id=run_id)
        except Exception: return _error(ResearchError('internal'), run_id=run_id)

    @app.post('/api/v1/runs/{run_id}/collection-confirmation')
    async def collection_confirmation(request: Request, run_id: str):
        from jiuwenswarm.research.collection import confirm
        try:
            authority.authenticate(request.headers.get('authorization'), 'export')
            value = _evaluation_json(await request.body())
        except ResearchError as exc: return _error(exc, run_id=run_id)
        return await invoke(request, 'export', lambda p: asyncio.to_thread(confirm, service, p, run_id, value), run_id=run_id)

    @app.get('/api/v1/workflow/runtime')
    async def workflow_runtime(request: Request):
        from jiuwenswarm.research.workflow_inspection import runtime_snapshot
        return await invoke(request, 'status', lambda p: runtime_snapshot(channel, p))

    @app.get('/api/v1/runs/{run_id}/timeline')
    async def workflow_timeline(request: Request, run_id: str):
        from jiuwenswarm.research.workflow_inspection import run_timeline
        return await invoke(request, 'status', lambda p: run_timeline(service, p, run_id), run_id=run_id)

    @app.get('/api/v1/workflow/example')
    async def research_example(request: Request):
        from jiuwenswarm.research.workflow_inspection import workflow_example
        return await invoke(request, 'status', lambda p: workflow_example(service, p))

    @app.get('/api/v1/runs/{run_id}/continuation')
    async def workflow_continuation(request: Request, run_id: str):
        from jiuwenswarm.research.planning import research_continuation
        def inspect(principal):
            run = service.store.get_run(run_id, account_id=principal.account_id)
            principal.require('status', run['workspace_id'])
            return research_continuation(service.store, run_id)
        return await invoke(request, 'status', inspect, run_id=run_id)

    @app.get('/api/v1/runs/{run_id}/result')
    async def workflow_result(request: Request, run_id: str):
        from jiuwenswarm.research.workflow_inspection import run_result
        return await invoke(request, 'export', lambda p: run_result(service, p, run_id), run_id=run_id)

    @app.get('/api/v1/sessions/{session_id}/research')
    async def native_session_history(request: Request, session_id: str):
        from jiuwenswarm.research.local_chat import native_session_research
        async def owned_history(principal):
            workspace_id = request.query_params.get('workspace_id')
            if workspace_id is None:
                if len(principal.workspace_ids) != 1:
                    raise ResearchError('validation', 'Select one authorized conversation workspace')
                workspace_id = next(iter(principal.workspace_ids))
            return await native_session_research(service, principal, session_id, workspace_id=workspace_id)
        return await invoke(request, 'status', owned_history)

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
        async def native_submit(principal):
            status = await service.submit(principal, value)
            from jiuwenswarm.research.local_chat import attach_native_research_run
            await attach_native_research_run(service, principal, status['run_id'])
            return status
        return await invoke(request, 'submit', native_submit, workspace_id=value.get('workspace_id'), submission=value)

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
                from jiuwenswarm.research.runner import _capture_off_loop
                archive = await _capture_off_loop(encode_export_zip, manifest, contents)
                return Response(archive, media_type='application/zip',
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
            async with request.form() as form:
                if set(form) != {'file', 'scope_id'} or not hasattr(form['file'], 'read'):
                    raise ResearchError('validation')
                file = form['file']
                limit = service.upload_manager.max_bytes if service.upload_manager is not None else None
                data = await file.read(limit + 1) if limit is not None else await file.read()
                return await _result(service.upload(p, kind, str(form['scope_id']), file.filename, data))
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
    if method in {'rsi.cc.snapshot', 'rsi.cc.candidate.get', 'rsi.cc.run.start', 'rsi.cc.operator.action', 'rsi.cc.targets.list'}:
        principal = authority.authenticate_ws(headers, 'status')
        workspace = getattr(channel, 'research_cc_workspace', None)
        publication = os.environ.get('JIUWENSWARM_CC_RSI_PUBLICATION')
        if publication and (publication != '/run/ai4r-rsi-ui/publication.json' or not workspace
                            or os.environ.get('JIUWENSWARM_CC_RSI_WORKSPACE') != workspace):
            raise ResearchError('unavailable', 'The public CC publication differs from the startup workspace')
        if workspace is not None and workspace not in principal.workspace_ids:
            raise ResearchError('auth', 'The native session cannot access the startup CC workspace', {'http_status': 403})
    if method == 'rsi.cc.targets.list':
        if not isinstance(params, dict) or params:
            raise ResearchError('validation', 'The Source target catalog accepts no parameters')
        if not workspace:
            raise ResearchError('unavailable', 'The startup workspace is not configured')
        from jiuwenswarm.research_rsi.targets.capsules import capsule_catalog
        targets = capsule_catalog()
        capsules = getattr(channel, 'research_cc_capsules', None)
        readiness = await _result(capsules.readiness(headers)) if capsules is not None else {}
        # Source availability is not Library admission or a protected execution grant.
        return True, {'schema_version': '1', 'workspace_id': workspace, 'targets': [
            dict(row, target_id=row['capsule_name'],
                 development_grant_status=('READY' if readiness[row['capsule_name']]['run']['allowed'] else 'BLOCKED')
                    if row['capsule_name'] in readiness else 'NOT_ESTABLISHED',
                 revision=readiness.get(row['capsule_name'], {}).get('revision'),
                 run_id=readiness.get(row['capsule_name'], {}).get('run_id'),
                 run=readiness.get(row['capsule_name'], {}).get('run', {
                     'allowed': False, 'blocker': row.get('blocker') or 'No prepared Root development slot is installed'}))
            for row in targets]}
    if method in {'rsi.cc.snapshot', 'rsi.cc.candidate.get'}:
        principal = authority.authenticate_ws(headers, 'status')
        # Inspection stays available while native execution readiness is blocked.
        # The dedicated AgentServer projection cannot read private Root runtime.
        setattr(ws, 'authenticated_user_id', principal.account_id)
        operator = getattr(channel, 'research_cc_operator', None)
        development = getattr(channel, 'research_cc_development', None)
        if method == 'rsi.cc.snapshot' and development is not None:
            base = await _result(operator.snapshot(headers, params)) if operator is not None and callable(getattr(operator, 'snapshot', None)) else None
            view = await _result(development.snapshot(headers, params, base=base))
            capsules = getattr(channel, 'research_cc_capsules', None)
            if capsules is not None:
                view = await _result(capsules.snapshot(headers, params, base=view))
            return True, view
        if method == 'rsi.cc.snapshot' and operator is not None and callable(getattr(operator, 'snapshot', None)):
            view = await _result(operator.snapshot(headers, params))
            capsules = getattr(channel, 'research_cc_capsules', None)
            if capsules is not None:
                view = await _result(capsules.snapshot(headers, params, base=view))
            return True, view
        return False, None
    if method == 'rsi.cc.run.start':
        authority.authenticate_ws(headers, 'status')
        capsules = getattr(channel, 'research_cc_capsules', None)
        if capsules is not None and isinstance(params, dict) and capsules.owns(params.get('target_id')):
            return True, await _result(capsules.execute(headers, params))
        development = getattr(channel, 'research_cc_development', None)
        if development is None:
            raise ResearchError('unavailable', 'The fixed development run broker is not installed')
        return True, await _result(development.execute(headers, params))
    if method == 'rsi.cc.operator.action':
        authority.authenticate_ws(headers, 'status')
        operator = getattr(channel, 'research_cc_operator', None)
        if operator is None:
            raise ResearchError('unavailable', 'Authenticated finite CC operator/run broker is not installed')
        # The installed adapter reauthenticates the actual native session and
        # signs an exact action assertion. Browser user_id/proof fields are not
        # forwarded as authority. Ordinary app roles gain no Library operation.
        return True, await _result(operator.execute(headers, params))
    if method == 'codex.chat':
        from jiuwenswarm.research.local_chat import enabled, conversation_document_context
        principal = authority.authenticate_ws(headers, 'submit')
        if not enabled():
            raise ResearchError('unavailable', 'Local subscription chat is not enabled')
        workspace_id = params.get('workspace_id')
        if workspace_id is None:
            if len(principal.workspace_ids) != 1:
                raise ResearchError('validation', 'Select one authorized workspace for this conversation')
            workspace_id = next(iter(principal.workspace_ids))
        params['_local_documents'] = await asyncio.to_thread(conversation_document_context,
            service.store, principal, params.get('session_id'), params.get('upload_refs', []), workspace_id=workspace_id)
        setattr(ws, 'authenticated_user_id', principal.account_id)
        return False, None
    if method == 'chat.send':
        principal = authority.authenticate_ws(headers, 'submit')
        if getattr(channel, 'research_refusal_reason', None):
            raise ResearchError('unavailable', 'Mandatory operator configuration is unavailable; inspection only')
        text = params.get('content', params.get('message', ''))
        if not isinstance(text, str) or not text.strip():
            raise ResearchError('validation', 'A research prompt is required')
        from jiuwenswarm.research.local_chat import conversation_upload_refs
        workspace_id, _ = service._workspace(principal, params.get('workspace_id'))
        upload_refs = await asyncio.to_thread(conversation_upload_refs,
            service.store, principal, params.get('session_id'), params.get('upload_refs', ()), workspace_id=workspace_id)
        ref = await _result(service.ingest(principal, text, upload_refs, workspace_id=workspace_id))
        from jiuwenswarm.research.local_chat import capture_conversation_intake
        await asyncio.to_thread(capture_conversation_intake, service.store, principal,
            params.get('session_id'), ref, workspace_id=workspace_id)
        return True, {'intake_ref': ref, 'qualified': True}
    # Existing Settings/model-account handlers retain their own semantics after
    # this scope check. Their user_id comes from this server grant, never query.
    settings_methods = {'config.get', 'config.set', 'config.save_all', 'config.validate_model',
                        'models.list', 'models.get', 'models.replace_all', 'models.validate', 'models.upsert', 'models.delete', 'models.references',
                        'model_groups.list', 'model_groups.upsert', 'model_groups.delete', 'session.selection.set',
                        'codex.auth.status', 'codex.auth.login', 'codex.auth.cancel', 'codex.auth.logout', 'codex.models.list',
                        'locale.get_conf', 'locale.set_conf', 'research.preferences.get', 'research.preferences.save',
                        'research.models.get','research.models.save','research.models.select','research.models.remove'}
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
    if method in {'locale.get_conf', 'locale.set_conf'}:
        preferences = getattr(channel, 'research_preferences', None)
        if preferences is None:
            raise ResearchError('unavailable', 'Native preference storage is unavailable')
        if method == 'locale.set_conf':
            if set(params) != {'preferred_language'} or params['preferred_language'] not in ('zh', 'en'):
                raise ResearchError('validation', 'preferred_language must be zh or en')
            language = preferences.locale(principal, params['preferred_language'])
        else:
            if params:
                raise ResearchError('validation', 'Unsupported language preference request')
            language = preferences.locale(principal)
        setattr(ws, 'authenticated_user_id', principal.account_id)
        # Preserve the existing native configured default until explicitly set.
        return (True, {'preferred_language': language}) if language is not None else (False, None)
    local_ui_methods = ui_methods if os.environ.get('JIUWENSWARM_M1_LOCAL_CHAT') == '1' else set()
    if getattr(channel, 'research_refusal_reason', None) and method not in (
            read_methods | local_ui_methods | {'config.get', 'locale.get_conf', 'research.preferences.get',
                            'codex.auth.status', 'codex.auth.login', 'codex.auth.cancel',
                            'codex.auth.logout', 'codex.models.list'}):
        raise ResearchError('unavailable', 'Mandatory operator configuration is unavailable; inspection only')
    setattr(ws, 'authenticated_user_id', principal.account_id)
    if method.startswith('research.models.'):
        model_settings=getattr(service,'model_settings',None)
        if model_settings is None:
            raise ResearchError('unavailable','Model settings are unavailable')
        return True, await _result(model_settings(principal,method.rsplit('.',1)[1],params))
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
