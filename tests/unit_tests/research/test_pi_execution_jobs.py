"""Pi host-job issuance controls exercised without claiming kernel execution."""
import asyncio
import io
import json
import platform
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.execution_jobs import ScienceExecutionAdapter, ScienceProfile
from jiuwenswarm.research.executor import InvocationBinding, PreparedEnvironment, ReadonlyMount
from jiuwenswarm.research.pi_task import _baseline_source, capture_pi_task
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from jiuwenswarm.research import trusted_pi


class _PiProfile:
    protocol = "ai4r-pi:1"

    def __init__(self, validation_ref):
        self.profile = {"public_dataset_ref": validation_ref}

    def digits_for(self, case_id):
        return {
            "pi-10000": 10_000, "pi-100000": 100_000,
            "pi-unseen-1": 23_457, "pi-unseen-2": 67_891, "pi-unseen-3": 99_991,
            "pi-boundary-0": 0, "pi-boundary-1": 1, "pi-boundary-2": 2, "pi-boundary-17": 17,
        }[case_id]


def _candidate_archive():
    files = {
        "requirements.txt": b"",
        "poc_patch.py": (
            b"def approximate_pi(digits):\n"
            b"    if digits == 0:\n"
            b"        return '3.'\n"
            b"    return '3.' + '0' * digits\n"
        ),
        "run_benchmark.py": (
            b"import json\nfrom pathlib import Path\n"
            b"from poc_patch import approximate_pi\n"
            b"request = json.loads(Path('/resources/validation/data.json').read_text())\n"
            b"digits = request['digits']\n"
            b"print(json.dumps({'digits': digits, 'decimal': approximate_pi(digits)}))\n"
        ),
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return stream.getvalue()


class _PreparedAdapter(ScienceExecutionAdapter):
    """Avoid OS-side execution while preserving job-factory admission logic."""
    def _resource(self, value, ref, target):
        self.mounted.append((value, ref, target))
        source = self.profile.asset_root / ("mount-" + str(len(self.mounted)))
        source.mkdir(parents=True, exist_ok=True)
        return ReadonlyMount(source, target, ref)

    def environment_verifier(self, prepared):
        assert prepared == self._prepared["invoke"][0]


@pytest.fixture
def setup_pi(tmp_path, monkeypatch):
    monkeypatch.setattr(trusted_pi, "capture_pi_profile", lambda _directory, public_ref: {
        "protocol": "ai4r-pi:1", "public_dataset_ref": public_ref,
        "unseen_precisions": [23_457, 67_891, 99_991], "measured_precisions": [10_000, 100_000],
        "repetitions": 5, "max_stdout_bytes": 1_048_576,
    })
    store = SQLiteRunStore(tmp_path / "store")
    task = capture_pi_task(store, tmp_path / "private")
    task_inputs = task["builder_inputs"]
    blueprint_ref = task_inputs["blueprint"]
    blueprint = store.read_record(blueprint_ref)
    baseline_ref, validation_ref, lock_ref = (task_inputs[key] for key in ("baseline_resource", "validation_resource", "lock"))
    bundle = _candidate_archive()
    bundle_ref = store.put_blob(bundle)
    manifest = {"schema_version": "2.0.0", "id": "poc_manifest", "blueprint_ref": blueprint_ref,
        "environment_ref": lock_ref, "archive_ref": bundle_ref, "files": [], "dependencies": []}
    manifest_ref = store.put_blob(json_bytes(manifest))
    inputs = {
        "hypothesis_blueprint": blueprint, "baseline_resource": store.read_record(baseline_ref),
        "validation_resource": store.read_record(validation_ref), "environment_lock": store.read_record(lock_ref),
        "poc_manifest": manifest, "poc_artifact_bundle": bundle_ref,
    }
    names = {"hypothesis_blueprint": blueprint_ref, "baseline_resource": baseline_ref,
        "validation_resource": validation_ref, "environment_lock": lock_ref, "poc_manifest": manifest_ref,
        "poc_artifact_bundle": bundle_ref}
    contract = {"run_id": "pi-run", "node_id": "benchmark", "attempt_id": "attempt-1",
        "inputs": [{"name": key, "artifact_refs": [ref]} for key, ref in names.items()],
        "subnode_limits": {"time_s": 3600, "memory_mb": 256},
        "bindings": [{"declaration_ref": store.put_blob(json_bytes({"identity":{"name":"research.benchmark","version_label":"pi-m1-1"}})), "limits": {"time_s": 3600, "memory_mb": 256}}]}
    contract_ref = store.put_blob(b"pi contract")
    binding = InvocationBinding(contract_ref, "invoke", contract)
    profile = ScienceProfile(tmp_path / "assets", tmp_path / "env", 256, 16, 60, 60,
        (), (), Path(sys.executable), Path(sys.executable))
    adapter = _PreparedAdapter(store, profile, approved_environments=[], workspace_allocator=lambda *_: tmp_path / "work",
        hardware_capture=None, scorer=_PiProfile(validation_ref))
    adapter.mounted = []
    environment_ref = store.put_blob(b"prepared environment")
    prepared = PreparedEnvironment(tmp_path / "prepared", environment_ref)
    adapter._prepared["invoke"] = (prepared, {}, {})
    inventory = {"hardware_id": "controlled", "gpu_model": None, "gpu_count": 0, "gpu_memory_mb": None,
        "driver_version": None, "cuda_version": None, "cpu_model": "fixture", "cpu_cores": 1,
        "ram_mb": 1024, "os": "test", "captured_at": "2026-01-01T00:00:00Z"}
    adapter._hardware["invoke"] = inventory
    hardware_ref = store.put_blob(json_bytes(inventory))
    try:
        yield store, task, adapter, contract, binding, inputs, names, hardware_ref, blueprint
    finally:
        store.close()


def _issue(fixture, sequence, case_id, role, repeat_index):
    store, _task, adapter, contract, binding, inputs, names, hardware_ref, blueprint = fixture
    subject_ref = blueprint["baseline_identity"]["resource_ref"] if role == "baseline" else inputs["poc_manifest"]["archive_ref"]
    job = asyncio.run(adapter.job_factory(contract, inputs, binding=binding, role=role,
        repeat_index=repeat_index, seed=blueprint["seed"], sequence=sequence, subject_ref=subject_ref,
        hardware_ref=hardware_ref, case_id=case_id))
    return job


def _complete_issuance(adapter):
    adapter._pi_last["invoke"] = max(1, adapter._pi_last.get("invoke", 0) + 1)
    adapter._pi_pending.discard("invoke")


def test_pi_job_factory_issues_exact_ordered_host_cases_and_mounts_no_reference(setup_pi):
    fixture = setup_pi
    store, task, adapter, _contract, _binding, _inputs, _names, _hardware_ref, _blueprint = fixture
    cases = [("pi-10000", "baseline", i) for i in range(5)] + [("pi-10000", "treatment", i) for i in range(5)]
    cases += [("pi-100000", "baseline", i) for i in range(5)] + [("pi-100000", "treatment", i) for i in range(5)]
    cases += [(f"pi-unseen-{i}", "treatment", 0) for i in range(1, 4)]
    cases += [(f"pi-boundary-{n}", "treatment", 0) for n in (0, 1, 2, 17)]
    jobs = []
    for sequence, (case_id, role, repeat_index) in enumerate(cases, 1):
        job = _issue(fixture, sequence, case_id, role, repeat_index)
        jobs.append(job)
        _complete_issuance(adapter)
        assert job.sequence == sequence
        assert job.timeout_s <= 30
        assert job.output_limit_bytes == 1_048_576
        assert [mount.target for mount in job.readonly_mounts] == ["/resources/baseline", "/resources/validation", "/resources/poc"]
        assert all("reference" not in mount.target for mount in job.readonly_mounts)
        request_snapshot = store.read_record(job.validation_ref)
        request = json.loads(store.read_blob(request_snapshot["files"][0]["artifact_ref"]))
        assert request == {"schema": "ai4r-pi-cases:1", "digits": adapter.scorer.digits_for(case_id)}
    assert len(jobs) == 27
    assert jobs[0].role == "baseline" and jobs[5].role == "treatment"
    assert jobs[10].role == "baseline" and jobs[15].role == "treatment"
    # Host-selected precisions resolve through the frozen scorer profile and are not caller inputs.
    assert [task["scoring_profile"]["unseen_precisions"][i] for i in range(3)] == [23_457, 67_891, 99_991]
    assert all(row[0]["environment_ref"] == task["builder_inputs"]["lock"] for row in adapter.mounted)
    original_request = store.read_record(task["builder_inputs"]["validation_resource"])
    original_digits = json.loads(store.read_blob(original_request["files"][0]["artifact_ref"]))
    assert original_digits == {"schema": "ai4r-pi-cases:1", "digits": 100_000}
    assert all(row[1] != task["scoring_profile"].get("reference_ref") for row in adapter.mounted)


def test_pi_job_factory_requires_completed_sequence_and_rejects_case_id_for_classification(setup_pi):
    fixture = setup_pi
    _store, _task, adapter, contract, binding, inputs, _names, hardware_ref, blueprint = fixture
    subject = blueprint["baseline_identity"]["resource_ref"]
    job = _issue(fixture, 1, "pi-10000", "baseline", 0)
    with pytest.raises(ResearchError):
        asyncio.run(adapter.job_factory(contract, inputs, binding=binding, role="baseline", repeat_index=0,
            seed=blueprint["seed"], sequence=1, subject_ref=subject, hardware_ref=hardware_ref, case_id="pi-10000"))
    _complete_issuance(adapter)
    with pytest.raises(ResearchError):
        asyncio.run(adapter.job_factory(contract, inputs, binding=binding, role="baseline", repeat_index=0,
            seed=blueprint["seed"], sequence=1, subject_ref=subject, hardware_ref=hardware_ref, case_id="pi-10000"))
    non_pi = _PreparedAdapter(adapter.store, adapter.profile, approved_environments=[], workspace_allocator=lambda *_: Path("."),
        hardware_capture=None, scorer=None)
    non_pi._prepared["invoke"] = adapter._prepared["invoke"]
    non_pi._hardware["invoke"] = adapter._hardware["invoke"]
    non_pi.mounted = []
    with pytest.raises(ResearchError):
        asyncio.run(non_pi.job_factory(contract, inputs, binding=binding, role="baseline", repeat_index=0,
            seed=blueprint["seed"], sequence=1, subject_ref=subject, hardware_ref=hardware_ref, case_id="pi-10000"))
    assert job.argv[0] == "/environment/bin/python"


def test_pi_job_factory_rejects_a_replaced_frozen_validation_ref(setup_pi):
    _store, _task, adapter, contract, binding, inputs, _names, hardware_ref, blueprint = setup_pi
    replacement = adapter.store.put_blob(b'{"schema":"ai4r-pi-cases:1","digits":17}')
    row = next(row for row in contract["inputs"] if row["name"] == "validation_resource")
    row["artifact_refs"] = [replacement]
    subject = blueprint["baseline_identity"]["resource_ref"]
    with pytest.raises(ResearchError):
        asyncio.run(adapter.job_factory(contract, inputs, binding=binding, role="baseline", repeat_index=0,
            seed=blueprint["seed"], sequence=1, subject_ref=subject, hardware_ref=hardware_ref, case_id="pi-10000"))
