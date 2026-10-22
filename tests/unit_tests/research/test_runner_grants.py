"""Finite operator-issued ordinary HTTP grants, without browser authority."""
import os
import time

import unittest
import tempfile
from pathlib import Path

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.shell_auth import SessionAuthority


def check_runner_grant(tmp_path, raises):
    authority=SessionAuthority(tmp_path/'sessions','http://127.0.0.1:5175')
    principal=Principal('alice',frozenset({'project'}),frozenset({'readiness','submit','status','reconcile','cancel',
        'export','upload','list_uploads','delete_upload','settings'}),frozenset({'researcher','reviewer'}))
    authority.initialize(principal)
    binding={'schema':'ai4r-runner-grant:1','account_id':'alice','workspace_id':'project','expires_in_s':60}
    token_path=tmp_path/'runner-token'
    try:
        receipt=authority.issue_runner(binding,token_path)
        token=token_path.read_text();authorization='Bearer '+token
        assert token not in str(receipt) and token_path.stat().st_uid==11001 and token_path.stat().st_mode&0o777==0o600
        assert authority.authenticate(authorization,'submit','project').account_id=='alice'
        for operation in ('settings','delete_upload','evaluation_profile'):
            with raises(ResearchError):authority.authenticate(authorization,operation)
        with raises(ResearchError):authority.authenticate(authorization,'status','foreign')
        with raises(ResearchError):authority.authenticate(authorization,'export',audience='reviewer')
        with raises(ResearchError):authority.authenticate_ws({'authorization':authorization,'host':'127.0.0.1:5175'},'status')
        with raises(ResearchError):authority.authorize_evaluation(authorization,'submit',submission={'profile_id':'private'})
        with raises(FileExistsError):authority.issue_runner(binding,token_path)
        authority.revoke_runner(receipt['grant_id'])
        with raises(ResearchError):authority.authenticate(authorization,'status')
        second=tmp_path/'second';second_receipt=authority.issue_runner(binding,second)
        authority.db.execute('UPDATE runner_grants SET expires_at=? WHERE id=?',(time.time()-1,second_receipt['grant_id']))
        with raises(ResearchError):authority.authenticate('Bearer '+second.read_text(),'status')
        third=tmp_path/'third';authority.issue_runner(binding,third)
        authority.revoke(authority.token_path.read_text())
        with raises(ResearchError):authority.authenticate('Bearer '+third.read_text(),'status')
    finally:authority.close()


@unittest.skipUnless(os.name=='posix' and hasattr(os,'geteuid') and os.geteuid()==0,'actual Linux root-only issuer')
class RunnerGrantTests(unittest.TestCase):
    def test_finite_scoped_revocable_and_never_native_session(self):
        with tempfile.TemporaryDirectory() as directory:check_runner_grant(Path(directory),self.assertRaises)


if __name__=='__main__':unittest.main()
