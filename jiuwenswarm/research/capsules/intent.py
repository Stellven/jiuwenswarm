"""One bounded, self-reviewed Intent generation; no browsing or clarification loop."""

from importlib.resources import files

from ._common import ask, produced


async def execute(ctx,inputs):
    intake=inputs['request']
    payload={'qualified_intake_ref':ctx.input_ref('request'),'qualified_intake':intake,
             'original_request':{'ref':intake['request_ref'],
                 'text':ctx.read_blob(intake['request_ref']).decode('utf-8')},
             'required_output_identity':{'request_ref':intake['request_ref'],
                 'allowed_context_refs':[intake['request_ref'],*intake['source_refs']]},
             'source_texts':[{'ref':ref,'text':ctx.read_blob(ref).decode('utf-8')} for ref in intake['source_refs']]}
    if intake.get('prior_plan_outcome_ref'):
        payload['prior_plan_outcome']=ctx.read_json(intake['prior_plan_outcome_ref'])
    prompt=files('jiuwenswarm.research_assets').joinpath('compiler','intent.txt').read_text('utf-8')
    value=await ask(ctx,'Intent',prompt,payload)
    return {'intent':produced(value,'intent-ir',name='intent_ir.json')}
