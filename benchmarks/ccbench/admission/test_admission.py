import contextlib
import copy
import importlib
import inspect
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import derive
from derive import derive_tests
from oracle import expected, matches, tagged, rounded_decimal
from reference import calculate, table_normalize
import study
from study import assess, load_declarations, thin, bootstrap
from usage import typical_use

ROOT = Path(__file__).resolve().parent


class AdmissionTests(unittest.TestCase):
    def test_derivation_pure_and_serializable(self):
        for d in load_declarations().values():
            original = copy.deepcopy(d)
            baseline = derive_tests(d)
            with patch('builtins.open', side_effect=AssertionError('I/O forbidden')), patch('random.random', side_effect=AssertionError('random forbidden')):
                again = derive_tests(json.loads(json.dumps(d)))
            self.assertEqual(d,original)
            self.assertEqual(baseline,again)
            self.assertEqual(baseline,json.loads(json.dumps(baseline)))
            again[0]['input'].clear()
            self.assertEqual(baseline,derive_tests(d))

    def test_derivation_ignores_identity_and_candidate_catalog(self):
        for d in load_declarations().values():
            renamed = copy.deepcopy(d)
            renamed['identity'] = {'name':'unseen.generic.tool','kind':'tool'}
            self.assertEqual(derive_tests(d),derive_tests(renamed))
        source = inspect.getsource(derive)
        self.assertNotIn('ground_truth',source)
        self.assertNotIn('candidates', '\n'.join(line for line in source.splitlines() if line.startswith(('import ', 'from '))))

    def test_contract_changes_generation(self):
        d = load_declarations()['calculate']
        modified = copy.deepcopy(d)
        modified['ports']['inputs']['operation'] = ['count']
        tests = derive_tests(modified)
        self.assertTrue(all(t['input']['operation']=='count' for t in tests))
        self.assertNotEqual(derive_tests(d),tests)
        self.assertLess(len(derive_tests(thin(d))),len(derive_tests(d)))

    def test_both_references_admitted(self):
        for tool,d in load_declarations().items():
            fn = calculate if tool == 'calculate' else table_normalize
            for contract in [d,thin(d)]:
                admitted,evidence = assess(tool,fn,derive_tests(contract))
                self.assertTrue(admitted,[e for e in evidence if not e['pass']][:3])

    def test_every_defect_independent_witness(self):
        labels = json.loads((ROOT/'ground_truth.json').read_text(encoding='utf-8'))
        self.assertEqual(16,len(labels))
        self.assertEqual(14,sum(r['defective'] for r in labels))
        for row in labels:
            fn = importlib.import_module('candidates.'+row['candidate']).run
            if row['defective']:
                p = row['witness']
                want = expected(row['tool'],p)
                if row['tool']=='calculate' and want['status']=='ok':
                    self.assertTrue(matches(row['tool'],p,row['expected']),row['candidate'])
                else: self.assertEqual(tagged(want),tagged(row['expected']),row['candidate'])
                self.assertFalse(matches(row['tool'],p,fn(p)),row['candidate'])

    def test_reference_on_typical_distribution(self):
        for tool,fn in [('calculate',calculate),('table_normalize',table_normalize)]:
            rng = random.Random(716)
            for _ in range(300):
                p = typical_use(tool,rng)
                self.assertTrue(matches(tool,p,fn(p)),p)

    def test_type_identity(self):
        p = {'format':'json','columns':['x'],'delimiter':None,'text':'[{"x":true}]'}
        self.assertFalse(matches('table_normalize',p,{'status':'ok','columns':['x'],'rows':[[1]]}))

    def test_integer_rounding_ties(self):
        from fractions import Fraction
        self.assertEqual('12e-1',rounded_decimal(Fraction('1.25'),2))
        self.assertEqual('14e-1',rounded_decimal(Fraction('1.35'),2))
        self.assertEqual('-12e-1',rounded_decimal(Fraction('-1.25'),2))

    def test_bootstrap_deterministic(self):
        self.assertEqual(bootstrap([1,2,3]),bootstrap([1,2,3]))
        self.assertEqual([4,4],bootstrap([4]*100)['bootstrap_95_ci'])

    def test_usage_reproducible(self):
        for tool in load_declarations():
            a,b = random.Random(918),random.Random(918)
            self.assertEqual([typical_use(tool,a) for _ in range(20)],[typical_use(tool,b) for _ in range(20)])

    def test_recorded_metrics_reconcile(self):
        reps = 5
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            study.run(tmp, reps)
            summary = json.loads((Path(tmp)/'results.json').read_text(encoding='utf-8'))
            trials = {route:json.loads((Path(tmp)/(route.lower()+'_trials.json')).read_text(encoding='utf-8')) for route in ['CC','CC_THIN','SKILL']}
        labels = json.loads((ROOT/'ground_truth.json').read_text(encoding='utf-8'))
        for route in ['CC','CC_THIN','SKILL']:
            rows = trials[route]
            self.assertEqual(16*reps,len(rows))
            for r in rows:
                self.assertEqual(r['failures_delivered_through_detection'],sum(not h['correct'] for h in r['history']))
                self.assertLessEqual(len(r['history']),20)
                self.assertEqual(r['defective'],next(l['defective'] for l in labels if l['candidate']==r['candidate']))
                if r['first_failure_use'] is not None:
                    self.assertEqual(r['first_failure_use'],len(r['history']))
                    self.assertFalse(r['history'][-1]['correct'])
                for h in r['history']:
                    self.assertEqual(h['correct'],matches(r['tool'],h['input'],h['actual']))
            count = sum(r['defective'] and r['admitted'] for r in rows)/reps
            self.assertEqual(count,summary[route]['defects_admitted']['mean'])


if __name__ == '__main__': unittest.main(verbosity=2)
