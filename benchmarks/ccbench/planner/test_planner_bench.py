import sys
sys.dont_write_bytecode = True
import contextlib
import copy
import io
import json
import os
import tempfile
import uuid
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from library import ROOT, build_library, declared_payload, undeclared_view
from plan_integrity import DEFECTS, check, normalize_declared, normalize_undeclared, score_raw, product_gate
from run_planner_bench import aggregate, load_tasks, main, make_prompt, task_text, invoke_once


@contextlib.contextmanager
def retained_scratch(parent, prefix='unused'):
    directory = Path(parent) / ('.scratch-' + uuid.uuid4().hex)
    os.makedirs(directory)
    yield str(directory)


class PlannerBenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_library()
        cls.tasks = {t['id']: t for t in load_tasks()}
        cls.expected = json.loads((ROOT / 'expected.json').read_text('utf-8'))

    def perfect_declared(self, tid='report'):
        task = self.tasks[tid]
        payload = declared_payload(task, self.lib)
        cap = self.expected[tid]['required_capabilities'][0]
        e = next(e for e in self.lib['library_snapshot']['entries'] if e['cc_name'] == cap)
        n = dict(node_id='work', cc={k: e[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')},
            objective='The checked result preserves supplied content and provenance.', requirement_ids=[task['brief']['mandatory_requirements'][0]['id']],
            deliverable_ids=[task['brief']['deliverables'][0]['id']], predecessors=[],
            inputs=[dict(name=p['name'], artifact_type=p['artifact_type'], required=p['required'], source_kind='accepted_ref', run_input_key='packet', accepted_ref=None, future=None) for p in e['input_ports']],
            outputs=[{k: p[k] for k in ('name', 'artifact_type', 'required')} for p in e['output_ports']],
            limits=dict(time_s=60, model_calls=1, memory_mb=256), suggested_checks=[self.lib['checks'][cap][0]])
        return dict(schema_version='3.0.0', id='handmade', plan_source='planned', nodes=[n],
            coverage=[dict(item_id=v['id'], item_kind=kind, node_ids=['work']) for kind, field in [('requirement', 'mandatory_requirements'), ('deliverable', 'deliverables'), ('evidence_obligation', 'evidence_obligations')] for v in task['brief'][field]],
            topic_hints=[], limits=copy.deepcopy(n['limits']), notes='', **{k: payload[k] for k in ('brief_ref', 'library_snapshot_ref', 'resource_inventory_ref', 'policy_ref')})

    def perfect(self):
        return normalize_declared(self.perfect_declared())

    def score(self, plan, tid='report', lib=None):
        return check(plan, self.tasks[tid], self.expected[tid], lib or self.lib)

    def test_library_builds_offline_and_catalog_is_exact(self):
        from jiuwenswarm.research.planner_catalog import verify_catalog
        from library import ref
        with patch('subprocess.Popen', side_effect=AssertionError('process forbidden')):
            build_library.cache_clear()
            lib = build_library()
        self.assertEqual(27, len(lib['library_snapshot']['entries']))
        self.assertEqual(22, sum(e['selectable_by_planner'] for e in lib['library_snapshot']['entries']))
        releases = {(e['cc_name'], e['cc_version']) for e in lib['library_snapshot']['entries']}
        self.assertTrue({('intent.compiler', 'm1-7'), ('requirements.compiler', 'm1-9'),
                         ('research.screening', 'm1-5'),
                         ('research.evaluation', 'm1-5-evidence-1'),
                         ('research.delivery', 'm1-5-evidence-1')} <= releases)
        verify_catalog(lib['capsule_contracts'], lib['library_snapshot'], ref(lib['library_snapshot'], 'library_snapshot'))
        self.assertIn('Pinned output schema:', lib['instructions'])
        self.assertIn('ai4r_integrated_policy_v2', lib['plan_policy']['id'])
        self.assertEqual(lib, self.lib)

    def test_undeclared_contains_verbatim_descriptions_and_port_names_and_types(self):
        view = undeclared_view(self.lib)
        for row, capsule in zip(view, self.lib['capsule_contracts']['capsules']):
            self.assertEqual({'name', 'description', 'inputs', 'outputs'}, set(row))
            for direction, key in (('inputs', 'inputs'), ('outputs', 'outputs')):
                self.assertEqual([(p['name'], p['artifact_type'], p['required']) for p in capsule['declaration']['ports'][direction]],
                                 [(p['name'], p['type'], p['required']) for p in row[key]])
                self.assertTrue(all(set(p) == {'name', 'type', 'required'} for p in row[key]))
            self.assertEqual(capsule['declaration']['identity']['summary'], row['description'])
            self.assertEqual(capsule['cc']['cc_name'], row['name'])
        # Literal 'typed' words in release names/summaries are deliberately
        # preserved; the test prohibits port/type/limit metadata, not English.
        for forbidden in ('ports', 'artifact_type', 'schema_ref', 'limits', 'effects', 'checks', 'needs'):
            self.assertNotIn('"' + forbidden + '":', json.dumps(view))

    def test_tasks_are_well_formed_and_labels_are_hidden(self):
        from jiuwenswarm.research.contracts import validate
        from jiuwenswarm.research.capsule_extensions.packet import validate_packet
        self.assertEqual(12, len(self.tasks))
        counts = {}
        for tid, task in self.tasks.items():
            validate('research-brief', task['brief'])
            validate('resource-inventory', task['resource_inventory'])
            self.assertEqual(tid, task['id'])
            self.assertNotIn('expected', task)
            self.assertNotIn('required_capabilities', task_text(task))
            category = self.expected[tid]['category']
            counts[category] = counts.get(category, 0) + 1
            for row in task['supplied_inputs'].values():
                if row['artifact_type'] in ('work_packet', 'table_packet'):
                    validate_packet(row['content'])
                elif row['artifact_type'] == 'candidate_set':
                    validate('candidate-set', row['content'])
                elif row['artifact_type'] == 'local_document_buffer':
                    validate('urn:ai4r:paper-document-buffer:1.0.0', row['content'])
        self.assertEqual(dict(normal=5, infeasible=3, over_budget=2, underspecified=2), counts)

    def test_perfect_handmade_declared_plan_zero_defects_and_product_pass(self):
        source = self.perfect_declared()
        scored = self.score(normalize_declared(source))
        self.assertEqual([], scored['defects'])
        self.assertEqual([], product_gate(json.dumps(source), self.tasks['report'], self.lib))

    def test_all_five_feasible_briefs_have_handmade_zero_defect_plans(self):
        for tid in ('normalize', 'calculate', 'report', 'screen', 'paper'):
            with self.subTest(tid=tid):
                task = self.tasks[tid]
                nodes = []
                for i, cap in enumerate(self.expected[tid]['required_capabilities']):
                    e = next(e for e in self.lib['library_snapshot']['entries'] if e['cc_name'] == cap)
                    sources = dict(brief='external:brief', packet='external:packet', documents='external:local_document_buffer', candidate_set='external:candidate_set', screening_rubric='external:screening_rubric', summary='n0.summary', gate_decision_index='external:gate_decision_index')
                    nodes.append(dict(id='n' + str(i), capability=cap, inputs=[dict(name=p['name'], source=sources[p['name']]) for p in e['input_ports']], outputs=[p['name'] for p in e['output_ports']], acceptance_criteria=[e['output_ports'][0]['name'] + ' conforms to its schema'], depends_on=['n0'] if i else [], limits=dict(time_s=60, model_calls=1, memory_mb=256), covers=self.expected[tid]['obligations']))
                self.assertEqual([], self.score(dict(nodes=nodes), tid)['defects'])

    def test_checker_catches_every_defect_class(self):
        found = set()
        changes = {
            'unknown_capability': lambda p: p['nodes'][0].update(capability='imaginary.train'),
            'unknown_or_missing_port': lambda p: p['nodes'][0]['outputs'].append('imaginary'),
            'type_incompatible_binding': lambda p: p['nodes'][0]['inputs'][0].update(source='external:brief'),
            'unsatisfied_required_input': lambda p: p['nodes'][0].update(inputs=[]),
            'cycle_or_unordered_dependency': lambda p: p['nodes'][0].update(depends_on=['work']),
            'uncovered_obligation': lambda p: p['nodes'][0].update(covers=[]),
            'missing_acceptance_criterion': lambda p: p['nodes'][0].update(acceptance_criteria=[]),
            'acceptance_not_machine_checkable': lambda p: p['nodes'][0].update(acceptance_criteria=['It looks excellent']),
            'over_budget': lambda p: p['nodes'][0]['limits'].update(time_s=12000),
            'effect_or_authority_violation': lambda p: p['nodes'][0].update(authority={'network': 'unrestricted'}),
            'invented_input_or_resource': lambda p: p['nodes'][0]['inputs'][0].update(source='external:made_up'),
        }
        for defect, mutate in changes.items():
            with self.subTest(defect=defect):
                p = self.perfect()
                mutate(p)
                scored = self.score(p)
                self.assertGreater(scored['counts'][defect], 0)
                found.add(defect)
        scored = self.score(self.perfect(), 'gpu_training')
        self.assertEqual(1, scored['counts']['infeasible_task_planned_anyway'])
        found.add('infeasible_task_planned_anyway')
        scored = self.score(dict(infeasible=True, reason='No capability', bounded=True))
        self.assertEqual(1, scored['counts']['feasible_task_declared_infeasible'])
        found.add('feasible_task_declared_infeasible')
        self.assertEqual(set(DEFECTS), found)

    def test_hallucination_and_unbound_input_counted_together(self):
        p = self.perfect()
        p['nodes'][0].update(capability='imaginary.skill')
        p['nodes'][0]['inputs'][0]['source'] = ''
        counts = self.score(p)['counts']
        self.assertEqual(1, counts['unknown_capability'])
        self.assertEqual(2, counts['unsatisfied_required_input'])  # unbound port + required task input unused

    def test_future_type_schema_and_dependency_are_checked_independently(self):
        p = self.perfect()
        producer = copy.deepcopy(p['nodes'][0])
        producer.update(id='producer', capability='research.paper_summary', inputs=[dict(name='brief', source='external:brief'), dict(name='documents', source='external:local_document_buffer')], outputs=['summary'])
        p['nodes'].insert(0, producer)
        p['nodes'][1]['inputs'][0]['source'] = 'producer.summary'
        counts = self.score(p)['counts']
        self.assertGreater(counts['type_incompatible_binding'], 0)
        self.assertGreater(counts['cycle_or_unordered_dependency'], 0)

    def test_aggregate_budget_is_sum_not_just_per_node(self):
        p = self.perfect()
        p['nodes'][0]['limits']['memory_mb'] = 9000
        other = copy.deepcopy(p['nodes'][0])
        other['id'] = 'second'
        p['nodes'].append(other)
        counts = self.score(p)['counts']
        self.assertEqual(1, counts['over_budget'])

    def test_infeasible_reply_must_name_reason_and_be_bounded(self):
        good = score_raw('INFEASIBLE: Distributed GPU training is absent.', 'B', self.tasks['gpu_training'], self.expected['gpu_training'], self.lib)
        self.assertTrue(good['valid'])
        for raw in ('INFEASIBLE: cannot help.', 'INFEASIBLE: GPU\n' + 'x' * 310):
            bad = score_raw(raw, 'B', self.tasks['gpu_training'], self.expected['gpu_training'], self.lib)
            self.assertFalse(bad['valid'])

    def test_prompts_have_identical_task_and_budget_without_expected_labels(self):
        for task in self.tasks.values():
            a, b = [make_prompt(task, c, self.lib) for c in ('A', 'B')]
            self.assertEqual(a.split('<task>\n')[1].split('\n</task>')[0], b.split('<task>\n')[1].split('\n</task>')[0])
            self.assertEqual(a.splitlines()[0], b.splitlines()[0])
            self.assertNotIn('missing_capability_or_input', a + b)
            self.assertNotIn('check_bundle_sha256', b)

    def test_dry_run_makes_no_process_call(self):
        with patch('subprocess.Popen', side_effect=AssertionError('process forbidden')), patch('subprocess.run', side_effect=AssertionError('process forbidden')), contextlib.redirect_stdout(io.StringIO()) as out:
            main(['plan'])
        self.assertEqual(24, len(json.loads(out.getvalue())))

    def test_execution_requires_explicit_flag(self):
        with patch('subprocess.Popen', side_effect=AssertionError('process forbidden')):
            with self.assertRaises(SystemExit):
                main(['run', '--model', 'gpt-6-luna'])

    def test_malformed_replies_are_scored_and_gate_failure_reported(self):
        for raw in ('', '{broken', '[]', '{"nodes":[{}]}', '{"nodes":[{"inputs":"wrong"}]}'):
            with self.subTest(raw=raw):
                scored = score_raw(raw, 'A', self.tasks['report'], self.expected['report'], self.lib)
                self.assertFalse(scored['valid'])
                self.assertTrue(scored['product_gate_failures'])

    def test_aggregate_stability_and_machine_check_fraction(self):
        good = self.score(self.perfect())
        rows = [dict(task='report', condition=c, repeat=r, expected_feasible=True, score=copy.deepcopy(good)) for c in ('A', 'B') for r in (1, 2)]
        rows[-1]['score']['capability_set'] = ['imaginary']
        s = aggregate(rows)
        self.assertEqual(1, s['A']['run_to_run_stability'])
        self.assertEqual(0.5, s['B']['run_to_run_stability'])
        self.assertEqual(1, s['A']['acceptance_machine_checkable_fraction'])
        self.assertIsNone(s['A']['infeasible_handling_accuracy'])

    def test_cli_boundary_one_process_timeout_and_token_capture(self):
        process = unittest.mock.Mock()
        process.communicate.return_value = ('completed', 'tokens used\n1,234\n')
        process.returncode = 0
        with patch('subprocess.Popen', return_value=process) as launch:
            result = invoke_once(['codex', 'exec'], 'prompt', {})
        launch.assert_called_once()
        process.communicate.assert_called_once_with('prompt', timeout=300)
        self.assertEqual(['1,234'], result['tokens_used'])
        self.assertFalse(result['timed_out'])

    def test_mocked_runner_and_score_roundtrip(self):
        import run_planner_bench as bench
        with patch.object(bench, 'fresh_empty_directory', retained_scratch), tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'expected.json').write_text(json.dumps(self.expected), encoding='utf-8')
            calls = []
            def fake_cli(command, prompt, env):
                calls.append(command)
                self.assertEqual('exec', command[1])
                self.assertIn('--skip-git-repo-check', command)
                self.assertEqual('read-only', command[command.index('-s') + 1])
                self.assertIn('--ephemeral', command)
                self.assertEqual('-', command[-1])
                cwd = Path(command[command.index('-C') + 1])
                self.assertTrue(cwd.is_relative_to(root))
                self.assertEqual([], list(cwd.iterdir()))
                reply = self.perfect_declared() if 'Declared planner payload:' in prompt else self.perfect()
                Path(command[command.index('-o') + 1]).write_text(json.dumps(reply), encoding='utf-8')
                return dict(elapsed_s=0.1, returncode=0, timed_out=False, stdout_tail='', stderr_tail='', tokens_used=[])
            with patch.object(bench, 'ROOT', root), patch.object(bench, 'load_tasks', return_value=[self.tasks['report']]), patch.object(bench, 'invoke_once', side_effect=fake_cli), patch.object(bench.roots, 'require_codex', return_value='codex'), contextlib.redirect_stdout(io.StringIO()):
                bench.run(SimpleNamespace(execute=True, repeats=2, model='gpt-6-luna', out=root, task=None))
                bench.score('gpt-6-luna', root)
            self.assertEqual(4, len(calls))
            scored = json.loads((root / 'scores/gpt-6-luna.json').read_text('utf-8'))
            self.assertEqual(4, len(scored['plans']))
            self.assertEqual(1, scored['aggregate']['A']['validity_rate'])
            self.assertEqual(1, scored['aggregate']['B']['validity_rate'])
            self.assertEqual(1, scored['aggregate']['A']['run_to_run_stability'])

    def test_skill_detail_names_is_default_and_full_adds_only_file_texts(self):
        import run_planner_bench as bench
        task = self.tasks['report']
        names = make_prompt(task, 'B', self.lib)
        self.assertEqual(names, make_prompt(task, 'B', self.lib, 'names'))
        full = make_prompt(task, 'B', self.lib, 'full')
        extra = bench.full_skill_text(self.lib)
        self.assertEqual(names, full.replace(extra, '', 1))
        self.assertGreater(len(full), len(names))
        self.assertEqual(make_prompt(task, 'A', self.lib), make_prompt(task, 'A', self.lib, 'full'))
        files = dict(bench.skillpack_files(self.lib))
        self.assertIn('tools/utility_calculate.py', files)
        self.assertIn('skills/research-paper-summary/SKILL.md', files)
        for rel, text in files.items():
            self.assertIn('--- file: %s ---\n%s' % (rel, text.rstrip('\n')), extra)
        self.assertNotIn('\r', extra)
        with self.assertRaises(ValueError):
            make_prompt(task, 'B', self.lib, 'bogus')

    def test_invoke_once_records_input_output_only_when_printed(self):
        import run_planner_bench as bench

        class Proc:
            returncode = 0
            def __init__(self, *a, **k): pass
            def communicate(self, prompt, timeout=None): return ('', self.err)
        for err, want in (('tokens used\n99,301\n', (None, None)), ('input tokens: 90,000\noutput tokens: 9,301\ntokens used\n99,301\n', (90000, 9301))):
            Proc.err = err
            with patch.object(bench.subprocess, 'Popen', Proc):
                rec = bench.invoke_once(['x'], 'p', {})
            self.assertEqual(['99,301'], rec['tokens_used'])
            self.assertEqual(want, (rec['input_tokens'], rec['output_tokens']))

    def test_resume_runs_only_missing_units_and_refuses_a_changed_setup(self):
        import run_planner_bench as bench
        calls = []

        def fake_cli(command, prompt, env):
            calls.append(prompt)
            Path(command[command.index('-o') + 1]).write_text('INFEASIBLE: x', encoding='utf-8')
            return dict(elapsed_s=0.1, returncode=0, timed_out=False, stdout_tail='', stderr_tail='', tokens_used=[])
        ids = list(self.tasks)[:2]

        def go(folder, task, **kw):
            args = dict(execute=True, repeats=1, model='gpt-6-luna', out=Path(folder), task=[task], skill_detail='full', resume=True)
            args.update(kw)
            with patch.object(bench, 'fresh_empty_directory', retained_scratch), patch.object(bench, 'invoke_once', side_effect=fake_cli), \
                    patch.object(bench.roots, 'require_codex', return_value='codex'), contextlib.redirect_stdout(io.StringIO()):
                bench.run(SimpleNamespace(**args))
        with tempfile.TemporaryDirectory() as folder:
            go(folder, ids[0])
            self.assertEqual(2, len(calls))
            self.assertIn('Full text of each skill and tool file', calls[0] + calls[1])
            go(folder, ids[0])                      # same units: nothing runs
            self.assertEqual(2, len(calls))
            go(folder, ids[1])                      # a new task is added to the same run
            self.assertEqual(4, len(calls))
            manifest = json.loads((Path(folder) / 'runs/gpt-6-luna/manifest.json').read_text('utf-8'))
            self.assertEqual(sorted(ids), sorted(t['id'] for t in manifest['tasks']))
            with self.assertRaises(SystemExit):
                go(folder, ids[1], skill_detail='names')
            with self.assertRaises(SystemExit):
                go(folder, ids[1], resume=False)


if __name__ == '__main__':
    unittest.main()
