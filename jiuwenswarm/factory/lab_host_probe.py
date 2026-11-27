"""Process and CPU probes shared by the host model-load gate and lab sampling."""

from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import time

INTERVAL_SECONDS = 2.0
WAIT_SECONDS = 5.0
SHARED = 'muse-r9-owner-006'
SHARED_POLICY = dict(protocol=SHARED, sample_interval_seconds=INTERVAL_SECONDS,
                     min_cpu_window_s=0.5, max_other_user_cpu_percent=200,
                     admission='No own builds, tests or helpers and no other user process above two cores.',
                     during='Sample load and background CPU for context without filtering rows.')

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


def processes(proc_root=Path('/proc'), own_pid=None, *, ownership=False):
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
            fields = tail.split()
            state, parent = fields[:2]
            if state in {'Z', 'X', 'x'}:
                continue
            argv = (directory / 'cmdline').read_bytes().decode('utf-8', errors='replace').rstrip('\0').split('\0')
            uid = directory.stat().st_uid if ownership else None
            background = False
            if ownership:
                # Empty cmdline identifies kernel tasks. System-managed daemon
                # services are background, while transient scopes (including
                # Docker workloads) still count as user processes.
                cgroup = (directory / 'cgroup').read_text(errors='replace')
                background = argv == [''] or uid == 0 and re.search(
                    r'^\d+:[^:]*:/system\.slice/[^/\n]+\.service(?:/|$)', cgroup, re.MULTILINE) is not None
        except (FileNotFoundError, ProcessLookupError):
            # It is normal for short-lived processes to exit between enumeration and read.
            continue
        table[pid] = (int(parent), state, workload(comm, argv if argv != [''] else []), comm,
                      uid, int(fields[19]) if ownership else None, background)
    if own_pid not in table:
        raise ValueError('own process absent from native process snapshot')
    descendants = {own_pid}
    previous = -1
    while previous != len(descendants):
        previous = len(descendants)
        descendants.update(pid for pid, proc in table.items() if proc[0] in descendants)
    # The Codex/shell chain can own this invocation. Its other branches are still foreign.
    ancestors = set()
    parent = table[own_pid][0]
    while parent in table and parent not in ancestors:
        ancestors.add(parent)
        parent = table[parent][0]
    relevant = []
    for pid, (parent, state, kind, comm, uid, born, background) in sorted(table.items()):
        own = pid in descendants or pid in ancestors and (ownership or kind == 'helper')
        if ownership or own or kind or state in {'R', 'D'}:
            row = dict(pid=pid, ppid=parent, name=comm, state=state, kind=kind or 'other', own_lab=own)
            if ownership:
                row.update(uid=uid, start_ticks=born, system_background=background)
            relevant.append(row)
    return dict(process_count=len(table), processes=relevant)


def shared_snapshot(phase, process_probe=processes):
    sample = dict(phase=phase, utc=datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                  monotonic_s=time.monotonic(), load_averages=None, process_count=None, processes=None, reasons=[])
    try:
        loads = os.getloadavg()
        if len(loads) != 3 or not all(math.isfinite(value) and value >= 0 for value in loads):
            raise ValueError('malformed load average')
        sample['load_averages'] = list(loads)
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        sample['observation_issues'] = [f'load probe unavailable ({type(exc).__name__})']
    try:
        sample.update(process_probe(ownership=True))
        uid = os.getuid()
        kinds = {proc['kind'] for proc in sample['processes']
                 if proc['uid'] == uid and not proc['own_lab'] and not proc['system_background']}
        sample['reasons'].extend(f'own {kind} process present' for kind in ('build', 'test', 'helper') if kind in kinds)
    except (OSError, ValueError, IndexError) as exc:
        sample['reasons'].append(f'process probe unavailable ({type(exc).__name__})')
    sample['ok'] = not sample['reasons']
    return sample


def shared_cpu_issues(cpu, processes_at_sample, limits, *, uid):
    interval = cpu.get('interval_s')
    if interval is None or interval < limits['min_cpu_window_s']:
        return ['waiting for a process CPU sample']
    metadata = {(proc['pid'], proc['start_ticks']): proc for proc in processes_at_sample}
    reasons = []
    for active in cpu['active']:
        if active['percent_one_core'] <= limits['max_other_user_cpu_percent']:
            continue
        proc = metadata.get((active['pid'], active['start_ticks']))
        if proc is None:
            reasons.append('active process ownership changed during sampling')
        elif proc['uid'] != uid and not proc['system_background']:
            reasons.append(f"other user PID {proc['pid']} ({proc['name']}) using more than two cores")
    return reasons


def shared_cpu_sample(sample, probe, limits, *, admission):
    cpu = probe.sample(runner_pid=os.getpid())
    sample['cpu'] = cpu
    processes_at_sample = sample['processes']
    if processes_at_sample is not None:
        if admission:
            sample['reasons'].extend(shared_cpu_issues(cpu, processes_at_sample, limits, uid=os.getuid()))
        active = {item['pid'] for item in cpu['active']}
        sample['processes'] = [proc for proc in processes_at_sample if proc['pid'] in active
                               or proc['own_lab'] or proc['kind'] != 'other' or proc['state'] in {'R', 'D'}]
    sample['ok'] = not sample['reasons']
    return sample


def shared_host_admission():
    """Sample prospectively before a model load, preserving the raw readings."""
    limits = SHARED_POLICY
    cpu = ProcessCPU()
    cpu.sample(runner_pid=os.getpid())
    time.sleep(limits['min_cpu_window_s'])
    return shared_cpu_sample(shared_snapshot('pre_launch_wait'), cpu, limits, admission=True)
