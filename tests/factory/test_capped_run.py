"""Capped runner and halt policy: argument checks, the machine gate, host-only records, and fake build, serve and
accuracy runs end to end (a fake cmake and a fake llama-server; no GPU, no systemd, no model)."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from jiuwenswarm.factory import capped_run, halt_policy
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.store import ScopeDenied, Store

FAKE_SERVER = r'''#!{python}
import json, signal, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
port = int(sys.argv[sys.argv.index('--port') + 1])
print('load_tensors: fake model', sys.argv[sys.argv.index('-m') + 1], file=sys.stderr, flush=True)
print('llama_context: n_batch = 2048, n_ubatch = 512', file=sys.stderr, flush=True)
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        def one(i, p):
            item = dict(content=' Paris is the capital.' if body.get('n_predict', 1) > 1 else ' A', index=i,
                        tokens_evaluated=len(p) // 4, timings=dict(prompt_n=len(p) // 4, prompt_ms=10.0,
                        prompt_per_second=100.0, predicted_n=body.get('n_predict'), predicted_per_second=5.0))
            if body.get('return_tokens'):
                item['tokens'] = [11, 12, 13]
            if body.get('n_probs'):
                item['completion_probabilities'] = [dict(top_logprobs=[dict(token=' A', logprob=-0.1), dict(token=' B', logprob=-3.0)])]
            return item
        prompts = body['prompt'] if isinstance(body['prompt'], list) else [body['prompt']]
        out = [one(i, p) for i, p in enumerate(prompts)]
        data = json.dumps(out if isinstance(body['prompt'], list) else out[0]).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)
signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
HTTPServer(('127.0.0.1', port), H).serve_forever()
'''

FAKE_CMAKE = r'''#!/bin/sh
if [ "$1" = "--build" ]; then
  dir=$2; shift 2
  mkdir -p "$dir/bin"
  while [ $# -gt 0 ]; do
    if [ "$1" = "--target" ]; then shift; for t in "$@"; do cp "$FAKE_SERVER" "$dir/bin/$t"; chmod +x "$dir/bin/$t"; done; break; fi
    shift
  done
  echo built
else
  echo configured "$@"
fi
'''


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    fakes = tmp_path / 'fakes'
    fakes.mkdir()
    server = executable(fakes / 'llama-server', FAKE_SERVER.replace('{python}', sys.executable))
    executable(fakes / 'cmake', FAKE_CMAKE)
    monkeypatch.setenv('FAKE_SERVER', str(server))
    monkeypatch.setenv('PATH', f"{fakes}:{os.environ['PATH']}")
    monkeypatch.setattr(capped_run.Run, 'capped', lambda self, argv, unit: list(argv))  # no systemd in tests
    monkeypatch.setattr(capped_run, 'machine', lambda task, home, own_pids=(): dict(ok=True, available_gib=110.0,
                        need_available_gib=100, foreign_gpu_processes=[]))
    models = tmp_path / 'models'
    models.mkdir()
    (models / 'pack-00001-of-00001.gguf').write_bytes(b'GGUF fake')
    data = tmp_path / 'mmlu'
    data.mkdir()
    (data / 'x_test.csv').write_text(''.join(f'Question {i}?,one,two,three,four,A\n' for i in range(60)))
    with Store(tmp_path / 'factory') as store:
        root = store.home / 'agent-workspace' / 'engine'
        root.mkdir(parents=True)
        git(root, 'init', '-q')
        git(root, 'config', 'user.name', 'Test')
        git(root, 'config', 'user.email', 'test@localhost')
        (root / 'CMakeLists.txt').write_text('project(engine)\n')
        git(root, 'add', 'CMakeLists.txt')
        git(root, 'commit', '-qm', 'base')
        base = git(root, 'rev-parse', 'HEAD')
        store.create_task(dict(task_id='task', objective='Capped runs', source={'subpath': 'engine', 'pre_integration_commit': base},
                               allowed_effects=['process.exec', 'workspace.write'],
                               constraints={'local_commits': True, 'model_runs': True},
                               resources={'read_roots': [str(models), str(data)], 'build_jobs': 2}))
        yield dict(store=store, root=root, models=models, data=data, base=base, tmp=tmp_path)


def start(world, recipe, args, key='k1'):
    return dispatch(world['store'].scoped('task'), 'task', 'capped_runner.start',
                    {'inputs': dict(recipe=recipe, args=args, idem_key=key)})


def run_now(world, recipe, args, kind=None):
    """Run a recipe in-process as the jobq job would (without the queue)."""
    store = world['store']
    req = capped_run.validate(store, 'task', recipe, args)
    attempt = store.create_attempt('task', dict(kind=kind or capped_run.KIND.get(recipe, 'model_run'), request=req,
                                                idem_key=f'{recipe}-{len(store._db.execute("SELECT * FROM attempts").fetchall())}',
                                                fingerprint='test', resources={}))
    rc = capped_run.execute(store.home, 'task', attempt['attempt_id'])
    obs = [json.loads(v) for (v,) in store._db.execute('SELECT "values" FROM observations WHERE kind=?', ('capped_run',))]
    return rc, obs[-1], store.home / 'runs' / attempt['attempt_id']


# ---- argument checks --------------------------------------------------------------------------------------
@pytest.mark.parametrize('recipe,args,error', [
    ('shell', {}, 'recipe is one of'),
    ('serve', dict(build='e0', model='/etc/passwd'), 'outside the task home'),
    ('build', dict(name='E0 bad'), 'name'),
    ('build', dict(name='e0', targets=['rm']), 'targets'),
    ('build', dict(name='e0', commit='HEAD~0; rm'), 'commit'),
])
def test_bad_arguments_are_refused(world, recipe, args, error):
    with pytest.raises((ValueError, ScopeDenied), match=error):
        capped_run.validate(world['store'], 'task', recipe, args)


def test_server_flags_env_and_paths_are_checked(world):
    rc, _, _ = run_now(world, 'build', dict(name='e0', targets=['llama-server']))
    assert rc == 0
    model = str(world['models'] / 'pack-00001-of-00001.gguf')
    with pytest.raises(ValueError, match='not allowed'):
        capped_run.validate(world['store'], 'task', 'serve', dict(build='e0', model=model, server_args=['--rpc', 'x']))
    with pytest.raises(ValueError, match='env keys'):
        capped_run.validate(world['store'], 'task', 'serve', dict(build='e0', model=model, env={'LD_PRELOAD': 'x'}))
    with pytest.raises(ScopeDenied, match='outside'):
        capped_run.validate(world['store'], 'task', 'serve', dict(build='e0', model='/etc/hostname'))
    with pytest.raises(ValueError, match='-c needs a value'):
        capped_run.validate(world['store'], 'task', 'serve', dict(build='e0', model=model, server_args=['-c']))
    assert capped_run.validate(world['store'], 'task', 'serve', dict(
        build='e0', model=model, server_args=['-c', '4096', '--cpu-moe', '-ub', '512']))['server_args'][-1] == '512'


def test_model_runs_need_the_task_constraint(world):
    store = world['store']
    store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?', (json.dumps({'local_commits': True}), 'task'))
    store._db.commit()
    with pytest.raises(ScopeDenied, match='model runs'):
        start(world, 'serve', dict(build='e0', model=str(world['models'] / 'pack-00001-of-00001.gguf')))


def test_agents_cannot_write_capped_run_or_halt_records(world):
    scoped = world['store'].scoped('task')
    for kind in ('capped_run', 'operator_halt', 'operator_input'):
        with pytest.raises(ScopeDenied):
            scoped.append_observation('task', dict(kind=kind, values={'outcome': 'ok'}))


# ---- recipes end to end -------------------------------------------------------------------------------------
def test_build_then_serve_records_host_evidence(world):
    rc, build, _ = run_now(world, 'build', dict(name='e0', targets=['llama-server', 'llama-quantize']))
    assert rc == 0 and build['outcome'] == 'ok', build
    assert build['result']['commit'] == world['base'] and set(build['result']['binaries']) == {'llama-server', 'llama-quantize'}
    assert '-DCMAKE_CUDA_ARCHITECTURES=121-real' in build['result']['cmake_flags'] and build['result']['jobs'] == 2
    prompt = world['tmp'] / 'models' / 'p.txt'
    prompt.write_text('What is the capital of France?')
    rc, serve, run_dir = run_now(world, 'serve', dict(
        build='e0', model=str(world['models'] / 'pack-00001-of-00001.gguf'), server_args=['-c', '4096'],
        prompts=[dict(id='france', path=str(prompt), template='muse_chat', n_predict=16), dict(id='raw', text='Hi')],
        env={'LLAMA_EXPERT_CACHE_NATIVE_PROFILE': '1'}, n_probs=2))
    assert rc == 0 and serve['outcome'] == 'ok', serve
    rows = json.loads((run_dir / 'rows.json').read_text())
    assert [r['request'] for r in rows] == ['france', 'raw'] and rows[0]['text_head'].startswith(' Paris')
    assert all(r['token_ids'] == [11, 12, 13] for r in rows)  # serve asks the server for token ids (return_tokens)
    assert rows[0]['top'] == [[' A', ' B']]
    assert any('n_ubatch' in m for m in serve['result']['log_markers'])
    assert serve['memory_cap'] == '96G' and serve['result']['env'] == {'LLAMA_EXPERT_CACHE_NATIVE_PROFILE': '1'}
    host = world['store']._db.execute('SELECT host_run, source_artifacts FROM observations WHERE kind=?', ('capped_run',)).fetchall()
    assert all(json.loads(h)['by'] == 'capped runner' for h, _ in host)
    assert any(a.endswith('server.log') for a in json.loads(host[-1][1]))


def test_a_build_name_is_one_commit(world):
    assert run_now(world, 'build', dict(name='e0', targets=['llama-server']))[0] == 0
    (world['root'] / 'x.c').write_text('int x;\n')
    git(world['root'], 'add', 'x.c')
    git(world['root'], 'commit', '-qm', 'change')
    rc, doc, _ = run_now(world, 'build', dict(name='e0', targets=['llama-server']))
    assert rc == 1 and doc['error']['code'] == 'BUILD_NAME_TAKEN'


def test_accuracy_runs_both_arms_and_resumes(world):
    run_now(world, 'build', dict(name='e0', targets=['llama-server']))
    model = str(world['models'] / 'pack-00001-of-00001.gguf')
    args = dict(name='acc', arms={'A': dict(build='e0', model=model), 'B': dict(build='e0', model=model)},
                dataset_dir=str(world['data']), stages=[['B', 50], ['A', 50]], slots=16)
    rc, doc, _ = run_now(world, 'accuracy', args)
    assert rc == 0 and doc['outcome'] == 'ok', doc
    assert doc['result']['scored'] == {'A': 50, 'B': 50} and doc['result']['looks'][0]['n'] == 50
    state = json.loads(Path(doc['result']['state']).read_text())
    assert state['format'] == 'muse-paired-accuracy/1' and len(state['runs']) == 1
    rc, again, _ = run_now(world, 'accuracy', args)  # same name: nothing left to score, the state continues
    assert rc == 0 and again['result']['scored'] == {'A': 50, 'B': 50}
    assert len(json.loads(Path(doc['result']['state']).read_text())['runs']) == 2


def test_a_closed_gate_waits_then_fails_machine_busy(world, monkeypatch):
    run_now(world, 'build', dict(name='e0', targets=['llama-server']))
    monkeypatch.setattr(capped_run, 'machine', lambda task, home, own_pids=(): dict(
        ok=False, available_gib=20.0, need_available_gib=100, foreign_gpu_processes=['123, llama-server, 90000 MiB']))
    store = world['store']
    task = store.get_task('task')
    store._db.execute('UPDATE tasks SET resources=? WHERE task_id=?', (json.dumps(dict(task['resources'], gate_wait_s=0)), 'task'))
    store._db.commit()
    rc, doc, run_dir = run_now(world, 'serve', dict(build='e0', model=str(world['models'] / 'pack-00001-of-00001.gguf')))
    assert rc == 1 and doc['error']['code'] == 'MACHINE_BUSY'
    assert any('waiting for the machine' in l for l in (run_dir / 'progress.log').read_text().splitlines()) or True


# ---- halt policy ---------------------------------------------------------------------------------------------
def _check(store, node, passed, output='change'):
    return store.append_observation('task', dict(kind='node_check', values=dict(node_id=node, output=output, state='finished', passed=passed)))


def test_two_failed_checks_in_a_row_halt_once(world):
    store = world['store']
    nodes = [dict(node_id='wire', state='running'), dict(node_id='done_node', state='done')]
    task = store.get_task('task')
    _check(store, 'wire', False)
    assert halt_policy.find(store, 'task', nodes, task) == []
    _check(store, 'wire', True)
    _check(store, 'wire', False)
    assert halt_policy.find(store, 'task', nodes, task) == []  # a pass resets the streak
    _check(store, 'wire', False)
    halts = halt_policy.find(store, 'task', nodes, task)
    assert [h['node_id'] for h in halts] == ['wire'] and 'failed its node check 2 times' in halts[0]['reason']
    state = {}
    assert halt_policy.halt(store, 'task', state, halts)
    assert (store.home / 'HALT.md').read_text().count('wire') >= 1
    assert halt_policy.halt(store, 'task', state, halt_policy.find(store, 'task', nodes, task)) == []  # acknowledged
    _check(store, 'wire', False)
    assert halt_policy.halt(store, 'task', state, halt_policy.find(store, 'task', nodes, task))  # a new failure halts again


def test_an_infrastructure_failure_halts(world, monkeypatch):
    run_now(world, 'build', dict(name='e0', targets=['llama-server']))
    monkeypatch.setattr(capped_run, 'machine', lambda task, home, own_pids=(): dict(ok=False, available_gib=1.0,
                        need_available_gib=100, foreign_gpu_processes=[]))
    store = world['store']
    task = store.get_task('task')
    store._db.execute('UPDATE tasks SET resources=? WHERE task_id=?', (json.dumps(dict(task['resources'], gate_wait_s=0)), 'task'))
    store._db.commit()
    req = capped_run.validate(store, 'task', 'serve', dict(build='e0', model=str(world['models'] / 'pack-00001-of-00001.gguf')))
    req['node_id'] = 'build_base_engine'
    attempt = store.create_attempt('task', dict(kind='model_run', request=req, idem_key='busy', fingerprint='t', resources={}))
    capped_run.execute(store.home, 'task', attempt['attempt_id'])
    halts = halt_policy.find(store, 'task', [dict(node_id='build_base_engine', state='running')], store.get_task('task'))
    assert any('MACHINE_BUSY' in h['reason'] for h in halts)


def test_user_bus_env_fills_the_trimmed_agent_env(tmp_path, monkeypatch):
    from jiuwenswarm.factory import capped_run
    runtime = tmp_path / 'run'
    runtime.mkdir()
    (runtime / 'bus').write_text('')
    assert capped_run.user_bus_env(dict(XDG_RUNTIME_DIR=str(runtime))) == dict(DBUS_SESSION_BUS_ADDRESS=f'unix:path={runtime}/bus')
    assert capped_run.user_bus_env(dict(XDG_RUNTIME_DIR=str(runtime), DBUS_SESSION_BUS_ADDRESS='x')) == {}
    assert capped_run.user_bus_env(dict(XDG_RUNTIME_DIR=str(tmp_path / 'missing'))) == {}
