"""Exploratory tools retain real populations; these fixtures are not trials."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from benchmarks.harbor_suite.contracts import canonical
from benchmarks.harbor_suite.value_data import Dataset, csv_bytes, public_record, write_once
from benchmarks.harbor_suite.value_campaign import import_job, import_comparison, launch_once


def task():
    return {'case_id': 'cc01-transfer', 'variant_id': 'evaluate-boundary', 'repeat': 1,
            'expected_model': 'test-model', 'variant': {'expected_behavior': 'complete'},
            'case': {'classification': 'core_m1_acceptance'}}


def assessment(t):
    return {'case_id': t['case_id'], 'variant_id': t['variant_id'], 'repeat': t['repeat'],
            'expected_model': t['expected_model'], 'task_sha256': hashlib.sha256(canonical(t)).hexdigest(),
            'status': 'unavailable', 'execution_available': False, 'case_correctness': None,
            'metrics': {}, 'checks': [], 'critical_violations': []}


def job(tmp_path, results):
    bundle = tmp_path / 'bundle'; bundle.mkdir()
    t = task()
    write_once(bundle / 'task-index.json', {'tasks': [t]})
    root = tmp_path / 'job'; root.mkdir()
    for ordinal, value in enumerate(results):
        path = root / str(ordinal) / 'verifier'; path.mkdir(parents=True)
        write_once(path / 'assessment.json', value)
    return bundle, root


def test_immutable_records_and_duplicate_import_do_not_inflate_population(tmp_path):
    bundle, root = job(tmp_path, [assessment(task())])
    data = tmp_path / 'data'
    result = import_job(data, bundle, root)
    assert result['value']['rows'][0]['correct'] is None
    assert result['value']['summary']['scheduled'] == 1
    with pytest.raises(FileExistsError):
        import_job(data, bundle, root)
    assert len(Dataset(data).records()) == 1


def test_missing_attempt_stays_in_rows_and_denominator(tmp_path):
    bundle, root = job(tmp_path, [])
    result = import_job(tmp_path / 'data', bundle, root)
    assert result['value']['summary']['missing'] == 1
    assert result['value']['rows'][0]['status'] == 'not_observed'


@pytest.mark.parametrize('change', ['task_sha256', 'expected_model'])
def test_foreign_assessment_is_rejected_before_adoption(tmp_path, change):
    value = assessment(task()); value[change] = 'foreign'
    bundle, root = job(tmp_path, [value])
    with pytest.raises(ValueError):
        import_job(tmp_path / 'data', bundle, root)
    assert not Dataset(tmp_path / 'data').records()


def test_duplicate_assessments_and_changed_artifacts_are_rejected(tmp_path):
    bundle, root = job(tmp_path, [assessment(task()), assessment(task())])
    with pytest.raises(ValueError, match='duplicate'):
        import_job(tmp_path / 'data', bundle, root)
    data = Dataset(tmp_path / 'data')
    source = root / '0/verifier/assessment.json'
    ref = data.artifact(source)
    data.append('test', {'source': ref})
    (data.root / ref['path']).write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        data.records()


@pytest.mark.parametrize('value', [{'api_key': 'secret'}, {'nested': [{'refresh_token': 'secret'}]},
                                  {'x': 'Bearer abcdefghijklmnopqrst'}, {'value': float('nan')}])
def test_credentials_and_nonfinite_measurements_never_persist(value):
    with pytest.raises(ValueError):
        public_record(value)


def test_csv_formula_text_is_escaped_and_missing_is_blank():
    raw = csv_bytes([{'case': '=HYPERLINK("bad")', 'cost': None}], ['case', 'cost']).decode('utf-8-sig')
    assert "'=HYPERLINK" in raw and 'None' not in raw


def test_verified_mirror_can_resume_but_never_overwrite(tmp_path):
    data = Dataset(tmp_path / 'data')
    record = data.append('fixture', {'observed': 1})
    first = data.mirror(tmp_path / 'mirror')
    assert first['files'] == 1
    assert data.mirror(tmp_path / 'mirror') == first
    (tmp_path / 'mirror/records' / (record['id'] + '.json')).write_text('{}')
    with pytest.raises(ValueError, match='never overwrite'):
        data.mirror(tmp_path / 'mirror')


def test_comparison_import_uses_actual_existing_schema(tmp_path):
    path = tmp_path / 'pair.json'
    write_once(path, {'schema': 'native-codex-ai4r-paired-comparison:1',
                     'arms': {'native_codex_tool_free': {}, 'ai4r_cc': {}},
                     'sample_pairs': 1, 'assignment_sha256': 'a' * 64})
    result = import_comparison(tmp_path / 'data', path)
    assert result['kind'] == 'comparison_summary'
    with pytest.raises(FileExistsError):
        import_comparison(tmp_path / 'data', path)


def test_hand_authored_incomplete_comparison_is_not_credited(tmp_path):
    path = tmp_path / 'pair.json'
    write_once(path, {'schema': 'native-codex-ai4r-paired-comparison:1', 'arms': {}, 'sample_pairs': 1})
    with pytest.raises(ValueError, match='incomplete'):
        import_comparison(tmp_path / 'data', path)


def test_launch_timeout_is_unknown_and_cannot_resubmit(tmp_path, monkeypatch):
    path = tmp_path / 'job.json'
    write_once(path, {'n_attempts': 1, 'n_concurrent_trials': 1, 'retry': {'max_retries': 0}})
    calls = []
    def timeout(argv, **kwargs):
        calls.append(argv)
        raise subprocess.TimeoutExpired(argv, 1)
    monkeypatch.setattr(subprocess, 'run', timeout)
    result = launch_once(tmp_path / 'data', path, timeout_s=1)
    assert result['value']['status'] == 'outcome_unknown'
    with pytest.raises(FileExistsError):
        launch_once(tmp_path / 'data', path, timeout_s=1)
    assert len(calls) == 1


def test_launch_rejects_retry_before_any_effect(tmp_path, monkeypatch):
    path = tmp_path / 'job.json'
    write_once(path, {'n_attempts': 2, 'n_concurrent_trials': 1, 'retry': {'max_retries': 0}})
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('must not dispatch'))
    with pytest.raises(ValueError):
        launch_once(tmp_path / 'data', path)


@pytest.mark.usefixtures('benchmark_case_assets')
def test_plan_reuses_29_existing_variants_without_product_calls(tmp_path):
    from benchmarks.harbor_suite.value_campaign import plan
    result = plan(tmp_path / 'plan.json')
    assert len(result['scheduled']) == 29
    assert len(result['cases']) == 4
    assert all(c['module'] in ('cc', 'verifier') for c in result['cases'])
    with pytest.raises(FileExistsError):
        plan(tmp_path / 'plan.json')
