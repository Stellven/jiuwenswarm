"""Read host-owned component materials; callers cannot supply engagement code."""
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).parent / 'ccs' / 'components'


def load(component):
    if not isinstance(component, str):
        raise ValueError('component must name a factory component')
    name = component.removeprefix('factory.components.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError('Invalid component identifier')
    path = ROOT / name / 'component.yaml'
    if not path.is_file():
        raise ValueError('Unknown component: ' + name)
    return yaml.safe_load(path.read_text())
