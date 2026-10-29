"""Controlled model/executor fixtures; these are not live scientific evidence."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsules.builder_loop import execute
from jiuwenswarm.research.checks.builder_loop import LoopBuilderChecks
from jiuwenswarm.research.checks.engine import CheckContext
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


def candidate(patch='def predict(train, test): return [train[0]["label"] for row in test]\n'):
    return {'files': {'requirements.txt': '# stdlib\n', 'poc_patch.py': patch,
        'run_benchmark.py': 'import json\npredictions=[]\nprint(json.dumps({"predictions":predictions},allow_nan=False))\n'},
        'tests': 'import unittest\nclass TestPredict(unittest.TestCase):\n def test_labels(self): self.assertTrue(True)\n'}


@pytest.fixture
def setup(tmp_path):
    store = SQLiteRunStore(tmp_path / 'store')
    lock = {'schema_version': '1.0.0', 'id': 'stdlib', 'platform': 'unit-platform',
            'requirements_ref': store.put_blob(b'# stdlib\n'), 'package_refs': [], 'approval_ref': store.put_blob(b'unit approval')}
    lock_ref = store.put_record('environment-lock', lock)
    blueprint = {'environment_ref': lock_ref, 'metrics': [{'metric_id': 'accuracy'}], 'seed': 42}
    public = {'schema': 'ai4r-classification-data:1', 'dataset_id': 'unit-public', 'feature_names': ['a','b'], 'classes': ['yes','no'],
              'train': [{'id':'train','features':[1,2],'label':'yes'}], 'test':[{'id':'test','features':[2,3]}]}
    inputs = {'lock': lock, 'blueprint': blueprint, 'baseline_resource': {'files': []},
              'validation_resource': {'files':[{'path':'data.json','artifact_ref':store.put_blob(json_bytes(public))}]}}
    refs = {key: lock_ref if key == 'lock' else store.put_blob(json_bytes(value)) for key,value in inputs.items()}
    declaration = {'identity': {'name':'research.builder','version_label':'m1-13','carrier':{'ref':'builder_loop.py'}},
                   'needs':{'model':{'tool_calling':False}}, 'budget':{'per_call':{'invocations':3,'tool_calls':0}}}
    contract = {'run_id':'run:builder','node_id':'builder','subnode_id':'builder','attempt_id':'attempt:builder',
                'inputs':[{'name':key,'artifact_refs':[ref],'contract_id':'opaque-bytes','version':'1.0.0'} for key,ref in refs.items()], 'outputs':[],
                'subnode_limits':{'time_s':10},'bindings':[{'limits':{'time_s':10},'declaration_ref':store.put_blob(json_bytes(declaration))}]}
    contract_ref = store.put_blob(json_bytes(contract))
    state = SimpleNamespace(store=store, inputs=inputs, refs=refs, contract=contract, contract_ref=contract_ref,
                            replies=[], prompts=[], test_statuses=[], reports=[], host=[], traces=[])
    async def model(prompt, system=None):
        state.prompts.append(json.loads(prompt)); number=len(state.prompts)
        reply=state.replies[min(number-1,len(state.replies)-1)]
        text=reply if isinstance(reply,str) else json.dumps(reply)
        claim=store.append_record('unit-call-claim', {'call_ordinal':number})
        call_id='call:'+str(number)
        store.append_record('model-call-start',{'run_id':contract['run_id'],'contract_ref':contract_ref,'call_id':call_id,
            'invocation_id':'inv:builder','execution_id':'exec:builder','call_claim_ref':claim})
        out=store.append_record('model-call-output',{'run_id':contract['run_id'],'call_id':call_id,'invocation_id':'inv:builder','text':text})
        ref=store.append_record('model-call',{'id':call_id,'invocation_id':'inv:builder','execution_id':'exec:builder',
            'outcome':'completed','observed_runtime':True,'evidence_refs':[out]})
        state.traces.append(ref)
        return text
    def record_host(key,ref):
        state.host.append(ref)
        store.append_record('host-record-proposal',dict(contract,key=key,ref=ref))
    async def builder_test(actual, *, manifest_ref, tests_ref, ordinal):
        assert actual == contract
        status=state.test_statuses.pop(0) if state.test_statuses else 'passed'
        manifest=store.read_record(manifest_ref)
        proof=store.put_blob(json_bytes({'ready':True,'executor_uid':10002,'executor_gid':10002}))
        stdout=store.put_blob(b'{"predictions":[{"id":"test","label":"yes"}]}')
        raw={'observed_runtime':True,'exit_code':0,'termination_reason':'completed','contract_ref':contract_ref,
             'invocation_id':'inv:builder','subject_ref':manifest['archive_ref'], 'stdout_ref':stdout,
             'observed_limits':{'network':'none','isolation_probe_ref':proof}}
        report={'schema':'ai4r-builder-test:1','run_id':contract['run_id'],'contract_ref':contract_ref,
                'invocation_id':'inv:builder','execution_id':'exec:builder','manifest_ref':manifest_ref,
                'tests_ref':tests_ref,'ordinal':ordinal,'status':status,'runs':[raw,raw],
                'diagnostics':{'detail':'unit fixture failure' if status=='failed' else 'unit fixture success'}}
        ref=store.append_record('builder_test_execution',report)
        state.reports.append(report)
        return {'report_ref':ref}
    ctx=SimpleNamespace(store=store,contract=contract,model=model,input_ref=refs.__getitem__,
                        executor=SimpleNamespace(builder_test=builder_test),record_host=record_host)
    state.ctx=ctx
    yield state
    store.close()


@pytest.mark.asyncio
async def test_failure_feedback_repairs_then_independent_checks_bind_final_bytes(setup):
    s=setup; s.replies=[candidate(),candidate('def predict(train, test): return ["no" for row in test]\n')]
    s.test_statuses=['failed','passed']
    output=await execute(s.ctx,s.inputs)
    assert len(s.prompts)==2 and s.prompts[1]['development_diagnostics']['status']=='failed'
    assert s.prompts[1]['previous_candidate']==s.replies[0]
    assert len(s.host)==1 and len(s.reports)==2
    receipt=s.store.read_record(s.host[0])
    assert receipt['trial_executed'] is True and receipt['candidate_count']==2
    refs={key:s.store.put_blob(value.data) for key,value in output.items()}
    outputs={'manifest':s.store.read_record(refs['manifest']),'bundle':s.store.read_blob(refs['bundle'])}
    check=CheckContext(s.contract,s.store,s.inputs,outputs,refs,{'contract_ref':s.contract_ref,'trace_refs':s.traces})
    checker=LoopBuilderChecks('builder')
    await checker._builder(check,s.inputs,outputs)
    # A producer test success cannot bless a later changed bundle.
    tampered=copy.deepcopy(outputs);tampered['manifest']['files'][0]['artifact_ref']=s.store.put_blob(b'changed')
    with pytest.raises(ValueError):
        await checker._builder(check,s.inputs,tampered)
    # Replacing the protected report by a self-authored success also fails.
    changed=copy.deepcopy(receipt)
    report=dict(s.reports[-1],status='passed',ordinal=3)
    changed['test_report_refs'][-1]=s.store.put_blob(json_bytes(report))
    offered=list(s.store.iter_records(kinds=('host-record-proposal',)))[0]['record']
    # Directly exercise a different scoped proposal in a fresh attempt is not needed:
    # mutate the existing referenced bytes through a controlled checker view.
    original=check.read_json
    fake=SimpleNamespace(**check.__dict__,input_ref=check.input_ref,read_blob=check.read_blob,
        read_json=lambda ref: changed if ref==s.host[0] else original(ref))
    with pytest.raises(ValueError): await checker._builder(fake,s.inputs,outputs)


@pytest.mark.asyncio
async def test_three_failed_tests_stop_without_receipt_or_outputs(setup):
    s=setup;s.replies=[candidate()];s.test_statuses=['failed']*3
    with pytest.raises(ResearchError,match='exhausted'): await execute(s.ctx,s.inputs)
    assert len(s.prompts)==len(s.reports)==3 and not s.host
    assert len(list(s.store.iter_records(kinds=('builder_attempt',))))==3


@pytest.mark.asyncio
async def test_static_failure_repairs_without_executing_invalid_code(setup):
    s=setup;s.replies=[candidate('import os\n'),candidate()]
    await execute(s.ctx,s.inputs)
    assert len(s.reports)==1 and s.reports[0]['ordinal']==2
    assert s.prompts[1]['development_diagnostics']['phase']=='static'


@pytest.mark.asyncio
async def test_unavailable_executor_and_cancellation_do_not_retry(setup):
    s=setup;s.replies=[candidate()];s.ctx.executor=None
    with pytest.raises(ResearchError,match='protected test executor'): await execute(s.ctx,s.inputs)
    assert not s.prompts
    async def cancelled(*args,**kwargs): raise asyncio.CancelledError()
    s.ctx.executor=SimpleNamespace(builder_test=cancelled)
    with pytest.raises(asyncio.CancelledError): await execute(s.ctx,s.inputs)
    assert len(s.prompts)==1 and not s.host
