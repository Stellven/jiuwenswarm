"""Host-only bounded campaign scheduling; never dispatches or retries requests.

Pair reservations and individual attempts share one SQLite transaction ledger.
An unfinished attempt consumes its allowance and blocks the next pair. This is
an orchestration guard, not a replacement for Harbor/provider reconciliation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time

ARMS = {'native', 'native-skills', 'cc'}


class Schedule:
    def __init__(self, path):
        self.path = Path(path).absolute()
        if any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise ValueError('symlink ledger refused')
        if not self.path.is_file():
            raise ValueError('initialize campaign explicitly')
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row

    @classmethod
    def create(cls, path, *, max_calls=256, wall_s=10800, now=None):
        if type(max_calls) is not int or not 1 <= max_calls <= 256:
            raise ValueError('campaign ceiling is 256 calls')
        if type(wall_s) is not int or not 1 <= wall_s <= 10800:
            raise ValueError('campaign ceiling is three hours')
        path = Path(path).absolute()
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('symlink ledger refused')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb'):
            pass
        obj = cls(path)
        obj.db.executescript('''
            CREATE TABLE policy(max_calls INTEGER, deadline REAL, started REAL,
                                model TEXT, effort TEXT);
            CREATE TABLE pairs(id TEXT PRIMARY KEY, task_sha256 TEXT, caps TEXT,
                               state TEXT, created REAL);
            CREATE TABLE attempts(id TEXT PRIMARY KEY, pair_id TEXT, arm TEXT,
                                  started REAL, state TEXT, effective_model TEXT,
                                  effective_effort TEXT, evidence TEXT);
        ''')
        instant = time.time() if now is None else now
        obj.db.execute('INSERT INTO policy VALUES(?,?,?,?,?)',
                       (max_calls, instant + wall_s, instant, 'gpt-6.1-sol', 'medium'))
        obj.db.commit()
        return obj

    def close(self):
        self.db.close()

    def _begin(self):
        self.db.execute('BEGIN IMMEDIATE')

    def reserve(self, pair_id, task_sha256, caps, *, now=None):
        if (not isinstance(pair_id, str) or not pair_id or len(pair_id) > 128
                or not isinstance(task_sha256, str) or len(task_sha256) != 64
                or any(c not in '0123456789abcdef' for c in task_sha256)):
            raise ValueError('bounded pair ID and frozen task SHA required')
        if (not isinstance(caps, dict) or not caps or set(caps) - ARMS
                or any(type(v) is not int or v <= 0 for v in caps.values())):
            raise ValueError('positive per-arm call caps required')
        instant = time.time() if now is None else now
        try:
            self._begin()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            if instant >= policy['deadline']:
                raise ValueError('wall-clock budget exhausted')
            if self.db.execute("SELECT 1 FROM pairs WHERE state='active'").fetchone():
                raise ValueError('finish or reconcile the active pair first')
            used = self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
            if used + sum(caps.values()) > policy['max_calls']:
                raise ValueError('whole-pair reservation exceeds remaining call budget')
            self.db.execute('INSERT INTO pairs VALUES(?,?,?,?,?)',
                            (pair_id, task_sha256, json.dumps(caps, sort_keys=True), 'active', instant))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def claim(self, pair_id, arm, request_id, *, model='gpt-6.1-sol', effort='medium', now=None):
        instant = time.time() if now is None else now
        if not isinstance(request_id, str) or not request_id or len(request_id) > 256:
            raise ValueError('persist the actual bounded request ID before dispatch')
        try:
            self._begin()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            pair = self.db.execute('SELECT * FROM pairs WHERE id=?', (pair_id,)).fetchone()
            if model != policy['model'] or effort != policy['effort']:
                raise ValueError('model/effort mismatch; fallback forbidden')
            if instant >= policy['deadline']:
                raise ValueError('wall-clock budget exhausted')
            if pair is None or pair['state'] != 'active' or arm not in json.loads(pair['caps']):
                raise ValueError('active reserved arm required')
            if self.db.execute("SELECT 1 FROM attempts WHERE state IN ('dispatched','unknown')").fetchone():
                raise ValueError('another request is active or outcome is unknown')
            used = self.db.execute('SELECT COUNT(*) FROM attempts WHERE pair_id=? AND arm=?',
                                   (pair_id, arm)).fetchone()[0]
            if used >= json.loads(pair['caps'])[arm]:
                raise ValueError('arm call cap exhausted')
            self.db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)',
                            (request_id, pair_id, arm, instant, 'dispatched', None, None, None))
            self.db.commit()
            return policy['deadline'] - instant
        except BaseException:
            self.db.rollback()
            raise

    def finish(self, request_id, state, *, evidence, effective_model=None, effective_effort=None):
        if state not in {'completed', 'failed', 'unknown', 'contained'}:
            raise ValueError('invalid terminal/reconciliation state')
        if not isinstance(evidence, str) or not evidence:
            raise ValueError('original evidence location required')
        try:
            self._begin()
            old = self.db.execute('SELECT * FROM attempts WHERE id=?', (request_id,)).fetchone()
            if old is None or old['state'] not in {'dispatched', 'unknown'}:
                raise ValueError('only original active/unknown request can be reconciled')
            if state == 'completed' and (effective_model != 'gpt-6.1-sol' or effective_effort != 'medium'):
                raise ValueError('completed inference requires verified model and effort')
            self.db.execute('UPDATE attempts SET state=?,effective_model=?,effective_effort=?,evidence=? WHERE id=?',
                            (state, effective_model, effective_effort, evidence, request_id))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def finish_pair(self, pair_id, *, state='closed'):
        if state not in {'closed', 'blocked'}:
            raise ValueError('invalid pair outcome')
        try:
            self._begin()
            if self.db.execute("SELECT 1 FROM attempts WHERE pair_id=? AND state IN ('dispatched','unknown')",
                               (pair_id,)).fetchone():
                raise ValueError('reconcile unknown requests before releasing reservation')
            cursor = self.db.execute("UPDATE pairs SET state=? WHERE id=? AND state='active'", (state, pair_id))
            if cursor.rowcount != 1:
                raise ValueError('active pair required')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def status(self):
        policy = dict(self.db.execute('SELECT * FROM policy').fetchone())
        attempts = [dict(r) for r in self.db.execute('SELECT * FROM attempts ORDER BY started,id')]
        pairs = [dict(r) for r in self.db.execute('SELECT * FROM pairs ORDER BY created,id')]
        return {'schema': 'ai4r-value-schedule:1', 'policy': policy,
                'attempts': attempts, 'pairs': pairs, 'calls_consumed': len(attempts),
                'calls_remaining': policy['max_calls'] - len(attempts),
                'engineering_agent_usage': 'outside experimental arm measurements'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'status'])
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    schedule = Schedule.create(args.ledger) if args.action == 'init' else Schedule(args.ledger)
    try:
        print(json.dumps(schedule.status(), sort_keys=True))
    finally:
        schedule.close()


if __name__ == '__main__':
    main()
