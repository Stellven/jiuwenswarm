"""Independent mandatory checks over complete research output sets."""
from __future__ import annotations

import hashlib
import json

from ..contracts import ResearchError, validate
from ..environment import parse_requirements, validate_lock
from ..science import empirical_row, validate_rule_regions
from ..state import json_bytes
from .research import (CheckError, BUNDLE_FILES, _refs, inspect_bundle, rank_opportunities,
                       validate_search, validate_blueprint, validate_benchmark,
                       validate_scientific_verdict, validate_delivery)


def require(condition, check_id):
    if not condition:
        raise CheckError(check_id)


def resolve_all(value, read_blob):
    for ref in _refs(value):
        require(hashlib.sha256(read_blob(ref)).hexdigest() == ref['sha256'], 'ref_hash_match')


def protected_builder_observation(ctx):
    """Read broker evidence after execution closes; never authorize another effect."""
    receipts = [entry for entry in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('builder_execution',))
                if entry['record'].get('contract_ref') == ctx.observation['contract_ref']]
    require(len(receipts) == 1, 'no_trial_no_install')
    observed = ctx.read_json(receipts[0]['ref'])
    require(observed == receipts[0]['record'], 'no_trial_no_install')
    starts = [entry for entry in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('model-call-start',))
              if entry['record'].get('contract_ref') == ctx.observation['contract_ref']
              and entry['record'].get('invocation_id') == observed.get('invocation_id')]
    require(len(starts) == 1 and starts[0]['ref'] == observed.get('model_call_start_ref'), 'no_trial_no_install')
    start = ctx.read_json(starts[0]['ref'])
    require(all(start.get(key) == observed.get(key) for key in ('contract_ref', 'invocation_id', 'execution_id', 'call_id', 'route_ref', 'input_ref')),
            'no_trial_no_install')
    require(observed.get('observed_runtime') is True and observed.get('credential_removed') is True
            and observed.get('terminal_reason') == 'completed', 'no_trial_no_install')
    return observed


class ResearchChecks:
    """One bundle invocation evaluates all source predicates before any verifier.

    A failed joint predicate rejects the complete coupled output set. Individual
    results name the actual first diagnostic; no omitted predicate becomes PASS.
    Protected host identity/limit checks are composed by the core check engine.
    """
    def __init__(self, stage, *, executor=None):
        from ..capsules.assets import source_metadata
        self.stage, self.executor = stage, executor
        self.metadata = source_metadata()[stage]
        self.check_ids = [row[0].strip('`') for row in self.metadata['checks']]
        if stage == 'benchmark':
            self.check_ids += ['empirical_sequence_contiguous', 'empirical_values_finite']

    async def __call__(self, ctx, inputs, outputs):
        status, reason = 'PASS', 'All source predicates for the complete coupled output set were evaluated successfully.'
        try:
            for port in self.metadata['declaration']['ports']['outputs']:
                require(port['name'] in outputs, port['name'] + '_schema')
                value = outputs[port['name']]
                if isinstance(value, dict):
                    validate(port['schema_ref'], value)
                require(hashlib.sha256(ctx.read_blob(ctx.output_refs[port['name']])).hexdigest() == ctx.output_refs[port['name']]['sha256'], 'ref_hash_match')
            await getattr(self, '_' + self.stage)(ctx, inputs, outputs)
        except ResearchError as exc:
            status = 'ENVIRONMENT_BLOCKED' if exc.code in {'unavailable', 'evidence_unavailable', 'runtime_unavailable'} else 'FAIL'
            reason = exc.code
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            status, reason = 'FAIL', getattr(exc, 'check_id', type(exc).__name__)
        except (OSError, TimeoutError) as exc:
            status, reason = 'ENVIRONMENT_BLOCKED', type(exc).__name__
        evidence = list(ctx.output_refs.values())
        return [{'check_id': key, 'outcome': status, 'reason': reason, 'evidence_refs': evidence} for key in self.check_ids]

    async def _search(self, ctx, inputs, outputs):
        candidate = outputs['candidate_set']
        require(candidate['brief_ref'] == ctx.input_ref('brief'), 'brief_binding')
        require(candidate['scope_ref'] == ctx.input_ref('search_scope'), 'scope_binding')
        validate_search(inputs['search_scope'], candidate, ctx.read_blob)

    async def _screening(self, ctx, inputs, outputs):
        screening, card = outputs['screening_result'], outputs['opportunity_card']
        candidates, rubric, brief = inputs['candidate_set'], inputs['screening_rubric'], inputs['brief']
        for output in [screening, card]:
            require(output['candidate_ref'] == ctx.input_ref('candidate_set') and output['brief_ref'] == ctx.input_ref('brief'), 'candidate_binding')
        require(screening['rubric_ref'] == ctx.input_ref('screening_rubric'), 'rubric_pinned')
        declaration = ctx.read_json(ctx.contract['bindings'][0]['declaration_ref'])
        require(any(item['path'] == 'screening_rubric.json' and item['sha256'] == screening['rubric_ref']['sha256'] for item in declaration['identity']['body']), 'rubric_pinned')
        validate('screening-rubric', rubric)
        ranking, selected = rank_opportunities(candidates['ideas'], screening['scores'], rubric)
        require(screening['ranking'] == ranking, 'ranking_deterministic')
        require(screening['selected_idea_id'] == selected == card['idea_id'], 'selected_is_top1')
        idea = next(item for item in candidates['ideas'] if item['idea_id'] == selected)
        score = next(item for item in screening['scores'] if item['idea_id'] == selected)
        require(card['screening_ref'] == ctx.output_refs['screening_result'] and card['rank'] == 1, 'card_matches_selection')
        for name in ['title', 'citation_ids', 'assumptions', 'risks']:
            require(card[name] == idea[name], 'card_matches_selection')
        require(card['scores'] == {key: score[key] for key in ['novelty', 'feasibility', 'compute_alignment', 'total']}, 'card_matches_selection')
        carried = [entry['text'] for entry in brief['constraints']] + [entry['text'] for entry in brief['mandatory_requirements']]
        require(set(carried) <= set(card['constraints']), 'card_constraints_carried')
        expected = [{'idea_id': entry['idea_id'], 'disposition': entry['disposition'], 'reason': entry['disposition_reason']}
                    for entry in screening['scores'] if entry['idea_id'] != selected]
        require(len(expected) == len(card['other_dispositions']) and sorted(expected, key=lambda row: row['idea_id']) == sorted(card['other_dispositions'], key=lambda row: row['idea_id']), 'card_dispositions_complete')

    async def _hypothesis(self, ctx, inputs, outputs):
        blueprint = outputs['blueprint']
        require(blueprint['brief_ref'] == ctx.input_ref('brief') and blueprint['opportunity_ref'] == ctx.input_ref('opportunity'), 'resource_refs_resolve')
        require(blueprint['baseline_identity']['resource_ref'] == ctx.input_ref('baseline_resource') and blueprint['validation_resource_ref'] == ctx.input_ref('validation_resource'), 'baseline_identity_resolves')
        validate_blueprint(blueprint, inputs['brief'], inputs['baseline_resource'], inputs['validation_resource'], ctx.read_blob)
        # Candidate bytes are immutable before checking. The core's atomic node
        # acceptance binds this exact Ref; it never serializes a replacement.
        require(ctx.read_blob(ctx.output_refs['blueprint']) == json_bytes(blueprint), 'blueprint_frozen_hash_recorded')

    async def _builder(self, ctx, inputs, outputs):
        manifest, bundle = outputs['manifest'], outputs['bundle']
        blueprint, lock = inputs['blueprint'], inputs['lock']
        require(manifest['blueprint_ref'] == ctx.input_ref('blueprint'), 'blueprint_unchanged')
        require(manifest['environment_ref'] == blueprint['environment_ref'] == ctx.input_ref('lock'), 'environment_unchanged')
        pins = validate_lock(lock, ctx.read_blob, lock['platform'])
        checked = inspect_bundle(bundle, [m['metric_id'] for m in blueprint['metrics']], pins)
        require(manifest['archive_ref'] == ctx.output_refs['bundle'], 'bundle_hash_matches')
        require({file['path'] for file in manifest['files']} == BUNDLE_FILES and len(manifest['files']) == 3, 'required_files_present')
        for file in manifest['files']:
            require(ctx.read_blob(file['artifact_ref']) == checked['files'][file['path']], 'bundle_hash_matches')
        require(manifest['dependencies'] == checked['dependencies'], 'dependencies_pinned')
        proposals = [item['record'] for item in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('host-record-proposal',))
                     if item['record'].get('key') == 'build_receipt' and item['record'].get('attempt_id') == ctx.contract['attempt_id'] and item['record'].get('subnode_id') == ctx.contract['subnode_id']]
        require(len(proposals) == 1, 'build_receipt_ready')
        receipt = ctx.read_json(proposals[0]['ref']); validate('build-receipt', receipt)
        require(receipt['manifest_ref'] == ctx.output_refs['manifest'] and receipt['archive_ref'] == ctx.output_refs['bundle']
                and receipt['blueprint_ref'] == ctx.input_ref('blueprint') and receipt['environment_ref'] == ctx.input_ref('lock'), 'build_receipt_ready')
        require(receipt['file_checks'] == checked['file_checks'] and receipt['output_format_check'] == checked['output_format_check']
                and receipt['dependencies'] == checked['dependencies'] and receipt['dependencies_all_pinned'] and receipt['forbidden_scan_result'] == 'pass'
                and not receipt['trial_executed'] and not receipt['packages_installed'] and receipt['readiness'] == 'READY', 'build_receipt_ready')
        observed = protected_builder_observation(ctx)
        require(observed['contract_ref'] == ctx.observation['contract_ref'] and observed['observed_runtime'] is True, 'no_trial_no_install')
        resolve_all(observed, ctx.read_blob)
        require(not observed['trial_executed'] and not observed['packages_installed'] and observed['terminal_reason'] in {'completed', 'success'}
                and bool(observed['identity']) and bool(observed['event_refs']) and bool(observed['route_ref']), 'no_trial_no_install')
        require(all(event['allowed'] is True and event['effect'] not in {'trial', 'package_install', 'network', 'measurement'} for event in observed['tool_events']), 'no_trial_no_install')
        declaration = ctx.read_json(ctx.contract['bindings'][0]['declaration_ref'])
        require(type(observed['tool_count']) is int and observed['tool_count'] == len(observed['tool_events'])
                and 0 <= observed['tool_count'] < min(40, declaration['budget']['per_call']['tool_calls']), 'no_trial_no_install')

    async def _benchmark(self, ctx, inputs, outputs):
        blueprint, manifest = inputs['hypothesis_blueprint'], inputs['poc_manifest']
        payload, receipt, provisioning = outputs['benchmark_payload'], outputs['execution_receipt'], outputs['provisioning_receipt']
        ready = inputs['build_receipt']
        require(ready['readiness'] == 'READY' and not ready['trial_executed'] and not ready['packages_installed']
                and ready['manifest_ref'] == ctx.input_ref('poc_manifest') and ready['archive_ref'] == ctx.input_ref('poc_artifact_bundle'), 'build_receipt_ready')
        require(payload['blueprint_ref'] == receipt['blueprint_ref'] == ctx.input_ref('hypothesis_blueprint') and payload['poc_ref'] == receipt['poc_ref'] == ctx.input_ref('poc_manifest'), 'protocol_matches_blueprint')
        require(payload['execution_receipt_ref'] == ctx.output_refs['execution_receipt'] and payload['provisioning_receipt_ref'] == ctx.output_refs['provisioning_receipt']
                and payload['resource_refs'] == blueprint['resource_refs'], 'protocol_matches_blueprint')
        resolve_all(outputs, ctx.read_blob)
        empirical = ctx.read_json(receipt['empirical_results_ref']); validate('empirical-results:field-contract:2', empirical)
        pins = validate_lock(inputs['environment_lock'], ctx.read_blob, inputs['environment_lock']['platform'])
        validate_benchmark(blueprint, manifest, payload, receipt, provisioning, empirical, ctx.read_blob, lock_pins=pins)
        protected_runs = [item['record']['receipt'] for item in ctx.store.iter_records(run_id=ctx.contract['run_id'], kinds=('scientific_execution',))
                          if item['record'].get('attempt_id') == ctx.contract['attempt_id'] and item['record'].get('node_id') == ctx.contract['node_id']]
        if len(protected_runs) != len(receipt['runs']):
            raise ResearchError('unavailable', 'Exact protected scientific execution observations are absent')
        for public, row in zip(receipt['runs'], empirical['runs']):
            matching = [raw for raw in protected_runs if raw['sequence'] == public['sequence']]
            require(len(matching) == 1, 'raw_repeats_present')
            raw = matching[0]
            require(all(raw[key] == public[key] for key in ['sequence', 'role', 'repeat_index', 'seed', 'subject_ref', 'exit_code', 'started_at', 'wall_time_s', 'timeout_s', 'stdout_ref', 'stderr_ref'])
                    and raw['argv'] == public['command'], 'protocol_matches_blueprint')
            require(ctx.read_json(raw['hardware_ref']) == receipt['hardware_inventory'], 'hardware_inventory_captured')
            actual = empirical_row(raw['sequence'], [m['metric_id'] for m in blueprint['metrics']], ctx.read_blob(raw['stdout_ref']), raw['exit_code'], raw.get('termination_reason'))
            require(actual == row, 'values_match_empirical_results')
            require(raw['observed_limits'].get('network') == 'none', 'network_policy_respected')

    async def _evaluation(self, ctx, inputs, outputs):
        blueprint, payload, verdict = inputs['hypothesis_blueprint'], inputs['benchmark_payload'], outputs['evaluation_verdict']
        require(verdict['brief_ref'] == ctx.input_ref('brief') and verdict['blueprint_ref'] == payload['blueprint_ref'] == ctx.input_ref('hypothesis_blueprint')
                and verdict['benchmark_ref'] == ctx.input_ref('benchmark_payload'), 'refs_match_inputs')
        for metric in blueprint['metrics']:
            validate_rule_regions(next(rule for rule in blueprint['outcome_rules'] if rule['metric_id'] == metric['metric_id']), metric['direction'])
        validate_scientific_verdict(blueprint, payload, verdict)
        for finding in verdict['findings']:
            rule = next(rule for rule in blueprint['outcome_rules'] if rule['metric_id'] == finding['metric_id'])
            require(finding['rule_applied'] != 'conditional' or rule['conditional_rule'] is not None, 'registered_rule_only')
            require(finding['classification'] != 'CONDITIONALLY_ACCEPTABLE' or finding['rule_applied'] == 'conditional', 'registered_rule_only')
            # Only canonical registered expressions are accepted by this carrier;
            # rationale remains free text for the independent semantic criteria.
            from ..science import rule_text
            require(finding['rule_text'] == rule_text(rule, finding['rule_applied']), 'registered_rule_only')

    async def _delivery(self, ctx, inputs, outputs):
        validate_delivery(inputs, {port: ctx.input_ref(port) for port in inputs}, outputs['delivery_manifest'], outputs['research_report'], ctx.read_blob)
