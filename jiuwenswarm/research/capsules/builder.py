"""Single governed Builder call, then mechanical packaging and static receipt."""
from __future__ import annotations

import io
import json
import platform
import zipfile

from ..checks.research import BUNDLE_FILES, FORBIDDEN_MODULES, CheckError, inspect_bundle
from ..contracts.types import ResearchError
from ..environment import parse_requirements
from ._common import captured, produced


async def execute(ctx, inputs):
    blueprint = inputs['blueprint']
    if ctx.executor is None:
        raise ResearchError('unavailable', 'Confined Builder collection is unavailable')
    # The core-bound model callback routes this call through the governed bridge
    # and dedicated Builder CLI. The carrier never receives a credential.
    await ctx.model(json.dumps(inputs, ensure_ascii=False, allow_nan=False), system=(
        'Implement exactly the frozen one-file intervention in the assigned workspace. '
        'Write only requirements.txt,poc_patch.py,run_benchmark.py. Use exact approved lock dependencies. '
        'Never run trials, scripts, package managers, dependency discovery or network tools. '
        'Preserve baseline,validation,measurement functions and outcome rules. '
        'run_benchmark.py prints exactly one json.dumps({"metrics":{all registered metric IDs:finite computed numbers}}) line. '
        'No forbidden os/sys/subprocess/requests/urllib/shutil imports or dynamic import/exec/eval. '
        'Do not invent empirical measurements, repair failures or request approval.'))
    files = await ctx.executor.collect_builder(ctx.contract)
    if set(files) != BUNDLE_FILES or not all(isinstance(v, bytes) for v in files.values()):
        raise ResearchError('invalid_output', 'Builder did not produce the exact required files')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(BUNDLE_FILES):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])
    bundle = buffer.getvalue()
    bundle_ref = ctx.store.put_blob(bundle, media_type='application/zip')
    lock = inputs['lock']
    lock_pins = parse_requirements(ctx.store.read_blob(lock['requirements_ref']))
    manifest = {'schema_version': '2.0.0', 'id': 'poc_manifest', 'blueprint_ref': ctx.input_ref('blueprint'),
                'environment_ref': blueprint['environment_ref'], 'archive_ref': bundle_ref,
                'files': [{'path': name, 'artifact_ref': ctx.store.put_blob(data, media_type='text/plain' if name.endswith('.txt') else 'text/x-python'),
                           'media_type': 'text/plain' if name.endswith('.txt') else 'text/x-python', 'audience': 'researcher'} for name, data in files.items()],
                'dependencies': [{'name': n, 'version': v} for n, v in parse_requirements(files['requirements.txt']).items()]}
    manifest_ref = captured(ctx, manifest)
    forbidden_ref = ctx.store.put_blob(('\n'.join(sorted(FORBIDDEN_MODULES)) + '\n').encode(), media_type='text/plain')
    receipt = {'schema_version': '1.0.0', 'id': 'build_receipt', 'manifest_ref': manifest_ref,
               'blueprint_ref': ctx.input_ref('blueprint'), 'environment_ref': blueprint['environment_ref'], 'archive_ref': bundle_ref,
               'checker': 'CPython ' + platform.python_version() + ' compile and ast scan; no generated execution',
               'file_checks': [], 'forbidden_modules_ref': forbidden_ref, 'forbidden_scan_result': 'fail',
               'output_format_check': {'result': 'fail', 'json_print_calls': 0, 'metrics_key_found': False, 'missing_metric_ids': [m['metric_id'] for m in blueprint['metrics']]},
               'dependencies': manifest['dependencies'], 'dependencies_all_pinned': True, 'trial_executed': False,
               'packages_installed': False, 'readiness': 'NOT_READY', 'readiness_reasons': []}
    try:
        checked = inspect_bundle(bundle, [m['metric_id'] for m in blueprint['metrics']], lock_pins)
        receipt.update(file_checks=checked['file_checks'], output_format_check=checked['output_format_check'],
                       forbidden_scan_result='pass', readiness='READY')
    except (CheckError, ValueError) as exc:
        receipt['readiness_reasons'] = [getattr(exc, 'check_id', 'build_validation')]
        ctx.store.append_record('build_failure', {'receipt': receipt, 'manifest_ref': manifest_ref,
                                                'run_id': ctx.contract.get('run_id'), 'node_id': ctx.contract.get('node_id')})
        raise
    receipt_ref = ctx.store.put_record('build-receipt', receipt, scope=ctx.contract)
    ctx.record_host('build_receipt', receipt_ref)
    return {'manifest': produced(manifest, 'poc-manifest'),
            'bundle': produced(bundle, 'poc-artifact-bundle', media_type='application/zip', name='poc_artifact_bundle.zip')}
