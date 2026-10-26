import copy

import pytest

from benchmarks.harbor_suite.value_data import Dataset
from benchmarks.harbor_suite.value_report import paired_gains, probe_improvements, render


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
