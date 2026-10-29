"""Read existing campaign files only; export public originals and receipt projections.

No inference, app mutation, account data, native packets or reviewer criteria.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def collect():
    root = Path('/home/user2/ai4r-data/benchmarks/router-v8-20261027')
    files, receipts = [], []
    for arm in ('chatgpt-ai4r', 'hybrid'):
        folder = root/arm
        plan = json.loads((folder/'plan.json').read_bytes())
        paths = [folder/name for name in ('plan.json', 'plan-pin.json', 'launched.json', 'finished.json')]
        assert sha((folder/'plan.json').read_bytes()) == json.loads((folder/'plan-pin.json').read_bytes())['sha256']
        for job in plan['jobs']:
            sub = folder/(job['variant_id']+'-r'+str(job['repeat']))
            paths += [sub/'request.json', sub/'original.txt']
            raw = (sub/'result.json').read_bytes()
            result = json.loads(raw)
            assert result['status'] == 'completed' and not result['unresolved_claims']
            assert result['prompt_sha256'] == job['prompt_sha256']
            receipts.append({'arm': arm, 'variant': job['variant_id'], 'repeat': job['repeat'],
                'source_sha256': sha(raw), 'projection': 'Worker-performance projection; no diagnostic verdicts.',
                'elapsed_s': result['elapsed_s'], 'prompt_sha256': result['prompt_sha256'],
                'identity': result['worker']['identity'], 'routing_policy': result['routing_policy'],
                'model_calls': result['model_calls'],
                'worker_decisions': [d for d in result['decisions'] if d['record']['subnode_id'] == 'worker']})
        for path in paths:
            raw = path.read_bytes()
            files.append({'path': arm+'/'+path.relative_to(folder).as_posix(),
                'sha256': sha(raw), 'bytes': len(raw), 'base64': base64.b64encode(raw).decode()})
    return {'files': files, 'receipts': receipts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if not args.ssh:
        print(json.dumps(collect()))
        return
    if not args.destination:
        parser.error('--destination is required with --ssh')
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'HostKeyAlias=100.105.127.48', '-o', 'UserKnownHostsFile=D:/ai4r-cache/ssh/known_hosts',
        args.ssh, 'python3', '-']
    response = subprocess.run(command, input=Path(__file__).read_bytes(), capture_output=True, timeout=45)
    if response.returncode:
        raise RuntimeError(response.stderr.decode(errors='replace'))
    package = json.loads(response.stdout)
    source = json.loads((Path(__file__).parent/'assessment.json').read_text(encoding='utf-8'))
    index = {(r['arm'], r['variant'], r['repeat']): r for r in source['observations']}
    assert len(package['receipts']) == len(index) == 48
    for receipt in package['receipts']:
        assert receipt['source_sha256'] == index[(receipt['arm'], receipt['variant'], receipt['repeat'])]['receipt_sha256']
    originals = args.destination/'originals'
    originals.mkdir(parents=True, exist_ok=True)
    manifest = []
    for item in package['files']:
        raw = base64.b64decode(item.pop('base64'), validate=True)
        assert sha(raw) == item['sha256'] and len(raw) == item['bytes']
        target = originals/item['path']
        assert target.resolve().is_relative_to(originals.resolve())
        if target.name == 'original.txt':
            arm, folder, _ = item['path'].split('/')
            variant, repeat = folder.rsplit('-r', 1)
            assert raw.decode() == index[(arm, variant, int(repeat))]['worker_output']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        manifest.append(item)
    (originals/'manifest.json').write_text(json.dumps({'schema': 'ai4r-original-public-artifacts:1',
        'scope': 'Byte-for-byte public requests, original worker answers and frozen campaign metadata.',
        'files': manifest}, indent=2)+'\n', encoding='utf-8')
    (args.destination/'receipt-projections.json').write_text(json.dumps({
        'schema': 'ai4r-worker-performance-receipt-projections:2',
        'note': 'Explicit projections, not full original receipts. Source receipt SHA-256 retained.',
        'receipts': package['receipts']}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'original_files': len(manifest), 'receipt_projections': len(package['receipts'])}))


if __name__ == '__main__':
    main()
