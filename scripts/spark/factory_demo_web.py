"""Serve the offline Factory Runs UI and its read-only fallback on loopback."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from jiuwenswarm.common.ws_limits import WEB_WS_MAX_MESSAGE_BYTES
from jiuwenswarm.factory import demo_board, monitor
from jiuwenswarm.factory.redact import sanitize
from jiuwenswarm.gateway.channel_manager.base import RobotMessageRouter
from jiuwenswarm.gateway.channel_manager.web.app_web_handlers import WebHandlersBindParams, _register_web_handlers
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
from jiuwenswarm.gateway.channel_manager.web.web_channel_app import build_web_channel_app
from jiuwenswarm.gateway.channel_manager.web.web_connect import WebChannel, WebChannelConfig

DEMO_PORT = 5175
DEFAULT_DIST = Path(__file__).resolve().parents[2] / 'jiuwenswarm/channels/web/frontend/dist'
BOARD_HEADERS = {'Cache-Control': 'no-store'}


def make_app(dist, live, history, *, extra_roots=()):
    dist, live, history = (Path(path).expanduser().resolve() for path in (dist, live, history))
    if not (dist / 'index.html').is_file():
        raise ValueError(f'Offline web build is missing: {dist / "index.html"}')
    for path in (live, history):
        if not (path / 'factory.sqlite').is_file():
            raise ValueError(f'Factory home is missing its database: {path}')
    if live.is_relative_to(history) or history.is_relative_to(live):
        raise ValueError('The live and history homes must be separate')
    service = FactoryHttpService(roots=[live, history, *extra_roots], historical_roots=[history, *extra_roots],
                                 launch_root=False, launch_home_root=False)
    channel = WebChannel(WebChannelConfig(enabled=True, port=DEMO_PORT), RobotMessageRouter())
    # Keep the native WebChannel transport and local web RPCs. Without an
    # AgentServer, unhandled messages return the native unavailable-method response.
    channel.on_message(lambda _message: False)
    _register_web_handlers(WebHandlersBindParams(channel=channel))
    app = build_web_channel_app(channel, factory_service=service)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])

    @app.get('/factory', include_in_schema=False)
    def factory_entry():
        return RedirectResponse('/#factory-run')

    @app.get('/fallback', include_in_schema=False)
    def fallback():
        return FileResponse(demo_board.HTML_PATH, media_type='text/html', headers=BOARD_HEADERS)

    def board_read(request: Request):
        path = request.url.path
        query = request.query_params
        task = query.get('task', '')
        try:
            if path in {'/api/board', '/api/plan', '/api/story', '/api/telemetry'}:
                native_tasks = monitor.tasks(live)
                task = task or (native_tasks[0]['task_id'] if native_tasks else '')
                if task not in {row['task_id'] for row in native_tasks}:
                    return JSONResponse({'error': 'Factory task not found in the live home'}, status_code=404,
                                        headers=BOARD_HEADERS)
            value = (demo_board.board_payload(live, task) if path == '/api/board' else
                     monitor.read_api(live, path, task=task, since=query.get('since', ''), attempt=query.get('attempt', '')))
        except monitor.READ_ERRORS as exc:
            return JSONResponse({'error': sanitize(str(exc))}, status_code=400, headers=BOARD_HEADERS)
        return JSONResponse(sanitize(value), headers=BOARD_HEADERS)

    for path in ('/api/board', *monitor.API_PATHS):
        app.add_api_route(path, board_read, methods=['GET'], include_in_schema=False)

    @app.post('/api/operator', include_in_schema=False)
    def fallback_operator():
        return JSONResponse({'error': 'The fallback board is read-only'}, status_code=403, headers=BOARD_HEADERS)

    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app


def main(argv=None):
    muse = Path.home() / 'muse-demo'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=DEFAULT_DIST)
    parser.add_argument('--live', type=Path, default=muse / 'graph-r8')
    parser.add_argument('--history', type=Path, default=muse / 'graph-v4')
    parser.add_argument('--extra-root', type=Path, action='append', default=[], metavar='PATH')
    parser.add_argument('--socket', type=Path, help='Serve on a Unix socket for local verification.')
    args = parser.parse_args(argv)
    # The offline demo retains the native authentication endpoints and uses
    # their existing disabled-remote-config mode.
    os.environ['JIUWENSWARM_CONFIG_URL'] = 'off'
    os.environ['JIUWENSWARM_ENABLE_ORIGIN_CHECK'] = '1'
    os.environ['JIUWENSWARM_WS_ALLOWED_ORIGIN_HOSTS'] = '127.0.0.1,localhost,none'
    try:
        app = make_app(args.dist, args.live, args.history, extra_roots=args.extra_root)
    except ValueError as exc:
        parser.error(str(exc))
    binding = {'uds': str(args.socket)} if args.socket else {'host': '127.0.0.1', 'port': DEMO_PORT}
    uvicorn.run(app, **binding, proxy_headers=False, access_log=False, ws_max_size=WEB_WS_MAX_MESSAGE_BYTES,
                ws_ping_interval=20.0, ws_ping_timeout=60.0)


if __name__ == '__main__':
    main()
