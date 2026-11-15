"""Export only the seven research capsules, focused tests and CPU receipts.

The previous handoffs remain unchanged. Models, credentials and mutable stores
are not included. An optional separately saved agent image is not swept in.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('research_qualification', Path(__file__).with_name('qualify-research-ccs.py'))
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)

VERIFY = '''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
expected=json.loads((root/'MANIFEST.json').read_text())
actual={}
for p in root.rglob('*'):
 if p.is_symlink():raise SystemExit('Unexpected symlink')
 if p.is_file() and p!=root/'MANIFEST.json':actual[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
if actual!=expected:raise SystemExit('File set or digest mismatch')
print('Verified',len(actual),'files; no runtime dependencies needed.')
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    root, out = a.root.resolve(), a.output.resolve()
    stage = out / 'research-cc-starter-kit'
    stage.mkdir(parents=True, exist_ok=False)
    def copy(source, relative):
        if source.is_symlink():
            raise ValueError('Unexpected source symlink')
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    receipt_root = root / 'research-cc-qualification-001'
    summary = json.loads((receipt_root / 'SUMMARY.json').read_text())
    if summary['passed'] is not True:
        raise ValueError('Research examples must pass before packaging')
    for name in qualifier.PACKAGES:
        package = REPO / 'jiuwenswarm/factory/ccs' / name
        record = json.loads((receipt_root / (name + '.json')).read_text())
        actual = {str(f.relative_to(package)):sha(f) for f in sorted(package.rglob('*'))
                  if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'}
        if actual != record['source_sha256']:
            raise ValueError('Qualified package changed: ' + name)
        for relative in actual:
            copy(package / relative, package.relative_to(REPO) / relative)
        copy(receipt_root / (name + '.json'), Path('receipts') / (name + '.json'))
    copy(receipt_root / 'SUMMARY.json', 'receipts/SUMMARY.json')
    for source in sorted((REPO / 'tests/factory').glob('test_research_*.py')):
        copy(source, source.relative_to(REPO))
    for source in sorted((REPO / 'docs/architecture/factory').glob('RESEARCH-*.md')):
        copy(source, source.relative_to(REPO))
    for name in ('qualify-research-ccs.py', 'package-research-ccs.py'):
        copy(REPO / 'deploy/spark' / name, 'deploy/spark/' + name)
    for name in ('LICENSE', 'AGENTS.md'):
        copy(REPO / name, name)
    for name in ('research-cc-final-quick-tests.log', 'research-cc-agent-refresh.log', 'final-role-images.json', 'agent-final-standalone-smoke.log'):
        copy(root / 'results' / name, 'receipts/' + name)
    (stage / 'README.md').write_text('''# RSI research CC starter kit

Seven standalone CC packages, 24 native capabilities, 59 focused tests passed.
The actual standalone agent smoke sealed all 32 top-level capsules. These are
CPU reference prototypes with attached checks, not integrated GPU optimizations
or factory admission certificates. No new model inference was run for this kit.

Read docs/architecture/factory/RESEARCH-CC-STARTER-KIT.md for jobs, research mappings,
integration ideas and limitations. Every package has SKILL.md, METHOD.md,
SOURCES.json, EXAMPLES.json and executable verification.py. Sources were inspected
at recorded revisions; no upstream engine implementation was copied.

Verify this archive with `python3 verify.py`. Then import the seven directories
under jiuwenswarm/factory/ccs into an existing compatible factory checkout, or use
the separately saved refreshed agent image. This kit is an overlay, not a complete
factory installation. No model weights, authentication, environments or mutable
mission database are included. Run qualify-research-ccs.py from the existing
checkout to generate NEW release-bound CPU receipts; don't overwrite originals.

RSI should use fixed verification holdouts, record changed package identities,
and qualify native engine integration separately. CPU/GPU on Spark share physical
memory. Cache/prefetch methods preserve routing; quantization and expert skipping
need a separate approximation/quality lane. Discrete simulation timings are not
GPU measurements. Methods and Python components introduce no new dependencies.

Cleanup: owned output archives and receipts can be moved off Spark. Retain source
packages and evidence until the transfer is verified. Do not prune shared Docker
layers, model weights, queues, builder caches or unrelated services.
''')
    (stage / 'verify.py').write_text(VERIFY)
    manifest = {str(f.relative_to(stage)):sha(f) for f in sorted(stage.rglob('*')) if f.is_file()}
    (stage / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    subprocess.run([sys.executable, str(stage / 'verify.py')], check=True)
    archive = out / 'research-cc-starter-kit.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(stage, arcname=stage.name)
    (out / (archive.name + '.sha256')).write_text(sha(archive) + '  ' + archive.name + '\n')
    print(json.dumps(dict(archive=str(archive), sha256=sha(archive), files=len(manifest), packages=7,
                          native_examples=summary['native_calls'], qualification='CPU reference only')))


if __name__ == '__main__':
    main()
