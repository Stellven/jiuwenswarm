"""Factory provenance outside the CC protocol; verify before every dispatch."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    root = Path(root).resolve()
    rows = {}
    for path in sorted(root.rglob('*')):
        if '__pycache__' in path.parts or '.git' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            raise ValueError('Frozen sources cannot contain symlinks')
        if path.is_file():
            rows[path.relative_to(root).as_posix()] = file_digest(path)
    if not rows:
        raise ValueError('Empty source snapshot')
    return rows


def freeze(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination == source or destination.is_relative_to(source):
        raise ValueError('Snapshot must be outside its source')
    before = inventory(source)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    if inventory(destination) != before or inventory(source) != before:
        raise ValueError('Source changed while freezing')
    return dict(root=str(destination), files=before, sha256=digest(before))


def create(host, release, backend, runtime, components=()):
    host.release(release)
    if set(runtime) == {'interpreters', 'dependencies', 'images'}:
        if not runtime['interpreters'] or any(not re.fullmatch(r'[0-9a-f]{64}',v) for v in runtime['interpreters']):
            raise ValueError('Pinned interpreter identities required')
        if any(not re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in runtime['images']):
            raise ValueError('Pinned runtime images required')
        for path,expected in runtime['dependencies'].items():
            if file_digest(path)!=expected: raise ValueError('Dependency identity differs')
    elif set(runtime) == {'image'}:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', runtime['image']):
            raise ValueError('Runtime image must be immutable')
    elif set(runtime) == {'python', 'sha256', 'dependencies'}:
        if file_digest(runtime['python']) != runtime['sha256']:
            raise ValueError('Interpreter identity differs')
        if not runtime['dependencies']:
            raise ValueError('Pinned dependency files required')
        for path, expected in runtime['dependencies'].items():
            if file_digest(path) != expected:
                raise ValueError('Dependency identity differs')
    else:
        raise ValueError('Explicit image or interpreter/dependency identity required')
    selected = []
    from jiuwenswarm.ccv2.roles import read_roles
    for item in components:
        declaration, bundle = host.release(item['release'])
        roles = read_roles(declaration, bundle)
        if roles['materials'].get(item['material']) != 'component':
            raise ValueError('Selected material is not a component')
        material = host.material(item['release'], item['material'])
        selected.append(dict(item, artifact=material['artifact']))
    if inventory(backend['root']) != backend['files'] or digest(backend['files']) != backend['sha256']:
        raise ValueError('Backend snapshot differs')
    record = dict(format='factory-execution-binding/1', release=release,
                  backend=backend, runtime=runtime, components=selected)
    return dict(record, binding_id=digest(record))


def verify(host, binding, *, backend_root=None):
    record = {k: v for k, v in binding.items() if k != 'binding_id'}
    if digest(record) != binding['binding_id']:
        raise ValueError('Execution binding identity differs')
    if backend_root is not None and inventory(backend_root) != binding['backend']['files']:
        raise ValueError('Running backend differs from admitted snapshot')
    actual = create(host, binding['release'], binding['backend'], binding['runtime'],
                    [{k: row[k] for k in ('release', 'material')} for row in binding['components']])
    if actual != binding:
        raise ValueError('Execution binding dependencies changed')
    return binding['binding_id']


def verify_task(store, task_id):
    task = store.get_task(task_id)
    binding = task.get('constraints', {}).get('execution_binding')
    if binding is None:
        return None  # historical tasks retain their original contract
    if 'interpreters' in binding['runtime'] and file_digest(sys.executable) not in binding['runtime']['interpreters']:
        raise ValueError('Running interpreter is outside admitted environments')
    if 'python' in binding['runtime'] and file_digest(sys.executable) != binding['runtime']['sha256']:
        raise ValueError('Running interpreter differs from admitted interpreter')
    from jiuwenswarm.ccv2.ccv2 import Host
    base = getattr(store, '_store', store)
    return verify(Host(base.home / 'ccstore', session_grants=[]), binding,
                  backend_root=Path(__file__).parent)


def worker_environment(binding):
    """Prevent a queue working directory from shadowing the admitted backend."""
    return dict(PYTHONPATH=str(Path(binding['backend']['root']).parents[1]), PYTHONSAFEPATH='1')
