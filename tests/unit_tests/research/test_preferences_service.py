import tempfile
import unittest
from pathlib import Path

from jiuwenswarm.research.accounts import AccountStore, PreferenceService
from jiuwenswarm.research.contracts import Principal, ResearchError


class PreferenceServiceTests(unittest.TestCase):
    def test_scopes_derive_server_ids_and_keep_active_snapshot_detached(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AccountStore(Path(directory) / 'account')
            account = store.primary()['account_id']
            principal = Principal(account, frozenset({'workspace'}), frozenset({'settings'}))
            service = PreferenceService(store, host_id='host', project_id='workspace', root=Path(directory))
            first = service.save(principal, 'account', {'display_name': 'Researcher', 'single_gpu': True})
            self.assertEqual(first['applies_on'], 'next_start')
            frozen = first['effective']
            service.save(principal, 'host', {'display_name': 'Host'})
            service.save(principal, 'project', {'display_name': 'Project'})
            self.assertEqual(service.get(principal)['effective']['display_name'], 'Project')
            self.assertEqual(frozen['display_name'], 'Researcher')
            for values in [{'codex': {}}, {'cc': {}}, {'workspace_input': '../outside'}]:
                with self.assertRaises(ResearchError):
                    service.save(principal, 'account', values)
            with self.assertRaises(ResearchError):
                service.get(Principal('foreign', frozenset({'workspace'}), frozenset({'settings'})))
            store.close()
