"""Local operator API for a task-scoped native workflow process."""
import asyncio
import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from .cc_workflow import WorkflowConflict
from .contracts import StageFailure


def create_cc_router(service):
    router = APIRouter(prefix='/api/v1/cc-workflows', tags=['CC workflows'])

    def local(request):
        try:
            allowed = request.client is not None and (
                request.client.host == 'testclient' or ipaddress.ip_address(request.client.host).is_loopback)
        except ValueError:
            allowed = False
        origin = request.headers.get('origin')
        if not allowed or (origin and urlparse(origin).hostname not in {'localhost', '127.0.0.1', '::1'}):
            raise HTTPException(403, 'Native workflows require the local operator connection')
        if service is None:
            raise HTTPException(503, 'Configure a task-scoped CC workflow service first')

    async def invoke(request, operation, *args):
        local(request)
        try:
            return await asyncio.to_thread(operation, *args)
        except KeyError as error:
            raise HTTPException(404, 'Unknown run or workflow input') from error
        except WorkflowConflict as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, StageFailure) as error:
            raise HTTPException(422, str(error)) from error

    @router.get('/catalog')
    async def catalog(request: Request):
        local(request)
        return service.catalog()

    @router.get('/schema')
    async def schema(request: Request):
        local(request)
        import json
        from pathlib import Path
        return json.loads(Path(__file__).with_name('shared-capability.schema.json').read_text())

    @router.post('/runs', status_code=202)
    async def create(request: Request, body: dict):
        local(request)
        return await invoke(request, service.create, body)

    @router.get('/runs/{run_id}')
    async def get(request: Request, run_id: str):
        local(request)
        return await invoke(request, service.get, run_id)

    @router.get('/runs/{run_id}/events')
    async def events(request: Request, run_id: str, after: int = 0):
        local(request)
        return await invoke(request, service.runtime.events, run_id, max(after, 0))

    @router.post('/runs/{run_id}/tick')
    async def tick(request: Request, run_id: str):
        local(request)
        return await invoke(request, service.tick, run_id)

    @router.post('/runs/{run_id}/stop')
    async def stop(request: Request, run_id: str):
        local(request)
        return await invoke(request, service.stop, run_id)

    @router.post('/runs/{run_id}/revisions')
    async def append(request: Request, run_id: str, body: dict):
        local(request)
        return await invoke(request, service.append, run_id, body)

    return router
