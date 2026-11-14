"""Source-driven STRATA core construction, compilation, validation and delivery.

Production source is generated from inspected upstream algorithms. Numerical
tests are a separate executable, never a substitute model or native-device run.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile
from .contracts import Stage, StageBlocked, StageFailure, json_object

ROOT = Path(__file__).parent

class SchemaMismatchError(StageFailure):
    def __init__(self, message, **details):
        super().__init__('schema_mismatch', message, details)


def _inventory(path: Path, key: str):
    value = json_object(path, {'schema': str, 'commit_sha': str, 'source_dir': str, 'files': list, key: list})
    if not value[key]:
        raise StageFailure('contract_invalid', f'{key} must contain actual source declarations')
    root = Path(value['source_dir']).resolve(strict=True)
    sources = {}
    for file in value['files']:
        source = (root / file['path']).resolve(strict=True)
        if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest() != file['sha256']:
            raise StageFailure('source_changed', f'Kernel inventory source bytes changed: {file["path"]}')
        sources[file['path']] = file['sha256']
    for op in value[key]:
        if op.get('file') not in sources or sources[op['file']] != op.get('source_sha256'):
            raise StageFailure('contract_invalid', 'Operation does not bind an inspected source file and hash')
    return value


def validate_inventory(path):
    value = json.loads(path.read_text())
    key = 'ascend_ops' if 'ascend_ops' in value else 'cuda_ops'
    checked = _inventory(path, key)
    return {'representation': key, 'source_operations': len(checked[key]), 'semantic_lowering_complete': False}


def validate_native_inventory(path):
    checked = _inventory(path, 'ascend_ops')
    from .core_codegen import validate_core
    if not isinstance(checked.get('core_ir'), dict):
        raise StageFailure('contract_invalid', 'Native inventory requires extracted algorithm bodies')
    validate_core(checked['core_ir'])
    return {'algorithms': checked['core_ir']['selected'], 'full_inference_validated': False}


def extract_cuda(ctx, inputs):
    source = inputs['source'].read_json()
    output = ctx.workspace / 'workspace/analysis/cuda_ops.json'
    ctx.run_command([sys.executable, str(ROOT/'scripts/analyze_cuda.py'), '--repository', source['source_dir'], '--output', str(output)], timeout=180)
    checked = _inventory(output, 'cuda_ops')
    if checked['commit_sha'] != source['commit_sha']:
        raise StageFailure('source_pin_mismatch', 'CUDA scan used a different source revision')
    return {'inventory': output}


def ascend_mapper(ctx, inputs):
    path = Path(inputs['inventory'].path)
    value = inputs['inventory'].read_json()
    if not isinstance(value.get('ascend_ops'), list):
        raise SchemaMismatchError('Ascend_Mapper requires {"ascend_ops": [...]}; received the actual CUDA inventory.',
                                  input_file=str(path), expected='ascend_ops:list', actual_keys=list(value),
                                  repair_contract='operator.inventory')
    checked = _inventory(path, 'ascend_ops')
    validate_native_inventory(path)
    return {'mapping': ctx.write_json('ascend-mapping.json', {'schema': 'strata.operator.mapping.v1',
        'inventory_path': str(path), 'inventory_sha256': inputs['inventory'].sha256,
        'commit_sha': checked['commit_sha'], 'core_ir': checked['core_ir'],
        'semantic_lowering_complete': False})}


def adapt_inventory(ctx, inputs):
    output = ctx.workspace / 'workspace/analysis/ascend_ops.json'
    command = [sys.executable, str(ROOT/'adapters/ast_to_ascend.py'), '--input', inputs['inventory'].path, '--output', str(output)]
    for selected in ctx.options.get('options', {}).get('core_algorithms') or []:
        command.extend(['--core', selected])
    ctx.run_command(command, timeout=180)
    validate_native_inventory(output)
    return {'inventory': output}


def construct_cpp(ctx, inputs):
    mapping = inputs['mapping'].read_json()
    inventory = _inventory(Path(mapping['inventory_path']), 'ascend_ops')
    if hashlib.sha256(Path(mapping['inventory_path']).read_bytes()).hexdigest() != mapping['inventory_sha256']:
        raise StageFailure('artifact_changed', 'Mapped inventory changed before C++ construction')
    from .core_codegen import validate_core
    core = mapping['core_ir']
    validate_core(core)
    if core != inventory.get('core_ir') or core['commit_sha'] != mapping['commit_sha']:
        raise StageFailure('source_pin_mismatch', 'Mapping does not bind the extracted source algorithms')
    destination = ctx.workspace / 'workspace/strata_native'
    core_path = ctx.write_json('core-ir.json', core)
    ctx.run_command([sys.executable, '-m', 'jiuwenswarm.software_factory.core_codegen',
                     '--inventory', str(core_path), '--output', str(destination)],
                    cwd=ROOT.parent.parent, timeout=180)
    required = ['src/strata_core.cpp', 'include/strata_core.h', 'src/main.cpp', 'CMakeLists.txt', 'code_diff.json']
    for name in required:
        if not (destination/name).is_file() or not (destination/name).stat().st_size:
            raise StageFailure('contract_invalid', f'Code generator did not produce {name}')
    return {'cpp': destination/'src/strata_core.cpp', 'header': destination/'include/strata_core.h',
        'cmake': destination/'CMakeLists.txt', 'code_diff': destination/'code_diff.json',
        'source': ctx.write_json('constructed-source.json', {'schema': 'strata.constructed.source.v1',
        'source_dir': str(destination), 'commit_sha': mapping['commit_sha'],
        'consumed_mapping_sha256': inputs['mapping'].sha256, 'algorithms': core['selected'],
        'scope': 'Source-derived STRATA core CPU implementation; optional Ascend integration is unvalidated',
        'full_inference_validated': False,
        'files': {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in destination.rglob('*') if p.is_file()}})}


def _checked_project(source):
    directory = Path(source['source_dir']).resolve(strict=True)
    for name, digest in source['files'].items():
        path = (directory/name).resolve(strict=True)
        if not path.is_relative_to(directory) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise StageFailure('source_changed', name)
    return directory


def validate_source_project(path):
    value = json_object(path, {'source_dir': str, 'files': dict, 'algorithms': list, 'commit_sha': str})
    _checked_project(value)
    for name in ('src/strata_core.cpp', 'include/strata_core.h', 'CMakeLists.txt'):
        if name not in value['files']:
            raise StageFailure('contract_invalid', f'Generated project is missing {name}')
    return {'algorithms': value['algorithms'], 'source_files': len(value['files'])}


def validate_code_diff(path):
    value = json_object(path, {'schema': str, 'files': list})
    if value['schema'] != 'strata.code.diff.v1' or not value['files']:
        raise StageFailure('contract_invalid', 'Code Diff requires actual source and generated code')
    for file in value['files']:
        if any(not isinstance(file.get(key), str) or not file[key].strip()
               for key in ('source_path', 'generated_path', 'source_code', 'generated_code')):
            raise StageFailure('contract_invalid', 'Code Diff contains an empty source pair')
        generated = (path.parent/file['generated_path']).resolve(strict=True)
        if not generated.is_relative_to(path.parent.resolve()) or file['generated_code'] not in generated.read_text():
            raise StageFailure('contract_invalid', 'Code Diff does not match generated source bytes')
    return {'source_pairs': len(value['files'])}


def build_cpp(ctx, inputs):
    source = inputs['source'].read_json()
    directory = _checked_project(source)
    cmake = ctx.options.get('cmake') or shutil.which('cmake') or 'cmake'
    make = shutil.which('make') or 'make'
    build = ctx.workspace/'build'
    ctx.run_command([cmake, '-B', str(build), '-S', str(directory), '-G', 'Unix Makefiles',
                     '-DSTRATA_CORE_BACKEND=CPU'], timeout=180)
    ctx.run_command([make, '-C', str(build), '-j2'], timeout=600)
    binary = (build/'strata_engine').resolve(strict=True)
    tests = (build/'strata_core_test').resolve(strict=True)
    if not binary.read_bytes().startswith(b'\x7fELF'):
        raise StageFailure('contract_invalid', 'Construction did not produce a real executable ELF')
    return {'executable': binary, 'build': ctx.write_json('constructed-build.json', {'schema': 'strata.constructed.build.v1',
        'binary': str(binary), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'tests': str(tests), 'tests_sha256': hashlib.sha256(tests.read_bytes()).hexdigest(),
        'cmake': cmake,
        'source_dir': str(directory), 'algorithms': source['algorithms'],
        'source_manifest_sha256': inputs['source'].sha256, 'scope': source['scope'],
        'cpu_compilation_validated': True, 'native_device_validated': False, 'full_inference_validated': False})}


def execute_cpp(ctx, inputs):
    from .oracle_validation import OracleError, validate_project
    binary = inputs['build'].read_json()
    requirements = inputs['requirements'].read_json()
    path = Path(binary['binary']).resolve(strict=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != binary['binary_sha256']:
        raise StageFailure('binary_changed', str(path))
    tests = Path(binary['tests']).resolve(strict=True)
    if hashlib.sha256(tests.read_bytes()).hexdigest() != binary['tests_sha256']:
        raise StageFailure('binary_changed', str(tests))
    try:
        validation = validate_project(ctx,path,tests,binary['source_dir'],requirements.get('oracle'),inputs['requirements'].sha256)
    except OracleError as error:
        details = {**error.details,'requirements_artifact_id':inputs['requirements'].id,
                   'requirements_sha256':inputs['requirements'].sha256}
        failure = StageBlocked if error.code=='numerical_oracle_missing' else StageFailure
        raise failure(error.code,str(error),details) from error
    command = validation.pop('self_test_command')
    return {'execution': ctx.write_json('constructed-execution.json', {'schema': 'strata.constructed.execution.v1',
        'stdout': command['stdout'], 'stdout_path': command['stdout_path'], 'stderr_path': command['stderr_path'],
        'binary_sha256': binary['binary_sha256'], **validation,
        'requirements_artifact_id':inputs['requirements'].id,'requirements_sha256':inputs['requirements'].sha256,
        'scope': 'Separate generated-core numerical tests on CPU; no model or native-device inference',
        'native_device_validated': False,'full_inference_validated': False})}


def package_cpp(ctx, inputs):
    source, build, execution = (inputs[name].read_json() for name in ('source', 'build', 'execution'))
    directory = _checked_project(source)
    if build['source_manifest_sha256'] != inputs['source'].sha256 or execution['binary_sha256'] != build['binary_sha256']:
        raise StageFailure('contract_invalid', 'Packaging requires the exact constructed, built and tested source')
    archive = ctx.workspace/'huawei_native_strata.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for name in sorted(source['files']):
            output.write(directory/name, arcname=name)
    validate_package(archive)
    return {'package': archive}


def validate_package(path):
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if any(Path(name).is_absolute() or '..' in Path(name).parts for name in names) or archive.testzip():
            raise StageFailure('contract_invalid', 'Generated source package is unsafe or corrupt')
        for name in ('src/strata_core.cpp', 'include/strata_core.h', 'src/main.cpp', 'CMakeLists.txt'):
            if name not in names or not archive.read(name):
                raise StageFailure('contract_invalid', f'Source ZIP is missing {name}')
        return {'source_files': len(names), 'full_inference_validated': False}


def rebuild_package(ctx, inputs):
    """Consume the delivered ZIP in a distinct source/build tree, then run it.

    The external numeric input below belongs to this isolated arithmetic check;
    it is not model weights, token generation, or a native-device validation.
    """
    validate_package(Path(inputs['package'].path))
    original_build = inputs['build'].read_json()
    directory = ctx.workspace/'unpacked-source'
    directory.mkdir()
    with zipfile.ZipFile(inputs['package'].path) as archive:
        for name in archive.namelist():
            path = (directory/name).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise StageFailure('invalid_path', name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    cmake = ctx.options.get('cmake') or original_build['cmake']
    build = ctx.workspace/'independent-build'
    ctx.run_command([cmake, '-S', str(directory), '-B', str(build), '-G', 'Unix Makefiles',
                     '-DSTRATA_CORE_BACKEND=CPU'], timeout=180)
    ctx.run_command([shutil.which('make') or 'make', '-C', str(build), '-j2'], timeout=600)
    ctest = ctx.options.get('ctest') or str(Path(cmake).with_name('ctest'))
    checked = ctx.run_command([ctest, '--test-dir', str(build), '--output-on-failure'], timeout=180)
    project = json.loads((directory/'project.json').read_text())
    data = ctx.workspace/'arithmetic-input.txt'
    declared = (directory/project['cli']['validation_input']).resolve(strict=True)
    if not declared.is_relative_to(directory.resolve()):
        raise StageFailure('invalid_path', 'Validation input escaped the delivered source package')
    data.write_bytes(declared.read_bytes())
    command = [str(build/'strata_engine'), '--input', str(data)]
    if project['cli'].get('validation_operation'):
        command.extend(['--operation', project['cli']['validation_operation']])
    result = ctx.run_command(command, timeout=120)
    actual = json.loads(result['stdout'])
    if not isinstance(actual, dict) or not actual:
        raise StageFailure('numeric_runtime_mismatch', 'Standalone CLI did not produce a computation result')
    return {'portability': ctx.write_json('source-portability.json', {
        'schema': 'strata.source.portability.v1', 'package_sha256': inputs['package'].sha256,
        'independent_rebuild_validated': True, 'source_dir': str(directory), 'build_dir': str(build),
        'input_path': str(data), 'input_sha256': hashlib.sha256(data.read_bytes()).hexdigest(),
        'runtime_result': actual, 'stdout_path': result['stdout_path'], 'stderr_path': result['stderr_path'],
        'ctest_stdout_path': checked['stdout_path'], 'ctest_stderr_path': checked['stderr_path'],
        'scope': 'Independent source ZIP rebuild and isolated external-input CPU arithmetic check',
        'native_device_validated': False, 'full_inference_validated': False})}


def construction_stages():
    return [
        Stage('source.cuda_ast', 'Analyze CUDA source declarations', 'source_acquisition', 'cuda_analysis',
              {'source': 'source.checkout'}, {'inventory': 'operator.inventory'}, extract_cuda,
              tools=('git', 'Python'), validators={'inventory': validate_inventory}),
        Stage('construction.ascend_mapper', 'Ascend_Mapper', 'construction', 'operator_mapping',
              {'inventory': 'operator.native_inventory'}, {'mapping': 'operator.mapping'}, ascend_mapper,
              verifier='Source-bound algorithm bodies, supported semantics and exact commit identity'),
        Stage('metadata.ast_to_ascend', 'Extract and lower STRATA core algorithms', 'transformation', 'semantic_lowering',
              {'inventory': 'operator.inventory'}, {'inventory': 'operator.native_inventory'}, adapt_inventory,
              tools=('Python', 'STRATA production source'), validators={'inventory': validate_native_inventory}, selection_only=True),
        Stage('construction.codegen', 'Generate STRATA core source project', 'construction', 'source_generation',
              {'mapping': 'operator.mapping'}, {'source': 'construction.source', 'cpp': 'construction.cpp',
              'header': 'construction.header', 'cmake': 'construction.cmake', 'code_diff': 'construction.code_diff'}, construct_cpp,
              tools=('Python', 'STRATA source'), validators={'source': validate_source_project, 'code_diff': validate_code_diff}),
        Stage('construction.build', 'Compile generated STRATA core', 'construction', 'cpp_build',
              {'source': 'construction.source'}, {'build': 'construction.build', 'executable': 'construction.executable'}, build_cpp,
              tools=('cmake', 'make', 'C++20 compiler')),
        Stage('construction.execute', 'Validate generated STRATA core arithmetic', 'verification', 'core_validation',
              {'build': 'construction.build','requirements':'task.requirements'}, {'execution': 'construction.execution'}, execute_cpp,
              tools=('local executable process',)),
        Stage('construction.package', 'Package generated STRATA source', 'delivery', 'source_packaging',
              {'source': 'construction.source', 'build': 'construction.build', 'execution': 'construction.execution'},
              {'package': 'construction.package'}, package_cpp, tools=('Python zipfile',), validators={'package': validate_package}),
        Stage('construction.rebuild_package', 'Rebuild delivered STRATA source', 'verification', 'source_portability',
              {'package': 'construction.package', 'build': 'construction.build'},
              {'portability': 'construction.portability'}, rebuild_package,
              tools=('cmake', 'make', 'C++ compiler', 'generated external-input executable')),
    ]
