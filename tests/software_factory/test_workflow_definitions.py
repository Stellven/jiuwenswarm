"""Hierarchical composition tests executing real isolated file/process stages.

The arithmetic programs here are isolated mechanical tests, not STRATA/model or
hardware substitutes. No process, file, input artifact, or exit status is mocked.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

from jiuwenswarm.software_factory.contracts import Stage, StageFailure, json_object
from jiuwenswarm.software_factory.engine import Execution
from jiuwenswarm.software_factory.workflow_definitions import (
    Binding, PortReference, StageRef, SubworkflowDefinition, SubworkflowRef,
    WorkflowDefinition, WorkflowRegistry,
)


def check_number(path):
    return json_object(path, {'value': int})


def produce(ctx, inputs):
    path = ctx.workspace / 'number.json'
    number = 11 if ctx.node['stage_id'] == 'seed11' else 7
    ctx.run_command([sys.executable, '-c', 'import json,sys;json.dump({"value":int(sys.argv[1])},open(sys.argv[2],"w"));print("wrote",sys.argv[1])', str(number), str(path)])
    return {'number': path}


def multiply(ctx, inputs):
    path = ctx.workspace / 'result.json'
    ctx.run_command([sys.executable, '-c', 'import json,sys;x=json.load(open(sys.argv[1]));json.dump({"value":x["value"]*int(sys.argv[3])},open(sys.argv[2],"w"));print("read upstream",x["value"])', inputs['number'].path, str(path), '2' if ctx.node['stage_id'] == 'double' else '3'])
    return {'result': path}


def finalize(ctx, inputs):
    path = ctx.workspace / 'final.json'
    ctx.run_command([sys.executable, '-c', 'import json,sys;x=json.load(open(sys.argv[1]));json.dump({"value":x["value"]+1},open(sys.argv[2],"w"));print("finalized")', inputs['result'].path, str(path)])
    return {'final': path}


def stage_catalog():
    return [
        Stage('seed7', 'Write seven', 'source', 'prepare', {}, {'number': 'number.seed'}, produce, validators={'number': check_number}),
        Stage('seed11', 'Write eleven', 'source', 'prepare', {}, {'number': 'number.seed'}, produce, validators={'number': check_number}),
        Stage('double', 'Double', 'source', 'prepare', {'number': 'number.seed'}, {'result': 'number.prepared'}, multiply, validators={'result': check_number}),
        Stage('triple', 'Triple', 'analysis', 'measure', {'number': 'number.seed'}, {'result': 'number.result'}, multiply, validators={'result': check_number}),
        Stage('finalize', 'Finalize', 'analysis', 'measure', {'result': 'number.result'}, {'final': 'number.final'}, finalize, validators={'final': check_number}),
    ]


def definitions():
    preparation = SubworkflowDefinition('preparation', 'Prepare numbers', {}, (
        StageRef('write', 'seed7'),
        StageRef('double', 'double', {'number': Binding('write', 'number')}),
    ), {'number': Binding('write', 'number'), 'prepared': Binding('double', 'result')})
    measurement = SubworkflowDefinition('measurement', 'Measure numbers', {'number': 'number.seed'}, (
        StageRef('triple', 'triple', {'number': Binding('$input', 'number')}),
        StageRef('finalize', 'finalize', {'result': Binding('triple', 'result')}),
    ), {'result': Binding('triple', 'result'), 'final': Binding('finalize', 'final')})
    source = WorkflowDefinition('source', 'Source workflow', {}, (SubworkflowRef('prepare', 'preparation'),),
                                {'number': Binding('prepare', 'number'), 'prepared': Binding('prepare', 'prepared')})
    analysis = WorkflowDefinition('analysis', 'Analysis workflow', {'number': 'number.seed'},
        (SubworkflowRef('measure', 'measurement', {'number': Binding('$input', 'number')}),),
        {'result': Binding('measure', 'result'), 'final': Binding('measure', 'final')})
    return [preparation, measurement], [source, analysis]


class WorkflowDefinitionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hierarchical-factory-')
        self.directory = Path(self.temporary.name)
        self.stages = stage_catalog()
        self.registry = WorkflowRegistry(self.stages, *definitions())

    def tearDown(self):
        self.temporary.cleanup()

    def execute_graphs(self, *graphs):
        execution = Execution(self.directory / 'run', {'goals': [], 'target_backend': 'cpu'}, self.stages)
        for graph in graphs:
            self.assertEqual(graph.inputs, {}, 'Test graph must bind all actual inputs')
            for instance in graph.nodes:
                stage = execution.stages[instance.stage_id]
                execution.snapshot['nodes'].append({**instance.serializable(), 'name': stage.name,
                    'workflow_id': stage.workflow_id, 'subworkflow_id': stage.subworkflow_id,
                    'status': 'pending', 'attempts': []})
            execution.snapshot['edges'].extend(graph.edges)
        for node in execution.snapshot['nodes']:
            execution.execute_node(node)
        return execution

    @staticmethod
    def value(execution, reference):
        artifacts = [a for a in execution.artifacts.values() if a.producer == reference.node_id and a.kind == reference.kind]
        if len(artifacts) != 1:
            raise AssertionError('Missing unique real output artifact')
        return artifacts[0].read_json()['value']

    def test_parent_expansion_executes_real_child_processes_and_ports(self):
        graph = self.registry.expand('source', instance_id='first')
        self.assertEqual([n.stage_id for n in graph.nodes], ['seed7', 'double'])
        self.assertEqual(graph.nodes[1].input_bindings['number'], graph.outputs['number'])
        execution = self.execute_graphs(graph)
        self.assertEqual(self.value(execution, graph.outputs['prepared']), 14)
        commands = [a['commands'][0] for n in execution.snapshot['nodes'] for a in n['attempts']]
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(record['exit_code'] == 0 for record in commands))
        self.assertIn('read upstream 7', Path(commands[1]['stdout_path']).read_text())
        self.assertTrue(all(node['status'] == 'verified' for node in execution.snapshot['nodes']))

    def test_extracts_internal_phases_across_parents_without_replaying_siblings(self):
        source = self.registry.expand('source/prepare/write', instance_id='selected-source')
        analysis = self.registry.expand('analysis/measure/triple', instance_id='selected-analysis')
        self.assertEqual(analysis.inputs, {'number': 'number.seed'})
        analysis = analysis.bind_inputs({'number': source.outputs['number']})
        execution = self.execute_graphs(source, analysis)
        self.assertEqual([n['stage_id'] for n in execution.snapshot['nodes']], ['seed7', 'triple'])
        self.assertEqual(self.value(execution, analysis.outputs['result']), 21)
        triple = execution.snapshot['nodes'][1]
        self.assertEqual(triple['attempts'][0]['inputs'][0]['producer'], source.nodes[0].id)
        self.assertIn('read upstream 7', Path(triple['attempts'][0]['commands'][0]['stdout_path']).read_text())

    def test_same_stage_runs_twice_with_distinct_bound_real_inputs(self):
        leaf7 = SubworkflowDefinition('seven', 'Seven', {}, (StageRef('write', 'seed7'),), {'number': Binding('write', 'number')})
        leaf11 = SubworkflowDefinition('eleven', 'Eleven', {}, (StageRef('write', 'seed11'),), {'number': Binding('write', 'number')})
        triple = SubworkflowDefinition('triple', 'Triple', {'number': 'number.seed'},
            (StageRef('calculate', 'triple', {'number': Binding('$input', 'number')}),), {'result': Binding('calculate', 'result')})
        dual = WorkflowDefinition('dual', 'Two bound calculations', {}, (
            SubworkflowRef('seven', 'seven'), SubworkflowRef('eleven', 'eleven'),
            SubworkflowRef('first', 'triple', {'number': Binding('seven', 'number')}),
            SubworkflowRef('second', 'triple', {'number': Binding('eleven', 'number')}),
        ), {'first': Binding('first', 'result'), 'second': Binding('second', 'result')})
        registry = WorkflowRegistry(self.stages, [leaf7, leaf11, triple], [dual])
        graph = registry.expand('dual')
        self.assertEqual(len({n.id for n in graph.nodes}), 4)
        self.assertEqual([n.stage_id for n in graph.nodes].count('triple'), 2)
        execution = self.execute_graphs(graph)
        self.assertEqual(self.value(execution, graph.outputs['first']), 21)
        self.assertEqual(self.value(execution, graph.outputs['second']), 33)
        self.assertEqual(sum(len(n['attempts']) for n in execution.snapshot['nodes']), 4)

    def test_nested_selection_and_ids_are_stable_and_instances_separate(self):
        one = self.registry.expand('analysis/measure', 'one')
        again = self.registry.expand('analysis/measure', 'one')
        two = self.registry.expand('analysis/measure', 'two')
        self.assertEqual(one.serializable(), again.serializable())
        self.assertTrue(set(n.id for n in one.nodes).isdisjoint(n.id for n in two.nodes))
        self.assertEqual([n.stage_id for n in one.nodes], ['triple', 'finalize'])

    def test_invalid_binding_unknown_entrypoint_and_cycles_are_rejected(self):
        invalid = [
            StageRef('bad', 'does-not-exist'),
            StageRef('bad', 'triple', {'number': Binding('later', 'number')}),
            StageRef('bad', 'triple', {'number': Binding('$input', 'number')}),
        ]
        for step in invalid:
            with self.subTest(step=step):
                bad = SubworkflowDefinition('bad', 'Invalid', {'number': 'incompatible.kind'}, (step,), {'out': Binding('bad', 'result')})
                with self.assertRaises(StageFailure):
                    WorkflowRegistry(self.stages, [bad], [])
        with self.assertRaises(StageFailure):
            self.registry.expand('../source')
        with self.assertRaises(StageFailure):
            self.registry.expand('source', '../escape')

    def test_binding_incompatible_actual_output_cannot_be_schema_renamed(self):
        source = self.registry.expand('source')
        analysis = self.registry.expand('analysis/measure/triple')
        with self.assertRaises(StageFailure):
            analysis.bind_inputs({'number': source.outputs['prepared']})
        with self.assertRaises(StageFailure):
            analysis.bind_inputs({'unknown': PortReference(None, 'unknown', 'number.seed')})
        with self.assertRaises(StageFailure):
            analysis.bind_inputs({'number': PortReference(None, 'unresolved', 'number.seed')})

    def test_empty_parents_and_noncallable_catalog_are_rejected(self):
        with self.assertRaises(StageFailure):
            WorkflowRegistry(self.stages, [SubworkflowDefinition('empty', 'Empty', {}, (), {})], [])
        with self.assertRaises(StageFailure):
            WorkflowRegistry(self.stages, [], [WorkflowDefinition('empty', 'Empty', {}, (), {})])
        with self.assertRaises(StageFailure):
            WorkflowRegistry([Stage('bad', 'Bad', 'x', 'y', {}, {'x': 'x'}, None)], [], [])

    def test_default_parents_resolve_only_actual_catalog_entrypoints(self):
        from jiuwenswarm.software_factory.catalog import stage_catalog as real_catalog
        stages = real_catalog()
        registry = WorkflowRegistry(stages)
        graph = registry.expand('construction')
        self.assertEqual([n.stage_id for n in graph.nodes],
                         ['construction.ascend_mapper', 'construction.codegen', 'construction.build'])
        self.assertEqual(graph.inputs, {'inventory': 'operator.native_inventory'})
        stage = registry.expand('verification/core_validation/execute')
        self.assertEqual([n.stage_id for n in stage.nodes], ['construction.execute'])
        self.assertEqual(stage.inputs, {'build': 'construction.build', 'requirements': 'task.requirements'})
        source = registry.expand('source_acquisition')
        self.assertEqual([n.stage_id for n in source.nodes], ['source.fetch', 'source.cuda_ast', 'source.discover'])
        actual = {s.id: s for s in stages}
        exported = registry.export()
        self.assertTrue(exported['workflows'])
        for record in exported['stage_refs']:
            self.assertIn(record['stage_id'], actual)
            self.assertEqual(record['entrypoint'], actual[record['stage_id']].serializable()['entrypoint'])
        json.dumps(exported)


if __name__ == '__main__':
    unittest.main()
