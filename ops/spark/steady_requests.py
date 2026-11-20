"""Collect a cold-start position curve and five post-warmup pairs on one existing capped server."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from run_p4_window import accepted_result, boundary_resources
from source_residency import snapshot

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / 'predemo-spark'

def run(scope, arm, port, view):
    receipt = json.loads((scope / 'scope.json').read_bytes())
    cgroup = Path(receipt['cgroup'])
    prompts = HERE / 'prompts'
    approved = {item['target_tokens_including_template']: item['prompt_sha256']
                for item in json.loads((prompts / 'MANIFEST.json').read_bytes())['prompts']}
    region_bytes = (ROOT / 'OPS/p4/source-regions.json').read_bytes()
    regions = json.loads(region_bytes)
    schedule = []
    for index in range(8):
        measured = index >= 3
        pair = index - 2 if measured else index + 1
        sizes = (2048, 512) if index in (2, 4, 6) else (512, 2048)
        for size in sizes:
            name = f'rep-{pair}-{size}' if measured else f'warmup-{pair}-{size}'
            schedule.append(dict(position=len(schedule) + 1, phase='steady' if measured else 'warmup',
                                 pair=pair, repeat=pair if measured else 0, size=size, path=name))
    protocol = dict(schema='spark-cold-steady/1', arm=arm, view=view, source_reset='file-specific DONTNEED',
                    regions_sha256=hashlib.sha256(region_bytes).hexdigest(), warmups_per_size=3, measured_per_size=5,
                    ordered_requests=schedule, conditioning_receipt=str(ROOT / 'OPS/p3/early-preflights' /
                                                                       (scope.name + '-source.json')))
    conditioning = json.loads(Path(protocol['conditioning_receipt']).read_bytes())
    fractions = [record['estimated_resident_fraction'] for source in conditioning['after']['views'].values()
                 for record in source['total'].values()]
    if not fractions or any(fractions):
        raise ValueError('Cold-start comparison needs zero sampled source-page residency before load')
    (scope / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    hashes = {str(size): [] for size in approved}
    for row in schedule:
        name, size, repeat = row['path'], row['size'], row['repeat']
        boundary_resources(scope / (name + '-before.json'), cgroup, receipt['pid'])
        page_state = snapshot(regions, view, 4096, 20261120, scope / 'scope.json')
        (scope / (name + '-residency.json')).write_text(json.dumps(page_state) + '\n')
        command = [sys.executable, str(HERE / 'bench_http.py'), '--url', f'http://127.0.0.1:{port}',
                   '--arm', arm, '--prompt', str(prompts / f'{size}.txt'), '--prompt-tokens', str(size),
                   '--out', str(scope / name), '--repeat', str(repeat)]
        if not repeat:
            command.append('--discard')
        subprocess.run(command, check=True)
        found = {}
        accepted_result(scope / name / 'result.json', size, repeat, arm, approved[size], found)
        hashes[str(size)].append(found[str(size)])
        boundary_resources(scope / (name + '-after.json'), cgroup, receipt['pid'])
    return hashes
