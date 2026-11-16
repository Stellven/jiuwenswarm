"""The executable stage pool. No task templates or successful traces live here."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

from .contracts import Stage, StageBlocked, StageFailure, json_object

STRATA_REPOSITORY = 'https://github.com/niko1221/strata'


def validate_source(path):
    value = json_object(path, {'schema': str, 'source_dir': str, 'commit_sha': str, 'repository_url': str})
    if value['repository_url'] != STRATA_REPOSITORY or not re.fullmatch(r'[a-f0-9]{40}', value['commit_sha']):
        raise StageFailure('contract_invalid', 'Source identity must be the allowlisted repository at an immutable SHA')
    directory = Path(value['source_dir'])
    if not directory.is_dir() or not (directory / '.git').is_dir() or not (directory / 'CMakeLists.txt').is_file():
        raise StageFailure('contract_invalid', 'Checkout does not contain the actual STRATA source and Git metadata')
    return {'commit_sha': value['commit_sha'], 'source_dir': str(directory)}


def validate_analysis(path):
    value = json_object(path, {'commit_sha': str, 'files': list, 'mechanism_evidence': dict})
    if not value['files']:
        raise StageFailure('contract_invalid', 'Analysis must inspect actual source files')
    for item in value['files']:
        source = Path(item['absolute_path'])
        import hashlib
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            raise StageFailure('contract_invalid', f'Source evidence changed: {source}')
    return {'inspected_files': len(value['files']), 'commit_sha': value['commit_sha']}


def validate_environment(path):
    value = json_object(path, {'platform': str, 'tools': dict, 'devices': dict, 'sdk': dict, 'model': dict})
    return {'devices': value['devices'], 'sdk': value['sdk']}


def validate_toolchain(path):
    value = json_object(path, {'cmake': str, 'ninja': str, 'ctest': str, 'versions': dict})
    if not all(Path(value[name]).is_file() and os.access(value[name], os.X_OK) for name in ('cmake', 'ninja', 'ctest')):
        raise StageFailure('contract_invalid', 'Toolchain paths must be executable files')
    return {'versions': value['versions']}


def acquire_source(ctx, inputs):
    repository = ctx.options.get('repository_url', STRATA_REPOSITORY)
    if repository != STRATA_REPOSITORY:
        raise StageFailure('repository_not_allowed', 'Only https://github.com/niko1221/strata is authorized')
    requested_revision = ctx.options.get('revision')
    from .strata_patch import PIN
    revision = requested_revision or PIN
    if revision and not re.fullmatch(r'[a-fA-F0-9]{40}', revision):
        raise StageFailure('invalid_revision', 'Specify an exact 40-character commit SHA')
    directory = ctx.workspace / 'workspace/strata'
    directory.parent.mkdir(parents=True, exist_ok=True)
    def network_git(command, cwd=None):
        for number in range(1, 4):
            try:
                return ctx.run_command(command, cwd=cwd, timeout=600)
            except StageFailure as error:
                detail = error.details.get('command', {})
                transient = re.search(r'(?:error: 50[234]|returned error: 50[234]|connection (?:reset|timeout)|could not resolve host)',
                                      detail.get('stderr', ''), re.I)
                if number == 3 or not transient:
                    raise
                ctx.execution.emit('source.network_retry', ctx.node['id'], {
                    'command': command, 'completed_network_attempt': number,
                    'previous_exit_code': detail.get('exit_code')})
                # Only discard an incomplete clone inside this new stage's own
                # workspace; preserve every failed command and its full logs.
                if command[1] == 'clone' and directory.exists():
                    if not directory.resolve().is_relative_to(ctx.workspace.resolve()):
                        raise StageFailure('invalid_path', 'Partial clone escaped the stage workspace')
                    shutil.rmtree(directory)
    network_git(['git', 'clone', '--depth', '1', '--no-checkout', repository, str(directory)])
    if revision:
        network_git(['git', 'fetch', '--depth', '1', 'origin', revision], cwd=directory)
        ctx.run_command(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=directory, timeout=120)
    else:
        ctx.run_command(['git', 'checkout', '--detach', 'HEAD'], cwd=directory, timeout=120)
    commit = ctx.run_command(['git', 'rev-parse', 'HEAD'], cwd=directory)['stdout'].strip()
    status = ctx.run_command(['git', 'status', '--porcelain'], cwd=directory)['stdout'].strip()
    if status:
        raise StageFailure('source_dirty', 'Fresh upstream checkout is unexpectedly modified')
    return {'source': ctx.write_json('source.json', {'schema': 'factory.source.v1', 'source_dir': str(directory),
                'commit_sha': commit, 'repository_url': repository, 'requested_revision': requested_revision, 'resolved_revision': revision,
                'dependencies': ['CMake >= 3.24', 'C++20', 'vendored strata-ggml', 'backend-specific SDK'],
                'build_entry': 'CMakeLists.txt', 'presets_entry': 'CMakePresets.json'})}


def analyze_source(ctx, inputs):
    source = inputs['source'].read_json()
    directory = Path(source['source_dir'])
    listed = ctx.run_command(['git', 'ls-files', 'src', 'include', 'cmake', 'CMakeLists.txt', 'CMakePresets.json'], cwd=directory)
    # Every finding cites exact source bytes and lines; these are not migration claims.
    patterns = {
        'model_loading': re.compile(r'gguf|mmap|load_model|load_weights|experts\.bin', re.I),
        'expert_routing': re.compile(r'router|top.?k|expert_ids|routing', re.I),
        'expert_cache': re.compile(r'cache|resident|evict|prefetch', re.I),
        'cpu_gpu_partition': re.compile(r'cpu.*expert|gpu.*expert|cuda|hip|sycl|metal', re.I),
        'inference_output': re.compile(r'logits|argmax|sampling|sample_token|decode', re.I),
    }
    evidence = {key: [] for key in patterns}
    files = []
    import hashlib
    for relative in Path(listed['stdout_path']).read_text().splitlines():
        path = directory / relative
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            continue
        if path.suffix not in {'.cpp', '.hpp', '.h', '.cu', '.cuh', '.cmake', '.json', '.txt'}:
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        hits = False
        for category, pattern in patterns.items():
            if len(evidence[category]) >= 30:
                continue
            for index, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    evidence[category].append({'path': relative, 'line': index, 'source': line[:320]})
                    hits = True
                    break
        if hits or relative in {'CMakeLists.txt', 'CMakePresets.json'}:
            files.append({'path': relative, 'absolute_path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    return {'analysis': ctx.write_json('source-analysis.json', {'schema': 'factory.analysis.v1', 'commit_sha': source['commit_sha'],
        'source_dir': str(directory), 'files': files, 'mechanism_evidence': evidence,
        'claims_limit': 'Source inspection only; not build, kernel, migration, or inference verification.'})}


def inspect_environment(ctx, inputs):
    model_path = ctx.options.get('model_path')
    model = Path(model_path).expanduser() if model_path else None
    candidates = [Path(os.environ.get('ASCEND_HOME_PATH', '/usr/local/Ascend/ascend-toolkit/latest')),
                  Path('/usr/local/Ascend/ascend-toolkit/latest')]
    sdk = next((p for p in candidates if (p / 'include/acl/acl.h').is_file()), None)
    report = {'schema': 'factory.environment.v1', 'platform': platform.platform(), 'machine': platform.machine(),
              'tools': {name: shutil.which(name) for name in ('git', 'cmake', 'ninja', 'c++', 'nvcc', 'npu-smi')},
              'devices': {'ascend': sorted(str(p) for p in Path('/dev').glob('davinci[0-9]*')),
                          'cuda': sorted(str(p) for p in Path('/dev').glob('nvidia[0-9]*'))},
              'sdk': {'ascend_home': str(sdk) if sdk else None, 'acl_header': bool(sdk), 'nvcc': shutil.which('nvcc')},
              'model': {'path': str(model) if model else None, 'exists': model.exists() if model else False,
                        'kind': 'directory' if model and model.is_dir() else 'file' if model and model.is_file() else None}}
    return {'environment': ctx.write_json('environment.json', report)}


def install_toolchain(ctx, inputs):
    # A real missing executable triggers this stage; the product has no injected-failure switch.
    environment = ctx.workspace / 'toolchain'
    ctx.run_command([sys.executable, '-m', 'venv', str(environment)], timeout=120)
    python = environment / 'bin/python'
    ctx.run_command([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', 'cmake>=3.24,<5', 'ninja>=1.11,<2'], timeout=600)
    paths = {name: str(environment / 'bin' / name) for name in ('cmake', 'ninja', 'ctest')}
    versions = {name: ctx.run_command([path, '--version'])['stdout'].splitlines()[0] for name, path in paths.items()}
    return {'toolchain': ctx.write_json('toolchain.json', {'schema': 'factory.toolchain.v1', **paths, 'versions': versions})}


def build_full_engine(ctx, inputs):
    environment = inputs['environment'].read_json()
    from .generated_candidate import validate_generated_candidate
    validate_generated_candidate(Path(inputs['implementation'].path))
    implementation = inputs['implementation'].read_json()
    backend = ctx.options.get('target_backend', 'ascend')
    if backend == 'ascend':
        missing = []
        if not environment['sdk']['acl_header']:
            missing.append('Ascend CANN SDK with acl/acl.h and aclnn headers/libraries')
        if not environment['devices']['ascend']:
            missing.append('native Ascend device (/dev/davinciN)')
        # Generated host cores and CUDA transport do not implement the native model graph.
        missing.extend(implementation['missing_native_operations'])
        raise StageBlocked('native_backend_incomplete', 'Full STRATA Ascend inference is blocked; no backend fallback is permitted.',
                           {'required': missing, 'implementation_artifact_id': inputs['implementation'].id,
                            'implementation_sha256': inputs['implementation'].sha256, 'implementation_path': inputs['implementation'].path,
                            'layer': 'full_engine_compile'})
    if backend == 'cpu':
        raise StageBlocked('full_cpu_engine_unavailable', 'Pinned STRATA has CPU expert components but no full CPU generation engine.', {'layer': 'full_engine_compile'})
    if not environment['sdk']['nvcc']:
        raise StageBlocked('cuda_sdk_missing', 'Full CUDA engine compilation requires the actual CUDA SDK.', {'layer': 'full_engine_compile'})
    # Compilation does not require a device; loading/execution is checked separately.
    directory = Path(implementation.get('source_dir', '')).resolve(strict=True)
    cmake = ctx.options.get('cmake') or shutil.which('cmake') or 'cmake'
    build = ctx.workspace / 'candidate-full-build'
    configure = [cmake, '--preset', 'cuda-compile', '-B', str(build)]
    if ctx.options.get('ninja'):
        configure.append(f'-DCMAKE_MAKE_PROGRAM={ctx.options["ninja"]}')
    arch = ctx.options.get('options', {}).get('cuda_architectures')
    if arch:
        configure.append(f'-DCMAKE_CUDA_ARCHITECTURES={arch}')
    ctx.run_command(configure, cwd=directory, timeout=300)
    ctx.run_command([cmake, '--build', str(build), '--target', 'strata', 'strata_kq', '--parallel', '2'], cwd=directory, timeout=3600)
    binary = build / 'strata'
    if not binary.is_file():
        raise StageFailure('contract_invalid', 'CMake completed without the declared full strata binary')
    import hashlib
    return {'binary': ctx.write_json('full-engine.json', {'schema': 'factory.strata.binary.v1', 'path': str(binary),
        'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'source_dir': str(directory),
        'backend': backend, 'commit_sha': implementation['commit_sha'], 'role': 'candidate', 'full_model_binary': True,
        'execution_strategy': implementation['execution_strategy'], 'algorithms': implementation['algorithms'],
        'implementation_artifact_id': inputs['implementation'].id,
        'implementation_manifest_path': inputs['implementation'].path,
        'implementation_manifest_sha256': inputs['implementation'].sha256,
        'generated_manifest_sha256': implementation['generated_manifest_sha256'],
        'integrated_files': implementation['files'], 'full_native_model': False})}


def validate_json_manifest(path):
    return {'schema': json_object(path, {'schema': str})['schema']}



def validate_implementation(path):
    value = json_object(path, {'schema': str, 'source_dir': str, 'commit_sha': str, 'patch': dict})
    directory = Path(value['source_dir']).resolve(strict=True)
    import hashlib
    files = value['patch'].get('files')
    if not isinstance(files, list) or not files:
        raise StageFailure('contract_invalid', 'Implementation must identify actual modified computation files')
    for item in files:
        source = (directory / item['path']).resolve(strict=True)
        if not source.is_relative_to(directory) or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            raise StageFailure('contract_invalid', f'Modified implementation bytes differ: {source}')
    return {'commit_sha': value['commit_sha'], 'modified_files': len(files), 'full_inference_validated': False}


def validate_components(path):
    value = json_object(path, {'schema': str, 'source_dir': str, 'build_dir': str, 'binaries': dict, 'binary_sha256': dict})
    import hashlib
    build = Path(value['build_dir']).resolve(strict=True)
    if not value['binaries']:
        raise StageFailure('contract_invalid', 'No compiled components were produced')
    for name, filename in value['binaries'].items():
        binary = Path(filename).resolve(strict=True)
        if not binary.is_relative_to(build) or not os.access(binary, os.X_OK):
            raise StageFailure('contract_invalid', f'Compiled component is not executable: {name}')
        data = binary.read_bytes()
        if not data.startswith(b'\x7fELF') or hashlib.sha256(data).hexdigest() != value['binary_sha256'].get(name):
            raise StageFailure('contract_invalid', f'Compiled component is not the recorded ELF binary: {name}')
    return {'binaries': list(value['binaries']), 'full_inference_validated': False}


def validate_component_results(path):
    value = json_object(path, {'schema': str, 'checks': list, 'status': str, 'native_device_validated': bool, 'full_inference_validated': bool})
    if value['status'] != 'passed' or not value['checks']:
        raise StageFailure('contract_invalid', 'Component verification did not pass real checks')
    parity = [c for c in value['checks'] if 'outputs_compared' in c]
    if not parity or any(c.get('outputs_compared', 0) < 10240 or c.get('max_abs_error', float('inf')) > 1e-5 for c in parity):
        raise StageFailure('contract_invalid', 'Numerical expert transformation evidence is absent or outside tolerance')
    if any(c.get('exit_code', 0) != 0 for c in value['checks']):
        raise StageFailure('contract_invalid', 'A real component process failed')
    return {'numerical_comparisons': sum(c['outputs_compared'] for c in parity),
            'native_device_validated': value['native_device_validated'], 'full_inference_validated': value['full_inference_validated']}


def package_candidate(ctx, inputs):
    import hashlib
    import tarfile
    implementation, build, verification = (inputs[name].read_json() for name in ('implementation', 'build', 'verification'))
    checkout = Path(implementation['source_dir']).resolve(strict=True)
    # Source bytes and the actual compiled/tested candidate, not a wrapper report.
    manifest = {'schema': 'factory.candidate.v1', 'repository_url': STRATA_REPOSITORY,
                'commit_sha': implementation['commit_sha'], 'implementation': implementation,
                'build': build, 'verification': verification,
                'scope': 'Partial STRATA expert backend candidate; full Ascend model inference is NOT validated.',
                'rebuild': ['cmake -S source -B build -G Ninja -DSTRATA_BUILD_TESTS=ON -DSTRATA_NATIVE_EXPERTS=OFF',
                            'cmake --build build --target strata-plan strata_ascend_adapter_test pool_stress --parallel 2',
                            'build/strata_ascend_adapter_test', 'build/pool_stress 3', 'build/strata-plan']}
    manifest_path = ctx.write_json('candidate-manifest.json', manifest)
    archive = ctx.workspace / 'strata-candidate.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        stream.add(manifest_path, arcname='candidate-manifest.json')
        for path in sorted(checkout.rglob('*')):
            relative = path.relative_to(checkout)
            if any(part in {'.git', 'build', '.factory-tools', '__pycache__'} for part in relative.parts):
                continue
            if path.is_symlink():
                if not path.resolve().is_relative_to(checkout):
                    raise StageFailure('invalid_path', f'Candidate source symlink escapes checkout: {relative}')
            if path.is_file():
                stream.add(path, arcname=str(Path('source') / relative), recursive=False)
        for name, filename in build['binaries'].items():
            binary = Path(filename)
            if hashlib.sha256(binary.read_bytes()).hexdigest() != build['binary_sha256'][name]:
                raise StageFailure('binary_changed', name)
            stream.add(binary, arcname=f'bin/{name}', recursive=False)
    return {'package': archive}


def validate_candidate(path):
    import tarfile
    with tarfile.open(path) as stream:
        members = {m.name: m for m in stream.getmembers()}
        if any(Path(name).is_absolute() or '..' in Path(name).parts for name in members):
            raise StageFailure('contract_invalid', 'Unsafe archive member')
        for name in ('candidate-manifest.json', 'source/CMakeLists.txt', 'bin/strata_ascend_adapter_test', 'bin/pool_stress'):
            if name not in members or members[name].size == 0:
                raise StageFailure('contract_invalid', f'Candidate package missing {name}')
        value = json.load(stream.extractfile('candidate-manifest.json'))
        if value['verification'].get('full_inference_validated') is not False:
            raise StageFailure('contract_invalid', 'A partial expert package must not claim full model inference')
        return {'commit_sha': value['commit_sha'], 'members': len(members), 'full_inference_validated': False}


def validate_full_binary(path):
    value = json_object(path, {'path': str, 'sha256': str, 'source_dir': str, 'commit_sha': str, 'backend': str})
    import hashlib
    binary = Path(value['path']).resolve(strict=True)
    if not binary.read_bytes().startswith(b'\x7fELF') or hashlib.sha256(binary.read_bytes()).hexdigest() != value['sha256']:
        raise StageFailure('contract_invalid', 'Full engine artifact must identify the actual compiled ELF bytes')
    return {'backend': value['backend'], 'commit_sha': value['commit_sha'], 'device_loading_validated': False}


def validate_inference(path):
    from .strata_inference import inspect_logits
    value = json_object(path, {'schema': str, 'generated_tokens': list, 'logits': dict, 'model': dict, 'settings': dict, 'backend': str})
    actual = inspect_logits(Path(value['logits']['path']))
    if actual['sha256'] != value['logits']['sha256'] or not value['generated_tokens']:
        raise StageFailure('contract_invalid', 'Inference manifest does not match actual generated tokens/logit bytes')
    return {'backend': value['backend'], 'generated_tokens': len(value['generated_tokens']),
            'logits_shape': [actual['rows'], actual['vocabulary']], 'ascend_validated': value.get('ascend_validated', False)}


def validate_comparison(path):
    value = json_object(path, {'schema': str, 'status': str, 'logits_compared': int, 'max_abs_error': (int, float)})
    if value['status'] != 'passed' or value['logits_compared'] <= 0:
        raise StageFailure('contract_invalid', 'Comparison needs actual nonempty logit comparisons')
    return {'logits_compared': value['logits_compared'], 'max_abs_error': value['max_abs_error'],
            'ascend_validated': value.get('ascend_validated', False)}

def stage_catalog():
    stages = [
        Stage('source.fetch', 'Acquire pinned STRATA', 'source_acquisition', 'repository_fetch', {}, {'source': 'source.checkout'}, acquire_source,
              tools=('git',), environment=('Network access to github.com',), validators={'source': validate_source}),
        Stage('source.inspect', 'Inspect real source mechanisms', 'engineering', 'source_analysis', {'source': 'source.checkout'}, {'analysis': 'source.analysis'}, analyze_source,
              tools=('git', 'Python source reader'), validators={'analysis': validate_analysis}),
        Stage('environment.inspect', 'Inspect tools, devices and model', 'verification', 'environment_validation', {}, {'environment': 'environment.report'}, inspect_environment,
              validators={'environment': validate_environment}),
        Stage('toolchain.install', 'Install and verify missing CMake toolchain', 'environment_repair', 'dependency_recovery', {}, {'toolchain': 'toolchain.cmake'}, install_toolchain,
              tools=('Python venv', 'pip'), environment=('Package registry network access',), repairs=('missing_toolchain',), validators={'toolchain': validate_toolchain}),
    ]
    # Actual engineering actions are implemented against the acquired STRATA source.
    from .strata_stages import implement_strata, build_strata_components, verify_strata_components
    from .strata_inference import build_baseline_engine, run_baseline_inference, run_candidate_inference, compare_model_outputs
    from .generated_candidate import integrate_generated_candidate, validate_generated_candidate
    stages.extend([
        Stage('strata.implement', 'Apply native expert backend implementation', 'engineering', 'backend_implementation', {'source': 'source.checkout', 'analysis': 'source.analysis'}, {'implementation': 'implementation.checkout'}, implement_strata,
              tools=('git', 'Python'), validators={'implementation': validate_implementation}),
        Stage('strata.build_components', 'Build STRATA CPU expert components', 'engineering', 'native_build', {'implementation': 'implementation.checkout', 'environment': 'environment.report'}, {'build': 'build.components'}, build_strata_components,
              tools=('cmake', 'ninja', 'C++20 compiler'), validators={'build': validate_components}),
        Stage('strata.verify_components', 'Run actual expert and planner checks', 'verification', 'native_component_validation', {'build': 'build.components'}, {'verification': 'verification.components'}, verify_strata_components,
              tools=('ctest',), validators={'verification': validate_component_results}),
        Stage('candidate.package', 'Package constructed STRATA source and binaries', 'delivery', 'candidate_packaging',
              {'implementation': 'implementation.checkout', 'build': 'build.components', 'verification': 'verification.components'},
              {'package': 'candidate.package'}, package_candidate, tools=('Python tarfile',), validators={'package': validate_candidate}),
        Stage('candidate.integrate_generated', 'Integrate generated cores into the model engine', 'engineering', 'generated_source_integration',
              {'source': 'source.checkout', 'generated': 'construction.source'}, {'implementation': 'implementation.generated'}, integrate_generated_candidate,
              tools=('git', 'C++20 compiler'), validators={'implementation': validate_generated_candidate}),
        Stage('strata.build_full', 'Build full STRATA engine', 'engineering', 'full_engine_build', {'implementation': 'implementation.generated', 'environment': 'environment.report'}, {'binary': 'build.binary'}, build_full_engine,
              tools=('backend SDK', 'C++20 compiler'), validators={'binary': validate_full_binary}),
        Stage('strata.inference', 'Run full model inference', 'execution', 'model_inference', {'binary': 'build.binary', 'environment': 'environment.report'}, {'inference': 'inference.result'}, run_candidate_inference,
              environment=('Supported real STRATA model pack', 'native target device'), validators={'inference': validate_inference}),
        Stage('strata.baseline_build', 'Build pinned original STRATA engine', 'baseline', 'original_build',
              {'source': 'source.checkout', 'environment': 'environment.report'}, {'baseline_binary': 'build.baseline'}, build_baseline_engine,
              tools=('CMake', 'CUDA SDK'), validators={'baseline_binary': validate_full_binary}),
        Stage('strata.baseline_inference', 'Run pinned original model inference', 'baseline', 'original_inference',
              {'baseline_binary': 'build.baseline', 'environment': 'environment.report'}, {'baseline': 'inference.baseline'}, run_baseline_inference,
              environment=('Supported real STRATA model pack', 'native CUDA device'), validators={'baseline': validate_inference}),
        Stage('strata.compare', 'Compare original and candidate inference', 'verification', 'inference_comparison',
              {'inference': 'inference.result', 'baseline': 'inference.baseline'}, {'comparison': 'verification.comparison'}, compare_model_outputs,
              validators={'comparison': validate_comparison}),
    ])
    from .construction_pipeline import construction_stages
    from .value_agent import value_stages
    from .source_planning import planning_stages
    from .workflow_definitions import workflow_stages
    return stages + construction_stages() + planning_stages() + workflow_stages() + value_stages()
