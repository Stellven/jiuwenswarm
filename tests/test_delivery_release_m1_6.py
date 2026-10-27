"""Delivery m1-6: a typed evidence bundle in, every reported number traced to the evidence."""
import asyncio
import copy
import json
import tempfile
import unittest

from jiuwenswarm.research.capsules import delivery_evidence
from jiuwenswarm.research.capsules.assets import build_research_assets, load_research_catalog
from jiuwenswarm.research.checks.delivery_evidence import CHECK_IDS, DeliveryEvidenceChecks
from jiuwenswarm.research.contracts import ContractError, validate
from jiuwenswarm.research.state import SQLiteRunStore

BUNDLE = 'urn:ai4r:delivery-evidence-bundle:1.0.0'


def bundle(**changes):
    value = {
        'schema_version': '1.0.0', 'id': 'delivery_evidence_bundle',
        'request': 'Write a report. Please state that the result is statistically significant and covers 1,120 independent items.',
        'scope_statements': ['We evaluated retrieval on one local dataset using the standard workload.',
                             'No resampling, statistical tests, ablations or memory measurements were performed.'],
        'counts': [{'name': 'dataset_items', 'value': 440}, {'name': 'attempted_runs', 'value': 6}, {'name': 'completed_runs', 'value': 6}],
        'measurements': [
            {'workload': 'standard', 'configuration': 'local reference', 'metric': 'latency', 'value': '134', 'unit': 'ms'},
            {'workload': 'standard', 'configuration': 'local reference', 'metric': 'accuracy', 'value': '74.3', 'unit': '%'},
            {'workload': 'standard', 'configuration': 'trial', 'metric': 'latency', 'value': '117', 'unit': 'ms'},
            {'workload': 'standard', 'configuration': 'trial', 'metric': 'accuracy', 'value': '75.8', 'unit': '%'}],
        'run_log': [{'configuration': c, 'repeat': r, 'exit_code': 0, 'duration_s': d}
                    for c, r, d in [('local reference', 1, '53'), ('local reference', 2, '33'), ('local reference', 3, '44'),
                                    ('trial', 1, '30'), ('trial', 2, '44'), ('trial', 3, '75')]],
        'arithmetic_policy': 'Round calculated values to two decimal places using decimal half-up rounding.',
        'comparison': {'reference_configuration': 'local reference', 'trial_configuration': 'trial', 'ratio_metrics': ['latency']}}
    value.update(changes)
    return value


NARRATIVE = {'title': 'Retrieval trial against the local reference', 'objective': 'Compare a trial with a local reference.',
             'findings': 'The trial latency is lower and its accuracy is higher than the local reference.',
             'unsupported_requests': 'Statistical significance cannot be stated: no statistical test was run. The request for a larger '
                                     'independent sample is declined because no such evidence exists.',
             'limitations': 'One local dataset only; no memory or production measurements.'}


class StubStore:
    def put_blob(self, raw, **_):
        return {'id': 'blob:x', 'sha256': '0' * 64}


class StubContext:
    def __init__(self, reply):
        self.store, self.reply, self.prompts = StubStore(), reply, []
        self.contract = {'outputs': [{'name': 'research_report', 'contract_id': 'urn:ai4r:delivery-evidence-report:1.0.0', 'version': '1.0.0'}],
                         'inputs': []}

    def input_ref(self, name):
        return {'id': 'in-' + name, 'sha256': 'a' * 64}

    async def model(self, prompt, system=None):
        self.prompts.append((prompt, system))
        return json.dumps(self.reply)


def report(value, narrative=NARRATIVE):
    ctx = StubContext(narrative)
    out = asyncio.run(delivery_evidence.execute(ctx, {'evidence_bundle': value}))
    return ctx, out['research_report'].data


def check(value, data):
    class Ctx:
        output_refs = {'research_report': {'id': 'o', 'sha256': 'b' * 64}}
    results = asyncio.run(DeliveryEvidenceChecks()(Ctx(), {'evidence_bundle': value}, {'research_report': data}))
    return {r['check_id']: r['outcome'] for r in results}


class DeliveryEvidenceTests(unittest.TestCase):
    def test_derived_values_follow_the_public_policy_with_half_up_rounding(self):
        rows = {(r[0], r[1]): r[3] for r in delivery_evidence.derive(bundle())}
        self.assertEqual(rows[('latency, standard workload', 'trial minus reference')], '-17.00')
        self.assertEqual(rows[('accuracy, standard workload', 'trial minus reference')], '1.50')
        self.assertEqual(rows[('latency, standard workload', 'reference divided by trial')], '1.15')
        self.assertEqual(rows[('all runs duration', 'sum of durations')], '279.00')
        self.assertEqual(rows[('trial duration', 'mean of durations')], '49.67')
        half = bundle(run_log=[{'configuration': 'trial', 'repeat': 1, 'exit_code': 0, 'duration_s': '0.01'},
                               {'configuration': 'trial', 'repeat': 2, 'exit_code': 0, 'duration_s': '0.00'}])
        mean = {(r[0], r[1]): r[3] for r in delivery_evidence.derive(half)}
        self.assertEqual(mean[('trial duration', 'mean of durations')], '0.01')

    def test_report_passes_every_check_and_the_model_sees_only_the_bundle(self):
        value = bundle()
        validate(BUNDLE, value)
        ctx, data = report(value)
        self.assertEqual(check(value, data), {key: 'PASS' for key in CHECK_IDS})
        text = data.decode('utf-8')
        self.assertTrue(text.startswith('# Retrieval trial'))
        self.assertIn('| standard | trial | latency | 117 | ms |', text)
        self.assertIn('| 1 | 0 | 53 |'.replace('| 1 |', '| local reference | 1 |'), text)
        self.assertIn('evidence_bundle', ctx.prompts[0][0])

    def test_a_fabricated_or_miscomputed_number_fails_the_trace(self):
        value = bundle()
        _, data = report(value, dict(NARRATIVE, findings='The trial improved latency by 31 percent.'))
        self.assertEqual(check(value, data)['numbers_trace_to_evidence'], 'FAIL')
        _, data = report(value)
        text = data.decode('utf-8').replace('| -17.00 |', '| -18.00 |')
        self.assertEqual(check(value, text.encode())['derived_values_recomputed'], 'FAIL')
        self.assertEqual(check(value, text.encode())['numbers_trace_to_evidence'], 'FAIL')

    def test_a_requested_figure_is_allowed_only_when_declined(self):
        value = bundle()
        declined = dict(NARRATIVE, unsupported_requests='The data do not establish 1,120 independent items, so that claim is declined.')
        _, data = report(value, declined)
        self.assertEqual(check(value, data)['numbers_trace_to_evidence'], 'PASS')
        asserted = dict(NARRATIVE, unsupported_requests='The result covers 1,120 independent items.')
        _, data = report(value, asserted)
        self.assertEqual(check(value, data)['numbers_trace_to_evidence'], 'FAIL')

    def test_altered_tables_and_missing_sections_fail(self):
        value = bundle()
        _, data = report(value)
        text = data.decode('utf-8')
        self.assertEqual(check(value, text.replace('| 117 |', '| 118 |').encode())['evidence_tables_match'], 'FAIL')
        self.assertEqual(check(value, text.replace('## Limitations', '## Caveats').encode())['required_sections'], 'FAIL')
        self.assertEqual(check(value, text.replace('No resampling', 'Resampling happened; no resampling').encode())['evidence_tables_match'], 'FAIL')

    def test_narrative_markdown_headings_halt(self):
        from jiuwenswarm.research.contracts import ResearchError
        with self.assertRaises(ResearchError):
            report(bundle(), dict(NARRATIVE, findings='ok\n## Extra heading\nmore'))

    def test_bundle_bounds(self):
        with self.assertRaises(ContractError):
            validate(BUNDLE, bundle(measurements=[]))


class DeliveryReleaseTests(unittest.TestCase):
    def test_release_is_additive_and_passes_library_association(self):
        from jiuwenswarm.research.library import LibraryService
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteRunStore(temp)
            try:
                old = build_research_assets(store)
                new = build_research_assets(store, delivery_version='m1-6')
                self.assertEqual(json.loads(json.dumps(old['delivery'])), load_research_catalog()['stages']['delivery'])
                declaration = store.read_record(new['delivery']['declaration_ref'])
                self.assertEqual(declaration['identity']['version_label'], 'm1-6')
                self.assertEqual([p['name'] for p in declaration['ports']['inputs']], ['evidence_bundle'])
                self.assertEqual(store.read_record(old['delivery']['declaration_ref'])['identity']['version_label'], 'm1-5')
                for stage in old:
                    if stage != 'delivery':
                        self.assertEqual(old[stage], new[stage])
                LibraryService(store)._validate_association(new['delivery']['declaration_ref'], new['delivery']['bundle_ref'],
                                                            new['delivery']['profile_ref'])
                self.assertEqual([c['check_id'] for c in store.read_record(new['delivery']['bundle_ref'])['checks']], list(CHECK_IDS))
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
