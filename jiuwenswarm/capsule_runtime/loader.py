"""Discover capability capsules and verify their pins before any capsule code runs.

Reuses the existing release helpers: the manifest shape and the shared-runtime /
shared-dependency pin check come from ``capsule_extensions.catalog``; hashes are
plain SHA-256 of file bytes, exactly as ``release_tool.freeze`` writes them.
No run store, scheduler, runner or executor RPC is used. The declaration is
built by the capsule's own ``release.prepare`` against an in-memory stand-in for
the store (blob and record capture only).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from jiuwenswarm.research.capsule_extensions import catalog as _catalog
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.state import json_bytes

BUILTIN_ROOT = Path(_catalog.__file__).parent
_RESEARCH_PACKAGE = 'jiuwenswarm.research'
_BUILTIN_PACKAGE = _RESEARCH_PACKAGE + '.capsule_extensions'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MemoryStore:
    """Blob and record capture only; enough for ``release.prepare``."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}

    def put_blob(self, data: bytes, *, media_type: str = 'application/octet-stream', **_):
        digest = sha256(data)
        self.blobs[digest] = data
        return {'id': 'blob:' + digest, 'sha256': digest}

    def put_record(self, contract_id: str, record, **_):
        validate(contract_id, dict(record))
        return self.put_blob(json_bytes(record), media_type='application/json')

    def read_blob(self, ref):
        return self.blobs[ref['sha256']]

    def read_record(self, ref, contract_id: str | None = None):
        value = json.loads(self.blobs[ref['sha256']].decode('utf-8'))
        if contract_id:
            validate(contract_id, value)
        return value


@dataclass
class Capsule:
    key: str                      # registry key; the capability id unless two releases share it
    capability_id: str            # declaration identity.name
    version: str
    root: Path                    # directory that holds the capsule folders and packet.py
    module: str                   # folder name under root
    package: str                  # dotted package that root is imported as
    status: str = 'loaded'        # loaded | refused
    reason: str = ''
    refusal_code: str = ''
    declaration: dict = field(default_factory=dict)
    release_hash: str = ''
    release: dict = field(default_factory=dict)
    execute: Callable | None = None
    check: Callable | None = None
    wall_s: float = 30.0
    store: object = None          # MemoryStore holding the declaration, profile and check bundle
    asset: dict = field(default_factory=dict)


def verify_pins(root: Path, module: str) -> tuple[dict, str]:
    """Rehash every pinned byte on disk. Returns (release spec, release hash)."""
    path = root / module / 'release.json'
    try:
        raw = path.read_bytes()
        spec = json.loads(raw.decode('utf-8'))
    except (OSError, ValueError) as error:
        raise ResearchError('extension_manifest', 'release.json unreadable: ' + str(error)[:160]) from error
    if not isinstance(spec, dict):
        raise ResearchError('extension_manifest', 'release.json must be an object')
    legacy = set(spec) == {'name', 'module', 'files'}
    base = {'name', 'module', 'files', 'shared_runtime'}
    current = set(spec) in (base, base | {'shared_dependencies'})
    if not (legacy or current) or spec.get('module') != module:
        raise ResearchError('extension_manifest', 'Invalid installed release manifest')
    required = {p.relative_to(root).as_posix() for p in (root / module).glob('*.py')}
    if legacy:
        required |= {'assets.py', 'packet.py'}
    if set(spec['files']) != required:
        raise ResearchError('extension_manifest', 'Incomplete installed release closure: files on disk differ from the pinned list')
    for name, digest in spec['files'].items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ResearchError('extension_manifest', 'Pinned file missing: ' + name)
        if sha256(target.read_bytes()) != digest:
            raise ResearchError('extension_manifest', 'Pinned file changed on disk: ' + name)
    if current:
        _catalog._verify_current_pins(root, spec)
    return spec, sha256(raw)


def _package_for(root: Path) -> str:
    """Import name under which ``root`` is a package.

    The built-in tree is imported normally. Any other directory is mounted as a
    synthetic child of ``jiuwenswarm.research`` so a capsule written like the
    built-in ones (``...contracts``, ``..packet`` relative imports) resolves the
    same way.
    """
    if root.resolve() == BUILTIN_ROOT.resolve():
        return _BUILTIN_PACKAGE
    name = _RESEARCH_PACKAGE + '._ext_' + sha256(str(root.resolve()).encode())[:10]
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(root.resolve())]
        sys.modules[name] = package
    return name


def _load_one(root: Path, module: str, package: str) -> Capsule:
    capsule = Capsule(key=module, capability_id=module, version='', root=root, module=module, package=package)
    try:
        spec, release_hash = verify_pins(root, module)
    except ResearchError as error:
        capsule.status, capsule.reason, capsule.refusal_code = 'refused', error.message, error.code
        try:
            capsule.capability_id = capsule.key = json.loads((root / module / 'release.json').read_text('utf-8')).get('name', module)
        except (OSError, ValueError, AttributeError):
            pass
        return capsule
    capsule.capability_id = capsule.key = spec['name']
    capsule.release, capsule.release_hash = spec, release_hash
    try:
        release = importlib.import_module(package + '.' + module + '.release')
        store = MemoryStore()
        asset = release.prepare(store)
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        if declaration['identity']['name'] != spec['name']:
            raise ResearchError('extension_manifest', 'Declaration name differs from the release manifest')
        for row in declaration['identity']['body']:
            pinned = spec['files'].get(row['path'].removeprefix('capsule_extensions/'))
            if pinned is not None and pinned != row['sha256']:
                raise ResearchError('extension_manifest', 'Declaration body hash differs from the pinned release: ' + row['path'])
        capsule.declaration, capsule.store, capsule.asset = declaration, store, asset
        capsule.version = declaration['identity']['version_label']
        capsule.execute, capsule.check = release.execute, release.check
        capsule.wall_s = float(declaration['budget']['per_call']['wall_s'])
    except ResearchError as error:
        capsule.status, capsule.reason, capsule.refusal_code = 'refused', error.message, error.code
    except Exception as error:  # a broken capsule is refused with the real reason, never skipped
        capsule.status, capsule.refusal_code = 'refused', 'load_error'
        capsule.reason = type(error).__name__ + ': ' + str(error)[:200]
    return capsule


def discover(extra_dirs=(), *, include_builtin: bool = True) -> dict[str, Capsule]:
    """Return every capsule found, loaded or refused, keyed by capability id.

    A second release with an id already taken is keyed ``id@version``.
    """
    roots = ([BUILTIN_ROOT] if include_builtin else []) + [Path(d) for d in extra_dirs]
    found: dict[str, Capsule] = {}
    for root in roots:
        if not root.is_dir():
            continue
        package = _package_for(root)
        for manifest in sorted(root.glob('*/release.json')):
            capsule = _load_one(root, manifest.parent.name, package)
            key = capsule.capability_id
            if key in found:
                key = key + '@' + (capsule.version or capsule.module)
            if key in found:
                capsule.status, capsule.refusal_code = 'refused', 'duplicate_id'
                capsule.reason = 'Capability id already registered: ' + key
                key = key + '#' + capsule.module
            capsule.key = key
            found[key] = capsule
    return found
