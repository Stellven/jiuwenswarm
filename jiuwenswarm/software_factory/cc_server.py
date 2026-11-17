"""Serve the native factory operator console without a second agent runtime."""
import argparse
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .cc_api import create_cc_router
from .cc_service import CCService


def create_app(config, static):
    static = Path(static).resolve()
    if not (static / 'index.html').is_file():
        raise ValueError('Build the factory console before starting the service')
    service = CCService.from_config(config)
    app = FastAPI(title='Native CC Software Factory', docs_url=None, redoc_url=None)
    app.state.cc_workflow_service = service
    app.include_router(create_cc_router(service))

    @app.get('/review')
    def review():
        return FileResponse(Path(__file__).with_name('review.html'))

    @app.get('/healthz')
    def health():
        return {'status': 'ok', 'task_id': service.runtime.task_id,
                'execution': 'native-cc', 'acceptance': 'not_assessed',
                'foundation':'evolved-m1-native','shared_schema':'0.2.0'}

    app.mount('/', StaticFiles(directory=static, html=True), name='console')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--static', type=Path, required=True)
    args = parser.parse_args()
    import uvicorn
    # Loopback only. Remote operators use an SSH tunnel; never trust proxy headers.
    uvicorn.run(create_app(args.config, args.static), host='127.0.0.1', port=5175,
                proxy_headers=False)


if __name__ == '__main__':
    main()
