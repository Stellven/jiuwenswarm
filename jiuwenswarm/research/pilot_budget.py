"""Opt-in, durable hard limit for an informal live completion campaign."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
import time


class PilotBudgetError(RuntimeError):
    pass


class PilotLimitReached(PilotBudgetError):
    pass


def _directory(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise PilotBudgetError('Pilot budget path must be an absolute nonsymlink directory')
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PilotBudgetError('Pilot budget directory requires current owner and mode0700')
    return path


def prepare(directory, campaign_id, *, max_calls=900, wall_s=10800):
    if not isinstance(campaign_id, str) or not campaign_id or len(campaign_id) > 128:
        raise PilotBudgetError('A bounded campaign ID is required')
    if type(max_calls) is not int or not 1 <= max_calls <= 900 or type(wall_s) is not int or not 1 <= wall_s <= 10800:
        raise PilotBudgetError('Pilot ceilings are 900 attempts and10800 seconds')
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = _directory(directory)
    policy = {'schema': 'ai4r-pilot-budget:1', 'campaign_id': campaign_id,
              'max_calls': max_calls, 'wall_s': wall_s,
              'allowed_models': ['gpt-6-luna', 'gpt-6.1-sol']}
    with (directory / 'policy.json').open('x', encoding='utf-8') as stream:
        os.chmod(stream.name, 0o600)
        json.dump(policy, stream, sort_keys=True)
    connection = sqlite3.connect(directory / 'attempts.sqlite3')
    try:
        os.chmod(directory / 'attempts.sqlite3', 0o600)
        connection.executescript('CREATE TABLE campaign (id INTEGER PRIMARY KEY CHECK(id=1), started REAL, latest REAL);'
                                'INSERT INTO campaign VALUES(1,NULL,NULL);'
                                'CREATE TABLE attempts (request_id TEXT PRIMARY KEY, model TEXT NOT NULL, started REAL NOT NULL, '
                                'ended REAL, outcome TEXT, effective_model TEXT);')
        connection.commit()
    finally:
        connection.close()
    return policy


class PilotBudget:
    def __init__(self, directory):
        self.directory = _directory(directory)
        for name in ('policy.json', 'attempts.sqlite3'):
            path = self.directory / name
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise PilotBudgetError('Pilot policy/ledger custody is invalid')
        self.policy = json.loads((self.directory / 'policy.json').read_text('utf-8'))
        if (set(self.policy) != {'schema','campaign_id','max_calls','wall_s','allowed_models'}
                or self.policy['schema'] != 'ai4r-pilot-budget:1'
                or type(self.policy['max_calls']) is not int or not 1 <= self.policy['max_calls'] <= 900
                or type(self.policy['wall_s']) is not int or not 1 <= self.policy['wall_s'] <= 10800
                or self.policy['allowed_models'] != ['gpt-6-luna', 'gpt-6.1-sol']):
            raise PilotBudgetError('Pilot policy is invalid')
        self.db = sqlite3.connect(self.directory / 'attempts.sqlite3', timeout=10)

    def close(self):
        self.db.close()

    def claim(self, request_id, model, *, now=None):
        if model not in self.policy['allowed_models']:
            raise PilotBudgetError('Pilot requires an explicitly selected approved model; no fallback')
        instant = time.time() if now is None else now
        try:
            self.db.execute('BEGIN IMMEDIATE')
            started, latest = self.db.execute('SELECT started,latest FROM campaign WHERE id=1').fetchone()
            count = self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
            if latest is not None and instant < latest:
                raise PilotBudgetError('Pilot clock moved backwards')
            if count >= self.policy['max_calls']:
                raise PilotLimitReached('Pilot call budget exhausted')
            started = instant if started is None else started
            remaining = self.policy['wall_s'] - (instant - started)
            if remaining <= 0:
                raise PilotLimitReached('Pilot wall-clock budget exhausted')
            self.db.execute('INSERT INTO attempts(request_id,model,started) VALUES(?,?,?)', (request_id, model, instant))
            self.db.execute('UPDATE campaign SET started=?,latest=? WHERE id=1', (started, instant))
            self.db.commit()
            return remaining
        except BaseException:
            self.db.rollback()
            raise

    def finish(self, request_id, outcome, effective_model=None):
        self.db.execute('UPDATE attempts SET ended=?,outcome=?,effective_model=? WHERE request_id=? AND ended IS NULL',
                        (time.time(), outcome, effective_model, request_id))
        self.db.commit()

    def inspect(self):
        started, latest = self.db.execute('SELECT started,latest FROM campaign WHERE id=1').fetchone()
        return {'policy': self.policy, 'started_at_unix': started, 'latest_claim_unix': latest,
                'attempts': self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],
                'outcomes': dict(self.db.execute("SELECT COALESCE(outcome,'unknown'),COUNT(*) FROM attempts GROUP BY outcome"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'status'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--campaign-id')
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.directory, args.campaign_id)
    else:
        budget = PilotBudget(args.directory)
        try:
            result = budget.inspect()
        finally:
            budget.close()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
