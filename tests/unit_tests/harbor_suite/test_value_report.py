import copy
import json

import pytest

from benchmarks.harbor_suite.value_data import Dataset
from benchmarks.harbor_suite.value_report import flatten, paired_gains, probe_improvements, render


def poc_pair(revision='before', *, impossible=False):
    common = {'valid_response': True, 'correct_usable_completion': False,
        'scientific_success': None, 'model_calls': 1,
        'usage': {'input_tokens': 100, 'output_tokens': 10},
        'baseline_accuracy': None, 'treatment_accuracy': None,
        'unsupported_claims': 0, 'supported_claims': 3, 'assessed_claims': 3,
        'claim_scope': 'same-rubric observable completion claims', 'stopped_phase': 'compiler'}
    native = copy.deepcopy(common)
    if not impossible:
        native.update(correct_usable_completion=True, scientific_success=True,
            model_calls=13, baseline_accuracy=.5, treatment_accuracy=1., stopped_phase=None)
    return {'case_id': 'impossible' if impossible else 'feasible', 'revision': revision,
        'comparison_eligible': True, 'comparison_scope': 'Full original E1 versus ordinary native skills',
        'task_sha256': 'a' * 64, 'arms': {'cc': common, 'native-skills': native},
        'evidence': {'original_refs': ['originals-retained']}, 'limitations': ['One development task.']}


def test_poc_flatten_separates_valid_impossibility_from_useful_completion(tmp_path):
    data = Dataset(tmp_path / 'data')
    data.append('poc_comparison', poc_pair(impossible=True))
    rows = flatten(data.records())
    assert len(rows) == 2 and all(row['valid_response'] is True for row in rows)
    assert all(row['correct'] is False and row['scientific_success'] is None for row in rows)
    assert all(row['cost_usd'] is None for row in rows)
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    text = (output / 'report.md').read_text('utf-8')
    assert 'Correct impossibility handling is not PoC success' in text
    assert 'Unsupported / assessed claims' in text and '0/3' in text
    assert 'Explicit estimated cost scenario' not in text


def test_poc_report_retains_failed_revision_native_win_and_pending_repair(tmp_path):
    data = Dataset(tmp_path / 'data')
    failed = data.append('poc_comparison', poc_pair('fair03-before'))
    pending = poc_pair('repaired-rerun-pending')
    pending['comparison_eligible'] = False
    pending['arms'] = {'cc': {'stopped_phase': 'not_run'}, 'native-skills': {}}
    data.append('poc_comparison', pending)
    data.append('poc_comparison', dict(poc_pair('setup-visibility-excluded'), comparison_eligible=False))
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    analysis = json.loads((output / 'analysis.json').read_text())
    assert len(analysis['poc_comparisons']) == 3
    text = (output / 'report.md').read_text('utf-8')
    assert 'fair03-before' in text and 'repaired-rerun-pending' in text
    assert text.count('This eligible revision shows a useful-completion advantage for native') == 1
    rows = [json.loads(line) for line in (output / 'all-results.jsonl').read_text().splitlines()]
    assert len(rows) == 6
    assert next(r for r in rows if r['revision'] == 'repaired-rerun-pending' and r['arm'] == 'cc')['correct'] is None
    selected = tmp_path / 'selected'
    render(data.root, selected, selected_records=[failed['id']], charts=False)
    assert len((selected / 'all-results.jsonl').read_text().splitlines()) == 6
    selection = json.loads((selected / 'selection.json').read_text())
    assert selection['selected_rows'] == 2 and selection['all_outcomes_retained'] is True


def test_poc_estimated_cost_requires_explicit_scenario_and_provenance(tmp_path):
    data = Dataset(tmp_path / 'data')
    value = poc_pair()
    value['estimated_cost'] = {'scenario': 'Chosen Standard tariff with observed cache',
        'provenance': 'original trace cache-cost-audit.json', 'cc_usd': .1, 'native_usd': .2,
        'actual_bill': False}
    data.append('poc_comparison', value)
    render(data.root, tmp_path / 'explicit', charts=False)
    text = (tmp_path / 'explicit/report.md').read_text('utf-8')
    assert 'Explicit estimated cost scenario (not an actual bill)' in text
    assert 'original trace cache-cost-audit.json' in text
    second = Dataset(tmp_path / 'other')
    value['estimated_cost'].pop('provenance')
    second.append('poc_comparison', value)
    render(second.root, tmp_path / 'no-provenance', charts=False)
    assert 'Explicit estimated cost scenario' not in (tmp_path / 'no-provenance/report.md').read_text('utf-8')


def test_poc_missing_arm_fields_and_claim_denominators_stay_unavailable(tmp_path):
    data = Dataset(tmp_path / 'data')
    value = poc_pair()
    value['arms']['cc'] = {'valid_response': None, 'unsupported_claims': 0,
        'claim_scope': 'Only compiler source-attribution subset'}
    data.append('poc_comparison', value)
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    rows = [json.loads(line) for line in (output / 'all-results.jsonl').read_text().splitlines()]
    cc = next(row for row in rows if row['arm'] == 'cc')
    assert cc['correct'] is None and cc['model_calls'] is None and cc['usage'] is None
    text = (output / 'report.md').read_text('utf-8')
    assert 'Only compiler source-attribution subset' in text
    assert 'Different scopes or rubric subsets are not a shared denominator' in text
    assert '0/unavailable' not in text


def test_poc_honest_scientific_failure_can_be_useful_completion(tmp_path):
    data = Dataset(tmp_path / 'data')
    value = poc_pair()
    value['arms']['native-skills'].update(scientific_success=False,
        baseline_accuracy=.5, treatment_accuracy=.5)
    data.append('poc_comparison', value)
    native = next(row for row in flatten(data.records()) if row['arm'] == 'native-skills')
    assert native['correct'] is True and native['scientific_success'] is False
    render(data.root, tmp_path / 'report', charts=False)
    text = (tmp_path / 'report/report.md').read_text('utf-8')
    assert 'A scientific FAIL can be a useful completed study' in text
    assert 'does not imply a Harbor suite run' in text


def cost_scenario():
    return {'case_id': 'paper-injection', 'scope': 'Auxiliary paper workflow',
        'scenario': 'Chosen Standard tariff, short-context observed cached counts',
        'provenance': {'original_cache_audit_sha256': 'a' * 64},
        'not_actual_bill': True, 'comparison_eligible': True, 'quality_comparable': True,
        'quality_scope': 'Bounded content correctness tie; not main PoC success',
        'validation': {'full_call_populations_verified': True,
            'observed_cached_usage_complete': True, 'model_effort_match': True},
        'arms': {'cc': {'trial_id': 'original-cc', 'model_calls': 10,
                       'quality_correct': True, 'estimated_cost_usd': .6794988},
                 'native-skills': {'trial_id': 'original-native', 'model_calls': 10,
                       'quality_correct': True, 'estimated_cost_usd': .8874612}}}


def test_cost_scenario_selectable_rows_preserve_actual_unknown_and_no_new_trials(tmp_path):
    data = Dataset(tmp_path / 'data')
    cost = data.append('cost_scenario', cost_scenario())
    data.append('poc_comparison', poc_pair())
    rows = flatten(data.records())
    estimates = [r for r in rows if r['record_kind'] == 'cost_scenario']
    assert len(estimates) == 2
    assert all(r['correct'] is None and r['cost_usd'] is None and r['model_calls'] is None for r in estimates)
    assert all(r['new_trials'] == r['new_model_calls'] == 0 for r in estimates)
    output = tmp_path / 'selected'
    render(data.root, output, selected_records=[cost['id']], charts=False)
    analysis = json.loads((output / 'analysis.json').read_text())
    assert analysis['selected_rows'] == 2 and analysis['full_rows'] == 4
    scenario = analysis['estimated_cost_scenarios'][0]
    assert scenario['cc_reduction_percent'] == pytest.approx(23.4334075676)
    assert scenario['actual_cost_usd'] is None and scenario['actual_service_tier'] is None
    text = (output / 'report.md').read_text('utf-8')
    assert '23.433%' in text and '0.67949880' in text and '0.88746120' in text
    assert 'Auxiliary paper workflow' in text
    assert 'not actual service-tier observations' in text
    assert 'original-cc' in (output / 'estimated-cost-scenarios.csv').read_text('utf-8-sig')
    selection = json.loads((output / 'selection.json').read_text())
    assert len(selection['selected_row_ids']) == 2


@pytest.mark.parametrize('mutation', ['missing_cache', 'missing_cost', 'unproven', 'bool_cost'])
def test_cost_scenario_missing_unvalidated_numbers_remain_unavailable(tmp_path, mutation):
    data = Dataset(tmp_path / 'data')
    value = cost_scenario()
    if mutation == 'missing_cache': value['validation']['observed_cached_usage_complete'] = False
    elif mutation == 'missing_cost': value['arms']['cc'].pop('estimated_cost_usd')
    elif mutation == 'unproven': value.pop('provenance')
    else: value['arms']['cc']['estimated_cost_usd'] = True
    data.append('cost_scenario', value)
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    scenario = json.loads((output / 'analysis.json').read_text())['estimated_cost_scenarios'][0]
    assert scenario['estimate_validated'] is False
    assert scenario['costs_usd'] == {'cc': None, 'native-skills': None}
    assert scenario['cc_reduction_percent'] is None
    assert '23.433%' not in (output / 'report.md').read_text('utf-8')


def test_cheap_failed_cost_scenario_never_reports_successful_efficiency_gain(tmp_path):
    data = Dataset(tmp_path / 'data')
    value = cost_scenario()
    value['case_id'] = 'failed-main-poc'
    value['scope'] = 'Main PoC failed compiler versus useful completion'
    value['arms']['cc'].update(quality_correct=False, estimated_cost_usd=.01)
    value['quality_comparable'] = False
    value['quality_scope'] = 'CC failed; native useful completion'
    data.append('cost_scenario', value)
    render(data.root, tmp_path / 'report', charts=False)
    scenario = json.loads((tmp_path / 'report/analysis.json').read_text())['estimated_cost_scenarios'][0]
    assert scenario['estimate_validated'] is True and scenario['costs_usd']['cc'] == .01
    assert scenario['cc_reduction_percent'] is None
    text = (tmp_path / 'report/report.md').read_text('utf-8')
    assert 'Cheaper failed work is not a value win' in text


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


def test_primary_token_tradeoffs_keep_increases_and_missing_values(tmp_path):
    data = Dataset(tmp_path / 'data')
    for ident, native_input, cc_input, eligible in [('reduced', 100, 60, True),
            ('increased', 100, 120, True), ('missing', None, 60, True), ('mismatch', 100, 60, False)]:
        data.append('native_cc_pair', {'case_id': ident, 'task_sha256': 'a' * 64,
            'comparison_eligible': eligible, 'arms': {
                'native-skills': {'correct': True, 'model_calls': 2, 'usage': {'input_tokens': native_input, 'output_tokens': 10}},
                'cc': {'correct': True, 'model_calls': 2, 'usage': {'input_tokens': cc_input, 'output_tokens': 20}}}})
    output = tmp_path / 'report'
    render(data.root, output, charts=False)
    text = (output / 'report.md').read_text()
    assert '| reduced | 100 | 60 | 40.0% | 10 | 20 |' in text
    assert '| increased | 100 | 120 | -20.0% | 10 | 20 |' in text
    assert '| missing | None | 60 | unavailable | 10 | 20 |' in text
    assert '| mismatch | 100 | 60 | unavailable | 10 | 20 |' in text
    assert 'do not establish lower cost' in text
