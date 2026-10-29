"""Explicit authoring-time release freezing; never called by app startup."""
import argparse
import hashlib
import json
from pathlib import Path


def freeze(name, identity):
    root = Path(__file__).parent
    directory = root / name
    paths = sorted(directory.glob('*.py'))
    result = {'name': identity, 'module': name, 'files': {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'shared_runtime': {'path': 'packet.py',
            'sha256': hashlib.sha256((root / 'packet.py').read_bytes()).hexdigest()}}
    dependency_manifest = directory / 'release.dependencies.json'
    if dependency_manifest.exists():
        dependencies = json.loads(dependency_manifest.read_text('utf-8'))
        if (not isinstance(dependencies, list) or any(type(path) is not str for path in dependencies)
                or len(set(dependencies)) != len(dependencies)):
            raise ValueError('release.dependencies.json must be a list of unique relative paths')
        result['shared_dependencies'] = [{'path': path,
            'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()} for path in dependencies]
    (directory / 'release.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module')
    parser.add_argument('identity')
    args = parser.parse_args()
    if not args.module.isidentifier():
        parser.error('module must be one installed package name')
    freeze(args.module, args.identity)


if __name__ == '__main__':
    main()
