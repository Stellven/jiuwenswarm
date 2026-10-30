"""One qualitative assessment with deterministic outcome checks outside the worker."""
from ._common import ask, produced
from ..science import ScienceError, classify_metric, overall_classification, rule_text


def fill_recomputed(verdict, blueprint, payload):
    """Carrier-owned fields of evaluation-verdict, computed as the deterministic check computes them.

    Copied baseline/treatment values, per-metric classification, rule_applied,
    threshold and rule_text, overall classification, aggregation rule and
    completeness status follow from the frozen blueprint and the accepted
    payload. The model keeps rationale, plausibility, blockers, risks and
    followups. Rationales become one line, as the Delivery report renders them.
    Anything misaligned is returned unchanged for the checks to reject.
    """
    try:
        order = [m['metric_id'] for m in blueprint['metrics']]
        rules = {r['metric_id']: r for r in blueprint['outcome_rules']}
        measured = {m['metric_id']: m for m in payload['metrics']}
        findings = {f['metric_id']: f for f in verdict['findings']}
        if len(findings) != len(verdict['findings']) or set(findings) != set(order) or set(measured) != set(order):
            return verdict
        rows, classes, unmeasured = [], [], False
        for metric_id in order:
            baseline, treatment = measured[metric_id]['baseline']['value'], measured[metric_id]['treatment']['value']
            classification, applied, threshold = classify_metric(baseline, treatment, rules[metric_id])
            row = dict(findings[metric_id], baseline_value=baseline, treatment_value=treatment, classification=classification,
                       rule_applied=applied, threshold=threshold, rule_text=rule_text(rules[metric_id], applied))
            if isinstance(row.get('rationale'), str):
                row['rationale'] = ' '.join(row['rationale'].split())
            rows.append(row); classes.append(classification); unmeasured |= applied == 'unmeasured'
        return dict(verdict, findings=rows, aggregation_rule='m1_conjunctive_v1',
                    classification=overall_classification(classes, verdict['plausibility']['status']),
                    completeness=dict(verdict['completeness'], status='incomplete' if unmeasured else 'complete'))
    except (KeyError, TypeError, ValueError, ScienceError):
        return verdict


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
    verdict = fill_recomputed(verdict, inputs['hypothesis_blueprint'], inputs['benchmark_payload'])
    return {'evaluation_verdict': produced(verdict, 'evaluation-verdict')}
