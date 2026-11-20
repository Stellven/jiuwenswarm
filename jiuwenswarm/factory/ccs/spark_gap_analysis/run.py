"""Compute provenance-aware Spark timing summaries from retained lab evidence."""
from datetime import datetime
import hashlib
from itertools import product
import json
import math
import random
import re
from statistics import median, quantiles
import sys

PROMPTS = (512, 2048)
LIMIT = 8 * 1024 * 1024
CEILING = 100 * 1024**3
DIGEST = re.compile(r'[0-9a-f]{64}')


def reference(item):
    if not item['artifact_id'] or not DIGEST.fullmatch(item['sha256']):
        raise ValueError('Evidence must name a retained artifact and SHA256')
    return {key: item[key] for key in ('artifact_id', 'sha256')}


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def eligible(row, prompt_hash):
    request, result = row['request'], row['result']
    n = result['prompt_tokens']
    usage, timings = result.get('usage', {}), result.get('timings', {})
    messages = request.get('messages')
    return (result.get('ok') is True and positive(result.get('ttft_s'))
            and n in PROMPTS and usage.get('prompt_tokens') == n and usage.get('completion_tokens') == 32
            and usage.get('prompt_tokens_details', {}).get('cached_tokens') == 0 and timings.get('cache_n') == 0
            and request.get('cache_prompt') is False and request.get('stream') is True
            and request.get('temperature') == 0 and request.get('max_tokens') == 32 and request.get('seed') == 1
            and type(messages) is list and len(messages) == 1 and messages[0].get('role') == 'user'
            and hashlib.sha256(messages[0]['content'].encode()).hexdigest() == result.get('prompt_sha256') == prompt_hash[n]
            and bool(DIGEST.fullmatch(result.get('output_sha256', ''))))


def interval(values):
    bounds = quantiles(values, n=40, method='inclusive')
    return [bounds[0], bounds[-1]]


def compare(cell, controls, paired=None):
    t = cell['ttft_s']
    comparisons = {}
    for arm, key in (('A', 'inverse_ttft_vs_A'), ('A+', 'inverse_ttft_vs_Aplus')):
        if arm in controls:
            comparisons[key] = {'estimate': controls[arm]['ttft_s'] / t}
            if paired:
                comparisons[key]['conditional_ci95'] = interval([sample[arm] / sample[cell['arm']] for sample in paired])
    if 'A' in controls and 'S' in controls:
        a, s = controls['A']['ttft_s'], controls['S']['ttft_s']
        comparisons['stock_minus_strata_s'] = a - s
        comparisons['gap_closed'] = {'estimate': (a - t) / (a - s) if a > s else None}
        if paired and all(sample['A'] > sample['S'] for sample in paired):
            comparisons['gap_closed']['conditional_ci95'] = interval([
                (sample['A'] - sample[cell['arm']]) / (sample['A'] - sample['S']) for sample in paired])
    return comparisons


def paired_draws(blocks):
    if blocks == ((1, 2), (3, 4, 5)):
        return [before + after for before, after in product(
            product(blocks[0], repeat=2), product(blocks[1], repeat=3))]
    # Sample within each launch pass and apply the same labels to every arm and endpoint.
    rng = random.Random(20261120)
    return [tuple(i for block in blocks for i in rng.choices(block, k=len(block))) for _ in range(10000)]


def paired_samples(index, draws):
    return [{arm: median(repeats[i] for i in labels) for arm, repeats in index.items()} for labels in draws]


def paired_changes(index, arm, control, draws, blocks, direction):
    values = {key: direction * (index[arm][key] - index[control][key]) for block in blocks for key in block}
    return dict(estimate=median(values.values()), observed_range=[min(values.values()), max(values.values())],
                pass_medians=[median(values[i] for i in block) for block in blocks],
                conditional_ci95=interval([median(values[i] for i in labels) for labels in draws]))


def p4_design(scopes, rows):
    arm_order = [scope['arm'] for scope in scopes]
    half = len(arm_order) // 2
    first = arm_order[:half]
    if len(first) < 2 or len(set(first)) != half or arm_order[half:] != first[::-1]:
        raise ValueError('P4 requires two mirrored launch passes with distinct arms')
    blocks = None
    previous_stop = None
    for number, scope in enumerate(scopes):
        start = datetime.fromisoformat(scope['value']['start'])
        stop = datetime.fromisoformat(scope['value']['stop'])
        if stop <= start or (previous_stop is not None and start < previous_stop):
            raise ValueError('P4 launch intervals must be chronological and nonoverlapping')
        previous_stop = stop
        reference(scope['quiet_preflight'])
        if scope['quiet_preflight'].get('quiet') is not True:
            raise ValueError('P4 requires an explicit quiet preflight for each launch')
        local = sorted((r for r in rows if r['scope_id'] == scope['artifact_id']),
                       key=lambda r: datetime.fromisoformat(r['result']['started']))
        seen = [(r['result']['repeat'], r['result']['prompt_tokens']) for r in local]
        if blocks is None:
            blocks = ((tuple(range(1, 6)), tuple(range(6, 11))) if len(local) == 16 else ((1, 2), (3, 4, 5)))
        expected = [(0, 512), (0, 2048)] * 2
        modern = len(blocks[0]) == 5
        if modern:
            expected.extend(((0, 2048), (0, 512)))
        for j, i in enumerate(blocks[0 if number < half else 1]):
            forward = (j % 2 == 0) if modern else (i % 2 == 1)
            expected.extend((i, n) for n in (PROMPTS if forward else PROMPTS[::-1]))
        if seen != expected or any(not r['valid'] or bool(r['result']['discard']) != (r['result']['repeat'] == 0) for r in local):
            raise ValueError('P4 scope is missing matched warmups or measured repeats in protocol order')
        if any(not start <= datetime.fromisoformat(r['result']['started']) < stop for r in local):
            raise ValueError('P4 request timestamps must belong to their launch window')
    return blocks


def analyze(evidence):
    mode = evidence['mode']
    if mode == 'pooled-30-screen':
        from pooled30 import analyze as analyze_pooled
        return analyze_pooled(evidence, eligible, reference, positive)
    p4 = mode in ('p4-abba', 'p4-build-overlap')
    if mode == 'early-bracket':
        from early_bracket import analyze as analyze_early
        return analyze_early(evidence, eligible, reference, positive)
    if mode == 'c2-placement-functional':
        from placement_functional import analyze as analyze_placement
        return analyze_placement(evidence, eligible, reference, positive)
    if mode == 'c3-warmup-pilot':
        from residency_speed import analyze as analyze_warmup
        return analyze_warmup(evidence, eligible, reference, positive)
    if mode in ('c3-cold-steady', 'c3-screening-60', 'a-s-cold-steady'):
        from residency_speed import analyze_steady
        return analyze_steady(evidence, eligible, reference, positive)
    if mode == 'c3-direct-seed-30g':
        from direct_seed import analyze as analyze_direct_seed
        return analyze_direct_seed(evidence, eligible, reference, positive)
    if mode != 'p1-reconnaissance' and not p4:
        raise ValueError('Use the P1 reconnaissance or P4 ABBA evidence mode')
    manifest = evidence['prompt_manifest']
    prompt_hashes = {p['target_tokens_including_template']: p['prompt_sha256'] for p in manifest['value']['prompts']}
    if set(prompt_hashes) != set(PROMPTS) or not all(DIGEST.fullmatch(value) for value in prompt_hashes.values()):
        raise ValueError('Expected 512 and 2048 fixed prompt digests')

    scopes, rows = evidence['scopes'], evidence['requests']
    if not scopes or not rows or len(scopes) > 32 or len(rows) > 320:
        raise ValueError('Evidence must contain 1–32 scopes and 1–320 request records')
    owners = {r['artifact_id']: r['arm'] for r in scopes}
    if len(owners) != len(scopes) or len({r['artifact_id'] for r in rows}) != len(rows):
        raise ValueError('Scope and request artifact IDs must be unique')
    scope_metrics = []
    for scope in scopes:
        value = scope['value']
        if (value.get('returncode') != 0 or value.get('reason') or value.get('scope_verified') is not True
                or value.get('memory_max') != CEILING or value.get('cpus') != '0-7'
                or any(int(value['memory_events'][name]) for name in ('oom', 'oom_kill'))):
            raise ValueError('Timing scope failed verified 100GiB/8 CPU admission or normal exit')
        load = scope['load']
        scope_metrics.append({'arm': scope['arm'], 'result': reference(scope), 'load': reference(load),
                              'load_s': load['seconds'], 'binary_sha256': value['binary_sha256'],
                              **{key: value.get(key) for key in ('peak_memory_bytes', 'peak_rss_bytes', 'min_mem_available_bytes')}})
        if p4:
            scope_metrics[-1]['quiet_preflight'] = reference(scope['quiet_preflight'])
    validated, accepted, excluded = [], [], []
    for row in rows:
        result = row['result']
        if owners.get(row['scope_id']) != result['arm']:
            raise ValueError('Request arm must match its server scope')
        valid = eligible(row, prompt_hashes)
        validated.append(dict(row, valid=valid))
        lineage = dict(result=reference(row), request=reference(row['request_ref']), scope_id=row['scope_id'],
                       arm=result['arm'], prompt_tokens=result['prompt_tokens'], repeat=result['repeat'])
        if result['discard'] or not valid:
            excluded.append(dict(lineage, reason='warmup' if valid else 'request outside fixed workload'))
        else:
            accepted.append(dict(lineage, **{key: result.get(key) for key in ('ttft_s', 'decode_tps', 'output_sha256')},
                                 engine_prefill_ms=result['timings'].get('prompt_ms')))
    if not accepted:
        raise ValueError('No requests satisfy the fixed workload')
    blocks = p4_design(scopes, validated) if p4 else None
    draws = paired_draws(blocks) if blocks else None
    summaries = []
    for n in PROMPTS:
        arms = {}
        for arm in sorted(set(owners.values())):
            group = [row for row in accepted if row['arm'] == arm and row['prompt_tokens'] == n]
            if not group:
                continue
            ttft = [r['ttft_s'] for r in group]
            arms[arm] = dict(arm=arm, prompt_tokens=n, n=len(group), ttft_s=median(ttft),
                             range_s=[min(ttft), max(ttft)], output_hashes=sorted({r['output_sha256'] for r in group}),
                             source_artifacts=[r['result']['artifact_id'] for r in group])
            for metric in ('decode_tps', 'engine_prefill_ms'):
                values = [r[metric] for r in group if positive(r[metric])]
                arms[arm][metric] = median(values) if values else None
        index = {arm: {row['repeat']: row['ttft_s'] for row in accepted
                       if row['arm'] == arm and row['prompt_tokens'] == n} for arm in arms}
        samples = paired_samples(index, draws) if draws else None
        decode = {arm: {row['repeat']: row['decode_tps'] for row in accepted
                        if row['arm'] == arm and row['prompt_tokens'] == n} for arm in arms}
        for arm, cell in arms.items():
            comparisons = compare(cell, arms, samples)
            if draws and 'A+' in arms:
                comparisons['paired_ttft_seconds_saved_vs_Aplus'] = paired_changes(index, arm, 'A+', draws, blocks, -1)
                if all(positive(x) for label in (arm, 'A+') for x in decode[label].values()):
                    comparisons['paired_decode_tps_gained_vs_Aplus'] = paired_changes(decode, arm, 'A+', draws, blocks, 1)
            summaries.append(dict(cell, comparisons=comparisons))
    output = dict(schema='spark-gap-analysis/1', mode=mode, prompt_manifest=reference(manifest),
                scopes=scope_metrics, measurements=summaries, eligible=accepted, excluded=excluded,
                limitations=[
                    'Client TTFT measures wall time to first text or reasoning; engine prefill is an internal engine counter.',
                    'Sampled scope memory can omit final teardown and CUDA UMA may escape cgroup accounting.',
                    'Engine comparisons do not attribute changes to individual CCs without matched, activated candidate arms.',
                    ('P1 ran under concurrent work in contiguous batches and stock warm-up drifted; results are descriptive.'
                     if mode == 'p1-reconnaissance' else
                     'The paired bootstrap interval is conditional on two launches per arm and omits between-launch uncertainty.')])
    if mode == 'p4-build-overlap':
        from p4_build_overlap import classify_and_compare
        output['build_overlap'] = classify_and_compare(evidence, accepted)
        output['limitations'].append('The final A+ launch overlapped owner-authorized builds. Full-pair estimates and intervals are descriptive screening and do not adjust for the build lane.')
    return output


def main():
    try:
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('Evidence packet exceeds 8 MiB')
        packet = json.loads(raw)
        inputs = packet['inputs']
        analysis = analyze(inputs['evidence'])
        if packet['capability'] == 'analyze':
            outputs = {'analysis': analysis}
        elif packet['capability'] == 'verify':
            outputs = {'verification': {'done': analysis == inputs['analysis'],
                                        'method': 'exact deterministic recomputation from retained inputs'}}
        else:
            raise ValueError('Unsupported capability')
        reply = {'outcome': 'ok', 'outputs': outputs}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        reply = {'outcome': 'error', 'error': {'code': 'INVALID_EVIDENCE', 'message': str(exc)}}
    print(json.dumps(reply, allow_nan=False, sort_keys=True))


if __name__ == '__main__':
    main()
