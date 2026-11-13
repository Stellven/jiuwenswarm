"""ILLUSTRATION ONLY: a minimal power-aware decision rule, to show the evaluator produces different
ACTIONS (not just different explanations). It is not the RSI result. The RSI task is to design,
justify and validate the rule, then write it into factory.methodology_ab (AB.md + version bump)."""


def decide(c):
    if c['verdict'] == 'improved':
        return 'keep'
    if c['verdict'] == 'regressed':
        return 'reject'
    if c['power_at'](c['rounds']) >= 0.8:      # a well-powered null is evidence of no useful effect
        return 'reject'
    for k in (1, 2, 3):                         # cheapest design that would be decisive, within budget
        if 4 * k * c['minutes_per_run'] <= c['budget_min'] and c['power_at'](k) >= 0.8:
            return f'replicate:{k}'
    return 'inconclusive'                       # underpowered and nothing affordable helps: no negative claim
