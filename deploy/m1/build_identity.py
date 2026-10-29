"""Image-build identity over installed native code/assets and frozen inputs."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source')
    parser.add_argument('--tui-source', required=True)
    args = parser.parse_args()
    package = Path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm')).resolve()
    checked = 0
    if args.source:
        source = Path(args.source).resolve()
        for item in sorted(source.rglob('*')):
            if not item.is_file() or item.is_symlink() or item.suffix == '.pyc' or '__pycache__' in item.parts:
                continue
            relative = item.relative_to(source)
            # The independently deployed benchmark CLI is not part of the app.
            if relative.parts[0] == 'research_sidecar':
                continue
            installed = package / relative
            if installed.is_file():
                if item.read_bytes() != installed.read_bytes():
                    raise ValueError('INSTALLED_SOURCE_BYTES_DIFFER')
                checked += 1
            elif item.suffix == '.py' and all((source.joinpath(*relative.parts[:depth]) / '__init__.py').is_file() for depth in range(len(relative.parts))):
                raise ValueError('NATIVE_SOURCE_MISSING_FROM_WHEEL:' + relative.as_posix())
    files = []
    links = []
    for path in sorted(package.rglob('*')):
        if path.is_symlink():
            target = os.readlink(path)
            if Path(target).is_absolute() or not path.resolve(strict=True).is_relative_to(package):
                raise ValueError('INSTALLED_ASSET_SYMLINK_UNQUALIFIED')
            links.append({'path': path.relative_to(package).as_posix(), 'target': target})
            continue
        if not path.is_file() or path.suffix == '.pyc' or '__pycache__' in path.parts: continue
        if not path.resolve().is_relative_to(package):
            raise ValueError('INSTALLED_ASSET_SYMLINK_UNQUALIFIED')
        if path.name in {'auth.json', 'credentials.json', 'secrets.json', '.env'} or (path.name.startswith('.env.') and path.name != '.env.template'):
            raise ValueError('CREDENTIAL_FILE_IN_IMAGE_PACKAGE')
        raw = path.read_bytes()
        files.append({'path': path.relative_to(package).as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    dependencies = sorted(({'name': dist.metadata['Name'], 'version': dist.version} for dist in importlib.metadata.distributions()), key=lambda d: d['name'].lower())
    tui = Path(importlib.metadata.distribution('workswarm-tui').locate_file('jiuwenswarm_tui')).resolve()
    tui_source = Path(args.tui_source).resolve()
    for item in sorted(tui_source.rglob('*')):
        if not item.is_file() or item.suffix == '.pyc' or '__pycache__' in item.parts: continue
        target = tui / item.relative_to(tui_source)
        if item.is_symlink() or not target.is_file() or target.is_symlink() or item.read_bytes() != target.read_bytes():
            raise ValueError('INSTALLED_TUI_SOURCE_BYTES_DIFFER')
        checked += 1
    tui_files, tui_links = [], []
    for item in sorted(tui.rglob('*')):
        if item.suffix == '.pyc' or '__pycache__' in item.parts: continue
        relative = item.relative_to(tui).as_posix()
        if item.is_symlink():
            target = os.readlink(item)
            if Path(target).is_absolute() or not item.resolve(strict=True).is_relative_to(tui):
                raise ValueError('INSTALLED_TUI_SYMLINK_UNQUALIFIED')
            tui_links.append({'path': relative, 'target': target})
        elif item.is_file():
            raw = item.read_bytes()
            tui_files.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    payload = {'schema': 'ai4r-installed-build:2', 'files': files, 'links': links, 'dependencies': dependencies,
               'components': {'jiuwenswarm_tui': {'files': tui_files, 'links': tui_links}},
               'uv_lock_sha256': hashlib.sha256(Path(args.lock).read_bytes()).hexdigest(),
               'pyproject_sha256': hashlib.sha256(Path(args.project).read_bytes()).hexdigest()}
    payload['build_id'] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    Path(args.output).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'build_id': payload['build_id'], 'installed_files': len(files), 'source_files_checked': checked}))


if __name__ == '__main__': main()
