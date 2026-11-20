#!/usr/bin/env python3
"""Verify a flags-matched stock follow-up on the existing C5 pooled iteration."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import Store

from import_evidence import append_once, digest, safe_bytes
from report_p1 import CAPSULE, TASK, json_bytes
from report_p4 import HERE, REPO, demand, read_launch, reference, timepoint
from report_pooled30 import BASE


def render(analysis):
    rows = analysis['rows']
    keys = ('stock_flags_vs_pooled', 'c5_vs_stock_flags')
    names = ('Flags-matched stock vs pooled A+30', 'C5 vs flags-matched stock')
    deltas = ' / '.join(f'{r[keys[1]]["ttft_seconds_saved"]["median"]:+.2f} s' for r in rows)
    parity = 'Greedy output matched at both sizes.' if all(r['greedy_parity'][keys[1]] for r in rows) else (
        'Greedy output or reasoning differed at ' + ' and '.join(str(r['prompt_tokens']) for r in rows
            if not r['greedy_parity'][keys[1]]) + ' tokens.')
    summary = f'Paired first-token time saved at 512 / 2048 tokens was {deltas} in the separate fixed-flags stock screen. {parity}'
    lines = ['# C5 and a separate flags-matched stock launch', '',
             summary, '',
             'The follow-up used one pristine A+30 stock launch with the C5 slot, context, checkpoint and batch arguments '
             'and the mapper gate unset. Both fixed-flags arms used the same actual bank allocation and request order. '
             'The original pooled package comparison remains below.', '',
             '| Compared arms | Prompt | Paired TTFT saved s [range] | Paired decode gained tok/s [range] | Greedy parity |',
             '| --- | ---: | ---: | ---: | --- |']
    for name, key in zip(names, keys):
        for row in rows:
            metrics = []
            for metric in ('ttft_seconds_saved', 'decode_tps_gained'):
                value = row[key][metric]
                a, b = value['observed_range']
                metrics.append(f'{value["median"]:+.3f} [{a:+.3f}, {b:+.3f}]')
            lines.append(f'| {name} | {row["prompt_tokens"]} | {" | ".join(metrics)} | {row["greedy_parity"][key]} |')
    lines += ['', 'Each row uses four measured request positions after two warmups per size. The original pooled controls '
              'contribute the same absolute request positions, including their third discarded request. Greedy parity '
              'checks both content and reasoning. The structured analysis retains all matched hashes and individual '
              'control comparisons.', '', *analysis['limitations'], '', '## Absolute measured results', '',
              '| Profile | Prompt | TTFT median [range] (s) | Decode median [range] (tok/s) |',
              '| --- | ---: | ---: | ---: |']
    for row in rows:
        for label, key in (('C5', 'candidate'), ('A+30 C5 flags', 'stock_flags'), ('Pooled A+30', 'pooled_reference')):
            cells = []
            for metric in ('ttft_s', 'decode_tps'):
                item = row[key][metric]
                lower, upper = item['observed_range']
                cells.append(f'{item["median"]:.3f} [{lower:.3f}, {upper:.3f}]')
            lines.append(f'| {label} | {row["prompt_tokens"]} | {" | ".join(cells)} |')
    lines += ['', '## Greedy content and reasoning SHA-256', '',
              'Each printed pair is content SHA-256 followed by reasoning SHA-256. The structured analysis retains '
              'the hashes for each individual measured request.', '']
    for row in rows:
        values = row['greedy_hashes']
        lines += [f'### {row["prompt_tokens"]} tokens', '']
        sources = {'C5': values['c5'], 'A+30 with C5 flags': values['stock_flags'], **values['pooled_controls']}
        for label, hashes in sources.items():
            pairs = sorted({(h['output_sha256'], h['reasoning_sha256']) for h in hashes})
            lines.extend(f'- {label} `{a}` / `{b}`' for a, b in pairs)
        lines.append('')
    lines += [f"Observed competing CPU boundaries, C5 {analysis['cpu_overlap_observed']['c5']}, "
              f"flags-matched stock {analysis['cpu_overlap_observed']['stock_flags']}.", '', '## Original pooled package screen', '']
    return summary, '\n'.join(lines).encode()


def publish(path, sha):
    raw = safe_bytes(path)
    plan = json.loads(raw)
    iteration = plan['iteration_id']
    demand(digest(raw) == sha and plan['schema'] == 'spark-c5-matched-stock-admission/1' and
           iteration == 'spark-pooled30-c5-01' and plan['subject_arm'] == 'C5', 'Wrong frozen matched-stock manifest')
    launch, = plan['launches']
    scope = Path(launch['scope'])
    demand(scope == BASE / 'OPS/runs/pooled30-c5-matched-stock-01' and launch['arm'] == 'A+',
           'Matched stock manifest must identify the one authorized stock scope')
    demand(path.stat().st_mtime <= timepoint(json.loads(safe_bytes(scope/'start.json'))['start']).timestamp(),
           'Matched stock manifest postdates its launch')
    home = BASE / 'factory-runs/spark-direct-benchmarks'
    with Store(home) as store:
        retained = []

        def put(name, payload, media='application/json'):
            ref = reference(store.put_artifact(TASK, f'{iteration}/{name}', payload, media, None))
            retained.append(ref['artifact_id'])
            return ref

        def capture(filename, media='application/json'):
            data = safe_bytes(filename)
            loc = filename.relative_to(BASE if filename.is_relative_to(BASE) else REPO).as_posix()
            ref = put(f'matched-stock/raw/{loc}@{digest(data)}', data, media)
            return dict(ref, value=json.loads(data)) if media == 'application/json' else dict(ref, raw=data)

        origin = store.read(TASK, iteration + ':report')
        contract = origin['values']
        preceding = contract['report']
        manifest = contract['plan']['manifest']
        demand(manifest['sha256'] == plan['candidate_manifest_sha256'] ==
               digest(safe_bytes(Path(plan['candidate_manifest']))), 'Prior C5 manifest differs from the current run')
        earlier = store.artifact_bytes(TASK, preceding['artifact_id'])
        demand(digest(earlier) == preceding['sha256'], 'Original C5 report bytes changed')
        original_id = iteration + '/analysis-input.json'
        old_raw = store.artifact_bytes(TASK, original_id)
        proof = json.loads(store.artifact_bytes(TASK, iteration + '/verify-receipt.json'))
        demand(proof['outputs']['verification']['done'] is True and digest(old_raw) in proof['key'],
               'Original C5 screen lacks native verification of the exact analysis packet')
        original = json.loads(old_raw)
        previous_scope = original['candidate']['scope']
        candidate_manifest = json.loads(safe_bytes(Path(plan['candidate_manifest'])))
        previous_row, = candidate_manifest['launches']
        demand(previous_scope['profile']['sha256'] == previous_row['profile_sha256'], 'C5 launch profile differs from original')
        regions = capture(BASE / 'OPS/p4/source-regions.json')
        prompts = capture(HERE / 'prompts/MANIFEST.json')
        demand(regions['sha256'] == plan['regions_sha256'] == original['controls'][0]['regions_sha256'] and
               prompts['sha256'] == plan['prompt_manifest_sha256'] == original['prompt_manifest']['sha256'],
               'Matched stock prompt or source geometry changed')
        expected = {p['target_tokens_including_template']: p['prompt_sha256'] for p in prompts['value']['prompts']}
        for size, wanted in expected.items():
            demand(capture(HERE/'prompts'/f'{size}.txt', 'text/plain')['sha256'] == wanted, 'Fixed prompt bytes changed')
        measured, rows, _ = read_launch(BASE, launch, plan, regions['value'], expected,
                                        timepoint(plan['frozen_at']), {}, capture, pooled_screen=True)
        matched_manifest = put('matched-stock/admitted-launch.json', raw)
        evidence = dict(mode='c5-matched-stock', original_screen=dict(artifact_id=original_id, sha256=digest(old_raw), value=original),
                        matched_stock=dict(scope=measured, requests=rows), candidate_profile=previous_scope['profile'],
                        launch_manifest=matched_manifest)
        evidence_ref = put('matched-stock/analysis-input.json', json_bytes(evidence))
        host = Host(home / 'analysis-ccv2')
        release = host.seal(REPO / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        key = f'{iteration}:matched-stock:{release}:{evidence_ref["sha256"]}'
        receipt = host.call(release, 'analyze', {'evidence': evidence}, key=key+':analyze', grants=['process.exec'])
        result = receipt.get('outputs', {}).get('analysis')
        demand(result is not None, f'Native C5 matched-stock analysis refused evidence: {receipt.get("diagnostics")}')
        verified = host.call(release, 'verify', {'evidence': evidence, 'analysis': result}, key=key+':verify', grants=['process.exec'])
        demand(verified.get('outputs', {}).get('verification', {}).get('done') is True, 'Native matched-stock verification failed')
        lab_ids = retained.copy()
        result_ref = put('matched-stock-analysis.json', json_bytes(result))
        receipt_ref = put('matched-stock/verify-receipt.json', json_bytes(verified))
        analyzed_ref = put('matched-stock/analyze-receipt.json', json_bytes(receipt))
        released_ref = put('matched-stock/release-manifest.json', safe_bytes(host.store/'releases'/release/'manifest.json'))
        cc = dict(id=CAPSULE, version=host.describe(release)['version'], release=release)
        summary, appendix = render(result)
        doc = appendix+b'\n'+earlier
        summary = preceding['summary'] + ' ' + summary
        report = dict(put('report-v2.md', doc, 'text/markdown'), status=preceding['status'], summary=summary, revision=2,
                      supersedes_artifact_id=preceding['artifact_id'], supersedes_observation_id=iteration+':report')
        outputs = [r['artifact_id'] for r in (result_ref, receipt_ref, analyzed_ref, released_ref)]
        revised = deepcopy(contract)
        revised['lab']['result_artifact_ids'] += lab_ids
        revised['analysis']['output_artifact_ids'] += outputs
        revised['analysis']['ccs'].append(cc)
        revised['analysis']['matched_stock_comparison'] = dict(result, result_artifact=result_ref, verification=receipt_ref)
        revised['plan']['matched_stock_manifest'] = matched_manifest
        revised['report'] = report
        append_once(store, TASK, dict(obs_id=iteration+':report-v2', kind='factory_iteration_report_revision',
                    values=revised, source_artifacts=list(dict.fromkeys(origin['source_artifacts'] + retained))))
    out = BASE / 'OPS/iterations' / iteration
    (out/'report-v2.md').write_bytes(doc)
    (out/'iteration-v2.json').write_bytes(json_bytes(revised))
    (out/'matched-stock-analysis.json').write_bytes(json_bytes(result))
    return dict(report=report, native_verification=receipt_ref, analysis=result_ref)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.manifest, args.manifest_sha256), indent=2))
