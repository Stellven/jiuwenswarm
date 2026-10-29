"""Protected immutable exact-byte records; mutable indexes never replace evidence."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import re
import tempfile
import errno
import sys


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def _install_exclusive(pending,path):
    """Atomically install complete bytes, without overwrite or hardlinks."""
    if os.name=='nt':
        os.rename(pending,path) # Windows refuses an existing destination.
        return
    if sys.platform!='linux':raise OSError(errno.ENOTSUP,'Exclusive atomic record installation is unavailable')
    # Linux renameat2(2), RENAME_NOREPLACE. Never fall back to rename/replace:
    # their Unix overwrite semantics would destroy immutable prior evidence.
    try:
        import ctypes
        renameat2=ctypes.CDLL(None,use_errno=True).renameat2
    except (ImportError,AttributeError,OSError):raise OSError(errno.ENOSYS,'Exclusive atomic record installation is unavailable') from None
    renameat2.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    renameat2.restype=ctypes.c_int
    ctypes.set_errno(0)
    if renameat2(-100,os.fsencode(pending),-100,os.fsencode(path),1)!=0:
        error=ctypes.get_errno() or errno.EIO
        raise OSError(error,os.strerror(error),os.fspath(path))


class RecordStore:
    def __init__(self,root,*,file_mode=0o600):
        if file_mode not in (0o600,0o640):raise ValueError('Unknown protected record mode')
        self.file_mode=file_mode
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=sqlite3.connect(self.root/'index.sqlite',check_same_thread=False,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts(session TEXT,sequence INTEGER,ref TEXT,PRIMARY KEY(session,sequence))')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,ref TEXT NOT NULL,state TEXT NOT NULL,result TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS proposer_starts(session TEXT,sequence INTEGER,ref TEXT NOT NULL,PRIMARY KEY(session,sequence))')
        # Private indexes only: old unmapped records are retained, never treated
        # as proof that no original terminal was signed before an interruption.
        self.db.execute('CREATE TABLE IF NOT EXISTS history_jobs(id TEXT PRIMARY KEY,ref TEXT NOT NULL,session_ref TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS session_history(session TEXT PRIMARY KEY,session_ref TEXT NOT NULL,context_ref TEXT NOT NULL,population_ref TEXT,unsigned_ref TEXT,signed_ref TEXT,uncertain INTEGER NOT NULL)')
        self.lock=threading.RLock()
    def put_bytes(self,data):
        digest=hashlib.sha256(data).hexdigest();path=self.root/(digest+'.json')
        # Never expose a partial file at a deterministic immutable name. A
        # process may die at any instruction; orphan temporary bytes stay in
        # this protected root, while a completed install is never overwritten.
        fd,name=tempfile.mkstemp(prefix='.pending-',dir=self.root);pending=Path(name)
        try:
            with os.fdopen(fd,'wb') as f:
                if os.name=='posix':os.fchmod(f.fileno(),self.file_mode)
                f.write(data);f.flush();os.fsync(f.fileno())
            try:_install_exclusive(pending,path)
            except FileExistsError:
                if path.read_bytes()!=data:raise ValueError('immutable record collision')
            if os.name=='posix':
                directory=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(directory)
                finally:os.close(directory)
        finally:pending.unlink(missing_ok=True)
        return {'id':digest+'.json','sha256':digest}
    def put(self,value):return self.put_bytes(encoded(value))
    def read(self,ref):
        if set(ref)!={'id','sha256'} or not re.fullmatch('[a-f0-9]{64}',ref['sha256']) or ref['id']!=ref['sha256']+'.json':raise ValueError('invalid record reference')
        data=(self.root/ref['id']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=ref['sha256']:raise ValueError('record digest mismatch')
        return data
    def get(self,ref):return json.loads(self.read(ref))
    def attempts(self,session):
        return [json.loads(x[0]) for x in self.db.execute('SELECT ref FROM attempts WHERE session=? ORDER BY sequence',(session,))]
    def proposer_starts(self,session):
        return [json.loads(x[0]) for x in self.db.execute('SELECT ref FROM proposer_starts WHERE session=? ORDER BY sequence',(session,))]
    def record_proposer_start(self,session,value):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                if value['session_id']!=session or value['sequence']!=len(self.proposer_starts(session))+1:raise ValueError('proposer start sequence is not gapless')
                ref=self.put(value)
                self.db.execute('INSERT INTO proposer_starts VALUES(?,?,?)',(session,value['sequence'],encoded(ref).decode()))
                self.db.execute('COMMIT');return ref
            except BaseException:self.db.execute('ROLLBACK');raise
    def append_attempt(self,session,value):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                prior=self.attempts(session)
                if value['sequence']!=len(prior)+1 or value['previous_ref']!=(prior[-1] if prior else None):raise ValueError('attempt chain is not gapless')
                ref=self.put(value)
                self.db.execute('INSERT INTO attempts VALUES(?,?,?)',(session,value['sequence'],encoded(ref).decode()))
                self.db.execute('COMMIT');return ref
            except BaseException:self.db.execute('ROLLBACK');raise
    def close(self):self.db.close()
    def claim_job(self,ref):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                old=self.db.execute('SELECT ref FROM jobs WHERE id=?',(ref['id'],)).fetchone()
                if old and json.loads(old[0])!=ref:raise ValueError('job identity changed bytes')
                if not old:
                    self.db.execute('INSERT INTO jobs VALUES(?,?,?,NULL)',(ref['id'],encoded(ref).decode(),'started'))
                    self.db.execute('INSERT INTO history_jobs VALUES(?,?,NULL)',(ref['id'],encoded(ref).decode()))
                self.db.execute('COMMIT');return old is None
            except BaseException:self.db.execute('ROLLBACK');raise
    def job_state(self,ref):
        row=self.db.execute('SELECT ref,state,result FROM jobs WHERE id=?',(ref['id'],)).fetchone()
        if row is None:return {'state':'not_started'}
        if json.loads(row[0])!=ref:raise ValueError('job identity changed bytes')
        return json.loads(row[2]) if row[2] else {'state':'outcome_unknown','reason':'Started job has no durable terminal receipt; automatic replay forbidden.'}
    def finish_job(self,ref,result):
        self.put({'job_ref':ref,**result})
        changed=self.db.execute('UPDATE jobs SET state=?,result=? WHERE id=? AND result IS NULL',(result['state'],encoded(result).decode(),ref['id'])).rowcount
        if not changed:raise ValueError('terminal job state is immutable')
    def job_refs(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT ref FROM jobs ORDER BY id')]
    def job_session(self,ref):
        row=self.db.execute('SELECT ref,session_ref FROM history_jobs WHERE id=?',(ref['id'],)).fetchone()
        if row is None:return None
        if json.loads(row[0])!=ref:raise ValueError('Job identity changed bytes')
        return json.loads(row[1]) if row[1] is not None else None
    def bind_job_session(self,ref,session_ref):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                row=self.db.execute('SELECT ref,session_ref FROM history_jobs WHERE id=?',(ref['id'],)).fetchone()
                if row is None or json.loads(row[0])!=ref:raise ValueError('Legacy job has no durable terminal tracking; automatic replay forbidden')
                if row[1] is not None and json.loads(row[1])!=session_ref:raise ValueError('Job session changed bytes')
                if self.db.execute('SELECT 1 FROM history_jobs WHERE id<>? AND session_ref=?',(ref['id'],encoded(session_ref).decode())).fetchone():raise ValueError('Session is already bound to another job')
                self.db.execute('UPDATE history_jobs SET session_ref=? WHERE id=?',(encoded(session_ref).decode(),ref['id']))
                self.db.execute('COMMIT')
            except BaseException:self.db.execute('ROLLBACK');raise
    def begin_session_history(self,session,session_ref,context_ref):
        with self.lock:
            try:self.db.execute('INSERT INTO session_history VALUES(?,?,?,NULL,NULL,NULL,1)',(session,encoded(session_ref).decode(),encoded(context_ref).decode()))
            except sqlite3.IntegrityError:raise ValueError('Session history already exists; automatic replay forbidden') from None
    def session_history(self,session,session_ref,context_ref):
        row=self.db.execute('SELECT session_ref,context_ref,population_ref,unsigned_ref,signed_ref,uncertain FROM session_history WHERE session=?',(session,)).fetchone()
        if row is None:return None
        if json.loads(row[0])!=session_ref or json.loads(row[1])!=context_ref:raise ValueError('History session/context changed bytes')
        return {key:json.loads(value) if value is not None else None for key,value in zip(('population_ref','unsigned_ref','signed_ref'),row[2:5])}|{'containment_uncertain':bool(row[5])}
    def stage_terminal(self,session,session_ref,context_ref,population,result,*,containment_uncertain):
        population_ref=self.put(population);unsigned_ref=self.put(result)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                current=self.session_history(session,session_ref,context_ref)
                if current is None:raise ValueError('Terminal history tracking is absent; legacy originals remain unresolved')
                if current['unsigned_ref'] is not None:
                    if current['unsigned_ref']!=unsigned_ref or current['population_ref']!=population_ref:raise ValueError('Original terminal staging is immutable')
                else:self.db.execute('UPDATE session_history SET population_ref=?,unsigned_ref=?,uncertain=? WHERE session=?',(encoded(population_ref).decode(),encoded(unsigned_ref).decode(),int(containment_uncertain),session))
                self.db.execute('COMMIT');return unsigned_ref
            except BaseException:self.db.execute('ROLLBACK');raise
    def complete_terminal(self,session,session_ref,context_ref,signed):
        signed_ref=self.put(signed)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                current=self.session_history(session,session_ref,context_ref)
                if current is None or current['unsigned_ref'] is None:raise ValueError('Original unsigned terminal is absent')
                unsigned=self.get(current['unsigned_ref'])
                if {k:v for k,v in signed.items() if k not in {'signature','signer_key_id'}}!=unsigned:raise ValueError('Signed terminal changed original payload')
                if current['signed_ref'] is not None and current['signed_ref']!=signed_ref:raise ValueError('Original signed terminal is immutable')
                self.db.execute('UPDATE session_history SET signed_ref=? WHERE session=?',(encoded(signed_ref).decode(),session))
                self.db.execute('COMMIT');return signed_ref
            except BaseException:self.db.execute('ROLLBACK');raise
    def mark_history_uncertain(self,session,session_ref,context_ref):
        if self.session_history(session,session_ref,context_ref) is None:raise ValueError('Terminal tracking is absent')
        self.db.execute('UPDATE session_history SET uncertain=1 WHERE session=?',(session,))
    def _job_history(self,ref):
        session_ref=self.job_session(ref)
        if session_ref is None:return None
        history=self.db.execute('SELECT signed_ref,uncertain FROM session_history WHERE session_ref=?',(encoded(session_ref).decode(),)).fetchone()
        return history
    def retained_job_terminal(self,ref):
        row=self._job_history(ref)
        if row is None or row[0] is None:return None
        pin=json.loads(row[0]);return {'state':'terminal','result':(self.get(pin),pin)}
    def restore_job_terminal(self,ref,*,validate):
        session_ref=self.job_session(ref)
        if session_ref is None:return None
        row=self.db.execute('SELECT session,context_ref,population_ref,unsigned_ref,signed_ref FROM session_history WHERE session_ref=?',(encoded(session_ref).decode(),)).fetchone()
        if row is None or row[4] is None:return None
        sid=row[0];context_ref,population_ref,unsigned_ref,signed_ref=(json.loads(value) for value in row[1:])
        context=self.get(context_ref);session=self.get(context['session_bytes_ref']);validate('rsi-session',session)
        expected={'record_kind':'rsi-session-history-context:1','session_ref':session_ref,
            'session_bytes_ref':context['session_bytes_ref'],'parent_ref':context['parent_ref'],
            **{key:session[key] for key in ('parent_declaration_ref','target_profile_ref','hash_profile_ref',
                'chain_root_ref','configuration_ref','improver_ref','scoring_adapter_ref')}}
        if context!=expected or context['session_bytes_ref']['sha256']!=session_ref['sha256'] or session['session_id']!=sid:raise ValueError('Original cached session/context differs')
        unsigned=self.get(unsigned_ref);signed=self.get(signed_ref);validate('rsi-session-result',signed)
        if {k:v for k,v in signed.items() if k not in {'signature','signer_key_id'}}!=unsigned:raise ValueError('Original cached signed payload differs')
        starts=self.proposer_starts(sid);attempts=self.attempts(sid)
        population={'record_kind':'rsi-terminal-population:1','session_ref':session_ref,'context_ref':context_ref,
            'proposer_start_refs':starts,'attempt_refs':attempts,'queries_used':unsigned['queries_used']}
        if (self.get(population_ref)!=population or unsigned['session_ref']!=session_ref or unsigned['parent']!=session['parent']
                or unsigned['attempt_refs']!=attempts or unsigned['attempts_used']!=len(attempts) or len(starts)!=len(attempts)
                or len(attempts)>session['limits']['max_attempts'] or not 0<=unsigned['queries_used']<=session['limits']['session_query_limit']):raise ValueError('Original cached terminal population differs')
        previous=None;last_queries=0
        for sequence,(start_ref,attempt_ref) in enumerate(zip(starts,attempts),1):
            started=self.get(start_ref);attempt=self.get(attempt_ref);validate('rsi-attempt',attempt)
            expected={'record_kind':'rsi-proposer-start:1','session_id':sid,'sequence':sequence,'previous_ref':previous,
                'configuration_ref':session['configuration_ref'],'improver_ref':session['improver_ref']}
            if any(started.get(k)!=v for k,v in expected.items()):raise ValueError('Original cached start chain differs')
            expected={'schema_version':'2.0.0','session_id':sid,'sequence':sequence,'previous_ref':previous,
                'target_ref':session['target_profile_ref'],'parent_ref':context['parent_ref'],'configuration_ref':session['configuration_ref'],
                'hash_profile_ref':session['hash_profile_ref'],'chain_root_ref':session['chain_root_ref']}
            if any(attempt[k]!=v for k,v in expected.items()) or not last_queries<=attempt['queries_used']<=unsigned['queries_used']:raise ValueError('Original cached attempt chain differs')
            previous=attempt_ref;last_queries=attempt['queries_used']
        # This restores history only. No current custody/cleanup observation is
        # available, so it cannot restore a successful stop acknowledgement.
        self.mark_history_uncertain(sid,session_ref,context_ref)
        return {'state':'terminal','result':(signed,signed_ref)}
    def job_history_started(self,ref):return self._job_history(ref) is not None
    def job_containment_uncertain(self,ref):
        row=self._job_history(ref)
        return row is None or bool(row[1])
