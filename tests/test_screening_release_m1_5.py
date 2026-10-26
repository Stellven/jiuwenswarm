import copy
import json
from pathlib import Path
import tempfile
import unittest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.capsules.assets import build_research_assets, load_research_catalog
from jiuwenswarm.research.checks.research import rank_opportunities, CheckError


class ScreeningReleaseTests(unittest.TestCase):
    def test_repaired_release_passes_real_library_check_association_validation(self):
        from jiuwenswarm.research.library import LibraryService
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteRunStore(temp)
            try:
                asset = build_research_assets(store, screening_version='m1-5')['screening']
                library = LibraryService(store)
                library._validate_association(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'])
                self.assertEqual(store.read_record(asset['bundle_ref'])['bundle_id'], 'research.screening.checks')
                self.assertEqual(store.read_record(asset['profile_ref'])['profile_id'], 'research.screening.profile')
            finally:
                store.close()

    def test_additive_release_preserves_base_and_independent_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteRunStore(temp)
            try:
                old = build_research_assets(store)
                repaired = build_research_assets(store, screening_version='m1-5')
                old_s, new_s = old['screening'], repaired['screening']
                self.assertEqual(json.loads(json.dumps(old_s)), load_research_catalog()['stages']['screening'])
                self.assertNotEqual(old_s['declaration_ref'], new_s['declaration_ref'])
                self.assertEqual(store.read_record(new_s['declaration_ref'])['identity']['version_label'], 'm1-5')
                self.assertEqual(old_s['runner_ref'], new_s['runner_ref'])
                self.assertEqual(store.read_record(old_s['bundle_ref'])['checks'], store.read_record(new_s['bundle_ref'])['checks'])
                for name in old_s['body_refs']:
                    self.assertEqual(old_s['body_refs'][name] == new_s['body_refs'][name], name != 'screening_prompt.txt')
                for stage in old:
                    if stage != 'screening':
                        self.assertEqual(old[stage], repaired[stage])
                text = store.read_blob(new_s['body_refs']['screening_prompt.txt']).decode()
                self.assertIn('exact id', text)
                self.assertIn('dependency_flags=[] and eligible=true', text)
                self.assertIn('do not remove scientific caveats', text)
            finally:
                store.connection.close()

    def fixture(self):
        rubric = json.loads(Path('jiuwenswarm/research/resources/capsules/screening_rubric.json').read_text())
        idea = {'idea_id': 'a', 'title': 'A bounded change', 'summary': 'A local intervention',
                'assumptions': ['Generalization is untested.'], 'risks': [], 'citation_ids': ['c']}
        score = {'idea_id': 'a', 'novelty': 3, 'feasibility': 4, 'compute_alignment': 5,
                 'novelty_reason': 'Known method.', 'feasibility_reason': 'Bounded implementation.',
                 'compute_alignment_reason': 'Fits available resources.', 'total': 12,
                 'citation_ids': ['c'], 'dependency_flags': [], 'eligible': True,
                 'disposition': 'selected', 'disposition_reason': 'Highest eligible score.'}
        return rubric, idea, score

    def test_scientific_uncertainty_is_not_itself_a_forbidden_dependency(self):
        rubric, idea, score = self.fixture()
        self.assertEqual(rank_opportunities([idea], [score], rubric)[1], 'a')

    def test_free_prose_flags_still_rejected(self):
        rubric, idea, score = self.fixture()
        score['dependency_flags'] = ['Generalization is untested.']
        with self.assertRaisesRegex(CheckError, 'dependency_filter'):
            rank_opportunities([idea], [score], rubric)

    def test_actual_forbidden_dependency_requires_exact_flag_and_rejection(self):
        rubric, idea, score = self.fixture()
        forbidden = copy.deepcopy(idea)
        forbidden.update(idea_id='b', title='Needs a proprietary model')
        rejected = copy.deepcopy(score)
        rejected.update(idea_id='b', dependency_flags=['dep:proprietary_model'], eligible=False,
                        disposition='rejected', disposition_reason='Forbidden model dependency.')
        self.assertEqual(rank_opportunities([idea, forbidden], [score, rejected], rubric)[1], 'a')
        rejected['dependency_flags'] = []
        rejected['eligible'] = True
        with self.assertRaisesRegex(CheckError, 'dependency_filter'):
            rank_opportunities([idea, forbidden], [score, rejected], rubric)


if __name__ == '__main__':
    unittest.main()
