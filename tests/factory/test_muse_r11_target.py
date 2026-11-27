"""Independent target checks without starting a server, model, or image."""
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import capped_run, muse_r11_target as target
from jiuwenswarm.factory.store import ScopeDenied


def log_line(marker, value):
    return b'2026-11-27 INFO ' + marker.encode() + b' ' + json.dumps(value).encode() + b'\n'


def counters(**fields):
    return dict(dict.fromkeys(target.COUNTERS, 0), **fields)


def test_native_reports_interpret_observed_off_and_seeded_startup(tmp_path):
    path = tmp_path/'server.log'
    zero = dict(enabled=False, seed_ms=0, groups=[], **dict.fromkeys(target.SEED_FIELDS, 0))
    path.write_bytes(log_line(target.STARTUP_MARKER, zero))
    assert target.startup_receipt(path,'AQBC')['slots_populated'] == 0
    with pytest.raises(ValueError, match='Invalid native startup'):
        target.startup_receipt(path,'AQBCE')
    fill = dict(slots_admitted=2, slots_populated=2, charged_bytes=16, uploaded_bytes=12)
    path.write_bytes(log_line(target.STARTUP_MARKER, dict(enabled=True, seed_ms=500,
                     groups=[dict(group=0, **fill)], **fill)))
    assert target.startup_receipt(path,'AQBCE')['groups'][0]['uploaded_bytes'] == 12
    path.write_bytes(log_line(target.STARTUP_MARKER, dict(enabled=True, seed_ms=500,
                     groups=[dict(group=0, **fill)], **dict(fill, uploaded_bytes=6))))
    with pytest.raises(ValueError, match='do not reconcile'):
        target.startup_receipt(path,'AQBCE')


def test_cumulative_counter_deltas_do_not_double_count_phases(tmp_path):
    path = tmp_path/'server.log'
    with pytest.raises(ValueError, match='double count'):
        target._validate_counters(counters(demand_hits=1))
    begin = counters()
    total = counters(demand_hits=3, demand_misses=4, read_only_misses=5, prefill_misses=5,
                     decode_hits=3, decode_misses=4, hit_bytes=6, host_bytes=18)
    path.write_bytes(log_line(target.COUNTER_MARKER, begin) + log_line(target.COUNTER_MARKER,total)[:-1])
    samples = target.CacheLog(path)
    before, source = samples.read()
    assert before == begin and source['start'] == 0
    with path.open('ab') as writer:
        writer.write(b'\n')
    after, source = samples.read()
    assert source['end'] == path.stat().st_size
    assert target._delta(before, after) == total
    with pytest.raises(ValueError, match='regressed'):
        target._delta(after, before)


def test_fixed_schedule_keeps_first_and_three_samples_per_warm_and_follow(tmp_path):
    plan = list(target.request_schedule())
    assert plan[0] == ('first_after_start', 'first-request', 0, True)
    assert Counter(req for req, _, _, measured in plan if measured) == {
        'first_after_start': 1, 'p512': 3, 'p2048': 3, 'p512_followup': 3, 'p2048_followup': 3,
    }
    for i, (request, cell, repeat, measured) in enumerate(plan):
        if cell.startswith('follow-up'):
            assert plan[i-1] == (request.removesuffix('_followup'), cell.replace('follow-up','prime'), repeat, False)


def test_arm_reservations_require_prior_completed_loads_and_refuse_duplicates():
    profile = dict(attempt_id='a', request=dict(arm='profile'), state='succeeded')
    control = dict(attempt_id='b', request=dict(arm='AQBC'), state='succeeded')
    seeded = dict(attempt_id='c', request=dict(arm='AQBCE'), state='running')

    def store(*records):
        return SimpleNamespace(_db=SimpleNamespace(execute=lambda *args: records), _decode=lambda _, row: row)
    assert target.admit_order(store(), 'lab','profile') == {}
    assert target.admit_order(store(profile), 'lab','AQBC')['profile'] == profile
    assert target.admit_order(store(profile, control, seeded), 'lab','AQBCE', 'c')['AQBC'] == control
    with pytest.raises(ScopeDenied, match='admitted once'):
        target.admit_order(store(profile, control), 'lab','AQBC')
    with pytest.raises(ValueError, match='did not complete'):
        target.admit_order(store(profile, dict(control, state='failed')), 'lab','AQBCE')


def test_native_watchdog_distinguishes_cgroup_charge_from_server_rss(tmp_path, monkeypatch):
    proc, cgroups = tmp_path/'proc', tmp_path/'cgroup'
    pid = proc/'123'
    scope = cgroups/'factory-test.scope'
    pid.mkdir(parents=True)
    scope.mkdir(parents=True)
    (pid/'comm').write_text('llama-server\n')
    (pid/'cgroup').write_text('0::/factory-test.scope\n')
    good_rss = (target.CAP_BYTES - target.RSS_RESERVE - (1<<20))//1024
    (pid/'status').write_text(f'VmRSS: {good_rss} kB\nVmHWM: {good_rss} kB\n')
    for name, contents in {
        'memory.max': str(target.CAP_BYTES), 'memory.swap.max': '0', 'memory.swap.current': '0',
        'memory.current': str(target.CAP_BYTES), 'memory.peak': str(target.CAP_BYTES),
        'memory.events': 'low 0\nhigh 0\nmax 4000\noom 0\noom_kill 0\n',
        'memory.stat': 'anon 7000\nkernel 8000\n',
    }.items():
        (scope/name).write_text(contents)
    monkeypatch.setattr(capped_run, '_meminfo', lambda: {'MemAvailable':16<<30})
    watch = target.MemoryWatchdog(None, proc_root=proc,cgroup_root=cgroups)
    watch.attach(SimpleNamespace(pid=123,poll=lambda:None), ['systemd-run','--unit','factory-test'])
    watch.sample()
    assert watch.receipt['peak_memory_bytes'] == target.CAP_BYTES
    assert watch.receipt['peak_process_rss_bytes'] == good_rss * 1024
    (pid/'status').write_text(f'VmRSS: {good_rss+1024} kB\nVmHWM: {good_rss+1024} kB\n')
    with pytest.raises(capped_run.RunError, match='256 MiB'):
        watch.sample()
    (pid/'status').write_text(f'VmRSS: {good_rss} kB\nVmHWM: {good_rss} kB\n')
    (scope/'memory.events').write_text('oom 1\n')
    with pytest.raises(capped_run.RunError, match='pressure'):
        watch.sample()
    (scope/'memory.swap.max').write_text('1024')
    with pytest.raises(capped_run.RunError, match='not in its verified'):
        watch.sample()


def test_target_uses_exact_profile_bytes_and_does_not_inherit_profile_overlay(tmp_path, monkeypatch):
    raw = b'{"known":true}'
    sha = target._bytes_sha(raw)
    path, first = target._stage_profile(tmp_path, raw, sha)
    assert target._profile_identity(path, sha) == first
    monkeypatch.setenv('LD_LIBRARY_PATH', '/some/profiling/overlay')
    monkeypatch.setenv('LLAMA_MOE_CACHE_TRACE', 'trace.mct')
    binary = tmp_path/'llama-server'
    off = target._environment(binary, {}, path)
    on = target._environment(binary, {'LLAMA_EXPERT_CACHE_NATIVE_PROFILE':'1',
                                     target.PROFILE_PATH_ENV:'/opt/factory/r11/seeding-profile.json'}, path)
    assert on[target.PROFILE_PATH_ENV] == str(path)
    assert not {'LLAMA_MOE_CACHE_TRACE', target.PROFILE_PATH_ENV} & set(off)
    assert off['LD_LIBRARY_PATH'] == on['LD_LIBRARY_PATH'] == str(tmp_path)
    path.chmod(0o600)
    with pytest.raises(ValueError, match='profile changed'):
        target._profile_identity(path, sha)
