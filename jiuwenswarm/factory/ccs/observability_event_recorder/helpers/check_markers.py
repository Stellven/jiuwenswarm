"""Summarize recorder lifecycle lines and effective model load modes."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re


def inspect(log, name):
    marker = re.compile(rf'(?<![\w.]){re.escape(name)}: (active\b|inactive (?=\()|stats\b)')
    load_mode = re.compile(r'\bload_tensors:.*?\(load_mode = ([^()]+)\)')
    counts = Counter(active=0, inactive=0, stats=0)
    modes = []
    lines = []
    for line in log:
        found = marker.search(line)
        if found:
            counts[found[1].strip()] += 1
            lines.append(line.rstrip())
        load = load_mode.search(line)
        if load:
            modes.append(load[1])
    return {'markers': dict(counts), 'lines': lines, 'load_modes': modes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--name', default='runtime_event_recorder', help='Marker prefix before the colon')
    parser.add_argument('--expect', choices=('active', 'inactive', 'off'),
                        help='Require the corresponding first-use and exit marker counts')
    parser.add_argument('--load-mode', help='Require every reported load mode to equal this value')
    parser.add_argument("--expect-silent", action="store_true",
                        help="Fail if any line contains the component's marker prefix")
    args = parser.parse_args()
    if args.expect_silent:
        prefix = re.compile(rf"(?<![\w.]){re.escape(args.name)}:")
        try:
            with args.log.open(encoding="utf-8", errors="replace") as log:
                unexpected = [number for number, line in enumerate(log, 1) if prefix.search(line)]
        except OSError as exc:
            parser.exit(1, f"{exc}\n")
        if unexpected:
            print(json.dumps({"unexpected_marker_lines": unexpected}))
            return 1
    try:
        with args.log.open(encoding='utf-8', errors='replace') as log:
            report = inspect(log, args.name)
    except OSError as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(report, indent=2))
    if args.expect:
        expected = {'active': int(args.expect == 'active'),
                    'inactive': int(args.expect == 'inactive'), 'stats': int(args.expect != 'off')}
        if report['markers'] != expected:
            return 1
    modes = report['load_modes']
    return int(bool(args.load_mode) and (not modes or set(modes) != {args.load_mode}))


if __name__ == '__main__':
    raise SystemExit(main())
