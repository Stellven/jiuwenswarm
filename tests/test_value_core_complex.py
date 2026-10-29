"""Hard production-contract Brief fixtures; no model calls or fake admission."""
import asyncio
import copy
import inspect
import importlib.util
import hashlib
import json
from types import SimpleNamespace

import pytest

from benchmarks.harbor_suite.value_core_complex import freeze, load, grade, production_check
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.fixture
def bank(tmp_path):
    root = tmp_path / 'bank'; freeze(root)
    return root


def valid_brief(case):
    """Test-only independent authored response; never exported to public inputs."""
    public = case['public']; intent = public['inputs']['intent']; refs = public['input_refs']
    source = [refs['intent']]
    def requirement(identifier, text):
        return {'id': identifier, 'text': text, 'origin': 'user', 'source_refs': source}
    constraints = [{'id': row['id'], 'text': row['text'], 'category': row['category'], 'origin': 'user',
        'source_refs': source, 'scope': 'scientific_execution', 'normalized_value': None, 'unit': None, 'operator': 'qualitative'} for row in intent['constraints']]
    mandatory = [requirement('req-' + row['id'], row['text']) for row in intent['constraints']]
    mandatory += [requirement('req-' + row['id'], row['metric'] + ': ' + row['target_text']) for row in intent['user_targets']]
    equations = {'t-accuracy': ('ge', 'baseline', 1, 5, 'percentage points'),
                 't-latency': ('le', 'baseline', 0.95, 0, 'ms'),
                 't-cap': ('lt', 'constant', 0, 120, 'ms'),
                 't-conflict': ('ge', 'baseline', 1, 7, 'percentage points')}
    targets = []
    for item in intent['user_targets']:
        comparator, reference, factor, offset, unit = equations[item['id']]
        targets.append({'id': item['id'], 'metric': item['metric'], 'target_text': item['target_text'],
            'origin': 'user', 'source_refs': source, 'requirement_ids': ['req-' + item['id']],
            'unit': unit, 'comparison_status': 'quantitative', 'comparison': {
                'comparator': comparator, 'reference': reference, 'factor': factor, 'offset': offset}})
    brief = {'schema_version': '3.0.0', 'intent_ref': refs['intent'], 'intake_ref': refs['intake'],
        'objective': requirement('objective-main', 'Compare the requested sensor decision-cutoff intervention under unchanged scientific acceptance rules.'),
        'in_scope': [requirement(row['id'], row['text']) for row in intent['in_scope']],
        'out_of_scope': [requirement(row['id'], row['text']) for row in intent['out_of_scope']],
        'mandatory_requirements': mandatory,
        'optional_preferences': [requirement(row['id'], row['text']) for row in intent['preferences']],
        'constraints': constraints, 'target_metrics': targets,
        'deliverables': [{'id': 'd-report', 'name': 'research_report.md', 'description': 'Comparison report with sources and limitations', 'artifact_type': 'research_report'},
                         {'id': 'd-data', 'name': 'comparisons.csv', 'description': 'Baseline/treatment values, units and decisions', 'artifact_type': 'comparison_table'}],
        'acceptance_expectations': [{'id': 'accept-' + row['id'], 'requirement_ids': [row['id']], 'description': 'Assess compliance with ' + row['text']} for row in mandatory],
        'evidence_obligations': [{'id': 'evidence-' + row['id'], 'requirement_ids': [row['id']], 'description': 'Retain original evidence for ' + row['text']} for row in mandatory],
        'assumptions': [], 'unresolved_items': copy.deepcopy(intent['uncertainties']),
        'resource_refs': list(case['resources'].values()),
        'confirmation': {'basis': 'user_request', 'source_refs': [intent['request_ref']]},
        'context_refs': intent['context_refs'], 'domain_lane': 'scientific_research',
        'input_bindings': [{'id': 'binding-data', 'role': 'validation_data', 'resource_ref': case['resources']['dataset.json']},
                           {'id': 'binding-project', 'role': 'project_asset', 'resource_ref': case['resources']['weights.json']}]}
    return brief


@pytest.mark.parametrize('ordinal', range(4))
def test_valid_full_contract_and_real_checks_with_independent_productivity_grade(bank, ordinal):
    case = load(bank)[ordinal]; brief = valid_brief(case)
    store = SQLiteRunStore(bank / 'fixture-store')
    try:
        assert production_check(case, brief, store)['passed']
    finally: store.close()
    result = grade(case, brief)
    assert result['content_correct'], [item for item in result['checks'] if not item['passed']]
    assert result['correct_usable_completion'] is (ordinal != 2)
    assert result['honest_qualified_output'] is (ordinal == 2)
    assert result['invalid_output_promoted'] is None


def test_schema_valid_silent_threshold_and_unit_faults_escape_structure_but_fail_oracle(bank):
    case = load(bank)[0]; good = valid_brief(case); store = SQLiteRunStore(bank / 'fixture-store')
    try:
        for mutation in ('relative-instead-of-pp', 'fraction-wrong-offset', 'non-strict-cap'):
            wrong = copy.deepcopy(good)
            if mutation == 'relative-instead-of-pp':
                wrong['target_metrics'][0]['comparison'].update(factor=1.05, offset=0)
            elif mutation == 'fraction-wrong-offset': wrong['target_metrics'][0]['unit'] = 'fraction'
            else: wrong['target_metrics'][2]['comparison']['comparator'] = 'le'
            assert production_check(case, wrong, store)['passed']  # Actual check validates form, not original equation fidelity.
            result = grade(case, wrong, protected_accepted=True)
            assert not result['content_correct'] and result['invalid_output_promoted']
            assert not result['correct_usable_completion']
    finally: store.close()


def test_dropped_constraint_and_missing_mandatory_evidence_are_not_completion(bank):
    case = load(bank)[0]; good = valid_brief(case); store = SQLiteRunStore(bank / 'fixture-store')
    try:
        dropped = copy.deepcopy(good); dropped['constraints'] = [row for row in dropped['constraints'] if row['id'] != 'c-no-effects']
        assert not production_check(case, dropped, store)['passed']
        assert not grade(case, dropped)['content_correct']
        missing = copy.deepcopy(good); missing['evidence_obligations'].pop()
        assert not production_check(case, missing, store)['passed']
        assert not grade(case, missing)['content_correct']
        # Merely detecting/rejecting either fault earns no usable-completion credit.
        assert not grade(case, missing, protected_accepted=False)['correct_usable_completion']
    finally: store.close()


def test_wrong_qualified_unicode_source_fails_independent_attribution(bank):
    case = load(bank)[1]; good = valid_brief(case); wrong = copy.deepcopy(good)
    wrong['constraints'][0]['source_refs'] = [case['oracle']['forbidden_cutoff_source_ref']]
    store = SQLiteRunStore(bank / 'fixture-store')
    try: assert production_check(case, wrong, store)['passed']  # Qualified does not imply the right source supports it.
    finally: store.close()
    assert not grade(case, wrong)['content_correct']
    intent = case['public']['inputs']['intent']; source_by_ref = {json.dumps(row['ref'], sort_keys=True): row['text'] for row in case['public']['source_texts']}
    span = intent['constraints'][0]['source_spans'][0]
    text = source_by_ref[json.dumps(span['source_ref'], sort_keys=True)]
    assert '0.55' in text[span['start']:span['end']]
    assert len(text.encode()) != len(text)


def test_valid_paraphrase_equivalent_units_and_legitimate_conflict_accepted(bank):
    case = load(bank)[0]; brief = valid_brief(case)
    brief['constraints'][0]['text'] = 'Adjust the intervention cutoff 0.6 to 0.55 while retaining the separate scientific success rule.'
    brief['target_metrics'][0]['unit'] = 'fraction'; brief['target_metrics'][0]['comparison']['offset'] = 0.05
    brief['target_metrics'][2]['unit'] = 'seconds'; brief['target_metrics'][2]['comparison']['offset'] = 0.12
    assert grade(case, brief)['correct_usable_completion']
    assert grade(case, brief, protected_accepted=False)['false_rejection']
    conflict = load(bank)[2]
    assert grade(conflict, valid_brief(conflict))['honest_qualified_output']
    wrong = valid_brief(conflict); wrong['unresolved_items'] = []
    assert not grade(conflict, wrong)['content_correct']


def test_no_shared_production_oracle_or_invented_acceptance_or_trial(bank):
    assert 'production_check' not in inspect.getsource(grade)
    assert 'check_brief' not in inspect.getsource(grade)
    manifest = json.loads((bank / 'manifest.json').read_text('utf-8'))
    assert manifest['model_calls'] == manifest['new_measured_trials'] == 0
    assert not any(row['full_node_execution_ready'] for row in manifest['cases'])
    for case in load(bank):
        assert 'NOT a committed accepted output or E3 admission' in case['public']['input_status']
        assert 'oracle' not in case['public']


def test_real_requirements_worker_with_scripted_reply_is_not_a_measured_node(bank):
    from jiuwenswarm.research.capsules.requirements import execute
    case = load(bank)[0]; brief = valid_brief(case); store = SQLiteRunStore(bank / 'fixture-store'); observed = []
    async def scripted_model(prompt, *, system):
        observed.append(json.loads(prompt))
        assert 'qualified_output_ref_allowlist' in observed[-1]
        assert 'Requirements Capsule' in system and 'schema' in system
        return json.dumps(brief)
    public = case['public']; refs = public['input_refs']
    ctx = SimpleNamespace(store=store, contract={'inputs': [], 'outputs': [{'name': 'brief',
        'contract_id': 'urn:jiuwenswarm:m1-design:research-brief:3.0.0', 'version': '3.0.0'}]},
        input_ref=lambda key: refs[key], read_blob=store.read_blob, model=scripted_model)
    try:
        produced = asyncio.run(execute(ctx, public['inputs']))
        assert json.loads(produced['brief'].data) == brief
        assert len(observed) == 1
    finally: store.close()


@pytest.mark.parametrize('identifier,text', [
    ('c-cutoff', 'Change the intervention cutoff from 0.55 to 0.60; keep the scientific success rule separate.'),
    ('c-no-effects', 'Use network access, download data, retrain weights, invent measurements, add experiments and retry failed scientific runs.'),
    ('c-success', 'Keep the scientific accuracy success rule fixed: treatment must be at least 15 percentage points above baseline accuracy.'),
    ('c-budget', 'Keep scientific wall time at most 120 minutes and CPU memory at most 1512 MiB; preserve all mandatory acceptance requirements.')])
def test_schema_valid_direction_negation_and_numeric_substring_faults_are_rejected(bank, identifier, text):
    case = load(bank)[0]; wrong = valid_brief(case)
    next(item for item in wrong['constraints'] if item['id'] == identifier)['text'] = text
    store = SQLiteRunStore(bank / 'fixture-store')
    try: assert production_check(case, wrong, store)['passed']
    finally: store.close()
    assert grade(case, wrong)['content_correct'] is False


def test_mandatory_demoted_to_optional_and_optional_evidence_are_rejected(bank):
    case = load(bank)[0]; wrong = valid_brief(case); identifier = 'req-c-no-effects'
    removed = next(item for item in wrong['mandatory_requirements'] if item['id'] == identifier)
    wrong['mandatory_requirements'] = [item for item in wrong['mandatory_requirements'] if item['id'] != identifier]
    wrong['optional_preferences'].append(removed)
    for field in ('acceptance_expectations', 'evidence_obligations'):
        wrong[field] = [item for item in wrong[field] if identifier not in item['requirement_ids']]
    store = SQLiteRunStore(bank / 'fixture-store')
    try: assert production_check(case, wrong, store)['passed']
    finally: store.close()
    assert grade(case, wrong)['content_correct'] is False
    optional = valid_brief(case); optional['evidence_obligations'][0]['description'] = 'Evidence is optional for this mandatory requirement.'
    assert grade(case, optional)['content_correct'] is False


def test_valid_restriction_paraphrase_and_unknown_entailment_are_distinct(bank):
    case = load(bank)[0]; brief = valid_brief(case)
    next(item for item in brief['constraints'] if item['id'] == 'c-no-effects')['text'] = 'No network access, data downloads, retraining, fabricated measurements, extra experiments, or retries are permitted.'
    assert grade(case, brief)['correct_usable_completion']
    next(item for item in brief['constraints'] if item['id'] == 'c-no-effects')['text'] = 'Respect the agreed operational boundaries.'
    result = grade(case, brief, protected_accepted=True)
    assert result['content_correct'] is None and result['manual_review_required']
    assert not result['correct_usable_completion'] and result['invalid_output_promoted'] is None


def test_frozen_grader_and_private_oracle_pins_preserve_history(bank):
    manifest = json.loads((bank / 'manifest.json').read_text('utf-8'))
    archived = bank / 'private/grader-source.py'
    assert hashlib.sha256(archived.read_bytes()).hexdigest() == manifest['grader_source_sha256']
    case = load(bank)[0]
    spec = importlib.util.spec_from_file_location('archived_core_complex_grader', archived)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.grade(case, valid_brief(case))['correct_usable_completion']
    private_path = bank / 'private' / (case['id'] + '.json')
    private_path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='oracle changed'):
        load(bank)
