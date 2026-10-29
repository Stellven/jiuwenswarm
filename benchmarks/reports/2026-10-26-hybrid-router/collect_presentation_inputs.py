"""Collect small original inputs/answers and explicit receipt projections.

Read-only: no model calls and no account, auth, or reviewer files. Full diagnostic
receipts stay on Spark. The complete internal measurement export is unchanged.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def collect():
    base = Path('/home/user2/ai4r-data/benchmarks')
    files, receipts = [], []
    for arm, campaign in [('chatgpt', 'chatgpt-baseline-002'), ('v5', 'hybrid-operations-001')]:
        folder = base/campaign
        plan = json.loads((folder/'plan.json').read_bytes())
        paths = [folder/name for name in ('plan.json', 'plan-pin.json', 'launched.json', 'finished.json')]
        for job in plan['jobs']:
            sub = folder/(job['variant_id']+'-r'+str(job['repeat']))
            paths += [sub/'request.json', sub/'original.txt']
            raw = (sub/'result.json').read_bytes()
            result = json.loads(raw)
            receipt = {'cohort': arm, 'variant': job['variant_id'], 'repeat': job['repeat'],
                'source_path': str(sub/'result.json'), 'source_sha256': digest(raw),
                'projection': 'Worker-performance view of full receipt; diagnostic verdicts not exported.',
                'elapsed_s': result['elapsed_s'], 'prompt_sha256': result['prompt_sha256']}
            if arm == 'chatgpt':
                receipt.update(usage=result['usage'], identity=result['identity'])
            else:
                receipt.update(model_calls=result['model_calls'],
                    worker_decisions=[d for d in result['decisions'] if d['record']['subnode_id'] == 'worker'],
                    identity=result['worker']['identity'], routing_policy=result['routing_policy'])
            receipts.append(receipt)
        for path in paths:
            raw = path.read_bytes()
            files.append({'path': arm+'/'+path.relative_to(folder).as_posix(),
                'source_path': str(path), 'sha256': digest(raw), 'bytes': len(raw),
                'base64': base64.b64encode(raw).decode()})
    return {'files': files, 'receipts': receipts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if not args.ssh:
        print(json.dumps(collect()))
    else:
        if not args.destination:
            parser.error('--destination is required with --ssh')
        cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'HostKeyAlias=100.105.127.48', '-o', 'UserKnownHostsFile=D:/ai4r-cache/ssh/known_hosts',
            args.ssh, 'python3', '-']
        remote = subprocess.run(cmd, input=Path(__file__).read_bytes(), capture_output=True, timeout=45)
        if remote.returncode:
            raise RuntimeError(remote.stderr.decode(errors='replace'))
        package = json.loads(remote.stdout)
        measurements = json.loads((Path(__file__).parent/'data/measurements.json').read_text(encoding='utf-8'))
        index = {(r['cohort'], r['variant'], r['repeat']): r for r in measurements['observations']}
        for receipt in package['receipts']:
            row = index[(receipt['cohort'], receipt['variant'], receipt['repeat'])]
            assert row['source_sha256'] == receipt['source_sha256'], 'Source receipt changed'
        originals = args.destination/'originals'
        originals.mkdir(parents=True, exist_ok=True)
        manifest = []
        for item in package['files']:
            raw = base64.b64decode(item.pop('base64'), validate=True)
            assert digest(raw) == item['sha256']
            target = originals/item['path']
            assert target.resolve().is_relative_to(originals.resolve())
            if target.name == 'original.txt':
                arm, folder, _ = item['path'].split('/')
                variant, repeat = folder.rsplit('-r', 1)
                assert raw.decode('utf-8') == index[(arm, variant, int(repeat))]['worker_output']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            manifest.append(item)
        (originals/'manifest.json').write_text(json.dumps({'schema': 'ai4r-original-public-artifacts:1',
            'scope': 'Original public requests, worker answers and frozen campaign metadata; no full diagnostic receipts.',
            'files': manifest}, indent=2)+'\n', encoding='utf-8')
        (args.destination/'receipt-projections.json').write_text(json.dumps({
            'schema': 'ai4r-worker-performance-receipt-projections:1',
            'note': 'Explicit projections, not complete original receipts. Original source SHA-256 retained per observation.',
            'receipts': package['receipts']}, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'original_files': len(manifest), 'receipt_projections': len(package['receipts']),
            'destination': str(args.destination)}))
