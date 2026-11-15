"""Run the same executable factory from a terminal or serve its local API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import FactoryService
from .recordings import RecordingsStore, default_recordings_directory, export_recording
from .replay_export import ReplayExportError


def main():
    parser = argparse.ArgumentParser(description='Executable STRATA Software Factory')
    parser.add_argument('--root', default='.factory-runs')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=19000)
    parser.add_argument('--goal', action='append', dest='goals')
    parser.add_argument('--revision')
    parser.add_argument('--model-path')
    parser.add_argument('--backend', choices=['ascend', 'cpu', 'cuda'], default='ascend')
    parser.add_argument('--core', action='append', choices=['router', 'swiglu', 'moe_combine'])
    parser.add_argument('--workflow', dest='workflow_path')
    parser.add_argument('--task-file', type=Path)
    parser.add_argument('--recordings', type=Path, default=default_recordings_directory(),
                        help='Directory of portable read-only recording ZIPs')
    portable = parser.add_mutually_exclusive_group()
    portable.add_argument('--export-recording', type=Path, metavar='RUN_DIR',
                          help='Export existing evidence without executing the factory')
    portable.add_argument('--import-recording', type=Path, metavar='BUNDLE_ZIP')
    portable.add_argument('--list-recordings', action='store_true')
    parser.add_argument('--output', type=Path, help='Portable recording ZIP destination')
    args = parser.parse_args()
    recordings = RecordingsStore(args.recordings)
    try:
        if args.export_recording:
            if not args.output:
                parser.error('--export-recording requires --output')
            print(json.dumps(export_recording(args.export_recording, args.output), indent=2))
            return 0
        if args.import_recording:
            print(json.dumps(recordings.import_bundle(args.import_recording), indent=2))
            return 0
        if args.list_recordings:
            print(json.dumps({'recordings': recordings.list('local-operator')}, indent=2))
            return 0
    except (ReplayExportError, OSError) as error:
        parser.exit(1, f'Recording operation failed: {error}\n')
    service = FactoryService(Path(args.root))
    if args.serve:
        from fastapi import FastAPI
        import uvicorn
        from .api import create_router
        app = FastAPI(title='Software Factory')
        app.include_router(create_router(service, recordings=recordings))
        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    if not args.goals and not args.workflow_path and not args.task_file:
        parser.error('Specify --goal, --workflow or --task-file unless --serve is used')
    result = service.create({'goals': args.goals or [], 'workflow_path': args.workflow_path,
                             'task': json.loads(args.task_file.read_text()) if args.task_file else None,
                             'repository_url': 'https://github.com/niko1221/strata',
                             'revision': args.revision, 'model_path': args.model_path,
                             'target_backend': args.backend, 'owner_id': 'local-operator',
                             'options': {'jobs': 2, 'core_algorithms': args.core}}, background=False)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
