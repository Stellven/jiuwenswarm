#!/usr/bin/env python3
"""Verify a candidate-only 30 GiB screen against four closed A+30 scopes."""
import argparse
import json
from pathlib import Path
import re

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest, safe_bytes
from combined_gate_evidence import readback as combined_readback
from report_p1 import CAPSULE, TASK, json_bytes
from report_p4 import HERE, REPO, demand, read_launch, reference, timepoint


BASE = Path.home() / 'predemo-spark'
CONTROL_ITERATIONS = ('spark-p4-cache30-attribution', 'spark-p4-cache30-direct-seed')
MARKERS = {'C4': ('expert_demand_predictor:',), 'C2': ('weight_placement_planner:',),
           'C5': ('batch_layout_mapper:',),
           'D': ('runtime_event_recorder:', 'weight_placement_planner:', 'expert_weight_cache:',
                 'expert_demand_predictor:', 'batch_layout_mapper:')}


def old_controls(store):
    controls, refs = [], []
    for iteration in CONTROL_ITERATIONS:
        envelope = store.read(TASK, iteration + ':report')['values']
        source = envelope['plan']['manifest']
        result = envelope['analysis']['result_artifact']
        verify = envelope['analysis']['focused_comparison']['verification']
        raw = store.artifact_bytes(TASK, iteration + '/analysis-input.json')
        verification = json.loads(store.artifact_bytes(TASK, verify['artifact_id']))
        demand(verification['outputs']['verification']['done'] is True and digest(raw) in verification['key'] and
               all(store.read_artifact(TASK, ref['artifact_id'])['sha256'] == ref['sha256']
                   for ref in (source, result, verify, envelope['report'])),
               'A+ historical control is missing its exact native evidence or verified result')
        previous = json.loads(raw)
        for scope in previous['scopes']:
            if scope['arm'] == 'A+':
                identities = [row for row in previous['requests'] if row['scope_id'] == scope['artifact_id']]
                controls.append(dict(id=f'{iteration}:A+:{scope["launch_pass"]}', iteration_id=iteration, scope=scope,
                                     requests=identities, regions_sha256=previous['source_regions']['sha256'],
                                     prompts_sha256=previous['prompt_manifest']['sha256']))
        refs.extend([envelope['report'], source, result, verify, store.read_artifact(TASK, iteration + '/analysis-input.json')])
    return controls, refs


def render(report):
    subject = report['subject_arm']
    overlap = 'Competing CPU activity was observed.' if report['cpu_overlap_observed'] else 'No competing CPU activity was observed at the sampled boundaries.'
    estimates = []
    for row in report['rows']:
        change = row['pooled_estimates']
        estimates.append(f'{row["prompt_tokens"]} tokens ({change["ttft_seconds_saved"]["median"]:+.3f} s TTFT saved, '
                         f'{change["decode_tps_gained"]["median"]:+.3f} tok/s gained)')
    parity = 'Greedy output and reasoning matched.' if report['greedy_parity'] else 'Greedy output or reasoning differed.'
    summary = f'{subject} screened against four prior quiet A+30 scopes. Median paired differences at {" and ".join(estimates)}. {parity}'
    lines = [f'# {subject} pooled A+30 screening', '', summary, '', overlap, '', *report['limitations'], '']
    if not report['greedy_parity']:
        lines.extend(['Greedy output or reasoning differs from the controls. Timing is descriptive.', ''])
    allocation = report['candidate_bank']['allocated_mib']
    text = f'The candidate logged {allocation:,.2f} MiB. The four controls logged ' + ', '.join(
        f'{x:,.2f} MiB' for x in report['control_allocated_mib']) + '.'
    cap = report['cap']
    lines.extend([text, '', f'Startup to first healthy response took {report["startup_seconds"]:.2f} s. '
                  f'Host memory available stayed at or above {cap["min_mem_available_bytes"] / 1024**3:.2f} GiB. '
                  f'The capped scope recorded zero OOM events and {int(cap["memory_events"]["max"]):,} memory.max reclaim events.', ''])
    if report['package_treatment'] and subject != 'C5':
        lines.extend(['Placement and its allocation/readback differences are part of the treatment. These timings describe the package.', ''])
    if mapping := report.get('mapper'):
        summary = 'C5 and its single-slot, 4096-context, batch-2047 profile were screened as one package. ' + summary
        lines[2] = summary
        bank, control = (report[key] for key in ('candidate_bank', 'control_bank'))
        lines += ['## Mapper runtime settings and logical cuts', '',
                  '| Arm | Slots | Context | Batch | Ubatch | Requested bank MiB | Actual bank MiB | CPU miss share |',
                  '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for label, cell in (('C5 package', bank), ('Pooled A+', control)):
            settings = ' | '.join(str(cell['effective_settings'][k]) for k in ('n_slots', 'n_ctx', 'n_batch', 'n_ubatch'))
            lines.append(f'| {label} | {settings} | {cell["requested_mib"]:,} | {cell["allocated_mib"]:,.2f} | {cell["cpu_share_pct"]:.0f}% |')
        lines += ['', 'The candidate explicitly disables context checkpoints. The recorded launch artifact retains the full command.', '',
                  f'The gate-on log recorded {mapping["decisions"]:,} layout decisions, {mapping["rows"]:,} mapped rows and '
                  f'{mapping["bypasses"]:,} bypasses across all requests, including warmups.', '']
        cuts = ', '.join(f'{a}–{b}' for a, b in mapping['cuts_2048'])
        if mapping['all_2048_split']:
            lines += [f'All {mapping["prompts_2048"]} 2048-token prompts logged the logical cuts 0–1536 and 1536–2048.', '']
        else:
            lines += [f'Across {mapping["prompts_2048"]} 2048-token prompts, the logged logical cuts were {cuts or "absent"}. '
                      'The full expected split was not observed for every prompt.', '']
        earlier = report['earlier_matched_flags']
        lines += ['The logical cut markers do not measure physical dispatch counts.', '',
                  f'Earlier matched-flags functional control `{earlier["artifact_id"]}` used the legacy ELF without a native bank. '
                  'It reported greedy parity and zero mapper decisions. Its discarded timings do not estimate this repair’s effect.', '']
    if placement := report.get('placement'):
        summary = 'C2 placed three layer-27 projections on CUDA0. ' + summary
        lines[2] = summary
        lines += ['## Placement readback', '',
                  f"The v1 manual policy reports {placement['cpu_mapped_expert_tensors']} other expert weights on CPU_Mapped. "
                  'The tier-v2 path requires the native bank to be disabled.', '',
                  '| Tensor | Actual buffer | Payload bytes |', '| --- | --- | ---: |']
        lines.extend(f"| {row['name']} | {row['buffer']} | {row['bytes']:,} |" for row in placement['selected'])
        lines.append('')
    if gates := report['activation_readbacks'].get('combined_runtime'):
        trace = gates['recorder']['trace']
        lines.extend(['## Runtime gate readbacks', ''])
        if terminal := trace['summary']:
            lines.extend([f'The recorder wrote {terminal["written"]:,} of {terminal["expected"]:,} events with '
                          f'{terminal["lost"]:,} losses, {terminal["transfer_incomplete"]:,} incomplete transfer records, '
                          f'and {terminal["bytes_transferred"]:,} submitted bytes. '
                          f'Trace status is `{trace["status"]}`.', ''])
        else:
            lines.extend([f'The recorder trace has status `{trace["status"]}` without a terminal summary.', ''])
        placement = gates['placement']
        lines.extend([f'Placement emitted {placement["expert_assignment_rows"]} expert tensor readbacks among '
                      f'{placement["all_assignment_rows"]:,} assignments. CPU-equivalent placement verified '
                      f'for all 120 experts is {str(placement["cpu_equivalent"]).lower()}.', ''])
        for label, key in (('Legacy expert cache', 'legacy_cache'), ('Legacy demand predictor', 'legacy_predictor'),
                           ('Batch layout mapper', 'mapper')):
            gate = gates[key]
            detail = ', '.join(gate['declined']) or 'No decline marker observed'
            lines.append(f'- {label} reported {len(gate["active"])} activation markers and {len(gate["declined"])} decline markers. {detail}.')
        lines.extend([f'- The mapper emitted {len(gates["mapper"]["observed_cuts"])} changed cuts.', ''])
    for row in report['rows']:
        lines += [f'## {row["prompt_tokens"]}-token prompts', '',
                  '| Arm | TTFT median, range (s) | Decode median, range (tok/s) |', '| --- | ---: | ---: |']
        absolute = [(subject, row['candidate']), ('Pooled A+', row['pooled_reference'])]
        absolute.extend((control['id'], control['absolute']) for control in row['controls'])
        for label, field in absolute:
            values = [f'{field[k]["median"]:.3f} [{field[k]["observed_range"][0]:.3f}, {field[k]["observed_range"][1]:.3f}]'
                      for k in ('ttft_s', 'decode_tps')]
            lines.append(f'| {label} | {values[0]} | {values[1]} |')
        lines.extend(['', '| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |',
                      '| --- | ---: | ---: |'])
        keys = ('ttft_seconds_saved', 'decode_tps_gained')
        rows = [('Pooled by ordinal', row['pooled_estimates']), *[(x['id'], x) for x in row['controls']],
                ('Exclude third control warmup', row['sensitivity']['exclude_control_warmup'])]
        for label, item in rows:
            lines.append(f'| {label} | {item[keys[0]]["median"]:+.3f} | {item[keys[1]]["median"]:+.3f} |')
        a, b = (row['sensitivity'][key] for key in keys)
        lines.extend(['', f'Across individual controls, median TTFT saved ranged from {a[0]:+.3f} to {a[1]:+.3f} s '
                      f'and median decode gained ranged from {b[0]:+.3f} to {b[1]:+.3f} tok/s.', ''])
    readiness = report.get('predictor_decode')
    if readiness:
        lines += ['## Decode readiness', '', f'Coverage `{readiness["status"]}` across {readiness["graph_rows"]} observed '
                  f'graph rows and {readiness["observed_requests"]} request IDs. '
                  f'{readiness["requests_with_useful_ready"]} request IDs showed a completed prefetch consumed by demand.', '']
        if readiness['totals']:
            lines += ['| Counter | Value |', '| --- | ---: |']
            lines.extend(f'| {key.replace("_", " ")} | {value:,} |' for key, value in readiness['totals'].items() if value is not None)
            lines.extend(f'| {key.replace("_", " ")} | {value:,} |' for key, value in readiness['demand'].items() if value is not None)
            lines.append('')
    return summary, ('\n'.join(lines) + '\n').encode()


def native_build_lineage(plan, scope, capture, put):
    load = capture(scope / 'load-ready.json')['value']
    inventory = capture(Path(load['products_manifest']))
    demand(inventory['sha256'] == plan['products_manifest_sha256'], 'Pooled native product inventory changed')
    product, = [p for p in inventory['value']['products'] if p['receipt_artifact_id'] == load['native_build_receipt']]
    demand(product['source_commit'] == load['source_commit'], 'Native candidate is missing its exact source/build association')
    with Store(Path(product['home'])) as producer:
        refs = []
        for kind in ('receipt', 'record'):
            data = producer.artifact_bytes(product['task_id'], product[kind + '_artifact_id'])
            demand(digest(data) == product[kind + '_sha256'], 'Native build evidence digest changed')
            refs.append(put(f'{plan["iteration_id"]}/native/{kind}.json', data)['artifact_id'])
    return dict(source_commit=product['source_commit'], home=product['home'], task_id=product['task_id'],
                diff_artifact_id=None, verification_receipt_ids=[], build_receipt_ids=refs,
                binary_sha256=product['executable']['sha256'])


def source_lineage(arm, source_do, iteration, capture, put):
    manifests = {'C4': 'predictor-iteration2-source-product.json', 'D': 'combined-d-source-product.json',
                 'C5': 'mapper-alora-source-product.json'}
    source = capture(BASE / 'OPS/p3' / manifests[arm])
    identity = source['value']
    predictor = arm == 'C4'
    demand(identity['head' if arm == 'D' else 'source_commit'] == source_do['source_commit'] and
           all(identity[k] == source_do[k] for k in ('home', 'task_id')), 'Pooled source product differs from the built release')
    diff = (identity['source_diff'] if predictor else
            dict(artifact_id=identity['diff_artifact_id'], sha256=identity['diff_sha256']))
    source_plan = {}
    with Store(Path(identity['home'])) as producer:
        task = identity['task_id']

        def mirror(entry):
            identifier = entry['artifact_id']
            raw = producer.artifact_bytes(task, identifier)
            demand(entry.get('sha256', digest(raw)) == digest(raw), 'Pooled source artifact has a different digest')
            media = producer.read_artifact(task, identifier)['media_type']
            return put(f'{iteration}/do/{identifier}', raw, media)['artifact_id']

        if predictor:
            decision = producer.read(task, identity['planner_decision'])
            decision_ref = put(f'{iteration}/do/decision.json', json_bytes(decision))
            source_plan = dict(decision_id=identity['planner_decision'], decision_artifact_id=decision_ref['artifact_id'],
                               decision_sha256=decision_ref['sha256'], builder_ccs=[dict(id='routing.build_expert_demand_predictor',
                                   version='1.2.1', release=identity['verifier_release'])])
            verification = [identity['static_verification']]
        elif arm == 'C5':
            decision = producer.read(task, identity['planner_decision'])
            decision_ref = put(f'{iteration}/do/decision.json', json_bytes(decision))
            receipt = identity['native_verifier_artifact_id']
            validated = json.loads(producer.artifact_bytes(task, receipt))
            demand(validated['outputs']['done'] is True and validated['call'] == identity['native_verifier_call'] and
                   validated['release'] == identity['native_verifier_release'], 'C5 native source verdict changed')
            source_plan = dict(decision_id=decision['decision_id'], decision_artifact_id=decision_ref['artifact_id'],
                               decision_sha256=decision_ref['sha256'], builder_ccs=[dict(id='engine.build_batch_layout_mapper',
                                   version='1.1.4', release=validated['release'])])
            verification = [dict(artifact_id=receipt)]
        else:
            stages = identity['incremental_stages']
            demand(len(stages) == 5 and stages[-1]['commit'] == source_do['source_commit'] and all(s['done'] is True for s in stages),
                   'Combined D source lacks its five successful verifier receipts')
            verification = [dict(artifact_id=stage['receipt_artifact_id']) for stage in stages]
        source_do.update(source_product=reference(source), diff_artifact_id=mirror(diff),
                         verification_receipt_ids=[mirror(row) for row in verification])
    return source_plan


def earlier_mapper_control(iteration, put):
    task = 'spark-star-batch-layout-mapper'
    with Store(BASE / 'factory-runs/star-batch_layout_mapper') as source:
        ref = source.read(task, 'spark-c5-functional:report')['values']['report']
        raw = source.artifact_bytes(task, ref['artifact_id'])
        demand(digest(raw) == ref['sha256'] == '3103d2ab16df187c1e106bfd8ab0a2d9fd848b462e3a077fbaca755f6be5d441',
               'Earlier matched-flags C5 control changed')
        return put(f'{iteration}/history/{ref["artifact_id"]}', raw, 'text/markdown')


def placement_source_lineage(store, launch, iteration, put):
    inventory = json.loads(store.artifact_bytes(TASK, launch['provenance']['products']['artifact_id']))
    product, = inventory['products']
    with Store(Path(product['home'])) as native:
        task = product['task_id']
        source = native.read(task, 'spark-placement-tier-source-verified')['values']
        demand(source['head'] == launch['source_commit'] == product['source_commit'], 'C2 launch diverges from the verified source')
        controls = json.loads(native.artifact_bytes(task, source['launch_profile_artifact']))
        decision = native.read(task, task + ':decision:3')

        def mirror(identifier, digest_value=None):
            artifact = native.read_artifact(task, identifier)
            demand(digest_value is None or artifact['sha256'] == digest_value, 'C2 native source or build receipt changed')
            raw = native.artifact_bytes(task, identifier)
            return put(f'{iteration}/do/{identifier}', raw, artifact['media_type'])

        method = mirror(source['launch_profile_artifact'])
        diff = mirror(controls['diff_href'], source['diff_sha256'])
        static = mirror('spark-placement-tier-source-verify.json')
        verification = json.loads(native.artifact_bytes(task, 'spark-placement-tier-source-verify.json'))
        demand(verification.get('done') is True or verification.get('outputs', {}).get('done') is True,
               'C2 native source verdict missing')
        receipts = [mirror(product[f'{key}_artifact_id'], product[f'{key}_sha256']) for key in ('receipt', 'record')]
        plan = put(f'{iteration}/do/source-decision.json', json_bytes(decision))
    return (dict(decision_id=decision['decision_id'], home=product['home'], task_id=task,
                 decision_artifact_id=plan['artifact_id'], decision_sha256=plan['sha256'],
                 builder_ccs=[dict(id='placement.build_weight_placement_planner', version='1.2.1', release=controls['verifier_release'])]),
            dict(home=product['home'], task_id=task, source_commit=product['source_commit'],
                 source_product=method, diff_artifact_id=diff['artifact_id'], verification_receipt_ids=[static['artifact_id']],
                 build_receipt_ids=[item['artifact_id'] for item in receipts]))


def publish(path, pin):
    raw = safe_bytes(path)
    plan = json.loads(raw)
    iteration = plan['iteration_id']
    demand(digest(raw) == pin and plan['schema'] == 'spark-pooled30-admission/1' and
           re.fullmatch(r'spark-pooled30-[a-z0-9-]+', iteration), 'The frozen pooled screen admission differs from its SHA-256 pin')
    home = BASE / 'factory-runs/spark-direct-benchmarks'
    with Store(home) as store:
        try:
            existing = store.read(TASK, iteration + ':report')['values']
        except NotFound:
            existing = None
        if existing:
            demand(existing['plan']['manifest']['sha256'] == pin, 'Pooled iteration already uses another manifest')
            return existing['report']
        retained = []

        def put(identifier, value, media='application/json'):
            ref = reference(store.put_artifact(TASK, identifier, value, media, None))
            retained.append(ref['artifact_id'])
            return ref

        def capture(filepath, media='application/json'):
            data = safe_bytes(filepath)
            label = filepath.relative_to(BASE if filepath.is_relative_to(BASE) else REPO).as_posix()
            ref = put(f'{iteration}/raw/{label}@{digest(data)}', data, media)
            return dict(ref, value=json.loads(data)) if media == 'application/json' else dict(ref, raw=data)

        plan_ref = put(iteration + '/admitted-launch.json', raw)
        prompts = capture(HERE / 'prompts/MANIFEST.json')
        regions = capture(BASE / 'OPS/p4/source-regions.json')
        expected = {p['target_tokens_including_template']: p['prompt_sha256'] for p in prompts['value']['prompts']}
        historical, controls_refs = old_controls(store)
        demand(prompts['sha256'] == plan['prompt_manifest_sha256'] and regions['sha256'] == plan['regions_sha256'] and
               all(c['prompts_sha256'] == prompts['sha256'] and c['regions_sha256'] == regions['sha256'] for c in historical),
               'Pooled candidate and controls have different fixed prompt or source geometry')
        for size, sha in expected.items():
            demand(capture(HERE / 'prompts' / f'{size}.txt', 'text/plain')['sha256'] == sha, 'Fixed prompt input changed')
        launch, rows, _ = read_launch(BASE, plan['launches'][0], plan, regions['value'], expected,
                                      timepoint(plan['frozen_at']), {}, capture, pooled_screen=True)
        scope = BASE / plan['launches'][0]['scope']
        log = safe_bytes(scope / 'stderr.log').decode(errors='replace')
        readbacks = {}
        for marker in MARKERS.get(launch['arm'], ()):
            statements = [line.split(marker, 1)[1].strip() for line in log.splitlines() if marker in line]
            readbacks[marker] = dict(count=len(statements), first=statements[:8], last=statements[-8:])
        if launch.get('placement'):
            readbacks['verified_placement'] = launch['placement']
        if launch['arm'] == 'D':
            gates = combined_readback(scope)
            demand(gates['stderr_sha256'] == launch['provenance']['engine_log']['sha256'] and
                   gates['recorder']['trace'].get('sha256') == launch['provenance']['event_trace']['sha256'],
                   'Combined gate evidence differs from retained log or recorder stream')
            readbacks['combined_runtime'] = gates
            value = json_bytes(gates)
            put(iteration + '/runtime-gates.json', value)
            (BASE / 'OPS/p3/combined-d-pooled30-gates.json').write_bytes(value)
        payload = dict(mode='pooled-30-screen', prompt_manifest=prompts, candidate=dict(scope=launch, requests=rows),
                       controls=historical, activation_readbacks=readbacks)
        if launch['arm'] == 'C5':
            payload['earlier_matched_flags'] = earlier_mapper_control(iteration, put)
        evidence_ref = put(iteration + '/analysis-input.json', json_bytes(payload))
        host = Host(home / 'analysis-ccv2')
        release = host.seal(REPO / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        key = f'{iteration}:{release}:{evidence_ref["sha256"]}'
        analyzed = host.call(release, 'analyze', {'evidence': payload}, key=key+':analyze', grants=['process.exec'])
        analysis = analyzed.get('outputs', {}).get('analysis')
        demand(analysis is not None, f'Pooled analysis rejected the retained evidence: {analyzed.get("diagnostics")}')
        verified = host.call(release, 'verify', {'evidence': payload, 'analysis': analysis}, key=key+':verify', grants=['process.exec'])
        demand(verified.get('outputs', {}).get('verification', {}).get('done') is True, 'Native pooled verification failed')
        summary, text = render(analysis)
        if launch['arm'] == 'C2':
            source_plan, source_do = placement_source_lineage(store, launch, iteration, put)
        else:
            source_do = native_build_lineage(plan, scope, capture, put)
            source_plan = source_lineage(launch['arm'], source_do, iteration, capture, put)
        lab_ids = list(dict.fromkeys([*retained, *(c['artifact_id'] for c in controls_refs)]))
        analysis_ref = put(iteration + '/analysis.json', json_bytes(analysis))
        receipt = put(iteration + '/verify-receipt.json', json_bytes(verified))
        output = put(iteration + '/analyze-receipt.json', json_bytes(analyzed))
        manifest = put(iteration + '/release-manifest.json', safe_bytes(host.store / 'releases' / release / 'manifest.json'))
        report = dict(put(iteration + '/report.md', text, 'text/markdown'), summary=summary, status='pooled-control-screening')
        outputs = [x['artifact_id'] for x in (analysis_ref, receipt, output, manifest)]
        predecessors = [payload['earlier_matched_flags']['artifact_id']] if 'earlier_matched_flags' in payload else []
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=iteration, predecessor_report_ids=predecessors,
            plan=dict(decision_id=None, builder_ccs=[], incoming_report_ids=[], manifest=plan_ref,
                      summary='Screen one candidate launch against four closed, position-matched A+30 controls.') | source_plan,
            do=source_do,
            lab=dict(status='pooled-control-screening', result_artifact_ids=lab_ids),
            analysis=dict(ccs=[dict(id=CAPSULE, version=host.describe(release)['version'], release=release)],
                          output_artifact_ids=outputs, result_artifact=analysis_ref, pooled_comparison=analysis),
            report=report, next_plan=dict(decision_id=None))
        append_once(store, TASK, dict(obs_id=iteration+':report', kind='factory_iteration_report', values=envelope,
            source_artifacts=lab_ids + outputs + [report['artifact_id']]))
    out = BASE / 'OPS/iterations' / iteration
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (('report.md', text), ('analysis.json', json_bytes(analysis)), ('iteration.json', json_bytes(envelope))):
        (out / name).write_bytes(value)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.manifest, args.manifest_sha256), indent=2))


if __name__ == '__main__':
    main()
