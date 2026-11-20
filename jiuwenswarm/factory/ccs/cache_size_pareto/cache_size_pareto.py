"""Descriptive Pareto fronts from complete, provenance-bound cache launches."""
from collections import defaultdict
import hashlib
import json
import math
import re
from statistics import median


SIZES = (512, 2048)
TARGET_MIB = (15360, 30720, 46080)
ROLES = ('on', 'equivalent-stock', 'off')
SCHEDULE = [(size, phase, pair) for index in range(8)
            for size in (SIZES[::-1] if index in (2, 4, 6) else SIZES)
            for phase, pair in [('warmup', index + 1) if index < 3 else ('steady', index - 2)]]


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def evidence(value):
    if not value['artifact_id'] or not sha(value['sha256']):
        raise ValueError('Evidence must name a retained artifact and SHA-256')
    return value


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def interval(values):
    return dict(count=len(values), minimum=min(values), median=median(values), maximum=max(values))


def dominates(other, row):
    left, right = other['ttft_s']['median'], row['ttft_s']['median']
    faster, slower = other['decode_tokens_per_s']['median'], row['decode_tokens_per_s']['median']
    return left <= right and faster >= slower and (left < right or faster > slower)


def front(rows):
    return [row['arm_id'] for row in rows if not any(dominates(peer, row) for peer in rows)]


def admitted(launch):
    if launch['role'] not in ROLES or type(launch['requested_mib']) is not int or launch['requested_mib'] <= 0:
        raise ValueError('Expected a measured native bank role with an explicit integer budget')
    if not sha(launch['binary_sha256']) or not re.fullmatch('[0-9a-f]{40}', launch['source_commit']):
        raise ValueError('Missing native source or binary identity')
    for key in ('start', 'stop', 'scope', 'protocol', 'conditioning', 'log', 'load'):
        evidence(launch['receipts'][key])
    matching = launch['matching']
    if any(not sha(matching[key]) for key in ('model_sha256', 'regions_sha256', 'prompts_sha256', 'profile_family_sha256')):
        raise ValueError('Missing model, source regions, prompts or profile-family digest')
    if (not matching['common_argv'] or not matching['effective_settings'] or
            matching['source_reset'] != 'file-specific DONTNEED' or
            matching['scope_controls'] != dict(memory_max_bytes=100 * 1024**3, swap_max_bytes=0,
                                              oom_group=1, cpu_max='800000 100000', affinity=list(range(8)))):
        raise ValueError('Missing effective settings or validated matched runtime controls')
    if not positive(launch['allocated_mib']) or launch['allocated_mib'] > launch['requested_mib'] or not positive(launch['load_s']):
        raise ValueError('Missing observed bank allocation or startup time')
    seed = launch.get('seed_startup')
    if launch['role'] == 'on':
        if (not isinstance(seed, dict) or any(not positive(seed[key]) for key in ('seeds', 'initial_h2d_bytes', 'init_us', 'charged_bound')) or
                not seed['initial_h2d_bytes'] <= seed['charged_bound'] <= launch['requested_mib'] * 1024**2):
            raise ValueError('Profile-on arm lacks an observed and bounded seed startup')
    elif seed is not None:
        raise ValueError('The native control has an unexpected seed startup receipt')
    rows = launch['samples']
    if len(rows) != 16:
        raise ValueError('Complete sixteen-position receipt required')
    hashes = {}
    requests = set()
    for position, (row, (size, phase, pair)) in enumerate(zip(rows, SCHEDULE), 1):
        if (row['position'], row['prompt_tokens'], row['phase'], row['pair'], row['discard']) != (
                position, size, phase, pair, phase == 'warmup'):
            raise ValueError('Measured position, warmup status or request size differs from the verified protocol')
        result_ref = evidence(row['result'])['sha256']
        pair_hash = row['greedy_hashes']
        if (result_ref in requests or not all(positive(row[key]) for key in ('ttft_s', 'decode_tps')) or
                len(pair_hash) != 2 or not all(map(sha, pair_hash)) or hashes.setdefault(str(size), pair_hash) != pair_hash):
            raise ValueError('Repeated request receipt, invalid measurement or greedy instability within launch')
        requests.add(result_ref)
    return hashes


def summarize(packet):
    if packet['schema'] != 'spark-cache-pareto-input/1' or not packet['sources']:
        raise ValueError('Provide a verified cache launch evidence packet')
    groups = defaultdict(lambda: defaultdict(list))
    designs = {}
    seen = set()
    for src in packet['sources']:
        evidence(src['analysis'])
        evidence(src['verification'])
        if not src['scope_authority'] or not src['launches']:
            raise ValueError('A source needs verified launch receipt provenance')
        for launch in src['launches']:
            outputs = admitted(launch)
            stop = launch['receipts']['stop']['sha256']
            if stop in seen:
                raise ValueError('A launch appears more than once across input sources')
            seen.add(stop)
            design = dict(launch=launch['matching'], greedy_hashes=outputs)
            group = identity(design)
            designs[group] = design
            key = tuple(launch[k] for k in ('role', 'requested_mib', 'allocated_mib', 'source_commit', 'binary_sha256'))
            groups[group][key].append(launch)
    cohorts = []
    for cohort, cells in sorted(groups.items()):
        arms = []
        for (role, requested, allocated, commit, binary), launches in sorted(cells.items()):
            samples = [row for launch in launches for row in launch['samples'] if row['phase'] == 'steady']
            seed = [x['seed_startup'] for x in launches if x.get('seed_startup')]
            arms.append(dict(arm_id=identity([cohort, role, requested, allocated, commit, binary])[:16], role=role,
                             requested_mib=requested, allocated_mib=allocated, binary_sha256=binary, source_commit=commit,
                             requested_sweep=requested in TARGET_MIB, launch_count=len(launches),
                             launches=[dict(label=x['label'], receipts=x['receipts']) for x in launches],
                             startup=dict(load_to_ready_s=interval([x['load_s'] for x in launches]),
                                          seed_init_s=interval([x['init_us'] / 1e6 for x in seed]) if seed else None,
                                          seeded_experts=interval([x['seeds'] for x in seed]) if seed else None,
                                          seed_h2d_bytes=interval([x['initial_h2d_bytes'] for x in seed]) if seed else None,
                                          charged_bound_bytes=interval([x['charged_bound'] for x in seed]) if seed else None),
                             measurements={str(size): dict(ttft_s=interval([r['ttft_s'] for r in samples if r['prompt_tokens'] == size]),
                                               decode_tokens_per_s=interval([r['decode_tps'] for r in samples if r['prompt_tokens'] == size]))
                                           for size in SIZES}))
        capacity = []
        for budget in TARGET_MIB:
            treated = [arm for arm in arms if arm['requested_mib'] == budget and arm['role'] == 'on']
            controls = [arm for arm in arms if arm['requested_mib'] == budget and arm['role'] != 'on']
            matched = []
            for arm in treated:
                equal = [c for c in controls if c['allocated_mib'] == arm['allocated_mib']]
                stock_ids = [c['arm_id'] for c in equal if c['role'] == 'equivalent-stock']
                off_ids = [c['arm_id'] for c in equal if c['role'] == 'off' and c['binary_sha256'] == arm['binary_sha256']]
                matched.append(dict(treatment_id=arm['arm_id'], stock_ids=stock_ids, off_ids=off_ids,
                                    stock_status='matched' if stock_ids else 'absent',
                                    off_status='matched' if off_ids else 'absent'))
            capacity.append(dict(requested_mib=budget, treatment_status='measured' if treated else 'absent',
                stock_status='measured' if any(x['role'] == 'equivalent-stock' for x in controls) else 'absent',
                off_status='measured' if any(x['role'] == 'off' for x in controls) else 'absent',
                same_allocation_controls=matched))
        fronts = []
        for size in SIZES:
            rows = [dict(arm_id=arm['arm_id'], requested_sweep=arm['requested_sweep'], **arm['measurements'][str(size)]) for arm in arms]
            fronts.append(dict(prompt_tokens=size, all_measured=front(rows), requested_sweep=front([r for r in rows if r['requested_sweep']])))
        cohorts.append(dict(matched_cohort_sha256=cohort, matched_design=designs[cohort], arms=arms,
                            requested_capacity_coverage=capacity, fronts=fronts))
    return dict(schema='spark-cache-pareto/1', kind='analysis', input_sha256=identity(packet),
                summary='Measured cache arms are compared on TTFT and decode separately for each prompt length.',
                units=dict(ttft='seconds', decode='tokens/second', capacity='MiB (2^20 bytes)', startup='seconds'),
                sources=[dict({key: source[key] for key in ('analysis', 'verification', 'scope_authority')},
                              exclusions=source.get('exclusions', [])) for source in packet['sources']],
                cohorts=cohorts, limitations='Descriptive sample medians and observed min/max. No timing effect, uncertainty interval, scalar ranking, or inference for absent cells. Startup is separate from the Pareto criteria.')
