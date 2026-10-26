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
MODELS = {'gpt-6.1-sol', 'gpt-6-luna'}
EXTERNAL_RUN_CALL_CEILING = 80


class Schedule:
    def __init__(self, path):
        self.path = Path(path).absolute()
        if any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise ValueError('symlink ledger refused')
        if not self.path.is_file():
            raise ValueError('initialize campaign explicitly')
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS external_envelopes(
            id TEXT PRIMARY KEY, pair_id TEXT NOT NULL, arm TEXT NOT NULL,
            started REAL NOT NULL, call_bound INTEGER NOT NULL,
            actual_calls INTEGER, state TEXT NOT NULL, evidence TEXT)''')
        # Additive migration only: never replace the policy, deadline, charges,
        # reservations or unresolved original effects in an existing ledger.
        pairs_columns = {row[1] for row in self.db.execute('PRAGMA table_info(pairs)')}
        if pairs_columns and 'requested_model' not in pairs_columns:
            self.db.execute("ALTER TABLE pairs ADD COLUMN requested_model TEXT NOT NULL DEFAULT 'gpt-6.1-sol'")
        envelope_columns = {row[1] for row in self.db.execute('PRAGMA table_info(external_envelopes)')}
        for column in ('effective_model', 'effective_effort'):
            if column not in envelope_columns:
                self.db.execute('ALTER TABLE external_envelopes ADD COLUMN ' + column + ' TEXT')
        self.db.execute('''CREATE TABLE IF NOT EXISTS time_extensions(
            id TEXT PRIMARY KEY, additional_s INTEGER NOT NULL, authorized_at REAL NOT NULL,
            evidence TEXT NOT NULL, previous_deadline REAL NOT NULL, new_deadline REAL NOT NULL)''')
        self.db.commit()

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
                               state TEXT, created REAL, requested_model TEXT NOT NULL DEFAULT 'gpt-6.1-sol');
            CREATE TABLE attempts(id TEXT PRIMARY KEY, pair_id TEXT, arm TEXT,
                                  started REAL, state TEXT, effective_model TEXT,
                                  effective_effort TEXT, evidence TEXT);
            CREATE TABLE IF NOT EXISTS external_envelopes(
                id TEXT PRIMARY KEY, pair_id TEXT NOT NULL, arm TEXT NOT NULL,
                started REAL NOT NULL, call_bound INTEGER NOT NULL,
                actual_calls INTEGER, state TEXT NOT NULL, evidence TEXT);
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

    def extend_time_authorized(self, authorization_id, additional_s, *, evidence, now=None):
        """Host coordinator only, after explicit user approval; never a reset.

        The evidence locator records that approval. This method grants no calls,
        resolves no unknown effects and does not expose a worker/HTTP operation.
        Replaying the same authorization fails instead of adding more time.
        """
        if (not isinstance(authorization_id, str) or not 1 <= len(authorization_id) <= 128
                or type(additional_s) is not int or not 1 <= additional_s <= 3600
                or not isinstance(evidence, str) or not evidence.strip()):
            raise ValueError('explicit bounded user time authorization and evidence required')
        instant = time.time() if now is None else now
        try:
            self._begin()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            previous = policy['deadline']; updated = previous + additional_s
            self.db.execute('INSERT INTO time_extensions VALUES(?,?,?,?,?,?)',
                (authorization_id, additional_s, instant, evidence, previous, updated))
            self.db.execute('UPDATE policy SET deadline=?', (updated,))
            self.db.commit()
            return {'previous_deadline': previous, 'new_deadline': updated,
                    'max_calls_unchanged': policy['max_calls'], 'started_unchanged': policy['started']}
        except BaseException:
            self.db.rollback()
            raise

    def reserve(self, pair_id, task_sha256, caps, *, requested_model='gpt-6.1-sol', now=None):
        if (not isinstance(pair_id, str) or not pair_id or len(pair_id) > 128
                or not isinstance(task_sha256, str) or len(task_sha256) != 64
                or any(c not in '0123456789abcdef' for c in task_sha256)):
            raise ValueError('bounded pair ID and frozen task SHA required')
        if (not isinstance(caps, dict) or not caps or set(caps) - ARMS
                or any(type(v) is not int or v <= 0 for v in caps.values())):
            raise ValueError('positive per-arm call caps required')
        if requested_model not in MODELS:
            raise ValueError('requested model must be an explicitly supported campaign model')
        instant = time.time() if now is None else now
        try:
            self._begin()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            if instant >= policy['deadline']:
                raise ValueError('wall-clock budget exhausted')
            if (self.db.execute("SELECT 1 FROM pairs WHERE state='active'").fetchone()
                    or self.db.execute("SELECT 1 FROM attempts WHERE state IN ('dispatched','unknown')").fetchone()
                    or self.db.execute("SELECT 1 FROM external_envelopes WHERE state IN ('dispatched','unknown')").fetchone()):
                raise ValueError('finish or reconcile the active pair first')
            used = self._calls_charged()
            if used + sum(caps.values()) > policy['max_calls']:
                raise ValueError('whole-pair reservation exceeds remaining call budget')
            self.db.execute('INSERT INTO pairs(id,task_sha256,caps,state,created,requested_model) VALUES(?,?,?,?,?,?)',
                            (pair_id, task_sha256, json.dumps(caps, sort_keys=True), 'active', instant, requested_model))
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
            if pair is not None and (model != pair['requested_model'] or effort != policy['effort']):
                raise ValueError('model/effort mismatch; fallback forbidden')
            if instant >= policy['deadline']:
                raise ValueError('wall-clock budget exhausted')
            if pair is None or pair['state'] != 'active' or arm not in json.loads(pair['caps']):
                raise ValueError('active reserved arm required')
            if (self.db.execute("SELECT 1 FROM attempts WHERE state IN ('dispatched','unknown')").fetchone()
                    or self.db.execute("SELECT 1 FROM external_envelopes WHERE state IN ('dispatched','unknown')").fetchone()):
                raise ValueError('another request is active or outcome is unknown')
            if self.db.execute('SELECT 1 FROM external_envelopes WHERE id=?', (request_id,)).fetchone():
                raise ValueError('request ID was already used by an external run')
            used = self._arm_calls_charged(pair_id, arm)
            if used >= json.loads(pair['caps'])[arm]:
                raise ValueError('arm call cap exhausted')
            self.db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)',
                            (request_id, pair_id, arm, instant, 'dispatched', None, None, None))
            self.db.commit()
            return policy['deadline'] - instant
        except BaseException:
            self.db.rollback()
            raise

    def claim_envelope(self, pair_id, arm, request_id, call_bound, *, model='gpt-6.1-sol',
                       effort='medium', now=None):
        """Reserve a whole external app run before dispatching its one POST.

        The bound is charged as model calls until a caller validates a terminal
        original run export and reconciles its actual call count. No per-call IDs
        are invented for the external run.
        """
        instant = time.time() if now is None else now
        if (not isinstance(request_id, str) or not request_id or len(request_id) > 256
                or type(call_bound) is not int or not 1 <= call_bound <= EXTERNAL_RUN_CALL_CEILING):
            raise ValueError('persist one bounded external request ID and a call bound in 1..80')
        try:
            self._begin()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            pair = self.db.execute('SELECT * FROM pairs WHERE id=?', (pair_id,)).fetchone()
            if pair is not None and (model != pair['requested_model'] or effort != policy['effort']):
                raise ValueError('model/effort mismatch; fallback forbidden')
            if instant >= policy['deadline']:
                raise ValueError('wall-clock budget exhausted')
            if pair is None or pair['state'] != 'active' or arm not in json.loads(pair['caps']):
                raise ValueError('active reserved arm required')
            if (self.db.execute("SELECT 1 FROM attempts WHERE state IN ('dispatched','unknown')").fetchone()
                    or self.db.execute("SELECT 1 FROM external_envelopes WHERE state IN ('dispatched','unknown')").fetchone()):
                raise ValueError('another request is active or outcome is unknown')
            if (self.db.execute('SELECT 1 FROM attempts WHERE id=?', (request_id,)).fetchone()
                    or self.db.execute('SELECT 1 FROM external_envelopes WHERE id=?', (request_id,)).fetchone()):
                raise ValueError('request ID was already used; external submissions are never replayed')
            used = self._arm_calls_charged(pair_id, arm)
            arm_cap = json.loads(pair['caps'])[arm]
            if used + call_bound > arm_cap:
                raise ValueError('external run call bound exceeds its reserved arm cap')
            self.db.execute('''INSERT INTO external_envelopes
                (id,pair_id,arm,started,call_bound,actual_calls,state,evidence) VALUES(?,?,?,?,?,?,?,?)''',
                (request_id, pair_id, arm, instant, call_bound, None, 'dispatched', None))
            self.db.commit()
            return policy['deadline'] - instant
        except BaseException:
            self.db.rollback()
            raise

    def finish_envelope(self, request_id, state, *, actual_calls=None, evidence,
                        effective_model=None, effective_effort=None):
        """Reconcile only from a caller-validated terminal original run export.

        For completed/failed/contained outcomes, ``actual_calls`` is required
        and the caller is responsible for validating that export. Unknown or
        uncounted outcomes retain the entire original reservation and block all
        other dispatch until a later validated reconciliation.
        """
        if state not in {'completed', 'failed', 'unknown', 'contained'}:
            raise ValueError('invalid external run outcome')
        if not isinstance(evidence, str) or not evidence:
            raise ValueError('original run evidence location required')
        if state == 'unknown':
            if actual_calls is not None:
                raise ValueError('unknown outcome cannot release a partial call count')
        elif type(actual_calls) is not int or actual_calls < 0:
            raise ValueError('validated terminal evidence must provide a nonnegative actual call count')
        try:
            self._begin()
            old = self.db.execute('SELECT * FROM external_envelopes WHERE id=?', (request_id,)).fetchone()
            if old is None or old['state'] not in {'dispatched', 'unknown'}:
                raise ValueError('only original active/unknown external run can be reconciled')
            if actual_calls is not None and actual_calls > old['call_bound']:
                raise ValueError('validated external run exceeded its pre-dispatch call bound')
            pair = self.db.execute('SELECT * FROM pairs WHERE id=?', (old['pair_id'],)).fetchone()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            # Existing default-model reconciliation remains compatible with its
            # caller-validated original export. A newly selected model cannot
            # inherit that legacy omission: require observed identity explicitly.
            require_identity = (pair['requested_model'] != policy['model']
                                or effective_model is not None or effective_effort is not None)
            if state == 'completed' and require_identity and (
                    effective_model != pair['requested_model'] or effective_effort != policy['effort']):
                raise ValueError('completed external inference requires verified pair model and effort')
            stored_state = state
            # A terminal label without a reconciled count must remain fully
            # charged. The public API requires counts for terminals, but retain
            # this guard should a later caller add an uncounted terminal state.
            if state != 'unknown' and actual_calls is None:
                stored_state = 'unknown'
            self.db.execute('''UPDATE external_envelopes
                SET state=?,actual_calls=?,evidence=?,effective_model=?,effective_effort=? WHERE id=?''',
                (stored_state, actual_calls, evidence, effective_model, effective_effort, request_id))
            self.db.commit()
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
            pair = self.db.execute('SELECT * FROM pairs WHERE id=?', (old['pair_id'],)).fetchone()
            policy = self.db.execute('SELECT * FROM policy').fetchone()
            if state == 'completed' and (effective_model != pair['requested_model'] or effective_effort != policy['effort']):
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
            if (self.db.execute("SELECT 1 FROM attempts WHERE pair_id=? AND state IN ('dispatched','unknown')",
                               (pair_id,)).fetchone()
                    or self.db.execute("SELECT 1 FROM external_envelopes WHERE pair_id=? AND state IN ('dispatched','unknown')",
                                       (pair_id,)).fetchone()):
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
        envelopes = [dict(r) for r in self.db.execute('SELECT * FROM external_envelopes ORDER BY started,id')]
        pairs = [dict(r) for r in self.db.execute('SELECT * FROM pairs ORDER BY created,id')]
        calls_consumed = len(attempts) + sum(row['actual_calls'] or 0 for row in envelopes)
        calls_charged = len(attempts) + sum(self._envelope_charge(row) for row in envelopes)
        return {'schema': 'ai4r-value-schedule:1', 'policy': policy,
                'attempts': attempts, 'external_envelopes': envelopes, 'pairs': pairs,
                'calls_consumed': calls_consumed, 'calls_charged': calls_charged,
                'calls_remaining': policy['max_calls'] - calls_charged,
                'external_run_call_ceiling': EXTERNAL_RUN_CALL_CEILING,
                'allowed_pair_models': sorted(MODELS),
                'engineering_agent_usage': 'outside experimental arm measurements'}

    @staticmethod
    def _envelope_charge(row):
        return row['actual_calls'] if row['actual_calls'] is not None else row['call_bound']

    def _calls_charged(self):
        attempts = self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        envelopes = self.db.execute('SELECT call_bound,actual_calls FROM external_envelopes').fetchall()
        return attempts + sum(self._envelope_charge(row) for row in envelopes)

    def _arm_calls_charged(self, pair_id, arm):
        attempts = self.db.execute('SELECT COUNT(*) FROM attempts WHERE pair_id=? AND arm=?',
                                   (pair_id, arm)).fetchone()[0]
        envelopes = self.db.execute('SELECT call_bound,actual_calls FROM external_envelopes WHERE pair_id=? AND arm=?',
                                    (pair_id, arm)).fetchall()
        return attempts + sum(self._envelope_charge(row) for row in envelopes)


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
