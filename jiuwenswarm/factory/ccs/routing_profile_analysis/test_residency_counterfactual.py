"""Cross-check grouping, tail padding, and zero-copy exclusions."""
import json
import unittest

from residency_counterfactual import compare, upload_cost


class ResidencyCounterfactualTest(unittest.TestCase):
    def setUp(self):
        self.hashes = {
            'trace': 'a' * 64, 'ranks': 'b' * 64, 'transfer': 'c' * 64,
            'tensor_index': 'd' * 64, 'timing': 'e' * 64,
        }
        self.ranks = {
            'schema': 'routing-profile-analysis/1', 'layers': 1, 'experts_per_layer': 4,
            'rows': [{'k_per_layer': 1, 'indexed_payload_bytes': 6000}],
            'top_expert_ids_by_layer': [[1]], 'sha256': {'tensor_index': self.hashes['tensor_index']},
        }
        self.transfer = {
            'schema': 'routing-profile-transfer/1', 'capture_state': 'complete_as_reported',
            'sha256': {name: self.hashes[name] for name in ('trace', 'ranks')},
        }
        self.timing = {
            'schema': 'routing-copy-timing/1', 'sha256': {'transfer': self.hashes['transfer']},
            'prefill_submitted_bytes': 24000, 'replay_groups': 1, 'replay_copy_calls': 3,
            'qualifying_bandwidth_bytes_per_second': 10**9, 'matched_c1': {'ttft_s': 20},
        }
        self.index = ''.join(
            f't layers.0.ffn.experts.{expert}.w{role}.weight IQ2_XXS 0 0 {role * 1000}\n'
            for expert in range(4) for role in (1, 2, 3)
        )
        self.trace = [
            dict(type='event', microbatch=0, layer=0, phase='prefill', bytes_transferred=0, expert_ids=[[3]]),
            dict(type='event', microbatch=1, layer=0, phase='prefill', bytes_transferred=24000, expert_ids=[[0, 1, 2, 3]]),
            dict(type='event', microbatch=2, layer=0, phase='decode', bytes_transferred=0, expert_ids=[[0]]),
            dict(type='summary', expected=3, written=3, lost=0, transfer_incomplete=0, bytes_transferred=24000),
        ]

    def report(self):
        trace = b'\n'.join(json.dumps(row).encode() for row in self.trace)
        return compare(trace, self.ranks, self.transfer, self.index, self.timing, self.hashes)

    def test_group_split_can_reduce_bytes_and_increase_calls(self):
        self.assertEqual(upload_cost({0, 1, 3}, [1000, 2000, 3000], 4), (6, 19536))
        self.assertEqual(upload_cost(set(), [1000, 2000, 3000], 4), (0, 0))
        report = self.report()
        self.assertEqual(report['zero_copy_events_excluded'], 2)
        self.assertEqual(report['recorded_upload_bytes'], 24000)
        self.assertEqual(report['rows'][0]['modeled_upload_call_reduction'], -3)
        self.assertEqual(report['rows'][0]['modeled_avoided_upload_bytes'], 4464)

    def test_group_must_reproduce_recorded_bytes_and_copy_count(self):
        self.trace[1]['bytes_transferred'] = 23
        with self.assertRaisesRegex(ValueError, 'do not reproduce recorded bytes'):
            self.report()
        self.trace[1]['bytes_transferred'] = 24000
        self.timing['replay_copy_calls'] = 2
        with self.assertRaisesRegex(ValueError, 'differs from measured replay'):
            self.report()


if __name__ == '__main__':
    unittest.main()
