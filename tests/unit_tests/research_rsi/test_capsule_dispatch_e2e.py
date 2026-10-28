"""Model-free end-to-end dispatch through the real worker program.

Parent and mutated candidates of both real packet capsules run through
``LocalDispatcher``: the actual frozen runtime tree, the actual bootstrap
program (local_unprotected profile), the real worker bodies, the real public
fixtures and the independent checker. No model call, no bwrap, no UID switch.
Results are Interface A visible results tagged ``local_unprotected``.
"""
import asyncio
import json
from pathlib import Path
import time

import pytest

from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets import capsule_executor as executor
from jiuwenswarm.research_rsi.targets.capsule_local_dispatcher import LocalDispatcher, dispatcher_for
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime, implementation_body  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[3]
# (name, stem, historical public baseline count); every loop grant evaluates the
# whole tagged inventory (public, public_extended and held_out) from the objective.
CASES = [('utility.calculate', 'calculate', 4), ('utility.table_normalize', 'table_normalize', 5)]


def inventory(name):
    return executor.evaluation_fixtures(name)


def loop_grant(manifest, name, *, budget_pairs=8, timeout_s=30):
    fixtures = executor.evaluation_fixtures(name)
    parent_path = 'source/jiuwenswarm/' + registered_capsule(name).carrier_path
    return {'schema': executor.LOOP_GRANT_SCHEMA, 'bootstrap_schema': executor.BOOTSTRAP_SCHEMA,
        'run_id': 'local-e2e-' + name.replace('.', '-'), 'capsule_name': name,
        'runtime_manifest_sha256': executor.digest(encoded(manifest)),
        'parent_sha256': next(row['sha256'] for row in manifest['files'] if row['path'] == parent_path),
        'fixture_sha256': executor.digest(encoded(fixtures)), 'fixture_count': len(fixtures),
        'roles': ['parent', 'candidate'], 'max_executions': len(fixtures) * 2 * budget_pairs, 'iterations': 1,
        'limits': {'timeout_s': timeout_s, 'memory_mb': 1024, 'pids_max': 32, 'wall_s': 900},
        'worker': {key: {'id': 'local:e2e', 'sha256': 'b' * 64} for key in ('contract_ref', 'environment_ref', 'hardware_ref')},
        'expires_unix_s': int(time.time()) + 900, 'scope': 'public_m1_development_only', 'production_admission': 'UNKNOWN'}


def make(tmp_path, runtime, manifest, grant):
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    root = tmp_path / 'evaluator'; root.mkdir()
    captures = RecordStore(tmp_path / 'captures')
    return LocalDispatcher(root=root, runtime_root=runtime, manifest=manifest, grant_path=grant_path,
        grant_sha256=executor.digest(grant_path.read_bytes()), cgroup_root=None, captures=captures), captures


def binding(value, ref):
    return {'schema': executor.BINDING_SCHEMA, **{key: value.grant[key] for key in
        ('run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256')},
        'mutable_path': registered_capsule(value.grant['capsule_name']).carrier_path,
        'candidate_ref': ref, 'grant_sha256': executor.digest(encoded(value.grant))}


def candidate(value, captures, body, iteration, **kwargs):
    ref = captures.put_bytes(body)
    return asyncio.run(value.evaluate('candidate', body=body, candidate_ref=ref, binding=binding(value, ref),
                                      iteration=iteration, **kwargs))


def assert_interface_a(result, *, role, iteration, count, body, captures):
    assert result['schema'] == 'ai4r-rsi-whole-capsule-visible-result:2'
    assert result['role'] == role and result['iteration'] == iteration
    assert result['subject_sha256'] == executor.digest(body)
    cases = inventory(result['capsule_name'])
    assert result['case_count'] == count == len(cases) and len(result['rows']) == count
    assert type(result['protected_wall_s']) is float and result['protected_wall_s'] == sum(r['protected_wall_s'] for r in result['rows'])
    assert result['scope'] == 'local_unprotected' and result['security'] == 'UNQUALIFIED' and result['model_calls'] == 0
    assert [row['fixture_id'] for row in result['rows']] == [f['id'] for f in cases]
    assert [(r['fixture_set'], r['fixture_group']) for r in result['rows']] == [(f['fixture_set'], f['fixture_group']) for f in cases]
    assert result['held_out_case_count'] == sum(f['fixture_set'] == 'held_out' for f in cases) > 0
    for row in result['rows']:
        assert type(row['output_bytes']) is int and isinstance(row['checks'], list)
        if row['fixture_set'] == 'held_out':
            # Held-out rows: no output, no error text, pass/fail per check id only.
            assert 'actual_task_output' not in row and 'error' not in row
            assert all(set(c) == {'check_id', 'outcome'} for c in row['checks'])
        else:
            task = row['actual_task_output']
            assert set(task) == {'value', 'truncated', 'bytes'} and type(task['truncated']) is bool
        receipt = row['receipt']
        assert receipt['scope'] == 'local_unprotected' and receipt['isolation'] == 'none'
        assert receipt['subject_ref']['sha256'] == executor.digest(body)
        start = captures.get(row['start_ref'])
        assert start['scope'] == 'local_unprotected' and start['fixture_id'] == row['fixture_id']
        # Exactly what the controller verifies: the row is its own evidence record.
        assert captures.get(row['evidence_ref']) == {k: v for k, v in row.items() if k != 'evidence_ref'}
        assert all(isinstance(row[key], dict) for key in ('input_ref', 'program_ref', 'check_ref'))
        assert row['bootstrap_schema'] == executor.BOOTSTRAP_SCHEMA
    stored = captures.get(result['result_ref'])
    assert stored == {k: v for k, v in result.items() if k != 'result_ref'}
    failure = result['failure']
    assert failure is None or (set(failure) == {'exception_type', 'message'} and all(isinstance(v, str) for v in failure.values()))


@pytest.mark.parametrize('name,stem,count', CASES)
def test_parent_mutated_and_broken_candidates_through_real_worker_program(installed_runtime, tmp_path, name, stem, count):
    runtime, manifest = installed_runtime
    value, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, name))
    baseline_count, count = count, len(inventory(name))
    groups = {f['id']: f['fixture_group'] for f in inventory(name)}
    try:
        parent = value.parent
        assert parent == (ROOT / 'jiuwenswarm' / registered_capsule(name).carrier_path).read_bytes()
        proposal = implementation_body(name)
        with pytest.raises(ValueError, match='BASELINE_MUST_COMPLETE_FIRST'):
            candidate(value, captures, parent + b'\n# early\n', 1)
        baseline = asyncio.run(value.evaluate('parent', body=parent, candidate_ref=value.parent_ref, iteration=0))
        assert_interface_a(baseline, role='parent', iteration=0, count=count, body=parent, captures=captures)
        # The real parent passes its whole historical public baseline; any case
        # it fails is a harder (public_extended / held_out) case -- the headroom.
        passing = [row for row in baseline['rows'] if row['task_success']]
        assert [row['fixture_group'] for row in baseline['rows']].count('public') == baseline_count
        assert all(row['task_success'] for row in baseline['rows'] if row['fixture_group'] == 'public')
        assert all(groups[row['fixture_id']] in ('public_extended', 'held_out')
                   for row in baseline['rows'] if not row['task_success'])
        assert baseline['passed_count'] == count == len(passing) and baseline['passed'] is (len(passing) == count)
        assert (baseline['failure'] is None) is (len(passing) == count)
        assert all(row['checks'] and all(c['outcome'] == 'PASS' for c in row['checks']) for row in passing)
        expected = {f['id']: f['expected_task_output'] for f in inventory(name) if f['fixture_set'] == 'public'}
        for row in passing:
            if row['fixture_set'] == 'held_out':
                continue
            task = row['actual_task_output']
            if task['truncated']:  # Large public cases: bounded JSON text prefix.
                assert task['bytes'] > executor.TASK_OUTPUT_CAP_BYTES and len(task['value'].encode()) <= executor.TASK_OUTPUT_CAP_BYTES
                assert json.dumps(expected[row['fixture_id']], sort_keys=True, separators=(',', ':'),
                                  ensure_ascii=False).startswith(task['value'])
            else:
                assert task['value'] == expected[row['fixture_id']]
        assert baseline['executions'] == count and value.executions == count

        # Iteration 1: a semantics-preserving mutation of the real body.
        mutated = proposal.replace(b"    packet = inputs['packet']\n",
                                 b"    packet = inputs['packet']\n    _unused_local_mutation = len(packet)\n", 1)
        assert mutated != parent
        improved = candidate(value, captures, mutated, 1)
        assert_interface_a(improved, role='candidate', iteration=1, count=count, body=mutated, captures=captures)
        assert [r['task_success'] for r in improved['rows']] == [r['task_success'] for r in baseline['rows']]
        assert improved['passed_count'] == baseline['passed_count']

        # Iteration 2: wrong output -> every case still evaluated, checker failure captured.
        before, after = ((b'result[column] = metrics', b'result[column] = {}') if stem == 'calculate'
                         else (b"return {'columns': columns, 'rows': rows}", b"return {'columns': columns, 'rows': rows[1:]}"))
        assert proposal.count(before) == 1
        wrong = candidate(value, captures, proposal.replace(before, after), 2)
        assert_interface_a(wrong, role='candidate', iteration=2, count=count, body=proposal.replace(before, after), captures=captures)
        assert wrong['passed_count'] < baseline['passed_count'] and not wrong['passed']
        assert wrong['failure']['exception_type'] == 'IndependentCheckFailed'

        # Iteration 3: a candidate that raises -> captured exception, no crash.
        broken = proposal.replace(b"    packet = inputs['packet']\n",
                                b"    packet = inputs['packet']\n    raise ZeroDivisionError('deliberately broken candidate')\n", 1)
        failed = candidate(value, captures, broken, 3)
        assert_interface_a(failed, role='candidate', iteration=3, count=count, body=broken, captures=captures)
        assert failed['passed_count'] == 0 and failed['executions'] == count
        assert failed['failure']['exception_type'] == 'ZeroDivisionError'
        assert 'deliberately broken candidate' in failed['failure']['message']
        assert all(row['receipt']['exit_code'] != 0 and row['independent_check'] is None for row in failed['rows'])
        # Public rows carry the objective's failure detail; held-out rows never do.
        assert all(row['error']['exception_type'] == 'ZeroDivisionError'
                   for row in failed['rows'] if row['fixture_set'] == 'public')

        # The dispatcher keeps serving after failed candidates; replays are refused.
        again = candidate(value, captures, mutated, 4)
        assert again['passed_count'] == baseline['passed_count']
        with pytest.raises(FileExistsError):
            candidate(value, captures, mutated, 4)
        # Repeated parent trials for noise calibration.
        trials = asyncio.run(value.evaluate('parent', body=parent, candidate_ref=value.parent_ref, iteration=5, trials=2))
        assert len(trials['trial_wall_s']) == 2 and trials['executions'] == 2 * count and len(trials['trial_rows']) == 1
        assert value.executions == count * 7  # parent + four candidates + two parent trials
        assert value.plan()['scope'] == 'local_unprotected'
    finally:
        captures.close()


def test_execution_budget_is_checked_before_any_job(installed_runtime, tmp_path):
    runtime, manifest = installed_runtime
    value, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, 'utility.calculate', budget_pairs=1))
    try:
        asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref, iteration=0))
        candidate(value, captures, value.parent + b'\n# one\n', 1)
        executions = value.executions
        with pytest.raises(ValueError, match='ROOT_EXECUTION_BUDGET_EXHAUSTED'):
            candidate(value, captures, value.parent + b'\n# two\n', 2)
        assert value.executions == executions == 2 * len(inventory('utility.calculate'))
    finally:
        captures.close()


def test_output_limit_guard_and_timeout_are_enforced_and_captured(installed_runtime, tmp_path):
    runtime, manifest = installed_runtime
    value, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, 'utility.calculate', timeout_s=2))
    try:
        asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref, iteration=0))
        flood = (b"import sys\nsys.stdout.buffer.write(b'x' * (3 * 1024 * 1024)); sys.stdout.flush()\n" + value.parent)
        result = candidate(value, captures, flood, 1)
        assert result['passed_count'] == 0
        for row in result['rows']:
            limits = row['receipt']['observed_limits']
            assert row['receipt']['termination_reason'] == 'output_limit_exceeded'
            assert limits['admin_output_truncated'] and limits['admin_output_captured_bytes'] == limits['admin_output_limit_bytes']
            assert row['output_bytes'] <= executor.MAX_OUTPUT_BYTES
        assert result['failure']['exception_type'] == 'OutputLimitExceeded'
        spin = implementation_body(value.grant['capsule_name']).replace(b"    packet = inputs['packet']\n", b"    packet = inputs['packet']\n    while True: pass\n", 1)
        started = time.monotonic()
        cases = len(inventory('utility.calculate'))
        result = candidate(value, captures, spin, 2, trials=3)
        # Every case is bounded by the 2 s job timeout (generous host slack)...
        assert time.monotonic() - started < cases * 2 * 2
        # ...and a timed-out candidate is not re-run for latency trials.
        assert result['executions'] == cases and len(result['trial_wall_s']) == 1
        assert {row['receipt']['termination_reason'] for row in result['rows']} == {'timeout'}
        assert result['failure']['exception_type'] == 'TimeoutError'
    finally:
        captures.close()


def test_dispatcher_is_selected_only_by_explicit_configuration(installed_runtime, tmp_path):
    runtime, manifest = installed_runtime
    grant = loop_grant(manifest, 'utility.table_normalize')
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    captures = RecordStore(tmp_path / 'captures')
    (tmp_path / 'evaluator').mkdir()
    options = dict(root=tmp_path / 'evaluator', runtime_root=runtime, manifest=manifest, grant_path=grant_path,
                   grant_sha256=executor.digest(grant_path.read_bytes()), cgroup_root=tmp_path, captures=captures)
    try:
        assert type(dispatcher_for({'dispatcher': 'local'}, **options)) is LocalDispatcher
        with pytest.raises(ValueError, match='EXPLICIT_DISPATCHER_KIND_REQUIRED'):
            executor.make_dispatcher('auto', **options)
        # No key keeps the protected V18 path; it never falls back to local.
        with pytest.raises(ValueError, match='ROOT_CAPSULE_DISPATCHER_REQUIRED|HISTORICAL_V18_EXECUTOR|ROOT_'):
            dispatcher_for({}, **options)
    finally:
        captures.close()


def test_publication_never_accepts_local_unprotected_results(installed_runtime, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('capsule_publication_for_scope_test', ROOT / 'deploy/m1/rsi_capsule_publication.py')
    publication = importlib.util.module_from_spec(spec); spec.loader.exec_module(publication)
    runtime, manifest = installed_runtime
    value, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, 'utility.calculate'))
    try:
        result = asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref, iteration=0))
        read = lambda ref: captures.read(ref)
        for shown in (result, {**result, 'schema': 'ai4r-rsi-whole-capsule-visible-result:1'}):
            with pytest.raises((ValueError, KeyError)):
                publication.visible_summary(shown, name='utility.calculate', body_ref=value.parent_ref, read=read)
        # Interface A v2 readers accept historical v1 results unchanged.
        assert executor.visible_result_v2(result) is result
    finally:
        captures.close()


def test_handed_case_list_labels_are_carried_and_held_out_rows_hide_outputs(installed_runtime, tmp_path, monkeypatch):
    from jiuwenswarm.research_rsi.targets import capsules
    public = public_fixtures('utility.table_normalize')
    cases = ([dict(row, fixture_set='public', fixture_group='public') for row in public]
             + [dict(public[0], id='extended-copy', fixture_set='public', fixture_group='public_extended'),
                dict(public[1], id='opaque-held-1', fixture_set='held_out', fixture_group='held_out',
                     packet={**public[1]['packet'], 'data': {**public[1]['packet']['data'],
                                                             'unrelated': {'hidden_marker': 'held-out-only'}}})])
    monkeypatch.setattr(capsules, 'evaluation_fixtures', lambda name: [dict(row) for row in cases], raising=False)
    runtime, manifest = installed_runtime
    value, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, 'utility.table_normalize'))
    try:
        parent = asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref, iteration=0))
        body = value.parent + b'\n# same list for candidates\n'
        child = candidate(value, captures, body, 1)
        for result in (parent, child):
            assert [r['fixture_id'] for r in result['rows']] == [c['id'] for c in cases]
            assert [(r['fixture_set'], r['fixture_group']) for r in result['rows']] == [
                (c['fixture_set'], c['fixture_group']) for c in cases]
            assert result['passed_count'] == result['case_count'] == len(cases) and result['held_out_case_count'] == 1
            held = result['rows'][-1]
            assert 'actual_task_output' not in held
            assert all('actual_task_output' in r for r in result['rows'][:-1])
            assert all(set(c) == {'check_id', 'outcome'} for c in held['checks'])
            # Held-out bytes are sealed: pinned, but unreadable via the public
            # capture closure transferred to the controller.
            from deploy.m1.rsi_capsule_run import capture_closure
            exported = [item['ref'] for item in capture_closure(captures, result)]
            # (Empty stderr is byte-identical to public jobs' and so shared.)
            sealed = [held['input_ref'], held['check_ref'], held['receipt']['stdout_ref'],
                      captures.get(held['start_ref'])['test_ref']]
            assert not any(ref in exported for ref in sealed)
            for ref in sealed:
                with pytest.raises(FileNotFoundError):
                    captures.read(ref)
            assert value._read(held['input_ref'])  # Root can still audit them.
            public_row = result['rows'][0]
            assert public_row['input_ref'] in exported and public_row['receipt']['stdout_ref'] in exported
            hidden_packet = json.dumps(cases[-1]['packet']['data'], sort_keys=True)
            assert hidden_packet not in json.dumps(result, sort_keys=True)
    finally:
        captures.close()
