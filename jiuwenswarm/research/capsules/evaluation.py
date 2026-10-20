"""One qualitative assessment with deterministic outcome checks outside the worker."""
from ._common import ask, produced
from ..science import rule_text


async def execute(ctx, inputs):
    verdict = await ask(ctx, 'Scientific Evaluation', 'Write evaluation-verdict2.0.0 using the frozen blueprint and accepted payload only. '
                        'Exactly one finding per registered metric in blueprint order with copied baseline/treatment values. '
                        'Use success->PASS,falsification->FAIL,registered conditional->CONDITIONALLY_ACCEPTABLE,otherwise INCONCLUSIVE; '
                        'null side is INCONCLUSIVE/unmeasured. Thresholds never change. Overall first match: implausible->INCONCLUSIVE, '
                        'anyFAIL,anyINCONCLUSIVE,anyCONDITIONALLY_ACCEPTABLE,elsePASS. aggregation_rule m1_conjunctive_v1. '
                        'completeness.status incomplete iff an unmeasured metric; plausibility plausible/implausible/not_assessable. '
                        'Blockers nonempty iff unmeasured or implausible. Keep residual_risks/followups; suggestions never execute. '
                        'Copy rule_text exactly from registered_rule_text for its metric and rule_applied. '
                        'Valid negative science must remain deliverable. No experiments, patches or new metrics.',
                        dict(inputs, input_refs={p: ctx.input_ref(p) for p in inputs},
                             registered_rule_text={rule['metric_id']: {key: rule_text(rule, key) for key in
                                 ['success', 'falsification', 'middle', 'unmeasured'] + (['conditional'] if rule['conditional_rule'] else [])}
                                                   for rule in inputs['hypothesis_blueprint']['outcome_rules']}))
    return {'evaluation_verdict': produced(verdict, 'evaluation-verdict')}
