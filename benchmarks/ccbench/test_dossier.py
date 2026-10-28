"""Self-test for dossier.py. Tiny hand-made run folders in temp directories; no model, no docker, nothing written beside the source."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

import dossier

DEFECTS = ['a_defect', 'infeasible_task_planned_anyway']


def wj(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=1) + '\n').encode('utf-8'))


def wt(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))


def lines(path):
    return [json.loads(x) for x in Path(path).read_bytes().decode('utf-8').splitlines() if x.strip()]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.run_dir = self.tmp / 'run'
        self.out = self.tmp / 'dossier'
        self.run_dir.mkdir()

    def dossier(self, bench, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return dossier.main([bench, '--run', str(self.run_dir), '--out', str(self.out)] + list(extra))

    def claims(self):
        return json.loads((self.out / 'claims.json').read_bytes().decode('utf-8'))

    def run_json(self, case):
        return json.loads((self.out / case / 'run.json').read_bytes().decode('utf-8'))

    def write_meta(self, commit='abc123def456', dirty=False):
        wj(self.run_dir / 'run-meta' / '20261028T100000Z-bench-script.json', {
            'bench': 'bench', 'script': 'script', 'ai4r_bench_args': ['bench', 'script', '--out', 'x'], 'argv': ['--out', '/x'], 'mode': 'host',
            'started_at': '2026-10-28T10:00:00Z', 'finished_at': '2026-10-28T10:01:30Z', 'exit_code': 0,
            'product': {'root': '/r', 'commit': commit, 'dirty': dirty}})

    def assert_layout(self, case):
        d = self.out / case
        for name in ('score.json', 'run.json', 'case.md', 'input', 'ours', 'theirs', 'oracle', 'oracle/HOW.md', 'input/ARMS.md'):
            self.assertTrue((d / name).exists(), '%s missing %s' % (case, name))
        text = (d / 'case.md').read_bytes().decode('utf-8')
        for heading in ('what was asked', 'what we did', 'what they did', 'gold', 'verdict'):
            self.assertIn('## ' + heading, text)
        for target in re.findall(r'\]\(([^)]+)\)', text):
            self.assertTrue((d / target).exists(), 'dead link %s in %s' % (target, case))

    def assert_lf(self):
        for name in ('INDEX.md', 'claims.json', 'GAPS.md'):
            self.assertNotIn(b'\r', (self.out / name).read_bytes(), name)
        for case in self.out.iterdir():
            if case.is_dir():
                for name in ('case.md', 'score.json', 'run.json'):
                    self.assertNotIn(b'\r', (case / name).read_bytes(), name)

    def assert_run_untouched(self, before):
        self.assertEqual(before, sorted(str(p.relative_to(self.run_dir)) for p in self.run_dir.rglob('*')))


class AdmissionTest(Base):
    def row(self, cand, tool, defective, rep, admitted, pre, first, lag, fd):
        return {'candidate': cand, 'tool': tool, 'defective': defective, 'repeat': rep, 'admitted': admitted, 'pre_admitted': pre,
                'first_failure_use': first, 'right_censored': bool(pre and first is None), 'restricted_lag_20': lag,
                'failures_delivered_through_detection': int(first is not None), 'failures_strictly_before_detection': 0,
                'history': [{'use': 1, 'input': {'values': [1]}, 'actual': {'status': 'ok'}, 'correct': first != 1}] if pre else []}

    def make(self, defects_admitted=0.5):
        ref, bad = 'calculate_reference', 'calculate_absolute'
        wj(self.run_dir / 'ground_truth.json', [
            {'candidate': ref, 'tool': 'calculate', 'defective': False, 'witness': None, 'expected': None, 'defect': 'correct'},
            {'candidate': bad, 'tool': 'calculate', 'defective': True, 'witness': {'values': [-7, 2]}, 'expected': {'status': 'ok', 'value': '-5'}, 'defect': 'broad: signs discarded'}])
        cc = [self.row(ref, 'calculate', False, r, True, True, None, 20, 0) for r in (0, 1)] + [self.row(bad, 'calculate', True, r, False, False, None, 0, 0) for r in (0, 1)]
        sk = ([self.row(ref, 'calculate', False, r, True, True, None, 20, 0) for r in (0, 1)]
              + [self.row(bad, 'calculate', True, 0, False, True, 3, 3, 1), self.row(bad, 'calculate', True, 1, True, True, None, 20, 0)])
        wj(self.run_dir / 'cc_trials.json', cc)
        wj(self.run_dir / 'skill_trials.json', sk)

        def m(v):
            return {'mean': v, 'bootstrap_95_ci': [v, v]}
        wj(self.run_dir / 'results.json', {
            'CC': {'defects_admitted': m(0), 'defects_rejected': m(1), 'false_rejections': m(0), 'failures_delivered_through_detection': m(0),
                   'failures_strictly_before_detection': m(0), 'restricted_lag_20': m(0), 'conditional_observed_lag_mean': None, 'detected_during_use_candidate_repeats': 0},
            'SKILL': {'defects_admitted': m(defects_admitted), 'defects_rejected': m(0.5), 'false_rejections': m(0), 'failures_delivered_through_detection': m(0.5),
                      'failures_strictly_before_detection': m(0), 'restricted_lag_20': m(11.5), 'conditional_observed_lag_mean': 3.0, 'detected_during_use_candidate_repeats': 1}})
        wj(self.run_dir / 'frozen_manifest.json', {'seed': 1, 'N': 20, 'repetitions': 2, 'files': {}})

    def test_builds_cases_and_claims(self):
        self.make()
        before = sorted(str(p.relative_to(self.run_dir)) for p in self.run_dir.rglob('*'))
        self.assertEqual(self.dossier('admission'), 0)
        self.assert_run_untouched(before)
        self.assertEqual(sorted(p.name for p in self.out.iterdir() if p.is_dir()), ['calculate_absolute', 'calculate_reference'])
        for case in ('calculate_absolute', 'calculate_reference'):
            self.assert_layout(case)
        score = json.loads((self.out / 'calculate_absolute' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(score['ours']['class'], 'correct_stop')
        self.assertEqual(score['theirs']['class_counts'], {'correct_stop': 1, 'wrong_delivered': 1})
        self.assertEqual(score['theirs']['failures_delivered_before_stop'], 1)
        run = json.loads((self.out / 'calculate_absolute' / 'run.json').read_bytes().decode('utf-8'))
        self.assertEqual(run['command'], 'not recorded')
        self.assertEqual(run['product_commit'], 'not recorded')
        self.assertTrue(self.claims()['all_match'])
        self.assertTrue((self.out / 'calculate_absolute' / 'theirs' / 'skill_example_rep00.json').exists())
        self.assert_lf()

    def test_mismatch_is_loud(self):
        self.make(defects_admitted=0.25)
        self.assertEqual(self.dossier('admission'), 1)
        claims = self.claims()
        self.assertFalse(claims['all_match'])
        self.assertEqual(claims['mismatches'], ['SKILL.defects_admitted'])
        self.assertIn('CLAIM MISMATCH', (self.out / 'INDEX.md').read_bytes().decode('utf-8'))


class GatebenchTest(Base):
    def rec(self, policy, version, kind, accepted, regression=False, escape=False, improvement=False, cost=5):
        return {'tool': 'calculate', 'seed': 0, 'policy': policy, 'accepted': accepted, 'reason': 'x', 'regression': regression, 'tampering': False, 'escape': escape,
                'true_improvement': improvement, 'heldout_errors': 0, 'heldout_cost': cost, 'parent_cost': 10, 'new_failing_indices': [], 'visible_errors': 0,
                'parent_errors': 0, 'parent_body_sha256': 'p', 'effect_observations': [],
                'candidate': {'version': version, 'kind': kind, 'patch': {'body': {'memo': {}}}, 'self_score': version, 'sha256': 's%d' % version}}

    def make(self, a_regs=1):
        att = [self.rec('A', 1, 'improvement', True, improvement=True), self.rec('B', 1, 'improvement', True, improvement=True),
               self.rec('A', 2, 'outside-write', True, regression=True, escape=True, cost=12), self.rec('B', 2, 'outside-write', False, cost=12)]
        wt(self.run_dir / 'attempts.jsonl', ''.join(json.dumps(a, sort_keys=True) + '\n' for a in att))

        def metrics(**kw):
            base = {'accepted': 1, 'accepted_regressions': 0, 'accepted_tampering': 0, 'accepted_gaming_attempts': 0, 'accepted_visible_overfits': 0,
                    'accepted_correctness_regressions': 0, 'accepted_cost_regressions': 0, 'accepted_containment_escapes': 0, 'true_improvement_opportunities': 1,
                    'false_rejections': 0, 'dominated_improvements': 0, 'net_heldout_gain': 0.5, 'final_errors': 0, 'final_cost': 5, 'baseline_cost': 10, 'raw_cost_gain': 0.5}
            base.update(kw)
            return base
        a = metrics(accepted=2, accepted_regressions=a_regs, accepted_gaming_attempts=1, accepted_cost_regressions=1, accepted_containment_escapes=1)
        wj(self.run_dir / 'pairs.json', [{'tool': 'calculate', 'seed': 0, 'metrics': {'A': a, 'B': metrics()}}])

        def row(p, m):
            r = {'tool': 'calculate', 'policy': p, 'seeds': 1, 'candidate_versions': 2}
            r.update({k: m[k] for k in m if k not in ('final_errors', 'final_cost', 'baseline_cost', 'raw_cost_gain')})
            r.update(bootstrap_95_ci=[0.5, 0.5], final_incorrect_seeds=0, mean_raw_cost_gain=0.5)
            return r
        wj(self.run_dir / 'summary.json', {'series': 'scripted', 'model': None, 'seed_range': [0, 0], 'bootstrap_repeats': 2000, 'bootstrap_seed': 73017,
                                            'rows': [row('A', a), row('B', metrics())]})
        wj(self.run_dir / 'fixtures.json', {'calculate': {'declaration': {'tool': 'calculate'}, 'visible': [], 'hidden_sha256_by_seed': ['h0']}})

    def test_builds_tool_case(self):
        self.make()
        self.assertEqual(self.dossier('gatebench'), 0)
        self.assert_layout('calculate')
        score = json.loads((self.out / 'calculate' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(score['ours']['class_counts'], {'correct_delivered': 1, 'correct_stop': 1})
        self.assertEqual(score['theirs']['class_counts'], {'correct_delivered': 1, 'wrong_delivered': 1})
        self.assertEqual(len(lines(self.out / 'calculate' / 'theirs' / 'example_seed0_attempts.jsonl')), 2)
        self.assertTrue(self.claims()['all_match'])
        self.assert_lf()

    def test_heldout_requests_and_run_meta_reach_the_case(self):
        self.make()
        wj(self.run_dir / 'heldout' / 'calculate-seed0.json', {'tool': 'calculate', 'seed': 0, 'sha256': 'h0', 'requests': [{'rows': [['1']]}]})
        self.write_meta()
        self.assertEqual(self.dossier('gatebench'), 0)
        self.assertEqual(json.loads((self.out / 'calculate' / 'oracle' / 'heldout' / 'calculate-seed0.json').read_bytes())['sha256'], 'h0')
        run = self.run_json('calculate')
        self.assertEqual(run['product_commit'], 'abc123def456')
        self.assertEqual((run['started_at'], run['finished_at'], run['wall_time_s']), ('2026-10-28T10:00:00Z', '2026-10-28T10:01:30Z', 90.0))
        self.assertEqual(run['command'], ['ai4r-bench bench script --out x'])
        gaps = (self.out / 'GAPS.md').read_bytes().decode('utf-8')
        self.assertNotIn('not stored', gaps)
        self.assertIn('oracle/heldout/', gaps)

    def test_without_heldout_or_meta_the_old_statements_stay(self):
        self.make()
        self.assertEqual(self.dossier('gatebench'), 0)
        self.assertEqual(self.run_json('calculate')['product_commit'], 'not recorded')
        self.assertIn('not stored', (self.out / 'GAPS.md').read_bytes().decode('utf-8'))
        self.assertFalse((self.out / 'calculate' / 'oracle' / 'heldout').exists())

    def test_mismatch_is_loud(self):
        self.make(a_regs=3)
        self.assertEqual(self.dossier('gatebench'), 1)
        self.assertIn('calculate.A.accepted_regressions', self.claims()['mismatches'])


class TrapcheckTest(Base):
    def make(self, stop_causes=('baseline_definition_conflict',)):
        data = self.tmp / 'evidence'
        sess = data / 'traps' / 'sessions'
        for sid, trap in (('aaaaaaaa11112222', 'baselinedef'), ('bbbbbbbb11112222', 'clean')):
            s = sess / ('trap-' + sid)
            wj(s / 'fixture' / 'cases.json', {'cases': [{'task': 't'}]})
            wt(s / 'fixture' / 'inputs' / 'README.md', 'readme')
            wj(s / 'native' / 'spec.json', {'task': 'Do the task.', 'model': 'gpt-6.1-sol', 'max_model_calls': 80, 'reasoning_effort': 'medium'})
            wj(s / 'native' / 'run' / 'result.json', {'status': 'completed', 'model_calls': 2})
            wj(s / 'native' / 'run' / 'controller-start.json', {'started_at': '2026-10-27T02:00:00+00:00'})
            wj(s / 'native' / 'run' / 'controller-finished.json', {'finished_at': '2026-10-27T02:01:00+00:00', 'elapsed_s': 60.0})
            wt(s / 'native' / 'run' / 'events.jsonl', json.dumps({'payload': {'event_type': 'chat.final', 'content': 'final report ' + trap}}) + '\n')
            wj(s / 'native' / 'broker' / 'r1.response.json', {'usage': {'input_tokens': 10, 'output_tokens': 2}, 'elapsed_s': 1.5})
            wj(s / 'private-measurement' / 'scored-response.json', {'scientific_outcome': 'PASS'})
        wj(data / 'traps' / 'baselinedef' / 'expected.json', {'trap_id': 'baselinedef'})
        wt(data / 'traps' / 'baselinedef' / 'README.md', 'fixture readme')
        rows = [{'session': 'trap-aaaaaaaa11112222', 'trap': 'baselinedef', 'expected_cause': 'baseline_definition_conflict', 'native_delivered': True,
                 'native_scientific_outcome': 'PASS', 'C_stop_checks': ['baseline'] if stop_causes else [], 'C_stop_causes': list(stop_causes), 'C_abstain_checks': [],
                 'naive_extra_pin_failures': []},
                {'session': 'trap-bbbbbbbb11112222', 'trap': 'clean', 'expected_cause': None, 'native_delivered': False, 'native_scientific_outcome': None,
                 'C_stop_checks': [], 'C_stop_causes': [], 'C_abstain_checks': [], 'naive_extra_pin_failures': []}]
        wj(self.run_dir / 'results.json', rows)
        wt(self.run_dir / 'RESULTS.md', '\n'.join([
            '| Count | Value |', '|---|---|',
            '| Fault runs where native delivered results as valid | 1 of 1 (baselinedef) |',
            '| C would stop delivery, right fault, right reason | 1 of 1 delivered |',
            '| Wrong-reason stops by C | 0. Each stop matches. |',
            '| C false stops on clean controls (1 run) | 0 of 1 |',
            '| C false stops if all pins are checked naively | 0 of 1. |',
            '| Numeric-claim check stops | 0 of 1 delivered reports |', '']))
        return data

    def test_builds_session_cases(self):
        data = self.make()
        before = sorted(str(p.relative_to(self.run_dir)) for p in self.run_dir.rglob('*'))
        self.assertEqual(self.dossier('trapcheck', '--data', str(data)), 0)
        self.assert_run_untouched(before)
        for case in ('baselinedef-aaaaaaaa', 'clean-bbbbbbbb'):
            self.assert_layout(case)
        score = json.loads((self.out / 'baselinedef-aaaaaaaa' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(score['ours']['class'], 'correct_stop')
        self.assertEqual(score['theirs']['class'], 'wrong_delivered')
        clean = json.loads((self.out / 'clean-bbbbbbbb' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(clean['ours']['class'], 'correct_delivered')
        self.assertEqual(clean['theirs']['class'], 'stop_unjudged')
        run = json.loads((self.out / 'baselinedef-aaaaaaaa' / 'run.json').read_bytes().decode('utf-8'))
        self.assertEqual(run['tokens']['input_tokens'], 10)
        self.assertEqual(run['image'], 'not recorded')
        self.assertEqual((self.out / 'baselinedef-aaaaaaaa' / 'theirs' / 'final_message.txt').read_bytes(), b'final report baselinedef')
        self.assertTrue(self.claims()['all_match'], self.claims())
        self.assert_lf()

    def test_replay_provenance_is_recorded(self):
        data = self.make()
        wj(self.run_dir / 'results-provenance.json', {'integrity_py_sha256': 'f' * 64, 'delivery_evidence_py_sha256': 'e' * 64, 'run_py_sha256': 'd' * 64,
                                                      'product_commit': 'abc123def456', 'product_dirty': True})
        self.assertEqual(self.dossier('trapcheck', '--data', str(data)), 0)
        replay = self.run_json('baselinedef-aaaaaaaa')['ours_replay']
        self.assertEqual((replay['product_commit'], replay['integrity_py_sha256'], replay['product_dirty']), ('abc123def456', 'f' * 64, True))
        self.assertIn('results-provenance.json', (self.out / 'GAPS.md').read_bytes().decode('utf-8'))

    def test_wrong_reason_stop_changes_claim(self):
        data = self.make(stop_causes=('metric_unit_conflict',))
        self.assertEqual(self.dossier('trapcheck', '--data', str(data)), 1)
        self.assertIn('c_wrong_reason', self.claims()['mismatches'])
        score = json.loads((self.out / 'baselinedef-aaaaaaaa' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(score['ours']['class'], 'wrong_stop')


class PlannerTest(Base):
    def counts(self, **kw):
        c = {d: 0 for d in DEFECTS}
        c.update(kw)
        return c

    def make(self):
        base = self.run_dir / 'runs' / 'm1'
        wj(base / 'manifest.json', {'library': {'library_snapshot': {}}, 'tasks': [{'id': 't1'}, {'id': 't2'}], 'repeats': 1, 'model': 'm1',
                                    'expected': {'t1': {'feasible': True, 'category': 'normal', 'required_capabilities': ['x'], 'missing_capability_or_input': None},
                                                 't2': {'feasible': False, 'category': 'infeasible', 'required_capabilities': [], 'missing_capability_or_input': 'gpu'}}})
        replies = {('t1', 'A'): '{"nodes": []}', ('t1', 'B'): '{"nodes": []}', ('t2', 'A'): 'INFEASIBLE: needs a gpu', ('t2', 'B'): '{"nodes": [1]}'}
        for (tid, cond), reply in replies.items():
            d = base / tid / (cond + '-r1')
            wt(d / 'prompt.txt', 'prompt %s %s' % (tid, cond))
            wt(d / 'reply.txt', reply)
            wj(d / 'run.json', {'task': tid, 'condition': cond, 'model': 'm1', 'command': ['codex', 'exec'], 'elapsed_s': 2.0, 'tokens_used': ['1,234'],
                                'prompt': {'sha256': dossier.hashlib.sha256(('prompt %s %s' % (tid, cond)).encode()).hexdigest(), 'bytes': 11},
                                'raw_reply_sha256': dossier.hashlib.sha256(reply.encode()).hexdigest()})

        def plan(tid, cond, valid, handling, mc, tot, counts):
            return {'task': tid, 'condition': cond, 'repeat': 1, 'expected_feasible': tid == 't1', 'raw_reply': 'x',
                    'score': {'valid': valid, 'defects': [], 'counts': counts, 'machine_checkable': mc, 'acceptance_total': tot, 'capability_set': ['x'],
                              'infeasible_handling_correct': handling}}
        plans = [plan('t1', 'A', True, True, 2, 2, self.counts()), plan('t1', 'B', True, True, 3, 3, self.counts()),
                 plan('t2', 'A', True, True, 0, 0, self.counts()), plan('t2', 'B', False, False, 0, 1, self.counts(infeasible_task_planned_anyway=1))]
        agg_a = {'plans': 2, 'validity_rate': 1.0, 'defects_per_plan': {d: 0.0 for d in DEFECTS}, 'infeasible_handling_accuracy': 1.0,
                 'overall_feasibility_decision_accuracy': 1.0, 'acceptance_machine_checkable_fraction': 1.0, 'run_to_run_stability': None}
        agg_b = {'plans': 2, 'validity_rate': 0.5, 'defects_per_plan': {'a_defect': 0.0, 'infeasible_task_planned_anyway': 0.5}, 'infeasible_handling_accuracy': 0.0,
                 'overall_feasibility_decision_accuracy': 0.5, 'acceptance_machine_checkable_fraction': 0.75, 'run_to_run_stability': None}
        wj(self.run_dir / 'scores' / 'm1.json', {'model': 'm1', 'plans': plans, 'aggregate': {'A': agg_a, 'B': agg_b}})

    def test_builds_task_cases(self):
        self.make()
        self.assertEqual(self.dossier('planner'), 0)
        for case in ('m1__t1__r1', 'm1__t2__r1'):
            self.assert_layout(case)
        s2 = json.loads((self.out / 'm1__t2__r1' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual((s2['ours']['class'], s2['theirs']['class']), ('correct_stop', 'wrong_delivered'))
        s1 = json.loads((self.out / 'm1__t1__r1' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual((s1['ours']['class'], s1['theirs']['class']), ('correct_delivered', 'correct_delivered'))
        run = json.loads((self.out / 'm1__t1__r1' / 'run.json').read_bytes().decode('utf-8'))
        self.assertEqual(run['arms']['ours']['tokens'], {'total_reported_by_codex': 1234})
        self.assertTrue(run['arms']['ours']['integrity']['prompt_sha256_matches'])
        self.assertTrue(self.claims()['all_match'], self.claims()['mismatches'])
        self.assert_lf()

    def test_infeasible_detector(self):
        self.assertTrue(dossier.reply_infeasible('INFEASIBLE: no'))
        self.assertTrue(dossier.reply_infeasible('{"infeasible": true, "reason": "x"}'))
        self.assertFalse(dossier.reply_infeasible('{"nodes": []}'))


class NativeadmitTest(Base):
    def make(self, with_native):
        halt = {'id': 'calc_truncate', 'tool': 'calculate', 'route': 'CC', 'admitted': False, 'tests_run': 220, 'failed_tests': 7,
                'failed_test_evidence': [{'test': {}, 'actual': {}, 'oracle_expected': {}}], 'delivered_answer': None, 'halt_reason': 'admission failed'}
        ok = {'id': 'calc_reference', 'tool': 'calculate', 'route': 'CC', 'admitted': True, 'tests_run': 220, 'failed_tests': 0,
              'failed_test_evidence': [], 'delivered_answer': '1.6875', 'halt_reason': None}
        wj(self.run_dir / 'cc' / 'calc_truncate.json', halt)
        wj(self.run_dir / 'cc' / 'calc_reference.json', ok)
        zero = {c: 0 for c in ('correct', 'justified_halt', 'wrong_halt', 'flagged_wrong', 'silent_wrong', 'unavailable')}
        wj(self.run_dir / 'score-cc.json', {'rows': [], 'metrics': {'counts': dict(zero, correct=1, justified_halt=1), 'delivered_precision': 1.0,
                                                                   'silent_wrong_rate': 0.0, 'utility': 1.0}})
        if with_native:
            s = self.run_dir / 'sessions' / 'nadm-calc_truncate-01'
            wt(s / 'final-message.txt', 'Answer: 250.785\n')
            wj(s / 'native' / 'spec.json', {'task': 't', 'model': 'gpt-6.1-sol'})
            wj(s / 'staging-receipt.json', {'image': {'tag': 'ai4r:ccbench-native', 'id': 'sha256:abc', 'repo_digests': []}})
            wj(s / 'plan.json', {'spec': {'model': 'gpt-6.1-sol'}, 'worker': ['docker', 'run'], 'broker': ['python']})
            wj(s / 'usage.json', [{'usage': {'input_tokens': 100, 'output_tokens': 5}}])
            wj(s / 'controller-start.json', {'started_at': '2026-10-28T01:00:00+00:00'})
            wj(s / 'controller-finished.json', {'finished_at': '2026-10-28T01:02:00+00:00', 'elapsed_s': 120.0})
            wt(s / 'project' / 'notes.txt', 'hi')

    def test_cc_only_writes_missing_native(self):
        self.make(False)
        self.assertEqual(self.dossier('nativeadmit'), 0)
        self.assertEqual(sorted(p.name for p in self.out.iterdir() if p.is_dir()), ['calc_reference', 'calc_truncate'])
        self.assert_layout('calc_truncate')
        self.assertTrue((self.out / 'calc_truncate' / 'theirs' / 'MISSING.md').exists())
        score = json.loads((self.out / 'calc_truncate' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(score['ours']['class'], 'correct_stop')
        self.assertEqual(score['theirs']['class'], 'missing')
        self.assertTrue(self.claims()['all_match'], self.claims()['mismatches'])
        self.assert_lf()

    def test_native_session_is_scored_and_recorded(self):
        self.make(True)
        self.assertEqual(self.dossier('nativeadmit'), 0)
        case = 'calc_truncate-r01'
        self.assert_layout(case)
        score = json.loads((self.out / case / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(score['theirs']['bench_class'], 'correct')
        self.assertEqual(score['theirs']['class'], 'correct_delivered')
        run = json.loads((self.out / case / 'run.json').read_bytes().decode('utf-8'))
        self.assertEqual(run['tokens']['input_tokens'], 100)
        self.assertEqual(run['image']['tag'], 'ai4r:ccbench-native')
        self.assertEqual(run['wall_time_s'], 120.0)
        self.assertTrue((self.out / case / 'theirs' / 'final-message.txt').exists())
        self.assertTrue((self.out / 'calc_reference' / 'theirs' / 'MISSING.md').exists())


class NativeadmitFullLayoutTest(Base):
    """The A-full collection: sessions/<item>-r<N>, attempts/<id>.json, cc/<item>.json, score files from `nativeadmit score`; no map.json."""

    make = NativeadmitTest.make

    def session(self, name, text):
        s = self.run_dir / 'sessions' / name
        wt(s / 'final-message.txt', text)
        wj(s / 'native' / 'spec.json', {'task': 't', 'model': 'gpt-6.1-sol'})
        wj(s / 'staging-receipt.json', {'image': {'tag': 'ai4r:ccbench-native', 'id': 'sha256:abc', 'repo_digests': []}})
        wj(s / 'plan.json', {'spec': {'model': 'gpt-6.1-sol'}, 'worker': ['docker', 'run'], 'broker': ['python']})
        wj(s / 'usage.json', [{'usage': {'input_tokens': 100, 'output_tokens': 5}}])
        wj(self.run_dir / 'attempts' / (name + '.json'), {'attempt_id': name, 'status': 'executed', 'product': {'commit': 'cafe0123cafe', 'dirty': True}})

    def test_item_rN_sessions_are_found_without_a_map(self):
        self.make(False)
        self.session('calc_truncate-r1', 'Answer: 250.785\n')
        self.session('calc_truncate-r2', 'Answer: 1\n')
        self.session('calc_truncate-r3', 'Answer: 250.785\n')
        self.write_meta()
        self.assertEqual(self.dossier('nativeadmit'), 0)
        folders = sorted(p.name for p in self.out.iterdir() if p.is_dir())
        self.assertEqual(folders, ['calc_reference', 'calc_truncate-r1', 'calc_truncate-r2', 'calc_truncate-r3'])
        classes = {f: json.loads((self.out / f / 'score.json').read_bytes())['theirs']['bench_class'] for f in folders if f != 'calc_reference'}
        self.assertEqual(classes, {'calc_truncate-r1': 'correct', 'calc_truncate-r2': 'silent_wrong', 'calc_truncate-r3': 'correct'})
        for f in folders:
            self.assert_layout(f)
        run = self.run_json('calc_truncate-r2')
        self.assertEqual(run['product_commit'], 'cafe0123cafe (working tree dirty)')       # the attempt record wins over run-meta
        self.assertEqual(run['image']['tag'], 'ai4r:ccbench-native')
        self.assertTrue((self.out / 'calc_truncate-r1' / 'theirs' / 'attempt_record.json').exists())
        self.assertTrue((self.out / 'calc_reference' / 'theirs' / 'MISSING.md').exists())
        self.assertEqual(self.run_json('calc_reference')['product_commit'], 'abc123def456')   # run-meta fills the offline arm
        self.assertTrue(self.claims()['all_match'], self.claims()['mismatches'])

    def test_summary_over_one_rep_is_matched_to_that_rep(self):
        self.make(False)
        self.session('calc_truncate-r1', 'Answer: 1\n')
        self.session('calc_truncate-r2', 'Answer: 250.785\n')
        zero = {c: 0 for c in ('correct', 'justified_halt', 'wrong_halt', 'flagged_wrong', 'silent_wrong', 'unavailable')}
        wj(self.run_dir / 'score-summary.json', {'native': {'rows': [{}], 'metrics': {'counts': dict(zero, correct=1), 'delivered_precision': 1.0,
                                                                                   'silent_wrong_rate': 0.0, 'utility': 1.0}}})
        self.assertEqual(self.dossier('nativeadmit'), 0)
        claims = {c['id']: c for c in self.claims()['claims']}
        self.assertEqual(claims['native.count.correct']['status'], 'match')
        self.assertIn('rep r2', claims['native.count.correct']['note'])
        self.assertIn('native.all_sessions.counts', claims)


class PlanbenchTest(Base):
    """A real scripted skill-arm run (run_arm.py --stub, no model), then score.py, then the dossier."""

    def test_skill_arm_run_and_missing_cc_arm(self):
        import os
        import subprocess
        import sys
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(dossier.HERE), str(dossier.HERE.parents[1])]), PYTHONDONTWRITEBYTECODE='1')
        bench = dossier.HERE / 'planbench'
        subprocess.run([sys.executable, '-B', str(bench / 'run_arm.py'), 'run', '--arm', 'skill', '--label', 'pt', '--tasks', 'sum_csv,need_median',
                        '--stub', 'good', '--skill-transport', 'codex', '--out', str(self.run_dir)], env=env, check=True, capture_output=True, cwd=self.tmp)
        subprocess.run([sys.executable, '-B', str(bench / 'run_arm.py'), 'score', '--label', 'pt', '--out', str(self.run_dir)], env=env, check=True, capture_output=True, cwd=self.tmp)
        self.write_meta()
        self.assertEqual(self.dossier('planbench'), 0)
        for case in ('pt__sum_csv', 'pt__need_median'):
            self.assert_layout(case)
            self.assertTrue((self.out / case / 'ours' / 'MISSING.md').exists())
            self.assertTrue((self.out / case / 'theirs' / 'reply.txt').exists())
        score = json.loads((self.out / 'pt__sum_csv' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual((score['theirs']['bench_class'], score['theirs']['class'], score['ours']['class']), ('correct', 'correct_delivered', 'missing'))
        need = json.loads((self.out / 'pt__need_median' / 'score.json').read_bytes().decode('utf-8'))
        self.assertEqual(need['theirs']['class'], 'correct_stop')
        self.assertEqual(self.run_json('pt__sum_csv')['product_commit'], 'abc123def456')
        self.assertTrue(self.claims()['all_match'], self.claims()['mismatches'])
        self.assertIn('pt__sum_csv', (self.out / 'GAPS.md').read_bytes().decode('utf-8'))      # stub rows are named
        self.assert_lf()


class GuardTest(Base):
    def test_out_inside_run_is_refused(self):
        with self.assertRaises(SystemExit):
            dossier.main(['admission', '--run', str(self.run_dir), '--out', str(self.run_dir / 'sub')])

    def test_large_input_becomes_a_reference(self):
        src = self.tmp / 'big.bin'
        src.write_bytes(b'x' * (dossier.LIMIT + 1))
        part = dossier.Part(self.tmp / 'part')
        part.copy(src, 'big.bin')
        part.close()
        listing = json.loads((self.tmp / 'part' / 'NOT-COPIED.json').read_bytes().decode('utf-8'))
        self.assertFalse((self.tmp / 'part' / 'big.bin').exists())
        self.assertEqual(listing['files'][0]['sha256'], dossier.sha256_file(src))
        part2 = dossier.Part(self.tmp / 'part2')
        part2.copy(self.tmp / 'nothing', 'nothing')
        part2.close()
        self.assertTrue((self.tmp / 'part2' / 'NOT-FOUND.json').exists())


if __name__ == '__main__':
    unittest.main()
