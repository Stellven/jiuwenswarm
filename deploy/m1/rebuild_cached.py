"""Rebuild project wheels offline, retaining only a complete installed runtime.

Current generated frontend assets and cached complete TUI assets are explicit
build inputs. Their hashes are captured by the installed identity; this mode
requires an unchanged dependency lock relative to the selected runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import subprocess


def call(*args):
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dependency-image-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', args.dependency_image_id):
        raise ValueError('PINNED_DEPENDENCY_IMAGE_ID_REQUIRED')
    root = Path('/build')
    installed_distributions = {dist.metadata['Name'].lower(): dist for dist in
                               importlib.metadata.distributions(path=['/opt/venv/lib/python3.12/site-packages'])}
    installed = Path(installed_distributions['workswarm'].locate_file('jiuwenswarm'))
    # Refuse dependency drift instead of silently updating the large closure.
    previous = json.loads(Path('/usr/local/share/ai4r-build-identity.json').read_bytes())
    if hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest() != previous['uv_lock_sha256']:
        raise ValueError('CACHED_DEPENDENCY_LOCK_CHANGED_USE_FULL_BUILD')
    assets = ['channels/web/frontend/dist', 'channels/tui/frontend/dist',
              'channels/tui/frontend/node_modules', 'channels/tui/frontend/package.json']
    for relative in assets:
        source, target = installed / relative, root / 'jiuwenswarm' / relative
        if relative == 'channels/web/frontend/dist' and (target / 'index.html').is_file():
            continue
        if not source.exists():
            raise ValueError('CACHED_PRODUCT_ASSET_MISSING:' + relative)
        if target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    wheelhouse = Path('/usr/local/share/ai4r-wheels')
    if wheelhouse.exists():
        shutil.rmtree(wheelhouse)
    wheelhouse.mkdir()
    for project in ('/build/packages/jiuwenswarm-tui', '/build'):
        call('uv', 'build', '--wheel', '--python', '/opt/venv/bin/python', '--offline',
             '--no-cache', '--no-build-isolation', '--out-dir', str(wheelhouse), project)
    # setuptools' local egg-info must not shadow the actual installed metadata.
    for path in root.rglob('*.egg-info'):
        if path.is_dir():
            shutil.rmtree(path)
    call('python', '/build/research_compat_wheel.py', '--output', str(wheelhouse), '--license', '/build/LICENSE')
    # Removing the previous installation before installing wheels prevents stale
    # files (including the old runner) surviving setuptools package exclusions.
    for name in ('workswarm', 'workswarm-tui', 'jiuwenswarm'):
        distribution = installed_distributions.get(name)
        if distribution is None:
            continue
        for item in distribution.files or ():
            path = Path(distribution.locate_file(item))
            if path.is_file() or path.is_symlink():
                path.unlink()
    if installed.exists():
        shutil.rmtree(installed)
    for wheel in wheelhouse.glob('*.whl'):
        call('uv', 'pip', 'install', '--python', '/opt/venv/bin/python', '--offline', '--no-deps', '--reinstall', str(wheel))
    for name in ('benchmark-runner', 'benchmark-referee', 'benchmark-report'):
        Path('/opt/venv/bin', name).unlink(missing_ok=True)
        Path('/usr/local/bin', name).unlink(missing_ok=True)
    Path('/usr/local/share/ai4r-wheel-assets.json').unlink(missing_ok=True)
    call('python', '/build/research_offline_assets.py', '--wheelhouse', str(wheelhouse),
         '--project', '/build/pyproject.toml', '--lock', '/build/uv.lock',
         '--generated-root', '/build/jiuwenswarm/channels/tui/frontend',
         '--output', '/usr/local/share/ai4r-wheel-assets.json')
    call('python', '/build/build_identity.py', '--lock', '/build/uv.lock', '--project', '/build/pyproject.toml',
         '--source', '/build/jiuwenswarm', '--tui-source', '/build/packages/jiuwenswarm-tui/jiuwenswarm_tui',
         '--output', '/usr/local/share/ai4r-build-identity.json')
    Path('/usr/local/share/ai4r-dependency-reuse.json').write_text(json.dumps({
        'schema': 'ai4r-cached-runtime-input:1', 'dependency_image_id': args.dependency_image_id,
        'assets': assets, 'frontend_origin': 'frozen-current-build-context',
        'uv_lock_sha256': previous['uv_lock_sha256']}, indent=2) + '\n')
    for directory in ('/build', '/root/.cache', '/opt/ai4r-wheels'):
        if Path(directory).exists():
            shutil.rmtree(directory)


if __name__ == '__main__':
    main()
