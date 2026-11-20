"""Admission and descriptive estimates for one early stock/candidate/stock bracket."""
from datetime import datetime
import re


PROMPTS = (512, 2048)
PROCESSES = ('build_processes', 'model_processes', 'factory_controllers', 'test_processes')
GIB = 1024**3
GATES = {
    'C1': 'LLAMA_EVENT_REC', 'C2': 'LLAMA_PLACEMENT_PLAN', 'C3': 'LLAMA_EXPERT_CACHE',
    'C4': 'LLAMA_EXPERT_PREDICT', 'C5': 'LLAMA_BATCH_LAYOUT',
}


def reject_if(predicate, message):
    if predicate:
        raise ValueError(message)


def check_resources(value):
    reject_if(any(value[key] for key in PROCESSES), 'Competing job found in a retained boundary check')
    reject_if(value['mem_available_gib'] < 8 or unsafe_memory(value.get('memory_events', {})), 'Unexpected memory event')


def unsafe_memory(events):
    return any(int(events.get(name, 0)) for name in ('oom', 'oom_kill', 'oom_group_kill'))


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    reject_if(parsed.tzinfo is None, 'Early benchmark timestamps need a timezone')
    return parsed


def check_server(scope, mode, cc, expected, reference, window='early'):
    start, stop, kernel = (scope[name]['value'] for name in ('start', 'stop', 'scope'))
    probe = scope['probe']['value']
    label = expected.get('label', f'{cc}-{mode}-early')
    reject_if(probe['cc'] != cc or probe['window'] != window or probe['mode'] != expected.get('probe_mode', mode),
              'Wrong probe arm or order')
    reject_if(start['arm'] != label or stop['arm'] != label or probe['result_dir'] != start['result_path'], 'Scope arm or result path mismatch')
    reject_if(stop['binary_sha256'] != start['binary_sha256'] or stop['command'] != start['command'] or
              stop['start'] != start['start'] or stop['unit'] != start['unit'], 'Scope start/stop disagree')
    reject_if(start['command'] != expected['command'] or start['binary_sha256'] != expected['binary_sha256'] or
              scope['load']['value']['source_commit'] != expected['source_commit'], 'Launch disagrees with the pinned build or matched flags')
    reject_if(scope['load']['value'].get('products_manifest_sha256') != expected['products_manifest_sha256'],
              'Launch receipt differs from the selected build inventory')
    environment = start['launch_environment']
    gates = {key: val for key, val in environment.items() if key.startswith('LLAMA_')}
    expected_gates = dict(expected['gates'])
    if cc == 'C1' and mode == 'on':
        expected_gates[GATES[cc]] = start['result_path'].rstrip('/') + '/events.jsonl'
    reject_if(gates != expected_gates or environment.get('LD_LIBRARY_PATH') != expected['library_path'], 'Gate or library setting differs from the profile')
    reject_if(stop['returncode'] or stop['reason'] or stop['scope_verified'] is not True or unsafe_memory(stop['memory_events']) or
              'Result=oom-kill' in stop.get('systemd_properties', '') or stop['min_mem_available_bytes'] < 8 * GIB,
              'Scope ended on a safety event or abnormal exit')
    controls = {'memory.max': str(100 * GIB), 'memory.swap.max': '0', 'memory.oom.group': '1',
                'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}
    reject_if(start['memory_max'] != 100 * GIB or start['cpus'] != '0-7' or
              any(kernel['actual'].get(k) != v for k, v in controls.items()), 'Scope does not prove the 100 GiB/eight-CPU controls')
    ready = timestamp(scope['load']['value']['ready_at'])
    began, ended = timestamp(start['start']), timestamp(stop['stop'])
    summary = {key: reference(scope[key]) for key in ('start', 'stop', 'scope', 'load', 'probe', 'log')}
    summary.update(arm=label, peak_memory_bytes=stop['peak_memory_bytes'],
                   min_mem_available_bytes=stop['min_mem_available_bytes'],
                   reclaim_max=int(stop['memory_events'].get('max', 0)), load_s=scope['load']['value']['health_elapsed_s'])
    reject_if(not began < ready < ended, 'Scope timestamps are not ordered')
    if window == 'functional':
        return label, began, ready, ended, summary
    quiet, conditioned = scope['quiet']['value'], scope['conditioning']['value']
    reject_if(not quiet['quiet'] or quiet['load_1m'] >= 1 or not conditioned['quiet']['quiet'], 'Quiet prelaunch was not established')
    check_resources(quiet)
    reject_if(conditioned['schema'] != 'spark-source-cache-conditioning/1' or
              conditioned['method'] != 'file-specific POSIX_FADV_DONTNEED' or
              not timestamp(conditioned['after']['completed']) <= timestamp(scope['quiet']['mtime_utc']) <= began < ready < ended,
              'File-specific conditioning or ordered scope times are missing')
    summary.update(quiet=reference(scope['quiet']), conditioning=reference(scope['conditioning']))
    summary['runtime_environment'] = {k: v for k, v in environment.items() if not k.startswith('LLAMA_') and k != 'LD_LIBRARY_PATH'}
    runtime_settings = scope['log']['effective_settings']
    required = {'n_ctx', 'n_ctx_seq', 'n_batch', 'n_ubatch', 'n_slots', 'n_threads', 'n_threads_batch'}
    reject_if(set(runtime_settings) != required or any(type(v) is not int or v < 1 for v in runtime_settings.values()),
              'Engine log did not establish the effective runtime settings')
    summary['effective_settings'] = runtime_settings
    residency = conditioned['after']['views']['llama']['total']
    summary['prelaunch_source_fractions'] = {k: v['estimated_resident_fraction'] for k, v in residency.items()}
    return label, began, ready, ended, summary


def residency_identity(sample):
    return (sample['page_size'], sample['pages_per_sample'], sample['seed'],
            [(item['resolved_path'], item['identity']) for item in sample['views']['llama']['files']])


def check_requests(scope, label, ready, ended, prompt_hashes, source_identity, eligible, reference, positive):
    orders = [(0, 512), (0, 2048), (1, 512), (1, 2048)]
    reject_if(len(scope['requests']) != len(orders), 'Early scope needs two warmups followed by two measured requests')
    checked, previous, greedy = [], ready, {}
    for row, (repeat, size) in zip(scope['requests'], orders):
        result, request = row['result']['value'], row['request']['value']
        now = timestamp(result['started'])
        reject_if(result['arm'] != label or (result['repeat'], result['prompt_tokens']) != (repeat, size) or
                  result['discard'] is not (repeat == 0) or not previous <= now < ended,
                  'Early request order, scope, or timestamp mismatch')
        reject_if(not eligible(dict(request=request, result=result), prompt_hashes) or
                  not positive(result['decode_tps']) or request.get('chat_template_kwargs') != {'enable_thinking': False},
                  'Fixed prompt, output length, cache, template or client timing requirement failed')
        hashes = [row[name]['sha256'] for name in ('output', 'reasoning')]
        reject_if(hashes != [result['output_sha256'], result['reasoning_sha256']] or hashes != greedy.setdefault(size, hashes),
                  'Greedy outputs drifted or artifact bytes differ')
        for state in ('before', 'after'):
            check_resources(row[state]['value'])
        before, after = (timestamp(row[x]['value']['observed_utc']) for x in ('before', 'after'))
        reject_if(not previous <= before <= now < after < ended, 'Resource snapshots must surround the request in its scope')
        resources = row['request_resources']
        reject_if(resources['sha256'] != result['resource_windows_sha256'] or resources['value']['schema'] != 'spark-request-resources/1' or
                  set(resources['value']['snapshots']) != {'start', 'first_token', 'end'} or
                  resources['value']['cgroup'] != scope['scope']['value']['cgroup'], 'Request phase counters do not match their source scope/result')
        fields = ('result', 'request', 'before', 'after', 'request_resources', 'output', 'reasoning', 'response')
        record = dict(repeat=repeat, prompt_tokens=size, discard=repeat == 0, ttft_s=result['ttft_s'],
                      decode_tps=result['decode_tps'], evidence={name: reference(row[name]) for name in fields})
        if repeat:
            residency = row['residency']['value']
            reject_if(residency['schema'] != 'spark-source-residency/1' or not before <= timestamp(residency['completed']) <= now or
                      residency.get('scope_accounting', {}).get('path') != scope['scope']['value']['cgroup'] or
                      residency_identity(residency) != source_identity,
                      'Page residency has a mismatched inode/sampling profile, timestamp or scope')
            record['evidence']['residency'] = reference(row['residency'])
            record['source_fractions'] = {k: v['estimated_resident_fraction'] for k, v in residency['views']['llama']['total'].items()}
        checked.append(record)
        previous = after
    reject_if(scope['probe']['value']['greedy_hashes'] != {str(size): greedy[size] for size in PROMPTS}, 'Greedy proof differs from probe receipt')
    return checked, {str(size): hashes for size, hashes in greedy.items()}


def endpoint_relation(candidate, lower, upper):
    return ('lower than both stock endpoints' if candidate < lower else
            'higher than both stock endpoints' if candidate > upper else
            'within the stock endpoint range')


def analyze(evidence, eligible, reference, positive):
    cc, profiles = evidence['cc'], evidence['expected']
    stock_mode = profiles['stock_mode']
    nested = profiles.get('nested_strict', False)
    reject_if(cc not in GATES or stock_mode not in ('stock', 'equivalent-stock') or (stock_mode == 'equivalent-stock' and cc != 'C2'),
              'Early bracket arm or stock comparator is unsupported')
    scopes = evidence['scopes']
    reject_if(nested and cc != 'C5', 'Nested settings comparison is only admitted for C5')
    order = ('strict-stock', stock_mode, 'on', stock_mode, 'strict-stock') if nested else (stock_mode, 'on', stock_mode)
    reject_if(len(scopes) != len(order), 'Early timing needs the complete ordered bracket')
    prompt_manifest = evidence['prompt_manifest']
    prompt_hashes = {p['target_tokens_including_template']: p['prompt_sha256'] for p in prompt_manifest['value']['prompts']}
    reject_if(set(prompt_hashes) != set(PROMPTS), 'Expected approved 512 and 2048 prompt identities')
    ready_scopes, previous_stop = [], None
    source_identity = residency_identity(scopes[0]['conditioning']['value']['after'])
    source_files = scopes[0]['conditioning']['value']['after']['views']['llama']['files']
    retained = evidence['model_identity']['value']['files']
    ids = [(item['path'], item['identity']['size'], item['identity']['mtime_ns']) for item in source_files]
    reject_if(ids != [(item['path'], item['size'], item['mtime_ns']) for item in retained],
              'Source sampling does not match the pinned model receipt')
    for scope, mode in zip(scopes, order):
        label, began, ready, ended, summary = check_server(scope, mode, cc, profiles[mode], reference)
        reject_if(previous_stop is not None and (began <= previous_stop or
                   timestamp(scope['conditioning']['value']['before']['started']) <= previous_stop),
                  'Launches or their file-conditioning windows overlap')
        conditioning = scope['conditioning']['value']
        reject_if(any(residency_identity(conditioning[key]) != source_identity for key in ('before', 'after')),
                  'Scope conditioning does not use the matched model inodes and sampling profile')
        summary['requests'], summary['greedy_hashes'] = check_requests(scope, label, ready, ended, prompt_hashes,
            source_identity, eligible, reference, positive)
        summary['activation'] = scope['log']['markers']
        if 'recorder' in scope:
            recorder = scope['recorder']
            summary['recorder'] = dict(raw=reference(recorder['raw']), summary=reference(recorder['summary']),
                                       value=recorder['summary']['value'])
        ready_scopes.append(summary)
        previous_stop = ended
    middle = len(order) // 2
    candidate_log = ready_scopes[middle]['activation']
    active = bool(candidate_log['active']) and not candidate_log['inactive']
    reject_if(any(s['runtime_environment'] != ready_scopes[0]['runtime_environment'] for s in ready_scopes),
              'Additional runtime settings differ across the bracket')
    matched_settings = [s['effective_settings'] for s in ready_scopes[middle - 1:middle + 2]]
    reject_if(not matched_settings[0] == matched_settings[1] == matched_settings[2] or
              (nested and ready_scopes[0]['effective_settings'] != ready_scopes[-1]['effective_settings']),
              'Effective context, batch, slots or threads differ between matched launch scopes')
    if cc == 'C1' and active:
        trace = ready_scopes[middle].get('recorder', {}).get('value', {})
        active = trace.get('type') == 'summary' and trace.get('expected', 0) > 0 and trace.get('written', 0) > 0
    if cc == 'C5' and active:
        active = any(re.search(r'\bdecisions=[1-9]\d*\b', row) for row in candidate_log['stats'])
    functional = evidence.get('functional_controls')
    functional_parity = functional['value']['greedy_parity_passed'] if functional else None
    reject_if(any(scope['activation']['active'] or scope['activation']['inactive'] for i, scope in enumerate(ready_scopes) if i != middle),
              'Candidate activation markers found in stock control')
    cells = []
    for size in PROMPTS:
        measured = [next(cell for cell in s['requests'] if not cell['discard'] and cell['prompt_tokens'] == size) for s in ready_scopes]
        hashes = [s['greedy_hashes'][str(size)] for s in ready_scopes]
        matched_parity = hashes[middle - 1] == hashes[middle] == hashes[middle + 1]
        a0, c, a1 = measured[middle - 1:middle + 2]
        stock0, stock1, candidate = a0['ttft_s'], a1['ttft_s'], c['ttft_s']
        lower, upper = sorted((stock0, stock1))
        classification = endpoint_relation(candidate, lower, upper)
        interpretation = classification
        if not active:
            interpretation = 'candidate mechanism activation was not established'
        if not matched_parity:
            interpretation = 'matched candidate/control greedy parity diverged'
        elif functional_parity is False:
            interpretation = 'bound off/on functional greedy parity diverged'
        cell = dict(prompt_tokens=size, stock_before_s=stock0, candidate_s=candidate, stock_after_s=stock1,
            stock_drift_s=stock1 - stock0, stock_before_decode_tps=a0['decode_tps'], candidate_decode_tps=c['decode_tps'],
            stock_after_decode_tps=a1['decode_tps'], observed_inverse_ttft_range=[lower / candidate, upper / candidate],
            interpretation=interpretation, endpoint_order=classification,
            matched_greedy_parity=matched_parity, attribution_eligible=active and matched_parity and functional_parity is not False)
        if nested:
            strict0, strict1 = measured[0], measured[-1]
            lo, hi = sorted((strict0['ttft_s'], strict1['ttft_s']))
            cell['settings_comparison'] = dict(strict_before_s=strict0['ttft_s'], strict_after_s=strict1['ttft_s'],
                strict_before_decode_tps=strict0['decode_tps'], strict_after_decode_tps=strict1['decode_tps'],
                matched_before_vs_strict=endpoint_relation(stock0, lo, hi), matched_after_vs_strict=endpoint_relation(stock1, lo, hi),
                strict_greedy_parity=hashes[0] == hashes[-1],
                cross_settings_greedy_parity=hashes[0] == hashes[middle - 1] == hashes[middle + 1] == hashes[-1],
                before_ttft_reduction_s=strict0['ttft_s'] - stock0, after_ttft_reduction_s=strict1['ttft_s'] - stock1)
        cells.append(cell)
    return dict(schema='spark-early-bracket-analysis/1', cc=cc, mode='early-bracket', profile=profiles['label'],
                model_identity=reference(evidence['model_identity']), prompt_manifest=reference(prompt_manifest),
                matched_profile=reference(evidence['profile_ref']), scopes=ready_scopes, candidate_activation=active,
                functional_controls=reference(functional) if functional else None, functional_greedy_parity=functional_parity,
                measurements=cells,
                limitations=['A single ordered bracket has one measured request per size and launch. No confidence interval is estimated.',
                    'Both stock endpoints are reported, including drift. An endpoint ordering does not establish repeatable gain.',
                    'Boundary process checks do not detect all transient competition. Inode residency and cgroup accounting are distinct.',
                    'Reclaim-only memory.max events are informational. OOM and watchdog events make a bracket ineligible.'])
