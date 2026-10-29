"""Conditional adopted advanced compiler integration, independent of the baseline."""

from __future__ import annotations

import asyncio
import inspect

from .contracts import ResearchError, validate


class AdvancedCompiler:
    def __init__(self,*,module=None,module_ref=None,adopted_bindings=None):
        self.module,self.module_ref,self.bindings=module,module_ref,adopted_bindings

    def status(self):
        available=self.module is not None and self.module_ref is not None and self.bindings is not None
        return {'implementation':'available' if available else 'PENDING_SOURCE','integration':'configured' if available else 'not_integrated',
                'verification':'NOT_RUN','module_ref':self.module_ref,'reason':None if available else 'External advanced module and adopted alternate bindings are not supplied'}

    async def compile(self,qualified_context,*,interaction_mode,timeout_s,clarify=None):
        if self.status()['implementation']!='available':raise ResearchError('advanced_source_unavailable','Advanced module/adopted bindings are pending; fixed baseline remains independently available')
        if interaction_mode not in {'interactive','headless'} or timeout_s<=0:raise ResearchError('validation','Advanced intake needs frozen mode and deadline')
        # External module has no store/path/model-provider authority. Only the
        # prequalified detached data and explicitly bounded clarification port.
        options={'interaction_mode':interaction_mode,'bindings':self.bindings,'clarify':clarify if interaction_mode=='interactive' else None}
        if not inspect.iscoroutinefunction(self.module.compile):raise ResearchError('advanced_source_unavailable','A bounded adopted async adapter is required before this external module can execute')
        result=await asyncio.wait_for(self.module.compile(qualified_context,**options),timeout_s)
        validate('research-brief',result)
        return result
