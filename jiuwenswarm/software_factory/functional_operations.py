"""Executable adapters for source-derived functions and the project they build."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import zipfile

from .core_codegen import extract_core, generate_project
from .library_operations import _cmake


def pinned_checkout(parameters):
    checkout = Path(parameters['checkout']).resolve(strict=True)
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    changes = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True)
    if revision != parameters['revision'] or changes:
        raise ValueError('Upstream checkout must match the clean registered revision')
    return checkout


MATCHER = """#include <iostream>
#include <string>
#include "src/gtest-internal-inl.h"

int main(int argc, char** argv) {
    if (argc < 4 || argc % 2) return 2;
    GTEST_FLAG_SET(filter, argv[1]);
    for (int i = 2; i < argc; i += 2) {
        if (testing::internal::UnitTestOptions::FilterMatchesTest("STRATA", argv[i + 1]))
            std::cout << argv[i] << '\\n';
    }
}
"""

SHARDER = """#include <iostream>
#include <string>
#include "src/gtest-internal-inl.h"

int main(int argc, char** argv) {
    if (argc < 4) return 2;
    const int count = std::stoi(argv[1]), index = std::stoi(argv[2]);
    if (count < 1 || index < 0 || index >= count) return 2;
    for (int i = 3; i < argc; ++i) {
        if (testing::internal::ShouldRunTestOnShard(count, index, i - 3))
            std::cout << argv[i] << '\\n';
    }
}
"""


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return path


def _read(inputs, port):
    return json.loads(Path(inputs[port]['path']).read_bytes())


def _googletest_program(context, parameters, name, implementation):
    checkout = pinned_checkout(parameters)
    source = checkout / 'googletest'
    driver = context.workspace / (name + '.cpp')
    driver.write_text(implementation)
    executable = context.workspace / name
    context.run_command(['c++', '-std=c++17', '-O1', '-pthread',
                         '-I', str(source / 'include'), '-I', str(source),
                         str(driver), str(source / 'src/gtest-all.cc'), '-o', str(executable)])
    return executable


def match_names(context, inputs, parameters):
    """Use the original GoogleTest name matcher on the real STRATA candidates."""
    executable = _googletest_program(context, parameters, 'match_operations', MATCHER)
    candidates = parameters['candidates']
    items = [word for candidate in candidates for word in (candidate['id'], candidate['name'])]
    match = context.run_command([str(executable), parameters['pattern'], *items])
    selected = Path(match['stdout_path']).read_text().splitlines()
    if not selected or set(selected) - {candidate['id'] for candidate in candidates}:
        raise ValueError('Requested name filter selected no usable STRATA functions')
    context.emit('operations.selected', {'pattern': parameters['pattern'], 'selected': selected,
                                          'candidates': candidates})
    return {'selection': _write_json(context.workspace / 'selection.json', {'operations': selected})}


def assign_to_shard(context, inputs, parameters):
    executable = _googletest_program(context, parameters, 'assign_operations', SHARDER)
    selection = _read(inputs, 'selection')['operations']
    result = context.run_command([str(executable), str(parameters['count']),
                                  str(parameters['index']), *selection])
    assigned = Path(result['stdout_path']).read_text().splitlines()
    return {'shard': _write_json(context.workspace / 'shard.json', {'operations': assigned})}


def generate_source(context, inputs, parameters):
    checkout = pinned_checkout(parameters)
    selection = _read(inputs, 'selection')['operations']
    inventory = extract_core(checkout, context.workspace / 'source', selected=selection)
    project = context.workspace / 'strata_native'
    generate_project(inventory, project)
    with zipfile.ZipFile(context.workspace / 'strata_native.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(project.rglob('*')):
            if file.is_file():
                archive.write(file, file.relative_to(project))
    return {'source': context.workspace / 'strata_native.zip'}


def build_source(context, inputs, parameters):
    project = context.workspace / 'strata_native'
    project.mkdir()
    with zipfile.ZipFile(inputs['source']['path']) as archive:
        for member in archive.infolist():
            if not (project / member.filename).resolve().is_relative_to(project):
                raise ValueError('The source project contains an invalid archive path')
        archive.extractall(project)
    build = context.workspace / 'build'
    cmake = _cmake(parameters)
    context.run_command([cmake, '-S', str(project), '-B', str(build),
                         '-DSTRATA_CORE_BACKEND=CPU', '-DCMAKE_BUILD_TYPE=Release'])
    context.run_command([cmake, '--build', str(build), '--target', 'strata_engine', '--parallel', '2'])
    binary = build / 'strata_engine'
    if not binary.is_file():
        raise ValueError('The build did not create strata_engine')
    return {'binary': binary}


def compute(context, inputs, parameters):
    source_id = parameters['operation']
    operation_input = context.workspace / 'input.txt'
    numeric_input = parameters['numeric_input']
    if 'routing' in inputs:
        routing = _read(inputs, 'routing')
        ids, weights = routing['ids'], routing['weights']
        shared = parameters['shared_output']
        expert_outputs = parameters['expert_outputs']
        selected = [expert_outputs[str(expert)] for expert in ids]
        if not weights or len(weights) != len(ids) or not shared or any(len(row) != len(shared) for row in selected):
            raise ValueError('Routing output and the selected expert vectors have incompatible shapes')
        values = [*weights, *(value for row in selected for value in row), *shared]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
            raise ValueError('Expert vectors and routing weights must contain finite numbers')
        numeric_input = '\n'.join([
            f'{len(ids)} {len(shared)}',
            ' '.join(map(str, weights)),
            *[' '.join(map(str, row)) for row in selected],
            ' '.join(map(str, shared)),
        ]) + '\n'
        context.emit('aggregation.input_ready', {'experts': ids, 'weights': weights})
    operation_input.write_text(numeric_input)
    # Input artifacts are immutable copies and may not retain executable permissions.
    program = context.workspace / 'strata_engine'
    shutil.copyfile(inputs['binary']['path'], program)
    program.chmod(0o700)
    result = context.run_command([str(program), '--operation', source_id, '--input', str(operation_input)])
    output = context.workspace / 'output.json'
    output.write_bytes(Path(result['stdout_path']).read_bytes())
    observed = json.loads(output.read_bytes())
    if observed.get('backend') != 'CPU':
        raise ValueError('Component execution did not return a CPU reference result')
    context.emit('operation.result', {'operation': source_id, 'input': operation_input.read_text(),
                                     'output': observed})
    return {'result': output}
