"""Policy transitions cannot waive incomplete upgrades or unrelated histories."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from deploy.m1 import rsi_host_codex_upgrade as upgrade
from deploy.m1.rsi_host_codex_recovery import encoded, digest

@unittest.skipUnless(os.name=='posix' and os.geteuid()==0,'Root custody is part of the contract')
class PolicyUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
    def write(self,path,value):
        path.write_bytes(encoded(value));path.chmod(0o600)
    def transition(self,old,new):
        previous={'policy_sha256':old,'catalog':{},'session':{}}
        successor={**previous,'policy_sha256':new}
        archive={'profile.before.json':previous,'profile.after.json':successor}
        plan={'schema':'ai4r-host-codex-policy-upgrade-plan:1','prior_policy_sha256':old,'successor_policy_sha256':new,
              'prior_profile_sha256':digest(encoded(previous)),'successor_profile_sha256':digest(encoded(successor)),
              'archive_sha256':{name:digest(encoded(value)) for name,value in archive.items()}}
        sha=digest(encoded(plan));directory=self.root/'policy-upgrades'/sha
        directory.mkdir(parents=True,mode=0o700);directory.parent.chmod(0o700)
        self.write(directory/'plan.json',plan)
        claim={'schema':'ai4r-host-codex-policy-upgrade-claim:1','plan_sha256':sha};self.write(directory/'claim.json',claim)
        for name,value in archive.items():self.write(directory/name,value)
        self.write(directory/'complete.json',{'schema':'ai4r-host-codex-policy-upgrade-complete:1','plan_sha256':sha,
            'claim_sha256':digest(encoded(claim)),'profile_sha256':plan['successor_profile_sha256']})
        self.write(self.root/'profile.json',successor)
        return directory
    def test_exact_ancestor_chain_and_unrelated_policy(self):
        self.transition('a'*64,'b'*64);self.transition('b'*64,'c'*64)
        self.assertTrue(upgrade.policy_ancestor(self.root,'c'*64,'a'*64))
        self.assertFalse(upgrade.policy_ancestor(self.root,'c'*64,'d'*64))
    def test_disconnected_cycle_blocks_load(self):
        self.transition('a'*64,'b'*64);self.transition('b'*64,'a'*64)
        self.transition('c'*64,'d'*64)
        with self.assertRaises(ValueError):upgrade.verify_upgrade_complete(self.root)
    def test_duplicate_successor_blocks_load(self):
        self.transition('a'*64,'c'*64);self.transition('b'*64,'c'*64)
        with self.assertRaises(ValueError):upgrade.verify_upgrade_complete(self.root)
    def test_partial_upgrade_blocks_load(self):
        directory=self.transition('a'*64,'b'*64);(directory/'complete.json').unlink()
        with self.assertRaises(OSError):upgrade.verify_upgrade_complete(self.root)
    def test_archived_profile_tamper_blocks_load(self):
        directory=self.transition('a'*64,'b'*64);self.write(directory/'profile.before.json',{})
        with self.assertRaises(ValueError):upgrade.verify_upgrade_complete(self.root)
    def test_current_profile_must_be_exact_published_tip(self):
        self.transition('a'*64,'b'*64);self.write(self.root/'profile.json',{'policy_sha256':'a'*64})
        with self.assertRaises(ValueError):upgrade.verify_upgrade_complete(self.root)

if __name__=='__main__':unittest.main()