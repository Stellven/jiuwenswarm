"""Sample the Spark's raw host load and relevant processes with native Linux probes."""
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import threading
import time

from jiuwenswarm.factory import capped_run, contract
from scripts.factory.lab_v4_inputs import TASK

INTERVAL_SECONDS = 2.0
WAIT_SECONDS = 5.0
TOOLS = {
    'build': frozenset('cmake cpack make gmake ninja samurai nvcc cc c++ cc1 cc1plus as ld ld.lld '
                       'buildctl cargo rustc go esbuild rollup webpack tsc vite uv-build '
                       'build_job.py spark_engine.py build_image.py'.split()),
    'test': frozenset('pytest py.test unittest tox nox ctest jest vitest playwright mocha '
                      'node:test test_lab_v4_fast.py'.split()),
    'helper': frozenset('muse_v3_controller.py run_muse_v4_graph.sh scheduler_dry_run_v4.sh '
                        'capped_run.py llama-server llama-quantize llama-bench llama-cli convert_hf_to_gguf.py '
                        'lab_v4_fast.py sweep.py acc_run.py'.split()),
}
MODULES = {
    'jiuwenswarm.factory.build_job': 'build',
    'jiuwenswarm.factory.spark_engine': 'build',
    'jiuwenswarm.factory.capped_run': 'helper',
    'jiuwenswarm.factory.scheduler_agent': 'helper',
    'jiuwenswarm.factory.node_check': 'helper',
    'scripts.factory.lab_v4_fast': 'helper',
}
COMPILER = re.compile(r'(?:[\w.+]+-)*(?:gcc|g\+\+|clang(?:\+\+)?)(?:-\d+)?')
INTERPRETER = re.compile(r'python(?:\d+(?:\.\d+)?)?|node(?:js)?|(?:ba|da|z|k)?sh')


REVISED = 'r8-owner-revised-v1'
EMPTY = 'r8-owner-empty-v1'


def policy(protocol=None):
    declared = contract.load(TASK)['measurement']['protocol']['quiet']
    limits = dict(max_load_1m=declared['max_load'], no_builds=declared['no_builds'],
                  sample_interval_seconds=INTERVAL_SECONDS)
    if protocol in (REVISED, EMPTY):
        limits.update(protocol=REVISED, max_foreign_cpu_percent=50.0,
                      during='Sample raw load for context. The measured cpu-moe server raises raw load.',
                      admission='Idle measured slot, load1 below 1, machine gate passed, no builds, tests or helpers.',
                      cpu_scope='Percent of one core per process, excluding measured server PID and descendants only.')
        if protocol == EMPTY:
            limits.update(campaign=EMPTY, exempt_runner_tree=True, min_cpu_window_s=0.5,
                          cpu_scope='Percent of one core per foreign process. Exempt server and lab runner trees.')
    elif protocol is not None:
        raise ValueError(f'Unknown quiet protocol {protocol}')
    return limits


def load_decides(limits, phase):
    return limits.get('protocol') != REVISED or phase not in {'during', 'end'}


class ProcessCPU:
    def __init__(self):
        self.previous = {}
        self.when = None

    def sample(self, server_pid=None, proc_root=Path('/proc'), *, runner_pid=None):
        now = time.monotonic()
        hz = os.sysconf('SC_CLK_TCK')
        current = {}
        for directory in proc_root.iterdir():
            if not directory.name.isdecimal():
                continue
            try:
                head, tail = (directory / 'stat').read_text(errors='replace').rsplit(')', 1)
            except (FileNotFoundError, ProcessLookupError):
                continue
            fields = tail.split()
            pid = int(directory.name)
            current[pid] = (int(fields[1]), head.split('(', 1)[1], int(fields[19]), int(fields[11]) + int(fields[12]))
        if server_pid is not None and (server_pid not in current or current[server_pid][1] != 'llama-server'):
            raise ValueError('measured server missing from native CPU sample')
        def tree(root):
            members = {root} if root is not None else set()
            while children := {pid for pid, proc in current.items() if proc[0] in members} - members:
                members.update(children)
            return members

        owned = tree(server_pid)
        interval = now - self.when if self.when is not None else None
        active = []
        for pid, (ppid, name, born, ticks) in current.items():
            prev = self.previous.get(pid)
            if interval is None:
                continue
            # A newly observed PID has accrued these ticks since birth.
            start = prev[3] if prev and prev[2] == born else 0
            delta = ticks - start
            if delta > 0 or pid in owned:
                active.append(dict(pid=pid, ppid=ppid, name=name, start_ticks=born, cpu_ticks_delta=delta,
                                   percent_one_core=delta * 100 / (hz * interval), measured=pid in owned))
        self.previous, self.when = current, now
        return dict(server_pid=server_pid, process_count=len(current), interval_s=interval, ticks_per_second=hz,
                    active=active, measured_pids=sorted(owned), runner_tree=sorted(tree(runner_pid)))


def cpu_issues(cpu, limits):
    if not isinstance(cpu, dict) or not cpu.get('interval_s') or not cpu.get('measured_pids'):
        return ['missing timed process CPU evidence']
    if cpu['interval_s'] < limits.get('min_cpu_window_s', 0):
        return []
    exempt = set(cpu.get('runner_tree', [])) if limits.get('exempt_runner_tree') else set()
    return [f"foreign PID {p['pid']} ({p['name']}) above {limits['max_foreign_cpu_percent']:g}% of one core"
            for p in cpu['active'] if not p['measured'] and p['pid'] not in exempt
            and p['percent_one_core'] > limits['max_foreign_cpu_percent']]



def tool_kind(name, args):
    if name in MODULES:
        return MODULES[name]
    if COMPILER.fullmatch(name):
        return 'build'
    if name in {'vite', 'webpack', 'rollup', 'cargo', 'go', 'playwright'}:
        # These command families also provide long-lived servers and runtime tools.
        if set(args) & {'test', 'bench', 'check', 'lint'}:
            return 'test'
        return 'build' if set(args) & {'build', 'verify', 'install', 'run'} else None
    if name in {'docker', 'podman', 'buildx', 'buildah', 'npm', 'pnpm', 'yarn', 'npx', 'bun', 'uv', 'pip'}:
        if set(args) & {'build', 'bake', 'bud', 'wheel'}:
            return 'build'
        if set(args) & {'test', 'pytest', 'vitest', 'jest', 'lint', 'typecheck'}:
            return 'test'
    if name == 'codex' and 'exec' in args:
        return 'helper'
    return next((kind for kind, names in TOOLS.items() if name in names), None)


def workload(comm, argv):
    if not argv:
        return tool_kind(comm, ())
    executable = Path(argv[0]).name
    args = argv[1:]
    if INTERPRETER.fullmatch(executable):
        if args[:1] == ['--test']:
            return 'test'
        # A command string passed to -c stays private. Classify its native children instead.
        for token in args:
            if token in {'-c', '-e', '--eval'}:
                break
            if not token.startswith('-'):
                name = Path(token).name
                name = name.split('.')[0] if name.endswith(('.js', '.mjs', '.cjs')) else name
                return tool_kind(name, args)
    if comm.startswith(('npm run ', 'pnpm run ', 'yarn run ')):
        return tool_kind(comm.split()[0], comm.split()[1:] + args)
    return tool_kind(executable, args) or tool_kind(comm, args)


def processes(proc_root=Path('/proc'), own_pid=None):
    """Retain process names, PIDs, categories and states. Raw argv is used transiently for classification."""
    own_pid = os.getpid() if own_pid is None else own_pid
    table = {}
    for directory in proc_root.iterdir():
        if not directory.name.isdecimal():
            continue
        pid = int(directory.name)
        try:
            stat = (directory / 'stat').read_text(errors='replace')
            head, tail = stat.rsplit(')', 1)
            comm = head.split('(', 1)[1]
            state, parent, *_ = tail.split()
            if state in {'Z', 'X', 'x'}:
                continue
            argv = (directory / 'cmdline').read_bytes().decode('utf-8', errors='replace').rstrip('\0').split('\0')
        except (FileNotFoundError, ProcessLookupError):
            # It is normal for short-lived processes to exit between enumeration and read.
            continue
        table[pid] = (int(parent), state, workload(comm, argv if argv != [''] else []), comm)
    if own_pid not in table:
        raise ValueError('own process absent from native process snapshot')
    descendants = {own_pid}
    previous = -1
    while previous != len(descendants):
        previous = len(descendants)
        descendants.update(pid for pid, (parent, _, _, _) in table.items() if parent in descendants)
    # The Codex/shell chain can own this invocation. Its other branches are still foreign.
    ancestors = set()
    parent = table[own_pid][0]
    while parent in table and parent not in ancestors:
        ancestors.add(parent)
        parent = table[parent][0]
    relevant = []
    for pid, (parent, state, kind, comm) in sorted(table.items()):
        own = pid in descendants or pid in ancestors and kind == 'helper'
        if own or kind or state in {'R', 'D'}:
            relevant.append(dict(pid=pid, ppid=parent, name=comm, state=state, kind=kind or 'other', own_lab=own))
    return dict(process_count=len(table), processes=relevant)


def snapshot(limits, phase):
    sample = dict(phase=phase, utc=datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                  monotonic_s=time.monotonic(), load_averages=None, process_count=None, processes=None, reasons=[])
    try:
        loads = os.getloadavg()
        if len(loads) != 3 or not all(math.isfinite(value) and value >= 0 for value in loads):
            raise ValueError('malformed load average')
        sample['load_averages'] = list(loads)
        if load_decides(limits, phase) and loads[0] >= limits['max_load_1m']:
            sample['reasons'].append('one-minute load at or above limit')
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        sample['reasons'].append(f'load probe unavailable ({type(exc).__name__})')
    try:
        sample.update(processes())
        kinds = {item['kind'] for item in sample['processes'] if not item['own_lab']}
        for kind in ('build', 'test', 'helper'):
            if kind in kinds and (kind != 'build' or limits['no_builds']):
                sample['reasons'].append(f'foreign {kind} process present')
    except (OSError, ValueError, IndexError) as exc:
        sample['reasons'].append(f'process probe unavailable ({type(exc).__name__})')
    sample['ok'] = not sample['reasons']
    return sample


class Breach(capped_run.RunError):
    def __init__(self, sample):
        super().__init__('LAB_NOT_QUIET', f'{sample["phase"]}: {", ".join(sample["reasons"])}')


class Monitor:
    """One periodic watch for an arm, including startup, preparation and requests."""

    def __init__(self, limits, *, slots=1, stop_on_gate=False):
        self.limits = limits
        self.slots = slots
        self.stop_on_gate = stop_on_gate
        self.server = None
        self.cpu = ProcessCPU()
        self.phase = 'loading'
        self.samples = []
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def _capture(self, phase):
        sample = snapshot(self.limits, phase)
        if self.limits.get('protocol') == REVISED and self.server and phase in {'start_wait', 'during', 'end'}:
            try:
                if phase == 'start_wait':
                    # The next CPU delta must cover only this request, beginning after admission.
                    if sample['ok']:
                        import json
                        import urllib.request
                        with urllib.request.urlopen(f'http://127.0.0.1:{self.server.port}/slots', timeout=5) as reply:
                            slots = json.load(reply)
                        sample['idle_slot'] = len(slots) == self.slots and all(slot.get('is_processing') is False for slot in slots)
                        if not sample['idle_slot']:
                            sample['reasons'].append('measured slot is busy')
                        # Full pre-load memory gate already passed. This running server owns its allocation.
                        task = {'resources': dict(self.server.run.task['resources'], need_available_gib=self.server.run.task['resources']['floor_gib'])}
                        gate = capped_run.machine(task, self.server.run.home, own_pids=[self.server.proc.pid])
                        sample['resident_machine_gate'] = gate
                        if not gate['ok']:
                            sample['reasons'].append('resident-server machine gate closed')
                        self.cpu = ProcessCPU()
                        sample['cpu'] = self.cpu.sample(self.server.proc.pid, runner_pid=os.getpid())
                else:
                    sample['cpu'] = self.cpu.sample(self.server.proc.pid, runner_pid=os.getpid())
                    sample['reasons'].extend(cpu_issues(sample['cpu'], self.limits))
            except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
                sample['reasons'].append(f'cell admission or CPU probe unavailable ({type(exc).__name__})')
            sample['ok'] = not sample['reasons']
        self.samples.append(sample)
        return len(self.samples) - 1

    def mark(self, phase, following=None):
        with self._lock:
            if following is not None:
                self.phase = following
            return self._capture(phase)

    def _poll(self):
        while not self._done.wait(self.limits['sample_interval_seconds']):
            with self._lock:
                self._capture(self.phase)

    def wait(self, phase, following, log):
        waited = False
        while True:
            if self.stop_on_gate and self.server is not None:
                self.server.run.watch(self.server.proc)
                if self.server.proc.poll() is not None:
                    raise capped_run.RunError('SERVER_EXIT', 'measured server exited while waiting for admission')
            with self._lock:
                index = self._capture(f'{phase}_wait')
                sample = self.samples[index]
                if sample['ok']:
                    sample['phase'] = phase
                    self.phase = following
                    return index, waited
            gate = sample.get('resident_machine_gate')
            if self.stop_on_gate and gate and not gate['ok']:
                code = 'MEMORY_LOW' if gate['available_gib'] < gate['need_available_gib'] else 'MACHINE_BUSY'
                raise capped_run.RunError(code, f'resident-server machine gate closed: {gate}')
            if any('probe unavailable' in reason for reason in sample['reasons']):
                raise Breach(sample)
            log(f'{phase}: waiting for quiet at raw load {sample["load_averages"][0]:g}; '
                + ', '.join(sample['reasons']))
            waited = True
            self._done.wait(WAIT_SECONDS)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._done.set()
        self._thread.join()


def evidence_issues(samples, limits):
    if (not isinstance(samples, list) or len(samples) < 2
            or not all(isinstance(sample, dict) for sample in samples)
            or [sample.get('phase') for sample in samples] != ['start', *(['during'] * (len(samples) - 2)), 'end']):
        return ['missing start, periodic or end quiet evidence']
    issues = []
    for sample in samples:
        if sample.get('ok') is not True:
            issues.extend(sample.get('reasons') or ['quiet probe did not pass'])
            continue
        loads = sample.get('load_averages')
        procs = sample.get('processes')
        if (not isinstance(loads, list) or len(loads) != 3
                or any(type(load) not in (int, float) or not math.isfinite(load) or load < 0 for load in loads)
                or not isinstance(procs, list) or not procs or any(not isinstance(proc, dict) for proc in procs)
                or type(sample.get('process_count')) is not int or sample['process_count'] < len(procs)
                or not any(proc.get('own_lab') is True for proc in procs)
                or not sample.get('utc')):
            issues.append('incomplete load or process evidence')
            continue
        if limits.get('protocol') == REVISED:
            if sample['phase'] == 'start':
                if not sample.get('idle_slot') or not (sample.get('resident_machine_gate') or {}).get('ok'):
                    issues.append('cell lacks idle-server machine admission')
            else:
                issues.extend(cpu_issues(sample.get('cpu'), limits))
        if load_decides(limits, sample['phase']) and loads[0] >= limits['max_load_1m']:
            issues.append('one-minute load at or above limit')
        if any(proc.get('own_lab') is not True and (proc.get('kind') in {'helper', 'test'}
               or limits['no_builds'] and proc.get('kind') == 'build') for proc in procs):
            issues.append('foreign build, test or helper process present')
    times = [sample.get('monotonic_s') for sample in samples]
    if (any(type(stamp) not in (int, float) or not math.isfinite(stamp) for stamp in times)
            or any(not 0 <= after - before <= 2 * limits['sample_interval_seconds']
                   for before, after in zip(times, times[1:]))):
        issues.append('missing periodic quiet evidence')
    return list(dict.fromkeys(issues))


def report_policy(rows, limits):
    if limits is None and any(row.get('factory_task_id') == TASK or 'quiet' in row for row in rows):
        return policy()
    return limits


def excluded(row, limits):
    evidence = row.get('quiet')
    if evidence is None:
        return ['missing quiet evidence'] if limits else []
    if not isinstance(evidence, dict):
        return ['invalid quiet evidence']
    if evidence.get('status') != 'accepted':
        reasons = evidence.get('reasons')
        return reasons if isinstance(reasons, list) and reasons else ['quiet evidence was excluded']
    return evidence_issues(evidence.get('samples'), limits) if limits else []
