"""Actual offline installation from public frozen artifacts, never app credentials.

The complete artifact producer/positive population is not yet qualified. An
absent artifact profile fails before any installer effect; it is never skipped.
The controller image and original image/source closure remain separate pins.
"""
import hashlib
import fnmatch
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import sysconfig
import tomllib
import zipfile

import pytest
from packaging.markers import Marker, default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename
from packaging.version import Version

from scripts.research_offline_assets import audit_distribution, audit_native, audit_wheel, normalized_name, relative


VCS = {
    'https://gitcode.com/openJiuwen/agent-core.git': ('9e3390195a9ea15235b2b5f7412cb2aa440622cc', 'refs/heads/ai4r-offline'),
    'https://gitcode.com/openJiuwen/agent-protocol.git': ('f70ae827ba059deddef87406f90b77bcde403dc1', 'refs/heads/feature/intelliRouter'),
}
BUILD_TOOLS = frozenset({'hatchling', 'packaging', 'pathspec', 'pluggy', 'setuptools',
                         'tomlkit', 'trove-classifiers', 'wheel'})


def regular(path):
    path = Path(path)
    assert path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'ARTIFACT_CUSTODY'
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 1024**3, 'ARTIFACT_CUSTODY'
        data = stream.read(1024**3 + 1)
        after = os.fstat(stream.fileno())
    assert (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino), 'ARTIFACT_CHANGED'
    assert len(data) == before.st_size, 'ARTIFACT_CHANGED'
    return data


def controller_runtime(root, manifest):
    observed = json.loads(regular(root / 'source/controller-runtime.json'))
    assert set(observed) == {'schema', 'platform', 'python_version', 'python_file', 'packaging_version', 'tool_files', 'pip_frontend'}, 'RUNTIME_FILE_FIELDS'
    assert observed['schema'] == 'ai4r-offline-controller-runtime:1', 'RUNTIME_FILE_SCHEMA'
    assert observed['platform'] == manifest['platform'] and observed['python_version'] == platform.python_version(), 'RUNTIME_FILE_PLATFORM'
    assert observed['packaging_version'] == importlib.metadata.version('packaging'), 'RUNTIME_PACKAGING'
    assert set(observed['tool_files']) == {'git', 'node', 'codex'}, 'RUNTIME_TOOL_CLOSURE'
    expected = {'python': Path(sys.executable).resolve()}
    for name in ('git', 'node', 'codex'):
        located = shutil.which(name)
        assert located, 'RUNTIME_TOOL_UNAVAILABLE:' + name
        expected[name] = Path(located).resolve()
    for name, path in expected.items():
        record = observed['python_file'] if name == 'python' else observed['tool_files'][name]
        assert set(record) == {'path', 'bytes', 'sha256'} and type(record['bytes']) is int, 'RUNTIME_TOOL_FIELDS'
        data = regular(path)
        assert record == {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, 'RUNTIME_TOOL_IDENTITY:' + name
    frontend = observed['pip_frontend']
    assert set(frontend) == {'version', 'python_file', 'files'}, 'RUNTIME_PIP_FIELDS'
    base_python = Path(sys._base_executable).resolve()
    base_raw = regular(base_python)
    assert frontend['python_file'] == {'path': str(base_python), 'bytes': len(base_raw), 'sha256': hashlib.sha256(base_raw).hexdigest()}, 'RUNTIME_PIP_PYTHON'
    purelib = Path(sysconfig.get_path('purelib', vars={'base': sys.base_prefix, 'platbase': sys.base_prefix}))
    distributions = [d for d in importlib.metadata.distributions(path=[str(purelib)]) if normalized_name(d.metadata['Name']) == 'pip']
    assert len(distributions) == 1 and frontend['version'] == distributions[0].version, 'RUNTIME_PIP_METADATA'
    pip_root = Path(distributions[0].locate_file('pip'))
    assert pip_root.is_absolute() and pip_root.is_dir() and not pip_root.is_symlink(), 'RUNTIME_PIP_ROOT'
    files = []
    for item in sorted(pip_root.rglob('*')):
        assert not item.is_symlink() and (item.is_file() or item.is_dir()), 'RUNTIME_PIP_CUSTODY'
        if item.is_file() and item.suffix == '.py':
            data = regular(item)
            files.append({'path': str(item), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    required = {str(pip_root / name) for name in ('__init__.py', '__main__.py', '__pip-runner__.py')}
    assert required <= {row['path'] for row in files} and 0 < len(files) <= 2000 and sum(row['bytes'] for row in files) <= 128 * 1024**2 and frontend['files'] == files, 'RUNTIME_PIP_CLOSURE'
    return observed


def source_context(root, manifest, expected_candidate):
    """Recompute source identity; producer outcomes and backend booleans confer no trust."""
    candidate_raw = regular(root / 'source/candidate.json')
    assert candidate_raw == regular(expected_candidate), 'EXPECTED_CANDIDATE_MISMATCH'
    candidate = json.loads(candidate_raw)
    assert candidate['schema_version'] == '1.0.0' and candidate['candidate_id'] == manifest['candidate_id'], 'CANDIDATE_IDENTITY'
    identity = {k: candidate[k] for k in ('schema_version', 'base_head', 'scope', 'files')}
    assert hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest() == candidate['candidate_id'], 'CANDIDATE_IDENTITY'
    rows = candidate['files']; assert isinstance(rows, list) and 0 < len(rows) <= 50000, 'SOURCE_INVENTORY'
    names = [relative(row['path']) for row in rows]
    assert names == sorted(set(names)) and len({n.casefold() for n in names}) == len(names), 'SOURCE_INVENTORY'
    pins = {row['path']: row for row in rows}
    assert all(type(row['bytes']) is int and 0 <= row['bytes'] <= 128 * 1024**2 for row in rows) and sum(row['bytes'] for row in rows) <= 1024**3, 'SOURCE_INVENTORY_BOUND'
    archive_raw = regular(root / 'source/source.zip')
    assert hashlib.sha256(archive_raw).hexdigest() == candidate['snapshot']['sha256'], 'SOURCE_ARCHIVE_HASH'
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        members = archive.infolist()
        assert len(members) == len(names) and {m.filename for m in members} == set(names), 'SOURCE_ARCHIVE_CLOSURE'
        for member in members:
            pin = pins[member.filename]
            assert set(pin) == {'path', 'bytes', 'sha256'} and type(pin['bytes']) is int and 0 <= pin['bytes'] <= 1024**3, 'SOURCE_INVENTORY'
            assert stat.S_ISREG(member.external_attr >> 16) and stat.S_IMODE(member.external_attr >> 16) == 0o644 and not member.flag_bits & 1, 'SOURCE_ARCHIVE_TYPE'
            assert member.file_size == pin['bytes'], 'SOURCE_ARCHIVE_SIZE'
            data = archive.read(member)
            assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256'], 'SOURCE_ARCHIVE_MEMBER'
        assert regular(root / manifest['project']) == archive.read('pyproject.toml'), 'SOURCE_PROJECT_MISMATCH'
        assert regular(root / manifest['lock']) == archive.read('uv.lock'), 'SOURCE_LOCK_MISMATCH'
    build = json.loads(regular(root / 'source/source-build.json'))
    assert (build['schema'] == 'ai4r-source-build:1' and build['target'] == 'app-production'
            and build['candidate_id'] == candidate['candidate_id']
            and build['candidate_manifest_sha256'] == hashlib.sha256(candidate_raw).hexdigest()
            and build['snapshot_sha256'] == candidate['snapshot']['sha256']
            and build['platform'] == manifest['platform']), 'SOURCE_BUILD_IDENTITY'
    installed = build.get('runtime', {}).get('observation', {}).get('build', {}).get('value', {})
    installed_identity = {k: value for k, value in installed.items() if k != 'build_id'}
    assert installed.get('schema') == 'ai4r-installed-build:2' and installed.get('build_id') == hashlib.sha256(json.dumps(installed_identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), 'INSTALLED_BUILD_IDENTITY'
    assert installed.get('pyproject_sha256') == pins['pyproject.toml']['sha256'] and installed.get('uv_lock_sha256') == pins['uv.lock']['sha256'], 'INSTALLED_SOURCE_IDENTITY'
    assets = json.loads(regular(root / 'source/delivered-assets.json'))
    assert assets['pyproject_sha256'] == hashlib.sha256(regular(root / manifest['project'])).hexdigest() and assets['uv_lock_sha256'] == hashlib.sha256(regular(root / manifest['lock'])).hexdigest(), 'DELIVERED_SOURCE_IDENTITY'
    provenance = json.loads(regular(root / 'provenance.json'))
    observed = default_environment()
    target = {'x86_64': 'linux/amd64', 'aarch64': 'linux/arm64'}.get(platform.machine())
    assert sys.platform == 'linux' and sys.version_info[:2] == (3, 12), 'RUNTIME_LINUX_PYTHON312'
    assert provenance['schema'] == 'ai4r-offline-provenance:1' and provenance['candidate_id'] == candidate['candidate_id'], 'RUNTIME_PROVENANCE'
    assert provenance['platform'] == manifest['platform'] == target and provenance['python'] == sys.version, 'RUNTIME_PLATFORM'
    for key in ('implementation_name', 'python_full_version', 'python_version', 'os_name', 'platform_machine', 'sys_platform', 'platform_python_implementation'):
        assert provenance['marker_environment'][key] == observed[key], 'RUNTIME_MARKER_ENVIRONMENT'
    assert set(provenance['wheel_tags']) == {str(t) for t in sys_tags()}, 'RUNTIME_WHEEL_TAGS'
    controller_runtime(root, manifest)
    return candidate, assets, provenance


def git_environment(base, rewrites):
    result = {key: value for key, value in base.items() if not key.startswith('GIT_CONFIG_KEY_') and not key.startswith('GIT_CONFIG_VALUE_')}
    pairs = [('credential.helper', '')] + [('url.' + local + '.insteadOf', original) for original, local in sorted(rewrites.items())]
    result['GIT_CONFIG_COUNT'] = str(len(pairs))
    for index, (key, value) in enumerate(pairs):
        result['GIT_CONFIG_KEY_' + str(index)] = key
        result['GIT_CONFIG_VALUE_' + str(index)] = value
    return result


def build_tools(text):
    result = {}
    for line in text.replace('\\\n', ' ').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'\s*([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)((?:\s+--hash=sha256:[0-9a-f]{64})+)\s*', line)
        assert match, 'BUILD_TOOL_REQUIREMENT_MUST_HAVE_EXACT_VERSION_AND_HASH'
        key = normalized_name(match[1]); assert key not in result, 'DUPLICATE_BUILD_TOOL_REQUIREMENT'
        result[key] = (match[2], set(re.findall(r'--hash=sha256:([0-9a-f]{64})', match[3])))
    assert result, 'BUILD_TOOL_REQUIREMENTS_EMPTY'
    return result


def require_frozen_backend(requirements, tools):
    assert isinstance(requirements, list) and len(requirements) <= 100, 'BUILD_REQUIREMENT_BOUND'
    for value in requirements:
        requirement = Requirement(value)
        assert not requirement.url and not requirement.extras, 'BUILD_REQUIREMENT_AUTHORITY'
        if requirement.marker and not requirement.marker.evaluate(default_environment()):
            continue
        key = normalized_name(requirement.name)
        assert key in tools and Version(tools[key][0]) in requirement.specifier, 'BUILD_REQUIREMENT_NOT_FROZEN'


def compatible_wheel(report):
    supported = {str(tag) for tag in sys_tags()}
    assert supported.intersection(report['filename_tags']), 'INCOMPATIBLE_FILENAME_TAG'
    assert supported.intersection(report['wheel_tags']), 'INCOMPATIBLE_METADATA_TAG'
    expected = 'equal' if set(report['filename_tags']) == set(report['wheel_tags']) else 'mismatch'
    assert report['tag_consistency'] == expected, 'TAG_DIAGNOSTIC_INCONSISTENT'


def expected_native_members(source_pins, project):
    """Recompute required importable source and declared package-data membership."""
    config = project['tool']['setuptools']
    excluded_packages = config['packages']['find'].get('exclude', [])
    required = set()
    for package, source_prefix in (('jiuwenswarm', 'jiuwenswarm/'), ('jiuwenbox', 'jiuwenbox/src/jiuwenbox/')):
        for name in source_pins:
            if not name.startswith(source_prefix): continue
            tail = name[len(source_prefix):]; parts = tail.split('/')
            module_package = '.'.join((package, *parts[:-1]))
            parents = [source_prefix + '/'.join((*parts[:depth], '__init__.py')) for depth in range(len(parts))]
            module = name.endswith('.py') and all(parent in source_pins for parent in parents)
            module = module and not any(fnmatch.fnmatchcase(module_package, p) for p in excluded_packages)
            resource = any(fnmatch.fnmatchcase(tail, p) for p in config.get('package-data', {}).get(package, []))
            resource = resource and not any(fnmatch.fnmatchcase(tail, p) for p in config.get('exclude-package-data', {}).get(package, []))
            if module or resource: required.add(package + '/' + tail)
    return required


def validate_inputs(profile_path, expected_candidate):
    p = json.loads(regular(profile_path))
    assert set(p) == {'schema', 'artifact_root', 'manifest_sha256'} and p['schema'] == 'ai4r-offline-install-profile:1'
    root = Path(p['artifact_root'])
    assert root.is_absolute() and root.is_dir() and all(not q.is_symlink() for q in (root, *root.parents)), 'ARTIFACT_CUSTODY'
    manifest = root / 'offline-manifest.json'; raw = regular(manifest)
    assert hashlib.sha256(raw).hexdigest() == p['manifest_sha256'], 'MANIFEST_HASH'
    m = json.loads(raw)
    assert set(m) == {'schema', 'candidate_id', 'platform', 'project', 'lock', 'wheelhouse', 'build_requirements', 'vcs_sources', 'files'}
    assert m['schema'] == 'ai4r-offline-install-artifacts:1' and re.fullmatch('[0-9a-f]{64}', m['candidate_id'])
    assert m['platform'] in {'linux/amd64', 'linux/arm64'}, 'UNSUPPORTED_PLATFORM'
    actual = set()
    for item in root.rglob('*'):
        assert not item.is_symlink(), 'ARTIFACT_CUSTODY'
        assert stat.S_ISDIR(item.stat().st_mode) or stat.S_ISREG(item.stat().st_mode), 'ARTIFACT_CUSTODY'
        if item.is_file() and item != manifest:
            actual.add(item.relative_to(root).as_posix())
    assert actual == set(m['files']), 'ARTIFACT_MEMBER_CLOSURE'
    for name, record in m['files'].items():
        relative(name)
        assert set(record) == {'sha256', 'bytes'} and type(record['bytes']) is int and 0 <= record['bytes'] <= 1024**3
        data = regular(root / name)
        assert len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'], 'ARTIFACT_HASH_OR_SIZE'
    for key in ('project', 'lock', 'build_requirements'):
        assert relative(m[key]) in m['files'], 'REQUIRED_ARTIFACT'
    assert relative(m['wheelhouse']) and (root / m['wheelhouse']).is_dir()
    sources = m['vcs_sources']
    assert isinstance(sources, list) and len(sources) == 2
    assert {x['url'] for x in sources} == set(VCS)
    for source in sources:
        assert set(source) == {'url', 'commit', 'ref', 'bundle'}
        assert (source['commit'], source['ref']) == VCS[source['url']]
        assert relative(source['bundle']) in m['files']
    assert (m['project'], m['lock'], m['wheelhouse'], m['build_requirements']) == ('source/pyproject.toml', 'source/uv.lock', 'wheelhouse', 'build-requirements.txt'), 'FIXED_ARTIFACT_LOCATORS'
    assert len({x['bundle'] for x in sources}) == 2, 'DUPLICATE_BUNDLE'
    assert {x['bundle'] for x in sources} == {'vcs/agent-core.bundle', 'vcs/agent-protocol.bundle'}, 'FIXED_BUNDLE_LOCATORS'
    required = {'source/candidate.json', 'source/source.zip', 'source/source-build.json',
                'source/delivered-assets.json', 'source/controller-runtime.json', 'wheel-audits.json', 'provenance.json'}
    assert required <= set(m['files']), 'ARTIFACT_REQUIRED_CLOSURE'
    fixed = required | {'source/pyproject.toml', 'source/uv.lock', 'build-requirements.txt',
                        'vcs/agent-core.bundle', 'vcs/agent-protocol.bundle'}
    assert all(name in fixed or (name.startswith('wheelhouse/') and len(Path(name).parts) == 2
                                 and name.endswith('.whl')) for name in m['files']), 'ARTIFACT_ALLOWED_CLOSURE'
    source_context(root, m, Path(expected_candidate))
    return root, m


def read_inputs():
    value, expected = os.getenv('AI4R_OFFLINE_INSTALL_PROFILE'), os.getenv('AI4R_OFFLINE_EXPECTED_CANDIDATE')
    if not value or not expected:
        pytest.fail('BLOCKED: complete offline profile and external expected candidate are required; zero installation effects')
    return validate_inputs(Path(value), Path(expected))


def runtime_packages(locked):
    """Independent fixed-point walk; do not trust producer selected_runtime."""
    environment = default_environment(); chosen = {}; pending = [('workswarm', ('codex', 'tui'), None, None)]; visited = set()
    while pending:
        name, extras, version, source = pending.pop()
        options = [p for p in locked['package'] if normalized_name(p['name']) == name
                   and (version is None or Version(p['version']) == Version(version))
                   and (source is None or p['source'] == source)
                   and (not p.get('resolution-markers') or any(Marker(x).evaluate(environment) for x in p['resolution-markers']))]
        assert len(options) == 1, 'INDEPENDENT_LOCK_RESOLUTION'
        row = options[0]
        assert name not in chosen or chosen[name] == row, 'INDEPENDENT_LOCK_CONFLICT'
        chosen[name] = row
        for extra in (None, *extras):
            if (name, extra) in visited: continue
            visited.add((name, extra)); assert len(visited) <= 10000, 'LOCK_GRAPH_BOUND'
            if extra is None: edges = row.get('dependencies', [])
            else:
                assert extra in row.get('optional-dependencies', {}), 'INDEPENDENT_EXTRA_MISSING'
                edges = row['optional-dependencies'][extra]
            for edge in edges:
                if not edge.get('marker') or Marker(edge['marker']).evaluate(environment):
                    pending.append((normalized_name(edge['name']), tuple(edge.get('extra', [])), edge.get('version'), edge.get('source')))
    return chosen


def native_wheels(root, m):
    project = tomllib.loads((root / m['project']).read_text(encoding='utf-8'))
    locked = tomllib.loads((root / m['lock']).read_text(encoding='utf-8'))
    selected = runtime_packages(locked)
    tools = build_tools((root / m['build_requirements']).read_text(encoding='utf-8'))
    assert set(tools) == BUILD_TOOLS, 'EXACT_BUILD_TOOL_CLOSURE'
    provenance = json.loads(regular(root / 'provenance.json'))
    expected_selected = {name: {key: row[key] for key in ('name', 'version', 'source')} for name, row in selected.items()}
    assert provenance['selected_runtime'] == expected_selected, 'INDEPENDENT_RUNTIME_CLOSURE'
    assets = json.loads(regular(root / 'source/delivered-assets.json'))
    declared_audits = json.loads(regular(root / 'wheel-audits.json'))
    candidate = json.loads(regular(root / 'source/candidate.json'))
    source_pins = {row['path']: row for row in candidate['files']}
    build = json.loads(regular(root / 'source/source-build.json'))
    installed = build['runtime']['observation']['build']['value']
    wheels = {}
    for path in (root / m['wheelhouse']).glob('*.whl'):
        name, _, _, _ = parse_wheel_filename(path.name)
        report = audit_distribution(path, expected_name=str(name))
        key = normalized_name(report['metadata']['name'])
        assert key not in wheels, 'DUPLICATE_DISTRIBUTION'
        wheels[key] = (path, report)
        compatible_wheel(report)
        required_python = report['metadata']['requires_python']
        assert not required_python or Version(platform.python_version()) in SpecifierSet(required_python), 'INCOMPATIBLE_WHEEL_PYTHON'
        assert key in declared_audits and {k: v for k, v in report.items() if k != 'path'} == {k: v for k, v in declared_audits[key].items() if k != 'path'}, 'INDEPENDENT_WHEEL_AUDIT'
        if key in tools:
            assert (report['metadata']['version'], report['sha256'] in tools[key][1]) == (tools[key][0], True), 'BUILD_TOOL_WHEEL_PIN'
        if key in selected and 'registry' in selected[key]['source']:
            locked_row = selected[key]
            assert Version(report['metadata']['version']) == Version(locked_row['version']) and any(
                wheel['hash'] == 'sha256:' + report['sha256'] and wheel['size'] == report['bytes']
                and wheel['url'].rsplit('/', 1)[-1] == path.name for wheel in locked_row['wheels']), 'UNLOCKED_RUNTIME_WHEEL'
        elif key in {'workswarm', 'workswarm-tui', 'jiuwenswarm'}:
            assert report['sha256'] == assets['wheels'][key]['sha256'] and report['members'] == assets['wheels'][key]['members'], 'DELIVERED_WHEEL_IDENTITY'
            if key in {'workswarm', 'workswarm-tui'}:
                prefix = 'jiuwenswarm/' if key == 'workswarm' else 'jiuwenswarm_tui/'
                records = installed['files'] if key == 'workswarm' else installed['components']['jiuwenswarm_tui']['files']
                assert len({row['path'] for row in records}) == len(records), 'INSTALLED_MEMBER_DUPLICATE'
                image_files = {prefix + relative(row['path']): {k: row[k] for k in ('bytes', 'sha256')} for row in records}
                assert {n: value for n, value in report['members'].items() if n.startswith(prefix)} == image_files, 'INSTALLED_WHEEL_MEMBER_CLOSURE'
            for member, pin in report['members'].items():
                source_name = ('packages/jiuwenswarm-tui/' + member) if key == 'workswarm-tui' else ('jiuwenbox/src/' + member if member.startswith('jiuwenbox/') else member)
                if member.endswith('.py') and member.startswith(('jiuwenswarm/', 'jiuwenbox/', 'jiuwenswarm_tui/')) and '/node_modules/' not in member:
                    assert source_name in source_pins and pin == {k: source_pins[source_name][k] for k in ('bytes', 'sha256')}, 'SOURCE_PYTHON_MEMBER'
        else:
            assert key in tools, 'UNSELECTED_RUNTIME_OR_BUILD_INPUT'
    assert set(wheels) == (set(selected) - {'openjiuwen', 'intelli-router'}) | BUILD_TOOLS | {'jiuwenswarm'}, 'EXACT_WHEEL_CLOSURE'
    assert expected_native_members(source_pins, project) <= set(wheels['workswarm'][1]['members']), 'MISSING_REQUIRED_SOURCE_MEMBER'
    assert set(declared_audits) == set(wheels), 'AUDIT_INVENTORY_CLOSURE'
    audit_native(wheels['workswarm'][0], project)
    version = wheels['workswarm'][1]['metadata']['version']
    assert wheels['workswarm-tui'][1]['metadata']['version'] == version
    alias = wheels['jiuwenswarm'][1]
    assert alias['metadata']['version'] == version and alias['metadata']['requires_dist'] == ['workswarm[codex,tui]==' + version]
    return wheels, version


def test_delivered_wheels_preserve_metadata_and_native_tui():
    root, manifest = read_inputs()
    native_wheels(root, manifest)


class InstallCommands:
    """Contain each owned installer group and preserve interrupted observations."""
    def __init__(self, directory, environment):
        self.directory, self.environment, self.count = directory, environment, 0

    def __call__(self, argv, *, input=None, expect=0):
        self.count += 1
        prefix = self.directory / str(self.count)
        process = subprocess.Popen(argv, cwd=self.directory, env=self.environment,
                                   stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = process.communicate(input=input, timeout=120)
        except BaseException as exc:
            contained = False
            stdout, stderr = getattr(exc, 'stdout', None) or b'', getattr(exc, 'stderr', None) or b''
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
                contained = process.poll() is not None
            except BaseException:
                pass
            prefix.with_suffix('.stdout').write_bytes(stdout)
            prefix.with_suffix('.stderr').write_bytes(stderr)
            prefix.with_suffix('.json').write_text(json.dumps({'argv': list(map(str, argv)), 'outcome': 'OUTCOME_UNKNOWN',
                                                               'owned_group_kill_returned': contained}) + '\n')
            if isinstance(exc, subprocess.TimeoutExpired):
                raise AssertionError('INSTALL_EFFECT_TIMEOUT_OUTCOME_UNKNOWN') from exc
            raise
        result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
        prefix.with_suffix('.json').write_text(json.dumps({'argv': list(map(str, argv)), 'returncode': result.returncode}) + '\n')
        prefix.with_suffix('.stdout').write_bytes(stdout); prefix.with_suffix('.stderr').write_bytes(stderr)
        assert (result.returncode == 0) if expect == 0 else (result.returncode != 0), result.stderr[-4000:].decode(errors='replace')
        return result


@pytest.fixture(scope='module')
def installation_artifact_copy(tmp_path_factory):
    root, manifest = read_inputs()
    native_wheels(root, manifest)
    directory = tmp_path_factory.mktemp('invalid-offline-copies')
    copied = directory / 'artifacts'
    shutil.copytree(root, copied, symlinks=False)
    expected = directory / 'expected-candidate.json'
    expected.write_bytes(regular(Path(os.environ['AI4R_OFFLINE_EXPECTED_CANDIDATE'])))
    profile = directory / 'profile.json'
    original_manifest = regular(copied / 'offline-manifest.json')
    profile.write_text(json.dumps({'schema': 'ai4r-offline-install-profile:1', 'artifact_root': str(copied),
                                    'manifest_sha256': hashlib.sha256(original_manifest).hexdigest()}) + '\n')
    return copied, profile, expected, original_manifest


@pytest.mark.parametrize('fault', ['missing', 'wrong_version', 'corrupt', 'extra', 'alias'])
def test_invalid_artifact_copies_fail_before_installer(installation_artifact_copy, monkeypatch, fault):
    root, profile, expected, original_manifest = installation_artifact_copy
    manifest = json.loads(original_manifest)
    alias = next((root / 'wheelhouse').glob('jiuwenswarm-*.whl'))
    original = regular(alias)
    changed = alias
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args); raise AssertionError('INSTALLER_STARTED_FOR_INVALID_ARTIFACT')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    try:
        if fault == 'missing': alias.unlink()
        elif fault == 'corrupt': alias.write_bytes(original[:len(original) // 2])
        elif fault == 'alias':
            alias.unlink(); alias.symlink_to(root / 'source/uv.lock')
        elif fault == 'extra':
            changed = alias.with_name('foreign-' + alias.name); changed.write_bytes(original)
        else:
            changed = alias.with_name(re.sub(r'^jiuwenswarm-[^-]+-', 'jiuwenswarm-999-', alias.name))
            alias.rename(changed)
            record = manifest['files'].pop(alias.relative_to(root).as_posix())
            manifest['files'][changed.relative_to(root).as_posix()] = record
            raw = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
            (root / 'offline-manifest.json').write_bytes(raw)
            p = json.loads(profile.read_bytes()); p['manifest_sha256'] = hashlib.sha256(raw).hexdigest()
            profile.write_text(json.dumps(p) + '\n')
        with pytest.raises((AssertionError, ValueError, zipfile.BadZipFile)):
            validated, observed = validate_inputs(profile, expected)
            native_wheels(validated, observed)
        assert calls == []
    finally:
        if changed != alias and changed.exists(): changed.unlink()
        if alias.is_symlink(): alias.unlink()
        alias.write_bytes(original)
        (root / 'offline-manifest.json').write_bytes(original_manifest)
        profile.write_text(json.dumps({'schema': 'ai4r-offline-install-profile:1', 'artifact_root': str(root),
                                        'manifest_sha256': hashlib.sha256(original_manifest).hexdigest()}) + '\n')


def test_empty_venv_cannot_use_ambient_distribution_or_network(tmp_path):
    """Actual pip counterpart deliberately bypasses artifact preflight."""
    assert sys.platform == 'linux' and sys.version_info[:2] == (3, 12)
    assert {name for _, name in socket.if_nameindex()} <= {'lo'}, 'ACTUAL_NETWORK_DENIAL_REQUIRED'
    home = tmp_path / 'home'; home.mkdir()
    empty = tmp_path / 'empty-wheelhouse'; empty.mkdir()
    environment = {'PATH': os.environ['PATH'], 'HOME': str(home), 'LANG': 'C.UTF-8',
                   'PIP_CONFIG_FILE': '/dev/null', 'PIP_NO_INDEX': '1', 'PIP_NO_CACHE_DIR': '1',
                   'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PYTHONNOUSERSITE': '1'}
    run = InstallCommands(tmp_path, environment)
    venv = tmp_path / 'empty-venv'
    run([sys.executable, '-I', '-m', 'venv', str(venv)])
    assert 'include-system-site-packages = false' in (venv / 'pyvenv.cfg').read_text()
    python = str(venv / 'bin/python')
    probe = 'import importlib.metadata as m,importlib.util; assert importlib.util.find_spec("jiuwenswarm") is None; assert not any(d.metadata["Name"].lower() in ("workswarm","workswarm-tui","jiuwenswarm") for d in m.distributions())'
    run([python, '-I', '-c', probe])
    result = run([python, '-I', '-m', 'pip', 'install', '--no-index', '--find-links', str(empty), 'jiuwenswarm'], expect=1)
    assert b'No matching distribution found' in result.stderr, 'MISSING_WHEEL_DID_NOT_REACH_ACTUAL_RESOLVER'
    run([python, '-I', '-c', probe])


def test_empty_venv_literal_offline_installation(tmp_path):
    root, manifest = read_inputs()
    wheels, version = native_wheels(root, manifest)
    assert sys.version_info[:2] == (3, 12), 'PREPARED_PYTHON_REQUIRED'
    assert {name for _, name in socket.if_nameindex()} <= {'lo'}, 'ACTUAL_NETWORK_DENIAL_REQUIRED'
    assert shutil.which('git') and shutil.which('node'), 'PREPARED_GIT_NODE_REQUIRED'
    home = tmp_path / 'home'; home.mkdir()
    env = {'PATH': os.environ['PATH'], 'HOME': str(home), 'LANG': 'C.UTF-8', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0', 'GIT_ALLOW_PROTOCOL': 'file',
           'PIP_CONFIG_FILE': '/dev/null', 'PIP_NO_INDEX': '1', 'PIP_FIND_LINKS': str(root / manifest['wheelhouse']), 'PIP_NO_CACHE_DIR': '1',
           'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PYTHONNOUSERSITE': '1'}
    env = git_environment(env, {})
    run = InstallCommands(tmp_path, env)
    assert run(['node', '--version']).stdout.startswith(b'v22.'), 'PINNED_NODE22_REQUIRED'
    assert re.search(rb'\b0\.144\.4\b', run(['codex', '--version']).stdout), 'PINNED_CODEX_REQUIRED'
    tools = build_tools(regular(root / manifest['build_requirements']).decode())
    build_venv = tmp_path / 'backend-venv'
    run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(build_venv)])
    build_python = str(build_venv / 'bin/python')
    frontend = str(Path(sys._base_executable).resolve())
    frontend_pin = json.loads(regular(root / 'source/controller-runtime.json'))['pip_frontend']
    assert run([frontend, '-I', '-m', 'pip', '--version']).stdout.startswith(('pip ' + frontend_pin['version'] + ' ').encode()), 'ACTUAL_PIP_FRONTEND_VERSION'
    run([frontend, '-I', '-m', 'pip', '--python', build_python, 'install', '--no-index', '--find-links',
         str(root / manifest['wheelhouse']), '--no-deps', '--require-hashes', '-r', str(root / manifest['build_requirements'])])
    inventory_program = 'import importlib.metadata as m,json; print(json.dumps({d.metadata["Name"]:{"version":d.version,"root":str(d.locate_file(""))} for d in m.distributions()}))'
    isolated = {normalized_name(name): value for name, value in json.loads(run([build_python, '-I', '-c', inventory_program]).stdout).items()}
    assert set(isolated) == set(tools) and all(value['version'] == tools[name][0] and Path(value['root']).is_relative_to(build_venv)
                                               for name, value in isolated.items()), 'INDEPENDENT_CLOSED_BACKEND_ENVIRONMENT'
    rewrites = {}
    for ordinal, source in enumerate(manifest['vcs_sources']):
        repo = tmp_path / ('source-' + str(ordinal) + '.git')
        run(['git', 'clone', '--bare', str(root / source['bundle']), str(repo)])
        assert run(['git', '--git-dir', str(repo), 'rev-parse', source['ref']]).stdout.strip().decode() == source['commit']
        assert run(['git', '--git-dir', str(repo), 'rev-parse', '--is-shallow-repository']).stdout.strip() == b'false'
        assert not (repo / 'objects/info/alternates').exists() and not list(repo.rglob('*.promisor')) and not (repo / 'refs/replace').exists()
        assert run(['git', '--git-dir', str(repo), 'for-each-ref', '--format=%(objectname) %(refname)']).stdout.decode().splitlines() == [source['commit'] + ' ' + source['ref']], 'INDEPENDENT_VCS_REF_CLOSURE'
        run(['git', '--git-dir', str(repo), 'fsck', '--full', '--no-dangling'])
        run(['git', '--git-dir', str(repo), 'symbolic-ref', 'HEAD', source['ref']])
        rewrites[source['url']] = repo.as_uri()
        checkout = tmp_path / ('backend-source-' + str(ordinal))
        run(['git', 'clone', '--no-hardlinks', str(repo), str(checkout)])
        assert run(['git', '-C', str(checkout), 'rev-parse', 'HEAD']).stdout.strip().decode() == source['commit']
        subject = checkout / ('intelli_router' if source['url'].endswith('agent-protocol.git') else '')
        system = tomllib.loads(regular(subject / 'pyproject.toml').decode())['build-system']
        assert not system.get('backend-path') and system['build-backend'] in {'setuptools.build_meta', 'hatchling.build'}, 'INDEPENDENT_BACKEND_IDENTITY'
        require_frozen_backend(system['requires'], tools)
        hook = 'import importlib,json,os; os.chdir(' + repr(str(subject)) + '); b=importlib.import_module(' + repr(system['build-backend']) + '); print("AI4R_BUILD_REQUIRES="+json.dumps(b.get_requires_for_build_wheel({})))'
        lines = run([build_python, '-I', '-c', hook]).stdout.decode().splitlines()
        dynamic = [line[len('AI4R_BUILD_REQUIRES='):] for line in lines if line.startswith('AI4R_BUILD_REQUIRES=')]
        assert len(dynamic) == 1, 'INDEPENDENT_BACKEND_HOOK_RESULT'
        require_frozen_backend(json.loads(dynamic[0]), tools)
    env = git_environment(env, rewrites)
    run.environment = env
    venv = tmp_path / 'empty-venv'
    run([sys.executable, '-I', '-m', 'venv', str(venv)])
    assert 'include-system-site-packages = false' in (venv / 'pyvenv.cfg').read_text()
    python = str(venv / 'bin/python')
    baseline = {normalized_name(name): value for name, value in json.loads(run([python, '-I', '-c', inventory_program]).stdout).items()}
    assert set(baseline) == {'pip'} and all(Path(value['root']).is_relative_to(venv) for value in baseline.values()), 'EMPTY_VENV_BASELINE'
    # Explicit separate build inputs, all hash checked; no ambient site packages.
    run([python, '-I', '-m', 'pip', 'install', '--no-index', '--find-links', str(root / manifest['wheelhouse']),
         '--require-hashes', '-r', str(root / manifest['build_requirements'])])
    run([python, '-I', '-m', 'pip', 'install', '--no-index', '--find-links', str(root / manifest['wheelhouse']), 'jiuwenswarm'])
    run([python, '-I', '-m', 'pip', 'check'])
    installed_inventory = {normalized_name(name): value for name, value in json.loads(run([python, '-I', '-c', inventory_program]).stdout).items()}
    selected = runtime_packages(tomllib.loads(regular(root / manifest['lock']).decode()))
    expected_versions = {name: value['version'] for name, value in selected.items()}
    expected_versions.update({name: value[0] for name, value in tools.items()})
    expected_versions.update({'jiuwenswarm': version, 'pip': baseline['pip']['version']})
    assert set(installed_inventory) == set(expected_versions) and all(Version(value['version']) == Version(expected_versions[name])
        and Path(value['root']).is_relative_to(venv) for name, value in installed_inventory.items()), 'INSTALLED_EXACT_RUNTIME_AND_TOOL_CLOSURE'
    expected_members = {name: sorted(member for member in wheels[name][1]['members'] if not member.endswith('.dist-info/RECORD'))
                        for name in ('workswarm', 'workswarm-tui', 'jiuwenswarm')}
    member_file = tmp_path / 'expected-original-members.json'; member_file.write_text(json.dumps(expected_members) + '\n')
    member_probe = ('import hashlib,importlib.metadata as m,json,pathlib,sys; '
        'expected=json.loads(pathlib.Path(sys.argv[1]).read_bytes()); result={}; '
        '\nfor name,members in expected.items():\n d=m.distribution(name); rows={}\n for member in members:\n'
        '  p=pathlib.Path(d.locate_file(member)); assert p.is_file() and not p.is_symlink() and p.is_relative_to(pathlib.Path(sys.prefix)); '
        'data=p.read_bytes(); rows[member]={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}\n result[name]=rows\n'
        'print(json.dumps(result,sort_keys=True))')
    installed_members = json.loads(run([python, '-I', '-c', member_probe, str(member_file)]).stdout)
    for name, members in expected_members.items():
        assert installed_members[name] == {member: wheels[name][1]['members'][member] for member in members}, 'INSTALLED_ORIGINAL_NATIVE_BYTES'
    observed = run([python, '-I', '-c', 'import importlib.metadata as m,importlib.util,json; print(json.dumps({"version":m.version("workswarm"),"native":list(importlib.util.find_spec("jiuwenswarm").submodule_search_locations),"tui":m.version("workswarm-tui")}))'])
    installed = json.loads(observed.stdout)
    assert installed['version'] == installed['tui'] == version and all(Path(p).is_relative_to(venv) for p in installed['native'])
    vcs = run([python, '-I', '-c', 'import importlib.metadata as m,json; print(json.dumps({n:json.loads(m.distribution(n).read_text("direct_url.json")) for n in ("openjiuwen","intelli-router")}))'])
    actual_vcs = json.loads(vcs.stdout)
    for name, url in (('openjiuwen', 'https://gitcode.com/openJiuwen/agent-core.git'), ('intelli-router', 'https://gitcode.com/openJiuwen/agent-protocol.git')):
        assert actual_vcs[name]['url'] == url and actual_vcs[name]['vcs_info']['commit_id'] == VCS[url][0], 'INSTALLED_VCS_SOURCE_IDENTITY'
        expected_revision = VCS[url][0] if name == 'openjiuwen' else 'feature/intelliRouter'
        assert actual_vcs[name]['vcs_info']['vcs'] == 'git' and actual_vcs[name]['vcs_info']['requested_revision'] == expected_revision, 'INSTALLED_VCS_REQUESTED_REVISION'
        assert actual_vcs[name].get('subdirectory', '') == ('' if name == 'openjiuwen' else 'intelli_router'), 'INSTALLED_VCS_SUBDIRECTORY'
    for command in ('jiuwenswarm', 'jiuwenswarm-start', 'jiuwenswarm-tui', 'jiuwenswarm-init'):
        run([str(venv / 'bin' / command), '--help'])
    env['JIUWENSWARM_DATA_DIR'] = str(tmp_path / 'native-data')
    run([str(venv / 'bin/jiuwenswarm-init')], input=b'en\n')
    assert (tmp_path / 'native-data').is_dir()
    # No account/provider route is granted to installation checks.
    diagnostic = run([str(venv / 'bin/jiuwenswarm'), 'research', 'doctor'], expect=1)
    assert b'origin' in diagnostic.stdout + diagnostic.stderr and b'token' in diagnostic.stdout + diagnostic.stderr
