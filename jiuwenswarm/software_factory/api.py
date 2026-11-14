"""Factory HTTP API; uses host authority when mounted in the existing system."""
from __future__ import annotations

import asyncio
import json
import inspect
import ipaddress
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .catalog import STRATA_REPOSITORY
from .contracts import StageFailure
from .engine import FactoryService


class RunOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    jobs: int = Field(default=2, ge=1, le=8)
    prompt_tokens: list[int] = Field(default_factory=lambda: [1], min_length=1, max_length=4096)
    max_new: int = Field(default=1, ge=1, le=256)
    max_context: int = Field(default=256, ge=1, le=32768)
    ple_gguf: str | None = None
    logits_atol: float = Field(default=1e-5, ge=0, le=0.1)
    logits_rtol: float = Field(default=1e-4, ge=0, le=0.1)
    cuda_architectures: str | None = Field(default=None, pattern=r'^[0-9]+(?:-(?:real|virtual))?(?:;[0-9]+(?:-(?:real|virtual))?)*$')
    core_algorithms: list[Literal['router', 'swiglu', 'moe_combine']] | None = Field(default=None, min_length=1, max_length=3)
    reference_backend: Literal['cuda'] = 'cuda'


    @field_validator('prompt_tokens', mode='before')
    @classmethod
    def token_ids(cls, values):
        if not isinstance(values, list):
            raise ValueError('prompt_tokens must be a list of token IDs')
        if any(type(value) is not int or value < 0 or value > 2**31 - 1 for value in values):
            raise ValueError('prompt_tokens must be nonnegative signed-32-bit token IDs')
        return values


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goals: list[str] = Field(default_factory=list, max_length=12)
    repository_url: Literal['https://github.com/niko1221/strata'] = STRATA_REPOSITORY
    revision: str | None = Field(default=None, pattern=r'^[a-fA-F0-9]{40}$')
    model_path: str | None = None
    target_backend: Literal['ascend', 'cpu', 'cuda'] = 'ascend'
    options: RunOptions = Field(default_factory=RunOptions)
    task: dict[str, Any] | None = None
    workflow_path: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+){0,2}$')
    workflow_parameters: dict[str, Any] = Field(default_factory=dict)


def create_router(service: FactoryService, authorize: Callable[[Request, str], Any] | None = None):
    router = APIRouter(prefix='/api/v1/factory', tags=['Software Factory'])

    async def owner(request: Request, action='status'):
        if authorize:
            result = authorize(request, action)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, str):
                return result
            if isinstance(result, dict):
                identity = result.get('account_id') or result.get('owner_id') or result.get('id')
            else:
                identity = getattr(result, 'account_id', None) or getattr(result, 'owner_id', None) or getattr(result, 'id', None)
            if not isinstance(identity, str) or not identity:
                raise HTTPException(403, 'Factory authority did not provide an account identity')
            return identity
        try:
            local = ipaddress.ip_address(request.client.host).is_loopback if request.client else False
        except ValueError:
            local = request.client is not None and request.client.host == 'testclient'
        if not local:
            raise HTTPException(403, 'Unconfigured factory is available only to the local operator')
        origin = request.headers.get('origin')
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme not in {'http', 'https'} or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
                raise HTTPException(403, 'Factory requests require a local same-operator origin')
        return 'local-operator'

    async def owned_run(request, run_id):
        identity = await owner(request)
        try:
            run = service.get(run_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, 'Unknown factory run')
        if run['request'].get('owner_id') != identity:
            raise HTTPException(404, 'Unknown factory run')
        return run

    @router.get('/catalog')
    async def catalog(request: Request):
        await owner(request)
        return service.catalog()

    @router.post('/runs', status_code=202)
    async def create(request: Request, body: RunRequest):
        identity = await owner(request, 'submit')
        value = body.model_dump()
        from .task_contract import compile_goals
        try:
            compile_goals(value)
        except StageFailure as error:
            raise HTTPException(422, {'code': error.code, 'message': str(error)})
        available = service.catalog()['goals']
        if any(goal not in available for goal in value['goals']):
            raise HTTPException(422, {'error': 'Unknown artifact goal', 'available': available})
        if value['model_path'] is not None:
            value['model_path'] = str(Path(value['model_path']).expanduser().resolve())
        value['owner_id'] = identity
        return service.create(value)

    @router.get('/runs')
    async def list_runs(request: Request):
        identity = await owner(request)
        runs = []
        for path in sorted(service.root.glob('*/run.json'), reverse=True):
            try:
                run = service.get(path.parent.name)
                if run['request'].get('owner_id') == identity:
                    runs.append(run)
            except (FileNotFoundError, ValueError):
                continue
        return {'runs': sorted(runs, key=lambda run: run['created_at'], reverse=True)}

    @router.get('/runs/{run_id}')
    async def get_run(request: Request, run_id: str):
        return await owned_run(request, run_id)

    @router.get('/runs/{run_id}/events')
    async def events(request: Request, run_id: str, after: int = 0):
        await owned_run(request, run_id)
        return service.events(run_id, max(after, 0))

    @router.get('/runs/{run_id}/stream')
    async def stream(request: Request, run_id: str, after: int = 0):
        initial = await owned_run(request, run_id)
        async def frames():
            cursor = max(after, 0)
            yield 'event: snapshot\ndata: ' + json.dumps(initial, ensure_ascii=False) + '\n\n'
            while not await request.is_disconnected():
                batch = await asyncio.to_thread(service.wait_events, run_id, cursor, 10)
                for event in batch['events']:
                    cursor = event['sequence']
                    yield f'id: {cursor}\nevent: factory\ndata: ' + json.dumps(event, ensure_ascii=False) + '\n\n'
                if batch['status'] in {'completed', 'blocked', 'failed'} and cursor >= batch['sequence']:
                    break
                if not batch['events']:
                    yield ': keep-alive\n\n'
        return StreamingResponse(frames(), media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @router.get('/runs/{run_id}/artifacts/{artifact_id}')
    async def artifact(request: Request, run_id: str, artifact_id: str):
        await owned_run(request, run_id)
        try:
            path = service.artifact_path(run_id, artifact_id)
        except FileNotFoundError:
            raise HTTPException(404, 'Unknown factory artifact')
        except StageFailure as error:
            raise HTTPException(409, str(error))
        # Serve exact published bytes as an attachment; source previews fetch these
        # bytes and render them literally. Never infer executable HTML/JS types.
        suffix = path.suffix.lower()
        if suffix == '.zip':
            media_type = 'application/zip'
        elif suffix == '.json':
            media_type = 'application/json'
        elif suffix in {'.cpp', '.cc', '.c', '.hpp', '.h', '.cu', '.cuh', '.cmake',
                        '.txt', '.log', '.stdout', '.stderr'}:
            media_type = 'text/plain'
        elif path.name.endswith('.tar.gz'):
            media_type = 'application/gzip'
        else:
            media_type = 'application/octet-stream'
        return FileResponse(path, filename=path.name, media_type=media_type,
                            headers={'X-Content-Type-Options': 'nosniff'})

    return router
