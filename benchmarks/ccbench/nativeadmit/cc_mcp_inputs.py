"""Inputs for the real-capsule T1 arm (T1:ccmcp): plain JiuwenSwarm + the portable capsule MCP server.

Stages <out>/ccmcp-inputs/<item>/ from each item's public folder. The task text and the data file are byte for byte the
native arm's. --tool broken (default) keeps the team tool file exactly as the native arm gets it (defect included), so
the only difference between the arms is the registered MCP server. --tool none removes the tool file; the task text
still names it, so use that only to ask "what if the team tool is not there".
The run itself is: nativetask run --inputs-dir <out>/ccmcp-inputs/<item> --task-file <same>/task.txt --capsule-mcp ...
Usage: python -B cc_mcp_inputs.py --out DIR [--tool broken|none]   (writes DIR/ccmcp-inputs/<item>/ and DIR/ccmcp-inputs/manifest.json)
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(item, dest, tool='broken'):
    job = json.loads((HERE / 'items' / item / 'job.json').read_text(encoding='utf-8'))
    public = HERE / 'items' / item / 'public'
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(public, dest)
    if tool == 'none':
        (dest / job['tool_file']).unlink()
    present = (dest / job['tool_file']).is_file()
    return {'item': item, 'tool_file': job['tool_file'], 'tool': tool, 'tool_present': present,
            'tool_sha256': sha(dest / job['tool_file']) if present else None,
            'task_sha256': sha(dest / 'task.txt'), 'task_identical_to_native': sha(dest / 'task.txt') == sha(public / 'task.txt')}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--tool', choices=('broken', 'none'), default='broken')
    args = ap.parse_args(argv)
    root = args.out / 'ccmcp-inputs'
    root.mkdir(parents=True, exist_ok=True)
    rows = [build(p.name, root / p.name, args.tool) for p in sorted((HERE / 'items').iterdir()) if p.is_dir()]
    (root / 'manifest.json').write_bytes((json.dumps(rows, indent=1) + '\n').encode('utf-8'))
    for r in rows:
        print('%-16s tool=%-6s task_identical=%s' % (r['item'], r['tool'], r['task_identical_to_native']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
