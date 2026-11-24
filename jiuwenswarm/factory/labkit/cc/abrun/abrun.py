#!/usr/bin/env python3
"""Plan and execute a declarative counterbalanced experiment."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True

if __package__:
    from . import gate, preflight, run_summary
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from cc.abrun import gate, preflight, run_summary

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('FACTORY_LAB_STATE', '~/.jiuwenswarm-factory/lab')).expanduser()


def validate(spec):
    for key in ('id', 'outdir_base', 'runner', 'tool', 'argv', 'arms', 'order'):
        if key not in spec:
            raise ValueError(f'missing spec field: {key}')
    safe = r'[A-Za-z0-9][A-Za-z0-9_.-]*'
    if not isinstance(spec['id'], str) or not re.fullmatch(safe, spec['id']):
        raise ValueError('id must be a safe path component')
    if spec['runner'] != 'om_run':
        raise ValueError('only runner=om_run is supported')
    if not isinstance(spec['tool'], str) or not re.fullmatch(safe, spec['tool']):
        raise ValueError('tool must be a binary name')
    if not isinstance(spec['outdir_base'], str) or not spec['outdir_base']:
        raise ValueError('outdir_base must be a nonempty path')
    if not isinstance(spec['argv'], list) or not all(isinstance(x, str) for x in spec['argv']):
        raise ValueError('argv must be an array of strings')
    if not isinstance(spec.get('threads', False), bool):
        raise ValueError('threads must be boolean')
    if spec.get('cache_protocol', 'carryover') not in ('carryover', 'cold', 'warm'):
        raise ValueError('cache_protocol must be carryover, cold, or warm')
    if 'cache_warm_bytes' in spec and (not isinstance(spec['cache_warm_bytes'], int)
            or isinstance(spec['cache_warm_bytes'], bool) or spec['cache_warm_bytes'] < 0):
        raise ValueError('cache_warm_bytes must be a nonnegative integer')
    if 'cache_warm_ranges' in spec and (not isinstance(spec['cache_warm_ranges'], str)
            or not spec['cache_warm_ranges']):
        raise ValueError('cache_warm_ranges must be a nonempty host path')
    if 'cache_warm_bytes' in spec and 'cache_warm_ranges' in spec:
        raise ValueError('choose cache_warm_bytes or cache_warm_ranges')
    arms = spec['arms']
    if not isinstance(arms, dict) or len(arms) < 2 or 'base' not in arms:
        raise ValueError('arms must contain base and at least one treatment')
    for name, arm in arms.items():
        if not re.fullmatch(safe, name) or not isinstance(arm, dict):
            raise ValueError('invalid arm')
        if not isinstance(arm.get('image'), str) or not arm['image']:
            raise ValueError(f'{name}: missing image')
        extra = arm.get('extra_argv', [])
        if not isinstance(extra, list) or not all(isinstance(x, str) for x in extra):
            raise ValueError(f'{name}: extra_argv must be an array of strings')
        env = arm.get('env', {})
        if not isinstance(env, dict) or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k)
                                           or not isinstance(v, str) or re.search(r'\s', v)
                                           for k, v in env.items()):
            raise ValueError(f'{name}: env must map names to strings without whitespace (om_run restriction)')
        if not isinstance(arm.get('expect_switch', False), bool):
            raise ValueError('expect_switch must be boolean')
        if not isinstance(arm.get('switch_regex_is_config', False), bool):
            raise ValueError('switch_regex_is_config must be boolean')
        if arm.get('switch_regex_is_config') and not arm.get('switch_regex'):
            raise ValueError('switch_regex_is_config requires per-arm switch_regex')
    for owner in [spec, *arms.values()]:
        regexes = owner.get('switch_regex', [])
        if not isinstance(regexes, list) or not all(isinstance(r, str) for r in regexes):
            raise ValueError('switch_regex must be an array of regex strings')
        for pattern in regexes:
            re.compile(pattern)
    for arm in arms.values():
        if arm.get('expect_switch') and not (spec.get('switch_regex') or arm.get('switch_regex')):
            raise ValueError('expect_switch requires switch_regex')
    if arms['base'].get('expect_switch'):
        raise ValueError('base cannot expect a switch')
    rounds = spec.get('rounds', 1)
    if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1:
        raise ValueError('rounds must be a positive integer')
    if not isinstance(spec.get('metric', 'eval_ms_per_token'), str):
        raise ValueError('metric must be a summary field name')
    gate.metric_direction(spec.get('metric', 'eval_ms_per_token'), spec.get('direction'))
    planned_order(spec)


def planned_order(spec):
    arms = list(spec['arms'])
    arms = ['base'] + [name for name in arms if name != 'base']
    order = spec['order']
    if order == 'explicit':
        names = spec.get('explicit_order')
        if not isinstance(names, list) or not names or any(n not in arms for n in names):
            raise ValueError('explicit_order must be a nonempty list of known arms')
        if set(names) != set(arms):
            raise ValueError('explicit_order must include every arm')
    else:
        expected = ''.join(chr(65 + i) for i in range(len(arms)))
        expected += expected[::-1]
        if order not in (expected, 'mirrored'):
            raise ValueError(f'{len(arms)} arms require order={expected!r} or mirrored')
        names = arms + arms[::-1]
    return names * spec.get('rounds', 1)


def plan(spec):
    out = Path(spec['outdir_base']).expanduser() / spec['id']
    if not out.is_absolute():
        out = STATE / out
    runs = []
    for index, arm in enumerate(planned_order(spec), 1):
        config = spec['arms'][arm]
        directory = out / f'{index:03d}-{arm}'
        env_flags = ' '.join(f'-e {k}={v}' for k, v in config.get('env', {}).items())
        override = os.environ.get('ABRUN_RUNNER')
        runner = shlex.split(override) if override else [str(ROOT / 'cc/om_run/om_run.sh')]
        command = runner + [str(directory), config['image'], env_flags, spec['tool']] + spec['argv'] + config.get('extra_argv', [])
        cache_env = [f"OM_CACHE_PROTOCOL={spec.get('cache_protocol', 'carryover')}"]
        if 'cache_warm_bytes' in spec:
            cache_env += [f"OM_CACHE_WARM_BYTES={spec['cache_warm_bytes']}"]
            cache_env += ['OM_CACHE_WARM_RANGES=']
        if 'cache_warm_ranges' in spec:
            cache_env += [f"OM_CACHE_WARM_RANGES={spec['cache_warm_ranges']}"]
        command = ['env', *cache_env] + command
        if spec.get('threads'):
            command = ['env', 'OM_THREADS=1'] + command
        if not override:
            command = [str(ROOT / 'bin/run_op'), '--agent', 'abrun', '--task', spec['id'], '--'] + command
        runs.append({'index': index, 'arm': arm, 'dir': str(directory), 'command': command})
    return out, runs


def switch_patterns(spec):
    """All signatures are observed on every run to detect cross-arm leaks."""
    return list(dict.fromkeys([*spec.get('switch_regex', []),
                              *(p for arm in spec['arms'].values()
                                for p in arm.get('switch_regex', []))]))


def switch_errors(spec, arm, summary):
    config = spec['arms'][arm]
    matches = summary.get('switch_matches', {})
    if config.get('switch_regex_is_config', False):
        # A disabled component still prints its effective values. Require every
        # value assertion without treating its own config line as activation.
        own = set(config['switch_regex'])
        errors = [f'{arm}: config mismatch (no matches for {p!r})'
                  for p in own if not matches.get(p, 0)]
        if not config.get('expect_switch', False) and any(
                matches.get(p, 0) for p in switch_patterns(spec) if p not in own):
            errors.append(f'{arm}: switch leaked (another arm signature present)')
        return errors
    if not config.get('expect_switch', False):
        if any(matches.get(p, 0) for p in switch_patterns(spec)) or summary.get('switch_lines'):
            return [f'{arm}: switch leaked (switch_lines present)']
        return []
    errors = [f'{arm}: switch inert (no matches for {p!r})'
              for p in config.get('switch_regex', []) if not matches.get(p, 0)]
    legacy = spec.get('switch_regex', [])
    if legacy and not any(matches.get(p, 0) for p in legacy):
        errors.append(f'{arm}: switch inert (no switch_lines matching spec switch_regex)')
    return errors


def write_report(out, spec, runs, verdict):
    (out / 'verdict.json').write_text(json.dumps(verdict, indent=2) + '\n')
    lines = [f"# {spec['id']}", '', f"Status: {verdict['status']}", '',
             f"Page-cache protocol: {spec.get('cache_protocol', 'carryover')}", '',
             '| # | Arm | Status | Metric | Wall s | Output SHA | Switch matches | Cache start resident % | Cache end resident % |',
             '|---|---|---|---:|---:|---|---|---:|---:|']
    metric = spec.get('metric', 'eval_ms_per_token')
    for row in runs:
        s = row['summary']
        matches = json.dumps(s.get('switch_matches', {})).replace('|', '&#124;')
        lines.append(f"| {row['index']} | {row['arm']} | {s['status']} | {s.get(metric)} | {s['wall_s']} | {s['output_sha']} | {matches} | {s.get('cache_start_resident_pct')} | {s.get('cache_end_resident_pct')} |")
    lines += ['', f"Metric: {metric} ({verdict['direction']} is better)", '', f"| Arm | Mean | {'A/B' if verdict['direction'] == 'lower' else 'B/A'} | Gate |",
              '|---|---:|---:|---|']
    for arm, mean in verdict['means'].items():
        comparison = verdict['comparisons'].get(arm, {})
        lines.append(f"| {arm} | {mean} | {comparison.get('ratio', '—')} | {comparison.get('verdict', 'base')} |")
    lines += ['', '## Secondary metrics (descriptive; no verdict)', '', gate.secondary_table(verdict)]
    if verdict.get('cache_confound'):
        lines += ['', 'cache_confound: ' + verdict['cache_confound']]
    lines += ['', f"A/A gap: {verdict['aa_gap']}; drift: {verdict['drift']}; threshold: {verdict['threshold']}",
              '', f"Output class: {verdict['output']['class']}", '',
              'Output details: `' + json.dumps(verdict['output']) + '`', '',
              *verdict.get('invalid_reasons', []), *verdict.get('reasons', [])]
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n')


def execute(spec, out, runs):
    # Exclusive creation refuses accidental overwrite/replay into prior results.
    out.mkdir(parents=True, exist_ok=False)
    (out / 'spec.json').write_text(json.dumps(spec, indent=2) + '\n')
    grouped = {arm: [] for arm in spec['arms']}
    completed, invalid = [], []
    try:
        checked = set()
        for arm in spec['arms'].values():
            argv = spec['argv'] + arm.get('extra_argv', [])
            key = (arm['image'], spec['tool'], tuple(argv))
            if key not in checked:
                preflight.check(arm['image'], spec['tool'], argv)
                checked.add(key)
        for run in runs:
            rc = subprocess.run(run['command'], cwd=ROOT).returncode
            summary = run_summary.summarize(run['dir'], switch_patterns(spec))
            run['summary'] = summary
            completed.append(run)
            grouped[run['arm']].append(summary)
            invalid.extend(switch_errors(spec, run['arm'], summary))
            if rc != 0 or summary['status'] != 'ok':
                invalid.append(f"{run['arm']}: runner rc={rc}, status={summary['status']}")
            if invalid:
                break
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        invalid.append(str(exc))
    verdict = gate.evaluate(grouped, spec.get('metric', 'eval_ms_per_token'), direction=spec.get('direction'))
    if verdict['reasons']:
        invalid.extend(verdict['reasons'])
    verdict.update(status='INVALID' if invalid else 'completed', invalid_reasons=invalid,
                   cache_protocol=spec.get('cache_protocol', 'carryover'),
                   planned_order=[r['arm'] for r in runs],
                   executed_order=[r['arm'] for r in completed])
    if invalid:
        for comparison in verdict['comparisons'].values():
            comparison['verdict'] = 'null'
    write_report(out, spec, completed, verdict)
    print(json.dumps(verdict, indent=2))
    return 1 if invalid else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--submit', action='store_true')
    args = parser.parse_args()
    try:
        path = Path(args.spec).resolve()
        spec = json.loads(path.read_text())
        validate(spec)
        out, runs = plan(spec)
        if args.dry_run:
            print('Order: ' + ', '.join(r['arm'] for r in runs))
            for run in runs:
                print(f"Run {run['index']}: {run['arm']}  {shlex.join(run['command'])}")
            return 0
        if args.submit:
            queue = ROOT / 'bin/jobq'
            if not queue.exists():
                raise ValueError('--submit requires bin/jobq')
            return subprocess.run([str(queue), 'submit', '--class', 'gpu', '--name', spec['id'],
                                   '--', sys.executable, str(Path(__file__).resolve()), str(path)],
                                  cwd=ROOT).returncode
        return execute(spec, out, runs)
    except (OSError, ValueError, TypeError, re.error) as exc:
        parser.exit(1, f'abrun: {exc}\n')


if __name__ == '__main__':
    sys.exit(main())
