"""Actual frozen composition on private snapshots, without model/work effects.

Original Core, input, account and session stores must be mounted read-only.
Only a precreated private scratch directory is writable. No session execution,
DevelopmentModel, evaluation dispatcher, admission or activation is invoked.
"""
from __future__ import annotations
import asyncio
import copy
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile

SCHEMA = 'ai4r-rsi-capsule-compose-doctor:1'
MAX_SNAPSHOT_BYTES = 1024 * 1024 * 1024
MAX_FILES = 30000


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def private_database(path):
    """Read SQLite through a stable private DB/WAL copy, never SHM originals.

    A WAL-mode database without an existing SHM cannot be queried directly on
    a read-only mount. Preserve authoritative DB and WAL bytes together and
    let SQLite rebuild its coordination files only in the private copy.
    """
    path = Path(path)
    sources = (path, Path(str(path)+'-wal'))
    before = {source:source.read_bytes() for source in sources if source.exists()}
    need(sum(map(len,before.values())) <= 32*1024*1024, 'DOCTOR_DATABASE_COPY_BOUND_EXCEEDED')
    with tempfile.TemporaryDirectory(prefix='capsule-doctor-sqlite-') as directory:
        target = Path(directory)/path.name
        for source,raw in before.items():
            (Path(directory)/source.name).write_bytes(raw)
        after = {source:source.read_bytes() for source in sources if source.exists()}
        need(before == after, 'DOCTOR_DATABASE_CHANGED_DURING_COPY')
        connection = sqlite3.connect(target)
        try:
            yield connection
        finally:
            connection.close()


def database_fact(path):
    if not Path(path).exists():
        return {'present':False,'tables':{}}
    with private_database(path) as connection:
        tables = sorted(row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        values = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            # Sorting by full row representation also supports WITHOUT ROWID.
            rows = sorted(connection.execute('SELECT * FROM ' + quoted).fetchall(), key=repr)
            values[table] = {'count': len(rows), 'rows_sha256': digest(repr(rows).encode())}
        return {'present':True,'tables':values}


def tree_fact(root):
    rows = []
    for path in sorted(Path(root).rglob('*')):
        need(not path.is_symlink(), 'DOCTOR_ORIGINAL_SYMLINK_REFUSED')
        if path.is_file():
            meta = path.stat()
            need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, 'DOCTOR_ORDINARY_FILES_REQUIRED')
            # SQLite byte files may update their read coordination metadata;
            # logical contents are compared separately using mode=ro handles.
            if path.name.endswith(('.sqlite', '.sqlite3', '.sqlite-wal', '.sqlite-shm', '.sqlite3-wal', '.sqlite3-shm')):
                continue
            rows.append([path.relative_to(root).as_posix(), meta.st_size, digest(path.read_bytes())])
    need(len(rows) <= MAX_FILES and sum(row[1] for row in rows) <= MAX_SNAPSHOT_BYTES,
         'DOCTOR_SNAPSHOT_BOUND_EXCEEDED')
    return {'files': len(rows), 'bytes': sum(row[1] for row in rows),
            'inventory_sha256': digest(json.dumps(rows, separators=(',', ':')).encode())}


def backup_database(source, destination):
    with private_database(source) as original:
        target = sqlite3.connect(destination)
        try:
            original.backup(target)
        finally:
            target.close()


def snapshot(source, destination, database_relative):
    source, destination = Path(source), Path(destination)
    destination.mkdir(mode=0o700)
    database = source / database_relative
    size = count = 0
    for path in sorted(source.rglob('*')):
        need(not path.is_symlink(), 'DOCTOR_ORIGINAL_SYMLINK_REFUSED')
        relative = path.relative_to(source)
        output = destination / relative
        if path.is_dir():
            output.mkdir(mode=0o700)
            continue
        if path == database or path in (Path(str(database)+'-wal'), Path(str(database)+'-shm')):
            continue
        meta = path.stat()
        need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1, 'DOCTOR_ORDINARY_FILES_REQUIRED')
        size += meta.st_size; count += 1
        need(count <= MAX_FILES and size <= MAX_SNAPSHOT_BYTES, 'DOCTOR_SNAPSHOT_BOUND_EXCEEDED')
        shutil.copyfile(path, output); output.chmod(0o600)
    (destination / database_relative).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if database.exists():
        backup_database(database, destination / database_relative)
    return destination


async def compose_snapshot(value, helper, scratch):
    original = value['composition']
    composition = copy.deepcopy(original)
    composition.update(core_root=str(snapshot(original['core_root'], scratch/'core', 'state/research.sqlite3')),
        record_root=str(snapshot(original['record_root'], scratch/'records', 'index.sqlite')),
        native_lease_root=str(snapshot(original['native_lease_root'], scratch/'native-leases', 'index.sqlite')),
        work_root=str(scratch/'work'))
    (scratch/'work').mkdir(mode=0o700)
    composition.update({key:value['session'][key] for key in (
        'id', 'native_scope_ref', 'diagnosis_contract_ref', 'proposal_contract_ref')})
    core_before = database_fact(scratch/'core/state/research.sqlite3')
    native_before = database_fact(scratch/'native-leases/index.sqlite')
    records_before = database_fact(scratch/'records/index.sqlite')
    evaluated = 0
    async def forbidden_evaluation(*args, **kwargs):
        nonlocal evaluated
        evaluated += 1
        raise ValueError('DOCTOR_CANNOT_EXECUTE_JOBS')
    runtime = None
    try:
        # This is the literal source-pinned normal composition, including its
        # actual Library/check assets, child contracts, native lease and status.
        runtime = await helper.compose(composition, forbidden_evaluation)
        await runtime.before_model()  # Status/lease freshness only; never model.
        need(type(runtime.subscription).__name__ == 'HostCodexSubscriptionService',
             'EXACT_QUALIFIED_NATIVE_SUBSCRIPTION_REQUIRED')
        from .host_codex_backend import descriptor
        binding = runtime.subscription.binding()
        native = descriptor(binding)
        need(evaluated == 0, 'DOCTOR_EVALUATION_FORBIDDEN')
        return {'native_policy_sha256': native['sha256'],
                'native_binding_sha256': binding['binding_sha256']}
    finally:
        if runtime is not None:
            close = getattr(runtime.subscription.transport, 'close', None)
            if close is not None:
                pending = close()
                if inspect.isawaitable(pending):
                    await pending
            runtime.records.close(); runtime.lease_records.close(); runtime.core.close()
        # Constructors may establish empty schema/index tables on snapshots.
        # Every preexisting row and every effect-bearing new table stays empty.
        core_after = database_fact(scratch/'core/state/research.sqlite3')
        native_after = database_fact(scratch/'native-leases/index.sqlite')
        records_after = database_fact(scratch/'records/index.sqlite')
        need(core_before == core_after, 'DOCTOR_CORE_ROWS_CHANGED')
        for before, after in ((native_before,native_after),(records_before,records_after)):
            need(all(after['tables'].get(name) == rows for name,rows in before['tables'].items()), 'DOCTOR_EXISTING_SESSION_ROWS_CHANGED')
            need(all(rows['count'] == 0 for name,rows in after['tables'].items() if name not in before['tables']),
                 'DOCTOR_EFFECT_ROWS_CREATED')


def doctor(value, helper, scratch_root, *, scope_sha256):
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_DOCTOR_CONFIGURATION_REQUIRED')
    # Root intentionally lacks DAC_OVERRIDE in the metadata worker. Drop
    # before traversing any private controller directory, including parents.
    # Config and source custody have already been checked by the Root loader.
    os.setgroups([13000]); os.setgid(12001); os.setuid(12001)
    need(os.getuid()==os.geteuid()==12001 and os.getgroups()==[13000], 'DOCTOR_CONTROLLER_DROP_REQUIRED')
    scratch = Path(scratch_root)
    need(scratch.is_absolute() and not any(p.is_symlink() for p in (scratch,*scratch.parents)),
         'DOCTOR_REAL_SCRATCH_REQUIRED')
    meta = scratch.stat()
    need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 12001 and stat.S_IMODE(meta.st_mode) == 0o700
         and not any(scratch.iterdir()), 'FRESH_PRIVATE_DOCTOR_SCRATCH_REQUIRED')
    original = value['composition']
    for key in ('core_root','input_root','record_root','native_lease_root','account_root'):
        path = Path(original[key])
        need(not any(p.is_symlink() for p in (path,*path.parents))
             and bool(os.statvfs(path).f_flag & os.ST_RDONLY), 'DOCTOR_ORIGINALS_MUST_BE_READONLY_MOUNTS')
    # Private identity exactly matches the real controller. Account metadata is
    # reused read-only; its contents are never copied into the doctor snapshot.
    roots = {key:Path(original[key]) for key in ('core_root','record_root','native_lease_root')}
    before = {key:{'files':tree_fact(path), 'database':database_fact(path/(
        'state/research.sqlite3' if key=='core_root' else 'index.sqlite'))} for key,path in roots.items()}
    result = {'schema':SCHEMA,'scope_sha256':scope_sha256,'status':'ERROR',
        'actual_frozen_compose_completed':False,'originals_unchanged':False,
        'model_calls':0,'tool_calls':0,'execution_jobs':0,'work_claims':0,'native_starts':0,
        'uid':os.geteuid(),'gid':os.getegid(),'groups':os.getgroups(),
        'python':{'version':list(sys.version_info[:3]),'executable_sha256':digest(Path(sys.executable).resolve().read_bytes())},
        'originals_before':before}
    try:
        result.update(asyncio.run(compose_snapshot(value,helper,scratch)))
        result.update(status='COMPATIBLE',actual_frozen_compose_completed=True)
    except BaseException as error:
        result.update(exception_type=type(error).__name__,message=str(error)[:4096])
        raise
    finally:
        after = {key:{'files':tree_fact(path), 'database':database_fact(path/(
            'state/research.sqlite3' if key=='core_root' else 'index.sqlite'))} for key,path in roots.items()}
        result['originals_after'] = after
        result['originals_unchanged'] = before==after
        if before != after:
            result['status']='ERROR'
        with (scratch/'doctor-result.json').open('xb') as stream:
            stream.write(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
    need(result['originals_unchanged'], 'DOCTOR_ORIGINAL_ROWS_OR_BYTES_CHANGED')
    return result
