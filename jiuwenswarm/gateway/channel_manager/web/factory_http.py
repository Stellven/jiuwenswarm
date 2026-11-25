"""Factory-native export and live-home views; no model work during reads.

The operator supplies roots through FACTORY_RUN_ROOTS (os.pathsep separated).
Campaign measurements read FACTORY_MEASUREMENT_ROOT (default ~/predemo-spark/OPS).
Launching is opt-in: FACTORY_LAUNCH_ROOT contains reviewed task JSON templates;
FACTORY_LAUNCH_HOME_ROOT is a dedicated directory for new session homes.
Operator controls (hold, release, reopen, resume) act on live homes only.
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
from .capsule_catalog import CapsuleCatalog
from .capsule_evidence import capsule_usage, collect_capsule_evidence

from jiuwenswarm.gateway.channel_manager.web.factory_measurements import MeasurementEvidence
from jiuwenswarm.gateway.channel_manager.web.factory_session import controller_is_locked, session_snapshot
# The Spark demo walkthrough template (scripts/spark/recorder_live_demo.py); loaded only when launched.
RECORDER_WALKTHROUGH = 'recorder-evidence-walkthrough'

PREFIX = '/api/factory'
MAX_FILE = 16 * 1024 * 1024
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$')
HEADLINE_ID = re.compile(r'^source:OPS/final-headlines\.json@sha256:([a-f0-9]{64})$')
OPERATOR_OPS = ('hold', 'release', 'reopen')
# Controller outcomes after which a resume continues the same task (see Controller._paused_at).
RESUMABLE = ('paused', 'partial')
MAX_CHECKS = 8  # node checks kept per output in the compact view, newest last


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


CURATED_SCHEMA = 'factory.curated-replay/1'
SCRATCH_HOME = re.compile(r'^(?:web-\d{8}T\d{6}Z-[0-9a-f]{8}|synthetic-.*)$')


def curated_replay(path):
    """Step order of a curated replay bundle (built by scripts/spark/build_demo_replays.py on branch demo/cc-star-ui-20261120), else None."""
    replay = path / 'replay.json'
    if not replay.is_file() or replay.is_symlink():
        return None
    value = _json(replay)
    if not isinstance(value, dict) or value.get('schema') != CURATED_SCHEMA or not isinstance(value.get('steps'), list):
        return None
    for cursor, step in enumerate(value['steps'], 1):
        step['event_cursor'] = cursor
        step['recorded_plan_nodes'] = step.get('graph_nodes', [])
        step['graph_nodes'] = curated_graph_nodes(step)
    return value


def _record_title(ref):
    if ref.get('table') == 'file':
        return ref.get('source', ref['id']).removeprefix('OPS/') + (f" line {ref['line']}" if ref.get('line') else '')
    return f"{ref['table'].rstrip('s')} · {ref['id']}"


def curated_graph(replay, task_id):
    """The replay as a task graph: one node per step, chained in order, each with
    a child node per record it shows. Every node points at real record ids; the
    graph itself is a projection of the curated step order, labelled as such."""
    nodes = []
    previous = None
    for step in replay['steps']:
        key = f"step-{step['step']}"
        records = step.get('records') or []
        nodes.append(dict(
            node_id=key, title=f"{step['step']}. {step['presentation_title']}", kind=step['original_kind'],
            label_kind='Replay step', state='done', depends_on=[previous] if previous else [],
            evidence_ids=[r['id'] for r in records], attempt_ids=[], reason=step.get('say', ''),
            recorded=step.get('created_utc'), capability=None))
        for index, ref in enumerate(records, 1):
            nodes.append(dict(
                node_id=f'{key}-record-{index}', title=_record_title(ref), kind=ref['table'],
                label_kind='Record' if ref['table'] != 'file' else 'OPS record line', state='done',
                depends_on=[key], evidence_ids=[ref['id']], attempt_ids=[], reason='',
                source_home=ref.get('source_home') or 'OPS', task_id=ref.get('task_id'), capability=None))
        previous = key
    return dict(schema='factory.taskgraph/1', task_id=task_id, rev=len(replay['steps']), nodes=nodes, history=[],
                projection='curated replay steps; every node cites real record ids',
                ready_frontier=[], blocked_reasons={})


def curated_graph_nodes(step):
    key = f"step-{step['step']}"
    return [key] + [f'{key}-record-{i}' for i in range(1, len(step.get('records') or []) + 1)]


def curated_events(replay):
    """One story event per curated step, carrying the original record kind and summary."""
    events = []
    for cursor, step in enumerate(replay['steps'], 1):
        events.append(dict(
            cursor=cursor, id=step['primary_record'], kind=step['original_kind'], summary=step['original_summary'],
            created=step['created'], step=step['step'], presentation_title=step['presentation_title'],
            say=step.get('say', ''), graph_nodes=curated_graph_nodes(step), mark='·', rev=None))
    return events


def _json(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError('JSON evidence exceeds view limit')
    return json.loads(path.read_text())


def _identity(path):
    """File identity for caches: any content change moves mtime/ctime (ctime cannot be set back)."""
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _contains_symlink(root):
    # os.scandir reuses directory entry types: one walk, no per-file stat.
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    return True
                if entry.is_dir(follow_symlinks=False):
                    pending.append(entry.path)
    return False


def _compact_verifier(value):
    if not isinstance(value, dict):
        return None
    keep = {k: value.get(k) for k in ('cc', 'capability', 'release', 'state', 'passed', 'stage_reached', 'reason')
            if value.get(k) is not None}
    keep['checks'] = [{k: c.get(k) for k in ('name', 'status', 'stage', 'detail')}
                      for c in value.get('checks') or [] if isinstance(c, dict)]
    return keep


def _compact_review(value):
    if not isinstance(value, dict):
        return None
    keep = {k: value.get(k) for k in ('verdict', 'summary', 'passed', 'reason', 'reviewer', 'packet_artifact', 'reply_artifact')
            if value.get(k) is not None}
    keep['findings'] = [{k: f.get(k) for k in ('severity', 'file', 'line', 'problem')}
                        for f in value.get('findings') or [] if isinstance(f, dict)]
    return keep


def _check_entries(task, node, contract_node):
    """The node's checked outputs as the host sees them (node_check.effective_spec), else its node contract's."""
    from jiuwenswarm.factory.node_check import outputs_of
    spec = node.get('check')
    if not spec:
        constraints = task.get('constraints')
        defaults = constraints.get('node_checks') if isinstance(constraints, dict) else None
        spec = defaults.get(node.get('kind')) if isinstance(defaults, dict) else None
    if spec:
        return outputs_of(spec)
    if contract_node:
        from jiuwenswarm.factory.node_contract import check_spec
        return check_spec(contract_node)['outputs']
    return []


def _reopened_at(graph):
    """Per node, when an operator last reopened it or an ancestor: only later attempts and checks count."""
    nodes = {n['node_id']: n for n in graph.get('nodes', [])}
    children = {}
    for key, node in nodes.items():
        for dep in node.get('depends_on', []):
            children.setdefault(dep, []).append(key)
    result = {}
    for entry in graph.get('history', []):
        if entry.get('origin') != 'operator':
            continue
        for change in (entry.get('patch') or {}).get('reopen', []):
            frontier = [change.get('node_id')]
            while frontier:
                key = frontier.pop()
                if key in nodes and result.get(key, -1) < entry.get('created', 0):
                    result[key] = entry.get('created', 0)
                    frontier.extend(children.get(key, []))
    return result


def node_check_view(data, graph):
    """Compact per-node checking record: the node contract's work (CCs, capability), the verified
    outputs and their node_check observations, newest last. Only host records; nothing is inferred."""
    from jiuwenswarm.factory.node_contract import from_contract
    task = data['tasks'][0]
    tid = task['task_id']
    document = from_contract(data.get('_contract') or {}) or {}
    contract_nodes = {n.get('node_id'): n for n in document.get('nodes', []) if isinstance(n, dict)}
    rows = {}
    for row in data.get('observations', []):
        values = row.get('values') if isinstance(row.get('values'), dict) else {}
        if row.get('kind') == 'node_check' and row.get('task_id', tid) == tid and values.get('node_id'):
            rows.setdefault(values['node_id'], []).append(row)
    reopened = _reopened_at(graph)
    view = {}
    for node in graph.get('nodes', []):
        key = node['node_id']
        contract_node = contract_nodes.get(node.get('node_contract'))
        try:
            entries = _check_entries(task, node, contract_node)
        except (ValueError, KeyError, TypeError):
            entries = []
        if not entries and not contract_node and key not in rows:
            continue
        verifiers = {v.get('output'): v for v in (contract_node or {}).get('verifiers', []) if isinstance(v, dict)}
        names = [e['name'] for e in entries]
        for row in rows.get(key, []):
            name = row['values'].get('output', 'change')
            if name not in names:
                names.append(name)  # checked under settings the node no longer declares
        outputs = []
        for name in names:
            entry = next((e for e in entries if e['name'] == name), None)
            checks = []
            for row in [r for r in rows.get(key, []) if r['values'].get('output', 'change') == name][-MAX_CHECKS:]:
                values = row['values']
                checks.append(dict(
                    obs_id=row['obs_id'], created=row.get('created'), state=values.get('state'),
                    passed=bool(values.get('passed')), reason=values.get('reason'), kind=values.get('kind'),
                    same_settings=entry is not None and values.get('entry') == entry,
                    superseded=key in reopened and (row.get('created') or 0) < reopened[key],
                    cited=row['obs_id'] in node.get('evidence_ids', []), reused_from=values.get('reused_from'),
                    seconds=(values.get('seconds') or {}).get('total'),
                    verifier=_compact_verifier(values.get('verifier')), review=_compact_review(values.get('review')),
                    found=sorted(values['found']) if isinstance(values.get('found'), dict) else None,
                    artifacts=row.get('source_artifacts') or []))
            spec = entry or {}
            pinned = spec.get('inputs') or (verifiers.get(name) or {}).get('inputs')
            outputs.append(dict(
                name=name, kind=spec.get('kind') or (checks[-1]['kind'] if checks else None),
                required=spec.get('required', True) if entry else False, declared=entry is not None,
                verifier=spec.get('verifier'), stage=spec.get('stage'), review=bool(spec.get('review')),
                inputs=pinned or None, criteria=list(spec.get('criteria') or []), checks=checks))
        work = (contract_node or {}).get('work') or {}
        view[key] = dict(
            node_contract=node.get('node_contract'), objective=(contract_node or {}).get('objective'),
            helpful_ccs=list(work.get('helpful_ccs') or []), capability=work.get('capability') or node.get('capability'),
            requirement_ids=list((contract_node or {}).get('requirement_ids') or []),
            outputs=outputs, reopened_at=reopened.get(key))
    return view


class FactoryHttpService:
    def __init__(self, roots=None, launch_root=None, launch_home_root=None, measurement_root=None, *, capsule_catalog=None):
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
        self.capsule_catalog = capsule_catalog or CapsuleCatalog()
        # Per-file caches keyed by _identity: valid JSON verdicts and SHA256 digests.
        self._valid_json = {}
        self._digests = {}
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
                replay = None
                if (path / 'MANIFEST.json').is_file():
                    self.bundle_safe(path)
                    tasks = _json(_inside(path, 'records/tasks.json'))
                    kind = 'bundle'
                    replay = curated_replay(path)
                else:
                    for rel in ('factory.sqlite', 'factory.sqlite-wal'):
                        _inside(path, rel)
                    tasks = monitor.tasks(path)  # reads a stable copy of SQLite + WAL
                    kind = 'live'
                for task in tasks:
                    tid = task['task_id']
                    if not SAFE_ID.fullmatch(tid):
                        continue
                    item = dict(id=self.run_id(path, tid), name=tid, task_id=tid, kind=kind, source_name=path.name,
                                status='replay' if kind == 'bundle' else 'live',
                                updated=path.stat().st_mtime, objective=task.get('objective', ''))
                    if replay:
                        item.update(name=replay['title'], demo=True, demo_order=replay.get('order', 0),
                                    objective=replay.get('summary', ''))
                    elif kind == 'live' and SCRATCH_HOME.match(path.name):
                        item['scratch'] = True
                    result.append((item, path))
            except (OSError, ValueError, KeyError):
                continue
        # Older export snapshots of the same task are duplicates of the newest.
        newest = {}
        for item, _ in result:
            if item['kind'] == 'bundle' and not item.get('demo'):
                key = item['task_id']
                if key not in newest or item['updated'] > newest[key]['updated']:
                    newest[key] = item
        for item, _ in result:
            if item['kind'] == 'bundle' and not item.get('demo') and newest[item['task_id']] is not item:
                item['duplicate'] = True
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

    def capsules(self, usage):
        catalog = self.capsule_catalog.listing()
        if usage:
            summary = capsule_usage(self, {row['id'] for row in catalog['capsules']})
            for capsule in catalog['capsules']:
                capsule.update(summary[capsule['id']])
        return catalog

    def capsule_detail(self, name):
        detail = self.capsule_catalog.detail(name)
        detail['evidence'] = collect_capsule_evidence(
            self, detail['id'], release=detail['digest'] or detail['expected_digest'],
            starred=detail['starred'], analysis=detail['kind'] == 'analysis',
        )
        return detail

    def bundle_safe(self, path):
        # story.load_source reads records/contracts itself: validate those inputs
        # before calling the shared helper, including any nested symlink.
        if _contains_symlink(path):
            raise ValueError('Bundle contains a symlink')
        for folder in ('records', 'contracts'):
            for child in (path / folder).glob('*.json'):
                target = _inside(path, child.relative_to(path))
                key = (target, _identity(target))
                if key not in self._valid_json:
                    _json(target)
                    self._valid_json[key] = True

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
                # Reuse the validated snapshot; never re-open a live DB whose
                # contract reference may have changed meanwhile.
                return story.load_source(item['task_id'], Path(temporary), records=data)
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
        display_names = {}
        if item['kind'] == 'bundle' and (path / 'provenance.json').is_file():
            provenance = _json(_inside(path, 'provenance.json'))
            display_names = {k: v['display_name'] for k, v in (provenance.get('files') or {}).items()
                     if isinstance(v, dict) and v.get('display_name')}
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
                rows.append(dict(path=name, display_path=display_names.get(name) or ' · '.join(labels.get(name, [name])), artifact_ids=identities.get(name, []), size=0, sha256=None, expected_sha256=wanted, integrity='missing'))
                continue
            size = target.stat().st_size
            digest = self.cached_hash(target)
            rows.append(dict(path=name, display_path=display_names.get(name) or ' · '.join(labels.get(name, [name])), artifact_ids=identities.get(name, []), size=size, sha256=digest, expected_sha256=wanted,
                             integrity=('verified' if digest == wanted else 'mismatch') if wanted else 'untracked'))
        return rows

    def cached_hash(self, path):
        key = (path, _identity(path))
        if key not in self._digests:
            if len(self._digests) > 100_000:
                self._digests.clear()
            self._digests[key] = self.file_hash(path)
        return self._digests[key]

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
        replay = curated_replay(path) if item['kind'] == 'bundle' else None
        events = curated_events(replay) if replay else self.events(data)
        if item['kind'] == 'live':
            _inside(path, 'telemetry/events.jsonl')
            trace = telemetry.read_events(path, item['task_id'])
        else:
            trace_path = _inside(path, 'telemetry.jsonl')
            trace = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()] if trace_path.is_file() else []
        plan = taskgraph.from_records(data)
        return sanitize(dict(run=item, records=data, contract=data.get('_contract', {}),
                             graph=curated_graph(replay, item['task_id']) if replay else plan,
                             recorded_plan=plan if replay else None,
                             node_checks={} if replay else node_check_view(data, plan),
                             controls=self._controls(path, data) if item['kind'] == 'live' else None,
                             stack=monitor.engine_stack(data),
                             telemetry=trace, files=self.files(item, path, data), events=events,
                             summary=dict(meta=data.get('_meta', {}), telemetry=telemetry.summary(trace)),
                             session=self._session(item, path, data) if item['kind'] == 'live' else None,
                             curated=replay))

    @staticmethod
    def _running(path):
        return controller_is_locked(_inside(path, 'controller.lock'))

    def _controls(self, path, data):
        """What an operator may do to this live home now. Bundles and curated replays have no controls."""
        state = data['_meta']['controller_state']
        running = self._running(path)
        outcome = state.get('outcome')
        return dict(operator=True, running=running, outcome=outcome, stop_reason=state.get('stop_reason'),
                    resume=not running and outcome in RESUMABLE)

    def _live(self, run_id):
        item, path = self.resolve(run_id)
        if item['kind'] != 'live':
            raise HTTPException(403, 'Operator controls apply to live factory homes only, not exported bundles or replays')
        return item, path

    def operator(self, run_id, op, node_id, reason):
        """Hold, release or reopen one plan node through the controller, which also notes it for the agent."""
        if op not in OPERATOR_OPS:
            raise HTTPException(404, 'Unknown operator action')
        if not SAFE_ID.fullmatch(node_id):
            raise HTTPException(400, 'Invalid plan node')
        item, path = self._live(run_id)
        graph = operator_controller(path).operator(item['task_id'], op, node_id, reason)
        return sanitize(dict(run_id=run_id, task_id=item['task_id'], op=op, node_id=node_id, graph_rev=graph.get('rev'),
                             held=[n['node_id'] for n in graph.get('nodes', []) if n.get('hold')]))

    def resume(self, run_id):
        """Start `jiuwenswarm-factory resume <task>` detached, the way launch starts a run."""
        item, path = self._live(run_id)
        data = self.load(item, path)
        if self._running(path):
            raise HTTPException(409, 'A controller is already running in this factory home')
        outcome = data['_meta']['controller_state'].get('outcome')
        if outcome not in RESUMABLE:
            raise HTTPException(409, f'Resume continues a paused or partial run; this run is {outcome or "not stopped"}')
        tid = item['task_id']
        command = [sys.executable, '-m', 'jiuwenswarm.factory.cli', '--home', str(path), 'resume', tid, '--plain']
        for effect in data['tasks'][0].get('allowed_effects') or []:
            command.extend(('--grant', effect))
        if os.environ.get('FACTORY_LAUNCH_SYSTEMD') == '1':
            command = ['systemd-run', '--user', '--scope', f'--unit=factory-{tid}-resume-{uuid.uuid4().hex[:6]}', *command]
        with _inside(path, 'launch.log').open('ab') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True, close_fds=True)
        metadata = dict(id=run_id, task_id=tid, pid=process.pid, resumed_from=outcome)
        _inside(path, 'resume.json').write_text(json.dumps(dict(metadata, command=command, started=time.time())) + '\n')
        return metadata

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
        replay = curated_replay(path) if item['kind'] == 'bundle' else None
        events = curated_events(replay) if replay else self.events(data)
        return sanitize(dict(events=events, cursor=len(events), total=len(events),
                             reset=bool(since)))

    def headlines(self):
        """Return one verified final snapshot without hashing the whole run."""
        matches = [(item, path) for item, path in self.catalog()
                   if item['kind'] == 'live' and item['task_id'] == 'spark-direct-benchmarks-20261120']
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError('Multiple live headline publication homes')
        item, path = matches[0]
        data = self.load(item, path)
        publications = sorted(
            (row for row in data['observations'] if row['kind'] == 'report_publication'),
            key=lambda row: row['created'], reverse=True,
        )
        artifacts = {row['artifact_id']: row for row in data['artifacts']}
        for publication in publications:
            linked = publication['source_artifacts'] or []
            for artifact_id in linked:
                match = HEADLINE_ID.fullmatch(artifact_id)
                if not match:
                    continue
                artifact = artifacts.get(artifact_id, {})
                sha256 = match[1]
                relative = artifact.get('location', '')
                if (artifact.get('sha256') != sha256 or
                        not relative.startswith('artifacts/')):
                    raise ValueError('Headline publication has an invalid artifact binding')
                target = _inside(path, relative)
                with target.open('rb') as stream:
                    raw = stream.read(256 * 1024 + 1)
                if len(raw) > 256 * 1024 or _hash(raw) != sha256:
                    raise ValueError('Headline artifact failed integrity verification')
                payload = json.loads(raw)
                if not isinstance(payload, dict) or payload.get('schema') != 'spark-final-headlines/1':
                    raise ValueError('Unsupported headline schema')
                return sanitize(dict(
                    run_id=item['id'], artifact_id=artifact_id, sha256=sha256, payload=payload,
                    source_artifacts=[source for source in linked if source in artifacts],
                ))
        return None

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
        native_walkthrough = template_id == RECORDER_WALKTHROUGH
        if native_walkthrough:
            from scripts.spark.recorder_live_demo import TEMPLATE, valid_template as valid_recorder_walkthrough
            assert TEMPLATE == RECORDER_WALKTHROUGH
        if native_walkthrough and not valid_recorder_walkthrough(task):
            raise HTTPException(422, 'Recorder walkthrough template does not match the reviewed read-only task')
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
        if native_walkthrough:
            command = [sys.executable, '-m', 'scripts.spark.recorder_live_demo', str(home), tid]
        else:
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


def operator_controller(home):
    """The home's controller: imported lazily (Linux-only locking), replaceable in tests."""
    from jiuwenswarm.factory.controller import Controller
    return Controller(home)


def same_origin(request):
    origin = request.headers.get('origin')
    # Browser mutations require an exact same-origin host. CLI callers can
    # omit Origin; this is a trusted-operator service bound behind localhost.
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403, 'Factory controls require a same-origin request')


async def json_body(request, limit=4096):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, 'Request exceeds limit')
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError:
        raise HTTPException(400, 'Expected a JSON request') from None


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

    @app.get(PREFIX + '/capsules')
    async def capsules(usage: bool = True):
        return await call(service.capsules, usage)

    @app.get(PREFIX + '/capsules/{name}')
    async def capsule(name: str):
        return await call(service.capsule_detail, name)

    @app.get(PREFIX + '/capsules/{name}/file')
    async def capsule_file(name: str, path: str = Query(..., max_length=1024)):
        return await call(service.capsule_catalog.file, name, path)

    @app.get(PREFIX + '/measurements')
    async def measurements():
        return await call(service.measurements.listing)

    @app.get(PREFIX + '/headlines')
    async def headlines():
        return await call(service.headlines)

    @app.get(PREFIX + '/measurements/evidence/{line}')
    async def measurement_evidence(line: int, kind: Literal['ledger', 'result']):
        return await call(service.measurements.evidence, line, kind)

    @app.post(PREFIX + '/launch', status_code=202)
    async def launch(request: Request):
        same_origin(request)
        payload = await json_body(request)
        if not isinstance(payload, dict) or set(payload) != {'template_id'} or not isinstance(payload['template_id'], str):
            raise HTTPException(400, 'Expected template_id only')
        return await call(service.launch, payload['template_id'])

    @app.post(PREFIX + '/runs/{run_id}/nodes/{node_id}/{op}')
    async def operator(run_id: str, node_id: str, op: str, request: Request):
        same_origin(request)
        if op not in OPERATOR_OPS:
            raise HTTPException(404, 'Unknown operator action')
        payload = await json_body(request)
        if (not isinstance(payload, dict) or set(payload) != {'reason'} or not isinstance(payload['reason'], str)
                or not payload['reason'].strip() or len(payload['reason']) > 500):
            raise HTTPException(400, 'Expected {"reason": "..."} with a nonempty reason of at most 500 characters')
        return await call(service.operator, run_id, op, node_id, payload['reason'].strip())

    @app.post(PREFIX + '/runs/{run_id}/resume', status_code=202)
    async def resume(run_id: str, request: Request):
        same_origin(request)
        if await json_body(request) not in (None, {}):
            raise HTTPException(400, 'Resume takes no parameters')
        return await call(service.resume, run_id)
