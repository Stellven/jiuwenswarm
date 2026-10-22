"""One genuine native Planner call for the protected PDF summary workflow."""
import json

from ..contracts import ResearchError, contract_schema
from ..native import NativePlanner
from ..planning import parse_planner_reply
from ..summary_planning import document_summary_planner_instructions, is_document_summary_policy


async def execute(ctx, inputs):
    if not is_document_summary_policy(inputs['plan_policy']):
        raise ResearchError('paper_summary_policy', 'Paper Planner requires the exact explicitly selected protected policy')
    payload = dict(inputs, brief_ref=ctx.input_ref('brief'),
                   library_snapshot_ref=ctx.input_ref('library_snapshot'),
                   resource_inventory_ref=ctx.input_ref('resource_inventory'),
                   policy_ref=ctx.input_ref('plan_policy'))
    instructions = document_summary_planner_instructions()
    instructions += '\nPinned output schema:\n' + json.dumps(contract_schema('plan-proposal'), ensure_ascii=False)
    raw = await NativePlanner().propose(payload, invoke=ctx.model, instructions=instructions)
    try:
        kind, _ = parse_planner_reply(raw)
    except ResearchError as error:
        if not isinstance(raw, str) or error.code not in {'planner_output_invalid', 'contract_invalid', 'invalid_json'}:
            raise
        kind = 'proposal'
    if kind == 'infeasible':
        ref = ctx.store.put_blob(raw.encode('utf-8'), media_type='text/plain')
        ctx.record_host('planner_infeasible', ref)
        raise ResearchError('planner_reported_infeasible', 'The frozen paper capability set cannot cover this request', {'reason_ref': ref})
    from ..runner import ProducedArtifact
    return {'plan_proposal': ProducedArtifact(raw.encode('utf-8'), 'plan-proposal', name='plan_proposal.json')}
