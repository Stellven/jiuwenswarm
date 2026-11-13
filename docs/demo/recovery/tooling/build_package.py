#!/usr/bin/env python3
"""Build a versioned Satay demo/recovery package from a previous package plus authored sources.

This replaces the ad-hoc /tmp/satay-demo-*.py scripts from 13 Nov (kept unmodified in
tooling/original-tmp/ for provenance).

Steps:
- Copy the previous package's evidence, bundles and context. It is never modified.
- Overlay authored files from docs/demo/recovery.
- Refresh selected capsule/context files from the repo.
- Rebundle any source pins that changed.
- Scan for credentials, check links, write MANIFEST.json, run verify.py.
- Optionally zip and hash.

It submits no jobs and runs no inference.

Usage:
  build_package.py --base OLD_DIR --out NEW_DIR [--rebundle] [--zip]
"""
import argparse, gzip, hashlib, html.parser, json, re, shutil, subprocess, sys, tempfile, urllib.parse, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]            # docs/demo/recovery
J = HERE.parents[2]                                   # jiuwenswarm repo
CCS = J / 'jiuwenswarm/factory/ccs'

AUTHORED = ['20261113 Satay CC Demo Console prepresentation.html', 'START HERE.md', 'AUTONOMOUS.md',
            'PRESENTATION.md', 'RECOVERY.md', 'REPLAY.md', 'ONTOLOGY.md', 'ATTACK QUESTIONS.md',
            'REVIEW.md', 'VALIDATION.md', 'BUDGET.md', 'HANDOFF.md', 'MODEL-CONFIG.md']
OVERLAY_DIRS = {'scripts': 'scripts', 'context/engineering': 'context/engineering', 'media': 'media',
                'reviews': 'reviews', 'tooling': 'tooling'}
EXTRA = {HERE / 'extracts/factory-e5b8d4b7-decisions.json': 'evidence/incremental/decisions.json',
         CCS / 'methodology_ab/AB.md': 'context/methodology_ab/AB.md',
         CCS / 'expert_streaming/components/expert_fill/component.yaml': 'context/expert_streaming/components/expert_fill.component.yaml',
         J / 'docs/architecture/factory/NODE-EXAMPLE.md': 'context/NODE-EXAMPLE.md'}
REPOS = {'jiuwenswarm': Path('/home/muk/projects/jiuwenswarm'), 'siminfeng': Path('/home/muk/projects/siminfeng'),
         'tools': Path('/home/muk/tools'), 'llama-engine': Path('/home/muk/.jiuwenswarm-factory/agent-workspace/llama.cpp')}
SECRET = [re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----'), re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}'),
          re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}'), re.compile(rb'Bearer\s+[A-Za-z0-9_.-]{25,}', re.I),
          re.compile(rb'"(?:access|refresh|id)_token"\s*:\s*"[A-Za-z0-9_.-]{20,}')]


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def put(src, out, rel):
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if Path(src).is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    else:
        shutil.copy2(src, dst)


def rebundle(out):
    pins = json.loads((out / 'SOURCE-PINS.json').read_text())
    for name, repo in REPOS.items():
        head, branch = git(repo, 'rev-parse', 'HEAD'), git(repo, 'symbolic-ref', '--short', 'HEAD')
        old = pins.get(name, {})
        if old.get('commit') == head:
            print('unchanged pin', name, head[:10], flush=True)
            continue
        refs = sorted(set(['refs/heads/' + branch] + list(old.get('refs', {}))))
        dest = out / 'sources' / f'{name}.bundle'
        snap = Path(tempfile.mkdtemp(prefix='satay-snap-'))
        try:
            git(snap, 'init', '-q')
            for ref in refs:
                git(snap, 'fetch', '-q', '--depth=1', '--no-tags', 'file://' + str(repo), ref + ':' + ref)
            git(snap, '-c', 'pack.threads=1', 'bundle', 'create', str(dest), '--all')
            shutil.copy2(snap / '.git/shallow', dest.with_suffix('.shallow'))
            git(snap, 'bundle', 'verify', str(dest))
        finally:
            shutil.rmtree(snap, ignore_errors=True)
        pins[name] = dict(commit=head, branch=branch, remote=git(repo, 'remote', 'get-url', 'origin'),
                          bundle=str(dest.relative_to(out)), shallow=str(dest.with_suffix('.shallow').relative_to(out)),
                          history=old.get('history', 'Exact pinned source snapshots; restore boundary before unbundling.'),
                          refs={r: git(repo, 'rev-parse', r) for r in refs}, working_tree_status=git(repo, 'status', '--short'))
        print('rebundled', name, head[:10], dest.stat().st_size, 'bytes', flush=True)
    (out / 'SOURCE-PINS.json').write_text(json.dumps(pins, indent=2) + '\n')


def restore_check(out):
    """Restore every pinned bundle into a scratch dir with the package's own helper; record HEAD + fsck."""
    pins = json.loads((out / 'SOURCE-PINS.json').read_text())
    scratch = Path(tempfile.mkdtemp(prefix='satay-restore-'))
    try:
        proc = subprocess.run([sys.executable, '-I', str(out / 'scripts/restore-sources.py'), str(scratch / 'r')],
                              capture_output=True, text=True)
        heads = {n: git(scratch / 'r' / n, 'rev-parse', 'HEAD') for n in pins if (scratch / 'r' / n).exists()}
        ok = proc.returncode == 0 and all(heads.get(n) == pins[n]['commit'] for n in pins)
        (out / 'RESTORE-CHECK.json').write_text(json.dumps(dict(
            method='scripts/restore-sources.py into an empty scratch dir; each repo: unbundle + .shallow boundary, checkout pinned commit, git fsck --full',
            exit_code=proc.returncode, pinned={n: pins[n]['commit'] for n in pins}, restored_heads=heads, all_match=ok), indent=2) + '\n')
        print('restore check', 'PASS' if ok else 'FAIL', flush=True)
        if not ok:
            raise SystemExit(proc.stderr[-2000:])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ('href', 'src', 'poster') and v and not v.startswith(('#', 'http:', 'https:', 'data:', 'mailto:')):
                self.refs.append(v)


def check(out):
    problems = []
    for page in out.glob('*.html'):
        parser = Links(); parser.feed(page.read_text())
        for ref in parser.refs:
            if not (out / urllib.parse.unquote(ref.split('#')[0])).exists():
                problems.append(f'{page.name}: missing {ref}')
        if re.search(r'Run\s*5', page.read_text()):
            problems.append(f'{page.name}: mentions an excluded run')
    hits = []
    for f in out.rglob('*'):
        if not f.is_file() or f.suffix in ('.bundle', '.mp4', '.png', '.jpg', '.shallow'):
            continue
        data = f.read_bytes()
        if f.suffix == '.gz':
            data = gzip.decompress(data)
        if any(p.search(data) for p in SECRET):
            hits.append(str(f.relative_to(out)))
    (out / 'SECRET-SCAN.json').write_text(json.dumps({
        'scope': 'All package files except binary media and git bundles; gzip evidence decompressed. Git history not exhaustively scanned. Authentication directories and live DB are never copied.',
        'pattern_hits_files': hits}, indent=2) + '\n')
    if hits:
        problems.append('credential-like patterns in: ' + ', '.join(hits))
    return problems


def manifest(out):
    files = []
    for f in sorted(out.rglob('*')):
        if f.is_file() and f.name != 'MANIFEST.json':
            files.append(dict(path=str(f.relative_to(out)), bytes=f.stat().st_size, sha256=sha256(f)))
    prev = json.loads((out / 'MANIFEST.json').read_text()) if (out / 'MANIFEST.json').exists() else {}
    prev.update(schema='satay.demo.recovery/2', source_pins='SOURCE-PINS.json', files=files)
    (out / 'MANIFEST.json').write_text(json.dumps(prev, indent=2) + '\n')
    subprocess.run([sys.executable, '-I', str(out / 'scripts/verify.py')], check=True)
    return len(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--rebundle', action='store_true')
    ap.add_argument('--zip', action='store_true')
    a = ap.parse_args()
    base, out = a.base.resolve(), a.out.resolve()
    assert base != out and base.is_dir()
    if not out.exists():
        shutil.copytree(base, out, symlinks=True)
    for name in AUTHORED:
        if (HERE / name).exists():
            put(HERE / name, out, name)
    for src, rel in OVERLAY_DIRS.items():
        if (HERE / src).exists():
            put(HERE / src, out, rel)
    for src, rel in EXTRA.items():
        put(src, out, rel)
    for name in ('builder', 'lab_client', 'methodology_ab', 'expert_streaming'):
        put(CCS / name / 'cc.yaml', out, f'context/capsules/{name}.yaml')
    for name in ('STREAMING.md', 'SOURCE-MAP.md', 'ONTOLOGY.yaml', 'EVIDENCE.md', 'cc.yaml'):
        put(CCS / 'expert_streaming' / name, out, f'context/expert_streaming/{name}')
    if a.rebundle:
        rebundle(out)
        restore_check(out)
    problems = check(out)
    if problems:
        raise SystemExit('\n'.join(problems))
    n = manifest(out)
    result = dict(package=str(out), files=n)
    if a.zip:
        z = out.with_suffix('.zip')
        tmp = z.with_name(z.name + '.partial')
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=2) as zf:
            for f in sorted(out.rglob('*')):
                if f.is_file():
                    zf.write(f, str(Path(out.name) / f.relative_to(out)))
        tmp.replace(z)
        digest = sha256(z)
        z.with_suffix('.sha256').write_text(f'{digest}  {z.name}\n')
        result.update(zip=str(z), bytes=z.stat().st_size, sha256=digest)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
