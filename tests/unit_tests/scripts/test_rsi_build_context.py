"""Byte policy is explicit, portable, and leaves frozen binary inputs intact."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_build_context.py'
spec = importlib.util.spec_from_file_location('rsi_build_context_under_test', SOURCE)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


def test_canonical_bytes_uses_attributes_and_preserves_binary():
    raw = b'first\r\nsecond\n'
    assert context.canonical_bytes(raw, {'text': 'set', 'eol': 'lf'}) == b'first\nsecond\n'
    assert context.canonical_bytes(raw, {'text': 'set', 'eol': 'crlf'}) == b'first\r\nsecond\r\n'
    for attrs in ({'text': 'unset', 'eol': 'lf'}, {'text': 'unspecified', 'eol': 'unspecified'}):
        assert context.canonical_bytes(raw, attrs) == raw
    for raw in (b'zip\0binary\r\n', b'\xff\r\n'):
        assert context.canonical_bytes(raw, {'text': 'set', 'eol': 'lf'}) == raw


@pytest.mark.parametrize('name', ['jiuwenswarm/private/a.py', 'jiuwenswarm/evidence/a.json',
    'jiuwenswarm/credentials/a.txt', 'jiuwenswarm/auth.json', 'jiuwenswarm/secrets.json',
    'jiuwenswarm/.env.local', 'jiuwenswarm/key.pem', 'jiuwenbox/node_modules/a.js',
    'jiuwenswarm/research_sidecar/public.py'])
def test_sensitive_or_generated_files_are_excluded(name):
    assert not context.selected(name)


def test_snapshot_uses_git_attributes_and_preserves_unspecified_files(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / '.gitattributes').write_bytes(b'*.py text eol=lf\njiuwenswarm/frozen.txt text eol=crlf\n*.bin -text\n')
    (repo / 'uv.lock').write_bytes(b'lock\r\n')
    source = repo / 'jiuwenswarm'; source.mkdir()
    for name, raw in {'a.py': b'pass\r\n', 'frozen.txt': b'one\ntwo\n',
                      'raw.md': b'keep\r\n', 'a.bin': b'binary\0\r\n',
                      'auth.json': b'private', 'credential_manager.py': b'pass\r\n'}.items():
        (source / name).write_bytes(raw)
    first = tmp_path / 'first'; second = tmp_path / 'second'
    assert context.snapshot(repo, first) == context.snapshot(repo, second)
    assert (first / 'jiuwenswarm/frozen.txt').read_bytes() == b'one\r\ntwo\r\n'
    assert (first / 'jiuwenswarm/a.py').read_bytes() == b'pass\n'
    assert (first / 'jiuwenswarm/raw.md').read_bytes() == b'keep\r\n'
    assert (first / 'jiuwenswarm/a.bin').read_bytes() == b'binary\0\r\n'
    assert not (first / 'jiuwenswarm/auth.json').exists()
    assert (first / 'jiuwenswarm/credential_manager.py').exists()
    manifest = json.loads((first / 'public-snapshot.json').read_bytes())
    assert manifest['schema'] == 'rsi-public-build-snapshot:2'
    assert not (first / 'public-snapshot.json').read_bytes().startswith(b'\xef\xbb\xbf')
    for row in manifest['files']:
        assert row['sha256'] == hashlib.sha256((first / row['path']).read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        context.snapshot(repo, first)


def test_actual_frozen_corpus_remains_exact_in_snapshot_policy():
    repo = SOURCE.parents[2]
    root = repo / 'jiuwenswarm/research/resources/calibration'
    manifest = json.loads((root / 'manifest.json').read_bytes())
    names = ['jiuwenswarm/research/resources/calibration/' + name for name in manifest['files']]
    attrs = context._attributes(repo, names)
    for name, expected in manifest['files'].items():
        relative = 'jiuwenswarm/research/resources/calibration/' + name
        copied = context.canonical_bytes((root / name).read_bytes(), attrs[relative])
        assert hashlib.sha256(copied).hexdigest() == expected, name
