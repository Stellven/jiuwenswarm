"""Isolated contract/parser checks; these are NOT model inference evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from jiuwenswarm.software_factory.contracts import Artifact, StageFailure, StageBlocked
from jiuwenswarm.software_factory.strata_inference import (
    build_baseline_engine, compare_model_outputs, inference_argv,
    inspect_logits, inspect_model_pack, role_backend,
    run_baseline_inference, run_candidate_inference,
)


def artifact(path, value, kind):
    """A real hash-checked local file used only for isolated contract tests."""
    path.write_text(json.dumps(value))
    return Artifact(path.stem, kind, str(path),
                    hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, 'isolated-test')


class LocalContext:
    def __init__(self, root, options=None):
        self.workspace = root
        self.options = options or {}

    def write_json(self, name, value):
        path = self.workspace / name
        path.write_text(json.dumps(value))
        return path

    def run_command(self, *args, **kwargs):
        raise AssertionError('No device or compiler process is authorized by this isolated contract test')

class DriverContractTests(unittest.TestCase):
    def test_actual_pinned_flags_no_invented_subcommand_or_ablation(self):
        argv=inference_argv(Path('/work/strata'),{'pack_dir':'/models/pack','ple_gguf':'/models/ple.gguf'}, {'prompt_tokens':[1,2,3],'max_new':2,'max_context':256},Path('/work/logits.f32'))
        self.assertEqual(argv[:5],['/work/strata','--pack','/models/pack','--tokens','1,2,3'])
        self.assertNotIn('generate',argv)
        self.assertNotIn('--no-ple',argv)
        self.assertIn('--greedy',argv)
        self.assertEqual(argv[argv.index('--expert-cache')+1],'0')

    def test_real_float32_format_requires_exact_shape_and_finite_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'logits'
            path.write_bytes(struct.pack('<ii',3,2)+struct.pack('<6f',1,2,3,4,5,6))
            result=inspect_logits(path,2,3)
            self.assertEqual(result['rows'],2)
            self.assertEqual(result['dtype'],'float32-le')
            with self.assertRaises(StageFailure):inspect_logits(path,1,3)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(StageFailure):inspect_logits(path)
            path.write_bytes(struct.pack('<ii',1,1)+struct.pack('<f',float('nan')))
            with self.assertRaises(StageFailure):inspect_logits(path)

    def test_tiny_or_missing_pack_cannot_be_reported_as_model_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StageBlocked):inspect_model_pack(tmp,{},Path(tmp))
            Path(tmp,'single.gguf').write_bytes(b'GGUF')
            with self.assertRaises(StageBlocked):inspect_model_pack(Path(tmp,'single.gguf'),{},Path(tmp))

    def test_original_cuda_reference_is_independent_of_requested_ascend_candidate(self):
        ctx = SimpleNamespace(options={'target_backend': 'ascend',
                                       'options': {'reference_backend': 'cuda'}})
        self.assertEqual(role_backend(ctx, 'original'), 'cuda')
        self.assertEqual(role_backend(ctx, 'candidate'), 'ascend')
        self.assertEqual(role_backend(SimpleNamespace(options={'target_backend': 'ascend'}), 'original'), 'cuda')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = LocalContext(root, ctx.options)
            inputs = {
                'source': artifact(root/'source.json', {'source_dir': str(root)}, 'source.checkout'),
                'environment': artifact(root/'environment.json', {'sdk': {}}, 'environment.report'),
            }
            with self.assertRaises(StageBlocked) as blocked:
                build_baseline_engine(ctx, inputs)
            self.assertEqual(blocked.exception.code, 'cuda_sdk_missing')
            self.assertEqual(blocked.exception.details['layer'], 'original_compile')

    def test_original_reference_backend_is_not_silently_replaced(self):
        with self.assertRaises(StageBlocked) as blocked:
            role_backend(SimpleNamespace(options={'target_backend': 'cuda',
                'options': {'reference_backend': 'ascend'}}), 'original')
        self.assertEqual(blocked.exception.code, 'original_backend_unavailable')

    def test_candidate_requires_generated_integration_receipt_before_device_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = LocalContext(root, {'target_backend': 'cuda'})
            inputs = {
                # Untrusted contract-test metadata does not stand for a compiled engine.
                'binary': artifact(root/'candidate-binary.json', {
                    'backend': 'cuda', 'role': 'candidate', 'full_model_binary': True,
                }, 'build.binary'),
                'environment': artifact(root/'environment.json', {'devices': {}}, 'environment.report'),
            }
            with self.assertRaises(StageFailure) as failed:
                run_candidate_inference(ctx, inputs)
            self.assertEqual(failed.exception.code, 'candidate_integration_missing')
            self.assertNotIsInstance(failed.exception, StageBlocked)

    def test_original_cuda_reference_reaches_device_gate_for_ascend_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = LocalContext(root, {'target_backend': 'ascend',
                                      'options': {'reference_backend': 'cuda'}})
            inputs = {
                'baseline_binary': artifact(root/'original-binary.json', {
                    'backend': 'cuda', 'role': 'original', 'full_model_binary': True,
                }, 'build.baseline'),
                'environment': artifact(root/'environment.json', {'devices': {}}, 'environment.report'),
            }
            with self.assertRaises(StageBlocked) as blocked:
                run_baseline_inference(ctx, inputs)
            self.assertEqual(blocked.exception.code, 'target_device_missing')
            self.assertEqual(blocked.exception.details['layer'], 'device_loading')


class IsolatedOutputComparisonTests(unittest.TestCase):
    """Local receipts exercise comparison policy; they certify no model execution."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ctx = LocalContext(self.root)
        settings = {'prompt_tokens': [1, 2], 'max_new': 1, 'max_context': 256,
                    'sampling': 'greedy', 'expert_cache': 0}
        self.receipts = {}
        for role, backend in [('candidate', 'ascend'), ('original', 'cuda')]:
            model_dir = self.root/role/'weights'
            model_dir.mkdir(parents=True)
            files = []
            for index, name in enumerate(['manifest.json', 'index.txt', 'dense.bin',
                                          'embd.bin', 'experts.bin', 'ple.gguf']):
                path = model_dir/name
                # These small bytes are contract-test identities, not valid model weights.
                path.write_bytes(f'isolated comparison file {index}'.encode())
                files.append({'path': str(path), 'size': path.stat().st_size,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            logits = self.root/f'{role}-logits.f32'
            logits.write_bytes(struct.pack('<ii', 3, 2)+struct.pack('<6f', 1, 2, 3, 4, 5, 6))
            self.receipts[role] = {
                'schema': 'factory.strata.inference.v1', 'backend': backend, 'role': role,
                'model': {'pack_dir': str(model_dir), 'ple_gguf': str(model_dir/'ple.gguf'),
                          'vocabulary': 3, 'layers': 48, 'index_rows': 6, 'files': files},
                'settings': deepcopy(settings), 'generated_tokens': [2],
                'logits': inspect_logits(logits),
                # This is explicitly test input to the comparison policy, not a device result.
                'ascend_validated': role == 'candidate',
            }

    def tearDown(self):
        self.temp.cleanup()

    def inputs(self):
        return {
            'inference': artifact(self.root/'candidate.json', self.receipts['candidate'], 'inference.result'),
            'baseline': artifact(self.root/'original.json', self.receipts['original'], 'inference.baseline'),
        }

    def assert_comparison_failure(self, code):
        with self.assertRaises(StageFailure) as failed:
            compare_model_outputs(self.ctx, self.inputs())
        self.assertEqual(failed.exception.code, code)

    def test_identical_model_bytes_at_distinct_mounts_allow_distinct_backends(self):
        result = compare_model_outputs(self.ctx, self.inputs())
        comparison = json.loads(result['comparison'].read_text())
        self.assertNotEqual(self.receipts['candidate']['model']['pack_dir'],
                            self.receipts['original']['model']['pack_dir'])
        self.assertEqual(comparison['candidate_backend'], 'ascend')
        self.assertEqual(comparison['reference_backend'], 'cuda')
        self.assertEqual(comparison['logits_compared'], 6)
        self.assertEqual(comparison['max_abs_error'], 0)
        self.assertTrue(comparison['ascend_validated'])

    def test_unvalidated_candidate_cannot_inherit_native_validation_from_reference(self):
        self.receipts['candidate']['ascend_validated'] = False
        comparison = json.loads(compare_model_outputs(self.ctx, self.inputs())['comparison'].read_text())
        self.assertFalse(comparison['ascend_validated'])

    def test_changed_model_bytes_reject_comparison_even_when_local_paths_are_valid(self):
        record = self.receipts['candidate']['model']['files'][2]
        path = Path(record['path'])
        path.write_bytes(b'changed isolated model identity')
        record.update(size=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.assert_comparison_failure('comparison_input_mismatch')

    def test_different_prompt_settings_reject_comparison(self):
        self.receipts['candidate']['settings']['prompt_tokens'] = [2, 1]
        self.assert_comparison_failure('comparison_input_mismatch')

    def test_role_alias_cannot_compare_candidate_to_itself(self):
        self.receipts['original']['role'] = 'candidate'
        self.assert_comparison_failure('inference_role_mismatch')

    def test_real_local_logit_difference_rejects_comparison(self):
        path = Path(self.receipts['candidate']['logits']['path'])
        path.write_bytes(struct.pack('<ii', 3, 2)+struct.pack('<6f', 1, 2, 3, 4, 5, 7))
        self.receipts['candidate']['logits'] = inspect_logits(path)
        self.assert_comparison_failure('logits_mismatch')

if __name__=='__main__':unittest.main()
