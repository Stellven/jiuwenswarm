#!/usr/bin/env python3
"""A/A-aware, direction-aware performance gate for labelled summaries."""
import argparse
import json
import math
from pathlib import Path
import statistics


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


SECONDARY_FIELDS = ('nvme_gib_per_token', 'prompt_tps', 'eval_tps', 'eval_ms_per_token',
                    'nvme_gib_per_token_decode', 'gpu_util_median', 'energy_j_per_token',
                    'threads.cpu_workers_r_fraction', 'threads.main_workers_d_fraction',
                    'threads.majflt_per_token')


def metric_direction(metric, direction=None):
    direction = direction or ('lower' if metric == 'eval_ms_per_token' else 'higher')
    if direction not in ('lower', 'higher'):
        raise ValueError('direction must be lower or higher')
    return direction


def secondary_table(verdict):
    fields = ('eval_ms_per_token', 'nvme_gib_per_token_decode', 'gpu_util_median',
              'energy_j_per_token', 'nvme_gib_per_token', 'prompt_tps', 'eval_tps',
              'threads.cpu_workers_r_fraction', 'threads.main_workers_d_fraction',
              'threads.majflt_per_token')
    lines = ['| Arm | ms/token | NVMe GiB/token (decode) | gpu_util med (%) | J/token | NVMe GiB/token (whole) | Prompt t/s | Eval t/s | CPU workers R | Main+workers D | Threads majflt/token |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm, metrics in verdict['secondary_metrics'].items():
        values = [format(metrics[f], '.6g') if finite(metrics.get(f)) else '—' for f in fields]
        lines.append('| ' + ' | '.join([arm, *values]) + ' |')
    return '\n'.join(lines)


def evaluate(arms, metric='eval_tps', base='base', direction=None):
    direction = metric_direction(metric, direction)
    inputs = {arm: [run.get(metric) for run in runs] for arm, runs in arms.items()}
    means, gaps = {}, {}
    reasons = []
    for arm, numbers in inputs.items():
        valid = bool(numbers) and all(finite(n) and n > 0 for n in numbers)
        means[arm] = statistics.mean(numbers) if valid else None
        gaps[arm] = ((max(numbers) - min(numbers)) / means[arm]
                     if valid and len(numbers) >= 2 else None)
        if not valid:
            reasons.append(f'{arm}: missing/nonpositive/nonfinite {metric}')
        if any(r.get('status', 'ok') != 'ok' for r in arms[arm]):
            reasons.append(f'{arm}: unsuccessful run')
        if any(r.get('host_contention') for r in arms[arm]):
            reasons.append(f'{arm}: host_contention')
    base_values = inputs.get(base, [])
    drift_halves = None
    drift = None
    if means.get(base) and len(base_values) >= 2:
        split = len(base_values) // 2
        drift_halves = [statistics.mean(base_values[:split]), statistics.mean(base_values[split:])]
        drift = abs(drift_halves[1] - drift_halves[0]) / means[base]
    aa_gap = max((gap for gap in gaps.values() if gap is not None), default=0.0)
    threshold = max(0.03, 2 * aa_gap, 2 * (drift or 0.0))
    if base not in arms:
        reasons.append(f'base arm {base!r} absent')
    comparisons = {}
    for arm in arms:
        if arm == base:
            continue
        ratio = None
        if means[arm] and means.get(base):
            ratio = (means[base] / means[arm] if direction == 'lower'
                     else means[arm] / means[base])
        verdict = 'null'
        if ratio is not None and not reasons:
            if ratio - 1 > threshold and not math.isclose(ratio - 1, threshold, rel_tol=1e-12):
                verdict = 'improved'
            elif 1 - ratio > threshold and not math.isclose(1 - ratio, threshold, rel_tol=1e-12):
                verdict = 'regressed'
        comparisons[arm] = {'mean': means[arm], 'base_mean': means.get(base),
                            'ratio': ratio, 'change': ratio - 1 if ratio is not None else None,
                            'threshold': threshold, 'verdict': verdict}
    hashes = {arm: [run.get('output_sha') for run in runs] for arm, runs in arms.items()}
    flat = [value for values in hashes.values() for value in values]
    if not flat or any(value is None for value in flat):
        output = {'class': 'unknown', 'reason': 'output hash missing', 'hashes': hashes}
    elif len(set(flat)) == 1:
        output = {'class': 'identical', 'hashes': hashes}
    else:
        reference = next(iter(hashes.get(base, [])), flat[0])
        output = {'class': 'differs', 'hashes': hashes,
                  'differs': {arm: [{'run_index': i, 'output_sha': h} for i, h in enumerate(values)
                                    if h != reference] for arm, values in hashes.items()
                              if any(h != reference for h in values)},
                  'reference_sha': reference}
    secondary = {}
    for arm, runs in arms.items():
        secondary[arm] = {}
        for field in SECONDARY_FIELDS:
            values = [r[field] for r in runs if finite(r.get(field))]
            secondary[arm][field] = statistics.mean(values) if values else None
    cache_means = {}
    for arm, runs in arms.items():
        values = [r['cache_start_resident_pct'] for r in runs
                  if finite(r.get('cache_start_resident_pct'))
                  and 0 <= r['cache_start_resident_pct'] <= 100]
        if values:
            cache_means[arm] = statistics.mean(values)
    cache_confound = None
    if len(cache_means) >= 2 and max(cache_means.values()) - min(cache_means.values()) > 10:
        cache_confound = ('arms\' mean start residency differs by > 10 percentage points: '
                          + ', '.join(f'{arm}={value:.2f}%' for arm, value in cache_means.items()))
    return {'cache_confound': cache_confound,
            'secondary_metrics': secondary, 'metric': metric, 'direction': direction, 'base': base, 'inputs': inputs, 'means': means,
            'aa_gaps': gaps, 'aa_gap': aa_gap, 'drift_halves': drift_halves,
            'drift': drift, 'threshold': threshold, 'minimum_effect': 0.03,
            'noise_multiplier': 2, 'comparisons': comparisons, 'output': output,
            'reasons': reasons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summaries', help='JSON object: arm -> summary objects or summary.json paths')
    parser.add_argument('--metric', default='eval_ms_per_token')
    parser.add_argument('--direction', choices=['lower', 'higher'])
    parser.add_argument('--base', default='base')
    args = parser.parse_args()
    arms = json.loads(Path(args.summaries).read_text())
    arms = {arm: [json.loads(Path(r).read_text()) if isinstance(r, str) else r for r in runs]
            for arm, runs in arms.items()}
    print(json.dumps(evaluate(arms, args.metric, args.base, args.direction), indent=2))


if __name__ == '__main__':
    main()
