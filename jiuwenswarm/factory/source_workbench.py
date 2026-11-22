"""Bounded source construction in the current task's isolated Git checkout."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile
import uuid

from .store import ScopeDenied

MAX_FILE_BYTES = 1024 * 1024
MAX_PATHS = 64


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or set(required) - value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError('Invalid or missing source workbench fields')


def _parts(value):
    if not isinstance(value, str) or not value or '\\' in value or '\0' in value or len(value) > 1024:
        raise ValueError('A bounded relative source path is required')
    path = PurePosixPath(value)
    parts = value.split('/')
    if path.is_absolute() or any(p in {'', '.', '..'} or p.lower() == '.git' or p.startswith('-') for p in parts):
        raise ScopeDenied('Source path must stay outside Git metadata and inside the checkout')
    return parts


class Workbench:
    def __init__(self, store, task_id):
        if hasattr(store, '_check'):
            store._check(task_id, write=True)
        self.store = getattr(store, '_store', store)
        self.task_id = task_id
        task = store.get_task(task_id)
        if task.get('constraints', {}).get('local_commits') is not True or 'workspace.write' not in task.get('allowed_effects', []):
            raise ScopeDenied('Source construction requires local_commits and workspace.write authority')
        parts = _parts(task.get('source', {}).get('subpath'))
        base = self.store.home / 'agent-workspace'
        self.root = base.joinpath(*parts)
        # Source metadata must be an isolated clone, not a linked external worktree.
        for path in [base, *[base.joinpath(*parts[:i]) for i in range(1, len(parts) + 1)], self.root / '.git']:
            if path.is_symlink() or not path.is_dir():
                raise ScopeDenied('An isolated checkout without symlink directories is required')
        if self.git('rev-parse', '--show-toplevel').strip() != str(self.root.resolve()):
            raise ScopeDenied('Task source must identify the Git checkout root')
        if Path(self.git('rev-parse', '--absolute-git-dir').strip()).resolve() != (self.root / '.git').resolve():
            raise ScopeDenied('Git metadata must belong to the isolated checkout')

    def git(self, *args, data=None, index=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT='0', GIT_PAGER='cat',
                   GIT_AUTHOR_NAME='Factory source workbench', GIT_AUTHOR_EMAIL='factory@localhost',
                   GIT_COMMITTER_NAME='Factory source workbench', GIT_COMMITTER_EMAIL='factory@localhost')
        if index:
            env['GIT_INDEX_FILE'] = str(index)
        command = ['git', '--no-pager', '-c', 'core.hooksPath=/dev/null',
            '-c', 'core.fsmonitor=false', '-c', 'commit.gpgsign=false',
            '-c', 'core.attributesFile=/dev/null', '-C', str(self.root)]
        configured = subprocess.run([*command, 'config', '--includes', '--null', '--get-regexp',
            r'^filter\..*\.(clean|smudge|process|required)$'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, timeout=10)
        if configured.returncode not in (0, 1) or len(configured.stdout) > MAX_FILE_BYTES:
            raise ValueError('Cannot establish bounded Git filter configuration')
        filters = {entry.split(b'\n', 1)[0].decode().rsplit('.', 1)[0]
                   for entry in configured.stdout.split(b'\0') if entry}
        for name in sorted(filters):
            for field, value in [('clean', ''), ('smudge', ''), ('process', ''), ('required', 'false')]:
                command += ['-c', name + '.' + field + '=' + value]
        result = subprocess.run([*command, *args],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=20)
        if result.returncode:
            raise ValueError('Local Git operation failed: ' + result.stderr.decode(errors='replace')[:600])
        if len(result.stdout) > 2 * MAX_FILE_BYTES:
            raise ValueError('Git response exceeds source workbench limit')
        return result.stdout.decode('utf-8')

    @contextmanager
    def parent(self, path, *, create=False):
        parts = _parts(path)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def bytes(self, path):
        with self.parent(path) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE_BYTES:
                    raise ScopeDenied('Source files must be regular, singly linked and at most 1 MiB')
                data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError('Source file exceeds 1 MiB')
                return data, info.st_mode

    def inspect(self, inputs):
        _fields(inputs, (), ('prefix', 'offset', 'limit'))
        prefix = inputs.get('prefix', '')
        if not isinstance(prefix, str):
            raise ValueError('Source prefix must be text')
        if prefix:
            _parts(prefix[:-1] if prefix.endswith('/') else prefix)
        offset, limit = inputs.get('offset', 0), inputs.get('limit', 100)
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('Use a nonnegative offset and limit 1..500')
        paths = self.git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split('\0')
        paths = sorted(set(p for p in paths if p and p.startswith(prefix)))
        return dict(root=str(self.root), head=self.git('rev-parse', 'HEAD').strip(),
                    tree=self.git('rev-parse', 'HEAD^{tree}').strip(),
                    status=self.git('status', '--porcelain', '--untracked-files=all'),
                    files=paths[offset:offset + limit], next_offset=offset + limit if offset + limit < len(paths) else None)

    def read(self, inputs):
        _fields(inputs, ('path',), ('offset', 'limit'))
        data, _ = self.bytes(inputs['path'])
        offset, limit = inputs.get('offset', 0), inputs.get('limit', 65536)
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 262144:
            raise ValueError('Use a nonnegative byte offset and limit 1..262144')
        # Byte offsets permit bounded paging of large source files.
        return dict(path=inputs['path'], sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                    text=data[offset:offset + limit].decode('utf-8', errors='replace'),
                    next_offset=offset + limit if offset + limit < len(data) else None)

    def write(self, inputs):
        _fields(inputs, ('path', 'text', 'expected_sha256'))
        if not isinstance(inputs['text'], str):
            raise ValueError('Source text must be a string')
        data = inputs['text'].encode('utf-8')
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('Source file exceeds 1 MiB')
        expected = inputs['expected_sha256']
        try:
            before, mode = self.bytes(inputs['path'])
            actual = hashlib.sha256(before).hexdigest()
        except FileNotFoundError:
            actual, mode = None, 0o644
        if expected != actual:
            raise ValueError('Source changed; read current sha256 before writing (null for a new file)')
        with self.parent(inputs['path'], create=True) as (parent, name):
            temporary = '.factory-source-' + uuid.uuid4().hex
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    os.fchmod(stream.fileno(), stat.S_IMODE(mode) & 0o777)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
        return dict(path=inputs['path'], before_sha256=actual, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))

    def edit(self, inputs):
        _fields(inputs, ('path', 'replacements', 'expected_sha256', 'result_sha256'))
        replacements = inputs['replacements']
        if not isinstance(replacements, list) or not 1 <= len(replacements) <= 64:
            raise ValueError('Use 1..64 exact replacements')
        data, _ = self.bytes(inputs['path'])
        if hashlib.sha256(data).hexdigest() != inputs['expected_sha256']:
            raise ValueError('Source changed; read current sha256 before editing')
        text = data.decode('utf-8')
        for replacement in replacements:
            _fields(replacement, ('old', 'new'))
            old, new = replacement['old'], replacement['new']
            if not isinstance(old, str) or not old or not isinstance(new, str):
                raise ValueError('Replacement requires nonempty old text and string new text')
            if text.count(old) != 1:
                raise ValueError('Replacement must match exactly once')
            text = text.replace(old, new, 1)
            if len(text.encode('utf-8')) > MAX_FILE_BYTES:
                raise ValueError('Source file exceeds 1 MiB')
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != inputs['result_sha256']:
            raise ValueError('Edited source does not match declared result sha256')
        return self.write(dict(path=inputs['path'], text=text,
                               expected_sha256=inputs['expected_sha256']))

    def localcommit(self, inputs):
        _fields(inputs, ('paths', 'message', 'expected_head'))
        paths, message = inputs['paths'], inputs['message']
        if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_PATHS or len(set(paths)) != len(paths):
            raise ValueError('Commit requires 1..64 unique explicit file paths')
        if not isinstance(message, str) or not message.strip() or len(message.encode()) > 4000 or '\0' in message:
            raise ValueError('A bounded commit message is required')
        for path in paths:
            _parts(path)
        head = self.git('rev-parse', 'HEAD').strip()
        if inputs['expected_head'] != head:
            raise ValueError('HEAD changed; inspect before committing')
        if self.git('diff', '--cached', '--name-only', '--no-ext-diff', '--no-textconv'):
            raise ScopeDenied('Existing staged changes must be resolved before localcommit')
        # Plumbing avoids hooks, clean filters, signing, editors and remote operations.
        fd, name = tempfile.mkstemp(prefix='factory-index-', dir=self.root / '.git')
        os.close(fd)
        os.unlink(name)
        index = Path(name)
        try:
            self.git('read-tree', head, index=index)
            for path in paths:
                data, mode = self.bytes(path)
                blob = self.git('hash-object', '-w', '--stdin', '--no-filters', data=data).strip()
                self.git('update-index', '--add', '--cacheinfo', '100755' if mode & 0o111 else '100644', blob, path, index=index)
            tree = self.git('write-tree', index=index).strip()
            if tree == self.git('rev-parse', 'HEAD^{tree}').strip():
                raise ValueError('Selected paths contain no source change')
            commit = self.git('commit-tree', '--no-gpg-sign', tree, '-p', head, data=(message + '\n').encode()).strip()
            self.git('update-ref', '-m', 'factory source workbench localcommit', 'HEAD', commit, head)
            self.git('read-tree', commit)
        finally:
            index.unlink(missing_ok=True)
            Path(name + '.lock').unlink(missing_ok=True)
        return dict(commit=commit, parent=head, tree=tree, paths=paths,
                    status=self.git('status', '--porcelain', '--untracked-files=all'), pushed=False)


def dispatch(store, task_id, operation, inputs):
    if operation not in {'inspect', 'read', 'write', 'edit', 'localcommit'}:
        raise ValueError('Unknown source workbench capability')
    workbench = Workbench(store, task_id)
    locks = workbench.store.home / 'source-workbench-locks'
    locks.mkdir(exist_ok=True)
    with (locks / (hashlib.sha256(str(workbench.root).encode()).hexdigest() + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return {'result': getattr(workbench, operation)(inputs)}
