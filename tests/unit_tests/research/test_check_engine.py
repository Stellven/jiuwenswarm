import asyncio

import pytest

from jiuwenswarm.research.checks import CheckContext, CheckRegistry
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def test_bundle_runs_once_for_all_outputs_and_missing_check_fails(tmp_path):
    store = SQLiteRunStore(tmp_path)
    ref = store.put_blob(b"runner")
    calls = []
    def handler(ctx, inputs, outputs):
        calls.append(tuple(outputs))
        return [{"check_id": "one", "outcome": "PASS", "reason": "checked", "evidence_refs": []}]
    registry = CheckRegistry()
    registry.register_bundle("tests.checks", ["one", "two"], handler, implementation_ref=ref, profile_ref=ref)
    context = CheckContext({}, store, {}, {"first": 1, "second": 2}, {"first": ref, "second": ref}, {})
    plan = {"mandatory_deterministic": ["one", "two"], "runner_refs": [ref], "profile_ref": ref}
    result = asyncio.run(registry.run(plan, context, bundle_id="tests.checks"))
    assert calls == [("first", "second")]
    assert {r["check_id"]: r["outcome"] for r in result} == {"one": "PASS", "two": "FAIL"}


def test_duplicate_result_and_unpinned_runner_never_pass(tmp_path):
    store = SQLiteRunStore(tmp_path)
    ref = store.put_blob(b"runner")
    result = {"check_id": "one", "outcome": "PASS", "reason": "checked", "evidence_refs": []}
    registry = CheckRegistry()
    registry.register_bundle("tests.checks", ["one"], lambda *args: [result, result], implementation_ref=ref, profile_ref=ref)
    context = CheckContext({}, store, {}, {"out": 1}, {"out": ref}, {})
    plan = {"mandatory_deterministic": ["one"], "runner_refs": [ref], "profile_ref": ref}
    assert asyncio.run(registry.run(plan, context, bundle_id="tests.checks"))[0]["outcome"] == "FAIL"
    with pytest.raises(ResearchError, match="check_pin_mismatch"):
        asyncio.run(registry.run(plan | {"runner_refs": []}, context, bundle_id="tests.checks"))
