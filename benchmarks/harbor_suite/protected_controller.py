"""Root supervisor of real native sequential processes and dispatch barriers.

This is benchmark operator code, never an app request or a worker capability.
The private key and custody directory must be inaccessible to both product and
worker users. Its public key is frozen in the Harbor task before dispatch.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
from pathlib import Path
import signal
import sqlite3
import sys
import tempfile
import uuid

from .contracts import canonical, pin, read_json, regular, require
from ..harbor_pilot.bridge import observation, now

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('benchmarks/harbor_suite/protected_controller.py',
           'benchmarks/harbor_suite/adapter.py', 'benchmarks/harbor_suite/evidence.py',
           'benchmarks/harbor_pilot/bridge.py',
           'jiuwenswarm/research/protected_barrier.py',
           'jiuwenswarm/research/gate.py',
           'jiuwenswarm/research/scheduler.py',
           'jiuwenswarm/research/bootstrap_core.py',
           'jiuwenswarm/research_sidecar/sequential.py',
           'jiuwenswarm/research_sidecar/control_hooks.py',
           'jiuwenswarm/research_sidecar/client.py',
           'jiuwenswarm/research_sidecar/reconcile.py',
           'jiuwenswarm/research_sidecar/ledger.py')


def atomic(path, value):
    path = Path(path)
    require(path.parent.is_dir() and not any(p.is_symlink() for p in (path, *path.parents)),
            'unsafe protected publication path')
    raw = value if isinstance(value, bytes) else canonical(value)
    fd, temporary = tempfile.mkstemp(prefix='.controller-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def ref(name, raw):
    return {'id': 'protected-controller:' + name,
            'sha256': hashlib.sha256(raw).hexdigest()}


def load_config(path, task, suite):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    require(os.name == 'posix' and os.geteuid() == 0, 'protected controller requires root Linux custody')
    value = read_json(regular(path))
    required = {'schema', 'key_file', 'custody_root', 'hook_root', 'worker_uid', 'worker_gid', 'app_uid'}
    require(set(value) == required and value['schema'] == 'ai4r-native-controller-config:1', 'exact native controller config required')
    require(all(type(value[k]) is int and value[k] > 0 for k in ('worker_uid', 'worker_gid', 'app_uid'))
            and value['worker_uid'] != value['app_uid'], 'separate unprivileged app/worker identities required')
    for field in ('key_file', 'custody_root', 'hook_root'):
        target = Path(value[field]); require(target.is_absolute(), 'absolute protected controller path required')
        require(not any(p.is_symlink() for p in (target, *target.parents)), 'controller symlink refused')
        require(not target.is_relative_to(suite['bundle_root']) and not target.is_relative_to(suite['output_root']),
                'controller custody cannot be inside task/evidence')
    key = regular(value['key_file']); info = key.stat()
    require(info.st_uid == 0 and not info.st_mode & 0o077 and info.st_nlink == 1,
            'controller signing key must be root-only')
    raw = key.read_bytes(); require(len(raw) == 32, 'raw Ed25519 private seed required')
    public = Ed25519PrivateKey.from_private_bytes(raw).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    require(public == task.get('pipeline02_controller_public_key'), 'controller is not anchored in frozen task')
    custody = Path(value['custody_root']); custody.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(custody.stat().st_uid == 0 and not custody.stat().st_mode & 0o077,
            'controller custody must be root-only')
    value['public_key'] = public
    require(task.get('pipeline02_controller_sources') == {name: pin(ROOT / name) for name in SOURCES},
            'protected controller implementation changed after bundle freeze')
    return value


class NativeController:
    protected_native_controller = True
    def __init__(self, config, bridge, task):
        self.config, self.bridge, self.task = config, bridge, task
        self.custody = None
        criteria = read_json(regular(bridge.bundle_root / 'tasks' / task['task_key'] / 'tests' / 'criteria.json'))
        require(pin(bridge.bundle_root / 'tasks' / task['task_key'] / 'tests' / 'criteria.json') == task['criteria_pin'],
                'protected criteria changed')
        self.plan = criteria['variants'][task['variant_id']]['driver_plan']
        self.plan_sha = hashlib.sha256(canonical(self.plan)).hexdigest()
        self.audit = []
        self.process = None

    def store(self, name, value):
        raw = value if isinstance(value, bytes) else canonical(value)
        path = self.custody / name
        if path.exists():
            require(path.read_bytes() == raw, 'protected custody cannot change: ' + name)
        else:
            atomic(path, raw)
        return ref(name, raw)

    def event(self, event, **values):
        self.audit.append({'event': event, 'recorded_at': now(), **values})
        atomic(self.custody / 'audit-live.json', self.audit)

    def run_row(self):
        rows = list((self.folder / 'runs').glob('*/run_record.json'))
        require(len(rows) == 1, 'protected run requires exactly one denominator entry')
        return rows[0], read_json(rows[0])

    async def wait_file(self, path):
        deadline = asyncio.get_running_loop().time() + 900
        while not path.exists():
            if self.process is not None and self.process.returncode is not None:
                raise ValueError('native observer exited before protected trigger')
            require(asyncio.get_running_loop().time() < deadline, 'protected trigger deadline exceeded')
            await asyncio.sleep(.05)
        return read_json(regular(path))

    async def wait_app_barrier(self, path, request, app):
        """Wait for the real trigger, or collect a workflow that ended first.

        An upstream governed rejection is an original case outcome. It must
        release the held observer to collect, without manufacturing a fault.
        """
        from jiuwenswarm.research_sidecar.client import ResearchClient
        from ..harbor_pilot.bridge import TERMINAL
        client = ResearchClient(self.bridge.endpoint, self.bridge.token_file,
                                http_authority=self.bridge.http_authority)
        captures = []
        async def capture(response):
            raw = await response.aread()
            captures.append({'method': response.request.method, 'path': response.request.url.path,
                             'status_code': response.status_code, 'body_utf8': raw.decode('utf-8'),
                             'sha256': hashlib.sha256(raw).hexdigest()})
        client.http.event_hooks['response'] = [capture]
        deadline = asyncio.get_running_loop().time() + 900
        try:
            while not path.exists():
                require(self.process.returncode is None, 'native observer exited before protected trigger')
                require(asyncio.get_running_loop().time() < deadline, 'protected trigger deadline exceeded')
                captures.clear()
                status = await client.status(app)
                require(status.get('run_id') == app and status.get('client_request_id') == request,
                        'early-terminal observation has foreign request/run identity')
                if status.get('status') in TERMINAL:
                    manifest = await client.artifacts(app)
                    require(manifest.get('run_id') == app and manifest.get('execution_terminal') is True,
                            'early-terminal API status lacks terminal artifact proof')
                    self.store('early-terminal.json', {'request_id': request, 'app_run_id': app,
                        'status': status, 'manifest': manifest, 'http_captures': captures,
                        'observed_at': now()})
                    return None
                await asyncio.sleep(2)
            return read_json(regular(path))
        finally:
            await client.close()

    async def collect_before_fault(self, hook, request, app):
        """Release only the existing observer; no restart, POST or fault effect."""
        self.event('fault_not_applied', request_id=request, app_run_id=app,
                   fault=self.plan['fault'], reason='app_terminal_before_fault_trigger')
        release = hook / 'after_submit.release'
        atomic(release, b'released'); os.chmod(release, 0o644)
        code = await self.process.wait()
        observed = observation(self.folder)
        require(observed.get('request_id') == request and observed.get('app_run_id') == app
                and observed['evidence_complete'], 'early-terminal original collection remains unresolved')
        self.store('fault-not-applied.json', {'request_id': request, 'app_run_id': app,
            'reason': 'app_terminal_before_fault_trigger', 'worker_exit_code': code,
            'terminal_collection': observed, 'observed_at': now()})
        self.event('early_terminal_collected', request_id=request, app_run_id=app)
        return code, {'protected_recovered': False, 'protected_cancelled': False}

    async def start(self, command, hook):
        executable = Path(sys.executable).resolve(strict=True)
        executable_pin = pin(executable)
        # Preserve the selected virtualenv entry point while pinning its actual
        # binary target before dropping UID. Resolving the command itself would
        # accidentally discard the virtualenv's installed dependencies.
        args = [sys.executable, '-m', 'jiuwenswarm.research_sidecar.sequential', command]
        if command == 'run':
            raise ValueError('campaign is frozen before worker start; use resume')
        args += ['--campaign-dir', str(self.folder), '--endpoint', self.bridge.endpoint,
                 '--token-file', str(self.bridge.token_file), '--expected-build', self.bridge.expected_build, '--json']
        if self.bridge.http_authority: args += ['--http-authority', self.bridge.http_authority]
        env = dict(os.environ); env['AI4R_RUNNER_CONTROL'] = str(hook)
        def drop():
            os.setgroups([]); os.setgid(self.config['worker_gid']); os.setuid(self.config['worker_uid'])
        log = open(self.custody / ('worker-' + uuid.uuid4().hex + '.log'), 'xb')
        try:
            self.process = await asyncio.create_subprocess_exec(*args, cwd=ROOT, env=env,
                preexec_fn=drop, start_new_session=True, stdout=log, stderr=log)
        finally:
            log.close()
        proc = Path('/proc') / str(self.process.pid)
        identity = {'pid': self.process.pid, 'pgid': os.getpgid(self.process.pid), 'uid': proc.stat().st_uid,
                    'stat': (proc / 'stat').read_text(), 'exe': str(executable),
                    'executable_pin': executable_pin, 'command': args}
        require(identity['pgid'] == identity['pid'], 'native worker lacks owned process group')
        self.event('process_started', process=identity)
        return identity

    async def __call__(self, args):
        try:
            return await self._execute(args)
        except BaseException as error:
            # The bridge retains a bounded public error category. Keep the
            # actual backend failure privately, including failures before a
            # campaign/ledger exists; never turn those into signed effects.
            if self.custody is not None and self.custody.is_dir():
                message = str(error)
                try:
                    token = Path(self.bridge.token_file).read_text().strip()
                    if token: message = message.replace(token, '[REDACTED]')
                except (OSError, TypeError):
                    message = type(error).__name__
                try:
                    atomic(self.custody / ('failure-' + uuid.uuid4().hex + '.json'),
                           {'error_type': type(error).__name__, 'message': message[:4000],
                            'observed_at': now(), 'campaign_id': args.campaign_id})
                except (OSError, ValueError):
                    pass  # A failed diagnostic must not replace the real error.
            raise

    async def _execute(self, args):
        from jiuwenswarm.research_sidecar.sequential import create_campaign, campaign_lock
        require(args.command in {'run', 'resume'}, 'protected backend supports controlled run/resume only')
        self.folder = self.bridge.output_root / args.campaign_id
        self.custody = Path(self.config['custody_root']) / args.campaign_id
        self.custody.mkdir(mode=0o700, exist_ok=True)
        with campaign_lock(self.custody):
            finished = self.custody / 'finished.json'
            if finished.exists():
                require(observation(self.folder)['evidence_complete'], 'signed completed controller lost original collection')
                self.audit = read_json(self.custody / 'audit-live.json')
                previous = read_json(finished)
                return previous['code'], {'protected_recovered': True, 'protected_cancelled': previous['cancelled']}
            # Recovery never replays an effect whose outcome is uncertain.
            require(not (self.custody / 'frozen.json').exists(),
                    'interrupted controller requires operator reconciliation; never repeat fault or dispatch')
            self.store('plan.json', self.plan)
            self.store('frozen.json', {'task_sha256': hashlib.sha256(canonical(self.task)).hexdigest(),
                'plan_sha256': self.plan_sha, 'sources': {name: pin(ROOT / name) for name in SOURCES},
                'build': self.bridge.expected_build,
                'input_pins': self.task['public_inputs'], 'controller_pid': os.getpid()})
            self.event('plan_frozen', plan_sha256=self.plan_sha)
            require(not self.folder.exists(), 'protected campaign must be created under controller custody')
            _, campaign = create_campaign(args.cases, args.inputs, args.output, campaign_id=args.campaign_id,
                endpoint=self.bridge.endpoint, expected_build=self.bridge.expected_build,
                http_authority=self.bridge.http_authority)
            self.stage_public(args, campaign)
            for path in (self.folder, *self.folder.rglob('*')):
                os.chown(path, self.config['worker_uid'], self.config['worker_gid'])
            _, row = self.run_row(); request = row['request_id']
            hook = Path(self.config['hook_root']) / 'runner' / request
            hook.mkdir(parents=True, mode=0o755)
            (hook / 'worker').mkdir(mode=0o700)
            os.chown(hook / 'worker', self.config['worker_uid'], self.config['worker_gid'])
            target = 'during_collection' if self.plan['fault'] == 'collection_interruption' else 'after_submit'
            atomic(hook / 'plan.json', {'event': target})
            os.chmod(hook / 'plan.json', 0o644)
            app_request = Path(self.config['hook_root']) / 'app' / 'requests' / request
            if self.plan['fault'] in {'dependency_failure', 'cancel'}:
                app_request.mkdir(parents=True, mode=0o755)
                atomic(app_request / 'plan.json', {'schema': 'protected-dispatch-barrier:1',
                    'request_id': request, 'node_id': 'benchmark', 'plan_sha256': self.plan_sha,
                    'action': 'deny' if self.plan['fault'] == 'dependency_failure' else 'hold'})
                os.chmod(app_request / 'plan.json', 0o644)
            self.event('launch_started', request_id=request, campaign_id=args.campaign_id)
            identity = await self.start('resume', hook)
            reached = await self.wait_file(hook / 'worker' / (target + '.json'))
            require(reached['pid'] == identity['pid'] and reached['request_id'] == request
                    and reached['campaign_id'] == args.campaign_id and reached.get('app_run_id'),
                    'worker rendezvous scope differs')
            app = reached['app_run_id']
            self.store('worker-trigger.json', reached)
            await self.validate_trigger(request, app, target)
            if self.plan['fault'] in {'dependency_failure', 'cancel'}:
                # Observer remains paused; product progresses to its real barrier.
                app_event = Path(self.config['hook_root']) / 'app' / 'events' / (request + '.json')
                barrier = await self.wait_app_barrier(app_event, request, app)
                if barrier is None:
                    return await self.collect_before_fault(hook, request, app)
                require(app_event.stat().st_uid == self.config['app_uid']
                        and all(barrier.get(k) == v for k, v in {'request_id': request,
                            'app_run_id': app, 'node_id': 'benchmark'}.items())
                        and barrier.get('accepted_refs'), 'unbound native dispatch barrier')
                self.store('app-barrier.json', barrier)
                if self.plan['fault'] == 'cancel':
                    effect = await self.cancel(request, app)
                    response = {'request_id': request, 'app_run_id': app, 'action': 'release'}
                else:
                    response = {'request_id': request, 'app_run_id': app, 'action': 'deny_dependency'}
                    effect = {'operation': 'dependency_access_denied', 'barrier': barrier, 'response': response}
                atomic(app_request / 'response.json', response)
                os.chmod(app_request / 'response.json', 0o644)
                self.store('app-response.json', response)
            else:
                require(self.process.returncode is None, 'protected worker already exited')
                os.killpg(self.process.pid, signal.SIGKILL)
                exit_code = await self.process.wait()
                require(exit_code == -signal.SIGKILL, 'owned worker termination not observed')
                effect = {'operation': 'collector_process_exit' if target == 'during_collection' else 'observer_process_exit',
                          'process': identity, 'exit_code': exit_code, 'trigger': reached}
            effect.update(fault=self.plan['fault'], request_id=request, app_run_id=app, observed_at=now())
            effect_ref = self.store('effect.json', effect)
            self.event('fault_applied', fault=self.plan['fault'], trigger=self.plan['trigger'],
                       request_id=request, app_run_id=app, effect_receipt_ref=effect_ref)
            atomic(hook / (target + '.release'), b'released')
            os.chmod(hook / (target + '.release'), 0o644)
            recovered = self.plan['fault'] in {'observer_interruption', 'collection_interruption'}
            if recovered:
                self.event('resume_started', request_id=request, app_run_id=app, exited_process=identity)
                if target == 'during_collection': self.event('collection_resumed', request_id=request, app_run_id=app)
                await self.start('resume', hook)
            code = await self.process.wait()
            require(observation(self.folder)['evidence_complete'], 'protected attempt execution/collection unresolved')
            self.store('finished.json', {'code': code, 'recovered': recovered,
                                       'cancelled': self.plan['fault'] == 'cancel'})
            return code, {'protected_recovered': recovered, 'protected_cancelled': self.plan['fault'] == 'cancel'}

    def stage_public(self, args, campaign):
        """Publish only frozen public bytes for the unprivileged observer.

        Root-only bridge custody may contain the original case/input paths.
        Validate their original mounted bytes first (create_campaign), then give
        the worker byte-identical read-only files without revealing criteria,
        signing material or any other files from those private parents.
        """
        stage = Path(self.config['hook_root']) / 'public' / args.campaign_id
        stage.mkdir(parents=True, mode=0o755)
        inventory = {}
        sources = {'case.json': (Path(args.cases), self.task['runner_case_pin'])}
        sources.update({'inputs/' + name: (Path(args.inputs) / name, expected)
                        for name, expected in self.task['public_inputs'].items()})
        for name, (source, expected) in sources.items():
            require(pin(source) == expected, 'public staging source differs from frozen task')
            target = stage / name
            target.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
            atomic(target, regular(source).read_bytes())
            os.chmod(target, 0o444)
            require(pin(target) == expected, 'public staging changed original bytes')
            inventory[name] = {'source': str(source), 'target': str(target), **expected}
        self.store('public-stage.json', inventory)
        campaign['case_file'] = str(stage / 'case.json')
        campaign['inputs_root'] = str(stage / 'inputs')
        atomic(self.folder / 'campaign.json', campaign)

    async def validate_trigger(self, request, app, target):
        from jiuwenswarm.research_sidecar.client import ResearchClient
        _, row = self.run_row()
        with sqlite3.connect((self.folder / 'ledger.sqlite').as_uri() + '?mode=ro', uri=True) as db:
            claim = db.execute('SELECT fingerprint FROM attempts WHERE id=?', (row['run_id'],)).fetchone()
        require(claim == (hashlib.sha256(canonical(row['submission'])).hexdigest(),),
                'trigger has no original durable dispatch claim')
        client = ResearchClient(self.bridge.endpoint, self.bridge.token_file, http_authority=self.bridge.http_authority)
        try:
            status = await client.reconcile(request)
            require(status['run_id'] == app and status['client_request_id'] == request,
                    'independent API reconciliation differs from protected trigger')
            capture = {'request_id': request, 'app_run_id': app, 'status': status}
            if target == 'during_collection':
                manifest = await client.artifacts(app)
                require(manifest['execution_terminal'] is True and row['collection_state'] == 'collecting',
                        'collector interruption lacks actual terminal collection')
                capture['manifest'] = manifest
            self.store('trigger-api-capture.json', capture)
        finally:
            await client.close()

    async def cancel(self, request, app):
        from jiuwenswarm.research_sidecar.client import ResearchClient
        from jiuwenswarm.research_sidecar.ledger import Ledger
        path, row = self.run_row(); require(row['request_id'] == request and row['app_run_id'] == app, 'cancel scope differs')
        client = ResearchClient(self.bridge.endpoint, self.bridge.token_file, http_authority=self.bridge.http_authority)
        captures = []
        async def capture(response):
            raw = await response.aread()
            captures.append({'method': response.request.method, 'path': response.request.url.path,
                'status_code': response.status_code, 'body_utf8': raw.decode('utf-8'),
                'sha256': hashlib.sha256(raw).hexdigest()})
        client.http.event_hooks['response'] = [capture]
        ledger = Ledger(self.folder / 'ledger.sqlite')
        cancel_id = 'cancel-' + uuid.uuid4().hex
        payload = {k: row.get(k) for k in ('request_id', 'app_run_id', 'execution_state', 'collection_state')}
        try:
            ledger.event(row['run_id'], 'cancel_requested', {**payload, 'recorded_at': now()})
            # Independent root-held HTTP client causes the actual authenticated
            # API effect; no worker-authored acknowledgement is adopted.
            response = await client.cancel(app, cancel_id)
            require(len(captures) == 1 and captures[0]['status_code'] in {200, 202}, 'actual cancel HTTP acknowledgement absent')
            ledger.event(row['run_id'], 'cancel_acknowledged', {**payload, 'recorded_at': now()})
            row.update(cancel_requested_at=now(), cancellation_request_id=cancel_id, cancellation=response)
            atomic(path, row); os.chown(path, self.config['worker_uid'], self.config['worker_gid'])
            return {'operation': 'cancel_api_acknowledged', 'cancellation_request_id': cancel_id,
                    'method': 'POST', 'path': '/api/v1/runs/' + app + '/cancel', 'response': response,
                    'http_capture': captures[0]}
        finally:
            ledger.close(); await client.close()

    def finalize(self, result):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        require(self.custody is not None and result.folder == self.folder, 'controller finalization scope differs')
        if (not result.receipt.get('evidence_complete')
                or not (self.custody / 'finished.json').is_file()
                or not any(event.get('event') == 'fault_applied' for event in self.audit)):
            # A retained failed/unresolved attempt has no complete controller
            # projection. Its original bridge receipt remains authoritative;
            # do not open/create a missing ledger or manufacture effect Refs.
            return False
        _, row = self.run_row()
        with sqlite3.connect((self.folder / 'ledger.sqlite').as_uri() + '?mode=ro', uri=True) as db:
            events = [{'sequence': r[0], 'kind': r[1], 'payload': __import__('json').loads(r[2])}
                      for r in db.execute('SELECT seq,kind,payload FROM events WHERE id=? ORDER BY seq', (row['run_id'],))]
            claims = db.execute('SELECT id,fingerprint FROM attempts ORDER BY id').fetchall()
        require(claims == [(row['run_id'], hashlib.sha256(canonical(row['submission'])).hexdigest())],
                'native request claim differs from original submission')
        require(sum(e['kind'] == 'dispatch_planned' for e in events) == 1
                and all(e['payload'].get('request_id') == row['request_id']
                        and e['payload'].get('app_run_id') in {None, row['app_run_id']} for e in events),
                'native ledger dispatch/request identity differs')
        self.store('events.json', events); self.store('claims.json', claims)
        self.store('audit.json', self.audit)
        receipt = {'schema': 'pipeline02-controller-receipt:1', 'variant_id': self.task['variant_id'],
                   'plan_ref': ref('plan.json', (self.custody / 'plan.json').read_bytes()),
                   'plan_sha256': self.plan_sha, 'audit_ref': ref('audit.json', canonical(self.audit))}
        self.store('driver-receipt.json', receipt)
        exported = {}
        for path in self.custody.iterdir():
            if path.is_file() and path.suffix == '.json': exported['controller/' + path.name] = path.read_bytes()
        for name in ('campaign.json', 'pilot-receipt.json', 'bridge-pins.json', 'target_identity.json',
                     'runs/' + row['run_id'] + '/run_record.json'):
            exported[name] = regular(self.folder / name).read_bytes()
        payload = {'schema': 'ai4r-protected-custody:1', 'task_sha256': hashlib.sha256(canonical(self.task)).hexdigest(),
                   'campaign_id': row['campaign_id'], 'request_id': row['request_id'], 'app_run_id': row['app_run_id'],
                   'files': {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
                             for name, raw in exported.items()}}
        signature = Ed25519PrivateKey.from_private_bytes(Path(self.config['key_file']).read_bytes()).sign(canonical(payload)).hex()
        (self.folder / 'controller').mkdir(mode=0o755, exist_ok=True)
        for name, raw in exported.items():
            if name.startswith('controller/'): atomic(self.folder / name, raw)
        atomic(self.folder / 'controller-custody.json', {'payload': payload, 'signature': signature})
        return True


async def run_native(suite_path, task_key, identity):
    """Direct native launch with exactly the same protected Harbor backend.

    Harbor itself is optional for this operator entry point; the retained bridge
    receipt and sequential campaign are identical to the adapter's backend.
    """
    from .contracts import validate_bundle
    from ..harbor_pilot.bridge import Config, run_trial
    suite = read_json(regular(suite_path))
    require(suite.get('schema') == 'ai4r-harbor-suite-config:1' and suite.get('mode') == 'live',
            'explicit live suite required')
    suite['bundle_root'] = Path(suite['bundle_root']); suite['output_root'] = Path(suite['output_root'])
    matches = [t for t in validate_bundle(suite['bundle_root'], index_only=True)['tasks'] if t['task_key'] == task_key]
    require(len(matches) == 1 and matches[0]['case_id'] == 'pipeline02-recovery', 'one frozen native fault task required')
    task = matches[0]; validate_bundle(suite['bundle_root'], selected=task)
    bridge = Config.load(suite['runner_config'])
    require(bridge.bundle_root == suite['bundle_root'] and bridge.output_root == suite['output_root'],
            'native controller/bridge roots differ')
    control = NativeController(load_config(suite['controller_config'], task, suite), bridge, task)
    result = await run_trial(bridge, task_key, identity, execute=control)
    controller_complete = control.finalize(result)
    receipt = {'schema': 'ai4r-harbor-suite-receipt:1',
               **{k: task[k] for k in ('task_key', 'case_id', 'variant_id', 'repeat', 'expected_model')},
               'task_sha256': hashlib.sha256(canonical(task)).hexdigest(),
               'status': 'observed', 'launched': bool(result.receipt.get('app_run_id')),
               'blockers': [], 'campaign_id': result.receipt['campaign_id'], 'custody': 'live'}
    atomic(result.folder / 'suite-receipt.json', receipt)
    return {'folder': str(result.folder), 'receipt': receipt, 'controller_complete': controller_complete}


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-config', required=True)
    parser.add_argument('--task-key', required=True)
    parser.add_argument('--identity', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(run_native(args.suite_config, args.task_key, args.identity))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
