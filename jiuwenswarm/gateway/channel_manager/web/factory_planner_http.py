"""Factory planner over HTTP: plan task requirements into a checked task graph.

Mounted beside the factory runs routes (``/api/factory/planner/*``) and shown on the
web Factory runs page. Planning runs live under FACTORY_PLANNER_ROOT (default
<user workspace>/factory-planner). The model is the web instance's Codex
subscription, the same sign-in its chat uses; reads never call it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from jiuwenswarm.factory import ai_planner, requirements as req, tla_graph
from jiuwenswarm.factory.redact import sanitize

PREFIX = '/api/factory/planner'
MAX_BODY = 64 * 1024
MAX_TEXT = 256 * 1024
ROUND_FILES = {'prompt': 'prompt.txt', 'reply': 'reply.txt'}
CODEX_AUTH_HOSTS = frozenset({'auth.openai.com', 'auth0.openai.com', 'auth.chatgpt.com'})


def _safe_codex_auth_url(url: object) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or (parsed.hostname or '').lower() not in CODEX_AUTH_HOSTS:
        return None
    return url


def _sanitize_codex_payload(payload: dict) -> dict:
    """Keep error/meta strings sanitized while preserving OAuth query params (`state`, `code_challenge`)."""
    auth_url = _safe_codex_auth_url(payload.get('auth_url'))
    cleaned = sanitize(payload)
    if isinstance(cleaned, dict) and auth_url is not None:
        cleaned['auth_url'] = auth_url
    return cleaned


def default_ablation_dir() -> Path:
    return Path(__file__).resolve().parents[4] / 'benchmarks' / 'planner_tlc_ablation'


def _inspect_graph_tla(tla_path: Path, text: str) -> tuple[dict, dict | None]:
    t0 = time.perf_counter()
    parsed_tla = tla_graph.parse_taskgraph_tla(text)
    parse_ms = round((time.perf_counter() - t0) * 1000, 3)
    lines = text.splitlines()
    contract_nodes = (parsed_tla.get('node_contracts') or {}).get('nodes') or []
    plan_nodes = (parsed_tla.get('plan') or {}).get('nodes') or []
    contract_ids = [n.get('node_id') for n in contract_nodes]
    plan_ids = [n.get('node_id') for n in plan_nodes]
    roundtrip_consistent = bool(
        parsed_tla.get('task_id')
        and contract_nodes
        and len(contract_ids) == len(plan_ids)
        and set(contract_ids) == set(plan_ids)
    )
    sections = []
    markers = (
        ('constants', '1. Execution topology & locks', '-- 1.'),
        ('nodespec', '2. NodeSpec contracts', '-- 2.'),
        ('assume', '3. Static ASSUME invariants', '-- 3.'),
        ('spec', '4. Inlined state machine & properties', '-- 4.'),
    )
    for sid, label, token in markers:
        line_no = next((idx + 1 for idx, line in enumerate(lines) if token in line), None)
        if line_no is not None:
            sections.append({'id': sid, 'label': label, 'line': line_no})
    info = {
        'present': True,
        'path': str(tla_path),
        'bytes': len(text.encode('utf-8')),
        'lines': len(lines),
        'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'parse_ms': parse_ms,
        'roundtrip_consistent': roundtrip_consistent,
        'parsed_nodes': len(contract_nodes),
        'preview': '\n'.join(lines[:200]),
        'truncated': len(lines) > 200,
        'sections': sections,
    }
    return info, parsed_tla


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


class FactoryPlannerService:
    def __init__(self, root=None, *, invoke=None, ablation_dir=None):
        self.root = Path(root).resolve() if root else ai_planner.default_root()
        self.invoke = invoke
        self.ablation_dir = Path(ablation_dir).resolve() if ablation_dir else default_ablation_dir()
        self.active: dict[str, asyncio.Task] = {}
        self._ablation_task: asyncio.Task | None = None
        self._ablation_status: dict = {'state': 'idle'}

    def environment(self):
        """Whether this server can prove graphs at all (TLC), shown before anyone starts a run."""
        from jiuwenswarm.factory import tla_check
        try:
            java, jar = tla_check.tools()
            return dict(tlc=True, java=java, tla2tools=str(jar))
        except tla_check.TlaUnavailable as exc:
            return dict(tlc=False, reason=str(exc))

    def requirements(self):
        result = []
        for rid, document in req.shipped().items():
            found = req.problems(document)
            result.append(dict(id=rid, objective=document.get('objective', ''), contract_id=document.get('contract_id'),
                               notes=document.get('notes', []), document=document, problems=found))
        return dict(requirements=result, environment=self.environment())

    def _directory(self, plan_id):
        if not ai_planner.PLAN_ID.fullmatch(plan_id):
            raise HTTPException(404, 'Unknown planning run')
        directory = self.root / plan_id
        if not (directory / 'status.json').is_file():
            raise HTTPException(404, 'Unknown planning run')
        return directory

    def _status(self, plan_id, status):
        # A run that is not executing in this process was interrupted (server restart).
        if status.get('state') in {'pending', 'running'} and plan_id not in self.active:
            return dict(status, state='interrupted', error=status.get('error') or 'The server stopped during planning')
        return status

    def listing(self):
        return dict(runs=[self._status(r['id'], r) | {'id': r['id']} for r in ai_planner.runs(self.root)],
                    busy=sorted(self.active))

    def detail(self, plan_id):
        directory = self._directory(plan_id)
        status = self._status(plan_id, _read_json(directory / 'status.json') or {})
        rounds = []
        for folder in sorted((directory / 'rounds').glob('*'), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            result = _read_json(folder / 'result.json')
            reply = folder / 'reply.txt'
            rounds.append(dict(round=int(folder.name), finished=result is not None, layer=(result or {}).get('layer'),
                               problems=(result or {}).get('problems', []), warnings=(result or {}).get('warnings', []),
                               verification=(result or {}).get('verification'),
                               error=(result or {}).get('error'), nodes=(result or {}).get('nodes'),
                               prompt_chars=(folder / 'prompt.txt').stat().st_size if (folder / 'prompt.txt').is_file() else 0,
                               reply_chars=reply.stat().st_size if reply.is_file() else 0))
        tla_path = directory / 'graph.tla'
        graph_tla_info = None
        parsed_tla = None
        if tla_path.is_file():
            tla_text = tla_path.read_text(encoding='utf-8')
            graph_tla_info, parsed_tla = _inspect_graph_tla(tla_path, tla_text)
        contract = _read_json(directory / 'contract.json')
        verification = _read_json(directory / 'verification.json')
        graph = _read_json(directory / 'graph.json')
        plan = _read_json(directory / 'plan.json') or (parsed_tla['plan'] if parsed_tla else None)
        node_contracts = (
            ((contract or {}).get('extensions') or {}).get('factory.node-contracts')
            or (parsed_tla['node_contracts'] if parsed_tla else None)
        )
        json_outputs = {
            name: str(directory / name)
            for name in ('contract.json', 'plan.json', 'graph.json', 'verification.json', 'task.json', 'ir.json', 'derivation.json')
            if (directory / name).is_file()
        }
        outputs = json_outputs or ({'graph.tla': str(tla_path)} if tla_path.is_file() else {})
        return sanitize(dict(
            id=plan_id, status=status, requirements=_read_json(directory / 'requirements.json'), rounds=rounds,
            graph=graph, plan=plan,
            node_contracts=node_contracts,
            comparison=_read_json(directory / 'comparison.json'), record=_read_json(directory / 'plan-record.json'),
            verification=verification,
            selection=_read_json(directory / 'selection.json'),
            ir=_read_json(directory / 'ir.json') or next(
                (_read_json(f / 'ir.json') for f in sorted((directory / 'rounds').glob('*'), reverse=True)
                 if (f / 'ir.json').is_file()), None),
            derivation=_read_json(directory / 'derivation.json'),
            graph_tla_info=graph_tla_info,
            outputs=outputs))

    def graph_tla(self, plan_id):
        tla_path = self._directory(plan_id) / 'graph.tla'
        if not tla_path.is_file():
            raise HTTPException(404, 'graph.tla not recorded')
        return tla_path.read_text(encoding='utf-8')

    def graph_json(self, plan_id):
        directory = self._directory(plan_id)
        status = _read_json(directory / 'status.json') or {}
        verification = _read_json(directory / 'verification.json') or {}
        graph_path = directory / 'graph.json'
        if status.get('state') != 'succeeded' or not verification.get('passed') or not graph_path.is_file():
            raise HTTPException(404, 'Verified graph.json not available')
        return graph_path.read_text(encoding='utf-8')

    def round_file(self, plan_id, number, name):
        if name not in ROUND_FILES:
            raise HTTPException(404, 'Unknown round file')
        path = self._directory(plan_id) / 'rounds' / str(number) / ROUND_FILES[name]
        if not path.is_file():
            raise HTTPException(404, 'Round file not recorded')
        text = path.read_text(encoding='utf-8', errors='replace')
        return dict(text=sanitize(text[:MAX_TEXT]), truncated=len(text) > MAX_TEXT, size=len(text))

    def ablation(self):
        results_path = self.ablation_dir / 'results.json'
        results = _read_json(results_path) if results_path.is_file() else None
        running = bool(self._ablation_task and not self._ablation_task.done())
        return sanitize({
            'available': results is not None,
            'report_available': (self.ablation_dir / 'report.html').is_file(),
            'running': running,
            'run_state': dict(self._ablation_status),
            'environment': self.environment(),
            'results': results,
        })

    def ablation_report_html(self):
        report_path = self.ablation_dir / 'report.html'
        if not report_path.is_file():
            raise HTTPException(404, 'Ablation HTML report not generated yet')
        return report_path.read_text(encoding='utf-8')

    def start_ablation(self):
        environment = self.environment()
        if not environment['tlc']:
            raise HTTPException(503, 'TLC is unavailable, so the ablation benchmark cannot run: ' + environment['reason'])
        if self._ablation_task and not self._ablation_task.done():
            raise HTTPException(409, 'An ablation benchmark run is already in progress')

        repo_root = str(Path(__file__).resolve().parents[4])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        self._ablation_status = {
            'state': 'running',
            'started': time.time(),
            'finished': None,
            'error': None,
        }

        def _execute():
            from benchmarks.planner_tlc_ablation.report_gen import generate_html
            from benchmarks.planner_tlc_ablation.run_ablation import run_all
            self.ablation_dir.mkdir(parents=True, exist_ok=True)
            payload = run_all(self.ablation_dir)
            generate_html(payload, self.ablation_dir / 'report.html')
            return payload

        async def go():
            try:
                payload = await run_in_threadpool(_execute)
                self._ablation_status = {
                    'state': 'succeeded',
                    'started': self._ablation_status.get('started'),
                    'finished': time.time(),
                    'error': None,
                    'generated_at': payload.get('generated_at'),
                }
            except Exception as exc:
                self._ablation_status = {
                    'state': 'failed',
                    'started': self._ablation_status.get('started'),
                    'finished': time.time(),
                    'error': sanitize(str(exc))[:400],
                }
            finally:
                self._ablation_task = None

        self._ablation_task = asyncio.get_running_loop().create_task(go())
        return {'status': dict(self._ablation_status)}

    def start(self, payload):
        if not isinstance(payload, dict) or len(payload) != 1 or not ({'requirements_id', 'requirements'} & set(payload)):
            raise HTTPException(400, 'Expected requirements_id or requirements')
        if 'requirements_id' in payload:
            document = req.shipped().get(payload['requirements_id'])
            if document is None:
                raise HTTPException(404, 'Unknown requirements')
        else:
            document = payload['requirements']
        found = req.problems(document)
        if found:
            raise HTTPException(422, dict(message='Invalid requirements', problems=found[:20]))
        if self.active:
            raise HTTPException(409, 'A planning run is already in progress')
        environment = self.environment()
        if not environment['tlc']:
            raise HTTPException(503, 'TLC is unavailable, so no graph can be proven: ' + environment['reason'])
        plan_id = ai_planner.new_plan_id()
        directory = self.root / plan_id
        directory.mkdir(parents=True, exist_ok=False)
        ai_planner.PlanningRun(directory).update(state='pending', requirements_id=req.input_id(document))

        async def go():
            try:
                await ai_planner.synthesize(document, directory, invoke=self.invoke)
            except Exception as exc:  # never leave a run that claims to be running
                ai_planner.PlanningRun(directory).update(state='failed', error=sanitize(str(exc))[:400])
            finally:
                self.active.pop(plan_id, None)
        self.active[plan_id] = asyncio.get_running_loop().create_task(go())
        return dict(id=plan_id)


def attach_planner_routes(app: FastAPI, *, service=None):
    service = service or FactoryPlannerService()

    async def call(method, *args):
        try:
            return await run_in_threadpool(method, *args)
        except HTTPException:
            raise
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(422, sanitize(str(exc))[:200]) from None

    def check_origin(request: Request):
        origin = request.headers.get('origin')
        if not origin:
            return
        parsed = urlsplit(origin)
        host = request.headers.get('x-forwarded-host') or request.headers.get('host') or ''
        if parsed.netloc == host:
            return
        # Allow local Vite/browser dev-proxy loopback origins talking to a loopback backend
        origin_host = (parsed.hostname or '').lower()
        server_host = host.split(':', 1)[0].strip('[]').lower()
        loopback = {'127.0.0.1', 'localhost', '::1'}
        if origin_host in loopback and (server_host in loopback or not server_host):
            return
        raise HTTPException(403, 'Planning requires a same-origin request')

    async def read_json_body(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                raise HTTPException(413, 'Planning request exceeds limit')
        try:
            return json.loads(body)
        except ValueError:
            raise HTTPException(400, 'Expected a JSON planning request') from None

    @app.get(PREFIX + '/codex/status')
    async def codex_status():
        from jiuwenswarm.server.runtime.codex_subscription.service import get_service
        try:
            return _sanitize_codex_payload(await get_service().status())
        except Exception as exc:
            return sanitize({'enabled': False, 'state': 'unavailable', 'error': str(exc)[:300]})

    @app.post(PREFIX + '/codex/login')
    async def codex_login(request: Request):
        check_origin(request)
        payload = {}
        try:
            raw = await request.body()
            if raw and raw.strip():
                payload = json.loads(raw)
        except ValueError:
            raise HTTPException(400, 'Expected a JSON login payload') from None
        raw_device = payload.get('device_code') if isinstance(payload, dict) else None
        if raw_device is not None and not isinstance(raw_device, bool):
            raise HTTPException(400, 'device_code must be a boolean')
        device_arg = raw_device
        from jiuwenswarm.server.runtime.codex_subscription.service import get_service
        from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
        svc = get_service()
        try:
            return _sanitize_codex_payload(await svc.login(device_code=device_arg))
        except CodexError as exc:
            code = str(exc)
            if code == 'LOGIN_PENDING':
                pending = await svc.status()
                if (
                    device_arg is not None
                    and pending.get('login_attempt_id')
                    and bool(pending.get('user_code')) != device_arg
                ):
                    await svc.cancel_login(pending['login_attempt_id'])
                    return _sanitize_codex_payload(await svc.login(device_code=device_arg))
                return _sanitize_codex_payload(pending)
            status_code = 409 if code in {'BUSY', 'PROFILE_IN_USE'} else 503 if 'CLI' in code or 'START' in code else 422
            raise HTTPException(status_code, sanitize(code)[:300]) from None
        except OSError as exc:
            raise HTTPException(503, sanitize(str(exc))[:300]) from None

    @app.post(PREFIX + '/codex/cancel')
    async def codex_cancel(request: Request):
        check_origin(request)
        payload = await read_json_body(request)
        from jiuwenswarm.server.runtime.codex_subscription.service import get_service
        from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
        try:
            return _sanitize_codex_payload(await get_service().cancel_login(payload.get('login_attempt_id')))
        except CodexError as exc:
            raise HTTPException(409, sanitize(str(exc))[:300]) from None

    @app.post(PREFIX + '/codex/logout')
    async def codex_logout(request: Request):
        check_origin(request)
        from jiuwenswarm.server.runtime.codex_subscription.service import get_service
        from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
        try:
            return _sanitize_codex_payload(await get_service().logout())
        except CodexError as exc:
            raise HTTPException(409, sanitize(str(exc))[:300]) from None

    @app.get(PREFIX + '/requirements')
    async def requirements():
        return await call(service.requirements)

    @app.get(PREFIX + '/ablation')
    async def ablation():
        return await call(service.ablation)

    @app.get(PREFIX + '/ablation/report.html')
    async def ablation_report_html():
        html = await call(service.ablation_report_html)
        return Response(content=html, media_type='text/html; charset=utf-8')

    @app.post(PREFIX + '/ablation/run', status_code=202)
    async def ablation_run(request: Request):
        check_origin(request)
        return service.start_ablation()

    @app.get(PREFIX + '/runs')
    async def runs():
        return await call(service.listing)

    @app.get(PREFIX + '/runs/{plan_id}')
    async def detail(plan_id: str):
        return await call(service.detail, plan_id)

    @app.get(PREFIX + '/runs/{plan_id}/graph.tla')
    async def graph_tla(plan_id: str):
        text = await call(service.graph_tla, plan_id)
        return Response(
            content=text,
            media_type='text/plain; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename="graph.tla"'},
        )

    @app.get(PREFIX + '/runs/{plan_id}/graph.json')
    async def graph_json(plan_id: str):
        text = await call(service.graph_json, plan_id)
        return Response(
            content=text,
            media_type='application/json; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename="graph.json"'},
        )

    @app.get(PREFIX + '/runs/{plan_id}/rounds/{number}/{name}')
    async def round_file(plan_id: str, number: int, name: str):
        return await call(service.round_file, plan_id, number, name)

    @app.post(PREFIX + '/runs', status_code=202)
    async def start(request: Request):
        check_origin(request)
        payload = await read_json_body(request)
        return service.start(payload)  # on the event loop: the run is an asyncio task

    return service
