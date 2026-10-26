"""Adversarial authorization and containment tests for Builder host actions."""
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.builder_agent_host import BuilderAgentHost
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.executor import RestrictedExecutor


class _Store:
    def __init__(self):
        self.records = {}
        self.rows = []

    def add(self, ref, kind, record):
        self.records[ref] = record
        self.rows.append({"ref": ref, "kind": kind, "record": record})

    def iter_records(self, *, run_id, kinds):
        return [row for row in self.rows if row["kind"] in kinds and row["record"].get("run_id") == run_id]

    def read_record(self, ref):
        return self.records[ref]

    def record_ref(self, record_id):
        return record_id


def _host_and_binding(returned=None, *, include_output=True, evidence=True):
    store = _Store()
    host = object.__new__(BuilderAgentHost)
    host.store = store
    binding = SimpleNamespace(
        contract={"run_id": "run-1"}, contract_ref={"sha256": "c" * 64},
        invocation_id="inv-1", execution_id="exec-1")
    envelope = {"action": "write_file", "arguments": {"path": "poc_patch.py", "content": "safe", "expected_sha256": "d" * 64}}
    if returned is not None:
        envelope = returned
    claim_ref, call_id, output_ref = "claim-1", "call-1", "output-1"
    store.add(claim_ref, "model-call-claim", {"call_ordinal": 1})
    store.add(call_id, "model-call", {"id": call_id, "invocation_id": "inv-1", "execution_id": "exec-1",
        "contract_ref": dict(binding.contract_ref), "outcome": "completed", "observed_runtime": True,
        "evidence_refs": [output_ref] if evidence else []})
    store.add("start-1", "model-call-start", {"run_id": "run-1", "contract_ref": dict(binding.contract_ref),
        "invocation_id": "inv-1", "execution_id": "exec-1", "call_id": call_id, "call_claim_ref": claim_ref})
    if include_output:
        store.add(output_ref, "model-call-output", {"run_id": "run-1", "call_id": call_id,
            "invocation_id": "inv-1", "text": json.dumps(envelope)})
    return host, binding, envelope


def test_action_requires_exact_protected_model_output_and_argument_claim():
    host, binding, expected = _host_and_binding()
    call_ref, output_ref = host._model_action(binding, "write_file", expected["arguments"], 1)
    assert (call_ref, output_ref) == ("call-1", "output-1")
    with pytest.raises(ResearchError, match="differs"):
        host._model_action(binding, "write_file", {"path": "other"}, 1)
    with pytest.raises(ResearchError, match="differs"):
        host._model_action(binding, "read_file", expected["arguments"], 1)


def test_action_claim_must_join_completed_output_evidence_once():
    host, binding, envelope = _host_and_binding(evidence=False)
    with pytest.raises(ResearchError, match="Incomplete or unobserved"):
        host._model_action(binding, "write_file", envelope["arguments"], 1)
    host, binding, envelope = _host_and_binding(include_output=False)
    with pytest.raises(ResearchError, match="Incomplete or unobserved"):
        host._model_action(binding, "write_file", envelope["arguments"], 1)


def test_action_rejects_output_joined_to_another_invocation():
    host, binding, envelope = _host_and_binding()
    row = host.store.records["output-1"]
    row["invocation_id"] = "inv-other"
    with pytest.raises(ResearchError, match="Incomplete or unobserved"):
        host._model_action(binding, "write_file", envelope["arguments"], 1)


@pytest.mark.parametrize("field,value", [
    ("id", "foreign-call"),
    ("contract_ref", {"sha256": "f" * 64}),
    ("execution_id", "foreign-execution"),
    ("invocation_id", "foreign-invocation"),
])
def test_model_call_record_identity_must_match_its_protected_start(binding_identity_case, field, value):
    host, binding, envelope = binding_identity_case
    host.store.records["call-1"][field] = value
    with pytest.raises(ResearchError):
        host._model_action(binding, "write_file", envelope["arguments"], 1)


@pytest.fixture
def binding_identity_case():
    # The model-call output remains byte-for-byte while its protected identity
    # record is changed independently by the parametrized test.
    return _host_and_binding()


@pytest.mark.asyncio
async def test_agent_session_dispatch_rejects_stale_hash_and_replayed_model_ordinal():
    from jiuwenswarm.research.builder_agent_service import BuilderAgentService

    async def checks(*args):
        return {"passed": True}

    service = BuilderAgentService(initial_files={"requirements.txt": "# stdlib\n", "poc_patch.py": "x\n",
        "run_benchmark.py": "y\n"}, execute_check=checks)
    args = {"path": "poc_patch.py", "content": "changed\n", "expected_sha256": "0" * 64}
    stale = await service.dispatch("write_file", args, 1)
    replay = await service.dispatch("list_files", {}, 1)
    assert stale["error"] == "stale_file_hash"
    assert replay["error"] == "invalid_model_ordinal"
    assert service.inspect()["files"]["poc_patch.py"] == "x\n"


@pytest.mark.skipif(__import__("os").name != "posix" or not hasattr(__import__("os"), "geteuid"),
                    reason="Linux containment checks require POSIX")
def test_missing_cgroup_containment_is_a_prerequisite_failure(tmp_path, monkeypatch):
    import os
    if os.geteuid() != 0:
        pytest.skip("protected containment probe requires root")
    executor = object.__new__(RestrictedExecutor)
    executor.execution_mode = 'restricted'
    executor.broker = None
    executor.cgroup_root = tmp_path / "empty-cgroup"
    executor.cgroup_root.mkdir()
    monkeypatch.setattr("jiuwenswarm.research.executor.shutil.which", lambda _: "/usr/bin/bwrap")
    assert "CGROUP_V2_REQUIRED" in executor.prerequisites()
