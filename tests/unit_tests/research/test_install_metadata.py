"""Controlled wheel representations; these checks are not clean-install proof."""
import base64
import csv
import hashlib
import io
import json
import stat
import warnings
import zipfile

import pytest

from scripts.research_compat_wheel import build_compatibility_wheel
from scripts.research_offline_assets import AssetError, audit_wheel, audit_native


def wheel(tmp_path, *, omit=(), corrupt=False, extra=False, duplicate=False, link=False, metadata_extra=b'', bin_link=False):
    root = 'workswarm-0.2.5b1.dist-info/'
    prefix = 'jiuwenswarm/channels/tui/frontend/'
    files = {root + 'METADATA': b'Metadata-Version: 2.1\nName: workswarm\nVersion: 0.2.5b1\nRequires-Dist: openjiuwen @ git+https://example.invalid/core.git@abc\n\n',
             root + 'WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
             root + 'entry_points.txt': b'[console_scripts]\njiuwenswarm = jiuwenswarm.channels.cli.main:main\n',
             prefix + 'dist/index.js': b'compiled output', prefix + 'package.json': b'{"type":"module"}',
             prefix + 'node_modules/.package-lock.json': b'{}',
             prefix + 'node_modules/@mariozechner/pi-tui/dist/index.js': b'dependency',
             prefix + 'node_modules/koffi/build/koffi/linux_x64/koffi.node': b'x64',
             prefix + 'node_modules/koffi/build/koffi/linux_arm64/koffi.node': b'arm64'}
    for name in omit:
        files.pop(prefix + name)
    if bin_link:
        files[prefix + 'node_modules/.bin/probe'] = b'dependency'
    files[root + 'METADATA'] = files[root + 'METADATA'].rstrip(b'\n') + b'\n' + metadata_extra + b'\n'
    output = io.StringIO(newline=''); rows = csv.writer(output)
    for name, raw in sorted(files.items()):
        rows.writerow([name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode(), len(raw)])
    rows.writerow([root + 'RECORD', '', '']); files[root + 'RECORD'] = output.getvalue().encode()
    if corrupt:
        files[prefix + 'dist/index.js'] += b'changed'
    if extra:
        files['unrecorded'] = b'extra'
    path = tmp_path / 'workswarm-0.2.5b1-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as z:
        for name, raw in files.items():
            item = zipfile.ZipInfo(name); item.external_attr = ((stat.S_IFLNK if link else stat.S_IFREG) | 0o644) << 16
            z.writestr(item, raw)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                z.writestr(root + 'METADATA', files[root + 'METADATA'])
    return path, files


def test_exact_native_inventory_and_generated_correspondence(tmp_path):
    path, files = wheel(tmp_path)
    generated = tmp_path / 'generated'; generated.mkdir()
    prefix = 'jiuwenswarm/channels/tui/frontend/'
    for name, raw in files.items():
        if name.startswith(prefix):
            p = generated / name[len(prefix):]; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    project = {'project': {'name': 'workswarm', 'version': '0.2.5.beta1',
               'dependencies': ['openjiuwen @ git+https://example.invalid/core.git@abc'],
               'scripts': {'jiuwenswarm': 'jiuwenswarm.channels.cli.main:main'}}}
    result = audit_native(path, project, generated_root=generated)
    assert result['generated_files'] == 6
    assert len(result['native_tui_binaries']) == 2
    assert result['metadata']['requires_dist'] == project['project']['dependencies']
    (generated / 'dist/index.js').write_bytes(b'foreign generated output')
    with pytest.raises(AssetError, match='GENERATED_BYTES'):
        audit_native(path, project, generated_root=generated)


@pytest.mark.parametrize('kwargs,reason', [({'corrupt': True}, 'RECORD_HASH'), ({'extra': True}, 'RECORD_CLOSURE'),
    ({'duplicate': True}, 'DUPLICATE'), ({'link': True}, 'LINK'),
    ({'omit': ['dist/index.js']}, 'TUI_ASSETS')])
def test_corrupt_missing_and_ambiguous_wheels_fail(tmp_path, kwargs, reason):
    path, _ = wheel(tmp_path, **kwargs)
    with pytest.raises(AssetError, match=reason):
        audit_native(path, {'project': {'name': 'workswarm', 'version': '0.2.5b1',
            'dependencies': ['openjiuwen @ git+https://example.invalid/core.git@abc'],
            'scripts': {'jiuwenswarm': 'jiuwenswarm.channels.cli.main:main'}}})


def test_wrong_version_and_dependency_rewrite_fail(tmp_path):
    path, _ = wheel(tmp_path)
    with pytest.raises(AssetError, match='VERSION'):
        audit_wheel(path, expected_name='workswarm', expected_version='9.0.0')
    with pytest.raises(AssetError, match='DEPENDENCIES'):
        audit_native(path, {'project': {'name': 'workswarm', 'version': '0.2.5b1',
            'dependencies': ['openjiuwen==0.1.18'], 'scripts': {}}})


def test_metadata_only_alias_has_exact_native_extras_and_record(tmp_path):
    result = build_compatibility_wheel(tmp_path, native_version='0.2.5b1', license_bytes=b'license')
    observed = audit_wheel(result['wheel'], expected_name='jiuwenswarm', expected_version='0.2.5b1')
    assert observed['metadata']['requires_dist'] == ['workswarm[codex,tui]==0.2.5b1']
    assert all('.dist-info/' in name for name in observed['members'])


def test_no_ambient_asset_fallback(tmp_path):
    path, _ = wheel(tmp_path)
    with pytest.raises(AssetError, match='GENERATED_ROOT'):
        audit_native(path, {'project': {'name': 'workswarm', 'version': '0.2.5b1',
            'dependencies': ['openjiuwen @ git+https://example.invalid/core.git@abc'],
            'scripts': {'jiuwenswarm': 'jiuwenswarm.channels.cli.main:main'}}}, generated_root=tmp_path / 'absent')


@pytest.mark.parametrize('extra,reason', [(b'Requires-Python: >=3.10\n', 'REQUIRES_PYTHON'),
    (b'Provides-Extra: codex\nRequires-Dist: foreign-provider; extra == "codex"\n', 'DEPENDENCIES')])
def test_python_and_selected_extra_metadata_cannot_drift(tmp_path, extra, reason):
    path, _ = wheel(tmp_path, metadata_extra=extra)
    project = {'project': {'name': 'workswarm', 'version': '0.2.5b1',
        'dependencies': ['openjiuwen @ git+https://example.invalid/core.git@abc'],
        'scripts': {'jiuwenswarm': 'jiuwenswarm.channels.cli.main:main'}}}
    with pytest.raises(AssetError, match=reason):
        audit_native(path, project)


def test_equivalent_specifier_order_and_beta_spelling_preserve_source():
    from scripts.research_offline_assets import _requirement, _metadata_requirement
    assert _requirement('Pkg[Codex,Tui]>=1.0,<2') == _requirement('pkg[tui,codex]<2, >=1.0')
    assert _requirement('workswarm-tui==0.2.5.beta1') == _requirement('workswarm_tui==0.2.5b1')
    assert _metadata_requirement('openjiuwen[codex]; extra == "codex"') == ('codex', 'openjiuwen[codex]')
    with pytest.raises(AssetError, match='MARKER'):
        _metadata_requirement('pkg; extra == "codex" or python_version < "3.12"')


def test_installer_git_config_is_complete_before_first_effect():
    from tests.integration.research.test_installation import git_environment
    for rewrites in ({}, {'https://example.invalid/core.git': 'file:///owned/core.git', 'https://example.invalid/protocol.git': 'file:///owned/protocol.git'}):
        value = git_environment({'HOME': '/owned'}, rewrites)
        assert int(value['GIT_CONFIG_COUNT']) == 1 + len(rewrites)
        assert all('GIT_CONFIG_KEY_' + str(i) in value and 'GIT_CONFIG_VALUE_' + str(i) in value for i in range(int(value['GIT_CONFIG_COUNT'])))
        assert value['GIT_CONFIG_KEY_0'] == 'credential.helper' and value['GIT_CONFIG_VALUE_0'] == ''


@pytest.mark.parametrize('requirements', ['hatchling>=1\n', 'hatchling==1\n', 'hatchling @ https://example.invalid/tool.whl\n'])
def test_installer_build_tools_require_exact_versions_and_hashes(requirements):
    from tests.integration.research.test_installation import build_tools
    with pytest.raises(AssertionError, match='BUILD_TOOL_REQUIREMENT'):
        build_tools(requirements)


def test_independent_build_tool_pins_do_not_require_runtime_lock_membership():
    from tests.integration.research.test_installation import build_tools
    digest = 'a' * 64
    assert build_tools('hatchling==1.2.3 \\\n  --hash=sha256:' + digest + '\n') == {'hatchling': ('1.2.3', {digest})}


def test_only_explicit_contained_npm_bin_links_may_be_flattened(tmp_path):
    path, files = wheel(tmp_path, bin_link=True)
    generated = tmp_path / 'generated'; generated.mkdir()
    prefix = 'jiuwenswarm/channels/tui/frontend/'
    for name, raw in files.items():
        if name.startswith(prefix):
            p = generated / name[len(prefix):]; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    p = generated / 'node_modules/.bin/probe'; p.unlink()
    p.symlink_to('../@mariozechner/pi-tui/dist/index.js')
    project = {'project': {'name': 'workswarm', 'version': '0.2.5b1',
        'dependencies': ['openjiuwen @ git+https://example.invalid/core.git@abc'],
        'scripts': {'jiuwenswarm': 'jiuwenswarm.channels.cli.main:main'}}}
    result = audit_native(path, project, generated_root=generated)
    assert result['resolved_npm_bin_links'] == [{'path': 'node_modules/.bin/probe',
        'target': '../@mariozechner/pi-tui/dist/index.js', 'sha256': hashlib.sha256(b'dependency').hexdigest()}]
    module = generated / 'node_modules/@mariozechner/pi-tui/dist/index.js'; module.unlink()
    module.symlink_to(generated / 'dist/index.js')
    with pytest.raises(AssetError, match='FILE_LINK'):
        audit_native(path, project, generated_root=generated)


def test_wheel_filename_must_agree_with_metadata_and_tags(tmp_path):
    path, _ = wheel(tmp_path)
    wrong = path.with_name('workswarm-9.0.0-py3-none-any.whl'); path.rename(wrong)
    with pytest.raises(AssetError, match='FILENAME'):
        audit_wheel(wrong, expected_name='workswarm')
