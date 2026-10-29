"""Choose a registered protocol; protected job issuance separately binds its host profile."""
import json
from . import benchmark, pi_benchmark


def is_pi(inputs, read_blob):
    rows = inputs['validation_resource']['files']
    return len(rows)==1 and rows[0]['path']=='data.json' and json.loads(read_blob(rows[0]['artifact_ref'])).get('schema')=='ai4r-pi-cases:1'


async def execute(ctx, inputs):
    return await (pi_benchmark.execute if is_pi(inputs,ctx.store.read_blob) else benchmark.execute)(ctx,inputs)
