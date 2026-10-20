"""One bounded, self-reviewed Intent generation; no browsing or clarification loop."""

import json
from importlib.resources import files

from ._common import ask, produced
from ..contracts import contract_schema


async def execute(ctx,inputs):
    intake=inputs['request']
    payload={'qualified_intake':intake,'request_text':ctx.read_blob(intake['request_ref']).decode('utf-8'),
             'source_texts':[{'ref':ref,'text':ctx.read_blob(ref).decode('utf-8')} for ref in intake['source_refs']]}
    if intake.get('prior_plan_outcome_ref'):
        payload['prior_plan_outcome']=ctx.read_json(intake['prior_plan_outcome_ref'])
    prompt=files('jiuwenswarm.research_assets').joinpath('compiler','intent.txt').read_text('utf-8')
    payload['output_schema']=contract_schema('intent-ir')
    payload['common_schema']=json.loads(files('jiuwenswarm.research_contracts').joinpath('schemas','common.schema.json').read_text('utf-8'))
    value=await ask(ctx,'Intent',prompt,payload)
    return {'intent':produced(value,'intent-ir',name='intent_ir.json')}
