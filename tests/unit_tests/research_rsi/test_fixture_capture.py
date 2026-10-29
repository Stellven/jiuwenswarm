"""Public platform vectors and authenticated-response doubles, no confinement proof.

No hidden dataset is generated. These controls exercise the actual custodian
capture/paired methods using platform rows and an explicitly controlled worker.
"""
import asyncio
import base64
import copy
import hashlib

import pytest

from jiuwenswarm.research_rsi.fixed_resources import FixtureEvaluator
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.worker import worker_program, timing_program
from jiuwenswarm.research_records.contracts import ContractData


class AuthenticatedWorkerResponseDouble:
    """Models a validated worker-client return; never executes a candidate."""
    def __init__(self, requests, custody, *, session_ref, profile_ref, parent_ref,
                 expected, iterations, mutate=None, wrong_child=False, fail_at=None):
        self.requests=requests;self.custody=custody;self.session_ref=session_ref
        self.profile_ref=profile_ref;self.parent_ref=parent_ref;self.expected=expected
        self.iterations=iterations;self.mutate=mutate;self.wrong_child=wrong_child;self.fail_at=fail_at
        self.calls=[]

    async def run(self, candidate, inputs, *, phase, reservation_ref, repeat_index, timing):
        # Reservation durability precedes dispatch into this response double.
        assert self.custody.read(reservation_ref) == self.requests.read(reservation_ref)
        if self.fail_at is not None and len(self.calls) + 1 == self.fail_at:
            raise RuntimeError('Unit worker response unavailable; confinement NOT_RUN')
        pin=self.requests.put(inputs)
        request=dict(profile_ref=self.profile_ref, session_ref=self.session_ref, candidate_ref=candidate,
                     input_ref=pin, reservation_ref=reservation_ref, phase=phase, repeat_index=repeat_index)
        self.calls.append((copy.deepcopy(request), timing))
        output=self.expected[inputs['labels'][0]]
        if self.wrong_child and candidate != self.parent_ref: output={'unit':'deliberately wrong public platform output'}
        stdout=self.requests.put(output);stderr=self.requests.put_bytes(b'unit: controlled stderr')
        probe=self.requests.put({'unit':'Authenticated response double; kernel confinement NOT_RUN'})
        receipt=dict(termination_reason='completed', exit_code=0, stdout_ref=stdout, stderr_ref=stderr,
                     observed_limits={'isolation_probe_ref':probe}, wall_time_s=2 if candidate==self.parent_ref else 1,
                     invocation_id='unit:response:'+str(len(self.calls)))
        iterations=self.iterations if timing else 1
        program=timing_program(iterations,'normalize-labels-v1') if timing else worker_program('normalize-labels-v1')
        response=dict(schema='ai4r-rsi-worker-response:2', request=request, receipt=receipt,
                      captures=[dict(ref=item,bytes_base64=base64.b64encode(self.requests.read(item)).decode())
                                for item in (stdout,stderr,probe)],
                      program_sha256=hashlib.sha256(program).hexdigest(),batch_iterations=iterations)
        if self.mutate is not None:self.mutate(response)
        return response


def public_platform_evaluator(tmp_path, *, repeats=3, mutate=None, wrong_child=False, fail_at=None):
    custody=RecordStore(tmp_path/'custody-public-unit');requests=RecordStore(tmp_path/'requests-public-unit')
    session=custody.put({'unit':'platform capture session; no hidden population or operational authority'})
    profile=custody.put({'unit':'profile identity for authenticated-response double'})
    parent=custody.put_bytes(b'# unit parent source identity; never executed\n')
    child=custody.put_bytes(b'# unit child source identity; never executed\n')
    configuration=custody.put({'unit':'fixed public platform capture configuration'})
    expected={'public-a':{'unit_result':'a'},'public-b':{'unit_result':'b'}}
    rows=[dict(id=name,input_ref=custody.put({'labels':[name]}),expected_ref=custody.put(output))
          for name,output in expected.items()]
    # Isolate actual platform methods without constructing a hidden suite.
    evaluator=object.__new__(FixtureEvaluator)
    evaluator.store=custody;evaluator.session_ref=session;evaluator.repeats=repeats
    evaluator.manifest={'partitions':{'platform':rows},'independent':False};evaluator.last_evidence=[]
    evaluator.target={'configuration_ref':configuration,'scoring':{'batch_iterations':11,'calibrated_relative_noise':.01}}
    evaluator.worker=AuthenticatedWorkerResponseDouble(requests,custody,session_ref=session,profile_ref=profile,
        parent_ref=parent,expected=expected,iterations=11,mutate=mutate,wrong_child=wrong_child,fail_at=fail_at)
    return evaluator,parent,child,rows


@pytest.mark.parametrize('timed',[False,True])
def test_actual_one_copies_exact_input_reservation_and_raw_captures_before_capture2(tmp_path,timed):
    evaluator,parent,_,rows=public_platform_evaluator(tmp_path)
    passed,duration=asyncio.run(evaluator.one(parent,rows[0],'platform','timing:unit' if timed else 'unit:ordinary',2,timing=timed))
    assert (passed,duration)==(1,2)
    assert len(evaluator.last_evidence)==1
    record=evaluator.store.get(evaluator.last_evidence[0])
    ContractData().validate('urn:ai4r:private:rsi-fixture-capture:2',record)
    assert record['schema']=='ai4r-rsi-fixture-capture:2'
    assert record['timing'] is timed and record['batch_iterations']==(11 if timed else 1)
    assert record['worker_profile_ref']==evaluator.worker.profile_ref and record['repeat_index']==2
    assert record['input_ref']==rows[0]['input_ref'] and record['candidate_ref']==parent
    reservation=evaluator.store.get(record['reservation_ref'])
    assert reservation==dict(schema='ai4r-rsi-worker-reservation:1',session_ref=evaluator.session_ref,
        candidate_ref=parent,phase='platform',operation='timing:unit' if timed else 'unit:ordinary',fixture_id=rows[0]['id'])
    for pin in (record['input_ref'],record['reservation_ref'],record['receipt']['stdout_ref'],
                record['receipt']['stderr_ref'],record['receipt']['observed_limits']['isolation_probe_ref']):
        assert evaluator.store.read(pin)==evaluator.worker.requests.read(pin)
    assert record['program_sha256']==hashlib.sha256(timing_program(11,'normalize-labels-v1') if timed else worker_program('normalize-labels-v1')).hexdigest()
    evaluator.store.close();evaluator.worker.requests.close()


@pytest.mark.parametrize('field',['session_ref','candidate_ref','input_ref','reservation_ref','phase','repeat_index'])
def test_actual_one_rejects_foreign_scope_metadata_before_recording_fixture_capture(tmp_path,field):
    def mutate(response):
        if field.endswith('_ref'):response['request'][field]={'id':'unit:foreign','sha256':'f'*64}
        elif field=='phase':response['request'][field]='development'
        else:response['request'][field]=1
    evaluator,parent,_,rows=public_platform_evaluator(tmp_path,mutate=mutate)
    with pytest.raises(ValueError,match='Private worker input/scope differs'):
        asyncio.run(evaluator.one(parent,rows[0],'platform','unit:scope',0))
    assert evaluator.last_evidence==[]
    # Charge/start evidence remains private even after a rejected response.
    request=evaluator.worker.calls[0][0]
    assert evaluator.store.read(request['reservation_ref'])==evaluator.worker.requests.read(request['reservation_ref'])
    evaluator.store.close();evaluator.worker.requests.close()


@pytest.mark.parametrize('mutation',['legacy_response','missing_capture','extra_field'])
def test_actual_one_rejects_untyped_or_incomplete_response2(tmp_path,mutation):
    def mutate(response):
        if mutation=='legacy_response':response['schema']='ai4r-rsi-worker-response:1'
        elif mutation=='missing_capture':response['captures'].pop()
        else:response['callback']='untrusted'
    evaluator,parent,_,rows=public_platform_evaluator(tmp_path,mutate=mutate)
    with pytest.raises(ValueError,match='contract validation failed'):
        asyncio.run(evaluator.one(parent,rows[0],'platform','unit:version',0))
    assert evaluator.last_evidence==[]
    evaluator.store.close();evaluator.worker.requests.close()


def test_paired_retains_parent_child_quality_and_all_warmup_and_timing_capture_refs(tmp_path):
    evaluator,parent,child,rows=public_platform_evaluator(tmp_path,repeats=3)
    result=asyncio.run(evaluator.paired(parent,child,'platform',3,evaluator.target['configuration_ref']))
    expected_count=26*len(rows)*3
    assert len(evaluator.last_evidence)==len(evaluator.worker.calls)==expected_count
    assert len({pin['sha256'] for pin in evaluator.last_evidence})==expected_count
    records=[evaluator.store.get(pin) for pin in evaluator.last_evidence]
    ordinary=2*len(rows)*3
    assert all(not row['timing'] for row in records[:ordinary]) and all(row['timing'] for row in records[ordinary:])
    assert [row['candidate_ref'] for row in records[:ordinary]]==[parent]*(len(rows)*3)+[child]*(len(rows)*3)
    expected_order=[]
    for round_index in range(12):
        for candidate in ((parent,child) if round_index%2==0 else (child,parent)):
            expected_order.extend([candidate]*(len(rows)*3))
    assert [row['candidate_ref'] for row in records[ordinary:]]==expected_order
    assert result['parent']==result['child']==[[1,1,1]]*len(rows)
    assert result['parent_times']==[2*len(rows)*3]*7 and result['child_times']==[len(rows)*3]*7
    assert result['warmups']==5 and evaluator._collecting is False
    retained=list(evaluator.last_evidence)
    assert asyncio.run(evaluator.mandatory(parent)) is True
    assert len(evaluator.last_evidence)==len(rows)*3
    assert all(evaluator.store.get(pin)['schema']=='ai4r-rsi-fixture-capture:2' for pin in retained)
    evaluator.store.close();evaluator.worker.requests.close()


def test_unequal_scores_keep_both_quality_capture_sets_without_timing(tmp_path):
    evaluator,parent,child,rows=public_platform_evaluator(tmp_path,wrong_child=True)
    result=asyncio.run(evaluator.paired(parent,child,'platform',3,evaluator.target['configuration_ref']))
    assert len(evaluator.last_evidence)==2*len(rows)*3
    assert not any(timed for _,timed in evaluator.worker.calls)
    assert result['parent']==[[1,1,1]]*len(rows) and result['child']==[[0,0,0]]*len(rows)
    assert evaluator._collecting is False
    evaluator.store.close();evaluator.worker.requests.close()


def test_paired_failure_retains_completed_capture_and_releases_collection_mode(tmp_path):
    evaluator,parent,child,_=public_platform_evaluator(tmp_path,fail_at=2)
    with pytest.raises(RuntimeError,match='Unit worker response unavailable'):
        asyncio.run(evaluator.paired(parent,child,'platform',3,evaluator.target['configuration_ref']))
    assert evaluator._collecting is False and len(evaluator.last_evidence)==1
    assert evaluator.store.get(evaluator.last_evidence[0])['candidate_ref']==parent
    evaluator.store.close();evaluator.worker.requests.close()
