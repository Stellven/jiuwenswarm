"""Selected release authority, immutable delegates and historical fixture separation."""
import asyncio
import copy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.targets import capsules
from jiuwenswarm.research_rsi.targets.capsule_fixtures import regenerate
from jiuwenswarm.research_rsi.targets.capsule_runtime import validate_runtime_manifest, check_capsule_output
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime


@pytest.mark.parametrize('name,release,version', [
    ('utility.calculate', 'calculate_v4', 'm1-4'),
    ('utility.table_normalize', 'table_normalize_v3', 'm1-3'),
    ('utility.markdown_report', 'markdown_report_v2', 'm1-2'),
    ('utility.summary_to_packet', 'summary_to_packet', 'm1-1'),
])
def test_selected_declared_worker_checker_and_criteria(name, release, version):
    target = capsules.registered_capsule(name)
    binding = capsules.release_binding(name)
    assert target.release_module == release and target.version_label == version
    assert target.carrier_path == f'research/capsule_extensions/{release}/worker.py'
    assert target.checks_path == f'research/capsule_extensions/{release}/checks.py'
    assert target.check_ids == ('result_schema', 'result_integrity')
    store = capsules._SourceStore()
    asset = importlib.import_module(f'{capsules._PACKAGE}.{release}.release').prepare(store)
    declaration = store.read_record(asset['declaration_ref'])
    assert 'research/' + declaration['identity']['carrier']['ref'] == target.carrier_path
    assert binding['declaration_sha256'] == asset['declaration_ref']['sha256']
    assert target.carrier_path in dict(target.dependency_pins)
    assert all('fixtures/' not in path for path, _ in target.dependency_pins)
    assert len(target.dependency_pins) > 3
    parent = asyncio.run(capsules.evaluate_in_process(name))
    assert parent['passed_count'] == parent['case_count']
    assert all(set(row['checks']) == set(target.check_ids) for row in parent['rows'])


def test_frozen_delegated_dependency_and_criteria_changes_are_rejected(installed_runtime):
    _, manifest = installed_runtime
    assert manifest['schema'] == 'ai4r-rsi-capsule-runtime:2'
    for field, value in [('check_ids', ['unrelated']), ('version_label', 'old')]:
        changed = copy.deepcopy(manifest)
        changed['target_bindings']['utility.calculate'][field] = value
        with pytest.raises(ValueError, match='binding differs'):
            validate_runtime_manifest(changed)
    changed = copy.deepcopy(manifest)
    row = next(row for row in changed['files'] if row['path'].endswith('calculate_v3/worker.py'))
    row['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='dependency missing or changed'):
        validate_runtime_manifest(changed)


def test_checker_uses_selected_release_and_refuses_old_binding():
    name = 'utility.calculate'
    execute, _, _ = capsules._carrier(name)
    packet = capsules.public_fixtures(name)[0]['packet']
    output = asyncio.run(execute(None, {'packet': packet}))['result'].data
    current = capsules.release_binding(name)
    result = check_capsule_output(name, inputs={'packet': packet}, output=output, binding=current)
    assert result['task_success']
    assert {row['check_id'] for row in result['checks']} == set(current['check_ids'])
    changed = copy.deepcopy(current); changed['checks_module'] = capsules._PACKAGE + '.calculate.checks'
    with pytest.raises(ValueError, match='frozen checking binding'):
        check_capsule_output(name, inputs={'packet': packet}, output=output, binding=changed)


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize', 'utility.summary_to_packet'])
def test_checker_fixture_regeneration_is_now_idempotent(name):
    result = asyncio.run(regenerate(name))
    assert not result['written'] and not result['changes']
    assert result['version_label'] == capsules.registered_capsule(name).version_label


def test_historical_expectations_and_checker_remain_separate():
    name = 'utility.calculate'
    current = next(row for row in capsules.fixture_set(name, 'public_extended')
                   if row['id'] == 'max-tie-trailing-zeros')
    historical = json.loads((capsules._EXTENSIONS / 'calculate/fixtures/history/m1-1/public_extended.json').read_text())
    old = next(row for row in historical['cases'] if row['id'] == current['id'])
    assert old['expected_task_output'] != current['expected_task_output']
    packet = current['packet']
    output = copy.deepcopy(packet)
    output['data'][capsules.registered_capsule(name).task_output_key] = old['expected_task_output']
    legacy = importlib.import_module(capsules._PACKAGE + '.calculate.checks').check
    rows = legacy(SimpleNamespace(output_refs={}), {'packet': packet}, {'result': output})
    assert all(row['outcome'] == 'PASS' for row in rows)
    assert not check_capsule_output(name, inputs={'packet': packet}, output=encoded(output))['task_success']


def test_report_packet_transform_runs_through_real_local_dispatcher(installed_runtime, tmp_path):
    from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import make, loop_grant, candidate
    runtime, manifest = installed_runtime
    name = 'utility.markdown_report'
    dispatcher, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, name))
    try:
        parent = asyncio.run(dispatcher.evaluate('parent', body=dispatcher.parent,
            candidate_ref=dispatcher.parent_ref, iteration=0))
        assert parent['passed_count'] == parent['case_count'] == 3
        child = candidate(dispatcher, captures, dispatcher.parent + b'\n# equivalent report wrapper\n', 1)
        assert child['passed_count'] == child['case_count'] == 3
        assert all(row['receipt']['scope'] == 'local_unprotected' for row in child['rows'])
        assert {row['independent_check']['checks_sha256'] for row in child['rows']} == {
            capsules.registered_capsule(name).checks_sha256}
    finally:
        captures.close()


def test_stale_fixture_release_is_explicitly_unavailable(monkeypatch):
    manifest = capsules._manifest
    def stale(stem):
        value = copy.deepcopy(manifest(stem))
        if value['capsule_name'] == 'utility.calculate':
            value['release_module'] = 'calculate'
        return value
    monkeypatch.setattr(capsules, '_manifest', stale)
    target = capsules._discover()['utility.calculate'][1]
    assert not target.public_evaluation_available and 'stale' in target.adapter_blocker
    assert target.release_module == 'calculate_v4' and target.version_label == 'm1-4'


def test_release_facts_are_detached_from_mutable_capture_objects():
    bindings = capsules.runtime_target_bindings()
    bindings['utility.calculate']['version_label'] = 'poisoned'
    assert capsules.release_binding('utility.calculate')['version_label'] == 'm1-4'


def test_declared_summary_input_runs_through_frozen_local_dispatcher(installed_runtime, tmp_path):
    from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import make, loop_grant, candidate
    from jiuwenswarm.research_rsi.targets.capsule_runtime import capsule_job_assets
    runtime, manifest = installed_runtime
    name = 'utility.summary_to_packet'
    target = capsules.registered_capsule(name)
    assert target.input_name == manifest['target_bindings'][name]['input_name'] == 'summary'
    fixture = capsules.public_fixtures(name)[0]
    inputs = capsules.fixture_inputs(name, fixture)
    assert set(inputs) == {'summary'} and 'data' not in fixture['packet']
    parent_body = (runtime / 'source/jiuwenswarm' / target.carrier_path).read_bytes()
    with pytest.raises(ValueError, match='wrapper required'):
        capsule_job_assets(name, runtime_root=runtime, manifest=manifest, candidate=parent_body,
                           inputs={'packet': fixture['packet']})
    dispatcher, captures = make(tmp_path, runtime, manifest, loop_grant(manifest, name))
    try:
        parent = asyncio.run(dispatcher.evaluate('parent', body=dispatcher.parent,
            candidate_ref=dispatcher.parent_ref, iteration=0))
        assert parent['passed_count'] == parent['case_count'] == 3
        child = candidate(dispatcher, captures, dispatcher.parent + b'\n# same declared summary conversion\n', 1)
        assert child['passed_count'] == child['case_count'] == 3
        for row in child['rows']:
            assert set(json.loads(dispatcher._read(row['input_ref']))) == {'summary'}
            assert row['independent_check']['checks_sha256'] == target.checks_sha256
        changed = dispatcher.parent + b"\n_original_execute = execute\nasync def execute(ctx, inputs):\n inputs['summary']['title'] = 'mutated'\n return await _original_execute(ctx, inputs)\n"
        bad = candidate(dispatcher, captures, changed, 2)
        assert bad['passed_count'] == 0
        assert all(row['receipt']['exit_code'] != 0 for row in bad['rows'])
        assert all('capsule input mutation refused' in row['error']['message']
                   for row in bad['rows'] if row['fixture_set'] == 'public')
    finally:
        captures.close()
