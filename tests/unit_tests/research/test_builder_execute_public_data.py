"""Actual Builder execute parses public inputs before invoking its runtime.

Offline regression only. Native pin and agent runtime are replaced; no model,
build job, network request, or protected execution is launched.
"""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jiuwenswarm.research.capsules import builder_agent
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.metric_contract import metric_protocol


class RuntimeReached(Exception):
    pass


class BuilderExecutePublicDataTests(unittest.IsolatedAsyncioTestCase):
    def inputs(self):
        return {
            'validation_resource': {'files': [{'path': 'data.json', 'artifact_ref': {'id': 'public'}}]},
            'baseline_resource': {'files': [{'path': 'baseline.py', 'artifact_ref': {'id': 'baseline'}}]},
            'blueprint': {'id': 'test-blueprint', 'metrics': metric_protocol()['metrics']},
            'lock': {'platform': 'test-platform'},
        }

    def context(self, raw):
        def read_blob(ref):
            return raw if ref['id'] == 'public' else b'print("baseline fixture")\n'
        async def forbidden(*args, **kwargs):
            raise AssertionError('No model or Builder action is allowed in this regression')
        return SimpleNamespace(store=SimpleNamespace(read_blob=read_blob),
                               executor=SimpleNamespace(builder_action=forbidden),
                               contract={'attempt_id': 'offline-test'}, model=forbidden)

    async def test_classification_reaches_runtime_with_valid_public_contract(self):
        public = {'schema': 'ai4r-classification-data:1', 'dataset_id': 'offline-public',
                  'feature_names': ['f'], 'classes': ['a', 'b'],
                  'train': [{'id': 'r1', 'features': [0.0], 'label': 'a'},
                            {'id': 'r2', 'features': [1.0], 'label': 'b'}],
                  'test': [{'id': 't1', 'features': [0.5]}]}
        captured = {}
        async def runtime(**kwargs):
            captured.update(kwargs)
            raise RuntimeReached()
        with patch('jiuwenswarm.research.native.verify_native_pin'), \
             patch('jiuwenswarm.research.builder_agent_runtime.run_builder_agent', new=runtime):
            with self.assertRaises(RuntimeReached):
                await builder_agent.execute(self.context(json.dumps(public).encode()), self.inputs())
        self.assertEqual(captured['task']['public_validation'], public)
        self.assertEqual(captured['task']['contract']['interface'], 'predict(train, test)')
        self.assertEqual(captured['task']['contract']['classes'], ['a', 'b'])
        self.assertIn('baseline.py', captured['task']['baseline_source'])
        self.assertEqual(captured['max_model_calls'], 20)

    async def test_invalid_json_is_a_controlled_public_data_failure(self):
        with self.assertRaises(ResearchError) as caught:
            await builder_agent.execute(self.context(b'not valid JSON'), self.inputs())
        self.assertEqual(caught.exception.code, 'builder_public_data')

    async def test_wrong_dataset_schema_is_rejected_before_runtime(self):
        with self.assertRaises(ResearchError) as caught:
            await builder_agent.execute(self.context(b'{"schema":"wrong"}'), self.inputs())
        self.assertEqual(caught.exception.code, 'builder_public_data')


if __name__ == '__main__':
    unittest.main()
