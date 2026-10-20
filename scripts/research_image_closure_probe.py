"""Independent stdlib-only installed closure observation for M1-I018.

Production execution reads one public, hash-bound input at a fixed mount. No
product import, installed .pth execution, provider call or credential is used.
Explicit fixture paths are test-only and their output cannot qualify an image.
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tomllib


GENERATED = {'channels/web/frontend/dist/': ('compiled_web', 'jiuwenswarm/channels/web/frontend/package-lock.json'),
             'channels/tui/frontend/dist/': ('compiled_tui', 'jiuwenswarm/channels/tui/frontend/package-lock.json'),
             'channels/tui/frontend/node_modules/': ('locked_tui_dependency', 'jiuwenswarm/channels/tui/frontend/package-lock.json')}
CHECKS = ('manifest_custody', 'manifest_identity', 'installed_native', 'installed_tui', 'original_source',
          'required_source_present', 'generated_context', 'lock_project', 'dependency_metadata')


class ClosureError(ValueError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_file(path, maximum=32 * 1024**2):
    path = Path(path)
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ClosureError('FILE_ALIAS')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 <= info.st_size <= maximum:
        raise ClosureError('FILE_CUSTODY_OR_BOUND')
    raw = path.read_bytes()
    after = path.lstat()
    if len(raw) != info.st_size or (info.st_ino, info.st_size, info.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise ClosureError('FILE_CHANGED')
    return raw


def relative(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or any(ord(c) < 32 for c in name):
        raise ClosureError('NONCANONICAL_COMPONENT_PATH')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != name:
        raise ClosureError('NONCANONICAL_COMPONENT_PATH')
    return name


def component(root, value):
    if not isinstance(value, dict) or set(value) != {'files', 'links'} or not value['files']:
        raise ClosureError('COMPONENT_STRUCTURE')
    if Path(root).is_symlink():
        raise ClosureError('COMPONENT_ROOT_ALIAS')
    root = Path(root).resolve(strict=True)
    expected, expected_links = {}, {}
    for row in value['files']:
        if set(row) != {'path', 'bytes', 'sha256'} or type(row['bytes']) is not int or row['bytes'] < 0:
            raise ClosureError('COMPONENT_ROW')
        name = relative(row['path'])
        if name in expected or name in expected_links:
            raise ClosureError('DUPLICATE_COMPONENT_PATH')
        raw = raw_file(root / name, 256 * 1024**2)
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ClosureError('INSTALLED_BYTES_DIFFER')
        expected[name] = row
    for row in value['links']:
        if set(row) != {'path', 'target'}:
            raise ClosureError('COMPONENT_LINK_STRUCTURE')
        name, target = relative(row['path']), row['target']
        if not isinstance(target, str) or not target or Path(target).is_absolute() or name in expected or name in expected_links:
            raise ClosureError('COMPONENT_LINK_STRUCTURE')
        item = root / name
        if (not item.is_symlink() or os.readlink(item) != target or not item.resolve(strict=True).is_relative_to(root)
                or any(parent.is_symlink() for parent in item.parents if parent != root and parent.is_relative_to(root))):
            raise ClosureError('COMPONENT_LINK_DIFFERS')
        expected_links[name] = target
    observed, links = set(), {}
    for item in root.rglob('*'):
        name = item.relative_to(root).as_posix()
        if item.is_symlink(): links[name] = os.readlink(item)
        elif item.is_file(): observed.add(name)
    # Bytecode is deliberately not exempted: unchecked .pyc cannot escape this
    # independent exact native/TUI closure simply because source .py matches.
    if observed != set(expected) or links != expected_links:
        raise ClosureError('UNEXPECTED_OR_MISSING_INSTALLED_MEMBER')
    return expected, expected_links


def metadata(site):
    rows = {}
    for distribution in importlib.metadata.distributions(path=[str(site)]):
        name = distribution.metadata.get('Name')
        normalized = re.sub(r'[-_.]+', '-', name or '').lower()
        if not normalized or normalized in rows:
            raise ClosureError('DUPLICATE_OR_UNNAMED_DISTRIBUTION')
        directory = Path(distribution._path)
        if directory.parent.resolve() != Path(site).resolve():
            raise ClosureError('DISTRIBUTION_METADATA_OUTSIDE_SITE')
        raw = raw_file(directory / 'METADATA')
        rows[normalized] = {'name': name, 'version': distribution.version, 'metadata_sha256': sha(raw)}
    return rows


def required_sources(source, prefix, project):
    tool = project.get('tool', {}).get('setuptools', {})
    package = 'jiuwenswarm' if prefix == 'jiuwenswarm/' else 'jiuwenswarm_tui'
    data = tool.get('package-data', {}).get(package, [])
    excluded = tool.get('exclude-package-data', {}).get(package, [])
    result = set()
    for name in source:
        if not name.startswith(prefix): continue
        name = name[len(prefix):]
        if prefix == 'jiuwenswarm/' and name.startswith(('research_sidecar/', 'research_rsi/')): continue
        parts = name.split('/')
        python = name.endswith('.py') and all(prefix + '/'.join([*parts[:depth], '__init__.py']) in source for depth in range(len(parts)))
        resource = any(fnmatch.fnmatchcase(name, pattern) for pattern in data) and not any(fnmatch.fnmatchcase(name, pattern) for pattern in excluded)
        if python or resource: result.add(name)
    return result


def verify(value, *, fixture_paths=None):
    result = {'schema': 'ai4r-installed-closure-observation:1', 'mode': 'fixture' if fixture_paths else 'installed',
              'qualified': False, 'assertions': {name: False for name in CHECKS}, 'stage': 'input'}
    try:
        required = {'schema', 'candidate', 'source_build_receipt_sha256', 'context_sha256', 'snapshot_sha256',
                    'image_id', 'platform', 'build_id', 'source_payloads'}
        if not isinstance(value, dict) or set(value) != required or value['schema'] != 'ai4r-installed-closure-input:1':
            raise ClosureError('CLOSED_INPUT_REQUIRED')
        candidate = value['candidate']; source = {row['path']: row for row in candidate['files']}
        identity = {key: candidate[key] for key in ('schema_version', 'base_head', 'scope', 'files')}
        if candidate['candidate_id'] != sha(encoded(identity)) or len(source) != len(candidate['files']):
            raise ClosureError('SOURCE_CANDIDATE_IDENTITY')
        result['joins'] = {key: value[key] for key in ('source_build_receipt_sha256', 'context_sha256', 'snapshot_sha256', 'image_id', 'platform', 'build_id')}
        result['joins']['candidate_id'] = candidate['candidate_id']
        paths = fixture_paths or {'manifest': '/usr/local/share/ai4r-build-identity.json',
            'native': '/opt/venv/lib/python3.12/site-packages/jiuwenswarm',
            'tui': '/opt/venv/lib/python3.12/site-packages/jiuwenswarm_tui', 'site': '/opt/venv/lib/python3.12/site-packages'}
        result['stage'] = 'manifest'
        raw = raw_file(paths['manifest']); info = Path(paths['manifest']).stat()
        if not fixture_paths and (info.st_uid != 0 or info.st_mode & 0o022):
            raise ClosureError('ROOT_MANIFEST_CUSTODY_REQUIRED')
        result['assertions']['manifest_custody'] = True
        manifest = json.loads(raw)
        expected = {'schema', 'files', 'links', 'dependencies', 'uv_lock_sha256', 'pyproject_sha256', 'components', 'build_id'}
        if (set(manifest) != expected or manifest['schema'] != 'ai4r-installed-build:2'
                or set(manifest['components']) != {'jiuwenswarm_tui'} or manifest['build_id'] != value['build_id']
                or sha(encoded({key: item for key, item in manifest.items() if key != 'build_id'})) != manifest['build_id']):
            raise ClosureError('MANIFEST_IDENTITY')
        result.update(manifest_sha256=sha(raw), installed_build_id=manifest['build_id'])
        result['assertions']['manifest_identity'] = True
        result['stage'] = 'native'
        native, native_links = component(paths['native'], {'files': manifest['files'], 'links': manifest['links']})
        result['assertions']['installed_native'] = True
        result['stage'] = 'tui'
        tui, tui_links = component(paths['tui'], manifest['components']['jiuwenswarm_tui'])
        result['assertions']['installed_tui'] = True
        projects = {}
        if set(value['source_payloads']) != {'pyproject.toml', 'packages/jiuwenswarm-tui/pyproject.toml'}:
            raise ClosureError('CLOSED_SOURCE_PAYLOAD_REQUIRED')
        for name, payload in value['source_payloads'].items():
            raw = base64.b64decode(payload, validate=True)
            if len(raw) != source[name]['bytes'] or sha(raw) != source[name]['sha256']:
                raise ClosureError('SOURCE_PAYLOAD_DIFFERS')
            projects[name] = tomllib.loads(raw.decode('utf8'))
        result['stage'] = 'source'
        generated, matched = {}, 0
        for component_name, files, links, prefix, project_name in (
            ('native', native, native_links, 'jiuwenswarm/', 'pyproject.toml'),
            ('tui', tui, tui_links, 'packages/jiuwenswarm-tui/jiuwenswarm_tui/', 'packages/jiuwenswarm-tui/pyproject.toml')):
            for name, row in files.items():
                original = source.get(prefix + name)
                if original:
                    if (row['bytes'], row['sha256']) != (original['bytes'], original['sha256']):
                        raise ClosureError('ORIGINAL_SOURCE_BYTES_DIFFER')
                    matched += 1
                else:
                    entry = next(((root, data) for root, data in GENERATED.items() if component_name == 'native' and name.startswith(root)), None)
                    if not entry: raise ClosureError('UNIDENTIFIED_INSTALLED_OUTPUT')
                    root, (kind, lock) = entry
                    if lock not in source: raise ClosureError('GENERATED_OUTPUT_LOCK_MISSING')
                    generated[root] = {'kind': kind, 'files': generated.get(root, {}).get('files', 0) + 1,
                        'lock_sha256': source[lock]['sha256'], 'context_sha256': value['context_sha256']}
            for name in links:
                if component_name != 'native' or not any(name.startswith(root) for root in GENERATED):
                    raise ClosureError('UNIDENTIFIED_INSTALLED_LINK')
            required_names = required_sources(source, prefix, projects[project_name])
            if not required_names <= files.keys():
                raise ClosureError('REQUIRED_FROZEN_SOURCE_MISSING')
        result.update(source_files_matched=matched, generated_outputs=generated,
            native_files=len(native), native_links=len(native_links), tui_files=len(tui), tui_links=len(tui_links))
        result['assertions'].update(original_source=True, required_source_present=True, generated_context=True)
        if manifest['uv_lock_sha256'] != source['uv.lock']['sha256'] or manifest['pyproject_sha256'] != source['pyproject.toml']['sha256']:
            raise ClosureError('LOCK_OR_PROJECT_DIFFERS')
        result['assertions']['lock_project'] = True
        result['stage'] = 'dependencies'
        actual = metadata(paths['site'])
        expected = {re.sub(r'[-_.]+', '-', row['name']).lower(): row['version'] for row in manifest['dependencies']}
        if len(expected) != len(manifest['dependencies']) or {name: row['version'] for name, row in actual.items()} != expected:
            raise ClosureError('DEPENDENCY_METADATA_DIFFERS')
        result['dependency_metadata_sha256'] = sha(encoded(actual))
        result['dependencies'] = len(actual)
        result['assertions']['dependency_metadata'] = True
        result.update(stage='complete', qualified=all(result['assertions'].values()))
    except Exception as error:
        result['error'] = str(error) if isinstance(error, ClosureError) else type(error).__name__
    return result


def main():
    if os.geteuid() != 65534 or sys.version_info[:2] != (3, 12):
        raise SystemExit('Fixed unprivileged Python 3.12 closure observer required')
    value = json.loads(raw_file('/run/ai4r-image-closure/input.json', 32 * 1024**2))
    print(json.dumps(verify(value), sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
