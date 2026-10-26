"""Parent-owned real process/file faults for the standalone Codex baseline.

This does not implement the authenticated native AI4R fault-controller binding.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PYTHON = getattr(sys, '_base_executable', sys.executable)
WORKER = Path(__file__).with_name('standalone_pipeline02.py').resolve()
STAGES = ['search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery']


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def wait(path):
    end = time.monotonic()+30
    while not path.exists():
        if time.monotonic() > end:
            raise TimeoutError('Owned checkpoint not reached: '+str(path))
        time.sleep(.02)
    return read(path)


class Process:
    """Keep a real OS handle open across worker/controller process exits."""
    def __init__(self, record):
        self.record = record
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.OpenProcess.restype = ctypes.c_void_p
        self.handle = self.k.OpenProcess(0x1000 | 0x100000, False, record['pid'])
        if not self.handle:
            raise OSError(ctypes.get_last_error(), 'OpenProcess')
        times = [ctypes.c_uint64() for _ in range(4)]
        if not self.k.GetProcessTimes(ctypes.c_void_p(self.handle), *[ctypes.byref(t) for t in times]):
            raise OSError(ctypes.get_last_error(), 'GetProcessTimes')
        if str(times[0].value) != record['creation_identity']:
            raise RuntimeError('Owned process creation identity changed')

    def exit_code(self, finish=True):
        if finish and self.k.WaitForSingleObject(ctypes.c_void_p(self.handle), 30000) != 0:
            raise TimeoutError('Owned process did not exit')
        code = ctypes.c_ulong()
        if not self.k.GetExitCodeProcess(ctypes.c_void_p(self.handle), ctypes.byref(code)):
            raise OSError(ctypes.get_last_error(), 'GetExitCodeProcess')
        return code.value

    def close(self):
        self.k.CloseHandle(ctypes.c_void_p(self.handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--plans', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This controller records Windows process creation/exit evidence')
    inputs, output = args.inputs.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_sha = sha(WORKER)
    (output/'worker-source.py').write_bytes(WORKER.read_bytes())
    (output/'controller-source.py').write_bytes(Path(__file__).read_bytes())
    write(output/'environment.json', dict(python=sys.version, executable=PYTHON,
          controller_pid=os.getpid(), started_time_ns=time.time_ns(), argv=sys.argv,
          no_application_ports=True, no_docker_operations=True,
          resource_scope='Worker deadline/storage checks only; no OS memory quota or hostile-code sandbox'))
    plans = read(args.plans)['plans']
    write(output/'plans.json', read(args.plans))
    outcomes = []
    for plan in plans:
        variant = plan['variant']
        outer = output/variant
        outer.mkdir()
        request = outer/'request'
        commands, events, handles = [], [], []
        write(outer/'controller-plan.json', plan)
        expected_plan = hashlib.sha256(json.dumps(plan['original_driver_plan'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if expected_plan != plan['plan_sha256']:
            raise ValueError('Frozen controller plan hash differs')

        def event(kind, **data):
            events.append(dict(sequence=len(events)+1, kind=kind, time_ns=time.time_ns(), **data))
            write(outer/'controller-events.json', events)

        def call(action):
            command = [PYTHON, str(WORKER), action, '--request', str(request)]
            if action == 'launch':
                command += ['--inputs', str(inputs)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            commands.append(dict(argv=command, exit_code=result.returncode,
                                 stdout=result.stdout, stderr=result.stderr))
            write(outer/'controller-commands.json', commands)
            if result.returncode:
                raise RuntimeError('Owned controller operation failed: '+action)
            return json.loads(result.stdout) if result.stdout.strip() else None

        def owned(record):
            process = Process(record)
            handles.append(process)
            return process

        event('plan_frozen', plan_sha256=expected_plan, worker_source_sha256=source_sha)
        worker = owned(call('launch'))
        meta = read(request/'request.json')
        ident = meta['request_id']
        event('launch_started', request_id=ident, worker=worker.record)
        observer = owned(call('start-observer'))
        wait(request/'control/observe.json')
        effect = None
        if variant == 'observer-restart':
            assert worker.exit_code(False) == 259
            call('stop-observer')
            assert observer.exit_code() == 137
            effect = dict(operation='observer_process_exit', process=observer.record, actual_exit_code=137)
            event('fault_applied', request_id=ident, **effect)
            observer = owned(call('start-observer'))
            event('resume_started', request_id=ident, observer=observer.record)
        wait(request/'control/builder-complete.json')
        if variant == 'dependency-unavailable':
            source = request/'inputs/public/cache-traces.json'
            retained = outer/'fault-retained-cache-traces.json'
            before = sha(source)
            source.rename(retained)
            assert not source.exists() and sha(retained) == before
            effect = dict(operation='dependency_input_moved', source=str(source), retained=str(retained), sha256=before)
            event('fault_applied', request_id=ident, **effect)
            call('release-benchmark')
        elif variant == 'cancel-active':
            assert worker.exit_code(False) == 259
            call('cancel')
            effect = dict(operation='cooperative_cancel_requested', worker=worker.record,
                          cancellation=read(request/'control/cancel.json'))
            event('fault_applied', request_id=ident, **effect)
        else:
            call('release-benchmark')
        terminal = wait(request/'terminal.json')
        actual_worker_exit = worker.exit_code()
        assert observer.exit_code() == 0
        event('execution_terminal', request_id=ident, worker_actual_exit_code=actual_worker_exit, status=terminal['status'])
        collector = owned(call('start-collector'))
        checkpoint = wait(request/'control/collection-checkpoint.json')
        first = request/'collected'/checkpoint['first_artifact']['path']
        first_pin = dict(sha256=sha(first), mtime_ns=first.stat().st_mtime_ns)
        if variant == 'collection-restart':
            call('stop-collector')
            assert collector.exit_code() == 137
            effect = dict(operation='collector_process_exit', process=collector.record, actual_exit_code=137,
                          first_collected=first_pin)
            event('fault_applied', request_id=ident, **effect)
            collector = owned(call('start-collector'))
            event('resume_started', request_id=ident, collector=collector.record)
            event('collection_resumed', request_id=ident)
        call('release-collection')
        collection = wait(request/'control/collection-complete.json')
        assert collector.exit_code() == 0
        assert sha(first) == first_pin['sha256'] and first.stat().st_mtime_ns == first_pin['mtime_ns']
        assert read(request/'request.json') == meta and terminal['request_id'] == ident == collection['request_id']
        for item in collection['artifacts']:
            assert sha(request/item['path']) == item['sha256'] == sha(request/'collected'/item['path'])
        completed = terminal['status'] == 'completed'
        stages = sorted((request/'research').glob('*.json'))
        expected_stages = STAGES if completed else STAGES[:4]
        assert [read(path)['stage'] for path in stages] == expected_stages
        assert len(list(request.glob('attempt-*.claim'))) == len(expected_stages)
        assert len(list((request/'control').glob('launch-worker-*.json'))) == 1
        for previous, current in zip(stages, stages[1:]):
            assert read(current)['predecessors'] == [dict(path=previous.name, sha256=sha(previous))]
        if not completed:
            assert not (request/'control/benchmark-dispatched.json').exists()
            assert terminal['status'] == ('cancelled' if variant == 'cancel-active' else 'blocked')
            assert actual_worker_exit == (20 if variant == 'cancel-active' else 21)
        else:
            assert actual_worker_exit == 0
            delivered = read(stages[-1])['content']
            traces = read(inputs/'public/cache-traces.json')['traces']
            for name, trace in traces.items():
                cache, hits = [], 0
                for key in trace:
                    if key in cache:
                        hits += 1
                        cache.remove(key)
                    elif len(cache) == 2:
                        cache.pop(0)
                    cache.append(key)
                rows = {row['policy']: row for row in delivered['counts'] if row['trace'] == name}
                assert (rows['LRU']['hits'], rows['LRU']['misses']) == (hits, len(trace)-hits)
                assert rows['unbounded']['misses'] == len(set(trace))
            assert delivered['source_id'] == 'frozen-cache-traces-v1' and delivered['references'] == ['N1', 'N2']
        assert effect is not None and sha(WORKER) == source_sha
        event('collection_complete', request_id=ident, verified_files=len(collection['artifacts']))
        outcome = dict(variant=variant, request_id=ident, worker_pid=worker.record['pid'],
                       worker_actual_exit_code=actual_worker_exit, terminal=terminal['status'],
                       common_task_and_fault_checks='passed', stages=expected_stages,
                       benchmark_dispatched=(request/'control/benchmark-dispatched.json').exists(),
                       collection_verified=True, worker_launch_count=1, effect=effect,
                       native_ai4r_full_task_success=None, scope='Codex standalone controlled analogue; not native Pipeline02 acceptance')
        write(outer/'parent-assessment.json', outcome)
        outcomes.append(outcome)
        for process in handles:
            process.close()
    manifest = read(inputs/'public-input-manifest.json')['files']
    assert all(sha(inputs/item['path']) == item['sha256'] for item in manifest)
    write(output/'summary.json', dict(variants=outcomes, public_inputs_unchanged=True,
          agent_model='gpt-6.1-sol', model_identity_basis='subagent dispatch; no model calls in scientific processes',
          native_ai4r_full_task_success=None, scope='Parent-controlled standalone Codex baseline, not native AI4R acceptance'))
    write(output/'artifact-inventory.json', dict(files=[dict(path=p.relative_to(output).as_posix(),
          size=p.stat().st_size, sha256=sha(p)) for p in sorted(output.rglob('*')) if p.is_file()]))
    print(json.dumps(outcomes, indent=2))


if __name__ == '__main__':
    main()
