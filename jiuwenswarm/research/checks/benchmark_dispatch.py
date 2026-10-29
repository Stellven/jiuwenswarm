"""Independent protocol-specific validation under the admitted check bundle."""
import copy
from .blind_benchmark import BlindBenchmarkChecks
from .pi_benchmark import PiBenchmarkChecks
from ..capsules.benchmark_dispatch import is_pi


class BenchmarkDispatchChecks(BlindBenchmarkChecks):
    def __init__(self, stage='benchmark', **kwargs):
        super().__init__(stage,**kwargs)

    async def __call__(self,ctx,inputs,outputs):
        if not is_pi(inputs,ctx.read_blob):return await super().__call__(ctx,inputs,outputs)
        checker=PiBenchmarkChecks(executor=self.executor)
        checker.metadata=copy.deepcopy(checker.metadata)
        checker.check_ids=self.check_ids
        for port in checker.metadata['declaration']['ports']['outputs']:
            if port['name']=='benchmark_payload':port['schema_ref']='urn:ai4r:pi-benchmark-payload:1.0.0'
        return await checker(ctx,inputs,outputs)

    async def _benchmark(self, ctx, inputs, outputs):
        checker = PiBenchmarkChecks(executor=self.executor) if is_pi(inputs,ctx.read_blob) else self
        if checker is self:
            return await super()._benchmark(ctx,inputs,outputs)
        return await checker._benchmark(ctx,inputs,outputs)
