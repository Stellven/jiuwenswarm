"""Finite OS-operator credential management; never an HTTP issuer or token printer."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
from .contracts import ResearchError
from .shell_auth import SessionAuthority

SESSION_ROOT=Path('/var/lib/ai4r-accounts/sessions')
MAX_BINDING=64*1024


def read_binding(path):
    supplied=Path(path)
    if not supplied.is_absolute() or any(p.is_symlink() for p in (supplied,*supplied.parents)):
        raise ResearchError('auth','Protected campaign binding path is unsafe')
    descriptor=os.open(supplied,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077 or info.st_nlink!=1 or info.st_size>MAX_BINDING:
            raise ResearchError('auth','Protected campaign binding custody is invalid')
        raw=os.read(descriptor,MAX_BINDING+1)
        if len(raw)>MAX_BINDING:raise ResearchError('auth','Protected campaign binding is oversized')
    finally:os.close(descriptor)
    try:return json.loads(raw)
    except (ValueError,UnicodeError) as exc:raise ResearchError('validation','Protected campaign binding is invalid') from exc


def open_operator_authority():
    SessionAuthority._operator_only()
    root=SESSION_ROOT
    for path in (root,*root.parents):
        if path.is_symlink():raise ResearchError('auth','Native session custody is unsafe')
    database=root/'native-sessions.sqlite3'
    for path in (root,database):
        info=path.lstat()
        if info.st_uid!=10001 or info.st_mode&0o077 or path.is_symlink() or path==database and (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1):
            raise ResearchError('auth','Actual native session storage is unavailable')
    # Connect under the fixed application filesystem identity so SQLite WAL/SHM
    # files retain app custody. The root-only issuer effect is restored only
    # after opening the existing database; no user/module identity is supplied.
    os.seteuid(10001)
    try:
        connection=sqlite3.connect(f'file:{database}?mode=ro',uri=True)
        try:
            row=connection.execute("SELECT value FROM authority_settings WHERE key='origin'").fetchone()
        finally:connection.close()
        if row is None:raise ResearchError('auth','Actual native startup origin is unavailable')
        return SessionAuthority(root,row[0])
    finally:os.seteuid(0)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Manage separate approved evaluation HTTP grants')
    sub=parser.add_subparsers(dest='operation',required=True)
    issue=sub.add_parser('issue');issue.add_argument('--binding-file',required=True);issue.add_argument('--output',required=True)
    revoke=sub.add_parser('revoke');revoke.add_argument('--grant-id',required=True)
    args=parser.parse_args(argv)
    authority=None
    try:
        authority=open_operator_authority()
        result=(authority.issue_evaluation(read_binding(args.binding_file),args.output) if args.operation=='issue'
                else authority.revoke_evaluation(args.grant_id))
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ResearchError,OSError,ValueError,sqlite3.Error):
        print(json.dumps({'status':'blocked','reason':'Approved native session/profile, protected binding or operator custody is unavailable.'}))
        return 2
    finally:
        if authority is not None:authority.close()


if __name__=='__main__':raise SystemExit(main())
