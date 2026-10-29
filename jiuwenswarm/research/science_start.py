"""Root-owned preflight/activation and durable whole-attempt host ownership.

The fixed host ledger is shared across resource keys, accounts and profiles.
Captured receipts never supply live execution or cessation authority.
"""
from __future__ import annotations

import asyncio
import copy
import ctypes
import fcntl
import hashlib
import inspect
import json
import math
import os
import sqlite3
import stat
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .contracts import ResearchError, validate
from .bridge import BridgeError
from .executor import ExecutorBlocked, RestrictedExecutor
from .router_client import PlatformIntegrityError
from .science_runtime import decode_science_runtime_record
from .state import json_bytes


DOMAIN = 'm1-host-scientific-resources'
PREPARATION = 'invocation-preparation'
KINDS = {'scientific-attempt-preflight','scientific-attempt-activation'}


def _require(ok, reason):
    if not ok:
        raise ExecutorBlocked(reason)


def _ref(ref):
    validate('Ref',ref)
    return json_bytes(ref).decode()


async def _await(value):
    return await value if inspect.isawaitable(value) else value


class AttemptLeaseLedger:
    """Durable resource exclusion; no caller-accessible release operation.

    Production constructs one ledger at its fixed protected host path. Tests
    using an owned scratch directory establish SQLite/locking mechanics only.
    """
    def __init__(self,root,*,broker_instance_id):
        _require(os.name=='posix' and os.geteuid()==0,'ROOT_ATTEMPT_LEDGER_REQUIRED')
        _require(type(broker_instance_id) is str and broker_instance_id,'BROKER_INSTANCE_REQUIRED')
        self.root=Path(root).absolute();self.instance=broker_instance_id
        _require(not any(path.is_symlink() for path in (self.root,*self.root.parents)),
                 'ATTEMPT_LEDGER_CUSTODY_INVALID')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        metadata=self.root.stat()
        _require(metadata.st_uid==0 and stat.S_IMODE(metadata.st_mode)==0o700,'ATTEMPT_LEDGER_CUSTODY_INVALID')
        self.lock_fd=os.open(self.root/'broker.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        metadata=os.fstat(self.lock_fd)
        _require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid==0 and metadata.st_nlink==1
                 and stat.S_IMODE(metadata.st_mode)==0o600,'ATTEMPT_LEDGER_CUSTODY_INVALID')
        try:
            fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            os.close(self.lock_fd)
            raise ExecutorBlocked('HOST_BROKER_ALREADY_INSTALLED') from error
        database=self.root/'attempts.sqlite3'
        _require(not database.is_symlink(),'ATTEMPT_LEDGER_CUSTODY_INVALID')
        self.db=sqlite3.connect(database,isolation_level=None);self.db.row_factory=sqlite3.Row
        database.chmod(0o600)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS leases(
            id TEXT PRIMARY KEY,domain TEXT NOT NULL,parent_ref TEXT NOT NULL,parent_identity TEXT NOT NULL,
            broker_instance TEXT NOT NULL,state TEXT NOT NULL,effects_started INTEGER NOT NULL DEFAULT 0);
          CREATE UNIQUE INDEX IF NOT EXISTS one_held_host_domain ON leases(domain) WHERE state!='released';
          CREATE TABLE IF NOT EXISTS preparations(
            preparation_ref TEXT PRIMARY KEY,lease_id TEXT NOT NULL,binding TEXT NOT NULL,
            runtime_ref TEXT NOT NULL,state TEXT NOT NULL,preflight_body TEXT,preflight_ref TEXT,
            activation_body TEXT,activation_ref TEXT);
          CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY,lease_id TEXT NOT NULL,invocation_id TEXT NOT NULL,
            group_path TEXT NOT NULL,group_device INTEGER NOT NULL,group_inode INTEGER NOT NULL,
            pid INTEGER,pid_start TEXT);
        ''')
        # An equal durable UUID cannot recreate an uninterrupted owner.
        self.db.execute("UPDATE leases SET state='quarantined' WHERE state='held'")

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self.db
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def acquire(self,*,parent_ref,parent_identity):
        parent=_ref(parent_ref)
        _require(type(parent_identity) is tuple and len(parent_identity)==3
                 and all(type(value) is str and value for value in parent_identity),'WHOLE_ATTEMPT_IDENTITY_REQUIRED')
        identity=json_bytes(list(parent_identity)).decode()
        with self.transaction() as db:
            existing=db.execute("SELECT * FROM leases WHERE domain=? AND state!='released'",(DOMAIN,)).fetchone()
            if existing:
                _require(existing['state']=='held' and existing['broker_instance']==self.instance
                    and existing['parent_ref']==parent and existing['parent_identity']==identity,
                    'WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN')
                return existing['id']
            lease='attempt-lease:'+uuid.uuid4().hex
            db.execute("INSERT INTO leases(id,domain,parent_ref,parent_identity,broker_instance,state) VALUES(?,?,?,?,?,'held')",
                       (lease,DOMAIN,parent,identity,self.instance))
            return lease

    def inspect(self,lease):
        row=self.db.execute('SELECT * FROM leases WHERE id=?',(lease,)).fetchone()
        _require(row is not None,'UNKNOWN_ATTEMPT_LEASE')
        return dict(row)

    def bind_preparation(self,preparation_ref,*,lease,binding,runtime_ref):
        key=_ref(preparation_ref);runtime=_ref(runtime_ref);encoded=json_bytes(binding).decode()
        with self.transaction() as db:
            owner=db.execute('SELECT * FROM leases WHERE id=?',(lease,)).fetchone()
            _require(owner and owner['state']=='held' and owner['broker_instance']==self.instance,'ATTEMPT_LEASE_NOT_LIVE')
            prior=db.execute('SELECT * FROM preparations WHERE preparation_ref=?',(key,)).fetchone()
            if prior:
                _require(prior['lease_id']==lease and prior['binding']==encoded and prior['runtime_ref']==runtime,
                         'PREPARATION_OWNER_CONFLICT')
                return dict(prior)
            db.execute("INSERT INTO preparations(preparation_ref,lease_id,binding,runtime_ref,state) VALUES(?,?,?,?,'prepared')",
                       (key,lease,encoded,runtime))
        return self.preparation(preparation_ref)

    def preparation(self,preparation_ref):
        row=self.db.execute('SELECT * FROM preparations WHERE preparation_ref=?',(_ref(preparation_ref),)).fetchone()
        _require(row is not None,'UNKNOWN_INVOCATION_PREPARATION')
        return dict(row)

    def stage(self,preparation_ref,kind,body):
        _require(kind in KINDS,'START_RECEIPT_KIND_REQUIRED')
        column='preflight_body' if kind=='scientific-attempt-preflight' else 'activation_body'
        with self.transaction() as db:
            row=self.preparation(preparation_ref);owner=self.inspect(row['lease_id'])
            _require(owner['state']=='held' and owner['broker_instance']==self.instance
                     and row['state']=='prepared','ATTEMPT_LEASE_NOT_LIVE')
            _require(row[column] is None,'START_RECEIPT_ALREADY_STAGED_OR_UNKNOWN')
            if column=='activation_body':_require(row['preflight_ref'] is not None,'ORIGINAL_PREFLIGHT_REQUIRED')
            db.execute('UPDATE preparations SET '+column+'=? WHERE preparation_ref=?',
                       (json_bytes(body).decode(),_ref(preparation_ref)))

    def published(self,preparation_ref,kind,body,ref):
        prefix='preflight' if kind=='scientific-attempt-preflight' else 'activation'
        _require(kind in KINDS and ref=={'id':body['id'],'sha256':hashlib.sha256(json_bytes(body)).hexdigest()},
                 'ORIGINAL_START_RECEIPT_REF_REQUIRED')
        with self.transaction() as db:
            row=self.preparation(preparation_ref)
            _require(row[prefix+'_body']==json_bytes(body).decode() and row[prefix+'_ref'] is None
                     and row['state']=='prepared','START_RECEIPT_PUBLICATION_CONFLICT')
            db.execute('UPDATE preparations SET '+prefix+'_ref=? WHERE preparation_ref=?',(_ref(ref),_ref(preparation_ref)))

    def uncertain(self,preparation_ref):
        row=self.preparation(preparation_ref)
        with self.transaction() as db:
            db.execute("UPDATE preparations SET state='unknown' WHERE preparation_ref=?",(_ref(preparation_ref),))
            db.execute("UPDATE leases SET state='quarantined' WHERE id=? AND state!='released'",(row['lease_id'],))

    def require_effect(self,binding):
        encoded=json_bytes(binding).decode()
        rows=self.db.execute('SELECT * FROM preparations WHERE binding=?',(encoded,)).fetchall()
        _require(len(rows)==1 and rows[0]['state']=='prepared' and rows[0]['activation_ref'],
                 'ORIGINAL_ACTIVE_ATTEMPT_RESOURCES_REQUIRED')
        row=rows[0];lease=self.inspect(row['lease_id'])
        _require(lease['state']=='held' and lease['broker_instance']==self.instance,'ATTEMPT_LEASE_NOT_LIVE')
        return row['lease_id']

    def effect_started(self,binding):
        lease=self.require_effect(binding)
        with self.transaction() as db:
            db.execute('UPDATE leases SET effects_started=effects_started+1 WHERE id=?',(lease,))
        return lease

    def close(self):
        self.db.close();fcntl.flock(self.lock_fd,fcntl.LOCK_UN);os.close(self.lock_fd)


class ScienceAttemptBroker:
    """Installed root broker; receipt publication is a finite trusted port.

    An absent/uninstalled registration, publisher or live callback refuses.
    The broker does not register a service from a mapping or a record alone.
    """
    def __init__(self,*,store,registration,ledger,authorize_preparation,publish_receipt,
                 inspect_attempt=None,inspect_evaluation=None):
        from .science_registration import InstalledScienceRuntime
        _require(os.geteuid()==0 and type(registration) is InstalledScienceRuntime
                 and type(ledger) is AttemptLeaseLedger,'INSTALLED_SCIENCE_BROKER_REQUIRED')
        _require(registration.store is store and registration.backend is not None,'SCIENCE_CUSTODY_INSTANCE_MISMATCH')
        _require(callable(authorize_preparation) and callable(publish_receipt),'SCIENCE_PREPARATION_PORTS_UNAVAILABLE')
        self.store,self.registration,self.ledger=store,registration,ledger
        self.authorize_preparation,self.publish_receipt=authorize_preparation,publish_receipt
        self.instance=ledger.instance;self.locks={}
        self.inspect_attempt,self.inspect_evaluation=inspect_attempt,inspect_evaluation
        self.active_operations=None
        _require(registration.backend.lifecycle_observer is None,'SCIENCE_SUPERVISION_ALREADY_INSTALLED')
        self._kernel_observer=self.observe_kernel
        registration.backend.lifecycle_observer=self._kernel_observer

    async def _prepared(self,ref):
        _require(self.store.record_kind(ref)==PREPARATION,'ORIGINAL_INVOCATION_PREPARATION_REQUIRED')
        prepared=self.store.read_record(ref)
        validate('urn:ai4r:private:invocation-preparation:1',prepared)
        binding={key:copy.deepcopy(prepared[key]) for key in ('contract_ref','invocation_id','execution_id')}
        response=await _await(self.authorize_preparation(copy.deepcopy(binding)))
        fields=set(binding)|{'contract','preparation_ref','execution_deadline_monotonic_s','remaining_time_s'}
        _require(type(response) is dict and set(response)==fields and response['preparation_ref']==ref
                 and all(response[key]==value for key,value in binding.items()),'PREPARED_CALLBACK_MISMATCH')
        for key in ('execution_deadline_monotonic_s','remaining_time_s'):
            value=response[key]
            _require(type(value) in (int,float) and math.isfinite(value) and value>0,'PREPARED_DEADLINE_INVALID')
        _require(response['execution_deadline_monotonic_s']>time.monotonic()
                 and prepared['deadline_unix_ns']>time.time_ns(),'PREPARED_DEADLINE_EXPIRED')
        _require(self.store.read_record(binding['contract_ref'])==response['contract'],'PREPARED_ORIGINAL_CONTRACT_MISMATCH')
        await _await(self.registration.validate_preparation(ref,prepared,response))
        return prepared,binding,response

    async def prepare_attempt_resources(self,payload):
        _require(type(payload) is dict and set(payload)=={'preparation_ref'},'INVALID_EXECUTOR_PREPARATION_REQUEST')
        ref=payload['preparation_ref'];validate('Ref',ref)
        async with self.locks.setdefault(_ref(ref),asyncio.Lock()):
            previous=self.ledger.db.execute('SELECT * FROM preparations WHERE preparation_ref=?',(_ref(ref),)).fetchone()
            if previous:
                _require(previous['preflight_ref'] is not None,'START_DELIVERY_UNKNOWN')
                return {'preflight_ref':json.loads(previous['preflight_ref'])}  # inspection only
            prepared,binding,response=await self._prepared(ref)
            disposition=self.registration.disposition(response['contract'])
            await self.reconcile_completed()
            lease=self.ledger.acquire(parent_ref=response['contract']['node_contract_ref'],parent_identity=disposition.parent_identity)
            self.ledger.bind_preparation(ref,lease=lease,binding=binding,runtime_ref=self.registration.runtime_ref)
            body={'schema':'ai4r-scientific-attempt-preflight:1','id':'scientific-preflight:'+uuid.uuid4().hex,
                  'preparation_ref':copy.deepcopy(ref),'science_runtime_ref':copy.deepcopy(self.registration.runtime_ref),
                  'broker_instance_id':self.instance,'recorded_unix_ns':time.time_ns()}
            return await self._publish(ref,'scientific-attempt-preflight',body,'preflight_ref')

    async def activate_attempt_resources(self,payload):
        _require(type(payload) is dict and set(payload)=={'preparation_ref','preflight_ref'},'INVALID_EXECUTOR_ACTIVATION_REQUEST')
        ref=payload['preparation_ref'];validate('Ref',ref);validate('Ref',payload['preflight_ref'])
        async with self.locks.setdefault(_ref(ref),asyncio.Lock()):
            row=self.ledger.preparation(ref)
            _require(row['preflight_ref']==_ref(payload['preflight_ref']),'ORIGINAL_PREFLIGHT_REQUIRED')
            if row['activation_ref']:
                return {'activation_ref':json.loads(row['activation_ref'])}  # no fresh work or time
            try:
                await self._prepared(ref)
                lease=self.ledger.inspect(row['lease_id'])
                _require(lease['state']=='held' and lease['broker_instance']==self.instance,'ATTEMPT_LEASE_NOT_LIVE')
                body={'schema':'ai4r-scientific-attempt-activation:1','id':'scientific-activation:'+uuid.uuid4().hex,
                      'preflight_ref':copy.deepcopy(payload['preflight_ref']),'broker_instance_id':self.instance,
                      'recorded_unix_ns':time.time_ns()}
                return await self._publish(ref,'scientific-attempt-activation',body,'activation_ref')
            except BaseException:
                self.ledger.uncertain(ref);raise

    async def _publish(self,ref,kind,body,result_key):
        try:
            self.ledger.stage(ref,kind,body)
            original=await _await(self.publish_receipt(kind,copy.deepcopy(body),copy.deepcopy(ref)))
            _require(self.store.record_kind(original)==kind and self.store.read_record(original)==body,
                     'SCIENTIFIC_RECEIPT_CUSTODY_NAMESPACE_MISMATCH')
            self.ledger.published(ref,kind,body,original)
            return {result_key:original}
        except BaseException:
            self.ledger.uncertain(ref);raise

    def require_effect(self,binding,operation,contract):
        _require(self.registration.backend.lifecycle_observer is self._kernel_observer,
                 'SCIENCE_KERNEL_SUPERVISION_CHANGED')
        self.registration.require_operation(binding,operation,contract)
        return self.ledger.effect_started(binding)

    def observe_kernel(self,event,job,group,pid):
        """Durable group ownership is captured BEFORE any child gate opens."""
        process_mode = self.registration.backend.execution_mode == 'm1_app_process'
        _require(event in ({'process_scope_prepared','process_created'} if process_mode else
                          {'group_created','process_created'}),'UNKNOWN_KERNEL_LIFECYCLE_EVENT')
        rows=self.ledger.db.execute('SELECT * FROM preparations').fetchall()
        matches=[row for row in rows if (binding:=json.loads(row['binding']))['invocation_id']==job.invocation_id
                 and binding['contract_ref']==dict(job.contract_ref)]
        _require(len(matches)==1,'KERNEL_JOB_HAS_NO_EXACT_ACTIVATED_OWNER')
        binding=json.loads(matches[0]['binding']);lease=self.ledger.require_effect(binding)
        root=self.registration.backend.cgroup_root
        if process_mode:
            roots = (self.registration.backend.workspace_root, *self.registration.backend.preparation_roots)
            _require(group.name == job.job_id+'.capture' and not group.is_symlink()
                and any(group.is_relative_to(path) for path in roots)
                and group.stat().st_uid == 0 and stat.S_IMODE(group.stat().st_mode) == 0o700,
                'M1_PROCESS_SCOPE_IDENTITY_INVALID')
        else:
            _require(root is not None and group.parent==root and group.name==job.job_id and not group.is_symlink(),
                     'KERNEL_GROUP_IDENTITY_INVALID')
        metadata=group.stat()
        with self.ledger.transaction() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job.job_id,)).fetchone()
            if event in {'group_created','process_scope_prepared'}:
                _require(row is None,'KERNEL_JOB_REPLAY_DENIED')
                db.execute('INSERT INTO jobs(id,lease_id,invocation_id,group_path,group_device,group_inode) VALUES(?,?,?,?,?,?)',
                           (job.job_id,lease,job.invocation_id,str(group),metadata.st_dev,metadata.st_ino))
            else:
                _require(row and row['lease_id']==lease and row['group_path']==str(group)
                    and row['group_device']==metadata.st_dev and row['group_inode']==metadata.st_ino
                    and row['pid'] is None and type(pid) is int and pid>0,'KERNEL_PROCESS_IDENTITY_INVALID')
                proc=Path('/proc')/str(pid)/'stat'
                started=proc.read_text().rsplit(')',1)[1].split()[19]
                db.execute('UPDATE jobs SET pid=?,pid_start=? WHERE id=?',(pid,started,job.job_id))

    @staticmethod
    def _kernel_cgroup(group):
        # statfs verifies the actual cgroup-v2 filesystem. A directory filled
        # with caller-authored cgroup-looking text cannot certify cessation.
        buffer=ctypes.create_string_buffer(256)
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.statfs(os.fsencode(group),ctypes.byref(buffer))!=0:return False
        return int.from_bytes(buffer.raw[:ctypes.sizeof(ctypes.c_long)],byteorder=sys.byteorder)==0x63677270

    def _ceased(self,lease,preparations):
        backend=self.registration.backend
        invocations={json.loads(row['binding'])['invocation_id'] for row in preparations}
        if any(item['invocation_id'] in invocations for key,item in backend.owned_groups.items()
               if key in backend.active):return False
        if self.active_operations is None or any(run==json.loads(lease['parent_identity'])[0]
                                                for run in self.active_operations.values()):return False
        jobs=self.ledger.db.execute('SELECT * FROM jobs WHERE lease_id=?',(lease['id'],)).fetchall()
        if backend.execution_mode == 'm1_app_process':
            from .m1_process import process_members
            if not jobs:
                return lease['state']=='held' and lease['broker_instance']==self.instance
            for job in jobs:
                scope = Path(job['group_path'])
                if scope.is_symlink() or not scope.is_dir() or scope.stat().st_ino != job['group_inode']:
                    return False
                marker = scope/'finished.json'
                if not marker.is_file() or marker.is_symlink() or marker.stat().st_uid != 0:
                    return False
                finished = json.loads(marker.read_text())
                if (finished.get('job_id') != job['id'] or finished.get('pgid') != job['pid']
                        or finished.get('invocation_id') != job['invocation_id']
                        or finished.get('process_group_cleanup') is not True or process_members(job['pid'])):
                    return False
            return True
        if not jobs:
            if (type(lease['effects_started']) is not int or lease['effects_started']!=0
                    or any(item['invocation_id'] in invocations for item in backend.owned_groups.values())):
                return False
            if lease['state']=='held' and lease['broker_instance']==self.instance:
                return True
            # Only a proved terminal, never-activated old attempt may recover
            # across broker loss. The exclusive ledger flock remains held;
            # current empty maps alone cannot prove old kernel cessation.
            if (lease['state']!='quarantined' or lease['broker_instance']==self.instance
                    or not preparations or len(invocations)!=len(preparations) or any(row['state']!='prepared'
                        or row['activation_body'] is not None or row['activation_ref'] is not None
                        for row in preparations)):
                return False
            group=backend.cgroup_root
            if (group is None or group.is_symlink() or not group.is_dir()
                    or not self._kernel_cgroup(group) or any(path.is_dir() for path in group.iterdir())):
                return False
            events=dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
            return events.get('populated')=='0' and not (group/'cgroup.procs').read_text().strip()
        for job in jobs:
            group=Path(job['group_path'])
            if (backend.cgroup_root is None or group.parent!=backend.cgroup_root or group.name!=job['id']
                    or group.is_symlink() or not group.is_dir() or not self._kernel_cgroup(group)):
                return False
            metadata=group.stat()
            if metadata.st_dev!=job['group_device'] or metadata.st_ino!=job['group_inode']:return False
            events=dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
            if events.get('populated')!='0' or (group/'cgroup.procs').read_text().strip():return False
        return True

    async def reconcile_completed(self):
        """Internal supervision only; inspection cannot itself release a lease."""
        if not callable(self.inspect_attempt) or not callable(self.inspect_evaluation):return
        leases=self.ledger.db.execute("SELECT * FROM leases WHERE state!='released'").fetchall()
        for lease in leases:
            try:
                parent_ref=json.loads(lease['parent_ref']);parent=self.store.read_record(parent_ref)
                preparations=self.ledger.db.execute('SELECT * FROM preparations WHERE lease_id=?',(lease['id'],)).fetchall()
                if not preparations:continue
                if self.store.record_kind(parent_ref)=='node-execution-contract':
                    terminal=await _await(self.inspect_attempt({'node_contract_ref':parent_ref}))
                    expected={'node_contract_ref','run_plan_ref','run_id','node_id','attempt_id','state',
                              'dispatch_ref','source_outcome','cancellation_record'}
                    _require(type(terminal) is dict and set(terminal)==expected and terminal['node_contract_ref']==parent_ref
                        and terminal['state'] in {'terminal','cancelled'}
                        and all(terminal[key]==parent[key] for key in ('run_id','node_id','attempt_id')),
                        'WHOLE_ATTEMPT_TERMINAL_UNAVAILABLE')
                else:
                    _require(self.store.record_kind(parent_ref)=='evaluation-node-context','WHOLE_ATTEMPT_PARENT_KIND_INVALID')
                    for preparation in preparations:
                        binding=json.loads(preparation['binding'])
                        terminal=await _await(self.inspect_evaluation(binding))
                        expected=set(binding)|{'state','request_ref','scope_ref','assignment_grant_ref',
                                               'terminal_ref','containment_ref','cancel_id'}
                        _require(type(terminal) is dict and set(terminal)==expected
                            and all(terminal[key]==value for key,value in binding.items())
                            and terminal['state'] in {'completed','failed','cancelled'}
                            and terminal['terminal_ref'] is not None,'WHOLE_PRIVATE_TERMINAL_UNAVAILABLE')
                if not self._ceased(lease,preparations):continue
                # No await between actual kernel/supervision observations and
                # the guarded transition. New effects independently require a
                # live active core owner and this still-held original lease.
                with self.ledger.transaction() as db:
                    db.execute("UPDATE leases SET state='released' WHERE id=? AND state=? AND effects_started=?",
                               (lease['id'],lease['state'],lease['effects_started']))
            except (ResearchError,ExecutorBlocked,BridgeError,PlatformIntegrityError,
                    OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                continue  # unknown or contradictory ownership stays held
