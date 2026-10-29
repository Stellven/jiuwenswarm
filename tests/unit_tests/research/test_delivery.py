import unittest
from jiuwenswarm.research.checks.research import CheckError, REPORT_HEADINGS, report_sections


class DeliveryStructureTests(unittest.TestCase):
    def report(self):
        return '# Test\n' + '\n'.join('## ' + h + '\n' + ('- Recommendation: New authorized work.' if i == 7 else 'Content.') for i, h in enumerate(REPORT_HEADINGS))

    def test_exact_nine_sections_and_recommendation_scope(self):
        self.assertEqual(len(report_sections(self.report())), 9)
        for text in [self.report() + '\n## Extra\nwrong', self.report().replace('Content.', '', 1),
                     self.report().replace('Content.', 'Recommendation: Wrong section.', 1),
                     self.report().replace('- Recommendation:', '- Followup:')]:
            with self.assertRaises(CheckError):
                report_sections(text)
