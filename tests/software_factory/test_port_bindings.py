"""Same-kind output ports retain their identities through real execution.

These arithmetic child programs exercise engine artifact delivery in isolation.
They are not substitutes for STRATA inference, model, or device validation.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

from jiuwenswarm.software_factory.contracts import Stage, StageFailure, json_object
from jiuwenswarm.software_factory.engine import Execution
from jiuwenswarm.software_factory.workflow_definitions import (
    Binding, StageRef, SubworkflowDefinition, SubworkflowRef,
    WorkflowDefinition, WorkflowRegistry,
)


_VALIDATOR_CALLS = []


def validate_left(path):
    value = json_object(path, {'value': int})
    _VALIDATOR_CALLS.append(('left', value['value']))
    if value['value'] != 3:
        raise StageFailure('contract_invalid', 'The left output must contain three')
    return {'validated_output': 'left'}


def validate_right(path):
    value = json_object(path, {'value': int})
    _VALIDATOR_CALLS.append(('right', value['value']))
    if value['value'] != 7:
        raise StageFailure('contract_invalid', 'The right output must contain seven')
    return {'validated_output': 'right'}


def validate_product(path):
    value = json_object(path, {'value': int, 'input_value': int, 'input_path': str})
    if value['value'] != value['input_value'] * 7:
        raise StageFailure('contract_invalid', 'The output must be seven times its actual input')
    return {'consumed_path': value['input_path']}


def produce_two_numbers(ctx, inputs):
    left, right = ctx.workspace / 'left.json', ctx.workspace / 'right.json'
    ctx.run_command([
        sys.executable, '-c',
        'import json,sys;'
        'json.dump({"value":3},open(sys.argv[1],"w"));'
        'json.dump({"value":7},open(sys.argv[2],"w"));'
        'print("wrote distinct left and right files")',
        str(left), str(right),
    ])
    return {'left': left, 'right': right}


def multiply_actual_input(ctx, inputs):
    result = ctx.workspace / 'product.json'
    ctx.run_command([
        sys.executable, '-c',
        'import json,sys;'
        'value=json.load(open(sys.argv[1]))["value"];'
        'json.dump({"value":value*7,"input_value":value,"input_path":sys.argv[1]},'
        'open(sys.argv[2],"w"));'
        'print("consumed",sys.argv[1],"value",value)',
        inputs['number'].path, str(result),
    ])
    return {'result': result}


def stages():
    return [
        Stage('dual-seed', 'Write distinct numbers', 'source', 'prepare', {},
              {'left': 'number.same', 'right': 'number.same'}, produce_two_numbers,
              validators={'left': validate_left, 'right': validate_right}),
        Stage('times-seven', 'Read and multiply', 'analysis', 'compute',
              {'number': 'number.same'}, {'result': 'number.result'}, multiply_actual_input,
              validators={'result': validate_product}),
    ]


def registry(catalog):
    producer = SubworkflowDefinition('dual-producer', 'Two ports of the same kind', {}, (
        StageRef('write', 'dual-seed'),
    ), {'left': Binding('write', 'left'), 'right': Binding('write', 'right')})
    consumer = SubworkflowDefinition('one-consumer', 'Consume one explicit port',
        {'number': 'number.same'}, (
            StageRef('multiply', 'times-seven', {'number': Binding('$input', 'number')}),
        ), {'result': Binding('multiply', 'result')})
    parent = WorkflowDefinition('dual-parent', 'Execute both explicit output ports', {}, (
        SubworkflowRef('source', 'dual-producer'),
        SubworkflowRef('left-consumer', 'one-consumer',
                       {'number': Binding('source', 'left')}),
        SubworkflowRef('right-consumer', 'one-consumer',
                       {'number': Binding('source', 'right')}),
    ), {
        'source-left': Binding('source', 'left'),
        'source-right': Binding('source', 'right'),
        'left-product': Binding('left-consumer', 'result'),
        'right-product': Binding('right-consumer', 'result'),
    })
    return WorkflowRegistry(catalog, [producer, consumer], [parent])


class PortBindingsTests(unittest.TestCase):
    def setUp(self):
        _VALIDATOR_CALLS.clear()
        self.temporary = tempfile.TemporaryDirectory(prefix='factory-port-bindings-')
        self.addCleanup(self.temporary.cleanup)
        self.catalog = stages()
        self.execution = Execution(Path(self.temporary.name) / 'run',
                                   {'goals': [], 'target_backend': 'cpu'}, self.catalog)

    def assert_product(self, artifact, expected, source):
        payload = artifact.read_json()
        self.assertEqual(payload['value'], expected)
        self.assertEqual(payload['input_value'], source.read_json()['value'])
        self.assertEqual(Path(payload['input_path']), Path(source.path))
        self.assertEqual(artifact.metadata['consumed_path'], source.path)

    def assert_actual_commands(self, expected_count):
        commands = [command for node in self.execution.snapshot['nodes']
                    for attempt in node['attempts'] for command in attempt['commands']]
        self.assertEqual(len(commands), expected_count)
        for command in commands:
            self.assertEqual(command['exit_code'], 0)
            self.assertTrue(Path(command['stdout_path']).is_file())
            self.assertTrue(command['recipe']['executable']['sha256'])
        self.assertTrue(all(node['status'] == 'verified'
                            for node in self.execution.snapshot['nodes']))

    def test_direct_invocation_distinguishes_same_kind_ports_and_reuses_each_binding(self):
        produced = self.execution.invoke_stage('dual-seed', {})
        left, right = produced['left'], produced['right']
        self.assertEqual((left.read_json()['value'], right.read_json()['value']), (3, 7))
        self.assertEqual(left.kind, right.kind)
        self.assertEqual(left.producer, right.producer)
        self.assertNotEqual(left.id, right.id)
        self.assertNotEqual(left.path, right.path)
        self.assertEqual(left.metadata['output_port'], 'left')
        self.assertEqual(right.metadata['output_port'], 'right')
        self.assertEqual(left.metadata['validated_output'], 'left')
        self.assertEqual(right.metadata['validated_output'], 'right')

        left_result = self.execution.invoke_stage('times-seven', {'number': left})['result']
        right_result = self.execution.invoke_stage('times-seven', {'number': right})['result']
        self.assert_product(left_result, 21, left)
        self.assert_product(right_result, 49, right)
        self.assertNotEqual(left_result.producer, right_result.producer)
        self.assertNotEqual(left_result.path, right_result.path)
        self.assertEqual(_VALIDATOR_CALLS,
                         [('left', 3), ('right', 7), ('left', 3), ('right', 7)])
        consumers = [node for node in self.execution.snapshot['nodes']
                     if node['stage_id'] == 'times-seven']
        self.assertNotEqual(consumers[0]['instance_key'], consumers[1]['instance_key'])
        self.assertEqual([node['input_bindings']['number']['port'] for node in consumers],
                         ['left', 'right'])
        self.assertEqual([node['attempts'][0]['inputs'][0]['id'] for node in consumers],
                         [left.id, right.id])

        # Reuse each exact input identity, in the opposite order to its first call.
        reused_right = self.execution.invoke_stage('times-seven', {'number': right})['result']
        reused_left = self.execution.invoke_stage('times-seven', {'number': left})['result']
        self.assertEqual((reused_left.id, reused_right.id), (left_result.id, right_result.id))
        self.assertEqual(len(self.execution.snapshot['nodes']), 3)
        self.assertTrue(all(len(node['attempts']) == 1 for node in self.execution.snapshot['nodes']))
        events = [json.loads(line) for line in self.execution.events_path.read_text().splitlines()]
        self.assertEqual([event['payload']['input_artifact_ids'] for event in events
                          if event['type'] == 'stage.reused'], [[right.id], [left.id]])
        self.assert_actual_commands(3)

    def test_parent_import_preserves_same_kind_source_ports_and_exposed_outputs(self):
        custom = registry(self.catalog)
        expanded = custom.expand('dual-parent')
        selected_ports = [node.input_bindings['number'].port for node in expanded.nodes
                          if node.stage_id == 'times-seven']
        self.assertEqual(selected_ports, ['left', 'right'])
        self.assertEqual(expanded.outputs['source-left'].kind,
                         expanded.outputs['source-right'].kind)
        self.assertEqual(expanded.outputs['source-left'].port, 'left')
        self.assertEqual(expanded.outputs['source-right'].port, 'right')

        outputs = self.execution.import_workflow('dual-parent', registry=custom)
        self.assertEqual(set(outputs),
                         {'source-left', 'source-right', 'left-product', 'right-product'})
        left, right = outputs['source-left'], outputs['source-right']
        self.assertNotEqual(left.id, right.id)
        self.assertEqual(left.producer, right.producer)
        self.assertEqual((left.metadata['output_port'], right.metadata['output_port']),
                         ('left', 'right'))
        self.assert_product(outputs['left-product'], 21, left)
        self.assert_product(outputs['right-product'], 49, right)
        self.assertEqual(_VALIDATOR_CALLS,
                         [('left', 3), ('right', 7), ('left', 3), ('right', 7)])
        consumers = [node for node in self.execution.snapshot['nodes']
                     if node['stage_id'] == 'times-seven']
        self.assertEqual([node['input_bindings']['number']['port'] for node in consumers],
                         ['left', 'right'])
        self.assertEqual([node['attempts'][0]['inputs'][0]['id'] for node in consumers],
                         [left.id, right.id])

        reused = self.execution.import_workflow('dual-parent', registry=custom)
        self.assertEqual({name: item.id for name, item in reused.items()},
                         {name: item.id for name, item in outputs.items()})
        self.assertEqual(len(self.execution.snapshot['nodes']), 3)
        self.assert_actual_commands(3)

    def test_extracted_stage_accepts_explicit_right_port_from_another_parent(self):
        custom = registry(self.catalog)
        produced = self.execution.import_workflow('dual-parent/source/write', registry=custom)
        right = produced['right']
        output = self.execution.import_workflow(
            'dual-parent/right-consumer/multiply', external_inputs={'number': right},
            registry=custom,
        )['result']
        self.assert_product(output, 49, right)
        consumer = self.execution.snapshot['nodes'][-1]
        self.assertEqual(consumer['input_bindings']['number']['port'], 'right')
        self.assertEqual(consumer['attempts'][0]['inputs'][0]['id'], right.id)
        self.assertEqual(_VALIDATOR_CALLS, [('left', 3), ('right', 7), ('right', 7)])
        self.assert_actual_commands(2)


if __name__ == '__main__':
    unittest.main()
