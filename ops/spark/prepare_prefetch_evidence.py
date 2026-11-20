#!/usr/bin/env python3
"""Collect authentic matched C4 functional receipts for the native readiness analyzer."""
import argparse
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import Store

from import_evidence import append_once, digest, safe_bytes
from report_p1 import json_bytes


ROOT = Path.home() / 'predemo-spark'
HOME = ROOT / 'factory-runs/star-expert_demand_predictor-decode-bank-03'
TASK = 'spark-predictor-decode-bank-do-03'
CAPSULE = 'analysis.expert_prefetch_readiness'
BUNDLE = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs/expert_prefetch_readiness'


def collect(scope, mode, products):
    scope = scope.resolve(strict=True)
    if scope.parent != ROOT / 'OPS/runs':
        raise ValueError('Use complete Spark scope directories')
    names = dict(start='start.json', stop='result.json', scope='scope.json', probe='probe.json', log='stderr.log', load='load-ready.json')
    items = {name: safe_bytes(scope / path) for name, path in names.items()}
    data = {name: json.loads(items[name]) for name in names if name != 'log'}
    probe, start, load = (data[x] for x in ('probe', 'start', 'load'))
    if (probe['cc'] != 'C4' or probe['mode'] != ('equivalent-stock' if mode == 'stock' else mode) or probe['window'] != 'functional'):
        raise ValueError('Use the actual C4 A+30 functional probe modes')
    inventory_bytes = safe_bytes(products)
    product = next(p for p in json.loads(inventory_bytes)['products'] if p['capsule'] == 'expert_demand_predictor')
    first = json.loads(safe_bytes(ROOT / 'OPS/runs/a-first-load-retry/start.json'))
    expected = first['binary_sha256'] if mode == 'stock' else product['executable']['sha256']
    if (start['binary_sha256'] != expected or load['products_manifest_sha256'] != digest(inventory_bytes) or
            load['native_build_receipt'] != (None if mode == 'stock' else product['receipt_artifact_id'])):
        raise ValueError('C4 scope differs from its exact stock or verified native product')
    for size in (512, 2048):
        rel = f'rep-0-{size}'
        for file in ('result.json', 'request.json', 'response.sse', 'output.txt', 'reasoning.txt', 'resource-windows.json'):
            items[f'{rel}/{file}'] = safe_bytes(scope / rel / file)
        result = json.loads(items[f'{rel}/result.json'])
        hashes = [result['output_sha256'], result['reasoning_sha256']]
        if (result['arm'] != start['arm'] or not result['ok'] or result['prompt_tokens'] != size or
                result['usage']['completion_tokens'] != 32 or result['timings']['cache_n'] != 0 or
                hashes != probe['greedy_hashes'][str(size)] or
                hashes != [digest(items[f'{rel}/{kind}.txt']) for kind in ('output', 'reasoning')]):
            raise ValueError('C4 request lineage or greedy output verification failed')
    files = {name: (f'c4-prefetch/raw/{scope.name}/{names.get(name, name)}@{digest(raw)}', raw) for name, raw in items.items()}
    refs = {name: dict(artifact_id=identifier, sha256=digest(raw)) for name, (identifier, raw) in files.items()}
    return dict(**data, stderr=items['log'].decode(), references=refs), list(files.values())


def publish(packet, input_path, raw_files):
    host = Host(HOME / 'analysis-ccv2')
    release = host.seal(BUNDLE)
    evidence = host.put_artifact(input_path)
    key = f'c4-prefetch:{release}:{evidence["sha256"]}'
    analyzed = host.call(release, 'analyze', {'evidence': evidence}, key=key + ':analyze', grants=['process.exec'])
    report = analyzed.get('outputs', {}).get('report')
    if not report:
        raise ValueError(f'Native C4 analyzer refused the evidence: {analyzed.get("diagnostics")}')
    verified = host.call(release, 'verify', {'evidence': evidence, 'report': report}, key=key + ':verify', grants=['process.exec'])
    if verified.get('outputs', {}).get('verification', {}).get('done') is not True:
        raise ValueError('Native C4 analysis failed deterministic verification')
    prefix = 'c4-prefetch/' + evidence['sha256'][:12]
    with Store(HOME) as store:
        refs = [store.put_artifact(TASK, identifier, raw, 'application/octet-stream', None)['artifact_id']
                for identifier, raw in raw_files]
        for name, data in (('evidence', packet), ('report', report), ('analyze-receipt', analyzed), ('verify-receipt', verified)):
            row = store.put_artifact(TASK, f'{prefix}/{name}.json', json_bytes(data), 'application/json', None)
            refs.append(row['artifact_id'])
        output = store.read_artifact(TASK, f'{prefix}/report.json')
        ref = {k: output[k] for k in ('artifact_id', 'sha256')}
        append_once(store, TASK, dict(obs_id=prefix + ':verified', kind=CAPSULE, source_artifacts=refs,
                    values=dict(capsule_id=CAPSULE, release=release, summary=report['summary'], report=ref)))
    return dict(home=str(HOME), task_id=TASK, release=release, **ref)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for mode in ('stock', 'off', 'on'):
        parser.add_argument('--' + mode, type=Path, required=True)
    parser.add_argument('--products', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    arms, retained = {}, []
    for role in ('stock', 'off', 'on'):
        arms[role], artifacts = collect(getattr(args, role), role, args.products)
        retained.extend(artifacts)
    packet = dict(schema='spark-native-prefetch-evidence/1', arms=arms)
    args.out.write_bytes(json_bytes(packet))
    if args.publish:
        print(json.dumps(publish(packet, args.out, retained), indent=2))


if __name__ == '__main__':
    main()
