import unittest
from jiuwenswarm.research.checks.research import CheckError, rank_opportunities


class ScreeningChecks(unittest.TestCase):
    def fixture(self):
        ideas = [{'idea_id': name, 'title': 'Bounded variation', 'summary': 'Same assessment group', 'citation_ids': ['citation:one'], 'assumptions': [], 'risks': []} for name in ['idea:b', 'idea:a']]
        scores = [{'idea_id': i['idea_id'], 'novelty': 3, 'feasibility': 4, 'compute_alignment': 5, 'total': 12,
                   'novelty_reason': 'One reason.', 'feasibility_reason': 'One reason.', 'compute_alignment_reason': 'One reason.',
                   'citation_ids': ['citation:one'], 'dependency_flags': [], 'eligible': True,
                   'disposition': 'selected' if i['idea_id'] == 'idea:a' else 'eligible', 'disposition_reason': 'Fixed ranking.'} for i in ideas]
        rubric = {'dimensions': [{'name': n} for n in ['novelty', 'feasibility', 'compute_alignment']],
                  'reason_max_chars': 100, 'forbidden_dependencies': [{'id': 'dep:closed', 'match_terms': ['closed dataset']}]}
        return ideas, scores, rubric

    def test_same_group_retains_every_identity_and_ties(self):
        ideas, scores, rubric = self.fixture()
        ranking, selected = rank_opportunities(ideas, scores, rubric)
        self.assertEqual(selected, 'idea:a')
        self.assertEqual([r['idea_id'] for r in ranking], ['idea:a', 'idea:b'])
        with self.assertRaises(CheckError):
            rank_opportunities(ideas, scores[:1], rubric)

    def test_host_dependency_scan_cannot_be_omitted(self):
        ideas, scores, rubric = self.fixture()
        ideas[0]['risks'] = ['Requires CLOSED DATASET']
        with self.assertRaises(CheckError):
            rank_opportunities(ideas, scores, rubric)

    def test_dimension_order_does_not_change_the_frozen_ranking_policy(self):
        ideas,scores,rubric=self.fixture()
        expected=rank_opportunities(ideas,scores,rubric)
        rubric['dimensions'].reverse()
        self.assertEqual(rank_opportunities(ideas,scores,rubric),expected)
        rubric['dimensions'][1]=rubric['dimensions'][0]
        with self.assertRaises(CheckError):rank_opportunities(ideas,scores,rubric)
