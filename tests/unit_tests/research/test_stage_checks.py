"""Connected deterministic checks over the supplied synthetic lifecycle bytes."""
import asyncio
import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from jiuwenswarm.research.checks import CheckContext
from jiuwenswarm.research.checks.stages import ResearchChecks
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

SOURCE = Path(__file__).parents[2] / 'fixtures/research/pipeline/source-valid'


class StageChecksTests(unittest.TestCase):
    def run_screening(self, change=None):
        with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(directory)) as store:
            assets = build_research_assets(store)
            def capture(name):
                raw = (SOURCE / (name + '.json')).read_bytes()
                return store.put_blob(raw), json.loads(raw)
            inputs, bound = {}, []
            for port, file in [('brief', 'lifecycle_research_brief'), ('candidate_set', 'candidate_set'), ('screening_rubric', 'screening_rubric')]:
                ref, value = capture(file)
                if port == 'screening_rubric':
                    # The runtime requires the exact admitted rubric bytes;
                    # retain the independent fixture's scoring expectations.
                    ref = assets['screening']['body_refs']['screening_rubric.json']
                    admitted = json.loads(store.read_blob(ref))
                    self.assertEqual(value, admitted)
                    value = admitted
                inputs[port] = value
                bound.append({'name': port, 'artifact_refs': [ref]})
            outputs, refs = {}, {}
            for port in ['screening_result', 'opportunity_card']:
                ref, value = capture(port); outputs[port] = value; refs[port] = ref
                # Synthetic example markers are outside these closed field
                # contracts; they are fixture metadata, never product outputs.
                value.pop('ext', None)
            # Replace only identities with the newly captured exact bytes; no
            # computed score/rank expectation comes from the implementation.
            by_port = {row['name']: row['artifact_refs'][0] for row in bound}
            for value in outputs.values():
                value['candidate_ref'] = by_port['candidate_set']; value['brief_ref'] = by_port['brief']
            outputs['screening_result']['rubric_ref'] = by_port['screening_rubric']
            refs['screening_result'] = store.put_blob(json_bytes(outputs['screening_result']))
            outputs['opportunity_card']['screening_ref'] = refs['screening_result']
            if change: change(outputs)
            refs['opportunity_card'] = store.put_blob(json_bytes(outputs['opportunity_card']))
            refs['screening_result'] = store.put_blob(json_bytes(outputs['screening_result']))
            contract = {'run_id': 'fixture-run', 'inputs': bound, 'bindings': [{'declaration_ref': assets['screening']['declaration_ref']}]}
            ctx = CheckContext(contract, store, inputs, outputs, refs, {})
            return asyncio.run(ResearchChecks('screening')(ctx, inputs, outputs))

    def test_independent_full_pair_passes(self):
        results = self.run_screening()
        self.assertEqual(len(results), 16)
        self.assertEqual({row['outcome'] for row in results}, {'PASS'})

    def test_forged_ranking_or_card_rejects_whole_pair(self):
        for mutation in [lambda values: values['opportunity_card'].update(rank=2),
                         lambda values: values['screening_result']['scores'][0].update(total=15),
                         lambda values: values['opportunity_card'].update(other_dispositions=[])]:
            with self.subTest(mutation=mutation):
                self.assertEqual({row['outcome'] for row in self.run_screening(mutation)}, {'FAIL'})
