"""Custody and evidence-binding tests for protected Pi scoring."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.executor import InvocationBinding
from jiuwenswarm.research.execution_jobs import ScienceExecutionAdapter
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from jiuwenswarm.research.trusted_pi import PROTOCOL, RootPiScorer


pytestmark = pytest.mark.skipif(os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                                reason="trusted Pi custody tests require the Linux root broker")


@pytest.fixture
def scorer(tmp_path):
    store = SQLiteRunStore(tmp_path / "store")
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    reference = b"3." + b"1" * 100_000
    path = private_dir / "pi-reference.txt"
    path.write_bytes(reference)
    path.chmod(0o400)
    profile = {
        "protocol": PROTOCOL,
        "public_dataset_ref": {"sha256": "a" * 64},
        "reference_path": str(path),
        "reference_sha256": hashlib.sha256(reference).hexdigest(),
        "source_sha256": "b" * 64,
        "unseen_precisions": [20001, 30001, 40001],
        "measured_precisions": [10000, 100000],
        "repetitions": 5,
        "max_stdout_bytes": 1_048_576,
    }
    result = RootPiScorer(store, profile)
    yield store, result, profile
    store.close()


def _job():
    return SimpleNamespace(job_id="job-1", contract_ref={"sha256": "c" * 64},
        invocation_id="inv-1", timeout_s=1.0)


def _raw(store, job, *, wall_time_s=0.25, job_id=None, contract_ref=None, invocation_id=None, digits=10):
    decimal = b"3." + b"1" * digits
    stdout = store.put_blob(json.dumps({"digits": digits, "decimal": decimal.decode()}).encode())
    stderr = store.put_blob(b"")
    return {"job_id": job_id or job.job_id,
        "contract_ref": contract_ref or dict(job.contract_ref),
        "invocation_id": invocation_id or job.invocation_id,
        "role": "treatment", "repeat_index": 0, "sequence": 1,
        "subject_ref": {"sha256": "d" * 64}, "stdout_ref": stdout,
        "stderr_ref": stderr, "wall_time_s": wall_time_s,
        "exit_code": 0, "termination_reason": "completed", "observed_runtime": True}


def test_scorer_ties_requested_digits_to_the_registered_case(scorer):
    store, root_scorer, _ = scorer
    job = _job()
    # A caller must not relabel a seven-digit case as pi-10000 and receive a
    # trusted score just because the output matches the supplied short prefix.
    raw = _raw(store, job, digits=7)
    with pytest.raises(ResearchError):
        root_scorer.score(job, raw, {"case_id": "pi-10000", "digits": 7})


def test_scorer_rejects_forged_time_beyond_the_original_job_limit(scorer):
    store, root_scorer, _ = scorer
    job = _job()
    raw = _raw(store, job, wall_time_s=9.0, digits=10000)
    with pytest.raises(ResearchError):
        root_scorer.score(job, raw, {"case_id": "pi-10000", "digits": 10000})


def test_scorer_accepts_exact_registered_case_and_reference_prefix(scorer):
    store, root_scorer, _ = scorer
    job = _job()
    raw = _raw(store, job, wall_time_s=0.25, digits=10000)
    scored = root_scorer.score(job, raw, {"case_id": "pi-10000", "digits": 10000})
    assert scored["trusted_scoring_ref"]
    receipt = store.read_record(scored["trusted_scoring_ref"])
    assert receipt["correct"] is True
    assert receipt["digits"] == 10000
    assert receipt["elapsed_s"] == 0.25


@pytest.mark.parametrize("field,value", [
    ("job_id", "foreign-job"),
    ("invocation_id", "foreign-invocation"),
    ("contract_ref", {"sha256": "f" * 64}),
])
def test_executor_scorer_requires_original_raw_execution_identity(scorer, field, value):
    store, root_scorer, _ = scorer
    job = _job()
    raw = _raw(store, job, **{field: value})
    adapter = object.__new__(ScienceExecutionAdapter)
    adapter.scorer = root_scorer
    public = {"case_id": "pi-10000", "digits": 10}
    adapter._measurement_jobs = {job.job_id: (job, public)}
    binding = InvocationBinding(job.contract_ref, job.invocation_id,
        {"run_id": "run-1"}, execution_id="exec-1")
    with pytest.raises(ResearchError):
        adapter.score_result(job, raw, binding=binding)


def test_profile_reference_bytes_are_pinned_and_unseen_precisions_are_closed(scorer, tmp_path):
    store, _, profile = scorer
    changed = dict(profile)
    changed["unseen_precisions"] = [20001, 30001, 30001]
    with pytest.raises(ResearchError):
        RootPiScorer(store, changed)
    path = Path(profile["reference_path"])
    path.chmod(0o600)
    with pytest.raises(ResearchError):
        RootPiScorer(store, profile)
