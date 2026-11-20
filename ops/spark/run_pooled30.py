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
    command = [sys.executable, str(SPARK/'probe_candidate.py'), cc, 'on', 'pooled', str(scope), '--native-mib', '30720',
               '--products', str(inventory), '--arm', cc, '--launch-pass', '1', *options]
    profile = subprocess.check_output(command + ['--describe-profile'], env=environment())
    if not json.loads(profile)['build_receipt']:
        raise ValueError('Pooled candidate must use the exact alternate native product')
    plan = dict(schema='spark-pooled30-admission/1', iteration_id='spark-pooled30-'+tag, subject_arm=cc,
                comparison_target='same-budget-cc', frozen_at=datetime.now(timezone.utc).isoformat(),
                products_manifest_sha256=digest(inventory.read_bytes()), prompt_manifest_sha256=digest((SPARK/'prompts/MANIFEST.json').read_bytes()),
                regions_sha256=digest((ROOT/'OPS/p4/source-regions.json').read_bytes()), command=command,
                launches=[dict(arm=cc, launch_pass=1, view='llama', scope=str(scope), profile_sha256=digest(profile))])
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
    if plan['schema'] != 'spark-pooled30-admission/1' or len(plan['launches']) != 1:
        raise ValueError('Pooled admission requires exactly one candidate launch')
    until = time.monotonic() + wait_seconds
    while not (after.is_file() and after.with_name('probe.json').is_file()):
        if time.monotonic() >= until:
            raise ValueError('The preceding capped result and probe have not both closed')
        time.sleep(3)
    closed_cap(after.resolve(strict=True))
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
    subprocess.run([sys.executable, str(SPARK/'report_pooled30.py'), str(path), '--manifest-sha256', pin],
                   env=env | {'PYTHONPATH': str(ROOT/'jiuwenswarm')}, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    create = sub.add_parser('freeze')
    create.add_argument('manifest', type=Path)
    create.add_argument('--candidate', choices=('C4', 'C2', 'D'), required=True)
    create.add_argument('--products', type=Path, required=True)
    create.add_argument('--series', default='01')
    create.add_argument('--probe-option', action='append', default=[])
    start = sub.add_parser('run')
    start.add_argument('manifest', type=Path)
    start.add_argument('--sha256', required=True)
    start.add_argument('--after', type=Path, required=True)
    start.add_argument('--wait-after-seconds', type=int, default=0)
    args = parser.parse_args()
    if args.mode == 'freeze':
        freeze(args.manifest, args.candidate, args.products, args.series, args.probe_option)
    else:
        run(args.manifest, args.sha256, args.after, args.wait_after_seconds)
