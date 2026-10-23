"""Native one-shot Planner over the open typed catalog."""
import json

from ...capability_planning import INSTRUCTIONS, is_capability_policy
from ...capsules.planner import _protected_host_bindings, _protected_run_inputs
from ...contracts import ResearchError, contract_schema
from ...native import NativePlanner
from ...planning import parse_planner_reply
from ...runner import ProducedArtifact


async def execute(ctx, inputs):
    if not is_capability_policy(inputs['plan_policy']):
        raise ResearchError('capability_policy', 'Capability Planner requires its exact opt-in policy')
    payload = dict(inputs, **{key + '_ref': ctx.input_ref(port) for key, port in (
        ('brief', 'brief'), ('library_snapshot', 'library_snapshot'),
        ('resource_inventory', 'resource_inventory'), ('policy', 'plan_policy'))},
        protected_host_bindings=_protected_host_bindings(),
        protected_run_input_bindings=_protected_run_inputs(inputs['resource_inventory']))
    instructions = ('Return exactly one planned plan_proposal 3.0.0 using the supplied refs, '
        'exact typed catalog ports and Brief obligation IDs. Source inputs have accepted_ref null. '
        'Coverage exactly inverts requirement/deliverable tags; evidence obligations name real nodes. '
        'Objectives are plain outcome sentences, never executable code or authority grants. '
        'No literal artifact refs, renamed ports or unchecked schema conversion. '
        'If impossible return one line INFEASIBLE: reason (at most 300 characters).\n' + INSTRUCTIONS
        + '\nOutput schema:\n' + json.dumps(contract_schema('plan-proposal')))
    raw = await NativePlanner().propose(payload, invoke=ctx.model, instructions=instructions)
    try:
        kind, _ = parse_planner_reply(raw)
    except ResearchError:
        kind = 'proposal'  # retain malformed original bytes for ordinary checks
    if kind == 'infeasible':
        ref = ctx.store.put_blob(raw.encode(), media_type='text/plain')
        ctx.record_host('planner_infeasible', ref)
        raise ResearchError('planner_reported_infeasible', 'Frozen catalog cannot cover the task')
    return {'plan_proposal': ProducedArtifact(raw, 'plan-proposal', 'application/json', 'plan_proposal.json')}
