"""Transport preserves legitimate semantic abstentions, never coerces them."""
import pytest

from jiuwenswarm.research_sidecar.client import ResearchClient, ClientError


@pytest.mark.parametrize('verdict', ['INCONCLUSIVE', 'ENVIRONMENT_BLOCKED'])
def test_replay_retains_detailed_nonadvancing_outcome(verdict):
    client = object.__new__(ResearchClient)
    # Gate schema validation has independent contract tests; isolate transport's
    # narrower enum bug without inventing a live request or gate observation.
    client.validate = lambda kind, value: None
    value = {'replay_id': 'fixture', 'tier1_verdict': 'PASS', 'tier2_verdict': verdict,
             'gate_decision': {}, 'advanced': False, 'persisted_at': 'fixture',
             'downstream_action': 'locked', 'evidence_refs': [], 'model_calls': [],
             'duration_s': 0, 'reason': 'Fixture abstention', 'invalid_for_product': True}
    assert client._evaluation_result(value, 'node_replay') is value
    value['advanced'] = True
    with pytest.raises(ClientError, match='cannot advance'):
        client._evaluation_result(value, 'node_replay')


def test_recording_decision_has_its_own_closed_non_product_schema():
    from jiuwenswarm.research_records.contracts import ContractData
    import copy
    ref = {'id': 'fixture', 'sha256': 'a' * 64}
    value = {'contract_ref': ref, 'check_plan_ref': ref, 'output_port': 'result',
             'output_refs': [ref], 'deterministic_result_ref': ref, 'assessment_ref': None,
             'verifier_check_ref': None, 'verdict': 'INCONCLUSIVE', 'action': 'halt',
             'reasons': ['Missing supporting evidence'], 'accepted': False, 'invalid_for_product': True}
    validate = ContractData().validate
    validate('urn:ai4r:evaluation-recording-decision:1.0.0', value)
    for change in ({'accepted': True}, {'invalid_for_product': False}, {'foreign': 'field'}):
        with pytest.raises(ValueError):
            validate('urn:ai4r:evaluation-recording-decision:1.0.0', value | change)
    with pytest.raises(ValueError):
        validate('gate-decision', value)
