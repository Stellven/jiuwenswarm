"""Standalone preparation/build/validation entry for generated Ascend projects.

Copied into the generated project. Source checks are read-only. Target compile
and device execution occur only with explicit --compile / --validate options.
No CPU substitution is permitted and full-model status is always separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def prepare(project, build, *, compile_target=False, validate=False, source_only=False):
    project = Path(project).resolve(strict=True)
    build = Path(build).resolve()
    manifest = json.loads((project/'project.json').read_text())
    native = manifest['native_generation']
    report = {'schema': 'strata.ascend.readiness.v1', 'backend': 'ASCEND',
              'project': str(project), 'source_commit': manifest['source_commit'],
              'source_generation': 'GENERATED' if native['complete'] else 'PARTIAL',
              'source_integrity': 'NOT_RUN', 'sdk_prerequisites': 'NOT_RUN',
              'native_compilation': 'NOT_RUN', 'device_execution': 'NOT_RUN',
              'numerical_equivalence': 'NOT_RUN', 'full_model': 'NOT_RUN',
              'native_device_validated': False, 'full_inference_validated': False,
              'precision_policy': native['precision_policy'], 'commands': []}
    for file in manifest['generated_files']:
        path = (project/file['path']).resolve(strict=True)
        if not path.is_relative_to(project) or hashlib.sha256(path.read_bytes()).hexdigest() != file['sha256']:
            raise ValueError('Generated source changed: '+file['path'])
    report['source_integrity'] = 'PASS'
    if source_only:
        return report
    if not native['complete']:
        report['blocked_reason'] = 'Selected source contracts lack native generation; CPU fallback is prohibited'
        return report
    root = os.environ.get('ASCEND_HOME_PATH')
    sdk = Path(root).expanduser().resolve() if root else None
    missing = []
    for header in native['required_headers']:
        if sdk is None or not any((sdk/folder/header).is_file() for folder in ('include', 'include/aclnn', 'opp/built-in/op_impl/ai_core/tbe/op_api/include')):
            missing.append(header)
    for library in ('libascendcl.so', 'libopapi.so'):
        if sdk is None or not any((sdk/folder/library).is_file() for folder in ('lib64', 'lib', 'opp/built-in/op_impl/ai_core/tbe/op_api/lib')):
            missing.append(library)
    cmake = shutil.which('cmake')
    if not cmake:
        missing.append('cmake')
    if missing:
        report.update(sdk_prerequisites='MISSING', missing_prerequisites=missing)
        return report
    report['sdk_prerequisites'] = 'AVAILABLE'
    if not compile_target and not validate:
        return report

    def run(argv):
        build.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([str(x) for x in argv], text=True, capture_output=True, timeout=600)
        number = len(report['commands'])+1
        stdout = build/('native-command-'+str(number)+'.stdout')
        stderr = build/('native-command-'+str(number)+'.stderr')
        stdout.write_text(result.stdout)
        stderr.write_text(result.stderr)
        report['commands'].append({'argv': [str(x) for x in argv], 'exit_code': result.returncode,
                                   'stdout': str(stdout), 'stderr': str(stderr)})
        return result

    configuration = run([cmake, '-S', project, '-B', build, '-DSTRATA_CORE_BACKEND=ASCEND'])
    compiled = run([cmake, '--build', build, '--parallel', '2']) if not configuration.returncode else None
    report['native_compilation'] = 'PASS' if compiled is not None and not compiled.returncode else 'FAIL'
    if not validate or report['native_compilation'] != 'PASS':
        return report
    # This is the first device operation. No SDK-readiness check probes hardware.
    result = run([build/'strata_core_test'])
    report['device_execution'] = 'PASS' if result.returncode == 0 else 'FAIL'
    try:
        numerical = json.loads(result.stdout.strip().splitlines()[-1])
        report['numerical_result'] = numerical
    except (ValueError, IndexError):
        numerical = {}
    # CTest also executes the exact packaged task oracle at its declared
    # tolerances when one exists; built-in defaults cannot replace that oracle.
    ctest = shutil.which('ctest') or str(Path(cmake).with_name('ctest'))
    acceptance = run([ctest, '--test-dir', build, '--output-on-failure']) if result.returncode == 0 else None
    if (result.returncode == 0 and acceptance is not None and acceptance.returncode == 0
            and numerical.get('backend') == 'ASCEND' and numerical.get('coverage_complete') is True):
        report.update(numerical_equivalence='PASS', native_device_validated=True)
    else:
        report.update(numerical_equivalence='FAIL', native_device_validated=False)
    # Full-model inference has no implementation in this standalone core.
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepare/compile/validate generated device-only Ascend C++ sources')
    parser.add_argument('--project', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--build-dir', default='build-ascend')
    parser.add_argument('--check-source-only', action='store_true')
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--report')
    options = parser.parse_args(argv)
    if options.check_source_only and (options.compile or options.validate):
        parser.error('--check-source-only cannot compile or execute')
    report = prepare(options.project, options.build_dir, compile_target=options.compile,
                     validate=options.validate, source_only=options.check_source_only)
    text = json.dumps(report, indent=2)+'\n'
    if options.report:
        Path(options.report).write_text(text)
    print(text, end='')
    if options.compile or options.validate:
        return 0 if report['native_compilation'] == 'PASS' and (not options.validate or report['numerical_equivalence'] == 'PASS') else 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
