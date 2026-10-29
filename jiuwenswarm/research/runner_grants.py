"""OS-operator management of finite ordinary runner credentials."""
from __future__ import annotations
import argparse
import json
import stat
import sqlite3
from .contracts import ResearchError
from .evaluation_grants import SESSION_ROOT, open_operator_authority, read_binding


def main(argv=None):
    parser=argparse.ArgumentParser(description='Manage finite ordinary research runner HTTP grants')
    sub=parser.add_subparsers(dest='operation',required=True)
    issue=sub.add_parser('issue');issue.add_argument('--binding-file',required=True);issue.add_argument('--output',required=True)
    runner=sub.add_parser('issue-runner');runner.add_argument('--output',required=True)
    runner.add_argument('--expires-in-s',type=int,default=86400)
    revoke=sub.add_parser('revoke');revoke.add_argument('--grant-id',required=True)
    args=parser.parse_args(argv);authority=None
    try:
        authority=open_operator_authority()
        if args.operation=='issue':
            result=authority.issue_runner(read_binding(args.binding_file),args.output)
        elif args.operation=='issue-runner':
            if not 1<=args.expires_in_s<=86400:
                raise ResearchError('validation','Runner grant lifetime must be at most one day')
            session=SESSION_ROOT/'reusable-bootstrap.json'
            info=session.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=10001 or info.st_mode&0o077
                    or info.st_nlink!=1 or session.is_symlink()):
                raise ResearchError('auth','Reusable sign-in session custody is invalid')
            principal=json.loads(session.read_bytes())['principal']
            if isinstance(principal,str):principal=json.loads(principal)
            workspaces=principal.get('workspace_ids') if isinstance(principal,dict) else None
            if (not isinstance(workspaces,list) or len(workspaces)!=1 or not isinstance(workspaces[0],str)
                    or not isinstance(principal.get('account_id'),str) or not principal['account_id']):
                raise ResearchError('auth','One signed-in workspace is required')
            result=authority.issue_runner({'schema':'ai4r-runner-grant:1','account_id':principal['account_id'],
                'workspace_id':workspaces[0],'expires_in_s':args.expires_in_s},args.output)
        else:
            result=authority.revoke_runner(args.grant_id)
        print(json.dumps(result,sort_keys=True));return 0
    except (ResearchError,OSError,ValueError,sqlite3.Error):
        print(json.dumps({'status':'blocked','reason':'Native startup, finite binding or protected operator custody is unavailable.'}))
        return 2
    finally:
        if authority is not None:authority.close()


if __name__=='__main__':raise SystemExit(main())
