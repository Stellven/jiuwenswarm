"""Serve the R8 engine viewer on the Spark Tailscale address."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, _inside, attach_factory_routes

TAILSCALE_HOST = '100.105.127.48'
TAILSCALE_PORT = 5173
LIVE_TASK = 'muse-2bit-demo-r8'
HISTORY_TASK = 'muse-2bit-ttft-v4'
IDENTIFIER = r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}'
RUN = r'/api/factory/runs/[a-f0-9]{24}'
NODE = rf'{RUN}/nodes/{IDENTIFIER}'
FACTORY_READ = re.compile(
    rf'(?:/api/factory/(?:runs|engine-bench)'
    rf'|{RUN}(?:/(?:state|session|story|file))?|{NODE}(?:/(?:diff|material))?)'
)
STATIC_READ = re.compile(r'/(?:index\.html|logo\.svg|favicon\.ico|assets/[A-Za-z0-9_.-]+)?')


class EngineRuns(FactoryHttpService):
    def __init__(self, live, history, replay):
        super().__init__(
            roots=[live, history, replay], historical_roots=[history, replay],
            launch_root=False, launch_home_root=False,
        )
        self.live, self.history, self.replay = live, history, replay

    def catalog(self):
        return [
            (item, path) for item, path in super().catalog()
            if (path == self.live and item['task_id'] == LIVE_TASK and item['kind'] == 'live')
            or (path == self.history and item['task_id'] == HISTORY_TASK and item['kind'] == 'live')
            or (path == self.replay and item['task_id'] == LIVE_TASK and item.get('demo') is True)
        ]

    def detail(self, run_id):
        result = super().detail(run_id)
        item, path = self.resolve(run_id)
        result['engine_log'] = session_log(path, item, result)
        trace = result.get('telemetry') or []
        result['telemetry'] = [row for row in trace if isinstance(row, dict) and row.get('node_id')]
        return result


def session_log(path, run, detail):
    """Agent turn boundaries and factory-owned node jobs from this run only."""
    events = []
    task = run['task_id']
    relative = 'session.jsonl' if run['kind'] == 'bundle' else f'sessions/{task}.jsonl'
    transcript = _inside(path, relative)
    if transcript.is_file():
        with transcript.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                if not line.endswith('\n'):
                    break  # The active agent may still be writing the line.
                row = json.loads(line)
                kind = row.get('event') or row.get('event_type')
                turn = row.get('turn')
                if kind not in {'turn.start', 'turn.end'} or not isinstance(turn, int):
                    continue
                verb = 'started' if kind == 'turn.start' else 'ended'
                events.append(dict(id=f'{relative}:{number}', created=row.get('t') or 0,
                                   kind='agent turn', summary=f'Turn {turn} {verb}', mark='·'))

    for attempt in detail['records'].get('attempts', []):
        node = (attempt.get('request') or {}).get('node_id')
        if not node or attempt.get('task_id') != task:
            continue
        for index, transition in enumerate(attempt.get('history') or []):
            state = transition.get('state')
            mark = '✓' if state == 'succeeded' else '✗' if state in {'failed', 'cancelled'} else '·'
            events.append(dict(id=f"{attempt['attempt_id']}:{index}", created=transition.get('created') or 0,
                               kind='capped run', summary=f"{node} · {attempt['kind']} · {state}", mark=mark))
    events.sort(key=lambda event: event['created'])
    return [dict(event, cursor=i) for i, event in enumerate(events, 1)]


class ViewerBoundary:
    """Authorize before any native route or filesystem handler is reached."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 1008})
            return
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        path = scope['path']
        method = scope['method']
        allowed = (
            (method == 'GET' and FACTORY_READ.fullmatch(path))
            or (method in {'GET', 'HEAD'} and STATIC_READ.fullmatch(path))
        )
        if allowed:
            await self.app(scope, receive, send)
            return
        await JSONResponse(
            {'detail': 'This listener serves read-only engine evidence.'},
            status_code=403,
        )(scope, receive, send)


def make_app(dist, live, history, replay):
    dist, live, history, replay = (Path(path).expanduser().resolve() for path in (dist, live, history, replay))
    if not (dist / 'index.html').is_file():
        raise ValueError(f'Engine web build is missing: {dist / "index.html"}')
    for path in (live, history):
        if not (path / 'factory.sqlite').is_file():
            raise ValueError(f'Factory home is missing its database: {path}')

    service = EngineRuns(live, history, replay)
    app = FastAPI(openapi_url=None)
    attach_factory_routes(app, service=service)
    app.mount('/', StaticFiles(directory=dist, html=True), name='engine-frontend')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[TAILSCALE_HOST])
    app.add_middleware(ViewerBoundary)
    return app


def main(argv=None):
    muse = Path.home() / 'muse-demo'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--live', type=Path, default=muse / 'graph-r8')
    parser.add_argument('--history', type=Path, default=muse / 'graph-v4')
    parser.add_argument('--replay', type=Path, required=True, help='Exact R8 curated replay bundle directory.')
    args = parser.parse_args(argv)
    try:
        app = make_app(args.dist, args.live, args.history, args.replay)
    except ValueError as exc:
        parser.error(str(exc))
    # The redacting log record factory consumes formatting arguments before Uvicorn's access formatter.
    uvicorn.run(app, host=TAILSCALE_HOST, port=TAILSCALE_PORT, proxy_headers=False,
                access_log=False, ws='none')


if __name__ == '__main__':
    main()
