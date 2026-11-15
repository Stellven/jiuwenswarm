"""Run the seven owned research packages' quick CPU checks and native examples.

Produces release-bound smoke evidence, not factory admission or GPU certification.
No network, Docker, model execution or arbitrary caller-selected package commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from jiuwenswarm.ccv2.ccv2 import Host, load

PACKAGES = ('expert_cache_lab', 'ssd_streaming_lab', 'heterogeneous_placement_lab',
            'precision_lab', 'kv_reuse_lab', 'serving_scheduler_lab', 'methodology_transfer_lab')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    host = Host(output / 'ccstore', session_grants=['process.exec'], python=sys.executable)
    results = []
    for name in PACKAGES:
        package = REPO / 'jiuwenswarm/factory/ccs' / name
        declaration = load(package / 'cc.yaml')
        inputs = json.loads((package / 'EXAMPLES.json').read_text())
        if set(inputs) != set(declaration['capabilities']):
            raise ValueError('Example coverage differs for ' + name)
        release = host.prepare(package)
        start = time.monotonic()
        verification = subprocess.run([sys.executable, str(package / 'verification.py')],
                                      capture_output=True, text=True, timeout=30)
        record = dict(package=name, cc_id=declaration['id'], release=release,
                      checks=dict(exit_code=verification.returncode, stdout=verification.stdout,
                                  stderr=verification.stderr, elapsed_s=time.monotonic()-start), calls=[])
        results.append(record)
        for capability, value in inputs.items():
            start = time.monotonic()
            receipt = host.call(release, capability, value)
            record['calls'].append(dict(capability=capability, elapsed_s=time.monotonic()-start, receipt=receipt))
        record['source_sha256'] = {str(p.relative_to(package)): digest(p) for p in sorted(package.rglob('*'))
                                   if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        (output / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    passed = all(r['checks']['exit_code'] == 0 and all(c['receipt']['state'] == 'succeeded' for c in r['calls']) for r in results)
    summary = dict(scope='Quick CPU reference and native CC example checks only', passed=passed,
                   packages=len(results), native_calls=sum(len(r['calls']) for r in results),
                   gpu_executed=False, model_quality_evaluated=False, admission_granted=False,
                   releases={r['cc_id']:r['release'] for r in results})
    (output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
