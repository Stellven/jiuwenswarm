from ..calculate.checks import check as legacy
from ..typed_values import checked


def check(ctx, inputs, outputs):
    return checked(legacy, ctx, inputs, outputs, 'calculate')

