"""Real entrypoints shared by script and Agent workflow definitions.

Artifacts are inspected files. A source-project artifact is a manifest of an
actual C++ directory, not a schema-level promise that code exists. Host numerical
tests and CANN source generation have deliberately separate verification scopes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return path


def _artifact(inputs: dict, port: str) -> Path:
    reference = inputs[port]
    path = Path(reference["path"]).resolve(strict=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Input {port} is not a nonempty regular file")
    if _hash(path) != reference["sha256"]:
        raise ValueError(f"Input {port} bytes changed after publication")
    return path


def _read(inputs: dict, port: str) -> dict:
    value = json.loads(_artifact(inputs, port).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Input {port} must contain a JSON object")
    return value


def _checkout(context, parameters: dict) -> Path:
    root = Path(parameters["checkout"]).resolve(strict=True)
    revision_command = context.run_command(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=30)
    actual = Path(revision_command["stdout_path"]).read_text().strip()
    if actual != parameters["revision"]:
        raise ValueError("Pinned source checkout moved to another revision")
    status_command = context.run_command(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"], timeout=30)
    changes = Path(status_command["stdout_path"]).read_text()
    if changes:
        raise ValueError("Pinned upstream checkout contains local changes")
    return root


def _cmake(parameters: dict) -> str:
    candidates = [parameters.get("cmake"), os.environ.get("STRATA_FACTORY_CMAKE"), shutil.which("cmake"),
                  "/workspace/strata/.factory-tools/bin/cmake"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
    raise RuntimeError("CMake is required; set STRATA_FACTORY_CMAKE to an actual CMake executable")


def _checked_project(manifest: dict) -> Path:
    if manifest.get("schema") != "factory.source-project.v1":
        raise ValueError("Expected a generated source-project manifest")
    root = Path(manifest["source_dir"]).resolve(strict=True)
    for relative, expected in manifest["files"].items():
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or _hash(path) != expected:
            raise ValueError("Generated project changed: " + relative)
    for relative in ("src/strata_core.cpp", "include/strata_core.h", "CMakeLists.txt"):
        if relative not in manifest["files"]:
            raise ValueError("Generated source contract missing " + relative)
    return root


def extract(context, inputs: dict, parameters: dict) -> dict:
    """Read and structurally lower task-selected real STRATA function bodies."""
    from .core_codegen import extract_core, validate_core
    source = _checkout(context, parameters)
    demands = parameters.get("demands", ["routing"])
    if not isinstance(demands, list) or not demands or len(demands) > 32 or not all(isinstance(x, str) for x in demands):
        raise ValueError("demands must be a nonempty bounded list of source operation IDs or categories")
    inventory = extract_core(source, context.workspace / "extracted", demands=demands)
    validation = validate_core(inventory)
    context.emit("source.algorithms.extracted", {"revision": inventory["commit_sha"],
                 "selected": inventory["selected"], "source_functions": validation["source_functions"],
                 "sources": [{"path": item["path"], "line": item["line"], "end_line": item["end_line"],
                              "function_sha256": item["function_sha256"]} for item in inventory["kernels"].values()]})
    return {"algorithm": context.workspace / "extracted" / "core_ir.json"}


def generate(context, inputs: dict, parameters: dict) -> dict:
    """Run the existing source-bound generator; publish actual src/*.cpp bytes."""
    from .core_codegen import validate_core
    inventory = _read(inputs, "algorithm")
    validate_core(inventory)
    destination = context.workspace / "strata_native"
    context.run_command([sys.executable, "-m", "jiuwenswarm.software_factory.core_codegen",
                         "--inventory", str(_artifact(inputs, "algorithm")), "--output", str(destination)],
                        cwd=context.workspace, timeout=240,
                        env={"PYTHONPATH": str(Path(__file__).resolve().parents[2]) + os.pathsep + os.environ.get("PYTHONPATH", "")})
    metadata = json.loads((destination / "project.json").read_text())
    files = {str(path.relative_to(destination)): _hash(path) for path in sorted(destination.rglob("*")) if path.is_file()}
    manifest = {"schema": "factory.source-project.v1", "source_dir": str(destination), "files": files,
                "source_commit": inventory["commit_sha"], "selected": inventory["selected"],
                "algorithm_artifact": inputs["algorithm"], "native_generation": metadata["native_generation"],
                "verification_layers": {"source_implementation": "GENERATED", "local_cpu_tests": "NOT_RUN",
                     "target_compilation": "NOT_RUN", "device_loading": "NOT_RUN", "operator_execution": "NOT_RUN",
                     "model_inference": "NOT_RUN", "original_model_comparison": "NOT_RUN"},
                "full_inference_validated": False, "native_device_validated": False}
    _checked_project(manifest)
    context.emit("source.project.generated", {"source_dir": str(destination), "files": list(files),
                                              "selected": inventory["selected"]})
    return {"project": _write(context.workspace / "project-manifest.json", manifest),
            "cpp": destination / "src/strata_core.cpp"}


def report(context, inputs: dict, parameters: dict) -> dict:
    inventory = _read(inputs, "algorithm")
    lines = ["# Acquired STRATA algorithms", "", "Source commit: " + inventory["commit_sha"], ""]
    for item in inventory["kernels"].values():
        lines += [f"## {item['name']}", f"Source: {item['path']}:{item['line']}-{item['end_line']}",
                  "Function SHA-256: " + item["function_sha256"], "```cuda", item["source_code"], "```", ""]
    path = context.workspace / "source-analysis.md"
    path.write_text("\n".join(lines))
    return {"report": path}


def prepare(context, inputs: dict, parameters: dict) -> dict:
    """Compile the actual pinned GoogleTest project into downstream libraries."""
    source = _checkout(context, parameters)
    cmake = _cmake(parameters)
    build = context.workspace / "googletest-build"
    context.run_command([cmake, "-S", str(source), "-B", str(build), "-G", "Unix Makefiles",
                         "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_GMOCK=OFF", "-DINSTALL_GTEST=OFF",
                         "-Dgtest_build_tests=OFF"], timeout=240)
    context.run_command([cmake, "--build", str(build), "--parallel", "2"], timeout=600)
    include = source / "googletest/include"
    libraries = {}
    for name in ("gtest", "gtest_main"):
        matches = sorted(build.rglob("lib" + name + ".a"))
        if len(matches) != 1 or not matches[0].read_bytes().startswith(b"!<arch>\n"):
            raise ValueError("Actual GoogleTest static archive missing or ambiguous: " + name)
        libraries[name] = {"path": str(matches[0]), "sha256": _hash(matches[0])}
    headers = {str(path.relative_to(include)): _hash(path) for path in sorted(include.rglob("*.h"))}
    manifest = {"schema": "factory.test-framework.v1", "name": "GoogleTest", "revision": parameters["revision"],
                "repository": "https://github.com/google/googletest", "source_dir": str(source),
                "include_dir": str(include), "headers": headers, "libraries": libraries, "cmake": cmake}
    context.emit("framework.built", {"name": "GoogleTest", "revision": parameters["revision"],
                                    "libraries": libraries})
    return {"framework": _write(context.workspace / "framework-manifest.json", manifest)}


def _framework(manifest: dict):
    if manifest.get("schema") != "factory.test-framework.v1":
        raise ValueError("Expected a real GoogleTest framework manifest")
    include = Path(manifest["include_dir"]).resolve(strict=True)
    for relative, digest in manifest["headers"].items():
        path = (include / relative).resolve(strict=True)
        if not path.is_relative_to(include) or _hash(path) != digest:
            raise ValueError("GoogleTest header changed: " + relative)
    for library in manifest["libraries"].values():
        if _hash(Path(library["path"]).resolve(strict=True)) != library["sha256"]:
            raise ValueError("Built GoogleTest library changed")
    return include


def _quote(path: Path | str) -> str:
    text = str(path).replace("\\", "/")
    if any(character in text for character in ('"', "\n", "\r", ";", "$")):
        raise ValueError("Unsafe CMake path")
    return '"' + text + '"'


def _check_test_calls(content: str, selected_operations: list[dict]) -> None:
    """A shared convenience API cannot establish a second producer's coverage."""
    convenience = {"router": "route", "swiglu": "swiglu", "moe_combine": "moe_combine", "rms_norm": "rms_norm"}
    aliases = [convenience.get(operation["operation"], operation["name"]) for operation in selected_operations]
    for operation, alias in zip(selected_operations, aliases):
        names = {operation["binding"]}
        if aliases.count(alias) == 1:
            names.add(alias)
        if not any(re.search(r"\bstrata_core\s*::\s*" + re.escape(name) + r"\s*\(", content) for name in names):
            raise ValueError("Generated tests must call the selected source's unique binding: " + operation["source_id"])


def _baseline_report(command: dict, selected_operations: list[dict], *, require_original_reference: bool = True) -> dict:
    """Inspect actual numerical stdout by source ID; aggregate counts are not proof."""
    if not isinstance(require_original_reference, bool):
        raise ValueError("require_original_reference must be a boolean")
    stdout = Path(command["stdout_path"]).read_text()
    try:
        value = json.loads(next(line for line in reversed(stdout.splitlines()) if line.strip()))
    except (ValueError, StopIteration) as error:
        raise ValueError("Original-reference executable produced no valid JSON result") from error
    if not isinstance(value, dict) or value.get("backend") != "CPU":
        raise ValueError("Original-reference result must identify the actual CPU reference backend")
    if value.get("native_device_validated") is True or value.get("full_inference_validated") is True:
        raise ValueError("A CPU component result cannot establish native device or full model validation")
    checks = value.get("operation_checks")
    if not isinstance(checks, list) or not all(isinstance(check, dict) for check in checks):
        raise ValueError("Original-reference output must contain per-source operation checks")
    by_id = {}
    for check in checks:
        source_id = check.get("source_id")
        if not isinstance(source_id, str) or source_id in by_id:
            raise ValueError("Original-reference output has missing or duplicate source identities")
        by_id[source_id] = check
    requested = [operation["source_id"] for operation in selected_operations]
    if len(requested) != len(set(requested)):
        raise ValueError("Selected source identities must be unique")
    selected = [by_id[source_id] for source_id in requested if source_id in by_id]
    missing = [source_id for source_id in requested if source_id not in by_id]
    incomplete = list(missing)
    for check in selected:
        count, maximum = check.get("outputs_compared"), check.get("max_abs_error")
        if (check.get("status") != "passed" or type(count) is not int or count < 1
                or type(maximum) not in (int, float) or not math.isfinite(maximum) or maximum < 0):
            incomplete.append(check["source_id"])
    selected_complete = bool(requested) and not incomplete
    if require_original_reference and (not selected_complete or value.get("coverage_complete") is not True):
        raise ValueError("Original-reference coverage is incomplete for selected source operations: "
                         + ", ".join(incomplete or requested))
    return {"required": require_original_reference, "status": "verified" if selected_complete else "unverified",
            "coverage_complete": selected_complete, "reported_coverage_complete": value.get("coverage_complete"),
            "selected_source_ids": requested, "operation_checks": selected, "missing_source_ids": missing,
            "unselected_operation_checks": [check for check in checks if check["source_id"] not in requested],
            "outputs_compared": sum(check["outputs_compared"] for check in selected
                                     if type(check.get("outputs_compared")) is int),
            "stdout_path": command["stdout_path"], "stdout_sha256": _hash(Path(command["stdout_path"])),
            "native_device_validated": False, "full_inference_validated": False}


def verify(context, inputs: dict, parameters: dict) -> dict:
    """Compile generated STRATA source and actually link/run generated GoogleTest."""
    project = _read(inputs, "project")
    source = _checked_project(project)
    framework = _read(inputs, "framework")
    include = _framework(framework)
    tests = _artifact(inputs, "tests")
    content = tests.read_text()
    if "strata_core::" not in content or "TEST(" not in content or not any(x in content for x in ("EXPECT_", "ASSERT_")):
        raise ValueError("Agent tests must use GoogleTest assertions and the actual generated STRATA API")
    if "GTEST_SKIP" in content or "DISABLED_" in content:
        raise ValueError("Skipped or disabled generated acceptance tests are prohibited")
    metadata = json.loads((source / "project.json").read_text())
    _check_test_calls(content, metadata["operations"])
    cmake = _cmake({**parameters, "cmake": framework["cmake"]})
    driver = context.workspace / "test-project"
    driver.mkdir()
    script = ["cmake_minimum_required(VERSION 3.24)", "project(factory_cross_project_tests LANGUAGES CXX)",
              "set(CMAKE_CXX_STANDARD 20)", "set(CMAKE_CXX_STANDARD_REQUIRED ON)",
              "enable_testing()", "find_package(Threads REQUIRED)",
              f"add_subdirectory({_quote(source)} candidate)"]
    for name in ("gtest", "gtest_main"):
        script += [f"add_library(factory_{name} STATIC IMPORTED)",
                   f"set_target_properties(factory_{name} PROPERTIES IMPORTED_LOCATION {_quote(framework['libraries'][name]['path'])} INTERFACE_INCLUDE_DIRECTORIES {_quote(include)})"]
    script += [f"add_executable(factory_reference_tests {_quote(tests)})",
               "target_link_libraries(factory_reference_tests PRIVATE strata_core factory_gtest_main factory_gtest Threads::Threads)",
               "add_test(NAME factory_reference_tests COMMAND factory_reference_tests)"]
    (driver / "CMakeLists.txt").write_text("\n".join(script) + "\n")
    build = context.workspace / "build"
    context.run_command([cmake, "-S", str(driver), "-B", str(build), "-G", "Unix Makefiles",
                         "-DSTRATA_CORE_BACKEND=CPU", "-DCMAKE_BUILD_TYPE=Release"], timeout=240)
    context.run_command([cmake, "--build", str(build), "--parallel", "2"], timeout=600)
    binary = build / "factory_reference_tests"
    if not binary.is_file() or not binary.read_bytes().startswith(b"\x7fELF"):
        raise ValueError("GoogleTest compilation did not produce an actual host executable")
    xml_path = context.workspace / "googletest-results.xml"
    context.run_command([str(binary), "--gtest_color=no", "--gtest_output=xml:" + str(xml_path)], timeout=240)
    tree = ET.parse(xml_path).getroot()
    cases = tree.findall(".//testcase")
    if len(cases) < 3 or any(case.find("failure") is not None or case.find("skipped") is not None for case in cases):
        raise ValueError("GoogleTest must execute at least three passing cases without failures or skips")
    baseline = build / "candidate/strata_core_test"
    baseline_command = context.run_command([str(baseline)], timeout=240)
    original_reference = _baseline_report(baseline_command, metadata["operations"],
                                         require_original_reference=parameters.get("require_original_reference", True))
    engine = build / "candidate/strata_engine"
    argv = [str(engine), "--input", str(source / metadata["cli"]["validation_input"])]
    if metadata["cli"]["mode"] == "operations":
        argv.extend(["--operation", metadata["cli"]["validation_operation"]])
    context.run_command(argv, timeout=240)
    results = {"schema": "factory.verification.v1", "status": "verified", "backend": "CPU",
               "test_count": len(cases), "test_cases": [{"suite": x.get("classname"), "name": x.get("name"),
                  "time": x.get("time")} for x in cases], "xml": str(xml_path), "xml_sha256": _hash(xml_path),
               "tests": {"path": str(tests), "sha256": _hash(tests)}, "framework": framework,
               "project_sha256": inputs["project"]["sha256"], "binary": str(binary), "binary_sha256": _hash(binary),
               "engine": str(engine), "engine_sha256": _hash(engine),
               "original_reference": original_reference,
               "verification_layers": {"source_implementation": "GENERATED", "local_cpu_tests": "PASS",
                    "original_source_reference": "PASS" if original_reference["coverage_complete"] else "UNVERIFIED",
                    "target_compilation": "NOT_RUN", "device_loading": "NOT_RUN", "operator_execution": "NOT_RUN",
                    "model_inference": "NOT_RUN", "original_model_comparison": "NOT_RUN"},
               "native_device_validated": False, "full_inference_validated": False}
    context.emit("verification.completed", {"backend": "CPU", "test_count": len(cases), "binary": str(binary),
                                          "native_device_validated": False, "full_inference_validated": False})
    return {"results": _write(context.workspace / "verification.json", results)}


def _package_contents(source: Path, project: dict, tests: Path, results_file: Path, revision: str,
                      project_manifest_sha256: str) -> dict[str, bytes]:
    """Assemble final source bytes and refresh their deployable integrity map.

    Packaging adds a real test target. The original construction metadata is
    retained under reference/ while project.json describes the actual delivered
    bytes. A manifest cannot hash itself; generated_files excludes project.json.
    """
    files = {relative: (source / relative).read_bytes() for relative in project["files"]}
    original_cmake = files["CMakeLists.txt"]
    original_project = files["project.json"]
    original_diff = files.get("code_diff.json")
    appendix = '\noption(STRATA_BUILD_GENERATED_GTEST "Build Agent-generated source-reference GoogleTest cases" OFF)\nif(STRATA_BUILD_GENERATED_GTEST)\n include(FetchContent)\n set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)\n set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)\n FetchContent_Declare(googletest GIT_REPOSITORY https://github.com/google/googletest GIT_TAG ' + revision + ')\n FetchContent_MakeAvailable(googletest)\n add_executable(factory_reference_tests tests/factory_generated_tests.cpp)\n target_link_libraries(factory_reference_tests PRIVATE strata_core GTest::gtest_main)\n add_test(NAME factory_reference_tests COMMAND factory_reference_tests)\nendif()\n'
    files["CMakeLists.txt"] = original_cmake + appendix.encode()
    files["tests/factory_generated_tests.cpp"] = tests.read_bytes()
    files["verification/factory-verification.json"] = results_file.read_bytes()
    files["scripts/verify_generated_tests.sh"] = b'#!/usr/bin/env sh\nset -eu\ncmake -S . -B build -DSTRATA_CORE_BACKEND=CPU -DSTRATA_BUILD_GENERATED_GTEST=ON\ncmake --build build --parallel 2\nctest --test-dir build --output-on-failure\n'
    files["reference/factory-original-CMakeLists.txt"] = original_cmake
    files["reference/factory-original-project.json"] = original_project
    if original_diff is not None:
        files["reference/factory-original-code_diff.json"] = original_diff
        difference = json.loads(original_diff)
        difference["factory_packaging"] = {"original_sha256": hashlib.sha256(original_diff).hexdigest(),
                                           "added_tests": "tests/factory_generated_tests.cpp"}
        difference["generated_files"] = [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                                         for relative, raw in sorted(files.items())
                                         if relative not in {"project.json", "code_diff.json"}]
        files["code_diff.json"] = (json.dumps(difference, indent=2, allow_nan=False) + "\n").encode()
    metadata = json.loads(original_project)
    metadata["project_dir"] = "."
    metadata["factory_packaging"] = {
        "schema": "factory.source-package.v1", "construction_manifest_sha256": hashlib.sha256(original_project).hexdigest(),
        "construction_cmake_sha256": hashlib.sha256(original_cmake).hexdigest(),
        "consumed_project_manifest_sha256": project_manifest_sha256,
        "framework_revision": revision, "generated_tests": "tests/factory_generated_tests.cpp",
        "construction_metadata": "reference/factory-original-project.json",
        "native_device_validated": False, "full_inference_validated": False}
    metadata["generated_files"] = [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                                   for relative, raw in sorted(files.items()) if relative != "project.json"]
    files["project.json"] = (json.dumps(metadata, indent=2, allow_nan=False) + "\n").encode()
    return files


def package(context, inputs: dict, parameters: dict) -> dict:
    """Package the actual consumed project and successful Agent-generated tests."""
    project = _read(inputs, "project")
    source = _checked_project(project)
    results = _read(inputs, "results")
    if results.get("status") != "verified" or results.get("project_sha256") != inputs["project"]["sha256"]:
        raise ValueError("Package requires successful verification of this exact source project")
    tests = Path(results["tests"]["path"]).resolve(strict=True)
    if _hash(tests) != results["tests"]["sha256"]:
        raise ValueError("Verified Agent-generated tests changed before packaging")
    revision = results["framework"]["revision"]
    _checkout(context, {"checkout": results["framework"]["source_dir"], "revision": revision})
    files = _package_contents(source, project, tests, _artifact(inputs, "results"), revision, inputs["project"]["sha256"])
    destination = context.workspace / "huawei_native_strata.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, raw in sorted(files.items()):
            archive.writestr(relative, raw)
    with zipfile.ZipFile(destination) as archive:
        for required in ("src/strata_core.cpp", "include/strata_core.h", "CMakeLists.txt", "tests/factory_generated_tests.cpp"):
            if required not in archive.namelist() or not archive.read(required):
                raise ValueError("Source package is missing actual production code: " + required)
        # Verify the deliverable's exact CMake and source bytes, including the
        # added GoogleTest target. Reuse the already acquired pinned framework
        # through FetchContent's documented source override; no network or NPU
        # operation is introduced by this package verification.
        unpacked = context.workspace / "package-rebuild-source"
        archive.extractall(unpacked)
    context.run_command([sys.executable, str(unpacked / "scripts/prepare_ascend.py"), "--check-source-only"], timeout=60)
    cmake = _cmake({**parameters, "cmake": results["framework"]["cmake"]})
    build = context.workspace / "package-rebuild"
    context.run_command([cmake, "-S", str(unpacked), "-B", str(build), "-G", "Unix Makefiles",
                         "-DSTRATA_CORE_BACKEND=CPU", "-DSTRATA_BUILD_GENERATED_GTEST=ON",
                         "-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=" + results["framework"]["source_dir"],
                         "-DCMAKE_BUILD_TYPE=Release"], timeout=240)
    context.run_command([cmake, "--build", str(build), "--parallel", "2"], timeout=600)
    context.run_command([str(build / "factory_reference_tests"), "--gtest_color=no"], timeout=240)
    packaged_baseline = context.run_command([str(build / "strata_core_test")], timeout=240)
    packaged_metadata = json.loads((unpacked / "project.json").read_text())
    _baseline_report(packaged_baseline, packaged_metadata["operations"],
                     require_original_reference=results.get("original_reference", {}).get("required", True))
    context.emit("delivery.packaged", {"path": str(destination), "sha256": _hash(destination),
                                      "source_files": len(project["files"]), "generated_tests_included": True})
    return {"package": destination}
