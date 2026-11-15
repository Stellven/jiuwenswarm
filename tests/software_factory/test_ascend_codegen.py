"""Real source generation checks; these never simulate CANN or an NPU pass."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from jiuwenswarm.software_factory.ascend_codegen import native_plan
from jiuwenswarm.software_factory.construction_pipeline import _requested_backend, validate_code_diff, validate_cpu_reference
from jiuwenswarm.software_factory.contracts import Artifact, StageBlocked, StageFailure
from jiuwenswarm.software_factory.core_codegen import extract_core, generate_project
from jiuwenswarm.software_factory.native_build import prepare
from jiuwenswarm.software_factory.task_contract import compile_goals


SOURCE = Path(os.environ.get('STRATA_SOURCE', '/workspace/strata')).resolve()
TOOL = Path('/workspace/factory-runs/898700bb76154c07b9f60f48fe70adbf/stages/n19/1/toolchain/bin/cmake')


class AscendSourceGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SOURCE/'.git').is_dir():
            raise AssertionError('Actual acquired STRATA source is required; no missing-source pass')
        cls.temporary = tempfile.TemporaryDirectory(prefix='ascend-source-check-')
        cls.root = Path(cls.temporary.name)
        cls.inventory = extract_core(SOURCE, cls.root/'ir', selected=['routing', 'activation', 'aggregation', 'normalization'])
        cls.project = cls.root/'project'
        cls.metadata = generate_project(cls.inventory, cls.project)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_native_graphs_bind_every_actual_source_and_do_not_claim_target_execution(self):
        plan = self.metadata['native_generation']
        self.assertTrue(plan['complete'])
        self.assertEqual({v['operation'] for v in plan['operations']}, {'router', 'swiglu', 'moe_combine', 'rms_norm'})
        self.assertFalse(plan['cpu_fallback_permitted'])
        for layer in ('native_compilation', 'device_execution', 'numerical_equivalence', 'full_model'):
            self.assertEqual(plan[layer], 'NOT_RUN')
        for item in plan['operations']:
            original = next(v for v in self.inventory['kernels'].values() if v['id'] == item['source_id'])
            self.assertEqual(item['function_sha256'], hashlib.sha256(original['source_code'].encode()).hexdigest())
            self.assertEqual(item['source_sha256'], hashlib.sha256(Path(original['source_path']).read_bytes()).hexdigest())
            self.assertTrue((self.project/item['implementation']).is_file())
            self.assertEqual(item['numerical_equivalence'], 'NOT_RUN')
            self.assertTrue(item['contract']['precision'])
        self.assertGreaterEqual(validate_code_diff(self.project/'code_diff.json')['source_pairs'], 8)

    def test_actual_cann_math_and_stable_selection_are_separate_from_cpu_objects(self):
        router = (self.project/'src/ascend/router.cpp').read_text()
        self.assertIn('aclnnSoftmaxGetWorkspaceSize', router)
        self.assertIn('aclnnSortGetWorkspaceSize,aclnnSort,p.ptr,true,int64_t(-1),true', router)
        self.assertIn('maximum(s,sum,limit,denom);divide(s,top,denom,output)', router)
        combine = (self.project/'src/ascend/moe_combine.cpp').read_text()
        self.assertIn('for(int e=0;e<k;++e)', combine)
        self.assertIn('if(has_shared)', combine)
        rms = (self.project/'src/ascend/rms_norm.cpp').read_text()
        self.assertIn('base+=32', rms)
        self.assertIn('offset=16;offset>0;offset>>=1', rms)
        self.assertIn('mul(s,x,wt,wx);mul(s,wx,inv,out)', rms)
        cmake = (self.project/'CMakeLists.txt').read_text()
        native_branch = cmake.split('if(STRATA_CORE_BACKEND STREQUAL "ASCEND")', 1)[1].split('elseif', 1)[0]
        self.assertIn('src/strata_native.cpp', native_branch)
        self.assertNotIn('src/strata_core.cpp', native_branch)
        for source in (self.project/'src/ascend').glob('*.cpp'):
            self.assertNotIn('cuda_cpu', source.read_text())
        for primitive, evidence in self.metadata['native_generation']['api_evidence'].items():
            self.assertEqual(len(evidence['header_sha256']), 64)
            self.assertTrue(evidence['declarations'], primitive)
            self.assertTrue(evidence['header_url'].endswith('/aclnn_'+primitive+'.h'))

    def test_source_only_preparation_checks_integrity_without_rechecking_sdk_or_hardware(self):
        report = prepare(self.project, self.root/'unused-build', source_only=True)
        self.assertEqual(report['source_integrity'], 'PASS')
        self.assertEqual(report['sdk_prerequisites'], 'NOT_RUN')
        self.assertEqual(report['native_compilation'], 'NOT_RUN')
        self.assertEqual(report['device_execution'], 'NOT_RUN')
        self.assertFalse(report['native_device_validated'])
        self.assertFalse((self.root/'unused-build').exists())
        process = subprocess.run(['python', str(self.project/'scripts/prepare_ascend.py'),
                                  '--project', str(self.project), '--check-source-only'],
                                 capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual(json.loads(process.stdout)['source_integrity'], 'PASS')

    def test_changed_source_math_fails_native_coverage_before_any_sdk_discovery(self):
        repository = self.root/'changed-source'
        subprocess.run(['git', 'clone', '--shared', '--quiet', str(SOURCE), str(repository)], check=True, timeout=60)
        source = repository/'src/kernels/cuda/shared_expert.cu'
        text = source.read_text()
        source.write_text(text.replace('out[i] = (float) (x / (1.0 + exp(-x))) * up[i];',
                                       'out[i] = (float) (x / (2.0 + exp(-x))) * up[i];', 1))
        inventory = extract_core(repository, self.root/'changed-ir', selected=['routing', 'activation'])
        project = self.root/'changed-project'
        metadata = generate_project(inventory, project)
        self.assertFalse(metadata['native_generation']['complete'])
        self.assertEqual([v['operation'] for v in metadata['native_generation']['operations'] if not v['generated']], ['swiglu'])
        process = subprocess.run([shutil.which('cmake') or str(TOOL), '-S', str(project), '-B', str(self.root/'changed-build'),
                                  '-DSTRATA_CORE_BACKEND=ASCEND'], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('Selected source expressions have no native implementation', process.stderr)
        self.assertNotIn('Could NOT find AscendCL', process.stderr)

    def test_target_backend_selection_and_cpu_acceptance_are_distinct(self):
        self.assertEqual(_requested_backend(SimpleNamespace(options={'target_backend': 'ascend'})), 'ASCEND')
        self.assertEqual(_requested_backend(SimpleNamespace(options={'target_backend': 'cpu'})), 'CPU')
        with self.assertRaises(StageBlocked):
            _requested_backend(SimpleNamespace(options={'target_backend': 'cuda'}))
        request = compile_goals({'target_backend': 'ascend', 'task': {'description': 'Validate reference and native target',
            'acceptance': {'cpu_validation': True, 'native_execution': True}}})
        self.assertIn('construction.cpu_validation', request['goals'])
        self.assertIn('inference.result', request['goals'])
        self.assertNotIn('construction.portability', request['goals'])
        source_request = compile_goals({'target_backend': 'cpu', 'task': {'description': 'Deliver portable source',
            'acceptance': {'source_project': True, 'cpu_validation': True}}})
        self.assertTrue({'construction.package', 'construction.portability', 'construction.cpu_validation'}.issubset(source_request['goals']))

    def test_separate_cpu_acceptance_actually_compiles_and_compares_all_selected_sources(self):
        root = self.root/'cpu-reference'
        root.mkdir()

        class Context:
            workspace = root
            options = {'target_backend': 'ascend', 'cmake': shutil.which('cmake') or str(TOOL)}
            node = {'id': 'isolated-cpu-reference-check'}
            commands = []

            def write_json(self, name, value):
                path = root/name
                path.write_text(json.dumps(value, indent=2)+'\n')
                return path

            def run_command(self, argv, timeout=120, **kwargs):
                result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **kwargs)
                number = len(self.commands)+1
                stdout, stderr = root/(str(number)+'.stdout'), root/(str(number)+'.stderr')
                stdout.write_text(result.stdout)
                stderr.write_text(result.stderr)
                record = {'argv': argv, 'stdout': result.stdout, 'stderr': result.stderr,
                          'stdout_path': str(stdout), 'stderr_path': str(stderr), 'exit_code': result.returncode}
                self.commands.append(record)
                if result.returncode:
                    raise StageFailure('command_failed', 'Actual local command failed', {'command': record})
                return record

        context = Context()
        source = context.write_json('source.json', {'source_dir': str(self.project), 'algorithms': self.inventory['selected'],
            'scope': 'Separate CPU and native generation', 'files': {p.relative_to(self.project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.project.rglob('*') if p.is_file()}})
        requirements = context.write_json('requirements.json', {'acceptance': {'cpu_validation': True}})

        def artifact(path, kind):
            return Artifact(kind, kind, str(path), hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, 'actual-source-generation')

        outputs = validate_cpu_reference(context, {'source': artifact(source, 'construction.source'),
                                                    'requirements': artifact(requirements, 'task.requirements')})
        report = json.loads(outputs['validation'].read_text())
        self.assertEqual(report['backend'], 'CPU')
        self.assertTrue(report['cpu_compilation_validated'])
        self.assertEqual(len(report['operation_coverage']), 4)
        self.assertTrue(all(v['status'] == 'passed' for v in report['operation_coverage']))
        self.assertGreater(report['cpu_numerical_validation']['total_comparisons'], 0)
        self.assertEqual(report['native_compilation'], 'NOT_RUN')
        self.assertEqual(report['device_execution'], 'NOT_RUN')
        self.assertFalse(report['native_device_validated'])
        self.assertTrue(any('-DSTRATA_CORE_BACKEND=CPU' in v['argv'] for v in context.commands))
        self.assertFalse(any('-DSTRATA_CORE_BACKEND=ASCEND' in v['argv'] for v in context.commands))


if __name__ == '__main__':
    unittest.main()
