"""Independent closure and no-effect guards for I029's authoring producer."""
import hashlib
import json
import signal
from urllib.parse import urlencode
from pathlib import Path

import pytest

from scripts.research_offline import (
    OfflineError, parse_build_requirements, selected_packages,
    validate_dynamic_requirements, verified_input, required_native_members,
    validate_original_vcs, VCS, add_bundle, Commands, bind_delivered_members, verify_materialized,
    validate_target_tags, observe_pip_frontend, safe_environment, frontend_source_files,
)


ENV = {'python_version': '3.12', 'python_full_version': '3.12.15',
       'sys_platform': 'linux', 'os_name': 'posix', 'platform_machine': 'x86_64',
       'platform_python_implementation': 'CPython', 'implementation_name': 'cpython',
       'implementation_version': '3.12.15'}


def package(name, dependencies=(), **extra):
    return {'name': name, 'version': '1.0', 'source': {'registry': 'https://pypi.org/simple'},
            'dependencies': list(dependencies), **extra}


def test_selected_closure_propagates_extras_and_actual_markers_only():
    lock = {'package': [
        package('workswarm', [{'name': 'ordinary'}, {'name': 'windows', 'marker': "sys_platform == 'win32'"}],
                **{'optional-dependencies': {'codex': [{'name': 'engine', 'extra': ['codex']}],
                                            'tui': [{'name': 'workswarm-tui'}],
                                            'test': [{'name': 'pytest'}]}}),
        package('ordinary'), package('windows'), package('pytest'), package('workswarm-tui'),
        package('engine', **{'optional-dependencies': {'codex': [{'name': 'native-codex'}],
                                                     'other': [{'name': 'unselected'}]}}),
        package('native-codex'), package('unselected'),
    ]}
    result = selected_packages(lock, environment=ENV)
    assert set(result) == {'workswarm', 'ordinary', 'engine', 'native-codex', 'workswarm-tui'}


def test_locked_fork_selects_version_by_resolution_marker():
    lock = {'package': [package('workswarm', [{'name': 'fork'}],
              **{'optional-dependencies': {'codex': [], 'tui': []}}),
        package('fork', **{'resolution-markers': ["python_full_version < '3.12'"]}),
        {**package('fork', **{'resolution-markers': ["python_full_version >= '3.12'"]}), 'version': '2.0'},
    ]}
    assert selected_packages(lock, environment=ENV)['fork']['version'] == '2.0'


@pytest.mark.parametrize('dependencies,additional,reason', [
    ([{'name': 'absent'}], [], 'LOCK_DEPENDENCY_UNRESOLVED'),
    ([{'name': 'ambiguous'}], [package('ambiguous'), {**package('ambiguous'), 'version': '2'}], 'LOCK_DEPENDENCY_AMBIGUOUS'),
    ([{'name': 'child', 'extra': ['undeclared']}], [package('child')], 'LOCK_EXTRA_UNRESOLVED'),
])
def test_incomplete_or_ambiguous_lock_is_not_silently_narrowed(dependencies, additional, reason):
    lock = {'package': [package('workswarm', dependencies,
        **{'optional-dependencies': {'codex': [], 'tui': []}}), *additional]}
    with pytest.raises(OfflineError, match=reason):
        selected_packages(lock, environment=ENV)


def test_source_disambiguation_is_part_of_locked_identity():
    source = {'git': 'https://example.invalid/original.git#' + 'a' * 40}
    lock = {'package': [package('workswarm', [{'name': 'child', 'version': '1.0', 'source': source}],
                 **{'optional-dependencies': {'codex': [], 'tui': []}}),
        package('child'), {**package('child'), 'source': source}]}
    assert selected_packages(lock, environment=ENV)['child']['source'] == source


def test_build_requirement_lock_and_dynamic_requirements_are_separate():
    digest = 'a' * 64
    pins = parse_build_requirements('wheel==0.48.0 --hash=sha256:' + digest + '\n')
    assert pins == {'wheel': ('0.48.0', {digest})}
    validate_dynamic_requirements(['wheel>=0.40'], pins, ENV)
    with pytest.raises(OfflineError, match='UNFROZEN_BUILD_REQUIREMENT'):
        validate_dynamic_requirements(['packaging>=20'], pins, ENV)
    with pytest.raises(OfflineError, match='BUILD_REQUIREMENT_VERSION'):
        validate_dynamic_requirements(['wheel<0.40'], pins, ENV)
    with pytest.raises(OfflineError, match='BUILD_REQUIREMENT_AUTHORITY'):
        validate_dynamic_requirements(['wheel @ https://example.invalid/foreign.whl'], pins, ENV)
    with pytest.raises(OfflineError, match='BUILD_REQUIREMENT_AUTHORITY'):
        validate_dynamic_requirements(['wheel[extra]'], pins, ENV)


@pytest.mark.parametrize('text', ['wheel>=1', 'wheel==1',
    'wheel @ https://example.invalid/a.whl', 'wheel==1 --hash=sha256:' + 'a' * 63,
    'wheel==1 --hash=sha256:' + 'a' * 64 + '\nwheel==1 --hash=sha256:' + 'b' * 64])
def test_build_tools_require_exact_unique_hashed_inputs(text):
    with pytest.raises(OfflineError, match='BUILD_TOOL_REQUIREMENT'):
        parse_build_requirements(text)


def test_input_hash_and_canonical_path_verified_before_copy(tmp_path):
    data = b'original bytes'; (tmp_path / 'input.whl').write_bytes(data)
    row = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    assert verified_input(tmp_path, 'input.whl', row) == data
    with pytest.raises(OfflineError, match='INPUT_HASH_OR_SIZE'):
        verified_input(tmp_path, 'input.whl', {**row, 'sha256': '0' * 64})
    for name in ('../input.whl', '/input.whl', 'a/../input.whl', 'a\\input.whl'):
        with pytest.raises(OfflineError, match='INPUT_PATH'):
            verified_input(tmp_path, name, row)


def test_alias_input_cannot_be_used_as_original_artifact(tmp_path):
    target = tmp_path / 'original.whl'; target.write_bytes(b'original')
    alias = tmp_path / 'alias.whl'; alias.symlink_to(target)
    with pytest.raises(OfflineError, match='INPUT_CUSTODY'):
        verified_input(tmp_path, 'alias.whl', {'bytes': 8, 'sha256': hashlib.sha256(b'original').hexdigest()})


def test_native_source_closure_honors_packages_and_explicit_resource_exclusions():
    source = {'jiuwenswarm/__init__.py', 'jiuwenswarm/research/__init__.py',
              'jiuwenswarm/research/runner.py', 'jiuwenswarm/tests/unpackaged_test.py',
              'jiuwenswarm/resources/visible.json', 'jiuwenswarm/resources/excluded/private.py'}
    project = {'tool': {'setuptools': {'package-data': {'jiuwenswarm': ['resources/*', 'resources/**/*']},
                                      'exclude-package-data': {'jiuwenswarm': ['resources/excluded/*']}}}}
    assert required_native_members(source, project) == {'jiuwenswarm/__init__.py',
        'jiuwenswarm/research/__init__.py', 'jiuwenswarm/research/runner.py', 'jiuwenswarm/resources/visible.json'}


@pytest.mark.parametrize('changed', ['unknown', 'duplicate', 'blank'])
def test_vcs_url_cannot_gain_transport_or_duplicate_query_authority(changed):
    locked = {}
    for name, value in VCS.items():
        query = {'rev': value['commit'] if name == 'openjiuwen' else 'feature/intelliRouter'}
        if value['subdirectory']:
            query['subdirectory'] = value['subdirectory']
        locked[name] = {'source': {'git': value['url'] + '?' + urlencode(query) + '#' + value['commit']}}
    validate_original_vcs(locked)
    url, fragment = locked['openjiuwen']['source']['git'].split('#')
    extra = {'unknown': '&transport=external', 'duplicate': '&rev=' + VCS['openjiuwen']['commit'], 'blank': '&unknown='}[changed]
    locked['openjiuwen']['source']['git'] = url + extra + '#' + fragment
    with pytest.raises(OfflineError, match='VCS_SOURCE_AUTHORITY'):
        validate_original_vcs(locked)


def test_same_basename_source_bundle_cannot_be_silently_overwritten():
    bundles = {}
    add_bundle(bundles, 'first/agent-core.bundle')
    with pytest.raises(OfflineError, match='DUPLICATE_BUNDLE'):
        add_bundle(bundles, 'extra/agent-core.bundle')
    assert bundles == {'agent-core.bundle': 'first/agent-core.bundle'}


def test_interrupted_authoring_effect_is_killed_and_never_reported_completed(tmp_path, monkeypatch):
    class Started:
        pid = 43210
        count = 0
        def communicate(self, timeout):
            self.count += 1
            if self.count == 1:
                raise KeyboardInterrupt()
            return b'partial original output', b'partial original error'
        def poll(self):
            return -9
    killed = []
    monkeypatch.setattr('scripts.research_offline.subprocess.Popen', lambda *a, **kw: Started())
    monkeypatch.setattr('scripts.research_offline.os.killpg', lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(OfflineError, match='INTERRUPTED_OUTCOME_UNKNOWN'):
        Commands(tmp_path, {}).run(['fixed-tool'], cwd=tmp_path)
    assert killed == [(43210, signal.SIGKILL)]
    record = json.loads((tmp_path / '001.json').read_bytes())
    assert record['outcome'] == 'OUTCOME_UNKNOWN' and record['parent_reaped']
    assert (tmp_path / '001.stdout').read_bytes() == b'partial original output'


@pytest.mark.parametrize('foreign', ['jiuwenswarm/unpinned.py', 'jiuwenswarm/unpinned.json', 'foreign.pth'])
def test_native_wheel_and_matching_asset_report_cannot_inject_unpinned_code(foreign):
    pin = {'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}
    source = {'jiuwenswarm/__init__.py': pin}
    members = {'jiuwenswarm/__init__.py': pin, foreign: pin}
    installed = {'files': [{'path': key[len('jiuwenswarm/'):], **value}
                            for key, value in members.items() if key.startswith('jiuwenswarm/')]}
    with pytest.raises(OfflineError, match='UNPINNED_DELIVERED_MEMBER'):
        bind_delivered_members('workswarm', {'metadata': {'name': 'workswarm', 'version': '1'},
            'members': members}, source, {}, installed)


def test_generated_assets_must_match_the_frozen_installed_build():
    source_pin = {'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}
    js_pin = {'bytes': 2, 'sha256': hashlib.sha256(b'js').hexdigest()}
    source = {'jiuwenswarm/__init__.py': source_pin}
    members = {'jiuwenswarm/__init__.py': source_pin,
               'jiuwenswarm/channels/tui/frontend/dist/index.js': js_pin}
    installed = {'files': [{'path': key[len('jiuwenswarm/'):], **value} for key, value in members.items()]}
    report = {'metadata': {'name': 'workswarm', 'version': '1'}, 'members': members}
    bind_delivered_members('workswarm', report, source, {}, installed)
    installed['files'][1]['sha256'] = '0' * 64
    with pytest.raises(OfflineError, match='INSTALLED_MEMBER_CLOSURE'):
        bind_delivered_members('workswarm', report, source, {}, installed)


def test_backend_cannot_change_or_add_artifacts_before_profile_publication(tmp_path):
    (tmp_path / 'original').write_bytes(b'original')
    files = {'original': {'bytes': 8, 'sha256': hashlib.sha256(b'original').hexdigest()}}
    verify_materialized(tmp_path, files)
    (tmp_path / 'extra').write_bytes(b'extra')
    with pytest.raises(OfflineError, match='MATERIALIZED_MEMBER_CLOSURE'):
        verify_materialized(tmp_path, files)
    (tmp_path / 'extra').unlink()
    (tmp_path / 'original').write_bytes(b'changed!')
    with pytest.raises(OfflineError, match='INPUT_HASH_OR_SIZE'):
        verify_materialized(tmp_path, files)


def test_broad_original_metadata_does_not_widen_a_platform_wheel_filename():
    original = {'filename_tags': ['py3-none-manylinux1_x86_64'], 'wheel_tags': ['py3-none-any'],
                'tag_consistency': 'mismatch', 'metadata': {'requires_python': '>=3.9'}}
    validate_target_tags(original, {'py3-none-any', 'py3-none-manylinux1_x86_64'}, '3.12.15')
    assert original['tag_consistency'] == 'mismatch'
    with pytest.raises(OfflineError, match='INCOMPATIBLE_WHEEL'):
        validate_target_tags(original, {'py3-none-any', 'py3-none-manylinux1_aarch64'}, '3.12.15')


def test_supported_filename_cannot_override_incompatible_original_metadata_or_python():
    report = {'filename_tags': ['py3-none-any'], 'wheel_tags': ['cp311-cp311-win_amd64'],
              'metadata': {'requires_python': '>=3.13'}}
    with pytest.raises(OfflineError, match='INCOMPATIBLE_WHEEL'):
        validate_target_tags(report, {'py3-none-any'}, '3.12.15')
    report['wheel_tags'] = ['py3-none-any']
    with pytest.raises(OfflineError, match='INCOMPATIBLE_WHEEL'):
        validate_target_tags(report, {'py3-none-any'}, '3.12.15')


def test_actual_immutable_base_frontend_is_observed_outside_the_application_venv(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    observation = observe_pip_frontend(Commands(tmp_path, safe_environment(home, tmp_path)), tmp_path)
    assert observation['version']
    assert Path(observation['python_file']['path']).is_file()
    names = [row['path'] for row in observation['files']]
    assert any('/pip/_internal/' in name for name in names)
    assert any('/pip/_vendor/' in name for name in names)
    assert all(row['sha256'] == hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()
               for row in observation['files'])


def test_a_missing_authoring_tool_retains_the_attempt_without_claiming_a_child(tmp_path, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError('missing-fixed-tool')
    monkeypatch.setattr('scripts.research_offline.subprocess.Popen', missing)
    with pytest.raises(OfflineError, match='AUTHORING_EFFECT_NOT_STARTED'):
        Commands(tmp_path, {}).run(['missing-fixed-tool'], cwd=tmp_path)
    record = json.loads((tmp_path / '001.json').read_bytes())
    assert record['argv'] == ['missing-fixed-tool']
    assert record['outcome'] == 'NOT_STARTED' and record['child_started'] is False
    assert record['returncode'] is None
    assert (tmp_path / '001.stdout').read_bytes() == b''
    assert b'missing-fixed-tool' in (tmp_path / '001.stderr').read_bytes()


def test_a_vendor_directory_alias_cannot_hide_missing_frontend_code(tmp_path):
    root = tmp_path / 'pip'
    root.mkdir()
    for name in ('__init__.py', '__main__.py', '__pip-runner__.py'):
        (root / name).write_text('')
    external = tmp_path / 'external-vendor'
    external.mkdir()
    (external / 'hidden.py').write_text('unclosed source')
    (root / '_vendor').symlink_to(external, target_is_directory=True)
    with pytest.raises(OfflineError, match='PIP_FRONTEND_ALIAS_OR_SPECIAL'):
        frontend_source_files(root)
