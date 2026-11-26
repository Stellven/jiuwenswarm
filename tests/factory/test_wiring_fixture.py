import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import wiring_fixture as fixture
from jiuwenswarm.factory.ccs.expert_scale_wiring.helpers import fixture_scope
from jiuwenswarm.factory.node_check import CheckError


@pytest.fixture
def prepared(tmp_path):
    fixture_dir = tmp_path / 'inputs'
    fixture_dir.mkdir()
    for name in fixture.FILES:
        (fixture_dir / name).touch()
    pins = {name: hashlib.sha256(b'').hexdigest() for name in fixture.FILES}
    policy = tmp_path / fixture.POLICY_FILE
    policy.write_text(json.dumps(dict(
        task_id=fixture.TASK, node_id=fixture.NODE, loads=7, files=pins)))
    policy.chmod(0o600)
    task = dict(allowed_effects=['process.exec'], constraints={'model_runs': True},
                resources={'verifier_inputs': {'wiring_tiny_dir': str(fixture_dir)}},
                source={'subpath': 'llama.cpp-muse'})
    checkout = tmp_path / 'agent-workspace' / task['source']['subpath']
    work = tmp_path / 'node-checks'
    work.mkdir()
    patch = b'mock diff'
    (work / 'patch.diff').write_bytes(patch)
    request = dict(task_id=fixture.TASK, node_id=fixture.NODE, output='change', kind='diff',
                   entry={'stage': 'runtime acceptance'}, verifier={'cc': fixture.CC, 'capability': 'verify'},
                   head='a' * 40, checkout=str(checkout), working=False, verifier_inputs={},
                   diff_sha256=hashlib.sha256(patch).hexdigest())
    return SimpleNamespace(home=tmp_path, get_task=lambda _: task), request, work, pins


def test_only_owner_pins_and_checkout_are_allowed(prepared):
    store, request, work, pins = prepared
    payload = fixture._approved_request(store, request, work)
    assert payload['files'] == pins
    assert payload['inputs'] == dict(tiny_dir=str(store.home / 'inputs'), require_stage='runtime acceptance', jobs=4)
    for field, value in [('stock_bin', '/tmp/arbitrary'), ('mem_cap', 'none'), ('ref_pack', 'full-model.gguf')]:
        request['verifier_inputs'] = {field: value}
        with pytest.raises(CheckError, match=f'Leave {field} to the host'):
            fixture._approved_request(store, request, work)
    request['verifier_inputs'] = {}
    request['checkout'] = str(store.home / 'other')
    with pytest.raises(CheckError, match='owned demo checkout'):
        fixture._approved_request(store, request, work)


def test_missing_or_mutable_approval_closes_gate(prepared):
    store, request, work, _ = prepared
    policy = store.home / fixture.POLICY_FILE
    policy.chmod(0o666)
    with pytest.raises(CheckError, match='writable only by the operator'):
        fixture._approved_request(store, request, work)
    policy.unlink()
    with pytest.raises(CheckError, match='Cannot read operator fixture approval'):
        fixture._approved_request(store, request, work)


def test_submit_uses_one_host_slot_and_a_separate_attempt_kind(prepared, monkeypatch):
    store, request, work, _ = prepared
    run = store.home / 'runs' / 'mock-id'
    run.mkdir(parents=True)
    (run / 'result.json').write_text(json.dumps({'outcome': 'ok', 'result': {'receipt': {'state': 'succeeded'}}}))
    calls = []

    class Queue:
        def __init__(self, store):
            self.store = store

        def submit(self, *args):
            calls.append(args)
            return dict(attempt_id='mock-id', state='succeeded')

    monkeypatch.setattr(fixture, 'Jobs', Queue)
    result = fixture.submit(store, request, work)
    assert result['capped_attempt_id'] == 'mock-id'
    task, kind, payload, key, queue_class, command, _, _ = calls[0]
    assert (task, kind, key, queue_class) == (fixture.TASK, 'wire_fixture', fixture.ONCE_KEY, 'gpu')
    assert payload['recipe'] not in fixture.capped_run.RECIPES
    assert command[-2:] == [fixture.TASK, '{attempt_id}']


def test_job_gates_once_and_forces_the_scope(prepared, monkeypatch):
    store, request, work, _ = prepared
    payload = fixture._approved_request(store, request, work)
    calls = []
    attempt = dict(kind=fixture.ATTEMPT_KIND, idem_key=fixture.ONCE_KEY, attempt_id='abcdef1234')
    run = SimpleNamespace(store=store, task_id=fixture.TASK, attempt=attempt, task=store.get_task(fixture.TASK),
                          req=payload, dir=work, gate=lambda: calls.append('gate'))
    monkeypatch.setattr(fixture.capped_run, '_gpu_apps', lambda *, strict: [] if strict else ['test requires strict probe'])

    def mock_runner(command, log, *, env, unit):
        assert calls == ['gate']
        assert run.cap == '96G'
        assert run.task['resources']['need_available_gib'] == 100
        assert run.task['resources']['floor_gib'] == 6
        assert command[-2:] == ['jiuwenswarm.factory.wiring_fixture', attempt['attempt_id']]
        assert env['CUDA_VISIBLE_DEVICES'] == ''
        assert env['FACTORY_WIRING_FIXTURE_SCOPE'] == 'factory-wire-fixture-abcdef12-'
        assert unit == 'wire-fixture'
        calls.append('run')
        (work / 'verifier.json').write_text('{"state":"succeeded"}')
        return 0, 1

    run.run = mock_runner
    assert fixture.run_job(run)['approved_loads'] == 7
    with pytest.raises(CheckError, match='already been used'):
        fixture.run_job(run)
    assert calls == ['gate', 'run']


def test_fixture_runner_rejects_a_failed_machine_probe(monkeypatch):
    failed = SimpleNamespace(returncode=1, stdout='')
    monkeypatch.setattr(fixture.capped_run.subprocess, 'run', lambda *args, **kwargs: failed)
    with pytest.raises(fixture.capped_run.RunError, match='GPU process check exited unsuccessfully'):
        fixture.capped_run._gpu_apps(strict=True)


def test_inherited_scope_checks_the_actual_memory_and_swap_caps(tmp_path, monkeypatch):
    group = 'user.slice/factory-wire-fixture-abcdef12-1.scope'
    proc = tmp_path / 'cgroup'
    proc.write_text(f'0::/{group}\n')
    cgroups = tmp_path / 'groups'
    limits = cgroups / group
    limits.mkdir(parents=True)
    (limits / 'memory.max').write_text(str(96 << 30))
    (limits / 'memory.swap.max').write_text('0')
    monkeypatch.setattr(fixture_scope, 'Path', lambda path: {
        '/proc/self/cgroup': proc, '/sys/fs/cgroup': cgroups}.get(path, Path(path)))
    monkeypatch.setenv(fixture_scope.SCOPE_ENV, 'factory-wire-fixture-abcdef12-')
    assert fixture_scope.inherited_cap(['mock'], '16G')[0] == ['mock']
    (limits / 'memory.swap.max').write_text('max')
    with pytest.raises(ValueError, match='zero swap'):
        fixture_scope.inherited_cap(['mock'], '16G')
