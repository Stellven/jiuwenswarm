"""Qualification must prove owned GPU activity and clean, repeatable completion."""
import copy
import json
from pathlib import Path
import sys
import pytest
from jiuwenswarm.factory.runtime_job import gpu_activity,assess


def record(output='42 [end of text]\n'):
    return dict(output=output,collector=dict(reason='completed',container_exit_code=0,quiescent=True),
                container_removed=True,gpu_activity_confirmed=True,cuda_backend_reported=True)


def test_gpu_process_must_belong_to_container():
    raw='123, /app/llama-completion, 11119\n999, unrelated, 32000\n124, init, 100\n125, uncertain, N/A\nmalformed\n'
    assert gpu_activity(raw,{123,124,125})==[dict(pid=123,process='/app/llama-completion',used_memory_mib=11119)]
    assert gpu_activity(raw,{888})==[]


@pytest.mark.parametrize('failure',['exit','quiescence','container','gpu','backend','empty','repeat','model','wrong_arithmetic'])
def test_qualification_rejects_incomplete_evidence(failure):
    rows=[record(),record('CPU, memory and storage.'),record()];unchanged=True
    if failure=='exit':rows[0]['collector']['container_exit_code']=1
    elif failure=='quiescence':rows[0]['collector']['quiescent']=False
    elif failure=='container':rows[0]['container_removed']=False
    elif failure=='gpu':rows[0]['gpu_activity_confirmed']=False
    elif failure=='backend':rows[0]['cuda_backend_reported']=False
    elif failure=='empty':rows[1]['output']=' '
    elif failure=='repeat':rows[-1]['output']='43'
    elif failure=='model':unchanged=False
    elif failure=='wrong_arithmetic':rows[0]['output']=rows[-1]['output']='420 [end of text]'
    assert assess(rows,3,dict(repeat_first_last=True,arithmetic_expected='42'),unchanged)['status']=='failed'


def test_recorded_fallback_outputs_satisfy_functional_checks():
    rows=[record(),record('CPU, memory (RAM), and storage (hard drive/SSD). [end of text]\n'),record()]
    assert assess(rows,3,dict(repeat_first_last=True,arithmetic_expected='42'),True)==dict(status='success',repeated_output_equal=True,arithmetic_check=True)
    assert assess([record('Arbitrary user answer.')],1,{},True)['status']=='success'


def test_changed_worker_is_recorded_as_failure(store,monkeypatch):
    from jiuwenswarm.factory import runtime_job
    attempt=store.create_attempt('t',dict(kind='qualification',idem_key='changed-worker',fingerprint='pinned',request=dict(worker_sha256='incorrect',operation='collect')))
    monkeypatch.setenv('FACTORY_HOME',str(store.home))
    monkeypatch.setattr(sys,'argv',['runtime_job','--task','t','--attempt',attempt['attempt_id']])
    import signal
    handler=signal.getsignal(signal.SIGTERM)
    assert runtime_job.main()==1
    assert signal.getsignal(signal.SIGTERM)==handler
    result=json.loads((store.home/'runtime-jobs'/attempt['attempt_id']/'result.json').read_text())
    assert result['status']=='failed' and 'Worker changed' in result['error']
    assert store.read('t',attempt['attempt_id'])['result_refs']
