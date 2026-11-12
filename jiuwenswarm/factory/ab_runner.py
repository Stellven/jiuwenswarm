"""One queue-owned A/B worker: run abrun directly, then upload immutable evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

from .config import SIMINFENG_ROOT, MIN_AVAIL_MIB, DOCKER_PREFIX
from .contract import atomic_json
from .lab_runner import inspect_image, docker, upload


def run(task, run_id, config_path, spool):
    root = Path(spool).resolve() / run_id
    root.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(config_path).read_text())
    atomic_json(root / 'config.json', dict(config, lab_run_id=run_id))
    spec = dict(config['spec'], outdir_base=str(root))
    atomic_json(root / 'spec.json', spec)
    process = None
    cancelled = False
    outcome, reason = 'ok', None
    def stop(signum, frame):
        nonlocal cancelled
        cancelled = True
        if process:
            # abrun + om_run are in this worker's queue-owned process group.
            process.terminate()
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for admission in config['admissions'].values():
            image = inspect_image(admission['image']['id'])
            if image['Id'] != admission['image']['id']:
                raise ValueError('A/B image digest differs')
            if image.get('Architecture') != 'arm64' or (image.get('Config', {}).get('Labels') or {}).get('campaign.target.profile') != 'jetson-orin':
                raise ValueError('A/B image target differs')
        model = Path(config['contract']['model']['path'])
        if model.stat().st_size != config['contract']['model']['size']:
            raise ValueError('Model size differs from contract')
        expected = config['contract']['model'].get('sha256')
        if expected:
            with model.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('Model hash differs from contract')
        env = dict(os.environ, OM_MODELDIR=str(model.parent), OM_MIN_AVAIL_MIB=str(MIN_AVAIL_MIB),
                   DOCKER_CMD_PREFIX=DOCKER_PREFIX, PYTHONDONTWRITEBYTECODE='1')
        if os.environ.get('FACTORY_OM_RUN') and 'ABRUN_RUNNER' not in env:
            env['ABRUN_RUNNER'] = os.environ['FACTORY_OM_RUN']
        with (root / 'launcher.stdout.txt').open('w') as stdout, (root / 'launcher.stderr.txt').open('w') as stderr:
            process = subprocess.Popen([sys.executable,
                os.environ.get('FACTORY_ABRUN', str(SIMINFENG_ROOT / 'cc/abrun/abrun.py')),
                str(root / 'spec.json')], env=env, stdout=stdout, stderr=stderr)
            if process.wait():
                outcome = 'measurement_failed'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        outcome, reason = 'measurement_failed', str(exc)
    finally:
        if cancelled:
            outcome = 'cancelled'
        for path in root.glob('ab/*/container.id'):
            cid = path.read_text().strip()
            if re.fullmatch(r'[a-f0-9]{12,64}', cid):
                try:
                    removed = docker(['rm', '-f', cid])
                    if removed.returncode and 'No such container' not in removed.stderr:
                        outcome, reason = 'measurement_failed', 'Owned A/B container cleanup failed'
                except (OSError, subprocess.SubprocessError):
                    outcome, reason = 'measurement_failed', 'Owned A/B container cleanup failed'
        atomic_json(root / 'worker.json', dict(execution_outcome=outcome, reason=reason))
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob('*')) if p.is_file()
             and p.name not in {'manifest.json', 'ack.json'} and not p.name.startswith('.pending-')}
    atomic_json(root / 'manifest.json', dict(task_id=task, lab_run_id=run_id, files=files))
    if not upload(task, run_id, root, spool):
        return 1
    return 0 if outcome == 'ok' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('task', 'run', 'config', 'spool'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    return run(args.task, args.run, args.config, args.spool)


if __name__ == '__main__':
    raise SystemExit(main())
