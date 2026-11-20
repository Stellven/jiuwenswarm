"""Check static role counts and overlapping retained trace accounting."""
import unittest

from quant_kernel_profile import storage_inventory, summarize, union_ns


def trace(spans):
    return {
        'schema': 'quant-kernel-spans/1', 'aligned_clock': True, 'engine': 'llama.cpp',
        'capture_id': 'synthetic', **{name: 'a' * 64 for name in
            ('engine_sha256', 'model_receipt_sha256', 'raw_trace_sha256', 'clock_receipt_sha256')},
        'windows': [{'phase': 'ttft', 'start_ns': 4, 'end_ns': 14}],
        'spans': [dict(start_ns=a, end_ns=b, device=device, quant_type=quant, operation=op)
                  for a, b, device, quant, op in spans],
    }


class QuantKernelProfileTest(unittest.TestCase):
    def test_static_roles_include_other_expert_types(self):
        text = '\n'.join((
            't layers.0.ffn.experts.0.w1.weight IQ2_XXS 0 0 66 256',
            't layers.0.ffn.experts.0.w2.weight IQ1_M 0 66 56 256',
            't layers.1.engram.embed.weight IQ4_NL 1 0 18 32',
        ))
        self.assertEqual(storage_inventory(text), [
            {'quant_type': 'IQ1_M', 'role': 'routed_expert_matrix', 'tensors': 1, 'stored_bytes': 56},
            {'quant_type': 'IQ2_XXS', 'role': 'routed_expert_matrix', 'tensors': 1, 'stored_bytes': 66},
            {'quant_type': 'IQ4_NL', 'role': 'engram', 'tensors': 1, 'stored_bytes': 18},
        ])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            storage_inventory(text + '\n' + text)

    def test_overlap_and_fusion(self):
        data = trace([(0, 10, 'CPU', 'IQ2_XXS', 'fused_quant'), (8, 13, 'GPU', 'IQ4_NL', 'dequant'),
                      (6, 9, 'CPU', 'IQ2_XXS', 'fused_quant'), (12, 14, 'GPU', 'unknown', 'unknown')])
        row = summarize(data)['rows'][0]
        self.assertEqual(row['target_quant_observed_union_ns'], 9)
        self.assertEqual(row['target_quant_cpu_gpu_overlap_ns'], 2)
        self.assertEqual(row['unknown_attribution_union_ns'], 2)
        self.assertEqual(row['unobserved_ns'], 0)
        self.assertEqual(row['rows'][0]['operation'], 'fused_quant')
        self.assertEqual(row['rows'][0]['inclusive_ns'], 6)

    def test_unobserved_and_invalid_trace(self):
        data = trace([])
        self.assertEqual(summarize(data)['rows'][0]['unobserved_ns'], 10)
        self.assertEqual(union_ns([(2, 4), (3, 8), (11, 12)]), 7)
        data['aligned_clock'] = False
        with self.assertRaisesRegex(ValueError, 'common clock'):
            summarize(data)


if __name__ == '__main__':
    unittest.main()
