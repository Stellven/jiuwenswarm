"""Real Linux IPC/process/store; no external provider or qualification claim."""
import asyncio
from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import time
import pytest
from jiuwenswarm.research.router_client import RouterPort,PlatformIntegrityError


def _serve(path,audit,data_root):
    from jiuwenswarm.research_router.engine import DecisionEngine
    from jiuwenswarm.research_router.request_validation import ProtectedData
    from jiuwenswarm.research_router.contracts import ContractData
    from jiuwenswarm.research_router.service import RouterService
    engine=DecisionEngine(data=ProtectedData([data_root]),validate=ContractData().validate,audit_root=audit,
        catalog_ref={'id':'absent','sha256':'a'*64},profile_refs=[],development_profiles_ref={'id':'absent','sha256':'a'*64},adapter_revision='disposable:1')
    asyncio.run(RouterService(engine,[os.getuid()]).serve(path))


def test_real_process_rejects_forged_original_without_fallback(tmp_path):
    if not hasattr(os,'getuid'):pytest.fail('BLOCKED: qualified Linux Unix peer credentials required')
    fixture=Path(__file__).resolve().parents[3]/'fixtures/research/router/protected-capture'
    value=json.loads((fixture/'request.json').read_bytes());value['selected_capsule']['declaration']['identity']['summary']='forged'
    path=tmp_path/'router.sock'
    child=multiprocessing.Process(target=_serve,args=(str(path),str(tmp_path/'audit'),str(fixture)))
    child.start()
    try:
        until=time.monotonic()+10
        while not path.exists() and time.monotonic()<until:
            if not child.is_alive():pytest.fail('router process exited before IPC readiness')
            time.sleep(.01)
        assert path.exists()
        port=RouterPort(path,peer_uid=os.getuid())
        context={'call_function':'worker','router':{'enabled':True,'deadline_s':30,'profile_ref':{'id':'p','sha256':'b'*64}},'route_request':value,'approved_model_ids':[]}
        with pytest.raises(PlatformIntegrityError):asyncio.run(port.select(context))
        import sqlite3
        with sqlite3.connect(tmp_path/'audit/audit.sqlite') as db:assert db.execute('SELECT count(*) FROM claims').fetchone()[0]==0
    finally:
        child.terminate();child.join(5)
