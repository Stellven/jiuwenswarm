"""Shared helpers for the model-in-the-loop CC benches (heldout, contract, haltbench). Stdlib only.

* call_codex: one tool-free `codex exec` call, same command shape as planner/run_planner_bench.py
  (empty working directory, prompt on stdin, read-only sandbox, ephemeral). Writes prompt.txt, reply.txt, run.json.
* manifests: sha256 freeze of the gold files; `verify_manifest` refuses to run if a frozen file changed.
* tokens and wall time are recorded per call, so cost can be reported.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roots  # noqa: E402

MODEL = 'gpt-6.1-sol'
TIMEOUT_S = 300


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8-sig'))


def write_manifest(folder, names, manifest='MANIFEST.sha256'):
    """Write `<sha256>  <name>` lines for the gold files. Bytes are hashed as stored."""
    folder = Path(folder)
    lines = ['%s  %s' % (sha256_bytes((folder / n).read_bytes()), n) for n in names]
    (folder / manifest).write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
    return lines


def verify_manifest(folder, manifest='MANIFEST.sha256'):
    """Return a list of problems (empty = every frozen file matches)."""
    folder = Path(folder)
    path = folder / manifest
    if not path.exists():
        return ['%s is missing; run the bench `freeze` command first' % manifest]
    problems = []
    for line in path.read_bytes().decode('utf-8').splitlines():
        if not line.strip():
            continue
        digest, name = line.split('  ', 1)
        target = folder / name
        if not target.exists():
            problems.append('%s is missing' % name)
        elif sha256_bytes(target.read_bytes()) != digest:
            problems.append('%s differs from the frozen sha256' % name)
    return problems


def parse_tokens(text):
    """Last 'tokens used' figure printed by the codex CLI, or None."""
    found = re.findall(r'tokens used\s*[:\r\n ]+([\d,]+)', text or '', flags=re.I)
    return int(found[-1].replace(',', '')) if found else None


def parse_usage(text):
    """Token figures printed by the codex CLI: dict(total, input, output); a figure is None when it is not printed.

    `codex exec` prints only `tokens used` then the total (checked against saved run.json files, 2026-10-28). The input
    and output figures are read only when the text states them explicitly ("input tokens: N", "output_tokens": N);
    they are never derived from the total.
    """
    text = text or ''

    def last(pattern):
        found = re.findall(pattern, text, flags=re.I)
        return int(found[-1].replace(',', '')) if found else None
    return dict(total=parse_tokens(text),
                input=last(r'input[_ ]tokens\W{0,3}[:=]\s*([\d,]+)'),
                output=last(r'output[_ ]tokens\W{0,3}[:=]\s*([\d,]+)'))


def _invoke(command, prompt, timeout):
    start = time.monotonic()
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8', errors='replace',
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'))
    timed_out = False
    try:
        stdout, stderr = proc.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=10)
        proc.kill()
        stdout, stderr = proc.communicate(timeout=10)
    usage = parse_usage(stdout + '\n' + stderr)
    return dict(elapsed_s=round(time.monotonic() - start, 2), returncode=proc.returncode, timed_out=timed_out,
                stdout_tail=stdout[-3000:], stderr_tail=stderr[-3000:], tokens=usage['total'],
                input_tokens=usage['input'], output_tokens=usage['output'])


def call_codex(prompt, call_dir, model=MODEL, cli=None, timeout=TIMEOUT_S, invoke=None, meta=None):
    """One model call. Never retries. Returns dict(reply, tokens, elapsed_s, ok, dir). `invoke` is a test hook."""
    call_dir = Path(call_dir)
    call_dir.mkdir(parents=True, exist_ok=False)
    (call_dir / 'prompt.txt').write_bytes(prompt.encode('utf-8'))
    reply_path = call_dir / 'reply.txt'
    cwd = call_dir / ('empty-' + uuid.uuid4().hex[:8])
    cwd.mkdir()
    cli = cli or roots.require_codex()
    command = [cli, 'exec', '--skip-git-repo-check', '-m', model, '-s', 'read-only', '--ephemeral', '-C', str(cwd), '-o', str(reply_path), '-']
    record = dict(meta or {}, model=model, command=command, prompt_sha256=sha256_bytes(prompt.encode('utf-8')),
                  prompt_chars=len(prompt), cwd_initially_empty=True)
    try:
        record.update((invoke or _invoke)(command, prompt, timeout))
    except (OSError, subprocess.SubprocessError) as exc:
        record.update(error=str(exc), elapsed_s=0.0, tokens=None, input_tokens=None, output_tokens=None, timed_out=False, returncode=None)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    if not reply_path.exists():
        reply_path.write_bytes(b'')
    raw = reply_path.read_bytes()
    record['reply_sha256'] = sha256_bytes(raw)
    reply = raw.decode('utf-8', 'replace')
    record['ok'] = bool(reply.strip()) and not record.get('timed_out') and record.get('returncode') == 0
    write_json(call_dir / 'run.json', record)
    return dict(reply=reply, tokens=record.get('tokens'), input_tokens=record.get('input_tokens'), output_tokens=record.get('output_tokens'), elapsed_s=record.get('elapsed_s', 0.0), ok=record['ok'], dir=str(call_dir))


def call_cost(calls):
    """Sum a list of call dicts: calls, tokens (None when no call reported any), wall seconds."""
    tokens = [c['tokens'] for c in calls if c.get('tokens') is not None]
    ins = [c['input_tokens'] for c in calls if c.get('input_tokens') is not None]
    outs = [c['output_tokens'] for c in calls if c.get('output_tokens') is not None]
    # The split is summed only when every call reported it; a partial sum would understate the unit.
    return dict(calls=len(calls), tokens=sum(tokens) if tokens else None,
                input_tokens=sum(ins) if calls and len(ins) == len(calls) else None,
                output_tokens=sum(outs) if calls and len(outs) == len(calls) else None,
                calls_without_token_count=len(calls) - len(tokens), wall_s=round(sum(c.get('elapsed_s') or 0 for c in calls), 2))


def rotate(arms, rep):
    """Counterbalanced arm order: rotate the list by the repeat number."""
    k = (rep - 1) % len(arms)
    return arms[k:] + arms[:k]


def extract_blocks(text, lang=None):
    """Fenced code blocks, in order. With lang, only blocks whose info string starts with it (case-insensitive)."""
    blocks = []
    for m in re.finditer(r'```([^\n`]*)\n(.*?)```', text or '', flags=re.S):
        info = m.group(1).strip().lower()
        if lang is None or info.startswith(lang):
            blocks.append(m.group(2))
    return blocks
