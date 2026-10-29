"""Tests for slate.py with a fake runner: no model call, no docker, no subprocess."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import slate  # noqa: E402

MODEL = 'gpt-6-luna'


def opt(argv, name):
    return argv[argv.index(name) + 1] if name in argv else None


class FakeRunner:
    """Records every command and writes the files the real command would leave, so the next step finds them."""

    def __init__(self, docker_ok=True, fail_label=None):
        self.calls, self.docker_ok, self.fail_label = [], docker_ok, fail_label
        self.items = sorted(p.name for p in (HERE / 'nativeadmit' / 'items').iterdir() if p.is_dir())

    def capture(self, argv, cwd=None):
        self.calls.append(('capture', list(map(str, argv)), {}))
        if argv[0] == 'docker':
            return (0, 'sha256:abc') if self.docker_ok else (1, '')
        return 0, ''

    def run(self, argv, cwd=None, env=None, label='cmd'):
        argv = list(map(str, argv))
        self.calls.append(('run', argv, dict(env or {}, label=label)))
        if self.fail_label and self.fail_label in label:
            return 1
        j = ' '.join(argv)
        if 'cc_route.py' in j:
            out = Path(opt(argv, '--out')) / 'cc'
            out.mkdir(parents=True, exist_ok=True)
            for i in self.items:
                (out / (i + '.json')).write_text('{}')
        elif 'cc_live_inputs.py' in j:
            root = Path(opt(argv, '--out')) / 'cc-live'
            for i in self.items:
                (root / i).mkdir(parents=True, exist_ok=True)
                (root / i / 'task.txt').write_text('t')
            (root / 'manifest.json').write_text('[]')
        elif 'init-ledger' in j:
            led = Path(opt(argv, '--out'))
            led.mkdir(parents=True, exist_ok=True)
            (led / 'ledger.sqlite3').write_text('')
        elif 'nativetask' in argv and 'run' in argv:
            self.agent(Path(opt(argv, '--out')), opt(argv, '--attempt-id'))
        elif 'collect.sh' in j:
            self.collect(Path(argv[-1]), env or {})
        elif any(b in argv for b in ('heldout', 'contract', 'haltbench')) and 'run' in argv:
            self.modelbench(argv)
        elif 'planner' in argv and 'run' in argv:
            self.planner(argv)
        elif 'score_arms.py' in j or 'inputguard/score.py' in j or ('score' in argv):
            self.score(argv)
        return 0

    def agent(self, folder, attempt):
        (folder / 'attempts').mkdir(parents=True, exist_ok=True)
        (folder / 'attempts' / (attempt + '.json')).write_text('{}')
        s = folder / 'sessions' / attempt
        s.mkdir(parents=True, exist_ok=True)
        (s / 'final-message.txt').write_text('Answer: 1')
        (s / 'usage.json').write_text(json.dumps([dict(elapsed_s=2, usage=dict(input_tokens=1000, output_tokens=100))]))

    def collect(self, out, env):
        out = out.resolve() if out.exists() else out
        for spec in env['ARMS'].split():
            arm = spec.split('=')[0]
            fixtures = env['FIXTURES'].split() if env.get('FIXTURES') else sorted(p.name for p in (out / 'inputs' / 'plain').iterdir())
            for fx in fixtures:
                if not (out / arm / 'attempts' / (fx + '-r1.json')).exists():
                    self.agent(out / arm, fx + '-r1')

    def modelbench(self, argv):
        bench = next(b for b in ('heldout', 'contract', 'haltbench') if b in argv)
        out = Path(opt(argv, '--out')) / bench / MODEL
        cases = [opt(argv, '--case')] if '--case' in argv else [c['id'] for c in json.loads((HERE / bench / 'cases.json').read_text('utf-8-sig'))]
        arms = [opt(argv, '--arm')] if '--arm' in argv else list(slate.BENCH_ARMS[bench])
        for c in cases:
            for a in arms:
                u = out / c / (a + '-r1')
                if not (u / 'result.json').exists():
                    u.mkdir(parents=True, exist_ok=True)
                    (u / 'result.json').write_text(json.dumps(dict(calls=[dict(ok=True)])))

    def planner(self, argv):
        out = Path(opt(argv, '--out')) / 'runs' / MODEL
        tasks = [opt(argv, '--task')] if '--task' in argv else [t['id'] for t in json.loads((HERE / 'planner' / 'tasks.json').read_text('utf-8'))]
        for t in tasks:
            for cond in 'AB':
                u = out / t / (cond + '-r1')
                if not (u / 'run.json').exists():
                    u.mkdir(parents=True, exist_ok=True)
                    (u / 'reply.txt').write_text('{}')
                    (u / 'run.json').write_text(json.dumps(dict(returncode=0, timed_out=False, tokens_used=['2,000'], input_tokens=None, output_tokens=None, elapsed_s=5)))

    def score(self, argv):
        j = ' '.join(argv)
        out = Path(opt(argv, '--out'))
        out.mkdir(parents=True, exist_ok=True)
        if 'score_arms.py' in j or 'inputguard/score.py' in j:
            rows = []
            for spec in [argv[i + 1] for i, a in enumerate(argv) if a == '--arm']:
                name, folder = spec.split('=', 1)
                for s in sorted((Path(folder) / 'sessions').iterdir()):
                    rows.append(dict(arm=name, session=s.name, cls='correct' if name != 'plain' else 'silent_wrong', input_tokens=1000, output_tokens=100,
                                     total_tokens=1100, calls=1, wall_s=2.0))
            (out / ('score-arms.json' if 'score_arms.py' in j else 'score.json')).write_text(json.dumps(dict(rows=rows)))
        else:
            bench = next((b for b in ('heldout', 'contract', 'haltbench') if b in argv), None)
            (out / 'scores').mkdir(exist_ok=True)
            if bench:
                base = out / bench / MODEL
                units = []
                for r in sorted(base.glob('*/*/result.json')):
                    cost = dict(calls=1, tokens=1100, input_tokens=1000, output_tokens=100, wall_s=2.0)
                    units.append(dict(case=r.parent.parent.name, arm=r.parent.name[:-3], rep=1, cost=cost, passed_all=True, correct_and_compliant=True, label='correct'))
                (out / 'scores' / ('%s-%s.json' % (bench, MODEL))).write_text(json.dumps(dict(units=units)))
            else:
                plans = [dict(task=p.parent.parent.name, condition=p.parent.name[0], repeat=1, score=dict(valid=p.parent.name[0] == 'A')) for p in sorted((out / 'runs' / MODEL).glob('*/*/run.json'))]
                (out / 'scores' / (MODEL + '.json')).write_text(json.dumps(dict(plans=plans)))


def commands(runner, needle):
    return [c for k, c, _ in runner.calls if k == 'run' and needle in ' '.join(c)]


class SlateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / 'run'
        self.fix = Path(self.tmp.name) / 'fixtures'
        for name, cause in (('units-a', 'metric_unit_conflict'), ('clean-b', None)):
            d = self.fix / name
            (d / 'inputs').mkdir(parents=True)
            (d / 'task.txt').write_text('task\n')
            (d / 'fault.json').write_text(json.dumps(dict(expected_cause=cause)))
            (d / 'inputs' / 'README.md').write_text('x')
        self.env = patch.dict(os.environ, {'AI4R_T2_FIXTURES': str(self.fix), 'AI4R_CODEX_BIN': sys.executable})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def go(self, runner, *argv):
        return slate.main(['luna', '--out', str(self.out), '--no-selftest', *argv], runner=runner)

    def test_doctor_names_the_fix_and_starts_nothing(self):
        r = FakeRunner(docker_ok=False)
        with patch.dict(os.environ, {'AI4R_CODEX_BIN': str(Path(self.tmp.name) / 'nope')}), patch.object(slate.roots, 'codex_bin', return_value=None):
            self.assertEqual(self.go(r), 2)
        self.assertEqual(commands(r, 'ai4r-bench'), [])
        s = slate.Slate(self.out, FakeRunner(docker_ok=False))
        with patch.object(slate.roots, 'codex_bin', return_value=None):
            text = ' '.join(s.doctor(selftests=False))
        self.assertIn('AI4R_CODEX_BIN', text)
        self.assertIn('Docker', text)

    def test_full_run_order_serial_forward_slashes_and_t1_adoption(self):
        # two finished luna T1 sessions are adopted: no command is issued for them
        done = self.out / 'A-native-luna' / 'attempts'
        done.mkdir(parents=True)
        (done / 'calc_absolute-r1.json').write_text('{}')
        r = FakeRunner()
        self.assertEqual(self.go(r), 0)
        runs = commands(r, 'nativetask')
        adopted = [c for c in runs if 'run' in c and opt(c, '--attempt-id') == 'calc_absolute-r1' and 'A-native-luna' in opt(c, '--out')]
        self.assertEqual(adopted, [])
        t1 = [c for c in runs if 'run' in c]
        self.assertEqual(len(t1), 3 * 12 * 2 - 1)                      # 72 units minus the adopted one
        for c in t1:
            self.assertEqual(opt(c, '--model'), MODEL)
            self.assertNotIn('\\', ' '.join(c))                          # forward-slash paths only
        # arms in order, one at a time: plain, careful, cc
        order = [opt(c, '--out').rstrip('/').split('/')[-1] for c in t1]
        self.assertNotIn('A-native-luna', order[:2])               # the preflight pass runs first: the adopted plain unit is skipped
        self.assertLess(order.index('A-verify-luna'), order.index('A-cclive-luna'))
        # careful inputs carry the one sentence; cc inputs come from cc-live
        task = (self.out / 'A-verify-inputs' / 'calc_absolute' / 'task.txt').read_text()
        self.assertTrue(task.endswith('\n\n' + slate.T1_CAREFUL + '\n'))
        # T3: heldout and contract, luna, 1 rep; T4; T5 with --skill-detail full
        for bench in ('heldout', 'contract', 'haltbench'):
            full = [c for c in commands(r, bench + ' run') if '--case' not in c]
            self.assertEqual(len(full), 1)
            self.assertEqual((opt(full[0], '--reps'), opt(full[0], '--model')), ('1', MODEL))
            self.assertTrue(opt(full[0], '--out').endswith('/modelbench/' + bench))
        t5 = [c for c in commands(r, 'planner run') if '--task' not in c]
        self.assertEqual((opt(t5[0], '--skill-detail'), opt(t5[0], '--repeats'), opt(t5[0], '--model')), ('full', '1', MODEL))
        # preflight comes before the first long block: the first pass over T1 touches only item one
        summary = json.loads((self.out / 'summary.json').read_text())
        self.assertEqual(set(summary['tests']), {'T1', 'T2', 'T3', 'T4', 'T5'})
        self.assertIn('| plain |', (self.out / 'SUMMARY.md').read_text())
        self.assertEqual(summary['tests']['T1']['plain']['counts']['wrong'], 23)    # the adopted unit has no session folder in this fake
        self.assertEqual(summary['tests']['T1']['cc']['tokens_per_correct'], 1100)
        self.assertEqual(summary['tests']['T2']['careful']['runs'], 2)
        self.assertEqual(summary['tests']['T5']['A_declared']['counts']['correct'], 12)
        self.assertEqual(summary['tests']['T5']['B_skill_full']['counts']['wrong'], 12)

    def test_resume_issues_no_second_run(self):
        r = FakeRunner()
        self.assertEqual(self.go(r), 0)
        r2 = FakeRunner()
        self.assertEqual(self.go(r2), 0)
        self.assertEqual([c for c in commands(r2, 'nativetask') if 'run' in c], [])
        self.assertEqual([c for c in commands(r2, 'collect.sh')], [c for c in commands(r2, 'collect.sh')])
        # model benches and the planner are asked again, but they skip finished units themselves (--resume for the planner)
        self.assertTrue(all('--resume' in c for c in commands(r2, 'planner run')))

    def test_preflight_failure_stops_before_the_long_blocks(self):
        r = FakeRunner(fail_label='t1-plain')
        self.assertEqual(self.go(r, '--only', 'T1,T3'), 3)
        self.assertEqual(len([c for c in commands(r, 'nativetask') if 'run' in c]), 3)    # one preflight unit per arm, then stop
        self.assertEqual(commands(r, 'heldout run'), [])

    def test_extra_arm_hooks_and_refused_keys(self):
        cfg = Path(self.tmp.name) / 'rsi.json'
        served, code = Path(self.tmp.name) / 'served', Path(self.tmp.name) / 'code'
        served.mkdir()
        code.mkdir()
        cfg.write_text(json.dumps({'t1': {'served': str(served)}, 't2': {'code_root': str(code)}}))
        r = FakeRunner()
        self.assertEqual(self.go(r, '--arm', 'rsi=' + str(cfg), '--only', 'T1,T2'), 0)
        live = commands(r, 'cc_live_inputs.py')
        self.assertIn('--served', live[-1])
        self.assertEqual(opt(live[-1], '--served'), served.as_posix())
        t2 = [(c, e) for k, c, e in r.calls if k == 'run' and 'collect.sh' in ' '.join(c) and e.get('ARMS', '').startswith('rsi=cc')]
        self.assertTrue(t2)
        self.assertEqual(t2[0][1]['CODE_ROOT'], code.as_posix())
        for name in ('plain', 'careful', 'cc'):
            self.assertTrue(any(e.get('ARMS') == name for _, c, e in r.calls if 'collect.sh' in ' '.join(c)))
        summary = json.loads((self.out / 'summary.json').read_text())
        self.assertIn('rsi', summary['tests']['T1'])
        self.assertIn('rsi', summary['tests']['T2'])
        bad = Path(self.tmp.name) / 'bad.json'
        bad.write_text(json.dumps({'heldout': {'x': 1}}))
        self.assertEqual(self.go(FakeRunner(), '--arm', 'x=' + str(bad), '--only', 'T3'), 2)

    def test_arm_names_cannot_shadow_existing_arms(self):
        cfg = Path(self.tmp.name) / 'c.json'
        cfg.write_text('{}')
        with self.assertRaises(SystemExit):
            slate.parse_arms(['cc=' + str(cfg)])

    def test_modelbench_class_mapping(self):
        base = dict(case='c', arm='cc', rep=1, cost=dict(calls=2, tokens=10, input_tokens=7, output_tokens=3, wall_s=1.0))
        self.assertEqual(slate.mb_row('heldout', dict(base, passed_all=False))['cls'], 'wrong')
        self.assertEqual(slate.mb_row('contract', dict(base, correct_and_compliant=True))['cls'], 'correct')
        for label, want in (('correct', 'correct'), ('correct_stop', 'stopped'), ('false_stop', 'false_stop'), ('fabricated', 'wrong'), ('wrong_value', 'wrong')):
            self.assertEqual(slate.mb_row('haltbench', dict(base, label=label))['cls'], want)
        self.assertEqual(slate.mb_row('haltbench', dict(base, label='correct'))['input_tokens'], 7)


if __name__ == '__main__':
    unittest.main()
