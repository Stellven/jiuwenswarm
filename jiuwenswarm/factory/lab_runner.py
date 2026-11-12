"""Fixed external lab worker. Store access belongs exclusively to Manager ingest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

from .contract import atomic_json

from .config import OM_RUN, DOCKER_PREFIX, MIN_AVAIL_MIB, DOCKER_TIMEOUT, UPLOAD_TIMEOUT
from .effective_config import ENV_KEYS, parse_effective
REQUIRED = {'stdout.txt', 'stderr.txt', 'result.json', 'watchdog.jsonl',
            'telemetry.jsonl', 'threads.summary.json', 'cmd.txt'}


def docker(args):
    command = shlex.split(os.environ.get('FACTORY_DOCKER', 'docker')) + list(args)
    if not os.environ.get('FACTORY_DOCKER'):
        command = shlex.split(DOCKER_PREFIX) + [shlex.join(command)]
    return subprocess.run(command, capture_output=True, text=True, timeout=DOCKER_TIMEOUT)


def inspect_image(ref):
    result = docker(['image', 'inspect', ref])
    if result.returncode:
        raise ValueError('Local image is unavailable')
    return json.loads(result.stdout)[0]


def collect(root, config):
    """Parse raw files again on ingestion; never trust a worker's scored verdict."""
    root = Path(root)
    contract = config['contract']
    stderr = (root / 'stderr.txt').read_text(errors='replace') if (root / 'stderr.txt').exists() else ''
    def read_json(name):
        try:
            return json.loads((root / name).read_text())
        except (OSError, ValueError):
            return {}
    result = read_json('result.json')
    worker = read_json('worker.json')
    threads = read_json('threads.summary.json')
    lines, effective = parse_effective(stderr)
    mismatches = {}
    for key, value in config['env'].items():
        if key == 'LLAMA_MMAP_ADVICE':
            continue  # Patch 08 does not report this field; no effective-value claim.
        expected = str(int(value)) if value.isascii() and value.isdigit() else value
        actual = effective.get(ENV_KEYS.get(key))
        if actual != expected:
            mismatches[key] = dict(requested=value, effective=actual)
    config_ok = bool(lines) and len(set(lines)) == 1 and set(effective) == set(ENV_KEYS.values()) and not mismatches
    xfill = any(row.get('comm', '').startswith('xfill-') and row.get('samples', 0) > 0
                for row in threads.get('threads', {}).values())
    checks = {'effective_config_matches_request': config_ok, 'xfill_threads_present': xfill}
    required = list(contract['engagement_checks'])
    if config.get('role', 'candidate') == 'candidate':
        # Component-specific checks (e.g. patch 09 thread names) cannot hold on the reference image.
        required += contract.get('candidate_engagement_checks', [])
    for check in required:
        if check not in checks:
            checks[check] = check in stderr
    missing = sorted(name for name in REQUIRED if not (root / name).is_file())
    outcome = worker.get('execution_outcome', 'ok')
    invalid = re.search(r'^expert_config: invalid .*$', stderr, re.MULTILINE)
    watchdog = (root / 'watchdog.jsonl').read_text(errors='replace') if (root / 'watchdog.jsonl').exists() else ''
    if outcome == 'ok':
        if invalid:
            outcome = 'config_rejected'
        elif (result.get('oom_killed') or result.get('watchdog_trips') or 'watchdog_trip' in watchdog
              or result.get('exit_code') != 0 or result.get('status') != 'ok'
              or ('effective_config_matches_request' in required and not config_ok)
              or not all(checks.get(k, False) for k in required)):
            outcome = 'measurement_failed'
    complete = not missing and bool(result) and bool(threads)
    stdout = root / 'stdout.txt'
    metric = re.search(r'(?<!prompt )\beval time.*?\(\s*([\d.]+) ms per token', stderr)
    return dict(execution_outcome=outcome, evidence_completeness='complete' if complete else 'partial',
        stdout_sha256=hashlib.sha256(stdout.read_bytes()).hexdigest() if stdout.is_file() else None,
        image_id=config['admission']['image']['id'], run_ref=config.get('lab_run_id'),
        details=dict(requested=config['env'], effective=effective, mismatches=mismatches,
            unreported_requested=[k for k in config['env'] if k not in ENV_KEYS],
            effective_line_count=len(lines), engagement_checks=checks, missing_files=missing,
            invalid_message=invalid.group(0) if invalid else None,
            exit_status=result.get('exit_code'), aborted=(result.get('exit_code') or 0) > 128 or
                (result.get('exit_code') or 0) < 0 or bool(result.get('signal')),
            eval_ms_per_token=float(metric[1]) if metric else None, worker=worker))


def write_bundle(root, task, run, admission, contract):
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir())
             if p.is_file() and p.name not in {'manifest.json', 'ack.json'} and not p.name.startswith('.pending-')}
    manifest = dict(task_id=task, lab_run_id=run, admission_id=admission,
                    contract_id=contract, files=files)
    atomic_json(root / 'manifest.json', manifest)
    return manifest


def upload(task, run, root, spool):
    """A separate host process owns persistence. No store module is imported here."""
    for delay in (0, .2, 1, 2):
        if delay:
            time.sleep(delay)
        try:
            result = subprocess.run([sys.executable, '-m', 'jiuwenswarm.factory.manager',
                'ingest', '--task', task, '--run', run, '--bundle', str(root), '--spool', str(spool)],
                capture_output=True, text=True, timeout=UPLOAD_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and (root / 'ack.json').exists():
            return True
    return False


def run(task, lab_run, admission, contract_id, config, spool):
    root = Path(spool) / lab_run
    root.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(config).read_text())
    config['lab_run_id'] = lab_run
    atomic_json(root / 'config.json', config)
    outcome, reason = 'ok', None
    process = None
    cancelled = False
    def stop(signum, frame):
        nonlocal cancelled
        cancelled = True
        if process is not None:
            process.terminate()
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        image = inspect_image(config['admission']['image']['id'])
        if image['Id'] != config['admission']['image']['id']:
            outcome = 'bad_digest'
        elif image.get('Architecture') != 'arm64' or (image.get('Config', {}).get('Labels') or {}).get('campaign.target.profile') != 'jetson-orin':
            outcome = 'wrong_target'
        else:
            model = Path(config['contract']['model']['path'])
            if model.stat().st_size != config['contract']['model']['size']:
                raise ValueError('Model file size differs from contract')
            expected_sha = config['contract']['model'].get('sha256')
            if expected_sha:
                with model.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_sha:
                        raise ValueError('Model SHA256 differs from contract')
            # om_run interpolates ENV_FLAGS into its sg command. Manager restricts
            # every value to shell-safe tokens before this worker can be submitted.
            flags = ' '.join('-e ' + k + '=' + v for k, v in sorted(config['env'].items()))
            env = dict(os.environ, OM_THREADS='1', OM_MIN_AVAIL_MIB=str(MIN_AVAIL_MIB),
                       OM_MODELDIR=str(model.parent), DOCKER_CMD_PREFIX=DOCKER_PREFIX)
            with (root / 'launcher.stdout.txt').open('w') as stdout, (root / 'launcher.stderr.txt').open('w') as stderr:
                process = subprocess.Popen([os.environ.get('FACTORY_OM_RUN', OM_RUN), str(root),
                    image['Id'], flags, config['contract']['workload']['tool'], *config['argv']],
                    stdout=stdout, stderr=stderr, env=env)
                process.wait()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        outcome, reason = 'measurement_failed', type(exc).__name__ + ': lab preflight or execution failed'
    finally:
        if cancelled:
            outcome = 'cancelled'
        # The container id belongs to this run directory. Never reap by global label.
        cleanup = 'no_container_created'
        cid_path = root / 'container.id'
        if cid_path.exists():
            cid = cid_path.read_text().strip()
            if re.fullmatch(r'[a-f0-9]{12,64}', cid):
                try:
                    removed = docker(['rm', '-f', cid])
                    cleanup = 'reaped' if removed.returncode == 0 or 'No such container' in removed.stderr else 'failed'
                except (OSError, subprocess.SubprocessError):
                    cleanup = 'failed'
            else:
                cleanup = 'invalid_container_id'
        if cleanup in {'failed', 'invalid_container_id'} and outcome == 'ok':
            outcome = 'measurement_failed'
        atomic_json(root / 'worker.json', dict(execution_outcome=outcome, reason=reason, cleanup=cleanup))
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    write_bundle(root, task, lab_run, admission, contract_id)
    if not upload(task, lab_run, root, spool):
        print(json.dumps(dict(execution_outcome='upload_pending', lab_run_id=lab_run)))
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('task', 'run', 'admission', 'contract', 'config', 'spool'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    return run(args.task, args.run, args.admission, args.contract, args.config, args.spool)


if __name__ == '__main__':
    raise SystemExit(main())
