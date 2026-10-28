"""Scripted integration tests of actual workers/checks/verifier/gate, no effects."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import unittest
import subprocess
from unittest.mock import patch

import jiuwenswarm.research
from jiuwenswarm.research.binding import expand_selectors
from jiuwenswarm.research.capability_planning import capability_plan_policy
from jiuwenswarm.research.science import rule_text
from cclib import harness
from cclib.harness import Harness, ScriptedModel, CodexModel, transport_text, product_assets
from cclib.compare_prompts import compare_bytes

REPO = Path(jiuwenswarm.research.__file__).parents[2]
FIX = REPO / 'tests/fixtures/research'


def read(path):
    return json.loads(path.read_text('utf-8'))


def verifier_reply(prompt, system):
    criteria = json.loads(system.split('Criteria for this output:\n', 1)[1])
    return {'findings': [{'criterion_id': c['criterion_id'], 'outcome': 'PASS',
                          'reason': 'Controlled structural review, no model quality claim.'} for c in criteria],
            'uncertainties': [], 'limitations': [], 'required_correction': None}


class DirectoryFixture:
    """Repin a synthetic fixture closure topologically without editing originals."""
    def __init__(self, harness, directory):
        self.h, self.directory, self.refs, self.values, self.active = harness, directory, {}, {}, set()

    def capture(self, name):
        if name in self.refs:
            return self.refs[name]
        if name in self.active:
            raise ValueError('Fixture reference cycle')
        self.active.add(name)
        raw = (self.directory / name).read_bytes()
        def repin(v):
            if isinstance(v, dict):
                if set(v) == {'id', 'sha256'} and Path(v['id']).name == v['id'] and (self.directory / v['id']).is_file():
                    return self.capture(v['id'])
                return {k: repin(child) for k, child in v.items()}
            return [repin(child) for child in v] if isinstance(v, list) else v
        value = repin(json.loads(raw)) if name.endswith('.json') else raw
        ref = self.h.capture(value, record_id=name)
        self.refs[name], self.values[name] = ref, value
        self.active.remove(name)
        return ref

    def get(self, name):
        self.capture(name)
        return copy.deepcopy(self.values[name])


async def fixture(h, stage):
    if stage in ('intent', 'requirements'):
        request = h.capture((FIX / 'compiler/request.txt').read_bytes())
        intake = {'request_ref': request, 'source_refs': [], 'resource_refs': []}
        iref = h.capture(intake)
        intent = read(FIX / 'compiler/intent_ir.json')
        def rewrite(v):
            if isinstance(v, dict):
                if set(v) == {'id', 'sha256'}:
                    return request
                return {k: rewrite(c) for k, c in v.items()}
            return [rewrite(c) for c in v] if isinstance(v, list) else v
        intent = rewrite(intent)
        if stage == 'intent':
            return {'request': intake}, {'request': iref}, intent
        intent_ref = h.capture(intent)
        policy = {'schema_version': '1.0.0', 'id': 'defaults', 'hardware_profile': 'single_gpu', 'automatic_retries': 0}
        policy_ref = h.capture(policy)
        brief = read(FIX / 'compiler/research_brief.json')
        mappings = {'intent_ir.json': intent_ref, 'qualified_intake.json': iref,
                    'default_policy.json': policy_ref, 'request.txt': request}
        def rewrite_brief(v):
            if isinstance(v, dict):
                if set(v) == {'id', 'sha256'}:
                    return mappings[v['id']]
                return {k: rewrite_brief(c) for k, c in v.items()}
            return [rewrite_brief(c) for c in v] if isinstance(v, list) else v
        brief = rewrite_brief(brief)
        # Preserve Intent scope identity, as in the repository controlled fixture.
        brief['in_scope'][0]['id'] = intent['in_scope'][0]['id']
        return {'intent': intent, 'intake': intake, 'defaults': policy}, {'intent': intent_ref, 'intake': iref, 'defaults': policy_ref}, brief
    if stage == 'planner':
        directory = FIX / 'planning'
        source = read(directory / 'static_template.json')
        brief = read(directory / 'lifecycle_research_brief.json')
        library = read(directory / 'library_snapshot.json')
        resources = read(directory / 'resource_inventory.json')
        asset = await h.assets('screening')
        declaration = h.store.read_record(asset['declaration_ref'])
        declaration['identity']['name'] = 'utility.test_worker'
        declaration['ports']['inputs'] = []
        output = copy.deepcopy(declaration['ports']['outputs'][0])
        output.update(name='result', artifact_type='work_packet', schema_ref='urn:ai4r:work-packet:1.0.0')
        declaration['ports']['outputs'] = [output]
        declaration_ref = h.capture(declaration)
        node = source['nodes'][0]
        node.update(node_id='work', predecessors=[], inputs=[], outputs=[{'name': 'result', 'artifact_type': 'work_packet', 'required': True}],
                    requirement_ids=['all_mandatory_requirements'], deliverable_ids=['all_deliverables'])
        node['cc'] = {'cc_name': declaration['identity']['name'], 'cc_version': declaration['identity']['version_label'],
                      'declaration_sha256': declaration_ref['sha256']}
        source['nodes'] = [node]
        source['coverage'] = [{'selector': key, 'node_ids': ['work']} for key in ('all_mandatory_requirements', 'all_deliverables', 'all_evidence_obligations')]
        entry = library['entries'][0]
        entry.update(**node['cc'], selectable_by_planner=True, input_ports=[],
                     output_ports=[{k: output[k] for k in ('name', 'artifact_type', 'schema_ref', 'required')}],
                     resource_needs=[], max_limits=node['limits'])
        library['entries'] = [entry]
        policy = capability_plan_policy()
        inputs = {'brief': brief, 'library_snapshot': library, 'resource_inventory': resources, 'plan_policy': policy}
        refs = {k: h.capture(v) for k, v in inputs.items()}
        catalog = {'schema_version': '1.0.0', 'library_snapshot_ref': refs['library_snapshot'],
                   'capsules': [{'cc': node['cc'], 'declaration_ref': declaration_ref, 'declaration': declaration}]}
        inputs['capsule_contracts'], refs['capsule_contracts'] = catalog, h.capture(catalog)
        source = expand_selectors(source, brief)
        source.pop('template_name')
        source.update(schema_version='3.0.0', plan_source='planned', topic_hints=[], notes='',
                      brief_ref=refs['brief'], library_snapshot_ref=refs['library_snapshot'],
                      resource_inventory_ref=refs['resource_inventory'], policy_ref=refs['plan_policy'])
        return inputs, refs, source
    d = DirectoryFixture(h, FIX / 'pipeline/source-valid')
    asset = await h.assets(stage)
    declaration = h.store.read_record(asset['declaration_ref'])
    names = {'brief': 'lifecycle_research_brief.json'}
    inputs, refs = {}, {}
    for p in declaration['ports']['inputs']:
        name = p['name']
        filename = names.get(name, name + '.json')
        inputs[name] = d.get(filename)
        refs[name] = d.capture(filename)
    if stage == 'screening':
        refs['screening_rubric'] = asset['body_refs']['screening_rubric.json']
        inputs['screening_rubric'] = h.store.read_record(refs['screening_rubric'])
        reply = {'scores': d.get('screening_result.json')['scores'], 'opportunity_statement': d.get('opportunity_card.json')['opportunity_statement']}
    elif stage == 'evaluation':
        reply = d.get('evaluation_verdict.json')
        reply.pop('ext', None)
        for finding in reply['findings']:
            rule = next(r for r in inputs['hypothesis_blueprint']['outcome_rules'] if r['metric_id'] == finding['metric_id'])
            finding['rule_text'] = rule_text(rule, finding['rule_applied'])
    else:
        reply = {'title': 'Controlled negative science report', 'objective': 'Compare the registered treatment and baseline.',
                 'opportunity_and_citations': 'The accepted opportunity motivates the comparison.',
                 'method_and_poc': 'The supplied manifest and registered protocol define the method.'}
    return inputs, refs, reply


class HarnessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)

    async def test_product_release_selection_and_separate_evidence_pilots(self):
        h = Harness()
        try:
            compiler, research, paper, evidence = await product_assets(h.store)
            for asset, version in ((compiler['intent'], 'm1-7'),
                                   (compiler['requirements'], 'm1-9'),
                                   (research['screening'], 'm1-5')):
                self.assertEqual(h.store.read_record(asset['declaration_ref'])['identity']['version_label'], version)
            self.assertNotIn('paper_planner', paper)
            for stage in ('evaluation', 'delivery'):
                pilot = evidence['research_assets'][stage + '_evidence']
                self.assertNotEqual(pilot['profile_ref'], research[stage]['profile_ref'])
                self.assertEqual((await h.assets(stage))['declaration_ref'], research[stage]['declaration_ref'])
        finally:
            h.close()

    async def test_every_stage_advances_and_records_calls(self):
        for stage in ('intent', 'requirements', 'screening', 'evaluation', 'delivery', 'planner'):
            with self.subTest(stage=stage):
                h = Harness()
                try:
                    inputs, refs, reply = await fixture(h, stage)
                    model = ScriptedModel([reply, verifier_reply, verifier_reply])
                    result = await h.run_stage(stage, inputs, model=model, input_refs=refs)
                    self.assertEqual(result['status'], 'advance', result['reasons'])
                    self.assertTrue(result['check_results'])
                    self.assertTrue(result['gate_decisions'])
                    self.assertEqual(result['model_calls'], 1 + len(result['output']))
                    self.assertEqual(len(result['prompts']), result['model_calls'])
                    self.assertTrue(all(c['raw_reply'] for c in result['calls']))
                    self.assertIsNone(result['tokens'])
                    for prompt in result['prompts']:
                        self.assertEqual(prompt['sha256'], hashlib.sha256(prompt['text'].encode('utf-8')).hexdigest())
                finally:
                    h.close()

    async def test_intent_output_feeds_requirements(self):
        h = Harness()
        try:
            inputs, refs, brief = await fixture(h, 'requirements')
            first = await h.run_stage('intent', {'request': inputs['intake']},
                input_refs={'request': refs['intake']},
                model=ScriptedModel([inputs['intent'], verifier_reply]))
            self.assertEqual(first['status'], 'advance', first['reasons'])
            old_ref = refs['intent']
            new_ref = first['output_refs']['intent']

            def bind(value):
                if isinstance(value, dict):
                    if value == old_ref:
                        return new_ref
                    return {k: bind(v) for k, v in value.items()}
                return [bind(v) for v in value] if isinstance(value, list) else value

            inputs['intent'], refs['intent'] = first['output']['intent'], new_ref
            second = await h.run_stage('requirements', inputs, input_refs=refs,
                model=ScriptedModel([bind(brief), verifier_reply]))
            self.assertEqual(second['status'], 'advance', second['reasons'])
        finally:
            h.close()

    async def test_every_stage_defect_halts_in_real_deterministic_checks(self):
        for stage in ('intent', 'requirements', 'screening', 'evaluation', 'delivery', 'planner'):
            with self.subTest(stage=stage):
                h = Harness()
                try:
                    inputs, refs, reply = await fixture(h, stage)
                    if stage == 'intent':
                        reply['interpretation']['problem']['source_spans'][0]['end'] = 10**6
                    elif stage == 'requirements':
                        reply['acceptance_expectations'][0]['requirement_ids'] = [reply['mandatory_requirements'][0]['id']]
                    elif stage == 'screening':
                        reply['scores'] = reply['scores'][:-1]
                    elif stage == 'evaluation':
                        reply['findings'][0]['treatment_value'] += 1
                    elif stage == 'delivery':
                        reply['objective'] = '## An unauthorized report section'
                    else:
                        reply['nodes'][0]['predecessors'] = [reply['nodes'][0]['node_id']]
                    model = ScriptedModel([reply, reply])
                    result = await h.run_stage(stage, inputs, model=model, input_refs=refs)
                    self.assertEqual(result['status'], 'halt')
                    self.assertTrue(any(r['outcome'] == 'FAIL' for r in result['check_results']), result['reasons'])
                    self.assertFalse(result['verifier_findings'])
                    self.assertTrue(result['prompts'])
                    self.assertEqual(result['model_calls'], 2 if stage == 'planner' else 1)
                finally:
                    h.close()

    async def test_semantic_rejection_halts_after_good_checks(self):
        h = Harness()
        try:
            inputs, refs, reply = await fixture(h, 'intent')
            def reject(prompt, system):
                value = verifier_reply(prompt, system)
                value['findings'][0].update(outcome='FAIL', reason='Controlled semantic contradiction')
                return value
            result = await h.run_stage('intent', inputs, model=ScriptedModel([reply, reject]), input_refs=refs)
            self.assertEqual(result['status'], 'halt')
            self.assertTrue(all(r['outcome'] == 'PASS' for r in result['check_results']))
            self.assertIn('Controlled semantic contradiction', ' '.join(result['reasons']))
        finally:
            h.close()

    def test_no_implicit_model_calls(self):
        with patch('subprocess.run') as run:
            with self.assertRaises(ValueError):
                CodexModel('unused')
            run.assert_not_called()

    def test_comparison_never_normalizes_bytes(self):
        self.assertTrue(compare_bytes(b'a\n', b'a\n')['equal'])
        self.assertFalse(compare_bytes(b'a\r\n', b'a\n')['equal'])
        self.assertFalse(compare_bytes(b'{"a":1}', b'{ "a": 1 }')['equal'])

    async def test_codex_adapter_records_raw_reply_tokens_and_exact_command(self):
        def fake_run(argv, **kwargs):
            self.assertEqual(argv[1:8], ['exec', '--skip-git-repo-check', '-m', 'test-model', '-s', 'read-only', '--ephemeral'])
            self.assertEqual(kwargs['timeout'], 300)
            self.assertEqual(kwargs['input'], transport_text('payload', 'system').encode('utf-8'))
            directory = Path(argv[argv.index('-C') + 1])
            self.assertTrue(directory.is_relative_to(harness.SCRATCH_ROOT))
            Path(argv[argv.index('-o') + 1]).write_bytes(b'{"raw": true}\n')
            return subprocess.CompletedProcess(argv, 0, b'', b'tokens used\n1,234\n')
        model = CodexModel('test-model', execute=True)
        with patch('subprocess.run', side_effect=fake_run) as run, patch.object(harness.roots, 'require_codex', return_value='codex'):
            reply = await model('payload', system='system')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(reply, '{"raw": true}\n')
        self.assertEqual(model.records[0]['tokens'], 1234)
        self.assertTrue(model.records[0]['token_lines'])

    async def test_codex_timeout_has_no_retry(self):
        model = CodexModel('test-model', execute=True)
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['codex'], 300)) as run, patch.object(harness.roots, 'require_codex', return_value='codex'):
            with self.assertRaisesRegex(Exception, 'model_timeout'):
                await model('unused')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(model.records[0]['error'], 'timeout')

    async def test_blocking_readiness_skips_semantic_review(self):
        h = Harness()
        try:
            inputs, refs, reply = await fixture(h, 'intent')
            reply['readiness']['status'] = 'needs_clarification'
            result = await h.run_stage('intent', inputs, model=ScriptedModel([reply]), input_refs=refs)
            self.assertEqual(result['status'], 'halt')
            self.assertTrue(all(r['outcome'] == 'PASS' for r in result['check_results']))
            self.assertEqual(result['model_calls'], 1)
            self.assertIn('blocking_uncertainty', result['reasons'])
        finally:
            h.close()

    async def test_malformed_verifier_never_advances(self):
        h = Harness()
        try:
            inputs, refs, reply = await fixture(h, 'intent')
            result = await h.run_stage('intent', inputs, model=ScriptedModel([reply, {}]), input_refs=refs)
            self.assertEqual(result['status'], 'halt')
            self.assertEqual(result['model_calls'], 2)
            self.assertIn('assessment_invalid', ' '.join(result['reasons']))
        finally:
            h.close()


if __name__ == '__main__':
    unittest.main()
