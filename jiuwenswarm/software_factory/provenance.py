"""Write-once executor source recipes and fail-closed execution guards.

Recipes retain bytes of the code that actually implements a run, including
uncommitted adapters and templates. They do not turn old executions into audited
runs and do not capture process environments, credentials, or model weights.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .contracts import StageFailure

_SCHEMA = 'ai4r.executor-recipe:1'
_CODE_SUFFIXES = {'.py', '.pyi', '.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp',
                  '.cu', '.cuh', '.cmake', '.sh', '.bash', '.patch', '.in',
                  '.j2', '.jinja', '.jinja2', '.tmpl'}
_SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'build',
              'dist', '.pytest_cache', '.mypy_cache', 'runs', 'recipe'}
_SECRET_PARTS = {'key', 'apikey', 'api_key', 'token', 'password', 'passwd',
                 'secret', 'credential', 'credentials', 'authorization',
                 'cookie', 'private_key', 'env', 'environ', 'environment'}
_MAX_EXECUTABLE_BYTES = 32 * 1024 * 1024


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _code(path: Path) -> bool:
    return (not path.name.startswith('.env') and
            (path.name in {'CMakeLists.txt', 'Makefile'} or path.suffix.lower() in _CODE_SUFFIXES))


def _sources(root: Path, excluded: tuple[Path, ...] = ()) -> list[Path]:
    result = []
    for folder, directories, filenames in os.walk(root, followlinks=False):
        parent = Path(folder)
        directories[:] = [name for name in directories if name not in _SKIP_DIRS and
                          not any((parent / name).is_relative_to(path) for path in excluded)]
        for filename in filenames:
            candidate = parent / filename
            if any(candidate.is_relative_to(path) for path in excluded) or not _code(candidate):
                continue
            if candidate.is_symlink():
                raise StageFailure('executor_source_unavailable',
                                   f'Executor source symlink must be replaced by an owned file: {candidate}')
            if candidate.is_file():
                result.append(candidate)
    return sorted(result)


def _sensitive(key: str) -> bool:
    normalized = key.lower().replace('-', '_')
    return (normalized in _SECRET_PARTS or any(
        part in normalized for part in ('password', 'passwd', 'secret', 'token', 'credential', 'authorization', 'private_key')) or
        normalized.endswith('_key'))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): '[redacted]' if _sensitive(str(key)) else _redact(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str) and '://' in value:
        try:
            parts = urlsplit(value)
            if not parts.scheme or not parts.hostname:
                return value
            netloc = parts.netloc.rsplit('@', 1)[-1]
            query = urlencode([(key, '[redacted]' if _sensitive(key) else item)
                               for key, item in parse_qsl(parts.query, keep_blank_values=True)])
            return urlunsplit((parts.scheme, netloc, parts.path, query, ''))
        except ValueError:
            return '[redacted invalid URL]'
    return value


def _module_file(callback) -> Path:
    target = inspect.unwrap(callback)
    if hasattr(target, 'func'):
        target = target.func
    try:
        filename = inspect.getsourcefile(target)
    except TypeError:
        filename = inspect.getsourcefile(type(target))
    if not filename:
        raise StageFailure('executor_source_unavailable', 'Executable stage has no inspectable source module')
    path = Path(filename).absolute()
    if not path.is_file() or not _code(path) or path.is_symlink():
        raise StageFailure('executor_source_unavailable', f'Executable source is unavailable: {path}')
    return path.resolve()


def _git(factory_root: Path, selected: list[Path]) -> dict:
    def command(*args):
        return subprocess.run(['git', '-C', str(factory_root), *args],
                              capture_output=True, text=True, timeout=5, check=True).stdout.rstrip('\r\n')
    try:
        root = Path(command('rev-parse', '--show-toplevel')).resolve()
        head = command('rev-parse', 'HEAD')
        paths = [str(path.relative_to(root)) for path in selected if path.is_relative_to(root)]
        status = command('status', '--porcelain=v1', '--untracked-files=all', '--', *paths) if paths else ''
        return {'git_head': head, 'repository': str(root),
                'dirty_code_paths': [line[3:] for line in status.splitlines() if len(line) > 3]}
    except (OSError, subprocess.SubprocessError):
        return {'git_head': None, 'repository': None, 'dirty_code_paths': [], 'git_available': False}


def _packages() -> dict[str, str]:
    return dict(sorted((item.metadata['Name'], item.version) for item in importlib.metadata.distributions()
                       if item.metadata.get('Name')))


def capture_recipe(run_directory, stages, request) -> dict:
    """Capture executor bytes before planning; never overwrite an existing recipe.

    The returned object is JSON serializable. Persist it in the run record and
    call :func:`verify_recipe` before stage dispatch and each subprocess launch.
    Request values are sanitized; ``request_sha256`` identifies the complete
    original canonical request, while ``request_capture_sha256`` identifies the
    retained sanitized JSON bytes.
    """
    run = Path(run_directory).resolve()
    run.mkdir(parents=True, exist_ok=True)
    destination = run / 'recipe'
    if destination.exists():
        raise StageFailure('executor_recipe_exists', 'A run recipe is immutable and cannot be recaptured')
    factory = Path(__file__).resolve().parent
    selected = _sources(factory, (run,))
    callbacks = []
    for stage in stages:
        callbacks.append(stage.execute)
        callbacks.extend(stage.validators.values())
    selected = sorted(set(selected) | {_module_file(callback) for callback in callbacks})
    roots = {'factory': {'working': str(factory), 'snapshot': str(destination / 'source' / 'factory'),
                         'enumerated': True, 'excluded': [str(run)]}}
    external = []
    for path in selected:
        if not path.is_relative_to(factory):
            external.append(path)
    for index, parent in enumerate(sorted({path.parent for path in external})):
        key = f'external-{index + 1}'
        roots[key] = {'working': str(parent), 'snapshot': str(destination / 'source' / key),
                      'enumerated': False, 'excluded': []}
    temporary = Path(tempfile.mkdtemp(prefix='.recipe-', dir=run))
    records = []
    try:
        for source in selected:
            key = next(name for name, root in roots.items() if source.is_relative_to(Path(root['working'])))
            relative = source.relative_to(Path(roots[key]['working']))
            raw = source.read_bytes()
            captured = temporary / 'source' / key / relative
            captured.parent.mkdir(parents=True, exist_ok=True)
            with captured.open('xb') as stream:
                stream.write(raw)
            captured.chmod(0o444)
            records.append({'root': key, 'relative_path': relative.as_posix(),
                            'working_path': str(source),
                            'snapshot_path': str(destination / 'source' / key / relative),
                            'sha256': _digest(raw), 'size': len(raw)})
        catalog = [stage.serializable() for stage in stages]
        catalog_raw = _canonical(catalog)
        request_raw = _canonical(_redact(request))
        for name, raw in [('catalog.json', catalog_raw), ('request.json', request_raw)]:
            (temporary / name).write_bytes(raw)
            (temporary / name).chmod(0o444)
        manifest = {'schema': _SCHEMA, 'captured_at': datetime.now(timezone.utc).isoformat(),
                    'source_roots': roots, 'files': records,
                    'catalog_path': str(destination / 'catalog.json'), 'catalog_sha256': _digest(catalog_raw),
                    'request_path': str(destination / 'request.json'),
                    'request_sha256': _digest(_canonical(request)), 'request_capture_sha256': _digest(request_raw),
                    'request_redacted': _redact(request) != request,
                    'host': _git(factory, selected),
                    'interpreter': {'executable': str(Path(sys.executable).resolve()), 'version': sys.version,
                                    'implementation': sys.implementation.name}, 'packages': _packages()}
        raw = _canonical(manifest)
        (temporary / 'manifest.json').write_bytes(raw)
        (temporary / 'manifest.json').chmod(0o444)
        # rename never merges with an existing nonempty immutable recipe.
        temporary.rename(destination)
        result = dict(manifest, manifest_path=str(destination / 'manifest.json'), manifest_sha256=_digest(raw))
        verify_recipe(result)
        return result
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _changed(message: str, **details):
    raise StageFailure('executor_source_changed', message, details)


def verify_recipe(recipe) -> None:
    """Reject changed/missing working source, retained bytes, or recipe metadata."""
    try:
        raw = Path(recipe['manifest_path']).read_bytes()
        if _digest(raw) != recipe['manifest_sha256']:
            _changed('The immutable executor manifest changed')
        data = json.loads(raw)
        if data.get('schema') != _SCHEMA:
            _changed('Unsupported executor recipe schema')
        for root_id, root in data['source_roots'].items():
            if root.get('enumerated'):
                expected = {entry['relative_path'] for entry in data['files'] if entry['root'] == root_id}
                current = {str(path.relative_to(Path(root['working']))).replace('\\', '/') for path in
                           _sources(Path(root['working']), tuple(Path(value) for value in root.get('excluded', [])))}
                if current != expected:
                    _changed('Executor source file set changed', source_root=root_id,
                             added=sorted(current - expected), removed=sorted(expected - current))
        for entry in data['files']:
            for field in ('working_path', 'snapshot_path'):
                path = Path(entry[field])
                root = Path(data['source_roots'][entry['root']]['working' if field == 'working_path' else 'snapshot'])
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                    _changed('Executor source path escaped its captured root', source=entry['relative_path'])
                if _digest(path.read_bytes()) != entry['sha256']:
                    _changed('Executor source bytes changed', source=entry['relative_path'], kind=field)
        for path_field, hash_field in [('catalog_path', 'catalog_sha256'), ('request_path', 'request_capture_sha256')]:
            if _digest(Path(data[path_field]).read_bytes()) != data[hash_field]:
                _changed('Captured executor catalog or request changed', part=path_field)
    except StageFailure as error:
        if error.code == 'executor_source_changed':
            raise
        _changed('Executor source can no longer be verified', cause=error.code)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _changed('Executor recipe or source is missing or invalid', cause=type(error).__name__)


def command_recipe(argv, recipe, *, cwd=None, env=None) -> dict:
    """Identify the actual executable and code inputs without storing argv secrets.

    Generated scripts not part of the initial executor snapshot are identified
    as command inputs, not silently promoted to captured executor source.
    """
    verify_recipe(recipe)
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(value, str) for value in argv):
        raise StageFailure('invalid_command', 'Command provenance requires a nonempty argv list')
    directory = Path(cwd or Path.cwd()).resolve()
    actual_env = os.environ if env is None else env
    search = os.pathsep.join(str(Path(part) if Path(part).is_absolute() else directory / part)
                             for part in actual_env.get('PATH', os.defpath).split(os.pathsep))
    command = argv[0]
    if os.sep in command and not Path(command).is_absolute():
        command = str(directory / command)
    resolved = shutil.which(command, path=search)
    executable = Path(resolved).resolve() if resolved else None
    execution = {'requested_basename': Path(argv[0]).name, 'resolved_path': str(executable) if executable else None,
                 'sha256': None}
    if executable and executable.is_file():
        execution['size'] = executable.stat().st_size
        if execution['size'] <= _MAX_EXECUTABLE_BYTES:
            execution['sha256'] = _digest(executable.read_bytes())
        else:
            execution['hash_status'] = 'not_hashed_size_limit'
    manifest = json.loads(Path(recipe['manifest_path']).read_bytes())
    known = {str(Path(entry['working_path']).resolve()): entry for entry in manifest['files']}
    inputs = []
    for index, value in enumerate(argv[1:], 1):
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = directory / candidate
        try:
            if not candidate.is_file() or not _code(candidate):
                continue
        except (OSError, ValueError):
            continue
        candidate = candidate.resolve()
        captured = known.get(str(candidate))
        inputs.append({'argument_index': index, 'path': str(candidate),
                       'sha256': _digest(candidate.read_bytes()), 'size': candidate.stat().st_size,
                       'captured_executor_source': bool(captured),
                       'snapshot_path': captured['snapshot_path'] if captured else None})
    inline = []
    for index, value in enumerate(argv[:-1]):
        if value == '-c' and executable and 'python' in executable.name:
            inline.append({'argument_index': index + 1, 'sha256': _digest(argv[index + 1].encode()),
                           'bytes': len(argv[index + 1].encode())})
    return {'recipe_manifest_sha256': recipe['manifest_sha256'], 'executable': execution,
            'code_inputs': inputs, 'inline_code': inline}
