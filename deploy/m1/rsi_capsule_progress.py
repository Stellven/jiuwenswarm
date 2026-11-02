"""Observe one pinned run and publish only stage names, timing and counters.

Can watch an already running worker without changing its pinned source. Future
launchers call the same observer. No model calls, dispatch or grant mutations.
"""
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import time

from jiuwenswarm.research_rsi.progress import SCHEMA as EVENT_SCHEMA, STAGES
from jiuwenswarm.research.cc_ui_runtime import module

public_progress = module('cc_rsi_progress')
SCHEMA, validate = public_progress.SCHEMA, public_progress.validate


def read(path, *, owner=0, limit=16*1024*1024):
    path = Path(path)
    for parent in path.parents:
        meta = parent.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid not in (0, owner) or meta.st_mode & 0o022:
            raise ValueError('Protected progress input ancestry differs')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != owner or meta.st_nlink != 1 or meta.st_size > limit or meta.st_mode & 0o022:
            raise ValueError('Protected progress input differs')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Progress input exceeds bound')
        return raw
    finally:
        os.close(fd)


def pinned(pin):
    raw = read(pin['path'])
    if hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('Progress configuration pin differs')
    return json.loads(raw)


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


class Observer:
    def __init__(self, template_pin):
        self.template = pinned(template_pin)
        self.cfg = pinned(self.template['configuration'])
        self.session = self.cfg['session']
        self.run_id = self.session['id']
        self.control = Path(self.template['control_directory'])
        self.events = []
        self.seen = set()
        self.jobs = {}
        self.engine = None
        self.calls = None

    def event(self, stage, at, iteration=None, source='observation'):
        if stage not in STAGES or not isinstance(at, (float, int)):
            return
        # Many evaluator jobs belong to the same stage; only transitions enter
        # the public event list, never fixture names, prompts, outputs or paths.
        key = (stage, iteration, source)
        if self.events and tuple(self.events[-1][k] for k in ('stage', 'iteration', 'source')) == key:
            return
        raw = json.dumps([self.run_id, stage, at, iteration, source]).encode()
        self.events.append({'id': hashlib.sha256(raw).hexdigest(), 'stage': stage,
                            'at': at, 'iteration': iteration, 'source': source})
        self.events = self.events[-256:]

    def evidence(self):
        candidates = []
        # Root job claims are the exact grant's execution starts. This fallback
        # supports workers already launched before stage telemetry was added.
        claims = Path(self.cfg['evaluator']['root']) / 'claims'
        for path in claims.glob('*.json'):
            if ('job', path.name) in self.seen:
                continue
            raw = read(path, limit=65536)
            row = json.loads(raw)
            if row.get('schema') != 'ai4r-rsi-whole-capsule-execution-start:1' or row.get('grant_ref') != self.session['grant_ref']:
                continue
            self.seen.add(('job', path.name))
            self.jobs[row['job_id']] = True
            benchmark = row.get('benchmark')
            if isinstance(benchmark, dict):
                iteration = benchmark.get('iteration')
                stage = 'baseline' if iteration == 0 else 'benchmark'
            else:
                iteration = 0 if row.get('role') == 'parent' else None
                stage = 'parent' if row.get('role') == 'parent' else 'verify'
            candidates.append((row['recorded_unix_ns']/1e9, stage, iteration, 'observation'))
        records = Path(self.cfg['composition']['record_root'])
        for path in records.glob('*.json'):
            if ('record', path.name) in self.seen:
                continue
            # Only small immutable JSON records; never retain raw content.
            if path.lstat().st_size > 65536:
                self.seen.add(('record', path.name)); continue
            raw = read(path, owner=12001, limit=65536)
            self.seen.add(('record', path.name))
            try:
                row = json.loads(raw)
            except (ValueError, UnicodeError):
                continue  # Candidate code may use a content-addressed .json name.
            if not isinstance(row, dict) or row.get('schema') != EVENT_SCHEMA:
                continue
            if row.get('run_id') != self.run_id or row.get('target_id') != self.session['capsule_name']:
                continue
            if hashlib.sha256(raw).hexdigest() + '.json' != path.name or row.get('stage') not in STAGES:
                continue
            if self.engine is None or row['at'] > self.engine['at']:
                self.engine = row
            candidates.append((row['at'], row['stage'], row['iteration'], 'engine'))
        # Metadata only: use the exact prepared work contexts, not the records'
        # private contents. This observes diagnosis/proposal in older workers.
        contexts = self.cfg['composition']['run_contexts']
        if contexts:
            db_path = Path(self.cfg['composition']['core_root']) / 'state/research.sqlite3'
            db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True, timeout=1)
            try:
                marks = ','.join('?' for _ in contexts)
                rows = db.execute("SELECT id,run_id,captured_at FROM records WHERE kind='model-call-start' AND run_id IN (" + marks + ') ORDER BY captured_at LIMIT 201', list(contexts)).fetchall()
                self.calls = len(rows)
                for ident, context, at in rows:
                    if ('model', ident) in self.seen:
                        continue
                    self.seen.add(('model', ident))
                    parts = context.split(':')
                    role = 'diagnose' if 'diagnosis' in parts else 'propose' if 'proposal' in parts else None
                    if role:
                        iteration = int(parts[-1]) if parts[-1].isdigit() else 1
                        candidates.append((stamp(at), role, iteration, 'observation'))
            finally:
                db.close()
        for at, stage, iteration, source in sorted(candidates):
            # Earlier delayed metadata cannot move the displayed stage back.
            if not self.events or at >= self.events[-1]['at']:
                self.event(stage, at, iteration, source)

    def observe(self, info):
        container = json.loads(read(self.control/'run-container.json'))
        if info['Id'] != container['cid'] or info['Image'] != container['image'] or container['id'] != self.run_id:
            raise ValueError('Observed worker identity differs')
        started = stamp(info['State']['StartedAt'])
        if not self.events:
            self.event('starting', started)
        self.evidence()
        state = info['State']
        worker_status = 'running' if state['Running'] else 'failed' if state['ExitCode'] else 'finalizing'
        if not state['Running']:
            self.event('failed' if state['ExitCode'] else 'finalizing', stamp(state['FinishedAt']))
        from deploy.m1.rsi_capsule_launcher import run_deadline_s
        event = self.events[-1]
        engine = self.engine or {}
        value = {'schema': SCHEMA, 'workspace_id': self.template['meta']['workspace_id'],
            'run_id': self.run_id, 'target_id': self.session['capsule_name'],
            'parent_hash': self.session['parent_body_ref']['sha256'],
            'observed_at': time.time(), 'started_at': started, 'worker_status': worker_status,
            'events': self.events, 'iteration': event['iteration'],
            'max_iterations': self.session.get('loop', {}).get('max_iterations'),
            'completed_iterations': engine.get('completed_iterations'),
            'model_calls': self.calls, 'executions': len(self.jobs),
            'execution_limit': self.session['grant'].get('max_executions'),
            'limit_seconds': run_deadline_s(self.cfg)}
        validate(value, self.template['meta']['workspace_id'])
        directory = Path(self.template['publication_directory']) / 'live'
        directory.mkdir(mode=0o750, exist_ok=True)
        for parent in (directory, *directory.parents):
            meta = parent.lstat()
            if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
                raise ValueError('Root progress directory required')
        os.chown(directory, 0, 10001)
        fd, name = tempfile.mkstemp(prefix='.progress-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(json.dumps(value, sort_keys=True).encode())
                stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o440); os.fchown(stream.fileno(), 0, 10001)
            os.replace(name, directory/(self.run_id + '.json'))
        finally:
            Path(name).unlink(missing_ok=True)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Root observer required')
    observer = Observer({'path': args.template, 'sha256': args.sha256})
    launcher_path = observer.control/'launcher-configuration.json'
    # This installed template belongs to a pinned launcher configuration; its
    # restore helper isolates the owned Docker daemon from the desktop daemon.
    value = json.loads(read(launcher_path))
    raw = read(value['restore']['path'])
    if hashlib.sha256(raw).hexdigest() != value['restore']['sha256']:
        raise ValueError('Pinned Docker restore helper differs')
    while True:
        container_path = observer.control/'run-container.json'
        if container_path.exists():
            container = json.loads(read(container_path))
            command = ['/usr/bin/python3', '-B', value['restore']['path'], 'client', '/usr/bin/docker',
                       '--host', 'unix:///run/ai4r-rsi-docker/docker.sock', 'inspect', container['cid']]
            result = subprocess.run(command, check=True, capture_output=True, timeout=15)
            info = json.loads(result.stdout)[0]
            observer.observe(info)
            if not info['State']['Running']:
                return
        elif time.time() >= observer.session['grant']['expires_unix_s']:
            return
        time.sleep(3)


if __name__ == '__main__':
    main()
