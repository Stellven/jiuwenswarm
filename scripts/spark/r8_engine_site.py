"""Serve the JiuwenSwarm web app and its read-only factory evidence on the tailnet."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from jiuwenswarm.gateway.channel_manager.base import RobotMessageRouter
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, _inside
from jiuwenswarm.gateway.channel_manager.web.web_channel_app import build_web_channel_app
from jiuwenswarm.gateway.channel_manager.web.web_connect import WebChannel, WebChannelConfig

TAILSCALE_HOST = '100.105.127.48'
TAILSCALE_DNS = 'gx10-004d.tailbe236a.ts.net'
TAILSCALE_PORT = 5173
LIVE_TASK = 'muse-2bit-demo-r8'
HISTORY_TASK = 'muse-2bit-ttft-v4'
IDENTIFIER = r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}'
RUN = r'/api/factory/runs/[a-f0-9]{24}'
NODE = rf'{RUN}/nodes/{IDENTIFIER}'
CAPSULE = rf'/api/factory/capsules(?:/{IDENTIFIER}(?:/file)?)?'
PREFIX_FIXTURE = r'/api/factory/capsules/kv_reuse_lab/fixture(?:/(?:summary|stock|configured))?'
FACTORY_READ = re.compile(
    rf'(?:/api/factory/(?:runs|headlines|engine-bench(?:/(?:readme|method-history))?)'
    rf'|{RUN}(?:/(?:state|session|story|file))?|{NODE}(?:/(?:diff|material))?|{CAPSULE}|{PREFIX_FIXTURE})'
)
STATIC_READ = re.compile(r'/(?:index\.html|logo\.(?:svg|ico)|favicon\.ico|assets/[A-Za-z0-9_.-]+)?')


class EngineRuns(FactoryHttpService):
    def __init__(self, live, history, replay, second_replay=None, extra_roots=()):
        self.demo_roots = {replay}
        if second_replay:
            self.demo_roots.add(second_replay)
        roots = tuple(dict.fromkeys((live, history, *sorted(self.demo_roots), *extra_roots)))
        super().__init__(roots=roots, historical_roots=[history, *self.demo_roots],
                         launch_root=False, launch_home_root=False)

    def catalog(self):
        runs = super().catalog()
        # Earlier curated stories belong in All runs. The Demo view represents
        # the published contracts, with one selected replay for each delivery.
        for item, path in runs:
            if item.get('demo') and path not in self.demo_roots:
                item.pop('demo', None)
                item.pop('demo_order', None)
        return runs

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


def make_app(dist, live, history, replay, second_replay=None, *, extra_roots=()):
    dist, live, history, replay = (Path(path).expanduser().resolve() for path in (dist, live, history, replay))
    if not (dist / 'index.html').is_file():
        raise ValueError(f'Engine web build is missing: {dist / "index.html"}')
    for path in (live, history):
        if not (path / 'factory.sqlite').is_file():
            raise ValueError(f'Factory home is missing its database: {path}')

    service = EngineRuns(live, history, replay, second_replay, extra_roots)
    channel = WebChannel(WebChannelConfig(enabled=True, port=TAILSCALE_PORT), RobotMessageRouter())
    app = build_web_channel_app(channel, factory_service=service)
    app.mount('/', StaticFiles(directory=dist, html=True), name='engine-frontend')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[TAILSCALE_HOST, TAILSCALE_DNS])
    app.add_middleware(ViewerBoundary)
    return app


def main(argv=None):
    muse = Path.home() / 'muse-demo'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--live', type=Path, default=muse / 'graph-r8')
    parser.add_argument('--history', type=Path, default=muse / 'graph-v4')
    parser.add_argument('--replay', type=Path, required=True, help='Exact R8 curated replay bundle directory.')
    parser.add_argument('--second-replay', type=Path, default=muse/'r9/curated-replay')
    args = parser.parse_args(argv)
    os.environ['JIUWENSWARM_CONFIG_URL'] = 'off'
    # Reuse the native app's configured factory roots for All runs.
    configured = FactoryHttpService(launch_root=False, launch_home_root=False).roots
    try:
        app = make_app(args.dist, args.live, args.history, args.replay,
                       args.second_replay if args.second_replay.is_dir() else None,
                       extra_roots=(*configured, muse / 'r9/graph'))
    except ValueError as exc:
        parser.error(str(exc))
    # The redacting log record factory consumes formatting arguments before Uvicorn's access formatter.
    uvicorn.run(app, host=TAILSCALE_HOST, port=TAILSCALE_PORT, proxy_headers=False,
                access_log=False, ws='none')


if __name__ == '__main__':
    main()
