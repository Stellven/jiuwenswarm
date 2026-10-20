"""Literal supplied synthetic lifecycle is an oracle, never measured evidence."""
import copy
import json
import unittest
from pathlib import Path

from jiuwenswarm.research.checks.research import CheckError, validate_delivery

SOURCE = Path(__file__).parents[2] / 'fixtures/research/pipeline/source-valid'


class DeliveryContentTests(unittest.TestCase):
    def fixture(self):
        names = {'brief': 'lifecycle_research_brief', 'candidate_set': 'candidate_set',
                 'opportunity_card': 'opportunity_card', 'hypothesis_blueprint': 'hypothesis_blueprint',
                 'poc_manifest': 'poc_manifest', 'benchmark_payload': 'benchmark_payload',
                 'evaluation_verdict': 'evaluation_verdict', 'gate_decision_index': 'gate_decision_index',
                 'screening_result': 'screening_result', 'execution_receipt': 'execution_receipt',
                 'environment_lock': 'environment_lock', 'provisioning_receipt': 'provisioning_receipt'}
        inputs = {key: json.loads((SOURCE / (name + '.json')).read_text(encoding='utf-8')) for key, name in names.items()}
        import hashlib
        refs = {key: {'id': name + '.json', 'sha256': hashlib.sha256((SOURCE / (name + '.json')).read_bytes()).hexdigest()} for key, name in names.items()}
        refs['run_configuration'] = {'id': 'run_configuration.json', 'sha256': hashlib.sha256((SOURCE / 'run_configuration.json').read_bytes()).hexdigest()}
        manifest = json.loads((SOURCE / 'delivery_manifest.json').read_text(encoding='utf-8'))
        # The supplied example lists stdout only. Complete its synthetic raw
        # evidence inventory with the receipt's required stderr Ref.
        stderr = inputs['execution_receipt']['runs'][0]['stderr_ref']
        manifest['files'].append({'path': 'stderr.txt', 'artifact_ref': stderr,
                                  'media_type': 'text/plain', 'role': 'raw_evidence', 'audience': 'researcher'})
        return inputs, refs, manifest, (SOURCE / 'research_report.md').read_bytes()

    def test_exact_negative_science_delivery(self):
        inputs, refs, manifest, report = self.fixture()
        validate_delivery(inputs, refs, manifest, report, lambda ref: (SOURCE / ref['id']).read_bytes())

    def test_swapped_verdict_omitted_risk_and_wrong_value_rejected(self):
        inputs, refs, manifest, report = self.fixture()
        for changed in [report.replace(b'Classification: FAIL', b'Classification: PASS'),
                        report.replace(b'| latency_ms | ms | 100 | 105 | 5 |', b'| latency_ms | ms | 100 | 95 | -5 |')]:
            with self.assertRaises(CheckError):
                validate_delivery(inputs, refs, manifest, changed, lambda ref: (SOURCE / ref['id']).read_bytes())
        bad = copy.deepcopy(manifest); bad['files'] = [f for f in bad['files'] if f['role'] != 'screening']
        with self.assertRaises(CheckError):
            validate_delivery(inputs, refs, bad, report, lambda ref: (SOURCE / ref['id']).read_bytes())
