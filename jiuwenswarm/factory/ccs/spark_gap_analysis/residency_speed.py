"""Verify the quiet native cache preseed experiment and summarize its paired observations."""
from base64 import b64decode
import gzip
import hashlib
from io import BytesIO
import re
from statistics import median

from early_bracket import (PROMPTS, check_requests, check_server, reject_if,
                           residency_identity, timestamp)
WARMUP_PILOT = ((30720, 'on'), (30720, 'equivalent-stock'))
REFERENCE = ((30720, 'stock'), (0, 'strata'))
STEADY_LAB = ((30720, 'stock'), (61440, 'on'), (0, 'strata'), (30720, 'on'),
              (30720, 'equivalent-stock'), (61440, 'equivalent-stock'))
ORDER = ((0, 512), (0, 2048), (1, 512), (1, 2048), (2, 2048), (2, 512), (3, 512), (3, 2048))
PROFILE_MARKER = 'expert_weight_cache_native_profile:'
NATIVE_STATS = re.compile(r'llama_moe_cache: ubatch <= 8: hits = (\d+), misses = (\d+) \((\d+) on the CPU\), '
                          r'hit rate = ([\d.]+)%, uploaded = ([\d.]+) MiB')
D2D_STATS = re.compile(r'llama_moe_cache: large batches: (\d+) experts copied from the cache, ([\d.]+) MiB')
BANK = re.compile(r'CUDA0 MoE cache size = ([\d.]+) MiB for ([\d.]+) MiB of host experts, ([\d.]+)% of the misses on the CPU')
LOG_LIMIT = 8 * 1024**2


def captured_log(entry):
    with gzip.GzipFile(fileobj=BytesIO(b64decode(entry['gzip_b64'], validate=True))) as stream:
        data = stream.read(LOG_LIMIT + 1)
    reject_if(len(data) > LOG_LIMIT or hashlib.sha256(data).hexdigest() != entry['sha256'],
              'Engine log differs from the exact retained byte receipt')
    return data.decode(errors='replace')


def span(values):
    return dict(median=median(values), min=min(values), max=max(values), samples=values)


def boundaries(row, pid, comm='llama-server'):
    snapshots = row['request_resources']['value']['snapshots']
    phases = ('start', 'first_token', 'end')
    if pid is None:
        candidates = [key for key, val in snapshots['start']['processes'].items() if val['comm'] == comm]
        reject_if(len(candidates) != 1, 'Cannot identify the unique Strata engine process inside the scope')
        pid = candidates[0]
    task = [snapshots[phase]['processes'][str(pid)] for phase in phases]
    reject_if(any(p['comm'] != comm for p in task) or len({p['starttime_ticks'] for p in task}) != 1,
              'Request counters do not use the same engine process')
    times = [snapshots[phase]['monotonic_ns'] for phase in phases]
    reject_if(not times[0] < times[1] < times[2], 'Request counter phase timestamps are not ordered')
    metrics = {
        'process_read_bytes': [p['io']['read_bytes'] for p in task],
        'process_major_faults': [p['majflt'] for p in task],
        'cgroup_file_refaults': [snapshots[phase]['memory_stat']['workingset_refault_file'] for phase in phases],
    }
    reject_if(any(not 0 <= values[0] <= values[1] <= values[2] for values in metrics.values()),
              'Request phase counts decreased or are incomplete')
    phases = {label: {key: values[i + 1] - values[i] for key, values in metrics.items()}
              for i, label in enumerate(('start_to_first_token', 'first_token_to_end'))}
    disks = [snapshots[phase]['host_disks'] for phase in ('start', 'first_token', 'end')]
    for disk in sorted(set.intersection(*(set(d) for d in disks))):
        samples = [d[disk] for d in disks]
        if len({value['dev'] for value in samples}) != 1:
            continue
        values = [value['read_bytes'] for value in samples]
        if 0 <= values[0] <= values[1] <= values[2]:
            for i, phase in enumerate(phases.values()):
                phase.setdefault('host_nvme_read_bytes', {})[f"{disk} ({samples[0]['dev']})"] = values[i + 1] - values[i]
    return dict(phases=phases, process=dict(pid=int(pid), comm=comm, starttime_ticks=task[0]['starttime_ticks']))


def server_counters(log, mode, budget, scope, expected, reference):
    ran = 'probe' in scope
    active = re.findall(r'expert_weight_cache_native_profile: active (.+)', log)
    stats = re.findall(r'expert_weight_cache_native_profile: stats (.+)', log)
    reasons = re.findall(r'expert_weight_cache_native_profile: inactive \((.+)\)', log)
    native, d2d = NATIVE_STATS.findall(log), D2D_STATS.findall(log)
    bank = BANK.findall(log)
    if mode != 'on':
        reject_if(PROFILE_MARKER in log, 'Profile log markers appeared in a control')
    if not ran:
        reject_if(mode != 'on' or not reasons or active or scope['requests'],
                  'Missing observations are not explained by a clean profile decline')
        return dict(status='declined', reasons=reasons)
    counters = dict(status='completed')
    if mode in ('stock', 'strata'):
        reject_if(native or d2d or bank, 'The reference unexpectedly logged a llama.cpp native cache')
    else:
        reject_if(len(native) != 1 or len(d2d) != 1 or len(bank) != 1, 'Expected native-bank allocation and shutdown counters')
        allocated, host_experts, cpu_share = map(float, bank[0])
        reject_if(not 0 < allocated <= budget or host_experts <= 0 or cpu_share != 0,
                  'Actual native bank exceeds the admitted budget or changes the CPU miss policy')
        hits, misses, cpu, rate, mib = native[0]
        counters['native_bank'] = dict(allocated_mib=allocated, host_experts_mib=host_experts,
                                      hits=int(hits), misses=int(misses), cpu_misses=int(cpu),
                                      hit_rate_pct=float(rate), uploaded_mib=float(mib),
                                      large_batch_d2d_experts=int(d2d[0][0]), large_batch_d2d_mib=float(d2d[0][1]))
    if mode == 'on':
        reject_if(len(active) != 1 or len(stats) != 1 or reasons, 'The treatment did not establish measured profile activity')
        init, summary = ({key: int(value) for key, value in re.findall(r'(\w+)=(\d+)\b', entry)}
                         for entry in (active[0], stats[0]))
        fields = {'seeds', 'initial_h2d_bytes', 'init_us', 'charged_bound'}
        reject_if(set(init) != fields | {'reverse_rank'} or not all(init.values()) or summary['active'] != 1 or
                  init['charged_bound'] > budget * 1024**2 or
                  init['initial_h2d_bytes'] > init['charged_bound'] or any(summary[k] != init[k] for k in fields) or
                  'policy=stock_evictable reverse_rank=1' not in active[0], 'Profile activation and final byte ledger disagree')
        receipt = scope['activation']
        reject_if(receipt['value']['sha256'] != expected['profile_sha256'] or
                  not active[0].startswith(receipt['value']['marker'].split('active ', 1)[-1]),
                  'Activation receipt does not bind the logged preseed and nominated profile')
        counters.update(profile=summary, activation_receipt=reference(receipt))
    return counters


def comparison(candidate, control):
    comparisons = []
    for size in PROMPTS:
        on = [row for row in candidate['samples'] if row['prompt_tokens'] == size and not row['discard']]
        off = [row for row in control['samples'] if row['prompt_tokens'] == size and not row['discard']]
        pairs = list(zip(on, off))
        assert len(pairs) == 3
        comparisons.append(dict(
            prompt_tokens=size, n_pairs=len(pairs), greedy_parity=candidate['greedy_hashes'][str(size)] == control['greedy_hashes'][str(size)],
            control_ttft_s=span([b['ttft_s'] for _, b in pairs]),
            candidate_ttft_s=span([a['ttft_s'] for a, _ in pairs]),
            ttft_saved_s=span([b['ttft_s'] - a['ttft_s'] for a, b in pairs]),
            ttft_saved_pct=span([100 * (1 - a['ttft_s'] / b['ttft_s']) for a, b in pairs]),
            control_decode_tps=span([b['decode_tps'] for _, b in pairs]),
            candidate_decode_tps=span([a['decode_tps'] for a, _ in pairs]),
            decode_gain_tps=span([a['decode_tps'] - b['decode_tps'] for a, b in pairs]),
            decode_gain_pct=span([100 * (a['decode_tps'] / b['decode_tps'] - 1) for a, b in pairs]),
        ))
    return comparisons


def analyze(evidence, eligible, reference, positive):
    sources, expected = evidence['scopes'], evidence['expected']
    reject_if(len(sources) != len(WARMUP_PILOT) or len(expected) != len(WARMUP_PILOT),
              'Expected both ordered 30-GiB warm-up pilot scopes')
    prompts = {p['target_tokens_including_template']: p['prompt_sha256'] for p in evidence['prompts']['value']['prompts']}
    reject_if(set(prompts) != set(PROMPTS), 'Expected the approved two fixed prompt sizes')
    first_source = sources[0]['conditioning']['value']['after']
    source_id = residency_identity(first_source)
    pin = evidence['model_identity']['value']['files']
    reject_if([(f['path'], f['identity']['size'], f['identity']['mtime_ns']) for f in first_source['views']['llama']['files']] !=
              [(f['path'], f['size'], f['mtime_ns']) for f in pin], 'Sampled source files differ from the model identity receipt')
    results, last = [], None
    for (mib, mode), scope, profile in zip(WARMUP_PILOT, sources, expected):
        label, began, ready, ended, record = check_server(scope, mode, 'C3', profile, reference, window='speed')
        condition = scope['conditioning']['value']
        reject_if(last is not None and (began <= last or timestamp(condition['before']['started']) <= last), 'Launch or conditioning overlaps')
        reject_if(set(condition['after']['views']) != {'llama', 'strata'} or any(
            set(view['total']) != {'expert', 'dense', 'engram'} or any(
                item['estimated_resident_fraction'] != 0 for item in view['total'].values())
            for view in condition['after']['views'].values()), 'Pilot scope began with warm sampled source pages')
        reject_if(scope['quiet']['value']['mem_available_gib'] < 110 or
                  any(residency_identity(condition[boundary]) != source_id for boundary in ('before', 'after')),
                  'Prelaunch headroom or source device, inode and sampling identity failed')
        last = ended
        record.update(budget_mib=mib if mode != 'stock' else 0, mode=mode,
                      **server_counters(captured_log(scope['log']), mode, mib, scope, profile, reference))
        if record['status'] == 'completed':
            checked, hashes = check_requests(scope, label, ready, ended, prompts, source_id, eligible, reference, positive, orders=ORDER)
            pid = scope['scope']['value']['pid']
            for sample, row in zip(checked, scope['requests']):
                sample.update(boundaries(row, pid))
            reject_if(any(sample['process'] != checked[0]['process'] for sample in checked),
                      'Engine identity changed across pilot requests')
            record.update(samples=checked, greedy_hashes=hashes)
        results.append(record)
    candidate, control = results
    if candidate['status'] == 'completed':
        reject_if(candidate['native_bank']['allocated_mib'] != control['native_bank']['allocated_mib'],
                  'Pilot arms did not allocate the same native bank within log precision')
    paired = comparison(candidate, control) if candidate['status'] == 'completed' else []
    positions = []
    for i, (a, b) in enumerate(zip(candidate.get('samples', []), control['samples']), 1):
        size = a['prompt_tokens']
        phase_a, phase_b = a['phases']['start_to_first_token'], b['phases']['start_to_first_token']
        positions.append(dict(position=i, prompt_tokens=size, ttft_saved_s=b['ttft_s'] - a['ttft_s'],
            decode_gain_tps=a['decode_tps'] - b['decode_tps'],
            read_bytes_saved_to_first_token=phase_b['process_read_bytes'] - phase_a['process_read_bytes'],
            major_faults_avoided_to_first_token=phase_b['process_major_faults'] - phase_a['process_major_faults'],
            greedy_parity=candidate['greedy_hashes'][str(size)] == control['greedy_hashes'][str(size)]))
    return dict(mode='c3-warmup-pilot', scopes=results, matched_warmup_pairs=paired, matched_positions=positions,
                source_identity=reference(evidence['model_identity']), profile=reference(evidence['profile']))


def steady_order():
    schedule = []
    for index in range(8):
        measured = index >= 3
        pair = index - 2 if measured else index + 1
        sizes = (2048, 512) if index in (2, 4, 6) else (512, 2048)
        for size in sizes:
            name = f'rep-{pair}-{size}' if measured else f'warmup-{pair}-{size}'
            schedule.append(dict(position=len(schedule) + 1, phase='steady' if measured else 'warmup',
                                 pair=pair, repeat=pair if measured else 0, size=size, path=name))
    return schedule


def trends(rows):
    trends_by_size = {}
    for size in PROMPTS:
        repeats = [r for r in rows if r['prompt_tokens'] == size and r['phase'] == 'steady']
        trends_by_size[str(size)] = {
            metric: dict(span([row[metric] for row in repeats]),
                         last_minus_first=repeats[-1][metric] - repeats[0][metric])
            for metric in ('ttft_s', 'decode_tps')
        }
        trends_by_size[str(size)]['phase_counters'] = {
            phase: {metric: span([row['phases'][phase][metric] for row in repeats])
                    for metric in ('process_read_bytes', 'process_major_faults', 'cgroup_file_refaults')}
            for phase in ('start_to_first_token', 'first_token_to_end')
        }
    return trends_by_size


def paired_results(candidate, control):
    cold, steady = [], []
    for a, b in zip(candidate['samples'], control['samples']):
        reject_if(a['position'] != b['position'] or a['phase'] != b['phase'] or a['pair'] != b['pair'] or
                  a['prompt_tokens'] != b['prompt_tokens'], 'Comparisons require matching positions and prompt size')
        row = dict(position=a['position'], pair=a['pair'], prompt_tokens=a['prompt_tokens'],
                   greedy_parity=a['greedy_hashes'] == b['greedy_hashes'],
                   ttft_saved_s=b['ttft_s'] - a['ttft_s'], ttft_saved_pct=100 * (1 - a['ttft_s']/b['ttft_s']),
                   decode_gain_tps=a['decode_tps'] - b['decode_tps'], decode_gain_pct=100 * (a['decode_tps']/b['decode_tps'] - 1))
        if a['phase'] == 'warmup':
            row['counters_avoided'] = {
                phase: {key: b['phases'][phase][key] - a['phases'][phase][key]
                        for key in ('process_read_bytes', 'process_major_faults', 'cgroup_file_refaults')}
                for phase in ('start_to_first_token', 'first_token_to_end')
            }
            cold.append(row)
        else:
            steady.append(row)
    estimates = []
    for size in PROMPTS:
        pairs = [r for r in steady if r['prompt_tokens'] == size]
        reject_if(len(pairs) != 5, 'Steady comparison requires five same-position pairs per size')
        estimates.append(dict(
            prompt_tokens=size, n=len(pairs), greedy_parity=all(r['greedy_parity'] for r in pairs),
            pairs=pairs, **{metric: span([r[metric] for r in pairs]) for metric in (
                'ttft_saved_s', 'ttft_saved_pct', 'decode_gain_tps', 'decode_gain_pct')},
        ))
    return dict(cold_pairs=cold, steady=estimates)


def analyze_steady(evidence, eligible, reference, positive):
    direct = evidence['mode'] == 'a-s-cold-steady'
    scope_order = REFERENCE if direct else STEADY_LAB
    reject_if(len(evidence['scopes']) != len(scope_order) or len(evidence['expected']) != len(scope_order),
              'Expected all declared cold and steady scopes for the comparison')
    schedule = steady_order()
    prompts = {p['target_tokens_including_template']: p['prompt_sha256'] for p in evidence['prompts']['value']['prompts']}
    reject_if(set(prompts) != set(PROMPTS), 'Expected the approved two prompt sizes')
    conditioning = evidence['scopes'][0]['conditioning']['value']['after']
    fingerprint = {view: residency_identity(conditioning, view) for view in ('llama', 'strata')}
    pin = evidence['model_identity']['value']['files']
    reject_if([(f['path'], f['identity']['size'], f['identity']['mtime_ns']) for f in conditioning['views']['llama']['files']] !=
              [(f['path'], f['size'], f['mtime_ns']) for f in pin], 'GGUF source fingerprint differs from the model receipt')
    ordered, previous, runtime = {}, None, None
    for (budget, mode), scope, expected in zip(scope_order, evidence['scopes'], evidence['expected']):
        is_strata = mode == 'strata'
        view = 'strata' if is_strata else 'llama'
        label, began, ready, ended, record = check_server(scope, mode, 'S' if is_strata else 'C3',
                                                         expected, reference, window='steady' if is_strata else 'speed')
        condition = scope['conditioning']['value']
        reject_if(previous is not None and (timestamp(condition['before']['started']) <= previous or began <= previous),
                  'Declared launches or source conditioning overlap')
        reject_if(scope['quiet']['value']['mem_available_gib'] < 110 or
                  any(residency_identity(condition[s], v) != fingerprint[v] for s in ('before', 'after') for v in fingerprint),
                  'Source device, inode, sample geometry or quiet headroom differs between runs')
        after = condition['after']['views']
        reject_if(set(after) != set(fingerprint) or any(
            set(value['total']) != {'expert', 'engram', 'dense'} or any(
                record['estimated_resident_fraction'] != 0 for record in value['total'].values())
            for value in after.values()), 'There was sampled source residency before launch')
        previous = ended
        if not is_strata:
            settings = (record['effective_settings'], record['runtime_environment'])
            if runtime is None:
                runtime = settings
            reject_if(settings != runtime, 'llama.cpp effective settings differ apart from the named cache treatment')
        counters = server_counters(captured_log(scope['log']), mode, budget, scope, expected, reference)
        record.update(budget_mib=budget if mode not in ('stock', 'strata') else 0, mode=mode,
                      source_view=view, **counters)
        ordered[(budget, mode)] = record
        if counters['status'] == 'declined':
            continue
        protocol = scope['protocol']['value']
        reject_if(protocol['schema'] != 'spark-cold-steady/1' or protocol['arm'] != label or protocol['view'] != view or
                  protocol['source_reset'] != 'file-specific DONTNEED' or protocol['regions_sha256'] != evidence['regions']['sha256'] or
                  protocol['warmups_per_size'] != 3 or protocol['measured_per_size'] != 5 or
                  protocol['ordered_requests'] != schedule, 'Client protocol receipt disagrees with the approved order or source')
        record['protocol'] = reference(scope['protocol'])
        requests = [dict(row, discard=row['phase'] == 'warmup', residency=True) for row in schedule]
        samples, hashes = check_requests(scope, label, ready, ended, prompts, fingerprint[view],
                                         eligible, reference, positive, view=view, protocol=requests)
        reject_if(hashes != scope['probe']['value']['greedy_hashes'], 'Greedy output sequence differs from its completed probe receipt')
        for slot, sample, row in zip(schedule, samples, scope['requests']):
            process = boundaries(row, None if is_strata else scope['scope']['value']['pid'],
                                 'strata-dsv41' if is_strata else 'llama-server')
            sample.update(position=slot['position'], pair=slot['pair'], phase=slot['phase'],
                          greedy_hashes=[row[k]['sha256'] for k in ('output', 'reasoning')], **process)
        reject_if(any(sample['process'] != samples[0]['process'] for sample in samples),
                  'The underlying engine process changed across one launch')
        record.update(samples=samples, steady_trend=trends(samples), greedy_hashes=hashes)
    comparisons = []
    stock, strata = (30720, 'stock'), (0, 'strata')
    on30, on60 = (30720, 'on'), (61440, 'on')
    pairs = ((strata, stock, 'fair Strata engine and pack versus A-matched'),) if direct else (
        (on30, (30720, 'equivalent-stock'), '30-GiB profile versus the same-budget stock bank'),
        (on60, (61440, 'equivalent-stock'), '60-GiB profile versus the same-budget stock bank'),
        (on30, stock, '30-GiB profile and bank versus stock without a native bank'),
        (on60, stock, '60-GiB profile and bank versus stock without a native bank'),
        (on30, strata, '30-GiB profile versus fair Strata engine and pack'),
        (on60, strata, '60-GiB profile versus fair Strata engine and pack'),
    )
    for candidate, control, relation in pairs:
        a, b = ordered[candidate], ordered[control]
        if a['status'] == b['status'] == 'completed':
            if a['budget_mib'] and a['budget_mib'] == b['budget_mib']:
                reject_if(a['native_bank']['allocated_mib'] != b['native_bank']['allocated_mib'],
                          'Matched arms do not have the same native bank allocation within log precision')
            comparisons.append(dict(candidate=a['arm'], control=b['arm'], relation=relation, **paired_results(a, b)))
    result = dict(mode=evidence['mode'], scopes=list(ordered.values()), comparisons=comparisons,
                  source_identity=reference(evidence['model_identity']), source_regions=reference(evidence['regions']))
    if not direct:
        result['profile'] = reference(evidence['profile'])
    return result
