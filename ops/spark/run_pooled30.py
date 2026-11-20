"""Freeze and run the owner-approved single-candidate pooled 30 GiB screen."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
SPARK = ROOT / 'jiuwenswarm/ops/spark'
OOM = ('oom', 'oom_kill', 'oom_group_kill')
MAPPER_REPAIR = '0fe58a9484bcd2ba730e8bd28b3467361895ce98'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def environment():
    return {k: v for k, v in os.environ.items() if k not in ('SPARK_CONCURRENT_SCREENING_SCOPE', 'SPARK_EXPERT_SAMPLE_DETAIL')}


def freeze(path, cc, inventory, series, options):
    tag = f'{cc.lower()}-{series}'
    scope = ROOT / 'OPS/runs' / f'pooled30-{tag}'
    inventory = inventory.resolve(strict=True)
    inventory_bytes = inventory.read_bytes()
    if cc == 'C5':
        product, = json.loads(inventory_bytes)['products']
        if (product['capsule'], product['source_commit'], product['state']) != ('batch_layout_mapper', MAPPER_REPAIR, 'succeeded'):
            raise ValueError('C5 pooled screening requires the exact successfully built aLoRA repair')
    command = [sys.executable, str(SPARK/'probe_candidate.py'), cc, 'on', 'pooled', str(scope), '--native-mib', '30720',
               '--products', str(inventory), '--arm', cc, '--launch-pass', '1', *options]
    profile = subprocess.check_output(command + ['--describe-profile'], env=environment())
    if not json.loads(profile)['build_receipt']:
        raise ValueError('Pooled candidate must use the exact alternate native product')
    plan = dict(schema='spark-pooled30-admission/1', iteration_id='spark-pooled30-'+tag, subject_arm=cc,
                comparison_target='same-budget-cc', frozen_at=datetime.now(timezone.utc).isoformat(),
                products_manifest_sha256=digest(inventory_bytes), prompt_manifest_sha256=digest((SPARK/'prompts/MANIFEST.json').read_bytes()),
                regions_sha256=digest((ROOT/'OPS/p4/source-regions.json').read_bytes()), command=command,
                launches=[dict(arm=cc, launch_pass=1, view='llama', scope=str(scope), profile_sha256=digest(profile))])
    with path.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(path=str(path), sha256=digest(path.read_bytes()), scope=str(scope)), indent=2))


def freeze_mapper_stock(path, candidate_manifest, candidate_pin):
    candidate_raw = candidate_manifest.read_bytes()
    previous = json.loads(candidate_raw)
    if (digest(candidate_raw) != candidate_pin or previous['schema'] != 'spark-pooled30-admission/1' or
            previous['iteration_id'] != 'spark-pooled30-c5-01' or previous['subject_arm'] != 'C5'):
        raise ValueError('Flags-matched stock control requires the original frozen C5 manifest')
    candidate, = previous['launches']
    candidate_scope = Path(candidate['scope']).resolve(strict=True)
    closed_cap(candidate_scope / 'result.json')
    if not (candidate_scope / 'probe.json').is_file():
        raise ValueError('The candidate did not retain its completed probe receipt')
    candidate_profile = (candidate_scope / 'p4-launch-profile.json').read_bytes()
    if digest(candidate_profile) != candidate['profile_sha256']:
        raise ValueError('Repaired candidate launch profile changed')
    candidate_profile = json.loads(candidate_profile)
    command = list(previous['command'])
    scope = ROOT / 'OPS/runs/pooled30-c5-matched-stock-01'
    command[3] = 'equivalent-stock'
    command[5] = str(scope)
    command[command.index('--arm') + 1] = 'A+'
    profile = subprocess.check_output(command + ['--describe-profile'], env=environment())
    stock = json.loads(profile)
    observed = candidate_profile['environment'].copy()
    observed.pop('LD_LIBRARY_PATH')
    gates = stock['environment'].copy()
    gates.pop('LD_LIBRARY_PATH')
    if (stock['build_receipt'] is not None or stock['binary_sha256'] == candidate_profile['binary_sha256'] or
            stock['command'][1:] != candidate_profile['command'][1:] or
            stock['products_manifest_sha256'] != previous['products_manifest_sha256'] or
            observed != (gates | {'LLAMA_BATCH_LAYOUT': '1'}) or any(key.startswith('LLAMA_') for key in gates)):
        raise ValueError('Stock control must share exact C5 argv with its mapper gate unset')
    plan = dict(previous, schema='spark-c5-matched-stock-admission/1', frozen_at=datetime.now(timezone.utc).isoformat(),
                candidate_manifest=str(candidate_manifest.resolve()), candidate_manifest_sha256=candidate_pin,
                command=command, launches=[dict(arm='A+', launch_pass=1, view='llama', scope=str(scope),
                                                profile_sha256=digest(profile))])
    with path.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(path=str(path), sha256=digest(path.read_bytes()), scope=str(scope)), indent=2))


def closed_cap(path):
    cap = load(path)
    if (path.name != 'result.json' or path.parent.parent != ROOT / 'OPS/runs' or cap['reason'] or cap['returncode'] or
            not cap['scope_verified'] or cap['min_mem_available_bytes'] < 8 * 1024**3 or
            any(int(cap['memory_events'].get(k, 0)) for k in OOM) or 'Result=oom-kill' in cap.get('systemd_properties', '')):
        raise ValueError('Review the preceding completed cap before screening')
    return cap


def run(path, pin, after, wait_seconds):
    raw = path.read_bytes()
    if digest(raw) != pin:
        raise ValueError('Pooled screen admission digest differs from the frozen pin')
    plan = json.loads(raw)
    matched_mapper_stock = plan['schema'] == 'spark-c5-matched-stock-admission/1'
    if (plan['schema'] != 'spark-pooled30-admission/1' and not matched_mapper_stock) or len(plan['launches']) != 1:
        raise ValueError('Pooled admission requires exactly one candidate launch')
    until = time.monotonic() + wait_seconds
    while not (after.is_file() and after.with_name('probe.json').is_file()):
        if time.monotonic() >= until:
            raise ValueError('The preceding capped result and probe have not both closed')
        time.sleep(3)
    closed_cap(after.resolve(strict=True))
    if matched_mapper_stock:
        candidate = Path(plan['candidate_manifest'])
        if (digest(candidate.read_bytes()) != plan['candidate_manifest_sha256'] or
                after.resolve().parent != Path(load(candidate)['launches'][0]['scope'])):
            raise ValueError('The preceding cap differs from the frozen C5 candidate')
    prior_probe = load(after.with_name('probe.json'))
    if not prior_probe['greedy_hashes']:
        raise ValueError('The preceding probe closed without greedy request outputs')
    scope = Path(plan['launches'][0]['scope'])
    env = environment()
    if not scope.exists():
        profile = subprocess.check_output(plan['command'] + ['--describe-profile'], env=env)
        if digest(profile) != plan['launches'][0]['profile_sha256']:
            raise ValueError('Pooled candidate profile drifted after freeze')
        while True:
            gpu = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader']).strip()
            probe = subprocess.run([str(ROOT / 'bin/quiet')], capture_output=True, env=env, check=False)
            conditions = json.loads(probe.stdout)
            if probe.returncode in (0, 1) and not gpu and not conditions['model_processes'] and conditions['mem_available_gib'] >= 110:
                break
            time.sleep(5)
        print(json.dumps(dict(admission='candidate-only pooled screen', previous_cap=str(after), conditions=conditions), indent=2), flush=True)
        subprocess.run(plan['command'], env=env, check=True)
    closed_cap(scope / 'result.json')
    reporter = 'report_c5_matched_stock.py' if matched_mapper_stock else 'report_pooled30.py'
    subprocess.run([sys.executable, str(SPARK/reporter), str(path), '--manifest-sha256', pin],
                   env=env | {'PYTHONPATH': str(ROOT/'jiuwenswarm')}, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    create = sub.add_parser('freeze')
    create.add_argument('manifest', type=Path)
    create.add_argument('--candidate', choices=('C4', 'C2', 'C5', 'D'), required=True)
    create.add_argument('--products', type=Path, required=True)
    create.add_argument('--series', default='01')
    create.add_argument('--probe-option', action='append', default=[])
    matched = sub.add_parser('freeze-c5-stock')
    matched.add_argument('manifest', type=Path)
    matched.add_argument('--candidate-manifest', type=Path, required=True)
    matched.add_argument('--candidate-sha256', required=True)
    start = sub.add_parser('run')
    start.add_argument('manifest', type=Path)
    start.add_argument('--sha256', required=True)
    start.add_argument('--after', type=Path, required=True)
    start.add_argument('--wait-after-seconds', type=int, default=0)
    args = parser.parse_args()
    if args.mode == 'freeze':
        freeze(args.manifest, args.candidate, args.products, args.series, args.probe_option)
    elif args.mode == 'freeze-c5-stock':
        freeze_mapper_stock(args.manifest, args.candidate_manifest, args.candidate_sha256)
    else:
        run(args.manifest, args.sha256, args.after, args.wait_after_seconds)
