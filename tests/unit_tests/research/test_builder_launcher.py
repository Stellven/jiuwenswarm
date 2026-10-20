"""Builder transport boundaries; transcripts are local fixtures, never live qualification."""
import json
import asyncio
import copy
import hashlib
import os
import stat
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.builder_launcher import (BuilderCredentialLease, BuilderEvents,
    BuilderLauncher as ProductionBuilderLauncher, BuilderRuntime, FILES, create_builder_launcher)
from jiuwenswarm.research.executor import ExecutorBlocked, InvocationBinding


class BuilderLauncher(ProductionBuilderLauncher):
    """Transcript mechanics only; cannot qualify the production launcher.

    This explicit test adapter replaces live sandbox qualification. It never
    emits the protected producer record required by the production path.
    """
    def _qualify(self):
        if hashlib.sha256(self.runtime.codex_path.read_bytes()).hexdigest() != self.runtime.codex_sha256:
            raise ExecutorBlocked('BUILDER_PINNED_RUNTIME_CHANGED')
        BuilderCredentialLease.validate(self.runtime, self.store)
        if self.executor.prerequisites():
            raise ExecutorBlocked('UNIT_KERNEL_PREREQUISITE')


def emit(state, value):
    return state.feed(json.dumps(value).encode() + b'\n')


def tool(index, *, kind='command_execution', command='pwd', phase='item.started'):
    return {'type': phase, 'item': {'id': f'item_{index}', 'type': kind, 'command': command}}


@pytest.mark.parametrize('count,limit,expected', [(39,40,None),(40,40,'budget_exceeded'),
                                                 (41,40,'budget_exceeded'),(2,3,None),(3,3,'budget_exceeded')])
def test_exact_reported_event_boundary_and_duplicate_completion(count, limit, expected):
    state = BuilderEvents(limit)
    for index in range(count):
        emit(state, tool(index))
        emit(state, tool(index, phase='item.completed'))
    emit(state, {'type':'item.completed','item':{'id':'answer','type':'agent_message','text':'Built exact files.'}})
    emit(state, {'type':'turn.completed','usage':{'input_tokens':11,'output_tokens':7}})
    assert state.tool_count == count and state.stop_reason == expected
    assert state.usage['input_tokens'] == 11
    assert state.success is (count < limit)


@pytest.mark.parametrize('command', ['python run_benchmark.py', 'uv pip install x', 'pip install x',
                                    'curl https://example.test', 'cat x; python poc_patch.py',
                                    'sed -n "1e id" x', '$(python poc_patch.py)', 'bash -c pwd',
                                    'rg --pre=python x poc_patch.py','rg --hostname-bin=python x',
                                    'rg x *'])
def test_prohibited_or_unclassifiable_tool_effect_cannot_certify_no_trial(command):
    state = BuilderEvents(40)
    assert emit(state, tool(0, command=command)) == 'prohibited_tool'
    assert state.tool_count == 1 and not state.success
    assert state.tools[0]['allowed'] is False


def test_unknown_frames_changed_identity_and_provider_failure_are_closed():
    for event in [b'not json\n', b'{"type":"new.unqualified.event"}\n',
                  b'{"type":"item.started","item":{"id":"x","type":"new_tool"}}\n']:
        state=BuilderEvents(40)
        assert state.feed(event) == 'invalid_output'
        assert not state.success
    state=BuilderEvents(40)
    emit(state, tool(0))
    assert emit(state, tool(0,kind='web_search')) == 'invalid_output'
    state=BuilderEvents(40)
    assert emit(state, {'type':'turn.failed','error':{'message':'provider unavailable'}}) == 'provider_error'
    assert not state.success


def test_file_changes_only_exact_three_paths_and_multiple_turns_fail():
    state=BuilderEvents(40)
    assert emit(state, {'type':'item.completed','item':{'id':'edit','type':'file_change',
        'changes':[{'path':'/workspace/poc/poc_patch.py','kind':'add'}]}}) is None
    assert state.tools[0]['effect'] == 'write'
    assert emit(state, {'type':'item.completed','item':{'id':'edit2','type':'file_change',
        'changes':[{'path':'../baseline.py','kind':'update'}]}}) == 'prohibited_tool'
    state=BuilderEvents(40)
    emit(state, {'type':'turn.started'})
    assert emit(state, {'type':'turn.started'}) == 'invalid_output'


class CapturedFixtures:
    def __init__(self): self.data,self.records = {},[]
    def put_blob(self,data,**kwargs):
        digest=hashlib.sha256(data).hexdigest()
        ref={'id':'unit:'+digest,'sha256':digest};self.data[ref['id']]=bytes(data)
        return ref
    def capture(self,value): return self.put_blob(json.dumps(value,sort_keys=True).encode())
    def read_blob(self,ref): return self.data[ref['id']]
    def append_record(self,kind,record):
        self.records.append((kind,copy.deepcopy(record)));return self.capture(record)
    def iter_records(self,*,run_id,kinds):
        return [{'record':copy.deepcopy(record),'ref':self.capture(record)} for kind,record in self.records
                if kind in kinds and record.get('run_id')==run_id]


@pytest.fixture
def broker_fixture(tmp_path):
    if os.name != 'posix' or os.geteuid() != 0:
        pytest.fail('This custody fixture requires the Linux verification container with CHOWN')
    store=CapturedFixtures()
    evidence=store.put_blob(b'Synthetic unit mechanics fixture; NOT production credential or CLI qualification.')
    credential=tmp_path/'credentials';credential.mkdir(mode=0o700)
    auth=credential/'auth.json';auth.write_bytes(b'{"synthetic":"unit-only"}');auth.chmod(0o600)
    auth_sha=hashlib.sha256(auth.read_bytes()).hexdigest()
    common={'purpose':'research.builder','credential_sha256':auth_sha,'observed_runtime':True,
            'expires_at':'2099-01-01T00:00:00Z','provider_reference':'unit-only-not-operational','evidence_refs':[evidence]}
    budget=store.capture(dict(common,kind='builder-credential-budget1',budget_limit=1,budget_unit='unit-fixture'))
    revoke=store.capture(dict(common,kind='builder-credential-revocation1'))
    codex=tmp_path/'codex';codex.write_bytes(b'unit stub never executed');codex.chmod(0o555)
    digest=hashlib.sha256(codex.read_bytes()).hexdigest()
    qualified=store.capture({'kind':'builder-tool-sandbox-qualification1','build_id':'unit-only',
        'codex_sha256':digest,'observed_runtime':True,'executor_uid':10002,'executor_gid':10002,
        'sandbox':'workspace-write','approvals':'never','tool_network':'none',
        'denied_paths':{'run_state':True,'main_credential':True,'fixture':True},'evidence_refs':[evidence]})
    runtime=BuilderRuntime('unit-only',codex,digest,'0.144.4',tmp_path/'work',auth,auth_sha,budget,revoke,qualified,64,16,1024*1024)
    declaration=store.capture({'identity':{'name':'research.builder'},'budget':{'per_call':{'invocations':1,'wall_s':600,'tool_calls':40}}})
    ports=[]
    for name in ('blueprint','baseline_resource','validation_resource','lock'):
        value={'files':[{'path':'original.txt','artifact_ref':evidence}]} if name.endswith('_resource') else {'frozen':name}
        ports.append({'name':name,'artifact_refs':[store.capture(value)]})
    limits={'time_s':600,'memory_mb':128}
    authority={'write_roots':['/workspace/poc'],'network':'none','network_allowlist':[]}
    contract={'run_id':'run-unit','inputs':ports,'subnode_limits':limits,
              'bindings':[{'limits':limits,'declaration_ref':declaration,'effective_authority':authority}]}
    contract_ref=store.capture(contract)
    protected={'contract_ref':contract_ref,'invocation_id':'invocation-unit','execution_id':'execution-unit','call_id':'call-unit',
        'run_id':'run-unit','node_id':'builder','cc_name':'research.builder','limits':limits}
    protected['route_ref']=store.capture({'route_id':'route-unit','run_id':'run-unit','invocation_id':'invocation-unit'})
    protected['input_ref']=store.capture({'run_id':'run-unit','invocation_id':'invocation-unit','call_id':'call-unit','prompt':'unit prompt'})
    protected['model_call_start_ref']=store.capture({**{key:protected[key] for key in ('contract_ref','invocation_id','execution_id','call_id','route_ref','input_ref','run_id')},'route_id':'route-unit'})
    facts={**protected,'contract':contract,'execution_deadline_monotonic_s':time.monotonic()+30}
    async def authorize(request):
        assert request==protected
        return facts
    yield SimpleNamespace(store=store,runtime=runtime,protected=protected,facts=facts,authorize=authorize,root=tmp_path)
    # Restore only fixture-owned UID10002 directories for pytest cleanup.
    for path in tmp_path.rglob('*'):
        if not path.is_symlink() and path.stat().st_uid == 10002: os.chown(path,0,0)


class TranscriptKernel:
    def __init__(self,fixture,*,terminal='completed',count=1,delay=False):
        self.fixture,self.terminal,self.count,self.delay=fixture,terminal,count,delay
        self.calls=0
    def prerequisites(self): return []
    async def _run_kernel(self,job,command,*,output_parent,stdin_bytes,stdout_line_observer,stdout_line_limit):
        self.calls+=1
        assert stdin_bytes==b'unit prompt' and '--share-net' in command
        assert '--ask-for-approval' in job.argv and 'never' in job.argv and 'workspace-write' in job.argv
        home=output_parent/'codex-home'
        assert stat.S_IMODE((home/'auth.json').stat().st_mode)==0o600
        assert (home/'auth.json').stat().st_uid==10002
        assert home.stat().st_uid==10002 and stat.S_IMODE(home.stat().st_mode)==0o700
        observer=stdout_line_observer
        frames=[]
        for index in range(self.count):
            frame=json.dumps(tool(index)).encode()+b'\n';frames.append(frame);observer(frame)
        answer=json.dumps({'type':'item.completed','item':{'id':'answer','type':'agent_message','text':'unit complete'}}).encode()+b'\n'
        frames.append(answer);observer(answer)
        end=b'{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":4}}\n';frames.append(end);observer(end)
        if self.delay:
            # Model timeout/cancellation mechanics; kernel containment itself is
            # tested independently with actual cgroups in integration tests.
            await asyncio.sleep(0)
        store=self.fixture.store
        proof=store.capture({'ready':True,'profile':'builder-parent','executor_uid':10002,'executor_gid':10002})
        return {'termination_reason':self.terminal,'exit_code':0 if self.terminal=='completed' else -9,
                'identity':{'executor_uid':10002,'executor_gid':10002},'observed_runtime':True,
                'contract_ref':job.contract_ref,'invocation_id':job.invocation_id,
                'stdout_ref':store.put_blob(b''.join(frames)),'stderr_ref':store.put_blob(b'partial unit log\n'),
                'observed_limits':{'memory_max':str(job.memory_mb*1024*1024),'pids_max':str(job.pids_max),'isolation_probe_ref':proof}}


def test_synthetic_transcript_qualification_cannot_seed_production(broker_fixture):
    f = broker_fixture
    launcher = ProductionBuilderLauncher(store=f.store, executor=TranscriptKernel(f), runtime=f.runtime, authorize=f.authorize)
    with pytest.raises(ExecutorBlocked, match='PROTECTED_PROVENANCE'):
        launcher._qualify()


@pytest.mark.asyncio
@pytest.mark.parametrize('terminal,count,code',[('completed',39,None),('completed',40,'budget_exceeded'),
                                               ('completed',41,'budget_exceeded'),('timeout',1,'timeout'),
                                               ('cancelled',1,'cancelled'),('resource_limit_exceeded',1,'invalid_output')])
async def test_call_is_once_only_partial_logs_retained_and_credential_removed(broker_fixture,terminal,count,code):
    f=broker_fixture
    kernel=TranscriptKernel(f,terminal=terminal,count=count)
    launcher=BuilderLauncher(store=f.store,executor=kernel,runtime=f.runtime,authorize=f.authorize)
    result=await launcher.invoke(f.protected,'unit prompt',timeout_s=600)
    if code:
        assert result['outcome']=='failed' and result['error_code']==code and result['text'] is None
    else:
        assert result['text']=='unit complete' and result['usage']['input_tokens']==5
    assert result['evidence_refs']==[launcher.receipt_refs['invocation-unit']]
    assert json.loads(f.store.read_blob(result['evidence_refs'][0]))['call_id']=='call-unit'
    stage=launcher.stages['invocation-unit']
    assert not (stage.parent/'codex-home').exists()
    observation=launcher.observations['invocation-unit']
    assert observation['tool_count']==count and observation['credential_removed']
    assert f.store.read_blob(observation['output_refs'][1])==b'partial unit log\n'
    assert f.store.records[-1][0]=='builder_execution'
    with pytest.raises(ExecutorBlocked,match='REPLAY'):
        await launcher.invoke(f.protected,'unit prompt',timeout_s=600)
    assert kernel.calls==1


@pytest.mark.asyncio
async def test_governed_start_join_precedes_credential_access_and_process(broker_fixture):
    f=broker_fixture
    kernel=TranscriptKernel(f)
    launcher=BuilderLauncher(store=f.store,executor=kernel,runtime=f.runtime,authorize=f.authorize)
    with pytest.raises(ExecutorBlocked,match='JOIN'):
        await launcher.invoke(f.protected,'changed prompt',timeout_s=30)
    assert kernel.calls==0 and not f.runtime.workspace_root.exists()
    assert create_builder_launcher(store=f.store,executor=kernel,authorize=f.authorize,environ={},build_id='unit') is None
    launcher.runtime=replace(f.runtime,credential_source=f.root/'missing-main-auth.json')
    with pytest.raises((ExecutorBlocked,FileNotFoundError)):
        await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    assert kernel.calls==0


@pytest.mark.asyncio
async def test_exact_collection_cannot_follow_links_or_export_extras(broker_fixture):
    f=broker_fixture;kernel=TranscriptKernel(f)
    launcher=BuilderLauncher(store=f.store,executor=kernel,runtime=f.runtime,authorize=f.authorize)
    await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    stage=launcher.stages['invocation-unit'];os.chown(stage.workspace,0,0)
    binding=InvocationBinding(f.protected['contract_ref'],'invocation-unit',f.facts['contract'],'execution-unit')
    for name in FILES: (stage.workspace/name).write_bytes(b'unit source')
    assert set(await launcher.collect_builder(f.facts['contract'],binding=binding))==FILES
    (stage.workspace/'extra.txt').write_text('extra')
    with pytest.raises(ExecutorBlocked,match='THREE'): await launcher.collect_builder(f.facts['contract'],binding=binding)
    (stage.workspace/'extra.txt').unlink();(stage.workspace/'requirements.txt').unlink()
    (stage.workspace/'requirements.txt').symlink_to(f.runtime.credential_source)
    with pytest.raises(OSError): await launcher.collect_builder(f.facts['contract'],binding=binding)


@pytest.mark.asyncio
async def test_post_close_check_joins_only_unique_protected_receipt_and_start(broker_fixture):
    from jiuwenswarm.research.checks.stages import protected_builder_observation
    from jiuwenswarm.research.checks.research import CheckError
    f=broker_fixture;kernel=TranscriptKernel(f)
    launcher=BuilderLauncher(store=f.store,executor=kernel,runtime=f.runtime,authorize=f.authorize)
    await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    start=json.loads(f.store.read_blob(f.protected['model_call_start_ref']))
    f.store.append_record('model-call-start',start)
    ctx=SimpleNamespace(store=f.store,contract=f.facts['contract'],observation={'contract_ref':f.protected['contract_ref']},
                        read_json=lambda ref:json.loads(f.store.read_blob(ref)))
    assert protected_builder_observation(ctx)['call_id']=='call-unit'
    f.store.append_record('builder_execution',f.store.records[0][1])
    with pytest.raises(CheckError): protected_builder_observation(ctx)


@pytest.mark.asyncio
async def test_expired_external_budget_and_changed_runtime_are_unavailable_before_process(broker_fixture):
    f=broker_fixture;kernel=TranscriptKernel(f)
    launcher=BuilderLauncher(store=f.store,executor=kernel,runtime=f.runtime,authorize=f.authorize)
    budget=json.loads(f.store.read_blob(f.runtime.credential_budget_ref));budget['expires_at']='2000-01-01T00:00:00Z'
    launcher.runtime=replace(f.runtime,credential_budget_ref=f.store.capture(budget))
    with pytest.raises(ExecutorBlocked,match='QUALIFICATION'): await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    assert kernel.calls==0 and not f.runtime.workspace_root.exists()
    launcher.runtime=f.runtime;f.runtime.codex_path.chmod(0o755);f.runtime.codex_path.write_bytes(b'changed')
    with pytest.raises(ExecutorBlocked,match='PINNED'): await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    assert kernel.calls==0


@pytest.mark.asyncio
async def test_uncertain_kernel_cleanup_returns_durable_join_without_fabricated_logs_or_retry(broker_fixture):
    f=broker_fixture
    class UncertainKernel:
        owned_groups={}
        calls=0
        def prerequisites(self): return []
        async def _run_kernel(self,job,command,*,output_parent,**kwargs):
            self.calls+=1;self.owned_groups[job.job_id]={'invocation_id':job.invocation_id}
            capture=output_parent/(job.job_id+'.capture');capture.mkdir(mode=0o700)
            (capture/'stdout').write_bytes(b'partial bytes before containment uncertainty\n')
            raise ExecutorBlocked('EXECUTOR_PROCESS_TREE_DID_NOT_EXIT')
    kernel=UncertainKernel()
    launcher=BuilderLauncher(store=f.store,executor=kernel,runtime=f.runtime,authorize=f.authorize)
    value=await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    assert value['outcome']=='outcome_unknown' and value['error_code']=='CONTAINMENT_UNCERTAIN'
    receipt=json.loads(f.store.read_blob(value['evidence_refs'][0]))
    assert receipt['call_id']=='call-unit' and receipt['model_call_start_ref']==f.protected['model_call_start_ref']
    assert len(receipt['output_refs'])==1 and receipt['identity']=={}
    assert f.store.read_blob(receipt['output_refs'][0])==b'partial bytes before containment uncertainty\n'
    assert receipt['credential_removed'] and receipt['terminal_reason']=='containment_unknown'
    with pytest.raises(ExecutorBlocked,match='REPLAY'): await launcher.invoke(f.protected,'unit prompt',timeout_s=30)
    assert kernel.calls==1
