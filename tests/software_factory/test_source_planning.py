"""Real pinned-source planning checks with an explicitly isolated local fetch.

The production catalog performs network acquisition. These tests substitute only
source.fetch with git clone of an already acquired, unmodified upstream commit;
they are not evidence of a new network request, native-device or model inference.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from jiuwenswarm.software_factory.catalog import STRATA_REPOSITORY, stage_catalog
from jiuwenswarm.software_factory.contracts import StageFailure
from jiuwenswarm.software_factory.core_codegen import discover_operations
from jiuwenswarm.software_factory.engine import FactoryService
from jiuwenswarm.software_factory.source_planning import select_operations
from jiuwenswarm.software_factory.strata_patch import PIN


_DEFAULT_SOURCE = '/workspace/factory-runs/99ecb9591942439aa85683565ca4152f/stages/n1/1/workspace/strata'


def source_directory():
    return Path(os.environ.get('STRATA_TEST_SOURCE', _DEFAULT_SOURCE)).resolve()


def local_acquire_source(ctx, inputs):
    """Only test transport substitution; all downstream stages are production."""
    source = source_directory()
    destination = ctx.workspace / 'workspace' / 'strata'
    destination.parent.mkdir(parents=True, exist_ok=True)
    ctx.run_command(['git', 'clone', '--local', '--no-hardlinks', str(source), str(destination)], timeout=120)
    actual = ctx.run_command(['git', 'rev-parse', 'HEAD'], cwd=destination)['stdout'].strip()
    if actual != PIN or actual != ctx.options.get('revision', PIN):
        raise StageFailure('source_pin_mismatch', 'The isolated real-source clone does not match the requested upstream pin')
    if ctx.run_command(['git', 'status', '--porcelain'], cwd=destination)['stdout'].strip():
        raise StageFailure('source_dirty', 'Test source clone is unexpectedly modified')
    return {'source': ctx.write_json('source.json', {
        'schema': 'factory.source.v1', 'source_dir': str(destination), 'commit_sha': actual,
        'repository_url': STRATA_REPOSITORY, 'requested_revision': PIN, 'resolved_revision': PIN,
        'acquisition_mode': 'isolated_test_local_clone_of_previously_network_acquired_source',
        'dependencies': ['CMake', 'C++20', 'backend-specific SDK'], 'build_entry': 'CMakeLists.txt',
    })}


class RealSourcePlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = source_directory()
        if not (source / '.git').is_dir():
            raise unittest.SkipTest('Set STRATA_TEST_SOURCE to an actual acquired STRATA checkout at the pinned commit')
        actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != PIN:
            raise AssertionError(f'Real source fixture pin differs: {actual}')
        cls.discovery = {'operations': discover_operations(source)}

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        stages = [replace(stage, execute=local_acquire_source) if stage.id == 'source.fetch' else stage
                  for stage in stage_catalog()]
        self.service = FactoryService(self.root, stages)

    def tearDown(self):
        self.service.pool.shutdown(wait=True)
        self.temporary.cleanup()

    @staticmethod
    def requirements(capabilities, scope=None):
        return {'source_scope': scope or ['src/kernels/cuda/*.cu'], 'capabilities': capabilities}

    @staticmethod
    def request(capabilities, scope=None):
        return {'goals': ['construction.cpp'], 'target_backend': 'cpu', 'revision': PIN,
                'repository_url': STRATA_REPOSITORY, 'owner_id': 'isolated-real-source-test',
                'task': {'description': 'Construct the requested actual STRATA source operations',
                         'source_scope': scope or ['src/kernels/cuda/*.cu'],
                         'capabilities': capabilities,
                         'acceptance': {'source_project': False, 'cpu_validation': False}}}

    def run_request(self, capabilities, scope=None):
        run = self.service.create(self.request(capabilities, scope), background=False)
        failures = [(n['stage_id'], a.get('error')) for n in run['nodes'] for a in n['attempts']
                    if a['status'] != 'verified']
        self.assertEqual(run['status'], 'completed', json.dumps({'error': run.get('error'), 'attempt_failures': failures}, indent=2))
        return run

    def artifact(self, run, kind):
        candidates = [artifact for artifact in run['artifacts'] if artifact['kind'] == kind]
        self.assertEqual(len(candidates), 1)
        return candidates[0]

    def test_actual_discovery_and_contract_select_distinct_structures_without_task_template(self):
        default = select_operations(self.discovery, self.requirements(['routing', 'activation', 'aggregation']))
        normalization = select_operations(self.discovery, self.requirements(['normalization'], ['src/kernels/cuda/elementwise.cu']))
        self.assertEqual({row['category'] for row in default}, {'routing', 'activation', 'aggregation'})
        self.assertEqual({row['lowering_kind'] for row in default}, {'scalar', 'cooperative'})
        self.assertEqual(len(normalization), 1)
        self.assertEqual(normalization[0]['category'], 'normalization')
        self.assertEqual(normalization[0]['sourcefile'], 'src/kernels/cuda/elementwise.cu')
        self.assertEqual(normalization[0]['lowering_kind'], 'cooperative')
        self.assertTrue(normalization[0]['features']['shuffle'])
        self.assertNotEqual({row['id'] for row in default}, {row['id'] for row in normalization})
        for row in default + normalization:
            self.assertTrue(row['supported'])
            self.assertTrue(row['body'].strip())
            self.assertTrue((source_directory() / row['sourcefile']).is_file())

    def test_same_final_goal_selects_different_real_execution_instances_and_consumes_lowerings(self):
        default = self.run_request(['routing', 'activation', 'aggregation'])
        normalization = self.run_request(['normalization'], ['src/kernels/cuda/elementwise.cu'])
        self.assertEqual(default['request']['goals'], normalization['request']['goals'])
        profiles = []
        for run in (default, normalization):
            cpp = self.artifact(run, 'construction.cpp')
            self.assertTrue(Path(cpp['path']).is_file())
            self.assertEqual(hashlib.sha256(Path(cpp['path']).read_bytes()).hexdigest(), cpp['sha256'])
            compose = next(node for node in run['nodes'] if node['stage_id'] == 'metadata.compose_core')
            discovery_node = next(node for node in run['nodes'] if node['stage_id'] == 'source.discover')
            self.assertEqual(discovery_node['status'], 'verified')
            lowered = [node for node in run['nodes'] if node['stage_id'].startswith('lower.')]
            profiles.append([node['stage_id'] for node in lowered])
            mapped = self.artifact(run, 'operator.native_inventory')
            value = json.loads(Path(mapped['path']).read_text())
            self.assertEqual(len(value['consumed_lowerings']), len(lowered))
            for product in value['consumed_lowerings']:
                self.assertTrue(Path(product['path']).is_file())
                self.assertEqual(hashlib.sha256(Path(product['path']).read_bytes()).hexdigest(), product['sha256'])
                self.assertIn({'from': product['producer'], 'to': compose['id'], 'data': 'core.lowered'}, run['edges'])
                receipt = next(v for v in compose['attempts'][-1]['inputs'] if v['id'] == product['id'])
                self.assertEqual(receipt['sha256'], product['sha256'])
                self.assertEqual(receipt['producer'], product['producer'])
                producer = next(node for node in lowered if node['id'] == product['producer'])
                consumed = producer['attempts'][0]['inputs']
                self.assertEqual(len(consumed), 1)
                self.assertEqual(consumed[0]['kind'], 'source.operator')
                bound = next(node for node in run['nodes'] if node['id'] == consumed[0]['producer'])
                self.assertEqual(bound['stage_id'], 'source.bind_operation')
                bound_descriptor = json.loads(Path(consumed[0]['path']).read_text())['descriptor']
                lowered_ir = json.loads(Path(product['path']).read_text())
                self.assertEqual({item['id'] for item in lowered_ir['kernels'].values()}, {bound_descriptor['id']})
                self.assertEqual(bound['parameters']['operation_id'], bound_descriptor['id'])
                self.assertIn({'from': discovery_node['id'], 'to': bound['id'], 'data': 'source.operations'}, run['edges'])
            codegen = next(node for node in run['nodes'] if node['stage_id'] == 'construction.codegen')
            self.assertTrue(codegen['attempts'][0]['commands'])
            self.assertEqual(codegen['attempts'][0]['commands'][0]['exit_code'], 0)
            selection_events = [event for event in self.service.events(run['id'])['events'] if event['type'] == 'implementation.selected']
            self.assertEqual(len(selection_events), len(lowered))
            consumption_events = [event for event in self.service.events(run['id'])['events']
                                  if event['type'] == 'artifact.consumed' and event['node_id'] == compose['id']]
            self.assertEqual(len(consumption_events), len(lowered))
        self.assertEqual(profiles[0].count('lower.scalar'), 2)
        self.assertEqual(profiles[0].count('lower.cooperative'), 1)
        self.assertEqual(profiles[1], ['lower.cooperative'])
        self.assertNotEqual(Path(self.artifact(default, 'construction.cpp')['path']).read_bytes(),
                            Path(self.artifact(normalization, 'construction.cpp')['path']).read_bytes())

    def test_distinct_bindings_create_distinct_outputs_and_identical_binding_reuses_verified_instance(self):
        run = self.run_request(['routing', 'activation', 'aggregation'])
        execution = self.service.executions[run['id']]
        scalar_nodes = [node for node in execution.snapshot['nodes'] if node['stage_id'] == 'lower.scalar']
        self.assertEqual(len(scalar_nodes), 2)
        first, second = scalar_nodes
        self.assertNotEqual(first['instance_key'], second['instance_key'])
        first_output = next(artifact for artifact in execution.artifacts.values()
                            if artifact.kind == 'core.lowered' and artifact.producer == first['id'])
        second_output = next(artifact for artifact in execution.artifacts.values()
                             if artifact.kind == 'core.lowered' and artifact.producer == second['id'])
        self.assertNotEqual(first_output.path, second_output.path)
        self.assertNotEqual(first_output.sha256, second_output.sha256)
        operator = execution.artifacts[first['attempts'][0]['inputs'][0]['id']]
        before_nodes = len(execution.snapshot['nodes'])
        again = execution.invoke_stage('lower.scalar', {'operator': operator})['core']
        self.assertEqual(again.id, first_output.id)
        self.assertEqual(again.path, first_output.path)
        self.assertEqual(len(execution.snapshot['nodes']), before_nodes)
        self.assertEqual(len(first['attempts']), 1)


if __name__ == '__main__':
    unittest.main()
