import tempfile
import unittest
from contextlib import closing

from jiuwenswarm.research.contracts import Principal, validate
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.state import SQLiteRunStore


class CapsuleAssetsTests(unittest.TestCase):
    def test_complete_source_assets_separate_checks_and_no_auto_admission(self):
        from jiuwenswarm.research.capsules.assets import build_research_assets
        with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
            assets = build_research_assets(store)
            self.assertEqual(set(assets), {'search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery'})
            library = LibraryService(store)
            owner = Principal('verifier-owner', operations=frozenset({'verifier_assets'}))
            expected_versions = {
                'search': 'm1-6',
                'screening': 'm1-4',
                'hypothesis': 'm1-6',
                'builder': 'm1-13',
                'benchmark': 'm1-6-builder-tests',
                'evaluation': 'm1-5',
                'delivery': 'm1-5',
            }
            for stage, asset in assets.items():
                declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
                self.assertEqual(declaration['identity']['name'], 'research.' + stage)
                self.assertEqual(declaration['identity']['version_label'], expected_versions[stage])
                library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], owner)
                bundle = store.read_record(asset['bundle_ref'], contract_id='check-bundle')
                expected_range = expected_versions[stage] + '.x' if stage == 'screening' else expected_versions[stage]
                self.assertEqual(bundle['target_cc_version_range'], expected_range)
                self.assertEqual(len(bundle['checks']), len({c['check_id'] for c in bundle['checks']}))
                profile = store.read_record(asset['profile_ref'], contract_id='checking-profile')
                self.assertEqual(profile['target_cc_version_range'], expected_range)
                self.assertTrue(all(c['answerable_from'] == 'declaration_and_output' for c in profile['criteria']))
            self.assertEqual(library.entries(), [])
            screening = store.read_record(assets['screening']['declaration_ref'])
            self.assertEqual(screening['evolution']['may_change'], ['files:ranking_*.txt', 'files:screening_prompt.txt', 'files:screening_rubric.json'])
            self.assertEqual(store.read_record(assets['search']['declaration_ref'])['budget']['per_call'], {'wall_s': 300, 'invocations': 2, 'tool_calls': 20})
            self.assertEqual(store.read_record(assets['benchmark']['declaration_ref'])['needs']['injects'], [])
