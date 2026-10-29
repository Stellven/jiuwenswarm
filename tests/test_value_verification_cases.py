"""Real deterministic check components and competent independent helper controls."""
import asyncio
import copy
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from benchmarks.harbor_suite.value_probe import fixtures, variants
from benchmarks.harbor_suite.value_verification_cases import ASSETS, SELECTION, freeze, load, run_cc, grade_batch


@pytest.fixture
def frozen(tmp_path):
    rows = []
    available = {case_id: (module, source) for module, case_id, source in fixtures()}
    for module, case_id, fault, _, _ in SELECTION:
        original_module, source = available[case_id]
        worker = importlib.import_module('jiuwenswarm.research.capsule_extensions.' + module + '.worker')
        output = json.loads(asyncio.run(worker.execute(None, {'packet': source}))['result'].data)
        proposed = next(value for name, valid, value in variants(original_module, output) if name == fault)
        rows.append({'module': module, 'case_id': case_id, 'fault': fault, 'input': source, 'output': proposed})
    record = tmp_path / 'scripted-test-probe.json'
    record.write_text(json.dumps({'kind': 'capability_probe', 'id': 'scripted-test-only',
        'value': {'paired_with': 'scripted-parent-only', 'rows': rows}}), encoding='utf-8')
    root = tmp_path / 'bank'
    freeze(root, probe_record=record)
    return root


def helper():
    spec = importlib.util.spec_from_file_location('ordinary_verify_helper', ASSETS / 'verify_helper.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_public_contract_separation_and_unique_original_inputs(frozen):
    cases = load(frozen)
    assert len(cases) == len({case['input_sha256'] for case in cases}) == 9
    assert sum(case['oracle']['expected_verdict'] == 'safe' for case in cases) == 3
    public = (frozen / 'public' / 'batch.json').read_text('utf-8')
    for forbidden in ('known_valid', 'type_coercion', 'dropped_row', 'boolean_count', 'wrong_sum', 'altered_report_with_valid_hash', 'expected_verdict', 'independent_rationale'):
        assert forbidden not in public
    assert (frozen / 'public/native_skill/SKILL.md').is_file()
    manifest = json.loads((frozen / 'manifest.json').read_text('utf-8'))
    assert manifest['new_independent_trials_claimed'] == 0


def test_actual_typed_checks_and_competent_helper_tie_on_same_artifacts(frozen, tmp_path):
    observations = run_cc(frozen, tmp_path / 'cc')
    assert len(observations) == 9
    assert all(row['status'] == 'observed' and row['grade']['correct'] for row in observations)
    assert all(row['model_calls'] == 0 and len(row['checks']) == 2 for row in observations)
    batch = json.loads((frozen / 'public/batch.json').read_text('utf-8'))
    response = {'results': [helper().verify(task) for task in batch['cases']]}
    result = grade_batch(frozen, response)
    assert result['response_valid'] and result['correct'] == 9
    assert sum(row['verdict'] == 'safe' for row in response['results']) == 3
    assert not any(row['false_positive'] or row['missed_fault'] for row in result['rows'])


def test_type_faults_expose_python_equality_but_helper_uses_json_types(frozen):
    cases = load(frozen); h = helper()
    for task_id in ('verify-004', 'verify-006', 'verify-008'):
        task = next(case['task'] for case in cases if case['id'] == task_id)
        expected = h.expected(task)
        assert expected == task['proposed_packet']  # The precise equality pitfall.
        assert h.canonical(expected) != h.canonical(task['proposed_packet'])
        assert h.verify(task)['verdict'] == 'unsafe'


def test_non_type_faults_include_rehashed_report_and_lost_rows(frozen):
    import hashlib
    cases = load(frozen); h = helper()
    report = next(case['task'] for case in cases if case['id'] == 'verify-009')
    for item in report['proposed_packet']['files']:
        assert hashlib.sha256(item['text'].encode()).hexdigest() == item['sha256']
    assert h.verify(report)['verdict'] == 'unsafe'
    dropped = next(case['task'] for case in cases if case['id'] == 'verify-005')
    assert len(dropped['proposed_packet']['data']['table']['rows']) == 31
    assert len(h.expected(dropped)['data']['table']['rows']) == 32


def test_missing_duplicate_or_wrong_native_results_do_not_get_credit(frozen):
    batch = json.loads((frozen / 'public/batch.json').read_text('utf-8'))
    response = {'results': [helper().verify(task) for task in batch['cases']]}
    duplicate = copy.deepcopy(response); duplicate['results'][-1] = duplicate['results'][0]
    assert not grade_batch(frozen, duplicate)['response_valid']
    wrong = copy.deepcopy(response); wrong['results'][0]['verdict'] = 'unsafe'; wrong['results'][3]['verdict'] = 'safe'
    grade = grade_batch(frozen, wrong)
    assert grade['correct'] == 7 and grade['rows'][0]['false_positive'] and grade['rows'][3]['missed_fault']


def test_source_artifacts_not_regenerated_and_frozen_mutation_rejected(frozen):
    private = json.loads((frozen / 'private/original-probe-record.json').read_text('utf-8'))
    for case in load(frozen):
        original = private['value']['rows'][case['oracle']['origin']['row_index']]
        assert case['task']['original_packet'] == original['input']
        assert case['task']['proposed_packet'] == original['output']
    path = frozen / 'public/verify-001.json'; path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        load(frozen)
