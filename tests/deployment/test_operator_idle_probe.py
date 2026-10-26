"""Stopped-volume SQLite inspection preserves WAL and never edits source DBs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[2]/'deploy/m1/operator_host.py'
spec = importlib.util.spec_from_file_location('idle_probe_operator', SOURCE)
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class StoppedIdleProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root/'state'
        self.executor = self.root/'executor'
        self.research = self.state/'state/research.sqlite3'
        self.claims = self.executor/'ledger/claims.sqlite3'
        self.make(self.research, 'CREATE TABLE runs(state TEXT)', wal=True)
        self.make(self.claims, 'CREATE TABLE claims(state TEXT)')
        self.addCleanup(self.temp.cleanup)

    @staticmethod
    def make(path, sql, *, wal=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        if wal:db.execute('PRAGMA journal_mode=WAL')
        db.execute(sql)
        db.commit()
        db.close()

    def probe(self):
        return subprocess.run([sys.executable, '-B', '-c', host.IDLE_PROBE,
            str(self.state), str(self.executor), '--stopped-snapshot'],
            capture_output=True, text=True, timeout=15)

    def fingerprints(self):
        return {p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.root.rglob('*') if p.is_file()}

    def test_checkpointed_wal_database_is_read_without_source_mutation(self):
        self.assertFalse(Path(str(self.research)+'-wal').exists())
        before = self.fingerprints()
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'idle':True, 'active_runs':0, 'unfinished_claims':0, 'unreleased_leases':0})
        self.assertEqual(self.fingerprints(), before)

    def test_committed_active_run_in_wal_is_not_ignored(self):
        db = sqlite3.connect(self.research)
        try:
            db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute("INSERT INTO runs VALUES ('in_progress')")
            db.commit()
            self.assertGreater(Path(str(self.research)+'-wal').stat().st_size, 0)
            before = self.fingerprints()
            result = self.probe()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Active/unknown research execution', result.stderr)
            self.assertEqual(self.fingerprints(), before)
        finally:db.close()

    def test_unreleased_lease_still_blocks_lifecycle_changes(self):
        path = self.executor/'attempts/attempts.sqlite3'
        self.make(path, 'CREATE TABLE leases(state TEXT)')
        db = sqlite3.connect(path)
        db.execute("INSERT INTO leases VALUES ('active')")
        db.commit()
        db.close()
        result = self.probe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Active/unknown research execution', result.stderr)

    def test_missing_database_in_existing_optional_directory_is_not_idle(self):
        (self.executor/'attempts').mkdir()
        self.assertNotEqual(self.probe().returncode, 0)

    @unittest.skipUnless(os.name == 'posix', 'Native symlink fixture')
    def test_symlinked_wal_is_rejected(self):
        other = self.root/'foreign-wal'
        other.write_bytes(b'not a database journal')
        Path(str(self.research)+'-wal').symlink_to(other)
        self.assertNotEqual(self.probe().returncode, 0)


if __name__ == '__main__':
    unittest.main()
