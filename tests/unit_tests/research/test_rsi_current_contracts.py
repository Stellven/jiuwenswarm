"""Current IF009 r2 and explicit historical decoding have distinct identities."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import ContractError, validate


def test_current_feedback_preserves_fractional_means_and_closed_five_fields():
    value = {'schema_version': '2.0.0', 'id': 'feedback:test', 'passed': 20 / 3, 'total': 20, 'queries_left': 29}
    validate('rsi-loop-feedback', value)
    validate('rsi-loop-feedback:field-contract:2', value)
    with pytest.raises(ContractError):
        validate('rsi-loop-feedback:field-contract:1', value)
    with pytest.raises(ContractError):
        validate('rsi-loop-feedback', value | {'reasons': ['hidden detail']})
    validate('rsi-loop-feedback:field-contract:1', value | {'schema_version': '1.0.0', 'passed': 6})


def test_rejected_attempt_retains_absence_and_requires_real_failure_evidence():
    path = Path('tests/fixtures/research/governance/contracts/rsi_attempt_v1.json')
    value = json.loads(path.read_text(encoding='utf-8'))
    # The supplied illustration's disclosure marker is not an RSI field.
    value.pop('ext', None)
    historical = dict(value)
    value.update(schema_version='2.0.0', attempt_status='rejected', child_ref=None, diff_ref=None, rationale=None,
                 rejection_reason='No actual proposal bytes returned', failure_evidence_refs=[value['parent_ref']])
    validate('rsi-attempt', value)
    with pytest.raises(ContractError):
        validate('rsi-attempt', value | {'failure_evidence_refs': []})
    with pytest.raises(ContractError):
        validate('rsi-attempt', value | {'attempt_status': 'proposed', 'rejection_reason': None})
    validate('rsi-attempt:field-contract:1', historical)
    with pytest.raises(ContractError):
        validate('rsi-attempt', historical)
