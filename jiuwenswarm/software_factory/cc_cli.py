"""Run/inspect/reconcile native CC workflows without a second job scheduler."""
import argparse
import json
from pathlib import Path
import time

from .cc_service import CCService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('catalog')
    create = sub.add_parser('create')
    create.add_argument('request', type=Path)
    for name in ('get', 'tick', 'events', 'stop', 'run'):
        command = sub.add_parser(name)
        command.add_argument('run_id')
        if name == 'run':
            command.add_argument('--seconds', type=float, default=60)
    append = sub.add_parser('append')
    append.add_argument('run_id')
    append.add_argument('request', type=Path)
    args = parser.parse_args()
    service = CCService.from_config(args.config)
    if args.command == 'catalog':
        result = service.catalog()
    elif args.command == 'create':
        result = service.create(json.loads(args.request.read_text()))
    elif args.command == 'append':
        result = service.append(args.run_id, json.loads(args.request.read_text()))
    elif args.command == 'run':
        if not 0 < args.seconds <= 3600:
            parser.error('--seconds must be between 0 and 3600')
        until = time.monotonic() + args.seconds
        while True:
            result = service.runtime.tick(args.run_id)
            if result['status'] in {'completed', 'failed', 'cancelled'} or time.monotonic() >= until:
                break
            time.sleep(.25)
    else:
        result = getattr(service.runtime, args.command)(args.run_id)
    print(json.dumps(result, indent=2))
    return 2 if isinstance(result, dict) and result.get('status') == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
