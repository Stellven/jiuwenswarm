#!/usr/bin/env python3
"""Publish the completed C2 layer-27 functional lab without launching workloads."""
import argparse
from base64 import b64encode
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest, safe_bytes
from report_early_bracket import BUILDER_IDS, CAPSULE, STOCK, content
from report_p1 import json_bytes

ITERATION = 'spark-c2-layer27-functional'
ROLES = ('equivalent-stock', 'off', 'on')
CAPABILITY = 'weight_placement_planner'
PROMPTS = (512, 2048)


def render(analysis, release, refs):
    comparisons = analysis['comparison']
    on = comparisons['on']
    named = on['readback']['selected']
    count = len(on['readback']['other_expert_tensors'])
    parity = all(analysis['parity'].values())
    output = 'both greedy output pairs matched' if parity else 'at least one greedy output pair differed'
    summary = f'Exactly three layer-27 expert tensors moved to CUDA0, the other {count} stayed on CPU, and {output} across all three launch modes.'
    lines = [
        '# C2 held-out layer-27 placement functional lab', '', summary, '',
        '| Selected tensor | Actual buffer | Payload bytes |', '|---|---|---:|',
        *[f"| `{r['name']}` | {r['actual']} | {r['bytes']:,} |" for r in named],
        '', f"The selected payload totals {on['readback']['cuda_payload_bytes']:,} bytes. "
        'The instrumented gate-enabled launch provided per-tensor readback. Both controls used the equivalent '
        'explicit placement allowlist and logged no component markers.', '',
        '| Scope | CUDA0 model buffers | Launch to ready | Peak cgroup memory |', '|---|---:|---:|---:|',
    ]
    for mode, row in comparisons.items():
        lines.append(f"| {mode} | {row['cuda0_model_mib']:.2f} MiB | {row['load_s']:.2f} s | "
                     f"{row['peak_memory_bytes']/1024**3:.2f} GiB |")
    lines += [
        '', f"Gate-on CUDA0 allocation differed from equivalent stock by {on['cuda0_delta_vs_equivalent-stock_mib']:+.2f} MiB "
        f"and from gate-off by {on['cuda0_delta_vs_off_mib']:+.2f} MiB at log precision. "
        'These are equivalent-policy comparisons.', '',
        '| Scope | Prompt tokens | Client TTFT | Server prompt | Server decode | Decode tok/s |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for mode, row in comparisons.items():
        for sample in row['requests']:
            lines.append(f"| {mode} | {sample['prompt_tokens']} | {sample['ttft_s']:.2f} s | "
                         f"{sample['prompt_ms']/1000:.2f} s | {sample['predicted_ms']/1000:.2f} s | {sample['decode_tps']:.2f} |")
    lines.append('')
    for enabled, unset in zip(on['requests'], comparisons['off']['requests']):
        prompt_delta = (enabled['prompt_ms'] - unset['prompt_ms']) / 1000
        decode_delta = (enabled['predicted_ms'] - unset['predicted_ms']) / 1000
        lines.append(f"- At {enabled['prompt_tokens']} tokens, gate-on minus gate-off was "
                     f"{prompt_delta:+.2f} s in server prompt processing and {decode_delta:+.2f} s in server decode.")
    lines += ['', 'Each scope issued one discarded request per size, with zero cached prompt tokens and 32 greedy generated tokens. '
              'These phases were collected during the functional window, which overlapped other work. '
              'The timings are descriptive and cannot isolate a performance effect.', '']
    for i, size in enumerate(PROMPTS):
        prefix = f'- {size} prompt tokens'
        if analysis['parity'][str(size)]:
            row = on['requests'][i]
            lines.append(f"{prefix} matched across all modes. Content SHA256 `{row['output_sha256']}` and reasoning SHA256 `{row['reasoning_sha256']}`.")
        else:
            lines.append(f'{prefix} diverged across the retained outputs.')
    lines += ['', 'Compare the equivalent policy with matched quiet stock endpoints first. '
              'Use a separately labeled strict-A comparison to quantify the placement policy itself. '
              'Retain the layer-27 readback as an activation check for the next placement decision.', '',
              f'Native analysis and deterministic verification used sealed release `{release}`. '
              f"The retained lab and analysis are `{refs['lab']}` and `{refs['analysis']}`.", '']
    return summary, '\n'.join(lines).encode()


def publish(base):
    repo = Path(__file__).resolve().parents[2]
    ops = base / 'OPS/p3'
    source_path = ops / 'spark-source-products.json'
    products_path = ops / 'native-star-build-products.json'
    controls_path = ops / 'placement-v1-matched-controls.json'
    source = content(source_path)[CAPABILITY]
    product = next(row for row in content(products_path)['products'] if row['capsule'] == CAPABILITY)
    home, task = Path(source['home']), source['task']
    if (product['source_commit'], product['task_id'], product['home'], product['state']) != (
            source['source_commit'], task, str(home), 'succeeded'):
        raise ValueError('C2 source and compiled inventory disagree')
    controls = content(controls_path)
    if controls['source_commit'] != source['source_commit']:
        raise ValueError('Held-out controls target another source product')
    policy = controls['heldout_layer27_policy']
    plan = Path(policy['gate_on_argv'][-1])
    if digest(safe_bytes(plan)) != policy['plan_sha256']:
        raise ValueError('Held-out placement plan digest differs from the published policy')
    first_path = base / 'OPS/runs/a-first-load-retry/start.json'
    first = content(first_path)
    model_path = Path(first['command'][2])
    identity = model_path.parent.parent / 'factory-intake/asset-identity.json'
    if content(identity)['files'][0]['path'] != str(model_path):
        raise ValueError('C2 control model is not the first shard of the admitted model')
    inventory = digest(safe_bytes(products_path))

    with Store(home) as store:
        try:
            prior = store.read(task, ITERATION + ':report')['values']['report']
            return dict(prior, home=str(home), task_id=task)
        except NotFound:
            pass

        def put(relative, data, media='application/json'):
            record = store.put_artifact(task, f'{ITERATION}/{relative}', data, media, None)
            return {k: record[k] for k in ('artifact_id', 'sha256')}

        def attach(path, relative=None, form='json'):
            raw = safe_bytes(path)
            media = {'json': 'application/json', 'text': 'text/plain', 'sse': 'text/event-stream'}[form]
            ref = put(relative or path.name, raw, media)
            return dict(ref, value=json.loads(raw)) if form == 'json' else ref

        roots = [attach(path) for path in (source_path, products_path, controls_path, plan, first_path, identity)]
        prompt = attach(repo / 'ops/spark/prompts/MANIFEST.json')
        roots.append(prompt)
        refs = [r['artifact_id'] for r in roots]
        scopes, expected = {}, {}
        for role in ROLES:
            stock, enabled = role == 'equivalent-stock', role == 'on'
            path = base / f'OPS/runs/c2-layer27-{role}-functional-01'

            def scoped(name, form='json'):
                ref = attach(path / name, f'scopes/{role}/{name}', form)
                refs.append(ref['artifact_id'])
                return ref

            executable = first['command'][0] if stock else product['executable']['path']
            baseline_flags = ['-m', str(model_path), '--host', '127.0.0.1', '--port', '8082', *policy['common_argv']]
            expected[role] = dict(
                label=f'C2-{role}-functional', source_commit=STOCK if stock else source['source_commit'],
                products_manifest_sha256=None if stock else inventory, library_path=str(Path(executable).parent),
                binary_sha256=first['binary_sha256'] if stock else product['executable']['sha256'],
                command=[executable, *baseline_flags, *policy['gate_on_argv' if enabled else 'equivalent_stock_and_candidate_off_argv']],
                gates=policy['gate_on_env'] if enabled else {},
            )
            scope = {key: scoped(name) for key, name in dict(
                start='start.json', stop='result.json', scope='scope.json', load='load-ready.json', probe='probe.json').items()}
            if scope['load']['value']['native_build_receipt'] != (None if stock else product['receipt_artifact_id']):
                raise ValueError('Launch receipt does not match the compiled C2 build')
            scope['log'] = dict(scoped('stderr.log', 'text'),
                                raw_b64=b64encode(safe_bytes(path / 'stderr.log')).decode('ascii'))
            scope['requests'] = [
                {key: scoped(f'rep-0-{size}/{name}', form) for key, name, form in (
                    ('request', 'request.json', 'json'), ('result', 'result.json', 'json'),
                    ('resources', 'resource-windows.json', 'json'), ('response', 'response.sse', 'sse'),
                    ('output', 'output.txt', 'text'), ('reasoning', 'reasoning.txt', 'text'),
                )}
                for size in PROMPTS
            ]
            scopes[role] = scope
        for identifier, expected_hash in [
            (product['receipt_artifact_id'], product['receipt_sha256']),
            (product['record_artifact_id'], product['record_sha256']),
            (source['diff_artifact_id'], source['diff_sha256']),
        ]:
            if store.read_artifact(task, identifier)['sha256'] != expected_hash:
                raise ValueError(f'Source or build digest differs for {identifier}')
        store.read_artifact(task, source['verification_receipt_id'])
        evidence = dict(mode='c2-placement-functional', expected=expected, scopes=scopes,
                        controls=dict(roots[2], value=policy), prompts=prompt)
        input_bytes = json_bytes(evidence)
        host = Host(home / 'analysis-ccv2')
        release = host.seal(repo / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        key = f'{ITERATION}:{release}:{digest(input_bytes)}'
        analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key+':analyze', grants=['process.exec'])
        analysis = analyzed.get('outputs', {}).get('analysis')
        if not analysis:
            failed = json_bytes(analyzed)
            put(f'failed-analysis-receipt-{digest(failed)[:12]}.json', failed)
            raise ValueError(f"C2 placement analysis admission failed: {analyzed.get('diagnostics')}")
        checked = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis},
                            key=key+':verify', grants=['process.exec'])
        if checked.get('outputs', {}).get('verification', {}).get('done') is not True:
            raise ValueError('Recomputing placement analysis did not reproduce the result')
        input_ref = put('analysis-input.json', input_bytes)
        outputs = [
            put('analysis.json', json_bytes(analysis)),
            put('analyze-receipt.json', json_bytes(analyzed)),
            put('verify-receipt.json', json_bytes(checked)),
            put('release-manifest.json', (host.store / 'releases' / release / 'manifest.json').read_bytes()),
        ]
        lab = put('lab.json', json_bytes(dict(schema='spark-placement-functional-lab/1', **analysis)))
        summary, rendered = render(analysis, release, {'lab': lab['artifact_id'], 'analysis': outputs[0]['artifact_id']})
        report = put('report.md', rendered, 'text/markdown')
        decision_id = source['factory_initial_plan_decision_id']
        decision = store.read(task, decision_id)
        plan = dict(decision_id=decision_id, incoming_report_ids=[
            ident for ident in decision['evidence_ids'] if ident.startswith('incoming-') and '.md' in ident],
            builder_ccs=[dict(id=BUILDER_IDS['C2'], version=source['source_capsule_version'],
                              release=source['source_capsule_release'])], rationale=decision['hypothesis'])
        if summary_value := decision.get('action', {}).get('summary'):
            plan['summary'] = summary_value
        build_ids = [product['receipt_artifact_id'], product['record_artifact_id']]
        lab_ids = [lab['artifact_id'], input_ref['artifact_id'], *refs]
        output_ids = [r['artifact_id'] for r in outputs]
        do = dict(source_commit=source['source_commit'], diff_artifact_id=source['diff_artifact_id'],
                  verification_receipt_ids=[source['verification_receipt_id']], build_receipt_ids=build_ids)
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=ITERATION, predecessor_report_ids=[], plan=plan, do=do,
                        lab=dict(result_artifact_ids=lab_ids, status='stock-equivalent held-out placement verified'),
                        analysis=dict(ccs=[dict(id=CAPSULE, version=host.describe(release)['version'], release=release)],
                                      output_artifact_ids=output_ids),
                        report=dict(report, summary=summary, status='functional placement'), next_plan=dict(decision_id=None))
        append_once(store, task, dict(obs_id=ITERATION+':report', kind='factory_iteration_report', values=envelope,
            source_artifacts=[report['artifact_id'], *output_ids, *lab_ids, do['diff_artifact_id'],
                              *do['verification_receipt_ids'], *build_ids]))
        out = base / 'OPS/iterations' / ITERATION
        out.mkdir(parents=True, exist_ok=True)
        (out / 'report.md').write_bytes(rendered)
        (out / 'analysis.json').write_bytes(json_bytes(analysis))
        (out / 'iteration.json').write_bytes(json_bytes(envelope))
        return dict(report, home=str(home), task_id=task, iteration_observation_id=ITERATION+':report')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    print(json.dumps(publish(parser.parse_args().base.resolve()), indent=2))
