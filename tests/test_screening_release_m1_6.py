"""Screening m1-6: N ideas, exact rational weights, hard constraints, recomputable ranking."""
import asyncio
import copy
import json
import random
import tempfile
import unittest
from fractions import Fraction

from jiuwenswarm.research.capsules.assets import build_research_assets, load_research_catalog
from jiuwenswarm.research.capsules.ranking_weighted import rank_weighted
from jiuwenswarm.research.capsules.screening_weighted import WeightedScreeningCarrier
from jiuwenswarm.research.checks.screening_weighted import CHECK_IDS, WeightedScreeningChecks
from jiuwenswarm.research.contracts import ContractError, ResearchError, validate
from jiuwenswarm.research.state import SQLiteRunStore

CAND = 'urn:ai4r:screening-weighted-candidates:1.0.0'
RUBRIC = 'urn:ai4r:screening-weighted-rubric:1.0.0'
RESULT = 'urn:ai4r:screening-weighted-result:1.0.0'


def idea(name, nov, fea, cost, *, gpu=False, lic='MIT', runtime='10', deps=('numpy',)):
    return {'idea_id': name, 'title': 'Idea ' + name, 'summary': 'Summary of ' + name, 'citation_ids': ['c:' + name, 'Ref/' + name],
            'assessments': {'novelty': nov, 'feasibility': fea, 'expected_cost': cost},
            'facts': {'license': lic, 'runtime_minutes': runtime, 'requires_gpu': gpu, 'dependencies': list(deps)}}


def rubric(**changes):
    value = {'schema_version': '1.0.0', 'id': 'weighted_rubric',
             'weights': {'novelty': '2/5', 'feasibility': '1/2', 'expected_cost': '-1/10'},
             'constraints': {'cpu_only': True, 'max_runtime_minutes': '45', 'allowed_licenses': ['MIT', 'Apache-2.0'],
                             'forbidden_dependencies': ['bad-engine']},
             'tie_rule': 'ascending_idea_id_codepoint', 'reason_max_chars': 300}
    value.update(changes)
    return value


def candidates(*ideas):
    return {'schema_version': '1.0.0', 'id': 'weighted_candidate_set', 'ideas': list(ideas)}


class Ref(dict):
    pass


class StubStore:
    def __init__(self):
        self.blobs = {}

    def read_blob(self, ref):
        return self.blobs[ref['id']]

    def put_blob(self, raw, **_):
        ref = {'id': 'blob:' + str(len(self.blobs)), 'sha256': '0' * 64}
        self.blobs[ref['id']] = raw
        return ref


class StubContext:
    def __init__(self, reply, prompt=b'Narrate only.'):
        self.store = StubStore()
        self.helper = self.store.put_blob(b'helper')
        self.prompt = self.store.put_blob(prompt)
        self.contract = {'bindings': [{'implementation_refs': [self.prompt], 'dependency_refs': [self.helper]}], 'outputs': [
            {'name': 'screening_result', 'contract_id': RESULT, 'version': '1.0.0'}], 'inputs': []}
        self.reply, self.hosted, self.prompts = reply, [], []

    def input_ref(self, name):
        return {'id': 'in-' + name, 'sha256': 'a' * 64}

    def record_host(self, key, ref):
        self.hosted.append((key, ref))

    async def model(self, prompt, system=None):
        self.prompts.append((prompt, system))
        return json.dumps(self.reply(prompt) if callable(self.reply) else self.reply)


def run_carrier(cand, rub, reply):
    ctx = StubContext(reply)
    carrier = WeightedScreeningCarrier(rank_weighted, ctx.helper, ctx.prompt)
    # The carrier's captured() writes through ctx.store.put_blob with json_bytes.
    produced = asyncio.run(carrier.execute(ctx, {'candidate_set': cand, 'screening_rubric': rub}))
    return ctx, json.loads(produced['screening_result'].data)


def narration(cand):
    return lambda prompt: {'assessments': [{'idea_id': i['idea_id'], 'assessment': 'About ' + i['idea_id']} for i in cand['ideas']],
                           'opportunity_statement': 'The leading idea has the highest exact total.'}


class WeightedRankerTests(unittest.TestCase):
    def test_exact_rational_totals_ties_and_exclusions(self):
        cand = candidates(idea('b', '6', '6', '3'), idea('c', '6', '6', '3'), idea('e', '10', '10', '0'),
                          idea('a', '10', '10', '0', deps=('bad-engine',)), idea('d', '8', '6', '4', gpu=True),
                          idea('f', '4', '1', '1', lic='GPL-3.0', runtime='46'))
        out = rank_weighted(cand, rubric())
        self.assertEqual([r['idea_id'] for r in out['ranking']], ['e', 'b', 'c', ])
        totals = {r['idea_id']: r['weighted_total'] for r in out['rows']}
        self.assertEqual(totals['b'], '51/10')
        self.assertEqual(totals['e'], '9')
        self.assertEqual(totals['b'], totals['c'])
        codes = {r['idea_id']: [v['code'] for v in r['violations']] for r in out['rows']}
        self.assertEqual(codes['a'], ['forbidden_dependency'])
        self.assertEqual(codes['d'], ['requires_gpu'])
        self.assertEqual(codes['f'], ['license_not_allowed', 'runtime_exceeds_budget'])
        self.assertEqual(out['selected_idea_id'], 'e')

    def test_no_float_rounding_where_floats_would_tie_wrongly(self):
        # 0.1 + 0.2 != 0.3 in binary floats; exact arithmetic ties and falls to id order.
        weights = {'a': '1/10', 'b': '1/5'}
        cand = candidates({**idea('x', '1', '1', '1'), 'assessments': {'a': '1', 'b': '1'}},
                          {**idea('w', '1', '1', '1'), 'assessments': {'a': '3', 'b': '0'}})
        out = rank_weighted(cand, rubric(weights=weights))
        self.assertEqual([r['weighted_total'] for r in out['ranking']], ['3/10', '3/10'])
        self.assertEqual([r['idea_id'] for r in out['ranking']], ['w', 'x'])

    def test_decimal_and_ordinary_case_sensitive_tie_order(self):
        cand = candidates(idea('b', '1.5', '2', '0'), idea('B', '1.5', '2', '0'), idea('a', '3/2', '2', '0'))
        out = rank_weighted(cand, rubric())
        self.assertEqual([r['idea_id'] for r in out['ranking']], ['B', 'a', 'b'])

    def test_bounded_n_and_order_invariance(self):
        rng = random.Random(7)
        ideas = [idea('i%02d' % k, str(rng.randint(0, 10)), str(rng.randint(0, 10)), str(rng.randint(0, 5)),
                      gpu=k % 7 == 0, runtime=str(rng.randint(20, 60))) for k in range(32)]
        validate(CAND, candidates(*ideas))
        first = rank_weighted(candidates(*ideas), rubric())
        rng.shuffle(ideas)
        second = rank_weighted(candidates(*ideas), rubric())
        self.assertEqual(first['ranking'], second['ranking'])
        self.assertEqual(len(first['rows']), 32)
        with self.assertRaises(ContractError):
            validate(CAND, candidates(*[idea('j%02d' % k, '1', '1', '1') for k in range(33)]))

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, 'No eligible'):
            rank_weighted(candidates(idea('a', '1', '1', '1', gpu=True)), rubric())
        with self.assertRaisesRegex(ValueError, 'unique'):
            rank_weighted(candidates(idea('a', '1', '1', '1'), idea('a', '2', '2', '2')), rubric())
        broken = idea('a', '1', '1', '1')
        del broken['assessments']['expected_cost']
        with self.assertRaisesRegex(ValueError, 'lacks'):
            rank_weighted(candidates(broken), rubric())
        with self.assertRaisesRegex(ValueError, 'rational'):
            rank_weighted(candidates(idea('a', 'ten', '1', '1')), rubric())


class WeightedCarrierAndChecksTests(unittest.TestCase):
    def setUp(self):
        self.cand = candidates(idea('b', '6', '6', '3'), idea('c', '6', '6', '3'), idea('e', '10', '10', '0'),
                               idea('a', '10', '10', '0', deps=('bad-engine',)), idea('d', '8', '6', '4', gpu=True))
        self.rub = rubric()

    def result(self):
        _, value = run_carrier(self.cand, self.rub, narration(self.cand))
        return value

    def check(self, result, cand=None):
        class Ctx:
            output_refs = {'screening_result': {'id': 'o', 'sha256': 'b' * 64}}

            def input_ref(self, name):
                return {'id': 'in-' + name, 'sha256': 'a' * 64}
        outcomes = asyncio.run(WeightedScreeningChecks()(Ctx(), {'candidate_set': cand or self.cand, 'screening_rubric': self.rub},
                                                         {'screening_result': result}))
        return {r['check_id']: r['outcome'] for r in outcomes}

    def test_carrier_every_id_ranked_or_excluded_and_checks_pass(self):
        ctx, value = run_carrier(self.cand, self.rub, narration(self.cand))
        validate(RESULT, value)
        self.assertEqual([s['idea_id'] for s in value['scores']], ['b', 'c', 'e', 'a', 'd'])
        for row in value['scores']:
            self.assertTrue(row['eligible'] == (not row['violations']))
            self.assertTrue(row['disposition_reason'])
        self.assertEqual(value['selected_idea_id'], 'e')
        self.assertEqual(self.check(value), {key: 'PASS' for key in CHECK_IDS})
        self.assertEqual(ctx.hosted[0][0], 'screening_result')
        # The model sees the host computation and is told not to alter it.
        self.assertIn('host_computation', ctx.prompts[0][0])

    def test_model_cannot_change_totals_or_ranking(self):
        reply = lambda prompt: {'assessments': [{'idea_id': i['idea_id'], 'assessment': 'Ranked first with total 99.'}
                                                for i in self.cand['ideas']], 'opportunity_statement': 'x'}
        _, value = run_carrier(self.cand, self.rub, reply)
        self.assertEqual(value['ranking'][0], {'rank': 1, 'idea_id': 'e', 'weighted_total': '9'})
        self.assertEqual(self.check(value), {key: 'PASS' for key in CHECK_IDS})

    def test_missing_or_duplicate_assessment_halts_with_invalid_output(self):
        short = lambda prompt: {'assessments': [{'idea_id': 'e', 'assessment': 'x'}], 'opportunity_statement': 'y'}
        with self.assertRaises(ResearchError) as caught:
            run_carrier(self.cand, self.rub, short)
        self.assertEqual(caught.exception.code, 'invalid_output')

    def test_no_eligible_halts_before_any_model_call(self):
        cand = candidates(idea('a', '1', '1', '1', gpu=True))
        ctx = StubContext(lambda p: self.fail('model must not be called'))
        carrier = WeightedScreeningCarrier(rank_weighted, ctx.helper, ctx.prompt)
        with self.assertRaises(ResearchError) as caught:
            asyncio.run(carrier.execute(ctx, {'candidate_set': cand, 'screening_rubric': self.rub}))
        self.assertEqual(caught.exception.code, 'no_eligible_idea')

    def test_checks_reject_each_tampering(self):
        def mutate(change):
            value = copy.deepcopy(self.result())
            change(value)
            return self.check(value)

        def swap(v):
            v['ranking'][0], v['ranking'][1] = v['ranking'][1], v['ranking'][0]

        def wrong_total(v):
            v['scores'][0]['weighted_total'] = '52/10'

        def drop(v):
            v['scores'] = v['scores'][:-1]

        def wrong_value(v):
            v['scores'][0]['values']['novelty'] = '7'

        def unexclude(v):
            row = next(s for s in v['scores'] if s['idea_id'] == 'd')
            row.update(violations=[], eligible=True, disposition='eligible')

        def bad_selected(v):
            v['selected_idea_id'] = 'b'

        self.assertEqual(mutate(swap)['ranking_recomputable'], 'FAIL')
        self.assertEqual(mutate(wrong_total)['totals_recomputed'], 'FAIL')
        self.assertEqual(mutate(drop)['ids_accounted'], 'FAIL')
        self.assertEqual(mutate(wrong_value)['values_match_inputs'], 'FAIL')
        self.assertEqual(mutate(unexclude)['exclusions_recomputed'], 'FAIL')
        self.assertEqual(mutate(bad_selected)['ranking_recomputable'], 'FAIL')

    def test_checks_agree_with_ranker_on_random_inputs(self):
        rng = random.Random(11)
        for _ in range(40):
            ideas = [idea('n%02d' % k, str(rng.randint(0, 9)), str(rng.randint(0, 9)), str(rng.randint(0, 4)),
                          gpu=rng.random() < .2, lic=rng.choice(['MIT', 'GPL-3.0']), runtime=str(rng.randint(30, 55)),
                          deps=rng.choice([('numpy',), ('bad-engine',)])) for k in range(rng.randint(2, 12))]
            cand = candidates(*ideas)
            try:
                _, value = run_carrier(cand, self.rub, narration(cand))
            except ResearchError as exc:
                self.assertEqual(exc.code, 'no_eligible_idea')
                continue
            self.assertEqual(self.check(value, cand), {key: 'PASS' for key in CHECK_IDS})


class WeightedReleaseTests(unittest.TestCase):
    def test_release_is_additive_and_passes_library_association(self):
        from jiuwenswarm.research.library import LibraryService
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteRunStore(temp)
            try:
                old = build_research_assets(store)
                new = build_research_assets(store, screening_version='m1-6')
                self.assertEqual(json.loads(json.dumps(old['screening'])), load_research_catalog()['stages']['screening'])
                self.assertNotEqual(old['screening']['declaration_ref'], new['screening']['declaration_ref'])
                declaration = store.read_record(new['screening']['declaration_ref'])
                self.assertEqual(declaration['identity']['version_label'], 'm1-6')
                self.assertEqual([p['name'] for p in declaration['ports']['outputs']], ['screening_result'])
                for stage in old:
                    if stage != 'screening':
                        self.assertEqual(old[stage], new[stage])
                # m1-5 stays reachable and unchanged beside m1-6.
                five = build_research_assets(store, screening_version='m1-5')['screening']
                self.assertEqual(store.read_record(five['declaration_ref'])['identity']['version_label'], 'm1-5')
                LibraryService(store)._validate_association(new['screening']['declaration_ref'], new['screening']['bundle_ref'],
                                                            new['screening']['profile_ref'])
                bundle = store.read_record(new['screening']['bundle_ref'])
                self.assertEqual([c['check_id'] for c in bundle['checks']], list(CHECK_IDS))
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
