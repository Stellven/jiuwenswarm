"""One scoring pass; consolidation never erases an incoming audit identity."""
from ..contracts.types import ResearchError
from ._common import ask, captured, object_reply_schema, produced


class ScreeningCarrier:
    """Trusted setup binds an installed callable to its admitted immutable body."""

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
            prompt = ctx.store.read_blob(self.prompt_ref).decode('utf-8',errors='strict')
        except UnicodeError:
            raise ResearchError('prompt_pin_mismatch', 'Screening prompt is not exact UTF-8 text') from None
        if not prompt.strip():
            raise ResearchError('prompt_pin_mismatch', 'Screening prompt is empty')
        return await _execute(ctx, inputs, self.ranker, prompt)


async def _execute(ctx, inputs, ranker, pinned_prompt):
    candidates, rubric, brief = inputs['candidate_set'], inputs['screening_rubric'], inputs['brief']
    result = await ask(ctx, 'Screening', 'Return {"scores":[one IdeaScore per incoming idea_id],"opportunity_statement":"..."}. '
                       'Normalize/group near-identical proposals once for assessment, retaining every ID/citation/material variant. '
                       'Score novelty, feasibility and compute_alignment as integers1..5 under the exact rubric anchors. '
                       'Give one sentence per reason within reason_max_chars; total is sum. Include citation_ids, dependency_flags, '
                       'eligible, disposition and disposition_reason. Rank descending sum then ascending idea_id, select Top1. '
                       'No deferred disposition. The opportunity_statement names the bottleneck and mechanism. '
                       '\nPinned admitted scoring instruction:\n' + pinned_prompt,
                       {'brief': brief, 'candidate_set': candidates, 'screening_rubric': rubric},
                       reply_schema=object_reply_schema({'scores': ('screening-result', 'scores'),
                           'opportunity_statement': ('opportunity-card', 'opportunity_statement')}))
    scores = result.get('scores', [])
    selection = ranker(scores)
    ranking, selected_id = selection['ranking'], selection['selected_idea_id']
    screening = {'schema_version': '2.0.0', 'id': 'screening_result', 'candidate_ref': ctx.input_ref('candidate_set'),
                 'brief_ref': ctx.input_ref('brief'), 'rubric_ref': ctx.input_ref('screening_rubric'),
                 'scores': scores, 'ranking': ranking, 'selected_idea_id': selected_id}
    scoring_artifact = produced(screening, 'screening-result')
    screening_ref = captured(ctx, screening)
    ctx.record_host('screening_result', screening_ref)
    selected = next(i for i in candidates['ideas'] if i['idea_id'] == selected_id)
    score = next(s for s in scores if s['idea_id'] == selected_id)
    constraints = [c['text'] for c in brief['constraints']] + [r['text'] for r in brief['mandatory_requirements']]
    opportunity = {'schema_version': '2.0.0', 'id': 'opportunity_card',
                   'candidate_ref': ctx.input_ref('candidate_set'), 'screening_ref': screening_ref, 'brief_ref': ctx.input_ref('brief'),
                   'idea_id': selected_id, 'title': selected['title'], 'summary': selected['summary'],
                   'opportunity_statement': result.get('opportunity_statement'),
                   'scores': {k: score[k] for k in ['novelty', 'feasibility', 'compute_alignment', 'total']},
                   'rank': 1, 'citation_ids': selected['citation_ids'], 'constraints': constraints,
                   'assumptions': selected['assumptions'], 'risks': selected['risks'],
                   'other_dispositions': [{'idea_id': s['idea_id'], 'disposition': s['disposition'], 'reason': s['disposition_reason']}
                                          for s in scores if s['idea_id'] != selected_id]}
    return {'screening_result': scoring_artifact, 'opportunity_card': produced(opportunity, 'opportunity-card')}
