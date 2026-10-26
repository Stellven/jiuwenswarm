"""Independent joins for protected agentic Builder execution and tested snapshot."""
from __future__ import annotations

import hashlib
import json

from .stages import ResearchChecks, require
from ..pi_protocol import inspect_pi_bundle, validate_pi_request
from ..environment import validate_lock
from ..trusted_scoring import parse_public_dataset, parse_predictions
from ..pi_protocol import parse_pi_output
from .prediction_bundle import inspect_bundle as inspect_predictions
from ..process_evidence import validate_process_evidence

BUILD_SCHEMA = 'urn:ai4r:prediction-build-receipt:4.0.0'
DELIVERY_FILES = {'requirements.txt', 'poc_patch.py', 'run_benchmark.py'}
WORKSPACE_FILES = DELIVERY_FILES | {'tests.py'}
MUTATIONS = {'write_file', 'apply_patch'}


class AgentBuilderChecks(ResearchChecks):
    def __init__(self, stage, **kwargs):
        super().__init__(stage, **kwargs)
        self.check_ids = ['bounded_development' if key in {'no_trial_no_install', 'bounded_development_tests'} else key
                          for key in self.check_ids]

    async def _builder(self, ctx, inputs, outputs):
        manifest, bundle = outputs['manifest'], outputs['bundle']
        blueprint, lock = inputs['blueprint'], inputs['lock']
        require(manifest['blueprint_ref'] == ctx.input_ref('blueprint'), 'blueprint_unchanged')
        require(manifest['environment_ref'] == blueprint['environment_ref'] == ctx.input_ref('lock'), 'environment_unchanged')
        pins = validate_lock(lock, ctx.read_blob, lock['platform'])
        public_raw = ctx.read_blob(inputs['validation_resource']['files'][0]['artifact_ref'])
        is_pi = False
        try:
            is_pi = validate_pi_request(public_raw) >= 0
        except ValueError:
            pass
        checked = (inspect_pi_bundle(bundle, pins) if is_pi else
                   inspect_predictions(bundle, [item['metric_id'] for item in blueprint['metrics']], pins))
        require(manifest['archive_ref'] == ctx.output_refs['bundle'], 'bundle_hash_matches')
        files = {row['path']: row for row in manifest['files']}
        require(set(files) == DELIVERY_FILES and len(files) == 3, 'required_files_present')
        require(all(ctx.read_blob(files[name]['artifact_ref']) == checked['files'][name] for name in DELIVERY_FILES), 'bundle_hash_matches')
        require(checked['files']['requirements.txt'] == ctx.read_blob(lock['requirements_ref'])
                and manifest['dependencies'] == checked['dependencies'], 'dependencies_pinned')
        receipts = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('builder_agent_execution',))
                   if row['record'].get('contract_ref') == ctx.observation['contract_ref']]
        require(len(receipts) == 1, 'bounded_development')
        journal_ref = receipts[0]['ref']
        journal = ctx.read_json(journal_ref)
        require(journal == receipts[0]['record'] and journal.get('schema') == 'ai4r-builder-agent-execution:1', 'bounded_development')
        require(journal.get('contract_ref') == ctx.observation['contract_ref']
                and journal.get('manifest_ref') == ctx.output_refs['manifest']
                and journal.get('archive_ref') == ctx.output_refs['bundle'], 'bounded_development')
        final_files = journal.get('files')
        require(type(final_files) is dict and set(final_files) == WORKSPACE_FILES
                and all(type(text) is str for text in final_files.values())
                and all(final_files[name].encode('utf-8') == checked['files'][name]
                        for name in DELIVERY_FILES), 'bundle_hash_matches')
        def snapshot_digest(values):
            hashes = {name: hashlib.sha256(text.encode('utf-8')).hexdigest()
                      for name, text in sorted(values.items())}
            return hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        require(snapshot_digest(final_files) == journal.get('snapshot_sha256'), 'bounded_development')
        actions = journal.get('actions')
        require(type(actions) is list and 1 <= len(actions) <= 40, 'bounded_development')
        replay = journal.get('initial_files')
        require(type(replay) is dict and set(replay) == WORKSPACE_FILES
                and all(type(text) is str for text in replay.values()), 'bounded_development')
        for index, action in enumerate(actions, 1):
            require(type(action) is dict and action.get('ordinal') == index, 'bounded_development')
            name, args = action.get('action'), action.get('arguments')
            require(type(args) is dict and type(action.get('model_ordinal')) is int
                    and 1 <= action['model_ordinal'] <= 20, 'bounded_development')
            require(action.get('before_sha256') == snapshot_digest(replay), 'bounded_development')
            call_ref, output_ref = action.get('model_call_ref'), action.get('model_output_ref')
            require(ctx.store.record_kind(call_ref) == 'model-call' and
                    ctx.store.record_kind(output_ref) == 'model-call-output', 'bounded_development')
            call = ctx.read_json(call_ref)
            output = ctx.read_json(output_ref)
            require(call.get('outcome') == 'completed' and call.get('observed_runtime') is True
                    and call.get('contract_ref')==journal['contract_ref']
                    and call.get('invocation_id')==journal['invocation_id']
                    and call.get('execution_id')==journal['execution_id']
                    and call_ref in ctx.observation['trace_refs'] and output_ref in call.get('evidence_refs', [])
                    and output.get('call_id') == call.get('id')
                    and output.get('invocation_id') == journal.get('invocation_id')
                    and json.loads(output['text']) == {'action': name, 'arguments': args}, 'bounded_development')
            starts = [row['record'] for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-start',))
                      if row['record'].get('contract_ref') == journal['contract_ref']
                      and row['record'].get('invocation_id') == journal['invocation_id']
                      and row['record'].get('execution_id') == journal['execution_id']
                      and ctx.read_json(row['record']['call_claim_ref']).get('call_ordinal') == action['model_ordinal']]
            require(len(starts) == 1 and starts[0].get('call_id') == call.get('id'), 'bounded_development')
            if name in MUTATIONS:
                path = args.get('path')
                require(path in WORKSPACE_FILES, 'bounded_development')
                if action.get('result', {}).get('ok') is True:
                    before = replay[path]
                    require(hashlib.sha256(before.encode()).hexdigest() == args.get('expected_sha256'), 'bounded_development')
                    if name == 'write_file':
                        after = args.get('content')
                        require(type(after) is str, 'bounded_development')
                    else:
                        old, new = args.get('old'), args.get('new')
                        require(type(old) is str and type(new) is str and before.count(old) == 1, 'bounded_development')
                        after = before.replace(old, new, 1)
                    replay[path] = after
            require(action.get('after_sha256') == snapshot_digest(replay), 'bounded_development')
        require(replay == final_files, 'bounded_development')
        require(snapshot_digest(final_files) == journal.get('submitted_snapshot_sha256'), 'bounded_development')

        proposals = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('host-record-proposal',))
                     if row['record'].get('key') == 'build_receipt'
                     and row['record'].get('attempt_id') == ctx.contract['attempt_id']
                     and row['record'].get('subnode_id') == ctx.contract['subnode_id']]
        require(len(proposals) == 1, 'build_receipt_ready')
        receipt = ctx.read_json(proposals[0]['record']['ref'])
        submissions=[row['record'] for row in ctx.store.iter_records(run_id=ctx.contract['run_id'],kinds=('builder_agent_submission',))
                     if row['record'].get('contract_ref')==journal['contract_ref']]
        require(len(submissions)==1 and submissions[0]['build_receipt_ref']==proposals[0]['record']['ref']
                and submissions[0]['journal_ref']==journal_ref
                and submissions[0]['manifest_ref']==ctx.output_refs['manifest']
                and submissions[0]['archive_ref']==ctx.output_refs['bundle'],'build_receipt_ready')
        from ..contracts import validate
        validate(BUILD_SCHEMA, receipt)
        require(receipt['manifest_ref'] == ctx.output_refs['manifest'] and receipt['archive_ref'] == ctx.output_refs['bundle']
                and receipt['blueprint_ref'] == ctx.input_ref('blueprint') and receipt['environment_ref'] == ctx.input_ref('lock')
                and receipt['journal_ref'] == journal_ref, 'build_receipt_ready')
        require(receipt['workspace_sha256'] == journal['snapshot_sha256']
                and receipt['submitted_snapshot_sha256'] == journal['submitted_snapshot_sha256'], 'build_receipt_ready')
        require(receipt['development_only'] is True and receipt['trial_executed'] is True
                and receipt['packages_installed'] is bool(pins) and receipt['readiness'] == 'READY', 'build_receipt_ready')
        require(receipt['file_checks']==checked['file_checks'] and receipt['dependencies']==checked['dependencies']
                and receipt['dependencies_all_pinned'] is True and receipt['forbidden_scan_result']=='pass',
                'build_receipt_ready')
        require(1 <= receipt['model_call_count'] <= 20 and 1 <= receipt['tool_operation_count'] <= 40
                and receipt['tool_operation_count'] == len(actions)
                and 0 <= receipt['execution_job_count'] <= 12, 'bounded_development')
        starts=[row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'],kinds=('model-call-start',))
                if row['record'].get('contract_ref')==journal['contract_ref']
                and row['record'].get('invocation_id')==journal['invocation_id']]
        require(receipt['model_call_count'] == len(starts)
                and sorted(ctx.read_json(row['record']['call_claim_ref'])['call_ordinal'] for row in starts)
                    == list(range(1,len(starts)+1)), 'bounded_development')
        require([row['model_ordinal'] for row in actions] == sorted({row['model_ordinal'] for row in actions}),
                'bounded_development')
        reports = journal.get('checks')
        require(type(reports) is dict and set(reports) == {'compile', 'unit', 'smoke'}, 'bounded_development')
        for phase, entry in reports.items():
            require(type(entry) is dict and entry.get('status') == 'passed'
                    and entry.get('snapshot_sha256') == journal['submitted_snapshot_sha256'], 'bounded_development')
            report_ref = entry.get('report_ref')
            require(ctx.store.record_kind(report_ref) == 'builder_agent_check', 'bounded_development')
            report = ctx.read_json(report_ref)
            require(report.get('passed') is True and report.get('check') == phase
                    and report.get('snapshot_sha256', entry['snapshot_sha256']) == entry['snapshot_sha256']
                    and report.get('contract_ref') == journal['contract_ref']
                    and report.get('invocation_id') == journal['invocation_id'], 'bounded_development')
            if phase == 'compile':
                require(report.get('host_compilation') is True, 'bounded_development')
            else:
                runs = report.get('runs')
                require(type(runs) is list and len(runs) == 1, 'bounded_development')
                run = runs[0]
                require(run.get('observed_runtime') is True and run.get('exit_code') == 0
                        and run.get('termination_reason') == 'completed'
                        and run.get('contract_ref') == journal['contract_ref']
                        and run.get('invocation_id') == journal['invocation_id'], 'bounded_development')
                limits=run.get('observed_limits',{})
                if run.get('execution_mode') == 'm1_app_process':
                    require(validate_process_evidence(ctx.store, run, expected_uid=10002, expected_gid=10002,
                        contract_ref=ctx.observation['contract_ref'], invocation_id=journal['invocation_id'],
                        job_id=run.get('job_id')), 'bounded_development')
                else:
                    proof=ctx.read_json(limits.get('isolation_probe_ref'))
                    require(proof.get('ready') is True and proof.get('executor_uid')==10002
                        and proof.get('executor_gid')==10002 and proof.get('no_new_privileges')=='1'
                        and int(proof.get('cap_effective','-1'),16)==0
                        and proof.get('network')=='none' and limits.get('network')=='none',
                        'bounded_development')
                tested=ctx.read_json(report['manifest_ref'])
                require(tested['archive_ref']==ctx.output_refs['bundle'] and run['subject_ref']==ctx.output_refs['bundle'],
                    'bounded_development')
                if phase == 'smoke':
                    stdout = ctx.read_blob(run['stdout_ref'])
                    if is_pi:
                        digits = validate_pi_request(public_raw)
                        parse_pi_output(stdout, digits)
                    else:
                        parse_predictions(stdout, parse_public_dataset(public_raw), max_stdout_bytes=1024 * 1024)
        require(receipt['test_report_refs'] == [reports[name]['report_ref'] for name in ('compile', 'unit', 'smoke')],
                'bounded_development')
