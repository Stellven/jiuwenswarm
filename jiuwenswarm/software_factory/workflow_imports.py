"""Acquire pinned OSS sources and expose executable, inspectable workflow bundles.

The upstream repositories do not claim to contain factory workflows.  The
wrappers and agent instructions below are factory-owned and say so explicitly.
Source evidence is obtained from the clean acquired checkout, never invented by
the Library UI or copied from an earlier execution trace.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Callable


STRATA_PIN = "13eedf552417a6a791a7d13c6597e24300ee3a09"
PROJECTS = {
    "https://github.com/niko1221/strata": ("strata", "STRATA", STRATA_PIN),
    "https://github.com/google/googletest": ("googletest", "GoogleTest", "v1.17.0"),
}
PROMPTS = Path(__file__).with_name("workflow_prompts")
MODULE = "jiuwenswarm.software_factory.library_operations:"

# These are paths the real wrappers/prompt declare. They are not observations
# that a future execution has already produced those files.
ARTIFACT_PATHS = {
    "source.algorithm": "extracted/core_ir.json",
    "source.project": "project-manifest.json",
    "source.cpp": "strata_native/src/strata_core.cpp",
    "analysis.report": "source-analysis.md",
    "delivery.source_zip": "huawei_native_strata.zip",
    "test.framework": "framework-manifest.json",
    "source.tests": "generated_reference_tests.cpp",
    "verification.report": "verification.json",
}


def _json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return path


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _command(argv: list[str], *, cwd: Path | None, emit: Callable, log: list[dict], timeout: int = 240):
    emit("import.command.started", {"argv": argv, "cwd": str(cwd) if cwd else None})
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    record = {"argv": argv, "cwd": str(cwd) if cwd else None,
              "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    log.append(record)
    for stream in ("stdout", "stderr"):
        if record[stream]:
            emit("import.command.output", {"argv": argv, "stream": stream, "text": record[stream]})
    emit("import.command.completed", {"argv": argv, "returncode": result.returncode})
    if result.returncode:
        raise RuntimeError(f"Source acquisition command failed ({result.returncode}): {argv!r}\n{result.stderr}")
    return result.stdout.strip()


def _evidence(checkout: Path, relative: str, symbol: str | None = None) -> dict:
    path = (checkout / relative).resolve(strict=True)
    if not path.is_relative_to(checkout.resolve()):
        raise ValueError("Source evidence escapes checkout")
    data = path.read_bytes()
    text = data.decode("utf-8-sig")
    lines = text.splitlines()
    line = next((index + 1 for index, content in enumerate(lines) if symbol and symbol in content), 1)
    return {"path": relative, "absolute_path": str(path), "sha256": _digest(data),
            "line": line, "end_line": min(len(lines), line + 35), "symbol": symbol,
            "excerpt": "\n".join(lines[line - 1:min(len(lines), line + 35)])}


def _port(kind: str, required: bool = True) -> dict:
    result = {"semantic_type": kind, "required": required, "transport": "file"}
    fields = {
        "source.algorithm": {"schema": {"const": "strata.core.ir.v1"}, "source_dir": {"type": "string"},
                             "commit_sha": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
                             "kernels": {"type": "object", "minProperties": 1},
                             "selected": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
        "source.project": {"schema": {"const": "factory.source-project.v1"}, "source_dir": {"type": "string"},
                           "files": {"type": "object", "minProperties": 3, "additionalProperties": {"type": "string"}},
                           "selected": {"type": "array", "minItems": 1}},
        "test.framework": {"schema": {"const": "factory.test-framework.v1"}, "revision": {"type": "string"},
                           "include_dir": {"type": "string"}, "source_dir": {"type": "string"},
                           "headers": {"type": "object", "minProperties": 1},
                           "libraries": {"type": "object", "required": ["gtest", "gtest_main"]}},
        "verification.report": {"schema": {"const": "factory.verification.v1"}, "status": {"const": "verified"},
                                "backend": {"const": "CPU"}, "test_count": {"type": "integer", "minimum": 3},
                                "project_sha256": {"type": "string"}, "tests": {"type": "object"}},
    }.get(kind)
    if fields:
        result.update(format="json", json_schema={"type": "object", "required": list(fields), "properties": fields})
    return result


def _part(identifier: str, name: str, *, inputs=None, outputs=None, function=None,
          prompt=None, defaults=None, evidence=None, purpose="", tools=None) -> dict:
    implementation = ({"type": "agent", "prompt_path": str(PROMPTS / prompt)} if prompt else
                      {"type": "python", "entrypoint": MODULE + function})
    if prompt:
        implementation["prompt_sha256"] = _digest((PROMPTS / prompt).read_bytes())
    else:
        implementation["source_path"] = str(Path(__file__).with_name("library_operations.py"))
        implementation["source_sha256"] = _digest(Path(implementation["source_path"]).read_bytes())
    declared_tools = tools or ["python"]
    capabilities = [tool for tool in declared_tools if tool in {"configured agent", "filesystem"}]
    executables = [tool for tool in declared_tools if tool not in capabilities]
    result = {"id": identifier, "name": name, "purpose": purpose,
            "inputs": inputs or {}, "outputs": outputs or {}, "implementation": implementation,
            "default_parameters": defaults or {}, "source_evidence": evidence or [],
            "provenance": {"origin_kind": "factory_wrapper", "upstream_is_workflow": False},
            "requirements": {"tools": declared_tools, "executables": executables,
                             "capabilities": capabilities, "environment": "local host; no device access"},
            "verification": {"method": "Inspect real output bytes, recorded commands and downstream consumption",
                             "native_device_validation": False, "full_model_validation": False}}
    mapping = {"source_evidence": [{key: row.get(key) for key in ("path", "symbol", "line", "end_line", "sha256")}
                                   for row in evidence or []],
               "implementation": {"type": implementation["type"]}, "inputs": [], "outputs": [],
               "provenance": "Factory-owned wrapper; upstream files are source evidence, not upstream workflow declarations"}
    if prompt:
        instruction = Path(implementation["prompt_path"])
        mapping["implementation"].update(path=str(instruction), line=1,
                                          end_line=len(instruction.read_text().splitlines()),
                                          sha256=implementation["prompt_sha256"], technical_form="Agent-executed Markdown instruction")
    else:
        import inspect
        from . import library_operations
        implementation_lines, first_line = inspect.getsourcelines(getattr(library_operations, function))
        mapping["implementation"].update(entrypoint=implementation["entrypoint"], path=implementation["source_path"],
                                          line=first_line, end_line=first_line + len(implementation_lines) - 1,
                                          sha256=implementation["source_sha256"], technical_form="Python callable")
    for side in ("inputs", "outputs"):
        for port, contract in result[side].items():
            mapping[side].append({"port": port, "semantic_type": contract["semantic_type"],
                                  "expected_filename": ARTIFACT_PATHS.get(contract["semantic_type"]),
                                  "filename_basis": "Declared by the real wrapper or Agent instruction",
                                  "production_observed": False})
    result["inspection"] = mapping
    return result


def validate_composition(parts: list[dict], supplied: dict) -> dict:
    """Validate a factory-owned parent definition, independently of display order.

    This checks definition bindings. It does not dispatch a parent or claim a
    runtime success. The executor currently dispatches selected callable parts.
    """
    if not isinstance(supplied, dict) or not isinstance(parts, list) or not parts:
        raise ValueError("Parent composition and callable part definitions must be objects/lists")
    if not all(isinstance(part, dict) and isinstance(part.get("id"), str)
               and isinstance(part.get("inputs"), dict) and isinstance(part.get("outputs"), dict)
               for part in parts):
        raise ValueError("Parent composition callable parts require named input/output contracts")
    if not all(isinstance(contract, dict) and isinstance(contract.get("semantic_type"), str)
               for part in parts for side in ("inputs", "outputs") for contract in part[side].values()):
        raise ValueError("Parent composition callable ports require semantic artifact contracts")
    composition = deepcopy(supplied)
    identity = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,95}$")
    part_lookup = {part["id"]: part for part in parts}
    if len(part_lookup) != len(parts):
        raise ValueError("Parent composition part identities are duplicated")
    inputs = composition.get("inputs", {})
    nodes = composition.get("nodes")
    outputs = composition.get("outputs")
    if not isinstance(inputs, dict) or not isinstance(nodes, list) or not nodes or not isinstance(outputs, dict) or not outputs:
        raise ValueError("Parent composition requires typed inputs, nodes and exposed outputs")
    for name, contract in inputs.items():
        if not isinstance(name, str) or not identity.fullmatch(name) or not isinstance(contract, dict) or not contract.get("semantic_type"):
            raise ValueError("Parent composition external input has no valid identity/contract")
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not identity.fullmatch(node["id"]):
            raise ValueError("Parent composition node identity is invalid")
        if node["id"] in by_id:
            raise ValueError("Parent composition node identities are duplicated")
        if node.get("part") not in part_lookup:
            raise ValueError("Parent composition references an unknown callable part")
        if "optional" in node and not isinstance(node["optional"], bool):
            raise ValueError("Parent composition optional flag must be a boolean")
        by_id[node["id"]] = node
    edges, dependencies, used_inputs = [], {}, set()
    for node in nodes:
        part = part_lookup[node["part"]]
        bindings = node.get("bindings", {})
        if not isinstance(bindings, dict):
            raise ValueError("Parent composition bindings must identify named inputs")
        required = {name for name, contract in part["inputs"].items() if contract.get("required", True)}
        if required - bindings.keys() or bindings.keys() - part["inputs"].keys():
            raise ValueError("Parent composition must bind each required declared part input")
        dependencies[node["id"]] = set()
        for name, binding in bindings.items():
            if not isinstance(binding, dict) or set(binding) != {"node", "port"}:
                raise ValueError("Parent composition bindings identify one producer node and port")
            producer, port = binding["node"], binding["port"]
            if not isinstance(producer, str) or not isinstance(port, str) or not identity.fullmatch(port):
                raise ValueError("Parent composition producer and port identities must be strings")
            if producer == "$input":
                if port not in inputs:
                    raise ValueError("Parent composition external input is not declared")
                produced = inputs[port]
                used_inputs.add(port)
            else:
                if producer not in by_id:
                    raise ValueError("Parent composition references an unknown producer node")
                parent = by_id[producer]
                produced = part_lookup[parent["part"]]["outputs"].get(port)
                if produced is None:
                    raise ValueError("Parent composition references an unknown producer output")
                if parent.get("optional") and not node.get("optional"):
                    raise ValueError("Required parent nodes cannot depend on an optional producer")
                dependencies[node["id"]].add(producer)
                edges.append({"from": producer, "output": port, "to": node["id"], "input": name,
                              "semantic_type": produced["semantic_type"]})
            if produced.get("semantic_type") != part["inputs"][name].get("semantic_type"):
                raise ValueError("Parent composition connects incompatible semantic artifact types")
        if "depends_on" in node:
            if not isinstance(node["depends_on"], list) or not all(isinstance(name, str) for name in node["depends_on"]):
                raise ValueError("Parent composition dependencies must be node identities")
            if set(node["depends_on"]) != dependencies[node["id"]]:
                raise ValueError("Parent composition dependencies disagree with real port bindings")
        node["depends_on"] = sorted(dependencies[node["id"]])
    if set(inputs) - used_inputs:
        raise ValueError("Parent composition declares unused external inputs")
    remaining = {name: set(values) for name, values in dependencies.items()}
    ordered = []
    while remaining:
        ready = sorted(name for name, values in remaining.items() if not values)
        if not ready:
            raise ValueError("Parent composition contains a dependency cycle")
        ordered.extend(ready)
        for name in ready:
            remaining.pop(name)
        for values in remaining.values():
            values.difference_update(ready)
    output_contracts = {}
    for name, binding in outputs.items():
        if not isinstance(name, str) or not identity.fullmatch(name) or not isinstance(binding, dict) or set(binding) != {"node", "port"}:
            raise ValueError("Parent composition exposed output binding is invalid")
        if not isinstance(binding["node"], str) or not isinstance(binding["port"], str):
            raise ValueError("Parent composition exposed output identities must be strings")
        node = by_id.get(binding["node"])
        if node is None or binding["port"] not in part_lookup[node["part"]]["outputs"]:
            raise ValueError("Parent composition exposes an unknown callable output")
        contract = deepcopy(part_lookup[node["part"]]["outputs"][binding["port"]])
        if node.get("optional"):
            contract["required"] = False
        output_contracts[name] = contract
    composition.update(schema="factory.workflow-composition.v1", origin="factory_owned_wrapper",
                       executable=False, execution_support="parts_only", edges=edges,
                       output_contracts=output_contracts, topological_order=ordered,
                       validation={"scope": "definition_bindings", "references": True,
                                   "semantic_types": True, "acyclic": True,
                                   "parent_execution_performed": False})
    return composition


def parent_composition(project_id: str, parts: list[dict]) -> dict:
    """Reviewed factory parent recipes, with actual external artifact boundaries."""
    lookup = {part["id"]: part for part in parts}
    if project_id == "strata":
        definition = {"inputs": {"verified_results": deepcopy(lookup["package"]["inputs"]["results"])},
                      "nodes": [
                          {"id": "extract", "part": "extract", "bindings": {}},
                          {"id": "generate", "part": "generate", "bindings": {"algorithm": {"node": "extract", "port": "algorithm"}}},
                          {"id": "report", "part": "report", "optional": True,
                           "bindings": {"algorithm": {"node": "extract", "port": "algorithm"}}},
                          {"id": "package", "part": "package", "bindings": {"project": {"node": "generate", "port": "project"},
                                                                                 "results": {"node": "$input", "port": "verified_results"}}}],
                      "outputs": {"project": {"node": "generate", "port": "project"},
                                  "cpp": {"node": "generate", "port": "cpp"},
                                  "report": {"node": "report", "port": "report"},
                                  "package": {"node": "package", "port": "package"}}}
    elif project_id == "googletest":
        definition = {"inputs": {name: deepcopy(lookup["design_tests"]["inputs"][name]) for name in ("algorithm", "project")},
                      "nodes": [
                          {"id": "prepare", "part": "prepare", "bindings": {}},
                          {"id": "design_tests", "part": "design_tests", "bindings": {
                              "algorithm": {"node": "$input", "port": "algorithm"},
                              "project": {"node": "$input", "port": "project"},
                              "framework": {"node": "prepare", "port": "framework"}}},
                          {"id": "verify", "part": "verify", "bindings": {
                              "project": {"node": "$input", "port": "project"},
                              "framework": {"node": "prepare", "port": "framework"},
                              "tests": {"node": "design_tests", "port": "tests"}}}],
                      "outputs": {"framework": {"node": "prepare", "port": "framework"},
                                  "tests": {"node": "design_tests", "port": "tests"},
                                  "results": {"node": "verify", "port": "results"}}}
    else:
        raise ValueError("No reviewed parent composition exists for this importer")
    return validate_composition(parts, definition)


def _strata_parts(checkout: Path, revision: str) -> list[dict]:
    evidence = [_evidence(checkout, "src/kernels/cuda/router_top10.cu", "router_top10_kernel"),
                _evidence(checkout, "src/kernels/cuda/shared_expert.cu", "swiglu_kernel")]
    defaults = {"checkout": str(checkout), "revision": revision, "demands": ["routing"]}
    return [
        _part("extract", "Extract production algorithms", outputs={"algorithm": _port("source.algorithm")},
              function="extract", defaults=defaults, evidence=evidence, tools=["python", "git"],
              purpose="Discover actual source kernels and lower only the task-selected supported operations."),
        _part("generate", "Generate C++ source project", inputs={"algorithm": _port("source.algorithm")},
              outputs={"project": _port("source.project"), "cpp": _port("source.cpp")}, function="generate",
              evidence=evidence, purpose="Assemble source-bound CPU reference and separate CANN native sources."),
        _part("report", "Write source analysis report", inputs={"algorithm": _port("source.algorithm")},
              outputs={"report": _port("analysis.report")}, function="report", evidence=evidence,
              purpose="Publish an optional source analysis document; not needed to construct or test C++."),
        _part("package", "Package verified source engineering", inputs={"project": _port("source.project"),
              "results": _port("verification.report")}, outputs={"package": _port("delivery.source_zip")},
              function="package", evidence=evidence, tools=["python", "git", "cmake", "c++"],
              purpose="Archive and rebuild actual C++ source, headers, CMake and consumed generated tests."),
    ]


def _googletest_parts(checkout: Path, revision: str) -> list[dict]:
    evidence = [_evidence(checkout, "googletest/include/gtest/gtest.h", "TEST("),
                _evidence(checkout, "googletest/CMakeLists.txt", "cxx_library")]
    return [
        _part("prepare", "Build GoogleTest framework", outputs={"framework": _port("test.framework")},
              function="prepare", defaults={"checkout": str(checkout), "revision": revision}, evidence=evidence,
              tools=["python", "git", "cmake", "c++"], purpose="Build the pinned real GoogleTest static libraries for downstream linking."),
        _part("design_tests", "Design source-reference GoogleTest cases", inputs={"algorithm": _port("source.algorithm"),
              "project": _port("source.project"), "framework": _port("test.framework")},
              outputs={"tests": _port("source.tests")}, prompt="design_reference_tests.md", evidence=evidence,
              tools=["configured agent", "filesystem"], purpose="Agent reads actual source and generated APIs to write independent mathematical reference tests."),
        _part("verify", "Compile and execute GoogleTest comparisons", inputs={"project": _port("source.project"),
              "framework": _port("test.framework"), "tests": _port("source.tests")},
              outputs={"results": _port("verification.report")}, function="verify", evidence=evidence,
              tools=["python", "cmake", "c++"], purpose="Link real GoogleTest with generated STRATA C++, run all cases, and preserve actual stdout/XML."),
    ]


def import_project(root: Path, repository_url: str, *, revision=None, emit=None) -> dict:
    """Clone/fetch a real allowlisted project and write its inspectable wrappers.

    A source revision is resolved to a commit before decomposition. Existing
    checkouts must be clean and have the exact expected remote; no old modified
    worktree can masquerade as the upstream project.
    """
    emit = emit or (lambda kind, payload: None)
    canonical = repository_url.rstrip("/")
    if canonical.endswith(".git"):
        canonical = canonical[:-4]
    if canonical not in PROJECTS:
        raise ValueError("Only the reviewed STRATA and GoogleTest source importers are enabled")
    project_id, name, default_revision = PROJECTS[canonical]
    requested = str(revision or default_revision)
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,160}", requested) or requested.startswith("-") or ".." in requested:
        raise ValueError("Invalid source revision")
    root = Path(root).resolve()
    checkout = root / "sources" / project_id
    receipt_dir = root / "imports" / project_id
    receipt_dir.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []
    try:
        if not (checkout / ".git").is_dir():
            if checkout.exists():
                raise ValueError("Refusing to replace an unrecognized source directory")
            checkout.parent.mkdir(parents=True, exist_ok=True)
            _command(["git", "clone", "--filter=blob:none", "--no-checkout", canonical, str(checkout)], cwd=None, emit=emit, log=log)
        else:
            actual_remote = _command(["git", "remote", "get-url", "origin"], cwd=checkout, emit=emit, log=log)
            if actual_remote.removesuffix(".git").rstrip("/") != canonical:
                raise ValueError("Source checkout origin does not match requested repository")
            if _command(["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout, emit=emit, log=log):
                raise ValueError("Source checkout contains changes; upstream identity would be ambiguous")
        _command(["git", "fetch", "--depth", "1", "origin", requested], cwd=checkout, emit=emit, log=log)
        commit = _command(["git", "rev-parse", "FETCH_HEAD^{commit}"], cwd=checkout, emit=emit, log=log)
        _command(["git", "checkout", "--detach", commit], cwd=checkout, emit=emit, log=log)
        if _command(["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout, emit=emit, log=log):
            raise ValueError("Acquired source is not clean")
        parts = _strata_parts(checkout, commit) if project_id == "strata" else _googletest_parts(checkout, commit)
        if project_id == "strata":
            from .cuda_lowering import discover_operations
            operations = discover_operations(checkout)
            decomposition = [{key: value for key, value in operation.items()
                              if key not in {"body", "source_code", "parameters_text"}} for operation in operations]
        else:
            decomposition = [{"component": "assertions", "path": "googletest/include/gtest/gtest.h"},
                             {"component": "test runner", "path": "googletest/src/gtest_main.cc"},
                             {"component": "framework build", "path": "googletest/CMakeLists.txt"}]
        composition = parent_composition(project_id, parts)
        composition_path = _json(receipt_dir / "parent-composition.json", composition)
        for part in parts:
            wrapper = receipt_dir / "wrappers" / part["id"]
            wrapper.mkdir(parents=True, exist_ok=True)
            if part["implementation"]["type"] == "python":
                function = part["implementation"]["entrypoint"].split(":")[1]
                entry = wrapper / "execute.py"
                entry.write_text(
                    '"""Factory-owned entrypoint; upstream source provenance is in workflow.json."""\n'
                    f"from jiuwenswarm.software_factory.library_operations import {function} as execute\n")
            else:
                entry = wrapper / "instructions.md"
                entry.write_bytes(Path(part["implementation"]["prompt_path"]).read_bytes())
            part["wrapper_manifest"] = str(wrapper / "workflow.json")
            part["inspection"]["wrapper"] = {"manifest": part["wrapper_manifest"], "entry": str(entry),
                                                 "sha256": _digest(entry.read_bytes()), "file_observed": True,
                                                 "origin": "factory_owned_wrapper"}
            _json(wrapper / "workflow.json", part)
            emit("import.subworkflow.created", {"project_id": project_id, "subworkflow": part})
        decomposition_path = _json(receipt_dir / "source-decomposition.json", {
            "schema": "factory.source-decomposition.v1", "repository": canonical, "revision": commit,
            "source_components": decomposition,
            "wrapper_origin": "Factory-owned adapters around real upstream source; not upstream workflow declarations",
            "subworkflows": parts, "composition": composition,
        })
        bundle = {"schema": "factory.workflow-bundle.v1", "id": project_id, "name": name,
                  "source": {"repository": canonical, "requested_revision": requested, "revision": commit,
                             "checkout": str(checkout), "decomposition_path": str(decomposition_path),
                             "decomposition_sha256": _digest(decomposition_path.read_bytes()), "clean": True},
                  "subworkflows": parts,
                  "default_flow": [part["id"] for part in parts],
                  "default_flow_role": "display_only",
                  "composition": composition, "composition_manifest": str(composition_path),
                  "composition_sha256": _digest(composition_path.read_bytes()),
                  "provenance": {"wrapper_owner": "Software Factory", "upstream_workflow_definitions": False}}
        bundle["version"] = "sha256:" + _digest(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode())
        bundle_path = _json(receipt_dir / "workflow-bundle.json", bundle)
        emit("import.completed", {"project_id": project_id, "revision": commit,
                                  "bundle_path": str(bundle_path), "version": bundle["version"]})
        return bundle
    finally:
        _json(receipt_dir / "acquisition.json", {"repository": canonical, "requested_revision": requested,
              "recorded_at": datetime.now(timezone.utc).isoformat(), "commands": log})
