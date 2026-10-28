"""Collection mechanics only. Controlled RPC responses never qualify IF015.

Generated fixture inputs/labels exist only under actual Linux UID12002 in
private tmpfs, and are removed there. No operational calibration is performed.
"""
import asyncio
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_records.contracts import ContractData
from jiuwenswarm.research_rsi.calibration import (
    CalibrationLedger, CalibrationOutcomeUnknown, RankingCalibrationCollector,
    PLAN_SCHEMA, prepare_calibration_plan,
)
from jiuwenswarm.research_rsi.fixed_resources import FixtureEvaluator
from jiuwenswarm.research_rsi.qualification import QualificationUnavailable
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_rsi.targets import registered_helper
from jiuwenswarm.research_rsi.targets import ranking_preparation
from jiuwenswarm.research_rsi.worker import WorkerClient, worker_program, timing_program
from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification

ROOT = Path(__file__).parents[3]


def test_plan_contract_refuses_unbounded_or_ambiguous_execution():
    pin={'id':'unit:pin','sha256':'a'*64}
    plan=dict(schema='ai4r-rsi-calibration-plan:1',preparation_ref=pin,review_ref=pin,target_ref=pin,
              fixture_manifest_ref=pin,session_ref=pin,worker_profile_ref=pin,collector_ref=pin,
              target_context_sha256='b'*64,fixture_context_sha256='c'*64,fixture_identity='unit:fixture',
              pass_count_repeats=3,invocation_wall_s=.1,evidence_wall_s=30,wall_s=3600,
              reserved_wall_s=689,expected_invocations=6588)
    validate=ContractData().validate
    validate(PLAN_SCHEMA,plan)
    for changed in (dict(plan,wall_s=3601),dict(plan,invocation_wall_s=True),dict(plan,pass_count_repeats=2),
                    dict(plan,expected_invocations=100001),dict(plan,skip_qualification=True)):
        with pytest.raises(ValueError):validate(PLAN_SCHEMA,changed)


def test_calibration_ledger_cannot_be_created_by_non_custodian(tmp_path):
    store=RecordStore(tmp_path)
    if sys.platform=='linux' and os.geteuid()==12002:
        os.chmod(tmp_path,0o755)
    with pytest.raises(ValueError):CalibrationLedger(store)
    assert not (tmp_path/'calibration.sqlite').exists()
    store.close()


def _scope(store, *, seed, target_kind='ranking-v1'):
    from jiuwenswarm.research_rsi.targets.unrelated_helper import NORMALIZE_LABELS_PARENT
    ranking=target_kind=='ranking-v1'
    body=(ROOT/'jiuwenswarm/research/resources/capsules/ranking_parent.txt').read_bytes() if ranking else NORMALIZE_LABELS_PARENT
    path='ranking_parent.txt' if ranking else 'normalize.py';name='research.screening' if ranking else 'unit.labels'
    parent=store.put_bytes(body)
    declaration={'identity':{'name':name,'version_label':'unit-collection',
        'body':[{'path':path,'sha256':parent['sha256']}]},
        'evolution':{'rsi':'propose','may_change':['files:'+path]}}
    decl=store.put(declaration);origin=store.put({'unit':'Controlled collection provenance; no actual independent approval'})
    generator=store.put_bytes(Path(ranking_preparation.__file__).read_bytes())
    prep_ref=ranking_preparation.prepare_helper(store,target_kind=target_kind,parent_ref=parent,parent_declaration_ref=decl,
        declaration=declaration,author='unit:author',origin_ref=origin,generator_ref=generator,
        populations={'development':1,'hidden_loop':20,'hidden_final':20,'platform':3},seed=seed)
    review_ref=store.put(dict(schema='ai4r-rsi-ranking-review:1',preparation_ref=prep_ref,
        reviewer='unit:controlled-independent-review',provenance_approved=True,overlap_inventory_complete=True,
        development_disclosure_approved=False,independent=True,
        independence_reason='Controlled mechanics fixture only; not an operational independence finding',evidence_refs=[origin]))
    template=dict(schema_version='1.0.0',id='unit_collection_target',parent_ref=parent,parent_declaration_ref=decl,
        frozen_contract_ref=origin,required_test_refs=[origin],mutable_paths=[path],protected_refs=[origin],
        splits=dict(development='unit:d',hidden_loop='unit:l',hidden_final='unit:f',platform='unit:p'),
        scoring=dict(primary='passed_test_count',secondary='paired_time_at_equal_counts',warmup_batches=5,paired_rounds=7,
            min_relative_gain=.1,noise_multiplier=3,batch_iterations=1000,calibrated_relative_noise=.01),
        calibration_ref=origin,session_query_limit=30,lifetime_query_limit=90,
        limits=dict(time_s=1,model_calls=1,memory_mb=128),scoring_adapter_ref=origin,improver_ref=origin,configuration_ref=origin)
    target,manifest=ranking_preparation.draft_target(store,prep_ref,template,review_ref=review_ref,validate=ContractData().validate)
    target_ref=store.put(target);manifest['target_ref']=target_ref;manifest_ref=store.put(manifest)
    genesis=store.put({'unit':'Frozen collection genesis; not an operational session approval'})
    session=dict(schema_version='1.0.0',id='unit_collection_session',session_id='unit:collection:'+seed,
        target_profile_ref=target_ref,parent=dict(cc_name=name,cc_version='unit-collection',declaration_sha256=decl['sha256']),
        parent_declaration_ref=decl,improver_ref=origin,scoring_adapter_ref=origin,configuration_ref=origin,hash_profile_ref=origin,
        chain_root_ref=genesis,limits=dict(max_attempts=20,max_no_progress=5,wall_s=3600,per_call_s=300,
            session_query_limit=30,lifetime_query_limit=90),pass_count_repeats=1,
        qualification=dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        started_by='unit:owner',frozen_at='2026-10-25T00:00:00Z')
    ContractData().validate('rsi-session',session);session_ref=store.put(session)
    worker_profile=dict(schema='ai4r-rsi-worker-profile:2',target_kind=target_kind,session_ref=session_ref,
        target_ref=target_ref,parent_ref=parent,contract_ref=origin,environment_ref=origin,hardware_ref=origin,
        memory_mb=128,pids_max=8,timeout_s=.04)
    worker_ref=store.put(worker_profile)
    return dict(preparation_ref=prep_ref,review_ref=review_ref,target_ref=target_ref,fixture_manifest_ref=manifest_ref,
                session_ref=session_ref,worker_profile_ref=worker_ref)


class CollectionRPCDouble:
    """Authenticated response mechanics; no code or kernel measurement occurs."""
    def __init__(self,store,requests,scope,ledger,*,fail_on=None):
        self.store=store;self.requests=requests;self.scope=scope;self.ledger=ledger;self.fail_on=fail_on;self.calls=[]
        self.prep=store.get(scope['preparation_ref']);self.target=store.get(scope['target_ref'])
        self.bad={row['body_ref']['sha256'] for row in self.prep['children'] if row['kind']=='bad'}
        self.parent=self.target['parent_ref']

    async def call(self,operation,request,**kwargs):
        if operation=='cancel_session':return {'contained':True,'session_ref':request['session_ref']}
        assert operation in {'run_helper','run_timing_batch'}
        index=len(self.calls)+1
        # Actual durable exposure state precedes this controlled dispatch.
        state=self.ledger.lookup(self.prep['fixture_identity'],self.plan_ref)
        assert state['started']==index
        slot=self.ledger.db.execute('SELECT capture_ref FROM calibration_slots WHERE fixture=? AND ordinal=?',
            (self.prep['fixture_identity'],index)).fetchone()
        assert slot is not None and slot[0] is None
        self.calls.append(copy.deepcopy(request))
        if self.fail_on==index:raise RuntimeError('Controlled response loss; execution outcome unknown')
        value=self.requests.get(request['input_ref'])
        kind=self.store.get(self.scope['worker_profile_ref'])['target_kind']
        output=registered_helper(kind).reference(value)
        if request['candidate_ref']['sha256'] in self.bad:output={'unit':'Deliberately wrong control-double output'}
        stdout=self.requests.put(output);stderr=self.requests.put_bytes(b'')
        proof=self.requests.put({'ready':False,'unit':'No kernel isolation qualification in this RPC double'})
        profile=self.store.get(self.scope['worker_profile_ref'])
        duration=.02 if request['candidate_ref']==self.parent else .01
        receipt=dict(invocation_id='unit:collection:'+str(index),termination_reason='completed',exit_code=0,
            observed_runtime=False,identity=dict(executor_uid=12003,executor_gid=12003),contract_ref=profile['contract_ref'],
            timeout_s=profile['timeout_s'],wall_time_s=duration,stdout_ref=stdout,stderr_ref=stderr,
            observed_limits={'isolation_probe_ref':proof})
        timed=operation=='run_timing_batch';iterations=self.target['scoring']['batch_iterations'] if timed else 1
        program=timing_program(iterations,kind) if timed else worker_program(kind)
        return dict(schema='ai4r-rsi-worker-response:2',request=request,receipt=receipt,
            captures=[dict(ref=pin,bytes_base64=base64.b64encode(self.requests.read(pin)).decode()) for pin in (stdout,stderr,proof)],
            program_sha256=hashlib.sha256(program).hexdigest(),batch_iterations=iterations)


def _collector(store,requests,scope,ledger,plan_ref,*,qualification=None,approved=True,fail_on=None):
    target=store.get(scope['target_ref']);manifest=store.get(scope['fixture_manifest_ref'])
    rpc=CollectionRPCDouble(store,requests,scope,ledger,fail_on=fail_on);rpc.plan_ref=plan_ref
    worker=object.__new__(WorkerClient);worker.requests=requests;worker.profile_ref=scope['worker_profile_ref']
    worker.session_ref=scope['session_ref'];worker.hidden=True;worker.timeout_s=.5
    worker.target_kind=store.get(scope['worker_profile_ref'])['target_kind'];worker.batch_iterations=target['scoring']['batch_iterations'];worker.rpc=rpc
    evaluator=FixtureEvaluator(manifest=manifest,store=store,worker=worker,session_ref=scope['session_ref'],target=target,repeats=1)
    collector=RankingCalibrationCollector(store,ledger=ledger,evaluator=evaluator,qualification=qualification,
        approved_plan_refs=[plan_ref] if approved else [])
    return collector,rpc,evaluator


def controlled_main(root):
    """Runs in private Linux tmpfs as actual custodian; emits no fixture data."""
    import shutil
    os.setgid(12002);os.setuid(12002);os.umask(0o077)
    store=RecordStore(root/'store');requests=RecordStore(root/'requests');ledger=CalibrationLedger(store)
    try:
        scope=_scope(store,seed='unit:collection-private-seed-001')
        plan_ref=prepare_calibration_plan(store,**scope,invocation_wall_s=.5,evidence_wall_s=1,wall_s=3600)
        plan=store.get(plan_ref);fixture=plan['fixture_identity']
        collector,rpc,_=_collector(store,requests,scope,ledger,plan_ref,qualification=None)
        try:asyncio.run(collector.collect(plan_ref))
        except QualificationUnavailable:pass
        else:raise AssertionError('Unqualified collection executed')
        assert not rpc.calls and ledger.lookup(fixture,plan_ref) is None
        collector,rpc,_=_collector(store,requests,scope,ledger,plan_ref,qualification=ControlledQualification(),approved=False)
        try:asyncio.run(collector.collect(plan_ref))
        except ValueError:pass
        else:raise AssertionError('Unapproved plan executed')
        assert not rpc.calls and ledger.lookup(fixture,plan_ref) is None
        try:prepare_calibration_plan(store,**scope,invocation_wall_s=2,evidence_wall_s=1,wall_s=3600)
        except ValueError:pass
        else:raise AssertionError('Oversized execution plan accepted')
        collector,rpc,evaluator=_collector(store,requests,scope,ledger,plan_ref,qualification=ControlledQualification())
        result_ref=asyncio.run(collector.collect(plan_ref));result=store.get(result_ref)
        assert result['status']=='UNSIGNED_REVIEW_REQUIRED'
        proposal=store.get(result['proposal_ref'])
        assert 'signature' not in proposal and 'signer_key_id' not in proposal
        assert proposal['known_bad_rejected']==10 and proposal['known_good_qualified']==3
        assert len(rpc.calls)==plan['expected_invocations']==len(result['capture_refs'])
        assert len({(row['reservation_ref']['sha256'],row['repeat_index']) for row in rpc.calls})==len(rpc.calls)
        assert not any(row['candidate_ref']['sha256'] in rpc.bad and row['phase']!='platform' for row in rpc.calls)
        exposure=store.get(result['exposure_ref'])
        assert exposure['started_invocations']==plan['expected_invocations']
        assert all(row['capture_ref'] is not None for row in exposure['slots'])
        # Returning an unsigned proposal never turns a controlled response into
        # measured calibration: independent raw verification must reject it.
        signer=Signer.generate('unit:never-operational')
        try:ranking_preparation.verify_calibration2(signer.sign(proposal),target=evaluator.target,
            manifest=evaluator.manifest,store=store,public_key=signer.public_bytes(),key_id=signer.key_id)
        except ValueError:pass
        else:raise AssertionError('Controlled nonruntime captures certified calibration')
        before=len(rpc.calls)
        assert asyncio.run(collector.collect(plan_ref))==result_ref and len(rpc.calls)==before
        ledger.close();ledger=CalibrationLedger(store)
        collector,rpc,_=_collector(store,requests,scope,ledger,plan_ref,qualification=ControlledQualification())
        assert asyncio.run(collector.collect(plan_ref))==result_ref and not rpc.calls
        changed_ref=prepare_calibration_plan(store,**scope,invocation_wall_s=.6,evidence_wall_s=1,wall_s=3600)
        changed,changed_rpc,_=_collector(store,requests,scope,ledger,changed_ref,qualification=ControlledQualification())
        try:asyncio.run(changed.collect(changed_ref))
        except CalibrationOutcomeUnknown:pass
        else:raise AssertionError('Changed plan reset calibration lineage')
        assert not changed_rpc.calls
        # Response loss charges exactly one started slot; restart cannot replay.
        other=_scope(store,seed='unit:collection-private-seed-002')
        other_plan=prepare_calibration_plan(store,**other,invocation_wall_s=.5,evidence_wall_s=1,wall_s=3600)
        failed,failed_rpc,_=_collector(store,requests,other,ledger,other_plan,qualification=ControlledQualification(),fail_on=1)
        failed_ref=asyncio.run(failed.collect(other_plan));failure=store.get(failed_ref)
        assert failure['status']=='OUTCOME_UNKNOWN' and failure['proposal_ref'] is None
        assert len(failed_rpc.calls)==1
        assert store.get(failure['exposure_ref'])['started_invocations']==1
        assert asyncio.run(failed.collect(other_plan))==failed_ref and len(failed_rpc.calls)==1
        # A process loss immediately after the whole-plan claim has no terminal.
        third=_scope(store,seed='unit:collection-private-seed-003')
        third_plan=prepare_calibration_plan(store,**third,invocation_wall_s=.5,evidence_wall_s=1,wall_s=3600)
        third_value=store.get(third_plan);auth=store.put({'unit':'Controlled hard-loss start, no worker effect'})
        assert ledger.claim(third_value['fixture_identity'],third_plan,auth,third_value['expected_invocations'])
        ledger.close();ledger=CalibrationLedger(store)
        unknown,unknown_rpc,_=_collector(store,requests,third,ledger,third_plan,qualification=ControlledQualification())
        try:asyncio.run(unknown.collect(third_plan))
        except CalibrationOutcomeUnknown:pass
        else:raise AssertionError('Unknown calibration start replayed')
        assert not unknown_rpc.calls
        # The same actual custodian collection owner accepts an independently
        # declared unrelated helper, with its own closed original preparation.
        labels=_scope(store,seed='unit:collection-labels-seed-004',target_kind='normalize-labels-v1')
        labels_plan=prepare_calibration_plan(store,**labels,invocation_wall_s=.5,evidence_wall_s=1,wall_s=3600)
        label_collector,label_rpc,label_evaluator=_collector(store,requests,labels,ledger,labels_plan,qualification=ControlledQualification())
        labels_result=store.get(asyncio.run(label_collector.collect(labels_plan)))
        assert labels_result['status']=='UNSIGNED_REVIEW_REQUIRED'
        assert len(label_rpc.calls)==store.get(labels_plan)['expected_invocations']
        # A wrongly configured installed client must fail before durable claim
        # or any response dispatch, even when its registered kind is valid.
        label_collector.evaluator.worker.target_kind='ranking-v1'
        try:asyncio.run(label_collector.collect(labels_plan))
        except ValueError:pass
        else:raise AssertionError('Foreign calibration worker kind accepted')
        try:ranking_preparation.verify_calibration2(signer.sign(store.get(labels_result['proposal_ref'])),
            target=label_evaluator.target,manifest=label_evaluator.manifest,store=store,
            public_key=signer.public_bytes(),key_id=signer.key_id)
        except ValueError:pass
        else:raise AssertionError('Simulated normalize captures became real calibration')
    finally:
        ledger.close();requests.close();store.close();shutil.rmtree(root)


def test_actual_linux_custodian_collects_once_with_durable_slots_and_no_synthetic_qualification():
    if sys.platform!='linux' or os.geteuid()!=0:
        assert sys.platform!='linux' or os.geteuid()!=0
        return
    root=Path(tempfile.mkdtemp(prefix='rsi-calibration-control-',dir='/dev/shm'))
    os.chmod(root,0o700);os.chown(root,12002,12002)
    program='from pathlib import Path; import sys; from tests.unit_tests.research_rsi.test_calibration_collection import controlled_main; controlled_main(Path(sys.argv[1]))'
    completed=subprocess.run([sys.executable,'-B','-c',program,str(root)],capture_output=True,text=True,timeout=120)
    assert completed.returncode==0,completed.stderr
    assert completed.stdout=='' and not root.exists()
