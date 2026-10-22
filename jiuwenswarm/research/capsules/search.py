"""Two-call Search: strategy, bounded captured retrieval, then one synthesis."""
from ..contracts import validate
from ..contracts.types import ResearchError
from ._common import ask, object_reply_schema, produced


async def execute(ctx, inputs):
    scope, brief = inputs['search_scope'], inputs['brief']
    validate('search-scope', scope)
    strategy = await ask(ctx, 'Search strategy', 'Write {"queries":[...]} from the Brief and frozen search_scope. '
                         'For local_documents, matching is literal: every word token in a query must occur as a '
                         'case-insensitive substring in the same captured document. It does not interpret Boolean '
                         'operators, field syntax, stemming or semantic similarity. Use short distinctive literal '
                         'core terms supported by the Brief, not long natural-language clauses, filler, guessed '
                         'document wording or a conjunction of every requested output detail. Different bounded '
                         'queries may explore different core terms. Evidence is not guaranteed; never invent a hit. '
                         'Use 1..max_queries unique queries, each 3..200 characters. No reformulation or recursive search.',
                         {'brief': brief, 'search_scope': scope}, reply_schema={
                             'type': 'object', 'properties': {'queries': {'type': 'array',
                                 'minItems': 1, 'maxItems': scope['max_queries'], 'uniqueItems': True,
                                 'items': {'type': 'string', 'minLength': 3, 'maxLength': 200}}},
                             'required': ['queries'], 'additionalProperties': False})
    queries = strategy.get('queries')
    if not isinstance(queries, list) or not 1 <= len(queries) <= scope['max_queries'] or len(set(queries)) != len(queries) or any(not isinstance(q, str) or not 3 <= len(q) <= 200 for q in queries):
        raise ResearchError('invalid_output', 'Search strategy violates frozen query bounds')
    if ctx.connectors is None:
        raise ResearchError('unavailable', 'The approved connector operator is unavailable')
    citations, outcomes = await ctx.connectors.retrieve(scope, queries)
    if not citations:
        raise ResearchError('no_evidence', 'No captured citation is available')
    ideas = await ask(ctx, 'Search synthesis', 'Write {"ideas":[1..3 grounded ideas]}. Each idea contains idea_id, title, summary, '
                      'citation_ids, assumptions and risks. Follow every field type, length and required-field constraint in the '
                      'public reply schema; idea IDs are unique and every idea has at least one supplied captured citation ID. '
                      'Each summary, within600 characters, must itself state both a concrete proposed change and a conditional '
                      'causal reason that change may help. Naming a technique or evaluation procedure is not the reason; '
                      'do not leave the only explanatory mechanism in assumptions or risks. Proposals and causal explanations '
                      'must fit the supplied excerpts and Brief; cite only the captured IDs supplied in this call, never invent '
                      'a source, result or citation. Different ideas must differ in mechanism, not restate the same idea. '
                      'Give at least one specific unproved premise in assumptions and one specific failure mode in risks for '
                      'each idea; separate those premises from facts actually present in the captured excerpts. State no '
                      'observed improvement, measurement, executed experiment or verified evidence beyond the supplied content. '
                      'Keep the title, summary, citations, assumptions and risks internally consistent, including all stated '
                      'uncertainties and limitations; do not assert a premise as proved elsewhere in the same idea. '
                      'Before returning, self-review public output conformance, internal consistency, limitation consistency, '
                      'a concrete change plus conditional reason in every summary, distinct mechanisms and idea-specific '
                      'assumptions/failure modes. Do not execute, fetch another source or revise the frozen queries.',
                      {'brief': brief, 'queries': queries,
                       'excerpts_by_query': [{'query': q, 'citations': [c for c in citations if c['query'] == q]} for q in queries]},
                      reply_schema=object_reply_schema({'ideas': ('candidate-set', 'ideas')}))
    result = {'schema_version': '2.0.0', 'id': 'candidate_set', 'brief_ref': ctx.input_ref('brief'),
              'scope_ref': ctx.input_ref('search_scope'), 'queries': queries,
              'connector_outcomes': outcomes, 'citations': citations, 'ideas': ideas.get('ideas')}
    return {'candidate_set': produced(result, 'candidate-set')}
