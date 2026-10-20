"""Durable explicit cancellation and honest pending containment acknowledgments."""
import asyncio

import pytest

from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.contracts import Principal,ResearchError
from jiuwenswarm.research.runner import CapsuleRunner,Registry
from jiuwenswarm.research.state import SQLiteRunStore


def test_containment_grant_requires_the_exact_durable_request_and_includes_closed_work(tmp_path):
    store=SQLiteRunStore(tmp_path);store.create_run('run',account_id='alice',workspace_id='project',submission={})
    runner=CapsuleRunner(store,Registry(),CheckRegistry(),model=None)
    request={'run_id':'run','request_id':'cancel:one'}
    with pytest.raises(ResearchError):runner.authorize_containment(request)
    store.request_cancellation('run','alice','cancel:one')
    store.append_record('invocation-budget-reservation',{'id':'reservation:closed','run_id':'run','invocation_id':'closed-invocation'})
    assert runner.authorize_containment(request)=={'authorized':True,**request,'invocation_ids':['closed-invocation']}
    with pytest.raises(ResearchError):runner.authorize_containment(request|{'request_id':'unrequested'})


@pytest.mark.asyncio
@pytest.mark.parametrize('ack',[True,False])
async def test_terminal_cancellation_requires_both_actual_owner_acknowledgments(tmp_path,ack):
    store=SQLiteRunStore(tmp_path);store.create_run('run',account_id='alice',workspace_id='project',submission={})
    entered,release=asyncio.Event(),asyncio.Event()
    class Owner:
        async def contain_run(self,run_id,request_id):
            entered.set();await release.wait()
            return {'contained':ack,'run_id':run_id,'request_id':request_id}
    service=ResearchService(store,registry=Registry(),model=Owner(),executor=Owner())
    actor=Principal('alice',frozenset({'project'}),frozenset({'cancel'}))
    cancel=asyncio.create_task(service.cancel(actor,'run','cancel:one'))
    await entered.wait()
    assert store.get_cancellation('run','cancel:one')['status']=='requested'
    assert store.get_run('run')['state']=='pending'
    release.set();value=await cancel
    assert value['status']==('terminal' if ack else 'requested')
    assert store.get_run('run')['state']==('halted' if ack else 'pending')
