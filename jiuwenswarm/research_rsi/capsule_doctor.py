"""Actual frozen composition on private snapshots, without model/work effects.

Original Core, input, account and session stores must be mounted read-only.
Only a precreated private scratch directory is writable. No session execution,
DevelopmentModel, evaluation dispatcher, admission or activation is invoked.
"""
from __future__ import annotations
import asyncio
import copy
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile

SCHEMA = 'ai4r-rsi-capsule-compose-doctor:1'
CLOSURE_SCHEMA = 'ai4r-rsi-source-closure:1'
MAX_SNAPSHOT_BYTES = 1024 * 1024 * 1024
MAX_FILES = 30000
PACKAGE = 'jiuwenswarm'
# Controller/evaluator source roots of the RSI capsule engine. Every module in
# these packages, plus explicitly supplied entry programs, is a closure root.
CONTROLLER_ENTRY_PACKAGES = ('jiuwenswarm.research_rsi', 'jiuwenswarm.research')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Static source closure. This module must stay importable stand-alone (stdlib
# only at module level): the Root launcher loads it by pinned path before any
# package import, so a missing file is reported before a run is accepted.
# ---------------------------------------------------------------------------

class ChainEnv(dict):
    """Function-scope bindings falling back to module-level bindings."""
    def __init__(self, parent):
        super().__init__(); self.parent = parent

    def get(self, key, default=None):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        return self.parent.get(key, default)


class _Closure:
    """Static walk of imports and ``__file__``-relative resources.

    ``files`` maps package-relative POSIX names (``jiuwenswarm/...``) to a
    reader returning bytes. Nothing is imported or executed. Imports under
    ``try/except ImportError`` are optional; every other import, at any
    nesting level, is required because lazy imports run inside the same
    frozen owners. Path expressions are evaluated symbolically from
    ``Path(__file__)``, ``Path(<module>.__file__)`` and
    ``importlib.resources.files('<package>')`` through ``parent``,
    ``parents[n]``, ``with_name``, ``/`` and ``joinpath`` with literal parts.
    """

    def __init__(self, files, read, *, eager_only=False):
        import ast
        self.ast = ast
        self.files, self.read, self.eager_only = set(files), read, eager_only
        self.directories = {name.rsplit('/', i)[0] for name in self.files for i in range(1, name.count('/') + 1)}
        self.modules, self.resources, self.missing, self.optional_missing = {}, {}, {}, {}
        self.deferred_missing, self.unresolved = {}, {}
        self.dynamic = 0

    # -- module naming ---------------------------------------------------
    def module_file(self, module):
        base = module.replace('.', '/')
        for name in (base + '.py', base + '/__init__.py'):
            if name in self.files:
                return name
        return None

    @staticmethod
    def module_name(name):
        stem = name[:-3]
        return stem[:-len('/__init__')].replace('/', '.') if stem.endswith('/__init__') else stem.replace('/', '.')

    def require_module(self, module, origin, optional):
        if module != PACKAGE and not module.startswith(PACKAGE + '.'):
            return None
        parts = module.split('.')
        found = None
        for index in range(1, len(parts) + 1):
            prefix = '.'.join(parts[:index])
            found = self.module_file(prefix)
            if found is None:
                if prefix.replace('.', '/') in self.directories and index < len(parts):
                    continue  # PEP 420 namespace directory, e.g. data-only trees.
                expected = prefix.replace('.', '/') + '.py'
                self.bucket(optional).setdefault(expected, origin)
                return None
            self.modules.setdefault(found, origin)
        return found

    def bucket(self, optional):
        return {False: self.missing, 'optional': self.optional_missing, 'deferred': self.deferred_missing,
                'unresolved': self.unresolved}[optional]

    def require_path(self, name, origin, optional=False):
        if name in self.files or name in self.directories:
            self.resources.setdefault(name, origin)
        else:
            self.bucket(optional).setdefault(name, origin)

    # -- walk --------------------------------------------------------------
    def walk(self, roots):
        pending = list(roots); seen = set()
        while pending:
            name, origin = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            raw = self.read(name)
            try:
                tree = self.parse(name, raw)
            except SyntaxError as error:
                self.missing.setdefault(name + ':syntax', f'{origin} ({error.msg})')
                continue
            package = self.module_name(name) if name.endswith('/__init__.py') else self.module_name(name).rpartition('.')[0]
            for found in self.visit(tree, name, package):
                if found not in seen:
                    pending.append((found, name))
        return self

    def visit(self, tree, name, package):
        ast = self.ast
        found = []
        # One pass labels every node: inside a try/except-ImportError body
        # (optional) and/or inside a function body (nested).
        optional_nodes, nested_nodes, ordered = set(), set(), []
        functions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        stack = [(tree, False, False)]
        while stack:
            node, optional, nested = stack.pop()
            ordered.append(node)
            if optional: optional_nodes.add(id(node))
            if nested: nested_nodes.add(id(node))
            if isinstance(node, ast.Try) and any(self.catches_import_error(handler) for handler in node.handlers):
                body = {id(item) for item in node.body}
                stack.extend((child, optional or id(child) in body, nested) for child in ast.iter_child_nodes(node))
            elif isinstance(node, functions):
                body = {id(item) for item in (node.body if isinstance(node.body, list) else [node.body])}
                stack.extend((child, optional, nested or id(child) in body) for child in ast.iter_child_nodes(node))
            else:
                stack.extend((child, optional, nested) for child in ast.iter_child_nodes(node))
        deferred_nodes = nested_nodes if self.eager_only else set()
        imported = {}  # local alias -> module name, for Path(alias.__file__)
        hits = []
        for node in ordered:
            optional = 'optional' if id(node) in optional_nodes else 'deferred' if id(node) in deferred_nodes else False
            found = [] if optional == 'deferred' else hits  # Deferred hits are recorded, not walked.
            origin = f'{name}:{getattr(node, "lineno", 0)}'
            if isinstance(node, ast.Import):
                for alias in node.names:
                    hit = self.require_module(alias.name, origin, optional)
                    if hit: found.append(hit)
                    imported[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package.split('.') if package else []
                    if node.level > 1:
                        base = base[:len(base) - node.level + 1]
                    module = '.'.join(base + ([node.module] if node.module else []))
                else:
                    module = node.module or ''
                hit = self.require_module(module, origin, optional)
                if hit: found.append(hit)
                for alias in node.names:
                    if alias.name == '*':
                        continue
                    child = module + '.' + alias.name
                    if self.module_file(child):
                        hit = self.require_module(child, origin, optional)
                        if hit: found.append(hit)
                    elif not self.defines(module, alias.name):
                        # Neither a submodule nor a bound name: Python would
                        # need ``module.name`` as a module file. At import time
                        # that is a missing file; inside a function body it is
                        # reported as an unresolved lazy name (non-blocking).
                        self.require_module(child, origin, optional or (
                            'unresolved' if id(node) in nested_nodes else False))
                    imported[alias.asname or alias.name] = child
            elif isinstance(node, ast.Call):
                target = self.call_name(node.func)
                if (target in {'import_module', 'importlib.import_module'} and node.args
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    hit = self.require_module(node.args[0].value, origin, optional)
                    if hit: found.append(hit)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Literal registries of dotted module names (e.g. capsule
                # target tables) are closure edges when they name a module.
                value = node.value
                if value.startswith(PACKAGE + '.') and all(part.isidentifier() for part in value.split('.')):
                    hit = self.module_file(value)
                    if hit:
                        found.append(self.require_module(value, origin, optional) or hit)
        hits.extend(self.resource_refs(tree, name, imported, deferred_nodes))
        return hits

    def parse(self, name, raw=None):
        trees = self.__dict__.setdefault('_trees', {})
        if name not in trees:
            trees[name] = self.ast.parse(self.read(name) if raw is None else raw, filename=name)
        return trees[name]

    def defines(self, module, name):
        """Whether ``module`` (a file in this tree) binds ``name`` at top level.

        Unknown/out-of-tree modules, star imports and module ``__getattr__``
        are treated as binding everything (no false missing reports).
        """
        found = self.module_file(module) if module.startswith(PACKAGE) else None
        if found is None:
            return True
        cache = self.__dict__.setdefault('_bindings', {})
        if found not in cache:
            ast = self.ast
            names = set()
            try:
                tree = self.parse(found)
            except SyntaxError:
                cache[found] = None
                return True
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        names.add('*' if alias.name == '*' else (alias.asname or alias.name.split('.')[0]))
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    names.add(node.id)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier():
                    names.add(node.value)  # __all__ / globals() style registrations.
                elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                      and isinstance(node.value, ast.Attribute) and node.value.attr == 'modules'):
                    names.add('*')  # sys.modules[__name__] = alias module.
            cache[found] = names
        names = cache[found]
        return names is None or name in names or '*' in names or '__getattr__' in names

    def catches_import_error(self, handler):
        ast = self.ast
        if handler.type is None:
            return True
        names = [handler.type] if not isinstance(handler.type, ast.Tuple) else list(handler.type.elts)
        return any(isinstance(item, ast.Name) and item.id in {'ImportError', 'ModuleNotFoundError', 'Exception', 'BaseException'}
                   for item in names)

    def call_name(self, func):
        ast = self.ast
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return func.value.id + '.' + func.attr
        return func.attr if isinstance(func, ast.Attribute) else None

    # -- symbolic package-relative paths ----------------------------------
    # A path value is a package-relative POSIX string. Only consumption creates
    # a requirement (reading, opening, listing, loading as a module); probes
    # such as exists()/is_dir() describe optional layouts and are not required.
    CONSUMERS = frozenset({'read_bytes', 'read_text', 'open', 'iterdir', 'glob', 'rglob', 'stat',
                           'lstat', 'readlink', 'samefile'})
    CONSUMING_CALLS = frozenset({'open', 'io.open', 'spec_from_file_location', 'util.spec_from_file_location',
                                 'shutil.copyfile', 'shutil.copy', 'shutil.copy2', 'shutil.copytree', 'runpy.run_path'})
    PROBES = frozenset({'exists', 'is_dir', 'is_file'})

    def scopes(self, tree):
        """Yield (scope_node, own_nodes) without descending into nested defs."""
        ast = self.ast
        definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        stack = [tree]
        while stack:
            scope = stack.pop()
            own = []
            pending = list(ast.iter_child_nodes(scope))
            while pending:
                node = pending.pop()
                if isinstance(node, definitions):
                    stack.append(node)
                    # Decorators evaluate in the enclosing scope.
                    pending.extend(getattr(node, 'decorator_list', []))
                    continue
                own.append(node)
                pending.extend(ast.iter_child_nodes(node))
            yield scope, own

    def resource_refs(self, tree, name, imported, deferred_nodes=frozenset()):
        ast = self.ast
        found = []
        module_env = {}
        for scope, nodes in self.scopes(tree):
            env = module_env if scope is tree else ChainEnv(module_env)
            for node in sorted((n for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign, ast.NamedExpr))),
                               key=lambda n: (getattr(n, 'lineno', 0), getattr(n, 'col_offset', 0))):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if len(targets) == 1 and isinstance(targets[0], ast.Name) and node.value is not None:
                    env[targets[0].id] = self.path_value(node.value, name, imported, env)
            probed = set()
            for node in nodes:
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in self.PROBES):
                    path = self.path_value(node.func.value, name, imported, env)
                    if path is not None:
                        probed.add(path)
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue
                targets = []
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in self.CONSUMERS:
                    targets.append(func.value)
                if self.call_name(func) in self.CONSUMING_CALLS:
                    targets.extend(node.args[:2])
                for target in targets:
                    path = self.path_value(target, name, imported, env)
                    if path is None or path.split('/')[0] != PACKAGE:
                        continue  # Dynamic, or outside this package (host layout).
                    origin = f'{name}:{getattr(node, "lineno", 0)}'
                    if id(node) in deferred_nodes:
                        self.require_path(path, origin, 'deferred')
                        continue
                    if path in probed:
                        # Same-scope existence probe: an optional layout.
                        if path not in self.files and path not in self.directories:
                            self.optional_missing.setdefault(path, origin)
                        continue
                    self.require_path(path, origin)
                    if path in self.files and path.endswith('.py'):
                        found.append(path)
        return found

    def path_value(self, node, name, imported, env):
        """Return a package-relative path string, or None when not literal."""
        ast = self.ast
        if isinstance(node, ast.Name):
            return env.get(node.id)
        if isinstance(node, ast.Call):
            func = node.func
            callee = self.call_name(func)
            if callee in {'Path', 'pathlib.Path', 'PurePath', 'PurePosixPath'} and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Name) and arg.id == '__file__':
                    return name
                if (isinstance(arg, ast.Attribute) and arg.attr == '__file__' and isinstance(arg.value, ast.Name)
                        and arg.value.id in imported):
                    return self.module_file(imported[arg.value.id])
                return None if isinstance(arg, ast.Constant) else self.path_value(arg, name, imported, env)
            if callee in {'files', 'resources.files', 'importlib.resources.files'} and len(node.args) == 1:
                package = self.literal(node.args[0])
                if package is None or not (package == PACKAGE or package.startswith(PACKAGE + '.')):
                    return None
                return package.replace('.', '/')  # Package directory (traversable).
            if isinstance(func, ast.Attribute):
                base = self.path_value(func.value, name, imported, env)
                if base is None:
                    return None
                if func.attr in {'resolve', 'absolute', 'expanduser'} and not node.args:
                    return base
                if func.attr == 'with_name' and len(node.args) == 1:
                    part = self.literal(node.args[0])
                    if part is None:
                        self.dynamic += 1; return None
                    return self.join(self.parent(base), part)
                if func.attr == 'joinpath':
                    parts = [self.literal(arg) for arg in node.args]
                    if not parts or any(part is None for part in parts):
                        self.dynamic += 1; return None
                    return self.join(base, *parts)
            return None
        if isinstance(node, ast.Attribute):
            if node.attr == 'parent':
                base = self.path_value(node.value, name, imported, env)
                return None if base is None else self.parent(base)
            return None
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'parents':
            base = self.path_value(node.value.value, name, imported, env)
            index = self.literal(node.slice, kind=int)
            if base is None or index is None:
                return None
            for _ in range(index + 1):
                base = self.parent(base)
            return base
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            base = self.path_value(node.left, name, imported, env)
            if base is None:
                return None
            part = self.literal(node.right)
            if part is None:
                self.dynamic += 1; return None
            return self.join(base, part)
        return None

    @staticmethod
    def parent(path):
        # Climbing above the package root leaves this package's namespace.
        return path.rpartition('/')[0] if '/' in path else '..'

    @staticmethod
    def join(path, *parts):
        segments = path.split('/') if path else []
        for part in parts:
            for segment in part.split('/'):
                if segment in ('', '.'):
                    continue
                if segment == '..':
                    if segments: segments.pop()
                else:
                    segments.append(segment)
        return '/'.join(segments)

    def literal(self, node, kind=str):
        ast = self.ast
        if isinstance(node, ast.Constant) and type(node.value) is kind:
            return node.value
        return None


def source_closure(files, read, *, entry_modules=(), entry_files=(), entry_packages=CONTROLLER_ENTRY_PACKAGES,
                   eager_only=False):
    """Return the derived import/resource closure of a source tree.

    ``files`` is the complete inventory (``jiuwenswarm/...`` names); ``read``
    returns a pinned file's bytes; ``entry_files`` maps extra entry program
    names (outside the package, e.g. the runner) to bytes.
    """
    files = set(files)
    extra = dict(entry_files)
    closure = _Closure(files | set(extra), lambda name: extra[name] if name in extra else read(name),
                       eager_only=eager_only)
    roots = [(name, 'entry') for name in sorted(extra)]
    for package in entry_packages:
        prefix = package.replace('.', '/') + '/'
        roots += [(name, 'entry-package:' + package) for name in sorted(files)
                  if name.startswith(prefix) and name.endswith('.py')]
        init = closure.require_module(package, 'entry-package:' + package, False)
        if init: roots.append((init, 'entry-package:' + package))
    for module in entry_modules:
        hit = closure.require_module(module, 'entry-module:' + module, False)
        if hit: roots.append((hit, 'entry-module:' + module))
    closure.walk(roots)
    modules = sorted(name for name in closure.modules if name not in extra)
    return {'schema': CLOSURE_SCHEMA, 'complete': not closure.missing,
            'entry_packages': list(entry_packages), 'entry_modules': list(entry_modules),
            'entry_files': sorted(extra),
            'module_count': len(modules), 'resource_count': len(closure.resources),
            'modules_sha256': digest(json.dumps(modules, separators=(',', ':')).encode()),
            'missing': [{'path': path, 'required_by': origin} for path, origin in sorted(closure.missing.items())],
            'optional_missing': [{'path': path, 'required_by': origin}
                                 for path, origin in sorted(closure.optional_missing.items())],
            'mode': 'import_time' if eager_only else 'all_imports',
            'deferred_missing': [{'path': path, 'required_by': origin}
                                 for path, origin in sorted(closure.deferred_missing.items())],
            'unresolved_lazy_names': [{'path': path, 'required_by': origin}
                                      for path, origin in sorted(closure.unresolved.items())],
            'dynamic_path_expressions': closure.dynamic}


def require_source_closure(source_root, pins, *, entry_files=(), entry_modules=(),
                           entry_packages=CONTROLLER_ENTRY_PACKAGES):
    """Fail with the first exact missing package path before any run claim.

    ``pins`` is the run configuration's complete ``jiuwenswarm/...`` inventory.
    Each parsed file is digest-checked against its pin while it is read.
    """
    root = Path(source_root)
    need(isinstance(pins, dict) and pins, 'PINNED_SOURCE_CLOSURE_REQUIRED')
    def read(name):
        raw = (root / name).read_bytes()
        need(digest(raw) == pins[name], 'SOURCE_PIN_DIFFERS: ' + name)
        return raw
    entries = {}
    for path in entry_files:
        path = Path(path)
        entries['entry:' + path.name] = path.read_bytes()
    result = source_closure(pins, read, entry_modules=entry_modules, entry_files=entries,
                            entry_packages=entry_packages)
    if not result['complete']:
        first = result['missing'][0]
        raise ValueError('SOURCE_CLOSURE_INCOMPLETE: missing ' + first['path'] + ' required by '
                         + first['required_by'] + f' ({len(result["missing"])} missing)')
    return result


# ---------------------------------------------------------------------------
# Persisted closure proof. The derived closure is a pure function of the
# pinned inventory and bytes, the entry programs and this walker's own source,
# so it is computed once per installed package and reused by every later
# preflight after re-verifying those pins (no re-walk). The proof directory is
# created by Root preparation (``create_proof_directory``); without it every
# caller walks exactly as before. A changed package has a different key.
# ---------------------------------------------------------------------------

PROOF_SCHEMA = 'ai4r-rsi-source-closure-proof:1'
PROOF_DIRECTORY = '.ai4r-source-closure'
MAX_PROOF_BYTES = 1024 * 1024


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')


def walker_sha256():
    """Digest of the closure walker's own source bytes (this module)."""
    return digest(Path(__file__).read_bytes())


def closure_proof_key(pins, *, entry_files=(), entry_modules=(), entry_packages=CONTROLLER_ENTRY_PACKAGES):
    entries = sorted([str(Path(path)), digest(Path(path).read_bytes())] for path in entry_files)
    return {'schema': PROOF_SCHEMA, 'walker_sha256': walker_sha256(),
            'pins_sha256': digest(_canonical(pins)), 'entry_files': entries,
            'entry_modules': list(entry_modules), 'entry_packages': list(entry_packages)}


def _proof_owner(source_root):
    meta = Path(source_root).lstat()
    need(stat.S_ISDIR(meta.st_mode) and not stat.S_ISLNK(meta.st_mode), 'SOURCE_ROOT_DIRECTORY_REQUIRED')
    return meta.st_uid


def _proof_directory(source_root):
    """The package's proof directory when it exists with the package owner's
    custody (no symlink, no group/other write); otherwise None."""
    directory = Path(source_root) / PROOF_DIRECTORY
    try:
        meta = directory.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != _proof_owner(source_root) or meta.st_mode & 0o022):
        return None
    return directory


def create_proof_directory(source_root):
    """Root preparation opts an installed package into persisted proofs."""
    directory = Path(source_root) / PROOF_DIRECTORY
    if not os.path.lexists(directory) and os.geteuid() == _proof_owner(source_root):
        try:
            directory.mkdir(mode=0o755)
            os.chmod(directory, 0o755)
        except FileExistsError:
            pass
    return _proof_directory(source_root)


def inventory_sha256(source_root, pins):
    """Digest of the actual ``jiuwenswarm/`` inventory when it equals the
    pins exactly (names and bytes); None when anything differs."""
    root = Path(source_root)
    actual = {}
    for path in sorted((root / PACKAGE).rglob('*')):
        if path.is_symlink():
            return None
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if name not in pins:
                return None
            actual[name] = digest(path.read_bytes())
    if actual != pins:
        return None
    return digest(_canonical(sorted(actual.items())))


def read_closure_proof(source_root, pins, key):
    """The stored closure for exactly this key, after re-verifying the pins."""
    directory = _proof_directory(source_root)
    if directory is None:
        return None
    path = directory / (digest(_canonical(key)) + '.json')
    try:
        meta = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != _proof_owner(source_root) or meta.st_mode & 0o022
            or meta.st_nlink != 1 or meta.st_size > MAX_PROOF_BYTES):
        return None
    try:
        proof = json.loads(path.read_bytes())
    except ValueError:
        return None
    if (not isinstance(proof, dict) or proof.get('schema') != PROOF_SCHEMA or proof.get('key') != key
            or not isinstance(proof.get('result'), dict) or proof['result'].get('complete') is not True
            or proof['result'].get('schema') != CLOSURE_SCHEMA):
        return None
    if inventory_sha256(source_root, pins) != proof.get('inventory_sha256'):
        return None
    return proof['result']


def write_closure_proof(source_root, key, inventory, result):
    directory = _proof_directory(source_root)
    if directory is None or inventory is None or os.geteuid() != _proof_owner(source_root):
        return None
    raw = _canonical({'schema': PROOF_SCHEMA, 'key': key, 'inventory_sha256': inventory, 'result': result})
    path = directory / (digest(_canonical(key)) + '.json')
    pending = directory / ('.pending-%d-%d' % (os.getpid(), id(raw)))
    try:
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        os.replace(pending, path)  # Replaces only an unusable proof of the same key.
        handle = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(handle)
        finally: os.close(handle)
    except OSError:  # Read-only mounts (doctor/worker) only reuse proofs.
        try: os.unlink(pending)
        except OSError: pass
        return None
    return path


def proven_source_closure(source_root, pins, *, entry_files=(), entry_modules=(),
                          entry_packages=CONTROLLER_ENTRY_PACKAGES):
    """``require_source_closure`` with its result persisted once per package.

    A proof is reused only when its key (walker source, pins digest, entry
    program bytes, entry roots) matches and the actual package inventory and
    bytes equal the pins; otherwise the closure is re-walked with the exact
    same refusals, and persisted when the proof directory is writable.
    """
    need(isinstance(pins, dict) and pins, 'PINNED_SOURCE_CLOSURE_REQUIRED')
    key = closure_proof_key(pins, entry_files=entry_files, entry_modules=entry_modules, entry_packages=entry_packages)
    stored = read_closure_proof(source_root, pins, key)
    if stored is not None:
        return stored
    lock = None
    directory = _proof_directory(source_root)
    try:
        if directory is not None and os.geteuid() == _proof_owner(source_root):
            try:
                import fcntl
                lock = os.open(directory / '.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                fcntl.flock(lock, fcntl.LOCK_EX)  # One walk per package; waiters reuse it.
            except OSError:
                pass
            stored = read_closure_proof(source_root, pins, key)
            if stored is not None:
                return stored
        result = require_source_closure(source_root, pins, entry_files=entry_files, entry_modules=entry_modules,
                                        entry_packages=entry_packages)
        write_closure_proof(source_root, key, inventory_sha256(source_root, pins), result)
        return result
    finally:
        if lock is not None:
            os.close(lock)


# ---------------------------------------------------------------------------
# Worker-identity traversal. Stand-alone (stdlib only) like the closure walk:
# the Root launcher runs it before accepting a run; the evaluator reuses it.
# ---------------------------------------------------------------------------

WORKER_UID = WORKER_GID = 12003
TRAVERSE_MODE = 0o711


def _searchable(meta, uid, gids):
    """Static DAC search check (ACLs are not used by this deployment)."""
    if uid == 0:
        return True
    if meta.st_uid == uid:
        return bool(meta.st_mode & 0o100)
    if meta.st_gid in gids:
        return bool(meta.st_mode & 0o010)
    return bool(meta.st_mode & 0o001)


def traversal_components(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_TRAVERSAL_PATH_REQUIRED')
    return [*reversed(path.parents), path]


def static_traversal(paths, *, uid=WORKER_UID, gid=WORKER_GID, groups=()):
    """Return the first component of any path the identity cannot search."""
    gids = {gid, *groups}
    for target in paths:
        for component in traversal_components(target):
            try:
                meta = component.stat()
            except FileNotFoundError:
                return {'path': str(component), 'target': str(target), 'reason': 'missing'}
            if not stat.S_ISDIR(meta.st_mode):
                if component == Path(target):
                    break
                return {'path': str(component), 'target': str(target), 'reason': 'not_directory'}
            if not _searchable(meta, uid, gids):
                return {'path': str(component), 'target': str(target), 'reason': 'not_searchable',
                        'mode': oct(stat.S_IMODE(meta.st_mode)), 'uid': meta.st_uid, 'gid': meta.st_gid}
    return None


_TRAVERSAL_PROBE = r'''import json,os,stat,sys
def block(path,target,reason):
    sys.stdout.write(json.dumps({'path':path,'target':target,'reason':reason}));sys.exit(0)
for argument in sys.argv[1:]:
    tree=argument.startswith('tree:');target=argument[5:] if tree else argument
    parts=[part for part in target.split('/') if part]
    for index in range(len(parts)+1):
        current='/'+'/'.join(parts[:index])
        try:meta=os.stat(current)
        except FileNotFoundError:block(current,target,'missing')
        except OSError as error:block(current,target,'stat_'+type(error).__name__)
        if stat.S_ISDIR(meta.st_mode):
            if not os.access(current,os.X_OK):block(current,target,'not_searchable')
        elif current!=target:block(current,target,'not_directory')
    if tree:
        # The worker lists and reads the whole tree (inventory check), so an
        # unlistable directory would silently drop files from its view.
        def failed(error):block(getattr(error,'filename',target) or target,target,'not_listable')
        for directory,names,files in os.walk(target,onerror=failed):
            if not os.access(directory,os.R_OK|os.X_OK):block(directory,target,'not_listable')
            for name in files:
                path=os.path.join(directory,name)
                if not os.access(path,os.R_OK):block(path,target,'not_readable')
sys.stdout.write('null')
'''


def static_tree_readable(root, *, uid=WORKER_UID, gid=WORKER_GID):
    """First directory the identity cannot list, or file it cannot read."""
    gids = {gid}
    def allowed(meta, bits):
        shift = 6 if meta.st_uid == uid else 3 if meta.st_gid in gids else 0
        return (meta.st_mode >> shift) & bits == bits
    for directory, _, files in os.walk(root):
        if not allowed(os.stat(directory), 0o5):
            return {'path': directory, 'target': str(root), 'reason': 'not_listable'}
        for name in files:
            path = os.path.join(directory, name)
            if not allowed(os.stat(path), 0o4):
                return {'path': path, 'target': str(root), 'reason': 'not_readable'}
    return None


def worker_traversal(paths, *, trees=(), uid=WORKER_UID, gid=WORKER_GID):
    """Probe that the unprivileged worker identity can reach every path.

    ``paths`` must be resolvable/searchable; ``trees`` must additionally be
    fully listable and readable (the frozen runtime the worker inventories).
    As Root, a short-lived child actually switches to the worker identity and
    resolves every component (``simulated``); otherwise mode/ownership bits
    are evaluated (``static``). Returns the first blocking component.
    """
    import subprocess, sys
    paths = [str(Path(path)) for path in paths]
    trees = [str(Path(path)) for path in trees]
    for path in paths + trees:
        traversal_components(path)
    if os.name == 'posix' and os.geteuid() == 0:
        result = subprocess.run([sys.executable, '-I', '-S', '-c', _TRAVERSAL_PROBE, *paths,
                                 *('tree:' + path for path in trees)],
            user=uid, group=gid, extra_groups=[], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=15, check=False, cwd='/', close_fds=True,
            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
        need(result.returncode == 0 and len(result.stdout) <= 4096, 'WORKER_TRAVERSAL_PROBE_FAILED')
        return {'mode': 'simulated', 'uid': uid, 'gid': gid, 'blocking': json.loads(result.stdout)}
    blocking = static_traversal(paths + trees, uid=uid, gid=gid)
    for tree in trees:
        blocking = blocking or static_tree_readable(tree, uid=uid, gid=gid)
    return {'mode': 'static', 'uid': uid, 'gid': gid, 'blocking': blocking}


def require_worker_traversal(paths, *, trees=(), uid=WORKER_UID, gid=WORKER_GID):
    report = worker_traversal(paths, trees=trees, uid=uid, gid=gid)
    blocking = report['blocking']
    need(blocking is None, 'WORKER_TRAVERSAL_BLOCKED: ' + json.dumps(blocking, sort_keys=True))
    return report



@contextmanager
def private_database(path):
    """Read SQLite through a stable private DB/WAL copy, never SHM originals.

    A WAL-mode database without an existing SHM cannot be queried directly on
    a read-only mount. Preserve authoritative DB and WAL bytes together and
    let SQLite rebuild its coordination files only in the private copy.
    """
    path = Path(path)
    sources = (path, Path(str(path)+'-wal'))
    before = {source:source.read_bytes() for source in sources if source.exists()}
    need(sum(map(len,before.values())) <= 32*1024*1024, 'DOCTOR_DATABASE_COPY_BOUND_EXCEEDED')
    with tempfile.TemporaryDirectory(prefix='capsule-doctor-sqlite-') as directory:
        target = Path(directory)/path.name
        for source,raw in before.items():
            (Path(directory)/source.name).write_bytes(raw)
        after = {source:source.read_bytes() for source in sources if source.exists()}
        need(before == after, 'DOCTOR_DATABASE_CHANGED_DURING_COPY')
        connection = sqlite3.connect(target)
        try:
            yield connection
        finally:
            connection.close()


def database_fact(path):
    if not Path(path).exists():
        return {'present':False,'tables':{}}
    with private_database(path) as connection:
        tables = sorted(row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        values = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            # Sorting by full row representation also supports WITHOUT ROWID.
            rows = sorted(connection.execute('SELECT * FROM ' + quoted).fetchall(), key=repr)
            values[table] = {'count': len(rows), 'rows_sha256': digest(repr(rows).encode())}
        return {'present':True,'tables':values}


def tree_fact(root):
    rows = []
    for path in sorted(Path(root).rglob('*')):
        need(not path.is_symlink(), 'DOCTOR_ORIGINAL_SYMLINK_REFUSED')
        if path.is_file():
            meta = path.stat()
            need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, 'DOCTOR_ORDINARY_FILES_REQUIRED')
            # SQLite byte files may update their read coordination metadata;
            # logical contents are compared separately using mode=ro handles.
            if path.name.endswith(('.sqlite', '.sqlite3', '.sqlite-wal', '.sqlite-shm', '.sqlite3-wal', '.sqlite3-shm')):
                continue
            rows.append([path.relative_to(root).as_posix(), meta.st_size, digest(path.read_bytes())])
    need(len(rows) <= MAX_FILES and sum(row[1] for row in rows) <= MAX_SNAPSHOT_BYTES,
         'DOCTOR_SNAPSHOT_BOUND_EXCEEDED')
    return {'files': len(rows), 'bytes': sum(row[1] for row in rows),
            'inventory_sha256': digest(json.dumps(rows, separators=(',', ':')).encode())}


def backup_database(source, destination):
    with private_database(source) as original:
        target = sqlite3.connect(destination)
        try:
            original.backup(target)
        finally:
            target.close()


def snapshot(source, destination, database_relative):
    source, destination = Path(source), Path(destination)
    destination.mkdir(mode=0o700)
    database = source / database_relative
    size = count = 0
    for path in sorted(source.rglob('*')):
        need(not path.is_symlink(), 'DOCTOR_ORIGINAL_SYMLINK_REFUSED')
        relative = path.relative_to(source)
        output = destination / relative
        if path.is_dir():
            output.mkdir(mode=0o700)
            continue
        if path == database or path in (Path(str(database)+'-wal'), Path(str(database)+'-shm')):
            continue
        meta = path.stat()
        need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, 'DOCTOR_ORDINARY_FILES_REQUIRED')
        size += meta.st_size; count += 1
        need(count <= MAX_FILES and size <= MAX_SNAPSHOT_BYTES, 'DOCTOR_SNAPSHOT_BOUND_EXCEEDED')
        shutil.copyfile(path, output); output.chmod(0o600)
    (destination / database_relative).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if database.exists():
        backup_database(database, destination / database_relative)
    return destination


async def compose_snapshot(value, helper, scratch):
    original = value['composition']
    composition = copy.deepcopy(original)
    composition.update(core_root=str(snapshot(original['core_root'], scratch/'core', 'state/research.sqlite3')),
        record_root=str(snapshot(original['record_root'], scratch/'records', 'index.sqlite')),
        native_lease_root=str(snapshot(original['native_lease_root'], scratch/'native-leases', 'index.sqlite')),
        work_root=str(scratch/'work'))
    (scratch/'work').mkdir(mode=0o700)
    composition.update({key:value['session'][key] for key in (
        'id', 'native_scope_ref', 'diagnosis_contract_ref', 'proposal_contract_ref')})
    core_before = database_fact(scratch/'core/state/research.sqlite3')
    native_before = database_fact(scratch/'native-leases/index.sqlite')
    records_before = database_fact(scratch/'records/index.sqlite')
    evaluated = 0
    async def forbidden_evaluation(*args, **kwargs):
        nonlocal evaluated
        evaluated += 1
        raise ValueError('DOCTOR_CANNOT_EXECUTE_JOBS')
    runtime = None
    try:
        # This is the literal source-pinned normal composition, including its
        # actual Library/check assets, child contracts, native lease and status.
        runtime = await helper.compose(composition, forbidden_evaluation)
        await runtime.before_model()  # Status/lease freshness only; never model.
        need(type(runtime.subscription).__name__ == 'HostCodexSubscriptionService',
             'EXACT_QUALIFIED_NATIVE_SUBSCRIPTION_REQUIRED')
        from .host_codex_backend import descriptor
        binding = runtime.subscription.binding()
        native = descriptor(binding)
        need(evaluated == 0, 'DOCTOR_EVALUATION_FORBIDDEN')
        return {'native_policy_sha256': native['sha256'],
                'native_binding_sha256': binding['binding_sha256']}
    finally:
        if runtime is not None:
            close = getattr(runtime.subscription.transport, 'close', None)
            if close is not None:
                pending = close()
                if inspect.isawaitable(pending):
                    await pending
            runtime.records.close(); runtime.lease_records.close(); runtime.core.close()
        # Constructors may establish empty schema/index tables on snapshots.
        # Every preexisting row and every effect-bearing new table stays empty.
        core_after = database_fact(scratch/'core/state/research.sqlite3')
        native_after = database_fact(scratch/'native-leases/index.sqlite')
        records_after = database_fact(scratch/'records/index.sqlite')
        need(core_before == core_after, 'DOCTOR_CORE_ROWS_CHANGED')
        for before, after in ((native_before,native_after),(records_before,records_after)):
            need(all(after['tables'].get(name) == rows for name,rows in before['tables'].items()), 'DOCTOR_EXISTING_SESSION_ROWS_CHANGED')
            need(all(rows['count'] == 0 for name,rows in after['tables'].items() if name not in before['tables']),
                 'DOCTOR_EFFECT_ROWS_CREATED')


def doctor(value, helper, scratch_root, *, scope_sha256):
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_DOCTOR_CONFIGURATION_REQUIRED')
    # Root intentionally lacks DAC_OVERRIDE in the metadata worker. Drop
    # before traversing any private controller directory, including parents.
    # Config and source custody have already been checked by the Root loader.
    os.setgroups([13000]); os.setgid(12001); os.setuid(12001)
    need(os.getuid()==os.geteuid()==12001 and os.getgroups()==[13000], 'DOCTOR_CONTROLLER_DROP_REQUIRED')
    scratch = Path(scratch_root)
    need(scratch.is_absolute() and not any(p.is_symlink() for p in (scratch,*scratch.parents)),
         'DOCTOR_REAL_SCRATCH_REQUIRED')
    meta = scratch.stat()
    need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 12001 and stat.S_IMODE(meta.st_mode) == 0o700
         and not any(scratch.iterdir()), 'FRESH_PRIVATE_DOCTOR_SCRATCH_REQUIRED')
    original = value['composition']
    for key in ('core_root','input_root','record_root','native_lease_root','account_root'):
        path = Path(original[key])
        need(not any(p.is_symlink() for p in (path,*path.parents))
             and bool(os.statvfs(path).f_flag & os.ST_RDONLY), 'DOCTOR_ORIGINALS_MUST_BE_READONLY_MOUNTS')
    # Private identity exactly matches the real controller. Account metadata is
    # reused read-only; its contents are never copied into the doctor snapshot.
    roots = {key:Path(original[key]) for key in ('core_root','record_root','native_lease_root')}
    before = {key:{'files':tree_fact(path), 'database':database_fact(path/(
        'state/research.sqlite3' if key=='core_root' else 'index.sqlite'))} for key,path in roots.items()}
    result = {'schema':SCHEMA,'scope_sha256':scope_sha256,'status':'ERROR',
        'actual_frozen_compose_completed':False,'originals_unchanged':False,
        'model_calls':0,'tool_calls':0,'execution_jobs':0,'work_claims':0,'native_starts':0,
        'uid':os.geteuid(),'gid':os.getegid(),'groups':os.getgroups(),
        'python':{'version':list(sys.version_info[:3]),'executable_sha256':digest(Path(sys.executable).resolve().read_bytes())},
        'originals_before':before}
    try:
        # Derived whole-package closure of every controller/evaluator module
        # (and the frozen composition) before composing: an incomplete
        # package fails here with its exact missing path, never mid-run.
        closure = proven_source_closure(value['source_root'], value['source_pins'],
            entry_files=[value['composition_path']])
        result['source_closure'] = {key: closure[key] for key in (
            'schema', 'complete', 'module_count', 'resource_count', 'modules_sha256', 'entry_packages')}
        result.update(asyncio.run(compose_snapshot(value,helper,scratch)))
        result.update(status='COMPATIBLE',actual_frozen_compose_completed=True)
    except BaseException as error:
        result.update(exception_type=type(error).__name__,message=str(error)[:4096])
        raise
    finally:
        after = {key:{'files':tree_fact(path), 'database':database_fact(path/(
            'state/research.sqlite3' if key=='core_root' else 'index.sqlite'))} for key,path in roots.items()}
        result['originals_after'] = after
        result['originals_unchanged'] = before==after
        if before != after:
            result['status']='ERROR'
        with (scratch/'doctor-result.json').open('xb') as stream:
            stream.write(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
    need(result['originals_unchanged'], 'DOCTOR_ORIGINAL_ROWS_OR_BYTES_CHANGED')
    return result
