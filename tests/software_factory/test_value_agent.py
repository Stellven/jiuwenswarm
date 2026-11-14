"""Isolated Value Agent contracts, never a STRATA/model inference certificate."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from jiuwenswarm.software_factory.contracts import Artifact, Stage, StageBlocked, StageFailure
from jiuwenswarm.software_factory.engine import FactoryService
from jiuwenswarm.software_factory.value_agent import (
    GATEWAY_SEAM, _validated_model_analysis, collect_evidence,
    configured_model_assessment, render_report, value_stages,
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def construct(ctx, inputs):
    directory = ctx.workspace / 'source'
    directory.mkdir()
    cpp = directory / 'strata_core.cpp'
    ctx.run_command([sys.executable, '-c', 'import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("int project(){return 7;}\\n");print("wrote actual source")', str(cpp)])
    return {'source': ctx.write_json('source.json', {'schema': 'strata.constructed.source.v1',
        'source_dir': str(directory), 'commit_sha': 'a' * 40, 'files': {'strata_core.cpp': digest(cpp)},
        'algorithms': ['test_projection'], 'scope': 'Isolated Value Agent test project'})}


def validate(ctx, inputs):
    source = inputs['source'].read_json()
    ctx.run_command([sys.executable, '-c', 'import pathlib,sys;assert "return 7" in pathlib.Path(sys.argv[1]).read_text();print("checked actual source")', str(Path(source['source_dir'])/'strata_core.cpp')])
    return {'execution': ctx.write_json('execution.json', {'scope': 'Test source validation only',
        'full_inference_validated': False, 'numerical_result': {'outputs_compared': 0}})}


def package(ctx, inputs):
    source = inputs['source'].read_json()
    archive = ctx.workspace / 'huawei_native_strata.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        for name in source['files']:
            stream.write(Path(source['source_dir'])/name, name)
    return {'package': archive}


def portability(ctx, inputs):
    archive = Path(inputs['package'].path)
    directory = ctx.workspace / 'independent-source'
    directory.mkdir()
    with zipfile.ZipFile(archive) as package_zip:
        (directory/'strata_core.cpp').write_bytes(package_zip.read('strata_core.cpp'))
    main = directory/'main.cpp'
    main.write_text('#include <cstdio>\nint project();int main(int argc,char**argv){int n=0;FILE*f=fopen(argv[1],"r");if(!f)return 2;fscanf(f,"%d",&n);fclose(f);printf("{\\"value\\":%d}\\n",project()+n);return 0;}\n')
    binary = directory/'checked'
    runtime_input = ctx.workspace/'input.txt'
    runtime_input.write_text('1')
    ctx.run_command(['c++', str(directory/'strata_core.cpp'), str(main), '-o', str(binary)])
    command = ctx.run_command([str(binary), str(runtime_input)])
    result = json.loads(command['stdout'])
    if result != {'value': 8}:
        raise AssertionError(result)
    return {'portability': ctx.write_json('portability.json', {'schema': 'strata.source.portability.v1',
        'package_sha256': inputs['package'].sha256, 'independent_rebuild_validated': True,
        'source_dir': str(directory), 'build_dir': str(directory), 'input_path': str(runtime_input),
        'input_sha256': digest(runtime_input), 'runtime_result': result,
        'stdout_path': command['stdout_path'], 'stderr_path': command['stderr_path'],
        'native_device_validated': False, 'full_inference_validated': False})}


def blocked(ctx, inputs):
    raise StageBlocked('native_unavailable', 'Isolated test has no native backend')


def unavailable():
    return None, {'gateway': GATEWAY_SEAM, 'status': 'unavailable', 'invoked': False,
                  'reason': 'test_isolated_no_model', 'provenance': 'deterministic_evidence'}


class ValueAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        stages = [
            Stage('source', 'Source', 'engineering', 'code_generation', {}, {'source': 'construction.source'}, construct),
            Stage('validate', 'Validate', 'verification', 'source_check', {'source': 'construction.source'}, {'execution': 'construction.execution'}, validate),
            Stage('package', 'Package', 'delivery', 'source_package', {'source': 'construction.source', 'execution': 'construction.execution'}, {'package': 'construction.package'}, package),
            Stage('portability', 'Independent rebuild', 'delivery', 'independent_rebuild',
                  {'package': 'construction.package'}, {'portability': 'construction.portability'}, portability),
            Stage('native', 'Native', 'execution', 'model', {}, {'native': 'native.test'}, blocked),
            Stage('native_consumer', 'Native consumer', 'postprocessing', 'model_consumer',
                  {'native': 'native.test'}, {'consumer': 'native.consumer'}, validate),
            *value_stages(),
        ]
        self.service = FactoryService(self.root, stages)
        with patch('jiuwenswarm.software_factory.value_agent._gateway_configuration', side_effect=unavailable):
            self.run = self.service.create({'goals': ['value.report', 'native.test', 'native.consumer', 'construction.package'],
                                            'owner_id': 'unit-test-owner'}, background=False)
        self.artifacts = {a['kind']: Artifact(**a) for a in self.run['artifacts']
                          if a['kind'] in {'construction.source', 'construction.package', 'construction.execution', 'construction.portability', 'value.report', 'value.evidence'}}

    def tearDown(self):
        self.temp.cleanup()

    def evidence(self):
        return json.loads(Path(self.artifacts['value.evidence'].path).read_text())

    def inputs(self):
        return {name: self.artifacts[kind] for name, kind in (
            ('source', 'construction.source'), ('execution', 'construction.execution'), ('package', 'construction.package'),
            ('portability', 'construction.portability'))}

    def test_report_runs_after_main_goals_and_does_not_block_zip_without_model(self):
        self.assertEqual(self.run['status'], 'blocked')
        self.assertEqual(self.run['goal_results']['value.report']['status'], 'verified')
        self.assertEqual(self.run['goal_results']['construction.package']['status'], 'verified')
        evidence = self.evidence()
        self.assertEqual(evidence['model_assessment']['status'], 'unavailable')
        self.assertFalse(evidence['model_assessment']['invoked'])
        self.assertEqual(evidence['provenance'], 'deterministic_evidence')
        self.assertEqual(evidence['run']['goal_results_at_assessment']['native.test']['status'], 'blocked')
        self.assertEqual(evidence['run']['goal_results_at_assessment']['construction.package']['status'], 'verified')
        self.assertTrue(evidence['scope']['independent_source_zip_rebuild_verified'])
        self.assertEqual(evidence['independent_rebuild']['runtime_result'], {'value': 8})
        self.assertFalse(evidence['scope']['full_model_inference_verified'])
        self.assertFalse(evidence['scope']['native_ascend_inference_verified'])
        report = Path(self.artifacts['value.report'].path).read_text()
        self.assertIn('Value demonstrated (deterministic evidence)', report)
        self.assertIn('Independent source ZIP rebuild', report)
        self.assertIn('No AI-authored assessment is claimed', report)
        self.assertIn('native_unavailable', report)
        self.assertIn(self.artifacts['construction.package'].sha256, report)
        self.assertEqual(evidence['metrics']['recorded_command_count'], 4)
        self.assertEqual(evidence['metrics']['consumed_cross_workflow_dependency_count'], 3)
        self.assertEqual(evidence['metrics']['planned_cross_workflow_dependency_count'], 4)
        self.assertEqual(evidence['metrics']['planned_only_cross_workflow_dependency_count'], 1)
        self.assertEqual(evidence['metrics']['reused_dependency_artifact_count'], 1)
        self.assertEqual(evidence['metrics']['generated_project_file_count'], 1)
        self.assertEqual(evidence['metrics']['generated_cpp_source_file_count'], 1)

    def test_blocked_planned_edges_without_attempt_inputs_are_not_reported_as_deliveries(self):
        evidence = self.evidence()
        native = next(n for n in self.run['nodes'] if n['stage_id'] == 'native')
        consumer = next(n for n in self.run['nodes'] if n['stage_id'] == 'native_consumer')
        self.assertEqual(consumer['attempts'], [])
        planned = {'from': native['id'], 'to': consumer['id'], 'data': 'native.test'}
        self.assertIn(planned, evidence['planned_cross_workflow_edges'])
        self.assertIn(planned, evidence['planned_only_cross_workflow_edges'])
        self.assertFalse(any(e['from'] == native['id'] and e['to'] == consumer['id']
                             for e in evidence['consumed_cross_workflow_edges']))
        for edge in evidence['consumed_cross_workflow_edges']:
            self.assertTrue(edge['artifact_ids'])
            for identifier in edge['artifact_ids']:
                self.assertTrue(any(a['id'] == identifier and a['producer'] == edge['from']
                                    and a['kind'] == edge['data'] for a in self.run['artifacts']))
        report = Path(self.artifacts['value.report'].path).read_text()
        self.assertIn('Planned-only cross-workflow dependencies', report)
        self.assertIn(f'`{native["id"]}` → `{consumer["id"]}` plans `native.test`; no delivery is claimed.', report)

    def test_source_and_zip_contents_are_checked_not_just_manifest_schema(self):
        source = self.artifacts['construction.source'].read_json()
        path = Path(source['source_dir'])/'strata_core.cpp'
        path.write_text('changed source')
        with self.assertRaises(StageFailure) as failed:
            collect_evidence(self.run, self.inputs())
        self.assertEqual(failed.exception.code, 'source_changed')

    def test_zip_with_wrong_generated_bytes_is_rejected(self):
        archive = Path(self.artifacts['construction.package'].path)
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr('strata_core.cpp', 'wrong actual file content')
        inputs = self.inputs()
        inputs['package'] = Artifact(**{**inputs['package'].serializable(), 'sha256': digest(archive)})
        with self.assertRaises(StageFailure) as failed:
            collect_evidence(self.run, inputs)
        self.assertEqual(failed.exception.code, 'contract_invalid')

    def test_model_interpretation_requires_citations_and_rejects_unmeasured_gains(self):
        scope = self.evidence()['scope']
        valid = {'observed_value': [{'claim': 'Construction reuses upstream artifacts.', 'evidence_ids': ['fact.dependencies']}],
                 'limitations': ['Full-model inference is not verified.'], 'next_steps': ['Validate the native device path.']}
        self.assertEqual(_validated_model_analysis(json.dumps(valid), {'fact.dependencies'}, scope), valid)
        wrong = deepcopy(valid)
        wrong['observed_value'][0]['claim'] = 'The process is 2x faster.'
        with self.assertRaises(ValueError):
            _validated_model_analysis(json.dumps(wrong), {'fact.dependencies'}, scope)
        wrong = deepcopy(valid)
        wrong['observed_value'][0]['evidence_ids'] = ['invented.fact']
        with self.assertRaises(ValueError):
            _validated_model_analysis(json.dumps(wrong), {'fact.dependencies'}, scope)
        wrong = deepcopy(valid)
        wrong['observed_value'][0]['claim'] = 'Full-model inference is verified.'
        with self.assertRaises(ValueError):
            _validated_model_analysis(json.dumps(wrong), {'fact.dependencies'}, scope)

    def test_existing_gateway_seam_is_used_without_mutating_or_exposing_private_configuration(self):
        evidence = self.evidence()
        before = deepcopy(evidence)
        observed = {}
        interpretation = {'observed_value': [{'claim': 'Construction reuses upstream artifacts.', 'evidence_ids': ['fact.dependencies']}],
                          'limitations': ['Full-model inference is not verified.'], 'next_steps': ['Validate the native device path.']}
        class IsolatedClient:
            async def invoke(self, **kwargs):
                observed.update(kwargs)
                return {'content': json.dumps(interpretation)}
        private = ({'api_key': 'isolated-secret-not-real', 'api_base': 'https://private.example.test'},
                   {'model': 'isolated-test-model', 'model_name': 'isolated-test-model'})
        with patch('jiuwenswarm.software_factory.value_agent._gateway_configuration', return_value=(private, None)), \
             patch('jiuwenswarm.research.providers.native_client', return_value=IsolatedClient()) as factory:
            assessment = configured_model_assessment(evidence)
        self.assertEqual(assessment['status'], 'completed')
        self.assertTrue(assessment['invoked'])
        factory.assert_called_once_with(*private)
        self.assertEqual(evidence, before)
        self.assertNotIn('isolated-secret-not-real', json.dumps(assessment))
        self.assertNotIn('private.example.test', json.dumps(assessment))
        prompt = observed['messages'][0]['content']
        self.assertNotIn(str(self.root), prompt)
        self.assertNotIn('unit-test-owner', prompt)
        self.assertEqual(observed['tools'], None)

    def test_gateway_failure_never_reflects_secret_exception_text(self):
        evidence = self.evidence()
        private = ({'api_key': 'isolated-secret-not-real'}, {'model_name': 'isolated-test-model'})
        class FailingClient:
            async def invoke(self, **kwargs):
                raise RuntimeError('isolated-secret-not-real was rejected')
        with patch('jiuwenswarm.software_factory.value_agent._gateway_configuration', return_value=(private, None)), \
             patch('jiuwenswarm.research.providers.native_client', return_value=FailingClient()):
            assessment = configured_model_assessment(evidence)
        self.assertEqual(assessment['status'], 'failed')
        self.assertNotIn('isolated-secret-not-real', json.dumps(assessment))
        self.assertNotIn('interpretation', assessment)
        evidence['model_assessment'] = assessment
        self.assertIn('No AI-authored assessment is claimed', render_report(evidence))


if __name__ == '__main__':
    unittest.main()
