#!/usr/bin/env python3
"""Publish process I/O evidence from a completed native verified P4 comparison."""
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from statistics import median

from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest
from report_p1 import TASK, json_bytes

GIB = 1024**3
OOM_KEYS = ('oom', 'oom_kill', 'oom_group_kill')
SIZES = (512, 2048)
PHASES = ('to_first_token', 'after_first_token')
COUNTERS = ('read_bytes', 'major_faults')
SCHEMA = 'spark-p4-process-io/1'
SOURCE_HOME = 'factory-runs/star-expert_weight_cache-residency-01'
SOURCE_TASK = 'spark-cache-residency-do-01'


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


def effective_launches(store, publication, evidence, manifest, manifest_sha, amendment_sha):
    base = manifest['launches']
    ref = evidence.get('scope_amendment')
    if ref is None:
        require(amendment_sha is None and publication['plan'].get('scope_amendment') is None and
                evidence.get('effective_launches', base) == base, 'An altered launch order requires a pinned amendment')
        return base, None
    require(ref == publication['plan'].get('scope_amendment') and amendment_sha == ref['sha256'],
            'Amendment pointer differs from the supplied pin or published plan')
    record = json.loads(read_ref(store, ref))
    require(record['schema'] == 'spark-p4-scope-replacement/1' and record['manifest_sha256'] == manifest_sha,
            'Amendment does not bind the frozen launch manifest')
    source, target = (record[key] for key in ('replaced_scope', 'replacement_scope'))
    destinations = {row['scope'] for row in base}
    require(source in destinations and target not in destinations and
            Path(target).parent == Path('OPS/runs') and target != source,
            'Scope amendment does not make one fresh-path substitution')
    expected = [dict(row, scope=target) if row['scope'] == source else row for row in base]
    require(expected == evidence['effective_launches'], 'Published effective launch rows differ from the amendment')
    return expected, dict(ref=ref, **record)


def summarize(store, iteration, manifest_sha, base=None, amendment_sha=None):
    observation = store.read(TASK, iteration + ':report')
    publication = observation['values']
    report = publication['report']
    screened = report['status'] == 'build-overlap-screening'
    require(screened or report['status'] == 'verified-p4', 'Expected the final native verified P4 report')
    focus = publication['analysis']['screening_comparison' if screened else 'focused_comparison']
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
    launches, amendment = effective_launches(store, publication, evidence, manifest, manifest_sha, amendment_sha)
    require(analysis['mode'] == ('p4-build-overlap' if screened else 'p4-abba') and
            len(analysis['eligible']) == 40 and len(analysis['excluded']) == 24,
            'Native analysis did not admit all 40 measured requests and 24 warmups')
    eligible = {row['result']['artifact_id'] for row in analysis['eligible']}
    source_ids = [report['artifact_id'], analysis_ref['artifact_id'], verify_ref['artifact_id'],
                  input_id, manifest_ref['artifact_id']]
    if amendment:
        source_ids.append(amendment['ref']['artifact_id'])

    def retained(ref):
        source_ids.append(ref['artifact_id'])
        return read_ref(store, ref)

    windows, measurements = [], defaultdict(dict)
    for spec, scope in zip(launches, evidence['scopes']):
        outcome = json.loads(read_ref(store, scope))
        start = json.loads(retained(scope['start']))
        kernel = json.loads(read_ref(store, scope['scope']))
        prelaunch = json.loads(read_ref(store, scope['quiet_preflight']))
        caps = kernel['actual']
        require(outcome == scope['value'] and outcome['arm'] == spec['arm'] and
                outcome['result_path'] == start['result_path'] and outcome['start'] == start['start'] and
                ((base / spec['scope']) == Path(outcome['result_path']) if base else
                 Path(outcome['result_path']).parts[-3:] == Path(spec['scope']).parts) and
                outcome['returncode'] == 0 and outcome['reason'] is None and outcome['scope_verified'] is True and
                outcome['memory_max'] == 100 * GIB and outcome['min_mem_available_bytes'] >= 8 * GIB and
                not any(int(outcome['memory_events'].get(k, 0)) for k in OOM_KEYS) and
                caps.get('memory.max') == str(100 * GIB) and caps.get('memory.swap.max') == '0' and
                caps.get('sched_affinity') == list(range(8)) and prelaunch['quiet'] is True and
                not prelaunch.get('authorized_cpu_lane'),
                'Scope did not close cleanly under the quiet 100 GiB/no swap/eight CPU conditions')
        if amendment and spec['scope'] == amendment['replacement_scope']:
            require(datetime.fromisoformat(amendment['frozen_at']) <= datetime.fromisoformat(start['start']),
                    'Scope replacement was declared after the fresh scope started')
        arm, number = scope['arm'], scope['launch_pass']
        launch_profile = json.loads(retained(scope['profile']))
        require(scope['profile']['sha256'] == spec['profile_sha256'] and
                launch_profile['binary_sha256'] == outcome['binary_sha256'], 'Profile identity changed')
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
                            startup=startup, source_commit=scope.get('source_commit'),
                            binary_sha256=outcome['binary_sha256'], build_receipt=launch_profile['build_receipt']))
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
                  native_verification=verify_ref, native_analysis=analysis_ref, input=input_ref, scopes=windows, measured=effects)
    if amendment:
        result['scope_replacement'] = amendment
    if screened:
        result['build_overlap'] = analysis['build_overlap']
        for effect, quiet in zip(effects, result['build_overlap']['quiet_prefix']):
            require(effect['tokens'] == quiet['prompt_tokens'], 'Quiet-prefix prompt identity differs')
            pairs = [row for row in effect['requests'] if row['ordinal'] in quiet['labels']]
            require(len(pairs) == quiet['n'], 'Request I/O is missing a quiet-prefix pair')
            quiet['paired_process_io_avoided'] = {
                phase: {key: span([row['stock']['counters'][phase][key] - row['c3']['counters'][phase][key]
                                   for row in pairs]) for key in COUNTERS}
                for phase in PHASES}
    if focus['budget_mib'] == 61440 and base:
        from p4_seed_mechanism import collect
        result['mechanism'] = collect(base, evidence['scopes'], evidence['requests'],
                                      lambda ref: json.loads(retained(ref)), retained, span)
    return dict(result, source_artifacts=list(dict.fromkeys(source_ids)))


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
    if 'build_overlap' in data:
        lines[2] = 'The ten measured pairs include the final A+ control with authorized build exposure. The timing and I/O comparisons are screening.'
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
    if 'build_overlap' in data:
        lines += ['', '## Process I/O in the quiet-only paired subset', '',
                  '| Prompt | Pairs | Phase | Paired C3 reads avoided in GB [min, max] | Paired C3 major faults avoided [min, max] |',
                  '|---:|---:|---|---:|---:|']
        for row in data['build_overlap']['quiet_prefix']:
            for phase, counts in row['paired_process_io_avoided'].items():
                lines.append(f"| {row['prompt_tokens']} | {row['n']} | {phases[phase]} | "
                             f"{interval(counts['read_bytes'], 1e9)} | {interval(counts['major_faults'], digits=1)} |")
    if 'mechanism' in data:
        from p4_seed_mechanism import render as render_mechanism
        lines += ['', *render_mechanism(data['mechanism'])]
    if amendment := data.get('scope_replacement'):
        lines += ['', '## Prospective scope replacement', '',
                  f"The operator excluded `{amendment['replaced_scope']}` and named "
                  f"`{amendment['replacement_scope']}` before its fresh launch.",
                  f"{amendment['reason']} The paired results use the fresh verified scope.",
                  f"Amendment `{amendment['ref']['artifact_id']}` SHA256 `{amendment['ref']['sha256']}`.", '']
    if lineage := data.get('do_lineage'):
        lines += ['', '## Original native DO and build', '',
                  f"Factory source task `{SOURCE_TASK}` used original commit `{lineage['source_commit']}`, "
                  f"source verifier call `{lineage['verifier_call']}` and build attempt `{lineage['attempt']}`.",
                  'The revision links the exact source decision, diff, verifier receipt, ELF manifest, and build receipts.', '']
    lines += ['', f"Native report `{data['report']['artifact_id']}` SHA256 `{data['report']['sha256']}`.",
              f"Native verifier `{data['native_verification']['artifact_id']}` SHA256 `{data['native_verification']['sha256']}`.", '']
    return '\n'.join(lines).encode()


def copy_original_do(base, target, iteration, scopes):
    home = base / SOURCE_HOME
    if not (home / 'factory.sqlite').is_file():
        return None
    with Store(home) as native:
        report = native.read(SOURCE_TASK, 'spark-c3-native-cache:report-v3')['values']
        plan, do = report['plan'], report['do']
        captured = {}

        def mirror(identifier):
            artifact = native.read_artifact(SOURCE_TASK, identifier)
            raw = native.artifact_bytes(SOURCE_TASK, identifier)
            local = target.put_artifact(TASK, f'{iteration}/original-do/{identifier}', raw, artifact['media_type'], None)
            require(local['sha256'] == artifact['sha256'], 'Copied original source artifact changed')
            captured[identifier] = {key: local[key] for key in ('artifact_id', 'sha256')}
            return raw

        built = json.loads(mirror('revised-native-cache-elf-manifest.json'))
        source_manifest = json.loads(mirror('cache-native-profile-verified-native-request.json'))
        static = json.loads(mirror('cache-native-profile-static-receipt.json'))
        decision = json.loads(mirror(plan['decision_artifact_id']))
        mirror(do['diff_artifact_id'])
        for key in ('build_receipt', 'build_record'):
            ref = built[key]
            mirror(ref['artifact_id'])
            require(captured[ref['artifact_id']]['sha256'] == ref['sha256'], 'Original native build receipt changed')
        subject = [scope for scope in scopes if scope['arm'] == 'C3']
        require(len(subject) == 2 and all(o['binary_sha256'] == built['executable']['sha256'] and
                o['source_commit'] == built['source']['commit'] == source_manifest['observed_head'] == do['source_commit'] and
                o['build_receipt'] == built['build_receipt']['artifact_id'] for o in subject),
                'Original native source or build was not the launched 60 GiB subject')
        require(static['outputs']['done'] is True and static['release'] == plan['builder_ccs'][0]['release'] and
                static['call'] == source_manifest['native_verifier_call'] and
                decision['decision_id'] == plan['decision_id']['decision_id'], 'Original native plan or static verifier changed')
        return dict(home=str(home), task_id=SOURCE_TASK, source_commit=do['source_commit'],
                    attempt=built['build_attempt_id'], verifier_call=static['call'], decision_id=decision['decision_id'],
                    decision_artifact_id=captured[plan['decision_artifact_id']]['artifact_id'],
                    builder_ccs=plan['builder_ccs'],
                    diff_artifact_id=captured[do['diff_artifact_id']]['artifact_id'],
                    verification_receipt_ids=[captured['cache-native-profile-static-receipt.json']['artifact_id']],
                    build_receipt_ids=[captured[ref]['artifact_id'] for ref in do['build_receipt_ids']],
                    artifacts=list(captured.values()))


def publish_sixty_revision(store, out, data, appendix, refs, extent):
    iteration = data['iteration']
    original = store.read(TASK, iteration + ':report')
    envelope = deepcopy(original['values'])
    old_report = envelope['report']
    raw = read_ref(store, old_report).rstrip() + b'\n\n' + appendix
    artifact = store.put_artifact(TASK, iteration + '/report-v2.md', raw, 'text/markdown', None)
    report = dict(artifact_id=artifact['artifact_id'], sha256=artifact['sha256'], status=old_report['status'],
                  summary=old_report['summary'], revision=2, supersedes_observation_id=iteration + ':report',
                  supersedes_artifact_id=old_report['artifact_id'])
    envelope['report'] = report
    envelope['analysis']['request_io_and_residency'] = dict(report=refs[0], structured=refs[1], extent_manifest=extent)
    extras = [report['artifact_id'], refs[0]['artifact_id'], refs[1]['artifact_id'], extent['artifact_id']]
    envelope['analysis']['output_artifact_ids'] += extras[1:]
    if lineage := data.get('do_lineage'):
        keys = ('home', 'task_id', 'source_commit', 'diff_artifact_id', 'verification_receipt_ids', 'build_receipt_ids')
        envelope['do'].update({key: lineage[key] for key in keys})
        envelope['plan']['source_decision'] = {key: lineage[key] for key in ('home', 'task_id', 'decision_id', 'decision_artifact_id')}
        envelope['plan']['builder_ccs'] = lineage['builder_ccs']
        extras.extend(ref['artifact_id'] for ref in lineage['artifacts'])
    observation = iteration + ':report-v2'
    append_once(store, TASK, dict(obs_id=observation, kind='factory_iteration_report_revision', values=envelope,
        source_artifacts=list(dict.fromkeys(original['source_artifacts'] + data['source_artifacts'] + extras))))
    (out / 'report-v2.md').write_bytes(raw)
    (out / 'iteration-v2.json').write_bytes(json_bytes(envelope))
    return dict(observation_id=observation, **report)


def run(base, iteration, sha, publish, amendment_sha=None):
    with Store(base / 'factory-runs/spark-direct-benchmarks') as store:
        data = summarize(store, iteration, sha, base, amendment_sha)
        if not publish:
            return dict(iteration=iteration, scopes=len(data['scopes']),
                        pairs={row['tokens']: row['n_pairs'] for row in data['measured']})
        prefix = iteration + '/process-io'
        extent = None
        if data['budget_mib'] == 61440:
            info = data['mechanism']['extents']
            raw = Path(info['path']).read_bytes()
            require(digest(raw) == info['sha256'], 'Frozen extents changed before publication')
            artifact = store.put_artifact(TASK, iteration + '/expert-extents.json', raw, 'application/json', None)
            extent = {key: artifact[key] for key in ('artifact_id', 'sha256')}
            data['mechanism']['extents'] = extent
            data['source_artifacts'].append(extent['artifact_id'])
            try:
                lineage = copy_original_do(base, store, iteration, data['scopes'])
            except NotFound:
                lineage = None
            if lineage:
                data['do_lineage'] = lineage
                data['source_artifacts'].extend(item['artifact_id'] for item in lineage['artifacts'])
            else:
                data['mechanism']['warnings'].append('Original source DO or build evidence was unavailable in the native store.')
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
        result = dict(iteration=iteration, observation_id=observation, artifacts=refs)
        if extent:
            result['revision'] = publish_sixty_revision(store, out, data, report_bytes, refs, extent)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=Path.home()/'predemo-spark', type=Path)
    parser.add_argument('iteration')
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--scope-amendment-sha256')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.base.resolve(), args.iteration, args.manifest_sha256, args.publish,
                         args.scope_amendment_sha256), indent=2))
