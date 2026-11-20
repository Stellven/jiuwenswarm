"""Read host-owned component materials; callers cannot supply engagement code."""
from contextvars import ContextVar
from functools import lru_cache
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, ValidationError
import yaml

from jiuwenswarm.ccv2 import ccv2
from jiuwenswarm.ccv2.roles import read_roles

SELECTED_BINDING = ContextVar("factory_component_binding", default=None)
CCS = Path(__file__).with_name('ccs')
ROOT = CCS / 'expert_streaming' / 'components'
SCHEMA = Path(__file__).with_name('schemas') / 'component.schema.json'
COMPONENT_NAME = re.compile(r'[a-z][a-z0-9_]*')
BUILDER_PATH = re.compile(r'components/([a-z][a-z0-9_]*)/component[.]yaml')


@lru_cache(maxsize=1)
def _validator():
    return Draft202012Validator(json.loads(SCHEMA.read_text()))


def _read_component(path, *, ontology_path=None):
    from .ontology import validate_component

    material = yaml.safe_load(path.read_text())
    try:
        _validator().validate(material)
    except ValidationError as exc:
        raise ValueError(f'Invalid component manifest {path}: {exc.message}') from exc
    if (material.get('kind') == 'builder_spec') != (ontology_path is not None):
        raise ValueError(f'Unexpected component kind in {path}')
    return validate_component(material, ontology_path=ontology_path)


def _builder_materials(declaration, bundle, name, *, legacy=False):
    roles = read_roles(declaration, bundle, legacy=legacy)
    return [(key, descriptor) for key, descriptor in declaration.get('materials', {}).items()
            if (match := BUILDER_PATH.fullmatch(descriptor['path']))
            and roles['materials'].get(key) in {'component', 'reference'}
            and name in (match[1], declaration['id'])]


def _read_selected(declaration, bundle, name, *, material_name=None, legacy=False):
    if declaration['id'] == 'factory.components.' + name:
        roles = read_roles(declaration, bundle, legacy=legacy)
        if material_name not in (None, 'component') or roles['materials'].get('component') != 'component':
            raise ValueError('Selected material is not declared as a component')
        path = ccv2.contained(bundle, declaration['materials']['component']['path'])
        return _read_component(path)
    matches = _builder_materials(declaration, bundle, name, legacy=legacy)
    if material_name is not None:
        matches = [(key, descriptor) for key, descriptor in matches if key == material_name]
    if len(matches) != 1:
        raise ValueError('Selected release names a different or ambiguous component')
    path = ccv2.contained(bundle, matches[0][1]['path'])
    return _read_component(path, ontology_path=ccv2.contained(bundle, 'ONTOLOGY.yaml'))


def load(component, *, host=None, release=None, legacy=False):
    if not isinstance(component, str):
        raise ValueError('component must name a factory component')
    name = component.removeprefix('factory.components.')
    if not ccv2.ID.fullmatch(name):
        raise ValueError('Invalid component identifier')
    selected = SELECTED_BINDING.get()
    material_name = None
    if release is None and selected is not None:
        host, binding = selected
        matches = []
        for row in binding['components']:
            declaration, bundle = host.release(row['release'])
            if (declaration['id'] == 'factory.components.' + name
                    or _builder_materials(declaration, bundle, name, legacy=legacy)):
                matches.append(row)
        if len(matches) != 1:
            raise ValueError('Component is not selected by the execution binding: ' + name)
        release, material_name = matches[0]['release'], matches[0]['material']
    if release is not None:
        if host is None:
            raise ValueError('Sealed component selection requires its Host')
        declaration, bundle = host.release(release)
        return _read_selected(declaration, bundle, name, material_name=material_name, legacy=legacy)
    bundle = ROOT / name
    if COMPONENT_NAME.fullmatch(name) and (bundle / 'cc.yaml').is_file():
        declaration = ccv2.load(bundle / 'cc.yaml', legacy=legacy)
        return _read_selected(declaration, bundle, name, legacy=legacy)
    matches = []
    for manifest in sorted(CCS.glob('*/cc.yaml')):
        declaration = ccv2.load(manifest, legacy=legacy)
        if _builder_materials(declaration, manifest.parent, name, legacy=legacy):
            matches.append((declaration, manifest.parent))
    if not matches:
        raise ValueError('Unknown component: ' + name)
    if len(matches) != 1:
        raise ValueError('Ambiguous builder specification: ' + name)
    return _read_selected(*matches[0], name, legacy=legacy)


def dependents(component):
    """Components that need `component`'s source, directly or transitively."""
    names = sorted(p.parent.name for p in ROOT.glob('*/component.yaml'))
    needs = {name: set(load(name).get('depends_on') or []) for name in names}
    found, frontier = set(), {component}
    while frontier:
        frontier = {name for name, deps in needs.items() if deps & frontier} - found
        found |= frontier
    return found


def allowed_knobs():
    knobs = {}
    for path in sorted(ROOT.glob('*/component.yaml')):
        material = load(path.parent.name)
        for key, value in material.get('enable_env', {}).items():
            if key.startswith('LLAMA_EXPERT_') or key == 'LLAMA_MMAP_ADVICE':
                knobs.setdefault(key, 'enable value ' + value)
        for key, value in material.get('env_ranges', {}).items():
            if key.startswith('LLAMA_EXPERT_') or key == 'LLAMA_MMAP_ADVICE':
                knobs[key] = value
    return knobs


def environment(contract, requested):
    if not isinstance(requested, dict):
        raise ValueError('Engine environment must be an object')
    knobs = allowed_knobs()
    env = dict(contract['workload']['env'], **requested)
    if any(k not in knobs for k in env):
        raise ValueError('Unknown engine environment key. Allowed knobs and ranges: ' +
                         '; '.join(f'{k}: {v}' for k, v in sorted(knobs.items())))
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_./:+-]+', v) for v in env.values()):
        raise ValueError('Engine environment requires shell-safe string values')
    return env
