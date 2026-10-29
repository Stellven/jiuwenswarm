"""Inputs for the live CC arm: what a JiuwenSwarm agent sees when the team tool is served through a capsule.

A capsule serves only admitted versions. For each item, read cc_route's verdict (<out>/cc/<item>.json):
admitted -> the item's own tool file; rejected -> the admitted reference version of the same family
(calc_reference or table_reference), under the same file name. Task text and data files are unchanged.
The agent then runs exactly like the native arm (nativetask run --inputs-dir <out>/cc-live/<item>).
Usage: python -B cc_live_inputs.py --out DIR [--served SERVED]   (writes DIR/cc-live/<item>/ and DIR/cc-live/manifest.json)
--served SERVED: a folder of served tool versions, flat, named like the reference files (calc_tool.py, table_tool.py). A rejected
item then gets SERVED/<tool_file> instead of the reference version in items/. A file missing from SERVED stops the run (no silent
fallback). This is the hook for another arm, for example a capsule library changed by RSI: same command, different SERVED.
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


def build(item, cc_dir, dest, served_dir=None):
    job = json.loads((HERE / 'items' / item / 'job.json').read_text(encoding='utf-8'))
    cc = json.loads((Path(cc_dir) / (item + '.json')).read_text(encoding='utf-8'))
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(HERE / 'items' / item / 'public', dest)
    served = item
    if not cc['admitted']:
        served = REF[job['tool']]
        refjob = json.loads((HERE / 'items' / served / 'job.json').read_text(encoding='utf-8'))
        if served_dir is None:
            source = HERE / 'items' / served / 'public' / refjob['tool_file']
        else:
            source = Path(served_dir) / refjob['tool_file']
            if not source.is_file():
                raise SystemExit('--served %s has no %s (needed for %s)' % (served_dir, refjob['tool_file'], item))
        shutil.copyfile(source, dest / job['tool_file'])
    row = {'item': item, 'admitted': cc['admitted'], 'served_version': served, 'tool_file': job['tool_file'],
           'tool_sha256': sha(dest / job['tool_file']), 'task_sha256': sha(dest / 'task.txt')}
    if served_dir is not None and not cc['admitted']:      # the default manifest keeps its old keys
        row['served_from'] = str(served_dir)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--served', type=Path, help='folder of served tool versions (calc_tool.py, table_tool.py) used instead of the reference')
    args = ap.parse_args(argv)
    out = args.out
    root = out / 'cc-live'
    root.mkdir(parents=True, exist_ok=True)
    rows = [build(p.name, out / 'cc', root / p.name, args.served) for p in sorted((HERE / 'items').iterdir()) if p.is_dir()]
    (root / 'manifest.json').write_bytes((json.dumps(rows, indent=1) + '\n').encode('utf-8'))
    for r in rows:
        print('%-16s admitted=%-5s served=%s' % (r['item'], r['admitted'], r['served_version']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
