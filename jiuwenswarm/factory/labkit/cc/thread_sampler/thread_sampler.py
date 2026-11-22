#!/usr/bin/env python3
"""Unprivileged Linux task sampler. See README.md for JSONL schema and limits."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

COUNTERS = ('utime', 'stime', 'minflt', 'majflt')
GROUPS = ('main', 'cpu_workers', 'expert_fill', 'cuda_driver', 'others')


def parse_stat(line):
    # comm can contain spaces and parentheses. Fields after its final ')' start at 3.
    left, right = line.index('('), line.rindex(')')
    fields = line[right + 2:].split()
    return {'tid': int(line[:left]), 'comm': line[left + 1:right], 'state': fields[0],
            'utime': int(fields[11]), 'stime': int(fields[12]),
            'minflt': int(fields[7]), 'majflt': int(fields[9]),
            'processor': int(fields[36]), 'starttime': int(fields[19])}


def classify(comm, tid=None, pid=None):
    name = comm.lower()
    if name.startswith('xfill-'):
        return 'expert_fill'
    if name.startswith(('cuda', 'nv')):
        return 'cuda_driver'
    if tid is not None and tid == pid:
        return 'main'
    if name.startswith(('llama-', 'ggml', 'omp', 'openmp', 'gomp', 'kmp')):
        return 'main' if tid is None and name.startswith('llama-') else 'cpu_workers'
    return 'others'


def container_pid(name):
    cmd = ['docker', 'inspect', '-f', '{{.State.Pid}}', name]
    prefix = shlex.split(os.environ.get('DOCKER_CMD_PREFIX', ''))
    if prefix:
        cmd = prefix + [shlex.join(cmd)]
    pid = int(subprocess.check_output(cmd, text=True).strip())
    if pid <= 0:
        raise ValueError('container is not running')
    return pid


def sample(pid, output, hz=500, seconds=None):
    """Read every discovered task each tick; discover on count changes and at 10 Hz."""
    start, cpu_start = time.monotonic(), time.process_time()
    ticks = os.sysconf('SC_CLK_TCK')
    previous, fds = {}, {}
    count, missed = 0, 0
    encode = json.JSONEncoder(separators=(',', ':')).encode
    pid_str = str(pid)
    task = f'/proc/{pid}/task'
    task_fd = os.open(task, os.O_RDONLY | os.O_DIRECTORY)
    with open(output, 'w', buffering=262144) as out:
        out.write(json.dumps({'type': 'header', 'version': 1, 'pid': pid, 'hz': hz,
                              'clock_ticks': ticks, 'start_mono_s': start,
                              'columns': ['tid', 'state', *COUNTERS, 'processor', 'comm'],
                              'counter_encoding': 'delta; first observation is zero baseline'}) + '\n')
        deadline = start
        tids = []
        next_discovery = start
        known_count = None
        stop_at = start + seconds if seconds is not None else float("inf")
        leader_fd = os.open(f'{pid}/stat', os.O_RDONLY, dir_fd=task_fd)
        try:
            while True:
                now = time.monotonic()
                if now >= stop_at:
                    break
                try:
                    leader = os.pread(leader_fd, 4096, 0).decode()
                    leader_right = leader.rindex(')')
                    leader_fields = leader[leader_right + 2:].split()
                    # Discover immediately on a thread-count change; periodic scans also
                    # catch replacement TIDs when the count happens to stay constant.
                    if leader_fields[17] != known_count or now >= next_discovery:
                        known_count = leader_fields[17]
                        tids = os.listdir(task_fd)
                        next_discovery = now + .1
                        live = set(tids)
                        for gone in fds.keys() - live:
                            os.close(fds.pop(gone))
                            previous.pop(gone, None)
                except (FileNotFoundError, ProcessLookupError):
                    break
                rows = []
                for tid in tids:
                    try:
                        if tid == pid_str:
                            line = leader
                        else:
                            if tid not in fds:
                                fds[tid] = os.open(f'{tid}/stat', os.O_RDONLY, dir_fd=task_fd)
                            line = os.pread(fds[tid], 4096, 0).decode()
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    # Same proc fields as parse_stat; avoid building a dict in the hot loop.
                    right = leader_right if tid == pid_str else line.rindex(')')
                    fields = leader_fields if tid == pid_str else line[right + 2:].split()
                    state = fields[0]
                    if state in ('Z', 'X'):
                        continue
                    counters = (fields[11], fields[12], fields[7], fields[9])
                    identity = fields[19]
                    old = previous.get(tid)
                    if old is not None and old[0] == identity:
                        prev = old[1]
                        if counters == prev:
                            ut = st = minor = major = 0
                        else:
                            ut, st = int(counters[0]) - int(prev[0]), int(counters[1]) - int(prev[1])
                            minor, major = int(counters[2]) - int(prev[2]), int(counters[3]) - int(prev[3])
                    else:
                        ut = st = minor = major = 0
                    comm = line[line.index('(') + 1:right]
                    # Cache escaped comm strings; names usually stay constant for a task.
                    if old is not None and old[2] == comm:
                        quoted_comm = old[3]
                    else:
                        quoted_comm = encode(comm)
                    rows.append('[%s,"%s",%d,%d,%d,%d,%s,%s]' %
                                (tid, state, ut, st, minor, major, fields[36], quoted_comm))
                    previous[tid] = (identity, counters, comm, quoted_comm)
                if not rows:
                    break
                out.write('{"t":%.6f,"tasks":[%s]}\n' % (now, ','.join(rows)))
                count += 1
                deadline += 1 / hz
                delay = deadline - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    missed += 1
                    deadline = time.monotonic()
        finally:
            os.close(leader_fd)
            os.close(task_fd)
            for fd in fds.values():
                os.close(fd)
        out.flush()
        elapsed, cpu = time.monotonic() - start, time.process_time() - cpu_start
        stats = {'type': 'end', 'elapsed_s': elapsed, 'self_cpu_s': cpu,
                 'self_cpu_percent': 100 * cpu / elapsed if elapsed else 0,
                 'samples': count, 'missed_deadlines': missed}
        out.write(json.dumps(stats, separators=(',', ':')) + '\n')
    return stats


def aggregate(path, eval_ms_total=None, tokens=None, window=None):
    """Stream bounded-memory summaries; deltas crossing the window edge are prorated."""
    with open(path) as f:
        try:
            header = json.loads(next(f))
        except StopIteration as exc:
            raise ValueError('empty thread capture') from exc
        if not isinstance(header, dict) or header.get('clock_ticks', 0) <= 0 or 'pid' not in header:
            raise ValueError('invalid thread capture header')
        end = None
        overhead = {}
        for line in f:
            row = json.loads(line)
            if 't' in row:
                end = row['t']
            elif row.get('type') == 'end':
                overhead = row
    start = end - eval_ms_total / 1000 if end is not None and eval_ms_total else None
    if window is not None:
        start, end = window
    groups, threads, histogram = {}, {}, Counter()
    def empty():
        return {'samples': 0, 'states': Counter(), 'cpu_seconds': 0., 'minflt': 0., 'majflt': 0.}
    last = None
    intervals = []
    first = None
    with open(path) as f:
        next(f)
        for line in f:
            batch = json.loads(line)
            if 't' not in batch:
                continue
            t = batch['t']
            if first is None:
                first = t
            dt = t - last if last is not None else 0
            if dt > 0:
                # Only the maximum is needed, not an unbounded timing history.
                intervals[:] = [max(dt, intervals[0] if intervals else 0)]
            overlap = max(0, min(t, end) - max(last, start)) if (
                last is not None and start is not None and end is not None) else dt
            scale = overlap / dt if dt > 0 else 0
            included = (start is None or t >= start) and (end is None or t <= end)
            r = d = 0
            for tid, state, ut, st, minor, major, processor, comm in batch['tasks']:
                group = classify(comm, tid, header['pid'])
                if not included and not overlap:
                    continue
                g = groups.setdefault(group, empty())
                th = threads.setdefault(str(tid), {**empty(), 'comm': comm, 'group': group})
                for dest in (g, th):
                    if included:
                        dest['samples'] += 1
                        dest['states'][state] += 1
                    dest['cpu_seconds'] += (ut + st) / header['clock_ticks'] * scale
                    dest['minflt'] += minor * scale
                    dest['majflt'] += major * scale
                r += state == 'R'
                d += state == 'D'
            if included:
                histogram[f'{r},{d}'] += 1
            last = t
    for dest in [*groups.values(), *threads.values()]:
        dest['fractions'] = {s: dest['states'][s] / dest['samples'] if dest['samples'] else None
                             for s in ('R', 'D', 'S')}
        dest['cpu_seconds_per_token'] = dest['cpu_seconds'] / tokens if tokens else None
        dest['minflt_per_token'] = dest['minflt'] / tokens if tokens else None
        dest['majflt_per_token'] = dest['majflt'] / tokens if tokens else None
    cpu = groups.get('cpu_workers', {})
    mw = [groups[g] for g in ('main', 'cpu_workers') if g in groups]
    n = sum(g['samples'] for g in mw)
    total_faults = sum(g['majflt'] for g in groups.values())
    return {'pid': header['pid'], 'groups': groups, 'threads': threads, 'overhead': overhead,
            'phase_window': {'clock': 'mono_s', 'decode_start': start, 'decode_end': end,
                             'method': 'last_thread_sample_before_exit_minus_eval_ms_total' if start is not None else 'whole_capture',
                             'sampling_error_bound_s': intervals[0] if intervals else None,
                             'coverage_start': first, 'tokens': tokens,
                             'coverage_complete': first <= start if first is not None and start is not None else None,
                             'absolute_error_bound_s': None,
                             'error_note': 'Engine teardown/exit lag is unknown. Counter deltas crossing the window edge are prorated; first observation is a baseline.'},
            'rd_histogram': dict(sorted(histogram.items())),
            'cpu_workers_r_fraction': cpu.get('fractions', {}).get('R'),
            'main_workers_d_fraction': sum(g['states']['D'] for g in mw) / n if n else None,
            'majflt_per_token': total_faults / tokens if tokens else None}


def summarize(path, summary, stderr=None, eval_ms_total=None, tokens=None):
    if stderr:
        text = Path(stderr).read_text(errors='replace')
        matches = re.findall(r'(?<!prompt )\beval time\s*=\s*([\d.]+) ms.*?/\s*(\d+) (?:runs|tokens)', text)
        if matches:
            eval_ms_total, tokens = float(matches[-1][0]), int(matches[-1][1])
    result = aggregate(path, eval_ms_total, tokens)
    Path(summary).write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument('--pid', type=int)
    target.add_argument('--container')
    target.add_argument('--summarize', metavar='JSONL')
    p.add_argument('--hz', type=float, default=500)
    p.add_argument('--seconds', type=float)
    p.add_argument('--out', '--output', default='threads.jsonl')
    p.add_argument('--summary', default='summary.json')
    p.add_argument('--stderr')
    p.add_argument('--eval-ms-total', type=float)
    p.add_argument('--tokens', type=int)
    a = p.parse_args()
    if a.hz <= 0 or (a.seconds is not None and a.seconds <= 0) or (a.pid is not None and a.pid <= 0):
        p.error('hz, seconds and pid must be positive')
    try:
        if not a.summarize:
            pid = a.pid if a.pid else container_pid(a.container)
            # Fail visibly on inaccessible/missing PID rather than report an empty success.
            with open(f'/proc/{pid}/task/{pid}/stat') as f:
                parse_stat(f.read())
            sample(pid, a.out, a.hz, a.seconds)
        result = summarize(a.summarize or a.out, a.summary, a.stderr, a.eval_ms_total, a.tokens)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        p.exit(1, f'thread_sampler: {exc}\n')
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
