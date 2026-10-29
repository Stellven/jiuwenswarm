"""Pure admitted Screening helper; no effects or acceptance authority."""


def rank_opportunities(scores):
    """Compute sum-three, deterministic eligible ranking and Top-1 without mutation."""
    seen, eligible = set(), []
    for score in scores:
        idea_id = score['idea_id']
        if not isinstance(idea_id, str) or not idea_id or idea_id in seen:
            raise ValueError('Each incoming idea must have one unique identity')
        seen.add(idea_id)
        if type(score.get('eligible')) is not bool:
            raise ValueError('Eligibility must be a boolean')
        dimensions = [score[name] for name in ('novelty', 'feasibility', 'compute_alignment')]
        if any(type(value) is not int or not 1 <= value <= 5 for value in dimensions):
            raise ValueError('The three fixed dimensions must be integers in 1..5')
        if score['eligible']:
            eligible.append({'idea_id': idea_id, 'total': sum(dimensions)})
    eligible.sort(key=lambda row: (-row['total'], row['idea_id']))
    if not eligible:
        raise ValueError('No eligible opportunity')
    return {'ranking': [dict(row, rank=index + 1) for index, row in enumerate(eligible)],
            'selected_idea_id': eligible[0]['idea_id']}
