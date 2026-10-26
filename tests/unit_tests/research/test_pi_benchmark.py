import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest
from jsonschema import Draft202012Validator

from jiuwenswarm.research import trusted_pi
from jiuwenswarm.research.capsules.pi_benchmark import execute
from jiuwenswarm.research.checks.engine import CheckContext
from jiuwenswarm.research.checks.pi_benchmark import PiBenchmarkChecks
from jiuwenswarm.research.checks.research import CheckError
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.pi_protocol import baseline_pi, parse_pi_output
from jiuwenswarm.research.pi_task import capture_pi_task
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


ROOT = Path(__file__).resolve().parents[3]


def test_pi_payload_schema_is_closed_and_accepts_case_profiles():
    schema = json.loads((ROOT / "jiuwenswarm" / "research_contracts" / "schemas" /
                         "pi-benchmark-payload.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    ref = {"id": "r", "sha256": "a" * 64}
    def measure(repeats):
        return {"repeats": repeats, "median": 1.0, "spread": 0.1, "correct": True,
                "runs": [{"sequence": i + 1, "score_ref": ref, "elapsed_s": 1.0, "correct": True}
                         for i in range(repeats)]}
    value = {"schema_version": "1.0.0", "id": "pi_benchmark_payload", "blueprint_ref": ref,
             "poc_ref": ref, "environment_lock_ref": ref, "execution_receipt_ref": ref,
             "provisioning_receipt_ref": ref, "primary_case": "pi-100000", "speedup": 1.2,
             "cases": [{"case_id": "pi-10000", "digits": 10000, "baseline": measure(5), "treatment": measure(5)},
                       {"case_id": "pi-100000", "digits": 100000, "baseline": measure(5), "treatment": measure(5)},
                       *[{"case_id": f"pi-unseen-{i}", "digits": 23456+i, "treatment": measure(1)} for i in range(1, 4)],
                       *[{"case_id": f"pi-boundary-{digits}", "digits": digits, "treatment": measure(1)}
                         for digits in (0, 1, 2, 17)]],
             "raw_evidence_refs": [ref]}
    Draft202012Validator(schema).validate(value)
    value["invented_timing"] = 0
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(value)


def test_pi_benchmark_measurement_oracle_output():
    value = baseline_pi(17)
    assert value == "3.14159265358979323"
    assert parse_pi_output(json.dumps({"digits": 17, "decimal": value}), 17, value)["decimal"] == value


def _ready_receipt(manifest_ref, bundle_ref, blueprint_ref, lock_ref, store):
    ref = store.put_blob(b"{}")
    return {"schema_version": "4.0.0", "id": "pi-build", "manifest_ref": manifest_ref,
        "blueprint_ref": blueprint_ref, "environment_ref": lock_ref, "archive_ref": bundle_ref,
        "checker": "pi-build-checker:1", "file_checks": [
            {"path": path, "sha256": "a" * 64, "syntax_result": "pass", "syntax_detail": None,
             "forbidden_imports": []} for path in ("requirements.txt", "poc_patch.py", "run_benchmark.py")],
        "forbidden_scan_result": "pass", "dependencies": [], "dependencies_all_pinned": True,
        "trial_executed": True, "packages_installed": True, "readiness": "READY", "readiness_reasons": [],
        "development_only": True, "test_report_refs": [ref], "journal_ref": ref,
        "workspace_sha256": "b" * 64, "submitted_snapshot_sha256": "c" * 64,
        "model_call_count": 1, "tool_operation_count": 1, "execution_job_count": 2}


class _ControlledExecutor:
    def __init__(self, store, contract_ref, *, incorrect=None, wrong_digits=None, failed=None):
        self.store, self.contract_ref = store, contract_ref
        self.incorrect, self.wrong_digits, self.failed = incorrect, wrong_digits, failed
        self.ordinal = 0

    async def provision(self, contract, inputs, pins):
        return {"schema_version": "1.0.0", "id": "provisioning_receipt",
            "environment_lock_ref": inputs["environment_lock_ref"],
            "poc_manifest_ref": inputs["poc_manifest_ref"], "status": "succeeded",
            "python_version": "3.12", "venv_path": "/workspace/poc/venv", "runner_user": "worker",
            "packages": [], "network_policy_used": "none", "network_allowlist": [],
            "unlisted_network_requests": 0, "effects": [{"op": "unpack_bundle", "target": "poc", "outcome": "ok"}],
            "limits": {"wall_s_limit": 60, "wall_s_used": 1}}

    async def hardware_inventory(self, contract):
        return {"hardware_id": "fixture-cpu", "gpu_model": None, "gpu_count": 0, "gpu_memory_mb": None,
            "driver_version": None, "cuda_version": None, "cpu_model": "fixture", "cpu_cores": 4,
            "ram_mb": 8192, "os": "linux", "captured_at": "2026-01-01T00:00:00Z"}

    async def measure_job(self, contract, inputs, **selection):
        return dict(selection)

    async def run(self, job):
        self.ordinal += 1
        case_id = job["case_id"]
        digits = {"pi-10000": 10000, "pi-100000": 100000,
            "pi-unseen-1": 23457, "pi-unseen-2": 67891, "pi-unseen-3": 99991,
            "pi-boundary-0": 0, "pi-boundary-1": 1, "pi-boundary-2": 2,
            "pi-boundary-17": 17}[case_id]
        failed = self.failed == (case_id, job["role"], job["repeat_index"])
        started = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=self.ordinal)
        raw = {"job_id": f"job-{self.ordinal}", "sequence": job["sequence"], "role": job["role"],
            "repeat_index": job["repeat_index"], "seed": job["seed"], "subject_ref": job["subject_ref"],
            "contract_ref": self.contract_ref, "invocation_id": "invocation",
            "exit_code": 1 if failed else 0, "started_at": started.isoformat().replace("+00:00", "Z"),
            "wall_time_s": 0.2 if job["role"] == "baseline" else 0.1,
            "timeout_s": 30.0, "stdout_ref": self.store.put_blob(f"out-{self.ordinal}".encode()),
            "stderr_ref": self.store.put_blob(f"err-{self.ordinal}".encode()),
            "argv": ["/environment/bin/python", f"/{job['role']}.py"], "hardware_ref": job["hardware_ref"],
            "identity": {"executor_uid": 10002, "executor_gid": 10002}, "observed_runtime": True,
            "observed_limits": {"memory_max": str(256 * 1024 * 1024), "pids_max": "64", "network": "none",
                "cpu_affinity": [0, 1], "isolation_probe_ref": self.store.put_blob(json_bytes({
                    "ready": True, "executor_uid": 10002, "executor_gid": 10002,
                    "no_new_privileges": "1", "cap_effective": "0000000000000000",
                    "network": "none", "cpu_affinity": [0, 1]}))},
            "termination_reason": "failed" if failed else "completed"}
        correct = not failed and self.incorrect != (case_id, job["role"], job["repeat_index"])
        score = {"schema": "ai4r-pi-score:1", "id": f"score-{self.ordinal}", "case_id": case_id,
            "digits": digits + (1 if self.wrong_digits == (case_id, job["role"], job["repeat_index"]) else 0),
            "correct": correct,
            "elapsed_s": raw["wall_time_s"] if correct else None, "reference_sha256": "d" * 64,
            "protocol_profile_ref": self.store.put_blob(b"profile"), "cpu_affinity": [0, 1], "job_id": raw["job_id"],
            "contract_ref": self.contract_ref, "invocation_id": "invocation", "role": job["role"],
            "repeat_index": job["repeat_index"], "sequence": job["sequence"], "subject_ref": job["subject_ref"],
            "stdout_ref": raw["stdout_ref"], "stderr_ref": raw["stderr_ref"]}
        raw["trusted_scoring_ref"] = self.store.append_record("pi_scoring_receipt", score)
        return raw


class _ExecutionContext:
    def __init__(self, store, executor, contract, inputs, refs):
        self.store, self.executor, self.contract = store, executor, contract
        self._inputs, self._refs = inputs, refs
        self.contract_ref = {"id": "benchmark-contract", "sha256": "e" * 64}
        self.configuration_ref = {"id": "configuration", "sha256": "f" * 64}

    def input_ref(self, name):
        return self._refs[name]

    def record_host(self, key, ref):
        pass

    def read_json(self, ref):
        return self.store.read_record(ref)


async def _run_benchmark(tmp_path, monkeypatch, *, incorrect=None, wrong_digits=None, failed=None):
    monkeypatch.setattr(trusted_pi, "capture_pi_profile", lambda _directory, public_ref: {
        "protocol": "ai4r-pi:1", "public_dataset_ref": public_ref})
    store = SQLiteRunStore(tmp_path / "store")
    task = capture_pi_task(store, tmp_path / "private")
    blueprint_ref = task["builder_inputs"]["blueprint"]
    blueprint = store.read_record(blueprint_ref)
    lock_ref = task["builder_inputs"]["lock"]
    lock = store.read_record(lock_ref)
    bundle_ref = store.put_blob(b"archive")
    manifest = {"schema_version": "2.0.0", "id": "poc_manifest", "blueprint_ref": blueprint_ref,
        "environment_ref": lock_ref, "archive_ref": bundle_ref,
        "files": [{"path": path, "artifact_ref": store.put_blob(path.encode()), "media_type": "text/plain",
                   "audience": "authorized researcher"} for path in ("requirements.txt", "poc_patch.py", "run_benchmark.py")],
        "dependencies": []}
    # The capsule consumes this bound record; only the three archive names are
    # needed for execution identity here because archive admission is upstream.
    manifest_ref = store.put_record("poc-manifest", manifest)
    ready = _ready_receipt(manifest_ref, bundle_ref, blueprint_ref, lock_ref, store)
    ready_ref = store.put_record("urn:ai4r:prediction-build-receipt:4.0.0", ready)
    inputs = {"hypothesis_blueprint": blueprint, "poc_manifest": manifest, "build_receipt": ready,
        "environment_lock": lock, "baseline_resource": store.read_record(task["builder_inputs"]["baseline_resource"]),
        "validation_resource": store.read_record(task["builder_inputs"]["validation_resource"]),
        "poc_artifact_bundle": bundle_ref,
        "environment_lock_ref": lock_ref, "poc_manifest_ref": manifest_ref}
    refs = {"hypothesis_blueprint": blueprint_ref, "poc_manifest": manifest_ref,
        "build_receipt": ready_ref, "environment_lock": lock_ref,
        "baseline_resource": task["builder_inputs"]["baseline_resource"],
        "validation_resource": task["builder_inputs"]["validation_resource"],
        "poc_artifact_bundle": bundle_ref}
    contract = {"run_id": "run-pi", "node_id": "benchmark", "attempt_id": "attempt-pi",
        "inputs": [{"name": key, "artifact_refs": [ref]} for key, ref in refs.items()],
        "subnode_limits": {"time_s": 3600, "memory_mb": 256},
        "bindings": [{"limits": {"time_s": 3600, "memory_mb": 256}}]}
    context = _ExecutionContext(store, _ControlledExecutor(store,
        {"id": "benchmark-contract", "sha256": "e" * 64}, incorrect=incorrect,
        wrong_digits=wrong_digits, failed=failed), contract, inputs, refs)
    try:
        produced_outputs = await execute(context, inputs)
    except Exception:
        store.close()
        raise
    outputs, output_refs = {}, {}
    for name, artifact in produced_outputs.items():
        value = json.loads(artifact.data)
        outputs[name] = value
        output_refs[name] = store.put_blob(artifact.data)
    check_context = CheckContext(contract, store, inputs, outputs, output_refs,
        {"contract_ref": context.contract_ref, "trace_refs": []})
    checker = PiBenchmarkChecks()
    return store, outputs, check_context, checker


@pytest.mark.asyncio
async def test_pi_benchmark_capsule_and_checker_end_to_end(tmp_path, monkeypatch):
    store, outputs, check_ctx, checker = await _run_benchmark(tmp_path, monkeypatch)
    try:
        await checker._benchmark(check_ctx, check_ctx.inputs, check_ctx.outputs)
        from jiuwenswarm.research.checks.benchmark_dispatch import BenchmarkDispatchChecks
        results=await BenchmarkDispatchChecks()(check_ctx,check_ctx.inputs,check_ctx.outputs)
        assert results and all(row['outcome']=='PASS' for row in results),results
        payload = outputs["benchmark_payload"]
        assert len(payload["cases"]) == 9
        assert all(measurement["correct"] is True for case in payload["cases"]
                   for role, measurement in case.items() if role in {"baseline", "treatment"})
        assert payload["speedup"] == 2.0
    finally:
        store.close()


@pytest.mark.asyncio
async def test_pi_benchmark_checker_rejects_forged_median(tmp_path, monkeypatch):
    store, outputs, check_ctx, checker = await _run_benchmark(tmp_path, monkeypatch)
    try:
        outputs["benchmark_payload"]["cases"][0]["treatment"]["median"] += 0.5
        with pytest.raises(CheckError):
            await checker._benchmark(check_ctx, check_ctx.inputs, check_ctx.outputs)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_pi_benchmark_preserves_negative_and_fails_closed_on_bad_score(tmp_path, monkeypatch):
    store, outputs, check_ctx, checker = await _run_benchmark(tmp_path, monkeypatch,
        incorrect=("pi-10000", "treatment", 0), failed=("pi-boundary-2", "treatment", 0))
    try:
        await checker._benchmark(check_ctx, check_ctx.inputs, check_ctx.outputs)
        assert outputs["benchmark_payload"]["cases"][0]["treatment"]["correct"] is False
        assert next(run for run in outputs["execution_receipt"]["runs"] if run["sequence"] == 26)["exit_code"] == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_pi_benchmark_rejects_score_for_another_precision(tmp_path, monkeypatch):
    with pytest.raises(ResearchError, match="pi_score_mismatch"):
        await _run_benchmark(tmp_path, monkeypatch,
            wrong_digits=("pi-10000", "baseline", 0))


@pytest.mark.asyncio
async def test_pi_benchmark_checker_rejects_unproved_isolation(tmp_path, monkeypatch):
    store, _outputs, check_ctx, checker = await _run_benchmark(tmp_path, monkeypatch)
    try:
        raw_records = list(store.iter_records(run_id=check_ctx.contract["run_id"], kinds=("scientific_execution",)))
        proof_ref = raw_records[0]["record"]["receipt"]["observed_limits"]["isolation_probe_ref"]
        original_read_record = store.read_record

        def reject_probe(ref, **kwargs):
            proof = original_read_record(ref, **kwargs)
            if ref == proof_ref:
                return dict(proof, ready=False)
            return proof

        monkeypatch.setattr(store, "read_record", reject_probe)
        with pytest.raises(CheckError):
            await checker._benchmark(check_ctx, check_ctx.inputs, check_ctx.outputs)
    finally:
        store.close()
