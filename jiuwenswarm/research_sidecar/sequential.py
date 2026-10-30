"""One persistent sequential queue over the public authenticated research API.

Execution and collection are separate. A claimed submission is *only* reconciled
after interruption, even when the server cannot yet find it. Results are never
scientific judgements; the app's actual observations are retained for a person.
"""
import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import sys
import tempfile
import uuid

import httpx

from .client import ClientError, ResearchClient
from .evidence import canonical, relative, _evidence_directory as _custody_directory
from .ledger import Ledger
from .reconcile import submit_once
from .sequential_cases import identifier, load_cases, SECRET_NAME, DEFAULT_LIMITS

TERMINAL = {'completed', 'partial', 'halted', 'cancelled', 'failed', 'blocked', 'interrupted'}
LOCAL_TERMINAL = TERMINAL | {'preparation_failed', 'not_submitted', 'timed_out'}
OWNER = 'ai4r-sequential-runner:1'


def _evidence_directory(path):
    return _custody_directory(path, portable=True)


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def safe_path(path, *, directory=False):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink paths are not permitted: ' + str(path))
    path = path.resolve(strict=True)
    if directory and not path.is_dir():
        raise ValueError('directory required: ' + str(path))
    return path


def bounded_file(path, max_bytes):
    path = safe_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > max_bytes:
        raise ValueError('one bounded regular file required: ' + str(path))
    return path


def digest(path):
    value = hashlib.sha256(); size = 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b''):
            value.update(chunk); size += len(chunk)
    return {'sha256': value.hexdigest(), 'size': size}


def atomic(path, value, *, exclusive=False):
    """Durably publish only into an already owned tree; reject symlink parents."""
    path = Path(path); _evidence_directory(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('unsafe output target')
    raw = value if isinstance(value, bytes) else canonical(value)
    fd, temporary = tempfile.mkstemp(prefix='.publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path); os.unlink(temporary)
        else:
            os.replace(temporary, path)
        if os.name == 'posix':
            directory = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def read_json(path):
    return json.loads(bounded_file(path, 32 * 1024 * 1024).read_bytes())


def _mount_for(path):
    """Find actual Linux mount flags without requiring a container Docker socket."""
    mounts = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split(); mount = fields[4]
        for encoded, character in (('\\040', ' '), ('\\011', '\t'), ('\\134', '\\')):
            mount = mount.replace(encoded, character)
        root = Path(mount)
        if path == root or path.is_relative_to(root):
            mounts.append((len(root.parts), root, fields[5].split(',')))
    return max(mounts, key=lambda x: x[0]) if mounts else None


def validate_roots(cases, inputs, output):
    cases = bounded_file(cases, 16 * 1024 * 1024)
    inputs = safe_path(inputs, directory=True); output = safe_path(output, directory=True)
    for left, right in ((cases.parent, output), (inputs, output)):
        if left == right or left.is_relative_to(right) or right.is_relative_to(left):
            raise ValueError('case/input and output roots must not overlap')
    # Container-local output would disappear on removal. Mounted inputs/cases
    # must really be read-only; a command-line claim is insufficient.
    if os.name == 'posix' and Path('/.dockerenv').exists():
        for path, readonly in ((cases, True), (inputs, True), (output, False)):
            observed = _mount_for(path)
            if observed is None or str(observed[1]) == '/' or ('ro' in observed[2]) != readonly:
                raise ValueError('explicit read-only case/input mounts and writable output mount required: ' + str(path))
    probe = output / ('.ai4r-write-probe-' + uuid.uuid4().hex)
    try:
        atomic(probe, b'output mount write probe', exclusive=True)
        if probe.read_bytes() != b'output mount write probe': raise OSError('output probe read mismatch')
    finally:
        if probe.exists(): probe.unlink()
    return cases, inputs, output


@contextmanager
def campaign_lock(folder):
    """OS-owned lock releases after process death, unlike stale PID claims."""
    path = folder / '.runner.lock'
    if path.is_symlink(): raise ValueError('unsafe campaign lock')
    stream = open(path, 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
            try: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError: raise ValueError('campaign is already controlled by another runner') from None
        else:
            import fcntl
            try: fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('campaign is already controlled by another runner') from None
        yield
    finally:
        stream.close()


def load_campaign(folder):
    folder = safe_path(folder, directory=True)
    owner = read_json(folder / '.runner-owner.json')
    campaign = read_json(folder / 'campaign.json')
    if owner != {'owner': OWNER, 'campaign_id': campaign['campaign_id']} or campaign.get('schema_version') != 'sequential-campaign:1':
        raise ValueError('foreign campaign or incompatible campaign version')
    expected = {case['id'] + '-r' + str(repeat): (case['id'], repeat)
                for case in campaign['cases'] for repeat in range(1, case['repeats'] + 1)}
    runs = folder / 'runs'
    if runs.is_symlink(): raise ValueError('unsafe campaign run directory')
    actual = {path.parent.name for path in runs.glob('*/run_record.json')}
    if actual != set(expected):
        raise ValueError('campaign creation is incomplete or run inventory changed; no submission is permitted; retain this folder and use a new campaign ID')
    for ident, (case_id, repeat) in expected.items():
        record = read_json(runs / ident / 'run_record.json')
        if (record.get('campaign_id'), record.get('case_id'), record.get('repeat_index'), record.get('run_id')) != (campaign['campaign_id'], case_id, repeat, ident):
            raise ValueError('campaign run record identity differs from the frozen queue')
    return folder, campaign


def create_campaign(cases, inputs, output, *, campaign_id, endpoint, expected_build, http_authority=None):
    cases, inputs, output = validate_roots(cases, inputs, output)
    document = load_cases(cases); identifier(campaign_id)
    if not expected_build: raise ValueError('expected app build identity is required')
    # Validate all explicitly selected input bytes before creating any result.
    inventory = {}
    for case in document['cases']:
        for row in case['inputs']:
            path = bounded_file(inputs / relative(row['path']), case['limits']['max_artifact_bytes'])
            if not path.is_relative_to(inputs): raise ValueError('input escaped selected root')
            inventory[row['path']] = digest(path)
    folder = output / campaign_id
    folder.mkdir(mode=0o750)  # Never adopt/overwrite an existing user folder.
    atomic(folder / '.runner-owner.json', {'owner': OWNER, 'campaign_id': campaign_id}, exclusive=True)
    campaign = {'schema_version': 'sequential-campaign:1', 'campaign_id': campaign_id,
                'created_at': utc(), 'endpoint': endpoint, 'expected_build': expected_build, 'http_authority': http_authority,
                'case_file': str(cases), 'case_file_sha256': digest(cases)['sha256'],
                'inputs_root': str(inputs), 'output_root': str(output), 'input_inventory': inventory,
                **document}
    campaign['schema_version'] = 'sequential-campaign:1'
    atomic(folder / 'campaign.json', campaign, exclusive=True)
    atomic(folder / 'campaign_state.json', {'state': 'queued', 'updated_at': utc(), 'active_run': None}, exclusive=True)
    for case in document['cases']:
        for repeat in range(1, case['repeats'] + 1):
            ident = case['id'] + '-r' + str(repeat)
            record = {'schema_version': 'sequential-run:1', 'campaign_id': campaign_id, 'case_id': case['id'],
                      'repeat_index': repeat, 'run_id': ident, 'request_id': 'request-' + uuid.uuid4().hex,
                      'app_run_id': None, 'task': case['task'], 'inputs': [], 'setup': case['setup'],
                      'steps': case['steps'], 'collection': case['collection'], 'limits': case['limits'],
                      'execution_state': 'queued', 'collection_state': 'pending', 'created_at': utc(),
                      'submitted_at': None, 'ended_at': None, 'status': None, 'artifacts': [], 'commands': [],
                      'errors': [], 'observations': {'metrics': None, 'missing_metrics': ['CPU', 'memory', 'GPU', 'model_usage'],
                          'sampling_scope': 'app-exposed run events; no host attribution or zero inference'}, 'submission': None}
            atomic(folder / 'runs' / ident / 'run_record.json', record, exclusive=True)
    return folder, campaign


class SequentialRunner:
    def __init__(self, client, folder, campaign, *, progress=None):
        self.client, self.folder, self.campaign = client, Path(folder), campaign
        self.ledger = Ledger(self.folder / 'ledger.sqlite')
        self.progress = progress or (lambda value: print(value, file=sys.stderr, flush=True))
        authorization = getattr(getattr(client, 'http', None), 'headers', {}).get('Authorization', '')
        self.secrets = {authorization, authorization.removeprefix('Bearer ')} - {''}
        for case in campaign['cases']:
            for phase in ('setup', 'steps', 'collection'):
                for command in case[phase]:
                    for key, value in command['env'].items():
                        if isinstance(value, dict) and (SECRET_NAME.search(key) or SECRET_NAME.search(value['from_env'])):
                            secret = os.environ.get(value['from_env'])
                            if secret: self.secrets.add(secret)

    def redact(self, value):
        if isinstance(value, str):
            for secret in sorted(self.secrets, key=len, reverse=True): value = value.replace(secret, '[REDACTED]')
            return value
        if isinstance(value, list): return [self.redact(item) for item in value]
        if isinstance(value, dict): return {key: self.redact(item) for key, item in value.items()}
        return value

    def close(self): self.ledger.close()

    def rows(self):
        for case in self.campaign['cases']:
            for repeat in range(1, case['repeats'] + 1):
                ident = case['id'] + '-r' + str(repeat)
                yield case, read_json(self.folder / 'runs' / ident / 'run_record.json')

    def save(self, row, kind='snapshot'):
        event = {key: row.get(key) for key in ('request_id', 'app_run_id', 'execution_state', 'collection_state')}
        event['recorded_at'] = utc()
        if kind in {'status_observed', 'execution_terminal'}: event['status'] = row.get('status')
        if kind.startswith('command_'): event['command'] = row['commands'][-1]
        if kind in {'collection_failure', 'app_access_failure', 'infrastructure_failure'}: event['error'] = row['errors'][-1]
        if kind == 'artifact_collected': event['artifact'] = row['artifacts'][-1]
        if kind == 'events_observed': event['events'] = row['observations'].get('events')
        self.ledger.event(row['run_id'], kind, self.redact(event))
        atomic(self.folder / 'runs' / row['run_id'] / 'run_record.json', self.redact(row))

    def state(self, state, active=None, reason=None):
        atomic(self.folder / 'campaign_state.json', {'state': state, 'updated_at': utc(), 'active_run': active, 'reason': reason})

    def cancellation_signal(self):
        path = self.folder / 'cancellation_requested.json'
        return read_json(path) if path.exists() else None

    def acknowledge_cancellation(self):
        signal = self.cancellation_signal()
        if signal:
            atomic(self.folder / 'cancellation_requested.json', {**signal, 'handled': True, 'handled_at': utc()})

    def error(self, row, category, error):
        # API errors deliberately omit request headers and credentials.
        detail = str(error) if not isinstance(error, httpx.HTTPError) else type(error).__name__
        detail = detail or type(error).__name__  # a bare TimeoutError has no message
        row['errors'].append({'at': utc(), 'category': category, 'detail': detail[:4000]})
        self.save(row, category)

    async def readiness(self):
        value = await self.client.readiness()
        if not value.get('ready') or value.get('build_id') != self.campaign['expected_build']:
            raise ValueError('app is not ready or expected build identity differs; running target must not be patched')
        pins = {'build_id': value['build_id'], 'client_contract_version': value.get('client_contract_version'), 'pins': value.get('pins')}
        path = self.folder / 'target_identity.json'
        if path.exists() and read_json(path) != pins: raise ValueError('pinned target identity changed; start a new campaign')
        if not path.exists(): atomic(path, pins, exclusive=True)
        return value

    def workspace(self, row):
        path = self.folder / 'runs' / row['run_id'] / 'workspace'
        _evidence_directory(path)
        return path

    async def commands(self, case, row, phase):
        workspace = self.workspace(row); limits = case['limits']
        for command in case[phase]:
            identity = phase + ':' + command['id']
            old = next((v for v in row['commands'] if v['id'] == identity), None)
            if old:
                if old['state'] != 'complete':
                    raise ValueError('interrupted trusted command requires human action; it will not be re-executed: ' + identity)
                if old['exit_code'] != 0: return False
                continue
            cwd = workspace if command['cwd'] == '.' else workspace / relative(command['cwd'])
            _evidence_directory(cwd)
            stdout_path = self.folder / 'runs' / row['run_id'] / 'commands' / (phase + '-' + command['id'] + '.stdout')
            stderr_path = stdout_path.with_suffix('.stderr'); _evidence_directory(stdout_path.parent)
            receipt = {'id': identity, 'phase': phase, 'command': command['command'], 'cwd': command['cwd'],
                       'state': 'started', 'started_at': utc(), 'ended_at': None, 'exit_code': None,
                       'timed_out': False, 'stdout': str(stdout_path.relative_to(self.folder / 'runs' / row['run_id'])),
                       'stderr': str(stderr_path.relative_to(self.folder / 'runs' / row['run_id'])),
                       'allowed_env_names': sorted(command['env']), 'resource_limits': limits}
            row['commands'].append(receipt); self.save(row, 'command_started')
            allowed = {}
            for key, value in command['env'].items():
                if isinstance(value, dict):
                    if value['from_env'] not in os.environ: raise ValueError('required allowed environment reference unavailable: ' + value['from_env'])
                    allowed[key] = os.environ[value['from_env']]
                else: allowed[key] = value
            env = {'PATH': ('/usr/local/bin:' if os.name == 'posix' else '') + os.defpath,
                   'HOME': str(workspace), 'TMPDIR': str(workspace), 'LANG': 'C.UTF-8', **allowed}
            if os.name == 'nt': env.update({k: os.environ[k] for k in ('SystemRoot', 'WINDIR') if k in os.environ})
            def bound_resources():
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (limits['command_memory_mb'] * 1024 * 1024,) * 2)
                resource.setrlimit(resource.RLIMIT_CPU, (limits['command_cpu_s'],) * 2)
                resource.setrlimit(resource.RLIMIT_FSIZE, (limits['max_artifact_bytes'],) * 2)
                resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
            kwargs = {'start_new_session': True, 'preexec_fn': bound_resources} if os.name == 'posix' else {}
            process = await asyncio.create_subprocess_exec(*command['command'], cwd=cwd, env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **kwargs)
            receipt['pid'] = process.pid; self.save(row, 'command_spawned')
            async def capture(stream, path):
                total = 0; truncated = False; pending = b''
                secrets = [value.encode() for value in self.secrets]
                carry = max((len(value) for value in secrets), default=1) - 1
                with open(path, 'xb') as output:
                    while True:
                        chunk = await stream.read(65536)
                        pending += chunk
                        if not chunk:
                            safe = pending
                            for secret in secrets: safe = safe.replace(secret, b'[REDACTED]')
                        else:
                            # Keep enough original bytes for secrets spanning reads.
                            split = max(0, len(pending) - carry)
                            # Never split a secret that starts before the boundary.
                            for secret in secrets:
                                start = pending.find(secret, max(0, split - len(secret) + 1))
                                if 0 <= start < split: split = start
                            safe, pending = pending[:split], pending[split:]
                            for secret in secrets: safe = safe.replace(secret, b'[REDACTED]')
                        keep = safe[:max(0, limits['max_log_bytes'] - total)]
                        output.write(keep); total += len(keep)
                        truncated |= len(keep) != len(safe)
                        if not chunk: break
                    output.flush(); os.fsync(output.fileno())
                return truncated
            captures = [asyncio.create_task(capture(process.stdout, stdout_path)), asyncio.create_task(capture(process.stderr, stderr_path))]
            try:
                await asyncio.wait_for(process.wait(), min(command['timeout_s'], limits['command_timeout_s']))
            except (TimeoutError, asyncio.CancelledError) as error:
                receipt['timed_out'] = isinstance(error, TimeoutError)
                if os.name == 'posix': os.killpg(process.pid, signal.SIGKILL)
                else: process.kill()
                await process.wait()
                if isinstance(error, asyncio.CancelledError):
                    await asyncio.gather(*captures); raise
            receipt['log_truncated'] = await asyncio.gather(*captures)
            receipt.update(state='complete', ended_at=utc(), exit_code=process.returncode)
            receipt['stdout_file'] = digest(stdout_path); receipt['stderr_file'] = digest(stderr_path)
            self.scan_workspace(workspace, limits)
            for output in command['outputs']:
                path = bounded_file(workspace / relative(output), limits['max_artifact_bytes'])
                row['artifacts'].append({'path': 'workspace/' + output, 'source': 'trusted_command', **digest(path)})
            self.save(row, 'command_completed')
            if process.returncode != 0: return False
        return True

    @staticmethod
    def scan_workspace(workspace, limits):
        total = 0; count = 0
        for path in workspace.rglob('*'):
            if path.is_symlink(): raise ValueError('trusted command produced a symlink')
            if path.is_dir(): continue
            bounded_file(path, limits['max_artifact_bytes']); count += 1; total += path.stat().st_size
            if count > limits['max_files'] or total > limits['max_total_bytes']:
                raise ValueError('trusted workspace exceeds campaign disk/file bounds')

    async def prepare(self, case, row):
        row['execution_state'] = 'preparing'; self.save(row)
        workspace = self.workspace(row); inputs = Path(self.campaign['inputs_root'])
        for declared in case['inputs']:
            source = bounded_file(inputs / relative(declared['path']), case['limits']['max_artifact_bytes'])
            expected = self.campaign['input_inventory'][declared['path']]
            if digest(source) != expected: raise ValueError('supplied input changed after campaign creation')
            destination = workspace / 'inputs' / relative(declared['destination']); _evidence_directory(destination.parent)
            if destination.exists():
                if digest(bounded_file(destination, case['limits']['max_artifact_bytes'])) != expected:
                    raise ValueError('workspace input evidence changed')
            else:
                fd, temporary = tempfile.mkstemp(prefix='.input-', dir=destination.parent)
                try:
                    with os.fdopen(fd, 'wb') as output, source.open('rb') as incoming:
                        shutil.copyfileobj(incoming, output, 65536); output.flush(); os.fsync(output.fileno())
                    if digest(temporary) != expected: raise ValueError('input changed while being copied')
                    os.link(temporary, destination)
                finally: os.unlink(temporary)
            if not any(v['path'] == declared['path'] for v in row['inputs']):
                row['inputs'].append({**declared, **expected, 'upload_record': None})
        self.save(row, 'inputs_prepared')
        if not await self.commands(case, row, 'setup') or not await self.commands(case, row, 'steps'):
            row['execution_state'] = 'preparation_failed'; row['ended_at'] = utc(); self.save(row); return False
        context = await self.client.context(); workspace_id = context['defaults']['workspace_id']
        for item in row['inputs']:
            if item['upload'] and item['upload_record'] is None:
                upload = await self.client.upload(item['kind'], workspace_id, workspace / 'inputs' / relative(item['destination']))
                if upload['content_sha256'] != item['sha256'] or upload['size_bytes'] != item['size']:
                    raise ValueError('uploaded bytes differ from selected input')
                item['upload_record'] = upload; self.save(row, 'input_uploaded')
        if row.get('intake') is None:
            row['intake'] = await self.client.prepare_intake(case['task'], [v['upload_record']['id'] for v in row['inputs'] if v['upload']], workspace_id=workspace_id)
            self.save(row, 'intake_prepared')
        intake = row['intake']
        if not intake.get('qualified'):
            row['execution_state'] = 'blocked'; row['ended_at'] = utc()
            row['errors'].append({'at': utc(), 'category': 'human_action_required', 'detail': intake})
            self.save(row); return False
        row['submission'] = {**intake['submission_defaults'], 'client_request_id': row['request_id'], 'intake_ref': intake['intake_ref']}
        if 'plan_source' in case:
            row['submission']['plan_source'] = case['plan_source']
        self.save(row, 'submission_prepared'); return True

    def observe_status(self, row, value):
        if not isinstance(value, dict) or value.get('client_request_id') != row['request_id']:
            raise ValueError('status/request identity mismatch')
        if row['app_run_id'] and value.get('run_id') != row['app_run_id']:
            raise ValueError('app run identity changed')
        previous = row.get('status')
        if previous and value.get('revision', -1) < previous.get('revision', 0):
            raise ValueError('stale app status revision')
        row['app_run_id'] = value.get('run_id'); row['status'] = value
        row['execution_state'] = value.get('status', 'unknown') if row['app_run_id'] else 'unknown'
        if previous != value: self.save(row, 'status_observed')

    async def reconcile(self, row):
        try:
            self.observe_status(row, await self.client.reconcile(row['request_id']))
            return row['app_run_id'] is not None
        except ClientError as error:
            if error.status_code != 404: raise
            row['execution_state'] = 'unknown'; self.save(row, 'request_not_found')
            return False

    async def observe(self, case, row):
        limit = case['limits']; submitted = datetime.fromisoformat(row['submitted_at'].replace('Z', '+00:00'))
        deadline = submitted.timestamp() + limit['deadline_s']
        if case.get('deadline_at'):
            deadline = min(deadline, datetime.fromisoformat(case['deadline_at'].replace('Z', '+00:00')).timestamp())
        cancel_deadline = None
        while True:
            value = await self.client.status(row['app_run_id']); self.observe_status(row, value)
            await self.capture_events(case, row)
            if row['execution_state'] in TERMINAL:
                row['ended_at'] = utc(); self.save(row, 'execution_terminal'); return True
            # paused is not a safe terminal state: research may still resume.
            if row['execution_state'] == 'paused':
                self.state('paused', row['run_id'], 'app requires human action; no next dispatch'); return False
            current = datetime.now(timezone.utc).timestamp()
            if current >= deadline or row.get('cancel_requested_at') or (self.cancellation_signal() or {}).get('handled') is False:
                if not row.get('cancel_requested_at'):
                    row['cancel_requested_at'] = utc(); row['cancellation_request_id'] = 'cancel-' + uuid.uuid4().hex
                    self.save(row, 'cancel_requested')
                    row['cancellation'] = await self.client.cancel(row['app_run_id'], row['cancellation_request_id'])
                    self.save(row, 'cancel_acknowledged')
                cancel_deadline = cancel_deadline or current + limit['cancel_grace_s']
                if current >= cancel_deadline:
                    row['execution_state'] = 'cancellation_pending'; self.save(row)
                    self.state('paused', row['run_id'], 'cancellation is unresolved; no next dispatch'); return False
            await asyncio.sleep(limit['poll_s'])

    async def capture_events(self, case, row):
        observations = row['observations']
        if observations.get('event_log_truncated'): return
        for _ in range(case['limits']['max_files']):
            cursor = observations.get('event_cursor', 0)
            try: page = await self.client.events(row['app_run_id'], after=cursor)
            except ClientError as error:
                if error.status_code not in {404, 405, 501}: raise
                observations['events_unavailable'] = error.status_code; self.save(row); return
            raw = canonical(self.redact(page))
            if observations.get('event_bytes', 0) + len(raw) > case['limits']['max_log_bytes']:
                observations['event_log_truncated'] = True
                observations['event_log_note'] = 'Declared event log byte bound reached; missing observations are not zero usage.'
                self.save(row, 'events_bounded'); return
            if page.get('metrics') is not None: observations['metrics'] = page['metrics']
            next_cursor = page.get('next_after', cursor)
            if next_cursor < cursor: raise ValueError('event cursor moved backwards')
            if not page.get('events'):
                self.save(row); return
            if next_cursor == cursor: raise ValueError('nonempty event page did not advance cursor')
            name = 'events/' + str(cursor) + '-' + hashlib.sha256(raw).hexdigest() + '.json'
            path = self.folder / 'runs' / row['run_id'] / name
            if path.exists():
                if path.read_bytes() != raw: raise ValueError('saved event bytes changed')
            else: atomic(path, raw, exclusive=True)
            observations.setdefault('event_files', []).append({'path': name, **digest(path)})
            observations['event_bytes'] = observations.get('event_bytes', 0) + len(raw)
            observations['event_cursor'] = next_cursor
            self.save(row, 'events_observed')
        observations['event_log_truncated'] = True
        self.save(row, 'events_bounded')

    async def collect(self, case, row):
        # Older frozen campaigns predate the archive-member bound. Defaults
        # extend collection transport only; their task/request bytes stay exact.
        limits = {**DEFAULT_LIMITS, **case['limits']}; run_folder = self.folder / 'runs' / row['run_id']
        row['collection_state'] = 'collecting'; self.save(row)
        try:
            await self.capture_events(case, row)
            manifest_path = run_folder / 'collection_manifest.json'
            if manifest_path.exists():
                manifest = read_json(manifest_path)
                if manifest.get('run_id') != row['app_run_id']:
                    raise ValueError('saved collection manifest run identity differs')
                content = {key: value for key, value in manifest.items() if key != 'manifest_sha256'}
                if hashlib.sha256(canonical(content)).hexdigest() != manifest.get('manifest_sha256'):
                    raise ValueError('saved collection manifest identity changed')
            else:
                manifest = await self.client.artifacts(row['app_run_id'])
                atomic(manifest_path, manifest, exclusive=True)
            if manifest.get('execution_terminal') is not True:
                raise ValueError('artifact export does not confirm terminal execution; dispatch remains paused')
            files = manifest['artifacts']; names = set(); total = 0
            if not isinstance(files, list) or len(files) > limits['archive_member_limit']:
                raise ValueError('artifact archive member count exceeded')
            for item in files:
                name = str(relative(item['path']))
                if name in names or type(item['size']) is not int or item['size'] < 0 or item['size'] > limits['max_artifact_bytes']:
                    raise ValueError('duplicate, invalid or oversized artifact')
                names.add(name); total += item['size']
                if total > limits['max_total_bytes']: raise ValueError('artifact total bytes exceeded')
            if case.get('collection_mode', 'auto') == 'archive' or len(files) > min(128, limits['max_files']):
                if limits['max_files'] < 2:
                    raise ValueError('archive collection requires two physical files for original archive and verified inventory')
                from .archive_collection import collect_archive
                destination = run_folder / 'artifacts' / 'originals.zip'; _evidence_directory(destination.parent)
                retained = {item['path'] for item in row['artifacts'] if item.get('source', '').startswith('app')}
                base_paths = {'artifacts/originals.zip', 'artifacts/originals.inventory.json'}
                physical_reserved = len(retained | base_paths)
                if physical_reserved > limits['max_files']:
                    raise ValueError('retained verified evidence leaves insufficient physical file budget for archive collection')
                collected = await collect_archive(self.client, row['app_run_id'], manifest, destination,
                    max_archive_bytes=limits['max_total_bytes'], max_total_bytes=limits['max_total_bytes'],
                    max_member_bytes=limits['max_artifact_bytes'], max_members=limits['archive_member_limit'],
                    max_extract_files=min(32, limits['max_files'] - physical_reserved),
                    max_extract_bytes=min(4 * 1024 * 1024, limits['max_total_bytes']))
                records = [(collected['archive'], 'app_archive'), (collected['inventory'], 'app_archive_inventory')]
                records.extend((item, 'app_extracted') for item in collected['extracted'])
                for item, source in records:
                    target = bounded_file(item['path'], limits['max_total_bytes'])
                    if not target.is_relative_to(run_folder): raise ValueError('archive collection escaped owned run folder')
                    saved = {**item, 'path': target.relative_to(run_folder).as_posix(), 'source': source}
                    retained.add(saved['path'])
                    if len(retained) > limits['max_files']: raise ValueError('physical collected file count exceeded')
                    if saved not in row['artifacts']: row['artifacts'].append(saved)
                row['archive_collection'] = {key: collected[key] for key in ('verified_members', 'total_uncompressed_bytes')}
                row['archive_collection']['limits'] = {key: limits[key] for key in ('max_files', 'archive_member_limit', 'max_total_bytes', 'max_artifact_bytes')}
                self.save(row, 'archive_collected')
            else:
                for item in files:
                    name = str(relative(item['path']))
                    destination = run_folder / 'artifacts' / relative(name); _evidence_directory(destination.parent)
                    if destination.exists():
                        if digest(bounded_file(destination, limits['max_artifact_bytes'])) != {'sha256': item['sha256'], 'size': item['size']}:
                            raise ValueError('existing verified evidence conflicts with app artifact; never overwrite')
                    else:
                        await self.client.download_artifact(row['app_run_id'], item['artifact_id'], destination,
                            sha256=item['sha256'], size=item['size'], max_bytes=limits['max_artifact_bytes'])
                        if digest(bounded_file(destination, limits['max_artifact_bytes'])) != {'sha256': item['sha256'], 'size': item['size']}:
                            raise ValueError('downloaded artifact bytes do not match manifest')
                    saved = {'path': 'artifacts/' + name, 'artifact_id': item['artifact_id'], 'sha256': item['sha256'], 'size': item['size'], 'source': 'app'}
                    if saved not in row['artifacts']: row['artifacts'].append(saved)
                    self.save(row, 'artifact_collected')
            if not await self.commands(case, row, 'collection'):
                raise ValueError('declared collection command did not complete successfully; retained execution is unchanged')
            row['collection_confirmation'] = await self.client.confirm_collection(row['app_run_id'], manifest['manifest_sha256'], files)
            row['collection_state'] = 'complete'; self.save(row, 'collection_complete'); return True
        except (OSError, ValueError, httpx.HTTPError, TimeoutError) as error:
            row['collection_state'] = 'failed'; self.error(row, 'collection_failure', error)
            self.state('paused', row['run_id'], 'artifact collection incomplete; resume retries collection without execution')
            return False

    async def run(self):
        await self.readiness()
        self.state('running')
        failures = False
        for case, row in self.rows():
            if row['collection_state'] == 'complete':
                failures |= row['execution_state'] != 'completed'; continue
            self.state('running', row['run_id']); self.progress(row['run_id'] + ': ' + row['execution_state'])
            try:
                # Claim may predate the last snapshot. The ledger is authoritative
                # about whether a request could have left this process.
                claimed = bool(row['submission'] and self.ledger.claimed(row['run_id'], row['submission']))
                cancellation = self.cancellation_signal()
                if cancellation and not cancellation['handled'] and not claimed:
                    self.acknowledge_cancellation()
                    self.state('paused', reason='campaign cancellation stopped queued dispatch'); return 3
                if claimed and row['execution_state'] not in TERMINAL:
                    if not await self.reconcile(row):
                        self.state('paused', row['run_id'], 'request delivery unknown; reconcile before any dispatch'); return 3
                if row['execution_state'] in {'queued', 'preparing', 'submitting'} and not claimed:
                    if row['submission'] is None and not await self.prepare(case, row):
                        failures = True
                        row['collection_state'] = 'not_applicable'; self.save(row)
                        if self.campaign['policy'] == 'stop': self.state('stopped', row['run_id'], 'preparation or intake blocked'); return 2
                        continue
                    if case.get('deadline_at') and datetime.now(timezone.utc) >= datetime.fromisoformat(case['deadline_at'].replace('Z', '+00:00')):
                        row.update(execution_state='timed_out', collection_state='not_applicable', ended_at=utc())
                        row['errors'].append({'at': utc(), 'category': 'deadline', 'detail': 'absolute case deadline expired before dispatch'})
                        self.save(row, 'deadline_before_dispatch'); failures = True
                        if self.campaign['policy'] == 'stop': self.state('stopped', row['run_id'], 'deadline expired'); return 2
                        continue
                    row['submitted_at'] = utc(); row['execution_state'] = 'submitting'; self.save(row, 'dispatch_planned')
                    await self.readiness()
                    if (self.cancellation_signal() or {}).get('handled') is False:
                        row['execution_state'] = 'preparing'; self.save(row, 'dispatch_cancelled_before_claim')
                        self.acknowledge_cancellation()
                        self.state('paused', row['run_id'], 'cancellation stopped dispatch after preparation'); return 3
                    response = await submit_once(self.client, row['submission'], self.ledger, row['run_id'])
                    if not response.get('run_id'):
                        row['execution_state'] = 'unknown'; self.save(row)
                        self.state('paused', row['run_id'], 'request delivery unknown; no resubmission'); return 3
                    self.observe_status(row, response)
                if row['execution_state'] in {'preparation_failed', 'blocked', 'not_submitted', 'timed_out'} and not row['app_run_id']:
                    failures = True; continue
                if not row['app_run_id']:
                    self.state('paused', row['run_id'], 'execution unresolved; human action required'); return 3
                if row['execution_state'] not in TERMINAL and not await self.observe(case, row): return 3
                if not await self.collect(case, row): return 3
                from .human_reports import build_human_reports
                build_human_reports(self.folder)
                if cancellation and not cancellation['handled'] or ((self.cancellation_signal() or {}).get('handled') is False):
                    self.acknowledge_cancellation()
                    self.state('paused', row['run_id'], 'requested cancellation observed and collected; resume explicitly continues queued tasks'); return 3
                failures |= row['execution_state'] != 'completed'
                if row['execution_state'] != 'completed' and self.campaign['policy'] == 'stop':
                    self.state('stopped', row['run_id'], 'app execution did not complete'); return 2
            except ClientError as error:
                self.error(row, 'app_access_failure', error)
                # A definitive pre-dispatch refusal is preserved, but shared
                # auth/storage/configuration failures pause the entire queue.
                self.state('paused', row['run_id'], 'app access or supported interface unavailable'); return 2
            except (OSError, ValueError, httpx.HTTPError, TimeoutError) as error:
                self.error(row, 'infrastructure_failure', error)
                self.state('paused', row['run_id'], 'shared storage/access or execution state needs reconciliation'); return 3
        self.state('complete'); return 2 if failures else 0

    async def cancel(self):
        # Reconcile every dispatched unfinished request before acting. A failed
        # response never means cancellation finished or permits another task.
        for _, row in self.rows():
            claimed = bool(row['submission'] and self.ledger.claimed(row['run_id'], row['submission']))
            if not claimed or row['execution_state'] in TERMINAL: continue
            if not await self.reconcile(row):
                self.state('paused', row['run_id'], 'request delivery unknown; cancellation cannot be confirmed'); return 3
            if row['execution_state'] in TERMINAL: continue
            row['cancel_requested_at'] = row.get('cancel_requested_at') or utc()
            row['cancellation_request_id'] = row.get('cancellation_request_id') or 'cancel-' + uuid.uuid4().hex
            self.save(row, 'cancel_requested')
            row['cancellation'] = await self.client.cancel(row['app_run_id'], row['cancellation_request_id'])
            self.save(row, 'cancel_acknowledged')
            self.observe_status(row, await self.client.status(row['app_run_id']))
            self.state('paused', row['run_id'], 'cancel requested; resume observes terminal state and collects before dispatch')
            return 0 if row['execution_state'] in TERMINAL else 3
        self.acknowledge_cancellation()
        self.state('paused', reason='no active execution; resume explicitly continues queued tasks'); return 0


def snapshot(folder, campaign):
    return {'campaign_id': campaign['campaign_id'], **read_json(folder / 'campaign_state.json'),
            'runs': [read_json(p) for p in sorted((folder / 'runs').glob('*/run_record.json'))]}


def cleanup_owned(folder, campaign):
    """Remove only owned disposable workspaces; preserve all files and evidence."""
    state = read_json(folder / 'campaign_state.json')
    rows = [read_json(p) for p in (folder / 'runs').glob('*/run_record.json')]
    if any((v['app_run_id'] or v['execution_state'] in {'submitting', 'unknown', 'cancellation_pending'})
           and (v['execution_state'] not in TERMINAL or v['collection_state'] != 'complete') for v in rows):
        raise ValueError('cleanup refuses active, unknown or uncollected app data')
    # Workspaces contain captured command outputs and inputs referenced by reports;
    # retain them. Only uncommitted atomic staging files can be disposable.
    removed = []
    for path in folder.rglob('.publish-*'):
        path = safe_path(path)
        if not path.is_relative_to(folder) or not path.is_file(): raise ValueError('foreign cleanup target')
        path.unlink(); removed.append(str(path.relative_to(folder)))
    return {'campaign_id': campaign['campaign_id'], 'removed_staging_files': removed, 'results_retained': True,
            'containers': 'use the owned Compose host helper; runner has no Docker socket'}


def parser():
    result = argparse.ArgumentParser(prog='benchmark-runner', description=__doc__)
    sub = result.add_subparsers(dest='command', required=True)
    for name in ('doctor', 'run', 'status', 'resume', 'cancel', 'export', 'cleanup'):
        item = sub.add_parser(name); item.add_argument('--json', action='store_true')
        if name in {'doctor', 'run'}:
            item.add_argument('--cases', required=True); item.add_argument('--inputs', required=True); item.add_argument('--output', required=True)
            item.add_argument('--campaign-id', default=None)
        else: item.add_argument('--campaign-dir', required=True)
        if name in {'doctor', 'run', 'resume', 'cancel'}:
            item.add_argument('--endpoint', default=os.environ.get('AI4R_ENDPOINT'))
            item.add_argument('--http-authority', default=os.environ.get('AI4R_HTTP_AUTHORITY'),
                              help='HTTP virtual-host authority when connecting through a private network endpoint')
            item.add_argument('--token-file', default=os.environ.get('AI4R_TOKEN_FILE'))
            item.add_argument('--expected-build', default=os.environ.get('AI4R_EXPECTED_BUILD'))
    return result


async def execute(args):
    if args.command in {'doctor', 'run'}:
        if not args.endpoint or not args.token_file or not args.expected_build:
            raise ValueError('endpoint, token-file and expected-build are required (or AI4R_ENDPOINT/AI4R_TOKEN_FILE/AI4R_EXPECTED_BUILD)')
        cases, inputs, output = validate_roots(args.cases, args.inputs, args.output)
        document = load_cases(cases)
        # Credentials are referenced, not frozen into a campaign or exported.
        token = bounded_file(args.token_file, 16384).read_text(encoding='utf8').strip()
        known = {token} - {''}
        for case in document['cases']:
            for phase in ('setup', 'steps', 'collection'):
                for command in case[phase]:
                    for key, value in command['env'].items():
                        if isinstance(value, dict) and (SECRET_NAME.search(key) or SECRET_NAME.search(value['from_env'])):
                            secret = os.environ.get(value['from_env'])
                            if secret: known.add(secret)
        serialized = canonical(document).decode('utf8')
        if any(secret in serialized for secret in known):
            raise ValueError('case contains a literal credential; use an explicit from_env reference')
        if args.command == 'doctor':
            client = ResearchClient(args.endpoint, args.token_file, http_authority=args.http_authority)
            try:
                ready = await client.readiness()
                if not ready.get('ready') or ready.get('build_id') != args.expected_build: raise ValueError('target is not ready or build identity differs')
                context = await client.context()
                for case in document['cases']:
                    for item in case['inputs']: bounded_file(inputs / relative(item['path']), case['limits']['max_artifact_bytes'])
                return 0, {'ready': True, 'build_id': ready['build_id'], 'client_contract_version': ready.get('client_contract_version'),
                           'case_count': len(document['cases']), 'run_count': sum(c['repeats'] for c in document['cases']),
                           'cases': str(cases), 'inputs': str(inputs), 'output': str(output), 'workspace_id': context['defaults']['workspace_id']}
            finally: await client.close()
        folder, campaign = create_campaign(cases, inputs, output, campaign_id=args.campaign_id or 'campaign-' + uuid.uuid4().hex[:12],
                                           endpoint=args.endpoint, expected_build=args.expected_build, http_authority=args.http_authority)
    else:
        folder, campaign = load_campaign(args.campaign_dir)
    if args.command == 'status': return 0, snapshot(folder, campaign)
    if args.command == 'export':
        from .human_reports import build_human_reports
        return 0, build_human_reports(folder)
    if args.command == 'cancel':
        atomic(folder / 'cancellation_requested.json', {'requested_at': utc(), 'handled': False})
        try:
            with campaign_lock(folder): pass
        except ValueError:
            return 3, {'campaign_dir': str(folder), 'cancellation_requested': True,
                       'state': 'cancellation_pending', 'detail': 'active observer will request cancellation and collect terminal artifacts'}
    with campaign_lock(folder):
        if args.command == 'cleanup': return 0, cleanup_owned(folder, campaign)
        endpoint = args.endpoint or campaign['endpoint']; build = args.expected_build or campaign['expected_build']
        if endpoint != campaign['endpoint'] or build != campaign['expected_build']: raise ValueError('resume must target the pinned campaign endpoint/build')
        authority = campaign.get('http_authority')
        if args.http_authority is not None and args.http_authority != authority:
            raise ValueError('resume must use the pinned campaign HTTP authority')
        if not args.token_file: raise ValueError('credential reference required; token contents are never persisted')
        client = ResearchClient(endpoint, args.token_file, http_authority=authority); runner = SequentialRunner(client, folder, campaign)
        try:
            code = await (runner.cancel() if args.command == 'cancel' else runner.run())
            from .human_reports import build_human_reports
            reports = build_human_reports(folder)
            return code, {'campaign_dir': str(folder), **snapshot(folder, campaign), 'reports': reports}
        finally:
            runner.close(); await client.close()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        code, value = asyncio.run(execute(args))
        if args.json: print(json.dumps(value, ensure_ascii=False, default=str))
        else:
            if args.command == 'status':
                print(value['campaign_id'] + ': ' + value['state'])
                for row in value['runs']: print(row['run_id'] + ': execution=' + row['execution_state'] + ' collection=' + row['collection_state'])
            else: print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        return code
    except KeyboardInterrupt:
        print('Observation interrupted. Research may still be active; resume reconciles the recorded request before dispatch.', file=sys.stderr)
        return 3
    except (OSError, ValueError, KeyError, httpx.HTTPError, TimeoutError) as error:
        value = {'error': str(error) if not isinstance(error, httpx.HTTPError) else type(error).__name__, 'human_action_required': True}
        print(json.dumps(value) if args.json else 'Action required: ' + value['error'], file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
