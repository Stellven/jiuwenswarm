"""Normalize verified native cache reports and publish a separate analysis CC result."""
import argparse
import json
from pathlib import Path
import tempfile

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest
from report_p1 import json_bytes


ROOT = Path.home() / 'predemo-spark'
REPO = Path(__file__).resolve().parents[2]
CAPSULE = 'analysis.cache_size_pareto'
BUNDLE = REPO / 'jiuwenswarm/factory/ccs/cache_size_pareto'
TASK = 'spark-analysis-cache-size-pareto-20261120'


def load(path):
    return json.loads(path.read_bytes())


def read_verified(home, task, prefix):
    home = Path(home).resolve(strict=True)
    with Store(home) as store:
        def retained(name):
            artifact_id = f'{prefix}/{name}.json'
            raw = store.artifact_bytes(task, artifact_id)
            return dict(artifact_id=artifact_id, sha256=digest(raw)), json.loads(raw)

        ref, analysis = retained('analysis')
        verification, verified = retained('verify-receipt')
        _, native_evidence = retained('analysis-input')
        _, release_manifest = retained('release-manifest')
    attempt = home / 'analysis-ccv2/attempts' / verified['call']
    request = load(attempt / 'request.json')
    declared = load(home / 'analysis-ccv2/releases' / verified['release'] / 'manifest.json')
    if (verified['state'] != 'succeeded' or verified['capability'] != 'verify' or
            verified['outputs']['verification']['done'] is not True or request['capability'] != 'verify' or
            request['release'] != verified['release'] or request['inputs'] != dict(analysis=analysis, evidence=native_evidence) or
            release_manifest != declared or load(attempt / 'receipt.json') != verified):
        raise ValueError('Exact native analysis, verification receipt and original request do not agree')
    if analysis['mode'] not in ('c3-screening-60', 'c3-cold-steady', 'cache-size-cold-steady'):
        raise ValueError(f'Expected a supported matched 16-position native report, received {analysis["mode"]}')
    if len(analysis['scopes']) != len(native_evidence['scopes']):
        raise ValueError('Measured scopes do not match native verifier input')
    launches = []
    exclusions = []
    for scope, raw in zip(analysis['scopes'], native_evidence['scopes']):
        if scope['mode'] not in ('on', 'equivalent-stock', 'off') or scope['status'] != 'completed':
            exclusions.append(dict(label=scope['arm'], role=scope['mode'], status=scope['status'],
                                   stop=scope['stop'], reasons=scope.get('reasons', [])))
            continue
        start = raw['start']['value']
        budget = scope['budget_mib']
        argv = list(start['command'][1:])
        for flag, expected in (('--moe-cache-mib', str(budget)), ('--moe-cache-cpu-share', '0')):
            index = argv.index(flag)
            if argv.count(flag) != 1 or argv[index+1] != expected:
                raise ValueError('Native command does not establish the requested bank flags')
            del argv[index:index+2]
        protocol = raw['protocol']['value']
        controls = raw['scope']['value']['actual']
        if protocol['view'] != 'llama' or protocol['regions_sha256'] != analysis['source_regions']['sha256']:
            raise ValueError('Native lab scope does not establish the same source region and protocol')
        matching = dict(model_sha256=analysis['source_identity']['sha256'], regions_sha256=protocol['regions_sha256'],
                        prompts_sha256=native_evidence['prompts']['sha256'], profile_family_sha256=analysis['profile']['sha256'],
                        source_reset=protocol['source_reset'], common_argv=argv, effective_settings=scope['effective_settings'],
                        runtime_environment=scope['runtime_environment'], scope_controls=dict(
                            memory_max_bytes=int(controls['memory.max']), swap_max_bytes=int(controls['memory.swap.max']),
                            oom_group=int(controls['memory.oom.group']), cpu_max=controls['cpu.max'], affinity=controls['sched_affinity']))
        samples = [dict({key: row[key] for key in ('position', 'pair', 'phase', 'prompt_tokens', 'discard', 'ttft_s',
                                                   'decode_tps', 'greedy_hashes')}, result=row['evidence']['result']) for row in scope['samples']]
        launches.append(dict(label=scope['arm'], role=scope['mode'], requested_mib=budget,
                             allocated_mib=scope['native_bank']['allocated_mib'], load_s=scope['load_s'],
                             seed_startup=scope.get('profile'), binary_sha256=start['binary_sha256'],
                             source_commit=raw['load']['value']['source_commit'], matching=matching, samples=samples,
                             receipts={key: scope[key] for key in ('start', 'stop', 'scope', 'protocol', 'conditioning', 'log', 'load')}))
    return dict(analysis=ref, verification=verification, launches=launches, exclusions=exclusions,
                scope_authority=dict(home=str(home), task_id=task, release=verified['release'], verify_call=verified['call']))


def publish(packet, home):
    raw = json_bytes(packet)
    sha = digest(raw)
    host = Host(home / 'ccstore')
    release = host.seal(BUNDLE)
    with tempfile.TemporaryDirectory(prefix='cache-pareto-input-') as work:
        path = Path(work) / 'input.json'
        path.write_bytes(raw)
        evidence = host.put_artifact(path)
    result = host.call(release, 'analyze', {'evidence': evidence}, key='cache-pareto:' + sha + ':analyze', grants=['process.exec'])
    report = result.get('outputs', {}).get('report')
    if report is None:
        raise ValueError(f'Native cache Pareto analysis refused the evidence: {result.get("diagnostics")}')
    verification = host.call(release, 'verify', {'evidence': evidence, 'report': report},
                             key='cache-pareto:' + sha + ':verify', grants=['process.exec'])
    if verification.get('outputs', {}).get('verification', {}).get('done') is not True:
        raise ValueError('Native Pareto verifier did not reproduce the report')
    prefix = 'cache-pareto/' + release[:12] + '-' + sha[:12]
    with Store(home) as store:
        try:
            store.get_task(TASK)
        except NotFound:
            store.create_task(dict(task_id=TASK, objective='Compare verified cache sizes on TTFT and decode without ranking or model launches.'))
        refs = {}
        for key, data in (('evidence', raw), ('report', json_bytes(report)), ('analyze-receipt', json_bytes(result)),
                          ('verify-receipt', json_bytes(verification)), ('release-manifest',
                           (host.store / 'releases' / release / 'manifest.json').read_bytes())):
            record = store.put_artifact(TASK, f'{prefix}/{key}.json', data, 'application/json', None)
            refs[key] = {k: record[k] for k in ('artifact_id', 'sha256')}
        observation = prefix + ':verified'
        append_once(store, TASK, dict(obs_id=observation, kind='analysis.cache_size_pareto',
                    values=dict(capsule_id=CAPSULE, release=release, summary=report['summary'],
                                report=refs['report'], verify_call=verification['call']),
                    source_artifacts=[ref['artifact_id'] for ref in refs.values()], limitations=report['limitations']))
    return dict(home=str(home), task_id=TASK, observation_id=observation, release=release, **refs['report'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--source', nargs=3, metavar=('HOME', 'TASK', 'ARTIFACT_PREFIX'), action='append')
    inputs.add_argument('--evidence', type=Path, help='A packet assembled from separately verified 16-position receipts')
    parser.add_argument('--prepare-only', type=Path, help='Write normalized evidence without sealing or publishing')
    parser.add_argument('--home', type=Path, default=ROOT / 'factory-runs/spark-analysis-cache-pareto')
    args = parser.parse_args()
    packet = load(args.evidence) if args.evidence else dict(schema='spark-cache-pareto-input/1',
                                                            sources=[read_verified(*row) for row in args.source])
    if args.prepare_only:
        args.prepare_only.write_bytes(json_bytes(packet))
        return
    print(json.dumps(publish(packet, args.home.resolve()), indent=2))


if __name__ == '__main__':
    main()
