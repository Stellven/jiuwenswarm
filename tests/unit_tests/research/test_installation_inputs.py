"""Independent synthetic input guards, not complete offline installation evidence."""
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import stat
import sys
import sysconfig
import zipfile

from packaging.markers import default_environment
from packaging.tags import sys_tags
import pytest

from tests.integration.research.test_installation import compatible_wheel, expected_native_members, regular, require_frozen_backend, runtime_packages, validate_inputs


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def fixture(tmp_path, monkeypatch):
    # These are synthetic input-guard controls. Tool resolution is controlled;
    # actual installation independently requires the real pinned CLI versions.
    executable = Path(sys.executable).resolve()
    monkeypatch.setattr('shutil.which', lambda name: str(executable))
    executable_bytes = executable.read_bytes()
    tool = {'path': str(executable), 'bytes': len(executable_bytes), 'sha256': hashlib.sha256(executable_bytes).hexdigest()}
    base_python = Path(sys._base_executable).resolve(); base_bytes = base_python.read_bytes()
    base_library = sysconfig.get_path('purelib', vars={'base': sys.base_prefix, 'platbase': sys.base_prefix})
    pip_distribution = next(d for d in importlib.metadata.distributions(path=[base_library]) if d.metadata['Name'].lower() == 'pip')
    pip_files = []
    for p in sorted(Path(pip_distribution.locate_file('pip')).rglob('*.py')):
        data = p.read_bytes(); pip_files.append({'path': str(p), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    pip_frontend = {'version': pip_distribution.version,
        'python_file': {'path': str(base_python), 'bytes': len(base_bytes), 'sha256': hashlib.sha256(base_bytes).hexdigest()},
        'files': pip_files}
    root = tmp_path / 'artifacts'; root.mkdir()
    sources = {'pyproject.toml': b'[project]\nname="workswarm"\nversion="1.0"\n',
               'uv.lock': b'version=1\npackage=[]\n', 'jiuwenswarm/__init__.py': b'fixture=True\n'}
    identity = {'schema_version': '1.0.0', 'base_head': None, 'scope': ['synthetic-unit-fixture'],
                'files': [{'path': n, 'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for n, v in sorted(sources.items())]}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        for name, data in sorted(sources.items()):
            info = zipfile.ZipInfo(name); info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    archive = buffer.getvalue()
    candidate = {**identity, 'candidate_id': hashlib.sha256(raw(identity)).hexdigest(),
                 'snapshot': {'path': 'source.zip', 'sha256': hashlib.sha256(archive).hexdigest()}}
    candidate_raw = raw(candidate)
    target = {'x86_64': 'linux/amd64', 'aarch64': 'linux/arm64'}.get(platform.machine(), 'unsupported')
    installed = {'schema': 'ai4r-installed-build:2',
                 'pyproject_sha256': hashlib.sha256(sources['pyproject.toml']).hexdigest(),
                 'uv_lock_sha256': hashlib.sha256(sources['uv.lock']).hexdigest(),
                 'files': [{'path': '__init__.py', 'bytes': len(sources['jiuwenswarm/__init__.py']),
                            'sha256': hashlib.sha256(sources['jiuwenswarm/__init__.py']).hexdigest()}],
                 'links': [], 'components': {'jiuwenswarm_tui': {'files': [], 'links': []}}}
    installed['build_id'] = hashlib.sha256(raw(installed)).hexdigest()
    payloads = {'source/pyproject.toml': sources['pyproject.toml'], 'source/uv.lock': sources['uv.lock'],
                'source/candidate.json': candidate_raw, 'source/source.zip': archive,
                'source/source-build.json': raw({'schema': 'ai4r-source-build:1', 'outcome': 'BUILT',
                    'target': 'app-production', 'candidate_id': candidate['candidate_id'],
                    'candidate_manifest_sha256': hashlib.sha256(candidate_raw).hexdigest(),
                    'snapshot_sha256': candidate['snapshot']['sha256'], 'platform': target,
                    'runtime': {'observation': {'build': {'value': installed}}}}),
                'source/delivered-assets.json': raw({'pyproject_sha256': hashlib.sha256(sources['pyproject.toml']).hexdigest(),
                    'uv_lock_sha256': hashlib.sha256(sources['uv.lock']).hexdigest(), 'wheels': {}}),
                'source/controller-runtime.json': raw({'schema': 'ai4r-offline-controller-runtime:1',
                    'platform': target, 'python_version': platform.python_version(), 'python_file': tool,
                    'packaging_version': importlib.metadata.version('packaging'),
                    'tool_files': {name: tool for name in ('git', 'node', 'codex')}, 'pip_frontend': pip_frontend}),
                'build-requirements.txt': b'fixture==1 --hash=sha256:' + b'a' * 64 + b'\n',
                'wheelhouse/placeholder.whl': b'explicitly not a real wheel; input-tree guards only',
                'vcs/agent-core.bundle': b'synthetic core', 'vcs/agent-protocol.bundle': b'synthetic protocol',
                'wheel-audits.json': b'{}',
                'provenance.json': raw({'schema': 'ai4r-offline-provenance:1', 'candidate_id': candidate['candidate_id'],
                    'platform': target, 'python': sys.version, 'marker_environment': default_environment(),
                    'wheel_tags': sorted(map(str, sys_tags())), 'tools': {}, 'input_inventory_sha256': 'b' * 64,
                    'original_inputs': {}, 'selected_runtime': {}, 'backend_results': {}, 'scope': 'synthetic guard fixture'})}
    for name, data in payloads.items():
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    manifest = {'schema': 'ai4r-offline-install-artifacts:1', 'candidate_id': candidate['candidate_id'],
        'platform': target, 'project': 'source/pyproject.toml', 'lock': 'source/uv.lock',
        'wheelhouse': 'wheelhouse', 'build_requirements': 'build-requirements.txt',
        'vcs_sources': [
            {'url': 'https://gitcode.com/openJiuwen/agent-core.git', 'commit': '9e3390195a9ea15235b2b5f7412cb2aa440622cc',
             'ref': 'refs/heads/ai4r-offline', 'bundle': 'vcs/agent-core.bundle'},
            {'url': 'https://gitcode.com/openJiuwen/agent-protocol.git', 'commit': 'f70ae827ba059deddef87406f90b77bcde403dc1',
             'ref': 'refs/heads/feature/intelliRouter', 'bundle': 'vcs/agent-protocol.bundle'}],
        'files': {n: {'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for n, v in payloads.items()}}
    expected = tmp_path / 'expected.json'; expected.write_bytes(candidate_raw)
    profile = tmp_path / 'profile.json'
    publish(root, manifest, profile)
    return root, manifest, profile, expected


def publish(root, manifest, profile):
    data = raw(manifest); (root / 'offline-manifest.json').write_bytes(data)
    profile.write_bytes(raw({'schema': 'ai4r-offline-install-profile:1', 'artifact_root': str(root),
                             'manifest_sha256': hashlib.sha256(data).hexdigest()}))


def replace(root, manifest, name, data):
    (root / name).write_bytes(data)
    manifest['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def test_independent_source_guard_uses_external_candidate_and_original_zip(tmp_path, monkeypatch):
    root, manifest, profile, expected = fixture(tmp_path, monkeypatch)
    actual_root, actual = validate_inputs(profile, expected)
    assert actual_root == root and actual == manifest


@pytest.mark.parametrize('fault,reason', [
    ('missing', 'CLOSURE'), ('corrupt', 'HASH_OR_SIZE'), ('extra', 'CLOSURE'),
    ('alias', 'CUSTODY'), ('hardlink', 'CUSTODY'), ('external_candidate', 'EXPECTED_CANDIDATE'),
    ('source_project', 'SOURCE_PROJECT'), ('source_archive', 'SOURCE_ARCHIVE'),
    ('source_build', 'SOURCE_BUILD'), ('runtime', 'RUNTIME'), ('version', 'SOURCE_PROJECT'),
    ('tool_hash', 'RUNTIME_TOOL_IDENTITY'), ('tool_path', 'RUNTIME_TOOL_IDENTITY'),
    ('tool_extra', 'RUNTIME_TOOL_CLOSURE'), ('packaging', 'RUNTIME_PACKAGING'),
    ('hashed_extra', 'ARTIFACT_ALLOWED_CLOSURE'),
    ('installed_hash', 'INSTALLED_BUILD_IDENTITY'), ('installed_lock', 'INSTALLED_SOURCE_IDENTITY'),
    ('pip_hash', 'RUNTIME_PIP_CLOSURE'), ('pip_extra', 'RUNTIME_PIP_CLOSURE'),
    ('pip_version', 'RUNTIME_PIP_METADATA'), ('pip_python', 'RUNTIME_PIP_PYTHON'),
])
def test_bad_original_inputs_fail_before_any_install_or_ambient_fallback(tmp_path, monkeypatch, fault, reason):
    root, manifest, profile, expected = fixture(tmp_path, monkeypatch)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args); raise AssertionError('UNAUTHORIZED_INSTALL_OR_LOOKUP')
    monkeypatch.setattr('subprocess.Popen', forbidden)
    if fault == 'missing': (root / 'wheelhouse/placeholder.whl').unlink()
    elif fault == 'corrupt': (root / 'wheelhouse/placeholder.whl').write_bytes(b'corrupted')
    elif fault == 'extra': (root / 'wheelhouse/foreign.whl').write_bytes(b'not selected')
    elif fault == 'hashed_extra': replace(root, manifest, 'wheelhouse/ambient.zip', b'not a selected original wheel')
    elif fault == 'alias':
        p = root / 'wheelhouse/placeholder.whl'; p.unlink(); p.symlink_to(root / 'source/uv.lock')
    elif fault == 'hardlink':
        p = root / 'wheelhouse/placeholder.whl'; p.unlink(); p.hardlink_to(root / 'source/uv.lock')
    elif fault == 'external_candidate': expected.write_bytes(b'foreign expected candidate')
    elif fault in {'source_project', 'version'}:
        replace(root, manifest, 'source/pyproject.toml', b'[project]\nname="workswarm"\nversion="999"\n')
    elif fault == 'source_archive': replace(root, manifest, 'source/source.zip', b'foreign archive')
    elif fault == 'source_build':
        v = json.loads((root / 'source/source-build.json').read_bytes()); v['candidate_id'] = 'f' * 64
        replace(root, manifest, 'source/source-build.json', raw(v))
    elif fault in {'installed_hash', 'installed_lock'}:
        v = json.loads((root / 'source/source-build.json').read_bytes())
        installed = v['runtime']['observation']['build']['value']
        if fault == 'installed_hash': installed['build_id'] = '0' * 64
        else:
            installed['uv_lock_sha256'] = '0' * 64
            installed['build_id'] = hashlib.sha256(raw({k: value for k, value in installed.items() if k != 'build_id'})).hexdigest()
        replace(root, manifest, 'source/source-build.json', raw(v))
    elif fault == 'runtime':
        v = json.loads((root / 'provenance.json').read_bytes()); v['marker_environment']['python_version'] = '0.0'
        replace(root, manifest, 'provenance.json', raw(v))
    elif fault in {'tool_hash', 'tool_path', 'tool_extra', 'packaging', 'pip_hash', 'pip_extra', 'pip_version', 'pip_python'}:
        v = json.loads((root / 'source/controller-runtime.json').read_bytes())
        if fault == 'tool_hash': v['tool_files']['node']['sha256'] = '0' * 64
        elif fault == 'tool_path': v['tool_files']['git']['path'] = '/tmp/caller-selected-git'
        elif fault == 'tool_extra': v['tool_files']['ambient'] = v['python_file']
        elif fault == 'packaging': v['packaging_version'] = '0.0'
        elif fault == 'pip_hash': v['pip_frontend']['files'][0]['sha256'] = '0' * 64
        elif fault == 'pip_extra': v['pip_frontend']['files'].append(v['pip_frontend']['python_file'])
        elif fault == 'pip_version': v['pip_frontend']['version'] = '0.0'
        else: v['pip_frontend']['python_file']['path'] = '/tmp/unapproved-python'
        replace(root, manifest, 'source/controller-runtime.json', raw(v))
    publish(root, manifest, profile)
    with pytest.raises(AssertionError, match=reason): validate_inputs(profile, expected)
    assert calls == []


def test_backend_requirement_is_separate_from_available_runtime_wheels():
    tools = {'setuptools': ('82.0.1', {'0' * 64})}
    require_frozen_backend(['setuptools>=61', 'unavailable; python_version < "2"'], tools)


@pytest.mark.parametrize('requirements', [
    ['setuptools>=999'], ['packaging>=1'], ['setuptools[ambient]>=61'],
    ['setuptools @ https://example.invalid/setuptools.whl'],
])
def test_unfrozen_backend_requirements_reject(requirements):
    with pytest.raises(AssertionError):
        require_frozen_backend(requirements, {'setuptools': ('82.0.1', {'0' * 64})})


@pytest.mark.parametrize('report,reason', [
    ({'filename_tags': ['py3-none-win_arm64'], 'wheel_tags': ['py3-none-any'], 'tag_consistency': 'mismatch'}, 'FILENAME'),
    ({'filename_tags': ['py3-none-any'], 'wheel_tags': ['py3-none-win_arm64'], 'tag_consistency': 'mismatch'}, 'METADATA'),
    ({'filename_tags': ['py3-none-any'], 'wheel_tags': ['py3-none-any'], 'tag_consistency': 'mismatch'}, 'DIAGNOSTIC'),
])
def test_filename_and_metadata_targets_are_independently_required(report, reason):
    with pytest.raises(AssertionError, match=reason): compatible_wheel(report)


def test_recorded_tag_mismatch_does_not_widen_supported_target():
    actual = str(next(sys_tags()))
    compatible_wheel({'filename_tags': ['py3-none-any'], 'wheel_tags': [actual],
                      'tag_consistency': 'equal' if actual == 'py3-none-any' else 'mismatch'})


def test_runtime_extra_walk_is_independent_and_resolves_only_active_edges():
    locked = {'package': [
        {'name': 'workswarm', 'version': '1', 'source': {'virtual': '.'}, 'optional-dependencies':
            {'codex': [{'name': 'active'}], 'tui': [{'name': 'inactive', 'marker': 'python_version < "2"'}]}},
        {'name': 'active', 'version': '2', 'source': {'registry': 'https://example.invalid/simple'}},
        {'name': 'inactive', 'version': '3', 'source': {'registry': 'https://example.invalid/simple'}},
    ]}
    assert set(runtime_packages(locked)) == {'workswarm', 'active'}
    locked['package'].pop(1)
    with pytest.raises(AssertionError, match='LOCK_RESOLUTION'): runtime_packages(locked)


def test_source_membership_includes_modules_and_declared_resources_only():
    source = {name: {} for name in [
        'jiuwenswarm/__init__.py', 'jiuwenswarm/worker.py', 'jiuwenswarm/web/__init__.py',
        'jiuwenswarm/web/legacy.py', 'jiuwenswarm/unpackaged/loose.py',
        'jiuwenswarm/resources/public.json', 'jiuwenswarm/resources/private.json',
        'jiuwenbox/src/jiuwenbox/__init__.py', 'jiuwenbox/src/jiuwenbox/cli.py',
    ]}
    project = {'tool': {'setuptools': {'packages': {'find': {'exclude': ['jiuwenswarm.web*']}},
        'package-data': {'jiuwenswarm': ['resources/*']},
        'exclude-package-data': {'jiuwenswarm': ['resources/private.json']}}}}
    assert expected_native_members(source, project) == {'jiuwenswarm/__init__.py', 'jiuwenswarm/worker.py',
        'jiuwenswarm/resources/public.json', 'jiuwenbox/__init__.py', 'jiuwenbox/cli.py'}


def test_profile_fifo_rejects_without_a_blocking_stream_open(tmp_path, monkeypatch):
    path = tmp_path / 'profile-fifo'; os.mkfifo(path)
    def blocking_open_forbidden(*args, **kwargs):
        raise AssertionError('UNBOUNDED_PROFILE_OPEN')
    monkeypatch.setattr(Path, 'open', blocking_open_forbidden)
    with pytest.raises(AssertionError, match='ARTIFACT_CUSTODY'): regular(path)
