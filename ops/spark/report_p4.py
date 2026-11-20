#!/usr/bin/env python3
"""Admit a frozen P4 launch set and publish its verified native report."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from statistics import median

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.export import export_task, verify
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest, safe_bytes
from report_p1 import CAPSULE, TASK, json_bytes


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SIZES = (512, 2048)
PROCESSES = ('build_processes', 'model_processes', 'factory_controllers', 'test_processes')
OOM_KEYS = ('oom', 'oom_kill', 'oom_group_kill')
KERNEL = {'memory.max': str(100 * 1024**3), 'memory.swap.max': '0', 'memory.oom.group': '1',
          'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}


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


def planned_window(pass_number):
    result = [(f'warmup-{p}-{n}', 0, n, 'after' if index == 1 else None)
              for p in (1, 2, 3) for index, n in enumerate(SIZES if p < 3 else SIZES[::-1])]
    for pair in range(5):
        repeat = pair + (1 if pass_number == 1 else 6)
        result.extend((f'repeat-{repeat}-{n}', repeat, n, 'before')
                      for n in (SIZES if pair % 2 == 0 else SIZES[::-1]))
    return result


def frozen_plan(path, pinned_sha, base):
    raw = safe_bytes(path)
    value = json.loads(raw)
    demand(digest(raw) == pinned_sha and value['schema'] == 'spark-p4-admitted-launches/1', 'Wrong frozen P4 launch manifest')
    demand(re.fullmatch(r'spark-p4-[a-z0-9-]+', value['iteration_id']) is not None, 'Invalid P4 iteration ID')
    launches = value['launches']
    half = len(launches) // 2
    first = [x['arm'] for x in launches[:half]]
    demand(2 <= half <= 10 and len(launches) == 2 * half and len(set(first)) == half and {'A', 'S'} <= set(first),
           'P4 requires an admitted A/S reference and two passes with distinct arms')
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
        demand(load['config'] == str(config_path) and config['value'] == expected and
               start['engine_binary'] == profile['engine_binary'] and '--profile-readonly' in expected['args'] and
               expected['args'][expected['args'].index('--pack') + 1] == geometry['views']['strata']['pack'] and
               all(start['launch_environment'][key] == expected['env'][key]
                   for key in ('DS4_UMA_HEADROOM_GIB', 'STRATA_DS4_REUSE', 'STRATA_DS4_SLOT_DIR')),
               'P4 launched Strata config differs from its admitted fair read-only profile')
        command[command.index('--config') + 1] = str(config_path)
        refs = dict(config=config, fair_template=template)
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
                     window, scope_value, prompt, geometry, scope_id):
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
        strict_quiet(entry['value'])
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
    if phase == 'before':
        row['source_resident_fraction'] = {kind: value['estimated_resident_fraction']
            for kind, value in sample['value']['views'][window['view']]['total'].items()}
    return row, ended


def read_launch(base, row, plan, geometry, prompts, previous_stop, first, capture):
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
    expected_window = dict(schema='spark-p4-window/2', status='complete', arm=arm, launch_pass=number,
                           view=view, scope=str(scope), binary_sha256=s['binary_sha256'], pages_per_sample=stride, seed=seed,
                           prompts_sha256=plan['prompt_manifest_sha256'], regions_sha256=plan['regions_sha256'])
    demand(all(window[key] == value for key, value in expected_window.items()) and probe['value']['window'] == 'p4' and
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
    strict_quiet(quiet['value'], prelaunch=True)
    demand(quiet['sha256'] == original_quiet['sha256'] == window['quiet_preflight_sha256'], 'P4 window quiet receipt differs from the prelaunch artifact')
    quiet_time = datetime.fromtimestamp(quiet_path.stat().st_mtime, timezone.utc)
    conditioning = capture(preflights / f'{scope.name}-source.json')
    cold = conditioning['value']
    strict_quiet(cold['quiet'], prelaunch=True)
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
    schedule = planned_window(number)
    demand(len(window['requests']) == len(schedule), 'P4 requires all sixteen request positions per launch')
    requests = []
    previous = ready
    for (name, repeat, size, phase), item in zip(schedule, window['requests']):
        request, previous = request_evidence(capture, directory, name, repeat, size, phase, item, arm, previous, ended,
                                             window, k, prompts[size], geometry, stop['artifact_id'])
        requests.append(request)
    extra = {'engine_log': capture(scope / 'stderr.log', 'text/plain')}
    if view == 'strata':
        extra['strata_engine_log'] = capture(scope / 'engine.log', 'text/plain')
    resid = cold['after']['views'][view]['total']
    startup = {name: bucket['estimated_resident_fraction'] for name, bucket in resid.items()}
    provenance.update({key: reference(val) for key, val in extra.items()})
    return dict(reference(stop), value=z, arm=arm, launch_pass=number, view=view, load=dict(reference(load), seconds=l['health_elapsed_s']),
                quiet_preflight=dict(reference(quiet), quiet=True), start=reference(start), scope=reference(kernel),
                profile=reference(profile), window=reference(report), probe=reference(probe), memory=reference(memory),
                conditioning=reference(conditioning), prelaunch_source_fractions=startup, provenance=provenance), requests, ended


def evidence_from_lab(base, plan, plan_ref, capture):
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
        scope, items, previous = read_launch(base, row, plan, region_file['value'], prompts, previous, first, capture)
        scopes.append(scope)
        requests.extend(items)
    return dict(mode='p4-abba', launch_manifest=plan_ref, source_regions=reference(region_file),
                prompt_manifest=dict(reference(prompt_file), value=prompt_file['value']), scopes=scopes, requests=requests)


def fmt(value):
    return 'unavailable' if value is None else f'{value:.3f}'


def paired_comparisons(comparisons):
    for key, value in comparisons.items():
        if isinstance(value, dict) and 'estimate' in value:
            bounds = value.get('conditional_ci95')
            yield key.replace('_', ' '), fmt(value['estimate']), 'unavailable' if bounds is None else ' to '.join(map(fmt, bounds))
        elif isinstance(value, dict):
            for suffix, estimate, interval in paired_comparisons(value):
                yield f'{key.replace("_", " ")} {suffix}', estimate, interval
        elif isinstance(value, (int, float)):
            yield key.replace('_', ' '), fmt(value), 'unavailable'


def render(analysis, evidence, capsule):
    by_arm = {scope['arm'] for scope in evidence['scopes']}
    actual = {(cell['arm'], cell['prompt_tokens']): cell for cell in analysis['measurements']}
    demand(set(actual) == {(arm, size) for arm in by_arm for size in SIZES} and
           all(cell['n'] == 10 for cell in actual.values()) and analysis['mode'] == 'p4-abba',
           'The native release did not produce ten eligible requests per size and arm')
    summary = (f'P4 measured {len(by_arm)} arms in two mirrored launches with ten timed requests per arm at each prompt size. '
               'First-token latency and decode throughput are reported separately.')
    lines = ['# Spark P4 matched benchmark', '', summary, '',
             'All admitted scopes passed the strict quiet preflight and every retained request boundary. '
             'The boundary process checks cannot observe activity that begins and ends between snapshots.', '',
             'Intervals resample matched request repeats within the two fixed launch windows. '
             'They describe those launches and exclude between-launch variation.', '']
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
            lines += ['', '| Arm | Comparison | Estimate | Conditional 95% interval |', '| --- | --- | ---: | ---: |']
            lines.extend(f'| {arm} | {name} | {estimate} | {bounds} |' for arm, name, estimate, bounds in comparisons)
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


def publish(base, path, manifest_sha):
    manifest_raw, plan = frozen_plan(path, manifest_sha, base)
    iteration = plan['iteration_id']
    first = base / Path(plan['launches'][0]['scope'])
    first_start = json.loads(safe_bytes(first / 'start.json'))['start']
    demand(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) <= timepoint(first_start),
           'Frozen P4 manifest file postdates the first launch')
    home = base / 'factory-runs/spark-direct-benchmarks'
    out = base / 'OPS/iterations' / iteration
    observation = iteration + ':report'
    with Store(home) as store:
        store.get_task(TASK)
        try:
            existing = store.read(TASK, observation)['values']
        except NotFound:
            existing = None
        if existing:
            report = existing['report']
            demand(existing['plan']['manifest']['sha256'] == manifest_sha and
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
                ref = put(f'{iteration}/raw/{label}@{digest(raw)}', raw, media)
                retained.append(ref['artifact_id'])
                return dict(ref, value=json.loads(raw)) if media == 'application/json' else dict(ref, raw=raw)

            plan_ref = put(iteration + '/admitted-launches.json', manifest_raw)
            evidence = evidence_from_lab(base, plan, plan_ref, capture)
            payload = json_bytes(evidence)
            evidence_ref = put(iteration + '/analysis-input.json', payload)
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
            analysis_ref = put(iteration + '/analysis.json', analysis_bytes)
            outputs = [analysis_ref, put(iteration + '/analyze-receipt.json', json_bytes(analyzed)),
                       put(iteration + '/verify-receipt.json', json_bytes(checked)),
                       put(iteration + '/release-manifest.json', (host.store / 'releases' / release / 'manifest.json').read_bytes())]
            report = dict(put(iteration + '/report.md', report_bytes, 'text/markdown'), summary=summary, status='verified-p4')
            input_ids = list(dict.fromkeys([plan_ref['artifact_id'], evidence_ref['artifact_id'], *retained]))
            output_ids = [ref['artifact_id'] for ref in outputs]
            envelope = dict(schema='spark-factory-iteration/1', iteration_id=iteration, predecessor_report_ids=[],
                plan=dict(decision_id=None, incoming_report_ids=[], builder_ccs=[], manifest=plan_ref,
                          summary='Run the frozen admitted arms in two quiet mirrored passes on the fixed Spark prompts.'),
                do=dict(source_commit=None, diff_artifact_id=None, verification_receipt_ids=[], build_receipt_ids=[]),
                lab=dict(status='complete', result_artifact_ids=input_ids),
                analysis=dict(ccs=[capsule], output_artifact_ids=output_ids, result_artifact=analysis_ref),
                report=report, next_plan=dict(decision_id=None))
            append_once(store, TASK, dict(obs_id=observation, kind='factory_iteration_report', values=envelope,
                source_artifacts=input_ids + output_ids + [report['artifact_id']]))

    out.mkdir(parents=True, exist_ok=True)
    for name, raw in (('report.md', report_bytes), ('analysis.json', analysis_bytes), ('iteration.json', json_bytes(envelope))):
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
    parser.add_argument('--export', type=Path, help='Native export destination, defaulting to the iteration export directory')
    args = parser.parse_args()
    base = args.base.resolve(strict=True)
    report = publish(base, args.manifest.absolute(), args.manifest_sha256)
    iteration = report['observation_id'].removesuffix(':report')
    out = args.export or base / 'OPS/iterations' / iteration / 'export'
    bundle = out.resolve() if out.exists() else export_task(TASK, out, Path(report['home']))
    files = verify(bundle)
    exported = json.loads((bundle / 'artifacts.json').read_bytes())
    demand(any(row['artifact_id'] == report['artifact_id'] and row['sha256'] == report['sha256'] and row['exported_path']
               for row in exported), 'Native export does not contain this exact P4 report')
    report.update(export=str(bundle), verified_manifest_files=files)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
