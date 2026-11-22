import unittest

from prefetch import counters


GOOD = ('expert_demand_predictor: native phase=prefill requested=9 already_resident=3 issued=5 '
        'issued_bytes=80 useful_ready=3 useful_bytes=48 miss=8 late=1 unused=1 pending=0')


class PrefetchTests(unittest.TestCase):
    def test_keep_resident_and_useful_separate(self):
        report = counters(GOOD)
        self.assertEqual(report['prefill']['totals']['already_resident'], 3)
        self.assertEqual(report['prefill']['totals']['useful_bytes'], 48)
        self.assertIsNone(report['decode']['totals'])

    def test_reject_duplicate_and_impossible_late_count(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            counters(GOOD + '\n' + GOOD)
        with self.assertRaisesRegex(ValueError, 'conserve'):
            counters(GOOD.replace('late=1', 'late=9'))

    def test_decode_graph_separates_completions_from_graph_success(self):
        log = GOOD.replace('phase=prefill', 'phase=decode request=1 sequence=0 graph=9')
        result = counters(log + ' completed=5 completed_bytes=80 success=1')
        self.assertEqual(result['decode']['totals']['completed_transfers'], 5)
        self.assertTrue(result['decode']['rows'][0]['graph_completed'])
