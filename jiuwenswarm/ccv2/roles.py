"""Optional passive factory roles, carried by an ordinary CC material."""
import json
from .ccv2 import contained


def read_roles(declaration, bundle, *, legacy=False):
    descriptor = declaration.get('materials', {}).get('roles')
    if descriptor is None:
        return {section: {name: value.get('kind', default) if legacy else default
                         for name, value in declaration.get(section, {}).items()}
                for section, default in [('capabilities', 'tool'), ('materials', 'reference')]}
    path = contained(bundle, descriptor['path'])
    if path.stat().st_size > 65536:
        raise ValueError('Roles material exceeds 64 KiB')
    roles = json.loads(path.read_text())
    if set(roles) != {'format', 'capabilities', 'materials'} or roles['format'] != 'factory-roles/1':
        raise ValueError('Invalid roles material')
    for section, allowed in [('capabilities', {'tool'}), ('materials', {'reference', 'component', 'skill', 'method'})]:
        if not isinstance(roles[section], dict) or set(roles[section]) - set(declaration.get(section, {})):
            raise ValueError('Roles name undeclared entries')
        if any(value not in allowed for value in roles[section].values()):
            raise ValueError('Unsupported passive role')
    return roles
