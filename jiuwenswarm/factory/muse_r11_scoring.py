"""Independent, no-load acceptance scoring for the Run 4 target receipts."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from math import isfinite, isclose
import re
from statistics import median

from .ccs.kv_reuse_lab.request_log import first_cached_tasks
from .lab_mailbox import canonical
from .muse_r11_gate import REQUEST_METRICS, required_checks, required_measurements

TASK = 'muse-2bit-demo-r11'
ARMS = {'AQBC': 'control', 'AQBCE': 'seeded'}
CELLS = {
    'first_after_start': ('first-request', 1, 512),
    'p512': ('warm-512', 3, 512),
    'p2048': ('warm-2048', 3, 2048),
    'p512_followup': ('follow-up-512', 3, 512),
    'p2048_followup': ('follow-up-2048', 3, 2048),
}
ARTIFACTS = ('load-receipts.json', 'request-receipts.json', 'warmup-receipts.json', 'startup-fill-receipts.json',
             'server.log', 'memory-watchdog.json')
DEVICE = {
    'model': 'device_model_mib', 'moe_cache': 'gpu_expert_cache_mib', 'kv': 'device_kv_mib',
    'compute': 'device_compute_mib', 'host_compute': 'host_compute_mib',
}
NATIVE_COUNTERS = ('demand_hits', 'demand_misses', 'demand_evictions', 'read_only_hits', 'read_only_misses',
                   'hit_bytes', 'host_bytes', 'prefill_hits', 'prefill_misses', 'decode_hits', 'decode_misses',
                   'graphs', 'demand_seeded_hits', 'demand_seeded_evictions', 'read_only_seeded_hits')
SEED_COUNTS = ('slots_admitted', 'slots_populated', 'charged_bytes', 'uploaded_bytes')
GIB = 1 << 30


class Incomplete(ValueError):
    """The evidence does not answer this check."""


def check(condition, message):
    if not condition:
        raise ValueError(message)


def amount(value, *, minimum=0):
    return type(value) in (int, float) and isfinite(value) and value >= minimum


def sha(value):
    return sha256(value).hexdigest()


def token_digest(tokens):
    return sha(json.dumps(tokens, separators=(',', ':')).encode())


def digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def timestamp(value):
    try:
        date = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise Incomplete('The receipt has no parseable timestamp.') from exc
    if date.tzinfo is None:
        raise Incomplete('The receipt timestamp has no time zone.')
    return date.timestamp()


def optional_json(files, name):
    if name not in files:
        raise Incomplete(f'The capped worker sealed no {name}.')
    raw = files[name]['data']
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise Incomplete(f'The sealed {name} could not be read.') from exc
    if not isinstance(value, dict):
        raise Incomplete(f'The sealed {name} is not an object.')
    return value


def package_policy(package):
    contract = package['contract']['document']
    task = package['lab_task']
    protocol = contract['extensions']['muse.r11-seeding']
    marker = contract['extensions'].get('muse.r11-calibration-amendment') or {}
    if contract['version'] == 12:
        check(marker.get('amendment') == '032' and marker.get('by') == 'owner'
              and marker.get('previous_version') == 11, 'Run 4 revision 12 is missing its owned calibration amendment.')
    image_arm = task['arms']['AQBC']['subject']
    image = package['subjects'][image_arm]
    profile = package['subjects']['seeding_profile']
    check(package['schema'] == 'factory.lab-package/1'
          and package['origin'] == {'task_id': TASK, 'node_id': 'deliver_to_lab'}
          and package['contract']['id'] == contract['contract_id'] == TASK
          and contract['version'] in {11, 12}
          and task['arms']['AQBCE']['subject'] == image_arm
          and set(task['arms']) == set(ARMS)
          and set(package['subjects']) == {image_arm, 'seeding_profile'}
          and image.get('kind') == 'container_image'
          and image.get('verification', {}).get('verified') is True
          and isinstance(image.get('build_attempt_id'), str)
          and re.fullmatch(r'sha256:[0-9a-f]{64}', image['identity'].get('id', ''))
          and profile.get('kind') == 'artifact' and profile.get('transfer') == 'attach'
          and digest(profile['payload'].get('sha256')) and digest(package['contract']['sha256']),
          'The sealed request does not identify one verified image and one verified seed profile.')
    check(task['arms']['AQBC'].get('env', {}) == {} and task['arms']['AQBCE'].get('env') == protocol['profile_env']
          and not any(arm.get('args') for arm in task['arms'].values()),
          'The same-image arms differ outside the admitted seed switch.')
    check(set(CELLS) == {request['id'] for request in contract['workload']['requests']}
          and contract['measurement']['protocol']['repeats'] == 3
          and protocol['memory_cap'] == '96G' and protocol['swap_cap'] == 0
          and protocol['device_budget_mib'] == 110000,
          'The frozen request or machine policy is outside the Run 4 scoring protocol.')
    for name in ('minimum_warm_ttft_gain_fraction', 'latency_regression_fraction', 'max_added_ready_seconds'):
        check(amount(protocol.get(name)) and protocol[name] > 0, f'Missing acceptance threshold {name}.')
    check(package['package_id'] == 'labpkg-' + sha(canonical(
        {key: value for key, value in package.items() if key != 'package_id'}).encode())[:32],
        'The target package differs from the factory-sealed identity.')
    return contract, protocol, task, image, profile['payload']['sha256']


def sealed_line(log, source):
    safe = isinstance(source, dict) and source.get('path') == 'server.log'
    start, end = (source.get('start'), source.get('end')) if safe else (None, None)
    check(type(start) is int and type(end) is int and 0 <= start < end <= len(log),
          'A reported server record has no valid sealed byte interval.')
    return log[start:end]


def native_json(log, source, marker):
    raw = sealed_line(log, source)
    prefix = (marker + ' ').encode()
    check(raw.count(prefix) == 1 and raw.endswith(b'\n') and raw.count(b'\n') == 1,
          'The native receipt does not identify one complete ' + marker + ' record.')
    value = json.loads(raw.split(prefix, 1)[1])
    check(isinstance(value, dict), 'The native ' + marker + ' payload is not a record.')
    return value


def verify_counters(row, log):
    before = native_json(log, row['counters_before'], 'muse_cache_counters')
    after = native_json(log, row['counters_after'], 'muse_cache_counters')
    check(row['counters_before']['end'] <= row['source']['start'] <= row['counters_after']['start']
          < row['counters_after']['end'] <= row['source']['end'],
          'The native counters bracket a different request.')
    valid = lambda value: all(type(value.get(key)) is int and value[key] >= 0 for key in NATIVE_COUNTERS)
    check(valid(before) and valid(after), 'Malformed native cache counters.')
    deltas = {key: after[key] - before[key] for key in NATIVE_COUNTERS}
    hits = deltas['prefill_hits'] + deltas['decode_hits']
    misses = deltas['prefill_misses'] + deltas['decode_misses']
    check(min(deltas.values()) >= 0 and hits + misses > 0 and row.get('cache_counters') == deltas
          and hits == deltas['demand_hits'] + deltas['read_only_hits']
          and misses == deltas['demand_misses'] + deltas['read_only_misses']
          and deltas['demand_seeded_hits'] <= deltas['demand_hits']
          and deltas['demand_seeded_evictions'] <= deltas['demand_evictions']
          and deltas['read_only_seeded_hits'] <= deltas['read_only_hits']
          and amount(row.get('cache_hit_rate')) and isclose(row['cache_hit_rate'], hits / (hits + misses)),
          'Reported cache-hit rate differs from native per-request counter deltas.')
    for phase in ('prefill', 'decode'):
        hit, miss = deltas[phase + '_hits'], deltas[phase + '_misses']
        value = row.get(phase + '_cache_hit_rate')
        check(amount(value) and isclose(value, hit / (hit + miss)) if hit + miss else value is None,
              'Reported ' + phase + ' hit rate differs from its native counter deltas.')


def verify_load(load, arm, attempt, delivery, package, request_id, image, profile_sha, protocol):
    expected = dict(format='muse-r11-target-load/1', arm=arm, load_id=attempt['attempt_id'],
                    package_id=package['package_id'], request_id=request_id,
                    delivery_check_id=delivery['obs_id'], contract_sha256=package['contract']['sha256'],
                    build_attempt_id=image['build_attempt_id'], image_id=image['identity']['id'],
                    profile_sha256=profile_sha, prefill_plan_sha256=protocol['baseline']['prefill_plan_sha256'],
                    launch_config=protocol['baseline']['launch_config'],
                    launch_config_sha256=protocol['baseline']['launch_config_sha256'],
                    executable_sha256=delivery['executable_sha256'],
                    logical_env=package['lab_task']['arms'][arm].get('env', {}))
    check(all(load.get(key) == value for key, value in expected.items()),
          'The server load is not the exact same-image arm approved by the sealed delivery.')
    for key in ('image_check_id', 'source_commit', 'profile_artifact_id', 'profile_manifest_sha256'):
        if key in delivery:
            check(load.get(key) == delivery[key], 'The target receipt differs from the sealed ' + key + '.')
    check(digest(load.get('executable_sha256'))
          and load.get('pack', {}).get('manifest_sha256') == protocol['baseline']['pack_manifest_sha256'],
          'The target executable or released pack identity is unproven.')
    if load.get('status') != 'complete':
        raise Incomplete('The independently capped arm stopped before completing the workload.')
    library = load.get('library_delta') or {}
    libraries = load.get('image_files_sha256') or {}
    check(library.get('parent_image_id') == protocol['baseline']['image_id']
          and digest(library.get('parent_library_sha256'))
          and library.get('parent_library_sha256') != library.get('candidate_library_sha256')
          and library.get('candidate_library_sha256') == libraries.get('libllama.so.1'),
          'No sealed delta between the exact released and candidate runtime libraries.')
    mapping = load.get('profile_mapping_before') or {}
    check(mapping == load.get('profile_mapping_after') and mapping.get('sha256') == profile_sha
          and mapping.get('mode') == '0400', 'The verified read-only profile mapping was not preserved.')
    physical = load.get('physical_env') or {}
    for variable in protocol['profile_env']:
        if arm == 'AQBC':
            check(variable not in physical, 'The control arm supplied a seed variable.')
        elif variable.endswith('_PATH'):
            check(physical.get(variable) and physical[variable] == mapping.get('path'),
                  'The seeded arm lacks a staged private profile path.')
        else:
            check(physical.get(variable) == protocol['profile_env'][variable],
                  'The physical seeding switch differs from the delivery.')
    argv = load.get('argv') or []
    flags = expected['launch_config']['args']
    check(any(argv[index:index + len(flags)] == flags for index in range(len(argv))),
          'The actual target argv does not contain the exact frozen launch configuration.')
    check(load.get('server_closed') is True, 'The independent server did not record shutdown.')
    check(timestamp(load['started_utc']) < timestamp(load['ended_utc']),
          'Invalid server load timing.')
    if timestamp(load['ended_utc']) > timestamp(protocol['target_deadline']):
        raise ValueError('The target arm completed after the admitted deadline.')
    return 'Verified delivered image, executable, pack, prefill, launch arguments and arm settings.'


def verify_memory(load, native, watchdog, log, protocol):
    from .ccs.prefill_batch_sizing.run import parse_log

    if watchdog.get('stop_error'):
        raise ValueError(watchdog['stop_error']['message'])
    device = load.get('observed', {}).get('device_mib', {})
    missing = [name for name in DEVICE if not amount(device.get(name))]
    if missing:
        raise Incomplete('Missing load accounting for ' + ', '.join(missing) + '.')
    if not all(amount(load.get(name)) for name in ('peak_process_rss_bytes', 'peak_memory_bytes', 'min_available_bytes')):
        raise Incomplete('Peak RSS, capped memory peak or the observed MemAvailable floor is absent.')
    if log is None or not load.get('device_peak_source') or not amount(load.get('device_peak_mib')):
        raise Incomplete('No sealed full-log source for the comparable device buffer peak.')
    source = load['device_peak_source']
    raw = sealed_line(log, source)
    ready = source.get('ready_end')
    peak = round(sum(device[key] for key in DEVICE if key != 'host_compute'), 2)
    check(source['start'] == 0 and source['end'] == len(log) and type(ready) is int and 0 < ready < len(raw)
          and parse_log(raw[:ready].decode(errors='replace'))['device_mib'] == device
          and not parse_log(raw[ready:].decode(errors='replace'))['device_mib']
          and load.get('device_peak_categories_mib') == device
          and load['device_peak_mib'] == peak
          and load.get('device_budget_headroom_mib') == round(protocol['device_budget_mib'] - peak, 2),
          'The sealed ready and full logs do not establish the comparable native device buffer peak.')
    admission = load.get('gate_before_load') or {}
    check(load.get('memory_cap') == native.get('memory_cap') == protocol['memory_cap']
          and load.get('swap_cap_bytes') == protocol['swap_cap']
          and load.get('device_budget_mib') == protocol['device_budget_mib']
          and watchdog == load.get('watchdog')
          and watchdog.get('format') == 'muse-r11-memory-watchdog/1'
          and watchdog.get('cgroup_verified') is True and watchdog.get('samples', 0) > 0
          and watchdog.get('cap_bytes') == 96 * GIB and watchdog.get('swap_bytes') == 0
          and admission.get('ok') is True and admission.get('shared_admission', {}).get('ok') is True
          and watchdog.get('threshold_rss_bytes') == 96 * GIB - (256 << 20)
          and load['peak_process_rss_bytes'] == watchdog.get('peak_process_rss_bytes')
          and load['peak_memory_bytes'] == watchdog.get('peak_memory_bytes')
          and load['min_available_bytes'] == watchdog.get('min_available_bytes')
          and load['peak_process_rss_bytes'] < watchdog['threshold_rss_bytes']
          and (native.get('peak_memory_bytes') is None or amount(native['peak_memory_bytes'])
               and native['peak_memory_bytes'] <= 96 * GIB)
          and max(load['peak_process_rss_bytes'], load['peak_memory_bytes']) <= 96 * GIB
          and load['min_available_bytes'] >= 8 * GIB
          and sum(device[key] for key in DEVICE) <= protocol['device_budget_mib'],
          'The native capped receipt or recorded device accounting violates the admitted machine limits.')
    return 'The native capped run and device accounting stayed within the recorded machine limits.'


def read_request_rows(document, arm, log, prompts):
    check(document.get('format') == 'muse-r11-requests/1' and document.get('arm') == arm,
          'The request receipt belongs to a different schema or arm.')
    rows = document.get('rows')
    if not isinstance(rows, list) or not rows:
        raise Incomplete('The arm sealed no completed request rows.')
    identities, intervals = set(), []
    measured = {}
    completed = [row for row in rows if row.get('status') == 'complete']
    for row in completed:
        identity = row['id']
        start, end = row['source']['start'], row['source']['end']
        check(identity not in identities and (not intervals or intervals[-1][1] <= start),
              'Request identities or server source intervals overlap.')
        identities.add(identity)
        intervals.append((start, end))
        native = first_cached_tasks(sealed_line(log, row['source']))
        check(native == [row['server_task']] and native[0].get('slot_id') == 0 and native[0].get('end')
              and native[0].get('prompt_tokens') == row['prompt_tokens'],
              'The request does not bind a completed native single-slot log record.')
        check(digest(row['prompt_sha256']) and digest(row['token_ids_sha256']),
              'A request is missing its prompt or tokenizer identities.')
        size = row['nominal_prompt_tokens']
        check(size in prompts and (row['prompt_sha256'], row['tokenized_prompt_tokens'],
                                   row['token_ids_sha256']) == prompts[size]
              and row['tokenized_prompt_tokens'] == row['prompt_tokens']
              and row['prompt_tokens'] in {size, size - 1}
              and row['cache_prompt'] is (row['cell'].startswith('follow-up'))
              and (row['n_predict'], row['temperature'], row['seed'], row['ignore_eos']) == (32, 0, 1, True),
              'The retained request differs from the frozen rendered prompt or greedy policy.')
        output = row['output_token_ids']
        check(isinstance(output, list) and len(output) == row['generated_tokens'] == 32
              and all(type(token) is int and token >= 0 for token in output)
              and token_digest(output) == row['output_token_ids_sha256'],
              'A request does not bind its exact 32 generated token IDs.')
        verify_counters(row, log)
        check(row.get('quiet', {}).get('included') is True and bool(row['quiet'].get('samples')),
              'The scored source has no recorded target activity samples.')
        if row['measured_cell'] is not True:
            check(row['cell'] in {'prime-512', 'prime-2048'}, 'Unexpected unscored request in the target receipt.')
            continue
        request = row['contract_request']
        check(request in CELLS and row['cell'] == CELLS[request][0],
              'A measured row does not match the frozen request.')
        samples, size = CELLS[request][1:]
        repeat = row['repeat']
        check(size == row['nominal_prompt_tokens'] and type(repeat) is int
              and 0 <= repeat < samples and (request, repeat) not in measured,
              'A measured cell has the wrong token count or repeat identity.')
        check(all(amount(row.get(key)) and (key == 'cache_hit_rate' or row[key] > 0)
                  for key in REQUEST_METRICS), 'Missing or invalid recorded timing or cache-hit measurement.')
        check(row['client_ttft_ms'] <= row['request_total_ms'] and row['cache_hit_rate'] <= 1,
              'Impossible request latency or native hit rates.')
        measured[request, repeat] = row
    return measured, completed


def complete_rows(measured):
    return set(measured) == {(cell, repeat) for cell, (_, samples, _) in CELLS.items() for repeat in range(samples)}


def verify_prefix(rows):
    for index, row in enumerate(rows):
        cached = row['server_task']['cached_tokens']
        check(type(cached) is int and 0 <= cached <= row['prompt_tokens'], 'Invalid native restored token count.')
        if row['cell'].startswith('follow-up'):
            prime = rows[index - 1] if index else {}
            check(prime.get('cell') == row['cell'].replace('follow-up', 'prime')
                  and prime.get('repeat') == row['repeat'] and prime['server_task'].get('cached_tokens') == 0
                  and prime['prompt_sha256'] == row['prompt_sha256']
                  and prime['token_ids_sha256'] == row['token_ids_sha256']
                  and cached > 0, 'A measured follow-up lacks its immediately preceding cache-off prime or restored tokens.')
        else:
            check(cached == 0, 'A first, warm or priming request reused prior prompt tokens.')
    return 'Every measured follow-up restored native prompt tokens after its same-arm cache-off prime.'


def verify_warmup(warm, log, measured, all_rows, calibration_hashes):
    from scripts.factory import lab_warmup as w2

    rows = warm['requests']
    measured_prompts = {row['prompt_sha256'] for row in all_rows}
    measured_ids = {row['token_ids_sha256'] for row in all_rows}
    check(warm['format'] == w2.FORMAT and warm['status'] == 'complete' and 2 <= len(rows) <= w2.LIMIT
          and warm['request_cap'] == w2.LIMIT and warm['decode_relative_tolerance'] == w2.DECODE_TOLERANCE
          and measured_prompts <= set(warm['measured_prompt_sha256'])
          and measured_ids <= set(warm['measured_token_ids_sha256']),
          'The W2 receipt does not bind the target workload and stop rule.')
    first = measured.get(('first_after_start', 0))
    warm_starts = [row['source']['start'] for row in all_rows if row is not first]
    if first is None or not warm_starts:
        raise Incomplete('Cannot place W2 between the first request and the measured warm cells.')
    check(warm.get('target_tokens') == first['prompt_tokens'],
          'Warm-up prompts do not match the pinned short request length.')
    lower, upper = first['source']['end'], min(warm_starts)
    seen_hashes = measured_prompts | calibration_hashes
    seen_ids = set(measured_ids)
    seen_tasks = []
    for index, row in enumerate(rows, 1):
        start, end = row['server_log_start'], row['server_log_end']
        check(lower <= start < end <= upper and row['index'] == index and row['status'] == 'complete'
              and row['cache_prompt'] is False and row['measured_cell'] is False
              and row['n_predict'] == row['generated_tokens'] == w2.PREDICT
              and row['rendered_prompt_tokens'] == warm['target_tokens'] == row['prompt_tokens']
              and all(amount(row.get(metric)) and row[metric] > 0 for metric in (
                  'client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms'))
              and row['prompt_sha256'] == w2._sha(row['prompt']) and row['prompt_sha256'] not in seen_hashes
              and digest(row['token_ids_sha256']) and row['token_ids_sha256'] not in seen_ids,
              'Warm-up overlapped a measured/calibration prompt, fell outside the warm-up window or was incomplete.')
        task = w2._logged_request(first_cached_tasks(log[start:end]), row['rendered_prompt_tokens'])
        check(task == row['server_request'], 'A warm-up row differs from its native request log.')
        seen_tasks.append(task)
        seen_hashes.add(row['prompt_sha256'])
        seen_ids.add(row['token_ids_sha256'])
        lower = end
    check(first_cached_tasks(log[first['source']['end']:upper]) == seen_tasks,
          'Unexpected request before the warm cells.')
    rates = [row['decode_tokens_per_second'] for row in rows]
    stable = [index for index, (before, after) in enumerate(zip(rates, rates[1:]), 2) if w2._stable(before, after)]
    reason = warm.get('stop_reason')
    check((reason == 'stable' and stable == [len(rows)])
          or (reason == 'cap_reached' and len(rows) == w2.LIMIT and not stable),
          'W2 stopped at the wrong request.')
    return w2._summary(rows, reason)


def load_measurements(load, startup):
    device = load.get('observed', {}).get('device_mib', {})
    parts = {label: device.get(key) for key, label in DEVICE.items()}
    total = sum(parts.values()) if all(amount(value) for value in parts.values()) else None
    return dict(parts, pack_bytes=load.get('pack', {}).get('bytes'), ready_seconds=load.get('load_seconds'),
                sampled_peak_memory_bytes=load.get('peak_process_rss_bytes'),
                available_memory_floor_bytes=load.get('min_available_bytes'), device_peak_mib=load.get('device_peak_mib'),
                device_accounted_mib=total, device_headroom_mib=load['device_budget_mib'] - total if total is not None else None,
                fit_margin_mib=load.get('placement', {}).get('fit_margin_mib'),
                **{key: startup.get(key) for key in ('seed_fill_seconds', 'seed_fill_slots', 'seed_fill_bytes')})


def verify_startup(startup, arm, log, first_offset):
    check(startup.get('format') == 'muse-r11-startup-fill/1' and startup.get('arm') == arm,
          'The startup receipt has a different identity from the arm.')
    source = startup.get('source')
    native = native_json(log, source, 'muse_cache_startup')
    check({key: value for key, value in startup.items() if key not in {'format', 'arm', 'source'}} == native
          and source['end'] <= first_offset
          and amount(native.get('seed_ms')) and isinstance(native.get('groups'), list)
          and all(type(native.get(field)) is int and native[field] >= 0 for field in SEED_COUNTS),
          'The startup receipt does not match the native record before the first request.')
    for field in SEED_COUNTS:
        check(all(type(group.get(field)) is int and group[field] >= 0 for group in native['groups'])
              and sum(group[field] for group in native['groups']) == native[field],
              'Per-group startup counters do not reconcile to the native totals.')
    seconds, slots, size = native['seed_ms'] / 1000, native['slots_populated'], native['uploaded_bytes']
    if arm == 'AQBC':
        check(native.get('enabled') is False and not any(native[field] for field in SEED_COUNTS) and seconds == 0,
              'The switch-off control unexpectedly recorded seed work.')
    else:
        check(native.get('enabled') is True and slots == native['slots_admitted'] > 0 and size > 0 and seconds > 0
              and native['charged_bytes'] > 0 and all(group['slots_populated'] == group['slots_admitted']
                                                     for group in native['groups']),
              'The opt-in arm did not complete and publish all admitted startup slots.')
    return dict(seed_fill_seconds=seconds, seed_fill_slots=slots, seed_fill_bytes=size)


def matched_rows(by_arm):
    left, right = (by_arm[arm] for arm in ARMS)
    if not complete_rows(left) or not complete_rows(right):
        raise Incomplete('Incomplete matched request and repeat coverage.')
    for key, a in left.items():
        b = right[key]
        if any(a[field] != b[field] for field in ('prompt_sha256', 'token_ids_sha256', 'prompt_tokens')):
            raise ValueError('A request or tokenizer identity differs across arms: ' + key[0])
    return left, right


def compare_metrics(by_arm, startup, policy):
    off, on = matched_rows(by_arm)
    metrics = {}
    for key in CELLS:
        metrics[key] = {}
        for field in REQUEST_METRICS:
            control = [row[field] for (cell, _), row in off.items() if cell == key]
            seeded = [row[field] for (cell, _), row in on.items() if cell == key]
            metrics[key][field] = dict(control=control, seeded=seeded,
                                       control_median=median(control), seeded_median=median(seeded))
    gain = policy['minimum_warm_ttft_gain_fraction']
    tolerance = policy['latency_regression_fraction']
    qualifying = []
    failures = []
    for key, cell in metrics.items():
        ttft, hit = cell['client_ttft_ms'], cell['cache_hit_rate']
        if (key in {'p512', 'p2048'} and ttft['seeded_median'] <= ttft['control_median'] * (1 - gain)
                and max(ttft['seeded']) < ttft['control_median'] and hit['seeded_median'] > hit['control_median']):
            qualifying.append(key)
        for field in ('client_ttft_ms', 'request_total_ms', 'decode_tokens_per_second'):
            row = cell[field]
            ratio = row['seeded_median'] / row['control_median']
            if (field == 'decode_tokens_per_second' and ratio < 1 - tolerance
                    or field != 'decode_tokens_per_second' and ratio > 1 + tolerance):
                failures.append(f'{key} {field} exceeded the {tolerance:.0%} regression limit')
    if not qualifying:
        failures.append(f'No warm first-token cell met the {gain:.0%} threshold, sample separation and higher native hit rate.')
    ready = [startup[arm]['ready_seconds'] for arm in ARMS]
    if not all(amount(value) for value in ready):
        raise Incomplete('Readiness time is missing in a target arm.')
    added = ready[1] - ready[0]
    if added > policy['max_added_ready_seconds']:
        failures.append(f'Added readiness time {added:.2f} s exceeded the pinned budget.')
    first = metrics['first_after_start']['client_ttft_ms']
    first_only = first['seeded_median'] < first['control_median'] and not any(
        item['client_ttft_ms']['seeded_median'] < item['client_ttft_ms']['control_median']
        for cell, item in metrics.items() if cell != 'first_after_start')
    return dict(cells=metrics, failures=failures, qualifying_warm_cells=qualifying,
                first_request_only=first_only, added_ready_seconds=added)


def evaluate(package, request_id, delivery, arms, prompt_hashes, calibration_hashes):
    """Build the format-1 lab report body and source-linked comparison from capped evidence."""
    contract, protocol, task, image, profile_sha = package_policy(package)
    checks = {}
    measured = {arm: {} for arm in ARMS}
    load_values = {arm: {} for arm in ARMS}
    chart_startup = {}
    devices = {}

    def assess(key, arm, verify, *args):
        try:
            result = verify(*args)
        except Incomplete as exc:
            checks[key, arm] = ('not_run', str(exc))
            return None
        except (KeyError, TypeError, IndexError) as exc:
            checks[key, arm] = ('not_run', f'Incomplete sealed evidence for {key}: {exc}.')
            return None
        except ValueError as exc:
            checks[key, arm] = ('fail', str(exc))
            return None
        checks[key, arm] = ('pass', result if isinstance(result, str) else 'Verified from the native source record.')
        return result

    for arm in ARMS:
        source = arms.get(arm) or {}
        files = source.get('files') or {}
        try:
            load = optional_json(files, 'load-receipts.json')
        except Incomplete as exc:
            for key, side in required_checks(contract):
                if side == arm and key != 'independent_acceptance':
                    checks[key, arm] = ('not_run', str(exc))
            continue

        verified = assess('same_image_and_profile', arm, verify_load, load, arm, source['attempt'],
                          delivery, package, request_id, image, profile_sha, protocol)
        identity_status = checks['same_image_and_profile', arm][0]
        log = files.get('server.log', {}).get('data')
        try:
            watchdog = optional_json(files, 'memory-watchdog.json')
        except Incomplete as exc:
            checks['memory_gate', arm] = ('not_run', str(exc))
        else:
            assess('memory_gate', arm, verify_memory, load, source['observation']['values'], watchdog, log, protocol)
        if identity_status == 'fail':
            continue
        devices[arm] = dict(executable=load.get('executable_sha256'), libraries=load.get('image_files_sha256'))
        if log is None:
            for key in ('token_identity', 'prefix_reuse', 'warmup_w2', 'startup_cache_fill'):
                checks[key, arm] = ('not_run', 'The capped worker sealed no native server log.')
            load_values[arm] = load_measurements(load, {})
            continue

        try:
            request_data = optional_json(files, 'request-receipts.json')
            items, all_rows = read_request_rows(request_data, arm, log, prompt_hashes)
        except (Incomplete, KeyError, TypeError, IndexError) as exc:
            items, all_rows = {}, []
            checks['token_identity', arm] = ('not_run', str(exc))
        except ValueError as exc:
            items, all_rows = {}, []
            checks['token_identity', arm] = ('fail', str(exc))
        measured[arm] = items
        if any(row['prompt_sha256'] in calibration_hashes for row in all_rows):
            checks['same_image_and_profile', arm] = ('fail', 'A retained target request overlaps calibration.')
        if all_rows:
            assess('prefix_reuse', arm, verify_prefix, all_rows)
        try:
            warm = optional_json(files, 'warmup-receipts.json')
        except Incomplete as exc:
            checks['warmup_w2', arm] = ('not_run', str(exc))
        else:
            assess('warmup_w2', arm, verify_warmup, warm, log, items, all_rows, calibration_hashes)
        try:
            startup = optional_json(files, 'startup-fill-receipts.json')
        except Incomplete as exc:
            checks['startup_cache_fill', arm] = ('not_run', str(exc))
        else:
            first = items.get(('first_after_start', 0))
            if first:
                observed = assess('startup_cache_fill', arm, verify_startup, startup, arm, log, first['source']['start'])
                if observed is not None:
                    chart_startup[arm] = dict(startup, **observed)
                    checks['startup_cache_fill', arm] = ('pass', f"Native startup recorded "
                        f"{observed['seed_fill_slots']:,} populated slots and {observed['seed_fill_bytes'] / GIB:.2f} GiB uploaded.")
            else:
                checks['startup_cache_fill', arm] = ('not_run', 'Startup cannot be aligned with the first measured request.')
        load_values[arm] = load_measurements(load, chart_startup.get(arm, {}))
        if verified and source['attempt'].get('state') != 'succeeded':
            checks['same_image_and_profile', arm] = ('not_run', 'The arm did not have a successful capped completion.')

    if len(devices) == 2 and (devices['AQBC'] != devices['AQBCE']
                              or not isinstance(devices['AQBC']['libraries'], dict)
                              or devices['AQBC']['libraries'].get('llama-server') != devices['AQBC']['executable']
                              or not all(digest(value) for value in devices['AQBC']['libraries'].values())
                              or 'libllama.so.1' not in devices['AQBC']['libraries']
                              or not any(name.startswith('libggml-cuda.so') for name in devices['AQBC']['libraries'])):
        for arm in ARMS:
            checks['same_image_and_profile', arm] = ('fail', 'The extracted executable and native library digests differ across arms.')

    comparison = None
    missing_comparison = None
    try:
        control, seeded = matched_rows(measured)
    except Incomplete as exc:
        missing_comparison = str(exc)
    except ValueError as exc:
        for arm in ARMS:
            checks['token_identity', arm] = ('fail', str(exc))
    else:
        same = all(value['output_token_ids'] == seeded[key]['output_token_ids'] for key, value in control.items())
        same_prefix = all(value['server_task']['cached_tokens'] == seeded[key]['server_task']['cached_tokens']
                          for key, value in control.items())
        for arm in ARMS:
            checks['token_identity', arm] = (
                'pass' if same else 'fail',
                'All matched responses retained exactly the same 32 generated token IDs.' if same
                else 'At least one matched greedy response has different token IDs.')
            if not same_prefix:
                checks['prefix_reuse', arm] = ('fail', 'Native restored token counts differ across the two arms.')
        try:
            comparison = compare_metrics(measured, load_values, protocol)
        except Incomplete as exc:
            missing_comparison = str(exc)

    metrics = contract['measurement']['metrics']
    want_rows = required_measurements(contract)
    results = []
    skipped = {}
    for test in task['tests']:
        for arm in test['arms']:
            for name in test.get('measure', []):
                for cell in test.get('requests', [None]):
                    if cell is None:
                        value = load_values[arm].get(name)
                        samples = [value] if amount(value, minimum=-float('inf') if name == 'fit_margin_mib' else 0) else []
                        expected_count = 1
                    else:
                        expected_count = CELLS[cell][1]
                        samples = [measured[arm][cell, repeat][name] for repeat in range(expected_count)
                                   if (cell, repeat) in measured[arm]]
                    if len(samples) != expected_count:
                        skipped[test['id']] = 'Some required cells or load metrics have no complete native evidence.'
                    if samples:
                        results.append(dict(test_id=test['id'], arm=arm, metric=name, unit=metrics[name]['unit'],
                                            samples=samples, value=median(samples),
                                            statistic='single' if len(samples) == 1 else 'median',
                                            **({'request': cell} if cell else {})))
    result_keys = [(row['metric'], row['arm'], row.get('request')) for row in results]
    check(len(set(result_keys)) == len(result_keys), 'Expected one sealed test per arm, metric and request.')
    wanted_checks = required_checks(contract) - {('independent_acceptance', 'AQBCE')}
    for key, arm in wanted_checks:
        checks.setdefault((key, arm), ('not_run', 'The required native evidence was not complete.'))

    incomplete = bool(skipped) or set(result_keys) != want_rows or any(
        checks[key][0] == 'not_run' for key in wanted_checks)
    failures = [f'{arm} {key}: {checks[key, arm][1]}' for key, arm in sorted(wanted_checks)
                if checks[key, arm][0] == 'fail']
    if comparison:
        failures.extend(comparison['failures'])
    elif not failures:
        incomplete = True
    if incomplete:
        verdict, outcome = 'not_run', 'partial'
        verdict_detail = 'The available target evidence is incomplete. AQBCE did not earn acceptance.'
        if missing_comparison:
            verdict_detail += ' ' + missing_comparison
        if failures:
            verdict_detail += ' Recorded failures: ' + '; '.join(failures) + '.'
    elif failures:
        verdict, outcome = 'fail', 'completed'
        verdict_detail = 'AQBCE did not meet the sealed acceptance rule. ' + '; '.join(failures) + '.'
    else:
        verdict, outcome = 'pass', 'completed'
        verdict_detail = 'AQBCE met the same-image acceptance rule in ' + ', '.join(comparison['qualifying_warm_cells']) + '.'
    checks['independent_acceptance', 'AQBCE'] = (verdict, verdict_detail)

    summary = verdict_detail
    if comparison:
        first = comparison['cells']['first_after_start']['client_ttft_ms']
        delta = first['seeded_median'] / first['control_median'] - 1
        summary += f" First-request TTFT changed from {first['control_median']/1000:.2f} to " \
                   f"{first['seeded_median']/1000:.2f} s ({delta:+.1%})."
        if comparison['first_request_only']:
            summary += ' First-token improvement was confined to the first request after startup.'
        summary += f" Readiness changed by {comparison['added_ready_seconds']:+.2f} s."
    if 'AQBCE' in chart_startup:
        summary += f" The seeded server uploaded {chart_startup['AQBCE']['seed_fill_bytes']/GIB:.2f} GiB at startup."

    check_rows = []
    for test in task['tests']:
        key = test.get('check')
        if key:
            for arm in test['arms']:
                state, detail = checks[key, arm]
                check_rows.append(dict(test_id=test['id'], check=key, arm=arm, verdict=state, detail=detail))
    report = dict(outcome=outcome, summary=summary, results=results, checks=check_rows,
                  not_run=[dict(test_id=key, reason=reason) for key, reason in sorted(skipped.items())],
                  limits=['The two arms ran sequentially once each. Background activity is recorded without filtering rows.'],
                  sections=dict(setup='Same delivered image, original AQBC pack and launch settings, capped target arms.',
                                results=summary, deviations='No repeated loads or manufactured samples. '
                                'Missing or invalid native evidence carries no passing verdict.'))
    return report, measured, chart_startup, comparison
