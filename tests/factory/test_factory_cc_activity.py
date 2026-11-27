"""Read-only evidence tests for capsule use and verifier distinctions."""

from jiuwenswarm.gateway.channel_manager.web import factory_cc_activity as activity
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService


def record(id, kind, created, values, task_id='task', **extra):
    return dict(obs_id=id, kind=kind, created=created, values=values, task_id=task_id, **extra)


def final(ccs):
    return dict(node_id='first', digest='approved', cc_versions={cc: '1.0' for cc in ccs},
                final=dict(work=dict(bound_ccs=ccs)))


def graph(entries=()):
    return dict(nodes=[dict(node_id='first', final_contract='approved'), dict(node_id='other')], history=entries)


def test_worker_use_verifier_execution_and_declaration_are_independent():
    cc_list = ['example.check', 'factory.capped_runner', 'example.unused', 'example.unknown']
    data = dict(tasks=[dict(task_id='task')], observations=[
        record('final', 'node_contract_final', 1, final(cc_list)),
        record('scheduler-private-call', 'cc_call', 2, dict(node_id='first', cc='example.unused', role='scheduler-agent')),
        record('foreign-node', 'cc_call', 2, dict(node_id='other', cc='example.unused')),
        record('foreign-task', 'cc_call', 2, dict(node_id='first', cc='example.unused'), task_id='different'),
        record('host-verifier', 'node_check', 4, dict(node_id='first', output='legacy-name', passed=False, state='finished',
               verifier=dict(cc='example.check', capability='verify', passed=True))),
        record('capped-receipt', 'capped_run', 5, dict(node_id='first', attempt_id='capped-id', recipe='serve'),
               host_run=dict(module='jiuwenswarm.factory.capped_run')),
        record('wrong-node-receipt', 'capped_run', 6, dict(node_id='other', attempt_id='capped-id', recipe='serve'),
               host_run=dict(module='jiuwenswarm.factory.capped_run')),
    ], attempts=[dict(attempt_id='capped-id', request=dict(node_id='first', recipe='serve'), started=3)])
    declarations = {
        ('example.check', '1.0'): [('sealed-check', dict(declaration=dict(capabilities={'verify': {}})))],
        ('factory.capped_runner', '1.0'): [('sealed-capped', dict(declaration=dict(capabilities={'start': {}})))],
        ('example.unused', '1.0'): [('sealed-helper', dict(declaration=dict(capabilities={'submit': {}})))],
    }
    calls = [
        dict(id='tool-id', node_id='first', cc='factory.capped_runner', capability='status', created=3),
        dict(id='verifier-call', node_id='other', cc='example.check', capability='verify', created=3,
             result_at=3.5, verifier_passed=True),
    ]
    result = activity.project(data, graph(), calls, declarations, {'observations': 'observations.json'}, 'source-run')
    node = result['first']
    check_cc, runner, unused, unknown = node['capsules']
    assert [(row['kind'], row['id']) for row in check_cc['uses']] == [('cc-verifier', 'host-verifier')]
    assert check_cc['verifier_declaration'] == 'declared'
    assert check_cc['verifier_records'][0]['id'] == 'host-verifier'
    assert check_cc['verifier_records'][0]['status'] == 'pass'
    assert node['node_checks'][0] == dict(id='host-verifier', created=4, kind='node-check',
                                      path='observations.json', output='legacy-name', status='fail')
    assert {row['id'] for row in runner['uses']} == {'tool-id', 'capped-id', 'capped-receipt'}
    assert runner['verifier_declaration'] == 'none' and runner['verifier_records'] == []
    assert unused['uses'] == [] and unused['verifier_declaration'] == 'none'
    assert unknown['uses'] == [] and unknown['verifier_declaration'] == 'unknown'


def test_reached_and_cc_use_require_node_scoped_activity():
    data = dict(tasks=[dict(task_id='task')], observations=[
        record('final', 'node_contract_final', 1, final(['example.check', 'example.helper'])),
        record('future-final', 'node_contract_final', 2,
               final(['example.check']) | dict(node_id='other', digest='future')),
        record('planned-check', 'node_check', 4,
               dict(node_id='first', state='finished', passed=False, verifier={'cc': 'example.check'})),
        record('import', 'operator_input', 3, dict(artifact_id='out', producer_cc='example.helper'),
               source_artifacts=['out']),
        record('actual-check', 'node_check', 5, dict(node_id='first', state='finished', passed=True,
               refs=dict(artifact_ids=['out']),
               verifier=dict(cc='example.check', capability='verify', call='local-call', passed=False))),
    ], decisions=[dict(task_id='task', decision_id='plan', created=2, action=dict(type='propose', node_id='other')),
                  dict(task_id='task', decision_id='work', created=2, action=dict(type='inspect', node_id='first'))])
    receipts = [dict(id='local-call', cc='example.check', created=4.5, capability='verify'),
                dict(id='future-other-task', cc='example.check', node_id='other', task_id='different', created=2)]
    result = activity.project(data, graph(), receipts=receipts)
    node = result['first']
    assert node['reached']['id'] == 'work'
    assert node['searched']['operator_imports'] == ['import']
    assert node['searched']['ccstore_calls'] == ['local-call']
    assert node['capsules'][0]['verifier_records'][0]['status'] == 'fail'
    assert [row['id'] for row in node['capsules'][0]['uses']] == ['local-call', 'actual-check']
    use, = node['capsules'][1]['uses']
    assert (use['id'], use['created'], use['artifact_id']) == ('import', 5, 'out')
    assert result['other']['reached'] is None
    assert result['other']['capsules'][0]['uses'] == []


def test_read_ccstore_with_committed_rows_still_in_active_wal(tmp_path):
    import json
    import sqlite3
    from contextlib import closing

    path = tmp_path / 'calls.sqlite'
    release = 'release'
    with closing(sqlite3.connect(path)) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('CREATE TABLE calls (receipt TEXT)')
        receipt = dict(call='native-call', release=release, capability='produce', state='succeeded',
                       provenance=dict(started=42, inputs=dict(request=dict(node_id='first', task_id='task'))))
        writer.execute('INSERT INTO calls VALUES (?)', (json.dumps(receipt),))
        writer.commit()
        assert path.with_name(path.name + '-wal').stat().st_size > 0
        before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
        result = activity.ccstore_calls(path, {('example.helper', '1.0'): [(release, {})]})
        assert result == [dict(id='native-call', cc='example.helper', created=42, capability='produce',
                               node_id='first', task_id='task', state='succeeded')]
        assert before == {file.name: file.read_bytes() for file in tmp_path.iterdir()}


def test_closure_and_binding_end_are_exact_committed_records():
    entries = [
        dict(rev=1, origin='seed', patch=dict(add=[dict(node_id='first')])),
        dict(rev=2, origin='scheduler', patch=dict(finalize=[dict(node_id='first', digest='approved')])),
        dict(rev=3, origin='decision', decision_rev=7, patch=dict(update=[dict(node_id='first', state='done',
                                                                              evidence_ids=['accepted-output'])])),
        dict(rev=4, origin='operator', patch=dict(reopen=[dict(node_id='first', reason='Revisit')])),
    ]
    data = dict(tasks=[dict(task_id='task')], observations=[
        record('final', 'node_contract_final', 1, final(['example.check'])),
        *[record(f'plan-{entry["rev"]}', 'taskgraph_patch', entry['rev'], entry) for entry in entries],
    ], decisions=[dict(decision_id='native-decision-seven', rev=7)])
    result = activity.project(data, dict(nodes=[dict(node_id='first')], history=entries))['first']
    done, reopened = result['closures']
    assert done['decision_id'] == 'native-decision-seven' and done['evidence_ids'] == ['accepted-output']
    assert result['node_checks'] == []
    assert reopened['id'] == 'plan-4' and reopened['state'] == 'reopened'
    binding = result['capsules'][0]
    assert not binding['active'] and binding['unbound_at'] == 4
    assert binding['bindings'][0]['unbound_source']['id'] == 'plan-4'


def test_archive_only_borrows_exact_home_without_post_export_call_results(tmp_path, monkeypatch):
    archive, native = tmp_path/'archive', tmp_path/'native'
    archive.mkdir()
    native.mkdir()
    service = FactoryHttpService(roots=[archive, native])
    monkeypatch.setattr(service, 'expected', lambda *args: {})
    observed = []

    def load(path):
        observed.append(path)
        return [
            dict(id='within', request_node_id='first', node_id='other', cc='example.check',
                 capability='verify', created=5, result_at=13, verifier_passed=True),
            dict(id='direct', node_id='first', cc='example.check', capability='verify',
                 created=4, result_at=6, verifier_passed=True),
            dict(id='late', node_id='first', cc='example.check', capability='verify', created=14),
        ]
    monkeypatch.setattr(service, '_worker_transcript', load)
    bundle = dict(id='replay', kind='bundle', task_id='task', original_run_id='native')
    verified_origin = dict(id='native', kind='live', task_id='task', created=1)
    data = dict(tasks=[dict(task_id='task', created=1)], observations=[
        record('final', 'node_contract_final', 1, final(['example.check'])),
        record('end', 'node_check', 10, dict(node_id='first', state='finished', passed=True)),
    ])
    wrong = dict(verified_origin, created=2)
    assert service.capsule_activity(bundle, archive, data, graph(), [(wrong, native)])[1] == []
    _, calls, _ = service.capsule_activity(bundle, archive, data, graph(), [(verified_origin, native)])
    assert observed == [native/'sessions/task.jsonl']
    assert [row['id'] for row in calls] == ['within', 'direct']
    assert calls[0]['node_id'] == 'first' and 'verifier_passed' not in calls[0]
    assert calls[1]['verifier_passed']


def test_manifest_backed_portable_activity_restores_use_without_a_native_home(tmp_path):
    from hashlib import sha256
    import json

    task = dict(task_id='task', created=2)
    data = dict(tasks=[task], observations=[
        record('final', 'node_contract_final', 3, final(['example.check'])),
        record('snapshot-end', 'node_check', 10, dict(node_id='first', state='finished', passed=True)),
    ])
    archive = tmp_path/'archive'
    archive.mkdir()
    path = archive/activity.PORTABLE_PATH
    path.parent.mkdir(parents=True)
    plan = graph() | dict(rev=4)
    origin = 'a' * 24
    release = '1' * 64
    stored = activity.project(
        data, plan,
        [dict(id='direct', node_id='first', cc='example.check', capability='verify',
              created=4, result_at=8, verifier_passed=False)],
        {('example.check', '1.0'): [(release, dict(declaration=dict(capabilities={'verify': {}})))]},
        call_run_id=origin,
    )
    cc = stored['first']['capsules'][0]
    cc['uses'].append(dict(id='future', kind='worker-call', created=11, source_run_id=origin))
    key = dict(schema=activity.PORTABLE_SCHEMA, task_id='task', task_created=2, as_of=10, graph_rev=4,
               source_run_id=origin, nodes=stored)
    path.write_text(json.dumps(key))
    manifest_path = archive/'MANIFEST.json'
    manifest_path.write_text(json.dumps({activity.PORTABLE_PATH: sha256(path.read_bytes()).hexdigest()}))
    service = FactoryHttpService(roots=[archive])
    bundle = dict(id='read-only-replay', kind='bundle', task_id='task')
    result, calls, _ = service.capsule_activity(bundle, archive, data, plan)
    assert calls == []
    restored = result['first']['capsules'][0]
    assert [row['id'] for row in restored['uses']] == ['direct']
    assert restored['uses'][0]['path'] == activity.PORTABLE_PATH
    assert restored['verifier_records'][0]['status'] == 'fail'
    assert restored['verifier_declaration'] == 'declared'
    assert restored['verifier_declaration_source']['id'] == release
    attempt, _, _ = service.capsule_activity(bundle, archive, data, dict(plan, rev=3))
    assert attempt['first']['capsules'][0]['uses'] == []
    path.write_text(json.dumps(dict(key, task_created=9)))  # Files edited after manifest creation never contribute.
    attempt, _, _ = service.capsule_activity(bundle, archive, data, plan)
    assert attempt['first']['capsules'][0]['uses'] == []
