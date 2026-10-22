"""Freeze one scientific intervention before any generated code or measurement."""
import copy

from ..contracts import contract_schema
from ..contracts.types import ResearchError
from ._common import ask, produced


async def execute(ctx, inputs):
    baseline, validation = inputs['baseline_resource'], inputs['validation_resource']
    if baseline['availability'] != 'available' or validation['availability'] != 'available' or not baseline['environment_ref'] or baseline['environment_ref'] != validation['environment_ref']:
        raise ResearchError('unavailable', 'Both captured resources require the same prepared environment')
    reply_schema = copy.deepcopy(contract_schema('hypothesis-blueprint'))
    reply_schema['properties'].pop('dependent_variables')
    reply_schema['required'].remove('dependent_variables')
    blueprint = await ask(ctx, 'Hypothesis', 'Write hypothesis-blueprint2.0.0 with one claim, mechanism and independent_variable; '
                          'return its scientific fields except dependent_variables, which the carrier assembles as an exact index of '
                          'your metrics[].metric_id values before publication. Do not return that carrier-owned field. '
                          'Write1..8 metric declarations, baseline_identity, resource_refs, environment_ref, '
                          'one outcome_rule per metric, repeat_count3..30, seed0..2147483647 and fixed_same_for_all_runs. '
                          'Each metric_id is a unique lowercase identifier matching ^[a-z][a-z0-9_]*$; write exactly one outcome_rule '
                          'for each such ID and no undeclared IDs. Use the same exact identifiers in every metric reference. '
                          'Every Brief target_metrics[].id must appear as a metric target_id; target_id is null only for an added '
                          'metric without a Brief target. Give each metric its measurement, unit, aggregation, direction and valid bounds; '
                          'valid_min must not exceed valid_max when both are present. '
                          'Copy brief_ref and opportunity_ref from their exact bound input_refs. baseline_identity.resource_ref and '
                          'validation_resource_ref equal their corresponding bound input_refs. resource_refs contains exactly those '
                          'two resource Refs and no other resource. Copy baseline_identity.revision from the baseline snapshot and '
                          'choose an entry_point that is actually present in that snapshot files. Copy the same nonnull environment_ref '
                          'from both resource snapshots, never choose a different environment. Copy every Brief constraint text verbatim '
                          'into constraints. Preserve the accepted Brief objective and the selected opportunity without introducing '
                          'an unrelated intervention, data source or measured result. '
                          'Rules use treatment operand, lt/le/eq/ge/gt and factor*baseline+offset or constant factor0. '
                          'Preserve every Brief target, constraint and nonnull comparison exactly. Success/falsification regions disjoint; '
                          'For each nonnull Brief target comparison, copy its comparator and reference into the matching metric success rule, '
                          'set operand to treatment, and convert exactly: reference baseline means factor=comparison.value and offset=0; '
                          'reference constant means factor=0 and offset=comparison.value. A baseline-relative value is a multiplier, '
                          'never an absolute difference or percentage-point offset. Do not replace the accepted comparison with a '
                          'more plausible, stricter or weaker rule; do not silently repair or reinterpret the accepted Brief. '
                          'Each Brief target ID must appear as the corresponding metric target_id. A null comparison supplies no numeric '
                          'Brief threshold; do not claim a chosen scientific rule was a user-provided number. Self-review every nonnull '
                          'comparison against this exact conversion before returning. '
                          'For higher_better metrics, success comparator is gt/ge and falsification lt/le; for lower_better, '
                          'success is lt/le and falsification gt/ge. Success and falsification regions must never overlap, including '
                          'their equality boundaries. INCONCLUSIVE middle requires null conditional_rule and conditional_meaning. '
                          'CONDITIONALLY_ACCEPTABLE middle requires a nonnull conditional_rule and meaning, with its region outside '
                          'both success and falsification. Register these rules before measurements; do not select them from results. '
                          'Scope1..5 items,max_patch_files1, '
                          'must_not_change baseline/validation_data/measurement_functions/outcome_rules; verification_plan1..12 steps. '
                          'Before returning, self-review all exact input identities, target and constraint coverage, unique metric/rule '
                          'IDs, rule-direction families, disjoint boundaries, conditional nullability and scope/seed/repeat bounds. '
                          'No trials, invented data, dependencies or post-hoc thresholds.',
                          dict(inputs, input_refs={p: ctx.input_ref(p) for p in inputs}), reply_schema=reply_schema)
    blueprint['dependent_variables'] = [metric['metric_id'] for metric in blueprint['metrics']]
    return {'blueprint': produced(blueprint, 'hypothesis-blueprint')}
