"""Serve the existing host frontend and real factory recordings in one process.

The launcher never starts an engineering task. Live construction is available
only through the existing explicit run submission API. Recorded playback reads
the sealed portable bundles through the same owner-checked factory router.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[2]
FRONTEND = REPOSITORY / 'jiuwenswarm/channels/web/frontend'


def frontend_fingerprint(frontend: Path = FRONTEND) -> str:
    """Pin the source inputs to the host build, rather than relying on mtimes."""
    paths = [p for name in ('src', 'public') for p in (frontend / name).rglob('*')
             if p.is_file()]
    paths.extend(frontend / name for name in
                 ('package.json', 'package-lock.json', 'index.html', 'vite.config.ts',
                  'tailwind.config.js', 'postcss.config.js', 'tsconfig.json')
                 if (frontend / name).is_file())
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(frontend).as_posix().encode())
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def build_frontend(frontend: Path = FRONTEND) -> None:
    npm = shutil.which('npm.cmd' if sys.platform == 'win32' else 'npm')
    if not npm:
        raise RuntimeError('Node.js and npm are required to build the host frontend')
    if not (frontend / 'node_modules').is_dir():
        subprocess.run([npm, 'ci'], cwd=frontend, check=True)
    # The host prebuild generates its normal source inputs. Capture their hash
    # after generation, then run the unchanged build script without repeating
    # pre/post hooks. A legitimate first build must not appear stale.
    if json.loads((frontend / 'package.json').read_text()).get('scripts', {}).get('prebuild'):
        subprocess.run([npm, 'run', 'prebuild'], cwd=frontend, check=True)
    before = frontend_fingerprint(frontend)
    subprocess.run([npm, '--ignore-scripts', 'run', 'build'], cwd=frontend, check=True)
    after = frontend_fingerprint(frontend)
    if before != after:
        raise RuntimeError('Host source changed during build; repeat --build after edits finish')
    index = frontend / 'dist/index.html'
    if not index.is_file():
        raise RuntimeError('The host build did not produce dist/index.html')
    record_frontend_build(frontend)


def _build_files(frontend: Path) -> dict[str, str]:
    directory = frontend / 'dist'
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Host build contains an unverified symbolic link')
        if path.is_file() and path.name != '.factory-build.json':
            files[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def record_frontend_build(frontend: Path = FRONTEND) -> None:
    """Seal the existing host's actual build files after its build succeeds."""
    files = _build_files(frontend)
    if 'index.html' not in files:
        raise RuntimeError('The host build did not produce dist/index.html')
    (frontend / 'dist/.factory-build.json').write_text(json.dumps({
        'schema': 'ai4r.factory-host-build:2',
        'source_sha256': frontend_fingerprint(frontend), 'files': files,
    }, indent=2) + '\n')


def check_frontend(frontend: Path = FRONTEND) -> dict:
    index = frontend / 'dist/index.html'
    stamp = frontend / 'dist/.factory-build.json'
    if not index.is_file() or not stamp.is_file():
        raise RuntimeError('Build the existing host frontend with --build first')
    record = json.loads(stamp.read_text())
    if record.get('source_sha256') != frontend_fingerprint(frontend):
        raise RuntimeError('Host frontend build is stale; use --build before presenting')
    if record.get('schema') != 'ai4r.factory-host-build:2' or record.get('files') != _build_files(frontend):
        raise RuntimeError('Host frontend assets changed after their recorded build')
    return {'directory': str(index.parent), 'source_sha256': record['source_sha256'],
            'asset_count': len(record['files'])}


def preflight(recordings_directory: Path | None = None, frontend: Path = FRONTEND) -> dict:
    from .recordings import RecordingsStore, default_recordings_directory
    missing = [name for name in ('fastapi', 'uvicorn', 'pydantic')
               if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError('Install requirements-demo.txt; missing: ' + ', '.join(missing))
    records = RecordingsStore(recordings_directory or default_recordings_directory())
    summaries = records.list('local-operator')
    if not summaries:
        raise RuntimeError('No verified local-operator recordings are available')
    return {'frontend': check_frontend(frontend), 'recordings': summaries,
            'mode': 'existing-host-ui', 'execution_dispatched': False}


def create_app(*, root: Path, recordings_directory: Path | None = None,
               frontend: Path = FRONTEND):
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from .api import create_router
    from .engine import FactoryService
    from .recordings import RecordingsStore, default_recordings_directory
    check_frontend(frontend)
    app = FastAPI(title='JiuwenSwarm Software Factory')
    app.state.factory_service = FactoryService(root)
    app.state.factory_recordings = RecordingsStore(
        recordings_directory or default_recordings_directory())
    app.include_router(create_router(app.state.factory_service,
                                     recordings=app.state.factory_recordings))
    app.mount('/', StaticFiles(directory=frontend / 'dist', html=True), name='host-frontend')
    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='Build the existing host frontend')
    parser.add_argument('--check', action='store_true', help='Verify local presentation inputs only')
    parser.add_argument('--recordings', type=Path)
    parser.add_argument('--root', type=Path, default=REPOSITORY / '.factory-runs')
    parser.add_argument('--port', type=int, default=5175)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.port <= 65535:
            raise RuntimeError('Port must be between 1 and 65535')
        if args.build:
            build_frontend()
        report = preflight(args.recordings)
        if args.check:
            print(json.dumps(report, indent=2))
            return 0
        app = create_app(root=args.root, recordings_directory=args.recordings)
        identifier = report['recordings'][0]['id']
        print(f'Workflow: http://127.0.0.1:{args.port}/?view=workflow&lng=en&recording={identifier}', flush=True)
        import uvicorn
        uvicorn.run(app, host='127.0.0.1', port=args.port)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
