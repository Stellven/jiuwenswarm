"""Inputs for the live CC arm: what a JiuwenSwarm agent sees when the team tool is served through a capsule.

A capsule serves only admitted versions. For each item, read cc_route's verdict (<out>/cc/<item>.json):
admitted -> the item's own tool file; rejected -> the admitted reference version of the same family
(calc_reference or table_reference), under the same file name. Task text and data files are unchanged.
The agent then runs exactly like the native arm (nativetask run --inputs-dir <out>/cc-live/<item>).
Usage: python -B cc_live_inputs.py --out DIR   (writes DIR/cc-live/<item>/ and DIR/cc-live/manifest.json)
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
REF = {'calculate': 'calc_reference', 'table_normalize': 'table_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(item, cc_dir, dest):
    job = json.loads((HERE / 'items' / item / 'job.json').read_text(encoding='utf-8'))
    cc = json.loads((Path(cc_dir) / (item + '.json')).read_text(encoding='utf-8'))
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(HERE / 'items' / item / 'public', dest)
    served = item
    if not cc['admitted']:
        served = REF[job['tool']]
        refjob = json.loads((HERE / 'items' / served / 'job.json').read_text(encoding='utf-8'))
        shutil.copyfile(HERE / 'items' / served / 'public' / refjob['tool_file'], dest / job['tool_file'])
    return {'item': item, 'admitted': cc['admitted'], 'served_version': served, 'tool_file': job['tool_file'],
            'tool_sha256': sha(dest / job['tool_file']), 'task_sha256': sha(dest / 'task.txt')}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    out = ap.parse_args(argv).out
    root = out / 'cc-live'
    root.mkdir(parents=True, exist_ok=True)
    rows = [build(p.name, out / 'cc', root / p.name) for p in sorted((HERE / 'items').iterdir()) if p.is_dir()]
    (root / 'manifest.json').write_bytes((json.dumps(rows, indent=1) + '\n').encode('utf-8'))
    for r in rows:
        print('%-16s admitted=%-5s served=%s' % (r['item'], r['admitted'], r['served_version']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
