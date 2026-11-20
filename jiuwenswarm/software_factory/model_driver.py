"""A real, bounded Codex process; model text alone never verifies an artifact."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid

from .contracts import StageBlocked, StageFailure


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    """Do not publish accidental credential strings from a child process."""
    text = re.sub(r'(?i)(authorization\s*:\s*bearer\s+)\S+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|password|secret)\s*[=:]\s*)[^\s,;]+',
                  r'\1[REDACTED]', text)
    return re.sub(r'\bsk-[A-Za-z0-9_-]{20,}\b', '[REDACTED]', text)


def execute_process(argv, directory: Path, log_directory: Path, *, emit=None, timeout=300, env=None):
    """Execute argv without a shell, preserving actual streams and exit status."""
    if (not isinstance(argv, (list, tuple)) or not argv
            or not all(isinstance(value, str) and '\x00' not in value for value in argv)):
        raise StageFailure('invalid_command', 'Expected a nonempty command argument list')
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
        raise StageFailure('invalid_timeout', 'Process timeout must be between zero and 3600 seconds')
    directory = Path(directory).resolve(strict=True)
    log_directory.mkdir(parents=True, exist_ok=False)
    stdout_path, stderr_path = log_directory / 'stdout.log', log_directory / 'stderr.log'
    stdout_path.touch()
    stderr_path.touch()
    record = {'argv': [redact(value) for value in argv], 'cwd': str(directory),
              'started_at': timestamp(), 'exit_code': None, 'stdout_path': str(stdout_path),
              'stderr_path': str(stderr_path), 'stdout': '', 'stderr': ''}
    started = time.monotonic()

    def observe(kind, payload):
        if emit:
            emit(kind, payload)

    observe('command.started', {'command': record.copy()})

    def capture(pipe, destination, stream):
        with destination.open('w', encoding='utf-8') as writer:
            while True:
                raw = pipe.readline(65536)
                if not raw:
                    break
                text = redact(raw.decode('utf-8', errors='replace'))
                writer.write(text)
                writer.flush()
                observe('command.output', {'stream': stream, 'text': text,
                                           'command_started_at': record['started_at']})
        pipe.close()

    try:
        process = subprocess.Popen(list(argv), cwd=directory, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env={**os.environ, **(env or {})}, start_new_session=True)
        record['pid'] = process.pid
        readers = [threading.Thread(target=capture, args=(process.stdout, stdout_path, 'stdout'), daemon=True),
                   threading.Thread(target=capture, args=(process.stderr, stderr_path, 'stderr'), daemon=True)]
        for reader in readers:
            reader.start()
        try:
            record['exit_code'] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            record['timed_out'] = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            record['exit_code'] = process.returncode
        for reader in readers:
            reader.join(timeout=5)
        if any(reader.is_alive() for reader in readers):
            # Descendants cannot retain a terminal/log pipe after their parent exits.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            for reader in readers:
                reader.join(timeout=2)
            record['stream_incomplete'] = any(reader.is_alive() for reader in readers)
    except OSError as error:
        record['exit_code'] = 127
        stderr_path.write_text(redact(str(error)), encoding='utf-8')
    record.update(finished_at=timestamp(), duration_s=round(time.monotonic() - started, 6))
    record['stdout'] = stdout_path.read_text(encoding='utf-8')[-16000:]
    record['stderr'] = stderr_path.read_text(encoding='utf-8')[-16000:]
    observe('command.finished', {'command': record.copy()})
    (log_directory / 'invocation.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


class CodexDriver:
    """Run the installed authenticated engineering agent with its sandbox enabled."""

    def __init__(self, executable=None):
        self.executable = executable or shutil.which('codex')

    def run(self, prompt, workspace: Path, *, emit=None, model=None, timeout=300, sandbox='workspace-write'):
        if not self.executable:
            raise StageBlocked('model_unavailable', 'Codex CLI is not installed or not on PATH')
        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        if sandbox not in {'read-only', 'workspace-write'}:
            raise StageFailure('invalid_sandbox', 'Agent execution must retain a restricted sandbox')
        invocation_dir = workspace / '.agent' / uuid.uuid4().hex
        invocation_dir.mkdir(parents=True)
        prompt_path = invocation_dir / 'prompt.md'
        prompt_path.write_text(prompt, encoding='utf-8')
        final_path = invocation_dir / 'last-message.txt'
        # Passing the prompt by argv would expose it in process listings. The
        # shell-free Python launcher only delivers it through the child's stdin.
        argv = [str(self.executable), 'exec', '--json', '--skip-git-repo-check', '--ephemeral',
                '--sandbox', sandbox, '-c', 'approval_policy="never"',
                '--cd', str(workspace), '--output-last-message', str(final_path)]
        if model:
            if not isinstance(model, str) or not model or len(model) > 200:
                raise StageFailure('invalid_model', 'Expected a model profile name')
            argv += ['--model', model]
        argv += ['-']
        # The launcher is an actual Python process and starts the actual Codex
        # process. It reads one owned prompt file; no auth file is copied/logged.
        import sys
        launcher = (
            'import pathlib,subprocess,sys; '
            'p=subprocess.run(sys.argv[2:],input=pathlib.Path(sys.argv[1]).read_bytes()); '
            'sys.exit(p.returncode)'
        )
        command = [sys.executable, '-c', launcher, str(prompt_path), *argv]
        receipt = execute_process(command, workspace, invocation_dir / 'process', emit=emit, timeout=timeout)
        receipt.update(driver='codex-cli', model=model or 'configured-default',
                       prompt_path=str(prompt_path), response_path=str(final_path), agent_argv=argv)
        (invocation_dir / 'invocation.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if receipt['exit_code'] != 0 or receipt.get('timed_out') or receipt.get('stream_incomplete'):
            raise StageBlocked('model_execution_failed', 'The real model process did not complete successfully',
                               {'invocation': receipt})
        if not final_path.is_file() or not final_path.stat().st_size:
            raise StageFailure('model_response_missing', 'Codex did not produce a final response',
                               {'invocation': receipt})
        return {'text': final_path.read_text(encoding='utf-8'), 'invocation': receipt}
