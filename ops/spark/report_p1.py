#!/usr/bin/env python3
"""Publish the completed P1 historical lab and its post-lab analysis to Factory."""
import argparse
import hashlib
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.deep_profile import stream_counters
from jiuwenswarm.factory.export import export_task, verify
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, safe_bytes

TASK = 'spark-direct-benchmarks-20261120'
ITERATION = 'spark-p1-reference-reconnaissance'
CAPSULE = 'factory.spark_gap_analysis'
ARMS = {'A': 'a-first-load-retry', 'S': 's-first-load'}


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def evidence_from_lab(base, repo, retain):
    def source(path, label=None):
        label = label or path.relative_to(base).as_posix()
        data = safe_bytes(path)
        digest = hashlib.sha256(data).hexdigest()
        return retain(f'source:{label}@sha256:{digest}', data, 'application/json'), json.loads(data)

    manifest_ref, manifest = source(repo / 'ops/spark/prompts/MANIFEST.json', 'prompts/MANIFEST.json')
    scopes, requests = [], []
    for arm, run in ARMS.items():
        directory = base / 'OPS/runs' / run
        scope, result = source(directory / 'result.json')
        load, load_ready = source(directory / 'load-ready.json')
        load['seconds'] = load_ready.get('load_time_s_from_engine_log', load_ready.get('engine_reported_load_time_s'))
        scopes.append(dict(scope, value=result, load=load, arm=arm))
        for name in ['cold-discard'] + [f'warm-{n}-{i}' for n in (512, 2048) for i in range(1, 6)]:
            ref, response = source(directory / name / 'result.json')
            req_ref, request = source(directory / name / 'request.json')
            requests.append(dict(ref, request=request, request_ref=req_ref, result=response, scope_id=scope['artifact_id']))
    return dict(mode='p1-reconnaissance', prompt_manifest=dict(manifest_ref, value=manifest), scopes=scopes, requests=requests)


def make_report(analysis, analysis_ref, streams, stream_ref, engine_log, capsule, excluded_load):
    lines = [
        '# P1 reference-arm reconnaissance', '',
        'This historical iteration ran the stock llama.cpp arm A and the Strata fair-profile arm S under the same Spark cap. '
        'The direct operator ran the lab before the analysis capsule was available. No builder capsule, candidate diff or A+ timing enters this analysis.', '',
        '## Lab measurements', '',
        '| Arm | Prompt tokens | Warm requests | Client TTFT median and range | Engine prefill median | Decode median |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for cell in analysis['measurements']:
        lower, upper = cell['range_s']
        lines.append(f"| {cell['arm']} | {cell['prompt_tokens']} | {cell['n']} | {cell['ttft_s']:.3f} s ({lower:.3f}–{upper:.3f} s) "
                     f"| {cell['engine_prefill_ms'] / 1000:.3f} s | {cell['decode_tps']:.2f} tok/s |")
    s_rows = [row for row in analysis['measurements'] if row['arm'] == 'S']
    lines.extend(['',
        f"The descriptive A−S median TTFT gap was {s_rows[0]['comparisons']['stock_minus_strata_s']:.3f} s at 512 tokens and "
        f"{s_rows[1]['comparisons']['stock_minus_strata_s']:.3f} s at 2048 tokens. The corresponding inverse-TTFT ratios for S vs A were "
        f"{s_rows[0]['comparisons']['inverse_ttft_vs_A']['estimate']:.2f}× and {s_rows[1]['comparisons']['inverse_ttft_vs_A']['estimate']:.2f}×.", '',
        'Greedy output hashes were stable within each arm and size. A and S produced different output hashes. '
        'Each request produced 32 tokens with no prompt-cache hits. The first request from each arm is excluded. '
        'The preliminary A request used 510 actual tokens and is retained as an exclusion.', '',
        'The measurements came from contiguous P1 batches with concurrent activity. A showed substantial warm-up drift. '
        'There is no quiet ABBA inference, confidence interval or candidate attribution from these observations.', '',
        '| Arm | Reported load time | Sampled cgroup peak | Minimum host MemAvailable |',
        '|---|---:|---:|---:|',
    ])
    for scope in analysis['scopes']:
        lines.append(f"| {scope['arm']} | {scope['load_s']:.2f} s | {scope['peak_memory_bytes'] / 2**30:.2f} GiB "
                     f"| {scope['min_mem_available_bytes'] / 2**30:.2f} GiB |")
    lines.extend(['',
        'The first stock load stopped on reclaim-only cap events. The retry was not OS-cold. Both measured scopes exited normally. '
        'CUDA UMA can escape cgroup accounting and the sampled peak can omit final teardown.', '',
        '## Strata stream counters', '',
        '| Prompt tokens | Native rows | Experts streamed | Layer-cache reuses | Chunks | Compute read wait range | Aggregate I/O worker busy range |',
        '|---|---:|---:|---:|---:|---:|---:|'])
    for size in (512, 2048):
        rows = [r for r in streams['records'] if r['tokens'] == size]
        row = rows[0]
        wait, busy = ([r[key] / 1000 for r in rows] for key in ('compute_read_wait_ms', 'io_worker_busy_ms'))
        lines.append(f"| {size} | {len(rows)} | {row['experts_streamed']} | {row['layer_cache_experts']} "
                     f"| {row['layer_cache_chunks']} | {min(wait):.3f}–{max(wait):.3f} s | {min(busy):.3f}–{max(busy):.3f} s |")
    lines.extend(['',
        'These are ordinary CUDA0 stream log rows, including the 512-token warmup. '
        'I/O worker busy time is aggregate concurrent work and can exceed elapsed prompt time. '
        'The counters do not partition wall time or show corresponding stock phases. '
        'The larger prompt shows repeat reuse in Strata. This is a mechanism to test on llama.cpp, with a matched gate control and attributed counters.', '',
        '## Inputs for the next planner', '',
        '1. Keep P1 as reconnaissance. Re-establish A and S under quiet mirrored launch order using the identical prompt files. '
        'Use the retained read-only Strata pre-run profile to control profile drift.',
        '2. Finish A+ native calibration separately. Include A+ in the same mirrored profile if it is accepted.',
        '3. Establish recorder parity and activity before instrumenting quiet measurements. Check candidate-specific activation against the unchanged stock profile. '
        'For residency, test reductions in requested and copied expert bytes and wait-at-demand alongside TTFT. '
        'Profile traces can explain an effect after a matched uninstrumented comparison.', '',
        '## Evidence', '',
        f"- Analysis capsule `{CAPSULE}` version {capsule['version']}, sealed release `{capsule['release']}`.",
        f"- Timing analysis `{analysis_ref['artifact_id']}` SHA256 `{analysis_ref['sha256']}`. It lists every contributing and excluded request and the corresponding server scope and prompt manifest.",
        f"- Strata counters `{stream_ref['artifact_id']}` SHA256 `{stream_ref['sha256']}`, from `{engine_log['artifact_id']}` SHA256 `{engine_log['sha256']}`.",
        f"- Initial stock load exclusion `{excluded_load['artifact_id']}` SHA256 `{excluded_load['sha256']}`.", '',
    ])
    return '\n'.join(lines).encode()


def publish(base, repo, home):
    with Store(home) as store:
        store.get_task(TASK)
        try:
            existing = store.read(TASK, ITERATION + ':report')['values']['report']
        except NotFound:
            existing = None
        if existing:
            record = store.read_artifact(TASK, existing['artifact_id'])
            if record['sha256'] != existing['sha256']:
                raise RuntimeError('Stored report no longer matches its iteration record')
            return dict(home=str(home), task_id=TASK, artifact_id=record['artifact_id'], sha256=record['sha256'])

        def retain(artifact_id, data, media_type='application/json'):
            artifact = store.put_artifact(TASK, artifact_id, data, media_type, None)
            return {key: artifact[key] for key in ('artifact_id', 'sha256')}

        evidence = evidence_from_lab(base, repo, retain)
        evidence_bytes = json_bytes(evidence)
        evidence_ref = retain(ITERATION + '/inputs.json', evidence_bytes)
        capsule_dir = repo / 'jiuwenswarm/factory/ccs/spark_gap_analysis'
        host = Host(home / 'analysis-ccv2')
        release = host.seal(capsule_dir)
        capsule = dict(id=CAPSULE, version=host.describe(release)['version'], release=release)
        key = f'{ITERATION}:{release}:{evidence_ref["sha256"]}'
        analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key + ':analyze', grants=['process.exec'])
        analysis = analyzed.get('outputs', {}).get('analysis')
        if not analysis:
            raise RuntimeError(f'Analysis did not complete: {analyzed}')
        verified = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis},
                             key=key + ':verify', grants=['process.exec'])
        if verified.get('outputs', {}).get('verification', {}).get('done') is not True:
            raise RuntimeError(f'Analysis verification did not pass: {verified}')
        analysis_ref = retain(ITERATION + '/analysis.json', json_bytes(analysis))
        receipts = [retain(ITERATION + f'/{name}-receipt.json', json_bytes(receipt))
                    for name, receipt in [('analysis', analyzed), ('verification', verified)]]
        manifest = retain(ITERATION + '/analysis-release-manifest.json',
                          (host.store / 'releases' / release / 'manifest.json').read_bytes())
        engine_log = safe_bytes(base / 'OPS/runs/s-first-load/engine.log')
        engine_ref = retain(f'source:OPS/runs/s-first-load/engine.log@sha256:{hashlib.sha256(engine_log).hexdigest()}',
                            engine_log, 'text/plain')
        streams = stream_counters(engine_log.decode('utf-8', errors='replace'))
        stream_ref = retain(ITERATION + '/strata-stream-counters.json', json_bytes({'source': engine_ref, **streams}))
        excluded_load = safe_bytes(base / 'OPS/runs/a-first-load/result.json')
        excluded_ref = retain(f'source:OPS/runs/a-first-load/result.json@sha256:{hashlib.sha256(excluded_load).hexdigest()}', excluded_load)
        report = make_report(analysis, analysis_ref, streams, stream_ref, engine_ref, capsule, excluded_ref)
        report_ref = retain(ITERATION + '/report.md', report, 'text/markdown')
        inputs = [evidence_ref, evidence['prompt_manifest'], engine_ref, excluded_ref]
        for scope in evidence['scopes']:
            inputs.extend((scope, scope['load']))
        for row in evidence['requests']:
            inputs.extend((row, row['request_ref']))
        output_ids = [ref['artifact_id'] for ref in (analysis_ref, stream_ref, manifest, *receipts)]
        input_ids = list(dict.fromkeys(ref['artifact_id'] for ref in inputs))
        append_once(store, TASK, dict(obs_id=ITERATION + ':analysis', kind='gap_attribution',
            values=dict(capsule_id=CAPSULE, release=release, analysis=analysis,
                        message='P1 timing and gap analysis verified from historical operator lab records'),
            source_artifacts=input_ids + output_ids))
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=ITERATION, predecessor_report_ids=[],
            plan=dict(decision_id=None, incoming_report_ids=[], builder_ccs=[],
                      rationale='Prepare fixed-prompt A and S reference arms as supervised P1 reconnaissance.'),
            do=dict(source_commit=None, diff_artifact_id=None, verification_receipt_ids=[], build_receipt_ids=[]),
            lab=dict(result_artifact_ids=input_ids, status='historical-reconnaissance'),
            analysis=dict(ccs=[capsule], output_artifact_ids=output_ids),
            report=dict(report_ref, status='historical-reconnaissance'), next_plan=dict(decision_id=None))
        append_once(store, TASK, dict(obs_id=ITERATION + ':report', kind='factory_iteration_report',
                    values=envelope, source_artifacts=input_ids + output_ids + [report_ref['artifact_id']]))
        output = base / 'OPS/iterations' / ITERATION
        output.mkdir(parents=True, exist_ok=True)
        (output / 'report.md').write_bytes(report)
        (output / 'analysis.json').write_bytes(json_bytes(analysis))
        (output / 'iteration.json').write_bytes(json_bytes(envelope))
        return dict(home=str(home), task_id=TASK, **report_ref)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--export', type=Path, help='Optional new native export directory')
    args = parser.parse_args()
    base = args.base.resolve()
    repo = Path(__file__).resolve().parents[2]
    home = base / 'factory-runs/spark-direct-benchmarks'
    ref = publish(base, repo, home)
    if args.export:
        bundle = export_task(TASK, args.export.resolve(), home)
        ref.update(export=str(bundle), verified_manifest_files=verify(bundle))
    print(json.dumps(ref, indent=2))


if __name__ == '__main__':
    main()
