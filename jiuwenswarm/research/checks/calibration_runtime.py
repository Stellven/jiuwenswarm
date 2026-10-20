"""Verify-only installed check preparation; it grants no capsule eligibility."""
from __future__ import annotations
from ..compiler import prepare_compiler_assets
from ..capsules.assets import build_research_assets
from ..planning import planner_checks
from .compiler import compiler_checks
from .stages import ResearchChecks
from .verifier import verifier_checks
from ..contracts import ResearchError
import hashlib
import time


async def prepare_calibration_checks(store,registry,*,executor=None):
    prepared=await prepare_compiler_assets(store)
    handlers={'intent':compiler_checks,'requirements':compiler_checks,'planner':planner_checks,'verifier':verifier_checks}
    for stage,asset in prepared.items():
        bundle=asset['bundle']
        registry.register_bundle(bundle['bundle_id'],[row['check_id'] for row in bundle['checks']],handlers[stage],
            implementation_ref=asset['runner_ref'],profile_ref=asset['profile_ref'])
    scientific=build_research_assets(store)
    for stage,asset in scientific.items():
        bundle=store.read_record(asset['bundle_ref'],contract_id='check-bundle')
        registry.register_bundle(bundle['bundle_id'],[row['check_id'] for row in bundle['checks']],ResearchChecks(stage,executor=executor),
            implementation_ref=asset['runner_ref'],profile_ref=asset['profile_ref'])
    return {**prepared,**scientific}


class CalibrationModelPort:
    """Only fixed composition creates this port; the caller chooses no authority."""
    def __init__(self,authority,request_ref,case_id):
        self.authority,self.request_ref,self.case_id=authority,request_ref,case_id

    async def invoke(self,prompt,*,system):
        grant_ref=self.authority.prepare_calibration_case({'request_ref':self.request_ref,'case_id':self.case_id})['grant_ref']
        grant=self.authority.store.read_record(grant_ref)
        text=system+'\n\n<subject_payload>\n'+prompt+'\n</subject_payload>'
        if hashlib.sha256(text.encode()).hexdigest()!=grant['expected_prompt_sha256']:
            raise ResearchError('calibration_payload','Actual model payload differs from preregistered subject/instructions')
        if self.authority.model is None:raise ResearchError('calibration_model_unavailable','Managed native model port is unavailable')
        result=None
        try:
            result=await self.authority.model.call({'execution_id':grant['execution_id'],'call_ordinal':1},text)
            return result
        finally:
            returned=time.time()
            if result is not None:
                call=self.authority.store.read_record(result['call_ref'],contract_id='model-call')
                receipt=self.authority.store.append_record('calibration-call-return',{'id':grant['execution_id']+':return',
                    'request_ref':self.request_ref,'grant_ref':grant_ref,'execution_id':grant['execution_id'],'invocation_id':grant['invocation_id'],
                    'call_id':call['id'],'call_ref':result['call_ref'],'returned_epoch':returned})
                self.authority.mark([receipt])
            self.authority.capture_produced(self.request_ref)

    async def contain(self):return await self.authority.cancel_calibration({'request_ref':self.request_ref})
