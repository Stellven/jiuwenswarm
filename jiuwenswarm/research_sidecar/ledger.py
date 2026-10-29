"""Append-only attempt events with atomic immutable action claims."""
import hashlib
import json
from pathlib import Path
import sqlite3
from .evidence import canonical


class Ledger:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,isolation_level=None);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL);CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT,kind TEXT,payload TEXT);')
    def claim(self,ident,payload):
        digest=hashlib.sha256(canonical(payload)).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT fingerprint FROM attempts WHERE id=?',(ident,)).fetchone()
            if row and row[0]!=digest:raise ValueError('attempt identity changed content')
            if not row:self.db.execute('INSERT INTO attempts VALUES(?,?)',(ident,digest))
            self.db.execute('COMMIT');return not row
        except BaseException:self.db.execute('ROLLBACK');raise
    def claimed(self,ident,payload):
        """Read-only restart check; never allocate an action or change its bytes."""
        row=self.db.execute('SELECT fingerprint FROM attempts WHERE id=?',(ident,)).fetchone()
        if row is None:return False
        if row[0]!=hashlib.sha256(canonical(payload)).hexdigest():raise ValueError('attempt identity changed content')
        return True
    def event(self,ident,kind,payload):self.db.execute('INSERT INTO events(id,kind,payload) VALUES(?,?,?)',(ident,kind,canonical(payload).decode()))
    def events(self,ident):return [{'sequence':r[0],'kind':r[1],'payload':json.loads(r[2])} for r in self.db.execute('SELECT seq,kind,payload FROM events WHERE id=? ORDER BY seq',(ident,))]
    def close(self):self.db.close()
