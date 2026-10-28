"""Deterministic public build snapshot respecting per-file Git byte policy.

Unspecified line endings and binary bytes are preserved. Explicit LF/CRLF
attributes are applied only to UTF-8 text. No private deployment state, account
profile, credentials, build outputs or evidence directory is included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

PATHS = ('jiuwenswarm', 'jiuwenbox', 'packages/jiuwenswarm-tui', 'pyproject.toml',
         'uv.lock', 'LICENSE', 'OPEN_SOURCE_SOFTWARE_NOTICE.md', '.gitattributes',
         'deploy/m1/*.py', 'deploy/m1/Dockerfile.app-cached',
         'deploy/m1/Dockerfile.app-cached.dockerignore', 'deploy/m1/Dockerfile.rsi',
         'deploy/m1/Dockerfile.rsi-local', 'scripts/research_compat_wheel.py',
         'scripts/research_offline_assets.py')
EXCLUDED_PARTS = {'__pycache__', 'node_modules', 'dist', '.venv', 'private',
                  'protected', 'evidence', 'credential', 'credentials', 'secrets',
                  '.git', '.codex', '.agents', '.aws'}
EXCLUDED_NAMES = {'auth.json', 'credentials.json', 'secrets.json', '.env'}
EXCLUDED_SUFFIXES = {'.key', '.pem', '.p12', '.pfx', '.pyc'}


def _need(value, message):
    if not value:
        raise ValueError(message)


def selected(name):
    path = PurePosixPath(name)
    _need(not path.is_absolute() and '..' not in path.parts and '\\' not in name,
          'Noncanonical Git source path')
    parts = {part.lower() for part in path.parts}
    base = path.name.lower()
    return not (name.startswith('jiuwenswarm/research_sidecar/')
        or parts & EXCLUDED_PARTS or base in EXCLUDED_NAMES
        or base.startswith('.env')
        or path.suffix.lower() in EXCLUDED_SUFFIXES)


def canonical_bytes(raw, attrs):
    """Apply declared checkout policy; never infer a default global LF rule."""
    if attrs['text'] == 'unset' or attrs['eol'] not in {'lf', 'crlf'}:
        return raw
    if b'\0' in raw:
        return raw
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw
    normalized = raw.replace(b'\r\n', b'\n')
    return normalized if attrs['eol'] == 'lf' else normalized.replace(b'\n', b'\r\n')


def _attributes(source, names):
    output = subprocess.check_output(['git', 'check-attr', '-z', '--stdin', 'text', 'eol'],
        cwd=source, input=b''.join(name.encode('utf-8') + b'\0' for name in names))
    fields = output.split(b'\0')
    _need(fields.pop() == b'' and len(fields) == 6 * len(names), 'Incomplete Git byte attributes')
    result = {name: {} for name in names}
    for offset in range(0, len(fields), 3):
        name, key, value = (item.decode('utf-8') for item in fields[offset:offset + 3])
        _need(name in result and key in {'text', 'eol'} and key not in result[name],
              'Unexpected Git byte attributes')
        result[name][key] = value
    return result


def snapshot(source, target):
    source = Path(source).resolve(strict=True)
    target = Path(target).absolute()
    _need(not any(path.is_symlink() for path in (target, *target.parents)), 'Symlinked snapshot destination')
    target = target.resolve()
    _need(not target.exists() and target.parent.is_dir() and not target.is_relative_to(source)
          and not source.is_relative_to(target), 'Use a fresh snapshot directory outside the repository')
    top = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=source).decode().strip()).resolve()
    _need(source == top, 'Source must be the repository root')
    output = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                      '--exclude-standard', '--', *PATHS], cwd=source)
    names = sorted({value.decode('utf-8') for value in output.split(b'\0') if value})
    names = [name for name in names if selected(name)]
    attrs = _attributes(source, names)
    # Resolve every source path before creating a destination. Never traverse a
    # symlink or copy an escaped file, even when Git lists the symlink itself.
    for name in names:
        path = source / name
        _need(path.is_file() and not path.is_symlink(),
              'Public source must contain regular files')
        _need(path.resolve().is_relative_to(source), 'Public source escapes repository')
        _need(not any(parent.is_symlink() for parent in path.parents if parent != source.parent),
              'Public source has a symlinked ancestor')
    # This is a public source context, readable by the unprivileged build/test
    # identity. Private operator/account roots are never copied into it.
    target.mkdir(mode=0o755)
    rows = []
    for name in names:
        raw = (source / name).read_bytes()
        data = canonical_bytes(raw, attrs[name])
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        rows.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
            'source_sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(data),
            'attributes': attrs[name]})
    manifest = {'schema': 'rsi-public-build-snapshot:2', 'files': rows,
                'line_endings': 'git_attributes_explicit_otherwise_preserved'}
    encoded = (json.dumps(manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')
    (target / 'public-snapshot.json').write_bytes(encoded)
    return {'files': len(rows), 'snapshot_sha256': hashlib.sha256(encoded).hexdigest(),
            'lock_sha256': hashlib.sha256((target / 'uv.lock').read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args(argv)
    result = snapshot(args.source, args.target)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
