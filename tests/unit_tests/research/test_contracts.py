"""Source-contract checks; these host tests do not qualify Linux execution."""

import copy
import json
from importlib.resources import files
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import ContractError, validate


def test_ref_is_exact_and_hash_is_lowercase():
    validate("Ref", {"id": "captured:one", "sha256": "a" * 64})
    for bad in ({"id": "one", "sha256": "A" * 64},
                {"id": "one", "sha256": "a" * 64, "path": "/host"},
                {"id": "one"}):
        with pytest.raises(ContractError):
            validate("Ref", bad)


def test_catalog_is_packaged_and_pinned():
    root = files("jiuwenswarm.research_contracts")
    manifest = json.loads(root.joinpath("source_manifest.json").read_text("utf-8"))
    assert manifest["interfaces"]["M1-IF-003"] == "r3"
    assert manifest["sources"]
    assert json.loads(root.joinpath("catalog.json").read_text("utf-8"))["contracts"]


def test_research_brief_v3_and_historical_v2_are_versioned_explicitly():
    package = files("jiuwenswarm.research")
    current = json.loads((Path(__file__).parents[3] / "tests/fixtures/research/compiler/research_brief.json").read_text("utf-8"))
    historical = json.loads(package.joinpath("resources/calibration/research_brief.json").read_text("utf-8"))
    assert current["schema_version"] == "3.0.0"
    assert historical["schema_version"] == "2.0.0"

    # The short name follows each artifact's declared version, while explicit
    # URNs continue to enforce the requested version exactly.
    validate("research-brief", current)
    validate("research-brief", historical)
    validate("urn:jiuwenswarm:m1-design:research-brief:3.0.0", current)
    validate("urn:jiuwenswarm:m1-design:research-brief:2.0.0", historical)
    with pytest.raises(ContractError):
        validate("urn:jiuwenswarm:m1-design:research-brief:3.0.0", historical)
    with pytest.raises(ContractError):
        validate("urn:jiuwenswarm:m1-design:research-brief:2.0.0", current)


def test_unknown_contract_is_never_an_unchecked_pass():
    with pytest.raises(ContractError, match="unknown_contract"):
        validate("made-up:field-contract:99", {})
    with pytest.raises(ContractError, match="unknown_contract"):
        validate("client-submission:field-contract:99", {})


def test_nonfinite_values_never_validate():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ContractError):
            validate("Ref", {"id": "one", "sha256": "a" * 64, "value": value})


def test_field_contract_requiredness_enums_and_unknown_fields():
    request = {"schema_version": "1.0.0", "id": "submission:one", "client_request_id": "req-1",
               "workspace_id": "project", "account_id": "alice",
               "intake_ref": {"id": "intake:one", "sha256": "a" * 64},
               "configuration_ref": {"id": "configuration:one", "sha256": "b" * 64}}
    validate("client-submission", request)
    for change in ({"schema_version": "99.0.0"}, {"plan_source": "repair"},
                   {"cc.router.enabled": True}):
        with pytest.raises(ContractError):
            validate("client-submission", request | change)
    bad = copy.deepcopy(request)
    del bad["intake_ref"]
    with pytest.raises(ContractError):
        validate("client-submission", bad)


def test_array_constraints_apply_to_items_in_published_contracts():
    from jiuwenswarm.research.contracts import contract_schema
    schema = contract_schema("node-execution-contract")
    field = schema["properties"]["evidence_obligations"]
    assert "enum" not in field and "accepted_intent" in field["items"]["enum"]
