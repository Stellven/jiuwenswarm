"""Real component/factories with scripted callbacks, never model-quality results."""
import asyncio
import copy
import json
import os
from pathlib import Path

import pytest

from benchmarks.harbor_suite.value_semantic import freeze, freeze_core, load, run, grade, referee_index, SCOPE
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.gate import assemble_assessment
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.fixture
def frozen(tmp_path):
    root = tmp_path / 'frozen'
    freeze(root)
    return root


def reply(case):
    labels = case['private']['labels']
    return {'findings': [{'criterion_id': criterion['criterion_id'],
             'outcome': labels.get(criterion['criterion_id'], ['PASS'])[0],
             'reason': 'Scripted test finding for visible criterion ' + criterion['criterion_id']}
            for criterion in case['public']['criteria']],
            'uncertainties': [], 'limitations': [],
            'required_correction': 'Correct the visible defect.' if case['private']['kind'] == 'fault' else None}


def test_exact_factories_four_profiles_partial_independent_labels_and_no_admission(frozen):
    cases = load(frozen)
    assert len(cases) == 8 and len({case['profile_ref']['sha256'] for case in cases}) == 4
    assert len({case['declaration_ref']['sha256'] for case in cases}) == 4
    manifest = json.loads((frozen / 'manifest.json').read_text('utf-8'))
    assert not manifest['library_admission_performed'] and not manifest['service_started']
    assert manifest['model_calls'] == 0 and manifest['scope'] == SCOPE
    store = SQLiteRunStore(frozen / 'isolated-store')
    try:
        for case in cases:
            profile = store.read_record(case['profile_ref'])
            assert profile == case['public']['profile'] and profile['model_call_limit'] == 1
            assert store.read_blob(case['instruction_ref']).decode() in case['public']['system']
            assert 'labels' not in case['public'] and 'rationale' not in case['public']
            port = next(row for row in case['public']['declaration']['ports']['outputs'] if row['name'] == case['port'])
            if case['id'] == 'planner-missing-shape':
                with pytest.raises(ResearchError):
                    validate(port['schema_ref'], case['public']['subject_output'])
            else:
                validate(port['schema_ref'], case['public']['subject_output'])
    finally:
        store.close()


def test_actual_semantic_verifier_review_assembly_and_retained_callback_metadata(frozen, tmp_path):
    cases = load(frozen); index = {case['public']['payload']['subject_output']: case for case in cases}
    calls = []
    async def callback(prompt, *, system):
        payload = json.loads(prompt); case = index[payload['subject_output']]
        assert system == case['public']['system']
        calls.append(case['id'])
        return {'text': json.dumps(reply(case)), 'test_only_scripted': True, 'provider_model_calls': 0}
    result = asyncio.run(run(frozen, callback, output=tmp_path / 'observed'))
    assert len(calls) == len(set(calls)) == 8
    assert all(row['status'] == 'observed' for row in result['rows'])
    assert all(row['grade']['labeled_criteria_correct'] for row in result['rows'])
    assert all(row['protected_gate_result'] == 'not_run' for row in result['rows'])
    clean = next(row for row in result['rows'] if row['id'] == 'evaluation-consistent-inconclusive')
    assert clean['assessment']['verdict'] == 'PASS'
    raw = json.loads((tmp_path / 'observed' / clean['id'] / 'raw-response.json').read_text('utf-8'))
    assert raw['result']['test_only_scripted'] and raw['result']['provider_model_calls'] == 0


def test_false_positive_and_missed_fault_fail_independent_label_grade(frozen):
    cases = load(frozen)
    for case_id, criterion, wrong in [('utility-visible-count', 'internal_consistency', 'FAIL'),
                                     ('evaluation-contradiction', 'classification_consistent_with_findings', 'PASS')]:
        case = next(row for row in cases if row['id'] == case_id)
        body = reply(case)
        for finding in body['findings']:
            if finding['criterion_id'] == criterion:
                finding['outcome'] = wrong
        # The grade is independent of model reasons or final assembled verdict.
        assert not grade(case, body)['labeled_criteria_correct']


def test_malformed_reply_retained_as_invalid_response_without_retry(frozen, tmp_path):
    calls = []
    async def callback(prompt, *, system):
        calls.append(prompt)
        return '{broken'
    result = asyncio.run(run(frozen, callback, case_ids=['utility-visible-count'], output=tmp_path / 'invalid'))
    assert len(calls) == 1 and result['rows'][0]['status'] == 'invalid_response'
    assert result['rows'][0]['grade']['response_valid'] is False
    assert (tmp_path / 'invalid' / 'utility-visible-count' / 'raw-response.json').exists()


def test_callback_failure_retained_unavailable_and_never_retried(frozen, tmp_path):
    async def callback(prompt, *, system):
        raise TimeoutError('scripted transport failure')
    result = asyncio.run(run(frozen, callback, case_ids=['utility-visible-count'], output=tmp_path / 'failed'))
    assert result['rows'][0]['status'] == 'unavailable' and result['rows'][0]['callback_invocations'] == 1
    assert result['rows'][0]['model_calls'] is None


def test_missing_duplicate_findings_rejected_by_actual_assembler(frozen, tmp_path):
    case = load(frozen)[0]
    async def callback(prompt, *, system):
        body = reply(case); body['findings'][-1] = copy.deepcopy(body['findings'][0])
        return json.dumps(body)
    result = asyncio.run(run(frozen, callback, case_ids=[case['id']], output=tmp_path / 'duplicate'))
    assert result['rows'][0]['status'] == 'invalid_response'
    assert 'criterion_coverage_exact' in result['rows'][0]['error']


def test_frozen_mutation_and_duplicate_destination_fail(frozen):
    with pytest.raises(FileExistsError):
        freeze(frozen)
    path = next((frozen / 'public').glob('*.json'))
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        load(frozen)


def test_narrow_core_bank_uses_actual_original_planner_and_same_verifier(tmp_path):
    archive = os.environ.get('AI4R_TEST_CORE_PLANNER_ARCHIVE')
    if not archive:
        pytest.skip('Provide an actual retained E1 originals.zip with AI4R_TEST_CORE_PLANNER_ARCHIVE')
    root = tmp_path / 'core'
    rows = freeze_core(root, planner_archive=archive)
    cases = load(root)
    assert len(cases) == 4
    assert {case['public']['declaration']['identity']['name'] for case in cases} == {'research.evaluation', 'research.planner'}
    assert all('workflow.paper_planner' != case['public']['declaration']['identity']['name'] for case in cases)
    original, altered = cases[2]['public']['subject_output'], cases[3]['public']['subject_output']
    validate('plan-proposal', original); validate('plan-proposal', altered)
    copied = copy.deepcopy(altered)
    copied['nodes'][0]['predecessors'] = original['nodes'][0]['predecessors']
    assert copied == original
    assert altered['nodes'][0]['node_id'] in altered['nodes'][1]['predecessors']
    assert altered['nodes'][1]['node_id'] in altered['nodes'][0]['predecessors']
    manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
    assert manifest['core_PRD_subjects_only']
    assert manifest['original_planner_source']['output_sha256'] == cases[2]['output_ref']['sha256']
    assert (root / 'cases.md').is_file()
    assert all((root / 'public' / (case['id'] + '.prompt.txt')).is_file() for case in cases)
    index = {case['public']['payload']['subject_output']: case for case in cases}
    async def callback(prompt, *, system):
        case = index[json.loads(prompt)['subject_output']]
        assert system == case['public']['system']
        return {'text': json.dumps(reply(case)), 'test_only_scripted': True, 'provider_model_calls': 0}
    with pytest.raises(ValueError, match='exactly one'):
        asyncio.run(run(root, callback, output=tmp_path / 'refused-batch'))
    observed = []
    for ordinal, case in enumerate(cases):
        result = asyncio.run(run(root, callback, case_ids=[case['id']], output=tmp_path / ('scripted-core-' + str(ordinal))))
        observed.extend(result['rows'])
    assert len(observed) == 4
    assert all(row['status'] == 'observed' and row['grade']['labeled_criteria_correct'] for row in observed)
    assert observed[2]['assessment']['verdict'] == 'PASS'
    assert observed[3]['assessment']['verdict'] == 'FAIL'
    before = referee_index(root)
    assert all(card['actual']['status'] == 'not_run' for card in before['cases'])
    after = referee_index(root, actual_directory=tmp_path / 'scripted-core-0')
    assert sum(card['actual']['status'] == 'observed' for card in after['cases']) == 1
    assert all(Path(card['system_instruction_file']).is_file() for card in after['cases'])
    assert all(card['expected_criterion_labels'] for card in after['cases'])
    assert (root / 'private/referee-index.json').is_file()
