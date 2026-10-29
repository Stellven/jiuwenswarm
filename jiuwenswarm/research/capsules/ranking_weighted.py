"""Pure admitted weighted-screening helper: exact rational arithmetic, no effects.

Totals are exact sums of weight times the supplied assessment, so equal totals
are real ties. Hard constraints exclude an idea; ties order by idea_id as plain
code-point strings. The result is recomputable from the inputs alone.
"""
from fractions import Fraction

VIOLATION_CODES = ('requires_gpu', 'license_not_allowed', 'runtime_exceeds_budget', 'forbidden_dependency')


def exact(text):
    if not isinstance(text, str):
        raise ValueError('Rational values must be strings')
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise ValueError('Not an exact rational: ' + repr(text)) from None


def violations(facts, constraints):
    found = []
    if constraints['cpu_only'] and facts['requires_gpu']:
        found.append({'code': 'requires_gpu', 'detail': 'requires a GPU but only CPUs are allowed'})
    licenses = constraints['allowed_licenses']
    if licenses is not None and facts['license'] not in licenses:
        found.append({'code': 'license_not_allowed', 'detail': 'license ' + facts['license'] + ' is not allowed'})
    limit = constraints['max_runtime_minutes']
    if limit is not None and exact(facts['runtime_minutes']) > exact(limit):
        found.append({'code': 'runtime_exceeds_budget',
                      'detail': 'runtime ' + facts['runtime_minutes'] + ' minutes exceeds the ' + limit + ' minute budget'})
    for dependency in facts['dependencies']:
        if dependency in constraints['forbidden_dependencies']:
            found.append({'code': 'forbidden_dependency', 'detail': 'uses forbidden dependency ' + dependency})
    return found


def rank_weighted(candidates, rubric):
    """Return per-idea rows (input order), the eligible ranking and the Top-1."""
    weights = {name: exact(value) for name, value in rubric['weights'].items()}
    seen, rows = set(), []
    for idea in candidates['ideas']:
        idea_id = idea['idea_id']
        if not isinstance(idea_id, str) or not idea_id or idea_id in seen:
            raise ValueError('Each incoming idea must have one unique identity')
        seen.add(idea_id)
        missing = sorted(set(weights) - set(idea['assessments']))
        if missing:
            raise ValueError('Idea ' + idea_id + ' lacks weighted assessments: ' + ', '.join(missing))
        values = {name: idea['assessments'][name] for name in weights}
        total = sum((weights[name] * exact(values[name]) for name in weights), Fraction(0))
        found = violations(idea['facts'], rubric['constraints'])
        rows.append({'idea_id': idea_id, 'values': values, 'weighted_total': str(total), 'violations': found,
                     'eligible': not found, 'citation_ids': list(idea['citation_ids'])})
    eligible = sorted((row for row in rows if row['eligible']),
                      key=lambda row: (-Fraction(row['weighted_total']), row['idea_id']))
    if not eligible:
        raise ValueError('No eligible opportunity')
    ranking = [{'rank': index + 1, 'idea_id': row['idea_id'], 'weighted_total': row['weighted_total']}
               for index, row in enumerate(eligible)]
    return {'rows': rows, 'ranking': ranking, 'selected_idea_id': ranking[0]['idea_id']}
