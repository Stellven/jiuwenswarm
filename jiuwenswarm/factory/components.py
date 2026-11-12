"""Read host-owned component materials; callers cannot supply engagement code."""
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).parent / 'ccs' / 'expert_streaming' / 'components'


def load(component):
    if not isinstance(component, str):
        raise ValueError('component must name a factory component')
    name = component.removeprefix('factory.components.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError('Invalid component identifier')
    path = ROOT / name / 'component.yaml'
    if not path.is_file():
        raise ValueError('Unknown component: ' + name)
    declared = (yaml.safe_load((path.parent / 'cc.yaml').read_text()).get('materials') or {}).get('component') or {}
    if declared.get('kind') != 'component':
        raise ValueError('Not a component module (cc.yaml materials.component.kind must be component): ' + name)
    return yaml.safe_load(path.read_text())


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
