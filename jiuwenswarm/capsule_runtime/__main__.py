"""python -m jiuwenswarm.capsule_runtime list | describe ID | admit ID | invoke ID --inputs FILE.json"""
import argparse
import json
import sys

from . import verifier_backends
from .engine import Runtime


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python -m jiuwenswarm.capsule_runtime', description=__doc__)
    parser.add_argument('--extra-dir', action='append', default=[], help='extra directory of capsules (same layout as capsule_extensions)')
    verifier_backends.add_arguments(parser, 'worker')
    verifier_backends.add_arguments(parser, 'verifier')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    sub.add_parser('describe').add_argument('id')
    sub.add_parser('admit').add_argument('id')
    run = sub.add_parser('invoke')
    run.add_argument('id')
    run.add_argument('--inputs', required=True, help='JSON file: object keyed by input port name')
    run.add_argument('--out', help='write the full result (receipt included) to this file')
    run.add_argument('--objective', help='task objective for model-based capsules')
    run.add_argument('--no-admission', action='store_true', help='skip the in-process admission requirement')
    args = parser.parse_args(argv)
    runtime = Runtime(args.extra_dir, worker_model=verifier_backends.from_args(args, 'worker'))
    emit = lambda value: print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    try:
        if args.command == 'list':
            emit(runtime.list())
            return 0
        if args.command == 'describe':
            emit(runtime.describe(args.id))
            return 0
        if args.command == 'admit':
            result = runtime.admit(args.id)
            emit(result)
            return 0 if result['passed'] else 1
        with open(args.inputs, encoding='utf-8') as stream:
            inputs = json.load(stream)
        if not args.no_admission:
            admission = runtime.admit(args.id)
            if not admission['passed']:
                emit({'status': 'halted', 'halt': {'stage': 'pin', 'code': 'not_admitted',
                      'reason': '; '.join(admission['failures'])[:500]}})
                return 1
        result = runtime.invoke(args.id, inputs, require_admission=not args.no_admission,
                                verifier_model=verifier_backends.from_args(args, 'verifier'), require_semantic=args.require_semantic,
                                contract={'objective': args.objective} if args.objective else None)
        if args.out:
            with open(args.out, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(result, stream, indent=2, ensure_ascii=False, sort_keys=True)
        emit(result)
        return 0 if result['status'] == 'delivered' else 2
    except KeyError as error:
        print(str(error).strip('"'), file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
