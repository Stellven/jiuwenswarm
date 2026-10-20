import tempfile
import unittest
from pathlib import Path
from jiuwenswarm.research.accounts import AccountStore
from jiuwenswarm.research.configuration import PreferenceError


class AccountTests(unittest.TestCase):
    def test_stable_separate_identity_and_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'account'
            store = AccountStore(db)
            identity = store.primary()
            store.save_preferences(identity['account_id'], 'account', 'default', {'timezone': 'UTC'}, root=Path(directory))
            store.save_preferences(identity['account_id'], 'project', 'project', {'timezone': 'Europe/London'}, root=Path(directory))
            self.assertEqual(store.resolve(identity['account_id'], 'host', 'project', root=Path(directory))['timezone'], 'Europe/London')
            with self.assertRaises(PreferenceError):
                store.save_preferences(identity['account_id'], 'project', 'project', {'cc': {'router': {'enabled': True}}}, root=Path(directory))
            store.close()
            reopened = AccountStore(db)
            self.assertEqual(reopened.primary()['account_id'], identity['account_id'])
            reopened.close()
