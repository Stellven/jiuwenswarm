"""Print one_shot commands or compare three captured greedy completion responses."""

import argparse
import json
from pathlib import Path
import shlex
import sys


GATE = 'LLAMA_EVENT_REC'
CAP = 'LLAMA_EVENT_REC_MIB'
ARMS = ('stock', 'off', 'on')


def plan(args, engine_flags):
    print('set -e')
    for arm, binary in zip(ARMS, (args.stock_bin, args.candidate_bin, args.candidate_bin)):
        env = ['env', '-u', GATE, '-u', CAP, f'MODEL={args.model}']
        if arm == 'on':
            env.append(f'{GATE}={args.trace}')
        command = ['bash', args.runner, binary, args.output_dir / arm, '5175',
                   *engine_flags, '--port', '5175', '--host', '127.0.0.1', '-lv', '4']
        print(shlex.join(str(arg) for arg in (*env, *command)))


def completion(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected a completion object')
    tokens = data.get('tokens')
    content = data.get('content')
    if not isinstance(tokens, list) or not tokens or any(type(token) is not int for token in tokens):
        raise ValueError(f'{path}: expected nonempty integer token IDs')
    if not isinstance(content, str):
        raise ValueError(f'{path}: expected completion content')
    return tokens, content.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    planner = commands.add_parser('plan', help='Print shell commands for an authorized real shell')
    planner.add_argument('stock_bin', type=Path)
    planner.add_argument('candidate_bin', type=Path)
    planner.add_argument('model', type=Path)
    planner.add_argument('output_dir', type=Path)
    planner.add_argument('trace', type=Path)
    planner.add_argument('--runner', type=Path, default=Path.home() / 'predemo' / 'one_shot.sh')
    checker = commands.add_parser('check', help='Compare stock, recorder-off and recorder-on captures')
    checker.add_argument('output_dir', type=Path)
    arguments = sys.argv[1:]
    separator = arguments.index('--') if '--' in arguments else len(arguments)
    engine_flags = arguments[separator + 1:]
    args = parser.parse_args(arguments[:separator])
    if args.command == 'plan':
        paths = (args.stock_bin, args.candidate_bin, args.model, args.output_dir, args.trace, args.runner)
        if any(not path.is_absolute() for path in paths):
            parser.error('plan requires absolute paths')
        if not args.output_dir.is_dir() or args.trace.exists() or args.trace.is_symlink():
            parser.error('Use an existing output directory and a fresh trace path')
        if any((args.output_dir / f'{arm}.{suffix}').exists()
               or (args.output_dir / f'{arm}.{suffix}').is_symlink()
               for arm in ARMS for suffix in ('json', 'server.log')):
            parser.error('Use a fresh output directory for the three captures')
        if args.trace.resolve() in {(args.output_dir / f'{arm}.{suffix}').resolve()
                          for arm in ARMS for suffix in ('json', 'server.log')}:
            parser.error('Trace path must differ from capture paths')
        plan(args, engine_flags)
        return 0
    if engine_flags:
        parser.error('Engine flags apply only to plan')
    try:
        stock, off, on = (completion(args.output_dir / f'{arm}.json') for arm in ARMS)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    report = {'stock_vs_off': stock == off, 'stock_vs_on': stock == on}
    print(json.dumps(report))
    return int(not all(report.values()))


if __name__ == '__main__':
    raise SystemExit(main())
