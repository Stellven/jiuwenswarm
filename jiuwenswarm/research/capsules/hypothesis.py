"""Freeze one scientific intervention before any generated code or measurement."""
from ..contracts.types import ResearchError
from ._common import ask, produced


async def execute(ctx, inputs):
    baseline, validation = inputs['baseline_resource'], inputs['validation_resource']
    if baseline['availability'] != 'available' or validation['availability'] != 'available' or not baseline['environment_ref'] or baseline['environment_ref'] != validation['environment_ref']:
        raise ResearchError('unavailable', 'Both captured resources require the same prepared environment')
    blueprint = await ask(ctx, 'Hypothesis', 'Write hypothesis-blueprint2.0.0 with one claim, mechanism and independent_variable; '
                          'dependent_variables and1..8 metric declarations, baseline_identity, resource_refs, environment_ref, '
                          'one outcome_rule per metric, repeat_count3..30, seed0..2147483647 and fixed_same_for_all_runs. '
                          'Rules use treatment operand, lt/le/eq/ge/gt and factor*baseline+offset or constant factor0. '
                          'Preserve every Brief target, constraint and nonnull comparison exactly. Success/falsification regions disjoint; '
                          'conditional_rule only in a registered CONDITIONALLY_ACCEPTABLE middle. Scope1..5 items,max_patch_files1, '
                          'must_not_change baseline/validation_data/measurement_functions/outcome_rules; verification_plan1..12 steps. '
                          'No trials, invented data, dependencies or post-hoc thresholds.',
                          dict(inputs, input_refs={p: ctx.input_ref(p) for p in inputs}))
    return {'blueprint': produced(blueprint, 'hypothesis-blueprint')}
