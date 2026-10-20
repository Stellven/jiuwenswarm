from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Actual fixed-helper confinement mechanics; no RSI improvement/calibration."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import shutil

import pytest

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.worker import WorkerBroker,PublicBytes,DENIED_PATHS


@pytest.fixture
def actual_worker():
    configured=os.environ.get('AI4R_EXECUTOR_CGROUP_ROOT')
    if not configured:pytest.fail('BLOCKED: separate job-owned Linux cgroup delegation required')
    root=Path(tempfile.mkdtemp(prefix='ai4r-rsi-kernel-'));root.chmod(0o711)
    public=RecordStore(root/'public');requests=RecordStore(root/'requests');capture=RecordStore(root/'captures')
    pin=public.put({'controlled_fixture':'confinement mechanics only; no actual qualification'})
    profile=dict(schema='ai4r-rsi-worker-profile:1',target_kind='ranking-v1',session_ref=pin,target_ref=pin,
        parent_ref=pin,contract_ref=pin,environment_ref=pin,hardware_ref=pin,memory_mb=128,pids_max=16,timeout_s=5)
    profile_ref=public.put(profile)
    broker=WorkerBroker(qualification=ControlledQualification(),root=root/'broker',cgroup_root=configured,profiles=[profile_ref],public_reader=PublicBytes([public.root]),
        input_reader=PublicBytes([requests.root]),capture_store=capture,hidden=False)
    assert broker.executor.prerequisites()==[]
    def issue(body):
        candidate=public.put_bytes(body)
        inputs=requests.put({'scores':[{'idea_id':'b','eligible':True,'novelty':3,'feasibility':3,'compute_alignment':3},
            {'idea_id':'a','eligible':True,'novelty':3,'feasibility':3,'compute_alignment':3}]})
        reservation=requests.put({'session_ref':pin,'candidate_ref':candidate,'phase':'development','operation':os.urandom(8).hex()})
        return dict(profile_ref=profile_ref,session_ref=pin,candidate_ref=candidate,input_ref=inputs,
            reservation_ref=reservation,phase='development',repeat_index=0)
    yield broker,issue,capture,pin
    evidence=os.environ.get('AI4R_RSI_RAW_EVIDENCE')
    if not evidence:pytest.fail('BLOCKED: owned raw worker-capture destination required')
    destination=Path(evidence)/root.name;destination.mkdir(parents=True,exist_ok=False)
    for name,store in [('public',public),('requests',requests),('captures',capture)]:
        target=destination/name;target.mkdir()
        for path in store.root.glob('*.json'):shutil.copyfile(path,target/path.name)
    for item in broker.executor.owned_groups.values():
        group=item['path']
        assert group.resolve().parent==Path(configured).resolve()
        assert not (group/'cgroup.procs').read_text().strip()
        assert 'populated 0' in (group/'cgroup.events').read_text()
        group.rmdir()
    for store in (public,requests,capture):store.close()


@pytest.mark.asyncio
async def test_real_worker_helper_uid_limits_denied_roots_and_exact_output(actual_worker):
    broker,issue,capture,_=actual_worker
    from importlib.resources import files
    body=(files('jiuwenswarm.research')/'resources/capsules/ranking_parent.txt').read_bytes()
    result=await broker.run(issue(body));receipt=result['receipt']
    assert receipt['termination_reason']=='completed',capture.read(receipt['stderr_ref'])
    assert json.loads(capture.read(receipt['stdout_ref']))=={'ranking':[{'idea_id':'a','total':9,'rank':1},
        {'idea_id':'b','total':9,'rank':2}],'selected_idea_id':'a'}
    proof=json.loads(capture.read(receipt['observed_limits']['isolation_probe_ref']))
    assert proof['executor_uid']==12003 and proof['executor_gid']==12003 and proof['ready']
    assert proof['network']=='none' and proof['cap_effective']=='0000000000000000'
    assert set(proof['denied_paths'])==set(DENIED_PATHS) and all(proof['denied_paths'].values())
    assert receipt['observed_limits']['memory_max']==str(128*1024*1024)
    assert receipt['observed_limits']['pids_max']=='16' and not broker.executor.active


@pytest.mark.asyncio
async def test_real_worker_session_cancel_waits_for_kernel_tree_and_rejects_replay(actual_worker):
    broker,issue,_,session=actual_worker
    value=issue(b'def rank_opportunities(scores):\n import time\n time.sleep(30)\n return {}\n')
    running=asyncio.create_task(broker.run(value))
    try:
        async with asyncio.timeout(5):
            while not broker.executor.active:await asyncio.sleep(.01)
        assert (await broker.cancel({'session_ref':session}))['contained']
        assert running.done() and not broker.executor.active
        with pytest.raises(ValueError,match='cancelled'):await broker.run(value)
    finally:
        if not running.done():running.cancel()
        await asyncio.gather(running,return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['hidden_final','platform'])
async def test_real_frozen_timing_batch_iterations_are_executed_under_external_capture(actual_worker,phase):
    """Controlled mechanics vector, not an admitted target or speed claim."""
    from jiuwenswarm.research_rsi.records import encoded
    broker,issue,capture,_=actual_worker
    value=issue(b'calls=0\ndef rank_opportunities(scores):\n global calls\n calls+=1\n return {"calls":calls}\n')
    public=RecordStore(broker.public.roots[0]);requests=RecordStore(broker.inputs.roots[0])
    try:
        profile=dict(next(iter(broker.profiles.values())))
        profile['target_ref']=public.put({'controlled_fixture':'batch mechanics only','scoring':{'batch_iterations':3}})
        profile_ref=public.put(profile);broker.profiles[encoded(profile_ref)]=profile
        value.update(profile_ref=profile_ref,phase=phase,reservation_ref=requests.put({
            'session_ref':value['session_ref'],'candidate_ref':value['candidate_ref'],'phase':phase,'operation':'timing:controlled'}))
        broker.hidden=True
        result=await broker.run(value,timing=True);receipt=result['receipt']
        assert receipt['termination_reason']=='completed' and receipt['exit_code']==0
        assert json.loads(capture.read(receipt['stdout_ref']))=={'calls':3}
        assert receipt['wall_time_s']>0 and not broker.executor.active
    finally:
        requests.close();public.close()
