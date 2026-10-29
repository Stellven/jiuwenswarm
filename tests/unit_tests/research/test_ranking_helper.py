"""The production helper and its mutable body pin preserve the fixed contract."""
import copy
import unittest
from pathlib import Path


class RankingHelperTests(unittest.TestCase):
    def test_sum_three_tie_order_eligibility_and_top_one(self):
        from jiuwenswarm.research.capsules.ranking import rank_opportunities
        scores = [
            {'idea_id': 'idea:z', 'novelty': 5, 'feasibility': 5, 'compute_alignment': 5, 'eligible': False},
            {'idea_id': 'idea:b', 'novelty': 3, 'feasibility': 4, 'compute_alignment': 5, 'eligible': True},
            {'idea_id': 'idea:a', 'novelty': 4, 'feasibility': 4, 'compute_alignment': 4, 'eligible': True},
        ]
        original = copy.deepcopy(scores)
        expected = {'ranking': [{'rank': 1, 'idea_id': 'idea:a', 'total': 12},
                                {'rank': 2, 'idea_id': 'idea:b', 'total': 12}],
                    'selected_idea_id': 'idea:a'}
        self.assertEqual(rank_opportunities(scores), expected)
        self.assertEqual(rank_opportunities(list(reversed(scores))), expected)
        self.assertEqual(scores, original)

    def test_rejects_no_eligible_and_invalid_dimensions(self):
        from jiuwenswarm.research.capsules.ranking import rank_opportunities
        valid = {'idea_id': 'idea:a', 'novelty': 1, 'feasibility': 1, 'compute_alignment': 1, 'eligible': True}
        for change in [{'eligible': False}, {'novelty': True}, {'novelty': 0}, {'eligible': 'true'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                rank_opportunities([dict(valid, **change)])
        with self.assertRaises(ValueError):
            rank_opportunities([valid, valid])

    def test_resource_body_is_exact_installed_helper_not_checker(self):
        import jiuwenswarm.research.capsules.ranking as helper
        root = Path(helper.__file__).parents[1]
        installed = Path(helper.__file__).read_bytes()
        self.assertEqual((root / 'resources/capsules/ranking_parent.txt').read_bytes(), installed)
        self.assertNotIn(b'checks', installed)
        self.assertNotIn(b'import ', installed)
