"""Independent contract probes, not claims about model semantic quality."""
import copy
import json

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, sha256_bytes
from jiuwenswarm.ai4research.intent.models import validate_intent

ORIGINAL = "Compare batteries. No experiments."


def candidate():
    return {"schema_revision": "intent-r2", "run_id": "run-1", "source_sha256": sha256_bytes(ORIGINAL.encode()),
            "objective": {"text": "Compare batteries.", "source_spans": [{"start": 0, "end": 18}]},
            "desired_outcome": None, "scope": [], "constraints": [
                {"text": "No experiments.", "source_spans": [{"start": 19, "end": len(ORIGINAL)}]}],
            "omissions": ["Desired outcome is unstated."], "conflicts": []}


def test_m0_trial_1_b03_accepts_attributed_intermediate_omission():
    parsed = validate_intent(canonical_json(candidate()), ORIGINAL, "run-1")
    assert parsed.desired_outcome is None
    assert parsed.constraints[0].text == "No experiments."


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(run_id="other-run"),
    lambda x: x.update(source_sha256="0" * 64),
    lambda x: x.update(verdict="PASS"),
    lambda x: x["objective"].update(source_spans=[]),
    lambda x: x["objective"].update(source_spans=[{"start": 0, "end": 1000}]),
    lambda x: x["objective"].update(source_spans=[{"start": 5, "end": 2}]),
    lambda x: x["objective"].update(source_spans=[{"start": True, "end": 18}]),
    lambda x: x.update(omissions=[""]),
    lambda x: x.update(schema_revision="Research_Brief"),
])
def test_m0_trial_1_b05_refuses_malformed_stale_authority_and_evidence(mutation):
    value = candidate()
    mutation(value)
    with pytest.raises(GovernanceError):
        validate_intent(canonical_json(value), ORIGINAL, "run-1")


@pytest.mark.parametrize("raw", [b'{}', b'[]', b'{"run_id":"a","run_id":"b"}', b'```json\n{}\n```', b'{"x":NaN}'])
def test_m0_trial_1_b05_no_json_repair_or_duplicate_fields(raw):
    with pytest.raises(GovernanceError):
        validate_intent(raw, ORIGINAL, "run-1")
