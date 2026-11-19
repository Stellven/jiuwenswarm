"""Real local Git/files/CC transport; no shell agent, build, remote or GPU work."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.source_workbench import MAX_FILE_BYTES
from jiuwenswarm.factory.store import ScopeDenied, Store

ROOT = Path(__file__).resolve().parents[2]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


@pytest.fixture
def owned(tmp_path):
    with Store(tmp_path / 'factory') as store:
        root = store.home / 'agent-workspace' / 'engine'
        root.mkdir(parents=True)
        git(root, 'init', '-q')
        git(root, 'config', 'user.name', 'Test')
        git(root, 'config', 'user.email', 'test@localhost')
        (root / 'CMakeLists.txt').write_text('project(original)\n')
        git(root, 'add', 'CMakeLists.txt')
        git(root, 'commit', '-qm', 'initial')
        store.create_task(dict(task_id='task', objective='Construct source', source={'subpath': 'engine'},
            allowed_effects=['process.exec', 'workspace.write'], constraints={'local_commits': True}))
        yield store, root


def call(store, operation, **inputs):
    return dispatch(store.scoped('task'), 'task', 'source_workbench.' + operation,
                    {'inputs': inputs})['result']


def test_read_write_commit_preserves_other_changes_and_refuses_stale_inputs(owned):
    store, root = owned
    inspected = call(store, 'inspect')
    before = call(store, 'read', path='CMakeLists.txt')
    assert before['text'] == 'project(original)\n'
    changed = call(store, 'write', path='CMakeLists.txt', text='project(candidate)\n', expected_sha256=before['sha256'])
    with pytest.raises(ValueError, match='Source changed'):
        call(store, 'write', path='CMakeLists.txt', text='stale', expected_sha256=before['sha256'])
    call(store, 'write', path='tools/oracle.txt', text='keep unstaged\n', expected_sha256=None)
    committed = call(store, 'localcommit', paths=['CMakeLists.txt'], message='candidate source', expected_head=inspected['head'])
    assert committed['commit'] == git(root, 'rev-parse', 'HEAD')
    assert committed['parent'] == inspected['head'] and committed['pushed'] is False
    assert git(root, 'show', 'HEAD:CMakeLists.txt') == 'project(candidate)'
    assert 'tools/' in committed['status']
    assert changed['sha256'] == hashlib.sha256(b'project(candidate)\n').hexdigest()
    with pytest.raises(ValueError, match='HEAD changed'):
        call(store, 'localcommit', paths=['tools/oracle.txt'], message='stale head', expected_head=inspected['head'])


@pytest.mark.parametrize('path', ['../outside', '/tmp/outside', '.git/config', 'a/../b', 'a/.git/config', 'a\\b'])
def test_metadata_and_path_escape_are_refused(owned, path):
    store, _ = owned
    with pytest.raises((ScopeDenied, ValueError)):
        call(store, 'write', path=path, text='escape', expected_sha256=None)


def test_symlink_hardlink_and_oversized_files_are_refused(owned, tmp_path):
    store, root = owned
    outside = tmp_path / 'outside'
    outside.mkdir()
    target = outside / 'secret'
    target.write_text('unchanged')
    (root / 'link').symlink_to(outside, target_is_directory=True)
    (root / 'file-link').symlink_to(target)
    os.link(target, root / 'hardlink')
    for path in ['link/secret', 'file-link', 'hardlink']:
        with pytest.raises((ScopeDenied, OSError)):
            call(store, 'write', path=path, text='escape', expected_sha256=None)
    assert target.read_text() == 'unchanged'
    with pytest.raises(ValueError, match='1 MiB'):
        call(store, 'write', path='large', text='x' * (MAX_FILE_BYTES + 1), expected_sha256=None)
    (root / 'large').write_bytes(b'x' * (MAX_FILE_BYTES + 1))
    with pytest.raises(ScopeDenied):
        call(store, 'read', path='large')


def test_commit_does_not_execute_filters_hooks_or_signing(owned, tmp_path):
    store, root = owned
    marker = tmp_path / 'executed'
    hook = root / '.git/hooks/pre-commit'
    hook.write_text('#!/bin/sh\ntouch ' + str(marker) + '\nexit 1\n')
    hook.chmod(0o755)
    git(root, 'config', 'filter.evil.clean', 'touch ' + str(marker))
    git(root, 'config', 'filter.evil.process', 'touch ' + str(marker))
    git(root, 'config', 'filter.evil.required', 'true')
    git(root, 'config', 'commit.gpgsign', 'true')
    git(root, 'config', 'gpg.program', str(marker))
    (root / '.gitattributes').write_text('*.txt filter=evil\n')
    before = call(store, 'inspect')
    call(store, 'write', path='new.txt', text='raw source\n', expected_sha256=None)
    result = call(store, 'localcommit', paths=['new.txt'], message='safe plumbing', expected_head=before['head'])
    assert result['commit'] != before['head']
    assert not marker.exists()
    assert git(root, 'show', 'HEAD:new.txt') == 'raw source'


def test_authority_and_foreign_task_scope_are_required(owned):
    store, root = owned
    store.create_task(dict(task_id='foreign', objective='foreign', source={'subpath':'engine'},
        allowed_effects=['workspace.write'], constraints={'local_commits':True}))
    with pytest.raises(ScopeDenied):
        dispatch(store.scoped('task', ['foreign']), 'foreign', 'source_workbench.inspect', {'inputs':{}})
    for task_id, effects, constraints in [('no-write', [], {'local_commits':True}),
                                           ('no-commit', ['workspace.write'], {})]:
        store.create_task(dict(task_id=task_id, objective='unauthorized', source={'subpath':'engine'},
            allowed_effects=effects, constraints=constraints))
        with pytest.raises(ScopeDenied):
            dispatch(store.scoped(task_id), task_id, 'source_workbench.inspect', {'inputs':{}})


def test_existing_staged_changes_are_not_hidden_in_commit(owned):
    store, root = owned
    (root / 'staged').write_text('retain')
    git(root, 'add', 'staged')
    head = git(root, 'rev-parse', 'HEAD')
    with pytest.raises(ScopeDenied, match='staged changes'):
        call(store, 'localcommit', paths=['CMakeLists.txt'], message='do not hide staged work', expected_head=head)
    assert git(root, 'rev-parse', 'HEAD') == head
    assert git(root, 'diff', '--cached', '--name-only') == 'staged'


def test_bounded_file_listing_and_read_pages(owned):
    store, _ = owned
    call(store, 'write', path='nested/probe.txt', text='abcdef', expected_sha256=None)
    page = call(store, 'read', path='nested/probe.txt', offset=2, limit=2)
    assert page['text'] == 'cd' and page['next_offset'] == 4
    listed = call(store, 'inspect', prefix='nested/', limit=1)
    assert listed['files'] == ['nested/probe.txt']
    with pytest.raises(ValueError):
        call(store, 'read', path='nested/probe.txt', limit=MAX_FILE_BYTES)


def test_actual_native_cc_transport_without_agent_shell(owned, tmp_path, monkeypatch):
    from jiuwenswarm.ccv2.ccv2 import Host
    store, root = owned
    monkeypatch.setenv('FACTORY_HOME', str(store.home))
    monkeypatch.setenv('FACTORY_TASK_ID', 'task')
    monkeypatch.setenv('FACTORY_PYTHON', sys.executable)
    monkeypatch.setenv('PYTHONPATH', str(ROOT))
    host = Host(tmp_path / 'ccstore', python=sys.executable,
                session_grants=['process.exec', 'workspace.write'])
    release = host.prepare(ROOT / 'jiuwenswarm/factory/ccs/source_workbench')
    inspected = host.call(release, 'inspect', {})
    assert inspected['state'] == 'succeeded', inspected
    wrote = host.call(release, 'write', {'path':'probe.txt', 'text':'candidate\n', 'expected_sha256':None})
    assert wrote['state'] == 'succeeded', wrote
    edited = host.call(release, 'edit', {'path':'probe.txt',
        'replacements':[{'old':'candidate', 'new':'edited candidate'}],
        'expected_sha256':wrote['outputs']['result']['sha256'],
        'result_sha256':hashlib.sha256(b'edited candidate\n').hexdigest()})
    assert edited['state'] == 'succeeded', edited
    committed = host.call(release, 'localcommit', {'paths':['probe.txt'], 'message':'native construction',
        'expected_head':inspected['outputs']['result']['head']})
    assert committed['state'] == 'succeeded', committed
    assert git(root, 'show', 'HEAD:probe.txt') == 'edited candidate'


def test_exact_edits_validate_entire_result_before_write(owned):
    store, root = owned
    before = call(store, 'read', path='CMakeLists.txt')
    args = dict(path='CMakeLists.txt', expected_sha256=before['sha256'],
                result_sha256=hashlib.sha256(b'project(candidate)\n').hexdigest())
    for replacements, message in [([{'old': 'missing', 'new': 'x'}], 'exactly once'),
            ([{'old': 'original', 'new': 'wrong'}], 'result sha256'),
            ([{'old': 'original', 'new': 'candidate'}, {'old': 'missing', 'new': 'x'}], 'exactly once'),
            ([{'old': '', 'new': 'x'}], 'nonempty')]:
        with pytest.raises(ValueError, match=message):
            call(store, 'edit', replacements=replacements, **args)
        assert (root / 'CMakeLists.txt').read_bytes() == b'project(original)\n'
    result = call(store, 'edit', replacements=[{'old': 'original', 'new': 'candidate'}], **args)
    assert result['sha256'] == args['result_sha256']
    with pytest.raises(ValueError, match='Source changed'):
        call(store, 'edit', replacements=[{'old': 'original', 'new': 'candidate'}], **args)


def test_exact_edit_rejects_ambiguous_match_and_symlink(owned):
    store, root = owned
    before = call(store, 'read', path='CMakeLists.txt')
    with pytest.raises(ValueError, match='exactly once'):
        call(store, 'edit', path='CMakeLists.txt', expected_sha256=before['sha256'],
             result_sha256='0'*64, replacements=[{'old': 'r', 'new': 'x'}])
    (root / 'linked').symlink_to('CMakeLists.txt')
    with pytest.raises(OSError):
        call(store, 'edit', path='linked', expected_sha256=before['sha256'],
             result_sha256='0'*64, replacements=[{'old': 'original', 'new': 'x'}])
