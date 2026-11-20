"""Read counters at the client request boundary without touching the model mappings."""
import datetime
import os
from pathlib import Path
import re
import time


def read_lines(path, errors):
    try:
        return path.read_text().splitlines()
    except OSError as exc:
        errors[str(path)] = str(exc)
        return []


def snapshot(cgroup):
    errors = {}
    timestamp = time.monotonic_ns()
    utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mem = {}
    io = {}
    processes = {}
    if cgroup:
        for row in read_lines(cgroup / 'memory.stat', errors):
            key, value = row.split()
            mem[key] = int(value)
        for row in read_lines(cgroup / 'io.stat', errors):
            device, *counters = row.split()
            io[device] = {k: int(v) for k, v in (c.split('=') for c in counters)}
        for pid in read_lines(cgroup / 'cgroup.procs', errors):
            proc = Path('/proc') / pid
            stat = read_lines(proc / 'stat', errors)
            if not stat:
                continue
            line = stat[0]
            fields = line[line.rindex(')') + 1:].split()
            proc_io = {k.rstrip(':'): int(v) for k, v in
                       (row.split() for row in read_lines(proc / 'io', errors))}
            processes[pid] = {'comm': line[line.index('(') + 1:line.rindex(')')],
                              'starttime_ticks': int(fields[19]), 'minflt': int(fields[7]),
                              'majflt': int(fields[9]), 'io': proc_io}
    disks = {}
    for line in read_lines(Path('/proc/diskstats'), errors):
        fields = line.split()
        if re.fullmatch(r'nvme\d+n\d+', fields[2]):
            disks[fields[2]] = {'dev': ':'.join(fields[:2]), 'reads': int(fields[3]),
                                'sectors_read': int(fields[5]), 'read_bytes': 512 * int(fields[5])}
    return {'utc': utc, 'monotonic_ns': timestamp, 'end_monotonic_ns': time.monotonic_ns(),
            'page_size': os.sysconf('SC_PAGE_SIZE'), 'memory_stat': mem, 'io_stat': io,
            'processes': processes, 'host_disks': disks, 'errors': errors}
