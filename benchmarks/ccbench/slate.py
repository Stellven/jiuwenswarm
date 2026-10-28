"""The luna test slate in one command (host only; start it with scripts/ai4r-bench):

  sh scripts/ai4r-bench slate luna --out DIR [--arm NAME=CONFIG ...] [--only T1,T2,...] [--model gpt-6-luna] [--doctor-only]

Model + JiuwenSwarm (theirs: plain, careful) against model + JiuwenSwarm + AI4Research capsules (ours: cc). One model job at a
time (parallel jobs on one codex account hit HTTP 429). Steps, in this order:
  1. doctor    codex binary, Docker, image ai4r:ccbench-native, fixtures, then the selftests of the selected tests. Fails fast with the fix.
  2. preflight one unit per test and arm (the first case, 1 rep). A failed preflight stops the slate before the long blocks.
  3. blocks    T1 nativeadmit (plain, careful, cc; 12 items x 2 reps), T2 inputguard (11 fixtures), T3 heldout + contract,
               T4 haltbench, T5 planner with --skill-detail full. All on --model, --reps 1 except T1.
  4. score     DIR/SUMMARY.md and DIR/summary.json: counts, input / output / total tokens, calls, wall time, tokens per correct.
Resumable: rerun the same command and finished units are skipped (an attempt record or result file already exists). T1 uses the
folder names of the already-running luna T1 (A-native-luna, A-verify-luna, A-cclive-luna), so those sessions are adopted, not rerun.

--arm NAME=CONFIG adds an arm (for example RSI) next to the existing ones; CONFIG is a JSON file:
  {"t1": {"served": "DIR with calc_tool.py and table_tool.py"},   T1: cc_live_inputs.py --served DIR, then the same agent run
   "t2": {"code_root": "CHECKOUT"}}                                T2: the input guard of that checkout (AI4R_CODE_ROOT), then the agent
Keys for T3, T4 and T5 are refused: those benches have no library to point at (see LUNA-SLATE.md). Existing arms are untouched.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import cost  # noqa: E402
import roots  # noqa: E402

MODEL = 'gpt-6-luna'
IMAGE = 'ai4r:ccbench-native'
TESTS = ('T1', 'T2', 'T3', 'T4', 'T5')
T1_CAREFUL = 'Before you trust the team tool, check that its output is correct for this data.'
T1_REPS = 2
# T1 folders: the names the already-running luna T1 uses, so its finished sessions are adopted.
T1_DIRS = {'plain': 'A-native-luna', 'careful': 'A-verify-luna', 'cc': 'A-cclive-luna'}
MODEL_BENCHES = {'T3': ('heldout', 'contract'), 'T4': ('haltbench',)}
BENCH_ARMS = {'heldout': ('plain', 'verify', 'selftest', 'cc'), 'contract': ('plain', 'verify', 'cc'), 'haltbench': ('plain', 'verify', 'cc')}
SELFTESTS = {'T1': ('nativeadmit', 'nativetask', 'cost'), 'T2': ('inputguard', 'cost'), 'T3': ('modelbench', 'heldout', 'contract'),
             'T4': ('modelbench', 'haltbench'), 'T5': ('planner',)}
CONFIG_KEYS = {'t1': {'served'}, 't2': {'code_root'}}


def posix(path):
    return Path(path).as_posix()


class Runner:
    """Runs one command at a time. Output goes to a numbered log file under DIR/logs."""

    def __init__(self, logdir):
        self.logdir = Path(logdir)
        self.n = 0

    def run(self, argv, cwd=None, env=None, label='cmd'):
        self.logdir.mkdir(parents=True, exist_ok=True)
        self.n += 1
        log = self.logdir / ('%03d-%s.log' % (self.n, ''.join(c if c.isalnum() or c in '-_.' else '_' for c in label)[:60]))
        print('[slate] %s  (log %s)' % (' '.join(map(str, argv)), log.name), flush=True)
        with log.open('wb') as stream:
            stream.write(('$ %s\n' % ' '.join(map(str, argv))).encode('utf-8'))
            stream.flush()
            try:
                return subprocess.run(list(map(str, argv)), cwd=cwd, env=dict(os.environ, **(env or {})), stdout=stream, stderr=subprocess.STDOUT).returncode
            except OSError as exc:
                stream.write(('%s\n' % exc).encode('utf-8'))
                return 127

    def capture(self, argv, cwd=None):
        try:
            done = subprocess.run(list(map(str, argv)), cwd=cwd, capture_output=True, timeout=120)
            return done.returncode, done.stdout.decode('utf-8', 'replace') + done.stderr.decode('utf-8', 'replace')
        except (OSError, subprocess.SubprocessError) as exc:
            return 127, str(exc)


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8-sig'))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes((json.dumps(value, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))


class Slate:
    def __init__(self, out, runner, tests=TESTS, model=MODEL, extra_arms=None, repo=REPO):
        self.out, self.runner, self.tests, self.model = Path(out), runner, list(tests), model
        self.extra = extra_arms or {}
        self.repo = Path(repo)
        self.problems = []
        self.warnings = []
        self.notes = []

    # ---------------------------------------------------------------- helpers
    def bench(self, *argv):
        return ['sh', 'scripts/ai4r-bench', *argv]

    def sh(self, argv, label, env=None):
        return self.runner.run(argv, cwd=self.repo, env=env, label=label)

    def py(self, script, *argv):
        return [sys.executable, '-B', posix(HERE / script), *argv]

    def items(self):
        return sorted(p.name for p in (HERE / 'nativeadmit' / 'items').iterdir() if p.is_dir())

    def arm_config_problems(self):
        out = []
        for name, cfg in self.extra.items():
            for key in cfg:
                if key not in CONFIG_KEYS:
                    out.append('arm %s: key %r is not supported. T3, T4 and T5 (heldout, contract, haltbench, planner) take no library or '
                               'code root, so an extra arm cannot differ there; they run the existing arms only. Allowed keys: t1, t2.' % (name, key))
                else:
                    unknown = set(cfg[key]) - CONFIG_KEYS[key]
                    if unknown:
                        out.append('arm %s: %s has unknown field(s) %s (allowed: %s)' % (name, key, sorted(unknown), sorted(CONFIG_KEYS[key])))
        return out

    # ---------------------------------------------------------------- doctor
    def doctor(self, selftests=True):
        p = self.problems
        if not roots.codex_bin():
            p.append('codex executable not found. Fix: put `codex` on PATH, or set AI4R_CODEX_BIN=/full/path/to/codex.')
        needs_docker = any(t in self.tests for t in ('T1', 'T2'))
        if needs_docker:
            rc, _ = self.runner.capture(['docker', 'info'])
            if rc != 0:
                p.append('Docker is not running or not installed. Fix: start Docker Desktop, then check `docker info`.')
            else:
                rc, _ = self.runner.capture(['docker', 'image', 'inspect', IMAGE])
                if rc != 0:
                    p.append('image %s not found. Fix: sh scripts/ai4r-bench build-native --yes --out %s' % (IMAGE, posix(self.out / 'native-image')))
        if 'T2' in self.tests and not roots.t2_fixtures().is_dir():
            p.append('T2 fixtures not found at %s. Fix: set AI4R_T2_FIXTURES to the folder holding <fixture>/{task.txt,inputs,fault.json}.' % posix(roots.t2_fixtures()))
        if not roots.bench_data().is_dir():
            self.warnings.append('AI4R_BENCH_DATA %s does not exist. The luna tests do not read it; only trapcheck does.' % posix(roots.bench_data()))
        p.extend(self.arm_config_problems())
        for name, cfg in self.extra.items():
            for key, field in (('t1', 'served'), ('t2', 'code_root')):
                if key in cfg and field in cfg[key] and not Path(cfg[key][field]).is_dir():
                    p.append('arm %s: %s.%s %s is not a folder.' % (name, key, field, cfg[key][field]))
        if not p and selftests:
            names = []
            for t in self.tests:
                names.extend(n for n in SELFTESTS[t] if n not in names)
            if self.sh(self.bench('selftest', '--host', *names), 'selftest') != 0:
                p.append('selftest failed for %s. Fix: read the newest *-selftest.log under %s, repair, rerun.' % (', '.join(names), posix(self.out / 'logs')))
        return p

    # ---------------------------------------------------------------- T1
    def t1_arms(self):
        arms = [(a, self.out / T1_DIRS[a]) for a in ('plain', 'careful', 'cc')]
        arms += [(n, self.out / 'T1' / n) for n, cfg in self.extra.items() if 't1' in cfg]
        return arms

    def t1_inputs(self, arm, item):
        if arm == 'plain':
            return HERE / 'nativeadmit' / 'items' / item / 'public'
        if arm == 'careful':
            return self.out / 'A-verify-inputs' / item
        if arm == 'cc':
            return self.out / 'A-cc' / 'cc-live' / item
        return self.out / 'T1' / (arm + '-inputs') / 'cc-live' / item

    def t1_prepare(self):
        import shutil
        careful = self.out / 'A-verify-inputs'
        if not careful.is_dir():
            for item in self.items():
                shutil.copytree(HERE / 'nativeadmit' / 'items' / item / 'public', careful / item)
                with (careful / item / 'task.txt').open('ab') as f:
                    f.write(('\n\n' + T1_CAREFUL + '\n').encode('utf-8'))
        first = self.items()[0]
        routes = [(self.out / 'A-cc', None)] + [(self.out / 'T1' / (n + '-inputs'), cfg['t1'].get('served')) for n, cfg in self.extra.items() if 't1' in cfg]
        for root, served in routes:
            if not (root / 'cc' / (first + '.json')).is_file():
                if self.runner.run(self.py('nativeadmit/cc_route.py', '--out', posix(root)), label='t1-cc_route') != 0:
                    self.problems.append('T1: cc_route failed for %s' % posix(root))
            if not (root / 'cc-live' / 'manifest.json').is_file():
                argv = self.py('nativeadmit/cc_live_inputs.py', '--out', posix(root))
                if served:
                    argv += ['--served', posix(served)]
                if self.runner.run(argv, label='t1-cc_live_inputs') != 0:
                    self.problems.append('T1: cc_live_inputs failed for %s' % posix(root))

    def t1_unit(self, arm, folder, item, rep):
        att = folder / 'attempts' / ('%s-r%d.json' % (item, rep))
        if att.exists():
            return 'skip'
        ledger = folder / 'ledgers' / item
        if not (ledger / 'ledger.sqlite3').exists():
            if self.sh(self.bench('nativetask', 'init-ledger', '--out', posix(ledger)), 't1-init-ledger') != 0:
                return 'fail'
        d = self.t1_inputs(arm, item)
        rc = self.sh(self.bench('nativetask', 'run', '--task-file', posix(d / 'task.txt'), '--inputs-dir', posix(d), '--ledger', posix(ledger / 'ledger.sqlite3'),
                                '--attempt-id', '%s-r%d' % (item, rep), '--model', self.model, '--image', IMAGE, '--execute', '--out', posix(folder)),
                     't1-%s-%s-r%d' % (arm, item, rep))
        return 'ok' if rc == 0 else 'fail'

    def t1_check(self, folder, item, rep):
        f = folder / 'sessions' / ('%s-r%d' % (item, rep)) / 'final-message.txt'
        return f.is_file() and f.stat().st_size > 0

    def t1_preflight(self):
        item = self.items()[0]
        bad = []
        for arm, folder in self.t1_arms():
            r = self.t1_unit(arm, folder, item, 1)
            if r == 'fail' or (r == 'ok' and not self.t1_check(folder, item, 1)):
                bad.append('T1 %s %s-r1: no final message (see the newest t1-%s log)' % (arm, item, arm))
        return bad

    def t1_run(self):
        failed = 0
        for arm, folder in self.t1_arms():
            for item in self.items():
                for rep in range(1, T1_REPS + 1):
                    failed += self.t1_unit(arm, folder, item, rep) == 'fail'
        return failed

    def t1_score(self):
        arms = [(a, f) for a, f in self.t1_arms() if (f / 'sessions').is_dir()]
        if not arms:
            return []
        score_dir = self.out / 'T1' / 'score'
        argv = self.py('nativeadmit/score_arms.py', '--out', posix(score_dir))
        for a, f in arms:
            argv += ['--arm', '%s=%s' % (a, posix(f))]
        self.runner.run(argv, label='t1-score')
        return rows_of(score_dir / 'score-arms.json')

    # ---------------------------------------------------------------- T2
    def t2_arms(self):
        return [('plain', 'plain', None), ('careful', 'careful', None), ('cc', 'cc', None)] + \
               [(n, 'cc', cfg['t2']['code_root']) for n, cfg in self.extra.items() if 't2' in cfg]

    def t2_prepare(self):
        if (self.out / 'T2' / 'inputs').is_dir():
            return
        import importlib.util
        spec = importlib.util.spec_from_file_location('inputguard_prepare', HERE / 'inputguard' / 'prepare.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.prepare(roots.t2_fixtures(), self.out / 'T2')

    def t2_collect(self, arm, base, code_root, fixture=None):
        env = {'MODEL': self.model, 'ARMS': arm if base == arm else '%s=%s' % (arm, base)}
        if code_root:
            env['CODE_ROOT'] = posix(code_root)
        if fixture:
            env['FIXTURES'] = fixture
        return self.sh(['sh', posix(HERE / 'inputguard' / 'collect.sh'), posix(self.repo), posix(self.out / 'T2')], 't2-%s%s' % (arm, '-pre' if fixture else ''), env=env)

    def t2_first(self):
        return sorted(p.name for p in (self.out / 'T2' / 'inputs' / 'plain').iterdir() if p.is_dir())[0]

    def t2_preflight(self):
        fx, bad = self.t2_first(), []
        for arm, base, code_root in self.t2_arms():
            rc = self.t2_collect(arm, base, code_root, fx)
            f = self.out / 'T2' / arm / 'sessions' / (fx + '-r1') / 'final-message.txt'
            if rc != 0 or not (f.is_file() and f.stat().st_size > 0):
                bad.append('T2 %s %s-r1: no final message (see the newest t2-%s-pre log)' % (arm, fx, arm))
        return bad

    def t2_run(self):
        return sum(self.t2_collect(arm, base, code_root) != 0 for arm, base, code_root in self.t2_arms())

    def t2_score(self):
        arms = [a for a, _, _ in self.t2_arms() if (self.out / 'T2' / a / 'sessions').is_dir()]
        if not arms:
            return []
        argv = self.py('inputguard/score.py', '--out', posix(self.out / 'T2' / 'score'))
        for a in arms:
            argv += ['--arm', '%s=%s' % (a, posix(self.out / 'T2' / a))]
        self.runner.run(argv, label='t2-score')
        return rows_of(self.out / 'T2' / 'score' / 'score.json')

    # ---------------------------------------------------------------- T3, T4 (modelbench)
    def mb_out(self, bench):
        return self.out / 'modelbench' / bench

    def mb_run(self, bench, *extra):
        return self.sh(self.bench(bench, 'run', '--execute', '--reps', '1', '--model', self.model, *extra, '--host', '--out', posix(self.mb_out(bench))), '%s-run' % bench)

    def mb_cases(self, bench):
        return [c['id'] for c in read_json(HERE / bench / 'cases.json')]

    def mb_preflight(self, bench):
        case, bad = self.mb_cases(bench)[0], []
        for arm in BENCH_ARMS[bench]:
            rc = self.mb_run(bench, '--case', case, '--arm', arm)
            res = self.mb_out(bench) / bench / self.model / case / ('%s-r1' % arm) / 'result.json'
            if rc != 0 or not res.is_file() or not all(c.get('ok') for c in read_json(res).get('calls', [])):
                bad.append('%s %s %s-r1: model call failed or no result (see the newest %s-run log)' % (bench, arm, case, bench))
        return bad

    def mb_score(self, bench):
        if not (self.mb_out(bench) / bench / self.model).is_dir():
            return []
        self.sh(self.bench(bench, 'score', '--model', self.model, '--host', '--out', posix(self.mb_out(bench))), '%s-score' % bench)
        data = self.mb_out(bench) / 'scores' / ('%s-%s.json' % (bench, self.model))
        if not data.is_file():
            return []
        return [mb_row(bench, u) for u in read_json(data)['units']]

    # ---------------------------------------------------------------- T5 (planner)
    def t5_out(self):
        return self.out / 'T5'

    def t5_run(self, *extra):
        return self.sh(self.bench('planner', 'run', '--model', self.model, '--repeats', '1', '--skill-detail', 'full', '--resume', *extra,
                                  '--execute', '--host', '--out', posix(self.t5_out())), 't5-run')

    def t5_preflight(self):
        task = read_json(HERE / 'planner' / 'tasks.json')[0]['id']
        rc, bad = self.t5_run('--task', task), []
        for cond in ('A', 'B'):
            u = self.t5_out() / 'runs' / self.model / task / ('%s-r1' % cond)
            f = u / 'reply.txt'
            run = read_json(u / 'run.json') if (u / 'run.json').is_file() else {}
            if rc != 0 or not f.is_file() or f.stat().st_size == 0 or run.get('timed_out') or run.get('returncode') not in (0, None):
                bad.append('T5 %s %s: planner call failed or empty reply (see the newest t5-run log)' % (task, cond))
        return bad

    def t5_score(self):
        base = self.t5_out() / 'runs' / self.model
        if not base.is_dir():
            return []
        self.sh(self.bench('planner', 'score', '--model', self.model, '--host', '--out', posix(self.t5_out())), 't5-score')
        data = self.t5_out() / 'scores' / (self.model + '.json')
        if not data.is_file():
            return []
        rows = []
        for plan in read_json(data)['plans']:
            run = base / plan['task'] / ('%s-r%d' % (plan['condition'], plan['repeat'])) / 'run.json'
            meta = read_json(run) if run.is_file() else {}
            tokens = meta.get('tokens_used') or []
            rows.append(dict(arm={'A': 'A_declared', 'B': 'B_skill_full'}[plan['condition']], cls='correct' if plan['score'].get('valid') else 'wrong',
                             input_tokens=meta.get('input_tokens'), output_tokens=meta.get('output_tokens'),
                             total_tokens=int(tokens[-1].replace(',', '')) if tokens else None, calls=1, wall_s=meta.get('elapsed_s'), unit='%s/%s' % (plan['task'], plan['condition'])))
        return rows

    # ---------------------------------------------------------------- driver
    def prepare(self):
        if 'T1' in self.tests:
            self.t1_prepare()
        if 'T2' in self.tests:
            self.t2_prepare()

    def preflight(self):
        """One unit per test and arm. Stops at the first test that fails so no more model calls are spent on a broken setup."""
        steps = []
        if 'T1' in self.tests:
            steps.append(self.t1_preflight)
        if 'T2' in self.tests:
            steps.append(self.t2_preflight)
        for t in ('T3', 'T4'):
            if t in self.tests:
                steps.extend(lambda b=b: self.mb_preflight(b) for b in MODEL_BENCHES[t])
        if 'T5' in self.tests:
            steps.append(self.t5_preflight)
        for step in steps:
            bad = step()
            if bad:
                return bad
        return []

    def blocks(self):
        failed = {}
        if 'T1' in self.tests:
            failed['T1'] = self.t1_run()
        if 'T2' in self.tests:
            failed['T2'] = self.t2_run()
        for t in ('T3', 'T4'):
            if t in self.tests:
                failed[t] = sum(self.mb_run(b) != 0 for b in MODEL_BENCHES[t])
        if 'T5' in self.tests:
            failed['T5'] = self.t5_run() != 0
        return failed

    def collect_runs(self):
        runs = {}
        if 'T1' in self.tests:
            runs['T1'] = self.t1_score()
        if 'T2' in self.tests:
            runs['T2'] = self.t2_score()
        for t in ('T3', 'T4'):
            if t in self.tests:
                runs[t] = [r for b in MODEL_BENCHES[t] for r in self.mb_score(b)]
        if 'T5' in self.tests:
            runs['T5'] = self.t5_score()
        return runs

    def provenance(self):
        rc, ident = self.runner.capture(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'])
        rc2, digests = self.runner.capture(['docker', 'image', 'inspect', IMAGE, '--format', '{{json .RepoDigests}}'])
        return dict(model=self.model, product=roots.product_commit(), image=dict(tag=IMAGE, id=ident.strip() if rc == 0 else None,
                    repo_digests=json.loads(digests) if rc2 == 0 and digests.strip().startswith('[') else None),
                    extra_arms=sorted(self.extra), finished_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))

    def summarize(self, runs, failed=None):
        tables = {t: cost.cost_table(rows) for t, rows in runs.items() if rows}
        summary = dict(provenance=self.provenance(), failed_blocks=failed or {}, tests=tables,
                       not_applicable={n: 'T3, T4, T5 have no library or code root; only the existing arms run there' for n in self.extra})
        write_json(self.out / 'summary.json', summary)
        lines = ['# Luna test slate', '',
                 'Model %s. Product commit %s (dirty: %s). Image %s %s.' % (self.model, summary['provenance']['product']['commit'], summary['provenance']['product']['dirty'],
                                                                         IMAGE, summary['provenance']['image']['id'] or 'id not read'),
                 'Arms: plain = model + JiuwenSwarm; careful = plain + one sentence telling it to check; cc = plain + AI4Research layer (T3 to T5 use the bench names).',
                 'Tokens come from the model usage records. A "-" is a figure that was not recorded; nothing is estimated.', '']
        if failed and any(failed.values()):
            lines += ['Blocks with failed commands: %s. Rerun the same command to resume.' % ', '.join(k for k, v in failed.items() if v), '']
        for t in TESTS:
            if t in tables:
                lines.append(cost.markdown(tables[t], '## %s' % t))
            elif t in self.tests:
                lines += ['## %s' % t, '', 'No scored results yet.', '']
        (self.out / 'SUMMARY.md').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
        return summary


def rows_of(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [dict(arm=r['arm'], cls=r['cls'], input_tokens=r.get('input_tokens'), output_tokens=r.get('output_tokens'),
                 total_tokens=r.get('total_tokens'), calls=r.get('calls'), wall_s=r.get('wall_s'), unit=r.get('session') or r.get('fixture'))
            for r in read_json(path)['rows']]


def mb_row(bench, unit):
    """One scored modelbench unit as a cost row. The class names are the bucket names of cost.py."""
    if bench == 'heldout':
        cls = 'correct' if unit['passed_all'] else 'wrong'
    elif bench == 'contract':
        cls = 'correct' if unit['correct_and_compliant'] else 'wrong'
    else:
        label = unit['label']
        cls = {'correct': 'correct', 'correct_stop': 'stopped', 'wrong_reason_stop': 'stopped', 'false_stop': 'false_stop'}.get(label, 'wrong')
    c = unit['cost']
    return dict(arm='%s:%s' % (bench, unit['arm']), cls=cls, input_tokens=c.get('input_tokens'), output_tokens=c.get('output_tokens'),
                total_tokens=c.get('tokens'), calls=c.get('calls'), wall_s=c.get('wall_s'), unit='%s/%s-r%d' % (unit['case'], unit['arm'], unit['rep']))


def parse_arms(specs):
    extra = {}
    for spec in specs or []:
        name, sep, path = spec.partition('=')
        if not sep or not name or not path or name in ('plain', 'careful', 'cc'):
            raise SystemExit('--arm needs NAME=CONFIG.json with a new NAME (not plain, careful or cc), got %r' % spec)
        if not Path(path).is_file():
            raise SystemExit('--arm %s: config file %s not found' % (name, path))
        extra[name] = read_json(path)
    return extra


def main(argv=None, runner=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('suite', choices=['luna'])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--arm', action='append', metavar='NAME=CONFIG', help='extra arm, for example RSI (JSON config, see above)')
    ap.add_argument('--only', help='comma list of tests, for example T1,T2 (default all)')
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--doctor-only', action='store_true', help='check the machine and run the selftests, then stop')
    ap.add_argument('--no-selftest', action='store_true', help='skip the selftests in the doctor step')
    args = ap.parse_args(argv)
    tests = [t.strip().upper() for t in args.only.split(',')] if args.only else list(TESTS)
    if any(t not in TESTS for t in tests):
        raise SystemExit('--only takes tests from %s' % ', '.join(TESTS))
    args.out.mkdir(parents=True, exist_ok=True)
    slate = Slate(args.out.resolve(), runner or Runner(args.out.resolve() / 'logs'), tests, args.model, parse_arms(args.arm))
    problems = slate.doctor(selftests=not args.no_selftest)
    for w in slate.warnings:
        print('[slate] warning:', w)
    if problems:
        print('[slate] doctor: cannot start\n  - ' + '\n  - '.join(problems), file=sys.stderr)
        return 2
    print('[slate] doctor: ok')
    if args.doctor_only:
        return 0
    slate.prepare()
    if slate.problems:
        print('[slate] prepare failed\n  - ' + '\n  - '.join(slate.problems), file=sys.stderr)
        return 2
    bad = slate.preflight()
    if bad:
        print('[slate] preflight failed; nothing long was started. Fix, then rerun the same command (finished units are kept):\n  - ' + '\n  - '.join(bad), file=sys.stderr)
        return 3
    print('[slate] preflight: ok')
    failed = slate.blocks()
    summary = slate.summarize(slate.collect_runs(), failed)
    print('[slate] wrote %s and %s' % (args.out / 'SUMMARY.md', args.out / 'summary.json'))
    return 1 if any(failed.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
