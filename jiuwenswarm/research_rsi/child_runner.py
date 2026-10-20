"""Adapter to an isolated core runner, never the live scheduler or library."""
import asyncio


class ChildRunner:
    def __init__(self,runner,*,register_child,run_mandatory,configuration_ref,isolated_store_root,live_store_root,qualification=None,session_ref=None):
        from pathlib import Path
        a,b=Path(isolated_store_root).resolve(),Path(live_store_root).resolve()
        if a==b or a in b.parents or b in a.parents:raise ValueError('workbench store must be separate from live state')
        self.runner,self.register_child,self.run_mandatory=runner,register_child,run_mandatory
        self.configuration_ref=configuration_ref
        self.qualification,self.session_ref=qualification,session_ref
    async def execute(self,child,*,contract_ref,check_plan_ref,bundle_id,configuration_ref,verifier_contract_refs=None):
        if configuration_ref!=self.configuration_ref:raise ValueError('parent/child configuration mismatch')
        from .qualification import require_qualification
        require_qualification(self.qualification,'trial',session_ref=self.session_ref,candidate_ref=child)
        mandatory=await self.run_mandatory(child)
        if not mandatory.get('passed') or not mandatory.get('evidence_refs'):return {'passed':False,'mandatory':mandatory,'run':None}
        await self.register_child(child)
        result=await self.runner.run(contract_ref,check_plan_ref,bundle_id=bundle_id,verifier_contract_refs=verifier_contract_refs or {})
        return {'passed':True,'mandatory':mandatory,'run':result}
    @staticmethod
    def wiring(parent_ports,child_ports):
        if parent_ports!=child_ports:raise ValueError('port mismatch; wiring dry-run cannot execute')
        return {'compatible':True,'executed':False}
