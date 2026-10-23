"""Protocol-specific independent checks, before Builder can be dispatched."""
from .stages import ResearchChecks
from ..metric_contract import validate_metric_declarations


class PredictionHypothesisChecks(ResearchChecks):
    def __init__(self, stage, *, executor=None):
        super().__init__(stage, executor=executor)
        self.check_ids.append('metric_protocol_supported')

    async def _hypothesis(self, ctx, inputs, outputs):
        validate_metric_declarations(outputs['blueprint']['metrics'])
        await super()._hypothesis(ctx, inputs, outputs)
