"""Explicit, copy-only migration: old release directories are never modified."""
import json
from pathlib import Path
import shutil
import yaml
from jiuwenswarm.ccv2.ccv2 import Host


def migrate(source, destination, store):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('Migration destination must be fresh')
    host = Host(store, session_grants=[], legacy=True)
    paths = sorted(source.rglob('cc.yaml'))
    old = {p.relative_to(source).as_posix(): host.seal(p.parent) for p in paths}
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Children first: parent releases seal their final nested package bytes.
    for path in sorted(destination.rglob('cc.yaml'), key=lambda p: len(p.parts), reverse=True):
        declaration = yaml.safe_load(path.read_text())
        roles = {'format': 'factory-roles/1', 'capabilities': {}, 'materials': {}}
        for section, default in [('capabilities', 'tool'), ('materials', 'reference')]:
            for name, item in declaration.get(section, {}).items():
                roles[section][name] = item.pop('kind', default)
        declaration.setdefault('materials', {})['roles'] = {'path': 'roles.json', 'media_type': 'application/json'}
        major, minor, patch = map(int, declaration['version'].split('.'))
        declaration['version'] = f'{major}.{minor}.{patch + 1}'
        (path.parent / 'roles.json').write_text(json.dumps(roles, indent=2, sort_keys=True) + '\n')
        path.write_text(yaml.safe_dump(declaration, sort_keys=False))
    records = []
    for path in paths:
        relative = path.relative_to(source).as_posix()
        release = host.seal((destination / relative).parent)
        records.append(dict(path=relative, old_release=old[relative], new_release=release))
    result = dict(format='factory-cc-migration/1', releases=records)
    (destination / 'migration.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
