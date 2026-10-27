"""Independent candidate, model-call and protected development-execution joins."""
import json

from ..builder_mode import builder_mode

from .stages import ResearchChecks, require
from .prediction_bundle import inspect_bundle
from ..contracts import validate
from ..environment import validate_lock

BUILD_SCHEMA = 'urn:ai4r:prediction-build-receipt:3.0.0'


class LoopBuilderChecks(ResearchChecks):
    def __init__(self, stage, **kwargs):
        super().__init__(stage, **kwargs)
        self.check_ids = ['bounded_development_tests' if key == 'no_trial_no_install' else key for key in self.check_ids]

    async def _builder(self, ctx, inputs, outputs):
        manifest, bundle = outputs['manifest'], outputs['bundle']
        require(manifest['blueprint_ref'] == ctx.input_ref('blueprint'), 'blueprint_unchanged')
        require(manifest['environment_ref'] == inputs['blueprint']['environment_ref'] == ctx.input_ref('lock'), 'environment_unchanged')
        pins = validate_lock(inputs['lock'], ctx.read_blob, inputs['lock']['platform'])
        checked = inspect_bundle(bundle, ['accuracy'], pins)
        require(manifest['archive_ref'] == ctx.output_refs['bundle'], 'bundle_hash_matches')
        require(len(manifest['files']) == 3 and {row['path'] for row in manifest['files']} == set(checked['files']), 'required_files_present')
        require(all(ctx.read_blob(row['artifact_ref']) == checked['files'][row['path']] for row in manifest['files']), 'bundle_hash_matches')
        require(checked['files']['requirements.txt'] == ctx.read_blob(inputs['lock']['requirements_ref'])
                and manifest['dependencies'] == checked['dependencies'], 'dependencies_pinned')
        offers = [row['record'] for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('host-record-proposal',))
                  if row['record'].get('key') == 'build_receipt' and row['record'].get('attempt_id') == ctx.contract['attempt_id']
                  and row['record'].get('subnode_id') == ctx.contract['subnode_id']]
        require(len(offers) == 1, 'build_receipt_ready')
        receipt = ctx.read_json(offers[0]['ref']); validate(BUILD_SCHEMA, receipt)
        require(receipt['manifest_ref'] == ctx.output_refs['manifest'] and receipt['archive_ref'] == ctx.output_refs['bundle']
                and receipt['blueprint_ref'] == ctx.input_ref('blueprint') and receipt['environment_ref'] == ctx.input_ref('lock'), 'build_receipt_ready')
        require(receipt['file_checks'] == checked['file_checks'] and receipt['output_format_check'] == checked['output_format_check']
                and receipt['dependencies'] == checked['dependencies'] and receipt['dependencies_all_pinned']
                and receipt['forbidden_scan_result'] == 'pass' and receipt['trial_executed'] is True
                and receipt['packages_installed'] == bool(pins) and receipt['readiness'] == 'READY', 'build_receipt_ready')
        starts = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-start',))
                  if row['record'].get('contract_ref') == ctx.observation['contract_ref']]
        require(len(starts) == receipt['candidate_count'] <= 3, 'bounded_development_tests')
        calls = []
        for entry in starts:
            start = entry['record']; ref = ctx.store.record_ref(start['call_id']); call = ctx.read_json(ref)
            require(ref in ctx.observation['trace_refs'] and ctx.store.record_kind(ref) == 'model-call'
                    and call['outcome'] == 'completed' and call['observed_runtime'] is True
                    and all(start[key] == call[key] for key in ('invocation_id', 'execution_id'))
                    and start['call_id'] == call['id'], 'bounded_development_tests')
            calls.append(call)
        # Host call ordinals, not database iteration order, identify the final edit.
        ordinal_of = lambda row: ctx.read_json(row['record']['call_claim_ref'])['call_ordinal']
        starts.sort(key=ordinal_of)
        require([ordinal_of(row) for row in starts] == list(range(1, len(starts)+1)), 'bounded_development_tests')
        final_id = starts[-1]['record']['call_id']
        final_call = next(call for call in calls if call['id'] == final_id)
        returned = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-output',))
                    if row['record'].get('call_id') == final_id and row['record'].get('invocation_id') == final_call['invocation_id']]
        require(len(returned) == 1 and returned[0]['ref'] in final_call['evidence_refs'], 'bounded_development_tests')
        response = json.loads(returned[0]['record']['text'])
        require(set(response) == {'files', 'tests'} and set(response['files']) == set(checked['files'])
                and all(text.encode() == checked['files'][name] for name, text in response['files'].items()), 'bundle_hash_matches')
        executions = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('builder_test_execution',))
                      if row['record'].get('contract_ref') == ctx.observation['contract_ref']]
        require(len(executions) == len(receipt['test_report_refs']), 'bounded_development_tests')
        reports = []
        for ref in receipt['test_report_refs']:
            report = ctx.read_json(ref)
            require(any(row['record'] == report for row in executions)
                    and report['schema'] == 'ai4r-builder-test:1'
                    and report['invocation_id'] == final_call['invocation_id']
                    and report['execution_id'] == final_call['execution_id'], 'bounded_development_tests')
            require(type(report['ordinal']) is int and 1 <= report['ordinal'] <= len(starts), 'bounded_development_tests')
            history_id = starts[report['ordinal']-1]['record']['call_id']
            history_call = next(call for call in calls if call['id'] == history_id)
            history_outputs = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-output',))
                               if row['record'].get('call_id') == history_id and row['record'].get('invocation_id') == history_call['invocation_id']]
            require(len(history_outputs) == 1 and history_outputs[0]['ref'] in history_call['evidence_refs'], 'bounded_development_tests')
            history_response = json.loads(history_outputs[0]['record']['text'])
            history_manifest = ctx.read_json(report['manifest_ref'])
            history = inspect_bundle(ctx.read_blob(history_manifest['archive_ref']), ['accuracy'], pins)
            require(history_manifest['blueprint_ref'] == ctx.input_ref('blueprint')
                    and history_manifest['environment_ref'] == ctx.input_ref('lock')
                    and set(history_response) == {'files', 'tests'}
                    and set(history_response['files']) == set(history['files'])
                    and all(text.encode() == history['files'][name] for name, text in history_response['files'].items())
                    and ctx.read_blob(report['tests_ref']) == history_response['tests'].encode(), 'bounded_development_tests')
            reports.append(report)
        require(reports and [row['ordinal'] for row in reports] == sorted({row['ordinal'] for row in reports})
                and reports[-1]['ordinal'] == receipt['candidate_count']
                and all(row['status'] == 'failed' for row in reports[:-1]), 'bounded_development_tests')
        final = reports[-1]
        require(final['status'] == 'passed' and final['manifest_ref'] == ctx.output_refs['manifest']
                and ctx.read_blob(final['tests_ref']) == response['tests'].encode(), 'bounded_development_tests')
        require(len(final['runs']) == 2, 'bounded_development_tests')
        for raw in final['runs']:
            proof = ctx.read_json(raw['observed_limits']['isolation_probe_ref'])
            require(raw['observed_runtime'] is True and raw['exit_code'] == 0 and raw['termination_reason'] == 'completed'
                    and raw['contract_ref'] == ctx.observation['contract_ref'] and raw['invocation_id'] == final_call['invocation_id']
                    and raw['subject_ref'] == ctx.output_refs['bundle'] and proof.get('ready') is True
                    and raw['observed_limits'].get('network') == 'none'
                    and proof.get('executor_uid') == 10002 and proof.get('executor_gid') == 10002, 'bounded_development_tests')
        # Reparse raw smoke stdout; neither a producer's tests nor a report's
        # prediction_output_valid flag substitutes for this input-aware check.
        from ..trusted_scoring import parse_public_dataset, parse_predictions
        public = parse_public_dataset(ctx.read_blob(inputs['validation_resource']['files'][0]['artifact_ref']))
        parse_predictions(ctx.read_blob(final['runs'][1]['stdout_ref']), public, max_stdout_bytes=1024*1024)
        declaration = ctx.read_json(ctx.contract['bindings'][0]['declaration_ref'])
        require(builder_mode(declaration) == 'loop'
                and declaration['needs']['model']['tool_calling'] is False
                and declaration['budget']['per_call']['invocations'] == 3, 'bounded_development_tests')
