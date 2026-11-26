"""Capped runs for a task's agent: engine builds, checkpoint conversion, requantization, server runs and paired
accuracy, each as a durable job (jobq) the controller waits on and a later controller run reconciles.

The agent has no shell. It starts a run with capped_runner.start (a recipe and its arguments), reads progress
with capped_runner.status and cancels with capped_runner.cancel. Every recipe builds its own command line from
validated arguments; nothing the agent sends is executed as given.

Every model load (convert, quantize, serve, accuracy) runs under
    systemd-run --user --scope -p MemoryMax=<cap> -p MemorySwapMax=0
and only after the machine gate passes: enough available memory and no GPU process this task does not own.
While the gate fails the job waits (gate_wait_s, then it fails MACHINE_BUSY). During a run, available memory
below FLOOR_GIB stops the run (MEMORY_LOW): the box is shared.

At the end the job records one host observation of kind capped_run (agents cannot write it) with the recipe,
the arguments, the command, exit code, wall time, peak cgroup memory, the lowest available memory seen and the
recipe's own results; logs and result files are stored as artifacts run-<attempt>-<name>.

Resumable: a job's outputs go to FACTORY_HOME/runs/<attempt> (packs to FACTORY_HOME/packs/<name>). A job that
dies is a failed attempt; starting the recipe again with a new idem_key reruns it (accuracy keeps its scored
rows in FACTORY_HOME/accuracy/<name>/state.json and continues where it stopped).

    python -m jiuwenswarm.factory.capped_run _exec <task_id> <attempt_id>     # jobq runs this
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import uuid

from . import capped_replay
from .store import ScopeDenied, Store

RECIPES = ('build', 'convert', 'quantize', 'serve', 'accuracy', 'manifest')
MODEL_LOADS = {'convert', 'quantize', 'serve', 'accuracy'}
# attempt kind: build counts against build_attempts, model_run against gpu_launches; manifest (hashing files) neither
KIND = {'build': 'build', 'manifest': 'manifest'}
REPLAY_KIND = 'pack_replay'
CAP = '96G'
NEED_GIB = 100       # available memory a model load needs before it starts
FLOOR_GIB = 6        # a running load is stopped below this
GATE_WAIT_S = 6 * 3600
NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,40}$')
SHA = re.compile(r'^[0-9a-f]{7,40}$')
ENV_KEY = re.compile(r'^(LLAMA|GGML)_[A-Z0-9_]{1,64}$')
TARGETS = {'llama-server', 'llama-quantize', 'llama-imatrix', 'llama-cli', 'llama-completion', 'llama-gguf-split', 'llama-bench'}
# llama-server flags an agent may set (value count); always added: -m, --host, --port, -lv 4
SERVER_FLAGS = {'-c': 1, '-b': 1, '-ub': 1, '-np': 1, '-kvu': 0, '--cpu-moe': 0, '--n-cpu-moe': 1, '-ngl': 1,
                '--moe-cache-mib': 1, '--moe-cache-cpu-share': 1, '-lm': 1, '-fa': 1, '-t': 1, '-tb': 1, '-fitt': 1,
                '-fit': 1,
                '--no-warmup': 0, '-ctk': 1, '-ctv': 1, '--seed': 1}
MUSE_CHAT = ('<|start|>system<|message|>You are a helpful AI assistant.<|eot|>'
             '<|start|>user<|message|>{}<|eot|><|start|>assistant')


# ---- paths and task ------------------------------------------------------------------------------------
def _home(store):
    return Path(getattr(store, '_store', store).home)


def _task(store, task_id):
    return getattr(store, '_store', store).get_task(task_id)


def _resources(task):
    return task.get('resources') or {}


def _expand(value):
    return os.path.expandvars(os.path.expanduser(str(value)))


def _roots(store, task):
    """Where a run may read models, prompts and data: the task home and the roots the task names."""
    roots = [_home(store)]
    for value in (_resources(task).get('read_roots') or []):
        roots.append(Path(_expand(value)))
    return [r.resolve() for r in roots]


def _readable(store, task, value, what, kind='file'):
    path = Path(_expand(value)).resolve()
    if not any(path == r or path.is_relative_to(r) for r in _roots(store, task)):
        raise ScopeDenied(f'{what} {value} is outside the task home and its read_roots')
    if kind == 'file' and not path.is_file() or kind == 'dir' and not path.is_dir():
        raise ValueError(f'{what} {value} is not an existing {kind}')
    return path


def _checkout(store, task):
    parts = task['source']['subpath'].split('/')
    return _home(store) / 'agent-workspace' / Path(*parts)


def _git(checkout, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(['git', '-C', str(checkout), *args], capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


def _build_dir(home, name):
    return home / 'builds' / name


def _bin(store, name, tool):
    if not isinstance(name, str) or not NAME.match(name):
        raise ValueError('build must name an earlier build recipe (its name)')
    path = _build_dir(_home(store), name) / 'build' / 'bin' / tool
    if not path.is_file():
        raise ValueError(f'build {name} has no {tool}: run the build recipe with that target first')
    return path


def _pack_write_path(home, path):
    """Only ordinary paths below this factory's own packs root are writable."""
    packs = Path(os.path.abspath(home / 'packs'))
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(packs) or path == packs:
        raise ScopeDenied('Pack writes must be under FACTORY_HOME/packs')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ScopeDenied(f'Writing a pack through a symlink is forbidden: {part}. Use replay for shared packs.')
        if part == packs:
            break
    return path


def _quantize_write_path(home, output):
    path = _pack_write_path(home, output)
    if Path(output).resolve() != path:
        raise ScopeDenied('Quantize output must resolve to the checked pack path')
    return path


def _replay_admission(store, task, recipe, args, verify=False, expected_receipt_sha256=None):
    def readable(value, what, kind='file'):
        return _readable(store, task, value, what, kind)

    try:
        return capped_replay.admit(_home(store), task, recipe, args, readable, verify, expected_receipt_sha256)
    except (OSError, TypeError, AttributeError, KeyError) as exc:
        raise ValueError(f'Cannot validate replay inputs or receipt: {exc}') from exc


def _validate_replay(store, task, recipe, args):
    if recipe == 'convert':
        _fields(args, {'name', 'commit', 'checkpoint_manifest', 'replay'}, {'outtype', 'split_max_size'})
    elif recipe == 'quantize':
        _fields(args, {'name', 'commit', 'recipe', 'replay'})
    else:
        raise ValueError('replay is supported only for convert and quantize')
    if not isinstance(args['name'], str) or not NAME.fullmatch(args['name']):
        raise ValueError('name: lower-case letters, digits and dashes')
    provenance, receipt_sha256, _ = _replay_admission(store, task, recipe, args)
    return dict(recipe=recipe, name=args['name'], replay_args=args, replay={'rehash': False, **args['replay']},
                replayed_from=provenance, receipt_sha256=receipt_sha256)


# ---- argument validation per recipe ---------------------------------------------------------------------
def _fields(args, required, optional=()):
    if not isinstance(args, dict):
        raise ValueError('args must be an object')
    missing, extra = set(required) - set(args), set(args) - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f'args: missing {sorted(missing)}, unknown {sorted(extra)}')


def _server_args(values):
    values = list(values or [])
    i = 0
    while i < len(values):
        flag = values[i]
        if flag not in SERVER_FLAGS:
            raise ValueError(f'server flag {flag!r} is not allowed; allowed: {sorted(SERVER_FLAGS)}')
        n = SERVER_FLAGS[flag]
        if n and i + n >= len(values):
            raise ValueError(f'{flag} needs a value')
        for v in values[i + 1:i + 1 + n]:
            if not re.match(r'^[A-Za-z0-9_.:-]{1,32}$', str(v)):
                raise ValueError(f'{flag} value {v!r} is not allowed')
        i += 1 + n
    return [str(v) for v in values]


def _env(values):
    values = values or {}
    if not isinstance(values, dict) or not all(isinstance(k, str) and ENV_KEY.match(k) for k in values):
        raise ValueError('env keys must be LLAMA_* or GGML_* names')
    out = {}
    for k, v in values.items():
        if not isinstance(v, (str, int, float)) or len(str(v)) > 4096:
            raise ValueError(f'env {k}: a short string or number')
        out[k] = str(v)
    return out


def _prompts(store, task, values):
    out = []
    for item in values or []:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or sum(k in item for k in ('text', 'path', 'jsonl')) != 1:
            raise ValueError('each prompt is {id, text}, {id, path} or {id, jsonl} (a file of {"id", "prompt"} lines), '
                             'optionally template muse_chat or raw and n_predict')
        template = item.get('template', 'raw')
        if template not in {'raw', 'muse_chat'}:
            raise ValueError('template is raw or muse_chat')
        if 'jsonl' in item:
            lines = [json.loads(l) for l in _readable(store, task, item['jsonl'], 'prompt file').read_text(encoding='utf-8').splitlines() if l.strip()]
            texts = [(f"{item['id']}/{l['id']}", l['prompt']) for l in lines[:int(item.get('limit', 64))]]
        else:
            texts = [(item['id'], item['text'] if 'text' in item else _readable(store, task, item['path'], 'prompt').read_text(encoding='utf-8'))]
        for key, text in texts:
            out.append(dict(id=key, prompt=MUSE_CHAT.format(text) if template == 'muse_chat' else text,
                            n_predict=int(item.get('n_predict', 64))))
    if len(out) > 64 or any(not 0 <= p['n_predict'] <= 1024 for p in out):
        raise ValueError('at most 64 prompts, n_predict 0..1024')
    return out


def validate(store, task_id, recipe, args):
    """The full, checked request a job runs; raises on anything a recipe does not allow."""
    task = _task(store, task_id)
    home = _home(store)
    if recipe not in RECIPES:
        raise ValueError(f'recipe is one of {RECIPES}')
    if isinstance(args, dict) and 'replay' in args:
        return _validate_replay(store, task, recipe, args)
    req = dict(recipe=recipe)
    if recipe == 'build':
        _fields(args, {'name'}, {'commit', 'targets', 'cuda'})
        checkout = _checkout(store, task)
        commit = args.get('commit') or _git(checkout, 'rev-parse', 'HEAD')
        if not SHA.match(commit):
            raise ValueError('commit is a hex commit id')
        commit = _git(checkout, 'rev-parse', '--verify', commit + '^{commit}')
        targets = args.get('targets') or ['llama-server', 'llama-quantize']
        if not set(targets) <= TARGETS:
            raise ValueError(f'targets from {sorted(TARGETS)}')
        if not NAME.match(args['name']):
            raise ValueError('name: lower-case letters, digits and dashes')
        req.update(name=args['name'], commit=commit, targets=sorted(targets), cuda=bool(args.get('cuda', True)),
                   jobs=int(_resources(task).get('build_jobs', 4)))
    elif recipe == 'manifest':
        # sha256 of every shard of a pack this run wrote (packs written before host hashing, or to re-check one)
        _fields(args, {'pack'}, set())
        first = Path(os.path.abspath(_expand(args['pack'])))
        if (home / 'packs') not in first.parents or not first.is_file() or first.suffix != '.gguf':
            raise ValueError('pack is a .gguf file under FACTORY_HOME/packs')
        _pack_write_path(home, first)
        _pack_write_path(home, capped_replay.manifest_path(first))
        req.update(pack=str(first))
    elif recipe == 'convert':
        _fields(args, {'name'}, {'commit', 'split_max_size', 'outtype'})
        if not isinstance(args['name'], str) or not NAME.fullmatch(args['name']):
            raise ValueError('name: lower-case letters, digits and dashes')
        _pack_write_path(home, home / 'packs' / args['name'])
        checkout = _checkout(store, task)
        commit = _git(checkout, 'rev-parse', '--verify', (args.get('commit') or 'HEAD') + '^{commit}')
        source = _resources(task).get('checkpoint_dir')
        if not source:
            raise ValueError('the task names no resources.checkpoint_dir to convert')
        req.update(name=args['name'], commit=commit, checkpoint=str(_readable(store, task, source, 'checkpoint', 'dir')),
                   outtype=args.get('outtype', 'bf16'), split_max_size=args.get('split_max_size', '50G'),
                   python=_expand(_resources(task).get('converter_python', sys.executable)))
        if req['outtype'] not in {'bf16', 'f16', 'auto'} or not re.match(r'^\d{1,4}[GM]$', req['split_max_size']):
            raise ValueError('outtype bf16/f16/auto; split_max_size like 50G')
    elif recipe == 'quantize':
        _fields(args, {'name', 'recipe', 'build'}, {'probe', 'threads'})
        if not isinstance(args['name'], str) or not NAME.fullmatch(args['name']):
            raise ValueError('name: lower-case letters, digits and dashes')
        out_root = _pack_write_path(home, home / 'packs' / args['name'])
        plan = json.loads(_readable(store, task, args['recipe'], 'recipe').read_text(encoding='utf-8'))
        probe = bool(args.get('probe', False))
        argv = list((plan.get('probe') or {}).get('argv') or []) if probe else list(plan.get('argv') or [])
        if plan.get('format') != 'factory.pack-recipe/1' or not argv:
            raise ValueError('recipe is a factory.pack-recipe/1 from weights.build_weight_pack_compiler.plan_recipe'
                             + (' with a probe' if probe else ''))
        call = capped_replay.parse_quantize_argv(argv)  # raises where stock would refuse
        if not call['output']:
            raise ValueError('quantize recipe must name an output file')
        output = _quantize_write_path(home, call['output'])
        if not output.is_relative_to(out_root) or output == out_root:
            raise ScopeDenied(f'the recipe writes {output}; plan it with output under {out_root}/')
        _readable(store, task, call['input'], 'source pack')
        argv[0] = str(_bin(store, args['build'], 'llama-quantize'))
        if args.get('threads') is not None:
            threads = int(args['threads'])
            if not 1 <= threads <= (os.cpu_count() or 1):
                raise ValueError('threads 1..cpu count')
            if call.get('nthreads') is None:
                argv.append(str(threads))
        need = int((plan.get('estimate') or {}).get('probe_bytes' if probe else 'output_bytes') or 0)
        req.update(name=args['name'], argv=argv, probe=probe, output=str(output), need_bytes=need,
                   recipe_path=str(Path(_expand(args['recipe'])).resolve()))
    elif recipe == 'serve':
        _fields(args, {'build', 'model'}, {'prompts', 'server_args', 'env', 'trace', 'n_probs', 'repeat', 'label'})
        model = _readable(store, task, args['model'], 'model')
        req.update(server=str(_bin(store, args['build'], 'llama-server')), build=args['build'], model=str(model),
                   prompts=_prompts(store, task, args.get('prompts')), server_args=_server_args(args.get('server_args')),
                   env=_env(args.get('env')), trace=bool(args.get('trace', False)),
                   n_probs=int(args.get('n_probs', 0)), repeat=int(args.get('repeat', 1)),
                   label=str(args.get('label', ''))[:80])
        if not 0 <= req['n_probs'] <= 20 or not 1 <= req['repeat'] <= 4:
            raise ValueError('n_probs 0..20, repeat 1..4')
    elif recipe == 'accuracy':
        _fields(args, {'name', 'arms', 'dataset_dir'}, {'stages', 'margin_pts', 'slots'})
        if not NAME.match(args['name']):
            raise ValueError('name: lower-case letters, digits and dashes')
        arms = {}
        if not isinstance(args['arms'], dict) or set(args['arms']) != {'A', 'B'}:
            raise ValueError('arms is {"A": reference, "B": candidate}, each {build, model, server_args?}')
        for key, arm in args['arms'].items():
            _fields(arm, {'build', 'model'}, {'server_args', 'env'})
            arms[key] = dict(server=str(_bin(store, arm['build'], 'llama-server')), build=arm['build'],
                             model=str(_readable(store, task, arm['model'], f'arm {key} model')),
                             server_args=_server_args(arm.get('server_args')), env=_env(arm.get('env')))
        stages = args.get('stages') or [['B', 160], ['A', 160], ['B', 430], ['A', 430]]
        if not all(isinstance(s, list) and len(s) == 2 and s[0] in arms and int(s[1]) in (50, 100, 160, 250, 430)
                   for s in stages):
            raise ValueError('stages: [[arm, upto], ...] with upto a planned checkpoint (50, 100, 160, 250, 430)')
        req.update(name=args['name'], arms=arms, stages=[[a, int(n)] for a, n in stages],
                   dataset_dir=str(_readable(store, task, args['dataset_dir'], 'dataset', 'dir')),
                   margin_pts=float(args.get('margin_pts', 5)), slots=int(args.get('slots', 32)))
    return req


# ---- capability entry points ------------------------------------------------------------------------------
def dispatch(store, task_id, operation, inputs):
    if hasattr(store, '_check'):
        store._check(task_id, write=operation in {'start', 'cancel'})
    host = getattr(store, '_store', store)
    task = host.get_task(task_id)
    if operation == 'machine':
        return {'result': machine(task, host.home)}
    from .jobs import Jobs
    jobs = Jobs(host)
    if operation == 'start':
        _fields(inputs, {'recipe', 'args', 'idem_key'}, {'node_id'})
        if 'process.exec' not in task.get('allowed_effects', []):
            raise ScopeDenied('Capped runs need the process.exec effect')
        replaying = isinstance(inputs['args'], dict) and 'replay' in inputs['args']
        if not replaying and inputs['recipe'] in MODEL_LOADS and not (task.get('constraints') or {}).get('model_runs'):
            raise ScopeDenied('This task does not allow model runs (constraints.model_runs)')
        req = validate(store, task_id, inputs['recipe'], inputs['args'])
        kind = REPLAY_KIND if replaying else KIND.get(req['recipe'], 'model_run')
        if inputs.get('node_id'):
            req['node_id'] = inputs['node_id']
            from .scheduler import charge
            charge(host, task_id, inputs['node_id'], kind, inputs['idem_key'])
        argv = [os.environ.get('FACTORY_HOST_PYTHON', sys.executable), '-m', 'jiuwenswarm.factory.capped_run',
                '_exec', task_id, '{attempt_id}']
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'PYTHONPATH', 'LD_LIBRARY_PATH',
                                                             'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'}}
        env['FACTORY_HOME'] = str(host.home)
        timeout = int(_resources(task).get('run_timeout_s', {}).get(req['recipe'], 12 * 3600)) \
            if isinstance(_resources(task).get('run_timeout_s'), dict) else 12 * 3600
        job_class = 'build' if req['recipe'] in {'build', 'manifest'} else 'gpu'
        if replaying:
            env[capped_replay.REGISTRY_ENV] = os.environ[capped_replay.REGISTRY_ENV]
            job_class = 'cpu'
        else:
            timeout += GATE_WAIT_S
        attempt = jobs.submit(task_id, kind, req, inputs['idem_key'], job_class, argv, timeout, env)
        result = dict(attempt_id=attempt['attempt_id'], state=attempt['state'],
                      run_dir=str(host.home / 'runs' / attempt['attempt_id']),
                      note='The controller waits while the run is active; read capped_runner.status '
                           'for progress and, once it ends, its capped_run observation.')
        if replaying:
            result['replayed_from'] = req['replayed_from']
        return {'result': result}
    _fields(inputs, {'attempt_id'}, {'node_id'})
    attempt = jobs.status(inputs['attempt_id'])
    if attempt['task_id'] != task_id or attempt['kind'] not in {'build', 'model_run', 'manifest', REPLAY_KIND}:
        raise ScopeDenied('Not a capped run of this task')
    if operation == 'cancel':
        return {'result': {k: jobs.cancel(inputs['attempt_id'])[k] for k in ('attempt_id', 'state')}}
    if operation == 'status':
        run = host.home / 'runs' / attempt['attempt_id']
        progress = _tail(run / 'progress.log', 40)
        result = run / 'result.json'
        out = dict(attempt_id=attempt['attempt_id'], state=attempt['state'], recipe=attempt['request']['recipe'],
                   started=attempt.get('started'), ended=attempt.get('ended'), progress=progress)
        if 'replay' in attempt['request']:
            out['replayed_from'] = attempt['request']['replayed_from']
        if result.exists():
            doc = json.loads(result.read_text(encoding='utf-8'))
            out['result'] = _clip(doc)
        return {'result': out}
    raise ValueError('Unknown capped_runner capability')


def _tail(path, lines):
    try:
        return path.read_text(encoding='utf-8', errors='replace').splitlines()[-lines:]
    except OSError:
        return []


def _clip(doc, limit=24000):
    text = json.dumps(doc)
    return doc if len(text) <= limit else dict(clipped=True, head=text[:limit],
                                               note='Full result in the capped_run observation artifacts.')


# ---- machine gate ----------------------------------------------------------------------------------------
def _meminfo():
    out = {}
    for line in open('/proc/meminfo'):
        key, value = line.split(':')
        out[key] = int(value.split()[0]) * 1024
    return out


def _gpu_apps():
    try:
        rows = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory',
                               '--format=csv,noheader'], capture_output=True, text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return [f'GPU process list unavailable ({type(exc).__name__})']
    return [r.strip() for r in rows.splitlines() if r.strip()]


def machine(task, home, own_pids=()):
    mem = _meminfo()
    apps = _gpu_apps()
    owned = {str(pid) for pid in own_pids}
    foreign = [a for a in apps if a.split(',', 1)[0].strip() not in owned]
    disk = shutil.disk_usage(home)
    need = float(_resources(task).get('need_available_gib', NEED_GIB))
    ok = mem['MemAvailable'] / 2**30 >= need and not foreign
    return dict(ok=ok, available_gib=round(mem['MemAvailable'] / 2**30, 1), total_gib=round(mem['MemTotal'] / 2**30, 1),
                need_available_gib=need, foreign_gpu_processes=foreign, disk_free_bytes=disk.free,
                cap=_resources(task).get('memory_cap', CAP),
                rule=f'A model load starts only with {need:g} GiB available and no GPU process of another user.')


# ---- job side ----------------------------------------------------------------------------------------------
class Run:
    def __init__(self, store, task_id, attempt):
        self.store, self.task_id, self.attempt = store, task_id, attempt
        self.task = store.get_task(task_id)
        self.req = attempt['request']
        self.dir = store.home / 'runs' / attempt['attempt_id']
        self.dir.mkdir(parents=True, exist_ok=True)
        self.progress = (self.dir / 'progress.log').open('a', encoding='utf-8')
        self.peak = 0
        self.low = None
        self.files = {}
        self.cap = _resources(self.task).get('memory_cap', CAP)

    def log(self, *parts):
        self.progress.write(time.strftime('%H:%M:%S ') + ' '.join(str(p) for p in parts) + '\n')
        self.progress.flush()

    def gate(self):
        deadline = time.time() + float(_resources(self.task).get('gate_wait_s', GATE_WAIT_S))
        while True:
            state = machine(self.task, self.store.home)
            if state['ok']:
                self.log('machine gate passed:', state['available_gib'], 'GiB available, no foreign GPU process')
                return state
            if time.time() > deadline:
                raise RunError('MACHINE_BUSY', f"machine gate still closed: {state}")
            self.log('waiting for the machine:', state['available_gib'], 'GiB available, need',
                     state['need_available_gib'], '; foreign GPU', state['foreign_gpu_processes'])
            time.sleep(60)

    def capped(self, argv, unit):
        return ['systemd-run', '--user', '--scope', '--quiet', '-p', f'MemoryMax={self.cap}', '-p', 'MemorySwapMax=0',
                '--unit', f'factory-{unit}-{self.attempt["attempt_id"][:8]}-{int(time.time())}', *argv]

    def watch(self, proc):
        """One sample: peak cgroup memory of the scope and lowest available memory; stop below the floor."""
        try:
            cg = Path('/proc') / str(proc.pid) / 'cgroup'
            rel = cg.read_text().strip().split('::')[-1]
            peak = Path('/sys/fs/cgroup') / rel.lstrip('/') / 'memory.peak'
            if peak.exists():
                self.peak = max(self.peak, int(peak.read_text().split()[0]))
        except (OSError, ValueError):
            pass
        avail = _meminfo()['MemAvailable']
        self.low = avail if self.low is None else min(self.low, avail)
        if avail / 2**30 < float(_resources(self.task).get('floor_gib', FLOOR_GIB)):
            stop(proc)
            raise RunError('MEMORY_LOW', f'available memory fell to {avail / 2**30:.1f} GiB; the run was stopped')

    def run(self, argv, log_name, env=None, cwd=None, unit='run', capped=True):
        log = self.dir / log_name
        self.files[log_name] = log
        command = self.capped(argv, unit) if capped else argv
        self.log('run:', ' '.join(command)[:2000])
        started = time.time()
        with log.open('ab') as out:
            proc = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, cwd=cwd,
                                    env=dict(os.environ, **(env or {})), start_new_session=True)
            try:
                while proc.poll() is None:
                    self.watch(proc)
                    time.sleep(2)
            except BaseException:
                stop(proc)
                raise
        self.log(f'exit {proc.returncode} after {time.time() - started:.0f} s')
        return proc.returncode, time.time() - started


class RunError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(90)
    except (ProcessLookupError, subprocess.TimeoutExpired, PermissionError):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def _file_rows(run, files):
    """name, bytes and sha256 of each output file, hashed by the host after the run (the pack manifest digests)."""
    rows = []
    for f in files:
        started = time.time()
        rows.append(dict(name=f.name, bytes=f.stat().st_size, sha256=_sha(f)))
        run.log(f'sha256 {f.name} {rows[-1]["sha256"]} ({rows[-1]["bytes"]} bytes, {time.time() - started:.0f} s)')
    return rows


def _shards(first):
    """Every shard of the pack whose first file is ``first`` (NAME-00001-of-000NN.gguf), or that one file."""
    m = re.match(r'^(.*)-00001-of-(\d{5})\.gguf$', first.name)
    if not m:
        return [first]
    return [first.with_name(f'{m.group(1)}-{i:05d}-of-{m.group(2)}.gguf') for i in range(1, int(m.group(2)) + 1)]


def write_manifest(run, first, rows):
    """factory.pack-manifest/1 next to the pack (names relative to its folder), from the host's own digests: the
    file the weight pack compiler takes as pack_manifest so a recipe carries every source sha256."""
    path = _pack_write_path(run.store.home, capped_replay.manifest_path(first))
    doc = dict(format='factory.pack-manifest/1', files=[dict(name=r['name'], bytes=r['bytes'], sha256=r['sha256']) for r in rows],
               bytes=sum(r['bytes'] for r in rows), written_by='factory.capped_runner (host sha256)',
               attempt_id=run.attempt['attempt_id'])
    tmp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    handle = tmp.open('x', encoding='utf-8')
    try:
        with handle:
            json.dump(doc, handle, indent=1)
        _pack_write_path(run.store.home, path)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    run.log('manifest', path)
    return str(path)


def recipe_manifest(run):
    first = _pack_write_path(run.store.home, run.req['pack'])
    _pack_write_path(run.store.home, capped_replay.manifest_path(first))
    files = [_pack_write_path(run.store.home, f) for f in _shards(first)]
    missing = [f.name for f in files if not f.is_file()]
    if missing:
        raise RunError('SOURCE', f'missing shards: {missing[:5]}')
    rows = _file_rows(run, files)
    return dict(pack=str(first), files=rows, bytes=sum(r['bytes'] for r in rows), manifest=write_manifest(run, first, rows))


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(run, checkout, commit, dest):
    """The owned checkout at commit as a plain source tree (git archive), once per commit."""
    if (dest / '.factory-commit').exists():
        return dest
    tmp = dest.with_name(dest.name + '.tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    archive = subprocess.Popen(['git', '-C', str(checkout), 'archive', commit], stdout=subprocess.PIPE)
    subprocess.run(['tar', '-x', '-C', str(tmp)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        raise RunError('SOURCE', 'git archive failed')
    (tmp / '.factory-commit').write_text(commit + '\n')
    os.replace(tmp, dest)
    run.log('source snapshot', commit, '->', dest)
    return dest


def recipe_build(run):
    r = run.req
    base = _build_dir(run.store.home, r['name'])
    checkout = _checkout(run.store, run.task)
    marker = base / 'src' / '.factory-commit'
    if marker.exists() and marker.read_text().strip() != r['commit']:
        raise RunError('BUILD_NAME_TAKEN', f"build {r['name']} is commit {marker.read_text().strip()}; use a new name")
    src = _snapshot(run, checkout, r['commit'], base / 'src')
    build = base / 'build'
    # No network at build time: the server's web UI would come from a Hugging Face bucket (its pinned asset version
    # can disappear, and 'latest' need not fit an older source). The lab talks to the HTTP API only.
    flags = ['-DCMAKE_BUILD_TYPE=Release', '-DLLAMA_CURL=OFF', '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF',
             '-DLLAMA_BUILD_UI=OFF']
    # A build directory first configured with the UI download keeps that dist tree, and ui-assets.cmake falls back
    # to it ("embedding stale assets") when provisioning is off, then fails its asset check. It is generated output.
    shutil.rmtree(build / 'ui' / 'apps' / 'chat', ignore_errors=True)
    if r['cuda']:
        flags += ['-DGGML_CUDA=ON', '-DCMAKE_CUDA_ARCHITECTURES=121-real']
    env = dict(CCACHE_BASEDIR=str(base), CCACHE_NOHASHDIR='1',  # src/ and build/ relative: hits across builds
               PATH='/usr/local/cuda/bin:' + os.environ.get('PATH', ''))
    rc, t1 = run.run(['cmake', '-S', str(src), '-B', str(build), *flags], 'configure.log', env, capped=False)
    if rc:
        raise RunError('CONFIGURE', 'cmake configure failed; see configure.log')
    rc, t2 = run.run(['nice', '-n', '10', 'cmake', '--build', str(build), '-j', str(r['jobs']), '--target', *r['targets']],
                     'build.log', env, unit='build')
    if rc:
        raise RunError('BUILD', 'build failed; see build.log')
    base_commit = run.task['source']['pre_integration_commit']
    bins = {t: dict(path=str(build / 'bin' / t), sha256=_sha(build / 'bin' / t)) for t in r['targets']}
    return dict(name=r['name'], commit=r['commit'], base_commit=base_commit, cmake_flags=flags, jobs=r['jobs'],
                configure_s=round(t1, 1), build_s=round(t2, 1), binaries=bins, bindir=str(build / 'bin'),
                changed_files=_git(checkout, 'diff', '--stat', base_commit, r['commit']).splitlines()[-40:])


def _disk_check(run, need, where):
    free = shutil.disk_usage(where).free
    margin = int(_resources(run.task).get('disk_margin_bytes', 100e9))
    run.log('disk:', free, 'free at', where, 'need', need, '+ margin', margin)
    if free < need + margin:
        raise RunError('DISK', f'{free} bytes free at {where}; the run writes {need} and keeps a {margin} margin')
    return free


def recipe_convert(run):
    r = run.req
    out_dir = _pack_write_path(run.store.home, run.store.home / 'packs' / r['name'])
    stem = (_resources(run.task).get('pack_stem') or 'model') + '-' + r['name']
    if Path(stem).name != stem:
        raise RunError('SOURCE', 'pack_stem must be a basename')
    if any(out_dir.glob('*.gguf')):
        run.log('removing a partial or earlier output in', out_dir)
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    src = _snapshot(run, _checkout(run.store, run.task), r['commit'], run.store.home / 'snapshots' / r['commit'][:12])
    ckpt = Path(r['checkpoint'])
    need = sum(p.stat().st_size for p in ckpt.glob('*.safetensors'))
    free = _disk_check(run, need, out_dir)
    run.gate()
    _pack_write_path(run.store.home, out_dir)
    rc, seconds = run.run(['nice', '-n', '10', 'ionice', '-c3', r['python'], str(src / 'convert_hf_to_gguf.py'),
                           str(ckpt), '--outfile', str(out_dir / f'{stem}.gguf'), '--outtype', r['outtype'],
                           '--split-max-size', r['split_max_size']], 'convert.log', unit='convert')
    if rc:
        raise RunError('CONVERT', f'converter exited {rc}; see convert.log')
    files = sorted(out_dir.glob('*.gguf'))
    return dict(name=r['name'], commit=r['commit'], checkpoint=str(ckpt), out_dir=str(out_dir),
                first_shard=str(files[0]) if files else None, files=(rows := _file_rows(run, files)),
                manifest=write_manifest(run, files[0], rows) if files else None,
                bytes=sum(f.stat().st_size for f in files), seconds=round(seconds, 1), free_before=free,
                timing_lines=[l for l in _tail(run.dir / 'convert.log', 4000) if re.search(r'(?i)projected|timing|per expert', l)][:20])


def recipe_quantize(run):
    r = run.req
    output = _pack_write_path(run.store.home, r['output'])
    call = capped_replay.parse_quantize_argv(r['argv'])
    if not call['output'] or _quantize_write_path(run.store.home, call['output']) != output:
        raise ScopeDenied('Quantize command output differs from the checked pack path')
    output.parent.mkdir(parents=True, exist_ok=True)
    for old in output.parent.glob(output.name.removesuffix('.gguf') + '*'):
        run.log('removing an earlier output', old)
        old.unlink()
    free = _disk_check(run, r['need_bytes'], output.parent)
    run.gate()
    _quantize_write_path(run.store.home, call['output'])
    rc, seconds = run.run(['nice', '-n', '10', 'ionice', '-c3', *r['argv']], 'quantize.log', unit='quantize')
    if rc:
        raise RunError('QUANTIZE', f'llama-quantize exited {rc}; see quantize.log')
    files = sorted(output.parent.glob(output.name.removesuffix('.gguf') + '*.gguf'))
    tail = _tail(run.dir / 'quantize.log', 30)
    return dict(name=r['name'], probe=r['probe'], recipe=r['recipe_path'], argv=r['argv'], seconds=round(seconds, 1),
                first_shard=str(files[0]) if files else None, files=(rows := _file_rows(run, files)),
                manifest=write_manifest(run, files[0], rows) if files else None,
                bytes=sum(f.stat().st_size for f in files), free_before=free,
                quantize_time_lines=[l for l in tail if 'time' in l])


# ---- serving --------------------------------------------------------------------------------------------
def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


HOST_RESERVE_MIB = 14336  # host memory kept out of the device budget on a unified-memory machine (GB10)


def placement_args(server_args, task, avail_mib=None, total_mib=None):
    """Server args with the host's memory placement rules applied.

    On the GB10 device memory is system memory and is not charged to the cgroup cap, so llama.cpp's --fit (on by
    default) would fill all of it: a load of the 529 GB NVFP4 pack without --cpu-moe planned 119 GiB on the device
    and left the host 1.8 GiB. The runner passes -fitt (the margin fit keeps free) so the server stays within the
    device budget (resources.device_budget_mib, default total memory less HOST_RESERVE_MIB), raising a smaller
    margin the agent gave, and -lm mmap when no load mode is given (the packs are larger than memory)."""
    mem = _meminfo()
    avail_mib = mem['MemAvailable'] // 2**20 if avail_mib is None else avail_mib
    total_mib = mem['MemTotal'] // 2**20 if total_mib is None else total_mib
    budget = int(_resources(task).get('device_budget_mib') or total_mib - HOST_RESERVE_MIB)
    margin = max(1024, avail_mib - budget)
    args, out, i = list(server_args), [], 0
    while i < len(args):
        if args[i] in ('-fitt', '--fit-target'):
            margin = max(margin, max(int(x) for x in str(args[i + 1]).split(',')))
            i += 2
            continue
        out.append(args[i])
        i += 1
    if not {'-lm', '--load-mode'} & set(out):
        out = ['-lm', 'mmap', *out]
    return [*out, '-fitt', str(margin)], dict(device_budget_mib=budget, fit_margin_mib=margin, available_mib=avail_mib)


def server_error(log, tail_bytes=200_000):
    """The last error a llama-server log printed (send_error / decode failures), or None."""
    try:
        with open(log, 'rb') as handle:
            handle.seek(max(0, Path(log).stat().st_size - tail_bytes))
            lines = handle.read().decode(errors='replace').splitlines()
    except OSError:
        return None
    patterns = (r'send_error: .*?error: (.+)$', r'decode\(\) failed: (.+)$', r'E srv\s+\S+: (.+)$')
    for line in reversed(lines):
        for pattern in patterns:  # most specific first
            m = re.search(pattern, line)
            if m:
                return m.group(1).strip()[:300]
    return None


class Server:
    def __init__(self, run, server, model, server_args, env, log_name):
        self.run, self.port = run, _free_port()
        self.log = run.dir / log_name
        run.files[log_name] = self.log
        bindir = str(Path(server).parent)
        server_args, self.placement = placement_args(server_args, run.task)
        run.log('placement:', json.dumps(self.placement))
        argv = run.capped([server, '-m', model, *server_args, '--host', '127.0.0.1', '--port', str(self.port),
                           '-lv', '4'], 'serve')
        run.log('serve:', ' '.join(argv)[:2000], 'env', env)
        self.started = time.time()
        self.proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=self.log.open('ab'),
                                     env=dict(os.environ, LD_LIBRARY_PATH=bindir, **env), start_new_session=True)
        while True:
            time.sleep(2)
            run.watch(self.proc)
            if self.proc.poll() is not None:
                raise RunError('SERVER_EXIT', f'llama-server exited {self.proc.returncode} while loading; see {log_name}')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/health', timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            if time.time() - self.started > 3600:
                raise RunError('SERVER_LOAD', 'not ready after an hour')
        self.ready_s = time.time() - self.started
        run.log(f'ready in {self.ready_s:.0f} s')

    def post(self, body, timeout=7200):
        """POST and wait, sampling memory every 2 s (a request can take many minutes on a streamed pack)."""
        import threading
        box = {}

        def call():
            try:
                req = urllib.request.Request(f'http://127.0.0.1:{self.port}/completion', data=json.dumps(body).encode(),
                                             headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    box['out'] = json.loads(r.read())
            except Exception as exc:  # noqa: BLE001 - reported below
                box['error'] = exc
        thread = threading.Thread(target=call, daemon=True)
        thread.start()
        while thread.is_alive():
            thread.join(2)
            self.run.watch(self.proc)
            if self.proc.poll() is not None:
                raise RunError('SERVER_EXIT', f'llama-server exited {self.proc.returncode} during a request')
        if 'error' in box:
            # The HTTP status alone does not say why; the server's own error line does (e.g. context exceeded).
            said = server_error(self.log)
            raise RunError('REQUEST', f'request failed: {box["error"]}' + (f'; the server said: {said}' if said else ''))
        return box['out']

    def close(self):
        stop(self.proc)
        time.sleep(3)


def recipe_serve(run):
    r = run.req
    env = dict(r['env'])
    if r['trace']:
        env['LLAMA_MOE_CACHE_TRACE'] = str(run.dir / 'trace.mct')
        run.files['trace.mct'] = run.dir / 'trace.mct'
    gate = run.gate()
    server = Server(run, r['server'], r['model'], r['server_args'], env, 'server.log')
    rows = []
    try:
        for rep in range(r['repeat']):
            for p in r['prompts']:
                started = time.time()
                # return_tokens: greedy identity is judged on token ids, not on decoded text (pieces can match
                # while ids differ, and a byte-identical text can come from different ids).
                body = dict(prompt=p['prompt'], n_predict=p['n_predict'], temperature=0, seed=1, cache_prompt=False,
                            return_tokens=True)
                if r['n_probs']:
                    body['n_probs'] = r['n_probs']
                out = server.post(body)
                tm = out.get('timings', {})
                row = dict(request=p['id'], rep=rep, text=out.get('content', ''),
                           output_sha256=hashlib.sha256(out.get('content', '').encode()).hexdigest(),
                           text_head=out.get('content', '')[:200], wall_ms=round((time.time() - started) * 1000, 1),
                           prompt_n=tm.get('prompt_n'), prompt_ms=tm.get('prompt_ms'),
                           prompt_per_second=tm.get('prompt_per_second'), predicted_n=tm.get('predicted_n'),
                           decode_tps=tm.get('predicted_per_second'),
                           token_ids=out.get('tokens') or None)
                if r['n_probs']:
                    row['top'] = [[(t.get('token') or t.get('tok_str')) for t in (c.get('top_logprobs') or c.get('probs') or [])][:r['n_probs']]
                                  for c in out.get('completion_probabilities', [])]
                rows.append(row)
                run.log(json.dumps({k: v for k, v in row.items() if k not in {'text', 'top', 'token_ids'}}))
    finally:
        server.close()
    (run.dir / 'rows.json').write_text(json.dumps(rows, indent=1))
    run.files['rows.json'] = run.dir / 'rows.json'
    markers = sorted({l.strip()[:200] for l in _tail(run.dir / 'server.log', 200000)
                      if re.search(r'expert_weight_cache|moe_cache|prefill_batch|n_batch|n_ubatch|buffer size', l)})[:60]
    return dict(build=r['build'], model=r['model'], server_args=r['server_args'], env=env, label=r['label'],
                ready_s=round(server.ready_s, 1), available_gib_before=gate['available_gib'], rows=len(rows),
                rows_file=str(run.dir / 'rows.json'), server_log=str(run.dir / 'server.log'),
                trace=str(run.dir / 'trace.mct') if r['trace'] else None, log_markers=markers)


def recipe_accuracy(run):
    r = run.req
    sys.path.insert(0, str(Path(__file__).with_name('ccs') / 'paired_accuracy'))
    import paired as pacc
    root = run.store.home / 'accuracy' / r['name']
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / 'state.json'
    order = pacc.mmlu_order(r['dataset_dir'])
    order_sha = pacc.sha(json.dumps([q['id'] for q in order]))
    if state_path.exists():
        st = json.loads(state_path.read_text())
        if st['order_sha256'] != order_sha or st['margin_pts'] != r['margin_pts']:
            raise RunError('STATE', 'the saved state has another order or margin; use a new name')
    else:
        st = dict(format='muse-paired-accuracy/1', benchmark='MMLU test (Hendrycks), zero-shot, next-token letter',
                  seed=pacc.SEED, looks=list(pacc.LOOKS), z=pacc.Z_SEQ, margin_pts=r['margin_pts'], slots=r['slots'],
                  order_sha256=order_sha, rows={'A': {}, 'B': {}}, looks_done=[], decision=None, active_s=0.0,
                  arms={}, runs=[])
    st['runs'].append(dict(attempt=run.attempt['attempt_id'], started=time.strftime('%Y-%m-%dT%H:%M:%S')))

    def save():
        tmp = state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(st, indent=1))
        tmp.replace(state_path)

    def evaluate():
        ids = [q['id'] for q in order]
        st['looks_done'] = pacc.sequential(st['rows']['A'], st['rows']['B'], ids, st['margin_pts'], tuple(st['looks']), st['z'])
        last = st['looks_done'][-1] if st['looks_done'] else None
        st['decision'] = last['decision'] if last and last['decision'] in ('pass', 'fail', 'report') else None
        return last

    def score(server, qs):
        prompts = [pacc.prompt(q) for q in qs]
        out = server.post(dict(prompt=prompts, n_predict=1, n_probs=20, temperature=0, seed=1, cache_prompt=False))
        out = out if isinstance(out, list) else [out]
        if all('index' in o for o in out):
            out = sorted(out, key=lambda o: o['index'])
        if len(out) != len(qs):
            raise RunError('REQUEST', f'{len(out)} answers for {len(qs)} prompts')
        rows = []
        for q, p, item in zip(qs, prompts, out):
            cp = item.get('completion_probabilities') or []
            if cp and 'top_logprobs' in cp[0]:
                top = [(t['token'], t['logprob']) for t in cp[0]['top_logprobs']]
            elif cp and 'probs' in cp[0]:
                import math
                top = [(t['tok_str'], math.log(max(t['prob'], 1e-12))) for t in cp[0]['probs']]
            else:
                raise RunError('REQUEST', 'no token probabilities in the answer')
            probs = pacc.letter_probs(top)
            mass = sum(probs.values())
            pick = max(probs, key=probs.get)
            rows.append(dict(prompt_sha256=pacc.sha(p), prompt_tokens=item.get('tokens_evaluated'),
                             probs={k: round(v, 6) for k, v in probs.items()}, letter_mass=round(mass, 4), pick=pick,
                             answer=q['answer'], correct=pick == q['answer'] and mass > 0, top_token=top[0][0] if top else None))
        return rows

    save()
    for arm, upto in r['stages']:
        if st['decision'] in ('pass', 'fail'):
            break
        todo = [q for q in order[:upto] if q['id'] not in st['rows'][arm]]
        if not todo:
            if arm == 'A':
                evaluate()
            continue
        cfg = r['arms'][arm]
        run.gate()
        t0 = time.time()
        server = Server(run, cfg['server'], cfg['model'], cfg['server_args'], cfg['env'], f'{arm}-server.log')
        st['arms'][arm] = dict(build=cfg['build'], model=cfg['model'], args=cfg['server_args'],
                               load_seconds=round(server.ready_s, 1), server_log=str(server.log))
        try:
            for k in range(0, len(todo), r['slots']):
                chunk = todo[k:k + r['slots']]
                t1 = time.time()
                for q, row in zip(chunk, score(server, chunk)):
                    st['rows'][arm][q['id']] = row
                done = st['rows'][arm].values()
                run.log(f'{arm}: {len(done)} scored ({time.time() - t1:.0f} s for {len(chunk)}; acc '
                        f'{sum(x["correct"] for x in done) / len(done):.3f}, letter mass '
                        f'{sum(x["letter_mass"] for x in done) / len(done):.3f})')
                if arm == 'A':
                    last = evaluate()
                    if last and last['decision'] in ('pass', 'fail'):
                        run.log('checkpoint', json.dumps(last))
                        save()
                        break
                save()
        finally:
            server.close()
            st['active_s'] += time.time() - t0
            save()
    evaluate()
    st['runs'][-1]['ended'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    save()
    run.files['state.json'] = state_path
    return dict(name=r['name'], state=str(state_path), decision=st['decision'], looks=st['looks_done'],
                scored={a: len(v) for a, v in st['rows'].items()},
                server_logs={a: st['arms'][a]['server_log'] for a in st['arms']}, active_s=round(st['active_s']))


def _run_replay(run):
    req = run.req
    if req['recipe'] not in {'convert', 'quantize'}:
        raise RunError('REPLAY', 'Unknown pack replay recipe')
    started = time.monotonic()
    run.log('verifying historical pack for replay of job', req['replay']['job_id'])
    try:
        source, _, result = _replay_admission(
            run.store, run.task, req['recipe'], req['replay_args'], verify=True,
            expected_receipt_sha256=req['receipt_sha256'])
    except (ValueError, ScopeDenied) as exc:
        raise RunError('REPLAY', str(exc)) from exc
    if source != req['replayed_from']:
        raise RunError('REPLAY', 'Host replay receipt changed after submission')
    run.log('replay verified', result['bytes'], 'bytes and', result['tensors'], 'tensors')
    return dict(result, replayed_from=source, seconds=round(time.monotonic() - started, 1))


def execute(home, task_id, attempt_id):
    store = Store(Path(home))
    attempt = store._decode('attempts', store._db.execute(
        'SELECT * FROM attempts WHERE task_id=? AND attempt_id=?', (task_id, attempt_id)).fetchone())
    run = Run(store, task_id, attempt)
    req = run.req
    started = time.time()
    outcome, error, result = 'ok', None, None
    replaying = 'replay' in req or attempt['kind'] == REPLAY_KIND
    try:
        result = _run_replay(run) if replaying else globals()['recipe_' + req['recipe']](run)
    except ScopeDenied as exc:
        outcome, error = 'error', dict(code='SCOPE_DENIED', message=str(exc))
    except RunError as exc:
        outcome, error = 'error', dict(code=exc.code, message=str(exc))
    except Exception as exc:  # noqa: BLE001 - every failure is recorded as evidence
        outcome, error = 'error', dict(code='UNEXPECTED', message=f'{type(exc).__name__}: {exc}')
    run.log('outcome', outcome, error or '')
    doc = dict(format='factory.capped-run/1', recipe=req['recipe'], request=req, outcome=outcome, error=error,
               result=result, seconds=round(time.time() - started, 1),
               memory_cap=run.cap if req['recipe'] in MODEL_LOADS and not replaying else None,
               peak_memory_bytes=run.peak or None,
               min_available_bytes=run.low, node_id=req.get('node_id'), attempt_id=attempt_id)
    if replaying:
        doc['replayed_from'] = req.get('replayed_from')
    (run.dir / 'result.json').write_text(json.dumps(doc, indent=1))
    artifacts = []
    for name, path in {**run.files, 'progress.log': run.dir / 'progress.log', 'result.json': run.dir / 'result.json'}.items():
        if Path(path).is_file() and Path(path).stat().st_size <= 64 << 20:
            aid = f'run-{attempt_id[:12]}-{name}'
            store.put_artifact(task_id, aid, Path(path), 'application/json' if name.endswith('.json') else
                               'application/octet-stream' if name.endswith('.mct') else 'text/plain', None)
            artifacts.append(aid)
    store.append_observation(task_id, dict(
        kind='capped_run', values=doc, source_artifacts=artifacts,
        host_run=dict(by='capped runner', module='jiuwenswarm.factory.capped_run', attempt_id=attempt_id),
        limitations=('Host pack replay verification; original production provenance is in replayed_from.'
                     if replaying else 'Host record of one capped run; the recipe built the command from checked arguments.')))
    return 0 if outcome == 'ok' else 1


def user_bus_env(environ=None):
    """systemd-run --user needs the user's runtime dir and session bus. A job submitted from an agent's tool process
    (whose env is trimmed) has neither; take the standard per-user locations when they exist."""
    environ = os.environ if environ is None else environ
    runtime = environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
    if not Path(runtime).is_dir():
        return {}
    extra = {} if environ.get('XDG_RUNTIME_DIR') else dict(XDG_RUNTIME_DIR=runtime)
    if not environ.get('DBUS_SESSION_BUS_ADDRESS') and Path(runtime, 'bus').exists():
        extra['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path={runtime}/bus'
    return extra


if __name__ == '__main__':
    if sys.argv[1] == '_exec':
        os.environ.update(user_bus_env())
        # A cancelled job gets SIGTERM; exit through the recipes' finally blocks so the llama-server they started
        # (its own session and systemd scope, outside the job's process group) is stopped too.
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        sys.exit(execute(os.environ['FACTORY_HOME'], sys.argv[2], sys.argv[3]))
    raise SystemExit('usage: python -m jiuwenswarm.factory.capped_run _exec <task_id> <attempt_id>')
