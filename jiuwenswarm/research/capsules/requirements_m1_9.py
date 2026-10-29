"""Requirements generation receives only actually accepted Intent plus qualified inputs."""

from importlib.resources import files

from ._common import ask, produced


async def execute(ctx,inputs):
    intake=inputs['intake']
    payload=dict(inputs,intent_ref=ctx.input_ref('intent'),intake_ref=ctx.input_ref('intake'),default_policy_ref=ctx.input_ref('defaults'),
                 qualified_output_ref_allowlist=[ctx.input_ref('intent'),ctx.input_ref('intake'),ctx.input_ref('defaults'),
                     intake['request_ref'],*intake['source_refs'],*intake['resource_refs']],
                 request_text=ctx.read_blob(intake['request_ref']).decode('utf-8'),
                 source_texts=[{'ref':ref,'text':ctx.read_blob(ref).decode('utf-8')} for ref in intake['source_refs']])
    if intake.get('prior_plan_outcome_ref'):
        outcome=ctx.read_json(intake['prior_plan_outcome_ref'])
        payload['prior_plan_diagnostic']={'outcome':outcome['outcome'],'next_stage':outcome['next_stage'],
                                        'reasons':outcome['reasons']}
    prompt=files('jiuwenswarm.research_assets').joinpath('compiler','requirements_m1_9.txt').read_text('utf-8')
    value=await ask(ctx,'Requirements',prompt,payload)
    return {'brief':produced(value,'research-brief',name='research_brief.json')}
