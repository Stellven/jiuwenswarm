"""Independent input-aware joins for the root-scored classification release."""
import hashlib
from pathlib import Path

from .stages import ResearchChecks, require, resolve_all
from .research import validate_benchmark
from ..contracts import ResearchError, validate
from ..environment import validate_lock
from ..metric_contract import validate_metric_declarations, validate_empirical_metric_ids
from ..trusted_scoring import BUILD_SCHEMA, SCORE_KIND, scored_empirical_row, failed_empirical_row
from ..process_evidence import validate_process_evidence


class BlindBenchmarkChecks(ResearchChecks):
    async def _benchmark(self, ctx, inputs, outputs):
        blueprint, manifest = inputs['hypothesis_blueprint'], inputs['poc_manifest']
        payload, receipt, provisioning = outputs['benchmark_payload'], outputs['execution_receipt'], outputs['provisioning_receipt']
        validate_metric_declarations(blueprint['metrics'])
        ready = inputs['build_receipt']; validate('urn:ai4r:prediction-build-receipt:'+ready['schema_version'] if ready['schema_version'] in {'3.0.0','4.0.0'} else BUILD_SCHEMA, ready)
        require(ready['readiness'] == 'READY' and (ready['schema_version'] in {'3.0.0','4.0.0'} or (not ready['trial_executed'] and not ready['packages_installed']))
                and ready['manifest_ref'] == ctx.input_ref('poc_manifest') and ready['archive_ref'] == ctx.input_ref('poc_artifact_bundle'), 'build_receipt_ready')
        require(payload['blueprint_ref'] == receipt['blueprint_ref'] == ctx.input_ref('hypothesis_blueprint')
                and payload['poc_ref'] == receipt['poc_ref'] == ctx.input_ref('poc_manifest'), 'protocol_matches_blueprint')
        require(payload['execution_receipt_ref'] == ctx.output_refs['execution_receipt']
                and payload['provisioning_receipt_ref'] == ctx.output_refs['provisioning_receipt']
                and payload['resource_refs'] == blueprint['resource_refs'], 'protocol_matches_blueprint')
        resolve_all(outputs, ctx.read_blob)
        empirical = ctx.read_json(receipt['empirical_results_ref']); validate('empirical-results:field-contract:2', empirical)
        pins = validate_lock(inputs['environment_lock'], ctx.read_blob, inputs['environment_lock']['platform'])
        validate_benchmark(blueprint, manifest, payload, receipt, provisioning, empirical, ctx.read_blob, lock_pins=pins)
        protected = [item['record']['receipt'] for item in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('scientific_execution',))
                     if item['record'].get('attempt_id') == ctx.contract['attempt_id'] and item['record'].get('node_id') == ctx.contract['node_id']]
        require(len(protected) == len(receipt['runs']), 'raw_repeats_present')
        expected_data = [row for row in inputs['validation_resource']['files'] if row['path'] == 'data.json']
        require(len(expected_data) == 1 and len(inputs['validation_resource']['files']) == 1, 'protocol_matches_blueprint')
        from .. import trusted_scoring
        scorer_digest = hashlib.sha256(Path(trusted_scoring.__file__).read_bytes()).hexdigest()
        for public, row in zip(receipt['runs'], empirical['runs']):
            matching = [raw for raw in protected if raw['sequence'] == public['sequence']]
            require(len(matching) == 1, 'raw_repeats_present'); raw = matching[0]
            require(all(raw[key] == public[key] for key in ('sequence', 'role', 'repeat_index', 'seed', 'subject_ref',
                'exit_code', 'started_at', 'wall_time_s', 'timeout_s', 'stdout_ref', 'stderr_ref'))
                and raw['argv'] == public['command'], 'protocol_matches_blueprint')
            require(ctx.read_json(raw['hardware_ref']) == receipt['hardware_inventory'], 'hardware_inventory_captured')
            if 'trusted_scoring_ref' in raw:
                ref = raw['trusted_scoring_ref']
                require(ref in payload['raw_evidence_refs'] and ctx.store.record_kind(ref) == SCORE_KIND,
                        'values_match_empirical_results')
                score = ctx.read_json(ref)
                require(ctx.store.record_ref(score['id']) == ref and score['run_id'] == ctx.contract['run_id']
                    and score['node_id'] == ctx.contract['node_id'] and score['attempt_id'] == ctx.contract['attempt_id']
                    and score['contract_ref'] == ctx.observation['contract_ref']
                    and score['validation_ref'] == ctx.input_ref('validation_resource')
                    and score['public_data_sha256'] == expected_data[0]['artifact_ref']['sha256']
                    and score['scorer_sha256'] == scorer_digest, 'values_match_empirical_results')
                actual = scored_empirical_row(raw, score)
            else:
                actual = failed_empirical_row(raw)
            validate_empirical_metric_ids(actual)
            require(actual == row, 'values_match_empirical_results')
            if raw.get('execution_mode') == 'm1_app_process':
                require(validate_process_evidence(ctx.store, raw, expected_uid=10002, expected_gid=10002,
                    contract_ref=ctx.observation['contract_ref'], invocation_id=ctx.observation.get('invocation_id'),
                    job_id=raw.get('job_id')), 'raw_repeats_present')
            else:
                require(raw['observed_limits'].get('network') == 'none', 'network_policy_respected')
