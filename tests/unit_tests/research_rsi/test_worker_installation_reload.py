"""Late protected publication must not require restarting the observed worker."""
import asyncio
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi import security_installation as side
from jiuwenswarm.research_rsi import worker_bootstrap
from jiuwenswarm.research_rsi.worker import WorkerBroker,PublicBytes
from jiuwenswarm.research.contracts import rsi_installation as neutral


def test_absent_late_and_removed_installations_are_checked_on_every_effect(tmp_path,monkeypatch):
    worker=object.__new__(WorkerBroker);worker.public=PublicBytes([tmp_path])
    originals=tmp_path/'originals';originals.mkdir()
    monkeypatch.setattr(neutral,'ORIGINALS_ROOT',originals)
    calls=[];current=[None]
    class Authority:
        def require(self,operation,**subject):calls.append((operation,subject));return {'actual':'controlled-validator'}
    def load(actual,store,**kw):
        assert actual is worker and store=='capture' and kw=={'candidate_resolver':None}
        return current[0]
    monkeypatch.setattr(side,'build_worker_qualification',load)
    guard=side.WorkerQualificationOwner(worker,store='capture')
    with pytest.raises(side.InstallationUnavailable):guard.require('session_start',session_ref={'original':1})
    assert calls==[] and worker.public.roots==(tmp_path,)
    current[0]=Authority()
    assert guard.require('session_start',session_ref={'original':1})=={'actual':'controlled-validator'}
    assert worker.public.roots==(tmp_path,originals)
    guard.require('proposal',session_ref={'original':1})
    assert len(calls)==2
    current[0]=None
    with pytest.raises(side.InstallationUnavailable):guard.require('proposal',session_ref={'original':1})
    assert len(calls)==2


def test_scope_socket_starts_after_late_publication_and_closes_on_cancellation(monkeypatch):
    events=[];iterations=[None,SimpleNamespace(installation=SimpleNamespace(_raw=b'root-approved'))]
    class Owner:
        def current(self):return iterations.pop(0)
    class Server:
        async def start(self):events.append('start')
        async def close(self):events.append('close')
    def server(authority):
        assert authority.installation._raw==b'root-approved'
        return Server()
    async def pause(_):
        if not iterations:raise asyncio.CancelledError
    monkeypatch.setattr(side,'scope_server',server)
    monkeypatch.setattr(worker_bootstrap.asyncio,'sleep',pause)
    with pytest.raises(asyncio.CancelledError):asyncio.run(worker_bootstrap._observe_installation(Owner()))
    assert events==['start','close']
