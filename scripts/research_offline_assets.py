"""Stdlib audit of delivered native wheels (M1-I029 phase A).

This observes package representation only. It does not certify a complete
dependency wheelhouse, a clean installation, or operational research readiness.
"""
from __future__ import annotations

import argparse
import base64
import configparser
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
import zipfile


class AssetError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized_name(value):
    return re.sub(r'[-_.]+', '-', value).lower()


def normalized_version(value):
    return re.sub(r'[.-]?(alpha|beta)[.-]?(\d+)', lambda m: {'alpha': 'a', 'beta': 'b'}[m[1]] + m[2], value)


def relative(value):
    p = PurePosixPath(value)
    if not value or '\\' in value or ':' in value or p.is_absolute() or '..' in p.parts or p.as_posix() != value or any(ord(c) < 32 for c in value):
        raise AssetError('UNSAFE_WHEEL_PATH')
    return value


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**3:
        raise AssetError('WHEEL_CUSTODY')
    return path.read_bytes()


def _contents(path, *, general=False):
    raw = _read(path)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries = z.infolist()
        if len(entries) > 100000 or sum(e.file_size for e in entries) > 2 * 1024**3:
            raise AssetError('WHEEL_BOUND')
        files = {}
        directories = set()
        seen = set()
        for item in entries:
            if item.filename in seen:
                raise AssetError('DUPLICATE_WHEEL_MEMBER')
            seen.add(item.filename)
            mode = item.external_attr >> 16
            if item.flag_bits & 1 or item.file_size > 512 * 1024**2:
                raise AssetError('WHEEL_MEMBER_BOUND')
            if general and item.is_dir():
                name = relative(item.filename[:-1])
                if name in files:
                    raise AssetError('WHEEL_PATH_COLLISION')
                if stat.S_IFMT(mode) not in (0, stat.S_IFDIR) or item.file_size or z.read(item) != b'':
                    raise AssetError('WHEEL_DIRECTORY_MEMBER')
                directories.add(name)
                continue
            name = relative(item.filename)
            if name in directories:
                raise AssetError('WHEEL_PATH_COLLISION')
            if stat.S_ISLNK(mode) or item.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise AssetError('WHEEL_LINK_OR_SPECIAL_MEMBER')
            files[name] = z.read(item)
    if general:
        for name in files.keys() | directories:
            if any(parent.as_posix() in files for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
                raise AssetError('WHEEL_PATH_COLLISION')
        roots = {name.split('/')[0] for name in files.keys() | directories if name.split('/')[0].endswith('.dist-info')}
        if len(roots) != 1:
            raise AssetError('WHEEL_DIST_INFO')
        root = next(iter(roots)) + '/'
        records = [root + 'RECORD'] if root + 'RECORD' in files else []
        metadata = [root + 'METADATA'] if root + 'METADATA' in files else []
    else:
        records = [name for name in files if name.endswith('.dist-info/RECORD')]
        metadata = [name for name in files if name.endswith('.dist-info/METADATA')]
    if len(records) != 1 or len(metadata) != 1 or records[0].rsplit('/', 1)[0] != metadata[0].rsplit('/', 1)[0]:
        raise AssetError('WHEEL_DIST_INFO')
    rows = list(csv.reader(io.StringIO(files[records[0]].decode('utf-8'))))
    if any(len(row) != 3 for row in rows) or len({row[0] for row in rows}) != len(rows) or {row[0] for row in rows} != set(files):
        raise AssetError('RECORD_CLOSURE')
    for name, digest, size in rows:
        if name == records[0]:
            if digest or size:
                raise AssetError('RECORD_SELF_HASH')
            continue
        expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(files[name]).digest()).rstrip(b'=').decode()
        if digest != expected or size != str(len(files[name])):
            raise AssetError('RECORD_HASH_OR_SIZE')
    return raw, files, metadata[0]


def audit_wheel(path, *, expected_name, expected_version=None):
    """Strict delivered-native wheel audit; nested metadata/directories remain refused."""
    return _audit_wheel(path, expected_name=expected_name, expected_version=expected_version)


def audit_distribution(path, *, expected_name, expected_version=None):
    """Audit an original distribution using its sole top-level dist-info authority.

    Nested vendor metadata is ordinary root-RECORD-covered payload. Canonical,
    empty directory entries are checked but are not regular RECORD members.
    Both filename and WHEEL tag sets are retained; their equality diagnostic
    does not establish target eligibility. Installation callers must check
    each set independently against the actual target. Original archive bytes
    are never rewritten.
    """
    return _audit_wheel(path, expected_name=expected_name, expected_version=expected_version, general=True)


def _expanded_tags(values):
    result = set()
    for value in values:
        parts = value.split('-')
        if len(parts) != 3 or any(not re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*', part) for part in parts):
            raise AssetError('WHEEL_FILENAME_TAG_MISMATCH')
        result.update(p + '-' + abi + '-' + platform for p in parts[0].split('.')
                      for abi in parts[1].split('.') for platform in parts[2].split('.'))
    return result


def _general_identity(path, prefix, metadata, wheel):
    """Compare original names canonically while preserving version/build identity.

    PyPA's wheel escaping rules require consumers to support historical dots
    and uppercase letters. Name normalization changes comparison only; neither
    the archive nor its metadata is rewritten. Each compressed tag set is
    expanded independently. An upstream declaration mismatch remains visible
    rather than broadening the filename's target eligibility.
    """
    name, version = metadata['Name'], metadata['Version']
    valid_name = r'[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?'
    root_name, separator, root_version = prefix[:-len('.dist-info/')].rpartition('-')
    filename = Path(path).name
    parts = filename[:-4].split('-') if filename.endswith('.whl') else []
    if (not re.fullmatch(valid_name, name) or not separator
            or not re.fullmatch(valid_name, root_name)
            or normalized_name(root_name) != normalized_name(name) or root_version != version
            or len(parts) not in (5, 6) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9._]*[A-Za-z0-9])?', parts[0])
            or normalized_name(parts[0]) != normalized_name(name) or parts[1] != version):
        raise AssetError('WHEEL_FILENAME_OR_DIST_INFO_IDENTITY')
    build = parts[2] if len(parts) == 6 else None
    if ((build is not None and not re.fullmatch(r'[0-9][A-Za-z0-9_]*', build))
            or wheel.get_all('Build', []) != ([] if build is None else [build])):
        raise AssetError('WHEEL_FILENAME_BUILD_MISMATCH')
    filename_tags = _expanded_tags(['-'.join(parts[-3:])])
    declared_tags = _expanded_tags(wheel.get_all('Tag'))
    return sorted(filename_tags), sorted(declared_tags)


def _audit_wheel(path, *, expected_name, expected_version=None, general=False):
    raw, files, metadata_path = _contents(path, general=general)
    m = BytesParser().parsebytes(files[metadata_path])
    if len(m.get_all('Name', [])) != 1 or normalized_name(m['Name']) != normalized_name(expected_name):
        raise AssetError('METADATA_NAME')
    if len(m.get_all('Version', [])) != 1 or (expected_version is not None and m['Version'] != normalized_version(expected_version)):
        raise AssetError('METADATA_VERSION')
    prefix = metadata_path.rsplit('/', 1)[0] + '/'
    stem = normalized_name(m['Name']).replace('-', '_') + '-' + m['Version']
    if not general and (prefix != stem + '.dist-info/' or not Path(path).name.startswith(stem + '-')):
        raise AssetError('WHEEL_FILENAME_OR_DIST_INFO_IDENTITY')
    w = BytesParser().parsebytes(files.get(prefix + 'WHEEL', b''))
    if w.get('Wheel-Version') != '1.0' or not w.get_all('Tag'):
        raise AssetError('WHEEL_TAG')
    if general:
        filename_tags, wheel_tags = _general_identity(path, prefix, m, w)
    else:
        tags = Path(path).name[:-4].rsplit('-', 3)[-3:]
        if len(tags) != 3 or set(w.get_all('Tag')) != {p + '-' + abi + '-' + platform for p in tags[0].split('.') for abi in tags[1].split('.') for platform in tags[2].split('.')}:
            raise AssetError('WHEEL_FILENAME_TAG_MISMATCH')
        wheel_tags = w.get_all('Tag')
    entries = {}
    if prefix + 'entry_points.txt' in files:
        parser = configparser.ConfigParser(interpolation=None); parser.optionxform = str
        parser.read_string(files[prefix + 'entry_points.txt'].decode())
        entries = dict(parser['console_scripts']) if parser.has_section('console_scripts') else {}
    result = {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw),
        'metadata': {'name': m['Name'], 'version': m['Version'], 'requires_dist': m.get_all('Requires-Dist', []),
                     'requires_python': m.get('Requires-Python'), 'provides_extra': m.get_all('Provides-Extra', []), 'console_scripts': entries},
        'wheel_tags': wheel_tags,
        'members': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in sorted(files.items())}}
    if general:
        result.update(filename_tags=filename_tags,
                      tag_consistency='equal' if filename_tags == wheel_tags else 'mismatch')
    return result


def _requirement(value):
    """Normalize only the PEP508 forms actually present in the frozen project.

    Specifier ordering and the project's beta spelling are presentation details.
    URL, operator and version semantics are retained; unsupported marker forms
    fail closed rather than being silently discarded.
    """
    match = re.fullmatch(r'\s*([A-Za-z0-9_.-]+)(?:\[([^]]+)\])?\s*(.*?)\s*', value)
    if not match or ';' in match[3]:
        raise AssetError('UNSUPPORTED_REQUIREMENT_FORM')
    extras = '[' + ','.join(sorted(normalized_name(x.strip()) for x in match[2].split(','))) + ']' if match[2] else ''
    tail = match[3]
    if tail.startswith('@'):
        tail = '@' + tail[1:].strip()
    else:
        tail = ','.join(sorted(normalized_version(re.sub(r'\s+', '', x)) for x in tail.strip('()').split(',') if x))
    return normalized_name(match[1]) + extras + tail


def _metadata_requirement(value):
    parts = value.split(';')
    if len(parts) == 1:
        return None, _requirement(parts[0])
    marker = re.fullmatch(r'\s*extra\s*==\s*[\'"]([a-zA-Z0-9_.-]+)[\'"]\s*', parts[1]) if len(parts) == 2 else None
    if marker is None:
        raise AssetError('UNSUPPORTED_REQUIREMENT_MARKER')
    return normalized_name(marker[1]), _requirement(parts[0])


def audit_native(path, project, *, generated_root=None):
    p = project['project']
    result = audit_wheel(path, expected_name=p['name'], expected_version=p['version'])
    actual = [_metadata_requirement(v) for v in result['metadata']['requires_dist']]
    expected = [(None, _requirement(v)) for v in p.get('dependencies', [])]
    for extra, requirements in p.get('optional-dependencies', {}).items():
        expected.extend((normalized_name(extra), _requirement(v)) for v in requirements)
    if sorted(actual, key=repr) != sorted(expected, key=repr) or sorted(map(normalized_name, result['metadata']['provides_extra'])) != sorted(map(normalized_name, p.get('optional-dependencies', {}))):
        raise AssetError('NATIVE_DEPENDENCIES_CHANGED')
    normalize_spec = lambda s: sorted(re.sub(r'\s+', '', s or '').split(','))
    if normalize_spec(result['metadata']['requires_python']) != normalize_spec(p.get('requires-python')):
        raise AssetError('NATIVE_REQUIRES_PYTHON_CHANGED')
    if result['metadata']['console_scripts'] != p.get('scripts', {}):
        raise AssetError('NATIVE_ENTRYPOINTS_CHANGED')
    prefix = 'jiuwenswarm/channels/tui/frontend/'
    required = ('dist/index.js', 'package.json', 'node_modules/.package-lock.json',
                'node_modules/@mariozechner/pi-tui/dist/index.js')
    if any(prefix + name not in result['members'] for name in required):
        raise AssetError('TUI_ASSETS_MISSING')
    binaries = [n for n in result['members'] if n.startswith(prefix + 'node_modules/koffi/') and n.endswith('.node')]
    if not any('/linux_x64/' in n for n in binaries) or not any('/linux_arm64/' in n for n in binaries):
        raise AssetError('TUI_PLATFORM_ASSETS_MISSING')
    result['native_tui_binaries'] = binaries
    result['generated_files'] = None
    if generated_root is not None:
        root = Path(generated_root)
        if not root.is_dir() or root.is_symlink():
            raise AssetError('GENERATED_ROOT_MISSING')
        names = set(); resolved_links = []
        for section in ('dist', 'node_modules'):
            for item in (root / section).rglob('*'):
                if item.is_dir():
                    if item.is_symlink():
                        raise AssetError('GENERATED_DIRECTORY_LINK')
                    continue
                if not item.resolve().is_relative_to(root.resolve()) or not item.is_file():
                    raise AssetError('GENERATED_LINK_OR_SPECIAL')
                if item.is_symlink():
                    name = item.relative_to(root).as_posix()
                    if not name.startswith('node_modules/.bin/'):
                        raise AssetError('GENERATED_FILE_LINK')
                    resolved_links.append({'path': name, 'target': item.readlink().as_posix(), 'sha256': sha(item.read_bytes())})
                names.add(item.relative_to(root).as_posix())
        names.add('package.json')
        for name in names:
            data = (root / name).read_bytes()
            if result['members'].get(prefix + name) != {'sha256': sha(data), 'bytes': len(data)}:
                raise AssetError('GENERATED_BYTES_MISSING_OR_CHANGED:' + name)
        delivered = {n[len(prefix):] for n in result['members'] if n.startswith(prefix + 'dist/') or n.startswith(prefix + 'node_modules/') or n == prefix + 'package.json'}
        if delivered != names:
            raise AssetError('GENERATED_EXTRA_MEMBER')
        result['generated_files'] = len(names)
        result['resolved_npm_bin_links'] = sorted(resolved_links, key=lambda x: x['path'])
    return result


def audit_bundle(wheelhouse, project_file, lock_file, *, generated_root=None):
    root = Path(wheelhouse)
    project_raw = _read(project_file); lock_raw = _read(lock_file)
    project = tomllib.loads(project_raw.decode('utf-8')); version = normalized_version(project['project']['version'])
    wheels = list(root.glob('*.whl'))
    found = {}
    for path in wheels:
        _, files, metadata_path = _contents(path)
        name = normalized_name(BytesParser().parsebytes(files[metadata_path])['Name'])
        if name in found or name not in ('workswarm', 'workswarm-tui', 'jiuwenswarm'):
            raise AssetError('DELIVERED_WHEEL_CLOSURE')
        found[name] = path
    if set(found) != {'workswarm', 'workswarm-tui', 'jiuwenswarm'}:
        raise AssetError('DELIVERED_WHEEL_CLOSURE')
    native = audit_native(found['workswarm'], project, generated_root=generated_root)
    tui = audit_wheel(found['workswarm-tui'], expected_name='workswarm-tui', expected_version=version)
    if 'jiuwenswarm_tui/app.py' not in tui['members'] or tui['metadata']['console_scripts'].get('jiuwenswarm-tui') != 'jiuwenswarm_tui.app:main':
        raise AssetError('TUI_LAUNCHER_MISSING')
    alias = audit_wheel(found['jiuwenswarm'], expected_name='jiuwenswarm', expected_version=version)
    if alias['metadata']['requires_dist'] != ['workswarm[codex,tui]==' + version] or alias['metadata']['console_scripts'] or any('.dist-info/' not in name for name in alias['members']):
        raise AssetError('COMPATIBILITY_METADATA_CHANGED')
    return {'schema': 'ai4r-delivered-wheel-assets:1', 'pyproject_sha256': sha(project_raw), 'uv_lock_sha256': sha(lock_raw),
        'wheels': {'workswarm': native, 'workswarm-tui': tui, 'jiuwenswarm': alias},
        'scope': 'delivered package representation only', 'complete_offline_dependency_closure': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheelhouse', required=True); parser.add_argument('--project', required=True)
    parser.add_argument('--lock', required=True); parser.add_argument('--generated-root'); parser.add_argument('--output', required=True)
    a = parser.parse_args()
    result = audit_bundle(a.wheelhouse, a.project, a.lock, generated_root=a.generated_root)
    output = Path(a.output)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'schema': result['schema'], 'output': str(output), 'sha256': sha(output.read_bytes()),
                      'generated_files': result['wheels']['workswarm']['generated_files'], 'complete_offline_dependency_closure': False}))


if __name__ == '__main__':
    main()
