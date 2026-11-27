"""CPU fixtures for W1's read-only host and log probes."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.factory import warmup_w1_probe as probe


def test_pack_residency_checks_every_page_without_reading_the_cold_shard(tmp_path):
    names = ['warm.gguf', 'cold.gguf']
    size = 3 * probe.PAGE_SIZE + 13
    for name in names:
        with (tmp_path / name).open('wb') as stream:
            stream.truncate(size)
    with (tmp_path / names[0]).open('r+b', buffering=0) as stream:
        stream.write(b'warm head')
        stream.seek(size - 1)
        stream.write(b'x')
    manifest = tmp_path / 'model.manifest.json'
    manifest.write_text(json.dumps(dict(bytes=size * 2, files=[dict(name=name, bytes=size) for name in names])))
    pin = hashlib.sha256(manifest.read_bytes()).hexdigest()

    sample = probe.pack_residency(manifest, pin)
    assert sample['total_bytes'] == size * 2
    assert sample['total_pages'] == 8
    assert sample['resident_bytes'] == probe.PAGE_SIZE + 13
    assert [row['resident_pages'] for row in sample['shards']] == [2, 0]
    assert probe.pack_residency(manifest, pin)['resident_pages'] == 2

    with pytest.raises(ValueError, match='SHA-256'):
        probe.pack_residency(manifest, '0' * 64)
    (tmp_path / names[-1]).touch()
    with (tmp_path / names[-1]).open('r+b') as stream:
        stream.truncate(size - 1)
    with pytest.raises(ValueError, match='pinned shard size'):
        probe.pack_residency(manifest, pin)


def test_server_memory_reports_server_child_and_named_scope(tmp_path):
    proc = tmp_path / 'proc'
    sys = tmp_path / 'sys'
    wrapper, server = 11, 13
    executable = tmp_path / 'llama-server'
    systemd_run = tmp_path / 'systemd-run'
    executable.touch()
    systemd_run.touch()
    for pid, binary in ((wrapper, systemd_run), (server, executable)):
        node = proc / str(pid)
        thread = node / 'task' / str(pid)
        thread.mkdir(parents=True)
        (node / 'exe').symlink_to(binary)
        (thread / 'children').write_text(str(server) if pid == wrapper else '')
    server_node = proc / str(server)
    unit = 'factory-serve-w1-fixture'
    group = f'/user.slice/{unit}.scope'
    scope = sys / group[1:]
    scope.mkdir(parents=True)
    (server_node / 'cgroup').write_text(f'0::{group}\n')
    (server_node / 'status').write_text('VmRSS:\t101 kB\nRssFile:\t11 kB\nVmHWM:\t103 kB\n')
    fields = ['0'] * 20
    fields[0], fields[7], fields[9], fields[19] = 'S', '3', '5', '77'
    (server_node / 'stat').write_text(f'{server} (llama-server) ' + ' '.join(fields))
    for filename, data in {'memory.current': 210944, 'memory.peak': 220160, 'memory.max': 96 * 2**30,
                           'memory.swap.current': 0, 'memory.swap.max': 0}.items():
        (scope / filename).write_text(str(data))
    serve = SimpleNamespace(argv=['systemd-run', '--unit', unit, str(executable)], proc=SimpleNamespace(pid=wrapper))

    sample = probe.server_memory(serve, proc_root=proc, cgroup_root=sys)
    assert (sample['wrapper_pid'], sample['server_pid']) == (11, 13)
    assert sample['process']['rss_bytes'] == 101 * 1024
    assert sample['process']['peak_rss_bytes'] == 103 * 1024
    assert sample['process']['major_faults'] == 5
    assert sample['scope']['current_bytes'] == 210944
    assert sample['scope']['max_bytes'] == 96 * 2**30
    assert sample['scope']['swap_max_bytes'] == 0

    (server_node / 'cgroup').write_text('0::/user.slice/foreign.scope\n')
    with pytest.raises(ValueError, match='named capped scope'):
        probe.server_memory(serve, proc_root=proc, cgroup_root=sys)


def test_warmup_timestamps_cover_minute_boundary_and_ignore_post_startup_lines(tmp_path):
    log = tmp_path / 'llama-server.log'
    start = '2.55.700.100 I cmn  common_init_: warming up the model with an empty run\n'
    slot = '3.12.200.200 I srv  load_model: initializing, n_slots = 1, n_ctx_slot = 8192\n'
    ready = '3.12.200.205 I srv  server_on_li: listening on http://127.0.0.1:42\n'
    log.write_text(start + slot + ready + '3.15.000.041 I later request\n' + start)
    report = probe.startup_warmup(log)
    assert report['status'] == 'bounded'
    assert report['elapsed_s'] == 16.5001
    assert report['log_listening_elapsed_s'] == 192.200205
    assert report['start']['line'] == 1
    assert report['end']['line'] == 2

    log.write_text(start + ready)
    assert probe.startup_warmup(log)['status'] == 'unavailable'
