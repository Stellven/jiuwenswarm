"""DERIVED coherent synthetic lifecycle tests, never measured run evidence.

The supplied frozen reference closure is retained unchanged, including stale
pins. Tests derive fresh in-memory pins without changing scientific content.
"""
import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from jiuwenswarm.research.checks.research import CheckError, validate_delivery

SOURCE = Path(__file__).parents[2] / 'fixtures/research/pipeline/source-valid'


def derived_reader(source):
    """Topologically repin local artifact references; reject reference cycles."""
    cache, active = {}, set()
    def materialize(name):
        if Path(name).name != name:
            raise ValueError('Derived fixture references must be local filenames')
        if name in cache:
            return cache[name]
        if name in active:
            raise ValueError('Derived fixture reference cycle: ' + name)
        active.add(name)
        raw = (source / name).read_bytes()
        def repin(value):
            if isinstance(value, dict):
                if (set(value) == {'id', 'sha256'} and Path(value['id']).name == value['id']
                        and (source / value['id']).is_file()):
                    return {'id': value['id'], 'sha256': hashlib.sha256(materialize(value['id'])).hexdigest()}
                return {key: repin(child) for key, child in value.items()}
            return [repin(child) for child in value] if isinstance(value, list) else value
        if name.endswith('.json'):
            raw = json.dumps(repin(json.loads(raw)), sort_keys=True, ensure_ascii=False).encode('utf-8')
        if name == 'research_report.md':
            raw = re.sub(rb'(\|\s*([^|\s]+\.(?:json|zip|txt))\s*\|\s*)([a-f0-9]{64})(\s*\|)',
                lambda match: match[1] + hashlib.sha256(materialize(match[2].decode())).hexdigest().encode() + match[4], raw)
        active.remove(name)
        cache[name] = raw
        return raw
    return lambda ref: materialize(ref['id'])


class DeliveryContentTests(unittest.TestCase):
    def fixture(self, *, derived=True):
        names = {'brief': 'lifecycle_research_brief', 'candidate_set': 'candidate_set',
                 'opportunity_card': 'opportunity_card', 'hypothesis_blueprint': 'hypothesis_blueprint',
                 'poc_manifest': 'poc_manifest', 'benchmark_payload': 'benchmark_payload',
                 'evaluation_verdict': 'evaluation_verdict', 'gate_decision_index': 'gate_decision_index',
                 'screening_result': 'screening_result', 'execution_receipt': 'execution_receipt',
                 'environment_lock': 'environment_lock', 'provisioning_receipt': 'provisioning_receipt'}
        reader = derived_reader(SOURCE) if derived else lambda ref: (SOURCE / ref['id']).read_bytes()
        inputs = {key: json.loads(reader({'id': name + '.json'})) for key, name in names.items()}
        refs = {key: {'id': name + '.json', 'sha256': hashlib.sha256(reader({'id': name + '.json'})).hexdigest()} for key, name in names.items()}
        refs['run_configuration'] = {'id': 'run_configuration.json', 'sha256': hashlib.sha256(reader({'id': 'run_configuration.json'})).hexdigest()}
        manifest = json.loads(reader({'id': 'delivery_manifest.json'}))
        # The supplied example lists stdout only. Complete its synthetic raw
        # evidence inventory with the receipt's required stderr Ref.
        stderr = inputs['execution_receipt']['runs'][0]['stderr_ref']
        manifest['files'].append({'path': 'stderr.txt', 'artifact_ref': stderr,
                                  'media_type': 'text/plain', 'role': 'raw_evidence', 'audience': 'researcher'})
        return inputs, refs, manifest, reader({'id': 'research_report.md'}), reader

    def test_exact_negative_science_delivery(self):
        inputs, refs, manifest, report, reader = self.fixture()
        validate_delivery(inputs, refs, manifest, report, reader)

    def test_frozen_original_stale_closure_remains_rejected(self):
        inputs, refs, manifest, report, reader = self.fixture(derived=False)
        with self.assertRaisesRegex(CheckError, 'ref_hash_match'):
            validate_delivery(inputs, refs, manifest, report, reader)

    def test_derivation_preserves_scientific_content_and_frozen_originals(self):
        def without_pins(value):
            if isinstance(value, dict):
                return {key: without_pins(child) for key, child in value.items()
                        if not (set(value) == {'id', 'sha256'} and key == 'sha256')}
            return [without_pins(child) for child in value] if isinstance(value, list) else value
        reader = derived_reader(SOURCE)
        for path in SOURCE.iterdir():
            if not path.is_file():
                continue
            original = path.read_bytes()
            derived = reader({'id': path.name})
            if path.suffix == '.json':
                self.assertEqual(without_pins(json.loads(original)), without_pins(json.loads(derived)))
            elif path.name == 'research_report.md':
                self.assertEqual(re.sub(rb'[a-f0-9]{64}', b'<pin>', original), re.sub(rb'[a-f0-9]{64}', b'<pin>', derived))
            else:
                self.assertEqual(original, derived)
            self.assertEqual(path.read_bytes(), original)

    def test_derived_reference_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for name, target in [('a.json', 'b.json'), ('b.json', 'a.json')]:
                (source / name).write_text(json.dumps({'id': target, 'sha256': '0' * 64}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'reference cycle'):
                derived_reader(source)({'id': 'a.json'})

    def test_swapped_verdict_omitted_risk_and_wrong_value_rejected(self):
        inputs, refs, manifest, report, reader = self.fixture()
        for changed, failure in [(report.replace(b'Classification: FAIL', b'Classification: PASS'), 'verdict_matches_evaluation'),
                (report.replace(b'| latency_ms | ms | 100 | 105 | 5 |', b'| latency_ms | ms | 100 | 95 | -5 |'), 'results_table_matches_payload'),
                (report.replace(('Risk from the opportunity card: ' + inputs['opportunity_card']['risks'][0]).encode(), b'Omitted risk'), 'carried_content')]:
            self.assertNotEqual(changed, report)
            altered = copy.deepcopy(manifest)
            pin = {'id': altered['report_ref']['id'], 'sha256': hashlib.sha256(changed).hexdigest()}
            altered['report_ref'] = pin
            next(file for file in altered['files'] if file['role'] == 'report')['artifact_ref'] = pin
            changed_reader = lambda ref: changed if ref['id'] == pin['id'] else reader(ref)
            with self.assertRaisesRegex(CheckError, failure):
                validate_delivery(inputs, refs, altered, changed, changed_reader)
        bad = copy.deepcopy(manifest); bad['files'] = [f for f in bad['files'] if f['role'] != 'screening']
        with self.assertRaisesRegex(CheckError, 'manifest_completeness'):
            validate_delivery(inputs, refs, bad, report, reader)
