"""Sample the Spark's raw host load and relevant processes with native Linux probes."""
from datetime import datetime, timezone
import math
import os
import threading
import time

from jiuwenswarm.factory import capped_run, contract
from jiuwenswarm.factory.lab_host_probe import (
    INTERVAL_SECONDS, WAIT_SECONDS, SHARED, SHARED_POLICY, ProcessCPU,
    processes, shared_cpu_sample, shared_snapshot,
)
from scripts.factory.lab_v4_inputs import TASK

REVISED = 'r8-owner-revised-v1'
EMPTY = 'r8-owner-empty-v1'


def policy(protocol=None):
    if protocol == SHARED:
        return dict(SHARED_POLICY)
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
    protocol = limits.get('protocol')
    return protocol != SHARED and (protocol != REVISED or phase not in {'during', 'end'})


def cpu_issues(cpu, limits):
    if not isinstance(cpu, dict) or not cpu.get('interval_s') or not cpu.get('measured_pids'):
        return ['missing timed process CPU evidence']
    if cpu['interval_s'] < limits.get('min_cpu_window_s', 0):
        return []
    exempt = set(cpu.get('runner_tree', [])) if limits.get('exempt_runner_tree') else set()
    return [f"foreign PID {p['pid']} ({p['name']}) above {limits['max_foreign_cpu_percent']:g}% of one core"
            for p in cpu['active'] if not p['measured'] and p['pid'] not in exempt
            and p['percent_one_core'] > limits['max_foreign_cpu_percent']]



def snapshot(limits, phase):
    if limits.get('protocol') == SHARED:
        return shared_snapshot(phase, process_probe=processes)
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
        protocol = self.limits.get('protocol')
        shared = protocol == SHARED
        if shared:
            try:
                shared_cpu_sample(sample, self.cpu, self.limits, admission=phase.endswith('_wait'))
            except (OSError, ValueError, IndexError) as exc:
                sample['reasons'].append(f'process CPU probe unavailable ({type(exc).__name__})')
                sample['ok'] = False
        if protocol in (REVISED, SHARED) and self.server and phase in {'start_wait', 'during', 'end'}:
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
                        if not shared:
                            self.cpu = ProcessCPU()
                            sample['cpu'] = self.cpu.sample(self.server.proc.pid, runner_pid=os.getpid())
                elif not shared:
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
            load = sample['load_averages'][0] if sample['load_averages'] is not None else 'unavailable'
            log(f'{phase}: waiting for quiet at raw load {load}; ' + ', '.join(sample['reasons']))
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
    if limits.get('protocol') == SHARED:
        return list(dict.fromkeys(reason for sample in samples for reason in sample['reasons']))
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
