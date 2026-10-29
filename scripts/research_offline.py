"""I029: finite, source-preserving offline installation input producer.

This authoring tool runs explicitly in the pinned, network-denied Linux
controller. It never installs into the product environment, changes original
METADATA/URLs, grants execution authority, or asserts product acceptance.
"""
from __future__ import annotations

import argparse
import collections
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
import importlib.metadata
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import parse_qs, urlsplit
import zipfile

from packaging.markers import Marker, default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename
from packaging.version import Version

try:
    from scripts.research_build import context_tar, validate_manifest
    from scripts.research_offline_assets import audit_distribution, audit_native, audit_wheel, normalized_name
except ModuleNotFoundError:
    from research_build import context_tar, validate_manifest
    from research_offline_assets import audit_distribution, audit_native, audit_wheel, normalized_name


class OfflineError(ValueError):
    pass


TOOLS = frozenset({'hatchling', 'packaging', 'pathspec', 'pluggy', 'setuptools',
                   'tomlkit', 'trove-classifiers', 'wheel'})
VCS = {
    'openjiuwen': {'url': 'https://gitcode.com/openJiuwen/agent-core.git',
                  'commit': '9e3390195a9ea15235b2b5f7412cb2aa440622cc',
                  'ref': 'refs/heads/ai4r-offline', 'subdirectory': ''},
    'intelli-router': {'url': 'https://gitcode.com/openJiuwen/agent-protocol.git',
                      'commit': 'f70ae827ba059deddef87406f90b77bcde403dc1',
                      'ref': 'refs/heads/feature/intelliRouter', 'subdirectory': 'intelli_router'},
}
HEX = re.compile(r'[0-9a-f]{64}\Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')


def canonical(name):
    if not isinstance(name, str):
        raise OfflineError('INPUT_PATH')
    path = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name
            or any(ord(c) < 32 for c in name) or path.is_absolute()
            or '..' in path.parts or path.as_posix() != name):
        raise OfflineError('INPUT_PATH')
    return name


def verified_input(root, name, record):
    path = Path(root).absolute() / canonical(name)
    data = read_original(path)
    if (set(record) != {'bytes', 'sha256'} or type(record['bytes']) is not int
            or len(data) != record['bytes'] or not isinstance(record['sha256'], str)
            or not HEX.fullmatch(record['sha256']) or sha(data) != record['sha256']):
        raise OfflineError('INPUT_HASH_OR_SIZE')
    return data


def read_original(path):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise OfflineError('INPUT_CUSTODY')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size > 1024**3 or before.st_size < 0):
            raise OfflineError('INPUT_CUSTODY')
        data = stream.read()
        after = os.fstat(stream.fileno())
    if ((before.st_size, before.st_mtime_ns, before.st_ino) !=
            (after.st_size, after.st_mtime_ns, after.st_ino)):
        raise OfflineError('INPUT_CHANGED')
    return data


def verify_materialized(root, files):
    found = set()
    for path in Path(root).rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise OfflineError('MATERIALIZED_CUSTODY')
        if path.is_file():
            found.add(path.relative_to(root).as_posix())
    if found != set(files):
        raise OfflineError('MATERIALIZED_MEMBER_CLOSURE')
    for name, pin in files.items():
        verified_input(root, name, pin)


def selected_packages(lock, *, environment):
    """Traverse only production dependencies and explicit codex+tui extras."""
    rows = lock.get('package', [])
    if not isinstance(rows, list) or not 0 < len(rows) <= 4000:
        raise OfflineError('LOCK_PACKAGE_INVENTORY')
    by_name = collections.defaultdict(list)
    for row in rows:
        by_name[normalized_name(row['name'])].append(row)
    queue = collections.deque([{'name': 'workswarm', 'extra': ['codex', 'tui']}])
    chosen, visited = {}, set()
    while queue:
        edge = queue.popleft()
        if edge.get('marker') and not Marker(edge['marker']).evaluate(environment):
            continue
        name = normalized_name(edge['name'])
        candidates = [row for row in by_name[name]
                      if ('version' not in edge or Version(row['version']) == Version(edge['version']))
                      and ('source' not in edge or row['source'] == edge['source'])
                      and (not row.get('resolution-markers') or any(
                          Marker(marker).evaluate(environment) for marker in row['resolution-markers']))]
        if len(candidates) != 1:
            raise OfflineError('LOCK_DEPENDENCY_UNRESOLVED' if not candidates else 'LOCK_DEPENDENCY_AMBIGUOUS')
        row = candidates[0]
        if name in chosen and chosen[name] != row:
            raise OfflineError('LOCK_DEPENDENCY_AMBIGUOUS')
        chosen[name] = row
        extras = edge.get('extra', [])
        for extra in [None, *extras]:
            key = (name, extra)
            if key in visited:
                continue
            visited.add(key)
            if len(visited) > 10000:
                raise OfflineError('LOCK_GRAPH_BOUND')
            if extra is None:
                queue.extend(row.get('dependencies', []))
            else:
                optional = row.get('optional-dependencies', {})
                if extra not in optional:
                    raise OfflineError('LOCK_EXTRA_UNRESOLVED')
                queue.extend(optional[extra])
    return dict(sorted(chosen.items()))


def parse_build_requirements(text):
    result = {}
    for line in text.replace('\\\n', ' ').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'\s*([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)((?:\s+--hash=sha256:[0-9a-f]{64})+)\s*', line)
        if match is None or normalized_name(match[1]) in result:
            raise OfflineError('BUILD_TOOL_REQUIREMENT')
        result[normalized_name(match[1])] = (match[2], set(re.findall(r'--hash=sha256:([0-9a-f]{64})', match[3])))
    if not result:
        raise OfflineError('BUILD_TOOL_REQUIREMENT_EMPTY')
    return result


def validate_dynamic_requirements(requirements, tools, environment):
    if not isinstance(requirements, list) or len(requirements) > 100:
        raise OfflineError('BUILD_REQUIREMENT_SHAPE')
    for text in requirements:
        requirement = Requirement(text)
        if requirement.url or requirement.extras:
            raise OfflineError('BUILD_REQUIREMENT_AUTHORITY')
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        name = normalized_name(requirement.name)
        if name not in tools:
            raise OfflineError('UNFROZEN_BUILD_REQUIREMENT:' + name)
        if Version(tools[name][0]) not in requirement.specifier:
            raise OfflineError('BUILD_REQUIREMENT_VERSION:' + name)


def required_native_members(source, project):
    """Apply the frozen setuptools package/data selection to source members."""
    tool = project.get('tool', {}).get('setuptools', {})
    data = tool.get('package-data', {}).get('jiuwenswarm', [])
    excludes = tool.get('exclude-package-data', {}).get('jiuwenswarm', [])
    excluded_packages = tool.get('packages', {}).get('find', {}).get('exclude', [])
    result = set()
    for name in source:
        if not name.startswith('jiuwenswarm/'):
            continue
        tail = name[len('jiuwenswarm/'):]
        parts = tail.split('/')
        parents = ['jiuwenswarm/' + '/'.join([*parts[:depth], '__init__.py']) for depth in range(len(parts))]
        package = '.'.join(['jiuwenswarm', *parts[:-1]])
        python = name.endswith('.py') and all(parent in source for parent in parents)
        python = python and not any(fnmatch.fnmatchcase(package, pattern) for pattern in excluded_packages)
        resource = any(fnmatch.fnmatchcase(tail, pattern) for pattern in data)
        resource = resource and not any(fnmatch.fnmatchcase(tail, pattern) for pattern in excludes)
        if python or resource:
            result.add(name)
    return result


def bind_delivered_members(kind, report, source, project, installed):
    """Join both directions, allowing generated bytes only in fixed assets."""
    metadata = report['metadata']
    dist_info = normalized_name(metadata['name']).replace('-', '_') + '-' + metadata['version'] + '.dist-info/'
    members = report['members']
    generated = ('jiuwenswarm/channels/web/frontend/dist/',
                 'jiuwenswarm/channels/tui/frontend/dist/',
                 'jiuwenswarm/channels/tui/frontend/node_modules/')
    if kind == 'workswarm':
        image_files = {'jiuwenswarm/' + row['path']: {key: row[key] for key in ('bytes', 'sha256')}
                       for row in installed['files']}
        if {key: value for key, value in members.items() if key.startswith('jiuwenswarm/')} != image_files:
            raise OfflineError('DELIVERED_INSTALLED_MEMBER_CLOSURE')
        if not required_native_members(source, project) <= set(members):
            raise OfflineError('DELIVERED_CANDIDATE_MEMBER_MISSING')
    elif kind == 'workswarm-tui':
        image_files = {'jiuwenswarm_tui/' + row['path']: {key: row[key] for key in ('bytes', 'sha256')}
                       for row in installed['components']['jiuwenswarm_tui']['files']}
        if {key: value for key, value in members.items() if key.startswith('jiuwenswarm_tui/')} != image_files:
            raise OfflineError('DELIVERED_INSTALLED_MEMBER_CLOSURE')
    for member, pin in members.items():
        if member.startswith(dist_info):
            continue
        if kind == 'workswarm' and member.startswith('jiuwenswarm/'):
            source_name = member
        elif kind == 'workswarm' and member.startswith('jiuwenbox/'):
            source_name = 'jiuwenbox/src/' + member
        elif kind == 'workswarm-tui' and member.startswith('jiuwenswarm_tui/'):
            source_name = 'packages/jiuwenswarm-tui/' + member
        else:
            raise OfflineError('UNPINNED_DELIVERED_MEMBER:' + member)
        if source_name in source:
            if pin != {key: source[source_name][key] for key in ('bytes', 'sha256')}:
                raise OfflineError('DELIVERED_CANDIDATE_SOURCE_CHANGED:' + member)
        elif kind != 'workswarm' or not member.startswith(generated):
            raise OfflineError('UNPINNED_DELIVERED_MEMBER:' + member)


def safe_environment(home, wheelhouse):
    return {'PATH': os.environ['PATH'], 'HOME': str(home), 'LANG': 'C.UTF-8',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_TERMINAL_PROMPT': '0', 'GIT_ALLOW_PROTOCOL': 'file',
            'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'credential.helper', 'GIT_CONFIG_VALUE_0': '',
            'PIP_CONFIG_FILE': '/dev/null', 'PIP_NO_INDEX': '1', 'PIP_FIND_LINKS': str(wheelhouse),
            'PIP_NO_CACHE_DIR': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
            'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}


def base_python():
    # uv's application venv deliberately has no pip. The immutable Python
    # base image supplies the separately observed installation frontend.
    return str(Path(sys._base_executable).resolve(strict=True))


def frontend_source_files(root):
    root = Path(root)
    if not root.is_absolute() or root.name != 'pip' or root.is_symlink() or not root.is_dir():
        raise OfflineError('PIP_FRONTEND_CLOSURE')
    names = []
    for count, path in enumerate(root.rglob('*'), start=1):
        if count > 10000:
            raise OfflineError('PIP_FRONTEND_CLOSURE')
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise OfflineError('PIP_FRONTEND_ALIAS_OR_SPECIAL')
        if stat.S_ISREG(mode) and path.suffix == '.py':
            names.append(str(path))
    if not 3 <= len(names) <= 2000:
        raise OfflineError('PIP_FRONTEND_CLOSURE')
    return sorted(names)


def observe_pip_frontend(commands, cwd):
    program = '''import pip, pathlib, importlib.metadata as m, json
print(json.dumps({'version': m.version('pip'), 'root': str(pathlib.Path(pip.__file__).resolve().parent)}))'''
    observed = json.loads(commands.run([base_python(), '-I', '-c', program], cwd=cwd))
    root = Path(observed['root'])
    names = frontend_source_files(root)
    files = []
    for name in names:
        path = Path(name)
        if not path.is_relative_to(root) or path.suffix != '.py':
            raise OfflineError('PIP_FRONTEND_PATH')
        data = read_original(path)
        files.append({'path': str(path), 'bytes': len(data), 'sha256': sha(data)})
    if not {'__init__.py', '__main__.py', '__pip-runner__.py'} <= {Path(name).name for name in names}:
        raise OfflineError('PIP_FRONTEND_ENTRYPOINTS')
    data = read_original(Path(base_python()))
    return {'version': observed['version'], 'python_file': {
        'path': base_python(), 'bytes': len(data), 'sha256': sha(data)}, 'files': files}


def validate_target_tags(report, supported, python_version):
    # Original third-party wheels may disagree with their own filename.
    # Preserve that observation, and never let a broad metadata tag widen
    # the archive filename's independently supported target set.
    if (not supported.intersection(report['filename_tags'])
            or not supported.intersection(report['wheel_tags'])
            or (report['metadata']['requires_python']
                and Version(python_version) not in SpecifierSet(report['metadata']['requires_python']))):
        raise OfflineError('INCOMPATIBLE_WHEEL')


def controller_runtime(target, frontend):
    def executable(path):
        resolved = Path(path).resolve(strict=True)
        data = read_original(resolved)
        return {'path': str(resolved), 'bytes': len(data), 'sha256': sha(data)}
    tools = {}
    for name in ('git', 'node', 'codex'):
        path = shutil.which(name)
        if path is None:
            raise OfflineError('PREPARED_TOOL_MISSING:' + name)
        tools[name] = executable(path)
    return {'schema': 'ai4r-offline-controller-runtime:1', 'platform': target,
            'python_version': platform.python_version(), 'python_file': executable(sys.executable),
            'packaging_version': importlib.metadata.version('packaging'), 'tool_files': tools,
            'pip_frontend': frontend}


class Commands:
    """Fixed internal argv only; original outputs survive every terminal path."""
    def __init__(self, evidence, environment):
        self.evidence, self.environment = Path(evidence), environment
        self.count = 0

    def run(self, argv, *, cwd):
        self.count += 1
        prefix = self.evidence / f'{self.count:03d}'
        record = {'argv': list(map(str, argv)), 'cwd': str(cwd), 'maximum_seconds': 120,
                  'started_at': datetime.now(timezone.utc).isoformat()}
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=self.environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError as error:
            record.update(outcome='NOT_STARTED', child_started=False, returncode=None,
                          error_type=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
            prefix.with_suffix('.stdout').write_bytes(b'')
            prefix.with_suffix('.stderr').write_bytes(str(error).encode('utf-8'))
            prefix.with_suffix('.json').write_bytes(encoded(record))
            raise OfflineError('AUTHORING_EFFECT_NOT_STARTED') from error
        try:
            stdout, stderr = process.communicate(timeout=120)
            record['returncode'] = process.returncode
        except subprocess.TimeoutExpired as error:
            record['outcome'] = 'OUTCOME_UNKNOWN'
            try:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate(timeout=5)
                record['owned_group_kill_returned'] = True
                record['parent_reaped'] = process.poll() is not None
            except (ProcessLookupError, subprocess.TimeoutExpired):
                stdout, stderr = error.stdout or b'', error.stderr or b''
                record['owned_group_kill_returned'] = False
            prefix.with_suffix('.stdout').write_bytes(stdout)
            prefix.with_suffix('.stderr').write_bytes(stderr)
            prefix.with_suffix('.json').write_bytes(encoded(record))
            raise OfflineError('AUTHORING_EFFECT_TIMEOUT_OUTCOME_UNKNOWN') from error
        except BaseException as error:
            record['outcome'] = 'OUTCOME_UNKNOWN'
            record['interruption'] = type(error).__name__
            try:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate(timeout=5)
                record['owned_group_kill_returned'] = True
                record['parent_reaped'] = process.poll() is not None
            except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                stdout, stderr = b'', b''
                record['owned_group_kill_returned'] = False
            prefix.with_suffix('.stdout').write_bytes(stdout)
            prefix.with_suffix('.stderr').write_bytes(stderr)
            prefix.with_suffix('.json').write_bytes(encoded(record))
            raise OfflineError('AUTHORING_EFFECT_INTERRUPTED_OUTCOME_UNKNOWN') from error
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        prefix.with_suffix('.stdout').write_bytes(stdout)
        prefix.with_suffix('.stderr').write_bytes(stderr)
        prefix.with_suffix('.json').write_bytes(encoded(record))
        if process.returncode:
            raise OfflineError('AUTHORING_EFFECT_FAILED:' + str(self.count))
        return stdout


def validate_original_vcs(lock):
    for name, expected in VCS.items():
        source = urlsplit(lock[name]['source']['git'])
        query = parse_qs(source.query, keep_blank_values=True, strict_parsing=True)
        expected_query = {'rev': [expected['commit'] if name == 'openjiuwen' else 'feature/intelliRouter']}
        if expected['subdirectory']:
            expected_query['subdirectory'] = [expected['subdirectory']]
        if (source.scheme != 'https' or source.fragment != expected['commit']
                or source._replace(query='', fragment='').geturl() != expected['url']
                or query != expected_query):
            raise OfflineError('VCS_SOURCE_AUTHORITY')


def add_bundle(bundles, name):
    basename = Path(canonical(name)).name
    if basename in bundles:
        raise OfflineError('DUPLICATE_BUNDLE')
    bundles[basename] = name


def verify_backends(root, manifest, tools, environment, evidence):
    commands = Commands(evidence, environment)
    results = {}
    with tempfile.TemporaryDirectory(prefix='ai4r-offline-backends-') as temporary:
        work = Path(temporary)
        build_venv = work / 'build-venv'
        commands.run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(build_venv)], cwd=work)
        python = str(build_venv / 'bin/python')
        commands.run([base_python(), '-I', '-m', 'pip', '--python', python, 'install', '--no-index',
                      '--find-links', str(root / manifest['wheelhouse']), '--no-deps', '--require-hashes',
                      '-r', str(root / manifest['build_requirements'])], cwd=work)
        inventory_program = 'import importlib.metadata as m,json,sys; print(json.dumps({"prefix":sys.prefix,"distributions":{d.metadata["Name"]:{"version":d.version,"root":str(d.locate_file(""))} for d in m.distributions()}}))'
        inventory = json.loads(commands.run([python, '-I', '-c', inventory_program], cwd=work))
        actual = {normalized_name(name): row for name, row in inventory['distributions'].items()}
        if set(actual) != set(tools) or any(row['version'] != tools[name][0]
                or not Path(row['root']).is_relative_to(build_venv) for name, row in actual.items()):
            raise OfflineError('BUILD_ENVIRONMENT_NOT_CLOSED')
        results['build_environment'] = inventory
        for source in manifest['vcs_sources']:
            expected = next(value for value in VCS.values() if value['url'] == source['url'])
            name = next(key for key, value in VCS.items() if value == expected)
            mirror, checkout = work / (name + '.git'), work / name
            commands.run(['git', 'clone', '--bare', str(root / source['bundle']), str(mirror)], cwd=work)
            commands.run(['git', '--git-dir', str(mirror), 'bundle', 'verify', str(root / source['bundle'])], cwd=work)
            heads = commands.run(['git', '--git-dir', str(mirror), 'for-each-ref', '--format=%(objectname) %(refname)'], cwd=work).decode().splitlines()
            if heads != [source['commit'] + ' ' + source['ref']]:
                raise OfflineError('VCS_REF_CLOSURE')
            if (commands.run(['git', '--git-dir', str(mirror), 'rev-parse', '--is-shallow-repository'], cwd=work).strip() != b'false'
                    or (mirror / 'objects/info/alternates').exists() or list(mirror.rglob('*.promisor'))
                    or (mirror / 'refs/replace').exists()):
                raise OfflineError('VCS_EXTERNAL_OBJECT_AUTHORITY')
            commands.run(['git', '--git-dir', str(mirror), 'fsck', '--full', '--no-dangling'], cwd=work)
            tree = commands.run(['git', '--git-dir', str(mirror), 'rev-parse', source['commit'] + '^{tree}'], cwd=work).strip().decode()
            commands.run(['git', '--git-dir', str(mirror), 'symbolic-ref', 'HEAD', source['ref']], cwd=work)
            commands.run(['git', 'clone', '--no-hardlinks', str(mirror), str(checkout)], cwd=work)
            if commands.run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], cwd=work).strip().decode() != source['commit']:
                raise OfflineError('VCS_COMMIT')
            subject = checkout / expected['subdirectory']
            system = tomllib.loads(read_original(subject / 'pyproject.toml').decode())['build-system']
            if system.get('backend-path') or system['build-backend'] not in {'setuptools.build_meta', 'hatchling.build'}:
                raise OfflineError('UNFROZEN_BUILD_BACKEND')
            validate_dynamic_requirements(system['requires'], tools, environment)
            hook = ('import importlib,json; b=importlib.import_module(' + repr(system['build-backend']) +
                    '); print("AI4R_BUILD_REQUIRES="+json.dumps(b.get_requires_for_build_wheel({})))')
            observed = commands.run([python, '-I', '-c', hook], cwd=subject).decode()
            lines = [line[len('AI4R_BUILD_REQUIRES='):] for line in observed.splitlines() if line.startswith('AI4R_BUILD_REQUIRES=')]
            if len(lines) != 1:
                raise OfflineError('BUILD_HOOK_RESULT')
            dynamic = json.loads(lines[0])
            validate_dynamic_requirements(dynamic, tools, environment)
            wheel_output = work / (name + '-built')
            wheel_output.mkdir()
            commands.run([base_python(), '-I', '-m', 'pip', '--python', python, 'wheel', '--no-index',
                          '--no-build-isolation', '--no-deps', '--no-cache-dir', '--wheel-dir', str(wheel_output), str(subject)], cwd=work)
            wheels = list(wheel_output.glob('*.whl'))
            if len(wheels) != 1:
                raise OfflineError('BUILD_OUTPUT_CLOSURE')
            locked = selected_packages(tomllib.loads(read_original(root / manifest['lock']).decode()), environment=environment)
            audit = audit_distribution(wheels[0], expected_name=name, expected_version=locked[name]['version'])
            # pip applies POSIX metadata when publishing wheels. Keep that
            # operation on Linux storage, then publish original bytes only.
            published = Path(evidence) / (name + '-built'); published.mkdir()
            raw_wheel = read_original(wheels[0])
            with (published / wheels[0].name).open('xb') as stream:
                stream.write(raw_wheel)
            if sha(raw_wheel) != audit['sha256']:
                raise OfflineError('BUILD_OUTPUT_CHANGED')
            results[name] = {'url': source['url'], 'commit': source['commit'], 'ref': source['ref'],
                             'tree': tree, 'subdirectory': expected['subdirectory'], 'backend': system,
                             'dynamic_requires': dynamic, 'wheel_sha256': audit['sha256'],
                             'wheel_metadata': audit['metadata']}
    return results


def produce(*, candidate_file, snapshot, source_build, input_root, input_inventory,
            build_requirements, delivered_assets, output, evidence):
    if (sys.platform != 'linux' or sys.version_info[:2] != (3, 12)
            or {name for _, name in socket.if_nameindex()} - {'lo'}):
        raise OfflineError('ACTUAL_NETWORK_DENIED_LINUX_PYTHON312_REQUIRED')
    machine = platform.machine()
    target = {'x86_64': 'linux/amd64', 'aarch64': 'linux/arm64'}.get(machine)
    if target is None:
        raise OfflineError('UNSUPPORTED_PLATFORM')
    output, evidence = Path(output).absolute(), Path(evidence).absolute()
    if output.exists() or evidence.exists() or output.is_relative_to(evidence) or evidence.is_relative_to(output):
        raise OfflineError('FRESH_SEPARATE_OUTPUTS_REQUIRED')
    for path in (output, evidence):
        if any(parent.is_symlink() for parent in path.parents):
            raise OfflineError('OUTPUT_ALIAS')
    candidate_raw = read_original(candidate_file)
    candidate = json.loads(candidate_raw)
    pins = validate_manifest(candidate)
    build_raw = read_original(source_build); build = json.loads(build_raw)
    if (build.get('outcome') != 'BUILT' or build.get('target') != 'app-production'
            or build.get('candidate_id') != candidate['candidate_id']
            or build.get('candidate_manifest_sha256') != sha(candidate_raw)
            or build.get('snapshot_sha256') != candidate['snapshot']['sha256']
            or build.get('platform') != target):
        raise OfflineError('SOURCE_BUILD_IDENTITY')
    installed = build.get('runtime', {}).get('observation', {}).get('build', {}).get('value', {})
    installed_identity = {key: value for key, value in installed.items() if key != 'build_id'}
    installed_digest = sha(json.dumps(installed_identity, sort_keys=True, separators=(',', ':')).encode())
    if (installed.get('build_id') != installed_digest or installed.get('pyproject_sha256') != pins['pyproject.toml']['sha256']
            or installed.get('uv_lock_sha256') != pins['uv.lock']['sha256']):
        raise OfflineError('INSTALLED_BUILD_IDENTITY')
    with tempfile.TemporaryDirectory(prefix='ai4r-offline-source-') as temporary:
        context_tar(candidate, snapshot, Path(temporary) / 'context.tar')
    with zipfile.ZipFile(snapshot) as archive:
        project_raw, lock_raw = archive.read('pyproject.toml'), archive.read('uv.lock')
    project, lock = tomllib.loads(project_raw.decode()), tomllib.loads(lock_raw.decode())
    environment = default_environment()
    selected = selected_packages(lock, environment=environment)
    validate_original_vcs(selected)
    tool_raw = read_original(build_requirements); tools = parse_build_requirements(tool_raw.decode())
    if set(tools) != TOOLS:
        raise OfflineError('EXPLICIT_EIGHT_BUILD_TOOLS_REQUIRED')
    assets_raw = read_original(delivered_assets); assets = json.loads(assets_raw)
    if assets.get('pyproject_sha256') != sha(project_raw) or assets.get('uv_lock_sha256') != sha(lock_raw):
        raise OfflineError('DELIVERED_SOURCE_IDENTITY')
    inventory_raw = read_original(input_inventory); inventory = json.loads(inventory_raw)
    rows = inventory.get('artifacts', [])
    if not isinstance(rows, list) or not 0 < len(rows) <= 1000:
        raise OfflineError('INPUT_INVENTORY')
    originals, wheels, bundles = {}, {}, {}
    tags = {str(tag) for tag in sys_tags()}
    for row in rows:
        name = canonical(row['path'])
        if name in originals:
            raise OfflineError('DUPLICATE_INPUT')
        data = verified_input(input_root, name, {key: row[key] for key in ('bytes', 'sha256')})
        originals[name] = {'bytes': len(data), 'sha256': sha(data)}
        path = Path(input_root) / name
        if name.endswith('.whl'):
            wheel_name, _, _, _ = parse_wheel_filename(path.name)
            report = audit_distribution(path, expected_name=str(wheel_name))
            if {key: report[key] for key in ('bytes', 'sha256')} != originals[name]:
                raise OfflineError('AUDIT_ORIGINAL_BYTE_JOIN')
            key = normalized_name(report['metadata']['name'])
            if key in wheels:
                raise OfflineError('DUPLICATE_DISTRIBUTION')
            validate_target_tags(report, tags, environment['python_full_version'])
            if key in {'workswarm', 'workswarm-tui', 'jiuwenswarm'}:
                original = assets['wheels'][key]
                if report['sha256'] != original['sha256'] or report['members'] != original['members']:
                    raise OfflineError('DELIVERED_WHEEL_IDENTITY')
                if key == 'workswarm':
                    strict = audit_native(path, project)
                    if {field: strict[field] for field in ('bytes', 'sha256')} != originals[name]:
                        raise OfflineError('AUDIT_ORIGINAL_BYTE_JOIN')
                bind_delivered_members(key, report, pins, project, installed)
            else:
                if key in selected and 'registry' in selected[key]['source']:
                    locked = selected[key]
                    if report['metadata']['version'] != locked['version'] or not any(
                            item['hash'] == 'sha256:' + report['sha256'] and item['size'] == report['bytes']
                            and item['url'].rsplit('/', 1)[-1] == path.name for item in locked['wheels']):
                        raise OfflineError('UNLOCKED_ORIGINAL_WHEEL')
                elif key not in tools:
                    raise OfflineError('UNSELECTED_WHEEL')
            if key in tools and (report['sha256'] not in tools[key][1] or report['metadata']['version'] != tools[key][0]):
                raise OfflineError('BUILD_TOOL_WHEEL_PIN')
            wheels[key] = (path, report)
        elif name.endswith('.bundle'):
            add_bundle(bundles, name)
        else:
            raise OfflineError('UNSUPPORTED_INPUT_ARTIFACT')
    expected = (set(selected) - set(VCS)) | set(tools) | {'jiuwenswarm'}
    if set(wheels) != expected or set(bundles) != {'agent-core.bundle', 'agent-protocol.bundle'}:
        raise OfflineError('COMPLETE_ARTIFACT_CLOSURE_REQUIRED')
    version = wheels['workswarm'][1]['metadata']['version']
    if (wheels['workswarm-tui'][1]['metadata']['version'] != version
            or wheels['jiuwenswarm'][1]['metadata']['version'] != version
            or wheels['jiuwenswarm'][1]['metadata']['requires_dist'] != ['workswarm[codex,tui]==' + version]):
        raise OfflineError('COMPATIBILITY_METADATA')
    # Validate all originals before materializing the fresh, closed public tree.
    output.mkdir(); evidence.mkdir()
    files = {}
    def put(name, data):
        canonical(name)
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(data)
        files[name] = {'bytes': len(data), 'sha256': sha(data)}
    try:
        for name, (path, report) in wheels.items():
            original = next(key for key in originals if Path(key).name == path.name)
            put('wheelhouse/' + path.name, verified_input(input_root, original, originals[original]))
        sources = []
        for name, expected_vcs in VCS.items():
            filename = 'agent-core.bundle' if name == 'openjiuwen' else 'agent-protocol.bundle'
            original = bundles[filename]
            put('vcs/' + filename, verified_input(input_root, original, originals[original]))
            sources.append({key: expected_vcs[key] for key in ('url', 'commit', 'ref')} | {'bundle': 'vcs/' + filename})
        put('source/pyproject.toml', project_raw); put('source/uv.lock', lock_raw)
        put('source/candidate.json', candidate_raw); put('source/source-build.json', build_raw)
        snapshot_raw = read_original(snapshot)
        if sha(snapshot_raw) != candidate['snapshot']['sha256']:
            raise OfflineError('SNAPSHOT_CHANGED_BEFORE_COPY')
        put('source/source.zip', snapshot_raw); put('source/delivered-assets.json', assets_raw)
        put('build-requirements.txt', tool_raw)
        put('wheel-audits.json', encoded({name: report for name, (_, report) in sorted(wheels.items())}))
        home = evidence / 'home'; home.mkdir()
        env = safe_environment(home, output / 'wheelhouse')
        commands = Commands(evidence, env)
        observed_tools = {name: commands.run([name, '--version'], cwd=evidence).decode().strip() for name in ('git', 'node', 'codex')}
        if not observed_tools['node'].startswith('v22.') or not re.search(r'\b0\.144\.4\b', observed_tools['codex']):
            raise OfflineError('PINNED_NATIVE_TOOLS_REQUIRED')
        frontend = observe_pip_frontend(commands, evidence)
        put('source/controller-runtime.json', encoded(controller_runtime(target, frontend)))
        manifest = {'schema': 'ai4r-offline-install-artifacts:1', 'candidate_id': candidate['candidate_id'],
                    'platform': target, 'project': 'source/pyproject.toml', 'lock': 'source/uv.lock',
                    'wheelhouse': 'wheelhouse', 'build_requirements': 'build-requirements.txt',
                    'vcs_sources': sources, 'files': files}
        backend_evidence = evidence / 'backends'; backend_evidence.mkdir()
        backend = verify_backends(output, manifest, tools, environment, backend_evidence)
        put('provenance.json', encoded({'schema': 'ai4r-offline-provenance:1',
            'candidate_id': candidate['candidate_id'], 'platform': target, 'python': sys.version,
            'marker_environment': environment, 'wheel_tags': sorted(tags), 'tools': observed_tools,
            'input_inventory_sha256': sha(inventory_raw), 'original_inputs': originals,
            'selected_runtime': {name: {key: row[key] for key in ('name', 'version', 'source')} for name, row in selected.items()},
            'backend_results': backend, 'scope': 'Frozen input/build closure, not installation or product acceptance'}))
        verify_materialized(output, files)
        manifest_raw = encoded(manifest)
        with (output / 'offline-manifest.json').open('xb') as stream: stream.write(manifest_raw)
        profile = {'schema': 'ai4r-offline-install-profile:1', 'artifact_root': str(output), 'manifest_sha256': sha(manifest_raw)}
        with (evidence / 'profile.json').open('xb') as stream: stream.write(encoded(profile))
        result = {'outcome': 'PRODUCED', 'candidate_id': candidate['candidate_id'], 'platform': target,
                  'artifacts': len(files), 'original_wheels': len(wheels), 'original_bundles': len(sources),
                  'manifest_sha256': sha(manifest_raw), 'profile': str(evidence / 'profile.json'),
                  'installation': 'NOT_RUN', 'product_acceptance': 'NOT_ASSESSED'}
    except BaseException as error:
        (evidence / 'outcome.json').write_bytes(encoded({'outcome': 'PARTIAL_OR_FAILED',
            'reason': str(error), 'type': type(error).__name__, 'product_acceptance': 'NOT_ASSESSED'}))
        raise
    (evidence / 'outcome.json').write_bytes(encoded(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate-file', 'snapshot', 'source-build', 'input-root', 'input-inventory',
                 'build-requirements', 'delivered-assets', 'output', 'evidence'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(**vars(args))))


if __name__ == '__main__':
    main()
