#!/usr/bin/env python3
"""Sample visible foreign build processes without inspecting their command lines."""
import json
from pathlib import Path
import signal
import sys
import threading
import time

HEAVY = {'cc1plus', 'cc1', 'cicc', 'ptxas', 'nvcc', 'ld', 'ld.bfd', 'ld.gold',
         'cmake', 'ninja', 'make', 'cargo', 'rustc'}


def foreign_heavy(run_pid, proc=Path('/proc')):
    processes = {}
    children = {}
    for path in proc.iterdir():
        if not path.name.isdigit():
            continue
        try:
            head, tail = (path / 'stat').read_text().rsplit(')', 1)
            fields = tail.split()
            if fields[0] in ('Z', 'X'):
                continue
            pid, ppid = int(path.name), int(fields[1])
            processes[pid] = dict(pid=pid, ppid=ppid, comm=head.partition('(')[2],
                                  uid=path.stat().st_uid)
            children.setdefault(ppid, []).append(pid)
        except (OSError, ValueError, IndexError):
            continue  # Processes may exit or be unreadable during a snapshot.
    descendants = set()
    pending = [run_pid]
    while pending:
        pid = pending.pop()
        if pid not in descendants:
            descendants.add(pid)
            pending.extend(children.get(pid, []))
    return [p for pid, p in sorted(processes.items())
            if pid not in descendants and p['comm'] in HEAVY]


def main():
    output, run_pid = Path(sys.argv[1]), int(sys.argv[2])
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    record = dict(max_foreign_heavy=0, names=[], samples=[])
    while True:
        foreign = foreign_heavy(run_pid)
        record['samples'].append(dict(time=time.time(), foreign_heavy=foreign))
        record['max_foreign_heavy'] = max(record['max_foreign_heavy'], len(foreign))
        record['names'] = sorted(set(record['names']) | {p['comm'] for p in foreign})
        tmp = output.with_suffix('.tmp')
        tmp.write_text(json.dumps(record, indent=2) + '\n')
        tmp.replace(output)
        if stopped.wait(3):
            break


if __name__ == '__main__':
    main()
