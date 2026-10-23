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
        if set(spec) != {'name', 'module', 'files'} or spec['module'] != path.parent.name:
            raise ResearchError('extension_manifest', 'Invalid installed release manifest')
        required = {p.relative_to(root).as_posix() for p in path.parent.glob('*.py')} | {'assets.py', 'packet.py'}
        if set(spec['files']) != required:
            raise ResearchError('extension_manifest', 'Incomplete installed release closure')
        for name, digest in spec['files'].items():
            target = (root / name).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ResearchError('extension_manifest', 'Installed extension closure changed: ' + name)
        module = importlib.import_module(__package__ + '.' + spec['module'] + '.release')
        asset = module.prepare(store)
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        if declaration['identity']['name'] != spec['name'] or spec['name'] in result:
            raise ResearchError('extension_manifest', 'Duplicate or mismatched capsule identity')
        result[spec['name']] = (asset, module)
    return result


def register_active(registry, checks, library, store):
    """Unadmitted candidates do not block existing installations or get activated."""
    installed = {}
    for name, (asset, module) in candidates(store).items():
        declaration = store.read_record(asset['declaration_ref'])
        try:
            entry = library.get(name, declaration['identity']['version_label'])
        except ResearchError as error:
            if error.code != 'library_membership':
                raise
            continue
        if entry['standing'] != 'active' or entry['effect_scope'] != 'live_plans':
            continue
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
        installed[name] = asset
    return installed
