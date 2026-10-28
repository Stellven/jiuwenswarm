"""Write one run-meta record for a ccbench run (called by scripts/ai4r-bench; stdlib only, no model, no container).

  python runmeta.py --file OUT/run-meta/<name>.json --bench B --script S --mode host|container [--image TAG]
                    [--cmdline LINES]
                    [--model-run] [--start ISO] [--end ISO] [--exit-code N] -- ARGV...

Called twice per run with the same --file: before the bench starts (end and exit_code null) and after it stops.
The dossier reads these files into each case's run.json.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roots  # noqa: E402


def run(argv, timeout=60):
    try:
        done = subprocess.run(argv, capture_output=True, timeout=timeout)
        return done.returncode, done.stdout.decode('utf-8', 'replace').strip()
    except (OSError, subprocess.SubprocessError):
        return None, ''


def product():
    root = str(roots.code_root())
    info = roots.product_commit()
    rec = {'root': root, 'commit': info['commit'], 'dirty': info['dirty']}
    if info['dirty']:
        code, diff = run(['git', '-C', root, 'diff', 'HEAD', '--stat'])
        rec['dirty_stat'] = diff.splitlines()[-30:] if code == 0 else None
        try:
            full = subprocess.run(['git', '-C', root, 'diff', 'HEAD'], capture_output=True, timeout=60).stdout
            rec['diff_head_sha256'] = hashlib.sha256(full).hexdigest()
        except (OSError, subprocess.SubprocessError):
            rec['diff_head_sha256'] = None
    return rec


def image(tag):
    rec = {'tag': tag, 'id': None, 'repo_digests': None}
    code, text = run(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'])
    if code == 0:
        rec['id'] = text
        code, text = run(['docker', 'image', 'inspect', tag, '--format', '{{json .RepoDigests}}'])
        rec['repo_digests'] = json.loads(text) if code == 0 and text else None
    return rec


def codex():
    path = roots.codex_bin()
    rec = {'path': path, 'version': None}
    if path:
        code, text = run([path, '--version'])
        rec['version'] = text if code == 0 else 'codex --version failed'
    return rec


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--bench', required=True)
    parser.add_argument('--script', required=True)
    parser.add_argument('--mode', choices=('host', 'container'), required=True)
    parser.add_argument('--image')
    parser.add_argument('--cmdline', default='', help='the ai4r-bench arguments as typed, one per line')
    parser.add_argument('--model-run', action='store_true')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end')
    parser.add_argument('--exit-code', type=int)
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    words = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
    rec = {'bench': args.bench, 'script': args.script, 'ai4r_bench_args': args.cmdline.splitlines(), 'argv': words, 'mode': args.mode,
           'started_at': args.start, 'finished_at': args.end, 'exit_code': args.exit_code,
           'product': product()}
    if args.mode == 'container':
        rec['image'] = image(args.image)
    if args.model_run:
        # In container mode this is the host codex; the one the container ran is inside the image and is not probed.
        rec['codex'] = codex()
        if args.mode == 'container':
            rec['codex']['note'] = 'host codex; the container runs its own copy, not probed'
    args.file.parent.mkdir(parents=True, exist_ok=True)
    args.file.write_bytes((json.dumps(rec, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main(sys.argv[1:])
