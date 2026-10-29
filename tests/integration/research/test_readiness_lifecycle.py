"""Actual persistence/process/IPC lifecycle; controlled effects are labelled."""
import asyncio
import hashlib
import os
from pathlib import Path
import sys

import pytest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.contracts import Principal,ResearchError


@pytest.mark.asyncio
async def test_actual_owner_process_restart_pauses_without_replaying_effect(tmp_path):
    program='''import asyncio,sys
from jiuwenswarm.research.state import SQLiteRunStore
async def main():
 s=SQLiteRunStore(sys.argv[1]);s.create_run('restart',account_id='alice',workspace_id='project',submission={})
 s.set_run_state('restart','running');s.append_record('controlled-compiler-effect',{'id':'effect-once','run_id':'restart'})
 print('effect-captured',flush=True);await asyncio.Event().wait()
asyncio.run(main())
'''
    process=await asyncio.create_subprocess_exec(sys.executable,'-c',program,str(tmp_path/'state'),
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        assert await asyncio.wait_for(process.stdout.readline(),10)==b'effect-captured\n'
    finally:
        if process.returncode is None:process.kill()
        await asyncio.wait_for(process.wait(),5)
    store=SQLiteRunStore(tmp_path/'state',recover=True)
    try:
        assert store.get_run('restart')['state']=='paused'
        assert store.get_run('restart')['reason']=='interrupted'
        assert len(list(store.iter_records(kinds=('controlled-compiler-effect',))))==1
        assert store.recover_interrupted()==0
        assert not list(store.iter_records(kinds=('model-call','gate-decision','library-admission')))
    finally:store.close()


@pytest.mark.asyncio
async def test_actual_cancel_waits_for_both_effect_owners_and_preserves_partial_bytes(tmp_path):
    from jiuwenswarm.research.control import ResearchService
    from jiuwenswarm.research.runner import Registry
    store=SQLiteRunStore(tmp_path/'state');store.create_run('cancel',account_id='alice',workspace_id='project',submission={})
    store.set_run_state('cancel','running');raw=b'partial raw evidence'+b'x'*(1024*1024)
    ref=store.put_blob(raw);entered=asyncio.Event();release=asyncio.Event();seen=[]
    class Owner:
        async def contain_run(self,run_id,request_id):
            seen.append((run_id,request_id));entered.set();await release.wait()
            return {'contained':True,'run_id':run_id,'request_id':request_id}
    service=ResearchService(store,registry=Registry(),model=Owner(),executor=Owner())
    actor=Principal('alice',frozenset({'project'}),frozenset({'cancel'}))
    task=asyncio.create_task(service.cancel(actor,'cancel','cancel:one'))
    try:
        await asyncio.wait_for(entered.wait(),5)
        assert store.get_run('cancel')['state']=='running' and not task.done()
        release.set();result=await asyncio.wait_for(task,5)
        assert result['status']=='terminal' and store.get_run('cancel')['state']=='halted'
        assert store.read_blob(ref)==raw
        assert await service.cancel(actor,'cancel','cancel:one')==result and len(seen)==2
        store.create_run('later',account_id='alice',workspace_id='project',submission={})
        with pytest.raises(ResearchError):await service.cancel(actor,'later','cancel:one')
        assert len(seen)==2
    finally:
        release.set();await asyncio.gather(task,return_exceptions=True);store.close()


@pytest.mark.asyncio
async def test_client_disconnect_does_not_cancel_actual_owned_bridge_effect(tmp_path):
    from tests.integration.research.test_bridge import test_explicit_containment_waits_for_actual_owned_call_cleanup
    # This is the actual Unix client-disconnect/explicit-containment boundary,
    # with an independently controlled provider, not a live model qualification.
    await test_explicit_containment_waits_for_actual_owned_call_cleanup(tmp_path)


def test_complete_lossless_raw_capture_survives_reopen_and_capture_failure_latches(tmp_path):
    from tests.unit_tests.research.test_readiness_lifecycle import (
        test_raw_native_capture_survives_projection_limit_and_reopen,
        test_native_capture_failure_latches_and_cannot_be_reported_healthy)
    test_raw_native_capture_survives_projection_limit_and_reopen(tmp_path/'lossless')
    test_native_capture_failure_latches_and_cannot_be_reported_healthy(tmp_path/'failure')
