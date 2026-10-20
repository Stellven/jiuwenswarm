"""Two-call Search: strategy, bounded captured retrieval, then one synthesis."""
from ..contracts import validate
from ..contracts.types import ResearchError
from ._common import ask, produced


async def execute(ctx, inputs):
    scope, brief = inputs['search_scope'], inputs['brief']
    validate('search-scope', scope)
    strategy = await ask(ctx, 'Search strategy', 'Write {"queries":[...]} from the Brief and frozen search_scope. '
                         'Use 1..max_queries unique queries, each 3..200 characters. No reformulation or recursive search.',
                         {'brief': brief, 'search_scope': scope})
    queries = strategy.get('queries')
    if not isinstance(queries, list) or not 1 <= len(queries) <= scope['max_queries'] or len(set(queries)) != len(queries) or any(not isinstance(q, str) or not 3 <= len(q) <= 200 for q in queries):
        raise ResearchError('invalid_output', 'Search strategy violates frozen query bounds')
    if ctx.connectors is None:
        raise ResearchError('unavailable', 'The approved connector operator is unavailable')
    citations, outcomes = await ctx.connectors.retrieve(scope, queries)
    if not citations:
        raise ResearchError('no_evidence', 'No captured citation is available')
    ideas = await ask(ctx, 'Search synthesis', 'Write {"ideas":[1..3 grounded ideas]}. Each idea contains idea_id, title, summary, '
                      'citation_ids, assumptions and risks. Cite only supplied captured citation IDs. State one distinct mechanism per idea.',
                      {'brief': brief, 'queries': queries,
                       'excerpts_by_query': [{'query': q, 'citations': [c for c in citations if c['query'] == q]} for q in queries]})
    result = {'schema_version': '2.0.0', 'id': 'candidate_set', 'brief_ref': ctx.input_ref('brief'),
              'scope_ref': ctx.input_ref('search_scope'), 'queries': queries,
              'connector_outcomes': outcomes, 'citations': citations, 'ideas': ideas.get('ideas')}
    return {'candidate_set': produced(result, 'candidate-set')}
