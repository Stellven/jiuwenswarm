#!/usr/bin/env python3
"""Summarize guarded runs without requiring complete or well-formed logs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def summarize(directory, switch_regex=(), write=True):
    directory = Path(directory)
    result = {'dir': str(directory), 'reasons': {}, 'warnings': []}

    def put(key, value, reason='not recorded'):
        result[key] = value
        if value is None:
            result['reasons'][key] = reason
        else:
            result['reasons'].pop(key, None)

    def read(name):
        try:
            return (directory / name).read_text(errors='replace')
        except OSError as exc:
            result['warnings'].append(f'{name}: {exc.strerror}')
            return ''

    try:
        record = json.loads(read('result.json'))
        if not isinstance(record, dict):
            record = {}
    except (ValueError, TypeError):
        record = {}
    put('status', record.get('status'), 'result.json status missing or invalid')
    put('wall_s', record.get('wall_s') if numeric(record.get('wall_s')) else None)
    contention = {}
    if (directory / 'contention.json').exists():
        try:
            contention = json.loads(read('contention.json'))
            if not isinstance(contention, dict):
                contention = {}
        except (ValueError, TypeError):
            result['warnings'].append('invalid contention.json')
    count = contention.get('max_foreign_heavy', 0)
    result['max_foreign_heavy'] = count if numeric(count) and count >= 0 else 0
    result['host_contention'] = result['max_foreign_heavy'] > 0
    for phase in ('start', 'end'):
        try:
            cache = json.loads(read(f'page_cache.{phase}.json'))
            value = cache.get('resident_pct') if isinstance(cache, dict) else None
            error = cache.get('error') if isinstance(cache, dict) else None
        except (ValueError, TypeError):
            value, error = None, 'invalid page-cache JSON'
        put(f'cache_{phase}_resident_pct',
            value if numeric(value) and 0 <= value <= 100 else None,
            error or f'page_cache.{phase}.json residency unavailable')
    stderr = read('stderr.txt')
    stdout = read('stdout.txt')
    try:
        digest = hashlib.sha256((directory / 'stdout.txt').read_bytes()).hexdigest()[:12]
    except OSError:
        digest = None
    put('output_sha', digest, 'stdout.txt unavailable')
    patterns = []
    for pattern in switch_regex:
        try:
            patterns.append(re.compile(pattern))
        except re.error as exc:
            result['warnings'].append(f'invalid switch regex {pattern!r}: {exc}')
    result['switch_matches'] = {p.pattern: sum(bool(p.search(line)) for line in stderr.splitlines())
                                for p in patterns}
    result['switch_lines'] = [line for line in stderr.splitlines()
                              if any(p.search(line) for p in patterns)]
    for metric, expression in [('prompt_tps', r'prompt eval time.*?([\d.]+) tokens per second'),
                               ('eval_tps', r'(?<!prompt )\beval time.*?([\d.]+) tokens per second'),
                               ('load_s', r'\bload time\s*=\s*([\d.]+) ms'),
                               ('eval_tokens', r'(?<!prompt )\beval time.*?/\s*(\d+) (?:runs|tokens)')]:
        matches = re.findall(expression, stderr)
        try:
            value = float(matches[-1]) if matches else None
        except ValueError:
            value = None
        if metric == 'load_s' and value is not None:
            value /= 1000
        put(metric, value, 'performance line absent or invalid')

    for key, expression in [
            ('eval_ms_per_token', r'(?<!prompt )\beval time.*?\(\s*([\d.]+) ms per token'),
            ('prompt_ms_per_token', r'prompt eval time.*?\(\s*([\d.]+) ms per token'),
            ('eval_ms_total', r'(?<!prompt )\beval time\s*=\s*([\d.]+) ms'),
            ('eval_runs', r'(?<!prompt )\beval time.*?/\s*(\d+) (?:runs|tokens)'),
            ('load_ms', r'\bload time\s*=\s*([\d.]+) ms')]:
        matches = re.findall(expression, stderr)
        value = float(matches[-1]) if matches else None
        put(key, int(value) if key == 'eval_runs' and value is not None else value,
            'performance line absent or invalid')

    # Preserve both the benchmark average and the clock-ramp-discarded mean.
    try:
        bench = json.loads(stdout)
    except ValueError:
        bench = []
    if isinstance(bench, dict):
        bench = [bench]
    if not isinstance(bench, list):
        bench = []
    result['bench'] = {'pp': [], 'tg': []}
    for row in bench:
        if not isinstance(row, dict):
            continue
        kind = ('pp' if row.get('n_prompt') and not row.get('n_gen') else
                'tg' if row.get('n_gen') and not row.get('n_prompt') else None)
        if kind is None:
            continue
        samples = row.get('samples_ts', [])
        samples = samples if isinstance(samples, list) else []
        clean = all(numeric(x) for x in samples)
        steady = statistics.mean(samples[1:]) if len(samples) > 1 and clean else None
        avg = row.get('avg_ts') if numeric(row.get('avg_ts')) else None
        result['bench'][kind].append({'avg_ts': avg, 'samples_ts': samples, 'steady': steady})
        for suffix, value in [('avg_ts', avg), ('samples_ts', samples), ('steady', steady)]:
            put(f'{kind}_{suffix}', value, 'need at least two finite benchmark samples')
        metric = 'prompt_tps' if kind == 'pp' else 'eval_tps'
        put(metric, avg, 'benchmark avg_ts missing')
        if kind == 'tg' and numeric(row.get('n_gen')):
            put('eval_tokens', row['n_gen'])
    for kind in ('pp', 'tg'):
        for suffix in ('avg_ts', 'samples_ts', 'steady'):
            if f'{kind}_{suffix}' not in result:
                put(f'{kind}_{suffix}', None, 'no matching llama-bench JSON row')

    values = {}
    timed = {}
    clocks = {}
    swap_derived = []
    unavailable = {}
    factors = {'B': 1 / 1024, 'KiB': 1, 'MiB': 1024, 'GiB': 1024 ** 2,
               'kB': 1000 / 1024}
    for line in read('telemetry.jsonl').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            result['warnings'].append('ignored malformed telemetry line')
            continue
        if not isinstance(row, dict):
            continue
        if numeric(row.get('mono_s')):
            clocks.setdefault(str(row.get('backend', 'unknown')), []).append(row['mono_s'])
        local = {}
        metrics = row.get('metrics', [])
        for metric in metrics if isinstance(metrics, list) else []:
            if not isinstance(metric, dict) or not numeric(metric.get('value')):
                continue
            name, value = metric.get('name'), metric['value']
            if not isinstance(name, str):
                continue
            if name == 'device_read':
                factor = factors.get(metric.get('unit', 'KiB'))
                if factor is None:
                    unavailable[name] = 'unsupported device_read unit'
                    continue
                value *= factor
            elif name in ('mem_available', 'swap_used', 'swap_total', 'swap_free'):
                factor = factors.get(metric.get('unit', 'MiB'))
                if factor is None:
                    continue
                value *= factor / 1024
            elif name in ('gpu_freq', 'gpu_freq_cur', 'emc_freq') and metric.get('unit') == 'Hz':
                value /= 1e6  # Summary clocks are MHz, including legacy telemetry.
            values.setdefault(name, []).append(value)
            clock = row.get('mono_s')
            if numeric(clock):
                timed.setdefault(name, []).append((clock, value))
            local[name] = value
        if 'swap_total' in local and 'swap_free' in local:
            swap_derived.append(local['swap_total'] - local['swap_free'])
        missing = row.get('unavailable', [])
        for metric in missing if isinstance(missing, list) else []:
            if isinstance(metric, dict):
                unavailable[metric.get('name')] = str(metric.get('reason') or 'unavailable')

    def delta(name):
        v = values.get(name, [])
        return max(v) - min(v) if len(v) >= 2 else None

    read_kib, ios = delta('device_read'), delta('device_read_ios')
    put('nvme_gib', read_kib / 1024 ** 2 if read_kib is not None else None,
        unavailable.get('device_read', 'need two device_read samples'))
    put('avg_kib_per_io', read_kib / ios if read_kib is not None and ios and ios > 0 else None,
        'need device_read and positive device_read_ios delta')
    tokens = result['eval_tokens']
    put('nvme_gib_per_token', result['nvme_gib'] / tokens
        if result['nvme_gib'] is not None and tokens and tokens > 0 else None,
        'need NVMe delta and positive eval token count')
    for key, names, fn in [('mem_available_min_mib', ['mem_available'], min),
                           ('swap_max_mib', ['swap_used'], max),
                           ('gpu_freq_median', ['gpu_freq', 'gpu_freq_cur'], statistics.median)]:
        samples = next((values[n] for n in names if values.get(n)), [])
        if key == 'swap_max_mib':
            samples = samples + swap_derived
        put(key, fn(samples) if samples else None,
            '; '.join(unavailable.get(n, f'{n} not recorded') for n in names))
    # Legacy stderr timestamps have no origin on the telemetry clock. Never
    # equate them to host uptime. Use the explicit, auditable fallback below.
    all_times = [t for ts in clocks.values() for t in ts]
    duration = result['eval_ms_total']
    start = end = load_start = load_end = None
    if all_times:
        load_start, end = min(all_times), max(all_times)
        if numeric(duration) and duration > 0:
            start = end - duration / 1000
        if numeric(result['load_ms']) and result['load_ms'] >= 0:
            load_end = load_start + result['load_ms'] / 1000
    intervals = [b - a for ts in clocks.values()
                 for a, b in zip(sorted(set(ts)), sorted(set(ts))[1:])]
    result['phase_windows'] = {
        'clock': 'mono_s', 'method': 'last_telemetry_before_exit_minus_eval_ms_total',
        'decode_start': start, 'decode_end': end, 'load_start': load_start, 'load_end': load_end,
        'sampling_error_bound_s': max(intervals) if intervals else None,
        'absolute_error_bound_s': None,
        'error_note': 'Endpoint sampling error is at most the largest observed backend interval '
                      'assuming sampling continued until exit. Engine teardown/exit lag is unknown; '
                      'no finite absolute phase alignment bound is available. Load begins at first '
                      'telemetry sample; startup offset is also unknown.'}

    def series(name):
        return sorted(dict(timed.get(name, [])).items())

    def clipped(name, lo, hi):
        points = series(name)
        if lo is None or hi is None or hi <= lo or len(points) < 2:
            return []
        if lo < points[0][0] or hi > points[-1][0]:
            return []  # No extrapolation across missing coverage.
        def at(t):
            for (a, x), (b, y) in zip(points, points[1:]):
                if a <= t <= b:
                    return x + (y - x) * (t - a) / (b - a)
        return [(lo, at(lo)), *[(t, v) for t, v in points if lo < t < hi], (hi, at(hi))]

    # Different backends are emitted sequentially. Clip the endpoint to the
    # last available counter/power sample (normally microseconds earlier).
    def covered_end(name, hi):
        points = series(name)
        return min(hi, points[-1][0]) if hi is not None and points else hi

    def phase_read(lo, hi):
        points = clipped('device_read', lo, covered_end('device_read', hi))
        if not points or any(b < a for (_, a), (_, b) in zip(points, points[1:])):
            return None
        return (points[-1][1] - points[0][1]) / 1024 ** 2

    put('nvme_gib_decode', phase_read(start, end), 'need decode timing and covered device_read counters')
    put('nvme_gib_load', phase_read(load_start, load_end), 'need load timing and covered device_read counters')
    runs = result['eval_runs']
    put('nvme_gib_per_token_decode', result['nvme_gib_decode'] / runs
        if result['nvme_gib_decode'] is not None and runs and runs > 0 else None,
        'need decode NVMe delta and positive eval_runs')
    def window_values(names):
        return next(([v for t, v in series(n) if start <= t <= end]
                     for n in names if timed.get(n)), []) if start is not None else []

    for key, names, fn in [
            ('gpu_util_median', ['gpu_util'], statistics.median),
            ('gpu_util_p90', ['gpu_util'], lambda v: sorted(v)[math.ceil(.9 * len(v)) - 1]),
            ('device_util_median', ['device_util'], statistics.median),
            ('power_in_w_median', ['power_VDD_IN_instant'], lambda v: statistics.median(v) / 1000),
            ('temp_tj_max', ['temp_tj'], max),
            ('gpu_freq_median', ['gpu_freq', 'gpu_freq_cur'], statistics.median),
            ('emc_freq_median', ['emc_freq'], statistics.median)]:
        samples = window_values(names)
        # Keep legacy whole-run frequency support when no decode timing exists.
        if key == 'gpu_freq_median' and start is None:
            samples = next((values[n] for n in names if values.get(n)), [])
        put(key, fn(samples) if samples else None, 'no decode-window samples: ' + ', '.join(names))
    power = clipped('power_VDD_IN_instant', start,
                    covered_end('power_VDD_IN_instant', end))
    joules = sum((b - a) * (x + y) / 2000
                 for (a, x), (b, y) in zip(power, power[1:])) if power else None
    put('energy_j_per_token', joules / runs if joules is not None and runs and runs > 0 else None,
        'need covered instant VDD_IN power, decode timing and positive eval_runs')
    # Use the thread capture's own last sample as the exit endpoint, like telemetry.
    thread_path = directory / 'threads.jsonl'
    thread_summary = None
    if thread_path.exists():
        try:
            from cc.thread_sampler.thread_sampler import aggregate
            thread_summary = aggregate(thread_path, result['eval_ms_total'], result['eval_runs'])
            if write:
                (directory / 'threads.summary.json').write_text(json.dumps(thread_summary, indent=2) + '\n')
        except (OSError, ValueError, KeyError) as exc:
            result['warnings'].append(f'threads: {exc}')
    elif (directory / 'threads.summary.json').exists():
        try:
            thread_summary = json.loads((directory / 'threads.summary.json').read_text())
        except (OSError, ValueError) as exc:
            result['warnings'].append(f'threads: {exc}')
    for field in ('cpu_workers_r_fraction', 'main_workers_d_fraction', 'majflt_per_token'):
        value = thread_summary.get(field) if isinstance(thread_summary, dict) else None
        put('threads.' + field, value, 'thread capture or decode window unavailable')
    if write:
        try:
            (directory / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        except OSError as exc:
            result['warnings'].append(f'cannot write summary.json: {exc.strerror}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dirs', nargs='+')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--no-write', action='store_true')
    parser.add_argument('--switch-regex', action='append', default=[])
    args = parser.parse_args()
    summaries = [summarize(d, args.switch_regex, not args.no_write) for d in args.dirs]
    if args.json:
        print(json.dumps(summaries[0] if len(summaries) == 1 else summaries, indent=2))
    else:
        for summary in summaries:
            print(json.dumps(summary))


if __name__ == '__main__':
    main()
