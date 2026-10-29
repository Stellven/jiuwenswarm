"""Narrow adapters for the exact pinned OpenJiuwen runtime and native Leader."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import tempfile
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

from .contracts import ResearchError


OPENJIUWEN_COMMIT='9e3390195a9ea15235b2b5f7412cb2aa440622cc'
_planner_call=ContextVar('research_planner_call',default=None)
_client_class=None


def verify_native_pin():
    try:
        distribution=importlib.metadata.distribution('openjiuwen')
        direct=json.loads(distribution.read_text('direct_url.json') or '{}')
        if direct.get('vcs_info',{}).get('commit_id')!=OPENJIUWEN_COMMIT:
            raise ResearchError('native_pin_mismatch','Installed native runtime does not identify the reviewed commit')
    except importlib.metadata.PackageNotFoundError as exc:
        raise ResearchError('native_unavailable','Pinned OpenJiuwen runtime is not installed') from exc


_WORKFLOW='''from swarmflow import agent
META = {"name": "protected_research", "description": "Frozen serial research nodes"}
async def run(args):
    results = []
    for node_id in args["order"]:
        results.append(await agent(node_id, label=node_id))
    return results
'''


async def run_native_workflow(order,dispatch,*,run_id,progress_sink=None):
    verify_native_pin()
    from openjiuwen.agent_teams.workflow.engine import AgentBackend,AgentResult,run_workflow
    from openjiuwen.agent_teams.workflow.engine.primitives import _rt
    class ResearchAdmission:
        def __init__(self):self.lock=asyncio.Lock()
        @asynccontextmanager
        async def acquire(self):
            async with self.lock:
                runtime=_rt.get()
                if runtime is None or not hasattr(runtime,'retries'):raise ResearchError('native_compatibility','Reviewed per-run retry accessor is unavailable')
                runtime.retries=0
                if runtime.retries!=0:raise ResearchError('native_compatibility','Native retries could not be disabled')
                yield
    class ResearchBackend(AgentBackend):
        def __init__(self):super().__init__();self.seen=set();self.fatal=None
        async def run(self,prompt,opts,schema_json,*,call_key=None):
            if self.fatal is not None:return AgentResult(text=json.dumps({'protected_stop':True}))
            if prompt not in order or prompt in self.seen:
                self.fatal=ResearchError('native_dispatch_identity','Native dispatch differs from frozen order')
                return AgentResult(text=json.dumps({'protected_stop':True}))
            self.seen.add(prompt)
            try:
                value=await dispatch(prompt)
                return AgentResult(text=json.dumps(value,allow_nan=False))
            except BaseException as exc:
                self.fatal=exc
                raise
    backend=ResearchBackend()
    with tempfile.TemporaryDirectory(prefix='ai4r-native-') as directory:
        path=Path(directory)/'workflow.py';path.write_text(_WORKFLOW,encoding='utf-8',newline='\n')
        result=await run_workflow(str(path),args={'order':list(order)},backend=backend,cap=1,
            agent_gate=ResearchAdmission(),resume=None,journal_path=None,wal_path=None,
            run_id=run_id,progress_sink=progress_sink)
    if backend.fatal is not None:raise backend.fatal
    if backend.seen!=set(order):raise ResearchError('native_dispatch_incomplete','Native runtime did not visit each frozen node exactly once')
    return result


def _audited_client_class():
    global _client_class
    if _client_class is not None:return _client_class
    from openjiuwen.core.foundation.llm.model_clients.base_model_client import BaseModelClient
    from openjiuwen.core.foundation.llm.schema.message import AssistantMessage
    from openjiuwen.core.foundation.llm.schema.message_chunk import AssistantMessageChunk
    class AuditedBridgeModelClient(BaseModelClient):
        __client_name__='research_governed_bridge'
        def _validate_config(self):
            if self.model_client_config.max_retries!=0:raise ResearchError('native_retry_configuration','Native SDK retries must be zero')
        async def invoke(self,messages,*,tools=None,**kwargs):
            call=_planner_call.get()
            if call is None or call['calls']!=0:raise ResearchError('budget_exhausted','Native Planner may make one model call only')
            call['calls']+=1
            serialized=[]
            if isinstance(messages,str):serialized=[{'role':'user','content':messages}]
            else:
                for message in messages:
                    value=message if isinstance(message,dict) else message.model_dump(exclude_none=True)
                    if value.get('role') not in {'system','user','assistant'} or not isinstance(value.get('content'),str) or value.get('tool_calls'):
                        raise ResearchError('native_modality','Planner accepts text messages only')
                    serialized.append({'role':value['role'],'content':value['content']})
            # Native team tools are deliberately not exposed to the model. This
            # adapter has no tool dispatch and returns text-only AssistantMessage.
            text=await call['invoke'](json.dumps(serialized,ensure_ascii=False),system=call['instructions'])
            call['text']=text
            return AssistantMessage(content=text,tool_calls=None)
        async def stream(self,messages,**kwargs):
            response=await self.invoke(messages,**kwargs)
            yield AssistantMessageChunk(content=response.content)
        async def generate_image(self,*args,**kwargs):raise ResearchError('native_modality','Images are disabled')
        async def generate_speech(self,*args,**kwargs):raise ResearchError('native_modality','Speech is disabled')
        async def generate_video(self,*args,**kwargs):raise ResearchError('native_modality','Video is disabled')
    _client_class=AuditedBridgeModelClient
    return _client_class


class NativePlanner:
    async def propose(self,payload: dict,*,invoke,instructions: str)->str:
        verify_native_pin();_audited_client_class()
        from openjiuwen.agent_teams.schema.blueprint import TeamAgentSpec
        from openjiuwen.agent_teams.paths import set_task_openjiuwen_home,reset_task_openjiuwen_home
        from openjiuwen.agent_teams.schema.deep_agent_spec import DeepAgentSpec,TeamModelConfig
        from openjiuwen.core.foundation.llm.schema.config import ModelClientConfig,ModelRequestConfig
        client=ModelClientConfig(client_provider='research_governed_bridge',api_key='',api_base='protected-local-bridge',max_retries=0,timeout=120)
        deep=DeepAgentSpec(model=TeamModelConfig(model_client_config=client,model_request_config=ModelRequestConfig(model='codex-cli-default')),
            system_prompt=instructions,tools=[],mcps=[],subagents=[],rails=[],skills=[],enable_task_loop=False,enable_task_planning=False,
            enable_sys_operation=False,enable_tool_resilience_rail=False,enable_async_subagent=False,enable_subagent_runtime=False,
            enable_skill_discovery=False,enable_read_image_multimodal=False,add_general_purpose_agent=False,max_iterations=1,
            auto_create_workspace=False,completion_timeout=120)
        spec=TeamAgentSpec(agents={'leader':deep},team_name='research_planner',evolution_enabled=False,
            enable_team_plan=False,enable_task_verification=False,enable_group_chat=False,enable_hitt=False,
            enable_bridge=False,enable_fork=False,enable_swarmflow=False,predefined_members=[],external_cli_agents=[],model_pool=[])
        call={'calls':0,'invoke':invoke,'instructions':instructions,'text':None};token=_planner_call.set(call);agent=None
        temporary=tempfile.TemporaryDirectory(prefix='ai4r-planner-');home_token=set_task_openjiuwen_home(temporary.name)
        try:
            agent=spec.build()
            if agent.harness is None:raise ResearchError('native_unavailable','Native Leader harness did not build')
            await asyncio.wait_for(agent.harness.run_once(json.dumps(payload,ensure_ascii=False,allow_nan=False)),120)
            if call['calls']!=1 or call['text'] is None:raise ResearchError('native_dispatch_incomplete','Native Leader did not complete one governed call')
            return call['text']
        finally:
            try:
                if agent is not None and agent.harness is not None:await agent.harness.dispose()
            finally:
                reset_task_openjiuwen_home(home_token);temporary.cleanup();_planner_call.reset(token)
