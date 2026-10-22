"""OS-operator management of finite ordinary runner credentials."""
from __future__ import annotations
import argparse
import json
import sqlite3
from .contracts import ResearchError
from .evaluation_grants import open_operator_authority, read_binding


def main(argv=None):
    parser=argparse.ArgumentParser(description='Manage finite ordinary research runner HTTP grants')
    sub=parser.add_subparsers(dest='operation',required=True)
    issue=sub.add_parser('issue');issue.add_argument('--binding-file',required=True);issue.add_argument('--output',required=True)
    revoke=sub.add_parser('revoke');revoke.add_argument('--grant-id',required=True)
    args=parser.parse_args(argv);authority=None
    try:
        authority=open_operator_authority()
        result=(authority.issue_runner(read_binding(args.binding_file),args.output) if args.operation=='issue'
                else authority.revoke_runner(args.grant_id))
        print(json.dumps(result,sort_keys=True));return 0
    except (ResearchError,OSError,ValueError,sqlite3.Error):
        print(json.dumps({'status':'blocked','reason':'Native startup, finite binding or protected operator custody is unavailable.'}))
        return 2
    finally:
        if authority is not None:authority.close()


if __name__=='__main__':raise SystemExit(main())
