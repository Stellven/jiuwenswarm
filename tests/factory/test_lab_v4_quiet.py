"""Quiet Spark lab probes use minimal, privacy-preserving native evidence."""
import json

from jiuwenswarm.factory import lab_host_probe
from scripts.factory import lab_v4_quiet as quiet


def test_process_snapshot_records_only_categories_and_marks_own_lab(tmp_path):
    def entry(pid, parent, name, argv, state='S'):
        proc = tmp_path / str(pid)
        proc.mkdir()
        (proc / 'stat').write_text(f'{pid} ({name}) {state} {parent} 0 0 0')
        (proc / 'cmdline').write_text('\0'.join(argv) + '\0')

    entry(10, 1, 'codex', ['codex', 'exec', 'private root instruction'])
    entry(11, 10, 'python', ['python', 'lab_v4_fast.py', 'private config'])
    entry(12, 11, 'llama-server', ['/tmp/llama-server', 'private prompt'])
    entry(13, 10, 'docker', ['docker', 'buildx', 'build', 'private checkout'])
    entry(14, 10, 'python', ['python', '-m', 'pytest', 'private path'])
    entry(15, 10, 'npm run build', ['npm run build', 'private name'])
    entry(16, 10, 'node', ['node', '/tool/bin/vite.js', 'build'])
    entry(17, 10, 'python', ['python', '-m', 'jiuwenswarm.factory.capped_run', 'private resource'])
    entry(18, 10, 'python', ['python', '-c', 'pytest is an example, not a launched process'])
    entry(19, 1, 'idle monitor', ['idle monitor'])
    entry(20, 1, 'unrelated ))', ['unrelated', 'private argv'], state='R')
    entry(21, 1, 'zombie', ['zombie'], state='Z')
    (tmp_path / '22').mkdir()  # Exited during enumeration.
    snapshot = quiet.processes(tmp_path, 11)
    assert snapshot['process_count'] == 11
    assert [(item['pid'], item['kind'], item['own_lab']) for item in snapshot['processes']] == [
        (10, 'helper', True), (11, 'helper', True), (12, 'helper', True),
        (13, 'build', False), (14, 'test', False), (15, 'build', False), (16, 'build', False),
        (17, 'helper', False), (20, 'other', False),
    ]
    assert 'private' not in json.dumps(snapshot)


def test_unreadable_probes_fail_closed_without_recording_exception_details(monkeypatch):
    def inaccessible():
        raise PermissionError('private process detail')

    monkeypatch.setattr(quiet.os, 'getloadavg', lambda: (float('nan'), 0.1, 0.2))
    monkeypatch.setattr(quiet, 'processes', inaccessible)
    sample = quiet.snapshot(quiet.policy(), 'readiness')
    assert sample['ok'] is False
    assert sample['reasons'] == ['load probe unavailable (ValueError)', 'process probe unavailable (PermissionError)']
    assert sample['load_averages'] is None and sample['processes'] is None
    assert 'private' not in json.dumps(sample)


def test_gap_in_periodic_evidence_excludes_a_long_cell(monkeypatch):
    monkeypatch.setattr(quiet.os, 'getloadavg', lambda: (0.01, 0.1, 0.2))
    monkeypatch.setattr(quiet, 'processes', lambda: dict(process_count=1, processes=[dict(own_lab=True)]))
    limits = quiet.policy()
    start = quiet.snapshot(limits, 'start')
    end = quiet.snapshot(limits, 'end')
    end['monotonic_s'] = start['monotonic_s'] + 10
    assert quiet.evidence_issues([start, end], limits) == ['missing periodic quiet evidence']


def test_revised_cpu_gate_keeps_raw_load_and_excludes_only_measured_tree(tmp_path, monkeypatch):
    def process(pid, parent, name, ticks):
        path = tmp_path / str(pid)
        path.mkdir(exist_ok=True)
        fields = ['0'] * 20
        fields[0], fields[1], fields[11], fields[19] = 'S', str(parent), str(ticks), '135'
        (path / 'stat').write_text(f'{pid} ({name}) ' + ' '.join(fields))
    monkeypatch.setattr(quiet.os, 'sysconf', lambda _: 100)
    monkeypatch.setattr(quiet.time, 'monotonic', iter([1.0, 3.0, 5.0]).__next__)
    limits = quiet.policy(quiet.REVISED)
    monitor = quiet.ProcessCPU()
    for pid, parent, name in [(10, 1, 'llama-server'), (11, 10, 'child'), (12, 1, 'external')]:
        process(pid, parent, name, 0)
    monitor.sample(10, tmp_path)
    process(10, 1, 'llama-server', 400)
    process(11, 10, 'child', 180)
    process(12, 1, 'external', 100)
    cpu = monitor.sample(10, tmp_path)
    assert cpu['measured_pids'] == [10, 11]
    assert not quiet.cpu_issues(cpu, limits)  # 50% exactly is allowed.
    process(12, 1, 'external', 201)
    assert quiet.cpu_issues(monitor.sample(10, tmp_path), limits) == ['foreign PID 12 (external) above 50% of one core']
    assert quiet.load_decides(limits, 'start')
    assert not quiet.load_decides(limits, 'during')
    assert not quiet.load_decides(limits, 'end')
    assert quiet.load_decides(quiet.policy(), 'during')


def test_post_run_amendment_ignores_only_short_windows_and_runner_tree():
    from scripts.factory.rejudge_lab_r8 import correct_sample
    original = quiet.policy(quiet.REVISED)
    amended = dict(original, min_cpu_window_s=0.5, exempt_runner_tree=True)
    for interval, expected in [(0.499, []), (0.5, ['foreign PID 42 (apt) above 50% of one core'])]:
        sample = dict(phase='end', ok=False, processes=[dict(pid=2, ppid=1), dict(pid=3, ppid=2)],
                      cpu=dict(interval_s=interval, measured_pids=[4], active=[
                          dict(pid=3, name='child', measured=False, percent_one_core=95),
                          dict(pid=42, name='apt', measured=False, percent_one_core=60)]))
        sample['reasons'] = quiet.cpu_issues(sample['cpu'], original) + ['foreign helper process present']
        correct_sample(sample, 2, original, amended)
        assert sample['reasons'] == ['foreign helper process present', *expected]
        assert len(sample['launch_reasons']) == 3


def test_empty_campaign_records_native_runner_and_descendant_exemptions(tmp_path, monkeypatch):
    limits = quiet.policy(quiet.EMPTY)
    assert limits['min_cpu_window_s'] == 0.5 and limits['exempt_runner_tree']
    assert limits['max_foreign_cpu_percent'] == 50
    monkeypatch.setattr(quiet.time, 'monotonic', iter([0., 1.]).__next__)
    monkeypatch.setattr(quiet.os, 'sysconf', lambda _: 100)
    monitor = quiet.ProcessCPU()
    for tick in (0, 55):
        for pid, ppid, name in ((10, 1, 'runner'), (11, 10, 'child'), (12, 11, 'llama-server'), (13, 1, 'foreign')):
            proc = tmp_path / str(pid)
            proc.mkdir(exist_ok=True)
            fields = ['0'] * 20
            fields[0], fields[1], fields[11], fields[19] = 'S', str(ppid), str(tick), '100'
            (proc / 'stat').write_text(f'{pid} ({name}) ' + ' '.join(fields))
        sample = monitor.sample(12, tmp_path, runner_pid=10)
    assert sample['runner_tree'] == [10, 11, 12]
    assert quiet.cpu_issues(sample, limits) == ['foreign PID 13 (foreign) above 50% of one core']


def test_shared_admission_ignores_load_average_and_blocks_own_work(monkeypatch):
    uid = quiet.os.getuid()
    processes = [
        dict(kind='helper', own_lab=True, uid=uid, system_background=False),
        dict(kind='other', own_lab=False, uid=0, system_background=True),
        dict(kind='test', own_lab=False, uid=uid + 1, system_background=False),
    ]
    monkeypatch.setattr(quiet.os, 'getloadavg', lambda: (55.0, 40.0, 30.0))
    monkeypatch.setattr(quiet, 'processes', lambda *, ownership: dict(process_count=len(processes), processes=processes))
    limits = quiet.policy(quiet.SHARED)
    sample = quiet.snapshot(limits, 'pre_launch_wait')
    assert sample['ok'] and sample['load_averages'][0] == 55.0
    processes.append(dict(kind='build', own_lab=False, uid=uid, system_background=False))
    assert quiet.snapshot(limits, 'pre_launch_wait')['reasons'] == ['own build process present']


def test_shared_admission_only_counts_another_users_process_above_two_cores():
    limits = quiet.policy(quiet.SHARED)
    metadata = [
        dict(pid=10, uid=1000, start_ticks=1, name='runner', system_background=False),
        dict(pid=11, uid=0, start_ticks=1, name='dockerd', system_background=True),
        dict(pid=12, uid=1001, start_ticks=1, name='worker', system_background=False),
    ]
    active = [dict(pid=proc['pid'], start_ticks=1, percent_one_core=200.0 if proc['pid'] == 12 else 300.0)
              for proc in metadata]
    cpu = dict(interval_s=1.0, active=active)
    assert lab_host_probe.shared_cpu_issues(cpu, metadata, limits, uid=1000) == []
    active[-1]['percent_one_core'] = 200.01
    assert lab_host_probe.shared_cpu_issues(cpu, metadata, limits, uid=1000) == [
        'other user PID 12 (worker) using more than two cores']


def test_shared_background_cpu_is_recorded_during_cell_without_filtering(monkeypatch):
    limits = quiet.policy(quiet.SHARED)
    process = dict(pid=3, uid=1001, start_ticks=1, name='background', system_background=False,
                   own_lab=False, kind='other', state='S')
    cpu = dict(interval_s=1.0, active=[dict(pid=3, start_ticks=1, percent_one_core=325)])
    monitor = quiet.Monitor(limits)
    monkeypatch.setattr(monitor.cpu, 'sample', lambda **_: cpu)
    monkeypatch.setattr(quiet, 'snapshot', lambda _, phase: dict(phase=phase, reasons=[], processes=[process]))
    idx = monitor.mark('during')
    sample = monitor.samples[idx]
    assert sample['cpu'] == cpu and sample['processes'] == [process]
    assert sample['ok'] is True and sample['reasons'] == []
    idx = monitor.mark('start_wait')
    assert monitor.samples[idx]['ok'] is False


def test_generic_load_gate_rechecks_machine_after_shared_admission(tmp_path, monkeypatch):
    from jiuwenswarm.factory.capped_run import RunError, RunScope, CAP
    import pytest

    scope = RunScope(tmp_path, tmp_path, {'resources': {'gate_wait_s': 0}}, 'sample')
    checked = []
    machine_states = iter([True, False])
    monkeypatch.setattr(quiet.capped_run, 'machine', lambda *_: dict(
        ok=next(machine_states), available_gib=105.0, need_available_gib=100, foreign_gpu_processes=['pid']))
    monkeypatch.setattr(lab_host_probe, 'shared_host_admission', lambda: checked.append('checked') or dict(ok=True))
    with pytest.raises(RunError) as refusal:
        scope.gate()
    assert refusal.value.code == 'MACHINE_BUSY'
    assert checked == ['checked']
    assert f'MemoryMax={CAP}' in scope.capped(['llama-server'], 'serve')
    assert 'MemorySwapMax=0' in scope.capped(['llama-server'], 'serve')

    monkeypatch.setattr(quiet.capped_run, 'machine', lambda *_: dict(
        ok=True, available_gib=105.0, need_available_gib=100, foreign_gpu_processes=[]))
    monkeypatch.setattr(lab_host_probe, 'shared_host_admission', lambda: dict(ok=False, reasons=['own test process present']))
    with pytest.raises(RunError, match='own test process present') as refusal:
        scope.gate()
    assert refusal.value.code == 'LAB_NOT_QUIET'

    sample = dict(ok=True, reasons=[], load_averages=[25.0, 20.0, 15.0])
    monkeypatch.setattr(lab_host_probe, 'shared_host_admission', lambda: sample)
    assert scope.gate()['shared_admission'] == sample
