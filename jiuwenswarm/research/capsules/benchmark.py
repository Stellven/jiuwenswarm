"""Deterministic baseline-first execution and protected C002 evidence capture."""
from __future__ import annotations

from ..contracts.types import ResearchError
from ..environment import validate_lock
from ..science import metric_payload
from ..trusted_scoring import BUILD_SCHEMA, scored_empirical_row, failed_empirical_row
from ..contracts import validate
from ..state import json_bytes
from ..metric_contract import validate_metric_declarations, validate_empirical_metric_ids
from ._common import captured, produced


async def execute(ctx, inputs):
    if ctx.executor is None:
        raise ResearchError('unavailable', 'The scientific executor is unavailable')
    blueprint, manifest = inputs['hypothesis_blueprint'], inputs['poc_manifest']
    ready, lock = inputs['build_receipt'], inputs['environment_lock']
    validate('urn:ai4r:prediction-build-receipt:'+ready['schema_version'] if ready['schema_version'] in {'3.0.0','4.0.0'} else BUILD_SCHEMA, ready)
    validate_metric_declarations(blueprint['metrics'])
    if (ready['readiness'] != 'READY' or (ready['schema_version'] not in {'3.0.0','4.0.0'} and (ready['trial_executed'] or ready['packages_installed']))
            or ready['manifest_ref'] != ctx.input_ref('poc_manifest')
            or ready['archive_ref'] != manifest['archive_ref'] or ready['archive_ref'] != ctx.input_ref('poc_artifact_bundle')
            or manifest['blueprint_ref'] != ctx.input_ref('hypothesis_blueprint')
            or manifest['environment_ref'] != blueprint['environment_ref']):
        raise ResearchError('build_receipt_not_ready', 'Benchmark requires the exact accepted READY build')
    # Root provisioner separately checks actual-platform compatibility against
    # the protected runtime profile; labels are not inferred from this string.
    pins = validate_lock(lock, ctx.store.read_blob, lock['platform'])
    provision = await ctx.executor.provision(ctx.contract, inputs, pins)
    provision_ref = captured(ctx, provision)
    ctx.record_host('provisioning_receipt', provision_ref)
    if provision['status'] != 'succeeded':
        raise ResearchError('provisioning_failed', 'Frozen environment provisioning failed')
    hardware = await ctx.executor.hardware_inventory(ctx.contract)
    hardware_ref = captured(ctx, hardware)
    metric_ids = [m['metric_id'] for m in blueprint['metrics']]
    runs, rows, score_refs = [], [], []
    failure = None
    try:
        for role in ['baseline', 'treatment']:
            subject = blueprint['baseline_identity']['resource_ref'] if role == 'baseline' else manifest['archive_ref']
            for repeat_index in range(blueprint['repeat_count']):
                sequence = len(runs) + 1
                job = await ctx.executor.measure_job(ctx.contract, inputs, role=role, repeat_index=repeat_index,
                        seed=blueprint['seed'], sequence=sequence, subject_ref=subject, hardware_ref=hardware_ref)
                raw = await ctx.executor.run(job)
                ctx.store.append_record('scientific_execution', {'run_id': ctx.contract['run_id'], 'node_id': ctx.contract['node_id'],
                                                               'attempt_id': ctx.contract['attempt_id'], 'receipt': raw})
                if (raw['sequence'] != sequence or raw['role'] != role or raw['repeat_index'] != repeat_index
                        or raw['seed'] != blueprint['seed'] or raw['subject_ref'] != subject
                        or raw['hardware_ref'] != hardware_ref or ctx.store.read_blob(raw['hardware_ref']) != json_bytes(hardware)):
                    raise ResearchError('execution_receipt_mismatch', 'Executor identity differs from the frozen measured job')
                public = {k: raw[k] for k in ['sequence', 'role', 'repeat_index', 'seed', 'subject_ref', 'exit_code',
                                              'started_at', 'wall_time_s', 'timeout_s', 'stdout_ref', 'stderr_ref']}
                public.update(command=list(raw['argv']), hardware_ref=hardware['hardware_id'])
                runs.append(public)
                if 'trusted_scoring_ref' in raw:
                    score_refs.append(raw['trusted_scoring_ref'])
                row = (scored_empirical_row(raw, ctx.read_json(raw['trusted_scoring_ref']))
                       if 'trusted_scoring_ref' in raw else failed_empirical_row(raw))
                validate_empirical_metric_ids(row)
                rows.append(row)
                if role == 'baseline' and (raw['exit_code'] != 0 or raw.get('termination_reason') != 'completed'
                                           or row['status'] != 'measured'):
                    raise ResearchError('baseline_failed', 'Failed baseline halts before treatment')
    except BaseException as exc:
        failure = exc
    empirical = {'schema_version': '2.0.0', 'id': 'empirical_results', 'runs': rows}
    empirical_ref = captured(ctx, empirical)
    receipt = {'schema_version': '1.0.0', 'id': 'execution_receipt', 'blueprint_ref': ctx.input_ref('hypothesis_blueprint'),
               'poc_ref': ctx.input_ref('poc_manifest'), 'hardware_inventory': hardware, 'empirical_results_ref': empirical_ref, 'runs': runs}
    receipt_ref = captured(ctx, receipt)
    ctx.store.append_record('benchmark_attempt', {'run_id': ctx.contract['run_id'], 'node_id': ctx.contract['node_id'],
                           'execution_receipt_ref': receipt_ref, 'empirical_results_ref': empirical_ref,
                           'provisioning_receipt_ref': provision_ref, 'outcome': 'failed' if failure else 'complete'})
    if failure:
        raise failure
    metrics = []
    for metric in blueprint['metrics']:
        values, reasons = {}, {}
        for role in ['baseline', 'treatment']:
            relevant = [row for row, run in zip(rows, runs) if run['role'] == role]
            values[role] = [r['metrics'][metric['metric_id']] for r in relevant if metric['metric_id'] in r['metrics']]
            missing = [r['unmeasured_metrics'][metric['metric_id']] for r in relevant if metric['metric_id'] in r['unmeasured_metrics']]
            reasons[role] = missing[0] if missing else None
        metrics.append(metric_payload(metric, values['baseline'], values['treatment'], blueprint['repeat_count'], reasons['baseline'], reasons['treatment']))
    payload = {'schema_version': '2.0.0', 'id': 'benchmark_payload', 'blueprint_ref': ctx.input_ref('hypothesis_blueprint'),
               'poc_ref': ctx.input_ref('poc_manifest'), 'environment_lock_ref': ctx.input_ref('environment_lock'),
               'resource_refs': blueprint['resource_refs'], 'configuration_ref': ctx.configuration_ref,
               'execution_receipt_ref': receipt_ref, 'provisioning_receipt_ref': provision_ref,
               'repeat_count': blueprint['repeat_count'], 'seed': blueprint['seed'], 'run_order': [r['role'] for r in runs],
               'metrics': metrics, 'raw_evidence_refs': [empirical_ref] + [r[k] for r in runs for k in ['stdout_ref', 'stderr_ref']]
                    + score_refs}
    ctx.record_host('execution_receipt', receipt_ref)
    return {'benchmark_payload': produced(payload, 'benchmark-payload'),
            'execution_receipt': produced(receipt, 'execution-receipt'),
            'provisioning_receipt': produced(provision, 'provisioning-receipt')}
