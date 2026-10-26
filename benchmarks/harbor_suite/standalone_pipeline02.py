"""Plain Codex cache research baseline. No AI4R admission/gate semantics.

All IPC is durable files beneath one exclusive request directory. See README.
"""
import argparse
from collections import OrderedDict
import ctypes
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import uuid

STAGES = ('search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')
PROVENANCE = 'agent-authored standalone Codex baseline; not native AI4R CC/gate records'
PYTHON = getattr(sys, '_base_executable', sys.executable)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def exclusive(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)


def experiment(data, rounds=10000):
    """Execute real bounded CPU work on misses; retain computed-value digests."""
    results = []
    for name, trace in data['traces'].items():
        for policy, capacity in [('LRU', data['capacity_entries']), ('unbounded', None)]:
            cache = OrderedDict()
            hits = misses = 0
            outputs = []
            for key in trace:
                if key in cache:
                    hits += 1
                    value = cache.pop(key)
                else:
                    misses += 1
                    value = key.encode('utf-8')
                    for _ in range(rounds):
                        value = hashlib.sha256(value).digest()
                    if capacity is not None and len(cache) >= capacity:
                        cache.popitem(last=False)
                cache[key] = value
                outputs.append(value.hex())
            results.append(dict(trace=name, policy=policy, hits=hits, misses=misses,
                                requests=len(trace), miss_ratio=misses / len(trace) if trace else 0,
                                retained_entries=len(cache), value_digest=hashlib.sha256(
                                    json.dumps(outputs).encode()).hexdigest()))
    return dict(source_id=data['source_id'], units=data['units'], results=results,
                cpu_sha256_rounds_per_miss=rounds, references=['N1', 'N2'],
                timing_speedup_claim=None)


def process_identity(pid):
    # Creation time prevents PID reuse from targeting an unrelated process.
    if os.name != 'nt':
        return Path('/proc/%s/stat' % pid).read_text().split()[21]
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.restype = ctypes.c_void_p
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), 'OpenProcess')
    try:
        times = [(ctypes.c_uint64)() for _ in range(4)]
        if not k.GetProcessTimes(ctypes.c_void_p(handle), *[ctypes.byref(x) for x in times]):
            raise OSError(ctypes.get_last_error(), 'GetProcessTimes')
        return str(times[0].value)
    finally:
        k.CloseHandle(ctypes.c_void_p(handle))


def register(req, role):
    command = [PYTHON, str(Path(__file__).resolve()), *sys.argv[1:]]
    record = dict(pid=os.getpid(), creation_identity=process_identity(os.getpid()),
                  command=command, request_id=read(req / 'request.json')['request_id'],
                  role=role, provenance='standalone controller process evidence')
    write(req / 'control' / (role + '.json'), record)
    return record


def spawn(req, role):
    args = [PYTHON, str(Path(__file__).resolve()), role, '--request', str(req)]
    out = open(req / 'control' / (role + '.stdout.log'), 'ab')
    err = open(req / 'control' / (role + '.stderr.log'), 'ab')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                         creationflags=flags, close_fds=True)
    out.close()
    err.close()
    # Keep a frozen launch record separately from the process's resume records.
    launch = dict(pid=p.pid, creation_identity=process_identity(p.pid), command=args,
                  request_id=read(req / 'request.json')['request_id'], role=role)
    write(req / 'control' / ('launch-' + role + '-' + str(p.pid) + '.json'), launch)
    return launch


def check(req):
    meta = read(req / 'request.json')
    if time.time() > meta['deadline_epoch']:
        raise RuntimeError('wall time budget exhausted')
    if (req / 'control' / 'cancel.json').exists():
        raise InterruptedError('request cancelled before benchmark dispatch or next stage')
    size = sum(p.stat().st_size for p in req.rglob('*') if p.is_file())
    if size > 256 * 1024 * 1024:
        raise RuntimeError('256 MiB output budget exhausted')


def verify_inputs(req):
    meta = read(req / 'request.json')
    for item in read(req / 'inputs' / 'public-input-manifest.json')['files']:
        for root in [req / 'inputs', Path(meta['input_root'])]:
            path = root / item['path']
            if path.stat().st_size != item['size'] or sha(path) != item['sha256']:
                raise RuntimeError('public input changed: ' + str(path))


def worker(req):
    exclusive(req / 'worker.claim', dict(pid=os.getpid()))
    register(req, 'worker')
    outputs = []
    try:
        verify_inputs(req)
        workflow = read(req / 'inputs' / 'public' / 'workflow.json')
        if [n['node_id'] for n in workflow['nodes']] != list(STAGES):
            raise RuntimeError('unsupported stage order')
        for i, node in enumerate(workflow['nodes']):
            if node['max_attempts'] != 1 or node['predecessors'] != ([] if i == 0 else [STAGES[i-1]]):
                raise RuntimeError('workflow is not serial one-attempt')
        data = read(req / 'inputs' / 'public' / 'cache-traces.json')
        result = None
        for index, stage in enumerate(STAGES):
            check(req)
            if stage == 'benchmark':
                # Check genuine prerequisites before reserving a stage attempt.
                builder = read(outputs[-1])['content']
                for name, digest in [('dependency', 'dependency_sha256'),
                                     ('required_input', 'required_input_sha256')]:
                    path = Path(builder[name])
                    if not path.is_file() or sha(path) != builder[digest]:
                        raise RuntimeError('required scientific dependency missing or changed; no dispatch')
            exclusive(req / ('attempt-' + stage + '.claim'), {'attempt': 1})
            predecessor = [] if not outputs else [dict(path=outputs[-1].name, sha256=sha(outputs[-1]))]
            content = dict(references=['N1', 'N2'], source_id=data['source_id'])
            if stage == 'search':
                content.update(sources=['cache-traces.json', 'source-notes.md'],
                               public_file_count=3, trace_count=len(data['traces']), external_sources=0)
            elif stage == 'screening':
                content.update(accepted_traces=list(data['traces']), excluded_traces=[],
                               note='Authored local experiment notes, no external published research.')
            elif stage == 'hypothesis':
                content.update(hypothesis='Two-entry LRU matches unbounded miss counts on all supplied traces.',
                               criterion='Compare per-trace miss counts; retain every unfavorable result.')
            elif stage == 'builder':
                dependency = req / 'runtime' / 'experiment.py'
                dependency.parent.mkdir(exist_ok=True)
                dependency.write_bytes(Path(__file__).read_bytes())
                content.update(dependency=str(dependency), dependency_sha256=sha(dependency),
                               required_input=str(req / 'inputs' / 'public' / 'cache-traces.json'),
                               required_input_sha256=sha(req / 'inputs' / 'public' / 'cache-traces.json'),
                               rounds_per_miss=10000, capacity_entries=data['capacity_entries'])
            elif stage == 'benchmark':
                builder = read(outputs[-1])['content']
                dependency = Path(builder['dependency'])
                if not dependency.exists() or sha(dependency) != builder['dependency_sha256']:
                    raise RuntimeError('required experiment dependency missing or changed; no dispatch')
                scientific_input = Path(builder['required_input'])
                if not scientific_input.exists() or sha(scientific_input) != builder['required_input_sha256']:
                    raise RuntimeError('required scientific input missing or changed; no dispatch')
                data = read(scientific_input)
                verify_inputs(req)
                check(req)
                write(req / 'control' / 'benchmark-dispatched.json', {'time': time.time()})
                result = runpy.run_path(str(dependency))['experiment'](data)
                content.update(result)
            elif stage == 'evaluation':
                result = read(outputs[-1])['content']
                unfavorable = []
                for name in data['traces']:
                    rows = {r['policy']: r for r in result['results'] if r['trace'] == name}
                    if rows['LRU']['value_digest'] != rows['unbounded']['value_digest']:
                        raise RuntimeError('computed output mismatch')
                    if rows['LRU']['misses'] > rows['unbounded']['misses']:
                        unfavorable.append(name)
                content.update(hypothesis_supported=not unfavorable, unfavorable_traces=unfavorable,
                               counts=result['results'], units=data['units'],
                               conclusion='Two-entry LRU uses at most two entries, but has additional misses on locality and scan; burst ties. Counts do not establish timing speedups.')
            else:
                content.update(read(outputs[-1])['content'])
                content.update(native_ai4r_metrics='unscored; contracts, admission and governed gates absent',
                               scope='Common task/fault behavior only; no original Pipeline02 full_task_success claim.')
            path = req / 'research' / ('%02d-%s.json' % (index + 1, stage))
            write(path, dict(stage=stage, attempt=1, provenance=PROVENANCE,
                             predecessors=predecessor, content=content))
            outputs.append(path)
            if stage == 'builder':
                write(req / 'control' / 'builder-complete.json',
                      dict(artifact=str(path), sha256=sha(path), worker_pid=os.getpid()))
                while not (req / 'control' / 'release-benchmark.json').exists():
                    check(req)
                    time.sleep(0.05)  # Explicit checkpoint handshake only.
                check(req)
        terminal = dict(status='completed', artifacts=[dict(path=str(p.relative_to(req)), sha256=sha(p)) for p in outputs])
        code = 0
    except Exception as exc:
        terminal = dict(status='cancelled' if isinstance(exc, InterruptedError) else 'blocked',
                        error=str(exc), artifacts=[dict(path=str(p.relative_to(req)), sha256=sha(p)) for p in outputs])
        code = 20 if isinstance(exc, InterruptedError) else 21
    terminal.update(request_id=read(req / 'request.json')['request_id'], provenance=PROVENANCE,
                    worker_pid=os.getpid(), worker_exit_code=code)
    write(req / 'terminal.json', terminal)
    return code


def observe(req):
    register(req, 'observe')
    while not (req / 'terminal.json').exists():
        time.sleep(0.1)  # Observer attaches to existing request, never submits.
    terminal = read(req / 'terminal.json')
    write(req / 'control' / ('observed-' + str(os.getpid()) + '.json'), terminal)
    print(json.dumps(terminal))
    return 0


def collect(req):
    register(req, 'collect')
    terminal = read(req / 'terminal.json')
    target = req / 'collected'
    target.mkdir(exist_ok=True)
    artifacts = terminal['artifacts'] + [dict(path='terminal.json', sha256=sha(req / 'terminal.json'))]
    for index, item in enumerate(artifacts):
        src, dst = req / item['path'], target / item['path']
        if sha(src) != item['sha256']:
            raise RuntimeError('original artifact hash mismatch')
        if dst.exists():
            if sha(dst) != item['sha256']:
                raise RuntimeError('already collected bytes changed; refuse repair')
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open('xb') as f:
                f.write(src.read_bytes())
        write(req / 'control' / 'collection-progress.json', dict(request_id=terminal['request_id'], verified=index+1))
        if index == 0:
            write(req / 'control' / 'collection-checkpoint.json', dict(request_id=terminal['request_id'], first_artifact=item))
            while not (req / 'control' / 'release-collection.json').exists():
                time.sleep(0.05)  # Explicit mid-collection handshake.
    write(req / 'control' / 'collection-complete.json', dict(request_id=terminal['request_id'], artifacts=artifacts))
    return 0


def stop(req, role):
    record = read(req / 'control' / (role + '.json'))
    pid = record['pid']
    if record['request_id'] != read(req / 'request.json')['request_id'] or process_identity(pid) != record['creation_identity']:
        raise RuntimeError('process ownership identity mismatch')
    if os.name != 'nt':
        raise RuntimeError('controlled termination exit-code capture implemented for Windows only')
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.restype = ctypes.c_void_p
    handle = k.OpenProcess(0x1000 | 0x1 | 0x100000, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), 'OpenProcess')
    try:
        if not k.TerminateProcess(ctypes.c_void_p(handle), 137):
            raise OSError(ctypes.get_last_error(), 'TerminateProcess')
        k.WaitForSingleObject(ctypes.c_void_p(handle), 10000)
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)) or code.value == 259:
            raise RuntimeError('termination exit code unavailable')
        write(req / 'control' / ('stopped-' + role + '-' + str(pid) + '.json'),
              dict(process=record, actual_exit_code=code.value, time=time.time(),
                   provenance='external standalone controller; not candidate research'))
    finally:
        k.CloseHandle(ctypes.c_void_p(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['launch', 'worker', 'observe', 'collect', 'start-observer',
                                         'start-collector', 'release-benchmark', 'release-collection',
                                         'cancel', 'status', 'stop-observer', 'stop-collector', 'compute'])
    parser.add_argument('--request', type=Path)
    parser.add_argument('--inputs', type=Path)
    args = parser.parse_args()
    req = args.request.resolve() if args.request else None
    if args.action == 'compute':
        print(json.dumps(experiment(read(args.inputs / 'public' / 'cache-traces.json')), indent=2))
        return 0
    if req is None:
        parser.error('--request required')
    if args.action == 'launch':
        req.mkdir(parents=True, exist_ok=False)  # Durable exclusive request/launch claim.
        (req / 'control').mkdir()
        (req / 'research').mkdir()
        input_root = args.inputs.resolve()
        write(req / 'request.json', dict(request_id=str(uuid.uuid4()), input_root=str(input_root),
              deadline_epoch=time.time()+900, concurrency=1, output_budget_mib=256,
              memory_enforcement='best effort only; no OS memory cap installed', cpu_only=True,
              native_ai4r_metrics='unscored', provenance=PROVENANCE))
        for name in ['assignment.json', 'public-input-manifest.json', 'public/workflow.json',
                     'public/cache-traces.json', 'public/source-notes.md']:
            dst = req / 'inputs' / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((input_root / name).read_bytes())
        print(json.dumps(spawn(req, 'worker')))
    elif args.action in ['worker', 'observe', 'collect']:
        return globals()[args.action](req)
    elif args.action.startswith('start-'):
        print(json.dumps(spawn(req, 'observe' if args.action == 'start-observer' else 'collect')))
    elif args.action.startswith('stop-'):
        stop(req, 'observe' if args.action == 'stop-observer' else 'collect')
    elif args.action == 'status':
        print(json.dumps(dict(request=read(req / 'request.json'),
              terminal=read(req / 'terminal.json') if (req / 'terminal.json').exists() else None,
              builder_complete=(req / 'control' / 'builder-complete.json').exists(),
              benchmark_dispatched=(req / 'control' / 'benchmark-dispatched.json').exists()), indent=2))
    else:
        exclusive(req / 'control' / (args.action + '.json'),
                  dict(request_id=read(req / 'request.json')['request_id'], time=time.time(),
                       provenance='external standalone controller action'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
