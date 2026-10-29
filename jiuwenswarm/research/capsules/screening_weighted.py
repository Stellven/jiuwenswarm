"""Weighted screening: the host computes exclusions, exact totals and ranking; the model only narrates."""
from ..contracts.types import ResearchError
from ._common import ask, captured, produced

RESULT_SCHEMA = 'urn:ai4r:screening-weighted-result:1.0.0'


class WeightedScreeningCarrier:
    """Trusted setup binds an installed pure callable to its admitted immutable body."""

    def __init__(self, ranker, helper_ref, prompt_ref):
        if not callable(ranker):
            raise ValueError('An installed pure ranking callable is required')
        self.ranker, self.helper_ref, self.prompt_ref = ranker, dict(helper_ref), dict(prompt_ref)

    async def execute(self, ctx, inputs):
        binding = ctx.contract['bindings'][0]
        if self.helper_ref not in [*binding['implementation_refs'], *binding['dependency_refs']]:
            raise ResearchError('helper_pin_mismatch', 'Screening helper is outside the admitted closure')
        ctx.store.read_blob(self.helper_ref)
        if self.prompt_ref not in binding['implementation_refs']:
            raise ResearchError('prompt_pin_mismatch', 'Screening prompt is outside the admitted body')
        try:
            prompt = ctx.store.read_blob(self.prompt_ref).decode('utf-8', errors='strict')
        except UnicodeError:
            raise ResearchError('prompt_pin_mismatch', 'Screening prompt is not exact UTF-8 text') from None
        if not prompt.strip():
            raise ResearchError('prompt_pin_mismatch', 'Screening prompt is empty')
        return await _execute(ctx, inputs, self.ranker, prompt)


def _reason(row, rank):
    if not row['eligible']:
        return 'Excluded by hard constraint: ' + '; '.join(v['detail'] for v in row['violations']) + '.'
    if rank == 1:
        return 'Selected: rank 1 with exact weighted total ' + row['weighted_total'] + '.'
    return 'Ranked ' + str(rank) + ' with exact weighted total ' + row['weighted_total'] + '.'


async def _execute(ctx, inputs, ranker, pinned_prompt):
    candidates, rubric = inputs['candidate_set'], inputs['screening_rubric']
    try:
        computed = ranker(candidates, rubric)
    except ValueError as exc:
        raise ResearchError('no_eligible_idea' if 'No eligible' in str(exc) else 'ranking_failed', str(exc)) from None
    rows = {row['idea_id']: row for row in computed['rows']}
    ranks = {row['idea_id']: row['rank'] for row in computed['ranking']}
    limit = rubric['reason_max_chars']
    known = {idea['idea_id']: idea for idea in candidates['ideas']}
    payload = {'ideas': [{'idea_id': i, 'title': known[i]['title'], 'summary': known[i]['summary'],
                          'weighted_total': rows[i]['weighted_total'], 'violations': rows[i]['violations'],
                          'rank': ranks.get(i)} for i in known],
               'selected_idea_id': computed['selected_idea_id'], 'assessment_max_chars': limit}
    reply = await ask(ctx, 'Screening',
        'The host has already computed every exclusion, exact weighted total, rank and the Top-1 shown in host_computation. '
        'Return {"assessments":[exactly one {"idea_id","assessment"} per incoming idea_id],"opportunity_statement":"..."}. '
        'Each assessment is one plain-language paragraph of at most assessment_max_chars that explains the idea and states, '
        'without changing them, its host-computed exclusion reasons or its rank and total. Never alter, recompute or contradict '
        'a host-computed value, and cite no number that is not in the payload. '
        '\nPinned admitted scoring instruction:\n' + pinned_prompt,
        {'host_computation': payload},
        reply_schema={'type': 'object', 'additionalProperties': False, 'required': ['assessments', 'opportunity_statement'],
                      'properties': {'assessments': {'type': 'array', 'minItems': 1, 'maxItems': 32,
                          'items': {'type': 'object', 'additionalProperties': False, 'required': ['idea_id', 'assessment'],
                                    'properties': {'idea_id': {'type': 'string'},
                                                   'assessment': {'type': 'string', 'minLength': 1, 'maxLength': limit}}}},
                          'opportunity_statement': {'type': 'string', 'minLength': 1, 'maxLength': 1200}}})
    texts = {}
    for item in reply.get('assessments', []):
        if (not isinstance(item, dict) or set(item) != {'idea_id', 'assessment'} or item['idea_id'] in texts
                or type(item['assessment']) is not str or not item['assessment'].strip() or len(item['assessment']) > limit):
            raise ResearchError('invalid_output', 'Assessments must be one bounded paragraph per idea')
        texts[item['idea_id']] = item['assessment']
    statement = reply.get('opportunity_statement')
    if set(texts) != set(known) or type(statement) is not str or not statement.strip():
        raise ResearchError('invalid_output', 'Assessments must cover every incoming idea exactly once')
    scores = []
    for idea in candidates['ideas']:
        row, rank = rows[idea['idea_id']], ranks.get(idea['idea_id'])
        scores.append({'idea_id': row['idea_id'], 'values': row['values'], 'weighted_total': row['weighted_total'],
                       'violations': row['violations'], 'eligible': row['eligible'],
                       'disposition': 'rejected' if not row['eligible'] else 'selected' if rank == 1 else 'eligible',
                       'disposition_reason': _reason(row, rank), 'assessment': texts[idea['idea_id']],
                       'citation_ids': row['citation_ids']})
    result = {'schema_version': '1.0.0', 'id': 'screening_result', 'candidate_ref': ctx.input_ref('candidate_set'),
              'rubric_ref': ctx.input_ref('screening_rubric'), 'scores': scores, 'ranking': computed['ranking'],
              'selected_idea_id': computed['selected_idea_id'], 'opportunity_statement': statement}
    artifact = produced(result, RESULT_SCHEMA)
    ctx.record_host('screening_result', captured(ctx, result))
    return {'screening_result': artifact}
