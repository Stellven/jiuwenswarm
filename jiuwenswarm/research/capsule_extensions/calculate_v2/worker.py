from ..calculate.worker import execute as _execute


async def execute(ctx, inputs):
    return await _execute(ctx, inputs)
