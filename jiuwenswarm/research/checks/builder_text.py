"""Independent checks for the tool-free Builder release, with real call joins."""
from __future__ import annotations

import json

from .stages import ResearchChecks, require
from .research import BUNDLE_FILES, inspect_bundle
from ..contracts import validate
from ..environment import validate_lock


class TextBuilderChecks(ResearchChecks):
    async def _builder(self, ctx, inputs, outputs):
        manifest, bundle = outputs['manifest'], outputs['bundle']
        blueprint, lock = inputs['blueprint'], inputs['lock']
        require(manifest['blueprint_ref'] == ctx.input_ref('blueprint'), 'blueprint_unchanged')
        require(manifest['environment_ref'] == blueprint['environment_ref'] == ctx.input_ref('lock'), 'environment_unchanged')
        checked = inspect_bundle(bundle, [metric['metric_id'] for metric in blueprint['metrics']],
                                 validate_lock(lock, ctx.read_blob, lock['platform']))
        require(manifest['archive_ref'] == ctx.output_refs['bundle'], 'bundle_hash_matches')
        require({row['path'] for row in manifest['files']} == BUNDLE_FILES and len(manifest['files']) == 3, 'required_files_present')
        for row in manifest['files']:
            require(ctx.read_blob(row['artifact_ref']) == checked['files'][row['path']], 'bundle_hash_matches')
        require(manifest['dependencies'] == checked['dependencies'], 'dependencies_pinned')
        proposals = [row['record'] for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('host-record-proposal',))
            if row['record'].get('key') == 'build_receipt' and row['record'].get('attempt_id') == ctx.contract['attempt_id']
            and row['record'].get('subnode_id') == ctx.contract['subnode_id']]
        require(len(proposals) == 1, 'build_receipt_ready')
        receipt = ctx.read_json(proposals[0]['ref'])
        validate('build-receipt', receipt)
        require(receipt['manifest_ref'] == ctx.output_refs['manifest'] and receipt['archive_ref'] == ctx.output_refs['bundle']
            and receipt['blueprint_ref'] == ctx.input_ref('blueprint') and receipt['environment_ref'] == ctx.input_ref('lock'), 'build_receipt_ready')
        require(receipt['file_checks'] == checked['file_checks'] and receipt['output_format_check'] == checked['output_format_check']
            and receipt['dependencies'] == checked['dependencies'] and receipt['dependencies_all_pinned']
            and receipt['forbidden_scan_result'] == 'pass' and not receipt['trial_executed']
            and not receipt['packages_installed'] and receipt['readiness'] == 'READY', 'build_receipt_ready')
        # No producer-authored runtime receipt establishes this claim. Re-read
        # the protected model owner records and compare the exact returned file
        # texts to the mechanically captured archive. The transport is tool-free.
        calls = [ctx.read_json(ref) for ref in ctx.observation['trace_refs']
            if ctx.store.record_kind(ref) == 'model-call']
        require(len(calls) == 1 and calls[0]['outcome'] == 'completed' and calls[0]['observed_runtime'] is True,
                'no_trial_no_install')
        call = calls[0]
        starts = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-start',))
            if row['record'].get('contract_ref') == ctx.observation['contract_ref']
            and row['record'].get('invocation_id') == call['invocation_id']
            and row['record'].get('execution_id') == call['execution_id']
            and row['record'].get('call_id') == call['id']]
        returned = [row for row in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-output',))
            if row['record'].get('invocation_id') == call['invocation_id'] and row['record'].get('call_id') == call['id']]
        require(len(starts) == len(returned) == 1 and returned[0]['ref'] in call['evidence_refs'], 'no_trial_no_install')
        payload = json.loads(returned[0]['record']['text'])
        require(set(payload) == {'files'} and set(payload['files']) == BUNDLE_FILES, 'no_trial_no_install')
        require(all(type(text) is str and text.encode('utf-8') == checked['files'][name]
            for name, text in payload['files'].items()), 'no_trial_no_install')
        declaration = ctx.read_json(ctx.contract['bindings'][0]['declaration_ref'])
        require(declaration['identity']['version_label'] == 'm1-2'
            and declaration['needs']['model']['tool_calling'] is False
            and declaration['budget']['per_call']['tool_calls'] == 0, 'no_trial_no_install')
