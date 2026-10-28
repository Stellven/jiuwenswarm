"""Synthetic transport/capture controls only; no model or RSI qualification."""
import asyncio
import copy
import json

import pytest

from jiuwenswarm.research_rsi.diagnosis import BoundedDiagnosis
from jiuwenswarm.research_rsi.opportunity import (
    produce_opportunity, validated_preparation, validate_opportunity)
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_records.contracts import ContractData


@pytest.fixture
def prepared(tmp_path, request):
    store = RecordStore(tmp_path / 'records')
    unit = store.put({'controlled_fixture': 'synthetic; never operational evidence'})
    kind = getattr(request, 'param', 'ranking-v1')
    path, name = 'ranking.py', 'research.screening'
    source = b'def rank_opportunities(rows): return {}\n'
    if kind == 'normalize-labels-v1':
        from jiuwenswarm.research_rsi.targets.unrelated_helper import NORMALIZE_LABELS_PARENT
        source, path, name = NORMALIZE_LABELS_PARENT, 'normalize.py', 'utility.normalize'
    body = store.put_bytes(source)
    declaration = {'identity': {'name': name, 'version_label': 'unit',
        'body': [{'path': path, 'sha256': body['sha256']}]},
        'evolution': {'rsi': 'propose', 'may_change': ['files:' + path]}}
    declaration_ref = store.put(declaration)
    parent = {'cc_name': name, 'cc_version': 'unit',
        'declaration_sha256': declaration_ref['sha256']}
    target = {'schema_version': '1.0.0', 'id': 'unit_target', 'parent_ref': body,
        'parent_declaration_ref': declaration_ref, 'frozen_contract_ref': unit,
        'required_test_refs': [unit], 'mutable_paths': [path],
        'protected_refs': [store.put({'protected': 'must not disclose'})],
        'splits': dict(development='dev', hidden_loop='loop', hidden_final='final', platform='platform'),
        'scoring': dict(primary='passed_test_count', secondary='paired_time_at_equal_counts',
            warmup_batches=5, paired_rounds=7, min_relative_gain=.1, noise_multiplier=3,
            batch_iterations=1000, calibrated_relative_noise=.02),
        'calibration_ref': unit, 'session_query_limit': 30, 'lifetime_query_limit': 90,
        'limits': dict(time_s=600, model_calls=5, memory_mb=512),
        'scoring_adapter_ref': unit, 'improver_ref': unit, 'configuration_ref': unit}
    profile_ref = store.put(target)
    worker = dict(schema='ai4r-rsi-worker-profile:1' if kind == 'ranking-v1' else 'ai4r-rsi-worker-profile:2', target_kind=kind,
        session_ref=unit, target_ref=profile_ref, parent_ref=body,
        contract_ref=store.put({'controlled': 'worker invocation contract differs from interface'}),
        environment_ref=unit, hardware_ref=unit, memory_mb=64, pids_max=16, timeout_s=10)
    worker_ref = store.put(worker)
    approved = [unit]
    def measurement(expected, actual, *, candidate=None, duration=1., stamp=0):
        candidate = candidate or body
        inputs = store.put({'labels': [' Example ', 'EXAMPLE', str(stamp)]} if kind == 'normalize-labels-v1'
            else {'scores': [{'idea_id': str(stamp), 'novelty': 3,
                'feasibility': 4, 'compute_alignment': 5, 'eligible': True}]})
        expected_ref = store.put(expected)
        output = store.put(actual)
        request = dict(profile_ref=worker_ref, session_ref=unit, candidate_ref=candidate,
            input_ref=inputs, reservation_ref=unit, phase='development', repeat_index=0)
        receipt = dict(subject_ref=candidate, contract_ref=worker['contract_ref'], hardware_ref=unit,
            observed_runtime=True, identity=dict(executor_uid=12003, executor_gid=12003),
            termination_reason='completed', exit_code=0, wall_time_s=duration,
            stdout_ref=output, started_at=f'2026-10-25T00:{stamp//60:02}:{stamp%60:02}Z',
            ended_at=f'2026-10-25T00:{stamp//60:02}:{stamp%60:02}Z')
        capture = store.put(dict(schema='ai4r-rsi-worker-receipt:1', request=request, receipt=receipt))
        approved.extend([inputs, expected_ref, output, capture])
        return dict(input_ref=inputs, expected_ref=expected_ref, capture_ref=capture)
    mandatory = measurement({'ok': True}, {'ok': True})
    development = measurement({'expected': True}, {'actual': False})
    prep = dict(schema='ai4r-rsi-opportunity-preparation:1', target_profile_ref=profile_ref,
        parent=parent, parent_ref=body, parent_declaration_ref=declaration_ref,
        configuration_ref=unit, worker_profile_ref=worker_ref, development_ref='dev',
        review_ref=unit, attribution='implementation', observed_symptom='Visible wrong ranking',
        headroom_minimum=.1, audience='rsi_diagnosis',
        evidence=[dict(ref=development['capture_ref'], summary='Synthetic visible mismatch')],
        mandatory_checks=[dict(test_ref=unit, **mandatory)], development_checks=[development], timing=None)
    review = dict(schema='ai4r-rsi-opportunity-review:1', target_profile_ref=profile_ref,
        parent=parent, configuration_ref=unit, worker_profile_ref=worker_ref,
        reviewer='independent-unit-reviewer', prepared_by='unit-author', headroom_minimum=.1,
        approved_evidence_refs=approved, approved_reference_refs=[])
    def repin():
        prep['review_ref'] = store.put(review)
        pin = store.put(prep)
        return dict(store=store, profile_ref=profile_ref, parent=parent,
            preparation_ref=pin, approved_preparation_refs=[pin])
    data = dict(kw=repin(), store=store, prep=prep, review=review, target=target,
        worker=worker, measurement=measurement, repin=repin)
    yield data
    store.close()


class DiagnosisTransportDouble:
    """Controlled observed evidence, explicitly not a real governed model."""
    def __init__(self, store, evidence, *, changes=None, raw=None):
        self.calls = 0
        self.last_evidence = [store.put({'controlled_generation': 'test double only'})]
        self.last_model_calls = 1
        self.last_generating_model = 'controlled-test-double'
        self.last_unavailable_reasons = ['Synthetic test double; usage not measured']
        self.evidence, self.changes, self.raw = evidence, changes or {}, raw
    async def __call__(self, prompt):
        self.calls += 1
        self.prompt = json.loads(prompt)
        return self.raw if self.raw is not None else json.dumps({
            'schema': 'ai4r-rsi-diagnosis:1', 'observed_symptom': 'Visible wrong ranking',
            'supporting_visible_evidence': [self.evidence], 'suspected_mechanism': 'Ordering logic',
            'alternative_causes': ['Fixture expectation error'], 'authorized_component': 'ranking.py',
            'proposed_change_direction': 'Preserve sum-three, ascending ID ties and Top-1',
            'expected_effect': 'Hypothesized matching output',
            'visible_falsification_checks': ['Recheck exact visible fixture'],
            'uncertainties': ['Synthetic test evidence only'], **self.changes})


def run(prepared, **changes):
    kw = dict(prepared['kw'])
    model = changes.pop('model', DiagnosisTransportDouble(prepared['store'], prepared['prep']['evidence'][0]['ref']))
    kw.update(opportunity_id='unit:opportunity', selected_by='unit-operator', model=model)
    kw.update(changes)
    return asyncio.run(produce_opportunity(**kw)), model


def test_canonical_producer_retains_exact_prompt_response_and_observed_provenance(prepared):
    result, model = run(prepared)
    record = result['record']
    assert record['decision'] == 'START' and model.calls == 1
    assert record['headroom'] == 1 and record['parent_mandatory_passed']
    ContractData().validate('rsi-opportunity', record)
    facts = validate_opportunity(**prepared['kw'], opportunity_ref=result['ref'])
    assert facts['headroom'] == 1
    capture = prepared['store'].get(result['diagnosis_capture_ref'])
    assert capture['generating_model'] == 'controlled-test-double'
    assert capture['generation_evidence_refs'] == model.last_evidence
    assert capture['unavailable_reasons'] == model.last_unavailable_reasons
    assert prepared['store'].get(capture['response_ref']) == prepared['store'].get(record['diagnosis_ref'])
    assert model.prompt['visible_evidence'] == prepared['prep']['evidence']
    assert 'hidden_final' not in json.dumps(model.prompt)


@pytest.mark.parametrize('mutation', ['unapproved', 'profile', 'audience', 'self_review', 'protected', 'missing_capture', 'wrong_parent', 'missing_test'])
def test_invalid_or_unapproved_evidence_blocks_before_any_model_call(prepared, mutation):
    if mutation == 'profile': prepared['prep']['target_profile_ref'] = prepared['target']['parent_ref']
    elif mutation == 'audience': prepared['prep']['audience'] = 'public'
    elif mutation == 'self_review': prepared['review']['reviewer'] = prepared['review']['prepared_by']
    elif mutation == 'protected': prepared['review']['approved_evidence_refs'].append(prepared['target']['protected_refs'][0])
    elif mutation == 'missing_capture': prepared['prep']['development_checks'][0]['capture_ref'] = dict(id='missing', sha256='a'*64)
    elif mutation == 'wrong_parent': prepared['prep']['parent']['cc_version'] = 'foreign'
    elif mutation == 'missing_test': prepared['prep']['mandatory_checks'] = []
    prepared['kw'] = prepared['repin']()
    extra = {'approved_preparation_refs': []} if mutation == 'unapproved' else {}
    result, model = run(prepared, **extra)
    assert result['record']['decision'] == 'NO_ATTEMPT' and result['readiness'] == 'BLOCKED'
    assert model.calls == 0
    ContractData().validate('rsi-opportunity', result['record'])


@pytest.mark.parametrize('changes', [
    {'authorized_component': 'protected.py'}, {'supporting_visible_evidence': []},
    {'supporting_visible_evidence': [{'id': 'foreign', 'sha256': 'a'*64}]},
    {'permission': 'granted'}, {'ready': True}, {'suspected_mechanism': ''}])
def test_diagnosis_cannot_supply_authority_or_cite_foreign_evidence(prepared, changes):
    model = DiagnosisTransportDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'], changes=changes)
    result, _ = run(prepared, model=model)
    assert result['record']['decision'] == 'NEEDS_REVIEW' and model.calls == 1
    capture = prepared['store'].get(result['diagnosis_capture_ref'])
    assert capture['status'] == 'invalid' and capture['response_ref'] is not None


@pytest.mark.parametrize('raw', ['{"schema":"a","schema":"b"}', '{"score":NaN}', 'not JSON', '```json\n{}\n```'])
def test_malformed_diagnosis_is_retained_without_retry(prepared, raw):
    model = DiagnosisTransportDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'], raw=raw)
    result, _ = run(prepared, model=model)
    assert result['record']['decision'] == 'NEEDS_REVIEW' and model.calls == 1
    capture = prepared['store'].get(result['diagnosis_capture_ref'])
    assert prepared['store'].read(capture['response_ref']) == raw.encode()


def test_no_reproduction_or_uncertain_attribution_never_requests_diagnosis(prepared):
    prepared['prep']['attribution'] = 'uncertain'
    prepared['kw'] = prepared['repin']()
    result, model = run(prepared)
    assert result['record']['decision'] == 'NEEDS_REVIEW' and model.calls == 0
    prepared['prep']['attribution'] = 'implementation'
    prepared['prep']['development_checks'] = [prepared['prep']['mandatory_checks'][0].copy()]
    del prepared['prep']['development_checks'][0]['test_ref']
    prepared['kw'] = prepared['repin']()
    result, model = run(prepared)
    assert result['record']['decision'] == 'NO_ATTEMPT' and model.calls == 0


def test_missing_generation_evidence_is_explicit_and_cannot_start(prepared):
    model = DiagnosisTransportDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'])
    model.last_evidence = []; model.last_model_calls = None; model.last_generating_model = None
    result, _ = run(prepared, model=model)
    assert result['record']['decision'] == 'NEEDS_REVIEW'
    capture = prepared['store'].get(result['diagnosis_capture_ref'])
    assert capture['model_calls'] is None and capture['generating_model'] is None
    assert any('unavailable' in reason.lower() for reason in capture['unavailable_reasons'])


def test_resources_block_with_valid_canonical_no_attempt(prepared):
    result, model = run(prepared, resource_ready=False)
    assert result['readiness'] == 'BLOCKED' and result['record']['decision'] == 'NO_ATTEMPT'
    assert model.calls == 0


def test_diagnosis_object_is_once_only(prepared):
    model = DiagnosisTransportDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'])
    runner = BoundedDiagnosis(model, store=prepared['store'])
    kw = dict(parent=prepared['kw']['parent'], profile_ref=prepared['kw']['profile_ref'],
        preparation_ref=prepared['kw']['preparation_ref'], configuration_ref=prepared['target']['configuration_ref'],
        authorized_component='ranking.py', observed_symptom='Unit symptom', evidence=prepared['prep']['evidence'])
    asyncio.run(runner.diagnose(**kw))
    with pytest.raises(ValueError, match='once-only'): asyncio.run(runner.diagnose(**kw))
    assert model.calls == 1


def timing_fixture(prepared):
    """Synthetic paired durations; no actual speed or qualification claim."""
    store, prep, review = prepared['store'], prepared['prep'], prepared['review']
    base = dict(prep['mandatory_checks'][0]); del base['test_ref']
    prep['development_checks'] = [base]
    reference = store.put_bytes(b'# Independently scoped synthetic reference body')
    review['approved_reference_refs'] = [reference]
    rounds = []
    for index in range(12):
        value = {}
        for side, candidate, duration in [('parent', prep['parent_ref'], 2.), ('reference', reference, 1.6)]:
            position = 0 if (side == 'parent') == (index % 2 == 0) else 1
            row = prepared['measurement']({'ok': True}, {'ok': True}, candidate=candidate,
                duration=duration, stamp=4 * index + position)
            capture = store.get(row['capture_ref'])
            capture['request']['input_ref'] = base['input_ref']
            row.update(input_ref=base['input_ref'], expected_ref=base['expected_ref'], capture_ref=store.put(capture))
            review['approved_evidence_refs'].append(row['capture_ref'])
            value[side + '_checks'] = [row]
        rounds.append(value)
    prep['timing'] = dict(reference_ref=reference, rounds=rounds)
    prepared['kw'] = prepared['repin']()


def test_visible_timing_headroom_uses_actual_quality_preserving_paired_evidence(prepared):
    timing_fixture(prepared)
    result, model = run(prepared)
    assert result['record']['decision'] == 'START' and model.calls == 1
    assert result['record']['headroom'] == pytest.approx(.2)
    assert result['record']['symptom_reproduced']
    assert validated_preparation(**prepared['kw'])['headroom'] == pytest.approx(.2)


@pytest.mark.parametrize('mutation', ['reuse', 'reference', 'quality', 'ordering', 'foreign_worker'])
def test_invalid_timing_evidence_cannot_manufacture_headroom(prepared, mutation):
    timing_fixture(prepared)
    timing = prepared['prep']['timing']
    if mutation == 'reuse': timing['rounds'][2] = copy.deepcopy(timing['rounds'][0])
    elif mutation == 'reference': prepared['review']['approved_reference_refs'] = []
    else:
        row = timing['rounds'][0]['reference_checks'][0]
        capture = prepared['store'].get(row['capture_ref'])
        if mutation == 'quality':
            output = prepared['store'].put({'changed': 'wrong output'})
            prepared['review']['approved_evidence_refs'].append(output)
            capture['receipt']['stdout_ref'] = output
        elif mutation == 'ordering': capture['receipt']['started_at'] = '2026-10-24T00:00:00Z'
        elif mutation == 'foreign_worker': capture['request']['phase'] = 'hidden_final'
        row['capture_ref'] = prepared['store'].put(capture)
        prepared['review']['approved_evidence_refs'].append(row['capture_ref'])
    prepared['kw'] = prepared['repin']()
    result, model = run(prepared)
    assert result['record']['decision'] == 'NO_ATTEMPT' and result['readiness'] == 'BLOCKED'
    assert model.calls == 0


def test_larger_input_cannot_widen_admitted_port_to_manufacture_headroom(prepared):
    row = prepared['prep']['development_checks'][0]
    value = prepared['store'].get(row['input_ref'])
    value['scores'] = [dict(value['scores'][0], idea_id=str(i)) for i in range(4)]
    new_input = prepared['store'].put(value)
    capture = prepared['store'].get(row['capture_ref'])
    capture['request']['input_ref'] = new_input
    row.update(input_ref=new_input, capture_ref=prepared['store'].put(capture))
    prepared['review']['approved_evidence_refs'].extend([row['capture_ref'], new_input])
    prepared['kw'] = prepared['repin']()
    result, model = run(prepared)
    assert result['record']['decision'] == 'NO_ATTEMPT' and result['readiness'] == 'BLOCKED'
    assert model.calls == 0


def test_reconciliation_rejects_changed_original_prompt_and_fact_claims(prepared):
    result, _ = run(prepared)
    record = copy.deepcopy(result['record'])
    capture = prepared['store'].get(result['diagnosis_capture_ref'])
    capture['prompt_ref'] = prepared['store'].put_bytes(b'foreign prompt')
    record['evidence_refs'][-1] = prepared['store'].put(capture)
    pin = prepared['store'].put(record)
    with pytest.raises(ValueError, match='prompt differs'):
        validate_opportunity(**prepared['kw'], opportunity_ref=pin)
    record = copy.deepcopy(result['record']); record['headroom'] = .01
    with pytest.raises(ValueError, match='prepared facts'):
        validate_opportunity(**prepared['kw'], opportunity_ref=prepared['store'].put(record))
    record = copy.deepcopy(result['record'])
    record['evidence_refs'].insert(1, prepared['target']['protected_refs'][0])
    with pytest.raises(ValueError, match='evidence selection'):
        validate_opportunity(**prepared['kw'], opportunity_ref=prepared['store'].put(record))


def test_timeout_retains_actual_dispatch_metadata_without_retry(prepared):
    class FailingDouble(DiagnosisTransportDouble):
        async def __call__(self, prompt):
            self.calls += 1
            raise TimeoutError('Synthetic transport failure: hidden secret path must not become reason')
    model = FailingDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'])
    result, _ = run(prepared, model=model)
    assert model.calls == 1 and result['record']['decision'] == 'NEEDS_REVIEW'
    assert result['readiness'] == 'BLOCKED'
    capture = prepared['store'].get(result['diagnosis_capture_ref'])
    assert capture['response_ref'] is None and capture['generation_evidence_refs'] == model.last_evidence
    assert 'hidden secret' not in json.dumps(result)


@pytest.mark.parametrize('prepared', ['normalize-labels-v1'], indirect=True)
def test_unrelated_visible_helper_uses_same_opportunity_engine_without_executing_reference(prepared, monkeypatch):
    """An explicit synthetic parent grant, never an existing-capsule permission."""
    import jiuwenswarm.research_rsi.targets as targets
    def forbidden_reference(*_):
        pytest.fail('Read-only opportunity validation must not execute a reference helper')
    monkeypatch.setattr(targets, 'normalize_labels', forbidden_reference)
    facts = validated_preparation(**prepared['kw'])
    assert facts['headroom'] == 1 and facts['parent_mandatory_passed']
    assert prepared['target']['mutable_paths'] == ['normalize.py']
    model = DiagnosisTransportDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'], changes={
        'authorized_component': 'normalize.py', 'observed_symptom': 'Synthetic visible label mismatch',
        'suspected_mechanism': 'Normalization behavior',
        'proposed_change_direction': 'Preserve whitespace/case normalization and ordering'})
    result, _ = run(prepared, model=model)
    assert result['record']['decision'] == 'START' and model.calls == 1
    assert result['record']['parent']['cc_name'] == 'utility.normalize'
    assert model.prompt['authorized_component'] == 'normalize.py'
    assert validate_opportunity(**prepared['kw'], opportunity_ref=result['ref'])['headroom'] == 1


@pytest.mark.parametrize('failure', ['exposure', 'profile_in_use', 'security'])
def test_unknown_effect_and_security_failure_propagate_after_diagnosis_capture(prepared, monkeypatch, failure):
    """Controlled failed dispatch; ordinary BLOCKED cannot claim cessation."""
    import jiuwenswarm.research_rsi.opportunity as opportunity_module
    from jiuwenswarm.research_rsi.custody import ExposureError
    from jiuwenswarm.research_rsi.native_lease import ProfileInUse
    from jiuwenswarm.research_rsi.mutation import SecurityViolation
    error = {'exposure': ExposureError, 'profile_in_use': ProfileInUse, 'security': SecurityViolation}[failure]
    runners = []
    original = opportunity_module.BoundedDiagnosis
    def capture_runner(*args, **kwargs):
        runner = original(*args, **kwargs); runners.append(runner)
        return runner
    monkeypatch.setattr(opportunity_module, 'BoundedDiagnosis', capture_runner)
    class UnknownDouble(DiagnosisTransportDouble):
        async def __call__(self, prompt):
            self.calls += 1
            raise error('Controlled unknown effect or security violation')
    model = UnknownDouble(prepared['store'], prepared['prep']['evidence'][0]['ref'])
    with pytest.raises(error, match='Controlled'):
        run(prepared, model=model)
    assert model.calls == 1 and len(runners) == 1
    capture = prepared['store'].get(runners[0].last_capture_ref)
    assert capture['status'] == 'unavailable' and capture['response_ref'] is None
    assert capture['generation_evidence_refs'] == model.last_evidence
    assert prepared['store'].read(capture['prompt_ref'])


def test_host_worker_mismatch_emits_canonical_blocked_without_retaining_foreign_facts(prepared):
    foreign = prepared['store'].put({'controlled': 'different protected current worker'})
    result, model = run(prepared, expected_worker_profile_ref=foreign)
    assert model.calls == 0 and result['readiness'] == 'BLOCKED'
    record = result['record']
    assert record['decision'] == 'NO_ATTEMPT' and record['headroom'] is None
    assert record['attribution'] == 'uncertain' and record['diagnosis_ref'] is None
    assert not record['symptom_reproduced'] and not record['parent_mandatory_passed']
    assert result['parent_visible_time_s'] is None
    ContractData().validate('rsi-opportunity', record)
    accepted, model = run(prepared, expected_worker_profile_ref=prepared['prep']['worker_profile_ref'])
    assert accepted['record']['decision'] == 'START' and model.calls == 1
