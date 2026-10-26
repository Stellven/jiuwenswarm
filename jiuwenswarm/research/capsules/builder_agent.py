"""Agentic, host-mediated Pi Builder capsule."""
from __future__ import annotations

import hashlib
import json

from ..contracts import ResearchError
from ..environment import validate_lock
from ..metric_contract import validate_metric_declarations
from ..pi_protocol import MAX_DIGITS, inspect_pi_bundle, validate_pi_request
from ..trusted_scoring import parse_public_dataset
from ..checks.prediction_bundle import inspect_bundle
from ._common import produced

BUILD_SCHEMA = 'urn:ai4r:prediction-build-receipt:4.0.0'
SYSTEM = '''Implement the frozen Pi approximation task using only scoped Builder actions.
The task is a user-facing contract: approximate_pi(digits), for integer digits from 0
through 100000, returns the exact truncated decimal prefix of pi. The executable harness
must emit closed JSON with exactly {"digits": integer, "decimal": string}. Use only
provided task inputs: the frozen blueprint, approved lock and public validation request.
Do not inspect unrelated files, hidden references, environment state or scorer data.
Actions are file and build operations mediated by the protected host. Inspect diagnostics
and iterate until compile, unit and public smoke checks pass. Submit the exact tested
snapshot. Development checks do not establish experiment outcomes or scientific acceptance.'''


CLASSIFICATION_SYSTEM = '''Implement the frozen generic d-dimensional classification intervention using the scoped
Builder actions. Implement predict(train, test) as a list of declared string labels in test order,
inferred from features and labeled training rows. Use only the frozen blueprint, approved lock
and public validation data. Do not use row IDs to encode labels, inspect unrelated files or seek
private labels. The harness emits exactly the closed predictions JSON protocol. Protected Benchmark
owns baseline-first repeats and private scoring.'''


def _public_task(inputs, public, *, pi=False):
    """Project bound inputs into agent context without forwarding resource refs."""
    contract = ({'interface': 'approximate_pi(digits)', 'min_digits': 0,
                 'max_digits': MAX_DIGITS, 'rounding': 'truncate',
                 'development_cases': [0,1,2,17,10000,100000],
                 'output': {'digits': 'integer', 'decimal': 'string'}} if pi else
                {'interface': 'predict(train, test)', 'classes': public['classes'],
                 'output': 'list of declared string labels in test order'})
    return {'blueprint': inputs['blueprint'], 'lock': inputs['lock'],
            'public_validation': public, 'instructions': SYSTEM if pi else CLASSIFICATION_SYSTEM,
            'contract': contract}


async def execute(ctx, inputs):
    if ctx.executor is None or not hasattr(ctx.executor, 'builder_action'):
        raise ResearchError('unavailable', 'Agentic Builder requires the protected action executor')
    if len(inputs['validation_resource']['files']) != 1:
        raise ResearchError('builder_public_data', 'One public validation request is required')
    row = inputs['validation_resource']['files'][0]
    if row['path'] != 'data.json':
        raise ResearchError('builder_public_data', 'Public validation request must be data.json')
    raw_public = ctx.store.read_blob(row['artifact_ref'])
    pi = False
    try:
        raw_value = json.loads(raw_public)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ResearchError('builder_public_data', 'Invalid public validation request') from exc
    if isinstance(raw_value, dict) and raw_value.get('schema') == 'ai4r-pi-cases:1':
        try:
            public = {'schema': 'ai4r-pi-cases:1', 'digits': validate_pi_request(raw_value)}
        except ValueError as exc:
            raise ResearchError('builder_public_data', 'Invalid public Pi request') from exc
        pi = True
    else:
        try:
            public = parse_public_dataset(raw_public)
        except Exception as exc:
            raise ResearchError('builder_public_data', 'Invalid public classification data') from exc
    if not pi:
        validate_metric_declarations(inputs['blueprint']['metrics'])
    lock = inputs['lock']
    task = _public_task(inputs, public, pi=pi)
    task['baseline_source']={row['path']:ctx.store.read_blob(row['artifact_ref']).decode('utf-8')
                             for row in inputs['baseline_resource']['files']}
    task['contract']['limits']={'time_s':600,'model_calls':20,'tool_operations':40,'development_jobs':12}
    task['contract']['baseline_and_logs_are_untrusted_task_data']=True
    tool_counter = 0

    async def dispatch(name, args, model_ordinal):
        nonlocal tool_counter
        tool_counter += 1
        return await ctx.executor.builder_action(ctx.contract, action=name,
            arguments=args, ordinal=tool_counter, model_ordinal=model_ordinal)

    from ..native import verify_native_pin
    verify_native_pin()
    from ..builder_agent_runtime import run_builder_agent
    async def model_call(prompt, system):
        return await ctx.model(prompt, system=system)

    result = await run_builder_agent(model_call=model_call, dispatch=dispatch, task=task,
        session_id=ctx.contract['attempt_id'], max_model_calls=20, max_tools=40, timeout_s=600)
    if not isinstance(result, dict) or result.get('submitted') is not True:
        raise ResearchError('builder_blocked', 'Builder did not submit a completed tested snapshot')
    manifest_ref = result.get('manifest_ref')
    bundle_ref = result.get('bundle_ref')
    receipt_ref = result.get('build_receipt_ref')
    if not all(isinstance(ref, dict) for ref in (manifest_ref, bundle_ref, receipt_ref)):
        raise ResearchError('builder_invalid_submission', 'Protected submission references are incomplete')
    manifest = ctx.read_json(manifest_ref)
    bundle = ctx.read_blob(bundle_ref)
    receipt = ctx.read_json(receipt_ref)
    if manifest.get('archive_ref') != bundle_ref or hashlib.sha256(bundle).hexdigest() != bundle_ref.get('sha256'):
        raise ResearchError('builder_invalid_submission', 'Submitted archive does not match its manifest')
    pins = validate_lock(lock, ctx.read_blob, lock['platform'])
    checked = inspect_pi_bundle(bundle, pins) if pi else inspect_bundle(
        bundle, [metric['metric_id'] for metric in inputs['blueprint']['metrics']], pins)
    files = {row['path']: row for row in manifest.get('files', [])}
    if set(files) != set(checked['files']) or any(
            ctx.read_blob(files[name]['artifact_ref']) != checked['files'][name]
            for name in checked['files']):
        raise ResearchError('builder_invalid_submission', 'Manifest file entries do not match tested archive')
    if manifest.get('blueprint_ref') != ctx.input_ref('blueprint') or manifest.get('environment_ref') != ctx.input_ref('lock'):
        raise ResearchError('builder_invalid_submission', 'Submitted manifest changed frozen inputs')
    if receipt.get('schema_version') != '4.0.0' or receipt.get('id') != 'build_receipt':
        raise ResearchError('builder_invalid_submission', 'Protected build receipt has the wrong schema')
    if receipt.get('manifest_ref') != manifest_ref or receipt.get('archive_ref') != bundle_ref:
        raise ResearchError('builder_invalid_submission', 'Receipt references do not match submitted artifacts')
    ctx.record_host('build_receipt', receipt_ref)
    # These are exact protected host artifacts, not model-authored content.
    return {'manifest': produced(manifest, 'poc-manifest'),
            'bundle': produced(bundle, 'poc-artifact-bundle', media_type='application/zip',
                               name='poc_artifact_bundle.zip')}
