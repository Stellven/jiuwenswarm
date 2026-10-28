"""Offline image-build rebuild using the exact installed dependency environment.

Run only in a derived image, with public frozen inputs at the fixed build root.
It never starts the app, reads its volumes or invokes a model.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile

BUILD = Path('/run/ai4r-code-build')
PACKAGE = Path('/opt/venv/lib/python3.12/site-packages/jiuwenswarm')
IDENTITY = Path('/usr/local/share/ai4r-build-identity.json')
TUI = PACKAGE.parent / 'jiuwenswarm_tui'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def relative(name):
    path = PurePosixPath(name)
    need(isinstance(name, str) and name and name != '.' and '\\' not in name and ':' not in name
         and not path.is_absolute() and '..' not in path.parts and path.as_posix() == name,
         'UNSAFE_PUBLIC_BUILD_PATH')
    return path


def checked_manifest(raw):
    value = json.loads(raw)
    need(value.get('schema') == 'ai4r-installed-build:2'
         and sha(encoded({k: v for k, v in value.items() if k != 'build_id'})) == value['build_id'],
         'INSTALLED_BUILD_IDENTITY_DIFFERS')
    return value


def inventory(root):
    rows, links = [], []
    for path in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).as_posix()):
        if path.suffix == '.pyc' or '__pycache__' in path.parts:
            continue
        name = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            need(not Path(target).is_absolute() and path.resolve(strict=True).is_relative_to(root),
                 'INSTALLED_LINK_ESCAPE')
            links.append({'path': name, 'target': target})
        elif stat.S_ISREG(info.st_mode):
            need(info.st_nlink == 1, 'INSTALLED_HARDLINK')
            raw = path.read_bytes()
            rows.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw)})
        else:
            need(stat.S_ISDIR(info.st_mode), 'INSTALLED_SPECIAL_FILE')
    return {'files': rows, 'links': links}


def dependencies():
    return sorted(({'name': d.metadata['Name'], 'version': d.version}
                   for d in importlib.metadata.distributions()), key=lambda row: row['name'].lower())


def verify(value):
    for root, wanted in ((PACKAGE, value), (TUI, value['components']['jiuwenswarm_tui'])):
        actual = inventory(root)
        for kind in ('files', 'links'):
            need(actual[kind] == sorted(wanted[kind], key=lambda row: row['path']),
                 'INSTALLED_BYTES_DIFFER:' + root.name)
    need(dependencies() == value['dependencies'], 'INSTALLED_DEPENDENCIES_DIFFER')


def verify_frontend(root, expected):
    wanted = sorted(({'path': row['path'], 'bytes': row['size'], 'sha256': row['sha256']}
                     for row in expected), key=lambda row: row['path'])
    need(root.is_dir() and inventory(root) == {'files': wanted, 'links': []},
         'INSTALLED_FRONTEND_DIFFERS_FROM_FROZEN_BUILD')


def extract_public(archive_path, destination, expected):
    """Extract an exact regular-file inventory; refuse every link and extra path."""
    need(not destination.exists(), 'NEW_PUBLIC_BUILD_DIRECTORY_REQUIRED')
    index = {row['path']: row for row in expected}
    need(len(index) == len(expected) and 0 < len(index) <= 20000, 'FINITE_PUBLIC_INVENTORY_REQUIRED')
    seen = set(); total = 0
    with tarfile.open(archive_path, 'r') as archive:
        for member in archive:
            name = relative(member.name).as_posix()
            need(member.isfile() and name in index and name not in seen, 'UNLISTED_OR_NONREGULAR_BUILD_INPUT')
            row = index[name]
            need(member.size == row['size'] and member.size <= 128 * 1024 * 1024,
                 'PUBLIC_BUILD_SIZE_DIFFERS')
            raw = archive.extractfile(member).read()
            need(sha(raw) == row['sha256'], 'PUBLIC_BUILD_BYTES_DIFFER')
            seen.add(name); total += len(raw)
            need(total <= 512 * 1024 * 1024, 'PUBLIC_BUILD_SIZE_EXCEEDED')
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            with target.open('xb') as stream:
                stream.write(raw)
            target.chmod(0o755 if target.suffix == '.sh' else 0o644)
    need(seen == set(index), 'PUBLIC_BUILD_INPUT_MISSING')


def run():
    need(os.name == 'posix' and os.geteuid() == 0 and Path.cwd() == Path('/tmp'),
         'ISOLATED_ROOT_IMAGE_BUILD_REQUIRED')
    need(BUILD.is_dir() and not BUILD.is_symlink() and BUILD.stat().st_uid == 0,
         'FIXED_ROOT_BUILD_INPUT_REQUIRED')
    plan = json.loads((BUILD / 'plan.json').read_bytes())
    need(set(plan) == {'schema', 'base_manifest_sha256', 'source_archive_sha256',
        'source_files', 'frontend_archive_sha256', 'frontend_files', 'installer_sha256'},
        'CLOSED_IMAGE_REBUILD_PLAN_REQUIRED')
    need(plan['schema'] == 'ai4r-installed-app-rebuild:1'
         and sha(Path(__file__).read_bytes()) == plan['installer_sha256'], 'IMAGE_REBUILD_PLAN_DIFFERS')
    raw = IDENTITY.read_bytes()
    need(sha(raw) == plan['base_manifest_sha256']
         and checked_manifest(raw) == checked_manifest((BUILD/'base-installed-build.json').read_bytes()),
         'INHERITED_BUILD_DIFFERS')
    base = checked_manifest(raw); verify(base)
    for name, key in (('source.tar', 'source_archive_sha256'), ('frontend.tar', 'frontend_archive_sha256')):
        need(sha((BUILD/name).read_bytes()) == plan[key], 'PUBLIC_ARCHIVE_CHANGED')
    source = BUILD/'source'
    extract_public(BUILD/'source.tar', source, plan['source_files'])
    need(sha((source/'uv.lock').read_bytes()) == base['uv_lock_sha256']
         and sha((source/'pyproject.toml').read_bytes()) == base['pyproject_sha256'],
         'DEPENDENCY_INPUT_CHANGE_REQUIRES_FULL_BUILD')
    frontend = source/'jiuwenswarm/channels/web/frontend/dist'
    extract_public(BUILD/'frontend.tar', frontend, plan['frontend_files'])
    # These generated, locked TUI assets are unchanged by this app source build.
    for name in ('dist', 'node_modules'):
        previous = PACKAGE/'channels/tui/frontend'/name
        target = source/'jiuwenswarm/channels/tui/frontend'/name
        need(previous.is_dir() and not target.exists(), 'INHERITED_TUI_ASSETS_REQUIRED')
        shutil.copytree(previous, target, symlinks=True)
    wheelhouse = BUILD/'wheels'; wheelhouse.mkdir()
    subprocess.run(['/usr/local/bin/uv', 'build', '--wheel', '--python', '/opt/venv/bin/python',
        '--offline', '--no-cache', '--no-build-isolation', '--out-dir', str(wheelhouse), str(source)],
        check=True, cwd=source)
    wheels = list(wheelhouse.glob('workswarm-*.whl'))
    need(len(wheels) == 1, 'EXACT_REBUILT_WHEEL_REQUIRED')
    wheel_sha = sha(wheels[0].read_bytes())
    subprocess.run(['/usr/local/bin/uv', 'pip', 'install', '--python', '/opt/venv/bin/python',
        '--offline', '--no-deps', '--reinstall', str(wheels[0])], check=True)
    need(dependencies() == base['dependencies'], 'REBUILD_CHANGED_DEPENDENCIES')
    verify_frontend(PACKAGE/'channels/web/frontend/dist', plan['frontend_files'])
    subprocess.run(['/opt/venv/bin/python', '-I', '-B', str(source/'deploy/m1/build_identity.py'),
        '--lock', str(source/'uv.lock'), '--project', str(source/'pyproject.toml'),
        '--source', str(source/'jiuwenswarm'), '--tui-source', str(source/'packages/jiuwenswarm-tui/jiuwenswarm_tui'),
        '--output', str(IDENTITY)], check=True)
    current = checked_manifest(IDENTITY.read_bytes()); verify(current)
    need(current['components'] == base['components'] and current['links'] == base['links'],
         'REBUILD_CHANGED_TUI_OR_LINK_CLOSURE')
    receipt = {'schema': 'ai4r-installed-app-rebuild-complete:1', 'base_build_id': base['build_id'],
        'build_id': current['build_id'], 'plan_sha256': sha(encoded(plan)),
        'source_archive_sha256': plan['source_archive_sha256'],
        'frontend_archive_sha256': plan['frontend_archive_sha256'], 'wheel_sha256': wheel_sha,
        'installed_files': len(current['files']), 'dependencies_unchanged': True,
        'tui_unchanged': True, 'model_calls': 0}
    Path('/usr/local/share/ai4r-rsi-ui-build.json').write_bytes(encoded(receipt))
    # Fixed build-only directory, checked again before removing public inputs.
    need(BUILD == Path('/run/ai4r-code-build') and not BUILD.is_symlink()
         and not BUILD.is_mount() and BUILD.stat().st_uid == 0, 'BUILD_CLEANUP_BOUNDARY_DIFFERS')
    shutil.rmtree(BUILD)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    run()
