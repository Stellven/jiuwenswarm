"""Bounded Git-change materializer, separate from runtime dispatch."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid


def _materialize(host, template, change, output, *, trusted_build=False, timeout=120, core=None, attempt=None, persist=None):
    """Build in a new checkout; never applies a candidate to the caller's repository."""
    if core is None:
        from . import ccv2 as core
    core.require(trusted_build is True, 'BUILD_AUTHORIZATION_REQUIRED', 'Source builds execute repository code; authorize --trusted-build')
    core.fields(change, {'format', 'repository', 'base', 'patch', 'tree', 'build'}, {'format', 'repository', 'base', 'patch', 'tree', 'build'})
    core.require(change['format'] == 'cc-source-change/1', 'UNSUPPORTED_SOURCE_FORMAT', 'Expected cc-source-change/1')
    import re
    core.require(all(isinstance(change[k], str) and re.fullmatch('[0-9a-f]{40}', change[k]) for k in ('base', 'tree')), 'MUTABLE_SOURCE', 'Base commit and expected Git tree must be full immutable IDs')
    core.require(isinstance(change['repository'], str) and change['repository'], 'MISSING_MATERIAL', 'Repository locator required')
    build = change['build']
    core.fields(build, {'command', 'lock', 'output'}, {'command', 'output'})
    core.require(isinstance(build['command'], list) and build['command'] and all(isinstance(a, str) and a for a in build['command']), 'INVALID_RECIPE', 'Build command must be an argument vector')
    core.require(isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and 0 < timeout <= 3600, 'INVALID_LIMIT', 'Build timeout must be 0..3600 seconds')
    template, output = Path(template).resolve(), Path(output).resolve()
    core.require(not output.exists(), 'OUTPUT_EXISTS', 'Materialization writes a new package; choose an unused destination')
    declaration = json.loads(json.dumps(core.load(template/'cc.yaml')))
    patch = host.artifact_path(change['patch'])
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1', GIT_TERMINAL_PROMPT='0', PYTHONDONTWRITEBYTECODE='1')
    records = attempt['steps']
    def run(arguments, cwd, code):
        try:
            result = subprocess.run(arguments, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            records.append({'command': arguments, 'exit_code': None, 'outcome': 'unknown',
                            'stdout': (error.stdout or b'').decode('utf-8', errors='replace'),
                            'stderr': (error.stderr or b'').decode('utf-8', errors='replace')})
            persist()
            raise core.CCError('BUILD_TIMEOUT', 'Deadline exceeded; descendant cessation is not confirmed. Inspect this attempt before retrying.')
        records.append({'command': arguments, 'exit_code': result.returncode,
                        'stdout': result.stdout.decode('utf-8', errors='replace'), 'stderr': result.stderr.decode('utf-8', errors='replace')})
        persist()
        core.require(result.returncode == 0, code, records[-1]['stderr'] or records[-1]['stdout'])
        return result.stdout.decode('utf-8').strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cc-build-', dir=output.parent) as temporary:
        checkout = Path(temporary)/'source'; checkout.mkdir()
        run(['git', 'init', str(checkout)], output.parent, 'SOURCE_UNAVAILABLE')
        run(['git', '-c', 'core.autocrlf=false', 'fetch', '--depth=1', change['repository'], change['base']], checkout, 'SOURCE_UNAVAILABLE')
        run(['git', '-c', 'core.autocrlf=false', 'checkout', '--detach', 'FETCH_HEAD'], checkout, 'SOURCE_UNAVAILABLE')
        base = run(['git', 'rev-parse', 'HEAD'], checkout, 'SOURCE_UNAVAILABLE')
        core.require(base == change['base'], 'BASE_MISMATCH', 'Fetched source differs from requested base')
        # Empty patches rebuild the exact base; older Git has no --allow-empty.
        if patch.stat().st_size:
            run(['git', 'apply', '--check', '--index', '--binary', str(patch)], checkout, 'PATCH_REJECTED')
            run(['git', 'apply', '--index', '--binary', str(patch)], checkout, 'PATCH_REJECTED')
        tree = run(['git', 'write-tree'], checkout, 'SOURCE_INVALID')
        core.require(tree == change['tree'], 'TREE_MISMATCH', 'Patch does not reconstruct the declared source tree')
        entries = run(['git', 'ls-files', '--stage'], checkout, 'SOURCE_INVALID')
        core.require(not any(line.startswith('160000 ') for line in entries.splitlines()), 'UNSUPPORTED_SOURCE_MATERIAL', 'Resolve submodules with a qualified build profile; do not silently omit them')
        tracked = run(['git', 'ls-files', '-z'], checkout, 'SOURCE_INVALID')
        for name in filter(None, tracked.split('\0')):
            path = core.contained(checkout, name)
            if path.is_file():
                with path.open('rb') as stream:
                    pointer = stream.read(128).startswith(b'version https://git-lfs.github.com/spec/v1')
                core.require(not pointer, 'UNSUPPORTED_SOURCE_MATERIAL', 'Unresolved Git LFS pointer: ' + name)
        lock = None
        if 'lock' in build:
            path = core.contained(checkout, build['lock'])
            core.require(path.is_file(), 'MISSING_DEPENDENCY_LOCK', build['lock'])
            lock = {'path': build['lock'], 'sha256': core.file_sha(path)}
        command = [a.replace('{python}', host.python) for a in build['command']]
        run(command, checkout, 'BUILD_FAILED')
        # A build may create ignored output, but may not quietly rewrite source.
        after = run(['git', 'diff', '--name-only'], checkout, 'SOURCE_INVALID')
        staged = run(['git', 'write-tree'], checkout, 'SOURCE_INVALID')
        core.require(not after and staged == tree, 'BUILD_MUTATED_SOURCE', 'Build modified tracked source after the declared tree was bound')
        payload = core.contained(checkout, build['output'])
        core.require(payload.is_dir(), 'MISSING_BUILD_OUTPUT', build['output'])
        payload_files = core.tree_files(payload)
        core.require(bool(payload_files), 'MISSING_BUILD_OUTPUT', 'Build output is empty')
        package = Path(temporary)/'package'; package.mkdir()
        for row in core.tree_files(template):
            target = package/row['path']; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template/row['path'], target)
        core.require(not (package/'payload').exists(), 'CONFLICTING_MATERIAL', 'Template must not contain a stale payload')
        shutil.copytree(payload, package/'payload')
        record = {'format': 'cc-build/1', 'attempt': attempt['id'], 'source_change': change, 'observed_base': base, 'observed_tree': tree,
                  'dependency_lock': lock, 'command': command, 'python': {'path': host.python, 'sha256': core.file_sha(host.python)},
                  'payload_files': payload_files, 'steps': records, 'completed': time.time(),
                  'limits': 'Trusted local build; lock identity is not proof of full environment closure or software quality'}
        (package/'build-record.json').write_bytes(core.encoded(record))
        declaration['provenance'] = 'build-record.json'
        (package/'cc.yaml').write_bytes(core.encoded(declaration))
        # Validate executable paths and contracts before making the package visible.
        release = host.prepare(package)
        package.rename(output)
    return {'format': 'cc-materialization/1', 'package': str(output), 'release': release,
            'source_tree': tree, 'build_record': host.put_artifact(output/'build-record.json')}


def materialize(host, template, change, output, *, trusted_build=False, timeout=120, core=None):
    """Retain every authorized build attempt, including failure and uncertainty."""
    if core is None:
        from . import ccv2 as core
    core.require(trusted_build is True, 'BUILD_AUTHORIZATION_REQUIRED', 'Source builds execute repository code; authorize --trusted-build')
    identity = str(uuid.uuid4())
    directory = host.store/'builds'/identity
    directory.mkdir(parents=True)
    path = directory/'attempt.json'
    attempt = {'format': 'cc-build-attempt/1', 'id': identity, 'state': 'running', 'started': time.time(),
               'source_change': change, 'steps': [], 'limits': 'Trusted local build; no process containment or automatic retry. Logs may contain sensitive build data.'}
    def persist():
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(core.encoded(attempt))
        temporary.replace(path)
    persist()
    try:
        result = _materialize(host, template, change, output, trusted_build=True, timeout=timeout,
                              core=core, attempt=attempt, persist=persist)
        attempt.update(state='succeeded', result=result, completed=time.time())
        persist()
        return result
    except Exception as error:
        attempt.update(state='unknown' if getattr(error, 'code', None) == 'BUILD_TIMEOUT' else 'failed',
                       error={'code': getattr(error, 'code', 'BUILD_FAILED'), 'message': str(error)}, completed=time.time())
        persist()
        if isinstance(error, core.CCError):
            error.path = str(path)
            raise
        raise core.CCError('BUILD_FAILED', str(error), str(path)) from error
