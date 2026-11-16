"""Export the connected-development source overlay and explicit retained evidence.

No model weights, credentials, dependency environments or live databases are copied.
Run after verification; image export is separate so this script needs no Docker.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

REPO = Path(__file__).resolve().parents[2]
EXCLUDED = {'__pycache__', '.pytest_cache', '.git', 'node_modules', 'build',
            '.codex', '.env', 'auth.json', 'credentials.json'}
VERIFY = '''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
expected=json.loads((root/'MANIFEST.json').read_text())
actual={}
for p in root.rglob('*'):
 if p.is_symlink():raise SystemExit('Unexpected symlink')
 if p.is_file() and p!=root/'MANIFEST.json':
  with p.open('rb') as f:actual[str(p.relative_to(root))]=hashlib.file_digest(f,'sha256').hexdigest()
if actual!=expected:raise SystemExit('Digest or file set mismatch')
print('Verified',len(actual),'files')
'''


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output.resolve()
    stage = out / 'connected-development'
    stage.mkdir(parents=True, exist_ok=False)

    def copy(source, relative):
        if source.is_symlink():
            raise ValueError('Unexpected symlink: ' + str(source))
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def tree(source, relative):
        if not source.is_dir() or source.is_symlink():
            raise ValueError('Required regular directory missing: ' + str(source))
        for path in sorted(source.rglob('*')):
            parts = path.relative_to(source).parts
            if any(part in EXCLUDED for part in parts):
                continue
            if path.suffix in {'.pyc', '.lock', '.sqlite', '.db'} or path.name.endswith(('-wal', '-shm')):
                continue
            if path.is_file() or path.is_symlink():
                copy(path, Path(relative) / path.relative_to(source))

    for name in ['jiuwenswarm', 'tests/factory', 'docs/architecture/factory',
                 'docs/architecture/ccv2', 'deploy/spark']:
        tree(REPO / name, Path('source') / name)
    for name in ['AGENTS.md', 'LICENSE', 'pyproject.toml', 'scripts/factory_branch_mission.py',
                 'tools/run_ds4_numerical_diagnostic.py', 'tools/analyze_ds4_numerical_capture.py']:
        copy(REPO / name, Path('source') / name)
    for name in ['development-numerical-gpu-001', 'development-numerical-gpu-002',
                 'development-numerical-gpu-003', 'development-numerical-gpu-004',
                 'development-numerical-analysis-001', 'development-numerical-analysis-002',
                 'night-numerical-investigation-cpu-20261116']:
        tree(root / name, Path('evidence') / name)
    mission = root / 'development-cpu-mission-001'
    for name in ['manifest.json', 'campaign.json', 'task.json', 'launch.py', 'controller-result.json',
                 'evidence-snapshot.json', 'branches.json', 'pareto.json', 'native-receipts.json',
                 'AGENT-REPORT.json', 'NEXT-INPUT-PROPOSAL.json']:
        copy(mission / name, Path('evidence/jiuwen') / name)
    for name in ['runtime', 'controller-attempts', 'factory/ccstore/releases',
                 'factory/ccstore/attempts', 'factory/sessions']:
        tree(mission / name, Path('evidence/jiuwen') / name)
    copy(root / 'development-cpu-mission-001-spec.json', 'evidence/campaign-spec.json')
    for path in sorted((root / 'results').glob('development-*')):
        if path.is_file():
            copy(path, Path('evidence/verification') / path.name)
    for name in ['final-role-images.json', 'agent-final-standalone-smoke.log']:
        copy(root / 'results' / name, Path('evidence/runtime') / name)
    (stage / 'README.md').write_text('''# Connected development handoff

Read source/docs/architecture/factory/CONNECTED-DEVELOPMENT-2026-11-16.md for outcomes and limitations. Run `python3 verify.py` before using this supplement. It is a source overlay for the retained cc-dgx-spark checkout, not a complete dependency environment; the separately exported ARM64 agent image supplies the exercised runtime. Keep the earlier handoffs for full source/build ancestry and model identities. Frozen mission runtimes differ intentionally from the final source; their manifests identify their actual bytes.

The live CPU mission published a report but timed out. GPU evidence includes failures and a later successful re-import, not four successful campaigns. No new speedup or quality acceptance is claimed. Source/native paths in retained receipts identify the original machine and must be rebound through a fresh operator task before new execution. Model weights, credentials and live SQLite databases are excluded. The generic numerical tools do not authenticate operator-supplied engine identities.

Cleanup after copying and verification: exported archives and copied staging trees are optional removable duplicates. Keep raw evidence until RSI imports it. Do not prune shared Docker caches/images, user environments, source checkouts or model weights. No global dependency installation was required. All four owned diagnostic containers were removed; shared services were left alone.
''')
    state = {'git_head': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
             'git_status': subprocess.check_output(['git', '-C', str(REPO), 'status', '--porcelain'], text=True),
             'scope': 'MANIFEST pins exported bytes; source overlay requires the compatible base checkout.'}
    (stage / 'SOURCE-STATE.json').write_text(json.dumps(state, indent=2) + '\n')
    (stage / 'verify.py').write_text(VERIFY)
    manifest = {str(p.relative_to(stage)): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    subprocess.run([sys.executable, str(stage / 'verify.py')], check=True)
    archive = out / 'connected-development.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(stage, arcname=stage.name)
    (out / (archive.name + '.sha256')).write_text(sha(archive) + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'files': len(manifest), 'sha256': sha(archive)}))


if __name__ == '__main__':
    main()
