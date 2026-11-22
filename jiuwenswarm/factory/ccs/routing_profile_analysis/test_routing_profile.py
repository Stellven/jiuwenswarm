"""Synthetic tests for the historical profile and payload accounting method."""
import hashlib
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from routing_profile import analyze, verify


class RoutingProfileTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.request = {'layers': 1, 'experts_per_layer': 3, 'top_k': [1, 3], 'sha256': {}}
        self.pin('before', struct.pack('<6I', 5, 5, 4, 999, 999, 999))
        self.pin('after', struct.pack('<3I', 6, 10, 100))
        self.index = ''.join(
            f't layers.0.ffn.experts.{expert}.w{role}.weight IQ2_XXS 0 0 {expert + role}\n'
            for expert in range(3) for role in range(1, 4)
        ).encode()
        self.pin('tensor_index', self.index)

    def pin(self, key, data):
        path = self.root / key
        path.write_bytes(data)
        self.request[key] = path
        self.request['sha256'][key] = hashlib.sha256(data).hexdigest()

    def test_rank_uses_before_and_ties_use_ascending_expert(self):
        report = analyze(self.request)
        self.assertEqual(report['top_expert_ids_by_layer'], [[0, 1, 2]])
        self.assertEqual(report['count_delta'], 102)
        self.assertEqual(report['rows'][0]['counter_delta_in_selected'], 1)
        self.assertEqual(report['rows'][0]['indexed_payload_bytes'], 6)
        self.assertEqual(report['rows'][1]['indexed_payload_bytes'], 27)
        self.assertEqual(report['rows'][1]['fraction_new_routes'], 1.0)
        self.assertTrue(verify(self.request, report))
        report['rows'][0]['indexed_payload_bytes'] = 7
        self.assertFalse(verify(self.request, report))

    def test_decreasing_count_and_partial_row_rejected(self):
        self.pin('after', struct.pack('<3I', 4, 10, 100))
        with self.assertRaisesRegex(ValueError, 'Counter decreased'):
            analyze(self.request)
        self.pin('after', struct.pack('<4I', 6, 10, 100, 0))
        with self.assertRaisesRegex(ValueError, 'Profile shape'):
            analyze(self.request)

    def test_duplicate_and_missing_tensor_fail(self):
        lines = self.index.splitlines(keepends=True)
        self.pin('tensor_index', self.index + lines[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            analyze(self.request)
        self.pin('tensor_index', b''.join(lines[:-1]))
        with self.assertRaisesRegex(ValueError, 'every main-layer expert'):
            analyze(self.request)

    def test_changed_input_fails_digest(self):
        self.request['before'].write_bytes(struct.pack('<3I', 5, 5, 4))
        with self.assertRaisesRegex(ValueError, 'pinned SHA-256'):
            analyze(self.request)


if __name__ == '__main__':
    unittest.main()
