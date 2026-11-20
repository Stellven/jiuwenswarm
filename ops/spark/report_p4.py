#!/usr/bin/env python3
"""Admit a frozen P4 launch set and publish its verified native report."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import sys
import math
from pathlib import Path
import re
from statistics import median

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.ccs.expert_prefetch_readiness.prefetch import counters as predictor_counters
from jiuwenswarm.factory.export import export_task, verify
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest, safe_bytes
from report_early_bracket import EFFECTIVE_SETTINGS
from report_p1 import CAPSULE, TASK, json_bytes


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SIZES = (512, 2048)
PROCESSES = ('build_processes', 'model_processes', 'factory_controllers', 'test_processes')
OOM_KEYS = ('oom', 'oom_kill', 'oom_group_kill')
KERNEL = {'memory.max': str(100 * 1024**3), 'memory.swap.max': '0', 'memory.oom.group': '1',
          'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}
BANK = re.compile(r'CUDA0 MoE cache size = ([\d.]+) MiB for ([\d.]+) MiB of host experts, ([\d.]+)% of the misses on the CPU')


def timepoint(value):
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError('P4 timestamps must carry an explicit UTC offset')
    return timestamp


def demand(condition, context):
    if not condition:
        raise ValueError(context)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def strict_quiet(data, prelaunch=False):
    demand(all(data[key] == [] for key in PROCESSES) and
           not data.get('screening_admitted') and not data.get('authorized_cpu_lane'),
           'P4 forbids competing build, model, test and Factory controller activity')
    demand(not any(int(data.get('memory_events', {}).get(k, 0)) for k in OOM_KEYS), 'P4 saw a memory safety event')
    demand(data['mem_available_gib'] >= (110 if prelaunch else 8), 'P4 headroom below its boundary floor')
    if prelaunch:
        demand(data['quiet'] is True and 0 <= data['load_1m'] < 1, 'P4 prelaunch quiet threshold did not pass')


def screen_safety(data, prelaunch=False):
    demand(not data['model_processes'] and not any(int(data.get('memory_events', {}).get(k, 0)) for k in OOM_KEYS),
           'A competing model or memory safety event invalidates the pooled screen')
    demand(data['mem_available_gib'] >= (110 if prelaunch else 8), 'Pooled screen headroom fell below the safety floor')


def planned_window(pass_number, pooled_screen=False):
    result = [(f'warmup-{p}-{n}', 0, n, 'after' if index == 1 else None)
              for p in ((1, 2) if pooled_screen else (1, 2, 3)) for index, n in enumerate(SIZES if p < 3 else SIZES[::-1])]
    for pair in range(4 if pooled_screen else 5):
        repeat = pair + (1 if pass_number == 1 else 6)
        forward = pair % 2 == (1 if pooled_screen else 0)
        result.extend((f'repeat-{repeat}-{n}', repeat, n, 'before')
                      for n in (SIZES if forward else SIZES[::-1]))
    return result


def frozen_plan(path, pinned_sha, base):
    raw = safe_bytes(path)
    value = json.loads(raw)
    demand(digest(raw) == pinned_sha and value['schema'] == 'spark-p4-admitted-launches/1', 'Wrong frozen P4 launch manifest')
    demand(re.fullmatch(r'spark-p4-[a-z0-9-]+', value['iteration_id']) is not None, 'Invalid P4 iteration ID')
    launches = value['launches']
    half = len(launches) // 2
    first = [x['arm'] for x in launches[:half]]
    demand(2 <= half <= 10 and len(launches) == 2 * half and len(set(first)) == half,
           'P4 requires two passes with distinct arms')
    target = value.get('comparison_target', 'matrix')
    if target == 'same-budget-cc':
        subject = value['subject_arm']
        demand(half == 2 and subject not in ('A', 'A+', 'S') and set(first) == {'A+', subject},
               'Focused P4 must admit just A+ and the explicit subject arm')
    else:
        demand(target == 'matrix' and {'A', 'S'} <= set(first), 'P4 matrix requires admitted A and S reference arms')
    demand([x['arm'] for x in launches[half:]] == first[::-1], 'P4 second pass does not mirror the frozen order')
    by_arm = {}
    paths = set()
    for index, row in enumerate(launches):
        scope = Path(row['scope'])
        if not scope.is_absolute():
            scope = base / scope
        demand(scope.parent == base / 'OPS/runs' and scope == scope.resolve(strict=True) and scope not in paths,
               f'P4 needs each launch in a fresh, distinct, immediate OPS/runs child: {scope}')
        paths.add(scope)
        demand(row['launch_pass'] == (1 if index < half else 2) and row['view'] in ('llama', 'strata') and
               re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', row['arm']) and
               re.fullmatch(r'[0-9a-f]{64}', row['profile_sha256']), 'Unexpected P4 launch pass, label, view or profile digest')
        demand((row['arm'] == 'S') == (row['view'] == 'strata'), 'S must use the frozen fair Strata source view')
        identity = (row['view'], row['profile_sha256'])
        demand(by_arm.setdefault(row['arm'], identity) == identity, 'Arm launch profiles differ across passes')
    return raw, value


def same_budget_launch(start, log):
    cmd = start['command']
    demand(cmd.count('--moe-cache-mib') == 1 and cmd.count('--moe-cache-cpu-share') == 1,
           'Focused P4 requires one explicit native bank budget and CPU share')
    requested = int(cmd[cmd.index('--moe-cache-mib') + 1])
    cpu_share = float(cmd[cmd.index('--moe-cache-cpu-share') + 1])
    alloc = BANK.findall(log)
    demand(len(alloc) == 1, 'Focused P4 engine log lacks a unique observed native bank allocation')
    allocated, host_experts, logged_share = map(float, alloc[0])
    demand(0 < allocated <= requested and host_experts > 0 and cpu_share == logged_share,
           'Focused P4 observed bank or CPU share differs from its requested profile')
    settings = {key: int(match.group(1)) for key, regex in EFFECTIVE_SETTINGS.items()
                if (match := re.search(regex, log))}
    demand(set(settings) == set(EFFECTIVE_SETTINGS) and all(value > 0 for value in settings.values()),
           'Focused P4 engine log lacks effective context, batch, slots or thread counts')
    environment = {key: value for key, value in start['launch_environment'].items() if key.startswith('GGML_')}
    return dict(requested_mib=requested, allocated_mib=allocated, host_experts_mib=host_experts, cpu_share_pct=logged_share,
                argv=cmd[1:], effective_settings=settings, runtime_environment=environment)


def source_snapshot(sample, geometry, views, before, after, stride, seed, kernel=None):
    demand(sample['schema'] == 'spark-source-residency/1' and set(sample['views']) == set(views) and
           (sample['pages_per_sample'], sample['seed']) == (stride, seed) and
           before <= timepoint(sample['started']) <= timepoint(sample['completed']) <= after,
           'P4 source snapshot has a different sample or timestamp envelope')
    for view in views:
        fields = ('path', 'resolved_path', 'identity')
        expected = [[f[key] for key in fields] for f in geometry['views'][view]['files']]
        seen = [[f[key] for key in fields] for f in sample['views'][view]['files']]
        demand(expected == seen, 'P4 sampled model paths or inode identities differ from the frozen geometry')
        totals = sample['views'][view]['total']
        demand(set(totals) == {'expert', 'engram', 'dense'} and all(
            row['estimated_resident_fraction'] is None or 0 <= row['estimated_resident_fraction'] <= 1
            for row in totals.values()), 'P4 source sample is missing measured categories or has invalid fractions')
    accounting = sample['scope_accounting']
    demand((accounting is None if kernel is None else accounting and accounting['path'] == kernel['cgroup']),
           'P4 source snapshot does not belong to the admitted scope')


def profile_provenance(base, scope, arm, view, profile, start, load, geometry, capture):
    demand(profile['binary_sha256'] == start['binary_sha256'], 'P4 profile and launched executable disagree')
    command = list(profile['command'])
    if view == 'strata':
        template = capture(base / 'OPS/configs/p4-s-pass-1.json')
        demand(template['sha256'] == profile['fair_config_sha256'], 'P4 fair Strata template digest changed')
        expected = deepcopy(template['value'])
        expected['log'] = str(scope / 'engine.log')
        expected['env']['STRATA_DS4_SLOT_DIR'] = str(scope / 'ds4-slots')
        config_path = base / 'OPS/configs' / (scope.name + '.json')
        config = capture(config_path)
        args = expected['args']
        profile_path = Path(args[args.index('--expert-profile') + 1])
        expert_profile = capture(profile_path, 'application/octet-stream')
        demand(load['config'] == str(config_path) and config['value'] == expected and
               start['engine_binary'] == profile['engine_binary'] and '--profile-readonly' in expected['args'] and
               expert_profile['sha256'] == profile['fair_profile_sha256'] and
               expected['args'][expected['args'].index('--pack') + 1] == geometry['views']['strata']['pack'] and
               all(start['launch_environment'][key] == expected['env'][key]
                   for key in ('DS4_UMA_HEADROOM_GIB', 'STRATA_DS4_REUSE', 'STRATA_DS4_SLOT_DIR')),
               'P4 launched Strata config differs from its admitted fair read-only profile')
        command[command.index('--config') + 1] = str(config_path)
        refs = dict(config=config, fair_template=template, expert_profile=expert_profile)
    else:
        demand(command[command.index('-m') + 1] == geometry['views']['llama']['files'][0]['path'],
               'P4 llama launch model differs from the sampled GGUF geometry')
        runtime = dict(start['launch_environment'])
        refs = {}
        if 'LLAMA_EVENT_REC' in runtime:
            event_path = Path(runtime['LLAMA_EVENT_REC'])
            demand(event_path == scope / event_path.name, 'Recorder gate does not point into its own fresh P4 scope')
            runtime['LLAMA_EVENT_REC'] = event_path.name
            refs['event_trace'] = capture(event_path, 'application/x-ndjson')
        inventory = capture(Path(load['products_manifest']))
        demand(runtime == profile['environment'] and load['native_build_receipt'] == profile['build_receipt'] and
               load['products_manifest_sha256'] == inventory['sha256'] == profile['products_manifest_sha256'],
               'P4 engine gates, library path or native build manifest drifted')
        refs['products'] = inventory
        if runtime.get('LLAMA_EXPERT_CACHE_NATIVE_PROFILE') == '1':
            nomination = capture(Path(runtime['LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH']))
            activation = capture(scope / 'profile-activation.json')
            demand(nomination['sha256'] == activation['value']['sha256'], 'P4 native nomination input differs from its activation evidence')
            refs.update(nomination_profile=nomination, activation=activation)
        if arm in ('A', 'A+'):
            stock = capture(base / 'OPS/runs/a-first-load-retry/start.json')
            demand(stock['value']['binary_sha256'] == profile['binary_sha256'] and profile['build_receipt'] is None and
                   not any(key.startswith('LLAMA_') for key in runtime), 'P4 stock arms must use the admitted pristine binary and no capsule gate')
            if arm == 'A':
                demand(command == stock['value']['command'], 'P4 strict A must use its original flags')
            else:
                demand('--moe-cache-mib' in command and int(command[command.index('--moe-cache-mib') + 1]) > 0,
                       'P4 A+ must declare its positive native bank budget')
            refs['stock_reference'] = stock
    demand(start['command'] == command, 'P4 launch argv differs from its frozen profile')
    return {key: reference(item) for key, item in refs.items()}


def reference(item):
    return {key: item[key] for key in ('artifact_id', 'sha256')}


def sse_evidence(raw):
    content, reasoning = [], []
    complete = False
    usage, timings = {}, {}
    for line in raw.splitlines():
        if not line.startswith(b'data:'):
            continue
        row = line[5:].strip()
        if row == b'[DONE]':
            complete = True
            break
        event = json.loads(row)
        usage = event.get('usage') or usage
        timings = event.get('timings') or timings
        for choice in event.get('choices', []):
            delta = choice.get('delta') or {}
            content.append(delta.get('content') or '')
            reasoning.append(delta.get('reasoning_content') or '')
    demand(complete, 'P4 retained response lacks its terminal SSE frame')
    return [digest(''.join(text).encode()) for text in (content, reasoning)], usage, timings


def request_evidence(capture, directory, name, repeat, size, phase, item, arm, before_start, stop,
                     window, scope_value, prompt, geometry, scope_id, boundary_check=strict_quiet):
    expected_names = (f'{name}/result.json', f'{name}-before-resources.json', f'{name}-after-resources.json')
    demand((item['result'], item['before_resources'], item['after_resources']) == expected_names and
           (item['status'], item['repeat'], item['prompt_tokens'], item['discarded']) == ('complete', repeat, size, repeat == 0),
           'P4 window request path, status or sequence differs from the fixed protocol')
    path = directory / name
    result = capture(path / 'result.json')
    request = capture(path / 'request.json')
    data = result['value']
    before = capture(directory / expected_names[1])
    after = capture(directory / expected_names[2])
    resource = capture(path / 'resource-windows.json')
    content = capture(path / 'output.txt', 'text/plain')
    reasoning = capture(path / 'reasoning.txt', 'text/plain')
    response = capture(path / 'response.sse', 'text/event-stream')
    client = capture(directory / f'{name}-client.log', 'text/plain')
    stream_hashes, usage, timings = sse_evidence(response['raw'])
    refs = dict(before=before, after=after, resource_windows=resource, output=content, reasoning=reasoning, response=response, client=client)
    status_path = path / 'status.json'
    if status_path.exists():
        engine_status = capture(status_path)
        timings = engine_status['value'].get('last_timings') or timings
        refs['engine_status'] = engine_status
    for entry in (before, after):
        boundary_check(entry['value'])
        demand(str(scope_value['pid']) in entry['value']['scope_pids'], 'P4 boundary does not refer to its owning process')
    began, ended = (timepoint(x['value']['observed_utc']) for x in (before, after))
    started = timepoint(data['started'])
    snapshots = resource['value']['snapshots']
    times = [timepoint(snapshots[key]['utc']) for key in ('start', 'first_token', 'end')]
    monotonic = [snapshots[key]['monotonic_ns'] for key in ('start', 'first_token', 'end')]
    demand(before_start <= began <= started <= times[0] <= times[1] <= times[2] <= ended <= stop and
           monotonic[0] <= monotonic[1] <= monotonic[2] and resource['value']['cgroup'] == scope_value['cgroup'] and
           resource['value']['schema'] == 'spark-request-resources/1', 'P4 resource timestamps or scope do not match the request')
    output_hashes = [data['output_sha256'], data['reasoning_sha256']]
    demand(item['sha256'] == result['sha256'] and data['resource_windows_sha256'] == resource['sha256'] and
           data['request_path'] == str(path / 'request.json') and data['arm'] == arm and data['repeat'] == repeat and
           data['prompt_tokens'] == size and data['discard'] == (repeat == 0) and data['prompt_sha256'] == prompt and
           positive(data['ttft_s']) and positive(data['decode_tps']) and positive(data['wall_s']) and data['ttft_s'] <= data['wall_s'] and
           data['usage'] == usage and data['timings'] == timings and data['decode_tps'] == timings['predicted_per_second'] and
           request['value']['chat_template_kwargs']['enable_thinking'] is False and
           output_hashes == window['greedy_hashes'][str(size)] == [content['sha256'], reasoning['sha256']] and
           output_hashes == stream_hashes, 'P4 request or retained output lineage changed')
    if phase:
        filename = f'{name}-{phase}-residency.json'
        demand(item['residency'] == filename, 'P4 source sample is missing from the required request boundary')
        sample = capture(directory / filename)
        demand(sample['value']['regions_sha256'] == window['regions_sha256'], 'P4 source sample has a different region digest')
        bounds = (began, started) if phase == 'before' else (ended, stop)
        source_snapshot(sample['value'], geometry, (window['view'],), *bounds,
                        window['pages_per_sample'], window['seed'], scope_value)
        refs['residency'] = sample
        if phase == 'after':
            ended = timepoint(sample['value']['completed'])
    else:
        demand('residency' not in item, 'Unexpected P4 source sample role')
    row = dict(reference(result), result=data, request=request['value'], request_ref=reference(request), scope_id=scope_id,
               evidence={key: reference(value) for key, value in refs.items()})
    if boundary_check is screen_safety:
        row['cpu_overlap'] = {label: {key: rec['value'][key] for key in PROCESSES if key != 'model_processes'}
                              for label, rec in (('before', before), ('after', after))}
    beginning, first_token = (snapshots[key]['processes'] for key in ('start', 'first_token'))
    engine_name = 'llama-server' if window['view'] == 'llama' else 'strata-dsv41'
    engine_pids = [pid for pid, process in beginning.items() if process['comm'] == engine_name]
    demand(len(engine_pids) == 1, 'P4 resource window must identify one inference engine')
    pid = engine_pids[0]
    demand(pid in first_token and beginning[pid]['starttime_ticks'] == first_token[pid]['starttime_ticks'],
           'P4 engine process identity changed before first token')
    row['first_token_io'] = dict(read_bytes=first_token[pid]['io']['read_bytes'] - beginning[pid]['io']['read_bytes'],
                                 major_faults=first_token[pid]['majflt'] - beginning[pid]['majflt'])
    if phase == 'before':
        row['source_resident_fraction'] = {kind: value['estimated_resident_fraction']
            for kind, value in sample['value']['views'][window['view']]['total'].items()}
    return row, ended


def read_launch(base, row, plan, geometry, prompts, previous_stop, first, capture, boundary_check=strict_quiet, pooled_screen=False):
    if pooled_screen:
        boundary_check = screen_safety
    scope = base / Path(row['scope'])
    arm, number, view = (row[k] for k in ('arm', 'launch_pass', 'view'))
    directory = scope / 'p4-window'
    start = capture(scope / 'start.json')
    stop = capture(scope / 'result.json')
    load = capture(scope / 'load-ready.json')
    kernel = capture(scope / 'scope.json')
    profile = capture(scope / 'p4-launch-profile.json')
    probe = capture(scope / 'probe.json')
    report = capture(directory / 'window.json')
    s, z, l, k, window = (entry['value'] for entry in (start, stop, load, kernel, report))
    began, ended, ready = timepoint(s['start']), timepoint(z['stop']), timepoint(l['ready_at'])
    demand(previous_stop <= began < ready < ended and positive(l['health_elapsed_s']), 'P4 launch times or readiness are invalid')
    fields = ('arm', 'start', 'command', 'binary_sha256', 'result_path', 'unit', 'launch_environment', 'memory_max', 'cpus')
    demand(all(s[key] == z[key] for key in fields) and s['arm'] == arm and s['result_path'] == str(scope) and
           z['returncode'] == 0 and z['reason'] is None and z['scope_verified'] is True and not z['enforcement_test'] and
           s['memory_max'] == 100 * 1024**3 and s['cpus'] == '0-7' and z['min_mem_available_bytes'] >= 8 * 1024**3 and
           not any(int(z['memory_events'].get(key, 0)) for key in OOM_KEYS) and
           'Result=oom-kill' not in z.get('systemd_properties', ''), 'P4 capped scope failed or differs from its start receipt')
    cgroup = Path(k['cgroup'])
    demand(cgroup.is_relative_to('/sys/fs/cgroup') and cgroup.name == s['unit'] and
           (scope / 'monitor.ready').is_file() and type(k['pid']) is int and k['pid'] > 0 and
           all(k['actual'].get(key) == value for key, value in KERNEL.items()), 'P4 kernel scope controls are not established')
    demand(profile['sha256'] == row['profile_sha256'], 'P4 launch profile changed after admission')
    provenance = profile_provenance(base, scope, arm, view, profile['value'], s, l, geometry, capture)
    stride, seed = plan.get('pages_per_sample', 4096), plan.get('seed', 20261120)
    expected_window = dict(schema='spark-pooled30-window/1' if pooled_screen else 'spark-p4-window/2',
                           status='complete', arm=arm, launch_pass=number,
                           view=view, scope=str(scope), binary_sha256=s['binary_sha256'], pages_per_sample=stride, seed=seed,
                           prompts_sha256=plan['prompt_manifest_sha256'], regions_sha256=plan['regions_sha256'])
    demand(all(window[key] == value for key, value in expected_window.items()) and
           probe['value']['window'] == ('pooled' if pooled_screen else 'p4') and
           probe['value']['greedy_hashes'] == window['greedy_hashes'], 'P4 window and probe receipt do not establish completed launch')
    if number == 1:
        demand('first_window_sha256' not in window, 'First P4 launch unexpectedly refers to another window')
        first[arm] = report
    else:
        demand(window['first_window_sha256'] == first[arm]['sha256'] and
               window['greedy_hashes'] == first[arm]['value']['greedy_hashes'], 'Second P4 window did not bind the exact first window')

    preflights = base / 'OPS/p3/early-preflights'
    quiet_path = preflights / f'{scope.name}-quiet.json'
    quiet, original_quiet = capture(directory / 'quiet-prelaunch.json'), capture(quiet_path)
    (screen_safety if pooled_screen else strict_quiet)(quiet['value'], prelaunch=True)
    demand(quiet['sha256'] == original_quiet['sha256'] == window['quiet_preflight_sha256'], 'P4 window quiet receipt differs from the prelaunch artifact')
    quiet_time = datetime.fromtimestamp(quiet_path.stat().st_mtime, timezone.utc)
    conditioning = capture(preflights / f'{scope.name}-source.json')
    cold = conditioning['value']
    (screen_safety if pooled_screen else strict_quiet)(cold['quiet'], prelaunch=True)
    expected_paths = sorted({f['resolved_path'] for v in geometry['views'].values() for f in v['files']})
    demand(cold['schema'] == 'spark-source-cache-conditioning/1' and cold['method'] == 'file-specific POSIX_FADV_DONTNEED' and
           cold['regions_sha256'] == window['regions_sha256'] and cold['advised_files'] == expected_paths and quiet_time <= began,
           'P4 source conditioning did not use the common frozen source regions')
    source_snapshot(cold['before'], geometry, ('llama', 'strata'), previous_stop, quiet_time, stride, seed)
    source_snapshot(cold['after'], geometry, ('llama', 'strata'), timepoint(cold['before']['completed']), quiet_time, stride, seed)

    memory = capture(scope / 'memory.jsonl', 'application/x-ndjson')
    monitor = [json.loads(raw) for raw in memory['raw'].splitlines()]
    demand(monitor and all(began <= timepoint(sample['time']) <= ended and sample['available'] >= 8 * 1024**3 and
                           not any(int(sample['events'].get(key, 0)) for key in OOM_KEYS) for sample in monitor),
           'P4 watchdog memory series is missing or contains a safety event')
    schedule = planned_window(number, pooled_screen=pooled_screen)
    demand(len(window['requests']) == len(schedule), 'Window did not retain the full scheduled sequence')
    requests = []
    previous = ready
    for (name, repeat, size, phase), item in zip(schedule, window['requests']):
        request, previous = request_evidence(capture, directory, name, repeat, size, phase, item, arm, previous, ended,
                                             window, k, prompts[size], geometry, stop['artifact_id'], boundary_check)
        requests.append(request)
    extra = {'engine_log': capture(scope / 'stderr.log', 'text/plain')}
    if 'load_ready_residency' in window:
        demand(window['load_ready_residency'] == 'load-ready-residency.json', 'Invalid post-load sample path')
        after_load = capture(directory / window['load_ready_residency'])
        source_snapshot(after_load['value'], geometry, (view,), ready,
                        timepoint(requests[0]['result']['started']), stride, seed, k)
        extra['load_ready_residency'] = after_load
    if view == 'strata':
        extra['strata_engine_log'] = capture(scope / 'engine.log', 'text/plain')
    resid = cold['after']['views'][view]['total']
    startup = {name: bucket['estimated_resident_fraction'] for name, bucket in resid.items()}
    provenance.update({key: reference(val) for key, val in extra.items()})
    record = dict(reference(stop), value=z, arm=arm, launch_pass=number, view=view, source_commit=l.get('source_commit'),
                load=dict(reference(load), seconds=l['health_elapsed_s']),
                quiet_preflight=dict(reference(quiet), quiet=quiet['value']['quiet']), start=reference(start), scope=reference(kernel),
                profile=reference(profile), window=reference(report), probe=reference(probe), memory=reference(memory),
                conditioning=reference(conditioning), prelaunch_source_fractions=startup, provenance=provenance)
    if pooled_screen:
        record['cpu_overlap_prelaunch'] = {key: quiet['value'][key] for key in PROCESSES if key != 'model_processes'}
        record['cpu_overlap_conditioning'] = {key: cold['quiet'][key] for key in PROCESSES if key != 'model_processes'}
    if plan.get('comparison_target') == 'same-budget-cc':
        log = extra['engine_log']['raw'].decode(errors='replace')
        record['matched_bank'] = same_budget_launch(s, log)
        if arm == plan['subject_arm']:
            demand(l['native_build_receipt'], 'Focused P4 subject lacks a native build receipt')
        if pooled_screen and arm == 'C2':
            from probe_candidate import C2_POOLED_SOURCE, pooled_placement_readback

            operator = capture(base / 'OPS/p3/placement-v1-matched-controls.json')
            expected = operator['value']['heldout_layer27_policy']
            path = Path(s['command'][s['command'].index('--placement-plan') + 1])
            placement = capture(path)
            proof = capture(scope / 'placement-activation.json')
            gates = {key: value for key, value in s['launch_environment'].items() if key.startswith('LLAMA_')}
            demand(l['source_commit'] == C2_POOLED_SOURCE and gates == expected['gate_on_env'] and
                   '--placement-plan-mode' not in s['command'] and placement['value']['version'] == 1 and
                   placement['sha256'] == expected['plan_sha256'] and proof['value'] == pooled_placement_readback(log, expected),
                   'Pooled C2 must prove the pinned v1 layer-27 plan and its ready-time tensor placements')
            record['placement'] = dict(proof['value'], activation=reference(proof), placement_plan=reference(placement),
                                       control=reference(operator))
        if plan.get('source_treatment') == 'direct-seed' and arm == plan['subject_arm']:
            # Use the direct-seed capsule's exact same startup accounting and per-slot evidence checks.
            sys.path.insert(0, str(HERE.parents[1] / 'jiuwenswarm/factory/ccs/spark_gap_analysis'))
            try:
                from direct_seed import seed_ledger
            finally:
                sys.path.pop(0)
            env = s['launch_environment']
            demand(plan['subject_source_commit'] == l['source_commit'] and
                   env.get('LLAMA_EXPERT_CACHE_NATIVE_PROFILE') == '1' and
                   env.get('LLAMA_EXPERT_CACHE_DIRECT_SEED') == '1', 'Unexpected direct-seed build or activation')
            profile_data = capture(Path(env['LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH']))
            activation = capture(scope / 'profile-activation.json')
            verified = seed_ledger(log, 'on', {'activation': activation}, {'profile_sha256': profile_data['sha256']},
                                   profile_data['value'], reference)
            slots = verified.pop('admitted_slots')
            verified['admitted_slot_count'] = len(slots)
            verified['admitted_slots_sha256'] = digest(json.dumps(slots, sort_keys=True).encode())
            record['direct_seed'] = verified
        if arm == 'C3' and arm == plan['subject_arm']:
            demand(s['launch_environment'].get('LLAMA_EXPERT_CACHE_NATIVE_PROFILE') == '1' and
                   re.search(r'expert_weight_cache_native_profile: active\b', log) and
                   re.search(r'expert_weight_cache_native_profile: stats .*\bactive=1\b', log),
                   'Focused P4 native cache profile did not show activation and terminal stats')
        if plan['subject_arm'] == 'C5':
            gates = {key: value for key, value in s['launch_environment'].items() if key.startswith('LLAMA_')}
            demand(gates == ({'LLAMA_BATCH_LAYOUT': '1'} if arm == 'C5' else {}),
                   'Mapper comparison has unexpected runtime gates')
            if arm == 'C5':
                cuts = re.findall(r'batch_layout_mapper: layout length=2048 cached_prefix=0 begin=(\d+) end=(\d+) ', log)
                stats = re.findall(r'batch_layout_mapper: stats decisions=(\d+) rows=(\d+) bypasses=(\d+)', log)
                demand(len(stats) == 1, 'Mapper shutdown statistics are missing or ambiguous')
                expected = sum(row['result']['prompt_tokens'] == 2048 for row in requests)
                record['mapper'] = dict(decisions=int(stats[0][0]), rows=int(stats[0][1]), bypasses=int(stats[0][2]),
                    cuts_2048=cuts, prompts_2048=expected,
                    all_2048_split=cuts == [('0', '1536'), ('1536', '2048')] * expected,
                    engine_log=reference(extra['engine_log']))
            else:
                demand('batch_layout_mapper:' not in log, 'Stock control emitted mapper markers')
        if plan['subject_arm'] == 'C4':
            predictor_gate = s['launch_environment'].get('LLAMA_EXPERT_PREDICT')
            demand(predictor_gate == ('1' if arm == 'C4' else None), 'Focused P4 C4 treatment must use only its declared predictor gate')
            if arm == 'C4':
                demand(set(key for key in s['launch_environment'] if key.startswith('LLAMA_')) == {'LLAMA_EXPERT_PREDICT'},
                       'C4 must run directly on the stock native bank without another capsule gate')
                result = predictor_counters(log)['decode']
                totals = result['totals']
                issue = None if totals is None else totals['issued']
                record['predictor_decode'] = dict(
                    status='unobserved' if issue is None else 'observed-issue' if issue else 'observed-no-issue',
                    totals=totals, graph_rows=len(result['rows']), failed_graph_rows=result['failed_graph_rows'],
                    activation_marker='expert_demand_predictor: active native_bank phase=decode' in log,
                    inactive_reasons=sorted(set(re.findall(r'expert_demand_predictor: inactive \(([^\n]+)\)', log))),
                    engine_log=reference(extra['engine_log']))
                if pooled_screen:
                    rows = result['rows']
                    record['predictor_decode']['observed_requests'] = len({r['request_id'] for r in rows})
                    record['predictor_decode']['requests_with_useful_ready'] = len({r['request_id'] for r in rows
                                                                                   if r['counts']['useful_ready']})
                    record['predictor_decode']['demand'] = {key: sum(row['counts'][key] for row in rows)
                        if rows and all(key in row['counts'] for row in rows) else None
                        for key in ('demand_selected', 'demand_hits', 'demand_issued_bytes')}
            else:
                demand('expert_demand_predictor:' not in log, 'Focused P4 stock A+ unexpectedly reported predictor activity')
    return record, requests, ended


def evidence_from_lab(base, plan, plan_ref, capture, boundary_check=None):
    prompt_file = capture(HERE / 'prompts/MANIFEST.json')
    region_file = capture(base / 'OPS/p4/source-regions.json')
    demand(prompt_file['sha256'] == plan['prompt_manifest_sha256'] and region_file['sha256'] == plan['regions_sha256'],
           'P4 source geometry or prompts differ from admission pins')
    prompts = {row['target_tokens_including_template']: row['prompt_sha256'] for row in prompt_file['value']['prompts']}
    demand(set(prompts) == set(SIZES), 'P4 requires both fixed prompt sizes')
    for size, expected in prompts.items():
        prompt = capture(HERE / 'prompts' / f'{size}.txt', 'text/plain')
        demand(prompt['sha256'] == expected, 'P4 fixed prompt file changed')
    scopes, requests, first = [], [], {}
    previous = timepoint(plan['frozen_at'])
    for row in plan['launches']:
        admit = strict_quiet if boundary_check is None else boundary_check(row)
        scope, items, previous = read_launch(base, row, plan, region_file['value'], prompts, previous, first, capture, admit)
        scopes.append(scope)
        requests.extend(items)
    target = plan.get('comparison_target', 'matrix')
    if target == 'same-budget-cc':
        demand(all(scope['matched_bank'] == scopes[0]['matched_bank'] for scope in scopes[1:]),
               'Focused P4 actual bank allocation or effective launch settings differ among the mirrored scopes')
        demand(plan.get('bank_budget_mib', scopes[0]['matched_bank']['requested_mib']) == scopes[0]['matched_bank']['requested_mib'],
               'Focused P4 native budget differs from manifest admission')
        if plan.get('source_treatment') == 'direct-seed':
            direct = [s['direct_seed'] for s in scopes if s['arm'] == plan['subject_arm']]
            demand(len(direct) == 2 and direct[0]['admitted_slots_sha256'] == direct[1]['admitted_slots_sha256'],
                   'Direct-seed passes did not admit the same exact slots')
        demand(first['A+']['value']['greedy_hashes'] == first[plan['subject_arm']]['value']['greedy_hashes'],
               'Focused P4 candidate and A+ differ on greedy output or reasoning')
    return dict(mode='p4-abba', comparison_target=target, subject_arm=plan.get('subject_arm'),
                launch_manifest=plan_ref, source_regions=reference(region_file),
                prompt_manifest=dict(reference(prompt_file), value=prompt_file['value']), scopes=scopes, requests=requests)


def fmt(value):
    return 'unavailable' if value is None else f'{value:.3f}'


def fmt_values(value):
    if isinstance(value, dict):
        return ', '.join(f'{key} {fmt(metric)}' for key, metric in value.items())
    if isinstance(value, (list, tuple)):
        return ', '.join(map(fmt, value))
    return 'unavailable'


def paired_comparisons(comparisons):
    for key, value in comparisons.items():
        if isinstance(value, dict) and 'estimate' in value:
            yield (key.replace('_', ' '), fmt(value['estimate']), fmt_values(value.get('observed_range')),
                   fmt_values(value.get('pass_medians')), fmt_values(value.get('conditional_ci95')))
        elif isinstance(value, dict):
            for suffix, *values in paired_comparisons(value):
                yield f'{key.replace("_", " ")} {suffix}', *values
        elif isinstance(value, (int, float)):
            yield key.replace('_', ' '), fmt(value), 'unavailable', 'unavailable', 'unavailable'


def effect_rows(analysis, evidence, verification):
    if evidence['comparison_target'] != 'same-budget-cc':
        return None
    subject = evidence['subject_arm']
    bank = evidence['scopes'][0]['matched_bank']
    profiles = {scope['arm']: dict(profile_sha256=scope['profile']['sha256'],
                                  binary_sha256=scope['value']['binary_sha256'], source_commit=scope['source_commit'])
                for scope in evidence['scopes'] if scope['launch_pass'] == 1}
    cells = {(row['arm'], row['prompt_tokens']): row for row in analysis['measurements']}
    rows = []
    for size in SIZES:
        base, cc = (cells[(arm, size)] for arm in ('A+', subject))
        effects = cc['comparisons']
        metrics = {key: effects[key] for key in ('paired_ttft_seconds_saved_vs_Aplus',
                   'paired_decode_tps_gained_vs_Aplus', 'inverse_ttft_vs_Aplus')}
        demand(all({'estimate', 'observed_range', 'pass_medians', 'conditional_ci95'} <= set(v)
                   for key, v in metrics.items() if key.startswith('paired_')),
               'Focused native analysis did not retain the full paired estimates')
        rows.append(dict(prompt_tokens=size, n=cc['n'], control={k: base[k] for k in ('ttft_s', 'decode_tps')},
                         candidate={k: cc[k] for k in ('ttft_s', 'decode_tps')}, **metrics))
    projection = dict(schema='spark-p4-focused/1', subject_arm=subject, budget_mib=bank['requested_mib'],
                      allocated_mib=bank['allocated_mib'], profiles=profiles, verification=verification, rows=rows)
    if subject == 'C4':
        projection['predictor_decode_by_pass'] = [dict(pass_number=scope['launch_pass'], **scope['predictor_decode'])
                                                   for scope in evidence['scopes'] if scope['arm'] == subject]
    return projection


def render(analysis, evidence, capsule):
    screened = analysis['mode'] == 'p4-build-overlap'
    by_arm = {scope['arm'] for scope in evidence['scopes']}
    actual = {(cell['arm'], cell['prompt_tokens']): cell for cell in analysis['measurements']}
    demand(set(actual) == {(arm, size) for arm in by_arm for size in SIZES} and
           all(cell['n'] == 10 for cell in actual.values()) and analysis['mode'] in ('p4-abba', 'p4-build-overlap'),
           'The native release did not produce ten eligible requests per size and arm')
    summary = (f'P4 measured {len(by_arm)} arms in two mirrored launches with ten timed requests per arm at each prompt size. '
               'First-token latency and decode throughput are reported separately.')
    if evidence['comparison_target'] == 'same-budget-cc':
        subject = evidence['subject_arm']
        phrases = []
        for size in SIZES:
            saved = actual[(subject, size)]['comparisons']['paired_ttft_seconds_saved_vs_Aplus']['estimate']
            direction = 'sooner' if saved > 0 else 'later'
            phrases.append(f'{abs(saved):.2f} seconds {direction} at {size} tokens')
        summary = f'Across ten pairs per size, {subject} returned the first token ' + ' and '.join(phrases) + ' than same-budget stock A+ by the paired medians.'
    if screened:
        summary = 'Partially build-overlapped screening. ' + summary
    runtime = ('Every launch passed quiet preflight. Two authorized builds overlapped the final A+ scope. '
               'The ten-pair result is descriptive screening.' if screened else
               'All admitted scopes passed the strict quiet preflight and every retained request boundary.')
    lines = ['# Spark P4 matched benchmark', '', summary, '', runtime + ' '
             'The boundary process checks cannot observe activity that begins and ends between snapshots.', '',
             'Intervals resample matched request repeats within the two fixed launch windows. '
             'They describe those launches and exclude between-launch variation.', '']
    if 'scope_amendment' in evidence:
        lines += ['The initial reverse C3 launch completed all requests, but its cap monitor lost the final '
                  'process-exit receipt during cgroup teardown. Its entire window was excluded. A prospectively '
                  'recorded amendment repeated that C3 position from identical cold conditioning before the final '
                  'A+ control. The ten pairs use four launches with complete cap receipts. The original window, '
                  'memory trace and shutdown journals are retained as excluded evidence.', '']
    if evidence['comparison_target'] == 'same-budget-cc':
        bank = evidence['scopes'][0]['matched_bank']
        lines += [f'A+ and {evidence["subject_arm"]} used the same {bank["requested_mib"]:,} MiB budget, '
                  f'{bank["allocated_mib"]:,.2f} MiB logged allocation and effective runtime settings.', '']
    for scope in evidence['scopes']:
        if 'mapper' in scope:
            mapping = scope['mapper']
            split = ('Every 2048-token request used the 1536/512 split.' if mapping['all_2048_split'] else
                     'The observed cuts did not reproduce the planned 1536/512 split on every 2048-token request.')
            lines += [f"C5 pass {scope['launch_pass']} logged {mapping['decisions']} scheduling decisions and "
                      f"{mapping['bypasses']} bypasses across all requests. {split}", '']
    predictor = [scope for scope in evidence['scopes'] if 'predictor_decode' in scope]
    if predictor:
        lines += ['## Native predictor decode readiness', '',
                  'These engine counters include warmups and measured requests. Issue and transfer completion are separate from useful demand consumption.', '',
                  '| Pass | Coverage | Opportunities | Requested | Already resident | Issued | Completed | Useful | Late | Misses | Unused | Reused slots |',
                  '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        fields = ('opportunities', 'requested', 'already_resident', 'issued', 'completed_transfers', 'useful_ready',
                  'late', 'miss', 'unused', 'reused')
        for scope in predictor:
            readback = scope['predictor_decode']
            counts = readback['totals'] or {}
            values = ' | '.join('unobserved' if counts.get(k) is None else f'{counts[k]:,}' for k in fields)
            lines.append(f'| {scope["launch_pass"]} | {readback["status"]} | {values} |')
        lines.extend(['', 'Retained graph outcome rows and submitted, completed, useful and wasted byte totals are linked to each engine log.', ''])
    ordered = [scope['arm'] for scope in evidence['scopes'] if scope['launch_pass'] == 1]
    for size in SIZES:
        lines += [f'## {size}-token prompts', '', '| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | '
                  'Engine prefill median (ms) | Source expert pages resident at request (median) |',
                  '| --- | ---: | ---: | ---: | ---: | ---: |']
        comparisons = []
        for arm in ordered:
            cell = actual[(arm, size)]
            low, high = cell['range_s']
            expert = [row['source_resident_fraction']['expert'] for row in evidence['requests'] if
                      row['result']['arm'] == arm and row['result']['prompt_tokens'] == size and not row['result']['discard'] and
                      row['source_resident_fraction'].get('expert') is not None]
            share = f'{median(expert):.1%}' if expert else 'unavailable'
            lines.append(f'| {arm} | {cell["n"]} | {fmt(cell["ttft_s"])} [{fmt(low)}, {fmt(high)}] | '
                         f'{fmt(cell.get("decode_tps"))} | {fmt(cell.get("engine_prefill_ms"))} | {share} |')
            comparisons.extend((arm, *row) for row in paired_comparisons(cell['comparisons']))
        if comparisons:
            lines += ['', '| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |',
                      '| --- | --- | ---: | ---: | ---: | ---: |']
            lines.extend(f'| {arm} | {name} | {estimate} | {observed} | {passes} | {bounds} |'
                         for arm, name, estimate, observed, passes, bounds in comparisons)
        lines.append('')
    lines += ['## Startup requests by position', '',
              'Each pass began with the common file-specific source conditioning. Read and fault counts cover the engine process through the first token.', '',
              '| Arm | Pass | Request position | Prompt tokens | Load to ready (s) | TTFT (s) | Decode (tokens/s) | Reads (GB) | Major faults |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for scope in evidence['scopes']:
        warmups = [r for r in evidence['requests'] if r['scope_id'] == scope['artifact_id'] and r['result']['discard']]
        for position, row in enumerate(warmups, 1):
            result, io = row['result'], row['first_token_io']
            lines.append(f'| {scope["arm"]} | {scope["launch_pass"]} | {position} | {result["prompt_tokens"]} | '
                         f'{scope["load"]["seconds"]:.2f} | {result["ttft_s"]:.3f} | {result["decode_tps"]:.2f} | '
                         f'{io["read_bytes"] / 1e9:.3f} | {io["major_faults"]:,} |')
    for scope in evidence['scopes']:
        if 'direct_seed' in scope:
            io = scope['direct_seed']['direct_io']
            lines += ['', f'Direct-seed pass {scope["launch_pass"]} uploaded {io["uploaded_payload_bytes"]:,} bytes '
                      f'in {io["elapsed_us"] / 1e6:.3f} s, with {io["failures"]} failures and {io["fallback_count"]} fallbacks.']
    lines.append('')
    lines += ['## Change within each measured launch', '',
              'Last minus first measured position shows residual movement inside each launch. Exact request samples are retained.', '',
              '| Arm | Pass | Prompt tokens | TTFT change (s) | Decode change (tokens/s) |',
              '| --- | ---: | ---: | ---: | ---: |']
    for scope in evidence['scopes']:
        for size in SIZES:
            results = [row['result'] for row in evidence['requests'] if row['scope_id'] == scope['artifact_id'] and
                       row['result']['prompt_tokens'] == size and not row['result']['discard']]
            ttft, decode = (results[-1][key] - results[0][key] for key in ('ttft_s', 'decode_tps'))
            lines.append(f'| {scope["arm"]} | {scope["launch_pass"]} | {size} | {ttft:+.3f} | {decode:+.3f} |')
    lines.append('')
    lines += ['## Load and memory by launch', '', '| Arm | Pass | Load to ready (s) | Scope peak (GiB) | Host minimum available (GiB) |',
              '| --- | ---: | ---: | ---: | ---: |']
    for scope in evidence['scopes']:
        cap = scope['value']
        lines.append(f'| {scope["arm"]} | {scope["launch_pass"]} | {fmt(scope["load"]["seconds"])} | '
                     f'{fmt(cap["peak_memory_bytes"] / 1024**3)} | {fmt(cap["min_mem_available_bytes"] / 1024**3)} |')
    lines += ['', 'Source-page residency describes the external inode cache. Scope memory and GPU residency are separate quantities.', '',
              f'Native analysis `{capsule["id"]}` version `{capsule["version"]}`, release `{capsule["release"]}`.', '']
    return summary, '\n'.join(lines).encode()


def apply_scope_amendment(base, plan, manifest_sha, amendment_path, amendment_sha, capture):
    amendment = capture(amendment_path)
    change = amendment['value']
    demand(amendment['sha256'] == amendment_sha and change['manifest_sha256'] == manifest_sha and
           change['schema'] == 'spark-p4-scope-replacement/1', 'Scope amendment digest or parent is invalid')
    old, new = (Path(change[key]) for key in ('replaced_scope', 'replacement_scope'))
    launches = plan['launches']
    matches = [row for row in launches if Path(row['scope']) == old]
    demand(len(matches) == 1 and new.parent == old.parent == Path('OPS/runs') and
           (base / new).resolve(strict=True) == base / new and
           all(row['scope'] != str(new) for row in launches), 'Scope replacement must use a fresh local scope')
    old_dir = base / old
    demand(not (old_dir / 'result.json').exists(), 'Excluded scope already has a final receipt')
    files = [(old_dir / 'p4-window/window.json', 'application/json', 'excluded_window_sha256'),
             (old_dir / 'memory.jsonl', 'application/x-ndjson', 'excluded_memory_sha256'),
             (amendment_path.parent / 'cache60-incomplete-monitor.log', 'text/plain', 'monitor_journal_sha256'),
             (amendment_path.parent / 'cache60-incomplete-unit.log', 'text/plain', 'scope_journal_sha256')]
    for filename, media, key in files:
        demand(capture(filename, media)['sha256'] == change[key], 'Excluded-scope evidence changed')
    started = timepoint(json.loads(safe_bytes(base / new / 'start.json'))['start'])
    closed = timepoint(json.loads(safe_bytes(old_dir / 'memory.jsonl').splitlines()[-1])['time'])
    demand(closed < timepoint(change['frozen_at']) <= started and
           datetime.fromtimestamp(amendment_path.stat().st_mtime, timezone.utc) <= started,
           'Scope substitution must be recorded after the incomplete attempt and before its replacement')
    matches[0]['scope'] = str(new)
    return reference(amendment)


def apply_quiet_control(base, plan, path, pin, manifest_sha, retry_sha, capture):
    amendment = capture(path)
    change = amendment['value']
    row = plan['launches'][-1]
    scopes = [item['scope'] for item in plan['launches'][:-1]]
    demand(change['schema'] == 'spark-p4-quiet-control-amendment/1' and amendment['sha256'] == pin
           and change['manifest_sha256'] == manifest_sha and change['previous_amendment_sha256'] == retry_sha
           and row['arm'] == 'A+' and row['launch_pass'] == 2
           and change['replaced_scope'] == row['scope'] and change['profile_sha256'] == row['profile_sha256'],
           'Quiet control amendment must identify the original manifest, retry and frozen final A+ profile')
    new = Path(change['replacement_scope'])
    demand(new.parent == Path('OPS/runs') and (base/new).resolve(strict=True) == base/new
           and str(new) not in scopes + [row['scope']] and change['launch_order'] == scopes + [str(new)],
           'Amended scope order differs from the predeclared four launches')
    excluded = capture(base/row['scope']/'result.json')
    start = timepoint(json.loads(safe_bytes(base/new/'start.json'))['start'])
    demand(timepoint(excluded['value']['stop']) < timepoint(change['frozen_at']) <= start
           and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) <= start,
           'Control replacement must be declared before the new launch')
    samples = capture(base/new/'host-activity.jsonl', 'application/x-ndjson')
    activity = [json.loads(line) for line in samples['raw'].splitlines()]
    demand(activity and all(process['name'] in {'rsync', 'scp', 'rclone', 'sftp-server'}
                            for sample in activity for process in sample['browsers_or_transfer_processes']),
           'Browser activity observed during the replacement control')
    row['scope'] = str(new)
    return reference(amendment)


def publish(base, path, manifest_sha, amendment_path=None, amendment_sha=None,
            control_path=None, control_sha=None):
    manifest_raw, plan = frozen_plan(path, manifest_sha, base)
    iteration = plan['iteration_id']
    first = base / Path(plan['launches'][0]['scope'])
    first_start = json.loads(safe_bytes(first / 'start.json'))['start']
    demand(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) <= timepoint(first_start),
           'Frozen P4 manifest file postdates the first launch')
    home = base / 'factory-runs/spark-direct-benchmarks'
    out = base / 'OPS/iterations' / iteration
    if control_path:
        demand(iteration == 'spark-p4-cache60-attribution' and amendment_path is not None,
               'The quiet control is a revision of the amended 60 GiB experiment')
        iteration = 'spark-p4-cache60-build-overlap'
        out = base / 'OPS/iterations' / iteration
    revision = '-v3' if control_path else ''
    artifact_root = iteration + ('/quiet-v3' if control_path else '')
    observation = iteration + ':report' + revision
    with Store(home) as store:
        store.get_task(TASK)
        try:
            existing = store.read(TASK, observation)['values']
        except NotFound:
            existing = None
        if existing:
            report = existing['report']
            demand(existing['plan'].get('scope_amendment', {}).get('sha256') == amendment_sha and
                   existing['plan'].get('control_amendment', {}).get('sha256') == control_sha and
                   existing['plan']['manifest']['sha256'] == manifest_sha and
                   store.read_artifact(TASK, report['artifact_id'])['sha256'] == report['sha256'],
                   'P4 iteration already identifies a different manifest or report')
            report_bytes = store.artifact_bytes(TASK, report['artifact_id'])
            analysis_bytes = store.artifact_bytes(TASK, existing['analysis']['result_artifact']['artifact_id'])
            envelope = existing
        else:
            retained = []

            def put(artifact_id, raw, media='application/json'):
                return reference(store.put_artifact(TASK, artifact_id, raw, media, None))

            def capture(filepath, media='application/json'):
                raw = safe_bytes(filepath)
                label = filepath.relative_to(base if filepath.is_relative_to(base) else REPO).as_posix()
                ref = put(f'{artifact_root}/raw/{label}@{digest(raw)}', raw, media)
                retained.append(ref['artifact_id'])
                return dict(ref, value=json.loads(raw)) if media == 'application/json' else dict(ref, raw=raw)

            plan_ref = put(artifact_root + '/admitted-launches.json', manifest_raw)
            amendment_ref = None
            if amendment_path is not None:
                amendment_ref = apply_scope_amendment(base, plan, manifest_sha, amendment_path,
                                                      amendment_sha, capture)
            control_ref = (apply_quiet_control(base, plan, control_path, control_sha, manifest_sha, amendment_sha, capture)
                           if control_path else None)
            evidence = evidence_from_lab(base, plan, plan_ref, capture)
            if amendment_ref:
                evidence.update(scope_amendment=amendment_ref, effective_launches=plan['launches'])
            if control_ref:
                evidence['control_amendment'] = control_ref
            payload = json_bytes(evidence)
            evidence_ref = put(artifact_root + '/analysis-input.json', payload)
            host = Host(home / 'analysis-ccv2')
            release = host.seal(REPO / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
            capsule = dict(id=CAPSULE, version=host.describe(release)['version'], release=release)
            key = f'{iteration}:{release}:{evidence_ref["sha256"]}'
            analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key + ':analyze', grants=['process.exec'])
            analysis = analyzed.get('outputs', {}).get('analysis')
            demand(analysis is not None, f'P4 native analysis refused the evidence: {analyzed.get("diagnostics")}')
            checked = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis}, key=key + ':verify', grants=['process.exec'])
            demand(checked.get('outputs', {}).get('verification', {}).get('done') is True, 'P4 native verifier did not reproduce the analysis')
            summary, report_bytes = render(analysis, evidence, capsule)
            analysis_bytes = json_bytes(analysis)
            analysis_ref = put(artifact_root + '/analysis.json', analysis_bytes)
            verification = put(artifact_root + '/verify-receipt.json', json_bytes(checked))
            outputs = [analysis_ref, put(artifact_root + '/analyze-receipt.json', json_bytes(analyzed)), verification,
                       put(artifact_root + '/release-manifest.json', (host.store / 'releases' / release / 'manifest.json').read_bytes())]
            if control_ref:
                by_position = {(r['result']['arm'], r['result']['prompt_tokens'], r['result']['repeat']): r['first_token_io']
                               for r in evidence['requests'] if not r['result']['discard']}
                reads = {}
                for size in SIZES:
                    differences = [(by_position['A+', size, i], by_position['C3', size, i]) for i in range(1, 11)]
                    reads[str(size)] = {key: median(a[key] - b[key] for a, b in differences)
                                        for key in ('read_bytes', 'major_faults')}
                report_bytes += (b'\n## Prospective final-control replacement\n\n'
                                 b'The closing stock pass in report-v2 overlapped builds. The owner declared its whole-scope '
                                 b'replacement before the fresh control started. The three earlier admitted launches are reused. '
                                 b'The orchestrator disclosed a concurrent idle-priority file pull. Its storage impact was not isolated.\n')
                for size, io in reads.items():
                    report_bytes += (f"\nAt {size} tokens the paired median stock-minus-C3 difference before the first "
                                     f"token was {io['read_bytes']/1e9:.2f} GB read and {io['major_faults']:,.0f} major faults.\n").encode()
            report = dict(put(iteration + '/report' + revision + '.md', report_bytes, 'text/markdown'), summary=summary, status='verified-p4')
            input_ids = list(dict.fromkeys([plan_ref['artifact_id'], evidence_ref['artifact_id'], *retained]))
            output_ids = [ref['artifact_id'] for ref in outputs]
            envelope = dict(schema='spark-factory-iteration/1', iteration_id=iteration, predecessor_report_ids=[],
                plan=dict(decision_id=None, incoming_report_ids=[], builder_ccs=[], manifest=plan_ref,
                          summary='Run the frozen admitted arms in two quiet mirrored passes on the fixed Spark prompts.'),
                do=dict(source_commit=None, diff_artifact_id=None, verification_receipt_ids=[], build_receipt_ids=[]),
                lab=dict(status='complete', result_artifact_ids=input_ids),
                analysis=dict(ccs=[capsule], output_artifact_ids=output_ids, result_artifact=analysis_ref),
                report=report, next_plan=dict(decision_id=None))
            if amendment_ref:
                envelope['plan']['scope_amendment'] = amendment_ref
            if control_ref:
                prior_id = iteration + ':report-v2'
                prior = store.read(TASK, prior_id)['values']
                demand(prior['report']['revision'] == 2, 'Expected native screening predecessor')
                envelope['analysis']['paired_first_token_io_saved'] = reads
                envelope['do'] = prior['do']
                envelope['predecessor_report_ids'] = [prior_id]
                envelope['plan'].update(control_amendment=control_ref, incoming_report_ids=[prior_id],
                                        builder_ccs=prior['plan']['builder_ccs'], source_decision=prior['plan']['source_decision'],
                                        summary='Replace the build-overlapped closing stock control and measure all ten pairs at each size.')
                envelope['report'].update(revision=3, supersedes_observation_id=prior_id,
                                          supersedes_artifact_id=prior['report']['artifact_id'])
            focused = effect_rows(analysis, evidence, verification)
            if focused:
                envelope['analysis']['focused_comparison'] = focused
            kind = 'factory_iteration_report_revision' if control_ref else 'factory_iteration_report'
            append_once(store, TASK, dict(obs_id=observation, kind=kind, values=envelope,
                source_artifacts=input_ids + output_ids + [report['artifact_id']]))

    out.mkdir(parents=True, exist_ok=True)
    for name, raw in (('report' + revision + '.md', report_bytes), ('analysis' + revision + '.json', analysis_bytes), ('iteration' + revision + '.json', json_bytes(envelope))):
        dest = out / name
        temporary = dest.with_suffix('.tmp')
        temporary.write_bytes(raw)
        temporary.replace(dest)
    return dict(home=str(home), task_id=TASK, observation_id=observation, artifact_id=report['artifact_id'], sha256=report['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--scope-amendment', type=Path)
    parser.add_argument('--scope-amendment-sha256')
    parser.add_argument('--control-amendment', type=Path)
    parser.add_argument('--control-amendment-sha256')
    parser.add_argument('--export', type=Path, help='Native export destination, defaulting to the iteration export directory')
    args = parser.parse_args()
    base = args.base.resolve(strict=True)
    if bool(args.scope_amendment) != bool(args.scope_amendment_sha256):
        parser.error('Supply the prospective scope amendment and its SHA-256 together')
    amendment = args.scope_amendment.resolve(strict=True) if args.scope_amendment else None
    if bool(args.control_amendment) != bool(args.control_amendment_sha256):
        parser.error('Supply the control amendment and its SHA-256 together')
    control = args.control_amendment.resolve(strict=True) if args.control_amendment else None
    report = publish(base, args.manifest.absolute(), args.manifest_sha256, amendment, args.scope_amendment_sha256,
                     control, args.control_amendment_sha256)
    iteration = report['observation_id'].split(':')[0]
    out = args.export or base / 'OPS/iterations' / iteration / ('export-v3' if control else 'export')
    bundle = out.resolve() if out.exists() else export_task(TASK, out, Path(report['home']))
    files = verify(bundle)
    exported = json.loads((bundle / 'artifacts.json').read_bytes())
    demand(any(row['artifact_id'] == report['artifact_id'] and row['sha256'] == report['sha256'] and row['exported_path']
               for row in exported), 'Native export does not contain this exact P4 report')
    report.update(export=str(bundle), verified_manifest_files=files)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
