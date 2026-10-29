"""Offline, read-only inspection of original signed RSI job history.

Only private disposable SQLite snapshots are opened. Original databases, WAL,
indexes and blobs are never migrated, recovered, checkpointed or written. This
module has no worker, model, custodian, lease, signing or runtime-factory path.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

from .bootstrap import load_config
from .records import encoded
from .session_policy import _contracts
from .signing import verify

MAX_BLOB=4*1024*1024
MAX_DATABASE=128*1024*1024
MAX_EXPORT=4*1024*1024-65536


def _path(value):
    path=Path(value)
    if not path.is_absolute() or '..' in path.parts or any(item.is_symlink() for item in (path,*path.parents)):
        raise ValueError('Original protected history path required')
    return path


def _directory(value,uid=12001):
    path=_path(value);meta=path.stat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=uid or meta.st_mode&0o077:
        raise ValueError('Private history directory custody differs')
    return path


def _meta(path,uid,maximum,*,optional=False):
    path=_path(path)
    try:meta=path.lstat()
    except FileNotFoundError:
        if optional:return None
        raise
    owners=uid if isinstance(uid,tuple) else (uid,)
    if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or meta.st_uid not in owners
            or meta.st_mode&0o022 or meta.st_size>maximum):
        raise ValueError('Original history file custody or bound differs')
    return (meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns,meta.st_ctime_ns)


def _read(path,uid=12001,maximum=MAX_BLOB):
    before=_meta(path,uid,maximum)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(descriptor)
        if (meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns,meta.st_ctime_ns)!=before:
            raise ValueError('Original history file changed while opening')
        with os.fdopen(descriptor,'rb',closefd=False) as stream:data=stream.read(maximum+1)
    finally:os.close(descriptor)
    if len(data)>maximum or _meta(path,uid,maximum)!=before:
        raise ValueError('Original history file changed while reading')
    return data


def _json(raw):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Duplicate historical record key')
            value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite historical value')))


def _ref(pin):
    if (not isinstance(pin,dict) or set(pin)!={'id','sha256'} or not isinstance(pin['id'],str) or not pin['id']
            or not isinstance(pin['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',pin['sha256'])):
        raise ValueError('Exact historical reference required')


def _snapshot(database,destination):
    """Copy a stable DB/WAL pair; SQLite may create SHM only in this copy."""
    database=_path(database)
    source=[database,Path(str(database)+'-wal')]
    journal=Path(str(database)+'-journal')
    if _meta(journal,12001,MAX_DATABASE,optional=True) not in (None,):
        if journal.stat().st_size:raise ValueError('Unresolved historical rollback journal')
    _meta(Path(str(database)+'-shm'),12001,MAX_DATABASE,optional=True)
    for _ in range(2):
        before=[_meta(path,12001,MAX_DATABASE,optional=index==1) for index,path in enumerate(source)]
        digests=[]
        for index,path in enumerate(source):
            target=destination if index==0 else Path(str(destination)+'-wal')
            if before[index] is None:
                target.unlink(missing_ok=True);digests.append(None);continue
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
            digest=hashlib.sha256();size=0
            try:
                with os.fdopen(descriptor,'rb',closefd=False) as src,open(target,'wb') as dst:
                    os.chmod(target,0o600)
                    while True:
                        data=src.read(1024*1024)
                        if not data:break
                        size+=len(data)
                        if size>MAX_DATABASE:raise ValueError('Historical database snapshot exceeds bound')
                        digest.update(data);dst.write(data)
            finally:os.close(descriptor)
            if size!=before[index][2]:raise ValueError('Historical snapshot length changed')
            digests.append(digest.hexdigest())
        after=[_meta(path,12001,MAX_DATABASE,optional=index==1) for index,path in enumerate(source)]
        if before!=after:continue
        stable=True
        for index,path in enumerate(source):
            if after[index] is None:continue
            digest=hashlib.sha256(_read(path,maximum=MAX_DATABASE)).hexdigest()
            if digest!=digests[index]:stable=False
        journal_state=_meta(journal,12001,MAX_DATABASE,optional=True)
        if journal_state is not None and journal_state[2]:raise ValueError('Unresolved historical rollback journal')
        if stable and after==[_meta(path,12001,MAX_DATABASE,optional=index==1) for index,path in enumerate(source)]:
            connection=sqlite3.connect(destination.as_uri()+'?mode=ro',uri=True)
            connection.execute('PRAGMA query_only=ON');connection.execute('PRAGMA trusted_schema=OFF')
            if connection.execute('PRAGMA quick_check').fetchone()!=('ok',):
                connection.close();raise ValueError('Historical SQLite snapshot is unresolved')
            connection.execute('BEGIN')
            return connection
    raise ValueError('Historical DB/WAL did not yield a stable snapshot')


class _HistoryReader:
    def __init__(self,root):
        self.root=_directory(root);self.temp=tempfile.TemporaryDirectory(prefix='ai4r-rsi-history-')
        os.chmod(self.temp.name,0o700)
        self.records=_snapshot(self.root/'index.sqlite',Path(self.temp.name)/'records.sqlite')
        self.core=None;self.core_root=None;self.public_roots=[];self.cache={};self.total=0

    def attach(self,binding):
        root=binding.get('core_root')
        if root is not None:
            try:
                self.core_root=_directory(root)
                self.core=_snapshot(self.core_root/'state/research.sqlite3',Path(self.temp.name)/'core.sqlite')
            except (ValueError,OSError,sqlite3.Error):self.core_root=None;self.core=None
        roots=[]
        if binding.get('public_root') is not None:roots.append(binding['public_root'])
        custody=binding.get('custodian')
        if isinstance(custody,dict) and isinstance(custody.get('public_roots'),list):roots.extend(custody['public_roots'])
        for value in roots:
            try:
                root=_path(value);meta=root.stat()
                if not stat.S_ISDIR(meta.st_mode) or meta.st_uid not in (0,12001,12002) or meta.st_mode&0o022:continue
                self.public_roots.append(root)
            except (ValueError,OSError):continue

    def read(self,pin):
        _ref(pin);key=encoded(pin)
        if key in self.cache:return self.cache[key]
        if len(self.cache)>=512 or self.total>=64*1024*1024:raise ValueError('Finite history read bound exceeded')
        raw=None
        if pin['id']==pin['sha256']+'.json':
            path=self.root/pin['id']
            if path.exists():raw=_read(path)
        if raw is None and self.core is not None:
            row=self.core.execute('SELECT sha256 FROM artifacts WHERE id=?',(pin['id'],)).fetchone()
            if row is not None:
                if row[0]!=pin['sha256']:raise ValueError('Historical core reference changed')
                raw=_read(self.core_root/'artifacts/sha256'/pin['sha256'][:2]/pin['sha256'])
        if raw is None:
            from jiuwenswarm.research_records.original_bytes import OriginalBytes
            for root in self.public_roots:
                publication=OriginalBytes(root)
                if publication.index().get(pin['id'])==pin['sha256']:
                    raw=publication.read(pin);break
        if raw is None or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Exact original historical bytes unavailable')
        self.cache[key]=raw;self.total+=len(raw);return raw

    def get(self,pin):return _json(self.read(pin))
    def tables(self):return {row[0] for row in self.records.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    def close(self):
        if self.core is not None:self.core.close()
        self.records.close();self.temp.cleanup()


def _row_refs(connection,table,session):
    rows=connection.execute('SELECT ref FROM '+table+' WHERE session=? ORDER BY sequence',(session,)).fetchall()
    return [_json(row[0]) for row in rows]


def _terminal(reader,job_ref,job):
    required={'jobs','history_jobs','session_history','attempts','proposer_starts'}
    if not required<=reader.tables():raise ValueError('Original durable history indexes unavailable')
    row=reader.records.execute('SELECT ref,state,result FROM jobs WHERE id=?',(job_ref['id'],)).fetchone()
    if row is None:return {'state':'not_started'}
    if _json(row[0])!=job_ref:raise ValueError('Original job index changed')
    owner=reader.records.execute('SELECT ref,session_ref FROM history_jobs WHERE id=?',(job_ref['id'],)).fetchone()
    if owner is None or _json(owner[0])!=job_ref or owner[1] is None or _json(owner[1])!=job['session_ref']:
        raise ValueError('Original job/session binding unavailable')
    histories=reader.records.execute('SELECT session,context_ref,population_ref,unsigned_ref,signed_ref,uncertain '
        'FROM session_history WHERE session_ref=?',(encoded(job['session_ref']).decode(),)).fetchall()
    if len(histories)!=1 or histories[0][4] is None:
        return {'state':'outcome_unknown','reason':'Original signed terminal absent; offline history never replays or reconciles execution.'}
    sid,context_json,population_json,unsigned_json,signed_json,uncertain=histories[0]
    if population_json is None or unsigned_json is None:raise ValueError('Original terminal staging unavailable')
    context_ref,population_ref,unsigned_ref,signed_ref=map(_json,(context_json,population_json,unsigned_json,signed_json))
    context=reader.get(context_ref);session=reader.get(context['session_bytes_ref']);validate=_contracts().validate
    validate('rsi-session',session)
    expected={'record_kind':'rsi-session-history-context:1','session_ref':job['session_ref'],
        'session_bytes_ref':context['session_bytes_ref'],'parent_ref':context['parent_ref'],
        **{name:session[name] for name in ('parent_declaration_ref','target_profile_ref','hash_profile_ref','chain_root_ref',
            'configuration_ref','improver_ref','scoring_adapter_ref')}}
    if context!=expected or context['session_bytes_ref']['sha256']!=job['session_ref']['sha256'] or session['session_id']!=sid:
        raise ValueError('Original cached session/context changed')
    # The protected context joins an opaque original session identity to the
    # exact cached bytes. Export does not need a current core/public service.
    reader.cache[encoded(job['session_ref'])]=reader.read(context['session_bytes_ref'])
    signed=reader.get(signed_ref);unsigned=reader.get(unsigned_ref);validate('rsi-session-result',signed)
    if {name:value for name,value in signed.items() if name not in {'signature','signer_key_id'}}!=unsigned:
        raise ValueError('Original signed payload differs from staged terminal')
    attempts=_row_refs(reader.records,'attempts',sid);starts=_row_refs(reader.records,'proposer_starts',sid)
    population={'record_kind':'rsi-terminal-population:1','session_ref':job['session_ref'],'context_ref':context_ref,
        'proposer_start_refs':starts,'attempt_refs':attempts,'queries_used':signed['queries_used']}
    if (reader.get(population_ref)!=population or signed['session_ref']!=job['session_ref'] or signed['parent']!=session['parent']
            or signed['attempt_refs']!=attempts or signed['attempts_used']!=len(attempts) or len(starts)!=len(attempts)
            or len(attempts)>session['limits']['max_attempts'] or not 0<=signed['queries_used']<=session['limits']['session_query_limit']):
        raise ValueError('Original terminal population differs')
    previous=None;queries=0
    for sequence,(start_ref,attempt_ref) in enumerate(zip(starts,attempts),1):
        start=reader.get(start_ref);attempt=reader.get(attempt_ref);validate('rsi-attempt',attempt)
        fields=dict(record_kind='rsi-proposer-start:1',session_id=sid,sequence=sequence,previous_ref=previous,
            configuration_ref=session['configuration_ref'],improver_ref=session['improver_ref'])
        if any(start.get(name)!=value for name,value in fields.items()):raise ValueError('Original historical start chain differs')
        fields=dict(schema_version='2.0.0',session_id=sid,sequence=sequence,previous_ref=previous,
            target_ref=session['target_profile_ref'],parent_ref=context['parent_ref'],configuration_ref=session['configuration_ref'],
            hash_profile_ref=session['hash_profile_ref'],chain_root_ref=session['chain_root_ref'])
        if any(attempt.get(name)!=value for name,value in fields.items()) or not queries<=attempt['queries_used']<=signed['queries_used']:
            raise ValueError('Original historical attempt chain differs')
        previous=attempt_ref;queries=attempt['queries_used']
    if row[2] is not None:
        stored=_json(row[2])
        if stored.get('state')=='terminal' and stored.get('result')!=[signed,signed_ref]:raise ValueError('Job terminal index differs from exact signed history')
    return {'state':'terminal','result':[signed,signed_ref],'session':session,'session_id':sid,
            'containment_uncertain':bool(uncertain),'context_ref':context_ref,'population_ref':population_ref}


def _signature(reader,result,session,binding):
    pins=[session['configuration_ref']]
    exact=binding.get('exact_binding_refs',{})
    if isinstance(exact,dict) and exact.get('configuration_ref') not in (None,pins[0]):pins.append(exact['configuration_ref'])
    for pin in pins:
        try:
            value=reader.get(pin);operator=value.get('operator',value);settings=operator['rsi']
            public=settings['custodian_public_key'];key_id=settings['custodian_key_id']
            if key_id!=result.get('signer_key_id') or not isinstance(public,str):continue
            key=base64.b64decode(public+'='*(-len(public)%4),altchars=b'-_',validate=True)
            if len(key)!=32:continue
            try:verify(result,key,key_id)
            except ValueError:return {'status':'invalid','key_source_ref':pin}
            return {'status':'verified','key_source_ref':pin}
        except (ValueError,KeyError,TypeError,OSError):continue
    return {'status':'unavailable','reason':'Original approved public signing-key pin unavailable; no new signature was created.'}


def _opportunity(reader,session,session_ref):
    if 'session_opportunities' not in reader.tables():return {'status':'unavailable'}
    columns={row[1] for row in reader.records.execute('PRAGMA table_info(session_opportunities)')}
    capture_column='diagnosis_capture_ref' if 'diagnosis_capture_ref' in columns else 'NULL'
    rows=reader.records.execute('SELECT session,ref,'+capture_column+' FROM session_opportunities WHERE session_ref=?',
        (encoded(session_ref).decode(),)).fetchall()
    if not rows:return {'status':'unavailable'}
    if len(rows)!=1 or rows[0][0]!=session['session_id']:raise ValueError('Original opportunity index is ambiguous')
    pin=_json(rows[0][1]);record=reader.get(pin);_contracts().validate('rsi-opportunity',record)
    if record['parent']!=session['parent'] or record['target_profile_ref']!=session['target_profile_ref']:
        raise ValueError('Indexed opportunity differs from original session')
    capture_ref=_json(rows[0][2]) if rows[0][2] else None
    status='unavailable'
    if capture_ref is not None:
        capture=reader.get(capture_ref);_contracts().validate('urn:ai4r:private:rsi-diagnosis-capture:1',capture)
        if (capture_ref not in record['evidence_refs'] or capture['diagnosis_ref']!=record['diagnosis_ref']
                or capture['parent']!=session['parent'] or capture['target_profile_ref']!=session['target_profile_ref']
                or capture['configuration_ref']!=session['configuration_ref']):raise ValueError('Original diagnosis capture differs')
        status=capture['status']
    return {'status':'captured','opportunity_ref':pin,'decision':record['decision'],'diagnosis_ref':record['diagnosis_ref'],
            'diagnosis_capture_ref':capture_ref,'diagnosis_status':status}


def inspect_history(config,job_ref,*,export=False):
    """Inspect an allowlisted original job using an OS-root jobs config path."""
    config_path=_path(config);raw=_read(config_path,uid=0)
    settings=load_config(config_path,'jobs')
    if _json(raw)!=settings:raise ValueError('Root configuration changed while reading')
    _ref(job_ref)
    if job_ref not in settings['allowed_job_refs']:raise PermissionError('Job reference is outside the root history grant')
    if not re.fullmatch('job_[a-z0-9_]+',job_ref['id']):raise ValueError('Original finite job identity required')
    job_root=_directory(settings['job_root'])
    job_raw=_read(job_root/(job_ref['id']+'.json'),uid=(0,12001))
    if hashlib.sha256(job_raw).hexdigest()!=job_ref['sha256']:raise ValueError('Original approved job bytes changed')
    job=_json(job_raw);_ref(job['session_ref'])
    reader=None
    try:
        reader=_HistoryReader(settings['record_root'])
        try:binding=reader.get(settings['resource_binding_ref'])
        except (ValueError,OSError):binding={}
        reader.attach(binding)
        history=_terminal(reader,job_ref,job)
        if history['state']!='terminal':return {**history,'offline':True,'stop_acknowledged':False}
        result,result_ref=history['result'];session=history['session']
        signature=_signature(reader,result,session,binding)
        if signature['status']=='invalid':raise ValueError('Original history signature verification failed')
        value={'state':'terminal','offline':True,'result':[result,result_ref],'signature':signature,
               'containment_uncertain':history['containment_uncertain'],'stop_acknowledged':False,
               'limitations':['Offline originals do not establish current eligibility, containment, or permission for new execution.']}
        if 'session_phases' in reader.tables():
            row=reader.records.execute('SELECT ref FROM session_phases WHERE session=? ORDER BY revision DESC LIMIT 1',(history['session_id'],)).fetchone()
            if row:
                phase=reader.get(_json(row[0]));_contracts().validate('urn:ai4r:private:rsi-session-phase:1',phase)
                if phase['session_ref']!=job['session_ref'] or phase['phase']=='CLOSED' and phase['terminal_result_ref']!=result_ref:
                    raise ValueError('Original indexed phase differs from signed terminal')
                value['progress']={name:phase[name] for name in ('phase','revision','incumbent_ref','attempts_used','queries_used')}
        value['opportunity']=_opportunity(reader,session,job['session_ref'])
        if export:
            records=[];seen=set();size=0
            pins=[('rsi-session-result',result_ref),('rsi-session',job['session_ref']),
                  *[('rsi-attempt',pin) for pin in result['attempt_refs']]]
            if result['referee_evidence_ref'] is not None:pins.append(('rsi-referee-evidence',result['referee_evidence_ref']))
            diagnosis=value['opportunity'].get('diagnosis_ref')
            if diagnosis is not None:pins.append(('rsi-diagnosis',diagnosis))
            for kind,pin in pins:
                if encoded(pin) in seen:continue
                original=reader.read(pin);record=_json(original)
                _contracts().validate('urn:ai4r:private:rsi-diagnosis:1' if kind=='rsi-diagnosis' else kind,record)
                row={'kind':kind,'ref':pin,'bytes_base64':base64.b64encode(original).decode()}
                size+=len(encoded(row))
                if len(records)>=512 or size>MAX_EXPORT:raise ValueError('Finite historical export bound exceeded')
                records.append(row);seen.add(encoded(pin))
            value['records']=records
            value['unavailable_export_evidence']=['model_traces','private_preparations',
                'published_candidate_export_requires_an_explicit_job_publication_join']
        return value
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error):
        return {'state':'outcome_unknown','offline':True,'stop_acknowledged':False,
                'reason':'Original history snapshot or immutable terminal joins unavailable; no recovery or execution was attempted.'}
    finally:
        if reader is not None:reader.close()
