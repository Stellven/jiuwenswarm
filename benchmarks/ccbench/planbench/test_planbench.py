"""Offline tests: stub plans (good, unbindable, fabricated, infeasible) through both arms. No model, no Docker.

  python -B -m unittest discover -s planbench -p test_planbench.py -v     (product code from AI4R_CODE_ROOT)
"""
import sys
sys.dont_write_bytecode = True
import asyncio
import copy
import json
import re
import shutil
import tempfile
import importlib.util
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(tempfile.mkdtemp(prefix='planbench-test-'))     # every run, score and scratch file of these tests
sys.path.insert(0, str(HERE))
import caps
import executor
import normalize
import prompts
import run_arm
import score
import stubs

# The CC arm's NativePlanner needs the pinned openjiuwen runtime (installed in the bench image, usually not on the host).
needs_openjiuwen = unittest.skipUnless(importlib.util.find_spec('openjiuwen'), 'openjiuwen runtime not installed (runs in the container image)')

TASKS = {t['id']: t for t in json.loads((HERE / 'tasks.json').read_text('utf-8'))}
GOLD = json.loads((HERE / 'referee' / 'gold.json').read_text('utf-8'))
FEASIBLE = [t for t, g in GOLD.items() if g['feasible']]
INFEASIBLE = [t for t, g in GOLD.items() if not g['feasible']]
LEAK = ['result_schema', 'result_integrity', 'artifact_type', 'schema_ref', 'work_packet', 'urn:ai4r', 'declaration', 'check_id',
        'port_type', 'run_input_key', 'accepted_ref', 'future_output', 'cc_name', 'cc_version']


def has_token(token, text):
    return re.search(r'(?<![A-Za-z])' + re.escape(token) + r'(?![A-Za-z])', text) is not None


def run_neutral(task_id, variant):
    plan = stubs.neutral(TASKS[task_id], GOLD, variant)
    res = executor.execute(plan, TASKS[task_id], decoys=GOLD[task_id]['decoys']) if plan['kind'] == 'plan' else None
    ev = executor.evaluate(plan, res, GOLD[task_id]) if res and GOLD[task_id]['feasible'] else None
    return plan, res, ev


def tearDownModule():
    shutil.rmtree(OUT, ignore_errors=True)


class TaskSet(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(len(TASKS), 12)
        self.assertGreaterEqual(len(FEASIBLE), 7)
        self.assertGreaterEqual(len(INFEASIBLE), 3)
        self.assertLessEqual(len(INFEASIBLE) / 12, 0.5)          # SCORING-RULES 3.3 rule 4
        for kind in ('missing_capability', 'missing_input'):
            self.assertTrue(any(GOLD[t].get('category') == kind for t in INFEASIBLE))

    def test_reference_plans_execute_and_pass_the_referee(self):
        for t in FEASIBLE:
            with self.subTest(task=t):
                plan, res, ev = run_neutral(t, 'good')
                self.assertTrue(res['executed'], res['errors'])
                self.assertTrue(ev['final_correct'], ev)
                self.assertTrue(all(d['traced'] for d in ev['deliverables'].values()), ev)
                self.assertGreaterEqual(len(plan['steps']), 2)

    def test_near_duplicate_capability_gives_the_same_answer(self):
        plan = copy.deepcopy(GOLD['mean_report']['reference_plan'])
        plan['steps'][1]['capability'] = 'utility.calculate_typed'
        plan['steps'][0]['capability'] = 'utility.table_normalize_typed'
        plan['steps'][2]['capability'] = 'utility.packet_report'
        res = executor.execute(plan, TASKS['mean_report'])
        self.assertTrue(executor.evaluate(plan, res, GOLD['mean_report'])['final_correct'])

    def test_task_text_has_no_cc_vocabulary(self):
        for t in TASKS.values():
            for tok in LEAK:
                self.assertFalse(has_token(tok, t['request']), (t['id'], tok))
        for tok in LEAK:
            self.assertFalse(has_token(tok, prompts.FORMAT_BLOCK))

    def test_skill_pack_has_no_cc_vocabulary_and_matches_the_library(self):
        files = [p for p in (HERE / 'skillpack').rglob('*') if p.is_file() and 'plan-research-workflow' not in p.parts]
        self.assertGreaterEqual(len(files), 18)
        for p in files:
            text = p.read_text('utf-8')
            for tok in LEAK:
                self.assertFalse(has_token(tok, text), (p.name, tok))
        index = (HERE / 'skillpack' / 'SKILL.md').read_text('utf-8')
        for name in caps.all_names():
            self.assertIn('`%s`' % name, index)
        self.assertEqual((HERE / 'skillpack' / 'skills' / 'plan-research-workflow' / 'SKILL.md').read_bytes(),
                         (HERE.parent / 'skillpairs' / 'skills' / 'X3-plan' / 'SKILL.md').read_bytes())

    def test_skill_request_lists_every_capability(self):
        text = prompts.request_with_format(TASKS['sum_csv'])
        for name in caps.all_names():
            self.assertIn('`%s`' % name, text)
        for tok in LEAK:
            self.assertFalse(has_token(tok, prompts.capability_table()), tok)

    def test_capability_set_equals_the_cc_library(self):
        lib = run_arm.planner_library()
        selectable = {c['declaration']['identity']['name'] for c in lib['capsule_contracts']['capsules']}
        self.assertEqual(selectable, set(caps.all_names()))


class Executor(unittest.TestCase):
    def test_unbindable_is_a_body_rejection(self):
        for t in ('sum_csv', 'mean_report', 'json_minmax', 'pick_q2', 'normalize_report', 'pick_fahrenheit', 'table_ready'):
            plan, res, ev = run_neutral(t, 'unbindable')
            self.assertFalse(res['executed'], t)
            self.assertIn('body_rejected', {e['class'] for e in res['errors']}, (t, res['errors']))
            self.assertFalse(ev['final_correct'])

    def test_summary_passed_to_a_packet_capability_is_a_type_mismatch(self):
        plan, res, ev = run_neutral('summary_report', 'unbindable')
        self.assertIn('type_mismatch', {e['class'] for e in res['errors']})
        plan = copy.deepcopy(GOLD['summary_report']['reference_plan'])
        plan['steps'][0]['capability'] = 'utility.calculate'
        self.assertIn('type_mismatch', {e['class'] for e in executor.execute(plan, TASKS['summary_report'])['errors']})
        plan = copy.deepcopy(GOLD['sum_csv']['reference_plan'])
        plan['steps'][0]['capability'] = 'utility.summary_to_packet'
        self.assertIn('type_mismatch', {e['class'] for e in executor.execute(plan, TASKS['sum_csv'])['errors']})

    def test_fabricated_references(self):
        plan, res, ev = run_neutral('sum_csv', 'fabricated')
        classes = {e['class'] for e in res['errors']}
        self.assertIn('fabricated_capability', classes)
        self.assertIn('fabricated_input', classes)
        self.assertFalse(res['executed'])

    def test_unknown_step_cycle_and_non_executable(self):
        base = GOLD['sum_csv']['reference_plan']
        bad = copy.deepcopy(base)
        bad['steps'][1]['inputs'][0]['src'] = {'step': 'nope', 'output': 'result'}
        self.assertIn('missing_source', {e['class'] for e in executor.execute(bad, TASKS['sum_csv'])['errors']})
        cyc = copy.deepcopy(base)
        cyc['steps'][0]['inputs'][0]['src'] = {'step': 's2', 'output': 'result'}
        self.assertIn('cycle', {e['class'] for e in executor.execute(cyc, TASKS['sum_csv'])['errors']})
        ne = copy.deepcopy(base)
        ne['steps'][1]['capability'] = 'research.screening'
        self.assertIn('non_executable_capability', {e['class'] for e in executor.execute(ne, TASKS['sum_csv'])['errors']})

    def test_wrong_input_executes_but_is_wrong(self):
        plan, res, ev = run_neutral('pick_q2', 'wrong_input')
        self.assertTrue(res['executed'])
        self.assertIn('wrong_input_choice', {e['class'] for e in res['errors']})
        self.assertFalse(ev['final_correct'])

    def test_alias_errors_are_not_fatal(self):
        plan = copy.deepcopy(GOLD['sum_csv']['reference_plan'])
        plan['steps'][0]['capability'] = 'table_normalize'
        plan['steps'][0]['inputs'][0]['param'] = 'input'
        plan['steps'][1]['inputs'][0]['src']['output'] = 'normalized_packet'
        res = executor.execute(plan, TASKS['sum_csv'])
        self.assertTrue(res['executed'], res['errors'])
        self.assertEqual({e['class'] for e in res['errors']}, {'name_alias', 'param_alias', 'output_name_alias'})

    def test_report_before_calculation_fails(self):
        plan = copy.deepcopy(GOLD['mean_report']['reference_plan'])
        plan['steps'][1], plan['steps'][2] = plan['steps'][2], plan['steps'][1]
        plan['steps'][1]['inputs'][0]['src'] = {'step': 's1', 'output': 'result'}
        plan['steps'][2]['inputs'][0]['src'] = {'step': 's3', 'output': 'result'}
        plan['final'] = 's2'
        res = executor.execute(plan, TASKS['mean_report'])
        self.assertIn('body_rejected', {e['class'] for e in res['errors']})

    def test_machine_checkable_criteria(self):
        plan = copy.deepcopy(GOLD['sum_csv']['reference_plan'])
        plan['steps'][0]['criteria'] = ['data.table has the revenue column', 'looks fine']
        plan['steps'][1]['criteria'] = ['calculation_result.columns.revenue.sum is present', 'result_integrity']
        res = executor.execute(plan, TASKS['sum_csv'], checks={'utility.calculate': ['result_schema', 'result_integrity']})
        self.assertEqual(res['criteria']['total'], 4)
        self.assertEqual(res['criteria']['path_checkable'], 2)
        self.assertEqual(res['criteria']['check_id'], 1)
        self.assertEqual(res['criteria']['checkable'], 3)


class Parsers(unittest.TestCase):
    def skill(self, text, task='sum_csv'):
        return normalize.normalize_skill(text, TASKS[task])

    def test_prose_around_fenced_json(self):
        plan = stubs.neutral(TASKS['sum_csv'], GOLD, 'good')
        p = self.skill('Sure.\n```json\n' + stubs.to_skill_reply(plan, quirks=False) + '\n```\nDone.')
        self.assertEqual(p['kind'], 'plan')
        self.assertEqual([s['id'] for s in p['steps']], ['s1', 's2'])
        self.assertEqual(p['steps'][0]['inputs'][0]['src'], {'external': 'sales'})
        self.assertEqual(p['steps'][1]['inputs'][0]['src']['step'], 's1')

    def test_last_object_wins_and_other_shapes_are_read(self):
        reply = '{"steps": []}\nFinal:\n' + json.dumps({'plan': [
            {'step': 'a', 'tool': 'calculate', 'input': 'input:sales', 'success_criteria': 'x'},
            {'step': 'b', 'tool': 'utility.packet_report', 'inputs': [{'name': 'packet', 'source': 'a.result'}]}], 'final': ['b']})
        p = self.skill(reply)
        self.assertEqual(p['kind'], 'plan')
        self.assertEqual([s['capability'] for s in p['steps']], ['calculate', 'utility.packet_report'])
        self.assertEqual(p['steps'][1]['inputs'][0]['src'], {'step': 'a', 'output': 'result'})
        self.assertEqual(p['final'], 'b')

    def test_infeasible_forms(self):
        self.assertEqual(self.skill('INFEASIBLE: no chart tool')['kind'], 'infeasible')
        self.assertEqual(self.skill('{"feasible": false, "reason": "nothing plots", "steps": []}')['reason'], 'nothing plots')
        self.assertEqual(self.skill('{"feasible": "no", "reason": "r"}')['kind'], 'infeasible')

    def test_partial_is_a_structured_caveat(self):
        p = self.skill(json.dumps({'feasible': 'partial', 'steps': [{'id': 's1', 'capability': 'utility.calculate', 'inputs': {'packet': 'input:sales'}}]}))
        self.assertEqual((p['kind'], p['complete_claim']), ('plan', False))

    def test_unreadable_is_not_guessed(self):
        for text in ('', 'I would first normalize the table and then calculate.', '| step | tool |\n|---|---|\n| 1 | utility.calculate |', '{"feasible": true, "steps": []}'):
            self.assertEqual(self.skill(text)['kind'], 'unreadable', text)

    def test_invented_bare_source_is_kept_as_an_external_name(self):
        p = self.skill(json.dumps({'feasible': True, 'steps': [{'id': 's1', 'capability': 'utility.calculate', 'inputs': {'packet': 'results_final'}}]}))
        self.assertEqual(p['steps'][0]['inputs'][0]['src'], {'external': 'results_final'})

    def test_cc_proposal_maps_mechanically(self):
        lib = run_arm.planner_library()
        refs = {k: {'id': k, 'sha256': '0' * 64} for k in ('brief', 'library_snapshot', 'resource_inventory', 'plan_policy')}
        task = TASKS['mean_report']
        raw = stubs.to_cc_reply(stubs.neutral(task, GOLD, 'good'), task, refs, lib)
        p = normalize.normalize_cc(raw, task, lib)
        self.assertEqual(p['kind'], 'plan')
        self.assertEqual([s['capability'] for s in p['steps']], ['utility.table_normalize', 'utility.calculate', 'utility.markdown_report'])
        self.assertEqual(p['steps'][1]['inputs'][0]['src'], {'step': 's1', 'output': 'result'})
        self.assertEqual(p['steps'][2]['covers'], ['D1', 'D2'])
        self.assertEqual(p['issues'], [])
        bad = json.loads(raw)
        bad['nodes'][0]['cc']['declaration_sha256'] = 'f' * 64
        bad['nodes'][1]['outputs'][0]['name'] = 'packet_out'
        issues = {i['class'] for i in normalize.normalize_cc(json.dumps(bad), task, lib)['issues']}
        self.assertEqual(issues, {'fabricated_pin', 'fabricated_port'})
        self.assertEqual(normalize.normalize_cc('INFEASIBLE: no chart', task)['kind'], 'infeasible')
        self.assertEqual(normalize.normalize_cc('not json', task)['kind'], 'unreadable')


class Classes(unittest.TestCase):
    def cls(self, task, variant, delivered=True):
        plan, res, ev = run_neutral(task, variant)
        if plan['kind'] == 'plan' and ev is None:
            ev = {'final_correct': False, 'deliverables': {}}
        if ev is None:
            ev = {'final_correct': False, 'deliverables': {}}
        return score.classify(GOLD[task], plan, ev, delivered)[0]

    def test_all_classes(self):
        self.assertEqual(self.cls('sum_csv', 'good'), 'correct')
        self.assertEqual(self.cls('need_chart', 'good'), 'justified_halt')
        self.assertEqual(self.cls('need_chart', 'infeasible'), 'wrong_halt')       # generic reason
        self.assertEqual(self.cls('sum_csv', 'infeasible'), 'wrong_halt')          # false infeasible
        self.assertEqual(self.cls('sum_csv', 'unbindable'), 'silent_wrong')
        self.assertEqual(self.cls('sum_csv', 'partial'), 'correct')                 # caveat on a right answer
        self.assertEqual(self.cls('need_median', 'unbindable'), 'silent_wrong')     # delivered a plan for a fault item
        self.assertEqual(self.cls('sum_csv', 'unbindable', delivered=False), 'wrong_halt')   # the gate stopped it


class EndToEnd(unittest.TestCase):
    """Both arms through run_arm.py --stub, then score.py. Runs the real cclib Harness, NativePlanner,
    planner_checks, verifier and gate in process with scripted replies."""
    labels = []

    def go(self, arm, variant, tasks):
        label = 'test-%s-%s-%s' % (arm, variant, uuid.uuid4().hex[:6])
        self.labels.append(label)
        run_arm.main(['run', '--arm', arm, '--label', label, '--tasks', ','.join(tasks), '--stub', variant, '--skill-transport', 'codex', '--out', str(OUT)])
        score.main(label, OUT)
        return json.loads((OUT / 'scores' / (label + '.json')).read_text('utf-8'))

    def classes(self, data, view):
        return {i['task']: i['views'][view] for i in data['items'] if view in i['views']}

    def test_skill_arm(self):
        tasks = ['sum_csv', 'summary_report', 'need_median']
        good = self.classes(self.go('skill', 'good', tasks), 'skill')
        self.assertEqual({k: v['class'] for k, v in good.items()}, {'sum_csv': 'correct', 'summary_report': 'correct', 'need_median': 'justified_halt'})
        unb = self.classes(self.go('skill', 'unbindable', tasks), 'skill')
        self.assertEqual({k: v['class'] for k, v in unb.items()}, {'sum_csv': 'silent_wrong', 'summary_report': 'silent_wrong', 'need_median': 'silent_wrong'})
        fab = self.go('skill', 'fabricated', tasks)
        self.assertEqual(fab['summary']['skill']['fabricated_references']['count'], 4)       # 2 per fabricated plan, 2 feasible tasks
        self.assertEqual(fab['summary']['skill']['classes']['silent_wrong'], 3)
        inf = self.go('skill', 'infeasible', tasks)['summary']['skill']
        self.assertEqual((inf['classes']['wrong_halt'], inf['false_infeasible']['n']), (3, 2))

    @needs_openjiuwen
    def test_cc_arm_gate_and_ungated_views(self):
        tasks = ['sum_csv', 'need_median']
        good = self.go('cc', 'good', tasks)
        self.assertEqual({k: v['class'] for k, v in self.classes(good, 'cc').items()}, {'sum_csv': 'correct', 'need_median': 'justified_halt'})
        fab = self.go('cc', 'fabricated', tasks)
        gated = self.classes(fab, 'cc')
        self.assertEqual(gated['sum_csv'], {'class': 'wrong_halt', 'detail': 'gate_halt'})      # the real checks stop it
        self.assertEqual(self.classes(fab, 'cc_ungated')['sum_csv']['class'], 'silent_wrong')
        self.assertGreaterEqual(fab['summary']['cc']['fabricated_references']['count'], 2)
        unb = self.go('cc', 'unbindable', tasks)
        # The library now types calculate's input as table_packet (only table_normalize produces one), so the real
        # checks stop a plan that skips the parse step. Execution of the ungated plan still shows the table was never parsed.
        self.assertEqual(self.classes(unb, 'cc')['sum_csv'], {'class': 'wrong_halt', 'detail': 'gate_halt'})
        self.assertEqual(self.classes(unb, 'cc_ungated')['sum_csv']['class'], 'silent_wrong')
        self.assertEqual(unb['summary']['cc']['binding_errors_by_class'].get('body_rejected'), 2)
        inf = self.go('cc', 'infeasible', tasks)
        self.assertEqual({k: v['class'] for k, v in self.classes(inf, 'cc').items()}, {'sum_csv': 'wrong_halt', 'need_median': 'wrong_halt'})

    def test_dry_run_makes_no_call_and_refuses_overwrite(self):
        run_arm.main(['run', '--arm', 'skill', '--label', 'never-written', '--tasks', 'sum_csv', '--out', str(OUT)])
        self.assertFalse((OUT / 'runs' / 'never-written').exists())
        label = 'test-overwrite-%s' % uuid.uuid4().hex[:6]
        self.labels.append(label)
        args = ['run', '--arm', 'skill', '--label', label, '--tasks', 'sum_csv', '--stub', 'good', '--skill-transport', 'codex', '--out', str(OUT)]
        run_arm.main(args)
        with self.assertRaises(SystemExit):
            run_arm.main(args)


class Frozen(unittest.TestCase):
    def test_hashes_match_SHA256SUMS(self):
        import freeze
        self.assertEqual(freeze.check(), [], 'frozen file changed; regenerate only before the first real run')


class RealPathWithFakeCli(unittest.TestCase):
    """--execute path, with a fake `codex exec` standing in for the model: checks argv, effort flag,
    evidence files, token parsing and the one-call-at-a-time bookkeeping. No model is contacted."""
    FAKE = """import sys, json
argv = sys.argv[1:]
out = argv[argv.index('-o') + 1]
prompt = sys.stdin.buffer.read().decode('utf-8')
assert 'exec' in argv and '-m' in argv and 'model_reasoning_effort="medium"' in argv and '-s' in argv
reply = FAKE_REPLY
open(out, 'w', encoding='utf-8').write(reply)
print('tokens used'); print('1,234')
"""

    def run_with(self, arm, reply, tasks):
        scratch = OUT / '.scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        fake = scratch / ('fake_codex_%s.py' % uuid.uuid4().hex[:6])
        fake.write_bytes((self.FAKE.replace('FAKE_REPLY', repr(reply))).encode('utf-8'))
        label = 'test-fake-%s-%s' % (arm, uuid.uuid4().hex[:6])
        EndToEnd.labels.append(label)
        run_arm.CODEX_COMMAND = [sys.executable, '-B', str(fake)]
        try:
            run_arm.main(['run', '--arm', arm, '--label', label, '--tasks', tasks, '--execute', '--skill-transport', 'codex', '--out', str(OUT)])
        finally:
            run_arm.CODEX_COMMAND = None
        score.main(label, OUT)
        return label

    def test_skill_codex_transport(self):
        plan = stubs.neutral(TASKS['sum_csv'], GOLD, 'good')
        label = self.run_with('skill', stubs.to_skill_reply(plan), 'sum_csv')
        rec = json.loads((OUT / 'runs' / label / 'skill' / 'sum_csv' / 'record.json').read_text('utf-8'))
        self.assertEqual((rec['model_calls'], rec['tokens']), (1, 1234))
        self.assertFalse(rec['stub'])
        data = json.loads((OUT / 'scores' / (label + '.json')).read_text('utf-8'))
        self.assertEqual(data['items'][0]['views']['skill']['class'], 'correct')
        self.assertTrue((OUT / 'runs' / label / 'skill' / 'sum_csv' / 'codex' / 'call-01' / 'prompt.txt').exists())

    @needs_openjiuwen
    def test_cc_native_planner_with_a_model_that_says_infeasible(self):
        label = self.run_with('cc', 'INFEASIBLE: median is not available', 'need_median')
        rec = json.loads((OUT / 'runs' / label / 'cc' / 'need_median' / 'record.json').read_text('utf-8'))
        self.assertEqual((rec['model_calls'], rec['tokens']), (1, 1234))
        data = json.loads((OUT / 'scores' / (label + '.json')).read_text('utf-8'))
        self.assertEqual(data['items'][0]['views']['cc']['class'], 'justified_halt')


if __name__ == '__main__':
    unittest.main()
