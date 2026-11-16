"""Finite host owner for control-container exits, quiet lab work and review.

The supervisor never chooses an experiment. It runs the real controller until
it yields durable work, proves that control stopped, releases the exact lab
barrier, reconciles attempts, and starts a fresh controller session for review.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid

from .contract import atomic_json
from .store import Store

ACTIVE = {'queued', 'running', 'cancel_requested', 'unknown'}
FINAL = {'accept', 'reject', 'report_inconclusive', 'stop_missing_prerequisite', 'partial', 'cancelled'}


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def quiet_receipt(attempt, control):
    """A Docker exit is authoritative only for the exact admitted control image."""
    if (control['State']['Running'] or control['State'].get('Pid', 0) != 0
            or control.get('HostConfig', {}).get('AutoRemove')):
        raise ValueError('Control must be inspectable and fully stopped before quiet')
    return dict(attempt_id=attempt, control_container_id=control['Id'],
                control_image=control['Image'], control_stopped=True,
                recorded_at=time.time(), boot_id=boot_id())


def mission_root(home, task):
    home = Path(home).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', task):
        raise ValueError('Invalid task id')
    legacy = home / 'mission'
    deadline = legacy / 'deadline.json'
    if deadline.exists() and json.loads(deadline.read_text()).get('task_id') == task:
        return legacy
    return home / 'missions' / task


class Supervisor:
    def __init__(self, home, task, image, workspace, source, auth_file, *, grants=(),
                 bridge_dir=None, jobq_dir=None, jobq_bin=None, deadline_s=14400,
                 read_only_paths=()):
        self.home, self.workspace, self.source = map(lambda p: Path(p).resolve(), (home, workspace, source))
        self.task, self.image, self.auth_file = task, image, Path(auth_file).resolve()
        if not re.fullmatch(r'[A-Za-z0-9_-]+', task) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            raise ValueError('Task and immutable agent image required')
        if not self.home.is_relative_to(self.workspace) or not self.source.is_relative_to(self.workspace):
            raise ValueError('Factory home/source must be inside the owned workspace')
        if not 0 < deadline_s <= 14400:
            raise ValueError('Supervisor deadline must be at most four hours')
        self.grants = list(grants)
        self.bridge_dir, self.jobq_dir, self.jobq_bin = bridge_dir, jobq_dir, jobq_bin
        self.read_only_paths = tuple(Path(p).resolve() for p in read_only_paths)
        self.deadline_s = deadline_s
        self.root = mission_root(self.home, self.task)
        self.root.mkdir(parents=True, exist_ok=True)
        self.intent_path = self.root / 'control-intent.json'
        self.control_state_path = self.root / 'control-state.json'

    def docker(self, *args, required=True):
        result = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=30)
        if required and result.returncode:
            raise RuntimeError('Docker control failed: ' + str(args[0]))
        return result

    def inspect_control(self, intent):
        found = self.docker('inspect', intent['name'], required=False)
        if found.returncode:
            return None
        info = json.loads(found.stdout)[0]
        labels = info['Config'].get('Labels') or {}
        if (info['Image'] != intent['image'] or info['Name'] != '/' + intent['name']
                or labels.get('factory.mission.nonce') != intent['nonce']
                or labels.get('factory.task') != self.task):
            raise ValueError('Control container ownership changed')
        return info

    def recover_control(self):
        if not self.intent_path.exists():
            return
        intent = json.loads(self.intent_path.read_text())
        info = self.inspect_control(intent)
        if info:
            was_running = info['State']['Running']
            if was_running:
                self.docker('stop', '--time', '10', info['Id'])
                info = self.inspect_control(intent)
                if info is None or info['State']['Running'] or info['State'].get('Pid', 0):
                    raise RuntimeError('Could not prove recovered control stopped')
            atomic_json(self.root / ('control-exit-' + intent['nonce'] + '.json'), info)
            self.docker('rm', '-f', info['Id'])
            atomic_json(self.root / ('control-recovery-' + intent['nonce'] + '.json'),
                        dict(container_id=info['Id'], was_running=was_running, removed=True))
            return info

    def control_failure(self, info, progress):
        """Reserve restart allowance durably; replaying an exit never spends twice."""
        failures = progress.setdefault('failures', [])
        if not any(f['container_id'] == info['Id'] for f in failures):
            failures.append(dict(container_id=info['Id'], exit_code=info['State']['ExitCode'],
                                 recorded_at=time.time()))
        progress['last_stopped_control'] = info
        atomic_json(self.control_state_path, progress)
        return len(failures) <= 2

    def publish_quiet(self, attempt, control):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', attempt):
            raise ValueError('Invalid quiet receipt attempt ID')
        receipt = quiet_receipt(attempt, control)
        # One agent turn can submit several durable cells. Each queue worker
        # needs its own barrier; the compatibility file alone only names one.
        atomic_json(self.root / 'quiet' / (attempt + '.json'), receipt)
        atomic_json(self.root / 'quiet.json', receipt)

    def clear_quiet(self, generation):
        (self.root / 'quiet.json').unlink(missing_ok=True)
        directory = self.root / 'quiet'
        if directory.exists():
            history = self.root / 'quiet-history'
            history.mkdir(exist_ok=True)
            directory.rename(history / (str(generation) + '-' + uuid.uuid4().hex))

    def launch_control(self, generation):
        nonce = uuid.uuid4().hex
        intent = dict(name='factory-control-' + nonce, nonce=nonce, image=self.image, task_id=self.task)
        atomic_json(self.intent_path, intent)
        auth_target = self.home / 'agent-data/subscription/codex-home/auth.json'
        auth_target.parent.mkdir(parents=True, exist_ok=True)
        if not self.auth_file.is_file():
            raise ValueError('Operator authentication file missing')
        argv = ['create', '--pull=never', '--name', intent['name'], '--read-only',
                '--workdir', '/tmp',
                '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--pids-limit=256', '--cpus=2',
                '--memory=2g', '--memory-swap=2g', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
                '--log-opt', 'max-size=8m', '--log-opt', 'max-file=2',
                '--label', 'factory.mission.nonce=' + nonce, '--label', 'factory.task=' + self.task,
                '--mount', f'type=bind,src={self.workspace},dst={self.workspace}',
                '--mount', f'type=bind,src={self.source},dst=/factory,readonly',
                '--mount', f'type=bind,src={self.auth_file},dst={auth_target},readonly']
        readonly = set(self.read_only_paths)
        if self.jobq_dir:
            readonly.add(Path(self.jobq_dir).resolve())
        if self.jobq_bin:
            readonly.add(Path(self.jobq_bin).resolve().parent.parent)
        for path in sorted(readonly):
            # Explicit nested mounts override the broader writable workspace.
            argv += ['--mount', f'type=bind,src={path},dst={path},readonly']
        environment = dict(FACTORY_HOME=str(self.home), FACTORY_WORKSPACE=str(self.home / 'agent-workspace'),
                           FACTORY_TASK_ID=self.task, FACTORY_YIELD_ON_JOBS='1',
                           FACTORY_HOST_PYTHON='/usr/bin/python3', PYTHONPATH='/factory:/opt/factory-site',
                           HOME='/tmp', JIUWENSWARM_SKIP_DOTENV='1')
        if self.bridge_dir:
            environment['FACTORY_BRIDGE_DIR'] = str(self.bridge_dir)
        if self.jobq_dir:
            environment['JOBQ_DIR'] = str(self.jobq_dir)
        if self.jobq_bin:
            environment['FACTORY_JOBQ_BIN'] = str(self.jobq_bin)
        for key in ('FACTORY_NATIVE_BUILDER_IMAGE', 'JIUWENSWARM_CODEX_MODEL'):
            if key in os.environ:
                environment[key] = os.environ[key]
        for key, value in environment.items():
            argv += ['--env', key + '=' + value]
        argv += ['--entrypoint', '/usr/bin/python3', self.image, '-m', 'jiuwenswarm.factory.cli',
                 '--home', str(self.home), 'resume' if generation else 'run', self.task]
        for grant in self.grants:
            argv += ['--grant', grant]
        self.docker(*argv)
        info = self.inspect_control(intent)
        if info is None:
            raise RuntimeError('Created control container disappeared')
        self.docker('start', info['Id'])
        return intent

    def attempts(self):
        with Store(self.home) as store:
            from .loop import owned_attempts
            return owned_attempts(store, self.task)

    def reconcile(self):
        from .manager import Manager
        with Store(self.home) as store:
            manager = Manager(store, self.home / 'lab-spool')
            for attempt in self.attempts():
                if attempt['state'] in ACTIVE:
                    manager.jobs.status(attempt['attempt_id'])
                if (attempt['kind'] == 'lab' and attempt['state'] not in ACTIVE
                        and not any(ref.endswith(':evaluation') for ref in attempt.get('result_refs', []))):
                    # Import a newly terminal result once. Rehashing historical
                    # reports every second is unnecessary work during profiling.
                    self._import_result(store, manager, attempt)

    def _import_result(self, store, manager, attempt):
        adapter = attempt.get('request', {}).get('adapter', '')
        if adapter == 'factory-experiment-v1':
            from .experiment_jobs import ExperimentJobs
            ExperimentJobs(store).result(attempt['task_id'],attempt['attempt_id'])
        elif adapter == 'strata-prefill-scoped-v1':
            if not any(ref.endswith(':observation') for ref in attempt.get('result_refs', [])):
                from .prefill_workbench import Workbench
                Workbench(store).result(attempt['task_id'], attempt['attempt_id'])
        elif adapter.startswith('strata-benchmark-') or adapter == 'strata-construction-v1':
            # Benchmark owns independent parsing and its result receipt shape.
            if not any(ref.endswith(':observation') for ref in attempt.get('result_refs', [])):
                from .benchmark import Benchmark
                Benchmark(store).result(attempt['task_id'], attempt['attempt_id'])
        else:
            manager.result(attempt['attempt_id'])

    def cancel_owned(self):
        from .manager import Manager
        errors = []
        with Store(self.home) as store:
            manager = Manager(store, self.home / 'lab-spool')
            for attempt in self.attempts():
                if attempt['state'] in ACTIVE:
                    try:
                        manager.cancel(attempt['attempt_id'])
                    except Exception as exc:
                        errors.append(dict(attempt_id=attempt['attempt_id'], error=type(exc).__name__ + ': ' + str(exc)))
        return errors

    def run(self):
        with (self.home.parent / 'factory-supervisor.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self._run()

    def _run(self):
        started = time.monotonic()
        deadline_path = self.root / 'deadline.json'
        if not deadline_path.exists():
            atomic_json(deadline_path, dict(task_id=self.task, started_at=time.time(),
                                           deadline_at=time.time() + self.deadline_s))
        durable_deadline = json.loads(deadline_path.read_text())
        if durable_deadline['task_id'] != self.task:
            raise ValueError('Mission deadline belongs to another task')
        # A restarted supervisor never renews the task's four-hour wall budget.
        remaining_s = min(self.deadline_s, durable_deadline['deadline_at'] - time.time())
        progress = json.loads(self.control_state_path.read_text()) if self.control_state_path.exists() else dict(
            generations=0, failures=[])
        generation = progress['generations']
        last_stopped = progress.get('last_stopped_control')
        intent = None
        try:
            recovered = self.recover_control()
            if recovered:
                last_stopped = recovered
                if recovered['State']['ExitCode'] != 0 and not self.control_failure(recovered, progress):
                    raise RuntimeError('Control restart allowance exhausted')
            elif self.intent_path.exists():
                # Compatibility with an earlier supervisor that already removed
                # control but retained its exact inspected exit receipt.
                prior = json.loads(self.intent_path.read_text())
                receipt = self.root / ('control-exit-' + prior['nonce'] + '.json')
                if receipt.exists():
                    found = json.loads(receipt.read_text())
                    if (found['Image'] != prior['image'] or found['Name'] != '/' + prior['name']
                            or found['State']['Running'] or found['State'].get('Pid', 0)):
                        raise ValueError('Prior control exit receipt differs from durable intent')
                    last_stopped = found
            if len(progress.get('failures', [])) > 2:
                raise RuntimeError('Control restart allowance exhausted')
            while time.monotonic() - started < remaining_s:
                self.reconcile()
                active = [a for a in self.attempts() if a['state'] in ACTIVE]
                if active:
                    # Restart path: a durable quiet receipt is safe only after
                    # this supervisor has reconciled any old control container.
                    for attempt in active:
                        if attempt['kind'] == 'lab':
                            if last_stopped is None:
                                raise RuntimeError('No inspected control exit proves lab quiet')
                            self.publish_quiet(attempt['attempt_id'], last_stopped)
                    time.sleep(1)
                    continue
                state_path = self.home / 'sessions' / (self.task + '.state.json')
                state = json.loads(state_path.read_text()) if state_path.exists() else {}
                from .operator_notes import pending
                reopen = bool(state.get('operator_notes') or pending(self.home, self.task, state)) and state.get('outcome') in {'partial','report_inconclusive','stop_missing_prerequisite'}
                if state.get('outcome') in FINAL and not reopen:
                    result = dict(task_id=self.task, outcome=state['outcome'], generations=generation,
                                  elapsed_s=time.monotonic() - started)
                    atomic_json(self.root / 'supervisor-result.json', result)
                    return result
                self.clear_quiet(generation)
                intent = self.launch_control(generation)
                while time.monotonic() - started < remaining_s:
                    info = self.inspect_control(intent)
                    if info is None:
                        raise RuntimeError('Control disappeared before exit receipt')
                    if not info['State']['Running']:
                        break
                    time.sleep(1)
                else:
                    raise TimeoutError('Mission deadline')
                info = self.inspect_control(intent)
                atomic_json(self.root / ('control-exit-' + intent['nonce'] + '.json'), info)
                last_stopped = info
                progress.update(generations=generation + 1, last_stopped_control=info)
                restart_allowed = True
                if info['State']['ExitCode'] != 0:
                    restart_allowed = self.control_failure(info, progress)
                else:
                    atomic_json(self.control_state_path, progress)
                # Docker exit includes every process in that container, including
                # its agent app-server and MCP children. No attach client remains.
                for attempt in self.attempts():
                    if attempt['state'] in ACTIVE and attempt['kind'] == 'lab':
                        self.publish_quiet(attempt['attempt_id'], info)
                self.docker('rm', info['Id'])
                intent = None
                generation += 1
                if not restart_allowed:
                    raise RuntimeError('Control restart allowance exhausted')
            raise TimeoutError('Mission deadline')
        except BaseException as exc:
            # Cleanup failures must neither strand later children nor erase the
            # original stop reason. A cancellation request is not terminal proof.
            cleanup_errors = []
            try:
                self.recover_control()
            except Exception as cleanup:
                cleanup_errors.append(dict(operation='recover_control', error=type(cleanup).__name__ + ': ' + str(cleanup)))
            try:
                cleanup_errors.extend(self.cancel_owned() or [])
            except Exception as cleanup:
                cleanup_errors.append(dict(operation='cancel_owned', error=type(cleanup).__name__ + ': ' + str(cleanup)))
            pending_attempts = None
            try:
                pending_attempts = [a['attempt_id'] for a in self.attempts() if a['state'] in ACTIVE]
            except Exception as cleanup:
                cleanup_errors.append(dict(operation='read_attempts', error=type(cleanup).__name__ + ': ' + str(cleanup)))
            result = dict(task_id=self.task, outcome='partial', error=type(exc).__name__ + ': ' + str(exc),
                          generations=generation, elapsed_s=time.monotonic() - started,
                          cleanup_errors=cleanup_errors, pending_attempts=pending_attempts,
                          cancellation_complete=not cleanup_errors and pending_attempts == [])
            atomic_json(self.root / 'supervisor-result.json', result)
            return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('home', 'task', 'image', 'workspace', 'source', 'auth-file'):
        p.add_argument('--' + field, required=True)
    for field in ('bridge-dir', 'jobq-dir', 'jobq-bin'):
        p.add_argument('--' + field)
    p.add_argument('--grant', action='append', default=[])
    p.add_argument('--read-only-path', action='append', default=[])
    p.add_argument('--deadline-s', type=float, default=14400)
    args = vars(p.parse_args())
    args['grants'] = args.pop('grant')
    args['read_only_paths'] = args.pop('read_only_path')
    supervisor = Supervisor(**args)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda number, frame: (_ for _ in ()).throw(InterruptedError('Supervisor cancelled')))
    result = supervisor.run()
    print(json.dumps(result))
    return 1 if result['outcome'] == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
