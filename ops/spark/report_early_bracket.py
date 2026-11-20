#!/usr/bin/env python3
"""Verify and publish a completed early Spark bracket; this script launches no benchmark."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, safe_bytes
from probe_candidate import ARMS, PORT
from report_p1 import json_bytes

CAPSULE = 'factory.spark_gap_analysis'
STOCK = '9048bad8d6e3a0f9f1726e238e451181c7e02613'
BUILDER_IDS = {
    'C1': 'observability.build_runtime_event_recorder', 'C2': 'placement.build_weight_placement_planner',
    'C3': 'engine.build_expert_weight_cache', 'C4': 'routing.build_expert_demand_predictor',
    'C5': 'engine.build_batch_layout_mapper',
}
ON_ENV = {'C1': {}, 'C2': {'LLAMA_PLACEMENT_PLAN': '1'},
          'C3': {'LLAMA_EXPERT_CACHE': '1', 'LLAMA_EXPERT_CACHE_MIB': '64'},
          'C4': {'LLAMA_EXPERT_PREDICT': '1'}, 'C5': {'LLAMA_BATCH_LAYOUT': '1'}}

EFFECTIVE_SETTINGS = {
    **{key: rf'llama_context:\s*{key}\s*=\s*(\d+)' for key in ('n_ctx', 'n_ctx_seq', 'n_batch', 'n_ubatch')},
    'n_slots': r'load_model: initializing, n_slots\s*=\s*(\d+)',
    'n_threads': r'system_info: n_threads\s*=\s*(\d+)',
    'n_threads_batch': r'n_threads_batch\s*=\s*(\d+)',
}


def content(path):
    return json.loads(safe_bytes(path))


def expected_profiles(cc, first, product, policy, placement, inventory_sha):
    base_args = first['command'][1:]
    strict = list(base_args)
    matched, enabled = list(base_args), list(base_args)
    functional_off = None
    stock_mode = 'equivalent-stock' if policy == 'heldout-layer27-equivalent' else 'stock'
    if cc == 'C2':
        key = 'cpu_identity_smoke' if policy == 'cpu-identity' else 'heldout_layer27_policy'
        selected = placement[key]
        common = list(selected['common_argv'])
        index = common.index('-lv')
        del common[index:index + 2]
        same = 'stock_and_gate_unset_argv' if key == 'cpu_identity_smoke' else (
            'equivalent_stock_and_candidate_off_argv' if stock_mode == 'equivalent-stock' else 'all_cpu_stock_argv')
        base_flags = ['-m', first['command'][2], '--host', '127.0.0.1', '--port', str(PORT), *common]
        matched = base_flags + selected[same]
        enabled = base_flags + selected['gate_on_argv']
        off_key = 'stock_and_gate_unset_argv' if key == 'cpu_identity_smoke' else 'equivalent_stock_and_candidate_off_argv'
        functional_off = base_flags + selected[off_key]
    if cc in ('C4', 'C5'):
        additions = ['-np', '1', '-c', '4096']
        if cc == 'C5':
            additions += ['--ctx-checkpoints', '0', '-b', '2047', '-ub', '512']
        matched += additions
        enabled += additions

    def arm(flags, mode, on=False):
        binary = product['executable']['path'] if on else first['command'][0]
        digest = product['executable']['sha256'] if on else first['binary_sha256']
        label = {'strict-stock': f'A-{cc}-strict-early', 'stock': f'A-matched-{cc}-early'}.get(mode, f'{cc}-{mode}-early')
        return dict(command=[binary, *flags], binary_sha256=digest, library_path=str(Path(binary).parent),
                    source_commit=product['source_commit'] if on else STOCK, gates=ON_ENV[cc] if on else {}, label=label,
                    products_manifest_sha256=inventory_sha)

    label = policy if cc == 'C2' else 'nested-default-verbosity' if cc == 'C5' else 'candidate-matched-default-verbosity'
    return {'label': label, 'stock_mode': stock_mode, 'nested_strict': cc == 'C5', stock_mode: arm(matched, stock_mode),
            'on': arm(enabled, 'on', True), 'strict-stock': arm(strict, 'strict-stock'),
            'functional_off_argv': functional_off or enabled}


def scope_inputs(path, base, put, tag, cc):
    prefix = f'{tag}/scopes/{path.name}'

    def read(relative, source=None, media='application/json'):
        original = source or path / relative
        raw = safe_bytes(original)
        entry = put(f'{prefix}/{relative}', raw, media)
        if media == 'application/json':
            entry['value'] = json.loads(raw)
        return entry

    layout = dict(start='start.json', stop='result.json', scope='scope.json', load='load-ready.json', probe='probe.json')
    scope = {key: read(name) for key, name in layout.items()}
    preflight = base / 'OPS/p3/early-preflights'
    quiet = preflight / (path.name + '-quiet.json')
    scope['quiet'] = dict(read('quiet-prelaunch.json', quiet),
                          mtime_utc=datetime.fromtimestamp(quiet.stat().st_mtime, timezone.utc).isoformat())
    scope['conditioning'] = read('source-conditioning.json', preflight / (path.name + '-source.json'))
    log_path = path / 'stderr.log'
    log_text = safe_bytes(log_path).decode('utf-8', errors='replace')
    scope['log'] = read('stderr.log', media='text/plain')
    scope['log']['effective_settings'] = {key: int(match.group(1)) for key, pattern in EFFECTIVE_SETTINGS.items()
                                           if (match := re.search(pattern, log_text))}
    marker = ARMS[cc] + ': '
    instruments = [line.split(marker, 1)[-1].strip() for line in log_text.splitlines() if marker in line]
    scope['log']['markers'] = {key: [line for line in instruments if line.startswith(key)]
                              for key in ('active', 'inactive', 'stats', 'layout', 'tensor', 'assign')}
    event_path = path / 'events.jsonl'
    if cc == 'C1' and scope['probe']['value']['mode'] == 'on' and event_path.is_file():
        with event_path.open('rb') as events:
            events.seek(max(0, event_path.stat().st_size - 8192))
            summary = json.loads(events.read().splitlines()[-1])
        receipt = put(f'{prefix}/recorder-summary.json', json_bytes(summary))
        raw_events = put(f'{prefix}/events.jsonl', event_path, 'application/jsonl')
        scope['recorder'] = dict(raw=raw_events, summary=dict(receipt, value=summary))
    scope['requests'] = []
    for repeat, size in ((0, 512), (0, 2048), (1, 512), (1, 2048)):
        name = f'rep-{repeat}-{size}'
        files = {'result': f'{name}/result.json', 'request': f'{name}/request.json',
                 'request_resources': f'{name}/resource-windows.json', 'before': f'{name}-before.json',
                 'after': f'{name}-after.json'}
        row = {k: read(v) for k, v in files.items()}
        row['output'] = read(f'{name}/output.txt', media='text/plain')
        row['reasoning'] = read(f'{name}/reasoning.txt', media='text/plain')
        row['response'] = read(f'{name}/response.sse', media='text/event-stream')
        if repeat:
            row['residency'] = read(f'{name}-residency.json')
        scope['requests'].append(row)
    return scope


def bracket_summary(data):
    if not data['candidate_activation']:
        return 'The timing bracket did not establish that the candidate mechanism ran.'
    if not all(row['attribution_eligible'] for row in data['measurements']):
        return 'The candidate and control produced different greedy outputs in at least one comparison, which limits what the timings can establish.'
    outcomes = [
        f"time to first token at {row['prompt_tokens']} prompt tokens was {row['interpretation']}"
        for row in data['measurements']
    ]
    return 'In this single timing bracket, ' + ' and '.join(outcomes) + '.'


def render_report(data, analysis, source, release):
    lines = [f"# {data['cc']} early timing bracket", '', bracket_summary(data), '',
             f"Launch profile `{data['profile']}`. "
             f"Source `{source['source_commit']}`. Analysis `{analysis['artifact_id']}` SHA256 `{analysis['sha256']}`.", '',
             '| Prompt | Stock before TTFT | Candidate TTFT | Stock after TTFT | Stock drift | Decode tok/s, stock / candidate / stock |',
             '|---|---:|---:|---:|---:|---:|']
    for row in data['measurements']:
        lines.append(f"| {row['prompt_tokens']} | {row['stock_before_s']:.3f} s | {row['candidate_s']:.3f} s | "
                     f"{row['stock_after_s']:.3f} s | {row['stock_drift_s']:+.3f} s | "
                     f"{row['stock_before_decode_tps']:.2f} / {row['candidate_decode_tps']:.2f} / {row['stock_after_decode_tps']:.2f} |")
    lines.append('')
    for row in data['measurements']:
        lo, hi = row['observed_inverse_ttft_range']
        lines.append(f"- {row['prompt_tokens']} tokens showed {row['interpretation']}. The descriptive stock-to-candidate ratio "
                     f"spanned {lo:.3f}× to {hi:.3f}× across the endpoints.")
        if matched := row.get('settings_comparison'):
            lines.append(f"- {row['prompt_tokens']} tokens under strict A took {matched['strict_before_s']:.3f} s and "
                         f"{matched['strict_after_s']:.3f} s, with decode {matched['strict_before_decode_tps']:.2f} and "
                         f"{matched['strict_after_decode_tps']:.2f} tok/s. The two settings-only A-matched endpoints were "
                         f"{matched['matched_before_vs_strict']} and {matched['matched_after_vs_strict']}, respectively.")
            if not matched['cross_settings_greedy_parity']:
                lines.append(f"  Greedy hashes differ across settings at {row['prompt_tokens']} tokens. Decode settings comparisons are descriptive.")
            if not matched['strict_greedy_parity']:
                lines.append(f"  The strict-A endpoints also diverged for this prompt.")
    if not data['candidate_activation']:
        lines += ['', 'The retained candidate markers did not establish component activation.']
    if data.get('functional_greedy_parity') is False:
        lines += ['', 'The bound functional controls diverged with the gate enabled. The timing remains descriptive.']
    if data['profile'] == 'heldout-layer27-all-cpu':
        lines += ['', 'This comparison includes the selected expert-tensor placement policy.']
    if data['profile'] == 'heldout-layer27-equivalent':
        lines += ['', 'The stock control uses the equivalent placement allowlist.']
    lines += ['', '## Limits and next decision', '', *[f'- {text}' for text in data['limitations']], '',
              'Use the endpoint drift, parity checks and activity counters to select the next matched test. '
              'Repeat under the quiet mirrored-launch protocol before a performance claim.', '',
              f"The native analysis and verifier used sealed release `{release}`. The iteration record links the factory source plan, verified diff, "
              'native build receipts, model and prompt identities, scope records, activation markers and raw request resource windows.', '']
    return '\n'.join(lines).encode()


def functional_controls(cc, product, expected, scopes, put, iteration):
    evidence, output_pairs = [], []
    for mode, path in zip(('off', 'on'), scopes):
        prefix = f'{iteration}/functional/{mode}'
        start, stop, probe, load = (content(path / name) for name in ('start.json', 'result.json', 'probe.json', 'load-ready.json'))
        if (probe['cc'] != cc or probe['mode'] != mode or probe['window'] != 'functional' or
                start['binary_sha256'] != product['executable']['sha256'] or stop['binary_sha256'] != start['binary_sha256'] or
                load['source_commit'] != product['source_commit'] or stop['returncode'] or stop['reason'] or
                stop['scope_verified'] is not True or load.get('products_manifest_sha256') != expected['on']['products_manifest_sha256'] or
                any(int(stop['memory_events'].get(key, 0)) for key in ('oom', 'oom_kill', 'oom_group_kill'))):
            raise ValueError(f'Functional {mode} scope differs from current built product or did not complete safely')
        argv = list(start['command'][1:])
        if '-lv' in argv and argv[argv.index('-lv') + 1] == '4':
            idx = argv.index('-lv')
            del argv[idx:idx + 2]
        expected_argv = expected['functional_off_argv'] if mode == 'off' else expected['on']['command'][1:]
        env = start['launch_environment']
        gates = {k: v for k, v in env.items() if k.startswith('LLAMA_')}
        on_gates = {} if mode == 'off' else dict(expected['on']['gates'])
        if mode == 'on' and cc == 'C1':
            on_gates['LLAMA_EVENT_REC'] = str(path / 'events.jsonl')
        if argv != expected_argv or gates != on_gates or env.get('LD_LIBRARY_PATH') != expected['on']['library_path']:
            raise ValueError('Functional baseline and treatment do not use the declared engine settings')
        files = ['start.json', 'result.json', 'probe.json', 'load-ready.json', 'scope.json', 'stderr.log']
        for size in (512, 2048):
            files.extend([f'rep-0-{size}/result.json', f'rep-0-{size}/request.json', f'rep-0-{size}/output.txt', f'rep-0-{size}/reasoning.txt'])
        for name in files:
            orig = path / name
            evidence.append(put(f'{prefix}/{name}', safe_bytes(orig), 'application/json' if orig.suffix == '.json' else 'text/plain'))
        output_pairs.append(probe['greedy_hashes'])
        log = safe_bytes(path / 'stderr.log').decode('utf-8', errors='replace')
        family = ARMS[cc] + ':'
        if mode == 'off' and family in log:
            raise ValueError('Functional gate-off marker silence failed')
        if mode == 'on' and cc == 'C5' and not re.search(r'batch_layout_mapper: stats decisions=[1-9]\d*\b', log):
            raise ValueError('C5 functional probe did not demonstrate a split decision')
    summary = {'greedy_parity_passed': output_pairs[0] == output_pairs[1], 'raw_inputs': list(evidence)}
    receipt = put(f'{iteration}/functional/controls.json', json_bytes(summary))
    evidence.append(receipt)
    return evidence, dict(receipt, value=summary)


def source_product(path, cc):
    data = content(path)
    if ARMS[cc] in data:
        return data[ARMS[cc]]
    if cc != 'C5' or not data.get('planner_report_reads'):
        raise ValueError('Source manifest is missing the commissioned component')
    release = data['native_verifier_release']
    manifest = Path(data['home']) / 'ccstore/releases' / release / 'manifest.json'
    declaration = content(manifest)['declaration']
    if declaration['id'] != BUILDER_IDS[cc]:
        raise ValueError('Revised mapper verifier capsule does not match the component')
    return dict(data, task=data['task_id'], verification_receipt_id=data['native_verifier_artifact_id'],
                factory_initial_plan_decision_id=data['planner_decision'],
                source_capsule_release=release, source_capsule_version=declaration['version'])


def publish(base, cc, policy, directories, iteration, product_identity, source_identity, placement_file, functional):
    repo = Path(__file__).resolve().parents[2]
    ops = base / 'OPS/p3'
    meta = source_product(source_identity, cc)
    inventory = content(product_identity)
    if inventory['schema'] != 'spark-native-star-build-products/1':
        raise ValueError('Unrecognized candidate build inventory')
    products = inventory['products']
    product = next(row for row in products if row['capsule'] == ARMS[cc])
    if (product['source_commit'] != meta['source_commit'] or product['state'] != 'succeeded' or
            product['task_id'] != meta['task'] or product['home'] != meta['home']):
        raise ValueError('Compiled candidate is not the verified source product in this task')
    home, task = Path(meta['home']), meta['task']
    iteration = iteration or f'spark-{cc.lower()}-early-{policy or "matched"}-{meta["source_commit"][:12]}'
    if not iteration.replace('-', '').isalnum():
        raise ValueError('Iteration ID must be alphanumeric with optional hyphens')
    first_path = base / 'OPS/runs/a-first-load-retry/start.json'
    first = content(first_path)
    stock_path = Path(first['command'][2])
    model_identity = stock_path.parent.parent / 'factory-intake/asset-identity.json'
    placement = content(placement_file) if cc == 'C2' else {}
    if placement and placement['source_commit'] != product['source_commit']:
        raise ValueError('Placement controls bind a different source revision')
    expected = expected_profiles(cc, first, product, policy, placement, hashlib.sha256(safe_bytes(product_identity)).hexdigest())
    with Store(home) as store:
        try:
            existing = store.read(task, iteration + ':report')['values']
        except NotFound:
            existing = None
        if existing:
            previous = json.loads(store.artifact_bytes(task, f'{iteration}/analysis-input.json'))
            old_paths = [scope['start']['value']['result_path'] for scope in previous['scopes']]
            if (existing['do']['source_commit'] != meta['source_commit'] or old_paths != [str(path) for path in directories]
                    or previous['expected'] != expected):
                raise ValueError('This iteration ID already identifies another built product, profile or set of scopes')
            record = store.read_artifact(task, existing['report']['artifact_id'])
            if record['sha256'] != existing['report']['sha256']:
                raise ValueError('Existing report digest differs from its iteration record')
            return dict(home=str(home), task_id=task, artifact_id=record['artifact_id'], sha256=record['sha256'])

        def put(identifier, raw, media='application/json'):
            item = store.put_artifact(task, identifier, raw, media, None)
            return {k: item[k] for k in ('artifact_id', 'sha256')}

        def attach(path):
            return put(f'{iteration}/{path.name}', safe_bytes(path))

        prompt_path = repo / 'ops/spark/prompts/MANIFEST.json'
        prompt_manifest = dict(attach(prompt_path), value=content(prompt_path))
        identity = dict(attach(model_identity), value=content(model_identity))
        references = [attach(product_identity), attach(first_path), attach(source_identity),
                      attach(base / 'OPS/p4/source-regions.json'), identity, prompt_manifest]
        if placement:
            references.append(attach(placement_file))
            flag = expected['on']['command']
            plan_path = Path(flag[flag.index('--placement-plan') + 1])
            plan = attach(plan_path)
            key = 'cpu_identity_smoke' if policy == 'cpu-identity' else 'heldout_layer27_policy'
            if plan['sha256'] != placement[key]['plan_sha256']:
                raise ValueError('Actual placement plan digest differs from the requested profile')
            references.append(plan)
        functional_record = None
        if functional:
            functional_refs, functional_record = functional_controls(cc, product, expected, functional, put, iteration)
            references.extend(functional_refs)
        scopes = [scope_inputs(path, base, put, iteration, cc) for path in directories]
        profile = put(f'{iteration}/matched-profile.json', json_bytes(dict(launches=expected, sources=references)))
        evidence = dict(mode='early-bracket', cc=cc, expected=expected, model_identity=identity,
                        prompt_manifest=prompt_manifest, profile_ref=profile, scopes=scopes, functional_controls=functional_record)
        input_ref = put(f'{iteration}/analysis-input.json', json_bytes(evidence))
        for identifier, digest in [(product['receipt_artifact_id'], product['receipt_sha256']),
                                   (product['record_artifact_id'], product['record_sha256']),
                                   (meta['diff_artifact_id'], meta['diff_sha256'])]:
            if store.read_artifact(task, identifier)['sha256'] != digest:
                raise ValueError(f'Integrity mismatch for built source artifact {identifier}')
        store.read_artifact(task, meta['verification_receipt_id'])

        host = Host(home / 'analysis-ccv2')
        release = host.seal(repo / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        release_ref = put(f'{iteration}/release-manifest.json', (host.store / 'releases' / release / 'manifest.json').read_bytes())
        key = f'{iteration}:{release}:{input_ref["sha256"]}'
        analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key+':analyze', grants=['process.exec'])
        analysis = analyzed.get('outputs', {}).get('analysis')
        if not analysis:
            failed = put(f'{iteration}/failed-analysis-receipt.json', json_bytes(analyzed))
            raise ValueError(f'Early bracket failed analysis admission. See {failed["artifact_id"]}: {analyzed.get("diagnostics")}')
        checked = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis}, key=key+':verify', grants=['process.exec'])
        if checked.get('outputs', {}).get('verification', {}).get('done') is not True:
            raise ValueError('Recomputed bracket verification did not match')
        receipts = [put(f'{iteration}/{name}-receipt.json', json_bytes(value))
                    for name, value in [('analyze', analyzed), ('verify', checked)]]
        analysis_ref = put(f'{iteration}/analysis.json', json_bytes(analysis))
        lab = put(f'{iteration}/lab.json', json_bytes(dict(schema='spark-early-bracket-lab/1', cc=cc, scopes=analysis['scopes'], profile=profile)))
        report = put(f'{iteration}/report.md', render_report(analysis, analysis_ref, meta, release), 'text/markdown')
        outputs = [analysis_ref['artifact_id'], release_ref['artifact_id'], *[r['artifact_id'] for r in receipts]]
        decision_id = meta['factory_initial_plan_decision_id']
        decision = store.read(task, decision_id)
        provenance = [ref['artifact_id'] for ref in [*references, profile, input_ref, lab]]
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=iteration, predecessor_report_ids=[],
            plan=dict(decision_id=decision_id, incoming_report_ids=[i for i in decision['evidence_ids'] if i.startswith('incoming-') and '.md' in i],
                      builder_ccs=[dict(id=BUILDER_IDS[cc], version=meta['source_capsule_version'], release=meta['source_capsule_release'])],
                      rationale=decision['hypothesis']),
            do=dict(source_commit=meta['source_commit'], diff_artifact_id=meta['diff_artifact_id'],
                    verification_receipt_ids=[meta['verification_receipt_id']],
                    build_receipt_ids=[product['receipt_artifact_id'], product['record_artifact_id']]),
            lab=dict(result_artifact_ids=provenance, status='single quiet stock/candidate timing bracket'),
            analysis=dict(ccs=[dict(id=CAPSULE, version=host.describe(release)['version'], release=release)], output_artifact_ids=outputs),
            report=dict(report, status='early descriptive timing', summary=bracket_summary(analysis)),
            next_plan=dict(decision_id=None))
        plan_summary = (decision.get('action') or {}).get('summary')
        if isinstance(plan_summary, str) and plan_summary.strip():
            envelope['plan']['summary'] = plan_summary
        artifact_ids = [*provenance, *outputs, report['artifact_id'], meta['diff_artifact_id'], meta['verification_receipt_id'],
                        product['receipt_artifact_id'], product['record_artifact_id']]
        if meta.get('planner_report_reads'):
            store.read_artifact(task, meta['planner_report_reads'])
            artifact_ids.append(meta['planner_report_reads'])
        append_once(store, task, dict(obs_id=iteration+':analysis', kind='gap_attribution',
            values=dict(capsule_id=CAPSULE, release=release, analysis=analysis), source_artifacts=artifact_ids))
        append_once(store, task, dict(obs_id=iteration+':report', kind='factory_iteration_report',
            values=envelope, source_artifacts=artifact_ids))
        out = base / 'OPS/iterations' / iteration
        out.mkdir(parents=True, exist_ok=True)
        (out / 'report.md').write_bytes(store.artifact_bytes(task, report['artifact_id']))
        (out / 'analysis.json').write_bytes(json_bytes(analysis))
        (out / 'iteration.json').write_bytes(json_bytes(envelope))
        return dict(home=str(home), task_id=task, **report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cc', choices=ARMS)
    parser.add_argument('scopes', nargs='+', type=Path, help='Ordered completed OPS/runs scopes')
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--iteration')
    parser.add_argument('--products', type=Path, help='Exact build inventory passed to probe_candidate.py')
    parser.add_argument('--source-products', type=Path, help='Exact source/diff and native verification index for the chosen builds')
    parser.add_argument('--placement-controls', type=Path, help='Exact C2 matched launch control')
    parser.add_argument('--functional-off', type=Path, help='Completed same-binary gate-off functional scope')
    parser.add_argument('--functional-on', type=Path, help='Completed same-binary gate-on functional scope')
    parser.add_argument('--placement-policy', choices=('cpu-identity', 'heldout-layer27-all-cpu', 'heldout-layer27-equivalent'))
    args = parser.parse_args()
    base = args.base.resolve()
    scopes = [path.resolve(strict=True) for path in args.scopes]
    if len(scopes) != (5 if args.cc == 'C5' else 3) or len(set(scopes)) != len(scopes) or any(p.parent != base/'OPS/runs' for p in scopes):
        parser.error('Provide exactly 3 scopes (5 for C5) in actual chronological order under OPS/runs')
    if args.cc == 'C2' and not args.placement_policy:
        parser.error('C2 requires its explicit placement comparison policy')
    if args.cc != 'C2' and args.placement_policy:
        parser.error('Only C2 accepts a placement profile selection')
    if bool(args.products) != bool(args.source_products):
        parser.error('Provide both matching build and source indexes for a revised candidate')
    if bool(args.functional_off) != bool(args.functional_on) or (args.products and not args.functional_off):
        parser.error('A revised build requires completed matched --functional-off and --functional-on scopes')
    functional = tuple(p.resolve(strict=True) for p in (args.functional_off, args.functional_on)) if args.functional_off else ()
    if any(p.parent != base/'OPS/runs' for p in functional):
        parser.error('Use functional scopes immediately under OPS/runs')
    ops = base/'OPS/p3'
    product_identity = args.products.resolve(strict=True) if args.products else ops/'native-star-build-products.json'
    source_identity = args.source_products.resolve(strict=True) if args.source_products else ops/'spark-source-products.json'
    placement_file = args.placement_controls.resolve(strict=True) if args.placement_controls else ops/'placement-v1-matched-controls.json'
    print(json.dumps(publish(base, args.cc, args.placement_policy, scopes, args.iteration,
                             product_identity, source_identity, placement_file, functional), indent=2))


if __name__ == '__main__':
    main()
