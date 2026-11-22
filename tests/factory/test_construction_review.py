"""CPU-only regressions for construction recovery and campaign admission."""
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import execution_binding
from jiuwenswarm.factory.jobs import Jobs
from jiuwenswarm.factory.loop import FactoryLoop
from jiuwenswarm.factory.store import Store
from tests.factory.test_construction import prepared_loop


@pytest.mark.parametrize('reused', [False, True])
@pytest.mark.parametrize('stopped', [False, True])
@pytest.mark.parametrize('build_state', ['failed', 'queued', 'succeeded'])
def test_existing_build_recovers_without_new_lab_after_admission_closes(tmp_path, monkeypatch, stopped, build_state, reused):
    from jiuwenswarm.factory.builder import Builder
    from jiuwenswarm.factory import experiment_build
    store, loop, spec = prepared_loop(tmp_path)
    loop.prepare_experiment('one', spec, 'sha256:' + 'a' * 64)
    cycle = loop.select('one', ['seed'], spec['hypothesis'], expected_rev=0, experiment_id='one')
    cycle['contract']['build_binding'] = {}
    cycle['contract']['specification']['build'] = {}
    with store._transaction():
        loop._write(cycle, 'test_build_selected')
    attempt = store.create_attempt(loop.task_id, dict(kind='build', idem_key=cycle['idem_key'] + '-build', fingerprint='test', request={}))
    if reused:
        with store._transaction():
            store._db.execute('UPDATE attempts SET idem_key=? WHERE attempt_id=?', ('original-build', attempt['attempt_id']))
            store._db.execute('INSERT INTO builder_reuse_keys VALUES (?,?,?,?)',
                              (loop.task_id, cycle['idem_key'] + '-build', 'test', attempt['attempt_id']))
    monkeypatch.setattr(Builder, 'status', lambda self, ident: dict(attempt, state=build_state))
    monkeypatch.setattr(Builder, 'submit', lambda *a, **k: pytest.fail('must not submit another build'))
    if build_state == 'succeeded':
        monkeypatch.setattr(experiment_build, 'ensure_build', lambda owner, selected: (selected, True))
    if reused:
        with pytest.raises(Exception, match='abandonment cannot hide'):
            loop.abandon('one', 'cannot hide reused build')
    if stopped:
        loop.stop('operator stopped')
    else:
        deadline = loop.status()['deadline']
        loop = FactoryLoop(store, loop.task_id, benchmark=loop.benchmark, clock=lambda: deadline + 1)
    if build_state == 'succeeded':
        with pytest.raises(ValueError, match='Loop stopped|wall clock'):
            loop.execute('one')
    else:
        result = loop.execute('one')
        assert result['state'] == ('collected' if build_state == 'failed' else 'selected')
    assert loop.benchmark.calls == 0
    assert store._db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 1
    store.close()


@pytest.mark.parametrize('kind,job_class,allowance', [('build', 'build', 'max_build_attempts'), ('lab', 'gpu', 'max_gpu_launches')])
def test_construction_allowance_uses_shared_attempts_and_retry_is_free(tmp_path, monkeypatch, kind, job_class, allowance):
    with Store(tmp_path / 'store') as store:
        authority = {'max_build_attempts': 1, 'max_gpu_launches': 1}
        store.create_task(dict(task_id='owner', objective='test', constraints={'factory_loop': {'experiment_authority': authority}}))
        for task in ('prior', 'revision', 'cpu'):
            store.create_task(dict(task_id=task, objective='test', constraints={'campaign_budget_owner': 'owner'}))
        jobs = Jobs(store)
        monkeypatch.setattr(jobs, '_call', lambda *a, **k: SimpleNamespace(stdout='job-test'))
        # CPU evidence consumes no GPU allowance.
        jobs.submit('cpu', 'lab', {}, 'cpu', 'cpu', ['test'], 1, {})
        first = jobs.submit('prior', kind, {}, 'one', job_class, ['test'], 1, {})
        assert jobs.submit('prior', kind, {}, 'one', job_class, ['test'], 1, {})['attempt_id'] == first['attempt_id']
        store.transition_attempt('prior', first['attempt_id'], 'failed')
        with pytest.raises(ValueError, match=allowance):
            jobs.submit('revision', kind, {}, 'two', job_class, ['test'], 1, {})
        assert store._db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 2


def test_python_binding_checks_executing_interpreter_before_dispatch(monkeypatch):
    store = SimpleNamespace(get_task=lambda task: {'constraints': {'execution_binding': {'runtime': {'python': '/pinned/python', 'sha256': 'a' * 64, 'dependencies': {}}}}})
    monkeypatch.setattr(execution_binding, 'file_digest', lambda path: 'b' * 64)
    with pytest.raises(ValueError, match='Running interpreter differs'):
        execution_binding.verify_task(store, 'task')


def test_successful_build_reuse_does_not_spend_another_allowance(tmp_path, monkeypatch):
    from jiuwenswarm.factory.builder import Builder
    with Store(tmp_path / 'store') as store:
        authority = {'max_build_attempts': 1, 'max_gpu_launches': 0}
        store.create_task(dict(task_id='owner', objective='test', constraints={'factory_loop': {'experiment_authority': authority}}))
        builder = Builder(store)
        normalized = dict(env={}, deadline_s=1, source={'commit': 'frozen'}, tag='retained')
        monkeypatch.setattr(builder, '_request', lambda request: normalized.copy())
        monkeypatch.setattr(builder.jobs, '_call', lambda *a, **k: SimpleNamespace(stdout='job-test'))
        monkeypatch.setattr(builder.jobs, 'status', lambda ident: builder.jobs._get(ident))
        first = builder.submit('owner', {}, 'original')
        store.transition_attempt('owner', first['attempt_id'], 'running')
        store.transition_attempt('owner', first['attempt_id'], 'succeeded')
        assert builder.submit('owner', {}, 'reuse')['attempt_id'] == first['attempt_id']
        assert builder.submit('owner', {}, 'reuse')['attempt_id'] == first['attempt_id']
        assert store._db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 1
