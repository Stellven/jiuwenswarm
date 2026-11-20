#!/usr/bin/env python3
"""Publish the separately qualified 60 GiB matched run with final-control build overlap."""
import argparse
import json
from pathlib import Path
from statistics import median

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.ccs.spark_gap_analysis.p4_build_overlap import (
    AUTHORIZED_UNITS, PREFLIGHT_UNIT, service_intervals, service_record, stamp, validate_process,
)
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest, safe_bytes
from report_p1 import CAPSULE, TASK, json_bytes
from report_p4 import (
    REPO, SIZES, apply_scope_amendment, effect_rows, evidence_from_lab,
    frozen_plan, reference, render, strict_quiet,
)


ITERATION = 'spark-p4-cache60-build-overlap'
FINAL_SCOPE = 'OPS/runs/p4-cache60-aplus-pass-2-01'
SERVICE_PATHS = ('OPS/p3/owner-d-cpu-service.txt', 'OPS/p3/owner-c2-cpu-service.txt')
HOME = 'factory-runs/spark-direct-benchmarks'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load_services(base, capture):
    services = []
    for unit, relative in zip(AUTHORIZED_UNITS, SERVICE_PATHS):
        artifact = capture(base / relative, 'text/plain')
        raw = artifact['raw'].decode()
        services.append(dict(reference(artifact), unit=unit, raw=raw, value=service_record(raw)))
    return services


def load_journals(base, capture):
    journals = []
    for unit in (*AUTHORIZED_UNITS, PREFLIGHT_UNIT):
        path = base / 'OPS/iterations' / ITERATION / 'build-activity' / f'{unit}.log'
        artifact = capture(path, 'text/plain')
        journals.append(dict(reference(artifact), unit=unit, raw=artifact['raw'].decode()))
    return journals


def boundary_admission(row, services):
    starts = {s['unit']: stamp(s['value']['start']) for s in services}

    def admit(data):
        lane = data.get('authorized_cpu_lane', [])
        if not lane:
            strict_quiet(data)
            return
        require(row['scope'] == FINAL_SCOPE and data['screening_scope'] == Path(FINAL_SCOPE).name and
                data['screening_admitted'] is True and data['quiet'] is False, 'Unexpected screening request boundary')
        for proc in lane:
            validate_process(proc, starts, stamp(data['observed_utc']))
        strict_quiet(dict(data, authorized_cpu_lane=[], screening_admitted=False))

    return admit


def load(base, args):
    raw, plan = frozen_plan(args.manifest, args.manifest_sha256, base)
    require(plan['iteration_id'] == 'spark-p4-cache60-attribution' and plan['bank_budget_mib'] == 61440 and
            plan['launches'][-1]['scope'] == FINAL_SCOPE,
            'Build-overlap admission only applies to the original 60 GiB lab')
    start = json.loads(safe_bytes(base / plan['launches'][0]['scope'] / 'start.json'))
    require(args.manifest.stat().st_mtime <= stamp(start['start']).timestamp(), 'Frozen manifest postdates the launch')
    return raw, plan


def read_only(path, media='application/json'):
    raw = safe_bytes(path)
    ref = dict(artifact_id=str(path), sha256=digest(raw))
    return dict(ref, value=json.loads(raw)) if media == 'application/json' else dict(ref, raw=raw)


def provisional(base, args, out):
    _, plan = load(base, args)
    amendment = apply_scope_amendment(base, plan, args.manifest_sha256, args.amendment, args.amendment_sha256, read_only)
    services = load_services(base, read_only)
    journals = load_journals(base, read_only)
    cutoff = min(stamp(entry['start']) for journal in journals for entry in service_intervals(journal['unit'], journal['raw']))
    measurements, scopes = {}, []
    for launch in plan['launches']:
        scope = base / launch['scope']
        stopped = read_only(scope / 'result.json')
        terminal = stopped['value']
        require(terminal['returncode'] == 0 and terminal['reason'] is None and terminal['scope_verified'] is True,
                'A prospective measured scope did not close cleanly')
        window = read_only(scope / 'p4-window/window.json')
        requests = window['value']['requests']
        require(window['value']['status'] == 'complete' and len(requests) == 16, 'Scope lacks its full request sequence')
        retained = []
        for item in requests:
            result = read_only(scope / 'p4-window' / item['result'])
            after = read_only(scope / 'p4-window' / item['after_resources'])
            row = result['value']
            require(result['sha256'] == item['sha256'] and row['ok'] is True and row['arm'] == launch['arm'] and
                    row['repeat'] == item['repeat'] and row['prompt_tokens'] == item['prompt_tokens'],
                    'Request differs from its completed window')
            exposed = stamp(after['value']['observed_utc']) >= cutoff
            if not row['discard']:
                key = (row['arm'], row['prompt_tokens'], row['repeat'])
                require(key not in measurements, 'Duplicate measured request')
                measurements[key] = dict(ttft_s=row['ttft_s'], decode_tps=row['decode_tps'], build_overlap=exposed)
            retained.append(dict(result=reference(result), after=reference(after), repeat=row['repeat'],
                                 prompt_tokens=row['prompt_tokens'], discard=row['discard'], build_overlap=exposed))
        scopes.append(dict(launch, stop=reference(stopped), window=reference(window), requests=retained))
    effects = []
    for size in SIZES:
        pairs = []
        for repeat in range(1, 11):
            a, c = (measurements[arm, size, repeat] for arm in ('A+', 'C3'))
            pairs.append(dict(repeat=repeat, build_overlap=a['build_overlap'] or c['build_overlap'],
                              seconds_saved=a['ttft_s']-c['ttft_s'], decode_gained=c['decode_tps']-a['decode_tps']))
        quiet = [r for r in pairs if not r['build_overlap']]
        effects.append(dict(prompt_tokens=size, pairs=pairs, quiet_prefix_n=len(quiet),
                            ten_pair_seconds_saved=median(r['seconds_saved'] for r in pairs),
                            ten_pair_decode_gained=median(r['decode_gained'] for r in pairs),
                            quiet_seconds_saved=median(r['seconds_saved'] for r in quiet),
                            quiet_decode_gained=median(r['decode_gained'] for r in quiet)))
    result = dict(schema='spark-p4-build-overlap-provisional/1', status='raw-provisional',
                  base_manifest_sha256=args.manifest_sha256, amendment=amendment,
                  services=services, journals=journals, scopes=scopes, effects=effects)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'provisional.json').write_bytes(json_bytes(result))
    return dict(path=str(out / 'provisional.json'), effects=[{k: v for k, v in row.items() if k != 'pairs'} for row in effects])


def build_note(analysis):
    overlap = analysis['build_overlap']
    lines = ['## Build exposure and quiet-only pairs', '']
    for row in overlap['services']:
        lines.append(f"- `{row['unit']}` retained CPUs 12–19, nice 19 and idle I/O in its systemd properties.")
    lines += ['', '| Build service invocation | Start UTC | Stop UTC in this run | Attempt |', '|---|---|---|---|']
    for row in overlap['journals']:
        for entry in row['intervals']:
            lines.append(f"| {row['unit']} | {entry['start']} | {entry['stop'] or 'Still active at GPU close'} | {entry['attempt'] or 'Preflight only'} |")
    lines += ['', f"The quiet-only subset ends at the first authorized preflight or build activity at {overlap['first_activity_utc']}. "
              'A request whose after-boundary crosses that cutoff stays in the screening set, including later gaps. '
              'The journal identifies active-service intervals. Boundary snapshots separately record visible compiler processes.', '',
              '| Final A+ prompt | Repeat | Before UTC | After UTC | Intersecting service intervals | Compiler observed at boundary |',
              '|---:|---:|---|---|---|---|']
    for row in overlap['exposed_requests']:
        active = ', '.join(row['possible_units']) or 'None'
        compilers = ', '.join(row['compiler_units_seen']) or 'None observed'
        lines.append(f"| {row['prompt_tokens']} | {row['repeat']} | {row['before_utc']} | {row['after_utc']} | {active} | {compilers} |")
    lines += ['', '| Prompt | Quiet-only repeat labels | Paired C3 TTFT saved s (range) | Paired C3 decode gained tok/s (range) |',
              '|---:|---|---:|---:|']
    for row in overlap['quiet_prefix']:
        cells = ['{median:+.3f} [{low:+.3f}, {high:+.3f}]'.format(median=row[key]['median'],
                 low=row[key]['range'][0], high=row[key]['range'][1]) for key in ('seconds_saved', 'decode_gained')]
        labels = ', '.join(map(str, row['labels']))
        lines.append(f"| {row['prompt_tokens']} | {labels} | {' | '.join(cells)} |")
    lines += ['', 'Quiet-only rows give observed ranges. The ten-pair conditional bootstrap includes the build-overlapped '
              'reverse control and describes these run windows.', '',
              'A separate agent reported a read-only text search lasting about 10 seconds within 13:48:23–13:51:25 UTC. '
              'That period is already in the screened portion. Its shared-I/O effect was not measured.', '']
    return '\n'.join(lines).encode()


def publish(base, args, out):
    manifest, plan = load(base, args)
    home = base / HOME
    observation = ITERATION + ':report'
    with Store(home) as store:
        try:
            envelope = store.read(TASK, observation)['values']
        except NotFound:
            envelope = None
        if envelope:
            report = envelope['report']
            return dict(observation_id=observation, **report)
        retained, raw_boundaries = [], {}

        def put(name, raw, media='application/json'):
            return reference(store.put_artifact(TASK, ITERATION + '/' + name, raw, media, None))

        def capture(path, media='application/json'):
            raw = safe_bytes(path)
            label = path.relative_to(base if path.is_relative_to(base) else REPO).as_posix()
            ref = put(f'raw/{label}@{digest(raw)}', raw, media)
            retained.append(ref['artifact_id'])
            if media == 'application/json':
                data = json.loads(raw)
                if path.name.endswith('-resources.json'):
                    raw_boundaries[ref['artifact_id']] = data
                return dict(ref, value=data)
            return dict(ref, raw=raw)

        manifest_ref = put('admitted-launches.json', manifest)
        amendment = apply_scope_amendment(base, plan, args.manifest_sha256, args.amendment, args.amendment_sha256, capture)
        services = load_services(base, capture)
        journals = load_journals(base, capture)
        evidence = evidence_from_lab(base, plan, manifest_ref, capture, lambda row: boundary_admission(row, services))
        evidence.update(mode='p4-build-overlap', scope_amendment=amendment, effective_launches=plan['launches'],
                        build_services=services, build_journals=journals)
        for row in evidence['requests']:
            boundaries = {key: raw_boundaries[row['evidence'][key]['artifact_id']] for key in ('before', 'after')}
            row['build_boundary'] = {key: dict(utc=value['observed_utc'], processes=value.get('authorized_cpu_lane', []))
                                     for key, value in boundaries.items()}
        evidence_ref = put('analysis-input.json', json_bytes(evidence))
        host = Host(home / 'analysis-ccv2')
        release = host.seal(REPO / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        capsule = dict(id=CAPSULE, version=host.describe(release)['version'], release=release)
        key = f'{ITERATION}:{release}:{evidence_ref["sha256"]}'
        analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key + ':analyze', grants=['process.exec'])
        analysis = analyzed.get('outputs', {}).get('analysis')
        require(analysis is not None, f'Native screening analysis refused the evidence: {analyzed}')
        checked = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis},
                            key=key + ':verify', grants=['process.exec'])
        require(checked.get('outputs', {}).get('verification', {}).get('done') is True,
                'Native verifier did not reproduce the screening')
        summary, report_bytes = render(analysis, evidence, capsule)
        report_bytes += b'\n' + build_note(analysis)
        report = dict(put('report.md', report_bytes, 'text/markdown'), summary=summary, status='build-overlap-screening')
        analysis_ref = put('analysis.json', json_bytes(analysis))
        verification = put('verify-receipt.json', json_bytes(checked))
        outputs = [analysis_ref, put('analyze-receipt.json', json_bytes(analyzed)), verification,
                   put('release-manifest.json', (host.store / 'releases' / release / 'manifest.json').read_bytes())]
        ids = list(dict.fromkeys([manifest_ref['artifact_id'], evidence_ref['artifact_id'], *retained]))
        output_ids = [ref['artifact_id'] for ref in outputs]
        target = evidence['comparison_target']
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=ITERATION, predecessor_report_ids=[],
                        plan=dict(decision_id=None, incoming_report_ids=[], builder_ccs=[], manifest=manifest_ref,
                                  scope_amendment=amendment,
                                  summary='Measure the frozen same-budget comparison and record the final control’s authorized build exposure.'),
                        do=dict(source_commit=None, diff_artifact_id=None, verification_receipt_ids=[], build_receipt_ids=[]),
                        lab=dict(status='complete-screening', result_artifact_ids=ids),
                        analysis=dict(ccs=[capsule], output_artifact_ids=output_ids, result_artifact=analysis_ref,
                                      screening_comparison=effect_rows(analysis, evidence, verification), comparison_target=target),
                        report=report, next_plan=dict(decision_id=None))
        append_once(store, TASK, dict(obs_id=observation, kind='factory_iteration_report', values=envelope,
                                      source_artifacts=ids + output_ids + [report['artifact_id']]))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'report.md').write_bytes(report_bytes)
    (out / 'analysis.json').write_bytes(json_bytes(analysis))
    (out / 'iteration.json').write_bytes(json_bytes(envelope))
    return dict(observation_id=observation, **report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--amendment', type=Path, required=True)
    parser.add_argument('--amendment-sha256', required=True)
    parser.add_argument('--provisional', action='store_true')
    args = parser.parse_args()
    args.manifest = args.manifest.resolve(strict=True)
    args.amendment = args.amendment.resolve(strict=True)
    directory = args.base / 'OPS/iterations' / ITERATION
    execute = provisional if args.provisional else publish
    print(json.dumps(execute(args.base, args, directory), indent=2))
