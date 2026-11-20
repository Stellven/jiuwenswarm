"""Verify and publish the completed same-budget direct expert seed diagnostic."""
import argparse
from base64 import b64encode
import gzip
import json
from pathlib import Path
from statistics import median

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import NotFound, Store

from expert_seed_residency import classify, read_layout, startup_admissions, utc
from import_evidence import append_once, digest, safe_bytes
from report_early_bracket import CAPSULE, STOCK, scope_inputs
from report_p1 import json_bytes

ROOT = Path.home() / 'predemo-spark'
ITERATION = 'spark-c3-direct-seed-02b'
TASK = 'spark-cache-direct-seed-do-02b'
HOME = 'factory-runs/star-expert_weight_cache-direct-seed-02b'
BUDGET = 30720
ROLES = ('A+', '02b-mmap', '02b-direct')
MODES = ('equivalent-stock', 'off', 'on')
MODE = 'c3-direct-seed-30g'
ASSETS = ('source', 'products', 'stock', 'prompts', 'regions', 'expert_extents')


def expected_launch(row, stock, product, inventory, profile):
    mode = row['mode']
    seeded = mode != 'equivalent-stock'
    binary = product['executable']['path'] if seeded else stock['command'][0]
    argv = [binary, *stock['command'][1:], '-lv', '4', '--moe-cache-mib', str(BUDGET), '--moe-cache-cpu-share', '0']
    return dict(label=row['label'], command=argv, source_commit=product['source_commit'] if seeded else STOCK,
                binary_sha256=product['executable']['sha256'] if seeded else stock['binary_sha256'],
                library_path=str(Path(binary).parent), products_manifest_sha256=inventory,
                build_receipt=product['receipt_artifact_id'] if seeded else None, profile_sha256=profile,
                gates=product['runtime_contract'][f'gate_{mode}_env'] if seeded else {})


def classify_sources(scopes, extents, logs):
    layouts, payload = read_layout(extents)
    seed_sets = [startup_admissions(log.decode(errors='replace'), payload) for log in logs[1:]]
    if seed_sets[0] != seed_sets[1]:
        raise ValueError('Buffered and direct startup admit different expert IDs or uploaded bytes')
    seeded, uploaded = seed_sets[0]
    results, fingerprint = {}, None
    for arm, scope in zip(ROLES, scopes, strict=True):
        load = scope['load']['value']
        first = scope['requests'][0]['residency']['value']
        first_request = scope['requests'][0]['result']['value']
        if not utc(load['ready_at']) <= utc(first['started']) <= utc(first['completed']) <= utc(first_request['started']):
            raise ValueError('First retained source sample is outside the post-ready, pre-request boundary')
        after = scope['conditioning']
        keys = scope['protocol']['value']['ordered_requests']
        samples = [('post-conditioning', dict(after, value=after['value']['after'])), ('post-ready', scope['requests'][0]['residency'])]
        samples += [(position['path'], request['residency'])
                    for position, request in zip(keys[1:], scope['requests'][1:], strict=True)]
        for label, sample in samples:
            totals, identity = classify(sample['value'], layouts, seeded)
            if fingerprint is None:
                fingerprint = identity
            if fingerprint != identity or any(totals[k]['weighted_resident_fraction'] is None for k in ('startup_seeded', 'other_expert')):
                raise ValueError('Deterministic sampled pages or class coverage differ across arms')
            results.setdefault(arm, []).append(dict(label=label, artifact_id=sample['artifact_id'],
                sha256=sample['sha256'], totals=totals))
    return dict(schema='spark-direct-seed-class-residency/1', admitted_layer_expert_ids=[list(key) for key in sorted(seeded)],
                startup_upload_bytes=uploaded, scopes=results,
                limitations=['A+ uses the nominated classes defined by the two identical 02b seed sets. A+ itself does not preseed.',
                             'Page samples track source file cache. Boundary pages are excluded and later requests can change the GPU bank.'])


def span(item):
    return f"{item['median']:+.3f} [{item['min']:+.3f}, {item['max']:+.3f}]"


def remove_sample_details(scope):
    conditioning = scope['conditioning']['value']
    samples = [conditioning['before'], conditioning['after'], *(row['residency']['value'] for row in scope['requests'])]
    for sample in samples:
        for item in sample['views']['llama']['files']:
            item.pop('expert_page_samples', None)
            item.pop('expert_sample_columns', None)


def render(analysis, hot):
    aplus, buffered, direct = analysis['scopes']
    lookup = {arm: {row['label']: row['totals'] for row in rows} for arm, rows in hot['scopes'].items()}
    buffered_hot = lookup['02b-mmap']['post-ready']['startup_seeded']['weighted_resident_fraction']
    direct_hot = lookup['02b-direct']['post-ready']['startup_seeded']['weighted_resident_fraction']
    startup_delta = direct['load_s'] - buffered['load_s']
    summary = (f"At 30 GiB, direct seeding preserved greedy output and moved the same expert bytes into the bank, "
               f"with {buffered_hot:.1%} of sampled seeded pages resident after mmap startup and {direct_hot:.1%} after direct startup "
               f"and a {startup_delta:+.3f} s change in launch-to-ready time.")
    lines = ['# C3 direct expert seed at 30 GiB', '', summary, '',
             '| Arm | Ready s | Actual bank MiB | Seeded experts | Seed upload GiB | Peak cgroup GiB |',
             '|---|---:|---:|---:|---:|---:|']
    for arm in analysis['scopes']:
        active = arm['seed']['active'] if arm['seed'] else {'seeds': 0, 'initial_h2d_bytes': 0}
        lines.append(f"| {arm['role']} | {arm['load_s']:.3f} | {arm['native_bank']['allocated_mib']:.2f} | "
                     f"{active['seeds']:,} | {active['initial_h2d_bytes']/1024**3:.3f} | {arm['peak_memory_bytes']/1024**3:.2f} |")
    ledger = direct['seed']['direct_io']
    lines += ['', (f"The direct seed issued {ledger['calls']:,} reads. The ledger records {ledger['requested_io_bytes']:,} bytes "
                  f"requested, {ledger['returned_io_bytes']:,} returned, {ledger['uploaded_payload_bytes']:,} uploaded and "
                  f"{ledger['alignment_overhead_bytes']:,} alignment bytes, with zero failures and fallbacks."), '',
              '## Expert source file-cache samples', '',
              '| Arm | Post-conditioning seeded | Post-conditioning other | Post-ready seeded | Post-ready other |',
              '|---|---:|---:|---:|---:|']
    for role in ROLES:
        groups = lookup[role]
        values = [groups[when][population]['weighted_resident_fraction']
                  for when in ('post-conditioning', 'post-ready') for population in ('startup_seeded', 'other_expert')]
        lines.append(f"| {role} | " + ' | '.join(f'{value:.2%}' for value in values) + ' |')
    lines += ['', *hot['limitations'], '', '## Cold and warm-up positions', '',
              '| Arm | Position | Tokens | TTFT s | Decode tok/s | Engine MiB to first | Engine major faults to first |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for arm in analysis['scopes']:
        for row in arm['samples']:
            if row['phase'] == 'warmup':
                counters = row['phases']['start_to_first_token']
                lines.append(f"| {arm['role']} | {row['position']} | {row['prompt_tokens']} | {row['ttft_s']:.3f} | "
                             f"{row['decode_tps']:.3f} | {counters['process_read_bytes']/1024**2:.3f} | {counters['process_major_faults']:,} |")
    lines += ['', '## Steady measurements', '',
              '| Arm | Tokens | TTFT s, median [range] | Decode tok/s, median [range] | Sampled seeded / other file-cache pages |',
              '|---|---:|---:|---:|---:|']
    for arm in analysis['scopes']:
        for size, observed in arm['steady_trend'].items():
            groups = [lookup[arm['role']][f'rep-{repeat}-{size}'] for repeat in range(1, 6)]
            fractions = [median(group[population]['weighted_resident_fraction'] for group in groups)
                         for population in ('startup_seeded', 'other_expert')]
            lines.append(f"| {arm['role']} | {size} | {span(observed['ttft_s'])} | {span(observed['decode_tps'])} | "
                         f"{fractions[0]:.2%} / {fractions[1]:.2%} |")
    lines += ['', '## Steady paired effects', '',
              '| Candidate | Control | Tokens | Pairs | Candidate minus control TTFT s | Candidate minus control decode tok/s |',
              '|---|---|---:|---:|---:|---:|']
    for comp in analysis['comparisons']:
        for row in comp['steady']:
            lines.append(f"| {comp['candidate']} | {comp['control']} | {row['prompt_tokens']} | {row['n']} | "
                         f"{span(row['ttft_delta_s'])} | {span(row['decode_gain_tps'])} |")
    lines += ['', 'The table gives medians and observed ranges. All cold and steady position pairs matched the exact greedy hashes.',
              'The analysis artifact retains absolute steady estimates, matched process read and fault windows, and host NVMe counters.', '',
              *analysis['limitations'], '']
    return summary, '\n'.join(lines).encode()


def plan_input(report, analysis, hot):
    compared = analysis['comparisons'][0]
    after = {arm: next(row['totals'] for row in rows if row['label'] == 'post-ready')
             for arm, rows in hot['scopes'].items()}
    return dict(schema='spark-factory-next-plan-input/1', incoming_report=report,
                evidence=dict(direct_vs_mmap=compared, post_ready_source_classes=after),
                pending_decision=True,
                alternatives=[
                    'Retest direct versus mmap with fresh reversed-order launches if the startup file-cache effect and serving deltas warrant repeatability checks.',
                    'If startup improves but warmed request costs persist, evaluate the separate 15/30/45 GiB matched bank/placement screen.',
                    'If seed I/O does not account for TTFT, prioritize large-prefill demand and D2D evidence before another source revision.',
                ],
                control='Repeat at the same actual bank, source, context, slots, batch limits, affinity, and profile pins.')


def publish(base, plan_path, pin):
    raw_plan = safe_bytes(plan_path)
    if digest(raw_plan) != pin:
        raise ValueError('LAB plan digest mismatch')
    plan = json.loads(raw_plan)
    rows = plan['ordered_conditions']
    if (plan['schema'] != 'spark-c3-direct-seed-lab/1' or plan['iteration_id'] != ITERATION or plan['budget_mib'] != BUDGET
            or tuple((row['arm'], row['mode']) for row in rows) != tuple(zip(ROLES, MODES))):
        raise ValueError('Unexpected LAB experiment or arm order')
    paths = {name: Path(plan[name]['path']).resolve(strict=True) for name in ASSETS}
    data = {name: safe_bytes(path) for name, path in paths.items()}
    if any(digest(raw) != plan[name]['sha256'] for name, raw in data.items()):
        raise ValueError('Frozen LAB input digest has changed')
    provenance = {name: json.loads(raw) for name, raw in data.items()}
    product, = provenance['products']['products']
    source = provenance['source']
    home, repo = base / HOME, base / 'jiuwenswarm'
    if (source['home'] != str(home) or source['task_id'] != TASK or product['home'] != str(home)
            or product['task_id'] != TASK or product['source_commit'] != source['source_commit']
            or product['runtime_contract'] != source['runtime_contract']):
        raise ValueError('Native build and DO source do not agree')
    scopes_dir = [(base / Path(row['scope'])).resolve(strict=True) for row in rows]
    if any(path.parent != base / 'OPS/runs' for path in scopes_dir) or len(set(scopes_dir)) != 3:
        raise ValueError('Expected three distinct retained LAB scopes under OPS/runs')
    prefix = f'{ITERATION}/30g-lab'
    obs = ITERATION + ':report'
    with Store(home) as store:
        try:
            retained = store.read(TASK, obs)['values']['report']
        except NotFound:
            pass
        else:
            if store.read_artifact(TASK, retained['artifact_id'])['sha256'] != retained['sha256']:
                raise ValueError('Published report digest mismatch')
            return retained | dict(home=str(home), task_id=TASK, observation_id=obs)
        artifact_ids = []

        def put(identifier, raw, media='application/json'):
            record = store.put_artifact(TASK, identifier, raw, media, None)
            artifact_ids.append(identifier)
            return {key: record[key] for key in ('artifact_id', 'sha256')}

        def retain(name, raw):
            return dict(put(f'{prefix}/{name}.json', raw), value=json.loads(raw))

        prior = [source[key] for key in ('source_diff', 'predecessor_diff', 'static_verification', 'compiled_regression_and_syntax')]
        prior += [{ 'artifact_id': product[f'{key}_artifact_id'], 'sha256': product[f'{key}_sha256']} for key in ('receipt', 'record')]
        for row in prior:
            if store.read_artifact(TASK, row['artifact_id'])['sha256'] != row['sha256']:
                raise ValueError('Source or build receipt digest mismatch')
        source_plan = store.read(TASK, 'spark-c3-direct-seed-02b:plan-v2')['values']
        prior_plan = store.read(TASK, 'spark-c3-direct-seed-02b:plan')['values']
        incoming = dict(prior_plan['history'], **source_plan['history'])
        for alias, info in incoming.items():
            if store.read_artifact(TASK, alias)['sha256'] != info['sha256']:
                raise ValueError(f'Incoming evidence changed: {alias}')
        frozen = put(f'{prefix}/launch-plan.json', raw_plan)
        retained = {name: retain(name, raw) for name, raw in data.items()}
        model = provenance['stock']['command'][2]
        model_identity_path = Path(model).parent.parent / 'factory-intake/asset-identity.json'
        identity = retain('model-identity', safe_bytes(model_identity_path))
        contract = product['runtime_contract']
        profile_path = Path(contract['gate_on_env']['LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH'])
        profile = retain('profile', safe_bytes(profile_path))
        if profile['sha256'] != contract['profile_sha256']:
            raise ValueError('Frozen profile digest mismatch')
        sources, logs, expected = [], [], []
        for row, path in zip(rows, scopes_dir, strict=True):
            prot = safe_bytes(path / 'protocol.json')
            ordered = json.loads(prot)['ordered_requests']
            if any(Path(slot['path']).name != slot['path'] for slot in ordered):
                raise ValueError('Invalid request path in scope protocol')
            recorded = scope_inputs(path, base, put, prefix, 'C3', protocol=ordered)
            stem = f'{prefix}/scopes/{path.name}'
            recorded['protocol'] = dict(put(f'{stem}/protocol.json', prot), value=json.loads(prot))
            log = safe_bytes(path / 'stderr.log')
            logs.append(log)
            recorded['log']['gzip_b64'] = b64encode(gzip.compress(log, compresslevel=1, mtime=0)).decode('ascii')
            if row['mode'] != 'equivalent-stock':
                activation = safe_bytes(path / 'profile-activation.json')
                recorded['activation'] = dict(put(f'{stem}/profile-activation.json', activation), value=json.loads(activation))
            sources.append(recorded)
            expected.append(expected_launch(row, provenance['stock'], product, retained['products']['sha256'], profile['sha256']))
        categories = classify_sources(sources, provenance['expert_extents'], logs)
        classes = retain('source-page-classes', json_bytes(categories))
        # Keep every raw draw in Store. The native timing calculation checks
        # aggregate residency and links the separately classified raw draws.
        for scope in sources:
            remove_sample_details(scope)
        evidence = dict(mode=MODE, expected=expected, scopes=sources, model_identity=identity, profile=profile,
                        regions=retained['regions'], prompts=retained['prompts'], expert_classes=classes)
        packet = json_bytes(evidence)
        host = Host(home / 'analysis-ccv2')
        release = host.seal(repo / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        key = f'{prefix}:{release}:{digest(packet)}'
        analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key+':analyze', grants=['process.exec'])
        analysis = analyzed.get('outputs', {}).get('analysis')
        if analysis is None:
            failure = json_bytes(analyzed)
            put(f'{prefix}/failed-{digest(failure)[:12]}.json', failure)
            raise ValueError(f"Native direct-seed analysis refused the evidence: {analyzed.get('diagnostics')}")
        verified = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis},
                             key=key+':verify', grants=['process.exec'])
        if verified.get('outputs', {}).get('verification', {}).get('done') is not True:
            raise ValueError('Direct-seed native analysis does not reproduce exactly')
        lab_inputs = list(artifact_ids)
        lab = put(f'{prefix}/lab.json', json_bytes(dict(schema='spark-position-lab/1', mode=MODE, inputs=lab_inputs,
                  plan=frozen, scopes=analysis['scopes'])))
        outputs = [put(f'{prefix}/{name}.json', bytes_) for name, bytes_ in (
            ('analysis-input', packet), ('analysis', json_bytes(analysis)), ('analyze-receipt', json_bytes(analyzed)),
            ('verify-receipt', json_bytes(verified)), ('release-manifest', (host.store/'releases'/release/'manifest.json').read_bytes()))]
        summary, document = render(analysis, categories)
        report = put(f'{prefix}/report.md', document, 'text/markdown') | dict(summary=summary, status='same-budget diagnostic')
        next_input = put(f'{prefix}/next-plan-input.json', json_bytes(plan_input(report, analysis, categories)))
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=ITERATION,
            predecessor_report_ids=[dict(artifact_id=alias, sha256=ref['sha256']) for alias, ref in incoming.items()
                                    if alias.endswith('.md')],
            plan=source_plan['plan'] | dict(incoming_report_ids=list(incoming)),
            do=dict(source_commit=source['source_commit'], diff_artifact_id=source['source_diff']['artifact_id'],
                    verification_receipt_ids=[source['static_verification']['artifact_id']],
                    build_receipt_ids=[product[f'{key}_artifact_id'] for key in ('receipt', 'record')]),
            lab=dict(status=report['status'], result_artifact_ids=lab_inputs, lab_artifact_id=lab['artifact_id']),
            analysis=dict(ccs=[dict(id=CAPSULE, version=host.describe(release)['version'], release=release)],
                          output_artifact_ids=[item['artifact_id'] for item in outputs] + [classes['artifact_id']]),
            report=report, next_plan=dict(decision_id=None, input=next_input))
        append_once(store, TASK, dict(obs_id=obs, kind='factory_iteration_report', values=envelope,
            source_artifacts=list(dict.fromkeys([*artifact_ids, *incoming, *[item['artifact_id'] for item in prior]]))))
        destination = base / 'OPS/iterations' / ITERATION / '30g-lab'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'report.md').write_bytes(document)
        (destination / 'analysis.json').write_bytes(json_bytes(analysis))
        (destination / 'iteration.json').write_bytes(json_bytes(envelope))
        return report | dict(home=str(home), task_id=TASK, observation_id=obs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--plan-sha256', required=True)
    args = parser.parse_args()
    plan = args.plan or args.base / 'OPS/p3/cache-direct-seed-30g-launch-plan.json'
    print(json.dumps(publish(args.base.resolve(), plan.resolve(strict=True), args.plan_sha256), indent=2))


if __name__ == '__main__':
    main()
