"""Task-provided arithmetic oracles against real source-derived executables.

Only acquisition is replaced with a local clone of the acquired pinned STRATA
source. These checks establish CPU scalar arithmetic and oracle enforcement;
they do not establish a new network fetch, model inference, or native NPU use.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from jiuwenswarm.software_factory.catalog import STRATA_REPOSITORY, stage_catalog
from jiuwenswarm.software_factory.contracts import StageFailure
from jiuwenswarm.software_factory.core_codegen import discover_operations
from jiuwenswarm.software_factory.engine import FactoryService
from jiuwenswarm.software_factory.oracle_validation import OracleError, compare_expected, normalize_oracle
from jiuwenswarm.software_factory.source_planning import select_operations
from jiuwenswarm.software_factory.strata_patch import PIN


def source_directory():
    return Path(os.environ.get('STRATA_TEST_SOURCE', '/workspace/strata')).resolve()


def local_acquire(ctx, inputs):
    """Explicit isolated transport substitution; subsequent stages are real."""
    directory = ctx.workspace/'workspace'/'strata'
    directory.parent.mkdir(parents=True)
    ctx.run_command(['git', 'clone', '--local', '--no-hardlinks', str(source_directory()), str(directory)], timeout=120)
    actual = ctx.run_command(['git', 'rev-parse', 'HEAD'], cwd=directory)['stdout'].strip()
    if actual != PIN:
        raise StageFailure('source_pin_mismatch', 'Isolated source clone differs from the required upstream pin')
    if ctx.run_command(['git', 'status', '--porcelain'], cwd=directory)['stdout'].strip():
        raise StageFailure('source_dirty', 'Isolated source clone is modified')
    return {'source': ctx.write_json('source.json', {
        'schema': 'factory.source.v1', 'source_dir': str(directory), 'commit_sha': actual,
        'repository_url': STRATA_REPOSITORY, 'requested_revision': PIN, 'resolved_revision': PIN,
        'acquisition_mode': 'isolated_test_local_clone_of_previously_network_acquired_source',
        'dependencies': ['CMake', 'C++20'], 'build_entry': 'CMakeLists.txt',
    })}


class OracleContractTests(unittest.TestCase):
    def test_expected_object_is_subset_but_nested_tensor_shapes_must_match(self):
        actual = {'backend': 'CPU', 'output': [2, -4, 0, 7], 'metadata': {'count': 4}}
        checked = compare_expected(actual, {'output': [2, -4, 0, 7]}, atol=0, rtol=0)
        self.assertEqual(checked['comparisons'], 4)
        self.assertEqual(checked['mismatched_values'], 0)
        self.assertEqual(checked['max_abs_error'], 0)
        self.assertEqual(checked['mismatches'], [])
        for expected in ({'output': [2, -4, 0]}, {'output': {'0': 2}}, {'missing': [2]}):
            with self.subTest(expected=expected):
                mismatch = compare_expected(actual, expected, atol=0, rtol=0)
                self.assertGreater(mismatch['mismatched_values'], 0)

    def test_numeric_tolerance_and_nonfinite_actual_are_not_schema_only_passes(self):
        checked = compare_expected({'output': [1.00001, 10.0001]}, {'output': [1, 10]}, atol=0.00002, rtol=0.00002)
        self.assertEqual(checked['comparisons'], 2)
        self.assertEqual(checked['mismatched_values'], 0)
        checked = compare_expected({'output': [1.01]}, {'output': [1]}, atol=1e-6, rtol=1e-6)
        self.assertEqual(checked['mismatched_values'], 1)
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value):
                checked = compare_expected({'output': [value]}, {'output': [1]})
                self.assertGreater(checked['mismatched_values'], 0)

    def test_oracle_requires_nonempty_cases_and_finite_nonempty_expectation(self):
        valid = {'cases': [{'input': '4 2 1 -2 0 3.5\n', 'operation': 'scale_kernel',
                            'expected': {'output': [2, -4, 0, 7]}, 'atol': 1e-6, 'rtol': 1e-6}]}
        normalized = normalize_oracle(valid)
        self.assertEqual(normalized['cases'][0]['expected'], valid['cases'][0]['expected'])
        for invalid in ({'cases': []}, {'cases': [{'input': '1 2 3', 'expected': {}}]},
                        {'cases': valid['cases'] * 17},
                        {'cases': [{'input': '1 2 3', 'expected': {'output': [float('nan')]}}]},
                        {'cases': [{'input': '1 2 3', 'expected': {'output': [3]}, 'rtol': float('inf')}]},
                        {'cases': [{'input': '1 2 3', 'expected': {'output': [3]}, 'atol': -1}]}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(OracleError) as error:
                    normalize_oracle(invalid)
                self.assertEqual(error.exception.code, 'invalid_task_oracle')


class RealSourceOraclePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = source_directory()
        if not (source/'.git').is_dir():
            raise unittest.SkipTest('STRATA_TEST_SOURCE must identify the acquired pinned STRATA source')
        if not shutil.which('make') or not shutil.which('c++'):
            raise unittest.SkipTest('Actual C++ compiler and make are required for the source pipeline check')
        actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != PIN:
            raise AssertionError(f'Test source pin differs: {actual}')
        discovered = discover_operations(source)
        selected = select_operations({'operations': discovered}, {
            'source_scope': ['src/kernels/cuda/elementwise.cu'], 'capabilities': ['scale_kernel']})
        if len(selected) != 1 or selected[0]['name'] != 'scale_kernel':
            raise AssertionError('The independently supplied scale oracle no longer matches inspected source selection')
        cls.descriptor = selected[0]
        cls.cmake = shutil.which('cmake')
        if cls.cmake is None:
            candidate = source/'.factory-tools/bin/cmake'
            if not candidate.is_file():
                raise unittest.SkipTest('CMake is required for the actual source pipeline check')
            cls.cmake = str(candidate)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        stages = [replace(stage, execute=local_acquire) if stage.id == 'source.fetch' else stage
                  for stage in stage_catalog()]
        self.service = FactoryService(self.root, stages)

    def tearDown(self):
        self.service.pool.shutdown(wait=True)
        self.temporary.cleanup()

    def request(self, expected=None, include_oracle=True):
        task = {'description': 'Build the actual scoped scalar production kernel and verify supplied arithmetic',
                'source_scope': ['src/kernels/cuda/elementwise.cu'], 'capabilities': ['scale_kernel'],
                'acceptance': {'source_project': False, 'cpu_validation': False}}
        if include_oracle:
            # Independent arithmetic: multiplying [1,-2,0,3.5] by scalar 2.
            # Expected values are not obtained from generated code or its output.
            task['oracle'] = {'cases': [{'input': '4 2 1 -2 0 3.5\n', 'operation': 'scale_kernel',
                'expected': {'output': [2, -4, 0, 7]} if expected is None else deepcopy(expected),
                'atol': 1e-6, 'rtol': 1e-6}]}
        return {'goals': ['construction.execution'], 'target_backend': 'cpu', 'revision': PIN,
                'repository_url': STRATA_REPOSITORY, 'owner_id': 'isolated-source-oracle-test',
                'cmake': self.cmake, 'task': task}

    def execution_node(self, run):
        return next(node for node in run['nodes'] if node['stage_id'] == 'construction.execute')

    def mixed_request(self, oracle_operation):
        request = self.request()
        request['task']['source_scope'] = ['src/kernels/cuda/router_top10.cu', 'src/kernels/cuda/elementwise.cu']
        request['task']['capabilities'] = ['routing', 'scale_kernel']
        if oracle_operation == 'routing':
            # Ranking [1,5,-2,3] selects indices [1,3], independently of the
            # generated implementation and of its activation/scale outputs.
            request['task']['oracle']['cases'] = [{
                'input': '4 2 1 5 -2 3\n', 'operation': 'router_top10_kernel',
                'expected': {'ids': [1, 3]}, 'atol': 0, 'rtol': 0,
            }]
        return request

    def test_actual_scalar_source_build_consumes_independent_oracle_and_input(self):
        request = self.request()
        request['goals'] = ['construction.package']
        run = self.service.create(request, background=False)
        self.assertEqual(run['status'], 'completed', json.dumps(run.get('error'), indent=2))
        execution = next(product for product in run['artifacts'] if product['kind'] == 'construction.execution')
        value = json.loads(Path(execution['path']).read_text())
        node = self.execution_node(run)
        self.assertEqual(node['status'], 'verified')
        self.assertEqual(value['numerical_result']['outputs_compared'], 0)
        self.assertEqual(value['numerical_validation']['built_in_comparisons'], 0)
        self.assertEqual(value['numerical_validation']['oracle_comparisons'], 4)
        self.assertEqual(value['numerical_validation']['total_comparisons'], 4)
        oracle = value['oracle_validation']
        self.assertEqual(oracle['status'], 'passed')
        self.assertEqual(oracle['comparisons'], 4)
        requirements = next(item for item in node['attempts'][0]['inputs'] if item['kind'] == 'task.requirements')
        self.assertEqual(oracle['requirements_sha256'], requirements['sha256'])
        case = oracle['cases'][0]
        self.assertEqual(case['actual']['output'], [2, -4, 0, 7])
        self.assertEqual(case['expected']['output'], [2, -4, 0, 7])
        self.assertEqual(Path(case['input_path']).read_text(), '4 2 1 -2 0 3.5\n')
        self.assertEqual(hashlib.sha256(Path(case['input_path']).read_bytes()).hexdigest(), case['input_sha256'])
        self.assertTrue(Path(case['argv'][0]).read_bytes().startswith(b'\x7fELF'))
        command = next(command for command in node['attempts'][0]['commands'] if command['argv'] == case['argv'])
        self.assertEqual(command['exit_code'], 0)
        self.assertEqual(json.loads(Path(case['stdout_path']).read_text())['output'], [2, -4, 0, 7])
        self.assertFalse(value['full_inference_validated'])
        source = next(product for product in run['artifacts'] if product['kind'] == 'construction.source')
        project = json.loads(Path(source['path']).read_text())
        self.assertIn('scale_kernel', (Path(project['source_dir'])/'src/strata_core.cpp').read_text())
        # The delivered ZIP must preserve its oracle and execute independently
        # of the factory process/import tree, including through ordinary CTest.
        package = next(product for product in run['artifacts'] if product['kind'] == 'construction.package')
        independent = self.root/'downloaded-project'
        with zipfile.ZipFile(package['path']) as archive:
            archive.extractall(independent)
        metadata = json.loads((independent/'project.json').read_text())
        packaged_oracle = independent/metadata['task_oracle']['oracle']
        packaged_runner = independent/metadata['task_oracle']['runner']
        self.assertEqual(json.loads(packaged_oracle.read_text())['cases'][0]['expected'], {'output': [2, -4, 0, 7]})
        self.assertTrue(packaged_runner.is_file())
        build = self.root/'downloaded-build'
        environment = {**os.environ, 'PYTHONPATH': ''}
        for argv in ([self.cmake, '-S', str(independent), '-B', str(build), '-G', 'Unix Makefiles', '-DSTRATA_CORE_BACKEND=CPU'],
                     [self.cmake, '--build', str(build), '--parallel', '2']):
            command = subprocess.run(argv, cwd=independent, env=environment, capture_output=True, text=True, timeout=180)
            self.assertEqual(command.returncode, 0, command.stdout+command.stderr)
        ctest = shutil.which('ctest') or str(Path(self.cmake).with_name('ctest'))
        argv = [ctest, '--test-dir', str(build), '--output-on-failure']
        command = subprocess.run(argv, cwd=independent, env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(command.returncode, 0, command.stdout+command.stderr)
        self.assertIn('task_oracle_acceptance', command.stdout)
        changed_oracle = json.loads(packaged_oracle.read_text())
        changed_oracle['cases'][0]['expected']['output'][-1] = 8
        packaged_oracle.write_text(json.dumps(changed_oracle))
        rejected = subprocess.run(argv, cwd=independent, env=environment, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(rejected.returncode, 0, rejected.stdout+rejected.stderr)
        self.assertIn('task_oracle_acceptance', rejected.stdout)

    def test_changed_expected_value_fails_real_compiled_execution(self):
        request = self.request(expected={'output': [2, -4, 0, 8]})
        request['task']['oracle']['cases'].append({
            'input': '3 -0.5 2 -4 8\n', 'operation': 'scale_kernel',
            'expected': {'output': [-1, 2, -4]}, 'atol': 1e-6, 'rtol': 1e-6,
        })
        run = self.service.create(request, background=False)
        self.assertEqual(run['status'], 'failed')
        node = self.execution_node(run)
        self.assertEqual(node['status'], 'failed')
        self.assertEqual(node['attempts'][-1]['error']['code'], 'oracle_numerical_mismatch')
        self.assertEqual(node['attempts'][-1]['error']['details']['cases_executed'], 2)
        commands = node['attempts'][-1]['commands']
        self.assertGreaterEqual(len(commands), 3)
        self.assertTrue(all(command['exit_code'] == 0 for command in commands))
        self.assertEqual(json.loads(Path(commands[-1]['stdout_path']).read_text())['output'], [-1, 2, -4])
        self.assertFalse(any(product['kind'] == 'construction.execution' for product in run['artifacts']))

    def test_zero_reference_comparisons_without_oracle_remain_blocked(self):
        run = self.service.create(self.request(include_oracle=False), background=False)
        self.assertEqual(run['status'], 'blocked')
        node = self.execution_node(run)
        self.assertEqual(node['status'], 'blocked')
        self.assertEqual(node['attempts'][-1]['error']['code'], 'numerical_oracle_missing')
        commands = node['attempts'][-1]['commands']
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]['exit_code'], 0)
        measured = json.loads(Path(commands[0]['stdout_path']).read_text().strip().splitlines()[-1])
        self.assertEqual(measured['outputs_compared'], 0)
        self.assertFalse(any(product['kind'] == 'construction.execution' for product in run['artifacts']))

    def test_router_comparisons_and_router_oracle_cannot_cover_other_selected_operation(self):
        run = self.service.create(self.mixed_request('routing'), background=False)
        self.assertEqual(run['status'], 'blocked')
        node = self.execution_node(run)
        self.assertEqual(node['status'], 'blocked')
        error = node['attempts'][-1]['error']
        self.assertEqual(error['code'], 'numerical_oracle_missing')
        self.assertTrue(any(source_id.endswith(':scale_kernel') for source_id in error['details']['uncovered_operations']))
        commands = node['attempts'][-1]['commands']
        self.assertGreaterEqual(len(commands), 2)
        measured = json.loads(Path(commands[0]['stdout_path']).read_text().strip().splitlines()[-1])
        self.assertGreater(measured['outputs_compared'], 0)
        router_output = json.loads(Path(commands[-1]['stdout_path']).read_text())
        self.assertEqual(router_output['ids'], [1, 3])
        self.assertFalse(any(product['kind'] == 'construction.execution' for product in run['artifacts']))

    def test_mixed_project_requires_independently_accounted_coverage_for_each_source_operation(self):
        run = self.service.create(self.mixed_request('scale_kernel'), background=False)
        self.assertEqual(run['status'], 'completed', json.dumps(run.get('error'), indent=2))
        execution = next(product for product in run['artifacts'] if product['kind'] == 'construction.execution')
        value = json.loads(Path(execution['path']).read_text())
        self.assertGreater(value['numerical_validation']['built_in_comparisons'], 0)
        self.assertEqual(value['numerical_validation']['oracle_comparisons'], 4)
        coverage = value['operation_coverage']
        self.assertEqual(len(coverage), 2)
        scale = next(item for item in coverage if item['source_id'].endswith(':scale_kernel'))
        router = next(item for item in coverage if item['source_id'] != scale['source_id'])
        self.assertEqual(scale['built_in_comparisons'], 0)
        self.assertEqual(scale['oracle_comparisons'], 4)
        self.assertEqual(scale['status'], 'passed')
        self.assertGreater(router['built_in_comparisons'], 0)
        self.assertEqual(router['oracle_comparisons'], 0)
        self.assertEqual(router['status'], 'passed')
        self.assertFalse(value['full_inference_validated'])


if __name__ == '__main__':
    unittest.main()
