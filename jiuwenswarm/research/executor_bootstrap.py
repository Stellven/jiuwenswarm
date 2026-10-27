"""Literal core scientific runtime factory from protected captured resources."""
from __future__ import annotations
import asyncio
import copy
import json
import os
import stat
import sys
import time
from dataclasses import replace
from pathlib import Path

from .builder_mode import builder_mode

from .contracts import validate
from .executor import ExecutorBlocked, InvocationBinding, RestrictedExecutor
from .execution_jobs import ApprovedEnvironment, ScienceExecutionAdapter, ScienceProfile, allocate_science_workspace
from .hardware import SameSandboxHardwareCapture
from .science_runtime import decode_science_runtime_record


def _locator(path, *, expected_uid=0):
    supplied = Path(path)
    if not supplied.is_absolute() or any(p.is_symlink() for p in (supplied, *supplied.parents)):
        raise ExecutorBlocked("SCIENCE_BINDING_CUSTODY_INVALID")
    descriptor = os.open(supplied, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != expected_uid or metadata.st_nlink != 1
                or metadata.st_mode & 0o022 or not 0 < metadata.st_size <= 65536):
            raise ExecutorBlocked("SCIENCE_BINDING_CUSTODY_INVALID")
        raw = stream.read(65537)
        after = os.fstat(stream.fileno())
        current = supplied.lstat()
        stable = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_uid', 'st_nlink', 'st_mode')
        if (len(raw) != metadata.st_size or any(getattr(after, key) != getattr(metadata, key) for key in stable)
                or (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)):
            raise ExecutorBlocked("SCIENCE_BINDING_CUSTODY_INVALID")
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"binding_ref"}:
        raise ExecutorBlocked("SCIENCE_BINDING_INVALID")
    validate("Ref", data["binding_ref"])
    return data["binding_ref"]


def decode_inputs(store, contract):
    values, refs = {}, []
    for port in contract["inputs"]:
        decoded = []
        for ref in port["artifact_refs"]:
            refs.append(ref)
            raw = store.read_blob(ref)
            if port["contract_id"] in {"opaque-bytes", "text/plain", "poc-artifact-bundle", "poc-artifact-bundle:field-contract:1", "research-report", "research-report:field-contract:1"}:
                value = raw
            else:
                value = json.loads(raw.decode("utf-8"))
                validate(port["contract_id"], value)
            decoded.append(value)
        if port["required"] and not decoded or port["name"] in values:
            raise ExecutorBlocked("CAPTURED_EXECUTOR_INPUT_INVALID")
        values[port["name"]] = decoded[0] if len(decoded) == 1 else decoded
    if refs != contract["input_refs"]:
        raise ExecutorBlocked("CAPTURED_EXECUTOR_INPUT_INVENTORY_INVALID")
    return values


def create_scientific_backend(*, store, authorize, environ, authorize_builder=None):
    locator = environ.get("JIUWENSWARM_M1_SCIENCE_BINDINGS")
    if locator:
        runtime_ref = _locator(locator)
    elif environ.get('JIUWENSWARM_M1_LOCAL_RESEARCH') == '1':
        # Explicit local operator capture uses the product writer. This fixed
        # location supplies data only: all build, admission, policy, resource
        # and per-invocation joins are rechecked by the root registration.
        config = Path(environ.get('JIUWENSWARM_M1_CONFIG', ''))
        if not config.is_absolute() or not config.is_relative_to('/var/lib/ai4r/operator'):
            return None
        local_locator = config.with_name('science.json')
        if not local_locator.exists():
            return None
        runtime_ref = _locator(local_locator, expected_uid=10001)
    else:
        return None
    if store.record_kind(runtime_ref) != 'science-runtime':
        raise ExecutorBlocked('ORIGINAL_SCIENCE_RUNTIME_REQUIRED')
    record = decode_science_runtime_record(store.read_record(runtime_ref)).record
    from .native_ports import verify_installed_build
    actual = verify_installed_build()
    if record["build_id"] != actual:
        raise ExecutorBlocked("SCIENCE_BUILD_QUALIFICATION_MISMATCH")
    profile = record["profile"]
    fields = {"asset_root", "environment_root", "memory_mb", "pids_max", "run_timeout_s", "provision_timeout_s",
              "baseline_arguments", "treatment_arguments", "uv_path", "python_path"}
    if not isinstance(profile, dict) or set(profile) != fields or type(record["gpu_required"]) is not bool:
        raise ExecutorBlocked("SCIENCE_PROFILE_INVALID")
    base = Path("/var/lib/ai4r-executor")
    expected = {"asset_root": base / "assets", "environment_root": base / "environments",
                "uv_path": Path("/usr/local/bin/uv"), "python_path": Path(sys._base_executable)}
    for key, path in expected.items():
        if Path(profile[key]) != path or path.is_symlink() and key.endswith("root"):
            raise ExecutorBlocked("SCIENCE_PROFILE_PATH_INVALID")
    for key in ("baseline_arguments", "treatment_arguments"):
        if not isinstance(profile[key], list) or any(not isinstance(s, str) or "\x00" in s for s in profile[key]):
            raise ExecutorBlocked("SCIENCE_ARGUMENT_PROFILE_INVALID")
    entries = []
    if not isinstance(record["approved_environments"], list):
        raise ExecutorBlocked("SCIENCE_ENVIRONMENT_CATALOG_INVALID")
    for entry in record["approved_environments"]:
        if set(entry) != {"lock_ref", "approval_ref", "platform_fact", "wheel_filenames"}:
            raise ExecutorBlocked("SCIENCE_ENVIRONMENT_CATALOG_INVALID")
        for key in ("lock_ref", "approval_ref"):
            validate("Ref", entry[key])
            store.read_blob(entry[key])
        if (not isinstance(entry["platform_fact"], list) or len(entry["platform_fact"]) != 3
                or not all(isinstance(s, str) and s for s in entry["platform_fact"])
                or not isinstance(entry["wheel_filenames"], dict)):
            raise ExecutorBlocked("SCIENCE_ENVIRONMENT_CATALOG_INVALID")
        entries.append(ApprovedEnvironment(entry["lock_ref"], entry["approval_ref"], tuple(entry["platform_fact"]), entry["wheel_filenames"]))
    if len({entry.lock_ref["sha256"] for entry in entries}) != len(entries):
        raise ExecutorBlocked("SCIENCE_ENVIRONMENT_CATALOG_INVALID")
    for name in ("assets", "environments", "work"):
        path = base / name
        try:
            path.mkdir(mode=0o711)
        except FileExistsError:
            pass  # Existing custody/mode must still match; never repair it.
        else:
            # The production entrypoint deliberately retains umask 077.
            # Set traversal on only this newly created root-owned directory.
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                metadata = os.fstat(descriptor)
                if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
                    raise ExecutorBlocked("SCIENCE_PREPARATION_CUSTODY_INVALID")
                os.fchmod(descriptor, 0o711)
            finally:
                os.close(descriptor)
        if path.is_symlink() or path.stat().st_uid != 0 or stat.S_IMODE(path.stat().st_mode) != 0o711:
            raise ExecutorBlocked("SCIENCE_PREPARATION_CUSTODY_INVALID")
    values = {key: Path(value) if key in expected else tuple(value) if key.endswith("arguments") else value for key, value in profile.items()}
    science_profile = ScienceProfile(**values)
    issued, bindings = {}, {}

    async def authorize_binding(binding):
        if not isinstance(binding, InvocationBinding):
            raise ExecutorBlocked("PROTECTED_INVOCATION_BINDING_REQUIRED")
        response = await authorize({"contract_ref": binding.contract_ref, "invocation_id": binding.invocation_id,
                                    "execution_id": binding.execution_id})
        if (response.get("contract") != binding.contract or response.get("contract_ref") != binding.contract_ref
                or response.get("invocation_id") != binding.invocation_id or response.get("execution_id") != binding.execution_id):
            raise ExecutorBlocked("PROTECTED_INVOCATION_BINDING_MISMATCH")
        from .evaluation_executor import EvaluationExecutorAdapter
        private = EvaluationExecutorAdapter(store, executor)
        if private.is_private_reference(binding.contract_ref):
            private.validate_binding({"contract_ref": binding.contract_ref, "invocation_id": binding.invocation_id,
                "execution_id": binding.execution_id}, response)
        deadline = response.get("execution_deadline_monotonic_s")
        if type(deadline) not in (int, float) or deadline <= time.monotonic():
            raise ExecutorBlocked("PROTECTED_INVOCATION_DEADLINE_UNAVAILABLE")
        bindings[binding.invocation_id] = (copy.deepcopy(binding), deadline)
        return binding

    async def authorize_job(job):
        original, binding = issued.get(job.job_id, (None, None))
        if original != job:
            raise ExecutorBlocked("UNISSUED_EXECUTION_JOB")
        await authorize_binding(binding)
        return replace(job, timeout_s=min(job.timeout_s, bindings[binding.invocation_id][1] - time.monotonic()))

    async def authorize_provisioning(job, *, binding):
        await authorize_binding(binding)
        return job

    executor = RestrictedExecutor(workspace_root=base / "work", cgroup_root=environ.get("AI4R_EXECUTOR_CGROUP_ROOT"),
        authorize_job=authorize_job, capture=store.put_blob, allowed_asset_roots=[base / "assets"],
        execution_mode=record.get("execution_mode", "restricted"),runtime_ref=runtime_ref,
        preparation_roots=[base / "environments"], authorize_provisioning=authorize_provisioning)
    hardware = SameSandboxHardwareCapture(store, executor, authorize_binding=authorize_binding, gpu_required=record["gpu_required"])
    async def capture_hardware(binding, **options):
        await authorize_binding(binding)
        options["timeout_s"] = min(options["timeout_s"], bindings[binding.invocation_id][1] - time.monotonic())
        return await hardware(binding, **options)
    async def provision(job, *, binding):
        await authorize_binding(binding)
        bounded = replace(job, timeout_s=min(job.timeout_s, bindings[binding.invocation_id][1] - time.monotonic()))
        return await executor.run_provisioning(bounded, binding=binding)
    scorer = None
    if (record.get('scoring_profile') or {}).get('protocol') == 'ai4r-blind-classification:1':
        from .trusted_scoring import RootClassificationScorer
        scorer = RootClassificationScorer(store, record['scoring_profile'])
    elif (record.get('scoring_profile') or {}).get('protocol') == 'ai4r-pi:1':
        from .trusted_pi import RootPiScorer
        scorer = RootPiScorer(store, record['scoring_profile'])
    adapter = ScienceExecutionAdapter(store, science_profile, approved_environments=entries,
        workspace_allocator=lambda binding, sequence, role: allocate_science_workspace(base / "work", binding, sequence, role),
        hardware_capture=capture_hardware, provision_runner=provision, scorer=scorer)
    adapter.runtime_ref = runtime_ref
    def capture_process(receipt):
        child=store.read_record(receipt['contract_ref'])
        return store.append_record('m1_process_execution',dict(run_id=child['run_id'],
            job_id=receipt['job_id'],contract_ref=receipt['contract_ref'],invocation_id=receipt['invocation_id'],
            runtime_ref=runtime_ref,receipt=receipt))
    executor.process_receipt_capture = capture_process
    async def job_factory(contract, inputs, *, binding, **selection):
        await authorize_binding(binding)
        job = await adapter.job_factory(contract, inputs, binding=binding, **selection)
        issued[job.job_id] = (copy.deepcopy(job), copy.deepcopy(binding))
        return job
    executor.job_factory = job_factory
    executor.provisioner = adapter.provisioner
    executor.hardware_probe = adapter.hardware_probe
    executor.verify_mount = adapter.verify_mount
    executor.environment_verifier = adapter.environment_verifier
    executor.score_result = adapter.score_result
    executor.read_blob = store.read_blob
    from .builder_testing import BuilderTestService
    def register_builder_job(job, binding):
        issued[job.job_id] = (copy.deepcopy(job), copy.deepcopy(binding))
    executor.builder_test_service = BuilderTestService(store, adapter, executor,
        authorize_binding, register_builder_job)
    from .builder_agent_host import BuilderAgentHost
    executor.builder_agent_service = BuilderAgentHost(store, adapter, executor,
        authorize_binding, register_builder_job)
    executor.builder_input_resolver = lambda contract: decode_inputs(store, contract)
    executor.tool_free_builder = False
    executor.builder_test_required = False
    for mapping in record['execution_bindings']:
        declared = store.read_record(mapping['declaration_ref'], contract_id='capsule-declaration')
        if (declared['identity']['name'] == 'research.builder'
                and builder_mode(declared) != 'legacy'):
            from .capsules.assets import load_research_catalog
            authored = load_research_catalog()['stages']['builder']
            if mapping['declaration_ref'] != authored['declaration_ref']:
                raise ExecutorBlocked('TOOL_FREE_BUILDER_RELEASE_MISMATCH')
            admitted = store.read_record(mapping['admission_ref'], contract_id='library-admission')
            if admitted['status'] != 'admitted' or admitted['candidate_ref'] != mapping['declaration_ref']:
                raise ExecutorBlocked('TOOL_FREE_BUILDER_ADMISSION_REQUIRED')
            executor.tool_free_builder = True
            executor.builder_test_required = builder_mode(declared) == 'loop'
            if executor.builder_test_required and mapping['operations'] != ['builder_test']:
                raise ExecutorBlocked('BUILDER_TEST_OPERATION_MAPPING_REQUIRED')
            if builder_mode(declared) == 'agent':
                executor.builder_agent_required = True
                if mapping['operations'] != ['builder_action']:
                    raise ExecutorBlocked('BUILDER_AGENT_OPERATION_MAPPING_REQUIRED')
    if authorize_builder is not None:
        from .builder_launcher import create_builder_launcher
        try:
            launcher = create_builder_launcher(store=store, executor=executor, authorize=authorize_builder,
                environ=environ, build_id=actual)
        except (ExecutorBlocked, OSError, ValueError, KeyError):
            # Invalid/missing operational Builder resources constrain Builder
            # readiness, while the native app can still expose diagnostics.
            launcher = None
        executor.builder_launcher = launcher
        if launcher is not None:
            executor.builder_collector = launcher.collect_builder
            executor.builder_observer = launcher.builder_observation
    from .science_registration import install_science_runtime
    install_science_runtime(store=store,backend=executor,runtime_ref=runtime_ref)
    return executor
