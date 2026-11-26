"""Quiet Spark lab probes use minimal, privacy-preserving native evidence."""
import json

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
