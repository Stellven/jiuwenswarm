"""Custodian-only fixture identities and durable charge-before-release reservations."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading


class ExposureError(ValueError):pass


def require_custody(path,uid=None):
    root=Path(path)
    for item in [root,*root.rglob('*')]:
        info=item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o077 or (uid is not None and info.st_uid!=uid):
            raise ExposureError('custodian storage ownership or permissions unsafe')
        if stat.S_ISREG(info.st_mode) and info.st_nlink!=1:raise ExposureError('custodian hardlink denied')


class ExposureLedger:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=sqlite3.connect(path,isolation_level=None,check_same_thread=False)
        self.db.row_factory=sqlite3.Row;self.lock=threading.RLock()
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS fixtures(identity TEXT PRIMARY KEY,partition_hash TEXT UNIQUE NOT NULL,partitions TEXT NOT NULL,lifetime INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,fixture TEXT NOT NULL,cap INTEGER NOT NULL,lifetime_cap INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0,final_sealed INTEGER NOT NULL DEFAULT 0,halted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS actions(session TEXT,id TEXT,kind TEXT,state TEXT,result TEXT,PRIMARY KEY(session,id));''')
        if 'fingerprint' not in {r[1] for r in self.db.execute('PRAGMA table_info(actions)')}:
            self.db.execute('ALTER TABLE actions ADD COLUMN fingerprint TEXT')
        try:os.chmod(path,0o600)
        except OSError:pass
    def register(self,identity,partitions,*,known_bad,known_good):
        if set(partitions)!={'development','hidden_loop','hidden_final','platform'}:raise ExposureError('four partitions required')
        if known_bad<10 or known_good<3:raise ExposureError('calibration controls incomplete')
        all_ids=[]
        for name,items in partitions.items():
            if not items or len(items)!=len(set(items)) or name in {'hidden_loop','hidden_final'} and len(items)<20:raise ExposureError('invalid fixture population')
            all_ids.extend(items)
        if len(all_ids)!=len(set(all_ids)):raise ExposureError('partition overlap')
        canonical=json.dumps({k:sorted(v) for k,v in sorted(partitions.items())},sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        with self.lock:
            row=self.db.execute('SELECT * FROM fixtures WHERE identity=? OR partition_hash=?',(identity,digest)).fetchone()
            if row:
                if row['partition_hash']!=digest:raise ExposureError('fixture identity cannot be reclassified')
                return row['identity'] # Identical bytes/identities repackaged retain original lifetime.
            # Existing per-fixture lineage may not be overlapped under a new set ID.
            for prior in self.db.execute('SELECT partitions FROM fixtures'):
                if set(all_ids)&{i for group in json.loads(prior[0]).values() for i in group}:raise ExposureError('fixture lineage overlap requires custodian review')
            self.db.execute('INSERT INTO fixtures(identity,partition_hash,partitions) VALUES(?,?,?)',(identity,digest,canonical))
        return identity
    def open_session(self,session,fixture,*,session_cap=30,lifetime_cap=90):
        if isinstance(session_cap,bool) or not 0<session_cap<=30 or not session_cap<=lifetime_cap<=90:raise ExposureError('query cap widened')
        with self.lock:
            if not self.db.execute('SELECT 1 FROM fixtures WHERE identity=?',(fixture,)).fetchone():raise ExposureError('unregistered fixture identity')
            old=self.db.execute('SELECT * FROM sessions WHERE id=?',(session,)).fetchone()
            if old:
                if (old['fixture'],old['cap'],old['lifetime_cap'])!=(fixture,session_cap,lifetime_cap):raise ExposureError('session configuration changed')
                return
            self.db.execute('INSERT INTO sessions(id,fixture,cap,lifetime_cap) VALUES(?,?,?,?)',(session,fixture,session_cap,lifetime_cap))
    def state(self,session):
        row=self.db.execute('SELECT s.*,f.lifetime FROM sessions s JOIN fixtures f ON f.identity=s.fixture WHERE s.id=?',(session,)).fetchone()
        if not row:raise ExposureError('unknown session')
        return dict(row)
    def reserve(self,session,action,kind,*,fingerprint=None):
        if kind not in {'loop','final'}:raise ExposureError('invalid evaluation operation')
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                s=self.state(session)
                old=self.db.execute('SELECT * FROM actions WHERE session=? AND id=?',(session,action)).fetchone()
                if old:
                    if old['kind']!=kind or old['fingerprint']!=fingerprint:raise ExposureError('action identity changed content')
                    self.db.execute('COMMIT');return {**dict(old),'fresh':False,'queries_used':s['used'],'queries_left':min(s['cap']-s['used'],s['lifetime_cap']-s['lifetime'])}
                if s['halted']:raise ExposureError('session permanently halted')
                if kind=='loop':
                    if s['used']>=s['cap'] or s['lifetime']>=s['lifetime_cap']:raise ExposureError('query budget exhausted')
                    self.db.execute('UPDATE sessions SET used=used+1 WHERE id=?',(session,))
                    self.db.execute('UPDATE fixtures SET lifetime=lifetime+1 WHERE identity=?',(s['fixture'],))
                else:
                    if s['final_sealed']:raise ExposureError('final already sealed')
                    self.db.execute('UPDATE sessions SET final_sealed=1 WHERE id=?',(session,))
                self.db.execute('INSERT INTO actions(session,id,kind,state,result,fingerprint) VALUES(?,?,?,?,NULL,?)',(session,action,kind,'reserved',fingerprint))
                s=self.state(session);self.db.execute('COMMIT')
                return {'state':'reserved','fresh':True,'queries_used':s['used'],'queries_left':min(s['cap']-s['used'],s['lifetime_cap']-s['lifetime'])}
            except BaseException:self.db.execute('ROLLBACK');raise
    def complete(self,session,action,result):
        encoded=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)
        with self.lock:
            old=self.db.execute('SELECT state,result FROM actions WHERE session=? AND id=?',(session,action)).fetchone()
            if not old:raise ExposureError('evaluation was not reserved')
            if old['state']=='complete' and old['result']!=encoded:raise ExposureError('completed evaluation is immutable')
            self.db.execute('UPDATE actions SET state=?,result=? WHERE session=? AND id=?',('complete',encoded,session,action))
    def halt(self,session):self.db.execute('UPDATE sessions SET halted=1 WHERE id=?',(session,))
    def close(self):self.db.close()
