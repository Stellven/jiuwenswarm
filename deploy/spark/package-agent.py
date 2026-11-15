"""Package the exercised native agent dependency closure without resolving PyPI.

Run with the existing approved ARM64 factory environment. The output is an
owned Docker build context, never the user's home or authentication directory.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Use a new build context; dependency snapshots are immutable')
    repo = Path(__file__).resolve().parents[2]
    os.environ['JIUWENSWARM_SKIP_DOTENV'] = '1'
    sys.path.insert(0, str(repo))
    from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm  # noqa: F401
    from jiuwenswarm.factory.controller import Controller  # noqa: F401
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    mapping = metadata.packages_distributions()
    names = {'openai-codex-cli-bin', 'rfc8785', 'psutil', 'PyYAML', 'jsonschema'}
    for module in list(sys.modules):
        names.update(mapping.get(module.split('.')[0], []))
    names = {canonicalize_name(n) for n in names} - {'workswarm', 'pip', 'setuptools'}
    queue = list(names)
    while queue:
        name = queue.pop()
        for raw in metadata.requires(name) or []:
            requirement = Requirement(raw)
            if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency not in names and dependency not in {'workswarm', 'pip', 'setuptools'}:
                metadata.distribution(dependency)  # fail on an incomplete existing environment
                names.add(dependency)
                queue.append(dependency)
    target = a.output / 'site'
    target.mkdir(parents=True)
    distributions = []
    for name in sorted(names):
        dist = metadata.distribution(name)
        origin = Path(dist.locate_file('')).resolve()
        direct = dist.read_text('direct_url.json')
        distributions.append(dict(name=name, version=dist.version,
                                  direct_url=json.loads(direct) if direct else None))
        for item in dist.files or []:
            relative = Path(str(item))
            if relative.is_absolute() or '..' in relative.parts or '__pycache__' in relative.parts:
                continue
            source = origin / relative
            if source.is_file():
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    shutil.copytree(repo / 'jiuwenswarm', a.output / 'jiuwenswarm',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(repo / 'deploy/spark', a.output / 'deploy/spark',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Codex shell tools and clean local integration commits need native Git.
    # Copy exact local executables/libraries; do not install global packages.
    files = [Path('/usr/bin/git'), Path('/usr/bin/bash')]
    libraries = set()
    for executable in files:
        raw = subprocess.check_output(['ldd', str(executable)], text=True)
        for line in raw.splitlines():
            parts = line.split()
            candidate = parts[2] if '=>' in parts and len(parts) > 2 else parts[0] if parts else ''
            if candidate.startswith('/') and Path(candidate).is_file():
                libraries.add(Path(candidate))
    for source in [*files, *libraries]:
        relative = source.relative_to('/')
        if relative.parts[0] == 'lib':
            relative = Path('usr') / relative
        destination = a.output / 'system' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    git_exec = Path(subprocess.check_output(['git', '--exec-path'], text=True).strip())
    shutil.copytree(git_exec, a.output / 'system' / git_exec.relative_to('/'), symlinks=False)
    manifest = dict(purpose='Exercised JiuwenSwarm factory agent closure; not full project dependencies',
                    architecture=os.uname().machine, python=sys.version,
                    distributions=distributions,
                    files={str(p.relative_to(a.output)): sha(p) for p in sorted(a.output.rglob('*')) if p.is_file()})
    (a.output / 'closure.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (a.output / 'requirements-agent.lock').write_text('\n'.join(
        f"{d['name']}=={d['version']}" for d in distributions) + '\n')
    shutil.copy2(repo / 'deploy/spark/Agent.Dockerfile', a.output / 'Dockerfile')
    print(json.dumps(dict(packages=len(distributions), files=len(manifest['files']),
                          output=str(a.output), closure_sha256=sha(a.output / 'closure.json'))))


if __name__ == '__main__':
    main()
