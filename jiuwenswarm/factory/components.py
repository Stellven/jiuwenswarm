"""Read host-owned component materials; callers cannot supply engagement code."""
from pathlib import Path
import re
import yaml
from contextvars import ContextVar

SELECTED_BINDING = ContextVar("factory_component_binding", default=None)

ROOT = Path(__file__).parent / 'ccs' / 'expert_streaming' / 'components'


def load(component, *, host=None, release=None, legacy=False):
    if not isinstance(component, str):
        raise ValueError('component must name a factory component')
    name = component.removeprefix('factory.components.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError('Invalid component identifier')
    selected = SELECTED_BINDING.get()
    if release is None and selected is not None:
        host, binding = selected
        matches = [row['release'] for row in binding['components']
                   if host.describe(row['release'])['id'] == 'factory.components.' + name]
        if len(matches) != 1:
            raise ValueError('Component is not selected by the execution binding: ' + name)
        release = matches[0]
    if release is not None:
        if host is None:
            raise ValueError('Sealed component selection requires its Host')
        declaration, bundle = host.release(release)
        if declaration['id'] != 'factory.components.' + name:
            raise ValueError('Selected release names a different component')
    else:
        bundle = ROOT / name
        if not (bundle / 'cc.yaml').is_file():
            raise ValueError('Unknown component: ' + name)
        declaration = yaml.safe_load((bundle / 'cc.yaml').read_text())
    from jiuwenswarm.ccv2.roles import read_roles
    roles = read_roles(declaration, bundle, legacy=legacy)
    if roles['materials'].get('component') != 'component':
        raise ValueError('Selected material is not declared as a component')
    from jiuwenswarm.ccv2.ccv2 import contained
    path = contained(bundle, declaration['materials']['component']['path'])
    from .ontology import validate_component
    return validate_component(yaml.safe_load(path.read_text()))


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
