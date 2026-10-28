"""Frozen whole-package runtime adapter for registered selected packet releases.

This module only validates/captures source facts and constructs child programs.
It never imports or executes a proposed carrier in an authority owner. Runtime
installation, development grants, isolation and dispatch remain broker duties.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
from types import MappingProxyType

from ..records import encoded
from ..process_policy import POLICY

LEGACY_SCHEMA = 'ai4r-rsi-capsule-runtime:1'
SCHEMA = 'ai4r-rsi-capsule-runtime:2'
BOOTSTRAP_SCHEMA = 'ai4r-rsi-capsule-bootstrap:2'
MAX_FILES = 30000
MAX_RUNTIME_BYTES = 512 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
from .capsules import runtime_target_bindings, registered_capsule, release_binding

TARGET_MODULES = MappingProxyType({name: row['selected_worker_module']
    for name, row in runtime_target_bindings().items()})
LEGACY_TARGET_MODULES = {'utility.calculate': 'jiuwenswarm.research.capsule_extensions.calculate.worker',
    'utility.table_normalize': 'jiuwenswarm.research.capsule_extensions.table_normalize.worker'}


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value or any(ord(c) < 32 for c in value)
            or value.startswith('/') or any(p in {'', '.', '..'} for p in value.split('/'))
            or PurePosixPath(value).is_absolute()):
        raise ValueError('Normalized relative runtime path required')
    if value.split('/')[0] not in {'source', 'dependencies'}:
        raise ValueError('Runtime must contain only source and dependency code trees')
    if any(p.casefold() in {'.git', '__pycache__', 'accounts', 'auth', 'credentials',
            'volumes', 'runtime-data', 'private-fixtures', 'hidden-fixtures', 'fixtures'} for p in value.split('/')):
        raise ValueError('Runtime data/auth/fixture trees are forbidden')
    if value.endswith(('.pyc', '.pyo')):
        raise ValueError('Capture source and installed runtime dependencies, not stale bytecode')
    return value


def python_identity():
    return {'implementation': sys.implementation.name, 'cache_tag': sys.implementation.cache_tag,
        'version': list(sys.version_info[:3]), 'machine': platform.machine(),
        'executable_sha256': _digest(Path(sys.executable).resolve(strict=True).read_bytes())}


def inventory_runtime(root):
    """Inventory an already staged, reviewed code-only tree; never copy a host tree.

    The Root installer chooses the dependency/source closure before calling this.
    Every staged file is captured, including package data and binary dependencies.
    The manifest is stored separately from the read-only runtime directory.
    """
    root = Path(root)
    if not root.is_absolute() or any(path.is_symlink() for path in (root, *root.parents)) or not root.is_dir():
        raise ValueError('Real staged runtime directory required')
    rows = []
    seen = set()
    total = 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Runtime symlinks are forbidden')
        if path.is_dir():
            continue
        meta = path.stat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise ValueError('Runtime requires ordinary independent files')
        name = _path(path.relative_to(root).as_posix())
        if name.casefold() in seen:
            raise ValueError('Case-insensitive runtime path collision')
        seen.add(name.casefold())
        total += meta.st_size
        if len(rows) >= MAX_FILES or total > MAX_RUNTIME_BYTES:
            raise ValueError('Runtime closure exceeds fixed bounds')
        raw = path.read_bytes()
        rows.append({'path': name, 'sha256': _digest(raw), 'size_bytes': len(raw)})
        if len(rows) > MAX_FILES or total > MAX_RUNTIME_BYTES:
            raise ValueError('Runtime closure exceeds fixed bounds')
    return rows


def capture_runtime_manifest(root, *, build_id, dependency_environment, python=None):
    """Capture the exact Root-staged installed closure without granting execution."""
    if not isinstance(build_id, str) or not build_id or len(build_id) > 256:
        raise ValueError('Exact installed source build identity required')
    if (not isinstance(dependency_environment, dict) or not dependency_environment
            or not isinstance(dependency_environment.get('distributions'), list)):
        raise ValueError('Reviewed installed dependency environment facts required')
    value = {'schema': SCHEMA, 'build_id': build_id, 'python': python or python_identity(),
        'dependency_environment': dependency_environment, 'files': inventory_runtime(root),
        'target_modules': dict(TARGET_MODULES), 'target_bindings': runtime_target_bindings(), 'candidate_scope': 'actual_worker_source_only',
        'source_admission': 'UNKNOWN', 'scope': 'public_m1_development_only'}
    # Derived closure first: every import-time edge/resource of the finite
    # targets must be staged, reported with the exact missing path.
    require_runtime_closure(root, value)
    validate_runtime_manifest(value)
    return value


def validate_runtime_manifest(value):
    fields = {'schema', 'build_id', 'python', 'dependency_environment', 'files', 'target_modules',
        'candidate_scope', 'source_admission', 'scope'}
    if isinstance(value, dict) and value.get('schema') == SCHEMA:
        fields.add('target_bindings')
    if (not isinstance(value, dict) or set(value) != fields or value['schema'] not in (SCHEMA, LEGACY_SCHEMA)
            or value['target_modules'] != (TARGET_MODULES if value['schema'] == SCHEMA else LEGACY_TARGET_MODULES) or value['candidate_scope'] != 'actual_worker_source_only'
            or value['source_admission'] != 'UNKNOWN' or value['scope'] != 'public_m1_development_only'):
        raise ValueError('Unknown finite capsule runtime manifest')
    py = value['python']
    if (not isinstance(py, dict) or set(py) != {'implementation', 'cache_tag', 'version', 'machine', 'executable_sha256'}
            or py['implementation'] != 'cpython' or not isinstance(py['version'], list) or len(py['version']) != 3
            or any(type(x) is not int or x < 0 for x in py['version'])
            or not isinstance(py['cache_tag'], str) or not isinstance(py['machine'], str)
            or not isinstance(py['executable_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', py['executable_sha256'])):
        raise ValueError('Exact CPython ABI and executable identity required')
    files = value['files']
    if not isinstance(files, list) or not 0 < len(files) <= MAX_FILES:
        raise ValueError('Bounded complete runtime inventory required')
    names = set(); total = 0
    for row in files:
        if not isinstance(row, dict) or set(row) != {'path', 'sha256', 'size_bytes'}:
            raise ValueError('Exact runtime file facts required')
        name = _path(row['path'])
        if (name.casefold() in names or type(row['size_bytes']) is not int or row['size_bytes'] < 0
                or not isinstance(row['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise ValueError('Runtime collision or invalid file identity')
        names.add(name.casefold()); total += row['size_bytes']
    modules = value['target_modules']
    if value['schema'] == SCHEMA:
        # Normalize JSON tuples/lists before exact source-derived comparison.
        if encoded(value['target_bindings']) != encoded(runtime_target_bindings()):
            raise ValueError('Frozen selected release binding differs')
    required = {'source/' + module.replace('.', '/') + '.py' for module in modules.values()}
    required |= {path.removesuffix('worker.py') + 'checks.py' for path in required}
    required |= {'source/jiuwenswarm/research/capsule_extensions/packet.py',
        'source/jiuwenswarm/research/runner.py', 'source/jiuwenswarm/research/state.py',
        'source/jiuwenswarm/research/contracts/validators.py',
        'source/jiuwenswarm/research_contracts/schemas/work-packet.schema.json'}
    if value['schema'] == SCHEMA:
        for binding in value['target_bindings'].values():
            release_manifest = Path(__file__).resolve().parents[2] / 'research/capsule_extensions' / binding['release_module'] / 'release.json'
            if _digest(release_manifest.read_bytes()) != binding['release_manifest_sha256']:
                raise ValueError('Selected release manifest changed')
            for path, pin in binding['dependency_pins']:
                source = 'source/jiuwenswarm/' + path
                if not any(row['path'] == source and row['sha256'] == pin for row in files):
                    raise ValueError('Frozen release dependency missing or changed: ' + source)
                required.add(source)
    if not required <= names or total > MAX_RUNTIME_BYTES:
        raise ValueError('Real capsule/runtime contract dependency source is missing')
    if any(name.startswith('dependencies/jiuwenswarm/') or name == 'dependencies/jiuwenswarm.py' for name in names):
        raise ValueError('Dependency tree must not shadow the frozen source package')
    if (not isinstance(value['build_id'], str) or not value['build_id'] or len(value['build_id']) > 256
            or not isinstance(value['dependency_environment'], dict)
            or not isinstance(value['dependency_environment'].get('distributions'), list)):
        raise ValueError('Installed build/dependency environment facts required')
    return value


def verify_runtime(root, manifest):
    validate_runtime_manifest(manifest)
    if inventory_runtime(root) != manifest['files']:
        raise ValueError('Read-only runtime differs from its complete frozen inventory')
    return manifest


def runtime_closure(root, files, target_bindings=None):
    """Derive the worker runtime's import/resource closure from its own bytes.

    Entry points are every finite target module and its sibling ``checks``
    module; their transitive import-time imports and ``__file__``/``files()``
    resources must be present under ``source/``. No list is hand-maintained.
    """
    from ..capsule_doctor import source_closure
    root = Path(root)
    sources = {row['path'].removeprefix('source/'): row['sha256'] for row in files if row['path'].startswith('source/')}
    def read(name):
        raw = (root / 'source' / name).read_bytes()
        if _digest(raw) != sources[name]:
            raise ValueError('Runtime source differs from its frozen inventory: ' + name)
        return raw
    bindings = target_bindings or runtime_target_bindings()
    entries = sorted({module for row in bindings.values() for module in (row['selected_worker_module'], row['checks_module'])})
    # The worker imports the target package and executes one entrypoint, so
    # import-time edges are required; function-level imports of the shared
    # research modules are reported as deferred (they belong to authority
    # owners, not to the pure packet carriers).
    return source_closure(sources, read, entry_modules=entries, entry_packages=(), eager_only=True)


def require_runtime_closure(root, manifest):
    """Fail before any job with the first exact missing runtime source path."""
    bindings = manifest.get('target_bindings') or {name: {'selected_worker_module': module,
        'checks_module': module.rpartition('.')[0] + '.checks'}
        for name, module in manifest['target_modules'].items()}
    result = runtime_closure(root, manifest['files'], bindings)
    if not result['complete']:
        first = result['missing'][0]
        raise ValueError('Runtime source closure incomplete: missing source/' + first['path']
                         + ' required by ' + first['required_by'] + f' ({len(result["missing"])} missing)')
    return result


def _child_main(config):
    """Self-contained installed child bootstrap; generated candidate runs only here."""
    import hashlib
    import importlib
    import importlib.util
    import inspect
    import json
    import os
    from pathlib import Path, PurePosixPath
    import platform
    import stat
    import sys
    import types

    def need(ok, reason):
        if not ok:
            raise RuntimeError(reason)
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    def pinned(path, expected, maximum):
        path = Path(path)
        need(not path.is_symlink() and path.is_file(), 'regular pinned asset required')
        raw = path.read_bytes()
        need(len(raw) <= maximum and digest(raw) == expected, 'pinned asset differs')
        return raw
    # Production configuration carries no profile keys: the protected V18
    # worker identity and /resources mount layout are mandatory. Only the
    # explicitly selected local_unprotected profile names its own layout and
    # is tagged as such by its dispatcher; it never claims confinement.
    local = config.get('execution_profile') == 'local_unprotected'
    need(set(config) - {'execution_profile', 'resource_root', 'runtime_root'} == {
        'bootstrap_schema', 'capsule_name', 'manifest_sha256', 'candidate_sha256', 'input_sha256',
        'iterations', 'output_limit_bytes'} and (local or set(config).isdisjoint(
        {'execution_profile', 'resource_root', 'runtime_root'})), 'closed capsule bootstrap configuration required')
    if os.name == 'posix' and not local:
        need(os.getuid() == 12003 and os.getgid() == 12003, 'unprivileged capsule worker identity required')
    need(sys.flags.isolated == 1 and sys.flags.no_site == 1, 'isolated no-site Python bootstrap required')
    resources = Path(config['resource_root'] if local else '/resources/')
    root = Path(config['runtime_root'] if local else '/resources/capsule-runtime')
    manifest = json.loads(pinned(resources / 'capsule-runtime-manifest.json', config['manifest_sha256'], 16 * 1024 * 1024))
    need(manifest['schema'] in ('ai4r-rsi-capsule-runtime:1', 'ai4r-rsi-capsule-runtime:2'), 'unknown runtime schema')
    need(config['capsule_name'] in manifest['target_modules'], 'captured target required')
    if manifest['schema'] == 'ai4r-rsi-capsule-runtime:2':
        binding = manifest['target_bindings'][config['capsule_name']]
        need(binding['selected_worker_module'] == manifest['target_modules'][config['capsule_name']], 'captured carrier differs')
    py = manifest['python']
    need(py == {'implementation': sys.implementation.name, 'cache_tag': sys.implementation.cache_tag,
        'version': list(sys.version_info[:3]), 'machine': platform.machine(),
        'executable_sha256': digest(Path(sys.executable).resolve(strict=True).read_bytes())}, 'captured Python ABI/build differs')
    need(not any(path.is_symlink() for path in (root, *root.parents)), 'runtime root symlink refused')
    expected = {row['path']: row for row in manifest['files']}
    need(len(expected) == len(manifest['files']) <= 30000, 'duplicate or oversized runtime inventory')
    actual = {}; names = set(); total = 0
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(), 'runtime symlink refused')
        if path.is_dir():
            continue
        name = path.relative_to(root).as_posix()
        need(name.split('/')[0] in {'source', 'dependencies'} and '..' not in PurePosixPath(name).parts
             and '\\' not in name and ':' not in name and name.casefold() not in names,
             'runtime path/collision refused')
        names.add(name.casefold())
        meta = path.stat()
        need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, 'runtime file type refused')
        total += meta.st_size
        need(total <= 512 * 1024 * 1024 and len(actual) < 30000, 'runtime size bound exceeded')
        raw = path.read_bytes()
        actual[name] = {'path': name, 'sha256': digest(raw), 'size_bytes': len(raw)}
    need(actual == expected, 'complete runtime inventory differs')
    candidate = pinned(resources / 'body.py', config['candidate_sha256'], 256 * 1024)
    source_input = pinned(resources / 'input.json', config['input_sha256'], 1024 * 1024)
    need(config['bootstrap_schema'] == 'ai4r-rsi-capsule-bootstrap:2', 'unknown capsule bootstrap')
    packet = json.loads(source_input)
    input_name = binding['input_name'] if manifest['schema'] == 'ai4r-rsi-capsule-runtime:2' else 'packet'
    need(isinstance(packet, dict) and set(packet) == {input_name}, 'exact declared capsule input required')
    # Capture an immutable, exact-type snapshot before importing candidate code.
    # Keep the comparator and its primitives local to this trusted bootstrap;
    # candidate JSON output/checkers cannot attest input preservation.
    def snapshot(value, _type=type, _tuple=tuple, _sorted=sorted,
                 _dict=dict, _list=list, _str=str, _int=int, _float=float,
                 _bool=bool, _none=type(None), _error=RuntimeError):
        kind = _type(value)
        if kind is _dict:
            if any(_type(key) is not _str for key in value):
                raise _error('capsule input mutation: non-JSON key')
            return ('dict', _tuple((key, snapshot(value[key])) for key in _sorted(value)))
        if kind is _list:
            return ('list', _tuple(snapshot(item) for item in value))
        if kind in (_str, _int, _float, _bool, _none):
            return (kind, value)
        raise _error('capsule input mutation: non-JSON value')
    original_snapshot = snapshot(packet)
    def require_original(_snapshot=snapshot, _original=original_snapshot, _packet=packet,
                         _error=RuntimeError):
        if _snapshot(_packet) != _original:
            raise _error('capsule input mutation refused')
    # Installed dependencies load from the frozen tree; .pth files are never
    # processed and PYTHONPATH/user site are disabled by -I.
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(root / 'source'), str(root / 'dependencies')]
    module_name = manifest['target_modules'][config['capsule_name']]
    importlib.import_module(module_name.rpartition('.')[0])
    module = types.ModuleType(module_name)
    module.__package__ = module_name.rpartition('.')[0]
    module.__file__ = str(resources / 'body.py')
    module.__spec__ = importlib.util.spec_from_loader(module_name, loader=None)
    sys.modules[module_name] = module
    exec(compile(candidate, str(resources / 'body.py'), 'exec'), module.__dict__)
    require_original()
    raw = None
    for _ in range(config['iterations']):
        # These two pure packet carriers have async entrypoints but contain no
        # suspension/I/O. Drive their real coroutine to completion directly:
        # constructing an event loop would request a socketpair forbidden by
        # the unchanged single-process helper policy. A suspended candidate is
        # refused; no alternate scheduler, socket grant or API shim is added.
        invocation = module.execute(None, packet)
        need(inspect.iscoroutine(invocation), 'actual async carrier entrypoint required')
        try:
            invocation.send(None)
        except StopIteration as complete:
            require_original()
            raw = complete.value['result'].data
        else:
            invocation.close()
            raise RuntimeError('pure capsule carrier must complete without asynchronous I/O')
    need(isinstance(raw, bytes) and len(raw) <= config['output_limit_bytes'], 'bounded actual serialized packet output required')
    # Validate output JSON framing before emitting; independent correctness
    # checking takes place outside this candidate-controlled interpreter.
    json.loads(raw)
    sys.stdout.buffer.write(raw)


EXECUTION_PROFILES = ('v18-bwrap', 'local_unprotected')


def capsule_worker_program(name, *, manifest_sha256, candidate_sha256, input_sha256, iterations=1, process_policy=POLICY,
                           execution_profile='v18-bwrap', resource_root=None, runtime_root=None):
    """Return fixed child bytes. No source supplied by a proposal executes here.

    ``execution_profile='v18-bwrap'`` (default) yields the protected program
    for the /resources mount layout and UID/GID 12003. ``local_unprotected``
    is selected only by explicit configuration: it names real host paths,
    carries no identity requirement and must be dispatched without a policy.
    """
    config = bootstrap_config(name, manifest_sha256=manifest_sha256, candidate_sha256=candidate_sha256,
        input_sha256=input_sha256, iterations=iterations, process_policy=process_policy,
        execution_profile=execution_profile, resource_root=resource_root, runtime_root=runtime_root)
    from ..process_policy import apply_policy
    return apply_policy((inspect.getsource(_child_main) + '\n_child_main(' + repr(config) + ')\n').encode(), process_policy)


def bootstrap_config(name, *, manifest_sha256, candidate_sha256, input_sha256, iterations=1, process_policy=POLICY,
                     execution_profile='v18-bwrap', resource_root=None, runtime_root=None):
    """The closed ``_child_main`` configuration (shared by every guarded program)."""
    if name not in TARGET_MODULES:
        raise ValueError('Unknown finite whole-capsule target')
    for pin in (manifest_sha256, candidate_sha256, input_sha256):
        if not isinstance(pin, str) or not re.fullmatch('[0-9a-f]{64}', pin):
            raise ValueError('Exact asset SHA256 required')
    if type(iterations) is not int or not 1 <= iterations <= 10000:
        raise ValueError('Frozen bounded timing batch required')
    config = {'bootstrap_schema': BOOTSTRAP_SCHEMA, 'capsule_name': name, 'manifest_sha256': manifest_sha256,
        'candidate_sha256': candidate_sha256, 'input_sha256': input_sha256,
        'iterations': iterations, 'output_limit_bytes': MAX_OUTPUT_BYTES}
    if execution_profile not in EXECUTION_PROFILES:
        raise ValueError('Explicit known capsule execution profile required')
    if execution_profile == 'local_unprotected':
        if process_policy is not None:
            raise ValueError('The kernel helper policy requires the protected worker identity')
        for value in (resource_root, runtime_root):
            if not isinstance(value, str) or not Path(value).is_absolute():
                raise ValueError('Absolute local resource/runtime roots required')
        config.update(execution_profile=execution_profile, resource_root=resource_root, runtime_root=runtime_root)
    elif resource_root is not None or runtime_root is not None:
        raise ValueError('Protected programs use the fixed /resources layout')
    return config


def capsule_job_assets(name, *, runtime_root, manifest, candidate, inputs, iterations=1,
                       execution_profile='v18-bwrap', resource_root=None):
    """Broker adapter: verify immutable facts and return finite read-only assets.

    The caller must bind these to a separately authorized unprivileged
    ExecutionJob. This helper neither creates grants nor invokes an executor.
    """
    if name not in TARGET_MODULES or not isinstance(candidate, bytes) or not 0 < len(candidate) <= 256 * 1024:
        raise ValueError('Finite capsule candidate body required')
    input_name = manifest.get('target_bindings', {}).get(name, {}).get('input_name', 'packet')
    if not isinstance(inputs, dict) or set(inputs) != {input_name}:
        raise ValueError('Exact capsule packet wrapper required')
    raw = encoded(inputs)
    if len(raw) > 1024 * 1024:
        raise ValueError('Capsule input exceeds fixed bound')
    verify_runtime(runtime_root, manifest)
    manifest_raw = encoded(manifest)
    local = execution_profile == 'local_unprotected'
    program = capsule_worker_program(name, manifest_sha256=_digest(manifest_raw),
        candidate_sha256=_digest(candidate), input_sha256=_digest(raw), iterations=iterations,
        **({'process_policy': None, 'execution_profile': execution_profile, 'resource_root': str(resource_root),
            'runtime_root': str(Path(runtime_root).resolve(strict=True))} if local else
           {'execution_profile': execution_profile}))
    mutable_path = manifest['target_modules'][name].removeprefix('jiuwenswarm.').replace('.', '/') + '.py'
    original_path = 'source/jiuwenswarm/' + mutable_path
    return {'bootstrap_schema': BOOTSTRAP_SCHEMA, 'runtime_root': str(Path(runtime_root).resolve(strict=True)),
        'runtime_manifest_sha256': _digest(manifest_raw),
        'capsule_name': name, 'mutable_path': mutable_path,
        'original_parent_sha256': next(row['sha256'] for row in manifest['files'] if row['path'] == original_path),
        'checks_sha256': next(row['sha256'] for row in manifest['files']
                             if row['path'] == original_path.removesuffix('worker.py') + 'checks.py'),
        'candidate_sha256': _digest(candidate), 'batch_iterations': iterations,
        'files': {'worker.py': program, 'body.py': candidate, 'input.json': raw,
                  'capsule-runtime-manifest.json': manifest_raw},
        'argv': (('-I', '-S', '-B', str(Path(resource_root) / 'worker.py')) if local
                 else ('/usr/local/bin/python3', '-I', '-S', '/resources/worker.py')),
        'output_limit_bytes': MAX_OUTPUT_BYTES, 'required_worker_uid': None if local else 12003,
        'scope': 'local_unprotected' if local else 'public_m1_development_only', 'production_admission': 'UNKNOWN'}


def check_capsule_output(name, *, inputs, output, expected_checks_sha256=None, binding=None):
    """Independent adapter for captured child bytes; never import candidate code.

    The broker authenticates receipt/source/runtime pins before calling this
    installed check owner. Time comes from that receipt, never candidate output.
    """
    from types import SimpleNamespace
    if name not in TARGET_MODULES or not isinstance(inputs, dict) or set(inputs) != {registered_capsule(name).input_name}:
        raise ValueError('Finite capsule and exact original packet wrapper required')
    if not isinstance(output, bytes) or not 0 < len(output) <= MAX_OUTPUT_BYTES:
        raise ValueError('Captured capsule output exceeds fixed bound')
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate capsule output JSON key')
            value[key] = item
        return value
    result = json.loads(output, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite capsule output')))
    import importlib
    current = release_binding(name)
    if binding is not None and encoded(binding) != encoded(current):
        raise ValueError('Installed selected release differs from frozen checking binding')
    binding = binding or current
    root = Path(__file__).resolve().parents[2]
    for path, pin in binding['dependency_pins']:
        if _digest((root / path).read_bytes()) != pin:
            raise ValueError('Installed independent checking dependency differs: ' + path)
    check = importlib.import_module(binding['checks_module']).check
    checks_sha256 = _digest((root / binding['checks_path']).read_bytes())
    if expected_checks_sha256 is not None and expected_checks_sha256 != checks_sha256:
        raise ValueError('Installed independent checker differs from frozen checking source')
    rows = check(SimpleNamespace(output_refs={}), inputs, {'result': result})
    passed = (len(rows) == len(binding['check_ids']) and {row['check_id'] for row in rows} == set(binding['check_ids'])
              and all(row['outcome'] == 'PASS' for row in rows))
    return {'capsule_name': name, 'task_success': passed, 'checks': rows,
        'checks_sha256': checks_sha256,
        'output_bytes': len(output), 'output_sha256': _digest(output),
        'input_sha256': _digest(encoded(inputs)), 'scope': 'public_m1_development_only'}
