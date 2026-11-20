#!/usr/bin/env python3
"""Publish process I/O evidence from a completed native verified P4 comparison."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median

from jiuwenswarm.factory.store import Store

from import_evidence import append_once, digest
from report_p1 import TASK, json_bytes

GIB = 1024**3
OOM_KEYS = ('oom', 'oom_kill', 'oom_group_kill')
SIZES = (512, 2048)
PHASES = ('to_first_token', 'after_first_token')
COUNTERS = ('read_bytes', 'major_faults')
SCHEMA = 'spark-p4-process-io/1'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def span(values):
    return dict(median=median(values), min=min(values), max=max(values))


def read_ref(store, ref):
    raw = store.artifact_bytes(TASK, ref['artifact_id'])
    require(digest(raw) == ref['sha256'], f"Bound artifact hash differs for {ref['artifact_id']}")
    return raw


def process_deltas(snapshots, pid):
    rows = [snapshots[key] for key in ('start', 'first_token', 'end')]
    clocks = [row['monotonic_ns'] for row in rows]
    require(clocks[0] <= clocks[1] <= clocks[2], 'Process snapshot clocks disagree')
    processes = [row['processes'][str(pid)] for row in rows]
    require(all(row['comm'] == 'llama-server' for row in processes) and
            len({row['starttime_ticks'] for row in processes}) == 1,
            'The same llama-server PID and birth time are required at all phase boundaries')
    native = {'read_bytes': [row['io']['read_bytes'] for row in processes],
              'major_faults': [row['majflt'] for row in processes]}
    require(all(all(type(value) is int for value in counters) and 0 <= counters[0] <= counters[1] <= counters[2]
                for counters in native.values()), 'Process I/O counters must be nonnegative monotone integers')
    return {phase: {field: values[pos+1] - values[pos] for field, values in native.items()}
            for pos, phase in enumerate(PHASES)}


def summarize(store, iteration, manifest_sha):
    observation = store.read(TASK, iteration + ':report')
    publication = observation['values']
    report = publication['report']
    require(report['status'] == 'verified-p4', 'Expected the final native verified P4 report')
    focus = publication['analysis']['focused_comparison']
    require(focus['schema'] == 'spark-p4-focused/1' and focus['subject_arm'] == 'C3', 'Expected original C3 and A+')
    manifest_ref = publication['plan']['manifest']
    require(manifest_ref['sha256'] == manifest_sha, 'Unexpected frozen manifest')
    manifest = json.loads(read_ref(store, manifest_ref))
    read_ref(store, report)
    analysis_ref = publication['analysis']['result_artifact']
    analysis = json.loads(read_ref(store, analysis_ref))
    verify_ref = focus['verification']
    verified = json.loads(read_ref(store, verify_ref))
    require(verified['capability'] == 'verify' and verified['outputs']['verification']['done'] is True,
            'Native deterministic verifier did not pass')
    input_id = iteration + '/analysis-input.json'
    input_raw = store.artifact_bytes(TASK, input_id)
    input_ref = dict(artifact_id=input_id, sha256=digest(input_raw))
    expected_key = f"{iteration}:{verified['release']}:{input_ref['sha256']}:verify"
    require(verified['key'] == expected_key and input_id in observation['source_artifacts'],
            'Native verifier does not bind this exact analysis input')
    evidence = json.loads(input_raw)
    require(evidence['launch_manifest'] == manifest_ref and
            focus['budget_mib'] == manifest.get('bank_budget_mib', focus['budget_mib']) and
            [(s['arm'], s['launch_pass']) for s in evidence['scopes']] == [('A+', 1), ('C3', 1), ('C3', 2), ('A+', 2)],
            'Expected four admitted mirrored scopes at one common budget')
    require(analysis['mode'] == 'p4-abba' and len(analysis['eligible']) == 40 and len(analysis['excluded']) == 24,
            'Native analysis did not admit all 40 measured requests and 24 warmups')
    eligible = {row['result']['artifact_id'] for row in analysis['eligible']}
    source_ids = [report['artifact_id'], analysis_ref['artifact_id'], verify_ref['artifact_id'],
                  input_id, manifest_ref['artifact_id']]
    windows, measurements = [], defaultdict(dict)
    for spec, scope in zip(manifest['launches'], evidence['scopes']):
        outcome = json.loads(read_ref(store, scope))
        kernel = json.loads(read_ref(store, scope['scope']))
        prelaunch = json.loads(read_ref(store, scope['quiet_preflight']))
        caps = kernel['actual']
        require(outcome == scope['value'] and outcome['arm'] == spec['arm'] and
                outcome['returncode'] == 0 and outcome['reason'] is None and outcome['scope_verified'] is True and
                outcome['memory_max'] == 100 * GIB and outcome['min_mem_available_bytes'] >= 8 * GIB and
                not any(int(outcome['memory_events'].get(k, 0)) for k in OOM_KEYS) and
                caps.get('memory.max') == str(100 * GIB) and caps.get('memory.swap.max') == '0' and
                caps.get('sched_affinity') == list(range(8)) and prelaunch['quiet'] is True and
                not prelaunch.get('authorized_cpu_lane'),
                'Scope did not close cleanly under the quiet 100 GiB/no swap/eight CPU conditions')
        arm, number = scope['arm'], scope['launch_pass']
        source_ids.extend([scope['artifact_id'], scope['scope']['artifact_id'], scope['quiet_preflight']['artifact_id']])
        startup, measured = [], []
        for row in evidence['requests']:
            if row['scope_id'] != scope['artifact_id']:
                continue
            result = row['result']
            resource_ref = row['evidence']['resource_windows']
            resource = json.loads(read_ref(store, resource_ref))
            require(resource_ref['sha256'] == result['resource_windows_sha256'] and
                    resource['schema'] == 'spark-request-resources/1' and resource['cgroup'] == kernel['cgroup'] and
                    result['arm'] == arm, 'Request process evidence does not bind to its capped scope')
            source_ids.append(resource_ref['artifact_id'])
            size, repeat = result['prompt_tokens'], result['repeat']
            counts = process_deltas(resource['snapshots'], kernel['pid'])
            if 'first_token_io' in row:
                require(counts['to_first_token'] == row['first_token_io'], 'First-token I/O disagrees with the native input')
            entry = dict(tokens=size, repeat=repeat, ttft_s=result['ttft_s'], decode_tps=result['decode_tps'],
                         resource_windows=resource_ref, counters=counts)
            if result['discard']:
                require(row['artifact_id'] not in eligible and repeat == 0, 'Startup request was marked measured')
                startup.append(dict(position=len(startup)+1, **entry))
            else:
                require(row['artifact_id'] in eligible and type(repeat) is int and 1 <= repeat <= 10 and size in SIZES and
                        repeat not in measurements[(arm, size)], 'Timing pair is missing, duplicated or not eligible')
                measurements[(arm, size)][repeat] = entry
                measured.append(entry)
        require(len(startup) == 6 and len(measured) == 10, 'Scope does not have six warmups and ten measured requests')
        windows.append(dict(arm=arm, launch_pass=number, load_s=scope['load']['seconds'],
                            peak_memory_bytes=outcome['peak_memory_bytes'], min_mem_available_bytes=outcome['min_mem_available_bytes'],
                            memory_events=outcome['memory_events'], scope=spec['scope'], process_pid=kernel['pid'],
                            startup=startup))
    effects = []
    for size in SIZES:
        stock, c3 = (measurements[(arm, size)] for arm in ('A+', 'C3'))
        require(set(stock) == set(c3) == set(range(1, 11)), 'Expected ten exact ordinal pairs')
        counts = {}
        for phase in PHASES:
            counters = {}
            for key in COUNTERS:
                a = [stock[i]['counters'][phase][key] for i in range(1, 11)]
                b = [c3[i]['counters'][phase][key] for i in range(1, 11)]
                deltas = [x - y for x, y in zip(a, b)]
                counters[key] = dict(stock=span(a), c3=span(b), paired_avoided=span(deltas), paired_values=deltas)
            counts[phase] = counters
        timing = next(row for row in focus['rows'] if row['prompt_tokens'] == size)
        effects.append(dict(tokens=size, n_pairs=10, timing=timing, process_io=counts,
                            requests=[dict(ordinal=i, stock=stock[i], c3=c3[i]) for i in range(1, 11)]))
    result = dict(schema=SCHEMA, iteration=iteration, budget_mib=focus['budget_mib'], report=report, manifest=manifest_ref,
                  native_verification=verify_ref, native_analysis=analysis_ref, input=input_ref,
                  source_artifacts=list(dict.fromkeys(source_ids)), scopes=windows, measured=effects)
    return result


def interval(values, scale=1, digits=3):
    return f"{values['median']/scale:,.{digits}f} [{values['min']/scale:,.{digits}f}, {values['max']/scale:,.{digits}f}]"


def format_timing(timing, values, sign=1):
    result = timing[values]
    low, high = sorted(sign * point for point in result['conditional_ci95'])
    return f"{sign * result['estimate']:+.3f} [{low:+.3f}, {high:+.3f}]"


def render(data):
    lines = [f"# {data['budget_mib']//1024} GiB C3 versus A+ request I/O and scope review", '',
             'Paired timing uses the verified native report. The read and major-fault counts come from the same inference PID '
             'at all three request boundaries.', '',
             '| Prompt | Pairs | A+ / C3 TTFT (s) | Paired C3 TTFT added (s) | A+ / C3 decode (tok/s) | Paired C3 decode gain (tok/s) |',
             '|---:|---:|---:|---:|---:|---:|']
    for effect in data['measured']:
        row = effect['timing']
        a, c3 = row['control'], row['candidate']
        ttft = format_timing(row, 'paired_ttft_seconds_saved_vs_Aplus', -1)
        decode = format_timing(row, 'paired_decode_tps_gained_vs_Aplus')
        lines.append(f"| {effect['tokens']} | 10 | {a['ttft_s']:.3f} / {c3['ttft_s']:.3f} | {ttft} | "
                     f"{a['decode_tps']:.3f} / {c3['decode_tps']:.3f} | {decode} |")
    lines += ['', 'Timing brackets are conditional 95% intervals within the two mirrored launch windows.', '',
              '## Scope safety', '',
              '| Arm | Pass | Launch to ready (s) | Peak cap usage (GiB) | Minimum host available (GiB) | memory.events max | OOM events |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for row in data['scopes']:
        events = row['memory_events']
        lines.append(f"| {row['arm']} | {row['launch_pass']} | {row['load_s']:.3f} | {row['peak_memory_bytes']/GIB:.3f} | "
                     f"{row['min_mem_available_bytes']/GIB:.3f} | {int(events.get('max', 0)):,} | "
                     f"{sum(int(events.get(k, 0)) for k in OOM_KEYS)} |")
    lines += ['', 'All scopes exited normally under the 100 GiB cap with swap disabled and CPU affinity 0–7.', '',
              '## Ten measured pairs per prompt', '',
              '| Prompt | Phase | Counter | A+ median [min, max] | C3 median [min, max] | Paired A+ minus C3 median [min, max] |',
              '|---:|---|---|---:|---:|---:|']
    phases = {'to_first_token': 'Start to first token', 'after_first_token': 'First token to stream end'}
    for row in data['measured']:
        for phase, metrics in row['process_io'].items():
            for key, values in metrics.items():
                noun, unit, digits = ('Engine reads (GB)', 1e9, 3) if key == 'read_bytes' else ('Engine major faults', 1, 1)
                estimates = ' | '.join(interval(values[arm], unit, digits) for arm in ('stock', 'c3', 'paired_avoided'))
                lines.append(f"| {row['tokens']} | {phases[phase]} | {noun} | {estimates} |")
    lines += ['', 'Positive paired values mean fewer reads or faults in C3. Ranges here are observed pair ranges. '
              'Process read_bytes counts I/O charged to the engine by Linux. GPU copies and host-wide disk counters have separate accounting.', '',
              '## Startup after identical source conditioning', '',
              '| Arm | Pass | Position | Tokens | TTFT (s) | Decode (tok/s) | Reads before / after first token (GB) | Major faults before / after |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for scope in data['scopes']:
        for row in scope['startup']:
            before, after = (row['counters'][phase] for phase in PHASES)
            lines.append(f"| {scope['arm']} | {scope['launch_pass']} | {row['position']} | {row['tokens']} | {row['ttft_s']:.3f} | "
                         f"{row['decode_tps']:.3f} | {before['read_bytes']/1e9:.3f} / {after['read_bytes']/1e9:.3f} | "
                         f"{before['major_faults']:,} / {after['major_faults']:,} |")
    lines += ['', f"Native report `{data['report']['artifact_id']}` SHA256 `{data['report']['sha256']}`.",
              f"Native verifier `{data['native_verification']['artifact_id']}` SHA256 `{data['native_verification']['sha256']}`.", '']
    return '\n'.join(lines).encode()


def run(base, iteration, sha, publish):
    with Store(base / 'factory-runs/spark-direct-benchmarks') as store:
        data = summarize(store, iteration, sha)
        if not publish:
            return dict(iteration=iteration, scopes=len(data['scopes']),
                        pairs={row['tokens']: row['n_pairs'] for row in data['measured']})
        prefix = iteration + '/process-io'
        report_bytes = render(data)
        report = store.put_artifact(TASK, prefix + '.md', report_bytes, 'text/markdown', None)
        payload = json_bytes(data)
        structured = store.put_artifact(TASK, prefix + '.json', payload, 'application/json', None)
        refs = [{key: row[key] for key in ('artifact_id', 'sha256')} for row in (report, structured)]
        observation = iteration + ':process-io'
        append_once(store, TASK, dict(obs_id=observation, kind='p4_scope_io_analysis',
            values=dict(schema=SCHEMA, iteration_id=iteration, report=refs[0], structured=refs[1],
                        native_verification=data['native_verification'], comparison='same-budget-cc'),
            source_artifacts=[row['artifact_id'] for row in refs] + data['source_artifacts']))
        out = base / 'OPS/iterations' / iteration
        (out / 'process-io.md').write_bytes(report_bytes)
        (out / 'process-io.json').write_bytes(payload)
        return dict(iteration=iteration, observation_id=observation, artifacts=refs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=Path.home()/'predemo-spark', type=Path)
    parser.add_argument('iteration')
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.base.resolve(), args.iteration, args.manifest_sha256, args.publish), indent=2))
