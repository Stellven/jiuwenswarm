import json
from pathlib import Path

import pytest

from jiuwenswarm.factory.mission_supervisor import Supervisor, quiet_receipt


def control(running=False, nonce='nonce'):
    return dict(Id='a'*64, Image='sha256:'+'b'*64, Name='/factory-control-'+nonce,
                Config={'Labels': {'factory.mission.nonce': nonce, 'factory.task': 'task'}},
                HostConfig={'AutoRemove': False}, State={'Running': running, 'Pid': 123 if running else 0, 'ExitCode': 0})


def supervisor(tmp_path):
    auth = tmp_path / 'operator-auth.json'
    auth.write_text('{"test":"not-a-real-credential"}')
    runner = Supervisor(tmp_path / 'home', 'task', 'sha256:'+'b'*64, tmp_path, tmp_path, auth)
    runner.remaining_control_budget = lambda state: dict(turns=32, wall_clock_s=14400)
    return runner


@pytest.mark.parametrize('change', [{'Running': True}, {'Pid': 12}])
def test_quiet_requires_all_control_processes_stopped(change):
    info = control()
    info['State'].update(change)
    with pytest.raises(ValueError, match='fully stopped'):
        quiet_receipt('attempt', info)


def test_control_ownership_must_match_nonce_and_image(tmp_path):
    runner = supervisor(tmp_path)
    info = control()
    runner.docker = lambda *args, **kw: type('Result', (), {'returncode': 0, 'stdout': json.dumps([info])})()
    with pytest.raises(ValueError, match='ownership'):
        runner.inspect_control(dict(name='factory-control-nonce', nonce='wrong', image=info['Image']))


def test_launch_mounts_single_auth_readonly_and_has_no_docker_socket(tmp_path):
    runner = supervisor(tmp_path)
    calls = []
    runner.docker = lambda *args, **kw: calls.append(args)
    runner.inspect_control = lambda intent: control(nonce=intent['nonce'])
    runner.launch_control(0)
    args = list(calls[0])
    assert 'FACTORY_YIELD_ON_JOBS=1' in args
    auth = [a for a in args if isinstance(a, str) and str(runner.auth_file) in a]
    assert len(auth) == 1 and auth[0].endswith(',readonly')
    assert all('docker.sock' not in str(a) for a in args)
    assert all('not-a-real-credential' not in str(a) for a in args)


def test_controller_exits_before_lab_barrier_then_restarts_review(tmp_path):
    runner = supervisor(tmp_path)
    rows = []
    order = []
    state = runner.home / 'sessions/task.state.json'
    state.parent.mkdir(parents=True)

    def reconcile():
        if rows and rows[0]['state'] == 'running':
            receipt = json.loads((runner.root / 'quiet.json').read_text())
            assert receipt['control_stopped'] is True
            order.append('lab-completes')
            rows[0]['state'] = 'succeeded'

    def launch(generation):
        assert not (runner.root / 'quiet.json').exists()
        order.append('agent-'+str(generation))
        if generation == 0:
            rows.append(dict(attempt_id='attempt', kind='lab', state='running'))
            state.write_text('{"outcome":"waiting"}')
        else:
            state.write_text('{"outcome":"accept"}')
        return {'nonce': 'nonce'}

    runner.reconcile = reconcile
    runner.recover_control = lambda: None
    runner.attempts = lambda: rows
    runner.launch_control = launch
    runner.inspect_control = lambda intent: (order.append('control-stopped') or control())
    runner.docker = lambda *args, **kw: None
    result = runner.run()
    assert result['outcome'] == 'accept'
    assert order.index('control-stopped') < order.index('lab-completes') < order.index('agent-1')


def test_supervisor_deadline_preserves_partial_and_cancels_owned(tmp_path):
    runner = supervisor(tmp_path)
    runner.deadline_s = 0
    calls = []
    runner.recover_control = lambda: calls.append('recover-control')
    runner.cancel_owned = lambda: calls.append('cancel-owned')
    result = runner.run()
    assert result['outcome'] == 'partial'
    assert 'TimeoutError' in result['error']
    assert calls == ['recover-control', 'recover-control', 'cancel-owned']
    assert json.loads((runner.root / 'supervisor-result.json').read_text()) == result


def test_restart_does_not_renew_expired_mission_budget(tmp_path):
    runner = supervisor(tmp_path)
    (runner.root / 'deadline.json').write_text('{"task_id":"task","started_at":0,"deadline_at":1}')
    runner.recover_control = lambda: None
    runner.cancel_owned = lambda: None
    runner.launch_control = lambda generation: pytest.fail('Expired mission must not launch control')
    assert runner.run()['outcome'] == 'partial'


def test_native_builder_has_no_gpu_network_or_writable_source(tmp_path):
    from jiuwenswarm.factory.spark_engine import native_compile_argv
    source, dependency, cache, output = (tmp_path / n for n in ('source','dependency','cache','out'))
    argv = native_compile_argv('sha256:'+'c'*64,source,dependency,cache,output,[])
    assert '--network=none' in argv and '--read-only' in argv
    assert f'type=bind,src={source},dst={source},readonly' in argv
    assert f'type=bind,src={dependency},dst={dependency},readonly' in argv
    assert not any('docker.sock' in a or '--device' in a or '--gpus' in a for a in argv)
    with pytest.raises(ValueError,match='immutable'):
        native_compile_argv('mutable:tag',source,dependency,cache,output,[])


def test_explicit_readonly_contract_mount_overrides_workspace(tmp_path):
    runner = supervisor(tmp_path)
    contract = tmp_path / 'operator-contract.json'
    contract.write_text('{}')
    runner.read_only_paths = (contract,)
    calls = []
    runner.docker = lambda *args, **kw: calls.append(args)
    runner.inspect_control = lambda intent: control(nonce=intent['nonce'])
    runner.launch_control(0)
    assert f'type=bind,src={contract},dst={contract},readonly' in calls[0]


def test_failed_control_preserves_submitted_lab_then_restarts_review(tmp_path):
    runner = supervisor(tmp_path)
    rows, events = [], []
    state = runner.home / 'sessions/task.state.json'
    state.parent.mkdir(parents=True)

    def reconcile():
        if rows and rows[0]['state'] == 'running':
            receipt = json.loads((runner.root / 'quiet.json').read_text())
            assert receipt['control_stopped'] and receipt['control_container_id'] == 'a'*64
            events.append('lab-reconciled-once')
            rows[0]['state'] = 'succeeded'

    def launch(generation):
        events.append('control-'+str(generation))
        if generation == 0:
            rows.append(dict(attempt_id='original-attempt', kind='lab', state='running'))
            state.write_text('{"outcome":"waiting"}')
        else:
            assert rows[0]['attempt_id'] == 'original-attempt'
            state.write_text('{"outcome":"accept"}')
        return {'nonce': str(generation)}

    def inspect(intent):
        info = control()
        if intent['nonce'] == '0':
            info['State']['ExitCode'] = 137
        return info

    runner.attempts = lambda: rows
    runner.reconcile = reconcile
    runner.recover_control = lambda: None
    runner.launch_control = launch
    runner.inspect_control = inspect
    runner.docker = lambda *args, **kwargs: None
    runner.cancel_owned = lambda: pytest.fail('One failed control must not cancel its durable lab job')
    assert runner.run()['outcome'] == 'accept'
    assert events == ['control-0', 'lab-reconciled-once', 'control-1']
    assert len(json.loads(runner.control_state_path.read_text())['failures']) == 1


def test_control_restart_allowance_persists_across_supervisor_restart(tmp_path):
    runner = supervisor(tmp_path)
    launches, cancels = [], []
    runner.attempts = lambda: []
    runner.reconcile = lambda: None
    runner.recover_control = lambda: None
    runner.docker = lambda *args, **kwargs: None
    runner.cancel_owned = lambda: cancels.append(True)

    def launch(generation):
        launches.append(generation)
        return {'nonce': str(generation)}

    def inspect(intent):
        info = control()
        info['Id'] = str(int(intent['nonce']) + 1)*64
        info['State']['ExitCode'] = 137
        return info

    runner.launch_control, runner.inspect_control = launch, inspect
    assert runner.run()['outcome'] == 'partial'
    assert launches == [0, 1, 2]  # initial control plus two bounded restarts
    assert len(json.loads(runner.control_state_path.read_text())['failures']) == 3
    runner.launch_control = lambda generation: pytest.fail('Restart cannot renew failure allowance')
    assert runner.run()['outcome'] == 'partial'
    assert len(cancels) == 2


def test_batched_cells_each_receive_quiet_barrier_before_review(tmp_path):
    runner = supervisor(tmp_path)
    rows = []
    state = runner.home / 'sessions/task.state.json'
    state.parent.mkdir(parents=True)
    completed = []

    def launch(generation):
        if generation == 0:
            rows.extend(dict(attempt_id='cell-'+str(i), kind='lab', state='queued') for i in range(3))
            state.write_text('{"outcome":"waiting"}')
        else:
            assert completed == ['cell-0', 'cell-1', 'cell-2']
            assert not (runner.root / 'quiet').exists()
            archived = list((runner.root / 'quiet-history').glob('*/*.json'))
            assert len(archived) == 3
            state.write_text('{"outcome":"accept"}')
        return {'nonce': 'nonce'}

    def reconcile():
        active = [r for r in rows if r['state'] == 'queued']
        if active:
            # Every cell has a receipt, including the first queued worker;
            # compatibility quiet.json happens to contain only the final ID.
            for row in active:
                receipt = json.loads((runner.root / 'quiet' / (row['attempt_id']+'.json')).read_text())
                assert receipt['attempt_id'] == row['attempt_id'] and receipt['control_stopped']
            assert json.loads((runner.root / 'quiet.json').read_text())['attempt_id'] == 'cell-2'
            for row in active:
                row['state'] = 'succeeded'
                completed.append(row['attempt_id'])

    runner.attempts = lambda: rows
    runner.reconcile = reconcile
    runner.recover_control = lambda: None
    runner.launch_control = launch
    runner.inspect_control = lambda intent: control()
    runner.docker = lambda *args, **kwargs: None
    assert runner.run()['outcome'] == 'accept'


def test_reconcile_does_not_reimport_historical_results_during_lab(tmp_path, monkeypatch):
    import jiuwenswarm.factory.mission_supervisor as module
    import jiuwenswarm.factory.manager as manager_module
    runner = supervisor(tmp_path)
    observed, imported = [], []
    rows = [dict(attempt_id='queued', kind='lab', state='queued', result_refs=[]),
            dict(attempt_id='unknown', kind='lab', state='unknown', result_refs=[]),
            dict(attempt_id='new-terminal', kind='lab', state='failed', result_refs=[]),
            dict(attempt_id='already-imported', kind='lab', state='succeeded',
                 result_refs=['already-imported:evaluation']),
            dict(attempt_id='build', kind='build', state='succeeded', result_refs=[])]
    class FakeStore:
        def __init__(self, home): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class FakeManager:
        def __init__(self, store, spool): self.jobs = self
        def status(self, attempt): observed.append(attempt)
        def result(self, attempt): imported.append(attempt)
    monkeypatch.setattr(module, 'Store', FakeStore)
    monkeypatch.setattr(manager_module, 'Manager', FakeManager)
    runner.attempts = lambda: rows
    runner.reconcile()
    assert observed == ['queued', 'unknown']
    assert imported == ['new-terminal']


def test_sequential_task_state_isolated_and_legacy_receipts_preserved(tmp_path):
    from jiuwenswarm.factory.mission_supervisor import mission_root
    import json
    home=tmp_path/'home';legacy=home/'mission';legacy.mkdir(parents=True)
    (legacy/'deadline.json').write_text(json.dumps({'task_id':'first','deadline_at':123}))
    assert mission_root(home,'first')==legacy
    assert mission_root(home,'second')==home/'missions/second'
    assert json.loads((legacy/'deadline.json').read_text())['task_id']=='first'


def test_cancel_owned_continues_after_one_child_cancellation_failure(tmp_path, monkeypatch):
    runner = supervisor(tmp_path)
    rows = [dict(attempt_id='first', state='unknown'), dict(attempt_id='second', state='running'),
            dict(attempt_id='finished', state='failed')]
    runner.attempts = lambda: rows
    calls = []
    def cancel(self, attempt_id):
        calls.append(attempt_id)
        if attempt_id == 'first':
            raise RuntimeError('queue unavailable')
        rows[1]['state'] = 'cancel_requested'
    monkeypatch.setattr('jiuwenswarm.factory.manager.Manager.cancel', cancel)
    errors = runner.cancel_owned()
    assert calls == ['first', 'second']
    assert errors == [{'attempt_id': 'first', 'error': 'RuntimeError: queue unavailable'}]


def test_parent_deadline_retains_pending_children_when_cleanup_fails(tmp_path):
    runner = supervisor(tmp_path)
    runner.deadline_s = 0
    calls = []
    def recover():
        calls.append('recover')
        if len(calls) > 1:
            raise RuntimeError('control cleanup unavailable')
    def cancel():
        calls.append('cancel')
        raise RuntimeError('queue unavailable')
    runner.recover_control = recover
    runner.cancel_owned = cancel
    runner.attempts = lambda: [dict(attempt_id='child-job', state='unknown')]
    result = runner.run()
    assert result['outcome'] == 'partial'
    assert 'TimeoutError' in result['error']
    assert calls == ['recover', 'recover', 'cancel']
    assert result['pending_attempts'] == ['child-job']
    assert result['cancellation_complete'] is False
    assert len(result['cleanup_errors']) == 2
    assert json.loads((runner.root / 'supervisor-result.json').read_text()) == result


def test_parent_deadline_does_not_call_requested_cancellation_complete(tmp_path):
    runner = supervisor(tmp_path)
    runner.deadline_s = 0
    runner.recover_control = lambda: None
    runner.cancel_owned = lambda: []
    runner.attempts = lambda: [dict(attempt_id='child-job', state='cancel_requested')]
    result = runner.run()
    assert result['pending_attempts'] == ['child-job']
    assert result['cleanup_errors'] == []
    assert result['cancellation_complete'] is False


def test_pending_note_cannot_restart_exhausted_shared_turn_budget(tmp_path):
    from jiuwenswarm.factory.store import Store
    from jiuwenswarm.factory.operator_notes import publish, pending
    runner=supervisor(tmp_path)
    del runner.remaining_control_budget  # exercise actual Controller shared accounting
    with Store(runner.home) as store:
        store.create_task(dict(task_id='owner',objective='shared budget',budget={'max_turns':32,'wall_clock_s':14400}))
        store.create_task(dict(task_id='task',objective='finish one admitted job',budget={'max_turns':8,'wall_clock_s':14400},constraints={'campaign_budget_owner':'owner'}))
    sessions=runner.home/'sessions';sessions.mkdir(exist_ok=True)
    owner=sessions/'owner.state.json';owner.write_text(json.dumps({'turns':32,'active_s':10}))
    state=sessions/'task.state.json';state.write_text(json.dumps({'turns':0,'outcome':'partial','active_s':0}))
    note=publish(runner.home,'task','Finish the existing task')
    runner.reconcile=lambda:None;runner.recover_control=lambda:None;runner.attempts=lambda:[]
    launches=[]
    def launch(generation):
        launches.append(generation)
        state.write_text(json.dumps({'turns':1,'outcome':'report_inconclusive','active_s':1,'operator_notes_delivered':[note['note_id']]}))
        return {'nonce':'nonce'}
    runner.launch_control=launch;runner.inspect_control=lambda intent:control();runner.docker=lambda *args,**kwargs:None
    result=runner.run()
    assert result['reason']=='control_budget_exhausted' and result['remaining']['turns']==0
    assert not launches and pending(runner.home,'task',json.loads(state.read_text()))
    deadline=(runner.root/'deadline.json').read_bytes()
    # Explicit operator amendment, not a note or restart, permits more planning.
    with Store(runner.home) as store:
        with store._transaction():
            store._db.execute('UPDATE tasks SET budget=? WHERE task_id=?',(json.dumps({'max_turns':40,'wall_clock_s':14400}),'owner'))
    assert runner.remaining_control_budget(json.loads(state.read_text()))['turns']==8
    assert runner.run()['outcome']=='report_inconclusive'
    assert launches==[0] and json.loads(owner.read_text())['turns']==32
    assert (runner.root/'deadline.json').read_bytes()==deadline
