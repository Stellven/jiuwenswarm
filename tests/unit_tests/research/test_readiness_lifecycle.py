"""Missing confinement facilities cannot become permission to execute."""
import os
from pathlib import Path

import pytest

from jiuwenswarm.research.executor import ExecutorBlocked, RestrictedExecutor


def executor(tmp_path, **kwargs):
    return RestrictedExecutor(workspace_root=tmp_path / "work", cgroup_root=None,
                              authorize_job=lambda job: job, capture=lambda *a, **k: None, **kwargs)


def test_missing_cgroup_is_explicit_not_an_unconfined_fallback(tmp_path):
    assert "DELEGATED_CGROUP_UNAVAILABLE" in executor(tmp_path).prerequisites()


@pytest.mark.asyncio
async def test_missing_authoritative_factories_never_invent_run_receipts(tmp_path):
    value = executor(tmp_path)
    for operation in (value.provision({}, {}, {}), value.hardware_inventory({}),
                      value.collect_builder({}), value.measure_job({}, {})):
        with pytest.raises(ExecutorBlocked):
            await operation


def test_workspace_outside_owned_root_is_refused(tmp_path):
    work = tmp_path / "outside"
    work.mkdir()
    with pytest.raises(ExecutorBlocked, match="WORKSPACE_SCOPE_DENIED"):
        executor(tmp_path)._workspace(work)


def test_no_resource_mount_is_allowed_without_pinned_verifier(tmp_path):
    from jiuwenswarm.research.executor import ReadonlyMount
    resource = tmp_path / "asset"
    resource.write_bytes(b"captured")
    value = executor(tmp_path, allowed_asset_roots=[tmp_path])
    with pytest.raises(ExecutorBlocked, match="RESOURCE_MOUNT_INVALID"):
        value._mount_arguments([ReadonlyMount(resource, "/resources/baseline", {"id": "x", "sha256": "a" * 64})])


def test_raw_native_capture_survives_projection_limit_and_reopen(tmp_path):
    import hashlib
    import sqlite3
    from types import SimpleNamespace
    from jiuwenswarm.research.trajectory import LosslessTrajectoryJournal
    raw = b'{"payload":"' + b'x' * (4 * 1024 * 1024 + 1) + b'"}'
    blob = b'["complete native content"]'
    digest = hashlib.sha256(blob).hexdigest()
    sequence = SimpleNamespace(key="content", seq_hash="chain", depth=1, logical_bytes=len(blob),
        nodes=[SimpleNamespace(seq_hash="chain", prev_hash=None, blob_hash=digest, depth=1)], blobs={digest: blob})
    record = SimpleNamespace(raw_json=raw, trace_id="trace", span_id="span", session_id="session", sequences=[sequence])
    journal = LosslessTrajectoryJournal(tmp_path / "capture")
    journal.consume(record)
    journal.close()
    journal = LosslessTrajectoryJournal(tmp_path / "capture")
    assert journal.healthy and journal.count == 1
    with sqlite3.connect(journal.path) as db:
        assert db.execute('SELECT content FROM blobs WHERE sha256=?', (hashlib.sha256(raw).hexdigest(),)).fetchone()[0] == raw
        assert db.execute('SELECT content FROM blobs WHERE sha256=?', (digest,)).fetchone()[0] == blob
    journal.close()


def test_native_capture_failure_latches_and_cannot_be_reported_healthy(tmp_path):
    from types import SimpleNamespace
    from jiuwenswarm.research.trajectory import LosslessTrajectoryJournal, CaptureUnavailable
    journal = LosslessTrajectoryJournal(tmp_path / "capture")
    with pytest.raises(CaptureUnavailable):
        journal.consume(SimpleNamespace(raw_json=b'{}', sequences=[SimpleNamespace(blobs={"wrong": b"bytes"})]))
    assert not journal.healthy and journal.count == 0
    with pytest.raises(CaptureUnavailable):
        journal.consume(SimpleNamespace(raw_json=b'{}', sequences=[]))
    journal.close()


def test_native_capture_refuses_symlink_store_before_opening(tmp_path):
    from jiuwenswarm.research.trajectory import LosslessTrajectoryJournal, CaptureUnavailable
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(CaptureUnavailable):
        LosslessTrajectoryJournal(link)


@pytest.mark.asyncio
async def test_bound_executor_rejects_swapped_and_replayed_jobs_before_broker(tmp_path):
    from dataclasses import replace
    from jiuwenswarm.research.executor import ExecutionJob
    ref = {"id": "contract", "sha256": "a" * 64}
    seen = []
    async def factory(contract, inputs, *, binding, **selection):
        assert binding.contract_ref == ref and binding.invocation_id == "invocation"
        return ExecutionJob(job_id="job", invocation_id=binding.invocation_id, contract_ref=binding.contract_ref,
            run_id="run", node_id="node", attempt_id="attempt", sequence=1, role="baseline", repeat_index=0,
            seed=1, argv=("/usr/local/bin/python3", "run.py"), cwd=tmp_path, timeout_s=1, memory_mb=16,
            pids_max=16, baseline_ref=ref, validation_ref=ref, environment_ref=ref, subject_ref=ref, hardware_ref=ref)
    class Broker:
        async def run(self, job):
            seen.append(job)
            return {"observed_runtime": True}
    value = executor(tmp_path, job_factory=factory, broker=Broker())
    bound = value.bind_invocation(contract_ref=ref, invocation_id="invocation", contract={"id": "contract"})
    job = await bound.measure_job({"id": "contract"}, {})
    with pytest.raises(ExecutorBlocked, match="UNISSUED_EXECUTION_JOB"):
        await bound.run(replace(job, argv=("/usr/local/bin/python3", "foreign.py")))
    assert await bound.run(job) == {"observed_runtime": True}
    with pytest.raises(ExecutorBlocked, match="EXECUTION_JOB_ALREADY_CLAIMED"):
        await bound.run(job)
    assert seen == [job]
