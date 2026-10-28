"""Disposable build-identity trees; no image build or operational qualification."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[3] / 'deploy' / 'm1' / 'rsi_build_identity.py'
SPEC = importlib.util.spec_from_file_location('controlled_rsi_build_identity', SOURCE)
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


def test_windows_context_modes_are_normalized_only_within_reviewed_overlays(installed):
    if os.name!='posix' or os.geteuid()!=0:return
    package=installed['package']
    selected=package/'research_rsi/worker.py';selected.chmod(0o777)
    outside=package/'research/core.py';outside.chmod(0o666)
    raw=selected.read_bytes()
    assert identity.normalize_overlay_permissions((package,))>0
    assert selected.read_bytes()==raw and selected.stat().st_mode&0o777==0o644
    assert selected.parent.stat().st_mode&0o777==0o755
    assert outside.stat().st_mode&0o777==0o666


def test_overlay_permission_normalization_rejects_links_before_any_change(installed):
    if os.name!='posix' or os.geteuid()!=0:return
    package=installed['package'];source=package/'research_rsi/worker.py';source.chmod(0o777)
    link=package/'research/contracts/foreign.py';link.symlink_to(package/'research/core.py')
    with pytest.raises(ValueError,match='LINK_REJECTED'):identity.normalize_overlay_permissions((package,))
    assert source.stat().st_mode&0o777==0o777


@pytest.fixture
def installed(tmp_path, monkeypatch):
    package = tmp_path / 'site-packages' / 'jiuwenswarm'
    tui = package.parent / 'jiuwenswarm_tui'
    def write(root, name, raw):
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        return path
    for name in ('__init__.py', 'research/core.py', 'channels/tui/frontend/bundle.js',
                 'research_rsi/worker.py', 'research_records/records.py',
                 'research_contracts/schemas/neutral.json', 'research/contracts/rsi_security.py'):
        write(package, name, ('original:' + name).encode())
    write(tui, '__init__.py', b'# independently installed TUI')
    write(tui, 'main.py', b'# fixed TUI source')
    lock = write(tmp_path, 'uv.lock', b'controlled frozen dependency lock')
    project = write(tmp_path, 'pyproject.toml', b'[project]\nname="controlled"\n')
    dependencies = [{'name': 'workswarm', 'version': '1.0'}, {'name': 'workswarm-tui', 'version': '1.0'}]
    monkeypatch.setattr(identity, '_dependencies', lambda: deepcopy(dependencies))
    tree = identity._inventory(package)
    base = dict(schema='ai4r-installed-build:2', **tree, dependencies=dependencies,
        components={'jiuwenswarm_tui': identity._inventory(tui)},
        uv_lock_sha256=identity._sha(lock.read_bytes()), pyproject_sha256=identity._sha(project.read_bytes()))
    base['build_id'] = identity._sha(identity._encoded(base))
    manifest = write(tmp_path, 'installed-build.json', json.dumps(base, indent=2).encode())
    yield dict(package=package, tui=tui, lock=lock, project=project, manifest=manifest, base=base,
        dependencies=dependencies, write=write,
        kwargs=dict(lock=lock, project=project, manifest=manifest, package_root=package))


@pytest.mark.parametrize('path', ['research_rsi/worker.py', 'research_records/records.py',
    'research_contracts/schemas/neutral.json', 'research/contracts/rsi_security.py'])
def test_refreshes_each_permitted_overlay_and_preserves_frozen_non_source_identity(installed, path):
    old = installed['base']; installed['write'](installed['package'], path, b'controlled derivative bytes')
    report = identity.refresh_manifest(**installed['kwargs'])
    current = json.loads(installed['manifest'].read_bytes())
    assert report['base_build_id'] == old['build_id'] and report['build_id'] != old['build_id']
    assert report['changed_paths'] == [path]
    for field in ('schema', 'dependencies', 'components', 'uv_lock_sha256', 'pyproject_sha256'):
        assert current[field] == old[field]
    assert current['files'] == identity._inventory(installed['package'])['files']
    assert current['build_id'] == identity._sha(identity._encoded({k: v for k, v in current.items() if k != 'build_id'}))
    repeated = identity.refresh_manifest(**installed['kwargs'])
    assert repeated['changed_paths'] == [] and repeated['build_id'] == current['build_id']


def test_permitted_file_addition_and_deletion_are_measured(installed):
    (installed['package'] / 'research_rsi' / 'worker.py').unlink()
    installed['write'](installed['package'], 'research/contracts/new_guard.py', b'new guard')
    report = identity.refresh_manifest(**installed['kwargs'])
    assert report['changed_paths'] == ['research/contracts/new_guard.py', 'research_rsi/worker.py']


@pytest.mark.parametrize('path', ['__init__.py', 'research/core.py', 'channels/tui/frontend/bundle.js',
    'research_rsi_other/escape.py', 'research/contracts_extra/escape.py', 'research/contract.py'])
def test_changes_outside_exact_four_prefixes_refuse_without_rewriting_manifest(installed, path):
    original = installed['manifest'].read_bytes()
    installed['write'](installed['package'], path, b'outside derivative scope')
    with pytest.raises(ValueError, match='OUTSIDE_RSI_PREFIXES'):
        identity.refresh_manifest(**installed['kwargs'])
    assert installed['manifest'].read_bytes() == original


def test_outside_file_deletion_is_not_silently_absent(installed):
    (installed['package'] / 'research' / 'core.py').unlink()
    with pytest.raises(ValueError, match='OUTSIDE_RSI_PREFIXES'):
        identity.refresh_manifest(**installed['kwargs'])


@pytest.mark.parametrize('input_name', ['lock', 'project'])
def test_current_repo_lock_and_project_must_match_inherited_inputs(installed, input_name):
    original = installed['manifest'].read_bytes()
    installed[input_name].write_bytes(b'changed current build input')
    with pytest.raises(ValueError, match='INHERITED_' + input_name.upper() + '_INPUT_CHANGED'):
        identity.refresh_manifest(**installed['kwargs'])
    assert installed['manifest'].read_bytes() == original


def test_changed_actual_dependencies_or_tui_cannot_be_recertified(installed, monkeypatch):
    original = installed['manifest'].read_bytes()
    changed = deepcopy(installed['dependencies']); changed[0]['version'] = '2.0'
    monkeypatch.setattr(identity, '_dependencies', lambda: changed)
    with pytest.raises(ValueError, match='DEPENDENCIES_CHANGED'):
        identity.refresh_manifest(**installed['kwargs'])
    monkeypatch.setattr(identity, '_dependencies', lambda: installed['dependencies'])
    (installed['tui'] / 'main.py').write_bytes(b'changed TUI')
    with pytest.raises(ValueError, match='TUI_CHANGED'):
        identity.refresh_manifest(**installed['kwargs'])
    assert installed['manifest'].read_bytes() == original


def test_base_manifest_self_hash_is_required_before_any_update(installed):
    base = deepcopy(installed['base']); base['files'][0]['sha256'] = 'a' * 64
    raw = json.dumps(base).encode(); installed['manifest'].write_bytes(raw)
    with pytest.raises(ValueError, match='BUILD_ID_CHANGED'):
        identity.refresh_manifest(**installed['kwargs'])
    assert installed['manifest'].read_bytes() == raw


def test_duplicate_or_unknown_manifest_fields_are_rejected(installed):
    raw = installed['manifest'].read_bytes()
    installed['manifest'].write_bytes(raw.replace(b'"schema":', b'"schema": "duplicate", "schema":', 1))
    with pytest.raises(ValueError, match='DUPLICATE_MANIFEST_FIELD'):
        identity.refresh_manifest(**installed['kwargs'])
    base = deepcopy(installed['base']); base['arbitrary_authority'] = True
    installed['manifest'].write_bytes(json.dumps(base).encode())
    with pytest.raises(ValueError, match='UNKNOWN_INHERITED_BUILD_MANIFEST'):
        identity.refresh_manifest(**installed['kwargs'])


def test_runtime_cache_files_do_not_replace_source_identity(installed):
    installed['write'](installed['package'], 'research/__pycache__/core.cpython-312.pyc', b'cache')
    installed['write'](installed['package'], 'research/core.pyc', b'cache')
    report = identity.refresh_manifest(**installed['kwargs'])
    assert report['changed_paths'] == [] and report['build_id'] == installed['base']['build_id']


def test_credentials_inside_allowed_prefix_are_still_refused(installed):
    installed['write'](installed['package'], 'research_rsi/auth.json', b'not real credentials')
    with pytest.raises(ValueError, match='CREDENTIAL_FILE_IN_IMAGE_PACKAGE'):
        identity.refresh_manifest(**installed['kwargs'])


def test_failed_atomic_replacement_leaves_original_and_cleans_pending_bytes(installed, monkeypatch):
    original = installed['manifest'].read_bytes()
    installed['write'](installed['package'], 'research_rsi/worker.py', b'changed')
    def fail(*_): raise OSError('controlled replacement failure')
    monkeypatch.setattr(identity.os, 'replace', fail)
    with pytest.raises(OSError, match='controlled'):
        identity.refresh_manifest(**installed['kwargs'])
    assert installed['manifest'].read_bytes() == original
    assert list(installed['manifest'].parent.glob('.rsi-build-*')) == []


def test_cli_uses_installed_distribution_roots_without_importing_application(installed, monkeypatch, capsys):
    roots = {'workswarm': installed['package'], 'workswarm-tui': installed['tui']}
    monkeypatch.setattr(identity.importlib.metadata, 'distribution',
        lambda name: SimpleNamespace(locate_file=lambda _: roots[name]))
    installed['write'](installed['package'], 'research/contracts/rsi_security.py', b'derivative guard')
    identity.main(['--lock', str(installed['lock']), '--project', str(installed['project']),
                   '--manifest', str(installed['manifest'])])
    report = json.loads(capsys.readouterr().out)
    assert report['changed_paths'] == ['research/contracts/rsi_security.py']


def test_actual_metadata_dependency_recipe_preserves_exact_identity_and_sorting(monkeypatch):
    distributions = [SimpleNamespace(metadata={'Name': 'Zulu'}, version='2.0'),
                     SimpleNamespace(metadata={'Name': 'alpha'}, version='1.0')]
    monkeypatch.setattr(identity.importlib.metadata, 'distributions', lambda: distributions)
    assert identity._dependencies() == [{'name': 'alpha', 'version': '1.0'}, {'name': 'Zulu', 'version': '2.0'}]


def _symlink(source, target):
    try: source.symlink_to(target)
    except (OSError, NotImplementedError): pytest.skip('Host cannot create actual symlinks; Linux boundary remains required')


def test_actual_links_are_inventoried_and_escape_or_outside_changes_rejected(installed):
    path = installed['package'] / 'research_rsi' / 'alias.py'
    _symlink(path, 'worker.py')
    report = identity.refresh_manifest(**installed['kwargs'])
    assert report['changed_paths'] == ['research_rsi/alias.py']
    current = json.loads(installed['manifest'].read_bytes())
    assert current['links'] == [{'path': 'research_rsi/alias.py', 'target': 'worker.py'}]
    path.unlink(); _symlink(path, '../../outside-package.txt')
    with pytest.raises(ValueError, match='LINK_ESCAPES_PACKAGE'):
        identity.refresh_manifest(**installed['kwargs'])


def test_outside_prefix_link_addition_cannot_be_recertified(installed):
    path = installed['package'] / 'research' / 'alias.py'
    _symlink(path, '../research_rsi/worker.py')
    with pytest.raises(ValueError, match='OUTSIDE_RSI_PREFIXES'):
        identity.refresh_manifest(**installed['kwargs'])
