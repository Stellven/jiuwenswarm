"""Static verification for the runtime event recorder CC."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from helpers.verify_churn import signature_changes
from helpers.verify_gate import gate_silence, read_source


STAGE = 'native CC execution'
ENV_GATE = 'LLAMA_EVENT_REC'
RECORDER_NAME = 'runtime_event_recorder'
MARKERS = tuple(f'{RECORDER_NAME}: {suffix}' for suffix in ('active', 'inactive (', 'stats'))
ALLOWED_PATHS = {
    'src/CMakeLists.txt',
    'src/llama-context.cpp',
    'src/llama-context.h',
    'src/llama-event-recorder.cpp',
    'src/llama-event-recorder.h',
    'src/llama-moe-cache.cpp',
    'src/llama-moe-cache.h',
    'ggml/include/ggml-backend.h',
    'ggml/src/ggml-backend.cpp',
    'tools/server/server-context.cpp',
}
GIT_ENV = {
    key: value for key, value in os.environ.items()
    if not key.startswith('GIT_')
}
GIT_ENV.update(GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', LC_ALL='C')
NON_TEXT_CHANGE = re.compile(
    rb'^(?:rename (?:from|to) |copy (?:from|to) |(?:new file |old |new |deleted file )?'
    rb'mode (?!100644$)|GIT binary patch$|Binary files .* differ$)', re.M
)
COMMENT_OR_LITERAL = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
)
INFO_LITERAL = re.compile(
    r'\b(?:LLAMA_LOG_INFO|GGML_LOG_INFO)\s*\(\s*("(?:\\.|[^"\\])*")'
)
GATE_READER = re.compile(
    r'\b(?:auto|char\s+const|const\s+char)\s*\*?\s*(?:const\s+)?'
    r'(\w+)\s*=\s*(?:std::|::)?getenv\s*\(\s*"([^"]+)"\s*\)\s*;'
)
NEW_UNIT_SUFFIXES = {'.cpp', '.h'}


def record(name, status, detail, stage=STAGE):
    return {'name': name, 'status': status, 'detail': detail, 'stage': stage}


def result(checks):
    return {'checks': checks, 'done': all(check['status'] != 'fail' for check in checks)}


def git(checkout, *args, data=None, env=None):
    return subprocess.run(
        ['git', '-c', 'core.fsmonitor=false', *args],
        cwd=checkout, input=data, capture_output=True, env=env or GIT_ENV, check=False,
    )


def checked(process, allowed=(0,)):
    if process.returncode not in allowed:
        raise ValueError(process.stderr.decode(errors='replace').strip() or
                         f'Git exited with status {process.returncode}')
    return process.stdout


def existing_root(path):
    checkout = Path(path).expanduser()
    if not checkout.is_absolute():
        raise ValueError('checkout must be an absolute path')
    checkout = checkout.resolve(strict=True)
    root = checked(git(checkout, 'rev-parse', '--show-toplevel')).decode().rstrip('\n')
    if Path(root).resolve() != checkout:
        raise ValueError('checkout must be the root of the Git working tree')
    return checkout


def working_diff(checkout):
    diff_options = ('--binary', '--no-ext-diff', '--no-textconv', '--no-renames',
                    '--src-prefix=a/', '--dst-prefix=b/')
    diff = checked(git(checkout, 'diff', *diff_options, 'HEAD', '--', '.'))
    untracked = checked(git(checkout, 'ls-files', '--others', '--exclude-standard', '-z'))
    for path in filter(None, untracked.split(b'\0')):
        diff += checked(git(checkout, 'diff', *diff_options, '--no-index', '--',
                            '/dev/null', os.fsdecode(path)), allowed=(0, 1))
    return diff


def changed_paths(checkout, diff):
    if NON_TEXT_CHANGE.search(diff):
        raise ValueError('Use regular text-file changes without renames, copies or mode changes')
    stats = checked(git(checkout, 'apply', '--numstat', '-z', '-', data=diff))
    paths = set()
    for row in filter(None, stats.split(b'\0')):
        inserted, deleted, path = row.split(b'\t', 2)
        if not (inserted.isdigit() and deleted.isdigit() and path):
            raise ValueError('Expected Git numstat for a regular text-file change')
        paths.add(os.fsdecode(path))
    return paths


def source_lines(diff, *, additions_only):
    """Yield added or postimage hunk lines without joining separate hunks."""
    lines = []
    for line in diff.decode(errors='replace').splitlines():
        if line.startswith(('diff --git ', '@@ ')):
            yield '\n'.join(lines)
            lines = []
        elif line.startswith('+') and not line.startswith('+++ '):
            lines.append(line[1:])
        elif line.startswith(' ') and not additions_only:
            lines.append(line[1:])
        elif line.startswith(' '):
            lines.append('')
    yield '\n'.join(lines)


def strip_comments(source):
    return COMMENT_OR_LITERAL.sub(
        lambda match: match[0] if match[0].startswith(('"', "'")) else
        ' ' + '\n' * match[0].count('\n'), source,
    )


def default_off(source, env_gate):
    for reader in GATE_READER.finditer(source):
        variable, gate = reader.groups()
        if gate != env_gate:
            continue
        variable = re.escape(variable)
        guard = (
            rf'\s*if\s*\(\s*(?:!\s*{variable}\b|{variable}\s*==\s*nullptr)'
            r'\s*\)\s*(?:\{\s*)?return\s*(?:false|nullptr|\{\s*\})?\s*;'
        )
        if re.match(guard, source[reader.end():]):
            return True
    return False


def apply_check(checkout, diff, scratch, from_tree):
    if from_tree:
        env = dict(GIT_ENV, GIT_INDEX_FILE=str(scratch / 'index'))
        checked(git(checkout, 'read-tree', 'HEAD', env=env))
        checked(git(checkout, 'apply', '--cached', '--check', '-', data=diff, env=env))
        return
    checked(git(checkout, 'apply', '--check', '-', data=diff))


def patch_overlay(checkout, diff, scratch, paths):
    overlay = scratch / 'postimage'
    overlay.mkdir()
    for path in sorted(paths):
        original = checkout / path
        target = overlay / path
        if original.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
    # Apply in a separate Git directory so Git cannot discover an enclosing worktree.
    env = dict(GIT_ENV, GIT_DIR=str(scratch / 'overlay.git'), GIT_WORK_TREE=str(overlay))
    checked(git(overlay, 'init', '--quiet', '--template=', env=env))
    checked(git(overlay, 'apply', '-', data=diff, env=env))
    return overlay


def syntax_checks(checkout, postimage, paths):
    if not paths:
        return [record('syntax', 'skipped', 'No new C++ file to check', 'compile')]
    compiler = shutil.which('g++')
    if compiler is None:
        return [record('syntax', 'skipped', 'g++ is unavailable', 'compile')]
    includes = (
        postimage / 'src', postimage / 'include', postimage / 'ggml/include',
        checkout / 'src', checkout / 'include', checkout / 'ggml/include',
    )
    checks = []
    for path in paths:
        command = [compiler, '-std=c++17', '-fsyntax-only', '-x', 'c++']
        for directory in includes:
            command.extend(('-I', str(directory)))
        process = subprocess.run(
            [*command, str(postimage / path)], cwd=postimage,
            capture_output=True, text=True, errors='replace',
            env=dict(GIT_ENV, LC_ALL='C'), check=False,
        )
        detail = process.stderr.strip()
        missing = re.search(r'fatal error: ([^\n]+): No such file or directory', detail)
        if missing and missing[1] in {'build-info.h', 'ggml-config.h', 'llama-config.h'}:
            status = 'skipped'
        else:
            status = 'fail' if process.returncode else 'pass'
        checks.append(record('syntax:' + path, status, detail or 'g++ -fsyntax-only', 'compile'))
    return checks


def verify(inputs, scratch_dir=None):
    checks = []
    try:
        checkout = existing_root(inputs['checkout'])
        from_tree = 'diff_path' not in inputs
        if from_tree:
            diff = working_diff(checkout)
        else:
            diff_path = Path(inputs['diff_path']).expanduser()
            if not diff_path.is_absolute():
                raise ValueError('diff_path must be an absolute path')
            diff = diff_path.read_bytes()
        env_gate = inputs.get('env_gate', ENV_GATE)
        markers = inputs.get('markers', [])
        if env_gate != ENV_GATE:
            raise ValueError(f'This component requires {ENV_GATE}')
        if not isinstance(markers, list) or any(not isinstance(m, str) or not m for m in markers):
            raise ValueError('markers must be a list of nonempty literal strings')
        paths = changed_paths(checkout, diff)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        return result([record('diff_input', 'fail', str(exc)),
                       record('syntax', 'skipped', 'Diff unavailable', 'compile')])

    checks.append(record('high_churn_signatures', 'info', signature_changes(diff)))
    forbidden = sorted(paths - ALLOWED_PATHS)
    protected = sorted(path for path in forbidden if re.search(r'graph|router|sampl|/models/', path))
    checks.append(record('allowed_paths', 'pass' if paths and not forbidden else 'fail',
                         ', '.join(forbidden) if forbidden else
                         ('Only declared paths touched' if paths else 'Diff is empty')))
    checks.append(record('router_and_sampling_paths', 'fail' if protected else 'pass',
                         ', '.join(protected) if protected else 'No protected paths touched'))
    literals = [literal for hunk in source_lines(diff, additions_only=True)
                for literal in INFO_LITERAL.findall(strip_comments(hunk))]
    missing = [marker for marker in dict.fromkeys((*MARKERS, *markers))
               if not any(marker in literal for literal in literals)]
    checks.append(record('activation_markers', 'fail' if missing else 'pass',
                         'Missing: ' + ', '.join(missing) if missing else 'All INFO marker literals found'))

    try:
        with tempfile.TemporaryDirectory(dir=scratch_dir) as temporary:
            scratch = Path(temporary)
            apply_check(checkout, diff, scratch, from_tree)
            checks.insert(0, record('git_apply_check', 'pass', 'Applies to HEAD' if from_tree else
                                    'Applies to checkout'))
            if forbidden:
                checks.append(record('env_default_off', 'skipped', 'Diff touches forbidden paths'))
                checks.append(record('syntax', 'skipped', 'Diff touches forbidden paths', 'compile'))
                return result(checks)
            postimage = checkout if from_tree else patch_overlay(checkout, diff, scratch, paths)
            checks.append(record('gate_unset_silence', *gate_silence(
                diff, lambda path: read_source(postimage, path), env_gate, RECORDER_NAME + ':'
            )))
            # A revision can keep the gate in an unchanged recorder source.
            source_paths = {path for path in paths if Path(path).suffix in NEW_UNIT_SUFFIXES}
            source_paths.update(('src/llama-event-recorder.h', 'src/llama-event-recorder.cpp'))
            sources = ((postimage if path in paths else checkout) / path for path in sorted(source_paths))
            gate_found = any(
                default_off(strip_comments(source.read_text(errors='replace')), env_gate)
                for source in sources if source.is_file()
            )
            checks.append(record('env_default_off', 'pass' if gate_found else 'fail',
                                 f'{env_gate} getenv and immediate absent-value return '
                                 + ('found' if gate_found else 'missing')))
            new_units = sorted(path for path in paths if Path(path).suffix in NEW_UNIT_SUFFIXES
                               and (postimage / path).is_file()
                               and (git(checkout, 'cat-file', '-e', 'HEAD:' + path).returncode
                                    if from_tree else not (checkout / path).is_file()))
            checks.extend(syntax_checks(checkout, postimage, new_units))
    except (OSError, ValueError) as exc:
        name = 'postimage_check' if any(c['name'] == 'git_apply_check' for c in checks) else 'git_apply_check'
        checks.insert(0, record(name, 'fail', str(exc)))
        checks.append(record('syntax', 'skipped', 'Could not obtain checked postimage', 'compile'))
    return result(checks)


def main():
    packet = json.load(sys.stdin)
    if packet.get('capability') != 'verify':
        reply = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': 'Expected verify'}}
    else:
        reply = {'outcome': 'ok', 'outputs': verify(packet['inputs'], packet.get('output_dir'))}
    print(json.dumps(reply))


if __name__ == '__main__':
    main()
