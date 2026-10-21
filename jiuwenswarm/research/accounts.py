"""Durable local product identity/preferences, independent of research run deletion."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from pathlib import Path

from .configuration import PreferenceError, resolve_preferences
from .contracts import ResearchError


class AccountStore:
    def __init__(self, directory: str | Path):
        supplied = Path(directory)
        if supplied.is_symlink():
            raise ValueError('account directory cannot be a symlink')
        root = supplied.resolve(); root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        path = root / 'accounts.sqlite3'
        if path.is_symlink():
            raise ValueError('account database cannot be a symlink')
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        os.chmod(path, 0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS accounts (slot TEXT PRIMARY KEY, account_id TEXT UNIQUE NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS preferences (account_id TEXT NOT NULL, scope TEXT NOT NULL, scope_id TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(account_id,scope,scope_id))')
        self.db.execute("CREATE TABLE IF NOT EXISTS account_locales (account_id TEXT PRIMARY KEY, language TEXT NOT NULL CHECK(language IN ('zh','en')))")
        self.db.commit()

    def close(self):
        self.db.close()

    def primary(self) -> dict:
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO accounts VALUES(?,?)', ('primary', 'account:' + secrets.token_hex(16)))
            value = self.db.execute('SELECT account_id FROM accounts WHERE slot=?', ('primary',)).fetchone()[0]
        return {'account_id': value}

    def _require_account(self, account_id):
        if self.db.execute('SELECT 1 FROM accounts WHERE account_id=?', (account_id,)).fetchone() is None:
            raise PreferenceError('unknown local product account')

    def locale(self, account_id: str, language: str | None = None):
        if language is not None and language not in {'zh', 'en'}:
            raise PreferenceError('invalid language')
        with self.lock, self.db:
            self._require_account(account_id)
            if language is not None:
                self.db.execute('INSERT INTO account_locales VALUES(?,?) ON CONFLICT(account_id) DO UPDATE SET language=excluded.language',
                                (account_id, language))
            row = self.db.execute('SELECT language FROM account_locales WHERE account_id=?', (account_id,)).fetchone()
        return row[0] if row else None

    def save_preferences(self, account_id: str, scope: str, scope_id: str, values: dict, *, root: Path):
        if scope not in {'account', 'host', 'project'} or not isinstance(scope_id, str) or not scope_id:
            raise PreferenceError('invalid preference scope')
        validated = resolve_preferences(values, {}, {}, root=root)
        with self.lock, self.db:
            self._require_account(account_id)
            self.db.execute('INSERT INTO preferences VALUES(?,?,?,?) ON CONFLICT(account_id,scope,scope_id) DO UPDATE SET value=excluded.value',
                            (account_id, scope, scope_id, json.dumps(validated, sort_keys=True, allow_nan=False)))

    def resolve(self, account_id: str, host_id: str, project_id: str, *, root: Path):
        values = []
        with self.lock:
            self._require_account(account_id)
            for scope, scope_id in [('account', 'default'), ('host', host_id), ('project', project_id)]:
                row = self.db.execute('SELECT value FROM preferences WHERE account_id=? AND scope=? AND scope_id=?', (account_id, scope, scope_id)).fetchone()
                values.append(json.loads(row[0]) if row else {})
        return resolve_preferences(*values, root=root)

    def scoped_preferences(self, account_id, scope, scope_id):
        with self.lock:
            self._require_account(account_id)
            row = self.db.execute('SELECT value FROM preferences WHERE account_id=? AND scope=? AND scope_id=?',
                                  (account_id, scope, scope_id)).fetchone()
        return json.loads(row[0]) if row else {}


class PreferenceService:
    """Native Settings provider with server-derived account/host/project scope."""
    def __init__(self, store, *, host_id: str, project_id: str, root: Path):
        if not host_id or not project_id:
            raise ValueError('Protected host and project identities are required')
        self.store, self.host_id, self.project_id, self.root = store, host_id, project_id, root.resolve()

    def _authorize(self, principal):
        principal.require('settings', self.project_id)
        if principal.account_id != self.store.primary()['account_id']:
            raise ResearchError('auth', 'Account is outside the initialized product identity')

    def get(self, principal):
        self._authorize(principal)
        scopes = {scope: self.store.scoped_preferences(principal.account_id, scope, scope_id)
                  for scope, scope_id in [('account', 'default'), ('host', self.host_id), ('project', self.project_id)]}
        return {'scopes': scopes, 'effective': self.store.resolve(principal.account_id, self.host_id, self.project_id, root=self.root),
                'applies_on': 'next_start'}

    def locale(self, principal, language=None):
        self._authorize(principal)
        return self.store.locale(principal.account_id, language)

    def save(self, principal, scope, values):
        self._authorize(principal)
        scope_id = {'account': 'default', 'host': self.host_id, 'project': self.project_id}.get(scope)
        if scope_id is None:
            raise ResearchError('validation', 'Unknown preference scope')
        try:
            self.store.save_preferences(principal.account_id, scope, scope_id, values, root=self.root)
        except PreferenceError as exc:
            raise ResearchError('validation', 'Unknown, invalid or protected preference field') from exc
        return self.get(principal)
