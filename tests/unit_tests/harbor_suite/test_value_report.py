import copy
import json

import pytest

from benchmarks.harbor_suite.value_data import Dataset
from benchmarks.harbor_suite.value_report import flatten, paired_gains, probe_improvements, render


def probe():
    return {'case_id': 'sample', 'module': 'test_checker', 'known_valid': False,
            'checker_accepted': False, 'checker_elapsed_s': .01}


def test_selected_view_preserves_full_population_and_nulls(tmp_path):
    data = Dataset(tmp_path / 'data')
    first = data.append('capability_probe', {'rows': [probe()]})
    data.append('capability_probe', {'rows': [dict(probe(), checker_accepted=True)]})
    output = tmp_path / 'report'
    result = render(data.root, output, selected_records=[first['id']], charts=False)
    assert result['rows'] == 2 and result['selected'] == 1
    assert len((output / 'all-results.jsonl').read_text().splitlines()) == 2
    assert 'Part A' in (output / 'report.md').read_text()
    assert 'Part B' in (output / 'report.md').read_text()
    assert 'live semantic-verifier accuracy' in (output / 'report.md').read_text()
    with pytest.raises(ValueError):
        render(data.root, output, charts=False)


def test_unknown_selection_does_not_create_report(tmp_path):
    data = Dataset(tmp_path / 'data')
    with pytest.raises(ValueError):
        render(data.root, tmp_path / 'report', selected_records=['foreign'], charts=False)
    assert not (tmp_path / 'report').exists()


def test_template_is_filled_and_original_preserved(tmp_path):
    data = Dataset(tmp_path / 'data')
    template = tmp_path / 'template.md'
    template.write_text('# Team decision\n\n{{PART_A}}\n\n{{PART_B}}\n')
    render(data.root, tmp_path / 'report', template=template, charts=False)
    assert (tmp_path / 'report/report.md').read_text().startswith('# Team decision')
    assert '{{PART_A}}' in template.read_text()


def test_content_gain_is_unavailable_for_mismatched_or_unknown_models():
    arm = {'effective_model': 'm', 'reasoning_effort': 'medium',
           'content': {'metrics': {'deterministic_content_success': 0}}}
    result = {'assignment_sha256': 'a' * 64,
              'arms': {'native_codex_tool_free': copy.deepcopy(arm), 'ai4r_cc': copy.deepcopy(arm)}}
    result['arms']['ai4r_cc']['content']['metrics']['deterministic_content_success'] = 1
    record = {'kind': 'comparison', 'id': 'one', 'value': {'result': result, 'recomputed': True}}
    assert paired_gains([record])[0]['delta'] == 1
    result['arms']['ai4r_cc']['effective_model'] = None
    assert paired_gains([record])[0]['delta'] is None


def test_probe_repeats_are_not_cross_joined():
    def row(ident, module, paired=None):
        return {'record_id': ident, 'record_kind': 'capability_probe', 'module': module,
                'paired_with': paired, 'case_id': 'one', 'fault': 'mutation',
                'input_sha256': 'a' * 64, 'artifact_sha256': 'b' * 64,
                'known_valid': False, 'checker_accepted': module.endswith('_v2')}
    rows = [row('before1', 'calculate_v2'), row('before2', 'calculate_v2'),
            row('after1', 'calculate_typed', 'before1'), row('after2', 'calculate_typed', 'before2')]
    result = probe_improvements(rows)
    assert len(result) == 2
    assert {(r['before_record'], r['after_record']) for r in result} == {('before1', 'after1'), ('before2', 'after2')}


def test_unvalidated_summary_never_enters_paired_gain_analysis():
    assert paired_gains([{'kind': 'comparison_summary', 'value': {}}]) == []


def component_pair():
    return {'component': 'typed_artifact_verification', 'native_status': 'completed',
        'comparison_eligible': True, 'scope': 'Actual deterministic component versus native batch; not full-unit.',
        'batch_cost': {'cc_model_calls': 0, 'native_model_calls': 8, 'cost_usd': None,
                       'per_case_model_call_allocation': None},
        'population': {'native_batches': 1, 'artifact_decisions': 2, 'independent_native_trials': 1},
        'alignment': {'missing_ids': [], 'unexpected_ids': [], 'duplicate_ids': []},
        'ordinary_helper_control': {'measurement_status': 'observed_original_helper_receipt',
                                    'correct': 2, 'decisions': 2, 'model_calls': 0},
        'rows': [{'case_id': name, 'task_sha256': str(index) * 64,
                  'cc': {'available': True, 'correct': True, 'checks': [{'check_id': 'integrity', 'outcome': 'PASS'}]},
                  'native': {'available': True, 'correct': True}, 'per_case_call_allocation': None}
                 for index, name in enumerate(('verify-001', 'verify-002'))]}


def test_component_flatten_preserves_each_decision_without_distributing_batch_cost(tmp_path):
    data = Dataset(tmp_path / 'data')
    original = data.append('component_native_pair', component_pair())
    rows = flatten(data.records())
    assert len(rows) == 4
    assert {row['arm'] for row in rows} == {'cc', 'native'}
    assert all(row['batch_record_id'] == original['id'] for row in rows)
    assert all(row['model_calls'] is None and row['cost_usd'] is None for row in rows)
    assert all('native_model_calls' not in row for row in rows)
    assert rows[0]['checks'] == [{'check_id': 'integrity', 'outcome': 'PASS'}]


def test_component_selected_view_keeps_whole_batch_cost_and_reproducible_case_selection(tmp_path):
    data = Dataset(tmp_path / 'data')
    original = data.append('component_native_pair', component_pair())
    before = data.snapshot()
    reports = [tmp_path / 'report-one', tmp_path / 'report-two']
    for output in reports:
        result = render(data.root, output, selected_records=[original['id']], selected_cases=['verify-002'], charts=False)
        assert result['rows'] == 4 and result['selected'] == 2
        all_rows = [json.loads(line) for line in (output / 'all-results.jsonl').read_text().splitlines()]
        assert len(all_rows) == 4
        analysis = json.loads((output / 'analysis.json').read_text())
        batch = analysis['component_native_batches'][0]
        assert batch['selected_case_ids'] == ['verify-002']
        assert batch['selected_decisions'] == 1 and batch['batch_decisions'] == 2
        assert batch['batch_cost']['native_model_calls'] == 8
        assert batch['population']['independent_native_trials'] == 1
        assert batch['algorithm_gain_claim'] is False
        text = (output / 'report.md').read_text()
        assert '| typed_artifact_verification | 1/2 | 1/1 | 1/1 | 0/0 | 2/2 (0 calls) | 0 | 8 |' in text
        assert 'not independent native trials' in text
        assert 'no intrinsic algorithm or quality advantage' in text
    assert (reports[0] / 'selection.json').read_bytes() == (reports[1] / 'selection.json').read_bytes()
    assert data.snapshot() == before


def test_component_unavailable_decision_stays_null_and_is_not_scored_as_failure(tmp_path):
    data = Dataset(tmp_path / 'data')
    value = component_pair()
    value['rows'][1]['native'] = {'available': False, 'correct': None}
    value['alignment']['missing_ids'] = ['verify-002']
    value['comparison_eligible'] = False
    data.append('component_native_pair', value)
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    analysis = json.loads((output / 'analysis.json').read_text())
    batch = analysis['component_native_batches'][0]
    assert batch['selected_scores']['native'] == {'correct': 1, 'available': 1, 'unavailable': 1}
    assert batch['alignment']['missing_ids'] == ['verify-002']
    assert batch['comparison_eligible'] is False
    rows = [json.loads(line) for line in (output / 'all-results.jsonl').read_text().splitlines()]
    missing = next(row for row in rows if row['case_id'] == 'verify-002' and row['arm'] == 'native')
    assert missing['correct'] is None


def test_failed_native_attempt_without_usage_remains_unavailable(tmp_path):
    data = Dataset(tmp_path / 'data')
    data.append('native_trial', {'rows': [{'case_id': 'failed-batch', 'arm': 'native-skills',
        'status': 'failed', 'correct': None, 'model_calls': None,
        'comparison_eligible': False, 'ledger_model_call_attempts': 4}]})
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    rows = [json.loads(line) for line in (output / 'all-results.jsonl').read_text().splitlines()]
    assert rows[0]['correct'] is None and rows[0]['model_calls'] is None
    assert rows[0]['ledger_model_call_attempts'] == 4
    assert 'failed-batch' in (output / 'report.md').read_text()
