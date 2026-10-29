"""Candidate identity covers bytes and excludes credential-bearing paths."""
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from scripts.research_candidate import DEFAULT_SCOPE, capture_candidate, verify_candidate


def test_changed_or_added_execution_input_changes_identity(tmp_path):
    code = tmp_path / "jiuwenswarm"
    code.mkdir()
    file = code / "component.py"
    file.write_bytes(b"value = 1\n")
    first = capture_candidate(tmp_path, paths=["jiuwenswarm"])
    assert verify_candidate(tmp_path, first) == []
    file.write_bytes(b"value = 2\n")
    assert capture_candidate(tmp_path, paths=["jiuwenswarm"])["candidate_id"] != first["candidate_id"]
    assert verify_candidate(tmp_path, first)
    file.write_bytes(b"value = 1\n")
    (code / "new.py").write_bytes(b"new input\n")
    assert verify_candidate(tmp_path, first)


def test_credentials_are_excluded_before_file_read(tmp_path, monkeypatch):
    package = tmp_path / "jiuwenswarm"
    package.mkdir()
    (package / "component.py").write_bytes(b"source\n")
    credential = package / "auth.json"
    credential.write_bytes(b"private value")
    original = Path.read_bytes
    def guarded(path):
        if path == credential:
            raise AssertionError("Credential must never be read or hashed")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded)
    manifest = capture_candidate(tmp_path, paths=["jiuwenswarm"])
    assert [item["path"] for item in manifest["files"]] == ["jiuwenswarm/component.py"]


def test_external_or_symlink_execution_inputs_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        capture_candidate(tmp_path, paths=["../outside"])


def test_empty_candidate_never_produces_identity(tmp_path):
    with pytest.raises(ValueError, match="EMPTY_EXECUTION_INPUTS"):
        capture_candidate(tmp_path, paths=["jiuwenswarm"])


def test_tracked_product_workspace_code_and_templates_are_captured_but_user_data_is_not(tmp_path,monkeypatch):
    assert shutil.which('git'), 'A local Git executable is required for candidate tracked-file identity'
    allowed = ['jiuwenswarm/channels/web/frontend/src/features/workspace/localFilePicker.ts',
               'jiuwenswarm/resources/agent/workspace/AGENT_EN.md']
    forbidden = ['jiuwenswarm/resources/agent/workspace/untracked-user-note.md',
                 'jiuwenswarm/resources/agent/workspace/auth.json',
                 'jiuwenswarm/resources/agent/workspace/private/protected.txt',
                 'jiuwenswarm/user/workspace/AGENT_EN.md',
                 'jiuwenswarm/workspace/data.txt',
                 'jiuwenswarm/resources/agent/workspace/Auth.Json',
                 'jiuwenswarm/user/Workspace/data.txt']
    for name in [*allowed,*forbidden]:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'controlled fixture bytes\n')
    subprocess.run(['git','init','-q'],cwd=tmp_path,check=True,capture_output=True)
    subprocess.run(['git','add','--',*allowed,forbidden[1],forbidden[2],forbidden[3],forbidden[5]],cwd=tmp_path,check=True,capture_output=True)
    original=Path.read_bytes
    def guarded(path):
        if path.relative_to(tmp_path).as_posix() in forbidden:
            raise AssertionError('User/credential/private bytes must not be read')
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',guarded)
    snapshot=tmp_path/'candidate.zip'
    manifest=capture_candidate(tmp_path,paths=['jiuwenswarm'],snapshot=snapshot)
    assert {item['path'] for item in manifest['files']}==set(allowed)
    with zipfile.ZipFile(snapshot) as archive:
        assert set(archive.namelist())==set(allowed)
        assert archive.read(allowed[1])==b'controlled fixture bytes\n'
    assert verify_candidate(tmp_path,manifest)==[]
    (tmp_path/allowed[0]).write_bytes(b'changed native picker\n')
    assert verify_candidate(tmp_path,manifest)==[allowed[0]]


@pytest.mark.parametrize('kind',['file','directory','dangling'])
def test_symlink_and_ancestor_alias_never_become_execution_input(tmp_path,kind):
    root=tmp_path/'jiuwenswarm';root.mkdir()
    original=root/'original';original.mkdir();(original/'source.py').write_bytes(b'fixture\n')
    if kind=='file': (root/'alias.py').symlink_to(original/'source.py');scope=['jiuwenswarm']
    elif kind=='directory': (root/'alias').symlink_to(original,target_is_directory=True);scope=['jiuwenswarm/alias/source.py']
    else: (root/'missing.py').symlink_to(root/'nonexistent.py');scope=['jiuwenswarm']
    with pytest.raises(ValueError,match='SYMLINK'):
        capture_candidate(tmp_path,paths=scope)


def test_missing_git_inventory_cannot_silently_omit_shipped_workspace_code(tmp_path):
    path=tmp_path/'jiuwenswarm/channels/web/frontend/src/features/workspace/picker.ts'
    path.parent.mkdir(parents=True);path.write_bytes(b'controlled source\n')
    with pytest.raises(ValueError,match='TRACKED_PRODUCT_INVENTORY_UNAVAILABLE'):
        capture_candidate(tmp_path,paths=['jiuwenswarm'])


def test_default_public_build_metadata_and_exact_tracked_environment_template(tmp_path, monkeypatch):
    allowed = ['jiuwenbox/pyproject.toml', 'jiuwenbox/README.md', 'jiuwenbox/uv.lock',
               'jiuwenbox/src/jiuwenbox/__init__.py', 'LICENSE', 'OPEN_SOURCE_SOFTWARE_NOTICE.md',
               'jiuwenswarm/resources/.env.template']
    forbidden = ['jiuwenswarm/resources/.env', 'jiuwenswarm/resources/.env.local',
                 'jiuwenswarm/resources/other/.env.template', 'jiuwenswarm/user/.env.template',
                 'jiuwenswarm/resources/alternate/.ENV.Template', 'jiuwenbox/.env.template',
                 'jiuwenswarm/resources/auth.json', 'jiuwenswarm/resources/private/.env.template']
    for name in [*allowed, *forbidden]:
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'public controlled fixture\n' if name in allowed else b'private excluded fixture\n')
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'add', '--', *allowed, *forbidden], cwd=tmp_path, check=True, capture_output=True)
    original = Path.read_bytes
    def guarded(path):
        if path.relative_to(tmp_path).as_posix() in forbidden:
            raise AssertionError('Excluded environment/credential bytes must never be read')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    result = capture_candidate(tmp_path)
    assert result['scope'] == list(DEFAULT_SCOPE)
    assert {row['path'] for row in result['files']} == set(allowed)
    template = tmp_path / allowed[-1]
    template.write_bytes(b'changed public template\n')
    assert verify_candidate(tmp_path, result) == [allowed[-1]]


def test_reserved_environment_template_must_be_tracked_and_not_an_alias(tmp_path, monkeypatch):
    path = tmp_path / 'jiuwenswarm/resources/.env.template'
    path.parent.mkdir(parents=True); path.write_bytes(b'untracked file is not public authority')
    (tmp_path / 'LICENSE').write_bytes(b'controlled public license')
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True, capture_output=True)
    original = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda candidate: (_ for _ in ()).throw(AssertionError('untracked template read'))
                        if candidate == path else original(candidate))
    assert [row['path'] for row in capture_candidate(tmp_path)['files']] == ['LICENSE']
    path.unlink(); path.symlink_to(tmp_path / 'missing-template')
    subprocess.run(['git', 'add', '--', str(path.relative_to(tmp_path))], cwd=tmp_path, check=True, capture_output=True)
    with pytest.raises(ValueError, match='SYMLINK'):
        capture_candidate(tmp_path)
