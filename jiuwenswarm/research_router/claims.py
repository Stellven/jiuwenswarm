"""Atomic router-owned claims. Never owns a provider or core dispatch claim."""
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .request_validation import json_bytes


class ClaimConflict(ValueError):
    pass


class ClaimStore:
    def __init__(self, path, *, clock=time.time, recover=True):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL"); self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("CREATE TABLE IF NOT EXISTS claims(execution_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,fingerprint TEXT NOT NULL,state TEXT NOT NULL,decision TEXT,ready_at REAL,alternate_used INTEGER NOT NULL DEFAULT 0); CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,execution_id TEXT NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL,recorded_at REAL NOT NULL);")
        if recover:
            with self._transaction():
                rows = self.db.execute("SELECT execution_id FROM claims WHERE state IN ('claimed','started')").fetchall()
                for row in rows:
                    self.db.execute("UPDATE claims SET state='outcome_unknown' WHERE execution_id=?", (row[0],))
                    self._event(row[0], "outcome_unknown", {"reason": "owner_interrupted_no_replay"})

    class _Transaction:
        def __init__(self, store): self.store = store
        def __enter__(self): self.store.lock.acquire(); self.store.db.execute("BEGIN IMMEDIATE")
        def __exit__(self, kind, value, tb):
            try: self.store.db.execute("ROLLBACK" if kind else "COMMIT")
            finally: self.store.lock.release()

    def _transaction(self): return self._Transaction(self)
    def _event(self, key, event, detail):
        self.db.execute("INSERT INTO events(execution_id,event,detail,recorded_at) VALUES(?,?,?,?)", (key, event, json_bytes(detail).decode(), self.clock()))

    def claim(self, execution_id, user_id, request):
        fingerprint = hashlib.sha256(json_bytes(request)).hexdigest()
        with self._transaction():
            row = self.db.execute("SELECT * FROM claims WHERE execution_id=?", (execution_id,)).fetchone()
            if row:
                if row["user_id"] != user_id or row["fingerprint"] != fingerprint: raise ClaimConflict("execution_identity_conflict")
                return ("in_progress" if row["state"] == "claimed" else row["state"]), self._decode(row)
            self.db.execute("INSERT INTO claims(execution_id,user_id,fingerprint,state) VALUES(?,?,?,'claimed')", (execution_id,user_id,fingerprint))
            self._event(execution_id, "claimed", {"fingerprint": fingerprint})
            return "claimed", None

    @staticmethod
    def _decode(row):
        result = dict(row)
        if result["decision"] is not None: result["decision"] = json.loads(result["decision"])
        return result

    def lookup(self, key):
        with self.lock:
            row = self.db.execute("SELECT * FROM claims WHERE execution_id=?", (key,)).fetchone()
            if row is None: raise ClaimConflict("unknown_execution")
            result = self._decode(row)
            if result["state"] == "ready" and self.clock() >= result["ready_at"] + 30: result["state"] = "expired"
            return result

    def ready(self, key, decision):
        with self._transaction():
            row = self.db.execute("SELECT state FROM claims WHERE execution_id=?", (key,)).fetchone()
            if row is None or row[0] != "claimed": raise ClaimConflict("claim_not_owned")
            encoded = json_bytes(decision).decode()
            self.db.execute("UPDATE claims SET state='ready',decision=?,ready_at=? WHERE execution_id=?", (encoded,self.clock(),key))
            self._event(key,"ready",decision)

    def reject(self, key, reply):
        with self._transaction():
            row = self.db.execute("SELECT state FROM claims WHERE execution_id=?", (key,)).fetchone()
            if not row or row[0] != "claimed": raise ClaimConflict("claim_not_owned")
            self.db.execute("UPDATE claims SET state='failed',decision=? WHERE execution_id=?", (json_bytes(reply).decode(),key))
            self._event(key,"failed",reply)

    def note(self, key, event, detail):
        with self._transaction(): self._event(key,event,detail)

    def alternate(self, key, model_id, original_eligible):
        with self._transaction():
            row = self.db.execute("SELECT state,alternate_used,ready_at FROM claims WHERE execution_id=?", (key,)).fetchone()
            if not row or row[0] not in {"claimed", "ready"} or row[1] or model_id not in original_eligible:
                raise ClaimConflict("alternate_denied")
            if row[0] == "ready" and self.clock() >= row[2]+30: raise ClaimConflict("decision_expired")
            self.db.execute("UPDATE claims SET alternate_used=1 WHERE execution_id=?", (key,))
            self._event(key,"alternate",{"model_id":model_id})

    def start(self, key):
        with self._transaction():
            row = self.db.execute("SELECT state,ready_at FROM claims WHERE execution_id=?",(key,)).fetchone()
            if not row or row[0] != "ready" or self.clock() >= row[1]+30: raise ClaimConflict("decision_not_ready")
            self.db.execute("UPDATE claims SET state='started' WHERE execution_id=?", (key,)); self._event(key,"started",{})

    def terminal(self, key, state):
        if state not in {"completed","failed","outcome_unknown","cancelled"}: raise ClaimConflict("invalid_terminal")
        with self._transaction():
            row=self.db.execute("SELECT state FROM claims WHERE execution_id=?",(key,)).fetchone()
            if not row or row[0] in {"completed","failed","outcome_unknown","cancelled"}: raise ClaimConflict("terminal_immutable")
            self.db.execute("UPDATE claims SET state=? WHERE execution_id=?", (state,key)); self._event(key,state,{})

    def events(self, key):
        with self.lock: return [{"event":r[0],"detail":json.loads(r[1]),"recorded_at":r[2]} for r in self.db.execute("SELECT event,detail,recorded_at FROM events WHERE execution_id=? ORDER BY seq",(key,))]

    def close(self): self.db.close()

