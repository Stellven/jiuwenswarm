"""Actual multi-child production pools, whole-parent execution and leaf reuse.

The fixture is an already acquired pinned STRATA checkout. These tests execute
the real CUDA inventory analyzer as a subprocess and real discovery/extraction/
lowering functions against its files. They do not access a device, SDK or model,
and do not create a new production factory run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jiuwenswarm.software_factory.catalog import stage_catalog
from jiuwenswarm.software_factory.contracts import Stage, StageFailure
from jiuwenswarm.software_factory.core_codegen import discover_operations, validate_core
from jiuwenswarm.software_factory.engine import Execution
from jiuwenswarm.software_factory.source_planning import select_operations
from jiuwenswarm.software_factory.strata_patch import PIN
from jiuwenswarm.software_factory.workflow_definitions import WorkflowRegistry


SOURCE = Path(os.environ.get('STRATA_SOURCE', '/workspace/strata')).resolve()
FACTORY = Path(__file__).resolve().parents[2]/'jiuwenswarm/software_factory'
EXTRACTION = 'function_extraction/function_extraction'
SCALAR = 'scalar_implementation/scalar_lowering'
COOPERATIVE = 'cooperative_implementation/cooperative_lowering'


def analyze_actual_inventory(ctx, inputs):
    """Test acquisition boundary: inspect already acquired real source bytes."""
    path = ctx.workspace/'cuda-operations.json'
    ctx.run_command([sys.executable, str(FACTORY/'scripts/analyze_cuda.py'),
                     '--repository', str(SOURCE), '--output', str(path)], timeout=120)
    return {'inventory': path}


class NestedProductionPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SOURCE/'.git').is_dir():
            raise AssertionError('Actual acquired STRATA checkout is required; missing source is not a pass')
        actual = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != PIN:
            raise AssertionError(f'Pinned actual STRATA source required: {actual} != {PIN}')
        found = {'operations': discover_operations(SOURCE)}
        requirements = {'source_scope': ['src/kernels/cuda/*.cu'], 'capabilities': ['activation']}
        cls.scalar = select_operations(found, requirements)[0]
        cls.cooperative = select_operations(found, {**requirements, 'capabilities': ['routing']})[0]
        if cls.scalar['lowering_kind'] != 'scalar' or cls.cooperative['lowering_kind'] != 'cooperative':
            raise AssertionError('Actual source fixture must cover both lowering structures')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='nested-production-pool-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.catalog = stage_catalog()+[
            Stage('test.actual_inventory', 'Analyze previously acquired actual source', 'test_fixture', 'actual_source_inventory',
                  {}, {'inventory': 'operator.inventory'}, analyze_actual_inventory),
        ]
        self.registry = WorkflowRegistry(self.catalog)
        self.execution = Execution(self.directory/'run', {'goals': [], 'target_backend': 'cpu'}, self.catalog)
        self.inventory = self.execution.invoke_stage('test.actual_inventory', {})['inventory']

    def invoke(self, path, inputs, descriptor, instance_id='selection'):
        return self.execution.import_workflow(path, external_inputs=inputs, instance_id=instance_id,
            parameters={'operation_id': descriptor['id']}, registry=self.registry)

    def assert_actual_artifact(self, artifact):
        path = Path(artifact.path)
        self.assertTrue(path.is_file())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact.sha256)
        node = next(node for node in self.execution.snapshot['nodes'] if node['id'] == artifact.producer)
        self.assertEqual(node['status'], 'verified')
        self.assertEqual(node['attempts'][-1]['verification']['outcome'], 'pass')
        return node

    def assert_origin(self, node, full_ref, siblings, unselected):
        origin = node['pool_origin']
        self.assertEqual(origin['full_ref'], full_ref)
        self.assertEqual(origin['parent_ref'], full_ref.rsplit('/', 1)[0])
        self.assertEqual(origin['canonical_stage_id'], node['stage_id'])
        self.assertEqual(set(origin['all_sibling_refs']), set(siblings))
        self.assertEqual(set(origin['unselected_sibling_refs']), set(unselected))
        self.assertEqual(len(origin['parent_definition_hash']), 64)
        self.assertEqual(node['workflow_path'], full_ref)

    def test_three_public_subworkflows_have_real_connected_children_and_callable_contracts(self):
        expected = {
            EXTRACTION: [('discover', 'source.discover'), ('extract', 'source.bind_operation')],
            SCALAR: [('extract', 'source.bind_operation'), ('lower', 'lower.scalar')],
            COOPERATIVE: [('extract', 'source.bind_operation'), ('lower', 'lower.cooperative')],
        }
        exported = self.registry.snapshot()
        self.assertEqual(exported['schema'], 'factory.workflow.library.v1')
        self.assertEqual(self.execution.snapshot['workflow_catalog'], exported)
        canonical = json.dumps(exported, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(self.execution.snapshot['workflow_catalog_sha256'], hashlib.sha256(canonical).hexdigest())
        refs = {record['path']: record for record in exported['stage_refs']}
        for parent, children in expected.items():
            with self.subTest(parent=parent):
                graph = self.registry.expand(parent)
                self.assertEqual([node.stage_id for node in graph.nodes], [stage_id for _, stage_id in children])
                self.assertEqual(len(graph.nodes), 2)
                self.assertEqual(len(graph.edges), 1)
                self.assertEqual(graph.edges[0]['from'], graph.nodes[0].id)
                self.assertEqual(graph.edges[0]['to'], graph.nodes[1].id)
                for alias, stage_id in children:
                    full_ref = parent+'/'+alias
                    self.assertEqual(refs[full_ref]['stage_id'], stage_id)
                    self.assertTrue(callable(self.execution.stages[stage_id].execute))
                    leaf = self.registry.expand(full_ref)
                    self.assertEqual(len(leaf.nodes), 1)
                    self.assertEqual(leaf.nodes[0].stage_id, stage_id)
                    self.assertEqual(leaf.inputs, self.execution.stages[stage_id].inputs)

    def test_whole_extraction_and_both_whole_lowering_parents_execute_real_source_artifacts(self):
        extracted = self.invoke(EXTRACTION, {'inventory': self.inventory}, self.scalar, 'extraction-parent')
        discovery = extracted['discovery']
        operator = extracted['operator']
        self.assertEqual(operator.read_json()['descriptor']['id'], self.scalar['id'])
        discovery_node = self.assert_actual_artifact(discovery)
        extraction_node = self.assert_actual_artifact(operator)
        self.assert_origin(discovery_node, EXTRACTION+'/discover', [EXTRACTION+'/extract'], [])
        self.assert_origin(extraction_node, EXTRACTION+'/extract', [EXTRACTION+'/discover'], [])
        for parent, descriptor, stage_id in ((SCALAR, self.scalar, 'lower.scalar'),
                                              (COOPERATIVE, self.cooperative, 'lower.cooperative')):
            with self.subTest(parent=parent):
                result = self.invoke(parent, {'discovery': discovery}, descriptor, stage_id.replace('.', '-'))
                core = result['core']
                node = self.assert_actual_artifact(core)
                self.assertEqual(node['stage_id'], stage_id)
                self.assertEqual(validate_core(core.read_json())['source_functions'], 1)
                consumed = node['attempts'][-1]['inputs']
                self.assertEqual(len(consumed), 1)
                self.assertEqual(consumed[0]['kind'], 'source.operator')
                producer = next(item for item in self.execution.snapshot['nodes'] if item['id'] == consumed[0]['producer'])
                self.assert_origin(producer, parent+'/extract', [parent+'/lower'], [])
                self.assert_origin(node, parent+'/lower', [parent+'/extract'], [])
                self.assertEqual(producer['parameters']['operation_id'], descriptor['id'])
                self.assertEqual(node['parameters']['operation_id'], descriptor['id'])
        process_commands = [command for node in self.execution.snapshot['nodes']
                            for attempt in node['attempts'] for command in attempt['commands']]
        self.assertTrue(process_commands)
        self.assertTrue(all(command['exit_code'] == 0 for command in process_commands))
        self.assertTrue(all(Path(command['stdout_path']).is_file() for command in process_commands))

    def test_selecting_leaf_uses_external_artifact_and_skips_exact_sibling_ref(self):
        complete = self.invoke(EXTRACTION, {'inventory': self.inventory}, self.scalar, 'upstream')
        discovery = complete['discovery']
        before = len(self.execution.snapshot['nodes'])
        extracted = self.invoke(EXTRACTION+'/extract', {'discovery': discovery}, self.scalar, 'only-extract')['operator']
        node = self.assert_actual_artifact(extracted)
        # A prior whole-parent selection may reuse the same exact extraction.
        self.assertLessEqual(len(self.execution.snapshot['nodes'])-before, 1)
        self.assertEqual(node['pool_origin']['full_ref'], EXTRACTION+'/extract')
        before = len(self.execution.snapshot['nodes'])
        core = self.invoke(SCALAR+'/lower', {'operator': extracted}, self.scalar, 'only-lower')['core']
        new = self.execution.snapshot['nodes'][before:]
        self.assertEqual([item['stage_id'] for item in new], ['lower.scalar'])
        lower = self.assert_actual_artifact(core)
        self.assert_origin(lower, SCALAR+'/lower', [SCALAR+'/extract'], [SCALAR+'/extract'])
        self.assertEqual(lower['attempts'][0]['inputs'][0]['id'], extracted.id)
        self.assertEqual(lower['attempts'][0]['inputs'][0]['sha256'], extracted.sha256)
        selected_refs = {item.get('pool_origin', {}).get('full_ref') for item in self.execution.snapshot['nodes']}
        self.assertIn(EXTRACTION+'/extract', selected_refs)
        self.assertNotIn(SCALAR+'/extract', selected_refs)
        self.assertEqual(validate_core(core.read_json())['source_functions'], 1)
        events = [json.loads(line) for line in self.execution.events_path.read_text().splitlines()]
        selection = [event['payload'] for event in events if event['type'] == 'workflow.expanded'][-1]
        self.assertEqual(selection['path'], SCALAR+'/lower')
        self.assertEqual(selection['workflow_catalog_sha256'], self.execution.snapshot['workflow_catalog_sha256'])
        self.assertEqual(len(selection['graph']['nodes']), 1)
        self.assertEqual(len(selection['pool_origins']), 1)
        self.assertEqual(selection['pool_origins'][0]['node_id'], lower['id'])
        self.assertEqual(selection['pool_origins'][0]['full_ref'], SCALAR+'/lower')
        self.assertEqual(selection['pool_origins'][0]['unselected_sibling_refs'], [SCALAR+'/extract'])

    def test_same_canonical_extractor_has_distinct_full_ref_identity_and_no_origin_overwrite(self):
        complete = self.invoke(EXTRACTION, {'inventory': self.inventory}, self.scalar, 'prepare')
        discovery = complete['discovery']
        first = self.invoke(EXTRACTION+'/extract', {'discovery': discovery}, self.scalar, 'first')['operator']
        first_node = self.assert_actual_artifact(first)
        first_origin = json.loads(json.dumps(first_node['pool_origin']))
        second = self.invoke(SCALAR+'/extract', {'discovery': discovery}, self.scalar, 'second')['operator']
        second_node = self.assert_actual_artifact(second)
        self.assertNotEqual(first.producer, second.producer)
        self.assertNotEqual(first.path, second.path)
        self.assertNotEqual(first_node['instance_key'], second_node['instance_key'])
        self.assertEqual(first_node['stage_id'], second_node['stage_id'])
        self.assertEqual(first_node['pool_origin'], first_origin)
        self.assertEqual(first_origin['full_ref'], EXTRACTION+'/extract')
        self.assert_origin(second_node, SCALAR+'/extract', [SCALAR+'/lower'], [SCALAR+'/lower'])
        count = len(self.execution.snapshot['nodes'])
        repeated = self.invoke(SCALAR+'/extract', {'discovery': discovery}, self.scalar, 'same-ref')['operator']
        self.assertEqual(repeated.id, second.id)
        self.assertEqual(len(self.execution.snapshot['nodes']), count)

    def test_selected_cooperative_lowering_reads_existing_operator_without_running_its_extractor(self):
        upstream = self.invoke(EXTRACTION, {'inventory': self.inventory}, self.cooperative, 'cooperative-upstream')
        operator = upstream['operator']
        before = len(self.execution.snapshot['nodes'])
        core = self.invoke(COOPERATIVE+'/lower', {'operator': operator}, self.cooperative, 'cooperative-only')['core']
        added = self.execution.snapshot['nodes'][before:]
        self.assertEqual([node['stage_id'] for node in added], ['lower.cooperative'])
        node = self.assert_actual_artifact(core)
        self.assert_origin(node, COOPERATIVE+'/lower', [COOPERATIVE+'/extract'], [COOPERATIVE+'/extract'])
        self.assertEqual(node['attempts'][0]['inputs'][0]['id'], operator.id)
        inventory = core.read_json()
        self.assertEqual(validate_core(inventory)['source_functions'], 1)
        kernel = next(iter(inventory['kernels'].values()))
        self.assertEqual(kernel['id'], self.cooperative['id'])
        self.assertTrue(kernel['features']['shuffle'])
        self.assertIn('co_await', kernel['semantic_ir']['lowered_cpp'])


if __name__ == '__main__':
    unittest.main()
