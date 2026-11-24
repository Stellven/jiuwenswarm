"""Linux I/O telemetry and an explicitly targeted memory watchdog (stdlib only)."""
import os
import shlex
import signal
import subprocess
import time

MIB = 1048576
VM_KEYS = ('pgmajfault', 'pgfault', 'pgpgin', 'pgpgout', 'pswpin', 'pswpout', 'workingset_refault_file')
MEM_KEYS = ('anon', 'file', 'file_mapped', 'active_file', 'inactive_file', 'workingset_refault_file', 'pgmajfault')


def read(path):
    with open(path) as f:
        return f.read()


def pairs(text):
    return {p[0].rstrip(':'): int(p[1]) for line in text.splitlines()
            if len(p := line.split()) == 2 and p[1].isdigit()}


def resolve_device(path, sysroot='/sys', stat=os.stat):
    dev = stat(os.path.expanduser(path)).st_dev
    link = os.path.join(sysroot, 'dev/block', '%s:%s' % (os.major(dev), os.minor(dev)))
    if not os.path.exists(link):
        raise OSError('no sysfs block device for %s (filesystem may be overlay/network)' % link)
    node = os.path.realpath(link)
    while os.path.exists(os.path.join(node, 'partition')):
        node = os.path.dirname(node)
    name = os.path.basename(node)
    if not os.path.isfile(os.path.join(sysroot, 'block', name, 'stat')):
        raise OSError('parent disk stat unavailable: ' + name)
    return name


def proc_stat(text):
    # comm can contain spaces and closing parentheses; fields after the last ')' are fixed.
    fields = text[text.rindex(')') + 2:].split()
    return int(fields[7]), int(fields[9]), fields[19], fields[0]  # minflt, majflt, starttime, state


class IOSampler:
    def __init__(self, path='.', device=None, pid=None, pid_from_cgroup=None,
                 cgroup=None, procroot='/proc', sysroot='/sys', clock=time.monotonic):
        self.path, self.device = path, device
        self.pid, self.pid_from_cgroup, self.cgroup = pid, pid_from_cgroup, cgroup
        self.procroot, self.sysroot, self.clock = procroot, sysroot, clock
        self.previous = {}

    def sample(self):
        metrics, unavailable = [], []
        now = self.clock()
        seen = set()

        def missing(name, scope, reason):
            unavailable.append(dict(name=name, backend='io', scope=scope, reason=str(reason)))

        def metric(name, value, unit, scope, source, counter=False, identity=''):
            metrics.append(dict(name=name, value=value, unit=unit, scope=scope, source=source))
            if not counter:
                return
            key = (scope, name, source, identity)
            seen.add(key)
            old = self.previous.get(key)
            self.previous[key] = (now, value)
            reason = 'first observation; interval unavailable'
            if old and now > old[0] and value >= old[1]:
                delta = value - old[1]
                for suffix, val, u in (('_delta', delta, unit), ('_rate', delta / (now - old[0]), unit + '/s')):
                    metrics.append(dict(name=name + suffix, value=val, unit=u, scope=scope, source=source))
                if name == 'device_io_ticks':
                    metrics.append(dict(name='device_util', value=delta / (now - old[0]) / 10,
                                        unit='percent', scope=scope, source=source))
                return
            if old:
                reason = 'counter reset' if value < old[1] else 'nonpositive interval'
            missing(name + '_delta', scope, reason)
            missing(name + '_rate', scope, reason)
            if name == 'device_io_ticks':
                missing('device_util', scope, reason)

        def load(path, name, scope):
            try:
                return read(path)
            except OSError as ex:
                missing(name, scope, ex)
                return None

        src = os.path.join(self.procroot, 'vmstat')
        text = load(src, 'vmstat', 'system')
        if text is not None:
            d = pairs(text)
            for key in VM_KEYS:
                if key in d:
                    metric(key, d[key], 'KiB' if key in ('pgpgin', 'pgpgout') else
                           'pages' if key in ('pswpin', 'pswpout') else 'count', 'system', src, True)
                else:
                    missing(key, 'system', 'field absent from ' + src)
        try:
            dev = self.device or resolve_device(self.path, self.sysroot)
            src = os.path.join(self.sysroot, 'block', os.path.basename(dev), 'stat')
            data = read(src).split()
            for name, val, unit in (('device_read', int(data[2]) * 512 / MIB, 'MiB'),
                                    ('device_read_ios', int(data[0]), 'count'),
                                    ('device_io_ticks', int(data[9]), 'ms')):
                metric(name, val, unit, 'device', src, True)
        except (OSError, ValueError, IndexError) as ex:
            missing('device', 'device', ex)

        pids = [self.pid] if self.pid is not None else []
        if self.pid_from_cgroup:
            text = load(os.path.join(self.pid_from_cgroup, 'cgroup.procs'), 'processes', 'process')
            if text is not None:
                try:
                    pids = sorted(set(int(p) for p in text.split()))
                except ValueError as ex:
                    missing('processes', 'process', ex)
        totals, counts, identities = {}, {}, []
        specs = [('pid_minflt', 'count', True), ('pid_majflt', 'count', True),
                 ('pid_read_bytes', 'MiB', True)] + [('pid_' + k, 'MiB', False) for k in ('VmRSS', 'RssFile', 'RssAnon', 'VmSwap')]
        for pid in pids:
            base = os.path.join(self.procroot, str(pid))
            values = {}
            try:
                minor, major, start, _ = proc_stat(read(os.path.join(base, 'stat')))
                identities.append((pid, start))
                values.update(pid_minflt=minor, pid_majflt=major)
            except (OSError, ValueError, IndexError) as ex:
                missing('pid_stat', 'process', ex)
            text = load(os.path.join(base, 'io'), 'pid_read_bytes', 'process')
            if text is not None and 'read_bytes' in pairs(text):
                values['pid_read_bytes'] = pairs(text)['read_bytes'] / MIB
            text = load(os.path.join(base, 'status'), 'pid_status', 'process')
            if text is not None:
                for line in text.splitlines():
                    p = line.split()
                    if len(p) >= 3 and p[0].rstrip(':') in ('VmRSS', 'RssFile', 'RssAnon', 'VmSwap') and p[1].isdigit() and p[2] == 'kB':
                        values['pid_' + p[0].rstrip(':')] = int(p[1]) / 1024
            for key, val in values.items():
                totals[key] = totals.get(key, 0) + val
                counts[key] = counts.get(key, 0) + 1
        if self.pid is not None or self.pid_from_cgroup:
            for name, unit, counter in specs:
                if pids and counts.get(name) == len(pids) and (not counter or len(identities) == len(pids)):
                    metric(name, totals[name], unit, 'process', 'proc:' + ','.join(map(str, pids)), counter, str(identities))
                else:
                    missing(name, 'process', 'no processes or incomplete process data; partial sums suppressed')
        if self.cgroup:
            base = self.cgroup
            text = load(os.path.join(base, 'memory.current'), 'cgroup_current', 'cgroup')
            if text is not None:
                if text.strip().isdigit():
                    metric('cgroup_current', int(text) / MIB, 'MiB', 'cgroup', base + '/memory.current')
                else:
                    missing('cgroup_current', 'cgroup', 'invalid memory.current')
            for filename, keys in (('memory.stat', MEM_KEYS), ('memory.events', ('oom', 'oom_kill'))):
                src = os.path.join(base, filename)
                text = load(src, filename, 'cgroup')
                if text is None:
                    continue
                d = pairs(text)
                for key in keys:
                    counter = key in ('workingset_refault_file', 'pgmajfault', 'oom', 'oom_kill')
                    if key in d:
                        metric('cgroup_' + key, d[key] if counter else d[key] / MIB,
                               'count' if counter else 'MiB', 'cgroup', src, counter)
                    else:
                        missing('cgroup_' + key, 'cgroup', 'field absent from ' + src)
            src = os.path.join(base, 'io.stat')
            text = load(src, 'cgroup_rbytes', 'cgroup')
            if text is not None:
                for line in text.splitlines():
                    p = line.split()
                    fields = dict(x.split('=', 1) for x in p[1:] if '=' in x)
                    if p and fields.get('rbytes', '').isdigit():
                        metric('cgroup_rbytes_' + p[0], int(fields['rbytes']) / MIB, 'MiB', 'cgroup', src + ':' + p[0], True)
                    elif p:
                        missing('cgroup_rbytes_' + p[0], 'cgroup', 'rbytes absent or invalid')
                if not text.strip():
                    missing('cgroup_rbytes', 'cgroup', 'no device I/O entries')
        self.previous = {k: v for k, v in self.previous.items() if k in seen}
        return metrics, unavailable


def cgroup_pids(path):
    result = set()
    def walk_error(error):
        raise error
    for base, _, _ in os.walk(path, onerror=walk_error):
        result.update(int(p) for p in read(os.path.join(base, 'cgroup.procs')).split())
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    return sorted(result)


def pid_identity(pid, procroot='/proc'):
    try:
        _, _, start, state = proc_stat(read(os.path.join(procroot, str(pid), 'stat')))
        return None if state in ('Z', 'X') else start
    except FileNotFoundError:
        return None


def kill_target(a, sleep=time.sleep):
    """Only explicit targets, checked for PID reuse before each signal."""
    if a.kill_cmd:
        try:
            r = subprocess.run(shlex.split(a.kill_cmd), capture_output=True, text=True, timeout=15)
            return dict(action='command', returncode=r.returncode, stdout=r.stdout[-2000:], stderr=r.stderr[-2000:])
        except (OSError, ValueError, subprocess.TimeoutExpired) as ex:
            return dict(action='command', error=str(ex))
    result = dict(action='cgroup' if a.kill_cgroup else 'pid', signals=[], errors=[])
    targets = {}

    def capture():
        pids = cgroup_pids(a.kill_cgroup) if a.kill_cgroup else [a.kill_pid]
        for pid in pids:
            if pid not in targets:
                ident = pid_identity(pid)
                if ident is not None:
                    targets[pid] = ident

    def send(sig):
        for pid, ident in targets.items():
            try:
                if pid_identity(pid) == ident:
                    os.kill(pid, sig)
                    result['signals'].append(dict(pid=pid, signal=sig.name))
            except ProcessLookupError:
                pass
            except OSError as ex:
                result['errors'].append(str(ex))
    try:
        capture()
        send(signal.SIGTERM)
        sleep(3)
        # Include children created in the explicitly selected cgroup during the grace period.
        capture()
        send(signal.SIGKILL)
    except (OSError, ValueError, IndexError) as ex:
        result['errors'].append(str(ex))
    return result


def watchdog(a, emit, clock=time.monotonic, sleep=time.sleep, procroot='/proc', action=None):
    previous = None
    consecutive = {}
    watched_identity = None
    initialized = False
    while True:
        try:
            if not initialized:
                watched_identity = pid_identity(a.kill_pid, procroot) if a.kill_pid else None
                initialized = True
            if a.kill_pid and (watched_identity is None or pid_identity(a.kill_pid, procroot) != watched_identity):
                emit('watchdog_end', dict(reason='watched pid ended'))
                return 0
            if a.kill_cgroup and not cgroup_pids(a.kill_cgroup):
                emit('watchdog_end', dict(reason='watched cgroup empty'))
                return 0
            now = clock()
            mem = {}
            for line in read(os.path.join(procroot, 'meminfo')).splitlines():
                p = line.split()
                if len(p) >= 2 and p[1].isdigit():
                    mem[p[0].rstrip(':')] = int(p[1]) / 1024
            vm = pairs(read(os.path.join(procroot, 'vmstat')))
            swap = vm['pswpin'] + vm['pswpout']
            rate = None
            if previous and now > previous[0] and swap >= previous[1]:
                rate = (swap - previous[1]) * os.sysconf('SC_PAGE_SIZE') / MIB / (now - previous[0])
            previous = (now, swap)
            values = dict(available_mib=mem['MemAvailable'], swap_used_mib=mem['SwapTotal'] - mem['SwapFree'], swap_rate_mibs=rate)
            limits = dict(min_available_mib=values['available_mib'] < a.min_available_mib,
                          max_swap_used_mib=values['swap_used_mib'] > a.max_swap_used_mib,
                          max_swap_rate_mibs=rate is not None and rate > a.max_swap_rate_mibs)
            for key, crossed in limits.items():
                consecutive[key] = consecutive.get(key, 0) + 1 if crossed else 0
            emit('watchdog_sample', dict(values=values, crossed=[k for k, v in limits.items() if v]))
            trips = [k for k, count in consecutive.items() if count >= 2]
            if trips:
                emit('watchdog_trip', dict(limits=trips, values=values))
                if a.kill_pid or a.kill_cgroup or a.kill_cmd:
                    emit('watchdog_action', (action or kill_target)(a))
                else:
                    emit('watchdog_action', dict(action='none', reason='no kill target configured'))
                return 3
            sleep(max(0, a.interval_ms / 1000 - (clock() - now)))
        except (OSError, KeyError, ValueError, IndexError) as ex:
            emit('watchdog_error', dict(reason=str(ex)))
            return 2
