"""Additive release manifests keep optional capsule branches independent."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

from ..contracts import ResearchError


def candidates(store):
    result = {}
    root = Path(__file__).parent
    for path in sorted(root.glob('*/release.json')):
        spec = json.loads(path.read_text('utf-8'))
        legacy = set(spec) == {'name', 'module', 'files'}
        current_keys = {'name', 'module', 'files', 'shared_runtime'}
        dependency_keys = current_keys | {'shared_dependencies'}
        current = set(spec) in (current_keys, dependency_keys)
        if not (legacy or current) or spec['module'] != path.parent.name:
            raise ResearchError('extension_manifest', 'Invalid installed release manifest')
        required = {p.relative_to(root).as_posix() for p in path.parent.glob('*.py')}
        if legacy:
            required |= {'assets.py', 'packet.py'}
        if set(spec['files']) != required:
            raise ResearchError('extension_manifest', 'Incomplete installed release closure')
        for name, digest in spec['files'].items():
            target = (root / name).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ResearchError('extension_manifest', 'Installed extension closure changed: ' + name)
        if current:
            pin = spec['shared_runtime']
            if pin != {'path': 'packet.py', 'sha256': hashlib.sha256((root / 'packet.py').read_bytes()).hexdigest()}:
                raise ResearchError('extension_manifest', 'Installed shared runtime pin changed')
            dependencies = spec.get('shared_dependencies', [])
            seen_dependencies = set()
            for dependency in dependencies:
                if (set(dependency) != {'path', 'sha256'} or dependency['path'] in seen_dependencies
                        or not isinstance(dependency['path'], str) or not isinstance(dependency['sha256'], str)):
                    raise ResearchError('extension_manifest', 'Invalid shared dependency pin')
                target = (root / dependency['path']).resolve()
                if (not target.is_relative_to(root.resolve()) or not target.is_file()
                        or hashlib.sha256(target.read_bytes()).hexdigest() != dependency['sha256']):
                    raise ResearchError('extension_manifest', 'Installed shared dependency pin changed: ' + dependency['path'])
                seen_dependencies.add(dependency['path'])
        module = importlib.import_module(__package__ + '.' + spec['module'] + '.release')
        asset = module.prepare(store)
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        if declaration['identity']['name'] != spec['name'] or spec['name'] in result:
            raise ResearchError('extension_manifest', 'Duplicate or mismatched capsule identity')
        result[spec['name']] = (asset, module)
    return result


def historical_candidates(store):
    """Load immutable archived releases for already-admitted installations.

    Historical releases are never offered as new candidates. Their manifests
    still name the original module closure, which is rehashed before importing
    the exact old release factory for startup registration.
    """
    result = {}
    root = Path(__file__).parent
    for path in sorted((root / 'history/v1').glob('*/release.json')):
        spec = json.loads(path.read_text('utf-8'))
        if (set(spec) != {'name', 'module', 'files'} or not isinstance(spec['module'], str)
                or not spec['module'].isidentifier()):
            raise ResearchError('extension_manifest', 'Invalid historical release manifest')
        module_root = root / spec['module']
        if not module_root.is_dir():
            raise ResearchError('extension_manifest', 'Historical release source module is unavailable')
        required = {p.relative_to(root).as_posix() for p in module_root.glob('*.py')} | {'assets.py', 'packet.py'}
        if set(spec['files']) != required:
            raise ResearchError('extension_manifest', 'Incomplete historical release closure')
        for name, digest in spec['files'].items():
            target = (root / name).resolve()
            if (not target.is_relative_to(root.resolve()) or not target.is_file()
                    or hashlib.sha256(target.read_bytes()).hexdigest() != digest):
                raise ResearchError('extension_manifest', 'Historical extension closure changed: ' + name)
        module = importlib.import_module(__package__ + '.' + spec['module'] + '.release')
        asset = module.prepare(store)
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        identity = declaration['identity']
        if identity['name'] != spec['name']:
            raise ResearchError('extension_manifest', 'Historical manifest identity mismatch')
        key = (identity['name'], identity['version_label'])
        if key in result:
            raise ResearchError('extension_manifest', 'Duplicate historical release identity')
        result[key] = (asset, module)
    return result


def register_active(registry, checks, library, store):
    """Unadmitted candidates do not block existing installations or get activated."""
    installed = {}
    releases = [(name, asset, module) for name, (asset, module) in candidates(store).items()]
    releases.extend((name, asset, module)
        for (name, _version), (asset, module) in historical_candidates(store).items())
    for name, asset, module in releases:
        declaration = store.read_record(asset['declaration_ref'])
        try:
            entry = library.get(name, declaration['identity']['version_label'])
        except ResearchError as error:
            if error.code != 'library_membership':
                raise
            continue
        if entry['standing'] != 'active' or entry['effect_scope'] != 'live_plans':
            continue
        # Archived source bytes do not get grandfathered around current
        # independent check admission. A historical release is restored only
        # when its exact existing association still passes the normal policy.
        association = library.eligible_association(asset['declaration_ref'])
        if (entry['declaration_ref'] != asset['declaration_ref'] or entry['body_refs'] != asset['body_refs']
                or association['bundle_ref'] != asset['bundle_ref'] or association['profile_ref'] != asset['profile_ref']):
            raise ResearchError('extension_pin', 'Active extension differs from installed exact release')
        bundle = store.read_record(asset['bundle_ref'])
        checks.register_bundle(bundle['bundle_id'], [c['check_id'] for c in bundle['checks']], module.check,
                               implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
        registry.register(name, declaration['identity']['version_label'], module.execute,
                          declaration_sha256=asset['declaration_ref']['sha256'], implementation_refs=asset['implementation_refs'])
        asset['pin'] = store.read_record(entry['admission_ref'])['cc']
        installed_key = name if name not in installed else name + '@' + declaration['identity']['version_label']
        installed[installed_key] = asset
    return installed
