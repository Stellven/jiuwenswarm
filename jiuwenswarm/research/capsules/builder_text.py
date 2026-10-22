"""Tool-free Builder m1-10: one treatment measurement per protected host job."""
from __future__ import annotations

import io
import platform
import zipfile

from ..checks.research import BUNDLE_FILES, FORBIDDEN_MODULES, inspect_bundle
from ..environment import parse_requirements
from ._common import ask, captured, produced
from ..contracts import ResearchError


async def execute(ctx, inputs):
    blueprint = inputs['blueprint']
    reply = await ask(ctx, 'Builder',
        'Return {"files":{"requirements.txt":"file text","poc_patch.py":"file text",'
        '"run_benchmark.py":"file text"}} with exactly these three files. Implement exactly '
        'the frozen intervention; no tools or execution are available. requirements.txt must '
        'equal the approved lock requirements. Keep the baseline, validation data, measurement '
        'functions and outcome rules unchanged. The baseline and validation resources are '
        'mounted read-only at /resources/baseline and /resources/validation. '
        'run_benchmark.py must import poc_patch from its own directory and print exactly one '
        'json.dumps({"metrics":{each registered metric_id:finite computed number}}) line. '
        'The static output contract requires exactly one print call with one positional '
        'argument and no print keyword arguments. That argument must be a direct '
        'json.dumps call whose sole positional argument is a literal dict display with '
        'the literal "metrics" key, for example print(json.dumps({"metrics": '
        '{"registered_metric_id": computed_value}}, allow_nan=False)). Replace the example '
        'metric ID with each exact blueprint metric ID as a string literal. Compute values '
        'before this call; do not pass a helper call or variable containing the outer dict '
        'to json.dumps. Do not add diagnostic print calls. Self-review this syntax without '
        'executing the generated files. '
        'The emitted JSON object has exactly the outer key metrics and exactly the registered '
        'metric IDs inside it: do not print outcome classifications, repeat arrays, baseline '
        'summaries, limitations or other fields. Each metric value is computed at run time, '
        'not an embedded result. Keep each UTF-8 file at most256 KiB and total uncompressed '
        'file bytes at most1 MiB for the declared archive/projection bounds. '
        'Public output obligations: the three file roles and imports must agree, all code '
        'and comments must be internally consistent, and limitations must agree with the '
        'no-execution/no-measurement status of this Builder call. poc_patch.py is one standalone '
        'bounded file with a stated purpose and no code that edits other files. The protected '
        'Benchmark owns cross-role scheduling: it runs the original captured baseline command '
        'once per baseline job, completes all registered baseline repeats first, then invokes '
        'run_benchmark.py once per treatment job. Your harness therefore performs exactly ONE '
        'treatment measurement per invocation. It must not execute or import the baseline script, '
        'run baseline/treatment role loops, repeat the whole measurement, average repeat results '
        'or compute outcome classifications. Do not reproduce the host experiment inside a '
        'treatment job. Read the exact frozen validation file path beneath /resources/validation '
        'and visibly configure the exact registered blueprint seed for the one treatment run. '
        'The current captured treatment command supplies no CLI arguments, so this single '
        'measurement is the default script behavior. The fixed original baseline interface '
        'and bytes stay unchanged. Explain in a docstring that protected Benchmark, not this '
        'treatment harness, controls baseline-first ordering and repeat aggregation. Do not '
        'claim unseen baseline behavior or actual execution has been independently verified. '
        'Exact captured baseline/data/seed custody and actual order are protected host checks. '
        'Do not embed a substitute baseline, fabricate measurements or treat a source comment '
        'as execution evidence. Before returning, self-review public shape conformance, '
        'internal and limitation consistency, no embedded results, one treatment observation '
        'with visible seed/data configuration under the baseline-first host protocol, no '
        'nested experiment, and the single bounded patch. '
        'Use only Python standard library and exact approved dependencies. No os/sys/subprocess/'
        'requests/urllib/shutil imports, dynamic import, exec or eval. Do not invent empirical '
        'measurements. Read the baseline/validation file contents supplied below as data. '
        'Package managers and network access are unavailable.',
        dict(inputs, input_refs={name: ctx.input_ref(name) for name in inputs},
             approved_requirements=ctx.store.read_blob(inputs['lock']['requirements_ref']).decode('utf-8'),
             resource_contents={name: {row['path']: ctx.store.read_blob(row['artifact_ref']).decode('utf-8')
                 for row in inputs[name]['files']} for name in ('baseline_resource','validation_resource')}),
        reply_schema={'type': 'object', 'properties': {'files': {'type': 'object',
            'properties': {name: {'type': 'string', 'maxLength': 1024 * 1024} for name in sorted(BUNDLE_FILES)},
            'required': sorted(BUNDLE_FILES), 'additionalProperties': False}},
            'required': ['files'], 'additionalProperties': False})
    if set(reply) != {'files'} or type(reply['files']) is not dict or set(reply['files']) != BUNDLE_FILES:
        raise ResearchError('invalid_output', 'Builder must return exactly three declared file texts')
    if any(type(value) is not str or len(value.encode('utf-8')) > 1024 * 1024 for value in reply['files'].values()):
        raise ResearchError('invalid_output', 'Builder file text exceeds its bounded output contract')
    files = {name: reply['files'][name].encode('utf-8') for name in sorted(BUNDLE_FILES)}
    if sum(map(len, files.values())) > 2 * 1024 * 1024:
        raise ResearchError('invalid_output', 'Builder bundle exceeds its bounded output contract')
    pins = parse_requirements(ctx.store.read_blob(inputs['lock']['requirements_ref']))
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    bundle = archive_bytes.getvalue()
    checked = inspect_bundle(bundle, [metric['metric_id'] for metric in blueprint['metrics']], pins)
    bundle_ref = ctx.store.put_blob(bundle, media_type='application/zip')
    manifest = {'schema_version': '2.0.0', 'id': 'poc_manifest',
        'blueprint_ref': ctx.input_ref('blueprint'), 'environment_ref': blueprint['environment_ref'],
        'archive_ref': bundle_ref,
        'files': [{'path': name, 'artifact_ref': ctx.store.put_blob(data),
            'media_type': 'text/plain' if name.endswith('.txt') else 'text/x-python',
            'audience': 'authorized researcher'} for name, data in files.items()],
        'dependencies': checked['dependencies']}
    manifest_ref = captured(ctx, manifest)
    receipt = {'schema_version': '1.0.0', 'id': 'build_receipt', 'manifest_ref': manifest_ref,
        'blueprint_ref': ctx.input_ref('blueprint'), 'environment_ref': blueprint['environment_ref'],
        'archive_ref': bundle_ref,
        'checker': 'CPython ' + platform.python_version() + ' compile and ast scan; tool-free text carrier; no generated execution',
        'file_checks': checked['file_checks'],
        'forbidden_modules_ref': ctx.store.put_blob(('\n'.join(sorted(FORBIDDEN_MODULES)) + '\n').encode()),
        'forbidden_scan_result': 'pass', 'output_format_check': checked['output_format_check'],
        'dependencies': checked['dependencies'], 'dependencies_all_pinned': True,
        'trial_executed': False, 'packages_installed': False, 'readiness': 'READY', 'readiness_reasons': []}
    ctx.record_host('build_receipt', ctx.store.put_record('build-receipt', receipt, scope=ctx.contract))
    return {'manifest': produced(manifest, 'poc-manifest'),
        'bundle': produced(bundle, 'poc-artifact-bundle', media_type='application/zip', name='poc_artifact_bundle.zip')}
