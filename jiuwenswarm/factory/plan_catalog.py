"""The capsule catalog as the planner sees it: what exists, what each capability may change.

Read from the same declarations the agent's CC host serves (``ccs/*/cc.yaml``) and, for
builder capsules, their component specifications (``components/*/component.yaml``).
The planner prompt gets a reduced view; the plan checks use the full lookups.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import yaml

CCS = Path(__file__).with_name('ccs')


def _first_paragraph(path):
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return ''
    lines = []
    for line in text.splitlines():
        if line.startswith('#'):
            if lines:
                break
            continue
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line.strip())
    return ' '.join(lines)[:400]


def is_verifier_name(capability_name):
    """True when a capability name is a capsule verifier (verify or verify_*)."""
    return bool(capability_name) and (capability_name == 'verify' or capability_name.startswith('verify_'))


def _atlas_kinds():
    path = CCS / 'atlas-names.json'
    if not path.is_file():
        return {}
    entries = (json.loads(path.read_text(encoding='utf-8')) or {}).get('capsules') or {}
    return {spec['capsule_id']: spec.get('kind', '') for spec in entries.values() if 'capsule_id' in spec}


def _ontology_slices(folder):
    path = folder / 'ONTOLOGY.yaml'
    if not path.is_file():
        return []
    return sorted(((yaml.safe_load(path.read_text(encoding='utf-8')) or {}).get('slices') or {}).keys())


def _component(folder):
    """The builder specification of a capsule, or None. One builder component per capsule."""
    found = []
    for path in sorted(folder.glob('components/*/component.yaml')):
        spec = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        if spec.get('kind') == 'builder_spec':
            change = spec.get('change') or {}
            found.append(dict(
                name=path.parent.name,
                change_kind=change.get('kind'),
                touches=list(change.get('touches') or []),
                modifies_region=list(spec.get('modifies_region') or []),
                correctness_obligations=list(spec.get('correctness_obligations') or []),
                engagement_checks=list(spec.get('engagement_checks') or []),
                base_commit=(spec.get('base') or {}).get('commit'),
                supported_host=(spec.get('supported') or {}).get('host') or {},
                acceptance_type=(spec.get('acceptance') or {}).get('type')))
    return found[0] if len(found) == 1 else None


@lru_cache(maxsize=4)
def _load(root):
    root = Path(root)
    atlas = _atlas_kinds() if root == CCS.resolve() else {}
    capsules, digest = {}, hashlib.sha256()
    for manifest in sorted(root.glob('*/cc.yaml')):
        raw = manifest.read_bytes()
        digest.update(manifest.parent.name.encode() + b'\0' + raw)
        declaration = yaml.safe_load(raw) or {}
        if not declaration.get('id'):
            continue
        capabilities = {name: dict(does=(spec or {}).get('does', ''), changes=sorted((spec or {}).get('changes') or []))
                        for name, spec in (declaration.get('capabilities') or {}).items()}
        verifiers = sorted(name for name in capabilities if is_verifier_name(name))
        component = _component(manifest.parent)
        if component:
            for spec in sorted(manifest.parent.glob('components/*/component.yaml')):
                digest.update(spec.read_bytes())
        builder = bool(component) and 'verify' in capabilities
        # Realizable capsules can own an arm directly: builders (diff) or tool compilers (verify_pack).
        realizable = builder or ('verify_pack' in capabilities)
        capsules[declaration['id']] = dict(
            id=declaration['id'], version=str(declaration.get('version', '')), folder=manifest.parent.name,
            atlas_kind=atlas.get(declaration['id'], ''),
            summary=_first_paragraph(manifest.parent / 'GUIDE.md') or next(
                (c['does'] for c in capabilities.values() if c['does']), ''),
            capabilities=capabilities, verifiers=verifiers, slices=_ontology_slices(manifest.parent),
            component=component, builder=builder, realizable=realizable)
    return dict(capsules=capsules, sha256=digest.hexdigest())


def load(root=None):
    """{'capsules': {id: {...}}, 'sha256': digest of every declaration read}."""
    return _load(str(Path(root or CCS).resolve()))


def capability(catalog, name):
    """The capability record of ``<capsule id>.<capability>``, or None."""
    capsule_id, _, cap = (name or '').rpartition('.')
    capsule = catalog['capsules'].get(capsule_id)
    return capsule['capabilities'].get(cap) if capsule else None


def is_verifier(catalog, name):
    """True when ``name`` names an existing verifier capability (verify or verify_*) in ``catalog``."""
    _, _, cap = (name or '').rpartition('.')
    return is_verifier_name(cap) and capability(catalog, name) is not None


def prompt_view(catalog):
    """A compact JSON view for the planner prompt: builders and verifiable tools in full, others by capability."""
    builders, others = [], []
    for capsule in sorted(catalog['capsules'].values(), key=lambda c: c['id']):
        if capsule['builder']:
            component = capsule['component']
            builders.append(dict(
                id=capsule['id'], change_kind=component['change_kind'], summary=capsule['summary'],
                verify=dict(capability=capsule['id'] + '.verify', does=capsule['capabilities']['verify']['does'],
                            changes=capsule['capabilities']['verify']['changes']),
                verifiers=[capsule['id'] + '.' + v for v in capsule['verifiers']],
                component=component['name'], touches=component['touches'], slices=capsule['slices'],
                correctness_obligations=component['correctness_obligations'][:6]))
        else:
            entry = dict(id=capsule['id'], kind=capsule['atlas_kind'] or None, summary=capsule['summary'][:200],
                         capabilities={name: c['changes'] for name, c in capsule['capabilities'].items()})
            if capsule['verifiers']:
                entry['verifiers'] = [capsule['id'] + '.' + v for v in capsule['verifiers']]
            if capsule['slices']:
                entry['slices'] = capsule['slices']
            others.append(entry)
    return json.dumps(dict(builder_capsules=builders, other_capsules=others), ensure_ascii=False, indent=1)
