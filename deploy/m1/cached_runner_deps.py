"""Copy only the runner's locked installed wheel closure from a cached runtime."""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import shutil
import tomllib


def main():
    lock = tomllib.loads(Path('/build/uv.lock').read_text())
    packages = {p['name']: p for p in lock['package']}
    pending = ['httpx', 'jsonschema', 'psutil', 'cryptography', 'pyyaml', 'ruamel-yaml']
    selected = set()
    target = Path('/runner-deps')
    target.mkdir()
    inventory = []
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        package = packages[name]
        dist = importlib.metadata.distribution(name)
        if dist.version != package['version'] or set(package.get('source', {})) != {'registry'}:
            raise ValueError('CACHED_RUNNER_DEPENDENCY_PIN_MISMATCH:' + name)
        pending.extend(d['name'] for d in package.get('dependencies', []))
        site = Path(dist.locate_file('')).resolve()
        for item in dist.files or ():
            source = Path(dist.locate_file(item))
            if '__pycache__' in source.parts or source.suffix == '.pyc':
                continue
            # Console scripts are unnecessary; never copy from app-private roots.
            if not source.resolve().is_relative_to(site):
                continue
            destination = target / source.relative_to(site)
            if source.is_symlink():
                raise ValueError('DEPENDENCY_SYMLINK_DENIED')
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        inventory.append({'name': name, 'version': dist.version})
    Path('/runner-dependencies.json').write_text(json.dumps(sorted(inventory, key=lambda p: p['name']), indent=2) + '\n')


if __name__ == '__main__':
    main()
