"""Real Harbor single-trial native baseline; preparation/probing are effect-free."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

try:
    from harbor.agents.base import BaseAgent
except ImportError:  # Standalone, network-disabled grader needs no Harbor package.
    BaseAgent = object
try:
    from . import comparison
except ImportError:
    import comparison

ADAPTER = "benchmarks.harbor_suite.comparison_harbor:NativeCodexBaselineAgent"
IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:\-]*@sha256:[a-f0-9]{64}$")
PUBLIC_FILES = frozenset({"result.json", "original.txt", "outputs.json"})
EXPORT_FILES = PUBLIC_FILES | {"host-dispatch.json"}


def _source_content_oracle():
    # Standalone frozen graders use the adjacent pinned oracle instead.
    from .contracts import resolve_cases_root
    return resolve_cases_root() / "cc01-transfer" / "oracle.py"


def _regular(path, maximum=32*1024*1024):
    path = Path(path)
    if (not path.is_file() or any(p.is_symlink() for p in (path, *path.parents))
            or path.stat().st_size > maximum):
        raise ValueError("Expected bounded original regular file")
    return path


def _pin(path):
    raw = _regular(path, 256*1024*1024).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _tree_pin(root):
    root = Path(root)
    if not root.is_absolute() or not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("Existing absolute non-symlink control subtree required")
    rows, total = [], 0
    for folder, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name != "__pycache__")
        if any((Path(folder)/name).is_symlink() for name in directories):
            raise ValueError("Symlink in frozen control subtree")
        for name in sorted(names):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = Path(folder)/name
            if name == "auth.json" or ".codex" in path.parts:
                raise ValueError("Authentication storage is not a control subtree")
            pin = _pin(path)
            total += pin["size"]
            if len(rows) >= 10000 or total > 256*1024*1024:
                raise ValueError("Control subtree exceeds finite custody bound")
            rows.append({"path": path.relative_to(root).as_posix(), **pin})
    if not rows:
        raise ValueError("Empty control subtree")
    return {"sha256": comparison.assignment_digest(rows), "files": len(rows), "size": total}


def _metadata(task_root):
    task_root = Path(task_root)
    metadata = comparison._read(_regular(task_root.parent/"baseline-task.json"))
    for name, expected in metadata["files"].items():
        if _pin(task_root/name) != expected:
            raise ValueError("Frozen Harbor baseline task changed")
    return metadata


def prepare_baseline_task(destination, assignment, variant, *, quality_port, python_image,
                          expected_model="gpt-6.1-sol", jobs_dir=None, job_name=None):
    """Freeze one actual Harbor task, separate referee image and CLI job config."""
    comparison.validate_assignment(assignment)
    if quality_port not in assignment["output_contracts"]:
        raise ValueError("Quality port must be declared before observing either answer")
    if not IMAGE.fullmatch(python_image) or expected_model != "gpt-6.1-sol":
        raise ValueError("Digest-pinned image and qualified native model required")
    destination = Path(destination).absolute()
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError("Fresh bundle directory with existing parent required")
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("Non-symlink bundle required")
    digest = comparison.assignment_digest(assignment)
    key = "native-baseline-" + digest[:24]
    instruction = ("NATIVE_CODEX_HARBOR_TASK_KEY: " + key + "\n\n" + comparison.make_prompt(assignment) + "\n").encode()
    metadata = {"schema": "native-codex-harbor-task:1", "task_key": key,
                "assignment_sha256": digest, "quality_port": quality_port,
                "expected_model": expected_model, "instruction_sha256": hashlib.sha256(instruction).hexdigest()}
    config = '''schema_version = "1.4"
artifacts = ["/app/baseline-public"]
[metadata]
classification = "paired_native_codex_development_baseline"
split = "development"
[agent]
timeout_sec = 300.0
[environment]
cpus = 1
memory_mb = 256
storage_mb = 1024
network_mode = "no-network"
[verifier]
timeout_sec = 180.0
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 512
storage_mb = 1024
network_mode = "no-network"
'''
    files = {"instruction.md": instruction, "task.toml": config.encode(),
        "environment/Dockerfile": ("FROM " + python_image + "\nWORKDIR /app\n").encode(),
        "environment/.dockerignore": b"*\n!Dockerfile\n!.dockerignore\n",
        "tests/assignment.json": comparison.canonical(assignment),
        "tests/variant.json": comparison.canonical(variant),
        "tests/task.json": comparison.canonical(metadata),
        "tests/comparison.py": Path(comparison.__file__).read_bytes(),
        "tests/comparison_harbor.py": Path(__file__).read_bytes(),
        "tests/oracle.py": _source_content_oracle().read_bytes(),
        "tests/requirements.txt": b"jsonschema==4.26.0\nreferencing==0.37.0\nattrs==26.1.0\njsonschema-specifications==2025.9.1\nrpds-py==2026.9.1\n",
        "tests/test.sh": b"#!/bin/sh\nset -eu\npython /tests/comparison_harbor.py grade --evidence /app/baseline-public --tests /tests --output /logs/verifier\n"}
    files["tests/Dockerfile"] = ("FROM " + python_image + "\nWORKDIR /tests\n"
        "COPY requirements.txt /tests/requirements.txt\nRUN pip install --no-cache-dir -r /tests/requirements.txt\n"
        "COPY . /tests/\nRUN chmod 0555 /tests/test.sh\n").encode()
    controls = {name.removeprefix("tests/"): {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                for name, raw in files.items() if name.startswith("tests/")}
    files["tests/grader-controls.json"] = comparison.canonical(controls)
    files["tests/.dockerignore"] = ("*\n" + "\n".join("!" + Path(name).name for name in files
                                               if name.startswith("tests/")) + "\n!grader-controls.json\n!.dockerignore\n").encode()
    metadata["files"] = {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                         for name, raw in files.items()}
    task_root = destination/"task"
    task_root.mkdir(parents=True)
    for name, raw in files.items():
        path = task_root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        comparison._write(path, raw, raw=True)
    comparison._write(destination/"baseline-task.json", metadata)
    job = {"job_name": job_name or key, "jobs_dir": str(Path(jobs_dir).absolute()) if jobs_dir else str(destination/"jobs"),
           "n_attempts": 1, "n_concurrent_trials": 1, "retry": {"max_retries": 0},
           "environment": {"type": "docker", "delete": False},
           "agents": [{"name": None, "import_path": ADAPTER, "model_name": expected_model}],
           "tasks": [{"path": str(task_root)}]}
    comparison._write(destination/"job.json", job)
    return metadata


def freeze_host_config(config_path, *, task_root, workspace, command, cwd, public_root,
                       private_control, control_files, control_trees):
    """Freeze explicit host-only argv and custody roots; never execute/probe model."""
    task_root, workspace = Path(task_root).absolute(), Path(workspace).absolute()
    metadata = _metadata(task_root)
    if (not isinstance(command, list) or not command or any(not isinstance(v, str) or not v or "\0" in v for v in command)
            or not Path(command[0]).is_absolute()):
        raise ValueError("Explicit host executable and argv required; no shell string")
    private_control = Path(private_control).absolute()
    if any(part.lower() == "jobs" for part in private_control.parts):
        raise ValueError("Private observer receipts must stay outside Harbor jobs")
    private_control.mkdir(parents=True, exist_ok=True, mode=0o700)
    value = {"schema": "native-codex-harbor-host:1", "task_root": str(task_root),
        "workspace": str(workspace), "command": command, "cwd": str(Path(cwd).absolute()),
        "public_root": str(Path(public_root).absolute()), "private_control": str(private_control),
        "task_sha256": comparison.assignment_digest(metadata),
        "control_files": {str(Path(p).absolute()): _pin(p) for p in control_files},
        "control_trees": {str(Path(p).absolute()): _tree_pin(p) for p in control_trees}}
    if not value["control_files"] or not value["control_trees"] or str(Path(command[0])) not in value["control_files"]:
        raise ValueError("Executable, wrapper/private policy files and implementation subtrees must be pinned")
    # These are effect-owner control files, never copied into the task/container.
    for name in ("assignment.json", "prompt.txt", "frozen.json"):
        value["control_files"][str(workspace/name)] = _pin(workspace/name)
    frozen = comparison._read(workspace/"frozen.json")
    if frozen["assignment_sha256"] != metadata["assignment_sha256"]:
        raise ValueError("Native workspace and Harbor task assignment differ")
    path = Path(config_path).absolute()
    for root in (task_root.parent, Path(value["public_root"]), private_control):
        if path == root or root in path.parents:
            raise ValueError("Host config must remain outside task/public/receipt roots")
    comparison._write(path, value)
    job = comparison._read(task_root.parent/"job.json")
    job["agents"][0]["kwargs"] = {"host_config": str(path), "host_config_sha256": _pin(path)["sha256"]}
    configured_job = task_root.parent/"job-host.json"
    comparison._write(configured_job, job)
    return {**probe_host_config(path), "job_config": str(configured_job)}


def load_host_config(path):
    value = comparison._read(_regular(path))
    if value.get("schema") != "native-codex-harbor-host:1":
        raise ValueError("Wrong native baseline host configuration")
    for key in ("task_root", "workspace", "cwd", "public_root", "private_control"):
        root = Path(value[key])
        if not root.is_absolute() or not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError("Existing absolute non-symlink host directory required")
    metadata = _metadata(value["task_root"])
    if comparison.assignment_digest(metadata) != value["task_sha256"]:
        raise ValueError("Frozen task identity changed")
    for source, frozen_name in ((Path(__file__), "tests/comparison_harbor.py"),
                                (Path(comparison.__file__), "tests/comparison.py")):
        if _pin(source) != metadata["files"][frozen_name]:
            raise ValueError("Live controller differs from the frozen task implementation")
    for path, expected in value["control_files"].items():
        if Path(path).name == "auth.json" or _pin(path) != expected:
            raise ValueError("Frozen native baseline command file changed")
    for root, expected in value["control_trees"].items():
        if _tree_pin(root) != expected:
            raise ValueError("Frozen native baseline implementation subtree changed")
    command = value["command"]
    if (not isinstance(command, list) or not command or not Path(command[0]).is_absolute()
            or str(Path(command[0])) not in value["control_files"]):
        raise ValueError("Unpinned native baseline executable")
    for argument in command:
        candidate = Path(argument)
        if candidate.is_absolute() and candidate.is_file() and str(candidate) not in value["control_files"]:
            raise ValueError("Unpinned executable file argument")
    workspace = Path(value["workspace"])
    if Path(value["public_root"]).resolve() != (workspace/"public").resolve():
        raise ValueError("Only the prepared baseline workspace public directory may be uploaded")
    assignment = comparison._read(workspace/"assignment.json")
    if comparison.assignment_digest(assignment) != metadata["assignment_sha256"]:
        raise ValueError("Frozen assignment differs across native/Harbor namespaces")
    value["metadata"] = metadata
    value["config_sha256"] = _pin(path)["sha256"]
    return value


def probe_host_config(path):
    """Read-only custody validation, with no subprocess/authentication request."""
    value = load_host_config(path)
    return {"ready": True, "task_key": value["metadata"]["task_key"],
            "assignment_sha256": value["metadata"]["assignment_sha256"], "effect_performed": False}


def _export_public(config, dispatch):
    root = Path(config["public_root"])
    files = list(root.iterdir())
    if any(p.name not in PUBLIC_FILES or not p.is_file() or p.is_symlink() for p in files):
        raise ValueError("Unexpected file in native baseline public output")
    comparison._write(root/"host-dispatch.json", dispatch)
    inventory = {p.name: _pin(p) for p in sorted(root.iterdir())}
    if sum(p["size"] for p in inventory.values()) > 8*1024*1024:
        raise ValueError("Public baseline output exceeds finite bound")
    comparison._write(root/"public-inventory.json", {"schema": "native-baseline-public-inventory:1",
        "assignment_sha256": config["metadata"]["assignment_sha256"], "files": inventory})
    return root


class NativeCodexBaselineAgent(BaseAgent):
    def __init__(self, *args, host_config=None, host_config_sha256=None, **kwargs):
        self._host_path = host_config
        self._host_sha256 = host_config_sha256
        super().__init__(*args, **kwargs)

    @staticmethod
    def name():
        return "native-codex-tool-free-baseline"

    def version(self):
        return "1"

    async def setup(self, environment):
        self._host_path = self._host_path or os.environ.get("AI4R_HARBOR_COMPARISON_CONFIG")
        self._host_sha256 = self._host_sha256 or os.environ.get("AI4R_HARBOR_COMPARISON_CONFIG_SHA256")
        if not self._host_path or not self._host_sha256 or _pin(self._host_path)["sha256"] != self._host_sha256:
            raise ValueError("Exact pinned host-only baseline config is required")
        self._config = load_host_config(self._host_path)

    async def run(self, instruction, environment, context):
        if _pin(self._host_path)["sha256"] != self._host_sha256:
            raise ValueError("Host baseline argv/config changed after task configuration")
        config = load_host_config(self._host_path)
        expected = (Path(config["task_root"])/"instruction.md").read_bytes()
        if instruction.encode("utf-8") != expected:
            raise ValueError("Exact frozen native baseline instruction required")
        if list(Path(config["public_root"]).iterdir()):
            raise ValueError("Native baseline public directory must be empty before dispatch")
        control = Path(config["private_control"])
        claim = control/("harbor-dispatch-" + config["config_sha256"] + ".json")
        comparison._write(claim, {"schema": "native-baseline-harbor-claim:1",
            "config_sha256": config["config_sha256"], "task_key": config["metadata"]["task_key"],
            "trial_identity": str(Path(self.logs_dir).resolve())})
        dispatch = {"schema": "native-baseline-host-dispatch:1", "status": "delivery_unknown",
                    "returncode": None, "assignment_sha256": config["metadata"]["assignment_sha256"]}
        process = None
        cancelled = None
        # stdout/stderr stay private, including startup errors and native diagnostics.
        with (control/(claim.stem+".stdout")).open("xb") as stdout, (control/(claim.stem+".stderr")).open("xb") as stderr:
            try:
                process = await asyncio.create_subprocess_exec(*config["command"], cwd=config["cwd"], stdout=stdout, stderr=stderr)
                dispatch["returncode"] = await asyncio.wait_for(process.wait(), timeout=180)
                dispatch["status"] = "observer_returned"
            except (asyncio.CancelledError, TimeoutError) as exc:
                cancelled = exc
                dispatch["status"] = "observer_interrupted_outcome_unknown"
                if process is not None and process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=10)
                    except TimeoutError:
                        process.kill()
                        await process.wait()
            except OSError:
                dispatch["status"] = "host_command_start_failed"
        public = _export_public(config, dispatch)
        await environment.upload_dir(source_dir=public, target_dir="/app/baseline-public")
        result_path = public/"result.json"
        report = comparison._read(result_path) if result_path.exists() else {}
        usage = report.get("usage") or {}
        context.n_input_tokens = usage.get("input_tokens")
        context.n_output_tokens = usage.get("output_tokens")
        context.cost_usd = report.get("cost_usd")
        context.metadata = {"arm": "native_codex_tool_free", "host_dispatch": dispatch,
                            "native_provenance": "Private receipt validated by host owner; operator audit required."}
        if cancelled is not None:
            raise cancelled


def grade_public(evidence, assignment, variant, *, quality_port, expected_model="gpt-6.1-sol", oracle=None):
    """Recompute transport consistency, strict format and common content only."""
    root = Path(evidence)
    comparison.validate_assignment(assignment)
    checks, report, outputs = [], {}, None
    integrity = False
    try:
        inventory = comparison._read(_regular(root/"public-inventory.json"))
        if inventory.get("assignment_sha256") != comparison.assignment_digest(assignment):
            raise ValueError("Public inventory assignment differs")
        files = inventory["files"]
        actual = {p.name for p in root.iterdir()}
        if not set(files) <= EXPORT_FILES or actual != set(files)|{"public-inventory.json"}:
            raise ValueError("Unexpected public artifact inventory")
        for name, expected in files.items():
            if _pin(root/name) != expected:
                raise ValueError("Public original bytes changed")
        report = comparison._read(_regular(root/"result.json"))
        if report.get("assignment_sha256") != comparison.assignment_digest(assignment):
            raise ValueError("Public result assignment differs")
        text_path = root/"original.txt"
        if text_path.exists():
            text = _regular(text_path).read_bytes().decode("utf-8")
            try:
                outputs = comparison._loads(text)
            except ValueError:
                if report.get("outputs") is not None or (root/"outputs.json").exists():
                    raise ValueError("Parsed output exists for invalid original JSON")
            else:
                if report.get("status") == "completed":
                    if report.get("outputs") != outputs or comparison._read(_regular(root/"outputs.json")) != outputs:
                        raise ValueError("Parsed outputs differ from exact original answer")
                else:
                    if report.get("outputs") is not None or (root/"outputs.json").exists():
                        raise ValueError("Noncompleted native result published parsed outputs")
                    outputs = None
        elif report.get("status") == "completed":
            raise ValueError("Completed result has no original answer")
        integrity = True
        checks.append({"id": "public-artifact-consistency", "status": "pass"})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        checks.append({"id": "public-artifact-consistency", "status": "unavailable" if not report else "fail",
                       "reason": type(exc).__name__})
    quality, formatting = None, comparison.check_format(outputs, assignment["output_contracts"])
    if integrity and report.get("status") == "completed" and isinstance(outputs, dict) and isinstance(outputs.get(quality_port), dict):
        if oracle is None:
            oracle_path = Path(__file__).with_name("oracle.py")
            if not oracle_path.is_file():
                oracle_path = _source_content_oracle()
            spec = importlib.util.spec_from_file_location("baseline_content_oracle", oracle_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            oracle = module.evaluate_content
        quality = oracle(outputs[quality_port], variant)
    content = int(bool(quality and quality.get("metrics", {}).get("deterministic_content_success") == 1))
    return {"schema": "native-baseline-harbor-assessment:1", "arm": "native_codex_tool_free",
        "assignment_sha256": comparison.assignment_digest(assignment), "status": report.get("status", "unavailable"),
        "checks": checks, "format": formatting, "content": quality,
        "rewards": {"content_success": content, "format_success": int(integrity and formatting["valid"]),
                    "public_artifact_integrity": int(integrity)},
        "binding_requirement": "not_applicable_to_plain_native_baseline",
        "native_provenance": {"independently_verified_by_grader": False,
            "scope": "Public artifact consistency only. Private native receipts require independent operator audit."},
        "expected_model": expected_model, "reported_effective_model": report.get("effective_model")}


def _write_public_result(path, value):
    """Publish grader results readable by the separate Harbor controller UID.

    Native receipts and controller claims still use comparison._write(0600).
    Set the public mode explicitly, including under a restrictive container umask.
    """
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        if os.name == "posix":
            os.fchmod(stream.fileno(), 0o644)
        else:
            os.chmod(path, 0o644)
        stream.write(comparison.canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    comparison._sync_directory(path.parent)


def grade(evidence, tests, output):
    tests, output = Path(tests), Path(output)
    controls = comparison._read(_regular(tests/"grader-controls.json"))
    for name, expected in controls.items():
        if _pin(tests/name) != expected:
            raise ValueError("Frozen independent grader control changed")
    metadata = comparison._read(tests/"task.json")
    spec = importlib.util.spec_from_file_location("frozen_baseline_content_oracle", tests/"oracle.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    result = grade_public(evidence, comparison._read(tests/"assignment.json"),
        comparison._read(tests/"variant.json"), quality_port=metadata["quality_port"],
        expected_model=metadata["expected_model"], oracle=oracle.evaluate_content)
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o755)
    _write_public_result(output/"assessment.json", result)
    _write_public_result(output/"reward.json", result["rewards"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("probe")
    check.add_argument("--config", required=True, type=Path)
    grading = sub.add_parser("grade")
    for option in ("evidence", "tests", "output"):
        grading.add_argument("--"+option, required=True, type=Path)
    args = parser.parse_args()
    result = probe_host_config(args.config) if args.command == "probe" else grade(args.evidence, args.tests, args.output)
    print(json.dumps(result if args.command == "probe" else result["rewards"]))


if __name__ == "__main__":
    main()
