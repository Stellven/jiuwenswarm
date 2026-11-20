"""Validate units, trace identity and the C1 comparison denominator."""
import unittest

from copy_timing import timing


class CopyTimingTest(unittest.TestCase):
    def setUp(self):
        self.transfer = {
            'schema': 'routing-profile-transfer/1', 'capture_state': 'complete_as_reported',
            'known_submitted_copy_bytes': 10**9,
            'submitted_copy_by_dispatch_phase': {'prefill': {'known_submitted_copy_bytes': 10**9}},
            'sha256': {'trace': 'a' * 64}, 'unknown_copy_events': 0,
        }
        self.replay = {
            'schema': 'spark-mmap-expert-copy-replay/1', 'event_sha256': 'a' * 64,
            'submitted_bytes': 10**9, 'groups': 1, 'copy_calls': 4,
            'samples': [
                {'pass_index': 0, 'wall_s': 4, 'measured_GB_s': 0.25},
                {'pass_index': 1, 'wall_s': 1, 'measured_GB_s': 1},
                {'pass_index': 2, 'wall_s': 10, 'measured_GB_s': 0.1},
                {'pass_index': 3, 'wall_s': 0.5, 'measured_GB_s': 2},
            ],
            'warm_median_GB_s': 1, 'scope': 'Replay scope',
        }
        self.request = dict(ok=True, arm='C1', ttft_s=20, timings={'prompt_ms': 19000, 'prompt_n': 512, 'cache_n': 0},
                            prompt_tokens=512, request_path='runs/c1/request-01/request.json')
        self.activation = dict(arm='C1', binary_sha256='a' * 64,
                               command=['server', '-lm', 'mmap', '--cpu-moe'], result_path='/host/runs/c1')
        self.baseline = {'summary': [{'arm': 'A', 'prompt_tokens': 512, 'ttft_s': 10, 'n': 5}]}

    def report(self):
        return timing(self.transfer, self.replay, self.request, self.activation, self.baseline, {})

    def test_bytes_per_second_and_matched_denominator(self):
        report = self.report()
        self.assertEqual(report['qualifying_bandwidth_bytes_per_second'], 10**9)
        self.assertEqual(report['serial_copy_equivalent_seconds'], 1)
        self.assertEqual(report['serial_copy_equivalent_fraction_of_c1_ttft'], 0.05)
        self.assertEqual(report['rows'][2]['serial_copy_equivalent_seconds'], 10)
        self.assertEqual(report['historical_a_warm_context']['ttft_median_s'], 10)

    def test_trace_and_rate_reconcile(self):
        self.replay['event_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'complete prefill copy trace'):
            self.report()
        self.replay['event_sha256'] = self.transfer['sha256']['trace']
        self.replay['samples'][0]['measured_GB_s'] = 250
        with self.assertRaisesRegex(ValueError, 'sample index does not reconcile'):
            self.report()

    def test_wrong_timed_run_rejected(self):
        self.request['request_path'] = 'runs/another-c1/request-01/request.json'
        with self.assertRaisesRegex(ValueError, 'match the C1 activation run'):
            self.report()


if __name__ == '__main__':
    unittest.main()
