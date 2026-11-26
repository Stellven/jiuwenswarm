"""Wait for the owner's ten-minute empty-machine window. Samples contain no command lines."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time

from scripts.factory import lab_v4_quiet as quiet


def command(*args):
    return subprocess.check_output(args, text=True, timeout=4)


def interactive_sessions():
    user = pwd.getpwuid(os.getuid()).pw_name
    other = {line.split()[0] for line in command('who').splitlines() if line.split()[0] != user}
    for line in command('loginctl', 'list-sessions', '--no-legend', '--no-pager').splitlines():
        session, uid, *_ = line.split()
        if int(uid) == os.getuid():
            continue
        raw = command('loginctl', 'show-session', session, '-p', 'Class', '-p', 'State',
                      '-p', 'Type', '-p', 'Remote', '-p', 'Name')
        props = dict(line.split('=', 1) for line in raw.splitlines())
        if (props['Class'].startswith('user') and props['State'] in ('active', 'online')
                and (props['Type'] in ('tty', 'wayland', 'x11', 'mir', 'web') or props['Remote'] == 'yes')):
            other.add(props['Name'])
    return sorted(other)


def watch(bridge):
    cpu = quiet.ProcessCPU()
    hz = os.sysconf('SC_CLK_TCK')
    start = None
    last_log = 0
    limits = quiet.policy(quiet.EMPTY)
    with (bridge / 'r8-empty-watch.jsonl').open('x', buffering=1) as out:
        while True:
            stamp = time.monotonic()
            row = dict(utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), reasons=[])
            reasons = row['reasons']
            try:
                row['load1'] = os.getloadavg()[0]
                if row['load1'] >= limits['max_load_1m']:
                    reasons.append(f"load1 {row['load1']:.2f} >= 1.0")
                row['interactive_other'] = interactive_sessions()
                if row['interactive_other']:
                    reasons.append('other interactive login: ' + ', '.join(row['interactive_other']))
                sample = cpu.sample(runner_pid=os.getpid())
                interval = row['interval_s'] = sample['interval_s']
                if interval is None or not 0.5 <= interval <= 4:
                    reasons.append('CPU sampling window unavailable or discontinuous')
                busy = []
                for proc in sample['active']:
                    if proc['pid'] in sample['runner_tree'] or interval is None or interval < 0.5:
                        continue
                    if proc['cpu_ticks_delta'] * 100 <= limits['max_foreign_cpu_percent'] * hz * interval:
                        continue
                    pid = proc['pid']
                    try:
                        status = Path(f'/proc/{pid}/status').read_text()
                        uid = int(next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1])
                    except (FileNotFoundError, ProcessLookupError):
                        uid = None
                    busy.append(dict(pid=pid, uid=uid, name=proc['name'], percent=round(proc['percent_one_core'], 2)))
                row['busy'] = busy
                reasons += [f"{p['name']} PID {p['pid']} UID {p['uid']} at {p['percent']}%" for p in busy]
                kinds = sorted({p['kind'] for p in quiet.processes()['processes']
                                if not p['own_lab'] and p['kind'] in ('build', 'test', 'helper')})
                reasons += [f'foreign {kind} present' for kind in kinds]
            except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as exc:
                reasons.append(f'probe unavailable ({type(exc).__name__})')
            if reasons:
                start = None
            elif start is None:
                start = stamp
            elapsed = row['quiet_seconds'] = stamp - start if start is not None else 0
            out.write(json.dumps(row) + '\n')
            if not last_log or stamp - last_log >= 300 or elapsed >= 600:
                detail = ', '.join(reasons) if reasons else 'all admission checks clear'
                message = f"Empty-machine watch: {elapsed:.0f}/600 consecutive quiet seconds; {detail}."
                subprocess.run([sys.executable, bridge / 'log_step.py', 'run', message], check=True)
                last_log = stamp
            if elapsed >= 600:
                return
            time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bridge', type=Path)
    watch(parser.parse_args().bridge)
