"""Factory-native export and live-home views; no model work during reads.

The operator supplies roots through FACTORY_RUN_ROOTS (os.pathsep separated).
Campaign measurements read FACTORY_MEASUREMENT_ROOT (default ~/predemo-spark/OPS).
Launching is opt-in: FACTORY_LAUNCH_ROOT contains reviewed task JSON templates;
FACTORY_LAUNCH_HOME_ROOT is a dedicated directory for new session homes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import subprocess
import sys
import time
from typing import Literal
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from jiuwenswarm.factory import monitor, story, taskgraph, telemetry
from jiuwenswarm.factory.export import snapshot
from jiuwenswarm.factory.contract import CONTRACTS
from jiuwenswarm.factory.redact import sanitize, scrub_bytes
from jiuwenswarm.gateway.channel_manager.web.factory_measurements import MeasurementEvidence
from jiuwenswarm.gateway.channel_manager.web.factory_session import controller_is_locked, session_snapshot

PREFIX = '/api/factory'
MAX_FILE = 16 * 1024 * 1024
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _inside(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Path must be relative to the run')
    for parent in (path, *path.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ValueError('Symlinks are not evidence files')
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Path escapes run')
    return resolved


def _json(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError('JSON evidence exceeds view limit')
    return json.loads(path.read_text())


class FactoryHttpService:
    def __init__(self, roots=None, launch_root=None, launch_home_root=None, measurement_root=None):
        default = os.pathsep.join((str(Path.home() / 'predemo-spark/factory-runs'),
                                  str(Path.home() / 'software-factory-spark-20261113/exports/factory-loop-v1')))
        self.roots = tuple(Path(p).expanduser().resolve() for p in
                           (roots if roots is not None else os.environ.get('FACTORY_RUN_ROOTS', default).split(os.pathsep)) if p)
        self.measurements = MeasurementEvidence(measurement_root or os.environ.get(
            'FACTORY_MEASUREMENT_ROOT', Path.home() / 'predemo-spark/OPS'))
        launch_root = launch_root or os.environ.get('FACTORY_LAUNCH_ROOT')
        self.launch_root = Path(launch_root).expanduser().resolve() if launch_root else None
        launch_home_root = launch_home_root or os.environ.get('FACTORY_LAUNCH_HOME_ROOT')
        self.launch_home_root = Path(launch_home_root).expanduser().resolve() if launch_home_root else None
        if self.launch_home_root and not any(self.launch_home_root.is_relative_to(r) for r in self.roots):
            raise ValueError('Launch homes must be beneath an allowed run root')

    @staticmethod
    def run_id(path, task_id=''):
        return _hash((str(path) + '\0' + task_id).encode())[:24]

    def directories(self):
        seen = set()
        def visit(path, depth):
            if path.is_symlink() or not path.is_dir() or path in seen:
                return
            seen.add(path)
            if (path / 'MANIFEST.json').is_file() or (path / 'factory.sqlite').is_file():
                yield path
            elif depth < 4:
                for child in sorted(path.iterdir()):
                    if not child.name.startswith('.'):
                        yield from visit(child, depth + 1)
        for root in self.roots:
            if root.is_dir():
                yield from visit(root, 0)

    def catalog(self):
        result = []
        for path in self.directories():
            try:
                if (path / 'MANIFEST.json').is_file():
                    self.bundle_safe(path)
                    tasks = _json(_inside(path, 'records/tasks.json'))
                    kind = 'bundle'
                else:
                    for rel in ('factory.sqlite', 'factory.sqlite-wal'):
                        _inside(path, rel)
                    tasks = monitor.tasks(path)  # reads a stable copy of SQLite + WAL
                    kind = 'live'
                for task in tasks:
                    tid = task['task_id']
                    if not SAFE_ID.fullmatch(tid):
                        continue
                    item = dict(id=self.run_id(path, tid), name=tid, task_id=tid, kind=kind,
                                status='replay' if kind == 'bundle' else 'live',
                                updated=path.stat().st_mtime, objective=task.get('objective', ''))
                    result.append((item, path))
            except (OSError, ValueError, KeyError):
                continue
        return result

    def resolve(self, run_id):
        for item, path in self.catalog():
            if item['id'] == run_id:
                return item, path
        raise HTTPException(404, 'Factory run not found')

    def templates(self):
        if not self.launch_root or not self.launch_root.is_dir():
            return []
        templates = []
        for path in sorted(self.launch_root.glob('*.json')):
            if path.is_symlink() or not SAFE_ID.fullmatch(path.stem):
                continue
            try:
                task = _json(_inside(self.launch_root, path.name))
            except (OSError, ValueError):
                continue
            if not isinstance(task, dict):
                continue
            labels = task.get('operator_labels')
            name = labels.get('display_name') if isinstance(labels, dict) else None
            name = name if isinstance(name, str) and name else path.stem
            component = task.get('component_cc')
            capsules = [component] if isinstance(component, str) and component else []
            if path.stem == 'star-capsule-inspection':
                from scripts.spark.prepare_inspection_home import NAMES
                capsules = list(NAMES)
            template = dict(id=path.stem, name=name, capsules=capsules)
            for field in ('contract_id', 'objective'):
                if isinstance(task.get(field), str):
                    template[field] = task[field]
            templates.append(template)
        return templates

    def listing(self):
        return sanitize(dict(runs=[item for item, _ in self.catalog()], launch_templates=self.templates(),
                             launch_enabled=bool(self.launch_root and self.launch_home_root)))

    def bundle_safe(self, path):
        # story.load_source reads records/contracts itself: validate those inputs
        # before calling the shared helper, including any nested symlink.
        for child in path.rglob('*'):
            if child.is_symlink():
                raise ValueError('Bundle contains a symlink')
        for child in (path / 'records').glob('*.json'):
            _json(_inside(path, child.relative_to(path)))
        for child in (path / 'contracts').glob('*.json'):
            _json(_inside(path, child.relative_to(path)))

    def load(self, item, path):
        if item['kind'] == 'bundle':
            self.bundle_safe(path)
            return story.load_source(path)
        for relative in ('factory.sqlite', 'factory.sqlite-wal',
                         f"sessions/{item['task_id']}.jsonl", f"sessions/{item['task_id']}.state.json"):
            _inside(path, relative)
        # Inspect the contract reference from a stable DB copy before the story
        # helper can open it. Contract JSON files are evidence, not arbitrary
        # filesystem reads. Additional operator roots can include contract inputs.
        paths = [path / 'factory.sqlite', path / 'factory.sqlite-wal']
        def stamps():
            return [(p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in paths]
        for _ in range(5):
            before = stamps()
            with tempfile.TemporaryDirectory(prefix='factory-http-') as temporary:
                for source in paths:
                    if source.exists():
                        shutil.copyfile(source, Path(temporary) / source.name)
                if before != stamps():
                    continue
                data = snapshot(Path(temporary), item['task_id'])
                self.validate_contract(data['tasks'][0].get('contract_id'))
                for relative in (f"sessions/{item['task_id']}.jsonl", f"sessions/{item['task_id']}.state.json"):
                    original = _inside(path, relative)
                    if original.is_file():
                        if original.stat().st_size > MAX_FILE:
                            raise ValueError('Session evidence exceeds view limit')
                        target = Path(temporary) / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(original, target)
                # Read the same validated database snapshot; never re-open a
                # live DB whose contract reference may have changed meanwhile.
                return story.load_source(item['task_id'], Path(temporary))
        raise ValueError('Factory evidence changed during read; retry')

    def validate_contract(self, contract):
        if not contract:
            return
        contract_path = Path(contract)
        if '/' not in contract and not contract.endswith('.json'):
            contract_path = CONTRACTS / (contract + '.json')
        resolved = contract_path.resolve()
        permitted = (*self.roots, CONTRACTS.resolve())
        if not any(resolved.is_relative_to(root) for root in permitted):
            raise ValueError('Contract path is outside allowed evidence roots')
        root = next(root for root in permitted if resolved.is_relative_to(root))
        _inside(root, contract_path.absolute().relative_to(root))

    def expected(self, item, path, data):
        if item['kind'] == 'bundle':
            manifest = _json(_inside(path, 'MANIFEST.json'))
            if not isinstance(manifest, dict):
                raise ValueError('Invalid native manifest')
            return manifest
        result = {}
        for artifact in data.get('artifacts', []):
            relative = artifact['location']
            if not Path(relative).parts or Path(relative).parts[0] != 'artifacts':
                raise ValueError('Live artifact location is outside artifacts directory')
            result[relative] = artifact['sha256']
        return result

    def files(self, item, path, data):
        expected = self.expected(item, path, data)
        if item['kind'] == 'bundle':
            names = set(expected) | {p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()}
        else:
            names = set(expected)
            for rel in (f"sessions/{item['task_id']}.jsonl", f"sessions/{item['task_id']}.state.json", 'launch.log'):
                if (path / rel).is_file():
                    names.add(rel)
        labels = {}
        identities = {}
        artifacts = data.get('artifacts', [])
        if item['kind'] == 'bundle' and (path / 'artifacts.json').is_file():
            artifacts = _json(_inside(path, 'artifacts.json'))
        for artifact in artifacts:
            relative = artifact.get('exported_path') if item['kind'] == 'bundle' else artifact.get('location')
            label = artifact.get('artifact_id', '')
            if label.startswith('source:') and '@sha256:' in label:
                label = label.removeprefix('source:').rsplit('@sha256:', 1)[0]
            if relative and label:
                labels.setdefault(relative, []).append(label)
                identities.setdefault(relative, []).append(artifact['artifact_id'])
        rows = []
        for name in sorted(names):
            target = _inside(path, name)
            wanted = expected.get(name)
            if not target.is_file():
                rows.append(dict(path=name, display_path=' · '.join(labels.get(name, [name])), artifact_ids=identities.get(name, []), size=0, sha256=None, expected_sha256=wanted, integrity='missing'))
                continue
            size = target.stat().st_size
            digest = self.file_hash(target)
            rows.append(dict(path=name, display_path=' · '.join(labels.get(name, [name])), artifact_ids=identities.get(name, []), size=size, sha256=digest, expected_sha256=wanted,
                             integrity=('verified' if digest == wanted else 'mismatch') if wanted else 'untracked'))
        return rows

    @staticmethod
    def file_hash(path):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def detail(self, run_id):
        item, path = self.resolve(run_id)
        data = self.load(item, path)
        events = self.events(data)
        if item['kind'] == 'live':
            _inside(path, 'telemetry/events.jsonl')
            trace = telemetry.read_events(path, item['task_id'])
        else:
            trace_path = _inside(path, 'telemetry.jsonl')
            trace = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()] if trace_path.is_file() else []
        return sanitize(dict(run=item, records=data, contract=data.get('_contract', {}),
                             graph=taskgraph.from_records(data), stack=monitor.engine_stack(data),
                             telemetry=trace, files=self.files(item, path, data), events=events,
                             summary=dict(meta=data.get('_meta', {}), telemetry=telemetry.summary(trace)),
                             session=self._session(item, path, data) if item['kind'] == 'live' else None))

    def _session(self, item, path, data):
        state = data['_meta']['controller_state']
        # The native lock is scoped to the home. It identifies a task only
        # when the home has a single task; stale state may survive a crash.
        running = (state.get('tick') is not None and not state.get('outcome')
                   and not state.get('finished') and controller_is_locked(_inside(path, 'controller.lock'))
                   and len(monitor.tasks(path)) == 1)
        transcript = _inside(path, f"sessions/{item['task_id']}.jsonl")
        if transcript.is_file() and transcript.stat().st_size > MAX_FILE:
            raise ValueError('Session evidence exceeds view limit')
        return session_snapshot(data, transcript, running, time.time())

    def session(self, run_id):
        item, path = self.resolve(run_id)
        if item['kind'] != 'live':
            raise HTTPException(404, 'This run is an exported bundle')
        return sanitize(self._session(item, path, self.load(item, path)))

    @staticmethod
    def events(data):
        # Story is a projection: later decisions can revise earlier summaries.
        # The cursor counts this snapshot; polling replaces the projection.
        return [dict(event, cursor=i + 1) for i, event in enumerate(story.build_events(data))]

    def event_page(self, run_id, since):
        item, path = self.resolve(run_id)
        data = self.load(item, path)
        events = self.events(data)
        return sanitize(dict(events=events, cursor=len(events), total=len(events),
                             reset=bool(since)))

    def file(self, run_id, relative):
        item, path = self.resolve(run_id)
        data = self.load(item, path)
        rows = {row['path']: row for row in self.files(item, path, data)}
        if relative not in rows:
            raise HTTPException(404, 'File is not part of this run')
        target = _inside(path, relative)
        if not target.is_file():
            raise HTTPException(404, 'Evidence file is missing')
        with target.open('rb') as stream:
            content = stream.read(MAX_FILE)
        clean = scrub_bytes(content).decode(errors='replace')
        try:
            clean = json.dumps(sanitize(json.loads(clean)), ensure_ascii=False, indent=2)
        except ValueError:
            pass
        return sanitize(dict(rows[relative], content=clean, truncated=target.stat().st_size > MAX_FILE))

    def launch(self, template_id):
        if not self.launch_root or not self.launch_home_root:
            raise HTTPException(403, 'Factory launch is not configured by the operator')
        if template_id not in {t['id'] for t in self.templates()}:
            raise HTTPException(400, 'Select an operator-prepared task template')
        task = _json(_inside(self.launch_root, template_id + '.json'))
        tid = 'web-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:8]
        task['task_id'] = tid
        home = self.launch_home_root / tid
        home.mkdir(parents=True, exist_ok=False)
        task_file = home / 'task.json'
        task_file.write_text(json.dumps(task, indent=2) + '\n')
        cli = [sys.executable, '-m', 'jiuwenswarm.factory.cli', '--home', str(home)]
        init = subprocess.run([*cli, 'init', str(task_file)], capture_output=True, timeout=30, check=False)
        if init.returncode:
            (home / 'launch.log').write_bytes(scrub_bytes(init.stdout + init.stderr))
            raise HTTPException(422, 'Task initialization failed; preserved launch.log in the new home')
        if template_id == 'star-capsule-inspection':
            # One operator-reviewed CPU inspection template; never arbitrary
            # provisioning, source paths or credential files from HTTP input.
            from scripts.spark.prepare_inspection_home import prepare_inspection_home
            try:
                prepared = prepare_inspection_home(home, task)
                (home / 'preparation.json').write_text(json.dumps(prepared) + '\n')
            except (OSError, ValueError):
                (home / 'launch.log').write_text('Inspection preparation failed; operator login/template review required. No agent started.\n')
                raise HTTPException(422, 'Inspection preparation failed; operator login/template review required') from None
        command = [*cli, 'run', tid, '--plain']
        for effect in task.get('allowed_effects', []):
            command.extend(('--grant', effect))
        if os.environ.get('FACTORY_LAUNCH_SYSTEMD') == '1':
            command = ['systemd-run', '--user', '--scope', '--unit=factory-' + tid, *command]
        with (home / 'launch.log').open('ab') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True, close_fds=True)
        metadata = dict(id=self.run_id(home.resolve(), tid), task_id=tid, pid=process.pid)
        (home / 'launch.json').write_text(json.dumps(dict(metadata, command=command)) + '\n')
        return metadata


def attach_factory_routes(app: FastAPI, channel=None, *, service=None):
    service = service or FactoryHttpService()

    async def call(method, *args):
        try:
            return await run_in_threadpool(method, *args)
        except HTTPException:
            raise
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(422, sanitize(str(exc))[:200]) from None

    @app.get(PREFIX + '/runs')
    async def runs():
        return await call(service.listing)

    @app.get(PREFIX + '/runs/{run_id}')
    async def detail(run_id: str):
        return await call(service.detail, run_id)

    @app.get(PREFIX + '/runs/{run_id}/session')
    async def session(run_id: str):
        return await call(service.session, run_id)

    @app.get(PREFIX + '/runs/{run_id}/story')
    async def events(run_id: str, since: int = Query(0, ge=0)):
        return await call(service.event_page, run_id, since)

    @app.get(PREFIX + '/runs/{run_id}/file')
    async def file(run_id: str, path: str = Query(..., max_length=1024)):
        return await call(service.file, run_id, path)

    @app.get(PREFIX + '/measurements')
    async def measurements():
        return await call(service.measurements.listing)

    @app.get(PREFIX + '/measurements/evidence/{line}')
    async def measurement_evidence(line: int, kind: Literal['ledger', 'result']):
        return await call(service.measurements.evidence, line, kind)

    @app.post(PREFIX + '/launch', status_code=202)
    async def launch(request: Request):
        origin = request.headers.get('origin')
        # Browser mutations require an exact same-origin host. CLI callers can
        # omit Origin; this is a trusted-operator service bound behind localhost.
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            raise HTTPException(403, 'Factory launch requires a same-origin request')
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                raise HTTPException(413, 'Launch request exceeds limit')
        try:
            payload = json.loads(body)
        except ValueError:
            raise HTTPException(400, 'Expected a JSON launch request') from None
        if not isinstance(payload, dict) or set(payload) != {'template_id'} or not isinstance(payload['template_id'], str):
            raise HTTPException(400, 'Expected template_id only')
        return await call(service.launch, payload['template_id'])
