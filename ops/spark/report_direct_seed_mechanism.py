"""Publish a source-page and request-I/O supplement to the verified direct-seed ABBA."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from statistics import median
import sys

from jiuwenswarm.factory.store import NotFound, Store

from expert_seed_residency import classify, read_layout, startup_admissions, utc
from import_evidence import append_once, digest, safe_bytes
from report_p1 import TASK, json_bytes
from report_p4 import demand, reference

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parents[1] / 'jiuwenswarm/factory/ccs/spark_gap_analysis'
sys.path.insert(0, str(BUNDLE))
try:
    from direct_seed import seed_ledger
    from residency_speed import boundaries
finally:
    sys.path.pop(0)

ROOT = Path.home() / 'predemo-spark'
ITERATION = 'spark-p4-cache30-direct-seed'
PREFIX = ITERATION + '/mechanism'
SOURCE_HOME = 'factory-runs/star-expert_weight_cache-direct-seed-02b'
SOURCE_TASK = 'spark-cache-direct-seed-do-02b'
ARMS = ('A+', 'C3-direct')
CLASSES = ('startup_seeded', 'other_expert')
PHASES = ('start_to_first_token', 'first_token_to_end')
METRICS = ('process_read_bytes', 'process_major_faults', 'cgroup_file_refaults')


def sample(ref, value, load, layouts, seeded, label):
    totals, fingerprint = classify(value, layouts, seeded)
    demand(all(totals[k]['weighted_resident_fraction'] is not None for k in CLASSES),
           'A sampled expert class has no valid coverage')
    return dict(label=label, receipt=reference(ref), started=value['started'], completed=value['completed'],
                after_ready_s=(utc(value['completed']) - utc(load['ready_at'])).total_seconds(),
                totals=totals), fingerprint


def aggregate(values):
    return dict(n=len(values), median=median(values), min=min(values), max=max(values), values=values)


def measured_summary(scopes):
    groups = []
    for arm in ARMS:
        scope_rows = [row for scope in scopes if scope['arm'] == arm for row in scope['requests'] if row['repeat']]
        for size in (512, 2048):
            rows = [r for r in scope_rows if r['prompt_tokens'] == size]
            demand(len(rows) == 10 and {r['repeat'] for r in rows} == set(range(1, 11)),
                   'Expected ten positions indexed across the two mirrored launches')
            phase_stats = {}
            for phase in PHASES:
                phase_stats[phase] = {key: aggregate([row['phases'][phase][key] for row in rows]) for key in METRICS}
                shared = set.intersection(*(set(row['phases'][phase].get('host_nvme_read_bytes', {})) for row in rows))
                phase_stats[phase]['host_nvme_read_bytes'] = {device: aggregate([
                    row['phases'][phase]['host_nvme_read_bytes'][device] for row in rows]) for device in sorted(shared)}
            groups.append(dict(arm=arm, prompt_tokens=size, phases=phase_stats,
                               ttft_s=aggregate([r['ttft_s'] for r in rows]),
                               decode_tps=aggregate([r['decode_tps'] for r in rows]),
                               residency={kind: aggregate([
                                   row['sample']['totals'][kind]['weighted_resident_fraction'] for row in rows]) for kind in CLASSES}))
    return groups


def collect(evidence, extents, read, read_raw):
    layouts, projection_size = read_layout(extents)
    scopes = evidence['scopes']
    demand([(r['arm'], r['launch_pass']) for r in scopes] == [('A+', 1), ('C3-direct', 1), ('C3-direct', 2), ('A+', 2)],
           'Expected the complete direct-seed 30 GiB mirror')
    ledgers, seeded, exact_slots = {}, None, None
    for scope in scopes:
        if scope['arm'] != 'C3-direct':
            continue
        provenance = scope['provenance']
        log = read_raw(provenance['engine_log']).decode(errors='replace')
        profile = dict(provenance['nomination_profile'], value=read(provenance['nomination_profile']))
        activated = dict(provenance['activation'], value=read(provenance['activation']))
        ledger = seed_ledger(log, 'on', {'activation': activated}, {'profile_sha256': profile['sha256']},
                             profile['value'], reference)
        admitted, upload_bytes = startup_admissions(log, projection_size)
        slots = ledger.pop('admitted_slots')
        slot_sha = digest(json.dumps(slots, sort_keys=True).encode())
        verified = scope['direct_seed']
        demand(slot_sha == verified['admitted_slots_sha256'] and
               upload_bytes == verified['direct_io']['uploaded_payload_bytes'] == ledger['active']['initial_h2d_bytes'] and
               ledger == {key: verified[key] for key in ledger}, 'Raw direct ledger differs from the verified P4 record')
        if seeded is None:
            seeded, exact_slots = admitted, slot_sha
        demand(admitted == seeded and exact_slots == slot_sha, 'Candidate passes do not share the same seed IDs and slots')
        ledgers[scope['artifact_id']] = dict(ledger, admitted_slots_sha256=slot_sha, engine_log=provenance['engine_log'])
    common = None
    result = []
    for scope in scopes:
        load, kernel = read(scope['load']), read(scope['scope'])
        owner = scope['artifact_id']
        provenance = scope['provenance']

        def classify_sample(ref, value, label):
            nonlocal common
            classified, fingerprint = sample(ref, value, load, layouts, seeded, label)
            if common is None:
                common = fingerprint
            demand(common == fingerprint, 'Expert sample or stratum identities changed among captures')
            return classified

        prelaunch = scope['conditioning']
        conditioned = classify_sample(prelaunch, read(prelaunch)['after'], 'post-conditioning')
        demand(not any(conditioned['totals'][kind]['resident_sampled_pages'] for kind in CLASSES),
               'The matched source reset did not clear sampled expert pages')
        ready = None
        if 'load_ready_residency' in provenance:
            ref = provenance['load_ready_residency']
            record = read(ref)
            demand(record['scope_accounting']['path'] == kernel['cgroup'] and utc(record['started']) >= utc(load['ready_at']),
                   'Post-ready sample does not match scope readiness')
            ready = classify_sample(ref, record, 'post-ready')
        rows = []
        for position, row in enumerate((r for r in evidence['requests'] if r['scope_id'] == owner), 1):
            request = row['result']
            resource = row['evidence']['resource_windows']
            phases = boundaries({'request_resources': dict(resource, value=read(resource))}, kernel['pid'])
            first = phases['phases']['start_to_first_token']
            demand(first['process_read_bytes'] == row['first_token_io']['read_bytes'] and
                   first['process_major_faults'] == row['first_token_io']['major_faults'],
                   'Raw phase counts do not equal the verified P4 first-token deltas')
            observed = None
            if 'residency' in row['evidence']:
                ref = row['evidence']['residency']
                label = 'before-request' if request['repeat'] else 'after-warmup-pair'
                observed = classify_sample(ref, read(ref), label)
            rows.append(dict(position=position, repeat=request['repeat'], prompt_tokens=request['prompt_tokens'],
                             ttft_s=request['ttft_s'], decode_tps=request['decode_tps'], sample=observed,
                             request=reference(row), resource=resource, **phases))
        demand(len(rows) == 16 and sum(row['sample'] is not None for row in rows) == 13,
               'Expected 16 phase windows and 13 request-linked source-page captures per launch')
        demand((ready is not None) == (scope['launch_pass'] == 2), 'Post-ready coverage differs from the retained pass-2-only design')
        records = [row['process'] for row in rows]
        demand(all(record == records[0] for record in records), 'Engine changed during one launch')
        result.append(dict(arm=scope['arm'], pass_number=scope['launch_pass'], load_ready_s=load['health_elapsed_s'],
                           claim=ledgers.get(owner), conditioned=conditioned, post_ready=ready, requests=rows,
                           scope=reference(scope), ready_receipt=reference(scope['load'])))
    return dict(schema='spark-direct-30-seed-mechanism/1', admitted_layer_expert_ids=sorted(list(key) for key in seeded),
                source_pages=dict(page_size_bytes=common[0], pages_per_sample=common[1], seed=common[2]),
                scopes=result, steady=measured_summary(result),
                limitations=[
                    'Post-ready was captured on pass 2 only, before any request in those scopes. The pass 1 warmup-pair samples start later.',
                    'A+ uses the comparison classes from actual C3-direct admissions. It has no startup profile seed.',
                    'Each stratum contributes one deterministic mincore observation. Weight estimates source file-cache occupancy. Pages with slice or tensor boundary overlap are excluded.',
                    'Device bank membership can change after startup. Phase reads are engine-process counters, with cgroup file refault and host NVMe activity retained separately.',
                    'This candidate/control comparison changes both profile seeding and its read path. A same-ELF mmap-seed comparison is needed to isolate O_DIRECT from profile admission.',
                ])


def render(data):
    ready = {scope['arm']: scope['post_ready']['totals'] for scope in data['scopes'] if scope['post_ready']}
    ap, direct = (ready[arm]['startup_seeded']['weighted_resident_fraction'] for arm in ARMS)
    summary = (f'On pass 2, {direct:.2%} of sampled seeded-class file pages were resident after direct startup '
               f'and {ap:.2%} after stock A+ startup, before either server received a prompt.')
    lines = ['## Direct seed mechanism and source-page coverage', '', summary, '',
             '| Arm | Pass | Load to ready s | Expert seed upload GiB | Direct read GiB | Direct ledger s |',
             '|---|---:|---:|---:|---:|---:|']
    for scope in data['scopes']:
        io = scope['claim']['direct_io'] if scope['claim'] else None
        transfer = [f'{io[key]/1024**3:.3f}' for key in ('uploaded_payload_bytes', 'returned_io_bytes')] if io else ['—', '—']
        ledger_time = f"{io['elapsed_us']/1e6:.3f}" if io else '—'
        lines.append(f"| {scope['arm']} | {scope['pass_number']} | {scope['load_ready_s']:.3f} | "
                     f"{transfer[0]} | {transfer[1]} | {ledger_time} |")
    lines += ['', 'Both witnessed direct ledgers completed without failure or fallback. The source-page populations use the same actual seed IDs.',
              '', '| Pass 2 after ready | Seeded class | Other expert class | Excluded boundary draws |',
              '|---|---:|---:|---:|']
    for arm in ARMS:
        classes = ready[arm]
        display = [f"{classes[label]['weighted_resident_fraction']:.2%} ({classes[label]['sampled_pages']:,} draws)" for label in CLASSES]
        lines.append(f"| {arm} | {display[0]} | {display[1]} | {classes['excluded_boundary']['sampled_pages']:,} |")
    lines += ['', 'Each launch supplies a post-conditioning capture, three after-warmup-pair captures and ten before-steady-request captures. '
                  'The pass-2 post-ready sample is the only after-load comparison.', '',
              '| Arm | Tokens | Before-request seeded / other median | Engine read MiB to first token, median [range] | Major faults to first, median [range] | Engine read MiB after first, median [range] |',
              '|---|---:|---:|---:|---:|---:|']
    for group in data['steady']:
        residency = [group['residency'][key]['median'] for key in CLASSES]
        stats = group['phases']['start_to_first_token']
        read = stats['process_read_bytes']
        later = group['phases']['first_token_to_end']['process_read_bytes']
        faults = stats['process_major_faults']
        mib = 1024**2
        lines.append(f"| {group['arm']} | {group['prompt_tokens']} | {residency[0]:.2%} / {residency[1]:.2%} | "
                     f"{read['median']/mib:.3f} [{read['min']/mib:.3f}, {read['max']/mib:.3f}] | "
                     f"{faults['median']:g} [{faults['min']}, {faults['max']}] | "
                     f"{later['median']/mib:.3f} [{later['min']/mib:.3f}, {later['max']/mib:.3f}] |")
    lines += ['', 'The analysis attachment retains both request phases, all individual timings, cgroup refaults and host NVMe deltas.', '',
              *data['limitations'], '']
    return summary, '\n'.join(lines).encode()


def publish(base):
    home = base / 'factory-runs/spark-direct-benchmarks'
    out = base / 'OPS/iterations' / ITERATION
    obs = ITERATION + ':report-v2'
    with Store(home) as store:
        source = store.read(TASK, ITERATION + ':report')['values']
        older = source['report']
        try:
            return store.read(TASK, obs)['values']['report']
        except NotFound:
            pass
        loaded = {}

        def read_raw(ref):
            ident = ref['artifact_id']
            expected = ref['sha256']
            raw = store.artifact_bytes(TASK, ident)
            demand(digest(raw) == expected, f'Retained receipt digest changed: {ident}')
            loaded[ident] = expected
            return raw

        def read(ref):
            return json.loads(read_raw(ref))

        def put(name, raw, media='application/json'):
            return reference(store.put_artifact(TASK, f'{PREFIX}/{name}', raw, media, None))

        base_report = read_raw(older)
        analysis_id = ITERATION + '/analysis-input.json'
        evidence = read(store.read_artifact(TASK, analysis_id))
        geometry = base / 'OPS/p3/cache-direct-seed-30g-expert-extents.json'
        index = put('expert-extents.json', safe_bytes(geometry))
        data = collect(evidence, read(index), read, read_raw)
        native_home = base / SOURCE_HOME
        with Store(native_home) as native:
            def mirror(identifier):
                item = native.read_artifact(SOURCE_TASK, identifier)
                copied = put('do/' + identifier, native.artifact_bytes(SOURCE_TASK, identifier), item['media_type'])
                demand(copied['sha256'] == item['sha256'], 'Copied native DO receipt changed')
                return copied

            manifest = mirror('cache-direct-seed-02b-source-product.json')
            source_manifest = read(manifest)
            native_plan = native.read(SOURCE_TASK, 'spark-c3-direct-seed-02b:plan-v2')['values']['plan']
            source_plan = mirror(native_plan['artifact_id'])
            decision = native.read(SOURCE_TASK, native_plan['decision_id'])
            product, = read(next(r['provenance']['products'] for r in evidence['scopes']
                                  if r['arm'] == 'C3-direct'))['products']
            demand(source_manifest['source_commit'] == product['source_commit'] and
                   source_manifest['planner_decision'] == decision['decision_id'] and
                   source_plan['sha256'] == native_plan['sha256'] and product['task_id'] == SOURCE_TASK,
                   'P4 subject does not bind the exact native DO and original source decision')
            diff = mirror(source_manifest['source_diff']['artifact_id'])
            verifier = mirror(source_manifest['static_verification']['artifact_id'])
            compiled = mirror(source_manifest['compiled_regression_and_syntax']['artifact_id'])
            builder = [mirror(product[f'{key}_artifact_id']) for key in ('receipt', 'record')]
            demand(diff['sha256'] == source_manifest['source_diff']['sha256'] and
                   verifier['sha256'] == source_manifest['static_verification']['sha256'] and
                   compiled['sha256'] == source_manifest['compiled_regression_and_syntax']['sha256'] and
                   [item['sha256'] for item in builder] == [product[f'{key}_sha256'] for key in ('receipt', 'record')],
                   'Native diff, static verifier, compiled check or Builder receipt changed')
        lineage_refs = [manifest, source_plan, diff, verifier, compiled, *builder]
        data.update(predecessor_report=reference(older), verified_p4_input=reference(store.read_artifact(TASK, analysis_id)),
                    source_artifacts=loaded, lineage=dict(native_home=str(native_home), native_task_id=SOURCE_TASK,
                        source_commit=product['source_commit'], planner_decision_id=decision['decision_id'], receipts=lineage_refs))
        data_ref = put('analysis.json', json_bytes(data))
        summary, appendix = render(data)
        source_note = (f'\nNative source lineage is retained for task `{SOURCE_TASK}`, source decision '
                       f'`{decision["decision_id"]}`, commit `{product["source_commit"]}`, '
                       f'verifier `{source_manifest["verifier_call"]}` and build `{product["attempt_id"]}`.\n').encode()
        report_bytes = base_report.rstrip() + b'\n\n' + appendix + source_note
        report = dict(put('report-v2.md', report_bytes, 'text/markdown'), summary=older['summary'], revision=2,
                      status=older['status'], supersedes_observation_id=ITERATION + ':report',
                      supersedes_artifact_id=older['artifact_id'])
        next_input = put('next-plan-input.json', json_bytes(dict(schema='spark-factory-next-plan-input/1', report=report,
            mechanism=data_ref, pending_decision=True, controls=[
                'Read the verified A+30 / direct 02b ABBA and its source-page supplement before selecting the next test.',
                'If isolating startup read source remains valuable, compare mmap seed and direct seed within the same 02b ELF and budget.',
                'Treat same-budget 60 GiB original C3 and 15/30/45 GiB comparisons as separate experiment inputs.',
                'If warmed TTFT remains the main gap, follow verified transfer and process phase evidence before changing prefill policy.',
            ])))
        envelope = deepcopy(source)
        envelope['report'] = report
        envelope['next_plan'] = dict(decision_id=None, input=next_input)
        envelope['plan'].update(decision_id=decision['decision_id'], decision_artifact_id=source_plan['artifact_id'],
                                decision_sha256=source_plan['sha256'], home=str(native_home), task_id=SOURCE_TASK,
                                source_plan_summary=decision['action']['summary'],
                                builder_ccs=[dict(id='engine.build_expert_weight_cache', version='1.4.1',
                                                  release=source_manifest['verifier_release'])])
        envelope['do'].update(home=str(native_home), task_id=SOURCE_TASK, source_commit=product['source_commit'],
                              source_product=manifest, diff_artifact_id=diff['artifact_id'],
                              verification_receipt_ids=[verifier['artifact_id'], compiled['artifact_id']],
                              build_receipt_ids=[item['artifact_id'] for item in builder])
        envelope['analysis']['mechanism'] = dict(summary=summary, result=data_ref, index=index, coverage='post-ready pass 2 only')
        envelope['analysis']['output_artifact_ids'] += [data_ref['artifact_id'], index['artifact_id']]
        refs = [report['artifact_id'], older['artifact_id'], data_ref['artifact_id'], index['artifact_id'],
                next_input['artifact_id'], *(item['artifact_id'] for item in lineage_refs), *loaded]
        append_once(store, TASK, dict(obs_id=obs, kind='factory_iteration_report_revision', values=envelope,
                                      source_artifacts=list(dict.fromkeys(refs))))
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in (('report-v2.md', report_bytes), ('mechanism.md', appendix),
                      ('mechanism.json', json_bytes(data)), ('iteration-v2.json', json_bytes(envelope))):
        (out / name).write_bytes(raw)
    return dict(report, mechanism=data_ref, next_plan_input=next_input, observation_id=obs, task_id=TASK, home=str(home))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(publish(args.base.resolve(strict=True)), indent=2))


if __name__ == '__main__':
    main()
