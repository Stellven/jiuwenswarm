"""Refresh an inherited installed-build:2 after the finite RSI source overlay.

This build-time stdlib helper neither installs dependencies nor imports the
application. The inherited self-hashed manifest is the immutable comparison
baseline; only the four declared package subtrees may differ.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile


PREFIXES = ('research_rsi/', 'research_records/', 'research_contracts/', 'research/contracts/')
FIELDS = {'schema', 'files', 'links', 'dependencies', 'components', 'uv_lock_sha256', 'pyproject_sha256', 'build_id'}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            _need(key not in value, 'DUPLICATE_MANIFEST_FIELD')
            value[key] = item
        return value
    def constant(_):
        raise ValueError('NONFINITE_MANIFEST_VALUE')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def _relative(name):
    _need(isinstance(name, str) and bool(name), 'INVALID_INSTALLED_PATH')
    part = PurePosixPath(name)
    _need(not part.is_absolute() and '..' not in part.parts and '\\' not in name
          and ':' not in name and part.as_posix() == name and name != '.', 'INVALID_INSTALLED_PATH')
    return name


def _inventory(root):
    root = Path(root)
    _need(root.is_absolute() and root.is_dir() and not root.is_symlink(), 'INSTALLED_PACKAGE_ROOT_UNAVAILABLE')
    root = root.resolve(strict=True)
    paths = []
    def walk_error(error):
        raise error
    for directory, directories, files in os.walk(root, followlinks=False, onerror=walk_error):
        paths.extend(Path(directory) / name for name in directories + files)
        _need(len(paths) <= 20000, 'INSTALLED_INVENTORY_BOUND_EXCEEDED')
    files, links, total = [], [], 0
    for path in sorted(paths):
        relative = path.relative_to(root)
        if path.suffix == '.pyc' or '__pycache__' in relative.parts:
            continue
        name = relative.as_posix()
        meta = path.lstat()
        if stat.S_ISLNK(meta.st_mode):
            target = os.readlink(path)
            _need(not Path(target).is_absolute(), 'INSTALLED_LINK_ESCAPES_PACKAGE')
            try:
                confined = path.resolve(strict=True).is_relative_to(root)
            except (OSError, RuntimeError):
                confined = False
            _need(confined, 'INSTALLED_LINK_ESCAPES_PACKAGE')
            links.append({'path': name, 'target': target})
        elif stat.S_ISDIR(meta.st_mode):
            continue
        else:
            _need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, 'INSTALLED_ASSET_NOT_SINGLE_REGULAR_FILE')
            _need(path.name not in {'auth.json', 'credentials.json', 'secrets.json', '.env'}
                  and not (path.name.startswith('.env.') and path.name != '.env.template'), 'CREDENTIAL_FILE_IN_IMAGE_PACKAGE')
            raw = path.read_bytes(); total += len(raw)
            _need(total <= 128 * 1024 * 1024, 'INSTALLED_INVENTORY_BOUND_EXCEEDED')
            files.append({'path': name, 'bytes': len(raw), 'sha256': _sha(raw)})
    _need(bool(files), 'INSTALLED_PACKAGE_INVENTORY_EMPTY')
    return {'files': files, 'links': links}


def _validate_inventory(value):
    _need(isinstance(value, dict) and set(value) == {'files', 'links'}, 'INVALID_BASE_INVENTORY')
    _need(isinstance(value['files'], list) and value['files'] and isinstance(value['links'], list), 'INVALID_BASE_INVENTORY')
    seen = set()
    for row in value['files']:
        _need(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'}, 'INVALID_BASE_FILE')
        name = _relative(row['path'])
        _need(name not in seen and type(row['bytes']) is int and row['bytes'] >= 0 and _digest(row['sha256']), 'INVALID_BASE_FILE')
        seen.add(name)
    for row in value['links']:
        _need(isinstance(row, dict) and set(row) == {'path', 'target'}, 'INVALID_BASE_LINK')
        name = _relative(row['path'])
        _need(name not in seen and isinstance(row['target'], str) and row['target']
              and not PurePosixPath(row['target']).is_absolute(), 'INVALID_BASE_LINK')
        seen.add(name)


def _dependencies():
    return sorted(({'name': distribution.metadata['Name'], 'version': distribution.version}
        for distribution in importlib.metadata.distributions()), key=lambda row: row['name'].lower())


def _roots(package_root):
    if package_root is None:
        package = Path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm'))
        tui = Path(importlib.metadata.distribution('workswarm-tui').locate_file('jiuwenswarm_tui'))
    else:
        package = Path(package_root)
        tui = package.parent / 'jiuwenswarm_tui'
    return package, tui


def normalize_overlay_permissions(roots=None):
    """Normalize COPY modes from Windows contexts, only in the four overlays.

    This is a Linux root image-build step. It never repairs inherited code
    outside those overlays or follows a symlink/hardlink to another asset.
    Validate the complete selection before changing its permission bits.
    """
    _need(os.name=='posix' and os.geteuid()==0,'ROOT_IMAGE_BUILD_REQUIRED')
    if roots is None:
        package,_=_roots(None)
        roots=(package,Path('/opt/ai4r/jiuwenswarm'))
    selected=[];seen=set()
    for root in roots:
        root=Path(root)
        _need(root.is_absolute() and root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)),
            'INSTALLED_PACKAGE_ROOT_UNAVAILABLE')
        for prefix in PREFIXES:
            base=root/prefix.rstrip('/')
            _need(base.is_dir() and not base.is_symlink(),'OVERLAY_SUBTREE_UNAVAILABLE')
            for path in (base,*base.rglob('*')):
                _need(not path.is_symlink(),'OVERLAY_PERMISSION_LINK_REJECTED')
                meta=path.lstat()
                _need(meta.st_uid==0 and (stat.S_ISDIR(meta.st_mode) or
                    stat.S_ISREG(meta.st_mode) and meta.st_nlink==1),'OVERLAY_PERMISSION_CUSTODY_REJECTED')
                if path not in seen:
                    selected.append((path,0o755 if stat.S_ISDIR(meta.st_mode) else 0o644));seen.add(path)
                _need(len(selected)<=20000,'OVERLAY_PERMISSION_BOUND_EXCEEDED')
    for path,mode in selected:os.chmod(path,mode)
    return len(selected)


def refresh_manifest(*, lock, project, manifest, package_root=None):
    """Validate the complete inherited boundary, then replace its identity once."""
    manifest = Path(manifest)
    _need(manifest.is_file() and not manifest.is_symlink(), 'INHERITED_MANIFEST_UNAVAILABLE')
    metadata = manifest.stat()
    _need(metadata.st_nlink == 1 and metadata.st_size <= 16 * 1024 * 1024, 'INHERITED_MANIFEST_UNAVAILABLE')
    base = _json(manifest.read_bytes())
    _need(isinstance(base, dict) and set(base) == FIELDS and base['schema'] == 'ai4r-installed-build:2', 'UNKNOWN_INHERITED_BUILD_MANIFEST')
    payload = {key: value for key, value in base.items() if key != 'build_id'}
    _need(_digest(base['build_id']) and _sha(_encoded(payload)) == base['build_id'], 'INHERITED_BUILD_ID_CHANGED')
    _need(_digest(base['uv_lock_sha256']) and _sha(Path(lock).read_bytes()) == base['uv_lock_sha256'], 'INHERITED_LOCK_INPUT_CHANGED')
    _need(_digest(base['pyproject_sha256']) and _sha(Path(project).read_bytes()) == base['pyproject_sha256'], 'INHERITED_PROJECT_INPUT_CHANGED')
    _validate_inventory({'files': base['files'], 'links': base['links']})
    _need(isinstance(base['components'], dict) and set(base['components']) == {'jiuwenswarm_tui'}, 'UNKNOWN_INHERITED_COMPONENT')
    _validate_inventory(base['components']['jiuwenswarm_tui'])
    dependencies = base['dependencies']
    _need(isinstance(dependencies, list) and dependencies and all(isinstance(row, dict)
          and set(row) == {'name', 'version'} and isinstance(row['name'], str) and row['name']
          and isinstance(row['version'], str) and row['version'] for row in dependencies), 'INVALID_INHERITED_DEPENDENCIES')
    _need(dependencies == _dependencies(), 'INSTALLED_DEPENDENCIES_CHANGED')
    package, tui = _roots(package_root)
    current = _inventory(package)
    _need(_inventory(tui) == base['components']['jiuwenswarm_tui'], 'INSTALLED_TUI_CHANGED')
    previous = {row['path']: ('file', row) for row in base['files']}
    previous.update({row['path']: ('link', row) for row in base['links']})
    installed = {row['path']: ('file', row) for row in current['files']}
    installed.update({row['path']: ('link', row) for row in current['links']})
    changed = sorted(name for name in previous.keys() | installed.keys() if previous.get(name) != installed.get(name))
    for name in changed:
        _need(any(name.startswith(prefix) for prefix in PREFIXES), 'INSTALLED_CHANGE_OUTSIDE_RSI_PREFIXES:' + name)
    payload.update(current)
    updated = dict(payload, build_id=_sha(_encoded(payload)))
    raw = (json.dumps(updated, indent=2, allow_nan=False) + '\n').encode('utf8')
    descriptor, temporary = tempfile.mkstemp(prefix='.rsi-build-', dir=manifest.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            if hasattr(os, 'fchmod'): os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, manifest)
        if hasattr(os, 'O_DIRECTORY'):
            directory = os.open(manifest.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'base_build_id': base['build_id'], 'build_id': updated['build_id'], 'changed_paths': changed,
        'installed_files': len(current['files'])}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--package-root')
    parser.add_argument('--normalize-overlay-permissions',action='store_true')
    args = parser.parse_args(argv)
    if args.normalize_overlay_permissions:
        normalize_overlay_permissions(None if args.package_root is None else (Path(args.package_root),))
    print(json.dumps(refresh_manifest(lock=args.lock, project=args.project,
        manifest=args.manifest, package_root=args.package_root), sort_keys=True))


if __name__ == '__main__':
    main()
