"""Run/resume an already approved Spark mission with its finite host bridge."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from jiuwenswarm.factory.mission_supervisor import Supervisor
from jiuwenswarm.factory.store import Store

SHARED = Path('/home/user2/rsi-expert-streaming-spark-002/paired-retry-001')


def bridge_running(inbox):
    inbox.mkdir(parents=True, exist_ok=True)
    with (inbox / 'bridge.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream, fcntl.LOCK_UN)
        return False


def ensure_bridge(root, home, inbox, queue, jobq):
    if bridge_running(inbox):
        return None
    (inbox / 'STOP').unlink(missing_ok=True)
    # Bridge/jobq need tool paths, not provider credentials inherited from an
    # interactive shell. The agent receives its separate mounted profile.
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'USER', 'LANG', 'LC_ALL',
        'TMPDIR', 'LD_LIBRARY_PATH', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'FACTORY_NATIVE_BUILDER_IMAGE')
        if key in os.environ}
    env.update(FACTORY_BRIDGE_HOME=str(home), FACTORY_HOME=str(home),
               JOBQ_DIR=str(queue), FACTORY_JOBQ_BIN=str(jobq), DOCKER_PREFIX='',
               DOCKER_CMD_PREFIX='', PYTHONPATH=str(REPO))
    log_path = home / 'mission' / 'launcher-bridge.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('ab') as log:
        process = subprocess.Popen([sys.executable, '-m', 'jiuwenswarm.factory.bridge',
            '--workspace', str(root), '--queue', str(queue), '--jobq', str(jobq),
            '--inbox', str(inbox), '--seconds', '14400'], env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                if bridge_running(inbox):
                    return None  # another launcher won the finite bridge lock
                raise RuntimeError('Owned bridge exited before readiness; inspect launcher-bridge.log')
            if bridge_running(inbox):
                return process
            time.sleep(.05)
        raise TimeoutError('Owned bridge readiness missing')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = REPO.parents[1] if len(REPO.parents) > 1 else Path.cwd()
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('FACTORY_SPARK_ROOT', str(default_root))))
    parser.add_argument('--home', type=Path)
    parser.add_argument('--task', default='spark-strata-e2e-001')
    parser.add_argument('--roles', type=Path)
    parser.add_argument('--auth-file', type=Path, default=Path.home() / '.codex/auth.json')
    parser.add_argument('--jobq-dir', type=Path, default=SHARED / 'jobq')
    parser.add_argument('--jobq-bin', type=Path, default=SHARED / 'lab-source/bin/jobq')
    parser.add_argument('--bridge-dir', type=Path)
    parser.add_argument('--grant', action='append', help='subset of approved task effects; default all task effects')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    home = (args.home or root / 'mission-store').resolve()
    roles_path = (args.roles or root / 'results/mission-role-images.json').resolve()
    inbox = (args.bridge_dir or root / 'mission-ipc').resolve()
    queue, jobq = args.jobq_dir.resolve(), args.jobq_bin.resolve()
    if not (home / 'factory.sqlite').is_file():
        raise ValueError('Initialize and approve the task separately before launching a mission')
    if not queue.is_dir() or not jobq.is_file():
        raise ValueError('Existing shared queue and worker program are required')
    with Store(home) as store:
        task = store.get_task(args.task)
    grants = args.grant if args.grant is not None else task['allowed_effects']
    if set(grants) - set(task['allowed_effects']):
        raise ValueError('Launcher grants may not exceed the approved task')
    contract_path = Path(task['contract_id']).resolve()
    contract = json.loads(contract_path.read_text())
    readonly = [contract_path, Path(contract['assets']['identity_path']).resolve(),
                Path(contract['workload']['model_root']).resolve(), Path(contract['workload']['pack']).resolve()]
    roles = json.loads(roles_path.read_text())
    for role in ('agent', 'builder'):
        image = roles[role]['image_id']
        info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
        if info['Id'] != image or info['Architecture'] != 'arm64':
            raise ValueError('Admitted native role image changed: ' + role)
    os.environ.update(FACTORY_HOME=str(home), FACTORY_BRIDGE_HOME=str(home),
        FACTORY_NATIVE_BUILDER_IMAGE=roles['builder']['image_id'],
        FACTORY_JOBQ_BIN=str(jobq), JOBQ_DIR=str(queue), DOCKER_PREFIX='', DOCKER_CMD_PREFIX='',
        PYTHONPATH=str(REPO))
    # Do not route host reconciliation back through the container bridge.
    os.environ.pop('FACTORY_BRIDGE_DIR', None)
    owned_bridge = None
    previous = {}
    try:
        owned_bridge = ensure_bridge(root, home, inbox, queue, jobq)
        supervisor = Supervisor(home, args.task, roles['agent']['image_id'], root, REPO, args.auth_file,
            grants=grants, deadline_s=min(14400, task['budget']['wall_clock_s']), bridge_dir=inbox, jobq_dir=queue, jobq_bin=jobq, read_only_paths=readonly)
        def cancel(number, frame):
            raise InterruptedError('Mission launcher cancelled')
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, cancel)
        result = supervisor.run()
        print(json.dumps(result))
        return 1 if result['outcome'] == 'partial' else 0
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if owned_bridge is not None and owned_bridge.poll() is None:
            owned_bridge.terminate()
            try:
                owned_bridge.wait(timeout=5)
            except subprocess.TimeoutExpired:
                owned_bridge.kill()
                owned_bridge.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
