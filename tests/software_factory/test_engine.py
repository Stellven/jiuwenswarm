"""Isolated mechanical tests; these do not certify STRATA or native hardware."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from jiuwenswarm.software_factory.contracts import Stage, StageBlocked, StageFailure, json_object
from jiuwenswarm.software_factory.engine import FactoryService


def verify_object(path):
    return json_object(path, {'value': int})


def seed(ctx, inputs):
    path = ctx.workspace / 'seed.json'
    ctx.run_command([sys.executable, '-c', 'import json,sys;json.dump({"value":7},open(sys.argv[1],"w"));print("produced 7",flush=True)', str(path)])
    return {'seed': path}


def transform(ctx, inputs):
    path = ctx.workspace / 'result.json'
    ctx.run_command([sys.executable, '-c', 'import json,sys;x=json.load(open(sys.argv[1]));json.dump({"value":x["value"]*3},open(sys.argv[2],"w"));print("consumed source",flush=True)', inputs['seed'].path, str(path)])
    return {'result': path}


def raw_inventory(ctx, inputs):
    return {'inventory': ctx.write_json('inventory.json', {'cuda_ops': ['actual_test_name']})}


def mapped_consumer(ctx, inputs):
    value = inputs['inventory'].read_json()
    if 'ascend_ops' not in value:
        raise StageFailure('schema_mismatch', 'Expected ascend_ops; received cuda_ops')
    # This test validates representation adaptation, not kernel migration.
    return {'result': ctx.write_json('mapped-result.json', {'value': len(value['ascend_ops'])})}


def representation_adapter(ctx, inputs):
    target = ctx.workspace / 'adapted.json'
    ctx.run_command([sys.executable, '-c', 'import json,sys;x=json.load(open(sys.argv[1]));json.dump({"ascend_ops":x["cuda_ops"]},open(sys.argv[2],"w"));print("adapted actual file",flush=True)', inputs['inventory'].path, str(target)])
    return {'inventory': target}


def blocked(ctx, inputs):
    raise StageBlocked('device_absent', 'Test has no device')


def failing(ctx, inputs):
    ctx.run_command([sys.executable, '-c', 'import sys;print("real failure",file=sys.stderr);sys.exit(9)'])


def invalid_outputs(ctx, inputs):
    return {'first': ctx.write_json('first.json', {'value': 1}), 'second': ctx.write_json('second.json', {'value': 'wrong'})}


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def service(self, stages):
        return FactoryService(self.root, stages)

    @staticmethod
    def request(goals):
        return {'goals': goals, 'target_backend': 'cpu', 'owner_id': 'test-owner'}

    @staticmethod
    def stages():
        return [Stage('seed', 'Seed', 'acquisition', 'file_source', {}, {'seed': 'seed'}, seed, validators={'seed': verify_object}),
                Stage('transform', 'Transform', 'engineering', 'actual_compute', {'seed': 'seed'}, {'result': 'result'}, transform, validators={'result': verify_object})]

    def test_contract_search_uses_distinct_paths_and_consumes_upstream_bytes(self):
        service = self.service(self.stages())
        short = service.create(self.request(['seed']), background=False)
        long = service.create(self.request(['result']), background=False)
        self.assertEqual([n['stage_id'] for n in short['nodes']], ['seed'])
        self.assertEqual([n['stage_id'] for n in long['nodes']], ['seed', 'transform'])
        self.assertEqual(long['status'], 'completed')
        result = next(a for a in long['artifacts'] if a['kind'] == 'result')
        self.assertEqual(json.loads(Path(result['path']).read_text())['value'], 21)
        self.assertEqual(long['nodes'][1]['attempts'][0]['inputs'][0]['producer'], long['nodes'][0]['id'])
        self.assertEqual({n['workflow_id'] for n in long['nodes']}, {'engineering', 'acquisition'})
        self.assertTrue(any(e['type'] == 'command.output' for e in service.events(long['id'])['events']))

    def test_real_content_mismatch_selects_executable_adapter_and_rebinds_consumer(self):
        stages = [Stage('raw', 'Raw', 'source', 'extract', {}, {'inventory': 'inventory'}, raw_inventory),
                  Stage('consumer', 'Consumer', 'implementation', 'map', {'inventory': 'inventory'}, {'result': 'result'}, mapped_consumer, validators={'result': verify_object}),
                  Stage('adapter', 'Adapter', 'adaptation', 'convert', {'inventory': 'inventory'}, {'inventory': 'inventory'}, representation_adapter, repairs=('schema_mismatch',))]
        service = self.service(stages)
        run = service.create(self.request(['result']), background=False)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(len(run['graph_revisions']), 3)
        consumer = next(n for n in run['nodes'] if n['stage_id'] == 'consumer')
        raw = next(n for n in run['nodes'] if n['stage_id'] == 'raw')
        adapter = next(n for n in run['nodes'] if n['stage_id'] == 'adapter')
        self.assertEqual([a['status'] for a in consumer['attempts']], ['failed', 'verified'])
        self.assertEqual(consumer['attempts'][1]['inputs'][0]['producer'], adapter['id'])
        self.assertIn({'from': raw['id'], 'to': adapter['id'], 'data': 'inventory'}, run['edges'])
        self.assertNotIn({'from': raw['id'], 'to': consumer['id'], 'data': 'inventory'}, run['edges'])
        failed_graph = run['graph_revisions'][1]
        self.assertIn({'from': raw['id'], 'to': consumer['id'], 'data': 'inventory'}, failed_graph['edges'])
        self.assertEqual(next(n for n in failed_graph['nodes'] if n['id'] == consumer['id'])['status'], 'failed')
        events = service.events(run['id'])['events']
        self.assertTrue(any(e['type'] == 'schema.mismatch' for e in events))
        self.assertTrue(any(e['type'] == 'adapter.injected' for e in events))
        self.assertEqual([e['sequence'] for e in events], list(range(1, len(events)+1)))

    def test_blocked_goal_does_not_stop_independent_work_or_retry_blocked_stage(self):
        service = self.service([Stage('blocked', 'Blocked', 'native', 'device', {}, {'a': 'a', 'b': 'b'}, blocked), *self.stages()])
        run = service.create(self.request(['a', 'result', 'b']), background=False)
        self.assertEqual(run['status'], 'blocked')
        self.assertEqual(run['goal_results']['result']['status'], 'verified')
        self.assertEqual(len(next(n for n in run['nodes'] if n['stage_id'] == 'blocked')['attempts']), 1)

    def test_unexecuted_dependents_are_blocked_without_invented_attempts(self):
        def never_execute(ctx, inputs):
            raise AssertionError('Dependent stage must not execute')
        service = self.service([
            Stage('blocked', 'Blocked', 'native', 'device', {}, {'a': 'a'}, blocked),
            Stage('dependent', 'Dependent', 'model', 'inference', {'a': 'a'}, {'result': 'result'}, never_execute),
            Stage('compare', 'Compare', 'verification', 'comparison', {'result': 'result'}, {'comparison': 'comparison'}, never_execute),
        ])
        run = service.create(self.request(['result', 'comparison']), background=False)
        self.assertEqual(run['status'], 'blocked')
        for node in run['nodes']:
            if node['stage_id'] != 'blocked':
                self.assertEqual(node['status'], 'blocked')
                self.assertEqual(node['attempts'], [])
                self.assertEqual(node['dependency_error']['code'], 'device_absent')
                self.assertTrue(node['blocked_by'])
        self.assertEqual(len(run['nodes'][0]['attempts']), 1)

    def test_unknown_goal_does_not_discard_feasible_goal(self):
        service = self.service(self.stages())
        run = service.create(self.request(['unknown', 'result']), background=False)
        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['goal_results']['result']['status'], 'verified')

    def test_assessment_observes_settled_work_even_when_requested_first(self):
        def assess(ctx, inputs):
            settled = dict(ctx.execution.snapshot['goal_results'])
            return {'assessment': ctx.write_json('assessment.json', settled)}
        service = self.service([
            *self.stages(),
            Stage('blocked', 'Blocked', 'native', 'device', {}, {'native': 'native'}, blocked),
            Stage('assessment', 'Assess work outcomes', 'assessment', 'value', {},
                  {'assessment': 'assessment'}, assess, defer_until_goals_settle=True),
        ])
        run = service.create(self.request(['assessment', 'native', 'result']), background=False)
        self.assertEqual(run['status'], 'blocked')
        artifact = next(a for a in run['artifacts'] if a['kind'] == 'assessment')
        settled = json.loads(Path(artifact['path']).read_text())
        self.assertEqual(settled['native']['status'], 'blocked')
        self.assertEqual(settled['result']['status'], 'verified')
        self.assertEqual(run['goal_results']['assessment']['status'], 'verified')

    def test_command_failure_is_not_success_and_logs_are_actual_artifacts(self):
        service = self.service([Stage('bad', 'Bad', 'test', 'process', {}, {'x': 'x'}, failing)])
        run = service.create(self.request(['x']), background=False)
        self.assertEqual(run['status'], 'failed')
        command = run['nodes'][0]['attempts'][0]['commands'][0]
        self.assertEqual(command['exit_code'], 9)
        self.assertIn('real failure', Path(command['stderr_path']).read_text())
        artifact = next(a for a in run['artifacts'] if a['kind'] == 'process.stderr')
        self.assertEqual(service.artifact_path(run['id'], artifact['id']).read_text().strip(), 'real failure')

    def test_invalid_second_output_does_not_publish_first_output(self):
        service = self.service([Stage('invalid', 'Invalid', 'test', 'contracts', {}, {'first': 'first', 'second': 'second'}, invalid_outputs,
                                      validators={'first': verify_object, 'second': verify_object})])
        run = service.create(self.request(['first']), background=False)
        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['artifacts'], [])

    def test_artifact_tampering_and_path_escape_are_rejected(self):
        service = self.service(self.stages())
        run = service.create(self.request(['seed']), background=False)
        artifact = next(a for a in run['artifacts'] if a['kind'] == 'seed')
        Path(artifact['path']).write_text('{"value": 999}')
        with self.assertRaises(StageFailure):
            service.artifact_path(run['id'], artifact['id'])
        with self.assertRaises(FileNotFoundError):
            service.get('../escape')


if __name__ == '__main__':
    unittest.main()
