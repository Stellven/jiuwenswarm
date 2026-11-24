"""Reconcile JSONL event coverage and loss against an independent dispatch manifest."""

import argparse
import json
from pathlib import Path


def identity(microbatch, layer):
    if any(type(value) is not int or value < 0 for value in (microbatch, layer)):
        raise ValueError('microbatch and layer must be nonnegative integers')
    return microbatch, layer


def expected_keys(path):
    pairs = json.loads(path.read_text())
    if not isinstance(pairs, list) or not pairs:
        raise ValueError('expected a nonempty JSON array of [microbatch, layer] pairs')
    keys = set()
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError('expected [microbatch, layer] pairs')
        key = identity(*pair)
        if key in keys:
            raise ValueError(f'duplicate manifest key {key}')
        keys.add(key)
    return keys


def check(path, expected, expect_loss):
    seen = set()
    summary = None
    with path.open(encoding='utf-8') as trace:
        for number, line in enumerate(trace, 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict) or summary is not None:
                    raise ValueError('expected an object and a single final summary')
                if row.get('type') == 'summary':
                    summary = row
                elif row.get('type') == 'event':
                    key = identity(row['microbatch'], row['layer'])
                    if key in seen or key not in expected:
                        raise ValueError(f'duplicate or unexpected event {key}')
                    seen.add(key)
                else:
                    raise ValueError('expected an event or summary row')
            except (KeyError, ValueError) as error:
                raise ValueError(f'line {number}: {error}') from error
    if summary is None:
        raise ValueError('missing final summary')
    counts = {key: summary.get(key) for key in ('expected', 'written', 'lost')}
    if counts != {'expected': len(expected), 'written': len(seen), 'lost': len(expected - seen)} \
            or any(type(value) is not int for value in counts.values()):
        raise ValueError('summary does not reconcile with the dispatch manifest and retained events')
    if (counts['lost'] > 0) != expect_loss:
        raise ValueError(f'unexpected loss count {counts["lost"]}')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path, help='Recorder JSONL file')
    parser.add_argument('manifest', type=Path, help='Independent JSON list of [microbatch, layer] pairs')
    parser.add_argument('--expect-loss', action='store_true', help='Require positive accounted loss')
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.trace, expected_keys(args.manifest), args.expect_loss)))
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
