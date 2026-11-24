"""Verify phase, distinct union and recorder-loss accounting."""
import json
import unittest

from routing_transfer import compare


RANKS = {
    'schema': 'routing-profile-analysis/1', 'layers': 1, 'experts_per_layer': 3,
    'rows': [{'k_per_layer': 1}, {'k_per_layer': 2}], 'top_expert_ids_by_layer': [[2, 0]],
}


def events(*records):
    return b'\n'.join(json.dumps(record).encode() for record in records)


def dispatch(microbatch, phase, copies, ids, **extra):
    return dict(type='event', layer=0, microbatch=microbatch, phase=phase,
                bytes_transferred=copies, expert_ids=ids, **extra)


class RoutingTransferTest(unittest.TestCase):
    def test_mixed_phases_and_union_deduplication(self):
        trace = events(
            dispatch(1, 'prefill', 50, [[2, 1], [2, 0]]),
            dispatch(2, 'mixed', None, [[2], [0], [1]],
                     rows=[{'phase': 'prefill'}, {'phase': 'decode'}, {'phase': 'unknown'}]),
            dict(type='summary', expected=3, written=2, lost=1, bytes_transferred=50, transfer_incomplete=1),
        )
        report = compare(trace, RANKS, {})
        self.assertEqual(report['capture_state'], 'accounted_loss')
        prefill, _, decode, _, unknown, _ = report['rows']
        self.assertEqual((prefill['route_selections'], prefill['covered_route_selections']), (5, 3))
        self.assertEqual((prefill['dispatch_expert_unions'], prefill['covered_dispatch_expert_unions']), (4, 2))
        self.assertEqual(decode['route_fraction'], 0)
        self.assertEqual(unknown['route_selections'], 1)
        self.assertEqual(report['submitted_copy_by_dispatch_phase']['mixed']['unknown_events'], 1)
        self.assertEqual(report['known_submitted_copy_bytes'], 50)

    def test_empty_and_without_summary_preserve_uncertainty(self):
        empty = compare(b'', RANKS, {})
        self.assertEqual(empty['capture_state'], 'empty')
        self.assertIsNone(empty['known_submitted_copy_bytes'])
        self.assertTrue(all(row['route_fraction'] is None for row in empty['rows']))
        report = compare(events(dispatch(1, 'decode', 0, [[2]])), RANKS, {})
        self.assertEqual(report['capture_state'], 'missing_summary')
        self.assertEqual(report['known_submitted_copy_bytes'], 0)
        self.assertIsNone(report['recorder_summary'])

    def test_inconsistent_summary_and_duplicate_dispatch_fail(self):
        event = dispatch(1, 'prefill', 50, [[1]])
        bad = dict(type='summary', expected=1, written=1, lost=0, bytes_transferred=49, transfer_incomplete=0)
        with self.assertRaisesRegex(ValueError, 'summary does not reconcile'):
            compare(events(event, bad), RANKS, {})
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            compare(events(event, event), RANKS, {})

    def test_mixed_dispatch_requires_per_row_phase(self):
        with self.assertRaisesRegex(ValueError, 'missing row phases'):
            compare(events(dispatch(1, 'mixed', 20, [[1]])), RANKS, {})


if __name__ == '__main__':
    unittest.main()
