"""Oracle fixtures only; no model, live E3 or admission claim."""
import copy
import json
from pathlib import Path
import unittest

from oracle import evaluate, evaluate_content


def fixture(ident='json-types'):
    criteria = json.loads(Path('referee/criteria.json').read_text())
    variant = criteria['variants'][ident]
    expected = variant['binding']
    def ref(label):
        return {'id': 'unit-only:' + label, 'sha256': 'a' * 64}
    source_ref, admission_ref, actual_ref, observed_ref, output_ref, normal_ref = [
        ref(label) for label in ('source', 'admission', 'actual', 'observation', 'output', 'normal')]
    binding = {'declaration_ref': expected['declaration_ref'], 'admission_ref': admission_ref,
               'implementation_refs': expected['implementation_refs'], 'effective_authority': {}}
    packet_ref = variant['input_refs']['packet']
    source = {'bindings': [binding], 'inputs': [{'name': 'packet', 'artifact_refs': [packet_ref]}],
              'input_refs': [packet_ref]}
    actual = {'source_subject_ref': source_ref, 'role': 'worker', 'bindings': [binding],
              'input_refs': [packet_ref], 'run_id': 'unit-only', 'node_id': 'table',
              'subnode_id': 'worker', 'attempt_id': 'one'}
    observed = {'contract_ref': actual_ref, 'observed_runtime': True, 'input_refs': [packet_ref],
                'output_refs': [output_ref], **{k: actual[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id')}}
    measured = {'contract_ref': actual_ref, 'observation_ref': observed_ref,
                'status': 'completed', 'accepted': False, 'output_refs': {'result': output_ref}}
    if ident == 'malformed-row':
        measured.update(status='failed', failure='table_input', output_refs={})
        observed['output_refs'] = []
    def row(kind, value, original):
        return {'kind': kind, 'ref': original, 'record': value}
    records = [row('request', {'entry_point': 'E3', 'normalized_request_ref': normal_ref}, ref('request')),
        row('normalized_request', {'capsule_id': expected['name'], 'capsule_version': expected['version'],
            'capsule_declaration_sha256': expected['declaration_ref']['sha256']}, normal_ref),
        row('source_contract', source, source_ref),
        row('source_declaration', {'identity': {'name': expected['name'], 'version_label': expected['version']}}, expected['declaration_ref']),
        row('source_admission', {'status': 'admitted', 'candidate_ref': expected['declaration_ref']}, admission_ref),
        row('actual_contract', actual, actual_ref), row('observation', observed, observed_ref),
        row('measurement', measured, ref('measurement')),
        row('output', {'data': {'table': variant['expected_table']}}, output_ref)]
    return {'variant_id': ident, 'entrypoint': 'single_cc',
            'execution': {'launched': True, 'terminal': True}, 'records': records}, criteria


class OracleTests(unittest.TestCase):
    def test_valid_controls_and_malformed_refusal_are_separate(self):
        for ident in ('csv-control', 'csv-leading-zero', 'json-types', 'malformed-row'):
            evidence, criteria = fixture(ident)
            result = evaluate(evidence, criteria)
            self.assertTrue(all(c['status'] == 'pass' for c in result['checks']))
            self.assertEqual(result['metrics']['productive_completion'], int(ident != 'malformed-row'))

    def test_foreign_source_binding_or_authority_is_rejected(self):
        for field in ('source_subject_ref', 'bindings', 'input_refs'):
            evidence, criteria = fixture()
            actual = next(r['record'] for r in evidence['records'] if r['kind'] == 'actual_contract')
            actual[field] = [] if field != 'source_subject_ref' else {'id': 'other', 'sha256': 'b' * 64}
            self.assertTrue(evaluate(evidence, criteria)['critical_violations'])

    def test_missing_observation_does_not_become_a_rejection(self):
        evidence, criteria = fixture()
        evidence['records'] = [r for r in evidence['records'] if r['kind'] != 'observation']
        self.assertEqual(evaluate(evidence, criteria)['checks'][-1]['status'], 'unavailable')

    def test_unrelated_failure_is_not_a_correct_refusal(self):
        evidence, criteria = fixture('malformed-row')
        next(r['record'] for r in evidence['records'] if r['kind'] == 'measurement')['failure'] = 'provider_error'
        self.assertTrue(evaluate(evidence, criteria)['critical_violations'])

    def test_missing_original_evidence_is_unavailable(self):
        criteria = json.loads(Path('referee/criteria.json').read_text())
        value = evaluate({'variant_id': 'json-types', 'entrypoint': 'single_cc',
                          'execution': {'launched': True, 'terminal': True}, 'records': []}, criteria)
        self.assertEqual(value['checks'][0]['status'], 'unavailable')

    def test_type_coercion_is_not_equal_content(self):
        variant = {'expected_table': {'columns': ['value'], 'rows': [[1], [False], [None]]}}
        output = {'data': {'table': copy.deepcopy(variant['expected_table'])}}
        self.assertEqual(evaluate_content(output, variant)['metrics']['deterministic_content_success'], 1)
        output['data']['table']['rows'][0][0] = True
        self.assertEqual(evaluate_content(output, variant)['metrics']['deterministic_content_success'], 0)

    def test_row_loss_and_string_conversion_fail(self):
        variant = {'expected_table': {'columns': ['id'], 'rows': [['001'], ['002']]}}
        for rows in ([['001']], [[1], [2]]):
            self.assertEqual(evaluate_content({'data': {'table': {'columns': ['id'], 'rows': rows}}}, variant)
                             ['metrics']['deterministic_content_success'], 0)


if __name__ == '__main__':
    unittest.main()
